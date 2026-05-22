"""Academic Year management page — /admin/config/academic-years."""

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
from durgam.states.config_academic_year import AcademicYearConfigState


def _kebab(row: dict) -> rx.Component:
    is_locked = row["is_locked"] == "Yes"
    master_locked = row["master_locked"] == "Yes"
    return rx.menu.root(
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
            rx.cond(
                is_locked,
                rx.menu.item("Locked — no actions", disabled=True),
                rx.fragment(
                    rx.menu.item(
                        "Edit",
                        on_click=AcademicYearConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                            row["id"], row["code"], row["starts_on"], row["ends_on"]
                        ),
                    ),
                    rx.cond(
                        master_locked,
                        rx.fragment(),
                        rx.menu.item(
                            "Lock Master Calendar",
                            on_click=AcademicYearConfigState.open_lock_master_confirm(  # type: ignore[call-arg, func-returns-value]
                                row["id"], row["code"]
                            ),
                        ),
                    ),
                    rx.menu.item(
                        "Deactivate",
                        on_click=AcademicYearConfigState.open_soft_delete_confirm(  # type: ignore[call-arg, func-returns-value]
                            row["id"], row["code"]
                        ),
                        color="var(--color-danger, #c0392b)",
                    ),
                ),
            ),
        ),
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    AcademicYearConfigState.editing_id == "",
                    "New Academic Year",
                    "Edit Academic Year",
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
                        value=AcademicYearConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Code", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_code",
                            value=AcademicYearConfigState.form_code,
                            on_change=AcademicYearConfigState.set_form_code,
                            placeholder="e.g. 2025-26",
                            disabled=AcademicYearConfigState.editing_id != "",
                            max_length=10,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Start Date", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            type="date",
                            name="form_starts_on",
                            value=AcademicYearConfigState.form_starts_on,
                            on_change=AcademicYearConfigState.set_form_starts_on,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("End Date", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            type="date",
                            name="form_ends_on",
                            value=AcademicYearConfigState.form_ends_on,
                            on_change=AcademicYearConfigState.set_form_ends_on,
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
                            on_click=AcademicYearConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=AcademicYearConfigState.save_academic_year,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=AcademicYearConfigState.show_form,
    )


def admin_config_academic_years() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "Academic Years",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    primary_btn(
                        "+ New Academic Year",
                        on_click=AcademicYearConfigState.open_create,
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="0.5rem",
                ),
                rx.text(
                    "Year Locked: set automatically when the year ends; "
                    "no edits allowed. "
                    "Master Calendar: set by Registrar to finalize the "
                    "calendar framework; other roles can then add entries.",
                    font_size="0.8rem",
                    color="var(--color-muted)",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    AcademicYearConfigState.flash,
                    AcademicYearConfigState.flash_type,
                    AcademicYearConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    AcademicYearConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=AcademicYearConfigState.academic_years,
                        columns=[
                            TableColumn(key="code", label="Code"),
                            TableColumn(key="starts_on", label="Start"),
                            TableColumn(key="ends_on", label="End"),
                            TableColumn(key="is_locked", label="Year Locked"),
                            TableColumn(key="master_locked", label="Master Calendar"),
                        ],
                        card_primary_key="code",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No academic years found.",
                    ),
                ),
                confirmation_dialog(
                    is_open=AcademicYearConfigState.confirm_open,
                    title=AcademicYearConfigState.confirm_title,
                    body=AcademicYearConfigState.confirm_body,
                    on_confirm=AcademicYearConfigState.confirm_action_handler,
                    on_cancel=AcademicYearConfigState.cancel_confirm,
                    confirm_label=rx.cond(
                        AcademicYearConfigState.confirm_action == "lock_master",
                        "Lock",
                        "Deactivate",
                    ),
                ),
                padding="2rem",
                max_width="1200px",
                width="100%",
                id="ay-page-top",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
