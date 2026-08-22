"""Campus management page — /admin/config/campuses."""

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
from durgam.states.config_campus import CampusConfigState


def _kebab(row: dict) -> rx.Component:
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
            rx.menu.item(
                "Edit",
                on_click=CampusConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["code"], row["name"], row["address"]
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=CampusConfigState.open_soft_delete_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["name"]
                ),
                color="var(--color-danger, #c0392b)",
            ),
        ),
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(CampusConfigState.editing_id == "", "New Campus", "Edit Campus"),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.input(
                        type="hidden",
                        name="editing_id",
                        value=CampusConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Code", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_code",
                            value=CampusConfigState.form_code,
                            on_change=CampusConfigState.set_form_code,
                            placeholder="e.g. PSN",
                            disabled=CampusConfigState.editing_id != "",
                            max_length=10,
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
                            value=CampusConfigState.form_name,
                            on_change=CampusConfigState.set_form_name,
                            placeholder="Campus name",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Address (optional)",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                        ),
                        rx.input(
                            name="form_address",
                            value=CampusConfigState.form_address,
                            on_change=CampusConfigState.set_form_address,
                            placeholder="Full address",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel", on_click=CampusConfigState.cancel_form, type="button"
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=CampusConfigState.save_campus,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=CampusConfigState.show_form,
    )


def admin_config_campuses() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        "Campuses",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    primary_btn("+ New Campus", on_click=CampusConfigState.open_create),
                    align="center",
                    width="100%",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    CampusConfigState.flash,
                    CampusConfigState.flash_type,
                    CampusConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    CampusConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=CampusConfigState.campuses,
                        columns=[
                            TableColumn(key="code", label="Code"),
                            TableColumn(key="name", label="Name"),
                            TableColumn(key="address", label="Address", hidden_on_card=True),
                        ],
                        card_primary_key="name",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No campuses found.",
                    ),
                ),
                confirmation_dialog(
                    is_open=CampusConfigState.confirm_open,
                    title=CampusConfigState.confirm_title,
                    body=CampusConfigState.confirm_body,
                    on_confirm=CampusConfigState.soft_delete_campus,
                    on_cancel=CampusConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                align="start",
                width="100%",
                id="campus-page-top",
            ),
            container="lg",
        )
    )
