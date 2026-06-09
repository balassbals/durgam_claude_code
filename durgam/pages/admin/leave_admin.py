"""Late Attendance admin page — /admin/leave/late-attendance (M8 Phase 8)."""

import reflex as rx

from durgam.pages.components import (
    config_toast,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.auth import AuthState
from durgam.states.leave_admin import LateAttendanceAdminState

_COLUMNS: list[TableColumn] = [
    TableColumn(key="employee",    label="Employee"),
    TableColumn(key="occurred_on", label="Date"),
    TableColumn(key="notes",       label="Notes",       hidden_on_card=True),
    TableColumn(key="recorded_at", label="Recorded On", hidden_on_card=True),
]


def _add_marker_form() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Record Late Attendance", size="4", font_family="var(--font-sans)"),
            rx.form(
                rx.vstack(
                    # Employee username lookup
                    rx.vstack(
                        rx.text("Employee Username *", font_size="0.85rem", font_weight="500"),
                        rx.hstack(
                            rx.input(
                                name="form_employee_username",
                                placeholder="e.g. faculty_001",
                                value=LateAttendanceAdminState.form_employee_username,
                                on_change=LateAttendanceAdminState.set_form_employee_username,
                                on_blur=LateAttendanceAdminState.resolve_employee,
                                size="2",
                                flex="1",
                            ),
                            secondary_btn(
                                "Lookup",
                                on_click=LateAttendanceAdminState.resolve_employee,
                                type="button",
                                size="2",
                            ),
                            gap="0.5rem",
                            width="100%",
                        ),
                        rx.cond(
                            LateAttendanceAdminState.form_employee_display != "",
                            rx.text(
                                LateAttendanceAdminState.form_employee_display,
                                font_size="0.8rem",
                                color="var(--color-success)",
                                font_weight="500",
                            ),
                            rx.fragment(),
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    # Date
                    rx.vstack(
                        rx.text("Date *", font_size="0.85rem", font_weight="500"),
                        rx.input(
                            name="form_occurred_on",
                            type="date",
                            value=LateAttendanceAdminState.form_occurred_on,
                            on_change=LateAttendanceAdminState.set_form_occurred_on,
                            size="2",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    # Notes
                    rx.vstack(
                        rx.text("Notes (optional)", font_size="0.85rem", font_weight="500"),
                        rx.text_area(
                            name="form_notes",
                            value=LateAttendanceAdminState.form_notes,
                            on_change=LateAttendanceAdminState.set_form_notes,
                            placeholder="Reason or context",
                            rows="2",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    # Submit
                    rx.hstack(
                        primary_btn("Record Marker", type="submit"),
                        gap="0.75rem",
                        justify="end",
                        width="100%",
                    ),
                    gap="1rem",
                    width="100%",
                    align="start",
                ),
                on_submit=LateAttendanceAdminState.add_marker,
                reset_on_submit=False,
                width="100%",
            ),
            gap="1rem",
            align="start",
            width="100%",
        ),
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="1.5rem",
        background="var(--color-surface)",
        max_width="500px",
        width="100%",
    )


def _filter_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            placeholder="Filter by month (YYYY-MM)",
            value=LateAttendanceAdminState.filter_month,
            on_change=LateAttendanceAdminState.set_filter_month,
            size="2",
            width="180px",
        ),
        primary_btn("Filter", on_click=LateAttendanceAdminState.apply_filter, type="button"),
        gap="0.5rem",
        align="center",
    )


def admin_late_attendance() -> rx.Component:
    page_content = rx.vstack(
        nav_shell(),
        rx.box(
            rx.heading(
                "Late Attendance Markers",
                size="5",
                font_family="var(--font-sans)",
                margin_bottom="1.5rem",
            ),
            config_toast(
                LateAttendanceAdminState.flash,
                LateAttendanceAdminState.flash_type,
                LateAttendanceAdminState.dismiss_flash,
            ),
            rx.flex(
                _add_marker_form(),
                rx.vstack(
                    rx.hstack(
                        rx.heading("Recent Markers", size="4", font_family="var(--font-sans)"),
                        rx.spacer(),
                        _filter_bar(),
                        align="center",
                        width="100%",
                        margin_bottom="1rem",
                    ),
                    rx.cond(
                        LateAttendanceAdminState.loading,
                        rx.center(rx.spinner(), padding="2rem"),
                        data_table(
                            rows=LateAttendanceAdminState.markers,
                            columns=_COLUMNS,
                            card_primary_key="employee",
                            is_mobile=False,
                            empty_message="No late-attendance markers found.",
                        ),
                    ),
                    align="start",
                    width="100%",
                    flex="1",
                ),
                gap="2rem",
                align="start",
                width="100%",
                flex_wrap="wrap",
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

    return rx.cond(
        AuthState.current_user_id != "",
        page_content,
        rx.fragment(),
    )
