"""Permission check widget — manual verification tool for gate Step 7.

Embeds on the user detail or role detail page. The administrator fills in
(user, action, resource, scope_type, scope_id) and submits to see the
live can() result. Used at the M2 gate to verify that scoped permission
checking works correctly.
"""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.permissions import can
from durgam.db import open_session
from durgam.states.base import BaseState


class PermissionCheckState(BaseState):
    """State for the permission check widget."""

    pc_user_id: str = ""
    pc_action: str = ""
    pc_resource: str = ""
    pc_scope_type: str = ""
    pc_scope_id: str = ""

    pc_result: str = ""   # "granted", "denied", or "" (not yet checked)
    pc_error: str = ""

    def check_permission(self) -> None:
        """Run can() with the widget's inputs and store the result."""
        self.pc_result = ""
        self.pc_error = ""

        user_id_str = self.pc_user_id.strip()
        action = self.pc_action.strip()
        resource = self.pc_resource.strip()
        scope_type = self.pc_scope_type.strip() or None
        scope_id_str = self.pc_scope_id.strip()

        if not user_id_str or not action or not resource:
            self.pc_error = "User ID, action, and resource are required."
            return

        try:
            user_id = UUID(user_id_str)
        except ValueError:
            self.pc_error = "User ID must be a valid UUID."
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
    """Render the permission check form and result display."""
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

    return rx.box(
        rx.heading("Check Permission", size="3", margin_bottom="1rem"),
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.text("User ID", font_size="0.8rem", color="var(--color-muted)"),
                    rx.input(
                        placeholder="UUID of the user",
                        value=PermissionCheckState.pc_user_id,
                        on_change=PermissionCheckState.set_pc_user_id,  # type: ignore[attr-defined]
                        font_size="0.875rem",
                    ),
                    flex="1",
                ),
                rx.box(
                    rx.text("Action", font_size="0.8rem", color="var(--color-muted)"),
                    rx.input(
                        placeholder="e.g. read",
                        value=PermissionCheckState.pc_action,
                        on_change=PermissionCheckState.set_pc_action,  # type: ignore[attr-defined]
                        font_size="0.875rem",
                    ),
                    flex="1",
                ),
                gap="1rem",
                width="100%",
            ),
            rx.hstack(
                rx.box(
                    rx.text("Resource", font_size="0.8rem", color="var(--color-muted)"),
                    rx.input(
                        placeholder="e.g. department",
                        value=PermissionCheckState.pc_resource,
                        on_change=PermissionCheckState.set_pc_resource,  # type: ignore[attr-defined]
                        font_size="0.875rem",
                    ),
                    flex="1",
                ),
                rx.box(
                    rx.text("Scope type", font_size="0.8rem", color="var(--color-muted)"),
                    rx.input(
                        placeholder="e.g. department (optional)",
                        value=PermissionCheckState.pc_scope_type,
                        on_change=PermissionCheckState.set_pc_scope_type,  # type: ignore[attr-defined]
                        font_size="0.875rem",
                    ),
                    flex="1",
                ),
                rx.box(
                    rx.text("Scope ID", font_size="0.8rem", color="var(--color-muted)"),
                    rx.input(
                        placeholder="UUID of scoped object (optional)",
                        value=PermissionCheckState.pc_scope_id,
                        on_change=PermissionCheckState.set_pc_scope_id,  # type: ignore[attr-defined]
                        font_size="0.875rem",
                    ),
                    flex="1",
                ),
                gap="1rem",
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
                rx.text(
                    PermissionCheckState.pc_error,
                    color="var(--color-danger, #c0392b)",
                    font_size="0.875rem",
                ),
                rx.fragment(),
            ),
            rx.cond(
                PermissionCheckState.pc_result != "",
                rx.text(result_text, color=result_color, font_size="1.1rem", font_weight="700"),
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
    )
