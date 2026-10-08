"""Clinical audit trail.

A hospital record is not just "who may do this" but "who *did* this, and what
did it look like before". These helpers write an append-only entry with a
field-level before/after diff for every clinical mutation.

Nothing here ever updates or deletes an existing row — the trail is append-only
by construction, and there is no API that can rewrite it.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from . import models

# Housekeeping columns add no clinical meaning and would drown the real changes.
_IGNORED_FIELDS = {
    "created_at",
    "updated_at",
    "created_by",
    "updated_by",
    "hashed_password",
}

# Refuse to persist anything that might carry a credential.
_REDACTED_FIELDS = {"password", "token", "refresh_token", "secret", "api_key"}


def _coerce(value: Any) -> Any:
    """Make a column value JSON-serialisable."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    return value


def snapshot(instance: Any, fields: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Capture the current column values of a mapped instance."""
    if instance is None:
        return {}
    columns = fields if fields is not None else [c.name for c in instance.__table__.columns]
    captured: Dict[str, Any] = {}
    for name in columns:
        if name in _IGNORED_FIELDS or name in _REDACTED_FIELDS:
            continue
        try:
            captured[name] = _coerce(getattr(instance, name))
        except AttributeError:
            continue
    return captured


def diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Only the fields that actually changed, as {field: {from, to}}."""
    changed: Dict[str, Dict[str, Any]] = {}
    for key in set(before) | set(after):
        old = before.get(key)
        new = after.get(key)
        if old != new:
            changed[key] = {"from": old, "to": new}
    return changed


def _dump(payload: Optional[Dict[str, Any]]) -> Optional[str]:
    if payload is None:
        return None
    try:
        return json.dumps(payload, default=str, sort_keys=True)
    except (TypeError, ValueError):
        return json.dumps({"_unserialisable": str(type(payload))})


def record(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: Optional[int],
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
    patient_id: Optional[int] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> models.AuditLog:
    """Append one clinical audit entry.

    The caller owns the transaction, so an audit row and the change it describes
    commit together — a change can never be recorded without its trail, and a
    trail entry is never written for a change that rolled back.
    """
    entry = models.AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        patient_id=patient_id,
        username=actor,
        actor_role=actor_role,
        details=details,
        ip_address=ip_address,
        before_state=_dump(before),
        after_state=_dump(after),
    )
    db.add(entry)
    return entry


def record_change(
    db: Session,
    instance: Any,
    *,
    action: str,
    entity_type: str,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
    patient_id: Optional[int] = None,
    before: Optional[Dict[str, Any]] = None,
    details: Optional[str] = None,
) -> models.AuditLog:
    """Snapshot the instance and store it against the supplied prior state.

    Both sides are stored as *full* snapshots so the pair is self-describing: a
    consumer computes the diff itself, and an unchanged field can never be
    mistaken for a change. `before` is None for a creation, which is the honest
    representation — everything is new.
    """
    after = snapshot(instance)
    return record(
        db,
        action=action,
        entity_type=entity_type,
        entity_id=getattr(instance, "id", None),
        actor=actor,
        actor_role=actor_role,
        patient_id=patient_id,
        before=before,
        after=after,
        details=details,
    )


def decode_state(raw: Optional[str]) -> Optional[Any]:
    """Parse a stored state blob for API responses."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


def entity_trail(
    db: Session,
    entity_type: str,
    entity_id: int,
    limit: int = 200,
):
    """Every audit entry for one clinical record, newest first."""
    return (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.entity_type == entity_type,
            models.AuditLog.entity_id == entity_id,
        )
        .order_by(models.AuditLog.timestamp.desc(), models.AuditLog.id.desc())
        .limit(limit)
        .all()
    )


def patient_trail(db: Session, patient_id: int, limit: int = 300):
    """Everything that happened to a patient, across every record type."""
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.patient_id == patient_id)
        .order_by(models.AuditLog.timestamp.desc(), models.AuditLog.id.desc())
        .limit(limit)
        .all()
    )
