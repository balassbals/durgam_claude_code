"""Change-password page — for authenticated users and forced first-login (M1)."""

import reflex as rx

from durgam.states.auth import AuthState


def change_password() -> rx.Component:
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
