"""Vision & Mission management page — /admin/config/vision-mission (Session 7)."""

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer
from durgam.states.config_vision_mission import VisionMissionConfigState


def admin_config_vision_mission() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.link(
                    "← Configuration",
                    href="/admin/config",
                    font_size="0.85rem",
                    color="var(--color-primary)",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                    display="block",
                ),
                rx.heading(
                    "Vision & Mission",
                    size="5",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                ),
                rx.box(
                    rx.vstack(
                        rx.text(
                            "Vision & Mission management ships in Session 7.",
                            font_weight="600",
                            font_family="var(--font-sans)",
                        ),
                        rx.text(
                            "Includes: university vision/mission edit (Registrar), "
                            "department vision/mission edit (HoD scoped to their department), "
                            "ordered mission statement list with add/reorder, "
                            "and read-only /about/* pages visible to all authenticated users.",
                            color="var(--color-muted)",
                            font_size="0.9rem",
                            font_family="var(--font-sans)",
                        ),
                        align="start",
                        gap="0.5rem",
                    ),
                    border="1px solid var(--color-rule)",
                    border_radius="8px",
                    padding="1.5rem",
                    background="white",
                    max_width="600px",
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
