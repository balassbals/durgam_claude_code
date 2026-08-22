"""Holiday management page — /admin/config/holidays."""

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
from durgam.states.config_holiday import HolidayConfigState


def _kebab(row: dict) -> rx.Component:
    return rx.cond(
        HolidayConfigState.ay_is_locked,
        rx.text("🔒", font_size="0.8rem", color="var(--color-muted)"),
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
                    on_click=HolidayConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["date"], row["name"]
                    ),
                ),
                rx.menu.item(
                    "Delete",
                    on_click=HolidayConfigState.open_soft_delete_confirm(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["name"]
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
                    HolidayConfigState.ay_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=HolidayConfigState.selected_ay_id,
            on_change=HolidayConfigState.on_ay_change,
            width="200px",
        ),
        rx.cond(
            HolidayConfigState.ay_is_locked,
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
                    HolidayConfigState.editing_id == "",
                    "New Holiday",
                    "Edit Holiday",
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
                        value=HolidayConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Date", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            type="date",
                            name="form_date",
                            value=HolidayConfigState.form_date,
                            on_change=HolidayConfigState.set_form_date,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Name", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_name",
                            value=HolidayConfigState.form_name,
                            on_change=HolidayConfigState.set_form_name,
                            placeholder="Holiday name",
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
                            on_click=HolidayConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=HolidayConfigState.save_holiday,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=HolidayConfigState.show_form,
    )


def admin_config_holidays() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        "Holidays",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    rx.cond(
                        HolidayConfigState.ay_is_locked,
                        rx.fragment(),
                        primary_btn(
                            "+ New Holiday",
                            on_click=HolidayConfigState.open_create,
                        ),
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1rem",
                ),
                _ay_selector(),
                rx.box(height="1rem"),
                config_toast(
                    HolidayConfigState.flash,
                    HolidayConfigState.flash_type,
                    HolidayConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    HolidayConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=HolidayConfigState.holidays,
                        columns=[
                            TableColumn(key="date", label="Date"),
                            TableColumn(key="name", label="Name"),
                        ],
                        card_primary_key="name",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No holidays found for this academic year.",
                    ),
                ),
                confirmation_dialog(
                    is_open=HolidayConfigState.confirm_open,
                    title=HolidayConfigState.confirm_title,
                    body=HolidayConfigState.confirm_body,
                    on_confirm=HolidayConfigState.soft_delete_holiday,
                    on_cancel=HolidayConfigState.cancel_confirm,
                    confirm_label="Delete",
                ),
                align="start",
                width="100%",
                id="holiday-page-top",
            ),
            container="lg",
        )
    )
