"""My Leave page — balance cards, in-flight requests, history, and Apply modal."""

import reflex as rx

from durgam.pages.components import (
    config_toast,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.states.auth import AuthState
from durgam.states.leave_request import LEAVE_TYPE_OPTIONS, LeavePageState


# ── Leave-type display helper ────────────────────────────────────────

_LEAVE_TYPE_LABELS: dict[str, str] = dict(LEAVE_TYPE_OPTIONS)


def _leave_type_label(code: rx.Var) -> rx.Component:
    return rx.match(
        code,
        ("CL",  rx.text("Casual Leave",          display="inline")),
        ("SCL", rx.text("Special Casual Leave",   display="inline")),
        ("EL",  rx.text("Earned Leave",           display="inline")),
        ("HPL", rx.text("Half Pay Leave",         display="inline")),
        ("CML", rx.text("Commuted Leave",         display="inline")),
        ("EOL", rx.text("Extraordinary Leave",    display="inline")),
        ("ML",  rx.text("Maternity Leave",        display="inline")),
        ("SL",  rx.text("Study Leave",            display="inline")),
        rx.text(code, display="inline"),
    )


def _state_badge(state_val: rx.Var) -> rx.Component:
    return rx.match(
        state_val,
        ("submitted", rx.badge("Submitted",    color_scheme="blue")),
        ("in_review", rx.badge("In Review",    color_scheme="orange")),
        ("approved",  rx.badge("Approved",     color_scheme="green")),
        ("rejected",  rx.badge("Rejected",     color_scheme="red")),
        ("withdrawn", rx.badge("Withdrawn",    color_scheme="gray")),
        ("cancelled", rx.badge("Cancelled",    color_scheme="gray")),
        rx.badge(state_val),
    )


# ── Balance cards ────────────────────────────────────────────────────

def _balance_card(bal: rx.Var) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading(bal["leave_type"], size="3", font_family="var(--font-sans)"),
                rx.spacer(),
                rx.cond(
                    bal["is_no_balance_type"],
                    rx.badge(
                        "As per approval",
                        color_scheme="gray",
                        radius="medium",
                        size="2",
                    ),
                    rx.badge(
                        rx.text(bal["closing"], as_="span"),
                        rx.text(" days", as_="span", font_size="0.75rem"),
                        color_scheme="indigo",
                        radius="medium",
                        size="2",
                    ),
                ),
                align="center",
                width="100%",
            ),
            rx.cond(
                bal["is_no_balance_type"],
                rx.text(
                    "Granted on a case-by-case basis — no running balance.",
                    font_size="0.75rem",
                    color="var(--color-muted)",
                ),
                rx.grid(
                    rx.text("Opening", font_size="0.75rem", color="var(--color-muted)"),
                    rx.text(bal["opening"], font_size="0.75rem", text_align="right"),
                    rx.text("Credited", font_size="0.75rem", color="var(--color-muted)"),
                    rx.text(bal["credited"], font_size="0.75rem", text_align="right"),
                    rx.text("Availed", font_size="0.75rem", color="var(--color-muted)"),
                    rx.text(bal["availed"], font_size="0.75rem", text_align="right"),
                    rx.text("Forfeited", font_size="0.75rem", color="var(--color-muted)"),
                    rx.text(bal["forfeited"], font_size="0.75rem", text_align="right"),
                    columns="2",
                    gap="0.25rem",
                    width="100%",
                ),
            ),
            gap="0.5rem",
            align="start",
            width="100%",
        ),
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="1rem",
        min_width="180px",
    )


def _balance_section() -> rx.Component:
    return rx.box(
        rx.text(
            "Leave Balances",
            font_weight="600",
            font_size="0.95rem",
            font_family="var(--font-sans)",
            color="var(--color-text)",
            margin_bottom="0.75rem",
        ),
        rx.cond(
            LeavePageState.balances.length() > 0,  # type: ignore[attr-defined]
            rx.flex(
                rx.foreach(LeavePageState.balances, _balance_card),
                gap="1rem",
                flex_wrap="wrap",
            ),
            rx.text(
                "No leave balances on record for this academic year.",
                color="var(--color-muted)",
                font_size="0.875rem",
            ),
        ),
        margin_bottom="2rem",
    )


# ── In-flight requests ───────────────────────────────────────────────

def _in_flight_row(row: rx.Var) -> rx.Component:
    return rx.box(
        rx.flex(
            _leave_type_label(row["leave_type"]),
            rx.text(row["starts_on"], font_size="0.85rem", color="var(--color-muted)"),
            rx.text("→", font_size="0.85rem", color="var(--color-muted)"),
            rx.text(row["ends_on"], font_size="0.85rem", color="var(--color-muted)"),
            rx.text(row["chargeable_days"], font_size="0.85rem"),
            rx.text("days", font_size="0.85rem", color="var(--color-muted)"),
            _state_badge(row["state"]),
            rx.spacer(),
            rx.cond(
                row["state"] == "submitted",
                rx.button(
                    "Withdraw",
                    on_click=LeavePageState.withdraw_leave(row["id"]),
                    variant="ghost",
                    size="1",
                    color="var(--color-destructive)",
                    cursor="pointer",
                ),
                rx.fragment(),
            ),
            rx.cond(
                row["within_withdraw_window"],
                rx.button(
                    "Withdraw (post-approval)",
                    on_click=LeavePageState.open_withdraw_modal(row["id"]),
                    variant="ghost",
                    size="1",
                    color="var(--color-destructive)",
                    cursor="pointer",
                ),
                rx.fragment(),
            ),
            wrap="wrap",
            gap="0.5rem",
            align="center",
            width="100%",
        ),
        rx.cond(
            row["progress_text"] != "",
            rx.text(
                "Progress: ",
                rx.text(row["progress_text"], as_="span", font_weight="500"),
                font_size="0.8rem",
                color="var(--color-muted)",
                margin_top="0.35rem",
            ),
            rx.fragment(),
        ),
        padding="0.75rem",
        border="1px solid var(--color-rule)",
        border_radius="6px",
        background="white",
        width="100%",
    )


def _in_flight_section() -> rx.Component:
    return rx.box(
        rx.text(
            "In-Flight Requests",
            font_weight="600",
            font_size="0.95rem",
            font_family="var(--font-sans)",
            color="var(--color-text)",
            margin_bottom="0.75rem",
        ),
        rx.cond(
            LeavePageState.in_flight.length() > 0,  # type: ignore[attr-defined]
            rx.vstack(
                rx.foreach(LeavePageState.in_flight, _in_flight_row),
                width="100%",
                gap="0.5rem",
            ),
            rx.text(
                "No active leave requests.",
                color="var(--color-muted)",
                font_size="0.875rem",
            ),
        ),
        margin_bottom="2rem",
    )


# ── History ──────────────────────────────────────────────────────────

def _history_row(row: rx.Var) -> rx.Component:
    return rx.box(
        rx.flex(
            _leave_type_label(row["leave_type"]),
            rx.text(row["starts_on"], font_size="0.85rem", color="var(--color-muted)"),
            rx.text("→", font_size="0.85rem", color="var(--color-muted)"),
            rx.text(row["ends_on"], font_size="0.85rem", color="var(--color-muted)"),
            rx.text(row["chargeable_days"], font_size="0.85rem"),
            rx.text("days", font_size="0.85rem", color="var(--color-muted)"),
            _state_badge(row["state"]),
            wrap="wrap",
            gap="0.5rem",
            align="center",
            width="100%",
        ),
        rx.cond(
            row["history_text"] != "",
            rx.text(
                row["history_text"],
                font_size="0.8rem",
                color="var(--color-muted)",
                margin_top="0.35rem",
            ),
            rx.fragment(),
        ),
        padding="0.75rem",
        border="1px solid var(--color-rule)",
        border_radius="6px",
        background="white",
        width="100%",
    )


def _history_section() -> rx.Component:
    return rx.box(
        rx.text(
            "Request History",
            font_weight="600",
            font_size="0.95rem",
            font_family="var(--font-sans)",
            color="var(--color-text)",
            margin_bottom="0.75rem",
        ),
        rx.cond(
            LeavePageState.history.length() > 0,  # type: ignore[attr-defined]
            rx.vstack(
                rx.foreach(LeavePageState.history, _history_row),
                width="100%",
                gap="0.5rem",
            ),
            rx.text(
                "No past leave requests this academic year.",
                color="var(--color-muted)",
                font_size="0.875rem",
            ),
        ),
    )


# ── Withdraw-approved modal ──────────────────────────────────────────

def _withdraw_approved_modal() -> rx.Component:
    from durgam.pages.components import form_modal

    form_body = rx.vstack(
        rx.heading(
            "Withdraw Approved Leave",
            size="4",
            font_family="var(--font-sans)",
            margin_bottom="0.5rem",
        ),
        rx.text(
            "This will withdraw your approved leave request. Your balance will be "
            "adjusted for any unused days. This action cannot be undone.",
            font_size="0.875rem",
            color="var(--color-muted)",
            margin_bottom="1rem",
        ),
        rx.form(
            rx.vstack(
                rx.text(
                    "Reason for withdrawal",
                    font_size="0.875rem",
                    font_weight="500",
                ),
                rx.text_area(
                    name="withdraw_reason",
                    on_change=LeavePageState.set_withdraw_reason,
                    placeholder="Provide a reason (minimum 10 characters)...",
                    rows="4",
                    width="100%",
                ),
                rx.cond(
                    ~LeavePageState.withdraw_reason_valid,
                    rx.text(
                        "Reason must be at least 10 characters.",
                        font_size="0.75rem",
                        color="var(--color-destructive)",
                    ),
                    rx.fragment(),
                ),
                align="start",
                width="100%",
                gap="0.35rem",
                margin_bottom="1rem",
            ),
            rx.hstack(
                secondary_btn("Cancel", on_click=LeavePageState.close_withdraw_modal, type="button"),
                primary_btn(
                    "Confirm Withdrawal",
                    type="submit",
                    disabled=~LeavePageState.withdraw_reason_valid,
                    opacity=rx.cond(LeavePageState.withdraw_reason_valid, "1", "0.5"),
                ),
                gap="0.75rem",
                justify="end",
                width="100%",
            ),
            on_submit=LeavePageState.submit_withdrawal,
            reset_on_submit=False,
        ),
        align="start",
        width="100%",
        gap="0",
    )

    return form_modal(
        content=form_body,
        is_open=LeavePageState.show_withdraw_modal,
        max_width="480px",
    )


# ── Apply modal ──────────────────────────────────────────────────────

def _leave_type_option(opt: tuple) -> rx.Component:
    return rx.select.item(opt[1], value=opt[0])


def _apply_modal() -> rx.Component:
    from durgam.pages.components import form_modal

    form_body = rx.vstack(
        rx.heading("Apply for Leave", size="4", font_family="var(--font-sans)"),
        rx.form(
            rx.vstack(
                # Leave type
                rx.vstack(
                    rx.text("Leave Type", font_size="0.85rem", font_weight="500"),
                    rx.select.root(
                        rx.select.trigger(placeholder="Select leave type"),
                        rx.select.content(
                            rx.foreach(
                                list(LEAVE_TYPE_OPTIONS),
                                _leave_type_option,
                            ),
                        ),
                        value=LeavePageState.leave_type,
                        on_change=LeavePageState.set_leave_type,
                        size="2",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Date range
                rx.hstack(
                    rx.vstack(
                        rx.text("From", font_size="0.85rem", font_weight="500"),
                        rx.input(
                            type="date",
                            name="starts_on",
                            value=LeavePageState.starts_on,
                            on_change=LeavePageState.set_starts_on,
                            size="2",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        flex="1",
                    ),
                    rx.vstack(
                        rx.text("To", font_size="0.85rem", font_weight="500"),
                        rx.input(
                            type="date",
                            name="ends_on",
                            value=LeavePageState.ends_on,
                            on_change=LeavePageState.set_ends_on,
                            size="2",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        flex="1",
                    ),
                    gap="0.75rem",
                    width="100%",
                ),
                # Half-day toggle
                rx.vstack(
                    rx.hstack(
                        rx.checkbox(
                            checked=LeavePageState.half_day,
                            on_change=LeavePageState.set_half_day,
                        ),
                        rx.text("Half-day CL", font_size="0.85rem"),
                        gap="0.5rem",
                        align="center",
                    ),
                    rx.cond(
                        LeavePageState.half_day,
                        rx.select.root(
                            rx.select.trigger(placeholder="Which half?"),
                            rx.select.content(
                                rx.select.item("First half", value="first"),
                                rx.select.item("Last half",  value="last"),
                            ),
                            value=LeavePageState.half_day_which,
                            on_change=LeavePageState.set_half_day_which,
                            size="2",
                        ),
                        rx.fragment(),
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Preview panel (chargeable days + channel)
                rx.cond(
                    (LeavePageState.starts_on != "") & (LeavePageState.ends_on != ""),
                    rx.vstack(
                        rx.button(
                            "Preview days & channel",
                            on_click=LeavePageState.fetch_preview,
                            variant="soft",
                            size="1",
                            type="button",
                        ),
                        rx.cond(
                            LeavePageState.preview_days > 0,
                            rx.hstack(
                                rx.text(
                                    "Chargeable days: ",
                                    font_size="0.8rem",
                                    color="var(--color-muted)",
                                ),
                                rx.text(
                                    LeavePageState.preview_days,
                                    font_size="0.8rem",
                                    font_weight="600",
                                ),
                                rx.text(
                                    " | Channel: ",
                                    font_size="0.8rem",
                                    color="var(--color-muted)",
                                ),
                                rx.text(
                                    LeavePageState.preview_channel_label,
                                    font_size="0.8rem",
                                ),
                                gap="0",
                                flex_wrap="wrap",
                            ),
                            rx.cond(
                                LeavePageState.preview_channel_label != "",
                                rx.text(
                                    LeavePageState.preview_channel_label,
                                    font_size="0.8rem",
                                    color="var(--color-destructive)",
                                ),
                                rx.fragment(),
                            ),
                        ),
                        align="start",
                        gap="0.4rem",
                    ),
                    rx.fragment(),
                ),
                # Reason
                rx.vstack(
                    rx.text("Reason", font_size="0.85rem", font_weight="500"),
                    rx.text_area(
                        name="reason",
                        value=LeavePageState.reason,
                        on_change=LeavePageState.set_reason,
                        placeholder="Brief reason for leave...",
                        rows="3",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Address
                rx.vstack(
                    rx.text("Address During Leave", font_size="0.85rem", font_weight="500"),
                    rx.input(
                        placeholder="Optional",
                        value=LeavePageState.address_during_leave,
                        on_change=LeavePageState.set_address_during_leave,
                        size="2",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Checkboxes
                rx.hstack(
                    rx.checkbox(
                        checked=LeavePageState.headquarters_left,
                        on_change=LeavePageState.set_headquarters_left,
                    ),
                    rx.text("Out of station", font_size="0.85rem"),
                    gap="0.5rem",
                    align="center",
                ),
                rx.hstack(
                    rx.checkbox(
                        checked=LeavePageState.intended_outside_india,
                        on_change=LeavePageState.set_intended_outside_india,
                    ),
                    rx.text("Outside India", font_size="0.85rem"),
                    gap="0.5rem",
                    align="center",
                ),
                # Q-P10.2: Prof-tier opt-in HoD recommendation. Visible to all
                # faculty; only effective for Prof-tier (the requires_optin matrix
                # rule keys on prof/assoc_prof/sr_prof).
                rx.hstack(
                    rx.checkbox(
                        checked=LeavePageState.hod_recommend_optin,
                        on_change=LeavePageState.set_hod_recommend_optin,
                    ),
                    rx.text(
                        "Send through my HoD for recommendation",
                        font_size="0.85rem",
                    ),
                    gap="0.5rem",
                    align="center",
                ),
                # In-charge designation (Director only)
                rx.cond(
                    LeavePageState.is_director,
                    rx.vstack(
                        rx.text("In-Charge Designation", font_size="0.85rem", font_weight="500"),
                        rx.input(
                            placeholder="Name of faculty taking charge",
                            value=LeavePageState.in_charge_designation,
                            on_change=LeavePageState.set_in_charge_designation,
                            size="2",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Alternate arrangement
                rx.vstack(
                    rx.text("Alternate Arrangement", font_size="0.85rem", font_weight="500"),
                    rx.input(
                        placeholder="Optional — who covers your duties?",
                        value=LeavePageState.alternate_arrangement,
                        on_change=LeavePageState.set_alternate_arrangement,
                        size="2",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Error
                rx.cond(
                    LeavePageState.form_error != "",
                    rx.text(
                        LeavePageState.form_error,
                        color="var(--color-destructive)",
                        font_size="0.85rem",
                    ),
                    rx.fragment(),
                ),
                # Post-facto badge (informational only — does not block submission)
                rx.cond(
                    LeavePageState.is_past_dated,
                    rx.box(
                        rx.text(
                            "⚠ Post-facto application — this request covers past dates.",
                            color="var(--color-warning, #b45309)",
                            font_size="0.85rem",
                            font_weight="500",
                        ),
                        background="rgba(245, 158, 11, 0.08)",
                        border="1px solid rgba(245, 158, 11, 0.3)",
                        border_radius="0.375rem",
                        padding="0.5rem 0.75rem",
                        margin_bottom="0.5rem",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Actions
                rx.hstack(
                    primary_btn(
                        rx.cond(
                            LeavePageState.submitting,
                            rx.spinner(size="1"),
                            rx.text("Submit"),
                        ),
                        type="submit",
                        disabled=LeavePageState.submitting,
                    ),
                    secondary_btn(
                        "Cancel",
                        on_click=LeavePageState.close_modal,
                        type="button",
                    ),
                    gap="0.75rem",
                    justify="end",
                    width="100%",
                ),
                gap="1rem",
                width="100%",
                align="start",
            ),
            on_submit=LeavePageState.submit_leave,
            reset_on_submit=False,
            width="100%",
        ),
        gap="1rem",
        align="start",
        width="100%",
    )

    return form_modal(
        content=form_body,
        is_open=LeavePageState.show_modal,
        max_width="540px",
    )


# ── Page root ────────────────────────────────────────────────────────

def my_leave_page() -> rx.Component:
    content = rx.vstack(
        nav_shell(),
        rx.box(
            # Page header
            rx.hstack(
                rx.heading(
                    "My Leave",
                    size="5",
                    font_family="var(--font-sans)",
                ),
                rx.spacer(),
                primary_btn(
                    rx.icon("plus", size=14),
                    " Apply for Leave",
                    on_click=LeavePageState.open_modal,
                ),
                align="center",
                width="100%",
                margin_bottom="1.5rem",
            ),
            # Toast
            config_toast(
                LeavePageState.flash,
                LeavePageState.flash_type,
                LeavePageState.dismiss_flash,
            ),
            # Content
            rx.cond(
                LeavePageState.loading,
                rx.center(rx.spinner(), padding="3rem"),
                rx.vstack(
                    _balance_section(),
                    _in_flight_section(),
                    _history_section(),
                    align="start",
                    width="100%",
                ),
            ),
            padding="2rem",
            max_width="1100px",
            width="100%",
        ),
        page_footer(),
        _apply_modal(),
        _withdraw_approved_modal(),
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
