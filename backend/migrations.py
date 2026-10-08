"""Alembic integration for the application runtime.

Schema is owned by Alembic (``alembic/versions``). Historically the app applied
``ALTER TABLE`` statements at import time; databases created that way have all the
tables but no ``alembic_version`` row, so upgrading them would try to re-create
tables that already exist.

:func:`run_alembic_upgrade` therefore adopts a pre-Alembic database by *stamping*
the baseline revision, and only then brings it up to head. That makes the upgrade
safe to run on an existing installation and idempotent on repeat starts.
"""

import logging
from typing import List

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

from .config import REPO_ROOT

logger = logging.getLogger(__name__)

BASELINE_REVISION = "0001_baseline"


def _alembic_config() -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", "")  # env.py supplies the real URL
    return cfg


def current_revision(bind) -> str | None:
    """The revision the database is currently at, or None if never migrated."""
    with bind.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def _has_application_tables(bind) -> bool:
    inspector = inspect(bind)
    # `users` and `patients` exist in every version of the schema, so their
    # presence means this is a real installation rather than a fresh database.
    return inspector.has_table("users") or inspector.has_table("patients")


def run_alembic_upgrade(bind) -> List[str]:
    """Bring ``bind`` up to head. Returns a human-readable log of what happened."""
    applied: List[str] = []
    before = current_revision(bind)
    has_version_table = inspect(bind).has_table("alembic_version")

    if not has_version_table and _has_application_tables(bind):
        # Pre-Alembic installation: declare it to be at the baseline.
        logger.info(
            "Existing database detected without Alembic history; stamping %s.", BASELINE_REVISION
        )
        command.stamp(_alembic_config(), BASELINE_REVISION)
        applied.append(f"stamped {BASELINE_REVISION} (adopted existing schema)")
        before = BASELINE_REVISION

    command.upgrade(_alembic_config(), "head")

    after = current_revision(bind)
    if after != before:
        applied.append(f"upgraded {before or 'base'} -> {after}")
    return applied
