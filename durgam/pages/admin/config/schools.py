"""School management page — /admin/config/schools."""

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
from durgam.states.config_school import SchoolConfigState


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
                on_click=SchoolConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["code"], row["name"]
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=SchoolConfigState.open_soft_delete_confirm(  # type: ignore[call-arg, func-returns-value]
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
                rx.cond(SchoolConfigState.editing_id == "", "New School", "Edit School"),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.input(
                        type="hidden",
                        name="editing_id",
                        value=SchoolConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Code", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_code",
                            value=SchoolConfigState.form_code,
                            on_change=SchoolConfigState.set_form_code,
                            placeholder="e.g. SCI",
                            disabled=SchoolConfigState.editing_id != "",
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
                            value=SchoolConfigState.form_name,
                            on_change=SchoolConfigState.set_form_name,
                            placeholder="Full school name",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel", on_click=SchoolConfigState.cancel_form, type="button"
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=SchoolConfigState.save_school,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=SchoolConfigState.show_form,
    )


def admin_config_schools() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.heading("Schools", size="5", font_family="var(--font-sans)"),
                    rx.spacer(),
                    primary_btn("+ New School", on_click=SchoolConfigState.open_create),
                    align="center",
                    width="100%",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    SchoolConfigState.flash,
                    SchoolConfigState.flash_type,
                    SchoolConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    SchoolConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=SchoolConfigState.schools,
                        columns=[
                            TableColumn(key="code", label="Code"),
                            TableColumn(key="name", label="Name"),
                        ],
                        card_primary_key="name",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No schools found.",
                    ),
                ),
                confirmation_dialog(
                    is_open=SchoolConfigState.confirm_open,
                    title=SchoolConfigState.confirm_title,
                    body=SchoolConfigState.confirm_body,
                    on_confirm=SchoolConfigState.soft_delete_school,
                    on_cancel=SchoolConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                align="start",
                width="100%",
                id="school-page-top",
            ),
            container="lg",
        )
    )
