"""Audit Log placeholder — ships at M6."""

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer
from durgam.states.base import BaseState


class AuditLogState(BaseState):
    async def load_audit(self) -> None:
        """on_load for /audit — route-protected like all admin pages."""
        guard = self._admin_guard()
        if guard is not None:
            return guard


def audit_log() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.link("← Admin", href="/admin", color="var(--color-primary)",
                            font_size="0.875rem"),
                    rx.heading("Audit Log", size="5", font_family="var(--font-sans)"),
                    gap="1rem", align="center", margin_bottom="1.5rem",
                ),
                rx.box(
                    rx.vstack(
                        rx.text("🔒", font_size="2.5rem"),
                        rx.heading("Coming in M6", size="4",
                                   color="var(--color-body)", font_family="var(--font-sans)"),
                        rx.text(
                            "The Audit Log module ships at Milestone 6. "
                            "Until then, audit data can be queried directly via the database.",
                            font_size="0.9rem",
                            color="var(--color-muted)",
                            text_align="center",
                            max_width="420px",
                        ),
                        rx.text(
                            "Contact System Admin for direct database access.",
                            font_size="0.875rem",
                            color="var(--color-muted)",
                        ),
                        align="center",
                        gap="0.75rem",
                        padding="3rem",
                    ),
                    border="1px solid var(--color-rule)",
                    border_radius="8px",
                    background="white",
                ),
                padding="2rem",
                max_width="700px",
                width="100%",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
