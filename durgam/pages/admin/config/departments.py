"""Department management page — /admin/config/departments (Session 6)."""

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer
from durgam.states.config_department import DepartmentConfigState


def admin_config_departments() -> rx.Component:
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
                    "Departments",
                    size="5",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                ),
                rx.box(
                    rx.vstack(
                        rx.text(
                            "Department management ships in Session 6.",
                            font_weight="600",
                            font_family="var(--font-sans)",
                        ),
                        rx.text(
                            "Includes: 10 department rows with school and campus mappings, "
                            "campus-link management, sub-department listing, and create/edit forms "
                            "gated by department:write:* (SYSTEM_ADMIN only per §9.3).",
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
