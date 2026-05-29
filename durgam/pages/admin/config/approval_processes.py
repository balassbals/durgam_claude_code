"""Approval processes management page — /admin/config/approval-processes."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    config_toast,
    form_modal,
    nav_shell,
    page_footer,
    primary_btn,
    role_multi_select,
    role_multi_select_ordered,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.config_approval_process import ApprovalProcessConfigState


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
                on_click=ApprovalProcessConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["code"], row["title"],
                    row["raw_requestors"], row["raw_channel"],
                    row["raw_finance"], row["raw_cc"],
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=ApprovalProcessConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["code"],
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
                    ApprovalProcessConfigState.editing_id == "",
                    "New Approval Process",
                    "Edit Approval Process",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.input(type="hidden", name="editing_id",
                             value=ApprovalProcessConfigState.editing_id),
                    rx.vstack(
                        rx.text("Code *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(name="form_code",
                                 value=ApprovalProcessConfigState.form_code,
                                 on_change=ApprovalProcessConfigState.set_form_code,
                                 placeholder="e.g. CPC_FUND_RELEASE",
                                 width="100%"),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Title *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(name="form_title",
                                 value=ApprovalProcessConfigState.form_title,
                                 on_change=ApprovalProcessConfigState.set_form_title,
                                 placeholder="e.g. Central Purchase Committee Fund Release",
                                 width="100%"),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Requestor Roles", font_size="0.85rem", color="var(--color-muted)"),
                        role_multi_select(
                            options=ApprovalProcessConfigState.role_options,
                            selected_codes=ApprovalProcessConfigState.form_requestors_selected,
                            toggle_handler=ApprovalProcessConfigState.toggle_requestor,
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Channel Roles (ordered)", font_size="0.85rem", color="var(--color-muted)"),
                        role_multi_select_ordered(
                            options=ApprovalProcessConfigState.role_options,
                            selected_codes=ApprovalProcessConfigState.form_channel_selected,
                            toggle_handler=ApprovalProcessConfigState.toggle_channel,
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Informational CC Roles", font_size="0.85rem", color="var(--color-muted)"),
                        role_multi_select(
                            options=ApprovalProcessConfigState.role_options,
                            selected_codes=ApprovalProcessConfigState.form_cc_selected,
                            toggle_handler=ApprovalProcessConfigState.toggle_cc,
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.checkbox(
                        "Finance process",
                        checked=ApprovalProcessConfigState.form_is_finance,
                        on_change=ApprovalProcessConfigState.set_form_is_finance,
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn("Cancel",
                                      on_click=ApprovalProcessConfigState.cancel_form,
                                      type="button"),
                        gap="0.75rem",
                    ),
                    gap="1rem", align="start", width="100%",
                ),
                on_submit=ApprovalProcessConfigState.save_process,
                reset_on_submit=False,
            ),
            gap="0", align="start", width="100%",
        ),
        is_open=ApprovalProcessConfigState.show_form,
    )


def admin_config_approval_processes() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading("Approval Processes", size="5",
                               font_family="var(--font-sans)"),
                    rx.spacer(),
                    primary_btn("+ Add Process",
                                on_click=ApprovalProcessConfigState.open_create),
                    align="center", width="100%", margin_bottom="1rem",
                ),
                config_toast(
                    ApprovalProcessConfigState.flash,
                    ApprovalProcessConfigState.flash_type,
                    ApprovalProcessConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    ApprovalProcessConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=ApprovalProcessConfigState.processes,
                        columns=[
                            TableColumn(key="code", label="Code"),
                            TableColumn(key="title", label="Title"),
                            TableColumn(key="finance", label="Finance request?"),
                            TableColumn(key="requestors", label="Requestors"),
                            TableColumn(key="channel", label="Channel"),
                            TableColumn(key="cc", label="CC"),
                        ],
                        card_primary_key="code",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No approval processes configured.",
                    ),
                ),
                confirmation_dialog(
                    is_open=ApprovalProcessConfigState.confirm_open,
                    title=ApprovalProcessConfigState.confirm_title,
                    body=ApprovalProcessConfigState.confirm_body,
                    on_confirm=ApprovalProcessConfigState.soft_delete_process,
                    on_cancel=ApprovalProcessConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                padding="2rem", max_width="1200px", width="100%",
            ),
            page_footer(),
            align="start", width="100%", min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
