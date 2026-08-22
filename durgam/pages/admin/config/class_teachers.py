"""Class teacher assignment management page — /admin/config/class-teachers."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    app_shell,
    config_toast,
    form_modal,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.pages.shared.faculty_picker import faculty_picker
from durgam.states.config_class_teacher import ClassTeacherConfigState


def _kebab(row: dict) -> rx.Component:
    return rx.cond(
        ClassTeacherConfigState.ay_is_locked,
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
                    on_click=ClassTeacherConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                        row["id"]
                    ),
                ),
                rx.menu.item(
                    "Deactivate",
                    on_click=ClassTeacherConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
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
                    ClassTeacherConfigState.ay_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=ClassTeacherConfigState.selected_ay_id,
            on_change=ClassTeacherConfigState.on_ay_change,
            width="200px",
        ),
        rx.cond(
            ClassTeacherConfigState.ay_is_locked,
            rx.badge("AY Locked", color_scheme="red", variant="soft"),
            rx.fragment(),
        ),
        align="center",
        gap="0.75rem",
    )


def _dept_selector() -> rx.Component:
    return rx.hstack(
        rx.text("Department:", font_size="0.85rem", color="var(--color-muted)"),
        rx.cond(
            ClassTeacherConfigState.dept_locked,
            rx.text(
                ClassTeacherConfigState.dept_name_display, font_weight="600", font_size="0.9rem"
            ),
            rx.select.root(
                rx.select.trigger(placeholder="Select department"),
                rx.select.content(
                    rx.foreach(
                        ClassTeacherConfigState.dept_options,
                        lambda o: rx.select.item(o["label"], value=o["value"]),
                    ),
                ),
                value=ClassTeacherConfigState.selected_dept_id,
                on_change=ClassTeacherConfigState.on_dept_change,
                width="320px",
            ),
        ),
        align="center",
        gap="0.75rem",
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    ClassTeacherConfigState.editing_id == "",
                    "New Class Teacher",
                    "Edit Class Teacher",
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
                        value=ClassTeacherConfigState.editing_id,
                    ),
                    faculty_picker(
                        selected_label=ClassTeacherConfigState.form_faculty_label,
                        search_value=ClassTeacherConfigState.picker_search,
                        results=ClassTeacherConfigState.picker_results,
                        on_search=ClassTeacherConfigState.on_picker_search,
                        on_select=ClassTeacherConfigState.select_faculty,
                        on_clear=ClassTeacherConfigState.clear_faculty,
                    ),
                    rx.vstack(
                        rx.text("Class *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_class",
                            value=ClassTeacherConfigState.form_class,
                            on_change=ClassTeacherConfigState.set_form_class,
                            placeholder="e.g. BSc-I-A",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Notes", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(
                            name="form_notes",
                            value=ClassTeacherConfigState.form_notes,
                            on_change=ClassTeacherConfigState.set_form_notes,
                            placeholder="Optional notes",
                            width="100%",
                            rows="3",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=ClassTeacherConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=ClassTeacherConfigState.save_teacher,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=ClassTeacherConfigState.show_form,
    )


def admin_config_class_teachers() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        "Class Teacher Assignments",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    rx.cond(
                        ClassTeacherConfigState.ay_is_locked,
                        rx.fragment(),
                        primary_btn(
                            "+ Add Assignment",
                            on_click=ClassTeacherConfigState.open_create,
                        ),
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1rem",
                ),
                rx.hstack(
                    _ay_selector(),
                    _dept_selector(),
                    gap="1.5rem",
                    flex_wrap="wrap",
                ),
                rx.box(height="1rem"),
                config_toast(
                    ClassTeacherConfigState.flash,
                    ClassTeacherConfigState.flash_type,
                    ClassTeacherConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    ClassTeacherConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=ClassTeacherConfigState.teachers,
                        columns=[
                            TableColumn(key="faculty", label="Faculty"),
                            TableColumn(key="class", label="Class"),
                            TableColumn(key="notes", label="Notes"),
                        ],
                        card_primary_key="faculty",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No class teacher assignments found.",
                    ),
                ),
                confirmation_dialog(
                    is_open=ClassTeacherConfigState.confirm_open,
                    title=ClassTeacherConfigState.confirm_title,
                    body=ClassTeacherConfigState.confirm_body,
                    on_confirm=ClassTeacherConfigState.soft_delete_teacher,
                    on_cancel=ClassTeacherConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                align="start",
                width="100%",
            ),
            container="lg",
        )
    )
