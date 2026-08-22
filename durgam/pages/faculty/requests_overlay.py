"""Faculty requests overlay (/faculty/requests) — M10 Phase 8B.

Thin overlay per Q-P8.2: two tab-styled deep-links into the existing approvals
views, filtered to faculty_* processes via ?type=faculty. No duplicate state —
this page is purely presentational; the filtering lives in MyRequestsState /
ApproverInboxState (which read the ?type param).
"""

from __future__ import annotations

import reflex as rx

from durgam.pages.components import app_shell
from durgam.states.auth import AuthState


def _tab_link(icon: str, label: str, sub: str, href: str) -> rx.Component:
    return rx.link(
        rx.box(
            rx.vstack(
                rx.icon(icon, size=28),
                rx.heading(label, size="4"),
                rx.text(sub, font_size="0.85rem", color="var(--color-muted)"),
                align="center",
                gap="0.4rem",
            ),
            background="white",
            border="1px solid var(--color-rule)",
            border_radius="10px",
            padding="2rem",
            min_width="240px",
            cursor="pointer",
            _hover={
                "border_color": "var(--color-primary)",
                "box_shadow": "0 2px 12px rgba(0,0,0,0.08)",
            },
        ),
        href=href,
    )


def _content() -> rx.Component:
    return app_shell(
        rx.vstack(
            rx.heading("Faculty Requests", size="6", margin_bottom="0.25rem"),
            rx.text(
                "Choose a view. Both open the standard approvals screens "
                "filtered to your faculty requests.",
                font_size="0.9rem",
                color="var(--color-muted)",
                margin_bottom="1rem",
            ),
            rx.hstack(
                _tab_link(
                    "inbox",
                    "My Requests",
                    "Requests you have submitted",
                    "/approvals/my-requests?type=faculty",
                ),
                _tab_link(
                    "clipboard-check",
                    "For my decision",
                    "Requests awaiting your approval",
                    "/approvals/inbox?type=faculty",
                ),
                gap="1.25rem",
                wrap="wrap",
                align="stretch",
            ),
            spacing="3",
            width="100%",
            align="start",
        ),
        container="md",
    )


def faculty_requests_overlay() -> rx.Component:
    return rx.cond(
        AuthState.current_user_id != "",
        _content(),
        rx.fragment(),
    )
