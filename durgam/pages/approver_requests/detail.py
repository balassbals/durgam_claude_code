"""Approver request detail page (/approver/requests/{faculty_request_id}) — M10 Phase 7C."""

import reflex as rx

from durgam.pages.components import (
    destructive_btn,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.states.approver_requests import ApproverRequestDetailState


def _kv_row(label: str, value: rx.Component | rx.Var) -> rx.Component:
    return rx.hstack(
        rx.text(label, font_weight="600", font_size="0.82rem", min_width="9rem", color="var(--color-muted)"),
        rx.box(value, font_size="0.9rem"),
        align="start",
        gap="1rem",
        width="100%",
    )


def _status_badge(status: rx.Var) -> rx.Component:
    return rx.match(
        status,
        ("submitted", rx.badge("Submitted", color_scheme="blue")),
        ("approved", rx.badge("Approved", color_scheme="green")),
        ("rejected", rx.badge("Rejected", color_scheme="red")),
        ("withdrawn", rx.badge("Withdrawn", color_scheme="gray")),
        rx.badge(status),
    )


def _payload_panel() -> rx.Component:
    req = ApproverRequestDetailState.request
    return rx.vstack(
        rx.heading("Request Details", size="3", font_family="var(--font-sans)", margin_bottom="0.5rem"),
        rx.box(
            rx.vstack(
                _kv_row("From", rx.text(req["requestor_name"])),
                _kv_row("Designation", rx.text(req["requestor_designation"])),
                _kv_row("Request Type", rx.text(req["request_type"])),
                _kv_row("Status", _status_badge(req["status"])),
                _kv_row("Purpose / Scope", rx.text(req["purpose"])),
                _kv_row("Addressed To", rx.text(req["to_whom"])),
                _kv_row("Needed By", rx.text(req["date_required_by"])),
                rx.cond(
                    req["additional_notes"] != "",
                    _kv_row("Additional Notes", rx.text(req["additional_notes"])),
                    rx.fragment(),
                ),
                _kv_row("Submitted", rx.text(req["submitted_at"])),
                _kv_row(
                    "Stage",
                    rx.text(
                        ApproverRequestDetailState.current_stage.to(str),
                        " of ",
                        ApproverRequestDetailState.request["id"].to(str),  # placeholder len
                    ),
                ),
                gap="0.6rem",
                align="start",
                width="100%",
            ),
            padding="1.25rem",
            border="1px solid var(--color-rule)",
            border_radius="var(--radius-2)",
            background="var(--color-surface)",
            width="100%",
        ),
        align="start",
        width="100%",
    )


def _attachments_panel() -> rx.Component:
    return rx.cond(
        ApproverRequestDetailState.attachments.length() > 0,
        rx.vstack(
            rx.heading("Attachments", size="3", font_family="var(--font-sans)", margin_bottom="0.5rem"),
            rx.vstack(
                rx.foreach(
                    ApproverRequestDetailState.attachments,
                    lambda a: rx.hstack(
                        rx.icon("paperclip", size=14, color="var(--color-muted)"),
                        rx.text(a["name"], font_size="0.88rem"),
                        rx.text(
                            a["size_kb"],
                            " KB",
                            font_size="0.78rem",
                            color="var(--color-muted)",
                        ),
                        align="center",
                        gap="0.5rem",
                    ),
                ),
                gap="0.4rem",
                padding="1rem 1.25rem",
                border="1px solid var(--color-rule)",
                border_radius="var(--radius-2)",
                background="var(--color-surface)",
                width="100%",
            ),
            align="start",
            width="100%",
        ),
        rx.fragment(),
    )


def _action_history_panel() -> rx.Component:
    return rx.cond(
        ApproverRequestDetailState.actions.length() > 0,
        rx.vstack(
            rx.heading("Action History", size="3", font_family="var(--font-sans)", margin_bottom="0.5rem"),
            rx.vstack(
                rx.foreach(
                    ApproverRequestDetailState.actions,
                    lambda act: rx.box(
                        rx.hstack(
                            rx.badge(act["action_type"], color_scheme=rx.cond(
                                act["action_type"] == "Approve",
                                "green",
                                "red",
                            ), size="1"),
                            rx.text(
                                "Stage ",
                                act["stage_index"],
                                " — ",
                                act["actor_display"],
                                font_size="0.85rem",
                                font_weight="500",
                            ),
                            rx.spacer(),
                            rx.text(act["decided_at"], font_size="0.78rem", color="var(--color-muted)"),
                            align="center",
                            width="100%",
                        ),
                        rx.cond(
                            act["comment"] != "",
                            rx.text(
                                act["comment"],
                                font_size="0.83rem",
                                color="var(--color-muted)",
                                margin_top="0.3rem",
                                font_style="italic",
                            ),
                            rx.fragment(),
                        ),
                        padding="0.85rem 1rem",
                        border="1px solid var(--color-rule)",
                        border_radius="var(--radius-2)",
                        background="var(--color-surface)",
                        width="100%",
                    ),
                ),
                gap="0.5rem",
                width="100%",
            ),
            align="start",
            width="100%",
        ),
        rx.fragment(),
    )


def _confidentiality_controls() -> rx.Component:
    """Hide-from-requestor checkbox + share-with multi-select for prior-stage actors."""
    return rx.vstack(
        rx.hstack(
            rx.checkbox(
                checked=ApproverRequestDetailState.action_hide_from_requestor,
                on_change=lambda _: ApproverRequestDetailState.toggle_hide_from_requestor(),
            ),
            rx.text("Hide this decision from the requestor", font_size="0.88rem"),
            align="center",
            gap="0.5rem",
        ),
        rx.text(
            "When checked, the requestor will not see your comment or action.",
            font_size="0.75rem",
            color="var(--color-muted)",
        ),
        rx.cond(
            ApproverRequestDetailState.prior_action_actors.length() > 0,
            rx.vstack(
                rx.text("Share with prior-stage approvers:", font_size="0.85rem", font_weight="500"),
                rx.foreach(
                    ApproverRequestDetailState.prior_action_actors,
                    lambda actor: rx.hstack(
                        rx.checkbox(
                            checked=ApproverRequestDetailState.action_share_with_user_ids.contains(
                                actor["id"]
                            ),
                            on_change=lambda _: ApproverRequestDetailState.toggle_share_with(actor["id"]),
                        ),
                        rx.text(actor["display"], font_size="0.85rem"),
                        align="center",
                        gap="0.5rem",
                    ),
                ),
                align="start",
                gap="0.4rem",
                width="100%",
            ),
            rx.fragment(),
        ),
        align="start",
        gap="0.35rem",
        width="100%",
    )


def _action_form() -> rx.Component:
    """Approve/reject form — only shown when user is eligible."""
    return rx.cond(
        ApproverRequestDetailState.user_eligible,
        rx.vstack(
            rx.heading("Your Decision", size="3", font_family="var(--font-sans)", margin_bottom="0.5rem"),
            rx.box(
                rx.vstack(
                    rx.text_area(
                        placeholder="Comment (required for rejection, optional for approval)…",
                        value=ApproverRequestDetailState.action_comment,
                        on_change=ApproverRequestDetailState.set_action_comment,
                        rows="4",
                        width="100%",
                        resize="vertical",
                        font_family="var(--font-sans)",
                        font_size="0.9rem",
                    ),
                    _confidentiality_controls(),
                    rx.cond(
                        ApproverRequestDetailState.action_error != "",
                        rx.callout(
                            ApproverRequestDetailState.action_error,
                            color="red",
                            icon="triangle-alert",
                        ),
                        rx.fragment(),
                    ),
                    rx.hstack(
                        primary_btn(
                            "Approve",
                            on_click=ApproverRequestDetailState.approve,
                            loading=ApproverRequestDetailState.action_in_progress,
                            type="button",
                        ),
                        destructive_btn(
                            "Reject",
                            on_click=ApproverRequestDetailState.reject,
                            loading=ApproverRequestDetailState.action_in_progress,
                            type="button",
                        ),
                        secondary_btn(
                            "Cancel",
                            on_click=rx.redirect("/approver/inbox"),
                            type="button",
                        ),
                        gap="0.75rem",
                        flex_wrap="wrap",
                    ),
                    gap="0.85rem",
                    align="start",
                    width="100%",
                ),
                padding="1.25rem",
                border="1px solid var(--color-rule)",
                border_radius="var(--radius-2)",
                background="var(--color-surface)",
                width="100%",
            ),
            align="start",
            width="100%",
        ),
        rx.callout(
            "You are not the eligible approver for this request at its current stage.",
            icon="lock",
            color="gray",
        ),
    )


def approver_request_detail_page() -> rx.Component:
    content = rx.vstack(
        nav_shell(),
        rx.box(
            rx.cond(
                ApproverRequestDetailState.detail_loading,
                rx.center(rx.spinner(), padding="4rem"),
                rx.cond(
                    ApproverRequestDetailState.detail_error != "",
                    rx.vstack(
                        rx.callout(
                            ApproverRequestDetailState.detail_error,
                            color="red",
                            icon="triangle-alert",
                        ),
                        rx.link(
                            secondary_btn("Back to Inbox", type="button"),
                            href="/approver/inbox",
                        ),
                        gap="1rem",
                    ),
                    rx.vstack(
                        rx.hstack(
                            rx.link(
                                rx.icon("arrow-left", size=16),
                                " Back",
                                href="/approver/inbox",
                                font_size="0.85rem",
                                color="var(--color-primary)",
                                display="flex",
                                align_items="center",
                                gap="0.3rem",
                            ),
                            width="100%",
                            margin_bottom="1rem",
                        ),
                        _payload_panel(),
                        _attachments_panel(),
                        _action_history_panel(),
                        _action_form(),
                        gap="1.5rem",
                        align="start",
                        width="100%",
                    ),
                ),
            ),
            padding="2rem",
            max_width="800px",
            width="100%",
        ),
        page_footer(),
        align="start",
        width="100%",
        min_height="100vh",
    )
    return rx.cond(
        ApproverRequestDetailState.current_user_id != "",
        content,
        rx.fragment(),
    )
