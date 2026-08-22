import reflex as rx

from durgam.pages.components import app_shell, typed_flash
from durgam.pages.shared.recent_announcements_widget import recent_announcements_widget
from durgam.states.auth import AuthState
from durgam.states.base import BaseState
from durgam.theme import TOKENS


def _swatch(var: str, label: str) -> rx.Component:
    return rx.hstack(
        rx.box(
            width="2rem",
            height="2rem",
            background_color=f"var({var})",
            border_radius="4px",
            border="1px solid var(--color-rule)",
            flex_shrink="0",
        ),
        rx.vstack(
            rx.text(
                var, font_size="0.75rem", color="var(--color-muted)", font_family="var(--font-sans)"
            ),
            rx.text(
                label,
                font_size="0.875rem",
                color="var(--color-body)",
                font_family="var(--font-sans)",
            ),
            align_items="flex-start",
            gap="0",
        ),
        align_items="center",
        gap="0.75rem",
    )


def index() -> rx.Component:
    color_tokens = [
        ("--color-primary", TOKENS["--color-primary"] + " — indigo (structural)"),
        ("--color-accent", TOKENS["--color-accent"] + " — saffron (CTA / highlights)"),
        ("--color-surface", TOKENS["--color-surface"] + " — ivory (backgrounds)"),
        ("--color-body", TOKENS["--color-body"] + " — slate (body text)"),
        ("--color-muted", TOKENS["--color-muted"] + " — muted (captions)"),
        ("--color-rule", TOKENS["--color-rule"] + " — gold (decorative rules)"),
    ]

    # Route protection guard (same pattern as admin_page() for /admin/*).
    # on_load fires AFTER first paint; wrapping in rx.cond prevents the home
    # page content from flashing for unauthenticated users before the redirect
    # to /login fires. Shows blank screen then /login — no content flash.
    return rx.cond(
        AuthState.current_user_id != "",
        app_shell(
            rx.fragment(
                rx.cond(
                    BaseState.flash != "",
                    rx.box(typed_flash(BaseState.flash, BaseState.flash_type), padding="0.5rem 1.5rem 0"),
                    rx.fragment(),
                ),
                rx.vstack(
                    rx.box(
                        height="4px",
                        width="100%",
                        background_color="var(--color-rule)",
                    ),
                    rx.vstack(
                        rx.heading(
                            "DURGAM",
                            size="9",
                            color="var(--color-primary)",
                            font_family="var(--font-serif)",
                        ),
                        rx.text(
                            "University ERP · SSSIHL",
                            color="var(--color-muted)",
                            font_size="1rem",
                            font_family="var(--font-sans)",
                        ),
                        rx.divider(border_color="var(--color-rule)", margin_y="1rem"),
                        recent_announcements_widget(),
                        rx.heading(
                            "M0 — Foundations · Theme Preview",
                            size="4",
                            color="var(--color-accent)",
                            font_family="var(--font-sans)",
                        ),
                        rx.text(
                            "Puttaparthi Saffron–Indigo–Ivory palette (§15.1)",
                            color="var(--color-muted)",
                            font_size="0.875rem",
                            margin_bottom="1rem",
                        ),
                        rx.vstack(
                            *[_swatch(var, label) for var, label in color_tokens],
                            align_items="flex-start",
                            gap="0.75rem",
                        ),
                        align_items="flex-start",
                        width="100%",
                    ),
                    align_items="stretch",
                    width="100%",
                ),
            ),
            container="sm",
        ),
        rx.fragment(),
    )
