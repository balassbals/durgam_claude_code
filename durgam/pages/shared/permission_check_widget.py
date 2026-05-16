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

    pc_users: list[dict[str, str]] = []        # {id, username}
    pc_available_actions: list[str] = []        # actions available for selected resource
    pc_selected_resource: str = ""              # drives pc_available_actions
    pc_selected_user_id: str = ""
    pc_selected_action: str = ""
    pc_selected_scope_type: str = "(global / none)"
    pc_selected_scope_id: str = ""
    pc_result: str = ""    # "granted", "denied", or ""
    pc_error: str = ""

    def clear_widget(self) -> None:
        """Reset widget to empty state — call from parent page's on_load (Bug J)."""
        self.pc_result = ""
        self.pc_error = ""
        self.pc_selected_resource = ""
        self.pc_selected_action = ""
        self.pc_selected_user_id = ""
        self.pc_selected_scope_type = "(global / none)"
        self.pc_selected_scope_id = ""
        self.pc_available_actions = []

    @require_role(action="read", resource="user")
    @audit_action(action="view", resource="user")
    async def load_widget_data(self) -> None:
        """Populate pc_users on widget mount. Excludes e2e_* ephemeral test users."""
        if self.pc_users:
            return
        with open_session() as session:
            from durgam.repositories.user import UserRepository
            repo = UserRepository(session)
            # exclude_ephemeral=True: filter out e2e_* test users (Issue 5).
            users, _ = repo.list_paginated(None, 0, 50, exclude_ephemeral=True)
            self.pc_users = [
                {"id": str(u.id), "username": u.username}
                for u in users
            ]

    @require_role(action="read", resource="permission")
    @audit_action(action="view", resource="permission")
    async def set_pc_resource(self, value: str) -> None:
        """Update selected resource and reload available actions (Bug I)."""
        self.pc_selected_resource = value
        self.pc_selected_action = ""
        self.pc_result = ""
        self.pc_error = ""
        if not value:
            self.pc_available_actions = []
            return
        with open_session() as session:
            from durgam.repositories.permission import PermissionRepository
            grouped = PermissionRepository(session).list_grouped_by_resource()
            perms = grouped.get(value, [])
            self.pc_available_actions = sorted({p.action for p in perms})

    def set_pc_user(self, value: str) -> None:
        self.pc_selected_user_id = value

    def set_pc_action(self, value: str) -> None:
        self.pc_selected_action = value

    def set_pc_scope_type(self, value: str) -> None:
        self.pc_selected_scope_type = value

    def set_pc_scope_id(self, value: str) -> None:
        self.pc_selected_scope_id = value

    @require_role(action="read", resource="user")
    @audit_action(action="check_permission", resource="user")
    async def check_permission(self) -> None:
        """Run can() with the state var selections and store the result (Bug I/J)."""
        self.pc_result = ""
        self.pc_error = ""

        user_id_str = self.pc_selected_user_id.strip()
        action = self.pc_selected_action.strip()
        resource = self.pc_selected_resource.strip()
        scope_type_raw = self.pc_selected_scope_type.strip()
        scope_id_str = self.pc_selected_scope_id.strip()

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

    _sel_style = {
        "width": "100%",
        "font_size": "0.875rem",
        "padding": "0.4rem",
        "border": "1px solid var(--color-rule)",
        "border_radius": "4px",
        "background": "white",
    }

    return rx.box(
        rx.heading("Check Permission", size="3", margin_bottom="1rem"),
        rx.vstack(
            # Row 1: Resource (determines available actions) + Scope type
            rx.hstack(
                rx.box(
                    _label("Resource — select first to populate actions"),
                    rx.el.select(
                        rx.el.option("— Select resource —", value=""),
                        *[rx.el.option(r, value=r) for r in _M2_RESOURCES],
                        id="pc-resource-select",
                        on_change=PermissionCheckState.set_pc_resource,
                        **_sel_style,
                    ),
                    flex="1",
                ),
                rx.box(
                    _label("Scope type"),
                    rx.el.select(
                        *[rx.el.option(s, value=s) for s in _SCOPE_TYPES],
                        id="pc-scope-type-select",
                        on_change=PermissionCheckState.set_pc_scope_type,
                        **_sel_style,
                    ),
                    flex="1",
                ),
                gap="1rem",
                width="100%",
            ),
            # Row 2: Action (filtered by resource) + User
            rx.hstack(
                rx.box(
                    _label("Action — available for selected resource"),
                    rx.cond(
                        PermissionCheckState.pc_selected_resource == "",
                        rx.text("Select a resource first.", font_size="0.8rem",
                                color="var(--color-muted)", padding="0.4rem"),
                        rx.el.select(
                            rx.el.option("— Select action —", value=""),
                            rx.foreach(
                                PermissionCheckState.pc_available_actions,
                                lambda a: rx.el.option(a, value=a),
                            ),
                            id="pc-action-select",
                            on_change=PermissionCheckState.set_pc_action,
                            **_sel_style,
                        ),
                    ),
                    flex="1",
                ),
                rx.box(
                    _label("User"),
                    rx.el.select(
                        rx.el.option("— Select user —", value=""),
                        rx.foreach(
                            PermissionCheckState.pc_users,
                            lambda u: rx.el.option(u["username"], value=u["id"]),
                        ),
                        id="pc-user-select",
                        on_change=PermissionCheckState.set_pc_user,
                        **_sel_style,
                    ),
                    flex="1",
                ),
                gap="1rem",
                width="100%",
            ),
            # Row 3: Scope ID — dropdown (disabled at M2; no scope objects seeded yet).
            # Issue 4: replaced text input with a dropdown showing availability status.
            rx.box(
                _label("Scope ID — specific object within the scope type"),
                rx.cond(
                    PermissionCheckState.pc_selected_scope_type == "(global / none)",
                    rx.text("Not applicable for global scope.", font_size="0.8rem",
                            color="var(--color-muted)", padding="0.4rem"),
                    rx.el.select(
                        rx.el.option("(No objects available — scope objects ship at M3+)",
                                     value="", disabled=True),
                        disabled=True,
                        id="pc-scope-id-select",
                        **{**_sel_style, "background": "var(--color-surface)"},
                    ),
                ),
                width="100%",
            ),
            rx.button(
                "Check",
                on_click=PermissionCheckState.check_permission,
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
        border="1px solid var(--color-rule)",
        border_radius="6px",
        padding="1.25rem",
        background="var(--color-surface, #faf9f7)",
        margin_top="2rem",
        on_mount=PermissionCheckState.load_widget_data,
    )
