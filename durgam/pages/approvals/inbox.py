"""Approval Inbox — pending requests awaiting the current user's decision."""

import reflex as rx

from durgam.pages.components import admin_page, app_shell
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.approval_requests import ApproverInboxState

_INBOX_COLUMNS: list[TableColumn] = [
    TableColumn(key="title", label="Title"),
    TableColumn(key="process_title", label="Process"),
    TableColumn(key="requestor_display", label="Requestor"),
    TableColumn(key="current_stage_label", label="Stage", hidden_on_card=True),
    TableColumn(key="submitted_at_display", label="Submitted", hidden_on_card=True),
]


def _actions(row: rx.Var) -> rx.Component:
    return rx.icon_button(
        rx.icon("eye", size=16),
        aria_label="Review request",
        on_click=ApproverInboxState.open_request(row["id"]),
        variant="ghost",
        size="1",
        cursor="pointer",
    )


def inbox_page() -> rx.Component:
    content = rx.vstack(
        rx.hstack(
            rx.heading(
                "Approval Inbox",
                size="5",
                font_family="var(--font-sans)",
            ),
            rx.spacer(),
            rx.segmented_control.root(
                rx.segmented_control.item("Pending", value="pending"),
                rx.segmented_control.item("Past Actions", value="past"),
                value=ApproverInboxState.view_mode,
                on_change=ApproverInboxState.set_view_mode,
            ),
            align="center",
            width="100%",
            margin_bottom="1rem",
        ),
        rx.text(
            rx.cond(
                ApproverInboxState.view_mode == "past",
                "Requests you have acted on as an approver.",
                rx.cond(
                    ApproverInboxState.rows.length() > 0,  # type: ignore[attr-defined]
                    rx.cond(
                        ApproverInboxState.rows.length() == 1,  # type: ignore[attr-defined]
                        "You have 1 request awaiting your decision.",
                        f"You have {ApproverInboxState.rows.length()} requests awaiting your decision.",  # type: ignore[attr-defined]
                    ),
                    "",
                ),
            ),
            font_size="0.85rem",
            color="var(--color-muted)",
            margin_bottom="0.75rem",
            font_family="var(--font-sans)",
        ),
        rx.cond(
            ApproverInboxState.loading,
            rx.center(rx.spinner(), padding="2rem"),
            data_table(
                rows=ApproverInboxState.rows,
                columns=_INBOX_COLUMNS,
                card_primary_key="title",
                is_mobile=False,
                actions=_actions,
                empty_message="No items found.",
            ),
        ),
        align="start",
        width="100%",
    )

    return admin_page(app_shell(content, container="lg"))
