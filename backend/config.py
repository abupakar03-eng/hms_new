"""Centralised, validated application configuration.

Previously every setting was read ad-hoc with ``os.getenv`` in ``auth.py``,
``database.py`` and ``main.py``, which meant a typo in an environment variable
name silently fell back to a default. All configuration now flows through one
validated :class:`Settings` object.

Environment variable names are unchanged from the previous implementation, so
existing deployments keep working.

    SECRET_KEY, DATABASE_URL, CORS_ORIGINS, ADMIN_PASSWORD, SERVE_FRONTEND,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, BCRYPT_ROUNDS,
    MAX_FAILED_ATTEMPTS, LOCKOUT_MINUTES, PASSWORD_MIN_LENGTH,
    PASSWORD_REQUIRE_UPPER, RATE_LIMIT_MAX_REQUESTS

Values can also be supplied in a ``.env`` file at the repository root.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_PATH = REPO_ROOT / "hms_local.db"

_DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -------------------------------------------------------
    app_name: str = "Hospital Management & Billing API"
    app_version: str = "3.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    # "text" for a console, "json" for log collectors (one object per line).
    log_format: Literal["text", "json"] = "text"
    log_level: str = "INFO"

    # --- Database ----------------------------------------------------------
    # Empty means "use the local SQLite file"; set a full SQLAlchemy URL for
    # PostgreSQL, e.g. postgresql+psycopg2://user:pass@host:5432/hms
    database_url: Optional[str] = None
    db_pool_size: int = Field(5, ge=1, le=100)
    db_max_overflow: int = Field(10, ge=0, le=200)
    db_pool_recycle_seconds: int = Field(1800, ge=0)
    db_echo: bool = False

    # --- Security ----------------------------------------------------------
    secret_key: Optional[str] = None
    access_token_expire_minutes: int = Field(480, ge=5, le=10080)
    refresh_token_expire_days: int = Field(1, ge=1, le=90)
    bcrypt_rounds: int = Field(12, ge=4, le=16)
    max_failed_attempts: int = Field(5, ge=1, le=50)
    lockout_minutes: int = Field(15, ge=1, le=1440)
    password_min_length: int = Field(8, ge=6, le=128)
    password_require_upper: bool = True

    # --- HTTP --------------------------------------------------------------
    cors_origins: str = ",".join(_DEFAULT_CORS_ORIGINS)
    serve_frontend: bool = True
    rate_limit_window_seconds: int = Field(60, ge=1, le=3600)
    rate_limit_max_requests: int = Field(300, ge=10, le=100000)
    trusted_hosts: str = "*"

    # --- Bootstrap ---------------------------------------------------------
    # Only used when the database contains no users at all.
    admin_password: Optional[str] = None

    @field_validator("database_url")
    @classmethod
    def _default_to_sqlite(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v
        return None

    @property
    def resolved_database_url(self) -> str:
        """The URL actually handed to SQLAlchemy."""
        return self.database_url or f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"

    @property
    def is_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_host_list(self) -> List[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    def sqlalchemy_engine_options(self) -> dict:
        """Engine kwargs that are correct for the configured dialect."""
        options: dict = {"echo": self.db_echo, "pool_pre_ping": True}

        if self.is_sqlite:
            # SQLite is used single-process by uvicorn's default worker, so the
            # default pool is fine; only the thread check needs relaxing.
            options["connect_args"] = {"check_same_thread": False}
        else:
            options.update(
                {
                    "pool_size": self.db_pool_size,
                    "max_overflow": self.db_max_overflow,
                    "pool_recycle": self.db_pool_recycle_seconds,
                }
            )
        return options

    def validate_for_production(self) -> List[str]:
        """Return configuration problems that must block a production start."""
        problems: List[str] = []
        if not self.is_production:
            return problems

        if not self.secret_key:
            problems.append(
                "SECRET_KEY is not set. Production must not rely on the generated file key."
            )
        elif len(self.secret_key) < 32:
            problems.append("SECRET_KEY is shorter than 32 characters.")

        if self.is_sqlite:
            problems.append(
                "DATABASE_URL points at SQLite. Use PostgreSQL for production so that "
                "concurrent writers and backups are safe."
            )

        if "*" in self.trusted_host_list:
            problems.append("TRUSTED_HOSTS is '*' — restrict it to the real hostnames.")

        if self.debug:
            problems.append("DEBUG is enabled in production.")

        if self.serve_frontend:
            problems.append(
                "SERVE_FRONTEND is enabled — serve the built assets from a CDN or reverse "
                "proxy instead so the API process is not also a file server."
            )
        return problems


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
