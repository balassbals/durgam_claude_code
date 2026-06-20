"""Faculty expertise list page (/faculty/profile/expertise) — M10 Phase P3c.

Tier 2 horizontal-scroll table (area, proficiency).
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
from durgam.states.faculty_expertise import FacultyExpertiseState


def _row_actions(record: dict) -> rx.Component:
    return rx.hstack(
        rx.button(
            "Edit",
            on_click=FacultyExpertiseState.open_edit_by_id(record["id"]),
            size="1",
            variant="soft",
            cursor="pointer",
        ),
        rx.button(
            "Delete",
            on_click=FacultyExpertiseState.open_delete_confirm_by_id(record["id"]),
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
        "min_width": "14rem",
        "white_space": "nowrap",
    }
    return rx.table.row(
        rx.table.cell(record["area"], style=sticky_cell_style),
        rx.table.cell(record["proficiency"], min_width="10rem"),
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
                    rx.table.column_header_cell("Area", style=sticky_header_style),
                    rx.table.column_header_cell("Proficiency"),
                    rx.table.column_header_cell("Actions"),
                )
            ),
            rx.table.body(
                rx.foreach(FacultyExpertiseState.records, _exp_row),
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
                    FacultyExpertiseState.form_exp_id == "",
                    "Add Expertise",
                    "Edit Expertise",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.vstack(
                        rx.text(
                            "Area of Expertise *",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                        ),
                        rx.input(
                            name="form_area",
                            value=FacultyExpertiseState.form_area,
                            on_change=FacultyExpertiseState.set_form_area,
                            placeholder="e.g. Machine Learning",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Proficiency", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_proficiency",
                            value=FacultyExpertiseState.form_proficiency,
                            on_change=FacultyExpertiseState.set_form_proficiency,
                            placeholder="e.g. Expert, Intermediate",
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
                            on_click=FacultyExpertiseState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                        margin_top="0.5rem",
                    ),
                    gap="1rem",
                    width="100%",
                ),
                on_submit=FacultyExpertiseState.save_expertise,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=FacultyExpertiseState.show_form,
    )


def _delete_confirm_dialog() -> rx.Component:
    return confirmation_dialog(
        is_open=FacultyExpertiseState.show_delete_confirm,
        title="Delete expertise record?",
        body=rx.vstack(
            rx.text(
                "This will remove the following expertise record. You can add it again later."
            ),
            rx.text(
                FacultyExpertiseState.deleting_area,
                font_weight="600",
            ),
            gap="0.4rem",
            align="start",
        ),
        on_confirm=FacultyExpertiseState.confirm_delete,
        on_cancel=FacultyExpertiseState.cancel_delete,
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


def faculty_expertise_page() -> rx.Component:
    return rx.cond(
        AuthState.current_user_id != "",
        rx.vstack(
            rx.toast.provider(),
            nav_shell(),
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.heading("My Expertise", size="6"),
                        rx.spacer(),
                        primary_btn(
                            "+ Add Expertise",
                            on_click=FacultyExpertiseState.open_create_modal,
                        ),
                        width="100%",
                        align="center",
                        margin_bottom="0.5rem",
                    ),
                    rx.cond(
                        FacultyExpertiseState.loading,
                        rx.center(rx.spinner(), padding="4rem"),
                        rx.cond(
                            ~FacultyExpertiseState.has_faculty_record,
                            _no_faculty_record_message(),
                            rx.cond(
                                FacultyExpertiseState.records.length() == 0,
                                rx.box(
                                    rx.text(
                                        "No expertise records yet. Click '+ Add Expertise' to add one.",
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
