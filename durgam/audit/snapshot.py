"""Audit snapshot utility — serializes SQLModel entities for before/after diffs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import inspect as sa_inspect


def audit_snapshot(entity: Any) -> dict[str, Any]:
    """Serialize a SQLModel entity's column values for audit diff.

    Redacts fields listed in the entity class's _audit_redact_fields ClassVar.
    Converts UUID -> str, datetime -> ISO string for JSON compatibility.
    Skips relationship attributes.
    """
    mapper = sa_inspect(type(entity))
    redact_fields: set[str] = getattr(type(entity), "_audit_redact_fields", set())

    result: dict[str, Any] = {}
    for attr in mapper.column_attrs:
        key = attr.key
        value = getattr(entity, key)
        if key in redact_fields:
            result[key] = "<redacted>"
        else:
            result[key] = _serialize_value(value)
    return result


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, dict)):
        return value
    return value
