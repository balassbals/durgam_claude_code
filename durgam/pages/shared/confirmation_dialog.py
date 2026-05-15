"""Reusable destructive-action confirmation dialog (UX Charter §4).

Usage:
    confirmation_dialog(
        is_open=SomeState.confirm_open,
        title="Delete user 'jdoe'?",
        body="This will deactivate the account. The user can no longer log in.",
        on_confirm=SomeState.confirmed_delete,
        on_cancel=SomeState.cancel_delete,
    )
"""

from __future__ import annotations

from collections.abc import Callable

import reflex as rx


def confirmation_dialog(
    *,
    is_open: bool,
    title: str,
    body: str,
    on_confirm: Callable,
    on_cancel: Callable,
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
    danger: bool = True,
) -> rx.Component:
    """A modal confirmation dialog for destructive actions.

    Per UX Charter §4: names the resource, states the consequence in plain
    language, and offers a clear cancel button.
    """
    confirm_bg = "var(--color-danger, #c0392b)" if danger else "var(--color-primary)"

    return rx.cond(
        is_open,
        rx.box(
            # Backdrop
            rx.box(
                # Dialog card
                rx.box(
                    rx.heading(title, size="4", color="var(--color-body)"),
                    rx.text(
                        body,
                        color="var(--color-muted)",
                        font_size="0.9rem",
                        margin_top="0.75rem",
                    ),
                    rx.hstack(
                        rx.button(
                            cancel_label,
                            on_click=on_cancel,
                            background="transparent",
                            border="1px solid var(--color-rule)",
                            color="var(--color-body)",
                            padding="0.4rem 1rem",
                            border_radius="4px",
                            cursor="pointer",
                            font_family="var(--font-sans)",
                        ),
                        rx.button(
                            confirm_label,
                            on_click=on_confirm,
                            background=confirm_bg,
                            color="white",
                            border="none",
                            padding="0.4rem 1rem",
                            border_radius="4px",
                            cursor="pointer",
                            font_family="var(--font-sans)",
                        ),
                        justify="end",
                        gap="0.75rem",
                        margin_top="1.5rem",
                    ),
                    background="white",
                    border_radius="8px",
                    padding="1.5rem",
                    width="min(480px, 90vw)",
                    box_shadow="0 8px 32px rgba(0,0,0,0.18)",
                ),
                display="flex",
                align_items="center",
                justify_content="center",
                position="fixed",
                top="0",
                left="0",
                width="100vw",
                height="100vh",
                z_index="1000",
            ),
            # Backdrop overlay
            position="fixed",
            top="0",
            left="0",
            width="100vw",
            height="100vh",
            background="rgba(0,0,0,0.45)",
            z_index="999",
        ),
        rx.fragment(),
    )
