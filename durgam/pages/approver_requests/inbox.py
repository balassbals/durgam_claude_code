"""Approver inbox page (/approver/inbox) — M10 Phase 7C."""

import reflex as rx

from durgam.pages.components import nav_shell, page_footer
from durgam.states.approver_requests import ApproverInboxState


def _inbox_card(item: rx.Var) -> rx.Component:
    return rx.box(
        rx.link(
            rx.vstack(
                rx.hstack(
                    rx.badge(
                        item["request_type_label"],
                        color_scheme="indigo",
                        size="1",
                    ),
                    rx.spacer(),
                    rx.text(
                        "Stage ",
                        item["current_stage"].to(str),
                        " of ",
                        item["total_stages"].to(str),
                        font_size="0.78rem",
                        color="var(--color-muted)",
                    ),
                    align="center",
                    width="100%",
                ),
                rx.text(
                    item["requestor_name"],
                    font_weight="600",
                    font_size="0.95rem",
                ),
                rx.text(
                    item["requestor_designation"],
                    font_size="0.8rem",
                    color="var(--color-muted)",
                ),
                rx.hstack(
                    rx.icon("calendar", size=12, color="var(--color-muted)"),
                    rx.text(
                        "Submitted: ",
                        item["submitted_at_display"],
                        font_size="0.78rem",
                        color="var(--color-muted)",
                    ),
                    align="center",
                    gap="0.3rem",
                ),
                align="start",
                gap="0.35rem",
                width="100%",
            ),
            href=rx.Var.create("/approver/requests/") + item["id"].to(str),
            text_decoration="none",
            color="inherit",
            width="100%",
            display="block",
        ),
        padding="1rem 1.25rem",
        border="1px solid var(--color-rule)",
        border_radius="var(--radius-2)",
        background="var(--color-surface)",
        cursor="pointer",
        _hover={"border_color": "var(--color-primary)", "box_shadow": "var(--shadow-sm)"},
        width="100%",
    )


def approver_inbox_page() -> rx.Component:
    content = rx.vstack(
        nav_shell(),
        rx.box(
            rx.vstack(
                rx.heading(
                    "Faculty Inbox",
                    size="5",
                    font_family="var(--font-sans)",
                    margin_bottom="0.25rem",
                ),
                rx.text(
                    "Faculty requests awaiting your action.",
                    font_size="0.85rem",
                    color="var(--color-muted)",
                    margin_bottom="1.5rem",
                ),
                rx.cond(
                    ApproverInboxState.inbox_loading,
                    rx.center(rx.spinner(), padding="3rem"),
                    rx.cond(
                        ApproverInboxState.inbox_error != "",
                        rx.callout(
                            ApproverInboxState.inbox_error,
                            color="red",
                            icon="triangle-alert",
                        ),
                        rx.cond(
                            ApproverInboxState.inbox_items.length() == 0,
                            rx.center(
                                rx.vstack(
                                    rx.icon("check-circle", size=40, color="var(--color-muted)"),
                                    rx.text(
                                        "No pending faculty requests.",
                                        color="var(--color-muted)",
                                        font_size="0.9rem",
                                    ),
                                    align="center",
                                    gap="0.75rem",
                                ),
                                padding="3rem",
                            ),
                            rx.vstack(
                                rx.foreach(
                                    ApproverInboxState.inbox_items,
                                    _inbox_card,
                                ),
                                gap="0.75rem",
                                width="100%",
                            ),
                        ),
                    ),
                ),
                align="start",
                width="100%",
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
        ApproverInboxState.current_user_id != "",
        content,
        rx.fragment(),
    )
