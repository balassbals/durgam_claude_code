"""Permission check widget — manual verification tool for gate Step 7.

Uses native <select> dropdowns (rx.el.select) for user, action, resource, and
scope type so a human can use it without knowing UUIDs. Users list is loaded
lazily via on_mount when the widget renders.

Bug F fix: replaced raw UUID text inputs with dropdowns.
"""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.auth.permissions import can
from durgam.db import open_session
from durgam.states.base import BaseState

# M2 seed values — static dropdown options sourced from the seed.
_M2_ACTIONS = ["read", "write", "delete", "approve", "configure"]
_M2_RESOURCES = [
    "academic_year", "audit_log", "department", "leave_request",
    "permission", "role", "system", "user",
]
_SCOPE_TYPES = [
    "(global / none)", "campus", "school", "department",
    "class", "centre", "committee", "self",
]


class PermissionCheckState(BaseState):
    """State for the permission check widget."""

    pc_users: list[dict[str, str]] = []   # {id, username}
    pc_result: str = ""    # "granted", "denied", or ""
    pc_error: str = ""

    @require_role(action="read", resource="user")
    @audit_action(action="view", resource="user")
    async def load_widget_data(self) -> None:
        """Populate pc_users on widget mount."""
        if self.pc_users:
            return  # already loaded
        with open_session() as session:
            from durgam.repositories.user import UserRepository
            repo = UserRepository(session)
            users, _ = repo.list_paginated(None, 0, 50)
            self.pc_users = [
                {"id": str(u.id), "username": u.username}
                for u in users
                if not u.is_deleted
            ]

    @require_role(action="read", resource="user")
    @audit_action(action="check_permission", resource="user")
    async def check_permission(self, form_data: dict) -> None:
        """Run can() with the dropdown selections and store the result."""
        self.pc_result = ""
        self.pc_error = ""

        user_id_str = form_data.get("pc_user_id", "").strip()
        action = form_data.get("pc_action", "").strip()
        resource = form_data.get("pc_resource", "").strip()
        scope_type_raw = form_data.get("pc_scope_type", "").strip()
        scope_id_str = form_data.get("pc_scope_id", "").strip()

        scope_type: str | None = (
            None if scope_type_raw in ("", "(global / none)") else scope_type_raw
        )

        if not user_id_str or not action or not resource:
            self.pc_error = "Select a user, action, and resource."
            return

        try:
            user_id = UUID(user_id_str)
        except ValueError:
            self.pc_error = "Invalid user selection."
            return

        scope_id: UUID | None = None
        if scope_id_str:
            try:
                scope_id = UUID(scope_id_str)
            except ValueError:
                self.pc_error = "Scope ID must be a valid UUID or left blank."
                return

        with open_session() as session:
            result = can(
                user_id=user_id,
                action=action,
                resource=resource,
                scope_type=scope_type,
                scope_id=scope_id,
                session=session,
            )

        self.pc_result = "granted" if result else "denied"


def permission_check_widget() -> rx.Component:
    """Permission check widget with human-readable dropdown inputs."""
    result_color = rx.cond(
        PermissionCheckState.pc_result == "granted",
        "var(--color-success, #27ae60)",
        "var(--color-danger, #c0392b)",
    )
    result_text = rx.cond(
        PermissionCheckState.pc_result == "granted",
        "✓ Granted",
        "✗ Denied",
    )

    def _label(text: str) -> rx.Component:
        return rx.text(text, font_size="0.8rem", color="var(--color-muted)")

    return rx.box(
        rx.heading("Check Permission", size="3", margin_bottom="1rem"),
        rx.form(
            rx.vstack(
                # Row 1: User + Action
                rx.hstack(
                    rx.box(
                        _label("User"),
                        rx.el.select(
                            rx.el.option("— Select user —", value="", disabled=True),
                            rx.foreach(
                                PermissionCheckState.pc_users,
                                lambda u: rx.el.option(u["username"], value=u["id"]),
                            ),
                            name="pc_user_id",
                            width="100%",
                            font_size="0.875rem",
                            padding="0.4rem",
                            border="1px solid var(--color-rule)",
                            border_radius="4px",
                            background="white",
                        ),
                        flex="1",
                    ),
                    rx.box(
                        _label("Action"),
                        rx.el.select(
                            rx.el.option("— Select action —", value="", disabled=True),
                            *[rx.el.option(a, value=a) for a in _M2_ACTIONS],
                            name="pc_action",
                            width="100%",
                            font_size="0.875rem",
                            padding="0.4rem",
                            border="1px solid var(--color-rule)",
                            border_radius="4px",
                            background="white",
                        ),
                        flex="1",
                    ),
                    gap="1rem",
                    width="100%",
                ),
                # Row 2: Resource + Scope type
                rx.hstack(
                    rx.box(
                        _label("Resource"),
                        rx.el.select(
                            rx.el.option("— Select resource —", value="", disabled=True),
                            *[rx.el.option(r, value=r) for r in _M2_RESOURCES],
                            name="pc_resource",
                            width="100%",
                            font_size="0.875rem",
                            padding="0.4rem",
                            border="1px solid var(--color-rule)",
                            border_radius="4px",
                            background="white",
                        ),
                        flex="1",
                    ),
                    rx.box(
                        _label("Scope type"),
                        rx.el.select(
                            *[rx.el.option(s, value=s) for s in _SCOPE_TYPES],
                            name="pc_scope_type",
                            width="100%",
                            font_size="0.875rem",
                            padding="0.4rem",
                            border="1px solid var(--color-rule)",
                            border_radius="4px",
                            background="white",
                        ),
                        flex="1",
                    ),
                    gap="1rem",
                    width="100%",
                ),
                # Row 3: Scope ID (optional UUID)
                rx.box(
                    _label("Scope ID — UUID of the scoped object (leave blank for global scope)"),
                    rx.input(
                        name="pc_scope_id",
                        placeholder="e.g. dept-uuid-here (optional)",
                        font_size="0.875rem",
                        width="100%",
                    ),
                    width="100%",
                ),
                rx.button(
                    "Check",
                    type="submit",
                    background="var(--color-primary)",
                    color="white",
                    border="none",
                    padding="0.4rem 1.2rem",
                    border_radius="4px",
                    cursor="pointer",
                    font_family="var(--font-sans)",
                    align_self="flex-start",
                ),
                rx.cond(
                    PermissionCheckState.pc_error != "",
                    rx.text(PermissionCheckState.pc_error,
                            color="var(--color-danger, #c0392b)", font_size="0.875rem"),
                    rx.fragment(),
                ),
                rx.cond(
                    PermissionCheckState.pc_result != "",
                    rx.text(result_text, color=result_color,
                            font_size="1.1rem", font_weight="700"),
                    rx.fragment(),
                ),
                align="start",
                gap="0.75rem",
                width="100%",
            ),
            on_submit=PermissionCheckState.check_permission,
        ),
        border="1px solid var(--color-rule)",
        border_radius="6px",
        padding="1.25rem",
        background="var(--color-surface, #faf9f7)",
        margin_top="2rem",
        on_mount=PermissionCheckState.load_widget_data,
    )
