"""Campus management page — /admin/config/campuses."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
    typed_flash,
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
    return rx.cond(
        CampusConfigState.show_form,
        rx.box(
            rx.heading(
                rx.cond(CampusConfigState.editing_id == "", "New Campus", "Edit Campus"),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            # rx.form collects all named inputs and sends them as form_data dict
            # to save_campus. This guarantees the handler receives current values
            # even if on_change round-trips were dropped (M3 Bug 1 fix).
            rx.form(
                rx.vstack(
                    # Hidden field carries editing_id so save_campus knows
                    # whether this is a create or edit operation.
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
                        secondary_btn("Cancel", on_click=CampusConfigState.cancel_form),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=CampusConfigState.save_campus,
                reset_on_submit=False,
            ),
            background="white",
            border="1px solid var(--color-rule)",
            border_radius="8px",
            padding="1.5rem",
            margin_bottom="1.5rem",
            width="100%",
            max_width="480px",
        ),
        rx.fragment(),
    )


def admin_config_campuses() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
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
                typed_flash(CampusConfigState.flash, CampusConfigState.flash_type),
                _inline_form(),
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
                confirmation_dialog(
                    is_open=CampusConfigState.confirm_open,
                    title=CampusConfigState.confirm_title,
                    body=CampusConfigState.confirm_body,
                    on_confirm=CampusConfigState.soft_delete_campus,
                    on_cancel=CampusConfigState.cancel_confirm,
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
