"""Permission check widget — manual verification tool for gate Step 7.

Embeds on the user detail or role detail page. The administrator fills in
(user, action, resource, scope_type, scope_id) and submits to see the
live can() result. Uses on_submit (not on_change) to avoid Reflex 0.9.2's
auto-setter limitation on substates.
"""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.auth.permissions import can
from durgam.db import open_session
from durgam.states.base import BaseState


class PermissionCheckState(BaseState):
    """State for the permission check widget."""

    pc_result: str = ""   # "granted", "denied", or "" (not yet checked)
    pc_error: str = ""

    @require_role(action="read", resource="user")
    @audit_action(action="check_permission", resource="user")
    async def check_permission(self, form_data: dict) -> None:
        """Run can() with the form's inputs and store the result."""
        self.pc_result = ""
        self.pc_error = ""

        user_id_str = form_data.get("pc_user_id", "").strip()
        action = form_data.get("pc_action", "").strip()
        resource = form_data.get("pc_resource", "").strip()
        scope_type = form_data.get("pc_scope_type", "").strip() or None
        scope_id_str = form_data.get("pc_scope_id", "").strip()

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
        rx.form(
            rx.vstack(
                rx.hstack(
                    rx.box(
                        rx.text("User ID", font_size="0.8rem", color="var(--color-muted)"),
                        rx.input(
                            name="pc_user_id",
                            placeholder="UUID of the user",
                            font_size="0.875rem",
                        ),
                        flex="1",
                    ),
                    rx.box(
                        rx.text("Action", font_size="0.8rem", color="var(--color-muted)"),
                        rx.input(
                            name="pc_action",
                            placeholder="e.g. read",
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
                            name="pc_resource",
                            placeholder="e.g. department",
                            font_size="0.875rem",
                        ),
                        flex="1",
                    ),
                    rx.box(
                        rx.text("Scope type", font_size="0.8rem", color="var(--color-muted)"),
                        rx.input(
                            name="pc_scope_type",
                            placeholder="e.g. department (optional)",
                            font_size="0.875rem",
                        ),
                        flex="1",
                    ),
                    rx.box(
                        rx.text("Scope ID", font_size="0.8rem", color="var(--color-muted)"),
                        rx.input(
                            name="pc_scope_id",
                            placeholder="UUID of scoped object (optional)",
                            font_size="0.875rem",
                        ),
                        flex="1",
                    ),
                    gap="1rem",
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
                    rx.text(
                        PermissionCheckState.pc_error,
                        color="var(--color-danger, #c0392b)",
                        font_size="0.875rem",
                    ),
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
    )
