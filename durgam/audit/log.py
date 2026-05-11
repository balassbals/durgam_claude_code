"""Audit row writer — called by @audit_action decorator."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlmodel import Session

from durgam.models.crosscutting import AuditLog

log = structlog.get_logger(__name__)


def write_audit_row(
    *,
    actor_user_id: UUID | None,
    actor_role_code: str | None,
    action: str,
    resource: str,
    resource_id: str | None,
    request_id: str | None,
    ip: str | None,
    user_agent: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    session: Session,
) -> AuditLog:
    """Insert one row into audit_logs and return it.

    diff_json is {field: [before_value, after_value]} for changed fields only.
    If before is None (creation) diff contains all after fields as [None, value].
    If after is None (deletion) diff contains all before fields as [value, None].
    """
    diff: dict[str, list[Any]] = {}
    if before is None and after is not None:
        diff = {k: [None, v] for k, v in after.items()}
    elif after is None and before is not None:
        diff = {k: [v, None] for k, v in before.items()}
    elif before is not None and after is not None:
        diff = {
            k: [before.get(k), after.get(k)]
            for k in set(before) | set(after)
            if before.get(k) != after.get(k)
        }

    row = AuditLog(
        occurred_at=datetime.now(UTC),
        actor_user_id=actor_user_id,
        actor_role_code=actor_role_code,
        action=action,
        resource=resource,
        resource_id=resource_id,
        request_id=request_id,
        ip=ip,
        user_agent=user_agent,
        diff_json=diff,
    )
    session.add(row)
    session.flush()

    log.info(
        "audit_row_written",
        actor=str(actor_user_id),
        action=action,
        resource=resource,
        resource_id=resource_id,
    )
    return row
