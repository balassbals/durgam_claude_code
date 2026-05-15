"""Shared page components for authenticated DURGAM pages."""

from __future__ import annotations

import reflex as rx

from durgam.states.auth import AuthState
from durgam.states.base import BaseState


def _nav_link(entry: dict) -> rx.Component:
    return rx.link(
        entry["label"],
        href=entry["href"],
        font_size="0.875rem",
        color="var(--color-primary)",
        font_family="var(--font-sans)",
        padding="0.25rem 0",
        text_decoration="none",
    )


def _mobile_drawer() -> rx.Component:
    """Hamburger drawer for narrow viewports (required from M2, UX Charter §12)."""
    return rx.drawer.root(
        rx.drawer.trigger(
            rx.button(
                "☰",
                background="transparent",
                border="1px solid var(--color-rule)",
                color="var(--color-body)",
                padding="0.25rem 0.5rem",
                border_radius="4px",
                cursor="pointer",
                font_size="1.1rem",
            ),
        ),
        rx.drawer.overlay(z_index="50"),
        rx.drawer.portal(
            rx.drawer.content(
                rx.vstack(
                    rx.text(
                        "DURGAM",
                        font_weight="700",
                        font_size="1.1rem",
                        color="var(--color-primary)",
                        font_family="var(--font-sans)",
                        margin_bottom="1rem",
                    ),
                    rx.foreach(
                        BaseState.visible_nav_entries,
                        _nav_link,
                    ),
                    rx.divider(margin_y="1rem"),
                    rx.link(
                        "Change password",
                        href="/change-password",
                        font_size="0.875rem",
                        color="var(--color-primary)",
                        font_family="var(--font-sans)",
                    ),
                    rx.button(
                        "Log out",
                        on_click=AuthState.logout,
                        font_size="0.875rem",
                        cursor="pointer",
                        background="transparent",
                        border="none",
                        color="var(--color-muted)",
                        padding="0",
                        font_family="var(--font-sans)",
                    ),
                    align="start",
                    padding="1.5rem",
                ),
                top="0",
                left="0",
                height="100%",
                width="min(280px, 80vw)",
                background="white",
                border_right="1px solid var(--color-rule)",
            ),
        ),
        direction="left",
    )


def nav_shell() -> rx.Component:
    """Persistent navigation bar shown on every authenticated page.

    Desktop: institutional name, nav links, username, change-password, logout.
    Mobile (≤768px): hamburger drawer + username + logout.
    """
    return rx.cond(
        AuthState.current_user_id != "",
        rx.box(
            rx.hstack(
                # Left: institutional name + nav links (desktop) OR hamburger (mobile)
                rx.hstack(
                    rx.text(
                        "DURGAM",
                        font_weight="700",
                        font_size="1rem",
                        color="var(--color-primary)",
                        font_family="var(--font-sans)",
                    ),
                    rx.hstack(
                        rx.foreach(
                            BaseState.visible_nav_entries,
                            _nav_link,
                        ),
                        gap="1.25rem",
                        display=["none", "none", "flex"],  # hidden on mobile
                        align="center",
                    ),
                    gap="1.5rem",
                    align="center",
                ),
                # Right: user info + actions
                rx.hstack(
                    rx.hstack(
                        rx.text(
                            "Logged in as: ",
                            font_size="0.875rem",
                            color="var(--color-muted)",
                            font_family="var(--font-sans)",
                        ),
                        rx.text(
                            AuthState.current_username,
                            font_size="0.875rem",
                            font_weight="600",
                            color="var(--color-body)",
                            font_family="var(--font-sans)",
                        ),
                        gap="0.25rem",
                        align="center",
                        display=["none", "flex"],  # hidden on very small screens
                    ),
                    rx.link(
                        "Change password",
                        href="/change-password",
                        font_size="0.875rem",
                        color="var(--color-primary)",
                        font_family="var(--font-sans)",
                        display=["none", "none", "block"],  # desktop only
                    ),
                    rx.button(
                        "Log out",
                        on_click=AuthState.logout,
                        font_size="0.875rem",
                        cursor="pointer",
                        background="transparent",
                        border="1px solid var(--color-rule)",
                        color="var(--color-body)",
                        padding="0.25rem 0.75rem",
                        border_radius="4px",
                        font_family="var(--font-sans)",
                    ),
                    _mobile_drawer(),
                    gap="1rem",
                    align="center",
                ),
                justify="between",
                align="center",
                width="100%",
            ),
            padding="0.5rem 1.5rem",
            background="white",
            border_bottom="1px solid var(--color-rule)",
            width="100%",
        ),
        rx.fragment(),
    )


def page_footer() -> rx.Component:
    """Footer with institutional name and academic year context."""
    return rx.box(
        rx.hstack(
            rx.text(
                "Sri Sathya Sai Institute of Higher Learning",
                font_size="0.75rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            rx.spacer(),
            rx.text(
                "AY 2025-26",
                font_size="0.75rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            width="100%",
        ),
        padding="0.75rem 1.5rem",
        border_top="1px solid var(--color-rule)",
        background="white",
        width="100%",
        margin_top="auto",
    )
