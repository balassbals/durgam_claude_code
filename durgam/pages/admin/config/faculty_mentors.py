"""Faculty mentor assignment management page — /admin/config/faculty-mentors."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    config_toast,
    form_modal,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.config_faculty_mentor import FacultyMentorConfigState


def _kebab(row: dict) -> rx.Component:
    return rx.cond(
        FacultyMentorConfigState.ay_is_locked,
        rx.text("\U0001f512", font_size="0.8rem", color="var(--color-muted)"),
        rx.menu.root(
            rx.menu.trigger(
                rx.button(
                    "⋮",
                    background="transparent",
                    border="none",
                    cursor="pointer",
                    font_size="1.2rem",
                    color="var(--color-muted)",
                    padding="0.1rem 0.4rem",
                )
            ),
            rx.menu.content(
                rx.menu.item(
                    "Edit",
                    on_click=FacultyMentorConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["faculty"], row["student"], row["notes"]
                    ),
                ),
                rx.menu.item(
                    "Deactivate",
                    on_click=FacultyMentorConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["faculty"]
                    ),
                    color="var(--color-danger, #c0392b)",
                ),
            ),
        ),
    )


def _ay_selector() -> rx.Component:
    return rx.hstack(
        rx.text("Academic Year:", font_size="0.85rem", color="var(--color-muted)"),
        rx.select.root(
            rx.select.trigger(placeholder="Select academic year"),
            rx.select.content(
                rx.foreach(
                    FacultyMentorConfigState.ay_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=FacultyMentorConfigState.selected_ay_id,
            on_change=FacultyMentorConfigState.on_ay_change,
            width="200px",
        ),
        rx.cond(
            FacultyMentorConfigState.ay_is_locked,
            rx.badge("AY Locked", color_scheme="red", variant="soft"),
            rx.fragment(),
        ),
        align="center",
        gap="0.75rem",
    )


def _campus_selector() -> rx.Component:
    return rx.hstack(
        rx.text("Campus:", font_size="0.85rem", color="var(--color-muted)"),
        rx.select.root(
            rx.select.trigger(placeholder="Select campus"),
            rx.select.content(
                rx.foreach(
                    FacultyMentorConfigState.campus_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=FacultyMentorConfigState.selected_campus_id,
            on_change=FacultyMentorConfigState.on_campus_change,
            width="280px",
        ),
        align="center",
        gap="0.75rem",
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    FacultyMentorConfigState.editing_id == "",
                    "New Mentor Assignment",
                    "Edit Mentor Assignment",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.input(
                        type="hidden",
                        name="editing_id",
                        value=FacultyMentorConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Faculty *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_faculty",
                            value=FacultyMentorConfigState.form_faculty,
                            on_change=FacultyMentorConfigState.set_form_faculty,
                            placeholder="Faculty identifier",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Student *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_student",
                            value=FacultyMentorConfigState.form_student,
                            on_change=FacultyMentorConfigState.set_form_student,
                            placeholder="Student identifier",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Notes", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(
                            name="form_notes",
                            value=FacultyMentorConfigState.form_notes,
                            on_change=FacultyMentorConfigState.set_form_notes,
                            placeholder="Optional notes",
                            width="100%",
                            rows="3",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=FacultyMentorConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=FacultyMentorConfigState.save_mentor,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=FacultyMentorConfigState.show_form,
    )


def admin_config_faculty_mentors() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "Faculty Mentor Assignments",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    rx.cond(
                        FacultyMentorConfigState.ay_is_locked,
                        rx.fragment(),
                        primary_btn(
                            "+ Add Assignment",
                            on_click=FacultyMentorConfigState.open_create,
                        ),
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1rem",
                ),
                rx.hstack(
                    _ay_selector(),
                    _campus_selector(),
                    gap="1.5rem",
                    flex_wrap="wrap",
                ),
                rx.box(height="1rem"),
                config_toast(
                    FacultyMentorConfigState.flash,
                    FacultyMentorConfigState.flash_type,
                    FacultyMentorConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    FacultyMentorConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=FacultyMentorConfigState.mentors,
                        columns=[
                            TableColumn(key="faculty", label="Faculty"),
                            TableColumn(key="student", label="Student"),
                            TableColumn(key="notes", label="Notes"),
                        ],
                        card_primary_key="faculty",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No mentor assignments found for this academic year and campus.",
                    ),
                ),
                confirmation_dialog(
                    is_open=FacultyMentorConfigState.confirm_open,
                    title=FacultyMentorConfigState.confirm_title,
                    body=FacultyMentorConfigState.confirm_body,
                    on_confirm=FacultyMentorConfigState.soft_delete_mentor,
                    on_cancel=FacultyMentorConfigState.cancel_confirm,
                    confirm_label="Deactivate",
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
