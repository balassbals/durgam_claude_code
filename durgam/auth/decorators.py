"""@require_role, @public_handler, and @audit_action decorator factories.

M1 contract: decorators read current_user_id from a Reflex State instance
(args[0]) rather than from kwargs. args[0] must have a current_user_id: str
attribute. Both @require_role and @public_handler pair with @audit_action.

Rule (enforced by CI lint):
  Every Reflex state event handler must wear EITHER @require_role OR
  @public_handler, PLUS @audit_action. No handler may be undecorated.

See docs/modules/auth.md for the full contract description.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any
from uuid import UUID

import structlog
from sqlmodel import Session

from durgam.audit.log import write_audit_row
from durgam.auth.permissions import PermissionDenied, can

log = structlog.get_logger(__name__)


def _get_session_from_state(state: Any) -> Session:
    """Extract a live DB session from a Reflex State instance.

    Reflex State objects expose _get_db_session() once the service layer is
    wired. At M1 this helper is called from within decorators; the session is
    opened and closed by the decorator, never leaked to the handler.
    """
    return state._get_db_session()


def _extract_user_id(state: Any) -> UUID | None:
    """Return the current_user_id from a Reflex State, or None if unauthenticated."""
    raw = getattr(state, "current_user_id", "")
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def _extract_context(state: Any) -> tuple[str | None, str | None, str | None]:
    """Extract request metadata from a Reflex State for audit rows."""
    return (
        getattr(state, "request_id", None),
        getattr(state, "client_ip", None),
        getattr(state, "client_user_agent", None),
    )


def require_role(
    action: str,
    resource: str,
    scope: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Gate a Reflex State event handler on (action, resource, scope).

    Reads current_user_id from args[0] (the State instance). Raises
    PermissionDenied if the user is unauthenticated or lacks the permission.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            state = args[0]
            user_id = _extract_user_id(state)
            if user_id is None:
                raise PermissionDenied(
                    user_id="<unauthenticated>", action=action, resource=resource
                )
            with _get_session_from_state(state) as session:
                scope_id: UUID | None = getattr(state, "scope_id", None)
                if not can(
                    user_id=user_id,
                    action=action,
                    resource=resource,
                    scope_type=scope,
                    scope_id=scope_id,
                    session=session,
                ):
                    raise PermissionDenied(user_id=user_id, action=action, resource=resource)
            return await func(*args, **kwargs)

        wrapper._require_role = (action, resource, scope)  # type: ignore[attr-defined]
        return wrapper

    return decorator


def public_handler(func: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a Reflex State event handler as intentionally unauthenticated.

    Replaces @require_role for login, forgot_password, reset_password, and
    other handlers that must be accessible without a session. Pairs with
    @audit_action which is still required for all state-changing operations.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        return await func(*args, **kwargs)

    wrapper._public_handler = True  # type: ignore[attr-defined]
    return wrapper


def audit_action(
    action: str,
    resource: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Record an AuditLog row after the decorated handler completes.

    Reads actor context from args[0] (the State instance):
    - current_user_id → actor_user_id
    - current_role_code → actor_role_code (optional)
    - request_id, client_ip, client_user_agent → audit metadata

    The decorated handler may return a dict with "resource_id", "before",
    "after" keys to populate the diff. If it raises, no audit row is written.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            state = args[0]
            user_id = _extract_user_id(state)
            actor_role = getattr(state, "current_role_code", None)
            request_id, ip, user_agent = _extract_context(state)

            result = await func(*args, **kwargs)

            with _get_session_from_state(state) as session:
                audit_data: dict[str, Any] = result if isinstance(result, dict) else {}
                write_audit_row(
                    actor_user_id=user_id,
                    actor_role_code=actor_role,
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
