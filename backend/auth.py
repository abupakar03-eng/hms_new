"""Authentication, authorisation and password policy.

Key changes from the previous revision:

* ``SECRET_KEY`` is read from the environment. If it is absent a random key is
  generated once and persisted to ``.secret_key`` next to the repository root,
  and a loud warning is logged. A hard-coded key in source control means every
  deployment shares signing material and any leaked copy forges admin tokens.
* Token revocation is persisted, so ``/logout`` survives a restart.
* ``validate_password_strength`` is actually enforced on user creation and
  password reset (it previously existed but was never called).
* ``require_roles`` replaces scattered ``role != "Admin"`` checks.
"""

import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from . import constants, models
from .config import REPO_ROOT, settings
from .database import get_db

logger = logging.getLogger(__name__)

# ============================
# Security configuration
# ============================
# Values come from backend.config (validated, .env-aware). The module-level names
# are kept because main.py and the test suite read them.
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.refresh_token_expire_days
MAX_FAILED_ATTEMPTS = settings.max_failed_attempts
LOCKOUT_MINUTES = settings.lockout_minutes
BCRYPT_ROUNDS = settings.bcrypt_rounds
PASSWORD_MIN_LENGTH = settings.password_min_length
PASSWORD_REQUIRE_UPPER = settings.password_require_upper

SECRET_FILE = REPO_ROOT / ".secret_key"


def _load_secret_key() -> str:
    if settings.secret_key:
        return settings.secret_key

    if SECRET_FILE.exists():
        stored = SECRET_FILE.read_text(encoding="utf-8").strip()
        if stored:
            logger.warning(
                "SECRET_KEY not set; using the locally persisted key in %s. "
                "Set the SECRET_KEY environment variable before deploying.",
                SECRET_FILE,
            )
            return stored

    generated = secrets.token_urlsafe(64)
    try:
        SECRET_FILE.write_text(generated, encoding="utf-8")
        os.chmod(SECRET_FILE, 0o600)
    except OSError as exc:  # pragma: no cover - filesystem dependent
        logger.warning("Could not persist generated SECRET_KEY (%s); tokens will not survive restart.", exc)
    logger.warning(
        "SECRET_KEY was not configured. A random key was generated and stored at %s. "
        "Set the SECRET_KEY environment variable for production deployments.",
        SECRET_FILE,
    )
    return generated


SECRET_KEY = _load_secret_key()
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)

# Failed login tracking: (username, client_ip) -> {count, locked_until}.
# Keying on the client as well as the username stops anyone on the network from
# locking the real administrator out by spraying wrong passwords at `admin`.
FAILED_LOGINS: dict = {}


# ============================
# Password hashing
# ============================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash in the database must not leak as a 500.
        return False


def get_password_hash(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def password_policy_errors(password: str) -> list[str]:
    """Return the list of policy violations for ``password`` (empty when valid)."""
    errors: list[str] = []
    if len(password or "") < PASSWORD_MIN_LENGTH:
        errors.append(f"at least {PASSWORD_MIN_LENGTH} characters")
    if not re.search(r"[A-Za-z]", password or ""):
        errors.append("at least one letter")
    if not re.search(r"\d", password or ""):
        errors.append("at least one digit")
    if PASSWORD_REQUIRE_UPPER and not re.search(r"[A-Z]", password or ""):
        errors.append("at least one uppercase letter")
    return errors


def validate_password_strength(password: str) -> bool:
    """Backwards-compatible boolean wrapper around :func:`password_policy_errors`."""
    return not password_policy_errors(password)


def assert_password_strength(password: str) -> None:
    errors = password_policy_errors(password)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain " + ", ".join(errors) + ".",
        )


# ============================
# Brute force protection
# ============================
def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _lockout_key(username: str, client_ip: Optional[str]) -> tuple:
    return ((username or "").lower(), client_ip or "unknown")


def check_account_lockout(username: str, client_ip: Optional[str] = None) -> None:
    """Raise if this username is currently locked out for this client."""
    key = _lockout_key(username, client_ip)
    data = FAILED_LOGINS.get(key)
    if not data:
        return
    locked_until = data.get("locked_until")
    if locked_until and _utcnow() < locked_until:
        remaining = int((locked_until - _utcnow()).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Account temporarily locked due to {MAX_FAILED_ATTEMPTS} failed attempts. "
                f"Try again in {remaining} minute(s)."
            ),
            headers={"Retry-After": str(remaining * 60)},
        )
    if locked_until and _utcnow() >= locked_until:
        FAILED_LOGINS.pop(key, None)


def record_failed_login(username: str, client_ip: Optional[str] = None) -> None:
    """Record a failed attempt and lock this username for this client at the threshold."""
    entry = FAILED_LOGINS.setdefault(_lockout_key(username, client_ip), {"count": 0, "locked_until": None})
    entry["count"] += 1
    if entry["count"] >= MAX_FAILED_ATTEMPTS:
        entry["locked_until"] = _utcnow() + timedelta(minutes=LOCKOUT_MINUTES)


def reset_failed_logins(username: str, client_ip: Optional[str] = None) -> None:
    FAILED_LOGINS.pop(_lockout_key(username, client_ip), None)


# ============================
# JWT
# ============================
def _encode(data: dict, expires_delta: timedelta, token_type: str) -> str:
    now = _utcnow()
    payload = data.copy()
    payload.update(
        {
            "exp": now + expires_delta,
            "iat": now,
            "type": token_type,
            # Without a unique id, two logins by the same user inside the same
            # second produce byte-identical tokens; blacklisting one (logout)
            # would then also revoke the other session.
            "jti": secrets.token_urlsafe(16),
        }
    )
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    return _encode(data, expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES), "access")


def create_refresh_token(data: dict) -> str:
    return _encode(data, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS), "refresh")


def decode_token(token: str, expected_type: str = "access") -> dict:
    """Decode and validate a JWT. Raises ``HTTPException(401)`` on any problem."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise credentials_exception

    if payload.get("sub") is None or payload.get("type", "access") != expected_type:
        raise credentials_exception
    return payload


# ============================
# Token revocation (persisted)
# ============================
def blacklist_token(db: Session, token: str, username: Optional[str] = None) -> None:
    """Persist a revoked token. Also prunes rows whose expiry has passed."""
    if not token:
        return
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        expires_at = datetime.utcfromtimestamp(payload["exp"]) if "exp" in payload else _utcnow()
    except JWTError:
        expires_at = _utcnow()

    if not db.query(models.TokenBlacklist).filter(models.TokenBlacklist.token == token).first():
        db.add(models.TokenBlacklist(token=token, username=username, expires_at=expires_at))

    # Opportunistic cleanup keeps the table from growing forever.
    db.query(models.TokenBlacklist).filter(models.TokenBlacklist.expires_at < _utcnow()).delete(
        synchronize_session=False
    )
    db.commit()


def is_token_blacklisted(db: Session, token: str) -> bool:
    return db.query(models.TokenBlacklist).filter(models.TokenBlacklist.token == token).first() is not None


def _issued_before_password_change(payload: dict, user: models.User) -> bool:
    changed = getattr(user, "password_changed_at", None)
    iat = payload.get("iat")
    if changed is None or iat is None:
        return False
    # iat has one-second resolution; a token minted in the same second as the
    # change (i.e. the new session itself) stays valid.
    return int(iat) < int(changed.replace(tzinfo=timezone.utc).timestamp())


def mark_password_changed(user: models.User) -> None:
    """Invalidate every token issued to ``user`` before now. Caller commits."""
    user.password_changed_at = _utcnow()


def authenticate_refresh_token(db: Session, token: Optional[str]) -> models.User:
    """Validate a refresh token: signature, type, revocation and owner state."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
    )
    if not token:
        raise credentials_exception
    payload = decode_token(token, "refresh")
    if is_token_blacklisted(db, token):
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == payload["sub"]).first()
    if user is None or not user.is_active or _issued_before_password_change(payload, user):
        raise credentials_exception
    return user


# ============================
# Input validation helpers
# ============================
def sanitize_input(value: str) -> str:
    """Strip HTML tags and quote characters from free-text user input."""
    if not value:
        return value
    sanitized = re.sub(r"<[^>]+>", "", value)
    sanitized = re.sub(r"[<>\"']", "", sanitized)
    return sanitized.strip()


def validate_phone(phone: str) -> bool:
    return bool(re.match(r"^[6-9]\d{9}$", phone.replace(" ", "").replace("-", "")))


def validate_aadhaar(aadhaar: str) -> bool:
    return bool(re.match(r"^\d{12}$", aadhaar.replace(" ", "")))


def validate_gst(gst: str) -> bool:
    return bool(re.match(r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$", gst.upper()))


# ============================
# FastAPI dependencies
# ============================
def authenticate_token(db: Session, token: Optional[str]) -> models.User:
    """Validate a raw bearer token and return the owning active user."""
    payload = decode_token(token or "", "access")
    if is_token_blacklisted(db, token or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(models.User).filter(models.User.username == payload["sub"]).first()
    if user is None or not user.is_active or _issued_before_password_change(payload, user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_token_raw(token: Optional[str] = Depends(oauth2_scheme)) -> str:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def get_current_user(
    token: str = Depends(get_token_raw), db: Session = Depends(get_db)
) -> models.User:
    return authenticate_token(db, token)


def require_roles(*roles: str):
    """Dependency factory enforcing that the caller holds one of ``roles``."""

    allowed: Sequence[str] = roles

    def _guard(current_user: models.User = Depends(get_current_user)) -> models.User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient privileges. Required role: {', '.join(allowed)}.",
            )
        return current_user

    return _guard


get_current_admin = require_roles("Admin")
require_staff = require_roles(*constants.STAFF_ROLES)


def get_current_patient(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
) -> models.Patient:
    """Resolve the patient behind a self-service account.

    Every ``/portal/*`` endpoint depends on this and must scope its queries with
    ``patient.id`` — never with a patient id taken from the request — so that one
    patient can never read another patient's records.
    """
    if current_user.role != constants.PATIENT_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is for patient accounts. Please use the staff sign-in.",
        )
    if not current_user.patient_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is not linked to a patient record. Contact the hospital.",
        )
    patient = db.query(models.Patient).filter(models.Patient.id == current_user.patient_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not found.")
    return patient
