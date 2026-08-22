"""Faculty experience list page (/faculty/profile/experience) — M10 Phase P3b.

Tier 2 horizontal-scroll table (organization, designation, date range, responsibilities).
"""

from __future__ import annotations

import reflex as rx

from durgam.pages.components import (
    app_shell,
    form_modal,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.states.auth import AuthState
from durgam.states.faculty_experience import FacultyExperienceState


def _row_actions(record: dict) -> rx.Component:
    return rx.hstack(
        rx.button(
            "Edit",
            on_click=FacultyExperienceState.open_edit_by_id(record["id"]),
            size="1",
            variant="soft",
            cursor="pointer",
        ),
        rx.button(
            "Delete",
            on_click=FacultyExperienceState.open_delete_confirm_by_id(record["id"]),
            size="1",
            variant="soft",
            color_scheme="red",
            cursor="pointer",
        ),
        gap="0.4rem",
    )


def _exp_row(record: dict) -> rx.Component:
    sticky_cell_style = {
        "position": "sticky",
        "left": "0",
        "background_color": "white",
        "z_index": "1",
        "min_width": "12rem",
        "white_space": "nowrap",
    }
    return rx.table.row(
        rx.table.cell(record["organization"], style=sticky_cell_style),
        rx.table.cell(record["designation_held"], min_width="10rem"),
        rx.table.cell(record["date_range"], min_width="12rem"),
        rx.table.cell(record["responsibilities_short"], min_width="14rem"),
        rx.table.cell(_row_actions(record), min_width="8rem"),
    )


def _exp_table() -> rx.Component:
    sticky_header_style = {
        "position": "sticky",
        "left": "0",
        "background_color": "var(--gray-2)",
        "z_index": "2",
    }
    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Organization", style=sticky_header_style),
                    rx.table.column_header_cell("Designation"),
                    rx.table.column_header_cell("Period"),
                    rx.table.column_header_cell("Responsibilities"),
                    rx.table.column_header_cell("Actions"),
                )
            ),
            rx.table.body(
                rx.foreach(FacultyExperienceState.records, _exp_row),
            ),
            width="100%",
        ),
        overflow_x="auto",
        width="100%",
    )


def _exp_form_modal() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    FacultyExperienceState.form_exp_id == "",
                    "Add Experience",
                    "Edit Experience",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.vstack(
                        rx.text("Organization *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_organization",
                            value=FacultyExperienceState.form_organization,
                            on_change=FacultyExperienceState.set_form_organization,
                            placeholder="e.g. Infosys Ltd.",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Designation Held *",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                        ),
                        rx.input(
                            name="form_designation_held",
                            value=FacultyExperienceState.form_designation_held,
                            on_change=FacultyExperienceState.set_form_designation_held,
                            placeholder="e.g. Senior Engineer",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text("From *", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(
                                type="date",
                                name="form_from_date_str",
                                value=FacultyExperienceState.form_from_date_str,
                                on_change=FacultyExperienceState.set_form_from_date_str,
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            flex="1",
                        ),
                        rx.vstack(
                            rx.text(
                                "To (leave blank if current)",
                                font_size="0.85rem",
                                color="var(--color-muted)",
                            ),
                            rx.input(
                                type="date",
                                name="form_to_date_str",
                                value=FacultyExperienceState.form_to_date_str,
                                on_change=FacultyExperienceState.set_form_to_date_str,
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            flex="1",
                        ),
                        gap="0.75rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Responsibilities",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                        ),
                        rx.text_area(
                            name="form_responsibilities",
                            value=FacultyExperienceState.form_responsibilities,
                            on_change=FacultyExperienceState.set_form_responsibilities,
                            placeholder="Brief description of responsibilities",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=FacultyExperienceState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                        margin_top="0.5rem",
                    ),
                    gap="1rem",
                    width="100%",
                ),
                on_submit=FacultyExperienceState.save_experience,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=FacultyExperienceState.show_form,
    )


def _delete_confirm_dialog() -> rx.Component:
    return confirmation_dialog(
        is_open=FacultyExperienceState.show_delete_confirm,
        title="Delete experience record?",
        body=rx.vstack(
            rx.text(
                "This will remove the following experience record. You can add it again later."
            ),
            rx.text(
                FacultyExperienceState.deleting_organization,
                font_weight="600",
            ),
            gap="0.4rem",
            align="start",
        ),
        on_confirm=FacultyExperienceState.confirm_delete,
        on_cancel=FacultyExperienceState.cancel_delete,
        confirm_label="Yes, delete",
        cancel_label="Cancel",
        danger=True,
    )


def _no_faculty_record_message() -> rx.Component:
    return rx.box(
        rx.heading("No Faculty Profile", size="5", margin_bottom="0.75rem"),
        rx.text(
            "You do not have a Faculty profile in this system. "
            "Contact the Registrar's office if this is an error.",
            color="var(--color-muted)",
            font_size="0.9rem",
        ),
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="2rem",
        width="100%",
    )


def faculty_experience_page() -> rx.Component:
    return rx.cond(
        AuthState.current_user_id != "",
        app_shell(
            rx.fragment(
                rx.toast.provider(),
                rx.vstack(
                    rx.hstack(
                        rx.heading("My Experience", size="6"),
                        rx.spacer(),
                        primary_btn(
                            "+ Add Experience",
                            on_click=FacultyExperienceState.open_create_modal,
                        ),
                        width="100%",
                        align="center",
                        margin_bottom="0.5rem",
                    ),
                    rx.cond(
                        FacultyExperienceState.loading,
                        rx.center(rx.spinner(), padding="4rem"),
                        rx.cond(
                            ~FacultyExperienceState.has_faculty_record,
                            _no_faculty_record_message(),
                            rx.cond(
                                FacultyExperienceState.records.length() == 0,
                                rx.box(
                                    rx.text(
                                        "No experience records yet. Click '+ Add Experience' to add one.",
                                        color="var(--color-muted)",
                                        font_size="0.9rem",
                                    ),
                                    background="white",
                                    border="1px solid var(--color-rule)",
                                    border_radius="8px",
                                    padding="2rem",
                                    width="100%",
                                ),
                                _exp_table(),
                            ),
                        ),
                    ),
                    _exp_form_modal(),
                    _delete_confirm_dialog(),
                    spacing="4",
                    width="100%",
                ),
            ),
            container="lg",
        ),
        rx.fragment(),
    )
