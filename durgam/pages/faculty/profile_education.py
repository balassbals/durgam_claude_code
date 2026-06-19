"""Faculty education list page (/faculty/profile/education) — M10 Phase P3a.

Tier 2 horizontal-scroll table (5 data columns + actions).
"""

from __future__ import annotations

import reflex as rx

from durgam.pages.components import (
    form_modal,
    nav_shell,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.states.auth import AuthState
from durgam.states.faculty_education import FacultyEducationState


def _row_actions(record: dict) -> rx.Component:
    return rx.hstack(
        rx.button(
            "Edit",
            on_click=FacultyEducationState.open_edit_by_id(record["id"]),
            size="1",
            variant="soft",
            cursor="pointer",
        ),
        rx.button(
            "Delete",
            on_click=FacultyEducationState.open_delete_confirm_by_id(record["id"]),
            size="1",
            variant="soft",
            color_scheme="red",
            cursor="pointer",
        ),
        gap="0.4rem",
    )


def _edu_row(record: dict) -> rx.Component:
    sticky_cell_style = {
        "position": "sticky",
        "left": "0",
        "background_color": "white",
        "z_index": "1",
        "min_width": "10rem",
        "white_space": "nowrap",
    }
    return rx.table.row(
        rx.table.cell(record["degree_name"], style=sticky_cell_style),
        rx.table.cell(record["specialization"], min_width="8rem"),
        rx.table.cell(record["awarding_institution"], min_width="12rem"),
        rx.table.cell(record["year_of_award"], min_width="5rem"),
        rx.table.cell(record["distinction"], min_width="8rem"),
        rx.table.cell(_row_actions(record), min_width="8rem"),
    )


def _edu_table() -> rx.Component:
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
                    rx.table.column_header_cell("Degree", style=sticky_header_style),
                    rx.table.column_header_cell("Specialization"),
                    rx.table.column_header_cell("Institution"),
                    rx.table.column_header_cell("Year"),
                    rx.table.column_header_cell("Distinction"),
                    rx.table.column_header_cell("Actions"),
                )
            ),
            rx.table.body(
                rx.foreach(FacultyEducationState.records, _edu_row),
            ),
            width="100%",
        ),
        overflow_x="auto",
        width="100%",
    )


def _edu_form_modal() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    FacultyEducationState.form_edu_id == "",
                    "Add Education",
                    "Edit Education",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.vstack(
                        rx.text("Degree *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_degree_name",
                            value=FacultyEducationState.form_degree_name,
                            on_change=FacultyEducationState.set_form_degree_name,
                            placeholder="e.g. B.Tech, M.Tech, PhD",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Specialization", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_specialization",
                            value=FacultyEducationState.form_specialization,
                            on_change=FacultyEducationState.set_form_specialization,
                            placeholder="e.g. Computer Science",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Awarding Institution *",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                        ),
                        rx.input(
                            name="form_awarding_institution",
                            value=FacultyEducationState.form_awarding_institution,
                            on_change=FacultyEducationState.set_form_awarding_institution,
                            placeholder="e.g. IIT Madras",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Year of Award *",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                        ),
                        rx.input(
                            name="form_year_str",
                            value=FacultyEducationState.form_year_str,
                            on_change=FacultyEducationState.set_form_year_str,
                            placeholder="e.g. 2015",
                            type="number",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Distinction", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_distinction",
                            value=FacultyEducationState.form_distinction,
                            on_change=FacultyEducationState.set_form_distinction,
                            placeholder="e.g. First Class, Gold Medal",
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
                            on_click=FacultyEducationState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                        margin_top="0.5rem",
                    ),
                    gap="1rem",
                    width="100%",
                ),
                on_submit=FacultyEducationState.save_education,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=FacultyEducationState.show_form,
    )


def _delete_confirm_dialog() -> rx.Component:
    return confirmation_dialog(
        is_open=FacultyEducationState.show_delete_confirm,
        title="Delete education record?",
        body=rx.vstack(
            rx.text(
                "This will remove the following education record. You can add it again later."
            ),
            rx.text(
                FacultyEducationState.deleting_degree,
                font_weight="600",
            ),
            gap="0.4rem",
            align="start",
        ),
        on_confirm=FacultyEducationState.confirm_delete,
        on_cancel=FacultyEducationState.cancel_delete,
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


def faculty_education_page() -> rx.Component:
    return rx.cond(
        AuthState.current_user_id != "",
        rx.vstack(
            rx.toast.provider(),
            nav_shell(),
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.heading("My Education", size="6"),
                        rx.spacer(),
                        primary_btn(
                            "+ Add Education",
                            on_click=FacultyEducationState.open_create_modal,
                        ),
                        width="100%",
                        align="center",
                        margin_bottom="0.5rem",
                    ),
                    rx.cond(
                        FacultyEducationState.loading,
                        rx.center(rx.spinner(), padding="4rem"),
                        rx.cond(
                            ~FacultyEducationState.has_faculty_record,
                            _no_faculty_record_message(),
                            rx.cond(
                                FacultyEducationState.records.length() == 0,
                                rx.box(
                                    rx.text(
                                        "No education records yet. Click '+ Add Education' to add one.",
                                        color="var(--color-muted)",
                                        font_size="0.9rem",
                                    ),
                                    background="white",
                                    border="1px solid var(--color-rule)",
                                    border_radius="8px",
                                    padding="2rem",
                                    width="100%",
                                ),
                                _edu_table(),
                            ),
                        ),
                    ),
                    _edu_form_modal(),
                    _delete_confirm_dialog(),
                    spacing="4",
                    width="100%",
                ),
                padding="2rem",
                max_width="1100px",
                margin="0 auto",
                width="100%",
            ),
            align="start",
            width="100%",
        ),
        rx.fragment(),
    )
