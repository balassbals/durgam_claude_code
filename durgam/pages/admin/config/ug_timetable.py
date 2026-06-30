"""UG timetable management page — /admin/config/ug-timetable."""

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
from durgam.pages.shared.faculty_picker import faculty_picker
from durgam.states.config_ug_timetable import UGTimetableConfigState


def _kebab(row: dict) -> rx.Component:
    return rx.cond(
        UGTimetableConfigState.ay_is_locked,
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
                    on_click=UGTimetableConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                        row["id"]
                    ),
                ),
                rx.menu.item(
                    "Deactivate",
                    on_click=UGTimetableConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
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
                    UGTimetableConfigState.ay_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=UGTimetableConfigState.selected_ay_id,
            on_change=UGTimetableConfigState.on_ay_change,
            width="200px",
        ),
        rx.cond(
            UGTimetableConfigState.ay_is_locked,
            rx.badge("AY Locked", color_scheme="red", variant="soft"),
            rx.fragment(),
        ),
        align="center",
        gap="0.75rem",
    )


def _semester_selector() -> rx.Component:
    return rx.hstack(
        rx.text("Semester:", font_size="0.85rem", color="var(--color-muted)"),
        rx.select.root(
            rx.select.trigger(placeholder="Select semester"),
            rx.select.content(
                rx.select.item("Odd", value="odd"),
                rx.select.item("Even", value="even"),
            ),
            value=UGTimetableConfigState.selected_semester,
            on_change=UGTimetableConfigState.on_semester_change,
            width="120px",
        ),
        align="center",
        gap="0.75rem",
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    UGTimetableConfigState.editing_id == "",
                    "New Timetable Slot",
                    "Edit Timetable Slot",
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
                        value=UGTimetableConfigState.editing_id,
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text("Year *", font_size="0.85rem", color="var(--color-muted)"),
                            rx.select.root(
                                rx.select.trigger(placeholder="Year"),
                                rx.select.content(
                                    rx.select.item("1st Year", value="1"),
                                    rx.select.item("2nd Year", value="2"),
                                ),
                                name="form_year_of_study",
                                value=UGTimetableConfigState.form_year_of_study,
                                on_change=UGTimetableConfigState.set_form_year_of_study,
                                width="100%",
                            ),
                            align="start", gap="0.25rem", flex="1",
                        ),
                        rx.vstack(
                            rx.text("Day *", font_size="0.85rem", color="var(--color-muted)"),
                            rx.select.root(
                                rx.select.trigger(placeholder="Day"),
                                rx.select.content(
                                    rx.select.item("Monday", value="1"),
                                    rx.select.item("Tuesday", value="2"),
                                    rx.select.item("Wednesday", value="3"),
                                    rx.select.item("Thursday", value="4"),
                                    rx.select.item("Friday", value="5"),
                                    rx.select.item("Saturday", value="6"),
                                ),
                                name="form_day_of_week",
                                value=UGTimetableConfigState.form_day_of_week,
                                on_change=UGTimetableConfigState.set_form_day_of_week,
                                width="100%",
                            ),
                            align="start", gap="0.25rem", flex="1",
                        ),
                        rx.vstack(
                            rx.text("Period *", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(
                                name="form_period_number",
                                type="number",
                                value=UGTimetableConfigState.form_period_number,
                                on_change=UGTimetableConfigState.set_form_period_number,
                                placeholder="1",
                                min_="1",
                                width="100%",
                            ),
                            align="start", gap="0.25rem", flex="1",
                        ),
                        gap="0.75rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Course Code *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_course_code",
                            value=UGTimetableConfigState.form_course_code,
                            on_change=UGTimetableConfigState.set_form_course_code,
                            placeholder="e.g. PHY101",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Course Name *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_course_name",
                            value=UGTimetableConfigState.form_course_name,
                            on_change=UGTimetableConfigState.set_form_course_name,
                            placeholder="e.g. General Physics",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    faculty_picker(
                        selected_label=UGTimetableConfigState.form_faculty_label,
                        search_value=UGTimetableConfigState.picker_search,
                        results=UGTimetableConfigState.picker_results,
                        on_search=UGTimetableConfigState.on_picker_search,
                        on_select=UGTimetableConfigState.select_faculty,
                        on_clear=UGTimetableConfigState.clear_faculty,
                    ),
                    rx.vstack(
                        rx.text("Room", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_room",
                            value=UGTimetableConfigState.form_room,
                            on_change=UGTimetableConfigState.set_form_room,
                            placeholder="e.g. LH-1",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Notes", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(
                            name="form_notes",
                            value=UGTimetableConfigState.form_notes,
                            on_change=UGTimetableConfigState.set_form_notes,
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
                            on_click=UGTimetableConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=UGTimetableConfigState.save_slot,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=UGTimetableConfigState.show_form,
    )


def admin_config_ug_timetable() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "UG Timetable",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    rx.cond(
                        UGTimetableConfigState.ay_is_locked,
                        rx.fragment(),
                        primary_btn(
                            "+ Add Slot",
                            on_click=UGTimetableConfigState.open_create,
                        ),
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1rem",
                ),
                rx.hstack(
                    _ay_selector(),
                    _semester_selector(),
                    gap="1.5rem",
                    flex_wrap="wrap",
                ),
                rx.box(height="1rem"),
                config_toast(
                    UGTimetableConfigState.flash,
                    UGTimetableConfigState.flash_type,
                    UGTimetableConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    UGTimetableConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=UGTimetableConfigState.slots,
                        columns=[
                            TableColumn(key="year_of_study", label="Year"),
                            TableColumn(key="day_label", label="Day"),
                            TableColumn(key="period_number", label="Period"),
                            TableColumn(key="course_code", label="Code"),
                            TableColumn(key="course_name", label="Course"),
                            TableColumn(key="faculty", label="Faculty"),
                            TableColumn(key="room", label="Room"),
                        ],
                        card_primary_key="course_code",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No timetable slots found.",
                    ),
                ),
                confirmation_dialog(
                    is_open=UGTimetableConfigState.confirm_open,
                    title=UGTimetableConfigState.confirm_title,
                    body=UGTimetableConfigState.confirm_body,
                    on_confirm=UGTimetableConfigState.soft_delete_slot,
                    on_cancel=UGTimetableConfigState.cancel_confirm,
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
