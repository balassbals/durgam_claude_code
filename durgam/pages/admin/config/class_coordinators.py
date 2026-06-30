"""Class coordinator assignment management page — /admin/config/class-coordinators."""

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
from durgam.states.config_class_coordinator import ClassCoordinatorConfigState


def _kebab(row: dict) -> rx.Component:
    return rx.cond(
        ClassCoordinatorConfigState.ay_is_locked,
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
                    on_click=ClassCoordinatorConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                        row["id"]
                    ),
                ),
                rx.menu.item(
                    "Deactivate",
                    on_click=ClassCoordinatorConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
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
                    ClassCoordinatorConfigState.ay_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=ClassCoordinatorConfigState.selected_ay_id,
            on_change=ClassCoordinatorConfigState.on_ay_change,
            width="200px",
        ),
        rx.cond(
            ClassCoordinatorConfigState.ay_is_locked,
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
            ClassCoordinatorConfigState.dept_locked,
            rx.text(ClassCoordinatorConfigState.dept_name_display,
                    font_weight="600", font_size="0.9rem"),
            rx.select.root(
                rx.select.trigger(placeholder="Select department"),
                rx.select.content(
                    rx.foreach(
                        ClassCoordinatorConfigState.dept_options,
                        lambda o: rx.select.item(o["label"], value=o["value"]),
                    ),
                ),
                value=ClassCoordinatorConfigState.selected_dept_id,
                on_change=ClassCoordinatorConfigState.on_dept_change,
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
                    ClassCoordinatorConfigState.editing_id == "",
                    "New Class Coordinator",
                    "Edit Class Coordinator",
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
                        value=ClassCoordinatorConfigState.editing_id,
                    ),
                    faculty_picker(
                        selected_label=ClassCoordinatorConfigState.form_faculty_label,
                        search_value=ClassCoordinatorConfigState.picker_search,
                        results=ClassCoordinatorConfigState.picker_results,
                        on_search=ClassCoordinatorConfigState.on_picker_search,
                        on_select=ClassCoordinatorConfigState.select_faculty,
                        on_clear=ClassCoordinatorConfigState.clear_faculty,
                    ),
                    rx.vstack(
                        rx.text("Class *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_class",
                            value=ClassCoordinatorConfigState.form_class,
                            on_change=ClassCoordinatorConfigState.set_form_class,
                            placeholder="e.g. BSc-II-A",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Notes", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(
                            name="form_notes",
                            value=ClassCoordinatorConfigState.form_notes,
                            on_change=ClassCoordinatorConfigState.set_form_notes,
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
                            on_click=ClassCoordinatorConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=ClassCoordinatorConfigState.save_coordinator,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=ClassCoordinatorConfigState.show_form,
    )


def admin_config_class_coordinators() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "Class Coordinator Assignments",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    rx.cond(
                        ClassCoordinatorConfigState.ay_is_locked,
                        rx.fragment(),
                        primary_btn(
                            "+ Add Assignment",
                            on_click=ClassCoordinatorConfigState.open_create,
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
                    ClassCoordinatorConfigState.flash,
                    ClassCoordinatorConfigState.flash_type,
                    ClassCoordinatorConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    ClassCoordinatorConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=ClassCoordinatorConfigState.coordinators,
                        columns=[
                            TableColumn(key="faculty", label="Student"),
                            TableColumn(key="class", label="Class"),
                            TableColumn(key="notes", label="Notes"),
                        ],
                        card_primary_key="faculty",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No class coordinator assignments found.",
                    ),
                ),
                confirmation_dialog(
                    is_open=ClassCoordinatorConfigState.confirm_open,
                    title=ClassCoordinatorConfigState.confirm_title,
                    body=ClassCoordinatorConfigState.confirm_body,
                    on_confirm=ClassCoordinatorConfigState.soft_delete_coordinator,
                    on_cancel=ClassCoordinatorConfigState.cancel_confirm,
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
