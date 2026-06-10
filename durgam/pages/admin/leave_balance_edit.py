"""Leave Balance Admin Edit page — /admin/leave/balance-edit (M8.1 E-022)."""

import reflex as rx

from durgam.pages.components import (
    config_toast,
    form_modal,
    nav_shell,
    primary_btn,
    secondary_btn,
)
from durgam.states.auth import AuthState
from durgam.states.leave_balance_admin import LeaveBalanceAdminState

_LEAVE_TYPES = ["CL", "SCL", "EL", "HPL", "CML", "EOL", "ML", "SL"]

_TH_STYLE = {
    "padding": "0.4rem 0.6rem",
    "font_size": "0.78rem",
    "font_weight": "600",
    "color": "var(--color-muted)",
    "white_space": "nowrap",
    "background": "var(--color-surface)",
    "border_bottom": "1px solid var(--color-rule)",
}

_TD_STYLE = {
    "padding": "0.4rem 0.6rem",
    "font_size": "0.82rem",
    "border_bottom": "1px solid var(--color-rule)",
    "white_space": "nowrap",
}


# ── Filter bar ───────────────────────────────────────────────────────

def _filter_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            placeholder="Username...",
            value=LeaveBalanceAdminState.username_filter,
            on_change=LeaveBalanceAdminState.set_username_filter,
            width="14rem",
            font_size="0.875rem",
        ),
        rx.select.root(
            rx.select.trigger(placeholder="Leave type"),
            rx.select.content(
                rx.select.item("All types", value="all"),
                *[rx.select.item(lt, value=lt) for lt in _LEAVE_TYPES],
            ),
            value=LeaveBalanceAdminState.leave_type_filter,
            on_change=LeaveBalanceAdminState.set_leave_type_filter,
            width="10rem",
        ),
        rx.select.root(
            rx.select.trigger(placeholder="Academic year"),
            rx.select.content(
                rx.select.item("All AYs", value="all"),
                rx.foreach(
                    LeaveBalanceAdminState.ay_options,
                    lambda opt: rx.select.item(opt["name"], value=opt["id"]),
                ),
            ),
            value=LeaveBalanceAdminState.ay_id_filter,
            on_change=LeaveBalanceAdminState.set_ay_id_filter,
            width="10rem",
        ),
        primary_btn(
            "Apply Filters",
            on_click=LeaveBalanceAdminState.apply_filters,
        ),
        gap="0.75rem",
        align="center",
        flex_wrap="wrap",
        margin_bottom="1rem",
    )


# ── Results table ────────────────────────────────────────────────────

def _results_table() -> rx.Component:
    return rx.cond(
        LeaveBalanceAdminState.loading,
        rx.center(rx.spinner(), padding="3rem"),
        rx.cond(
            LeaveBalanceAdminState.rows.length() > 0,  # type: ignore[attr-defined]
            rx.box(
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Username", **_TH_STYLE, position="sticky", left="0", z_index="1", background_color="var(--color-card-bg, var(--color-background))"),
                                rx.table.column_header_cell("Leave Type", **_TH_STYLE),
                                rx.table.column_header_cell("AY", **_TH_STYLE),
                                rx.table.column_header_cell("Opening", **_TH_STYLE),
                                rx.table.column_header_cell("Credited", **_TH_STYLE),
                                rx.table.column_header_cell("Availed", **_TH_STYLE),
                                rx.table.column_header_cell("Forfeited", **_TH_STYLE),
                                rx.table.column_header_cell("Encashed", **_TH_STYLE),
                                rx.table.column_header_cell("Closing", **_TH_STYLE),
                                rx.table.column_header_cell("", **_TH_STYLE),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(LeaveBalanceAdminState.rows, _balance_row),
                        ),
                        width="100%",
                    ),
                    overflow_x="auto",
                    border="1px solid var(--color-rule)",
                    border_radius="6px",
                    background="white",
                ),
                width="100%",
            ),
            rx.text(
                "No balance records match the current filters.",
                color="var(--color-muted)",
                font_size="0.875rem",
                padding="1rem 0",
            ),
        ),
    )


def _balance_row(row: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(row["username"], font_size="0.82rem", font_weight="500"),
            **_TD_STYLE,
            position="sticky",
            left="0",
            z_index="1",
            background_color="var(--color-card-bg, var(--color-background))",
        ),
        rx.table.cell(rx.text(row["leave_type"], font_size="0.82rem"), **_TD_STYLE),
        rx.table.cell(rx.text(row["ay_name"], font_size="0.82rem"), **_TD_STYLE),
        rx.table.cell(rx.text(row["opening"].to_string(), font_size="0.82rem"), **_TD_STYLE),  # type: ignore[attr-defined]
        rx.table.cell(rx.text(row["credited"].to_string(), font_size="0.82rem"), **_TD_STYLE),  # type: ignore[attr-defined]
        rx.table.cell(rx.text(row["availed"].to_string(), font_size="0.82rem"), **_TD_STYLE),  # type: ignore[attr-defined]
        rx.table.cell(rx.text(row["forfeited"].to_string(), font_size="0.82rem"), **_TD_STYLE),  # type: ignore[attr-defined]
        rx.table.cell(rx.text(row["encashed"].to_string(), font_size="0.82rem"), **_TD_STYLE),  # type: ignore[attr-defined]
        rx.table.cell(rx.text(row["closing"].to_string(), font_size="0.82rem", font_weight="600"), **_TD_STYLE),  # type: ignore[attr-defined]
        rx.table.cell(
            rx.button(
                "Edit",
                on_click=LeaveBalanceAdminState.open_edit_modal(
                    row["id"],
                    row["username"],
                    row["leave_type"],
                    row["ay_name"],
                    row["opening"],
                    row["credited"],
                    row["availed"],
                    row["forfeited"],
                    row["encashed"],
                ),
                variant="ghost",
                size="1",
                color="var(--color-primary)",
                cursor="pointer",
            ),
            **_TD_STYLE,
        ),
    )


# ── Edit modal ───────────────────────────────────────────────────────

def _num_field(label: str, name: str, value: rx.Var, on_change) -> rx.Component:
    return rx.vstack(
        rx.text(label, font_size="0.8rem", font_weight="500"),
        rx.input(
            name=name,
            value=value.to_string(),  # type: ignore[attr-defined]
            on_change=on_change,
            type="number",
            step="0.5",
            font_size="0.875rem",
            width="100%",
        ),
        align="start",
        gap="0.2rem",
        width="100%",
    )


def _edit_modal() -> rx.Component:
    form_body = rx.vstack(
        rx.heading(
            "Edit Leave Balance",
            size="4",
            font_family="var(--font-sans)",
            margin_bottom="0.25rem",
        ),
        rx.hstack(
            rx.text("Employee:", font_size="0.85rem", color="var(--color-muted)"),
            rx.text(LeaveBalanceAdminState.edit_username, font_size="0.85rem", font_weight="600"),
            rx.text("·", color="var(--color-muted)"),
            rx.text(LeaveBalanceAdminState.edit_leave_type, font_size="0.85rem", font_weight="600"),
            rx.text("·", color="var(--color-muted)"),
            rx.text(LeaveBalanceAdminState.edit_ay_name, font_size="0.85rem"),
            gap="0.35rem",
            align="center",
            flex_wrap="wrap",
            margin_bottom="1rem",
        ),
        rx.form(
            rx.grid(
                _num_field("Opening Balance", "f_opening", LeaveBalanceAdminState.edit_opening, LeaveBalanceAdminState.set_edit_opening),
                _num_field("Credited", "f_credited", LeaveBalanceAdminState.edit_credited, LeaveBalanceAdminState.set_edit_credited),
                _num_field("Availed", "f_availed", LeaveBalanceAdminState.edit_availed, LeaveBalanceAdminState.set_edit_availed),
                _num_field("Forfeited", "f_forfeited", LeaveBalanceAdminState.edit_forfeited, LeaveBalanceAdminState.set_edit_forfeited),
                _num_field("Encashed", "f_encashed", LeaveBalanceAdminState.edit_encashed, LeaveBalanceAdminState.set_edit_encashed),
                columns="2",
                gap="0.75rem",
                width="100%",
            ),
            rx.hstack(
                rx.text("Closing Balance:", font_size="0.85rem", color="var(--color-muted)"),
                rx.text(
                    LeaveBalanceAdminState.computed_closing.to_string(),  # type: ignore[attr-defined]
                    font_size="0.9rem",
                    font_weight="700",
                    color=rx.cond(
                        LeaveBalanceAdminState.is_save_valid,
                        "var(--color-success-border)",
                        "var(--color-destructive)",
                    ),
                ),
                gap="0.5rem",
                align="center",
                margin_top="0.5rem",
                margin_bottom="1rem",
            ),
            rx.hstack(
                secondary_btn("Cancel", on_click=LeaveBalanceAdminState.close_edit_modal, type="button"),
                primary_btn(
                    "Save Changes",
                    type="submit",
                    disabled=~LeaveBalanceAdminState.is_save_valid,
                    opacity=rx.cond(LeaveBalanceAdminState.is_save_valid, "1", "0.5"),
                ),
                gap="0.75rem",
                justify="end",
                width="100%",
            ),
            on_submit=LeaveBalanceAdminState.submit_edit,
            reset_on_submit=False,
        ),
        align="start",
        width="100%",
        gap="0",
    )

    return form_modal(
        content=form_body,
        is_open=LeaveBalanceAdminState.show_edit_modal,
        max_width="540px",
    )


# ── Page root ────────────────────────────────────────────────────────

def admin_leave_balance_edit() -> rx.Component:
    content = rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.heading(
                    "Leave Balance Admin",
                    size="5",
                    font_family="var(--font-sans)",
                ),
                rx.spacer(),
                align="center",
                width="100%",
                margin_bottom="1.5rem",
            ),
            config_toast(
                LeaveBalanceAdminState.flash,
                LeaveBalanceAdminState.flash_type,
                LeaveBalanceAdminState.dismiss_flash,
            ),
            _filter_bar(),
            _results_table(),
            _edit_modal(),
            padding="2rem",
            max_width="1200px",
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
