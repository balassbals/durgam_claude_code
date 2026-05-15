"""AdminIndexState — dashboard stats for the /admin landing page."""

from __future__ import annotations

from sqlmodel import func, select

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.models.identity import User
from durgam.states.base import BaseState


class AdminIndexState(BaseState):
    active_user_count: int = 0
    role_count: int = 0
    pending_password_change_count: int = 0

    @require_role(action="read", resource="user")
    @audit_action(action="view", resource="admin_dashboard")
    async def load_stats(self) -> None:
        from durgam.models.identity import Role

        with open_session() as session:
            self.active_user_count = session.exec(
                select(func.count()).select_from(User).where(
                    User.is_deleted == False,  # noqa: E712
                    User.is_active == True,  # noqa: E712
                )
            ).one()
            self.role_count = session.exec(
                select(func.count()).select_from(Role).where(Role.is_deleted == False)  # noqa: E712
            ).one()
            self.pending_password_change_count = session.exec(
                select(func.count()).select_from(User).where(
                    User.is_deleted == False,  # noqa: E712
                    User.must_change_password == True,  # noqa: E712
                )
            ).one()
        self._load_nav_entries()
