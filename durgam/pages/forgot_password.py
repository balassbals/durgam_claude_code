"""Forgot-password page (M1 Authentication)."""

import reflex as rx

from durgam.states.auth import AuthState


def forgot_password() -> rx.Component:
    return rx.box(
        rx.box(
            rx.vstack(
                rx.heading(
                    "DURGAM",
                    size="7",
                    color="var(--color-primary)",
                    font_family="var(--font-serif)",
                ),
                rx.divider(border_color="var(--color-rule)", margin_y="1rem"),
                rx.heading(
                    "Reset your password",
                    size="4",
                    color="var(--color-body)",
                    font_family="var(--font-sans)",
                ),
                rx.text(
                    "Enter your registered email address. If it exists, "
                    "a reset link will be sent.",
                    font_size="0.875rem",
                    color="var(--color-muted)",
                    font_family="var(--font-sans)",
                ),
                rx.cond(
                    AuthState.flash != "",
                    rx.box(
                        rx.text(
                            AuthState.flash,
                            color="var(--color-body)",
                            font_size="0.9rem",
                        ),
                        padding="0.75rem",
                        background="rgba(76, 78, 46, 0.06)",
                        border="1px solid var(--color-rule)",
                        border_radius="4px",
                    ),
                    rx.fragment(),
                ),
                rx.form(
                    rx.vstack(
                        rx.vstack(
                            rx.text(
                                "Email address",
                                font_size="0.85rem",
                                color="var(--color-body)",
                                font_weight="500",
                            ),
                            rx.input(
                                placeholder="your.email@sssihl.edu.in",
                                name="email",
                                type="email",
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
                            rx.cond(AuthState.is_loading, "Sending…", "Send reset link"),
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
                    on_submit=AuthState.request_password_reset,
                    width="100%",
                ),
                rx.link(
                    "Back to sign in",
                    href="/login",
                    font_size="0.85rem",
                    color="var(--color-primary)",
                    text_align="center",
                    width="100%",
                ),
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
        ),
        display="flex",
        justify_content="center",
        align_items="center",
        min_height="100vh",
        background="var(--color-surface)",
        padding="1rem",
    )
