"""@require_role and @audit_action decorator factories.

At M0 these decorators are stub-session-tested: they read current_user_id from a
kwarg (not from an HTTP session cookie, which is M1). Every Reflex state handler
MUST carry both decorators. CI lint enforces this when handlers exist.

Contract that M1 must preserve when wiring real session cookies:
- @require_role must still call can() with the live user_id from the session.
- @audit_action must still call write_audit_row() with non-null diff_json.
- Tests in tests/unit/test_auth.py must remain green after M1 auth wiring.
"""

import functools
from collections.abc import Callable
from typing import Any
from uuid import UUID

import structlog
from sqlmodel import Session

from durgam.audit.log import write_audit_row
from durgam.auth.permissions import PermissionDenied, can

log = structlog.get_logger(__name__)


def require_role(
    action: str,
    resource: str,
    scope: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Enforce that the caller holds (action, resource, scope) before the handler runs.

    The decorated function must accept:
    - user_id: UUID
    - session: sqlmodel.Session
    - scope_id: UUID | None  (optional, defaults to None)

    Raises PermissionDenied if the check fails.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user_id: UUID = kwargs["user_id"]
            session: Session = kwargs["session"]
            scope_id: UUID | None = kwargs.get("scope_id")

            if not can(
                user_id=user_id,
                action=action,
                resource=resource,
                scope_type=scope,
                scope_id=scope_id,
                session=session,
            ):
                raise PermissionDenied(user_id=user_id, action=action, resource=resource)

            return func(*args, **kwargs)

        wrapper._require_role = (action, resource, scope)  # type: ignore[attr-defined]
        return wrapper

    return decorator


def audit_action(
    action: str,
    resource: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Record an AuditLog row after the decorated function completes successfully.

    The decorated function must:
    - Accept user_id: UUID, session: Session in kwargs.
    - Return a dict with keys "resource_id", "before", "after" (all optional).

    If the function raises, no audit row is written.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user_id: UUID = kwargs["user_id"]
            session: Session = kwargs["session"]
            request_id: str | None = kwargs.get("request_id")
            ip: str | None = kwargs.get("ip")
            user_agent: str | None = kwargs.get("user_agent")

            result = func(*args, **kwargs)

            audit_data: dict[str, Any] = result if isinstance(result, dict) else {}
            write_audit_row(
                actor_user_id=user_id,
                actor_role_code=kwargs.get("actor_role_code"),
                action=action,
                resource=resource,
                resource_id=audit_data.get("resource_id"),
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                before=audit_data.get("before"),
                after=audit_data.get("after"),
                session=session,
            )
            return result

        wrapper._audit_action = (action, resource)  # type: ignore[attr-defined]
        return wrapper

    return decorator
