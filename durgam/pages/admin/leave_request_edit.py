"""Leave Request Admin Edit page — /admin/leave/request-edit (M8.1 E-022 Phase 8)."""

import reflex as rx

from durgam.pages.components import (
    config_toast,
    form_modal,
    nav_shell,
    primary_btn,
    secondary_btn,
)
from durgam.states.auth import AuthState
from durgam.states.leave_request_admin import LeaveRequestAdminState

_LEAVE_TYPES = ["CL", "SCL", "EL", "HPL", "CML", "EOL", "ML", "SL"]
_LEAVE_STATES = ["submitted", "in_review", "approved", "rejected", "withdrawn", "cancelled"]


# ── Filter bar ───────────────────────────────────────────────────────

def _filter_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            placeholder="Username...",
            value=LeaveRequestAdminState.username_filter,
            on_change=LeaveRequestAdminState.set_username_filter,
            width="14rem",
            font_size="0.875rem",
        ),
        rx.select.root(
            rx.select.trigger(placeholder="Leave type"),
            rx.select.content(
                rx.select.item("All types", value="all"),
                *[rx.select.item(lt, value=lt) for lt in _LEAVE_TYPES],
            ),
            value=LeaveRequestAdminState.leave_type_filter,
            on_change=LeaveRequestAdminState.set_leave_type_filter,
            width="10rem",
        ),
        rx.select.root(
            rx.select.trigger(placeholder="State"),
            rx.select.content(
                rx.select.item("All states", value="all"),
                *[rx.select.item(s, value=s) for s in _LEAVE_STATES],
            ),
            value=LeaveRequestAdminState.state_filter,
            on_change=LeaveRequestAdminState.set_state_filter,
            width="10rem",
        ),
        primary_btn(
            "Apply Filters",
            on_click=LeaveRequestAdminState.apply_filters,
        ),
        secondary_btn(
            "Clear Filters",
            on_click=LeaveRequestAdminState.clear_filters,
            type="button",
        ),
        gap="0.75rem",
        align="center",
        flex_wrap="wrap",
        margin_bottom="1rem",
    )


# ── Results table ────────────────────────────────────────────────────

def _request_row(row: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(row["username"], font_size="0.82rem", font_weight="500")),
        rx.table.cell(rx.text(row["leave_type"], font_size="0.82rem")),
        rx.table.cell(rx.text(row["starts_on"], font_size="0.82rem")),
        rx.table.cell(rx.text(row["ends_on"], font_size="0.82rem")),
        rx.table.cell(rx.text(row["sanctioned_days"], font_size="0.82rem")),
        rx.table.cell(rx.badge(row["state"])),
        rx.table.cell(
            rx.cond(
                row["is_post_facto"],
                rx.badge("Post-facto", color_scheme="amber", size="1"),
                rx.fragment(),
            ),
        ),
        rx.table.cell(
            rx.button(
                "Edit",
                on_click=LeaveRequestAdminState.open_edit_modal(
                    row["id"],
                    row["username"],
                    row["leave_type"],
                    row["starts_on"],
                    row["ends_on"],
                    row["sanctioned_days"],
                    row["state"],
                    row["is_post_facto"],
                ),
                variant="ghost",
                size="1",
                color="var(--color-primary)",
                cursor="pointer",
            ),
        ),
    )


def _results_table() -> rx.Component:
    return rx.cond(
        LeaveRequestAdminState.loading,
        rx.center(rx.spinner(), padding="3rem"),
        rx.cond(
            LeaveRequestAdminState.rows.length() > 0,  # type: ignore[attr-defined]
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Username"),
                            rx.table.column_header_cell("Type"),
                            rx.table.column_header_cell("From"),
                            rx.table.column_header_cell("To"),
                            rx.table.column_header_cell("Days"),
                            rx.table.column_header_cell("State"),
                            rx.table.column_header_cell("Flags"),
                            rx.table.column_header_cell(""),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(LeaveRequestAdminState.rows, _request_row),
                    ),
                    width="100%",
                ),
                overflow_x="auto",
                width="100%",
                border="1px solid var(--color-rule)",
                border_radius="6px",
            ),
            rx.text(
                "No requests match the current filters.",
                color="var(--color-muted)",
                font_size="0.875rem",
                padding="1rem 0",
            ),
        ),
    )


# ── Edit modal ───────────────────────────────────────────────────────

def _edit_modal() -> rx.Component:
    form_body = rx.vstack(
        rx.heading("Edit Leave Request", size="4", font_family="var(--font-sans)", margin_bottom="0.25rem"),
        rx.hstack(
            rx.text("Employee:", font_size="0.85rem", color="var(--color-muted)"),
            rx.text(LeaveRequestAdminState.edit_username, font_size="0.85rem", font_weight="600"),
            rx.text("·", color="var(--color-muted)"),
            rx.text(LeaveRequestAdminState.edit_leave_type, font_size="0.85rem", font_weight="600"),
            rx.text("·", color="var(--color-muted)"),
            rx.text(LeaveRequestAdminState.edit_starts_on, font_size="0.85rem"),
            rx.text("to", font_size="0.85rem", color="var(--color-muted)"),
            rx.text(LeaveRequestAdminState.edit_ends_on, font_size="0.85rem"),
            gap="0.35rem",
            align="center",
            flex_wrap="wrap",
            margin_bottom="0.5rem",
        ),
        rx.hstack(
            rx.text("Current state:", font_size="0.85rem", color="var(--color-muted)"),
            rx.badge(LeaveRequestAdminState.edit_current_state),
            rx.cond(
                LeaveRequestAdminState.edit_is_post_facto,
                rx.badge("Post-facto", color_scheme="amber", size="1"),
                rx.fragment(),
            ),
            gap="0.5rem",
            align="center",
            margin_bottom="1rem",
        ),
        rx.cond(
            LeaveRequestAdminState.edit_window_elapsed
            & (LeaveRequestAdminState.edit_current_state == "approved"),
            rx.box(
                rx.text(
                    "This approved leave's period has ended. It can no longer be cancelled"
                    " or withdrawn. Use the admin balance-edit page if a balance correction"
                    " is needed.",
                    font_size="0.82rem",
                    color="var(--color-warning-text, #92400e)",
                ),
                background="var(--color-warning-bg, #fef3c7)",
                border="1px solid var(--color-warning-border, #f59e0b)",
                border_radius="6px",
                padding="0.75rem",
                width="100%",
                margin_bottom="0.5rem",
            ),
            rx.fragment(),
        ),
        rx.form(
            rx.vstack(
                rx.vstack(
                    rx.text("New State", font_size="0.8rem", font_weight="500"),
                    rx.select.root(
                        rx.select.trigger(placeholder="Select new state"),
                        rx.select.content(
                            rx.foreach(
                                LeaveRequestAdminState.allowed_new_states_filtered,
                                lambda s: rx.select.item(s, value=s),
                            ),
                        ),
                        value=LeaveRequestAdminState.edit_new_state,
                        on_change=LeaveRequestAdminState.set_edit_new_state,
                        disabled=LeaveRequestAdminState.allowed_new_states_filtered.length() == 0,  # type: ignore[attr-defined]
                        width="100%",
                    ),
                    align="start",
                    gap="0.2rem",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("Reason (required)", font_size="0.8rem", font_weight="500"),
                    rx.text_area(
                        name="reason",
                        on_change=LeaveRequestAdminState.set_edit_reason,
                        placeholder="Provide a reason for this state change...",
                        rows="3",
                        width="100%",
                    ),
                    align="start",
                    gap="0.2rem",
                    width="100%",
                ),
                rx.hstack(
                    secondary_btn("Cancel", on_click=LeaveRequestAdminState.close_edit_modal, type="button"),
                    primary_btn(
                        "Save Changes",
                        type="submit",
                        disabled=~LeaveRequestAdminState.is_save_valid,
                        opacity=rx.cond(LeaveRequestAdminState.is_save_valid, "1", "0.5"),
                    ),
                    gap="0.75rem",
                    justify="end",
                    width="100%",
                ),
                gap="0.75rem",
                width="100%",
                align="start",
            ),
            on_submit=LeaveRequestAdminState.submit_edit,
            reset_on_submit=False,
        ),
        align="start",
        width="100%",
        gap="0",
    )

    return form_modal(
        content=form_body,
        is_open=LeaveRequestAdminState.show_edit_modal,
        max_width="540px",
    )


# ── Page root ────────────────────────────────────────────────────────

def admin_leave_request_edit() -> rx.Component:
    content = rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.heading(
                    "Leave Request Admin",
                    size="5",
                    font_family="var(--font-sans)",
                ),
                rx.spacer(),
                align="center",
                width="100%",
                margin_bottom="1.5rem",
            ),
            config_toast(
                LeaveRequestAdminState.flash,
                LeaveRequestAdminState.flash_type,
                LeaveRequestAdminState.dismiss_flash,
            ),
            _filter_bar(),
            _results_table(),
            _edit_modal(),
            padding="2rem",
            max_width="1400px",
            width="100%",
        ),
        align="start",
        width="100%",
        min_height="100vh",
        background="var(--color-background, #f5f0eb)",
    )

    return rx.cond(
        AuthState.admin_authorized,
        content,
        rx.fragment(),
    )
