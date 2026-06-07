"""Approval request detail with decision controls (/approvals/request/[approval_request_id])."""

import reflex as rx

from durgam.pages.components import (
    destructive_btn,
    flash_error,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.file_upload import file_upload_zone
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


def _downward_attachment_item(att: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.icon("file", size=14, color="var(--color-muted)"),
        rx.link(
            att["name"],
            href=rx.Var.create(DOWNLOAD_PREFIX) + att["id"].to(str),
            font_size="0.85rem",
            color="var(--color-primary)",
            text_decoration="underline",
        ),
        rx.cond(
            att["uploader"].to(str) != "",
            rx.text(
                rx.Var.create("uploaded by ") + att["uploader"].to(str),
                font_size="0.8rem",
                color="var(--color-muted)",
                font_style="italic",
            ),
            rx.fragment(),
        ),
        rx.text(
            rx.Var.create("(") + att["size_kb"].to(str) + " KB)",
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
            rx.cond(
                RequestDetailState.request["cc_role_codes"].to(str) != "",
                _kv_row("CC'd to", RequestDetailState.request["cc_role_codes"]),
                rx.fragment(),
            ),
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


def _nrf_details_section() -> rx.Component:
    return rx.vstack(
        rx.text(
            "Non-Regular Faculty Details",
            font_weight="700",
            font_size="1rem",
            color="var(--color-primary)",
            font_family="var(--font-sans)",
        ),
        rx.box(
            _kv_row("Name", RequestDetailState.request["nrf_name"]),
            _kv_row("Designation", RequestDetailState.request["nrf_designation"]),
            _kv_row("Organization", RequestDetailState.request["nrf_organization"]),
            _kv_row("Expertise", RequestDetailState.request["nrf_expertise"]),
            _kv_row("Available From", RequestDetailState.request["nrf_available_from"]),
            _kv_row("Available To", RequestDetailState.request["nrf_available_to"]),
            _kv_row("Type", RequestDetailState.request["nrf_type"]),
            width="100%",
        ),
        align="start",
        gap="0.5rem",
        width="100%",
        padding="1.25rem",
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="6px",
    )


def _attachments_section(title: str, items: rx.Var, *, item_renderer=None) -> rx.Component:
    renderer = item_renderer or _attachment_item
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
                rx.foreach(items, renderer),
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


def _decision_file_item(file_id: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.icon("file", size=14, color="var(--color-muted)"),
        rx.text(file_id, font_size="0.85rem", color="var(--color-body)"),
        rx.icon_button(
            rx.icon("x", size=12),
            aria_label="Remove file",
            on_click=RequestDetailState.remove_decision_file(file_id),
            variant="ghost",
            size="1",
            cursor="pointer",
            color="var(--color-muted)",
        ),
        align="center",
        gap="0.5rem",
        padding="0.25rem 0",
    )


def _downward_upload_section() -> rx.Component:
    return rx.cond(
        (RequestDetailState.process_max_downward > 0) | RequestDetailState.process_requires_downward,
        rx.vstack(
            rx.text(
                "Attachments",
                font_weight="600",
                font_size="0.85rem",
                font_family="var(--font-sans)",
            ),
            rx.cond(
                RequestDetailState.process_requires_downward,
                rx.text(
                    "At least 1 attachment is required.",
                    font_size="0.8rem",
                    color="var(--color-muted)",
                ),
                rx.text(
                    "Attachments are optional.",
                    font_size="0.8rem",
                    color="var(--color-muted)",
                ),
            ),
            rx.cond(
                RequestDetailState.decision_downward_file_ids.length() > 0,  # type: ignore[attr-defined]
                rx.vstack(
                    rx.foreach(
                        RequestDetailState.decision_downward_file_ids,
                        _decision_file_item,
                    ),
                    align="start",
                    gap="0",
                    width="100%",
                ),
                rx.fragment(),
            ),
            file_upload_zone(
                on_drop=RequestDetailState.handle_decision_upload(rx.upload_files()),  # type: ignore[arg-type]
                label="Drag & drop files, or click to browse",
            ),
            align="start",
            gap="0.5rem",
            width="100%",
        ),
        rx.fragment(),
    )


def _dialog_overlay(
    *,
    is_open: rx.Var,
    title: str | rx.Component,
    body_content: rx.Component,
    footer_content: rx.Component,
    error_var: rx.Var,
) -> rx.Component:
    return rx.cond(
        is_open,
        rx.box(
            rx.box(
                rx.box(
                    rx.heading(title, size="4", color="var(--color-body)"),
                    rx.cond(
                        error_var != "",
                        flash_error(error_var),
                        rx.fragment(),
                    ),
                    rx.box(
                        body_content,
                        overflow_y="auto",
                        max_height="calc(85vh - 10rem)",
                        width="100%",
                    ),
                    footer_content,
                    display="flex",
                    flex_direction="column",
                    background="white",
                    border_radius="8px",
                    padding="1.5rem",
                    width="min(560px, 90vw)",
                    max_height="85vh",
                    box_shadow="0 8px 32px rgba(0,0,0,0.18)",
                ),
                display="flex",
                align_items="center",
                justify_content="center",
                position="fixed",
                top="0",
                left="0",
                width="100vw",
                height="100vh",
                z_index="1000",
            ),
            position="fixed",
            top="0",
            left="0",
            width="100vw",
            height="100vh",
            background="rgba(0,0,0,0.45)",
            z_index="999",
        ),
        rx.fragment(),
    )


def _approve_dialog() -> rx.Component:
    body = rx.vstack(
        rx.text(
            "Comment (optional)",
            font_weight="600",
            font_size="0.85rem",
            font_family="var(--font-sans)",
            margin_top="0.75rem",
        ),
        rx.text_area(
            placeholder="Add a comment for the requestor…",
            value=RequestDetailState.decision_comment,
            on_change=RequestDetailState.set_decision_comment,
            width="100%",
            rows="3",
        ),
        _downward_upload_section(),
        align="start",
        gap="0.5rem",
        width="100%",
    )

    footer = rx.hstack(
        rx.button(
            "Cancel",
            on_click=RequestDetailState.close_approve_dialog,
            background="transparent",
            border="1px solid var(--color-rule)",
            color="var(--color-body)",
            padding="0.4rem 1rem",
            border_radius="4px",
            cursor="pointer",
            font_family="var(--font-sans)",
        ),
        rx.cond(
            RequestDetailState.decision_submitting,
            primary_btn(
                rx.hstack(
                    rx.spinner(size="1"),
                    rx.text("Approving…"),
                    align="center",
                    gap="0.5rem",
                ),
                disabled=True,
            ),
            primary_btn(
                "Confirm Approve",
                on_click=RequestDetailState.submit_approve,
            ),
        ),
        justify="end",
        gap="0.75rem",
        margin_top="1.5rem",
        width="100%",
    )

    return _dialog_overlay(
        is_open=RequestDetailState.approve_dialog_open,
        title=rx.cond(
            RequestDetailState.is_terminal_stage,
            "Approve this request",
            "Approve and forward to next stage",
        ),
        body_content=body,
        footer_content=footer,
        error_var=RequestDetailState.decision_error,
    )


def _reject_dialog() -> rx.Component:
    body = rx.vstack(
        rx.text(
            "Reason for rejection (required) *",
            font_weight="600",
            font_size="0.85rem",
            font_family="var(--font-sans)",
            margin_top="0.75rem",
        ),
        rx.text_area(
            placeholder="Explain why this request is being rejected…",
            value=RequestDetailState.decision_comment,
            on_change=RequestDetailState.set_decision_comment,
            width="100%",
            rows="3",
        ),
        _downward_upload_section(),
        align="start",
        gap="0.5rem",
        width="100%",
    )

    footer = rx.hstack(
        rx.button(
            "Cancel",
            on_click=RequestDetailState.close_reject_dialog,
            background="transparent",
            border="1px solid var(--color-rule)",
            color="var(--color-body)",
            padding="0.4rem 1rem",
            border_radius="4px",
            cursor="pointer",
            font_family="var(--font-sans)",
        ),
        destructive_btn(
            rx.cond(
                RequestDetailState.decision_submitting,
                rx.hstack(
                    rx.spinner(size="1"),
                    rx.text("Rejecting…"),
                    align="center",
                    gap="0.5rem",
                ),
                rx.text("Confirm Reject"),
            ),
            on_click=RequestDetailState.submit_reject,
            disabled=RequestDetailState.decision_submitting,
        ),
        justify="end",
        gap="0.75rem",
        margin_top="1.5rem",
        width="100%",
    )

    return _dialog_overlay(
        is_open=RequestDetailState.reject_dialog_open,
        title="Reject this request",
        body_content=body,
        footer_content=footer,
        error_var=RequestDetailState.decision_error,
    )


def _decision_section() -> rx.Component:
    approve_label = rx.cond(
        RequestDetailState.is_terminal_stage,
        "Approve",
        rx.cond(
            RequestDetailState.next_stage_approvers_preview.length() > 0,  # type: ignore[attr-defined]
            rx.text(
                "Approve & forward to ",
                rx.text(
                    RequestDetailState.next_stage_approvers_preview.join(", "),  # type: ignore[attr-defined]
                    font_weight="600",
                ),
            ),
            "Approve & Forward",
        ),
    )

    return rx.cond(
        RequestDetailState.can_decide,
        rx.vstack(
            rx.text(
                "Your Decision",
                font_weight="700",
                font_size="1rem",
                color="var(--color-primary)",
                font_family="var(--font-sans)",
            ),
            rx.text(
                rx.text("Acting as "),
                rx.text(
                    RequestDetailState.current_stage_role_code,
                    font_weight="600",
                ),
                font_size="0.85rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            rx.hstack(
                primary_btn(
                    approve_label,
                    on_click=RequestDetailState.open_approve_dialog,
                ),
                destructive_btn(
                    "Reject",
                    on_click=RequestDetailState.open_reject_dialog,
                ),
                gap="0.75rem",
                flex_wrap="wrap",
            ),
            align="start",
            gap="0.75rem",
            width="100%",
            padding="1.25rem",
            background="white",
            border="2px solid var(--color-primary)",
            border_radius="6px",
        ),
        rx.fragment(),
    )


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
                rx.cond(
                    RequestDetailState.viewer_is_channel_approver,
                    rx.link(
                        secondary_btn(
                            rx.icon("inbox", size=14),
                            " Back to Inbox",
                        ),
                        href="/approvals/inbox",
                        text_decoration="none",
                    ),
                    rx.fragment(),
                ),
                gap="0.75rem",
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
                        rx.cond(
                            RequestDetailState.request["process_code"].to(str) == "NRF_APPROVAL",
                            _nrf_details_section(),
                            rx.fragment(),
                        ),
                        _attachments_section(
                            "Supporting Documents",
                            RequestDetailState.upward_attachments,
                        ),
                        _steps_section(),
                        _attachments_section(
                            "Approver Attachments",
                            RequestDetailState.downward_attachments,
                            item_renderer=_downward_attachment_item,
                        ),
                        _decision_section(),
                        _action_row(),
                        align="start",
                        gap="1rem",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
            ),
            # Decision dialogs
            _approve_dialog(),
            _reject_dialog(),
            # Withdraw confirmation dialog
            confirmation_dialog(
                is_open=RequestDetailState.confirm_withdraw_open,
                title="Withdraw this request?",
                body="This request will be removed from approver inboxes. This cannot be undone.",
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
