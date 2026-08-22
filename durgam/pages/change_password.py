"""Change-password page — for authenticated users and forced first-login (M1)."""

import reflex as rx

from durgam.pages.components import app_shell, typed_flash
from durgam.services.password import PASSWORD_RULES
from durgam.states.auth import AuthState
from durgam.states.base import BaseState


def _password_rules_hint() -> rx.Component:
    """Password rules displayed below the new password field (Bug 2)."""
    return rx.box(
        rx.text(
            "New password must:",
            font_size="0.8rem",
            color="var(--color-muted)",
            font_weight="500",
            margin_bottom="0.25rem",
        ),
        rx.vstack(
            *[
                rx.hstack(
                    rx.text("·", color="var(--color-muted)", font_size="0.8rem"),
                    rx.text(rule, font_size="0.8rem", color="var(--color-muted)"),
                    gap="0.4rem",
                )
                for rule in PASSWORD_RULES
            ],
            align="start",
            gap="0.1rem",
        ),
        padding="0.5rem 0",
    )


def change_password() -> rx.Component:
    return app_shell(
        rx.box(
            rx.vstack(
                rx.heading(
                    "DURGAM",
                    size="7",
                    color="var(--color-primary)",
                    font_family="var(--font-serif)",
                ),
                rx.divider(border_color="var(--color-rule)", margin_y="1rem"),
                rx.cond(
                    AuthState.must_change_password,
                    rx.box(
                        rx.text(
                            "You must set a new password before continuing.",
                            font_size="0.875rem",
                            color="var(--color-accent)",
                        ),
                        padding="0.75rem",
                        background="rgba(183, 110, 0, 0.08)",
                        border="1px solid var(--color-accent)",
                        border_radius="4px",
                    ),
                    rx.heading(
                        "Change password",
                        size="4",
                        color="var(--color-body)",
                        font_family="var(--font-sans)",
                    ),
                ),
                typed_flash(BaseState.flash, BaseState.flash_type),
                rx.form(
                    rx.vstack(
                        rx.vstack(
                            rx.text(
                                "Current password",
                                font_size="0.85rem",
                                color="var(--color-body)",
                                font_weight="500",
                            ),
                            rx.el.input(
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
                        rx.vstack(
                            rx.text(
                                "New password",
                                font_size="0.85rem",
                                color="var(--color-body)",
                                font_weight="500",
                            ),
                            rx.el.input(
                                placeholder="••••••••••••",
                                name="new_password",
                                type="password",
                                width="100%",
                                border="1px solid var(--color-rule)",
                                border_radius="4px",
                                padding="0.5rem 0.75rem",
                                font_family="var(--font-sans)",
                            ),
                            _password_rules_hint(),
                            align_items="flex-start",
                            gap="0.25rem",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text(
                                "Confirm new password",
                                font_size="0.85rem",
                                color="var(--color-body)",
                                font_weight="500",
                            ),
                            rx.el.input(
                                placeholder="••••••••••••",
                                name="confirm_password",
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
                            "Update password",
                            type="submit",
                            width="100%",
                            background="var(--color-primary)",
                            color="white",
                            border_radius="4px",
                            padding="0.6rem",
                            font_family="var(--font-sans)",
                            cursor="pointer",
                        ),
                        align_items="stretch",
                        gap="1rem",
                    ),
                    on_submit=AuthState.change_password,
                    width="100%",
                ),
                rx.cond(
                    ~AuthState.must_change_password,
                    rx.link(
                        "Back to home",
                        href="/",
                        font_size="0.85rem",
                        color="var(--color-primary)",
                        text_align="center",
                        width="100%",
                    ),
                    rx.fragment(),
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
            box_shadow="0 2px 12px rgba(0,0,0,0.08)",
        ),
        container="sm",
    )
