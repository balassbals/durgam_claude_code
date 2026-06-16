"""Faculty requests list page (/faculty/requests)."""

import reflex as rx

from durgam.pages.components import nav_shell, page_footer, primary_btn
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.auth import AuthState
from durgam.states.faculty_requests import FacultyRequestsState

_COLUMNS: list[TableColumn] = [
    TableColumn(key="request_type", label="Type"),
    TableColumn(key="purpose", label="Purpose"),
    TableColumn(key="status_label", label="Status"),
    TableColumn(key="submitted_at", label="Last Updated", hidden_on_card=True),
]


def _status_badge(row: rx.Var) -> rx.Component:
    state_val = row["status"]
    return rx.match(
        state_val,
        ("draft", rx.badge("Draft", color_scheme="gray")),
        ("submitted", rx.badge("Submitted", color_scheme="blue")),
        ("approved", rx.badge("Approved", color_scheme="green")),
        ("rejected", rx.badge("Rejected", color_scheme="red")),
        ("withdrawn", rx.badge("Withdrawn", color_scheme="gray")),
        rx.badge(state_val),
    )


def _row_actions(row: rx.Var) -> rx.Component:
    return rx.icon_button(
        rx.icon("eye", size=16),
        aria_label="View request",
        on_click=rx.redirect(rx.Var.create("/faculty/requests/") + row["id"].to(str)),
        variant="ghost",
        size="1",
        cursor="pointer",
    )


def faculty_requests_list_page() -> rx.Component:
    content = rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.heading(
                    "My Faculty Requests",
                    size="5",
                    font_family="var(--font-sans)",
                ),
                rx.spacer(),
                rx.link(
                    primary_btn(rx.icon("plus", size=14), " New NOC Request"),
                    href="/faculty/requests/new",
                    text_decoration="none",
                ),
                align="center",
                width="100%",
                margin_bottom="1.5rem",
            ),
            rx.cond(
                FacultyRequestsState.list_loading,
                rx.center(rx.spinner(), padding="2rem"),
                data_table(
                    rows=FacultyRequestsState.my_requests,
                    columns=_COLUMNS,
                    card_primary_key="purpose",
                    is_mobile=False,
                    actions=_row_actions,
                    empty_message="You have not submitted any faculty requests yet.",
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

    return rx.cond(AuthState.current_user_id != "", content, rx.fragment())
