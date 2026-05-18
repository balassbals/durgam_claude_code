"""Config landing page — /admin/config."""

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer
from durgam.states.config_landing import ConfigLandingState


def _config_tile(label: str, href: str, description: str) -> rx.Component:
    return rx.link(
        rx.box(
            rx.text(label, font_weight="600", font_family="var(--font-sans)"),
            rx.text(
                description,
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
        href=href,
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
                    _config_tile(
                        "Campuses", "/admin/config/campuses",
                        "Manage the four SSSIHL campuses",
                    ),
                    _config_tile(
                        "Schools", "/admin/config/schools",
                        "Four academic schools headed by Deans",
                    ),
                    _config_tile(
                        "Departments", "/admin/config/departments",
                        "Ten departments with school and campus mappings",
                    ),
                    _config_tile(
                        "Centres", "/admin/config/centres",
                        "Centres of Excellence",
                    ),
                    _config_tile(
                        "Programs", "/admin/config/programs",
                        "Academic programs with outcomes and regulations",
                    ),
                    _config_tile(
                        "Courses", "/admin/config/courses",
                        "Course catalogue (basic fields)",
                    ),
                    _config_tile(
                        "Vision & Mission", "/admin/config/vision-mission",
                        "University and department vision/mission statements",
                    ),
                    _config_tile(
                        "Class Timings", "/admin/config/class-timings",
                        "Institute-wide period timings",
                    ),
                    _config_tile(
                        "Working Days", "/admin/config/working-days",
                        "5-day or 6-day work week",
                    ),
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
