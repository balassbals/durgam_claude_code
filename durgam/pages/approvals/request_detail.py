"""Approval request detail — read-only for Phase 2 (/approvals/request/[request_id])."""

import reflex as rx

from durgam.pages.components import (
    destructive_btn,
    flash_error,
    nav_shell,
    page_footer,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.states.approval_requests import RequestDetailState
from durgam.states.auth import AuthState

DOWNLOAD_PREFIX = "/api/files/"


def _state_badge_detail(state_val: rx.Var) -> rx.Component:
    return rx.match(
        state_val,
        ("submitted", rx.badge("Submitted", color_scheme="blue", size="2")),
        ("in_review", rx.badge("In Review", color_scheme="orange", size="2")),
        ("approved", rx.badge("Approved", color_scheme="green", size="2")),
        ("rejected", rx.badge("Rejected", color_scheme="red", size="2")),
        ("withdrawn", rx.badge("Withdrawn", color_scheme="gray", size="2")),
        ("cancelled", rx.badge("Cancelled", color_scheme="gray", size="2")),
        rx.badge(state_val, size="2"),
    )


def _kv_row(label: str, value: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.text(
            label,
            font_weight="600",
            font_size="0.85rem",
            color="var(--color-muted)",
            min_width="120px",
            font_family="var(--font-sans)",
        ),
        rx.text(
            value,
            font_size="0.9rem",
            color="var(--color-body)",
            font_family="var(--font-sans)",
        ),
        align="start",
        gap="0.75rem",
        width="100%",
    )


def _step_decision_badge(decision: rx.Var) -> rx.Component:
    return rx.match(
        decision,
        ("approved", rx.badge("Approved", color_scheme="green")),
        ("rejected", rx.badge("Rejected", color_scheme="red")),
        ("forwarded", rx.badge("Forwarded", color_scheme="blue")),
        rx.badge(decision),
    )


def _step_row(step: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(step["stage"], font_size="0.85rem")),
        rx.table.cell(rx.text(step["approver_display"], font_size="0.85rem")),
        rx.table.cell(rx.text(step["approver_role_code"], font_size="0.85rem")),
        rx.table.cell(_step_decision_badge(step["decision"])),
        rx.table.cell(
            rx.text(
                step["comment"],
                font_size="0.85rem",
                color="var(--color-body)",
                max_width="300px",
                overflow="hidden",
                text_overflow="ellipsis",
            ),
        ),
        rx.table.cell(rx.text(step["decided_at"], font_size="0.8rem", color="var(--color-muted)")),
    )


def _attachment_item(att: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.icon("file", size=14, color="var(--color-muted)"),
        rx.link(
            att["name"],
            href=DOWNLOAD_PREFIX + att["id"],
            font_size="0.85rem",
            color="var(--color-primary)",
            text_decoration="underline",
        ),
        rx.text(
            f"({att['size_kb']} KB)",
            font_size="0.8rem",
            color="var(--color-muted)",
        ),
        align="center",
        gap="0.5rem",
    )


def _header_section() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading(
                RequestDetailState.request["title"],
                size="5",
                font_family="var(--font-sans)",
            ),
            _state_badge_detail(RequestDetailState.request["state"]),
            align="center",
            gap="0.75rem",
            flex_wrap="wrap",
        ),
        rx.box(
            _kv_row("Process", RequestDetailState.process["title"]),
            _kv_row("Requestor", RequestDetailState.request["requestor_name"]),
            _kv_row("Current Stage", RequestDetailState.request["current_stage_label"]),
            _kv_row("Submitted", RequestDetailState.request["submitted_at"]),
            _kv_row("Decided", RequestDetailState.request["decided_at"]),
            width="100%",
        ),
        align="start",
        gap="0.75rem",
        width="100%",
        padding="1.5rem",
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="6px",
    )


def _description_section() -> rx.Component:
    return rx.cond(
        RequestDetailState.request["description"] != "",
        rx.vstack(
            rx.text(
                "Description",
                font_weight="700",
                font_size="1rem",
                color="var(--color-primary)",
                font_family="var(--font-sans)",
            ),
            rx.text(
                RequestDetailState.request["description"],
                font_size="0.9rem",
                line_height="1.6",
                color="var(--color-body)",
                font_family="var(--font-sans)",
                white_space="pre-wrap",
            ),
            align="start",
            gap="0.5rem",
            width="100%",
            padding="1.25rem",
            background="white",
            border="1px solid var(--color-rule)",
            border_radius="6px",
        ),
        rx.fragment(),
    )


def _attachments_section(title: str, items: rx.Var) -> rx.Component:
    return rx.cond(
        items.length() > 0,  # type: ignore[attr-defined]
        rx.vstack(
            rx.text(
                title,
                font_weight="700",
                font_size="1rem",
                color="var(--color-primary)",
                font_family="var(--font-sans)",
            ),
            rx.vstack(
                rx.foreach(items, _attachment_item),
                align="start",
                gap="0.5rem",
                width="100%",
            ),
            align="start",
            gap="0.5rem",
            width="100%",
            padding="1.25rem",
            background="white",
            border="1px solid var(--color-rule)",
            border_radius="6px",
        ),
        rx.fragment(),
    )


def _steps_section() -> rx.Component:
    header_cells = [
        rx.table.column_header_cell(h, font_weight="600", font_size="0.8rem",
                                     color="var(--color-muted)", text_transform="uppercase")
        for h in ["Stage", "Approver", "Role", "Decision", "Comment", "Date"]
    ]

    return rx.vstack(
        rx.text(
            "Approval History",
            font_weight="700",
            font_size="1rem",
            color="var(--color-primary)",
            font_family="var(--font-sans)",
        ),
        rx.cond(
            RequestDetailState.steps.length() > 0,  # type: ignore[attr-defined]
            rx.table.root(
                rx.table.header(rx.table.row(*header_cells)),
                rx.table.body(rx.foreach(RequestDetailState.steps, _step_row)),
                width="100%",
            ),
            rx.text(
                "No approver actions yet.",
                font_size="0.9rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
        ),
        align="start",
        gap="0.75rem",
        width="100%",
        padding="1.25rem",
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="6px",
    )


# Phase 3 adds approver decision controls here.
def _action_row() -> rx.Component:
    return rx.cond(
        RequestDetailState.can_withdraw,
        rx.hstack(
            destructive_btn(
                "Withdraw Request",
                on_click=RequestDetailState.open_withdraw_confirm,
            ),
            justify="start",
            width="100%",
        ),
        rx.fragment(),
    )


def request_detail_page() -> rx.Component:
    detail_content = rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.link(
                    secondary_btn(
                        rx.icon("arrow-left", size=14),
                        " Back to My Requests",
                    ),
                    href="/approvals/my-requests",
                    text_decoration="none",
                ),
                margin_bottom="1rem",
            ),
            # Error
            rx.cond(
                RequestDetailState.error != "",
                flash_error(RequestDetailState.error),
                rx.fragment(),
            ),
            # Loading
            rx.cond(
                RequestDetailState.loading,
                rx.center(rx.spinner(), padding="2rem"),
                rx.cond(
                    RequestDetailState.request,
                    rx.vstack(
                        _header_section(),
                        _description_section(),
                        _attachments_section(
                            "Supporting Documents",
                            RequestDetailState.upward_attachments,
                        ),
                        _steps_section(),
                        _attachments_section(
                            "Approver Attachments",
                            RequestDetailState.downward_attachments,
                        ),
                        _action_row(),
                        align="start",
                        gap="1rem",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
            ),
            # Withdraw confirmation dialog
            confirmation_dialog(
                is_open=RequestDetailState.confirm_withdraw_open,
                title="Withdraw this request?",
                body="Approvers will be notified. This cannot be undone.",
                on_confirm=RequestDetailState.withdraw_request,
                on_cancel=RequestDetailState.cancel_withdraw,
                confirm_label="Withdraw",
            ),
            padding="2rem",
            max_width="900px",
            width="100%",
        ),
        page_footer(),
        align="start",
        width="100%",
        min_height="100vh",
        background="var(--color-background, #f5f0eb)",
    )

    return rx.cond(
        AuthState.current_user_id != "",
        detail_content,
        rx.fragment(),
    )
