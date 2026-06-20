"""Faculty directory (/faculty) — M10 Phase 8A.

Peer-view card grid: photo-or-initials avatar, name, designation, dept, campus.
Search + multi-select filters (P6.1 pattern) + pagination. Card click → detail.
"""

from __future__ import annotations

import reflex as rx

from durgam.pages.components import (
    admin_page,
    nav_shell,
    page_footer,
    secondary_btn,
)
from durgam.states.faculty_directory import FacultyDirectoryState


def _filter_dropdown(
    label: str, options: rx.Var, selected: rx.Var, toggle
) -> rx.Component:
    """Popover + checkbox multi-select with selected-count badge (P6.1 pattern)."""
    return rx.popover.root(
        rx.popover.trigger(
            rx.button(
                rx.hstack(
                    rx.text(label),
                    rx.cond(
                        selected.length() > 0,
                        rx.badge(selected.length().to_string(), color_scheme="indigo"),
                        rx.fragment(),
                    ),
                    rx.icon("chevron-down", size=16),
                    align="center",
                    spacing="2",
                ),
                variant="outline",
                size="2",
                cursor="pointer",
                type="button",
            ),
        ),
        rx.popover.content(
            rx.vstack(
                rx.cond(
                    options.length() == 0,
                    rx.text("No options available", color="gray", size="2"),
                    rx.foreach(
                        options,
                        lambda opt: rx.hstack(
                            rx.checkbox(
                                checked=selected.contains(opt),
                                on_change=toggle(opt),
                            ),
                            rx.text(opt, size="2"),
                            spacing="2",
                            align="center",
                            width="100%",
                        ),
                    ),
                ),
                spacing="2",
                max_height="320px",
                overflow_y="auto",
                padding="2",
                min_width="240px",
                align="start",
            ),
        ),
    )


def _avatar(record: dict) -> rx.Component:
    return rx.cond(
        record["photo_url"] != "",
        rx.image(
            src=record["photo_url"],
            width="72px",
            height="72px",
            object_fit="cover",
            border_radius="50%",
            border="1px solid var(--color-rule)",
        ),
        rx.box(
            rx.text(
                record["initials"],
                font_size="1.5rem",
                font_weight="600",
                color="white",
            ),
            width="72px",
            height="72px",
            border_radius="50%",
            background="var(--color-primary)",
            display="flex",
            align_items="center",
            justify_content="center",
        ),
    )


def _card(record: dict) -> rx.Component:
    return rx.box(
        rx.vstack(
            _avatar(record),
            rx.heading(record["name"], size="3", text_align="center"),
            rx.text(record["designation"], font_size="0.85rem", color="var(--color-muted)"),
            rx.hstack(
                rx.badge(record["department_code"], color_scheme="gray"),
                rx.badge(record["campus_code"], color_scheme="gray"),
                gap="0.4rem",
            ),
            rx.text(
                record["employee_id"],
                font_size="0.75rem",
                color="var(--color-muted)",
            ),
            align="center",
            gap="0.4rem",
        ),
        on_click=FacultyDirectoryState.navigate_to_detail_by_id(record["faculty_id"]),
        cursor="pointer",
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="10px",
        padding="1.25rem",
        width="100%",
        _hover={"border_color": "var(--color-primary)", "box_shadow": "0 2px 12px rgba(0,0,0,0.08)"},
    )


def _grid() -> rx.Component:
    # Plain CSS auto-fill grid: tiles cards into as many 220px+ columns as fit the
    # viewport. More robust than rx.grid(columns=rx.breakpoints(...)), whose
    # mobile-first initial="1" was rendering one card per row (looked like rows).
    return rx.box(
        rx.foreach(FacultyDirectoryState.rows, _card),
        display="grid",
        grid_template_columns="repeat(auto-fill, minmax(220px, 1fr))",
        gap="1rem",
        width="100%",
    )


def _search_and_filters() -> rx.Component:
    return rx.vstack(
        rx.input(
            placeholder="Search by name or employee ID",
            value=FacultyDirectoryState.search_query,
            on_change=FacultyDirectoryState.set_search_query,
            width="24rem",
            max_width="100%",
        ),
        rx.hstack(
            _filter_dropdown(
                "Department",
                FacultyDirectoryState.dept_options,
                FacultyDirectoryState.selected_departments,
                FacultyDirectoryState.toggle_department,
            ),
            _filter_dropdown(
                "Campus",
                FacultyDirectoryState.campus_options,
                FacultyDirectoryState.selected_campuses,
                FacultyDirectoryState.toggle_campus,
            ),
            _filter_dropdown(
                "Designation",
                FacultyDirectoryState.desig_options,
                FacultyDirectoryState.selected_designations,
                FacultyDirectoryState.toggle_designation,
            ),
            secondary_btn(
                "Clear Filters",
                on_click=FacultyDirectoryState.clear_filters,
                type="button",
            ),
            gap="0.6rem",
            wrap="wrap",
            align="center",
        ),
        gap="0.75rem",
        width="100%",
        align="start",
    )


def _pagination() -> rx.Component:
    return rx.hstack(
        rx.text(
            "Total: ",
            FacultyDirectoryState.total.to_string(),
            font_size="0.85rem",
            color="var(--color-muted)",
        ),
        rx.spacer(),
        secondary_btn(
            "Prev",
            on_click=FacultyDirectoryState.prev_page,
            type="button",
            disabled=FacultyDirectoryState.page <= 1,
        ),
        rx.text(
            "Page ",
            FacultyDirectoryState.page.to_string(),
            " of ",
            FacultyDirectoryState.total_pages.to_string(),
            font_size="0.85rem",
        ),
        secondary_btn(
            "Next",
            on_click=FacultyDirectoryState.next_page,
            type="button",
            disabled=FacultyDirectoryState.page >= FacultyDirectoryState.total_pages,
        ),
        gap="0.6rem",
        align="center",
        width="100%",
        margin_top="0.75rem",
    )


def _content() -> rx.Component:
    return rx.vstack(
        nav_shell(),
        rx.box(
            rx.vstack(
                rx.heading("Faculty Directory", size="6", margin_bottom="0.25rem"),
                _search_and_filters(),
                rx.cond(
                    FacultyDirectoryState.loading,
                    rx.center(rx.spinner(), padding="3rem"),
                    rx.cond(
                        FacultyDirectoryState.rows.length() == 0,
                        rx.box(
                            rx.text(
                                "No faculty match the current filters.",
                                color="var(--color-muted)",
                                font_size="0.9rem",
                            ),
                            background="white",
                            border="1px solid var(--color-rule)",
                            border_radius="8px",
                            padding="2rem",
                            width="100%",
                        ),
                        _grid(),
                    ),
                ),
                _pagination(),
                spacing="4",
                width="100%",
                align="start",
            ),
            padding="2rem",
            max_width="1200px",
            margin="0 auto",
            width="100%",
        ),
        page_footer(),
        align="start",
        width="100%",
    )


def faculty_directory_page() -> rx.Component:
    return admin_page(_content())
