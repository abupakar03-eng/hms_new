"""Database backups for a local installation.

Usage (from the repository root)::

    python -m backend.backup                 # back up now, keep the newest 14
    python -m backend.backup --keep 30
    python -m backend.backup --dir D:/hms-backups
    python -m backend.backup --list

SQLite is copied with SQLite's online backup API, which produces a consistent
snapshot even while the app is writing (a plain file copy can capture a torn
page). PostgreSQL is dumped with ``pg_dump`` in custom format, which must be on
PATH. Schedule it daily with Windows Task Scheduler, e.g.::

    schtasks /Create /SC DAILY /ST 23:30 /TN "HMS backup" ^
      /TR "cmd /c cd /d C:\\path\\to\\hospital_os && python -m backend.backup"
"""

import argparse
import contextlib
import logging
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy.engine import make_url

from .config import REPO_ROOT, settings

logger = logging.getLogger("hospital_os.backup")

DEFAULT_DIR = REPO_ROOT / "backups"
PREFIX = "hms-"


def _target(target_dir: Path, suffix: str) -> Path:
    """A new, unused file name; two backups in the same second must not collide."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path, n = target_dir / f"{PREFIX}{stamp}{suffix}", 1
    while path.exists():
        path, n = target_dir / f"{PREFIX}{stamp}-{n}{suffix}", n + 1
    return path


def backup_sqlite(source: Path, target_dir: Path) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"SQLite database not found at {source}")
    target = _target(target_dir, ".sqlite3")
    # closing(): sqlite3's own context manager only commits, it never closes, and
    # an open handle keeps the file locked on Windows.
    with contextlib.closing(sqlite3.connect(str(source))) as src,             contextlib.closing(sqlite3.connect(str(target))) as dst:
        src.backup(dst)
    # Fail loudly rather than keep a corrupt backup.
    with contextlib.closing(sqlite3.connect(str(target))) as check:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Backup failed its integrity check: {result}")
    return target


def backup_postgres(url: str, target_dir: Path) -> Path:
    if shutil.which("pg_dump") is None:
        raise RuntimeError("pg_dump was not found on PATH; install the PostgreSQL client tools.")
    target = _target(target_dir, ".dump")
    # pg_dump accepts a libpq URL; drop the SQLAlchemy driver suffix (+psycopg2).
    libpq_url = make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)
    subprocess.run(["pg_dump", "--format=custom", f"--file={target}", libpq_url], check=True)
    return target


def prune(target_dir: Path, keep: int) -> List[Path]:
    # Names sort chronologically (timestamp, then collision counter).
    backups = sorted(target_dir.glob(f"{PREFIX}*"), key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    removed = backups[keep:]
    for path in removed:
        path.unlink()
    return removed


def run_backup(target_dir: Optional[Path] = None, keep: int = 14) -> Path:
    target_dir = Path(target_dir or DEFAULT_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    url = settings.resolved_database_url
    if settings.is_sqlite:
        source = Path(make_url(url).database or "")
        if not source.is_absolute():
            source = REPO_ROOT / source
        path = backup_sqlite(source, target_dir)
    else:
        path = backup_postgres(url, target_dir)
    prune(target_dir, keep)
    return path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Back up the hospital database.")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="where to write backups")
    parser.add_argument("--keep", type=int, default=14, help="how many recent backups to keep")
    parser.add_argument("--list", action="store_true", help="list existing backups and exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.list:
        for path in sorted(Path(args.dir).glob(f"{PREFIX}*")):
            print(f"{path.name}\t{path.stat().st_size // 1024} KB")
        return 0
    try:
        path = run_backup(args.dir, args.keep)
    except Exception as exc:  # surfaced to Task Scheduler as a non-zero exit
        logger.error("Backup failed: %s", exc)
        return 1
    logger.info("Backup written to %s (%d KB)", path, path.stat().st_size // 1024)
    return 0


if __name__ == "__main__":
    sys.exit(main())
