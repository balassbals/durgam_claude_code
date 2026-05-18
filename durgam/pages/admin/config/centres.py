"""Centre of Excellence management page — /admin/config/centres."""

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
                    row["id"], row["code"], row["name"], row["campus_id"]
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


def _campus_option(campus: dict) -> rx.Component:
    return rx.option(campus["name"], value=campus["id"])


def _inline_form() -> rx.Component:
    return rx.cond(
        CentreConfigState.show_form,
        rx.box(
            rx.heading(
                rx.cond(CentreConfigState.editing_id == "", "New Centre", "Edit Centre"),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.vstack(
                rx.vstack(
                    rx.text("Code", font_size="0.85rem", color="var(--color-muted)"),
                    rx.input(
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
                        rx.foreach(CentreConfigState.campus_options, _campus_option),
                        value=CentreConfigState.form_campus_id,
                        on_change=CentreConfigState.set_form_campus_id,
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                rx.hstack(
                    primary_btn("Save", on_click=CentreConfigState.save_centre),
                    secondary_btn("Cancel", on_click=CentreConfigState.cancel_form),
                    gap="0.75rem",
                ),
                gap="1rem",
                align="start",
                width="100%",
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


def admin_config_centres() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
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
                typed_flash(CentreConfigState.flash, CentreConfigState.flash_type),
                _inline_form(),
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
                confirmation_dialog(
                    is_open=CentreConfigState.confirm_open,
                    title=CentreConfigState.confirm_title,
                    body=CentreConfigState.confirm_body,
                    on_confirm=CentreConfigState.soft_delete_centre,
                    on_cancel=CentreConfigState.cancel_confirm,
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
