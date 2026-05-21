"""Config landing page — /admin/config.

Tiles are filtered by the user's write/configure permissions: sys_admin sees all 9,
registrar sees 3 (Vision & Mission, Class Timings, Working Days), students see none.
"""

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer
from durgam.states.config_landing import ConfigLandingState


def _config_tile(tile: dict) -> rx.Component:
    """Render one config tile from a state-var dict {label, href, description}."""
    return rx.link(
        rx.box(
            rx.text(
                tile["label"],
                font_weight="600",
                font_family="var(--font-sans)",
            ),
            rx.text(
                tile["description"],
                font_size="0.8rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            border="1px solid var(--color-rule)",
            border_radius="8px",
            padding="1.25rem",
            background="white",
            _hover={
                "border_color": "var(--color-primary)",
                "box_shadow": "0 2px 8px rgba(0,0,0,0.08)",
            },
            transition="border-color 0.15s, box-shadow 0.15s",
        ),
        href=tile["href"],
        text_decoration="none",
        color="var(--color-body)",
    )


def admin_config_index() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.heading(
                    "Configuration",
                    size="5",
                    font_family="var(--font-sans)",
                    margin_bottom="0.5rem",
                ),
                rx.text(
                    "Manage organisational structure and institute-wide settings.",
                    color="var(--color-muted)",
                    font_size="0.9rem",
                    margin_bottom="2rem",
                    font_family="var(--font-sans)",
                ),
                rx.grid(
                    rx.foreach(ConfigLandingState.config_tiles, _config_tile),
                    columns="repeat(auto-fill, minmax(220px, 1fr))",
                    gap="1rem",
                ),
                padding="2rem",
                max_width="1200px",
                width="100%",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
