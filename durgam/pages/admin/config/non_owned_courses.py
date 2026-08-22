"""Non-owned courses management page — /admin/config/non-owned-courses."""

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
from durgam.states.config_non_owned_course import NonOwnedCourseConfigState


def _kebab(row: dict) -> rx.Component:
    return rx.cond(
        NonOwnedCourseConfigState.ay_is_locked,
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
                    on_click=NonOwnedCourseConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                        row["id"]
                    ),
                ),
                rx.menu.item(
                    "Deactivate",
                    on_click=NonOwnedCourseConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["course_code"]
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
                    NonOwnedCourseConfigState.ay_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=NonOwnedCourseConfigState.selected_ay_id,
            on_change=NonOwnedCourseConfigState.on_ay_change,
            width="200px",
        ),
        rx.cond(
            NonOwnedCourseConfigState.ay_is_locked,
            rx.badge("AY Locked", color_scheme="red", variant="soft"),
            rx.fragment(),
        ),
        align="center",
        gap="0.75rem",
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    NonOwnedCourseConfigState.editing_id == "",
                    "New Non-Owned Course",
                    "Edit Non-Owned Course",
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
                        value=NonOwnedCourseConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Course Code *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_course_code",
                            value=NonOwnedCourseConfigState.form_course_code,
                            on_change=NonOwnedCourseConfigState.set_form_course_code,
                            placeholder="e.g. MDC101",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Course Name *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_course_name",
                            value=NonOwnedCourseConfigState.form_course_name,
                            on_change=NonOwnedCourseConfigState.set_form_course_name,
                            placeholder="e.g. Moral and Divine Culture",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Credits", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_credits",
                            type="number",
                            value=NonOwnedCourseConfigState.form_credits,
                            on_change=NonOwnedCourseConfigState.set_form_credits,
                            placeholder="0",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Semester *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select semester"),
                            rx.select.content(
                                rx.select.item("Odd", value="odd"),
                                rx.select.item("Even", value="even"),
                            ),
                            name="form_semester",
                            value=NonOwnedCourseConfigState.form_semester,
                            on_change=NonOwnedCourseConfigState.set_form_semester,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    faculty_picker(
                        selected_label=NonOwnedCourseConfigState.form_faculty_label,
                        search_value=NonOwnedCourseConfigState.picker_search,
                        results=NonOwnedCourseConfigState.picker_results,
                        on_search=NonOwnedCourseConfigState.on_picker_search,
                        on_select=NonOwnedCourseConfigState.select_faculty,
                        on_clear=NonOwnedCourseConfigState.clear_faculty,
                    ),
                    rx.vstack(
                        rx.text("Notes", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(
                            name="form_notes",
                            value=NonOwnedCourseConfigState.form_notes,
                            on_change=NonOwnedCourseConfigState.set_form_notes,
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
                            on_click=NonOwnedCourseConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=NonOwnedCourseConfigState.save_course,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=NonOwnedCourseConfigState.show_form,
    )


def admin_config_non_owned_courses() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        "Non-Owned Courses",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    rx.cond(
                        NonOwnedCourseConfigState.ay_is_locked,
                        rx.fragment(),
                        primary_btn(
                            "+ Add Course",
                            on_click=NonOwnedCourseConfigState.open_create,
                        ),
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1rem",
                ),
                rx.hstack(
                    _ay_selector(),
                    gap="1.5rem",
                    flex_wrap="wrap",
                ),
                rx.box(height="1rem"),
                config_toast(
                    NonOwnedCourseConfigState.flash,
                    NonOwnedCourseConfigState.flash_type,
                    NonOwnedCourseConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    NonOwnedCourseConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=NonOwnedCourseConfigState.courses,
                        columns=[
                            TableColumn(key="course_code", label="Code"),
                            TableColumn(key="course_name", label="Name"),
                            TableColumn(key="credits", label="Credits"),
                            TableColumn(key="semester", label="Semester"),
                            TableColumn(key="faculty", label="Faculty"),
                            TableColumn(key="notes", label="Notes"),
                        ],
                        card_primary_key="course_code",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No non-owned courses found.",
                    ),
                ),
                confirmation_dialog(
                    is_open=NonOwnedCourseConfigState.confirm_open,
                    title=NonOwnedCourseConfigState.confirm_title,
                    body=NonOwnedCourseConfigState.confirm_body,
                    on_confirm=NonOwnedCourseConfigState.soft_delete_course,
                    on_cancel=NonOwnedCourseConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                align="start",
                width="100%",
            ),
            container="lg",
        )
    )
