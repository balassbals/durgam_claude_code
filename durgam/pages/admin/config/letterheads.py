"""Letterhead management page — /admin/config/letterheads."""

import reflex as rx

from durgam.api import DOWNLOAD_PREFIX

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
from durgam.states.config_document_template import LetterheadConfigState


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
                        DOWNLOAD_PREFIX + "/api/files/" + row["file_id"],
                        "#",
                    )
                ),
            ),
            rx.menu.item(
                "Replace File",
                on_click=LetterheadConfigState.open_replace(  # type: ignore[call-arg, func-returns-value]
                    row["role_code"]
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


_LH_UPLOAD_ID = "letterhead_upload"


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
                    rx.text("Role *", font_size="0.85rem", color="var(--color-muted)"),
                    rx.select.root(
                        rx.select.trigger(placeholder="Select role"),
                        rx.select.content(
                            rx.foreach(
                                LetterheadConfigState.role_options,
                                lambda o: rx.select.item(o["label"], value=o["code"]),
                            ),
                        ),
                        value=LetterheadConfigState.form_role_code,
                        on_change=LetterheadConfigState.set_form_role_code,
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                rx.cond(
                    LetterheadConfigState.form_role_code != "",
                    rx.vstack(
                        file_upload_zone(
                            upload_id=_LH_UPLOAD_ID,
                            accept={
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
                            },
                            label="Drag & drop a letterhead DOCX template (≤ 5 MB)",
                        ),
                        rx.cond(
                            rx.selected_files(_LH_UPLOAD_ID).length() > 0,
                            rx.hstack(
                                rx.text(
                                    rx.selected_files(_LH_UPLOAD_ID)[0],
                                    font_size="0.85rem",
                                    color="var(--color-body)",
                                ),
                                rx.button(
                                    "✕",
                                    on_click=rx.clear_selected_files(_LH_UPLOAD_ID),
                                    background="transparent",
                                    border="none",
                                    cursor="pointer",
                                    color="var(--color-muted)",
                                    font_size="0.85rem",
                                    padding="0",
                                ),
                                align="center",
                                gap="0.5rem",
                            ),
                        ),
                        gap="0.5rem",
                        width="100%",
                    ),
                    rx.box(
                        rx.text(
                            "Enter a role code to enable upload",
                            color="var(--color-muted)",
                            font_size="0.875rem",
                            text_align="center",
                        ),
                        border="2px dashed var(--color-rule)",
                        border_radius="6px",
                        padding="2rem",
                        opacity="0.5",
                    ),
                ),
                rx.hstack(
                    primary_btn(
                        "Upload",
                        on_click=LetterheadConfigState.upload_letterhead(  # type: ignore[call-arg]
                            rx.upload_files(upload_id=_LH_UPLOAD_ID),
                        ),
                        type="button",
                    ),
                    secondary_btn(
                        "Cancel",
                        on_click=[
                            rx.clear_selected_files(_LH_UPLOAD_ID),
                            LetterheadConfigState.cancel_form,
                        ],
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
                            TableColumn(key="role_code", label="Role"),
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
