"""Letterhead management page — /admin/config/letterheads."""

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
from durgam.pages.shared.file_upload import file_upload_zone
from durgam.states.config_letterhead import LetterheadConfigState


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
                "Download",
                on_click=rx.redirect(
                    rx.cond(
                        row["file_id"] != "",
                        "/api/files/" + row["file_id"],
                        "#",
                    )
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=LetterheadConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["role_code"]
                ),
                color="var(--color-danger, #c0392b)",
            ),
        ),
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                "Upload Letterhead",
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.vstack(
                rx.vstack(
                    rx.text("Role Code", font_size="0.85rem", color="var(--color-muted)"),
                    rx.input(
                        value=LetterheadConfigState.form_role_code,
                        on_change=LetterheadConfigState.set_form_role_code,
                        placeholder="e.g. REGISTRAR",
                        max_length=64,
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                rx.vstack(
                    rx.text(
                        "Scope Type (optional)",
                        font_size="0.85rem",
                        color="var(--color-muted)",
                    ),
                    rx.input(
                        value=LetterheadConfigState.form_scope_type,
                        on_change=LetterheadConfigState.set_form_scope_type,
                        placeholder="e.g. department",
                        max_length=32,
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                rx.vstack(
                    rx.text(
                        "Scope ID (optional)",
                        font_size="0.85rem",
                        color="var(--color-muted)",
                    ),
                    rx.input(
                        value=LetterheadConfigState.form_scope_id,
                        on_change=LetterheadConfigState.set_form_scope_id,
                        placeholder="UUID of the scope entity",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                file_upload_zone(
                    on_drop=LetterheadConfigState.upload_letterhead,  # type: ignore[arg-type]
                    accept={
                        "image/png": [".png"],
                        "image/jpeg": [".jpg", ".jpeg"],
                        "application/pdf": [".pdf"],
                    },
                    label="Drag & drop a letterhead image (PNG, JPG, PDF ≤ 5 MB)",
                ),
                rx.hstack(
                    secondary_btn(
                        "Cancel",
                        on_click=LetterheadConfigState.cancel_form,
                        type="button",
                    ),
                    gap="0.75rem",
                ),
                gap="1rem",
                align="start",
                width="100%",
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=LetterheadConfigState.show_form,
    )


def admin_config_letterheads() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "Letterheads",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    primary_btn(
                        "+ Upload Letterhead",
                        on_click=LetterheadConfigState.open_upload,
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    LetterheadConfigState.flash,
                    LetterheadConfigState.flash_type,
                    LetterheadConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    LetterheadConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=LetterheadConfigState.letterheads,
                        columns=[
                            TableColumn(key="role_code", label="Role Code"),
                            TableColumn(key="scope", label="Scope"),
                        ],
                        card_primary_key="role_code",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No letterheads uploaded.",
                    ),
                ),
                confirmation_dialog(
                    is_open=LetterheadConfigState.confirm_open,
                    title=LetterheadConfigState.confirm_title,
                    body=LetterheadConfigState.confirm_body,
                    on_confirm=LetterheadConfigState.soft_delete_letterhead,
                    on_cancel=LetterheadConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                padding="2rem",
                max_width="1200px",
                width="100%",
                id="letterhead-page-top",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
