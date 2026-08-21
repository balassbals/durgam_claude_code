"""Design system proof page — M10.5 Phase 1 verification artefact.

Renders every token defined in `durgam/theme.py` so the design system can be
visually verified before page migration begins (Phases 3-6). Sys-admin only.

THIS IS A PHASE-1 VERIFICATION ARTEFACT — remove at M10.5 close, along with
its route registration in `durgam/durgam.py`. It does not belong in the
final navigation and ships no business functionality.
"""

from __future__ import annotations

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer
from durgam.states.base import BaseState
from durgam.theme import TOKENS

# ── Token catalogues (static — mirror durgam/theme.py) ──────────────────────
# Values are looked up from TOKENS at render time (never hardcoded here) —
# theme.py is the single source of truth; see tests/unit/test_theme.py
# ::test_no_hardcoded_hex_in_component_files.

_COLOR_SWATCHES: list[tuple[str, str]] = [
    # (token, description)
    ("--color-primary", "indigo — structural elements"),
    ("--color-accent", "saffron — primary CTA / highlights"),
    ("--color-surface", "ivory — legacy surface token"),
    ("--color-background", "ivory page background"),
    ("--color-card-bg", "white card background"),
    ("--color-surface-2", "nested/secondary surface"),
    ("--color-surface-hover", "hover tint for ivory rows"),
    ("--color-body", "slate — body text"),
    ("--color-muted", "muted — secondary / caption text"),
    ("--color-rule", "gold — decorative rules / dividers"),
    ("--color-destructive", "destructive actions"),
    ("--color-danger", "aliases --color-destructive — one red, not two"),
    ("--color-success", "aliases --color-success-border"),
    ("--color-warning", "warm amber-brown"),
    ("--color-success-border", "success notification border"),
    ("--color-warning-border", "warning notification border"),
    ("--color-error-border", "error notification border"),
    ("--color-info-border", "info notification border"),
]

_TYPE_SCALE: list[tuple[str, str, str, str]] = [
    # (token, size, line-height token, intended use)
    ("--text-xs", "0.75rem", "--leading-xs", "captions, timestamps, badges"),
    ("--text-sm", "0.8125rem", "--leading-sm", "secondary text, table cells, helper text"),
    ("--text-base", "0.875rem", "--leading-base", "body text, inputs, buttons (default)"),
    ("--text-lg", "1rem", "--leading-lg", "card titles, emphasized labels"),
    ("--text-xl", "1.125rem", "--leading-xl", "section headings"),
    ("--text-2xl", "1.5rem", "--leading-2xl", "page headings"),
    ("--text-3xl", "2rem", "--leading-3xl", "hero / display headings"),
]

_SPACING_SCALE: list[str] = [
    "--space-1",
    "--space-2",
    "--space-3",
    "--space-4",
    "--space-5",
    "--space-6",
    "--space-8",
    "--space-10",
    "--space-12",
    "--space-16",
]

_RADIUS_SCALE: list[tuple[str, str]] = [
    ("--radius-sm", "4px"),
    ("--radius-md", "8px"),
    ("--radius-lg", "12px"),
    ("--radius-full", "999px"),
]

_SHADOW_SCALE: list[str] = ["--shadow-sm", "--shadow-md", "--shadow-lg", "--shadow-xl"]

_CONTAINER_SCALE: list[tuple[str, str]] = [
    ("--container-sm", "640px"),
    ("--container-md", "1024px"),
    ("--container-lg", "1440px"),
    ("--container-xl", "1760px"),
]


class DesignSystemState(BaseState):
    """Sys-admin-only guard for the Phase 1 token verification page."""

    async def load_design_system(self) -> None:
        guard = self._config_guard("system", "configure")
        if guard is not None:
            return guard


def _section(title: str, content: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.heading(title, size="5", font_family="var(--font-serif)", margin_bottom="0.5rem"),
        content,
        align="start",
        width="100%",
        padding="1.5rem 0",
        border_bottom="1px solid var(--color-rule)",
    )


def _color_swatches() -> rx.Component:
    return rx.grid(
        *[
            rx.vstack(
                rx.box(
                    background=f"var({token})",
                    width="100%",
                    height="4rem",
                    border_radius="var(--radius-md)",
                    border="1px solid var(--color-rule)",
                ),
                rx.text(
                    f"{token} = {TOKENS.get(token, '?')}",
                    font_family="var(--font-mono)",
                    font_size="var(--text-xs)",
                    font_weight="600",
                ),
                rx.text(desc, font_size="var(--text-xs)", color="var(--color-muted)"),
                align="start",
                gap="0.25rem",
                width="100%",
            )
            for token, desc in _COLOR_SWATCHES
        ],
        columns="4",
        spacing="4",
        width="100%",
    )


def _type_scale() -> rx.Component:
    return rx.vstack(
        *[
            rx.hstack(
                rx.text(
                    "The quick brown fox",
                    font_size=f"var({size_tok})",
                    line_height=f"var({leading_tok})",
                    font_family="var(--font-sans)",
                    width="20rem",
                ),
                rx.vstack(
                    rx.text(
                        f"{size_tok} = {size}",
                        font_family="var(--font-mono)",
                        font_size="var(--text-xs)",
                    ),
                    rx.text(use, font_size="var(--text-xs)", color="var(--color-muted)"),
                    align="start",
                    gap="0",
                ),
                align="center",
                gap="2rem",
                padding="0.5rem 0",
            )
            for size_tok, size, leading_tok, use in _TYPE_SCALE
        ],
        align="start",
        width="100%",
    )


def _spacing_scale() -> rx.Component:
    return rx.vstack(
        *[
            rx.hstack(
                rx.text(
                    tok,
                    font_family="var(--font-mono)",
                    font_size="var(--text-xs)",
                    width="6rem",
                ),
                rx.box(background="var(--color-accent)", height="1rem", width=f"var({tok})"),
                align="center",
                gap="1rem",
            )
            for tok in _SPACING_SCALE
        ],
        align="start",
        width="100%",
    )


def _radius_scale() -> rx.Component:
    return rx.hstack(
        *[
            rx.vstack(
                rx.box(
                    background="var(--color-card-bg)",
                    border="2px solid var(--color-primary)",
                    width="5rem",
                    height="5rem",
                    border_radius=f"var({tok})",
                ),
                rx.text(
                    f"{tok} ({px})",
                    font_family="var(--font-mono)",
                    font_size="var(--text-xs)",
                ),
                align="center",
                gap="0.5rem",
            )
            for tok, px in _RADIUS_SCALE
        ],
        spacing="4",
    )


def _elevation_scale() -> rx.Component:
    return rx.hstack(
        *[
            rx.vstack(
                rx.box(
                    background="var(--color-card-bg)",
                    width="5rem",
                    height="5rem",
                    border_radius="var(--radius-md)",
                    box_shadow=f"var({tok})",
                ),
                rx.text(tok, font_family="var(--font-mono)", font_size="var(--text-xs)"),
                align="center",
                gap="0.5rem",
            )
            for tok in _SHADOW_SCALE
        ],
        spacing="6",
        padding="1rem",
    )


def _motion_demo() -> rx.Component:
    return rx.box(
        rx.text("Hover me", font_family="var(--font-sans)", color="white"),
        background="var(--color-primary)",
        padding="1rem 1.5rem",
        border_radius="var(--radius-md)",
        width="fit-content",
        transition="all var(--motion-base) var(--ease-standard)",
        _hover={
            "background": "var(--color-accent)",
            "transform": "translateY(-2px)",
            "box_shadow": "var(--shadow-lg)",
        },
    )


def _container_scale() -> rx.Component:
    return rx.vstack(
        *[
            rx.hstack(
                rx.text(
                    f"{tok} ({px})",
                    font_family="var(--font-mono)",
                    font_size="var(--text-xs)",
                    width="12rem",
                ),
                rx.box(
                    background="var(--color-rule)",
                    height="0.75rem",
                    max_width=f"var({tok})",
                    width="100%",
                ),
                align="center",
                gap="1rem",
                width="100%",
            )
            for tok, px in _CONTAINER_SCALE
        ],
        align="start",
        width="100%",
    )


def dev_design_system_page() -> rx.Component:
    """Phase-1 verification artefact — remove at M10.5 close."""
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.heading(
                    "Design System — Phase 1 Proof",
                    size="6",
                    font_family="var(--font-serif)",
                    margin_bottom="0.25rem",
                ),
                rx.text(
                    "M10.5 Phase 1 verification artefact — remove at milestone close.",
                    font_size="var(--text-sm)",
                    color="var(--color-muted)",
                    margin_bottom="1rem",
                ),
                _section("Colours", _color_swatches()),
                _section("Type scale", _type_scale()),
                _section("Spacing scale", _spacing_scale()),
                _section("Radius", _radius_scale()),
                _section("Elevation", _elevation_scale()),
                _section("Motion (hover the box)", _motion_demo()),
                _section("Container widths", _container_scale()),
                page_footer(),
                max_width="var(--container-xl)",
                margin="0 auto",
                padding="2rem",
            ),
            width="100%",
            background="var(--color-background)",
            min_height="100vh",
        )
    )
