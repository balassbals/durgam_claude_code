"""Student Category Count page — /admin/config/student-categories."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    app_shell,
    config_toast,
    primary_btn,
)
from durgam.states.config_student_category import StudentCategoryConfigState


def _ay_selector() -> rx.Component:
    return rx.hstack(
        rx.text("Academic Year:", font_size="0.85rem", color="var(--color-muted)"),
        rx.select.root(
            rx.select.trigger(placeholder="Select academic year"),
            rx.select.content(
                rx.foreach(
                    StudentCategoryConfigState.ay_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=StudentCategoryConfigState.selected_ay_id,
            on_change=StudentCategoryConfigState.on_ay_change,
            width="200px",
        ),
        rx.cond(
            StudentCategoryConfigState.ay_is_locked,
            rx.badge("AY Locked", color_scheme="red", variant="soft"),
            rx.fragment(),
        ),
        align="center",
        gap="0.75rem",
    )


def _count_field(label: str, name: str, value: rx.Var, on_change, disabled: rx.Var) -> rx.Component:
    return rx.vstack(
        rx.text(label, font_size="0.85rem", color="var(--color-muted)"),
        rx.input(
            type="number",
            name=name,
            value=value,
            on_change=on_change,
            min="0",
            width="100%",
            disabled=disabled,
        ),
        align="start",
        gap="0.25rem",
        width="100%",
    )


def _form() -> rx.Component:
    disabled = StudentCategoryConfigState.ay_is_locked
    return rx.form(
        rx.vstack(
            rx.hstack(
                _count_field(
                    "SC Count",
                    "sc_count",
                    StudentCategoryConfigState.sc_count,
                    StudentCategoryConfigState.set_sc_count,
                    disabled,
                ),
                _count_field(
                    "ST Count",
                    "st_count",
                    StudentCategoryConfigState.st_count,
                    StudentCategoryConfigState.set_st_count,
                    disabled,
                ),
                _count_field(
                    "OBC Count",
                    "obc_count",
                    StudentCategoryConfigState.obc_count,
                    StudentCategoryConfigState.set_obc_count,
                    disabled,
                ),
                gap="1rem",
                width="100%",
                flex_wrap="wrap",
            ),
            rx.hstack(
                _count_field(
                    "EWS Count",
                    "ews_count",
                    StudentCategoryConfigState.ews_count,
                    StudentCategoryConfigState.set_ews_count,
                    disabled,
                ),
                _count_field(
                    "General Count",
                    "general_count",
                    StudentCategoryConfigState.general_count,
                    StudentCategoryConfigState.set_general_count,
                    disabled,
                ),
                gap="1rem",
                width="100%",
                flex_wrap="wrap",
            ),
            rx.vstack(
                rx.text("Notes (optional)", font_size="0.85rem", color="var(--color-muted)"),
                rx.text_area(
                    name="notes",
                    value=StudentCategoryConfigState.notes,
                    on_change=StudentCategoryConfigState.set_notes,
                    placeholder="Additional notes",
                    width="100%",
                    rows="3",
                    disabled=disabled,
                ),
                align="start",
                gap="0.25rem",
                width="100%",
            ),
            rx.cond(
                disabled,
                rx.text(
                    "This academic year is locked. Edits are not permitted.",
                    color="var(--color-danger, #c0392b)",
                    font_size="0.85rem",
                ),
                primary_btn("Save", type="submit"),
            ),
            gap="1rem",
            align="start",
            width="100%",
        ),
        on_submit=StudentCategoryConfigState.save_student_categories,
        reset_on_submit=False,
    )


def admin_config_student_categories() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.heading(
                    "Student Category Counts",
                    size="5",
                    font_family="var(--font-sans)",
                    margin_bottom="1rem",
                ),
                _ay_selector(),
                rx.box(height="1rem"),
                config_toast(
                    StudentCategoryConfigState.flash,
                    StudentCategoryConfigState.flash_type,
                    StudentCategoryConfigState.dismiss_flash,
                ),
                rx.cond(
                    StudentCategoryConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    _form(),
                ),
                align="start",
                width="100%",
                id="scc-page-top",
            ),
            container="md",
        )
    )
