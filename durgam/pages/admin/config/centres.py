"""Centre of Excellence management page — /admin/config/centres."""

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
from durgam.states.config_centre import CentreConfigState


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
                on_click=CentreConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["code"], row["name"], row["campus_code"]
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=CentreConfigState.open_soft_delete_confirm(  # type: ignore[call-arg, func-returns-value]
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
                rx.cond(CentreConfigState.editing_id == "", "New Centre", "Edit Centre"),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.input(
                        type="hidden",
                        name="editing_id",
                        value=CentreConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Code", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_code",
                            value=CentreConfigState.form_code,
                            on_change=CentreConfigState.set_form_code,
                            placeholder="e.g. CMB",
                            disabled=CentreConfigState.editing_id != "",
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
                            value=CentreConfigState.form_name,
                            on_change=CentreConfigState.set_form_name,
                            placeholder="Centre name",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Campus", font_size="0.85rem", color="var(--color-muted)"),
                        rx.select(
                            CentreConfigState.campus_codes,
                            value=CentreConfigState.form_campus_code,
                            on_change=CentreConfigState.set_form_campus_code,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel", on_click=CentreConfigState.cancel_form, type="button"
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=CentreConfigState.save_centre,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=CentreConfigState.show_form,
    )


def admin_config_centres() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        "Centres of Excellence",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    primary_btn("+ New Centre", on_click=CentreConfigState.open_create),
                    align="center",
                    width="100%",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    CentreConfigState.flash,
                    CentreConfigState.flash_type,
                    CentreConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    CentreConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=CentreConfigState.centres,
                        columns=[
                            TableColumn(key="code", label="Code"),
                            TableColumn(key="name", label="Name"),
                            TableColumn(key="campus", label="Campus"),
                        ],
                        card_primary_key="name",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No centres found.",
                    ),
                ),
                confirmation_dialog(
                    is_open=CentreConfigState.confirm_open,
                    title=CentreConfigState.confirm_title,
                    body=CentreConfigState.confirm_body,
                    on_confirm=CentreConfigState.soft_delete_centre,
                    on_cancel=CentreConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                align="start",
                width="100%",
                id="centre-page-top",
            ),
            container="lg",
        )
    )
