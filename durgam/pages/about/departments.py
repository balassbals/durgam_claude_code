"""Departments list — read-only (/about/departments)."""

import reflex as rx

from durgam.pages.components import nav_shell, page_footer
from durgam.states.about import AboutDeptListState
from durgam.states.auth import AuthState


def _dept_row(row: dict) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(
                row["name"],
                font_weight="600",
                font_size="0.9rem",
                font_family="var(--font-sans)",
                color="var(--color-body)",
            ),
            rx.text(
                row["code"],
                font_size="0.8rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            align="start",
            gap="0.1rem",
            flex="1",
        ),
        rx.hstack(
            rx.text(
                rx.cond(row["has_vision"] == "Yes", "Vision configured", "Not yet configured"),
                font_size="0.8rem",
                color=rx.cond(row["has_vision"] == "Yes", "var(--color-success-border)", "var(--color-muted)"),
                font_family="var(--font-sans)",
            ),
            rx.link(
                "View",
                href=row["view_href"],
                font_size="0.85rem",
                color="var(--color-primary)",
                font_family="var(--font-sans)",
                padding="0.25rem 0.65rem",
                border="1px solid var(--color-primary)",
                border_radius="4px",
                text_decoration="none",
            ),
            gap="1rem",
            align="center",
        ),
        align="center",
        justify="between",
        width="100%",
        padding="0.75rem 1rem",
        border_bottom="1px solid var(--color-rule)",
        background="white",
    )


def about_departments() -> rx.Component:
    return rx.cond(
        AuthState.current_user_id != "",
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.heading(
                    "Department Vision & Mission",
                    size="5",
                    font_family="var(--font-sans)",
                    margin_bottom="0.5rem",
                ),
                rx.text(
                    "Click 'View' on any department to read its vision and mission statements.",
                    font_size="0.875rem",
                    color="var(--color-muted)",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                ),
                rx.cond(
                    AboutDeptListState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    rx.cond(
                        AboutDeptListState.dept_rows.length() == 0,  # type: ignore[attr-defined]
                        rx.text(
                            "No departments found.",
                            color="var(--color-muted)",
                            font_family="var(--font-sans)",
                        ),
                        rx.box(
                            rx.foreach(AboutDeptListState.dept_rows, _dept_row),
                            border="1px solid var(--color-rule)",
                            border_radius="6px",
                            overflow="hidden",
                            width="100%",
                        ),
                    ),
                ),
                padding="2rem",
                max_width="800px",
                width="100%",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        ),
        rx.fragment(),
    )
