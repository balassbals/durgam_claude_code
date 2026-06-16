"""Faculty request detail page (/faculty/requests/{faculty_request_id})."""

import reflex as rx

from durgam.pages.components import (
    destructive_btn,
    flash_error,
    nav_shell,
    page_footer,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.states.auth import AuthState
from durgam.states.faculty_requests import FacultyRequestDetailState

DOWNLOAD_PREFIX = "/api/files/"


def _kv_row(label: str, value: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.text(
            label,
            font_weight="600",
            font_size="0.85rem",
            color="var(--color-muted)",
            min_width="140px",
            font_family="var(--font-sans)",
        ),
        rx.text(value, font_size="0.9rem", color="var(--color-body)", font_family="var(--font-sans)"),
        align="start",
        gap="0.75rem",
        width="100%",
    )


def _status_badge(state_val: rx.Var) -> rx.Component:
    return rx.match(
        state_val,
        ("draft", rx.badge("Draft", color_scheme="gray", size="2")),
        ("submitted", rx.badge("Submitted", color_scheme="blue", size="2")),
        ("approved", rx.badge("Approved", color_scheme="green", size="2")),
        ("rejected", rx.badge("Rejected", color_scheme="red", size="2")),
        ("withdrawn", rx.badge("Withdrawn", color_scheme="gray", size="2")),
        rx.badge(state_val, size="2"),
    )


def _header_section() -> rx.Component:
    d = FacultyRequestDetailState.detail
    return rx.vstack(
        rx.hstack(
            rx.heading(d["request_type"], size="5", font_family="var(--font-sans)"),
            _status_badge(d["status"]),
            align="center",
            gap="0.75rem",
        ),
        rx.divider(),
        _kv_row("Purpose:", d["purpose"]),
        _kv_row("Addressed To:", d["to_whom"]),
        rx.cond(
            d["date_required_by"] != "—",
            _kv_row("Date Required By:", d["date_required_by"]),
            rx.fragment(),
        ),
        rx.cond(
            d["additional_notes"] != "",
            _kv_row("Additional Notes:", d["additional_notes"]),
            rx.fragment(),
        ),
        _kv_row("Last Updated:", d["submitted_at"]),
        align="start",
        gap="0.5rem",
        width="100%",
        padding="1rem",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        background="var(--color-surface, #fff)",
    )


def _attachment_item(att: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.icon("file", size=14, color="var(--color-muted)"),
        rx.link(
            att["name"],
            href=rx.Var.create(DOWNLOAD_PREFIX) + att["id"].to(str),
            font_size="0.85rem",
            color="var(--color-primary)",
            text_decoration="underline",
        ),
        rx.text(
            rx.Var.create("(") + att["size_kb"].to(str) + " KB)",
            font_size="0.8rem",
            color="var(--color-muted)",
        ),
        align="center",
        gap="0.5rem",
    )


def _attachments_section() -> rx.Component:
    return rx.vstack(
        rx.heading("Attachments", size="3", font_family="var(--font-sans)"),
        rx.cond(
            FacultyRequestDetailState.attachments.length() > 0,  # type: ignore[attr-defined]
            rx.vstack(
                rx.foreach(FacultyRequestDetailState.attachments, _attachment_item),
                align="start",
                gap="0.25rem",
            ),
            rx.text(
                "No attachments.",
                font_size="0.85rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
        ),
        align="start",
        gap="0.5rem",
        width="100%",
        padding="1rem",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        background="var(--color-surface, #fff)",
    )


def _action_row(act: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(act["stage_index"], font_size="0.85rem")),
        rx.table.cell(rx.text(act["action_type"], font_size="0.85rem")),
        rx.table.cell(rx.text(act["actor_display"], font_size="0.85rem")),
        rx.table.cell(
            rx.text(
                act["comment"],
                font_size="0.85rem",
                color="var(--color-body)",
                max_width="300px",
            )
        ),
        rx.table.cell(rx.text(act["decided_at"], font_size="0.8rem", color="var(--color-muted)")),
    )


def _approval_history_section() -> rx.Component:
    return rx.vstack(
        rx.heading("Approval History", size="3", font_family="var(--font-sans)"),
        rx.cond(
            FacultyRequestDetailState.actions.length() > 0,  # type: ignore[attr-defined]
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Stage"),
                        rx.table.column_header_cell("Decision"),
                        rx.table.column_header_cell("By"),
                        rx.table.column_header_cell("Comment"),
                        rx.table.column_header_cell("Date"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(FacultyRequestDetailState.actions, _action_row),
                ),
                width="100%",
                overflow_x="auto",
            ),
            rx.text(
                "No decisions yet.",
                font_size="0.85rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
        ),
        align="start",
        gap="0.5rem",
        width="100%",
        padding="1rem",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        background="var(--color-surface, #fff)",
    )


def faculty_request_detail_page() -> rx.Component:
    detail_content = rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.link(
                    secondary_btn(rx.icon("arrow-left", size=14), " Back to My Requests"),
                    href="/faculty/requests",
                    text_decoration="none",
                ),
                margin_bottom="1rem",
            ),
            rx.cond(
                FacultyRequestDetailState.detail_error != "",
                flash_error(FacultyRequestDetailState.detail_error),
                rx.fragment(),
            ),
            rx.cond(
                FacultyRequestDetailState.detail_loading,
                rx.center(rx.spinner(), padding="2rem"),
                rx.cond(
                    FacultyRequestDetailState.detail != {},
                    rx.vstack(
                        _header_section(),
                        _attachments_section(),
                        _approval_history_section(),
                        rx.cond(
                            FacultyRequestDetailState.detail["can_withdraw"],
                            rx.hstack(
                                destructive_btn(
                                    "Withdraw Request",
                                    on_click=FacultyRequestDetailState.open_withdraw_confirm,
                                ),
                                margin_top="0.5rem",
                            ),
                            rx.fragment(),
                        ),
                        align="start",
                        gap="1rem",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
            ),
            padding="2rem",
            max_width="900px",
            width="100%",
        ),
        confirmation_dialog(
            title="Withdraw Request",
            body="This will withdraw your NOC request. The assigned approver will be notified. This action cannot be undone.",
            confirm_label="Withdraw",
            cancel_label="Cancel",
            is_open=FacultyRequestDetailState.confirm_withdraw_open,
            on_confirm=FacultyRequestDetailState.withdraw_current_request,
            on_cancel=FacultyRequestDetailState.cancel_withdraw_confirm,
        ),
        page_footer(),
        align="start",
        width="100%",
        min_height="100vh",
        background="var(--color-background, #f5f0eb)",
    )

    return rx.cond(AuthState.current_user_id != "", detail_content, rx.fragment())
