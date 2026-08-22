"""Admin faculty directory (/admin/faculty) — M10 Phase P6.

Read-only list of active faculty for admin / HR access. Gated by faculty:read:*.
Search + department/campus/designation filters + pagination. NO PII fields.
"""

from __future__ import annotations

import reflex as rx

from durgam.pages.components import (
    admin_page,
    app_shell,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.faculty_admin import FacultyAdminListState

_COLUMNS = [
    TableColumn(key="employee_id", label="Employee ID"),
    TableColumn(key="name", label="Name"),
    TableColumn(key="designation", label="Designation"),
    TableColumn(key="department_code", label="Department"),
    TableColumn(key="campus", label="Campus"),
]


def _filter_dropdown(label: str, options: rx.Var, selected: rx.Var, toggle) -> rx.Component:
    """Popover + checkbox multi-select. Trigger shows a selected-count badge."""
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


def _search_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            placeholder="Search by name or employee ID",
            value=FacultyAdminListState.search_query,
            on_change=FacultyAdminListState.set_search_query,
            width="22rem",
        ),
        secondary_btn(
            "Clear Filters",
            on_click=FacultyAdminListState.clear_filters,
            type="button",
        ),
        gap="0.75rem",
        align="center",
        width="100%",
    )


def _pagination() -> rx.Component:
    return rx.hstack(
        rx.text(
            "Total: ",
            FacultyAdminListState.total.to_string(),
            font_size="0.85rem",
            color="var(--color-muted)",
        ),
        rx.spacer(),
        secondary_btn(
            "Prev",
            on_click=FacultyAdminListState.prev_page,
            type="button",
            disabled=FacultyAdminListState.page <= 1,
        ),
        rx.text(
            "Page ",
            FacultyAdminListState.page.to_string(),
            " of ",
            FacultyAdminListState.total_pages.to_string(),
            font_size="0.85rem",
        ),
        secondary_btn(
            "Next",
            on_click=FacultyAdminListState.next_page,
            type="button",
            disabled=FacultyAdminListState.page >= FacultyAdminListState.total_pages,
        ),
        gap="0.6rem",
        align="center",
        width="100%",
        margin_top="0.75rem",
    )


def _content() -> rx.Component:
    return app_shell(
        rx.vstack(
            rx.heading("Faculty Directory", size="6", margin_bottom="0.25rem"),
            rx.text(
                "Read-only directory of all active faculty. "
                "Sensitive identifiers are not shown here.",
                font_size="0.85rem",
                color="var(--color-muted)",
                margin_bottom="0.75rem",
            ),
            _search_bar(),
            rx.hstack(
                _filter_dropdown(
                    "Department",
                    FacultyAdminListState.dept_options,
                    FacultyAdminListState.selected_departments,
                    FacultyAdminListState.toggle_department,
                ),
                _filter_dropdown(
                    "Campus",
                    FacultyAdminListState.campus_options,
                    FacultyAdminListState.selected_campuses,
                    FacultyAdminListState.toggle_campus,
                ),
                _filter_dropdown(
                    "Designation",
                    FacultyAdminListState.desig_options,
                    FacultyAdminListState.selected_designations,
                    FacultyAdminListState.toggle_designation,
                ),
                gap="0.6rem",
                wrap="wrap",
                align="center",
                width="100%",
            ),
            rx.cond(
                FacultyAdminListState.loading,
                rx.center(rx.spinner(), padding="3rem"),
                data_table(
                    rows=FacultyAdminListState.rows,
                    columns=_COLUMNS,
                    card_primary_key="employee_id",
                    is_mobile=False,
                    empty_message="No faculty match the current filters.",
                ),
            ),
            _pagination(),
            spacing="3",
            width="100%",
            align="start",
        ),
        container="lg",
    )


def faculty_admin_list_page() -> rx.Component:
    return admin_page(_content())
