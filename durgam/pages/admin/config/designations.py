"""Designations management page — /admin/config/designations."""

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
from durgam.states.config_designation import DesignationConfigState


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
                on_click=DesignationConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"],
                    row["code"],
                    row["name"],
                    row["rank"],
                    row["notes"],
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=DesignationConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"],
                    row["code"],
                ),
                color="var(--color-danger, #c0392b)",
            ),
        ),
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    DesignationConfigState.editing_id == "",
                    "New Designation",
                    "Edit Designation",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.input(
                        type="hidden", name="editing_id", value=DesignationConfigState.editing_id
                    ),
                    rx.vstack(
                        rx.text("Code *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_code",
                            value=DesignationConfigState.form_code,
                            on_change=DesignationConfigState.set_form_code,
                            placeholder="e.g. senior_professor",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Name *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_name",
                            value=DesignationConfigState.form_name,
                            on_change=DesignationConfigState.set_form_name,
                            placeholder="e.g. Senior Professor",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Rank *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_rank",
                            type="number",
                            value=DesignationConfigState.form_rank,
                            on_change=DesignationConfigState.set_form_rank,
                            placeholder="1 = highest",
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
                            value=DesignationConfigState.form_notes,
                            on_change=DesignationConfigState.set_form_notes,
                            placeholder="Optional notes",
                            width="100%",
                            rows="2",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel", on_click=DesignationConfigState.cancel_form, type="button"
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=DesignationConfigState.save_designation,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=DesignationConfigState.show_form,
    )


def admin_config_designations() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.heading("Designations", size="5", font_family="var(--font-sans)"),
                    rx.spacer(),
                    primary_btn("+ Add Designation", on_click=DesignationConfigState.open_create),
                    align="center",
                    width="100%",
                    margin_bottom="1rem",
                ),
                config_toast(
                    DesignationConfigState.flash,
                    DesignationConfigState.flash_type,
                    DesignationConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    DesignationConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=DesignationConfigState.designations,
                        columns=[
                            TableColumn(key="code", label="Code"),
                            TableColumn(key="name", label="Name"),
                            TableColumn(key="rank", label="Rank"),
                            TableColumn(key="notes", label="Notes"),
                        ],
                        card_primary_key="code",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No designations configured.",
                    ),
                ),
                confirmation_dialog(
                    is_open=DesignationConfigState.confirm_open,
                    title=DesignationConfigState.confirm_title,
                    body=DesignationConfigState.confirm_body,
                    on_confirm=DesignationConfigState.soft_delete_designation,
                    on_cancel=DesignationConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                align="start",
                width="100%",
            ),
            container="lg",
        )
    )
