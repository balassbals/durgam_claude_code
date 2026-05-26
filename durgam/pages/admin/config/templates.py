"""Template management page — /admin/config/templates."""

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
from durgam.states.config_document_template import TemplateConfigState

_TYPE_OPTIONS = ["bos", "mom", "vac"]

_ACCEPT_MAP = {
    "bos": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    },
    "mom": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    },
    "vac": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
    },
}


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
                "Deactivate",
                on_click=TemplateConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["template_type"]
                ),
                color="var(--color-danger, #c0392b)",
            ),
        ),
    )


_TPL_UPLOAD_ID = "template_upload"


def _upload_zone() -> rx.Component:
    """Upload zone that adapts accept filter based on selected template type."""
    return rx.cond(
        TemplateConfigState.form_template_type == "vac",
        file_upload_zone(
            upload_id=_TPL_UPLOAD_ID,
            accept=_ACCEPT_MAP["vac"],
            label="Drag & drop a PPTX file (≤ 2 MB)",
        ),
        file_upload_zone(
            upload_id=_TPL_UPLOAD_ID,
            accept=_ACCEPT_MAP["bos"],
            label="Drag & drop a DOCX file (≤ 2 MB)",
        ),
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                "Upload Template",
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.vstack(
                rx.vstack(
                    rx.text(
                        "Template Type",
                        font_size="0.85rem",
                        color="var(--color-muted)",
                    ),
                    rx.select.root(
                        rx.select.trigger(placeholder="Select type"),
                        rx.select.content(
                            *[
                                rx.select.item(t.upper(), value=t)
                                for t in _TYPE_OPTIONS
                            ],
                        ),
                        value=TemplateConfigState.form_template_type,
                        on_change=TemplateConfigState.set_form_template_type,
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                rx.cond(
                    TemplateConfigState.form_template_type != "",
                    rx.vstack(
                        _upload_zone(),
                        rx.cond(
                            rx.selected_files(_TPL_UPLOAD_ID).length() > 0,
                            rx.hstack(
                                rx.text(
                                    rx.selected_files(_TPL_UPLOAD_ID)[0],
                                    font_size="0.85rem",
                                    color="var(--color-body)",
                                ),
                                rx.button(
                                    "✕",
                                    on_click=rx.clear_selected_files(_TPL_UPLOAD_ID),
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
                            "Select a template type to enable upload",
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
                        on_click=TemplateConfigState.upload_template(  # type: ignore[call-arg]
                            rx.upload_files(upload_id=_TPL_UPLOAD_ID),
                        ),
                        type="button",
                    ),
                    secondary_btn(
                        "Cancel",
                        on_click=[
                            rx.clear_selected_files(_TPL_UPLOAD_ID),
                            TemplateConfigState.cancel_form,
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
        is_open=TemplateConfigState.show_form,
    )


def admin_config_templates() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "Templates",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    primary_btn(
                        "+ Upload Template",
                        on_click=TemplateConfigState.open_upload,
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    TemplateConfigState.flash,
                    TemplateConfigState.flash_type,
                    TemplateConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    TemplateConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=TemplateConfigState.templates,
                        columns=[
                            TableColumn(key="template_type", label="Type"),
                        ],
                        card_primary_key="template_type",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No templates uploaded.",
                    ),
                ),
                confirmation_dialog(
                    is_open=TemplateConfigState.confirm_open,
                    title=TemplateConfigState.confirm_title,
                    body=TemplateConfigState.confirm_body,
                    on_confirm=TemplateConfigState.soft_delete_template,
                    on_cancel=TemplateConfigState.cancel_confirm,
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
