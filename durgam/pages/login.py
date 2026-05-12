"""Login page (M1 Authentication)."""

import reflex as rx

from durgam.states.auth import AuthState


def _card(*children) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "DURGAM",
                size="7",
                color="var(--color-primary)",
                font_family="var(--font-serif)",
            ),
            rx.text(
                "Sri Sathya Sai Institute of Higher Learning",
                font_size="0.8rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            rx.divider(border_color="var(--color-rule)", margin_y="1rem"),
            *children,
            align_items="stretch",
            gap="0.75rem",
            width="100%",
        ),
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="2rem",
        width="100%",
        max_width="420px",
        box_shadow="0 2px 12px rgba(0,0,0,0.08)",
    )


def _flash_box() -> rx.Component:
    return rx.cond(
        AuthState.flash != "",
        rx.box(
            rx.text(AuthState.flash, color="var(--color-accent)", font_size="0.9rem"),
            padding="0.75rem",
            background="rgba(183, 110, 0, 0.08)",
            border="1px solid var(--color-accent)",
            border_radius="4px",
        ),
        rx.fragment(),
    )


def login() -> rx.Component:
    return rx.box(
        _card(
            rx.heading(
                "Sign in",
                size="4",
                color="var(--color-body)",
                font_family="var(--font-sans)",
            ),
            _flash_box(),
            rx.form(
                rx.vstack(
                    rx.vstack(
                        rx.text(
                            "Username",
                            font_size="0.85rem",
                            color="var(--color-body)",
                            font_weight="500",
                        ),
                        rx.input(
                            placeholder="your.username",
                            name="username",
                            type="text",
                            width="100%",
                            border="1px solid var(--color-rule)",
                            border_radius="4px",
                            padding="0.5rem 0.75rem",
                            font_family="var(--font-sans)",
                        ),
                        align_items="flex-start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Password",
                            font_size="0.85rem",
                            color="var(--color-body)",
                            font_weight="500",
                        ),
                        rx.input(
                            placeholder="••••••••••••",
                            name="password",
                            type="password",
                            width="100%",
                            border="1px solid var(--color-rule)",
                            border_radius="4px",
                            padding="0.5rem 0.75rem",
                            font_family="var(--font-sans)",
                        ),
                        align_items="flex-start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.button(
                        rx.cond(AuthState.is_loading, "Signing in…", "Sign in"),
                        type="submit",
                        width="100%",
                        background="var(--color-primary)",
                        color="white",
                        border_radius="4px",
                        padding="0.6rem",
                        font_family="var(--font-sans)",
                        cursor="pointer",
                        disabled=AuthState.is_loading,
                    ),
                    align_items="stretch",
                    gap="1rem",
                ),
                on_submit=AuthState.login,
                width="100%",
            ),
            rx.link(
                "Forgot your password?",
                href="/forgot-password",
                font_size="0.85rem",
                color="var(--color-primary)",
                text_align="center",
                width="100%",
            ),
        ),
        display="flex",
        justify_content="center",
        align_items="center",
        min_height="100vh",
        background="var(--color-surface)",
        padding="1rem",
    )
