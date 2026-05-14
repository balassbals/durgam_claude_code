"""Shared page components for authenticated DURGAM pages."""

import reflex as rx

from durgam.states.auth import AuthState


def nav_shell() -> rx.Component:
    """Persistent navigation bar shown on every authenticated page.

    Displays the current username, a logout button, and a link to
    /change-password. Only rendered when current_user_id is set.
    """
    return rx.cond(
        AuthState.current_user_id != "",
        rx.box(
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
                ),
                rx.hstack(
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
                        border="1px solid var(--color-rule)",
                        color="var(--color-body)",
                        padding="0.25rem 0.75rem",
                        border_radius="4px",
                        font_family="var(--font-sans)",
                    ),
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
