"""My Approval Requests — list page for the logged-in user's own requests."""

import reflex as rx

from durgam.pages.components import nav_shell, page_footer, primary_btn, secondary_btn
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.approval_requests import MyRequestsState, _STATE_OPTIONS
from durgam.states.auth import AuthState

_MY_REQUESTS_COLUMNS: list[TableColumn] = [
    TableColumn(key="title", label="Title"),
    TableColumn(key="process_title", label="Process"),
    TableColumn(key="state", label="State"),
    TableColumn(key="current_stage_label", label="Current Stage", hidden_on_card=True),
    TableColumn(key="submitted_at_display", label="Submitted", hidden_on_card=True),
    TableColumn(key="decided_at_display", label="Decided", hidden_on_card=True),
]


def _state_badge(row: rx.Var) -> rx.Component:
    state_val = row["state"]
    return rx.match(
        state_val,
        ("submitted", rx.badge("Submitted", color_scheme="blue")),
        ("in_review", rx.badge("In Review", color_scheme="orange")),
        ("approved", rx.badge("Approved", color_scheme="green")),
        ("rejected", rx.badge("Rejected", color_scheme="red")),
        ("withdrawn", rx.badge("Withdrawn", color_scheme="gray")),
        ("cancelled", rx.badge("Cancelled", color_scheme="gray")),
        rx.badge(state_val),
    )


def _filter_option(opt: dict) -> rx.Component:
    return rx.select.item(opt["label"], value=opt["value"])


def _actions(row: rx.Var) -> rx.Component:
    return rx.icon_button(
        rx.icon("eye", size=16),
        aria_label="View request",
        on_click=MyRequestsState.open_detail(row["id"]),
        variant="ghost",
        size="1",
        cursor="pointer",
    )


def my_requests_page() -> rx.Component:
    content = rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.heading(
                    "My Approval Requests",
                    size="5",
                    font_family="var(--font-sans)",
                ),
                rx.spacer(),
                rx.link(
                    primary_btn(
                        rx.icon("plus", size=14),
                        " New Request",
                    ),
                    href="/approvals/submit",
                    text_decoration="none",
                ),
                align="center",
                width="100%",
                margin_bottom="1.5rem",
            ),
            # Filter strip
            rx.hstack(
                rx.select.root(
                    rx.select.trigger(
                        placeholder="Filter by state",
                    ),
                    rx.select.content(
                        rx.foreach(_STATE_OPTIONS, _filter_option),
                    ),
                    value=MyRequestsState.state_filter,
                    on_change=MyRequestsState.change_state_filter,
                    size="2",
                ),
                align="center",
                gap="0.75rem",
                margin_bottom="1rem",
                flex_wrap="wrap",
            ),
            # Result summary
            rx.text(
                rx.cond(
                    MyRequestsState.rows.length() > 0,  # type: ignore[attr-defined]
                    f"Showing {MyRequestsState.rows.length()} request(s)",  # type: ignore[attr-defined]
                    "",
                ),
                font_size="0.85rem",
                color="var(--color-muted)",
                margin_bottom="0.75rem",
                font_family="var(--font-sans)",
            ),
            # Data table
            rx.cond(
                MyRequestsState.loading,
                rx.center(rx.spinner(), padding="2rem"),
                data_table(
                    rows=MyRequestsState.rows,
                    columns=_MY_REQUESTS_COLUMNS,
                    card_primary_key="title",
                    is_mobile=False,
                    actions=_actions,
                    empty_message="You have not submitted any approval requests yet.",
                ),
            ),
            padding="2rem",
            max_width="1100px",
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
        content,
        rx.fragment(),
    )
