"""Leave Balance Import admin page — /admin/leave/balance-import (M8.1 E-016)."""

import reflex as rx

from durgam.pages.components import (
    config_toast,
    form_modal,
    nav_shell,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.file_upload import file_upload_zone
from durgam.states.leave_balance_import import LeaveBalanceImportState

_LEAVE_TYPES = ["CL", "SCL", "EL", "HPL", "CML", "EOL", "ML", "SL"]

_ROW_STYLE = {
    "padding": "0.5rem 0.75rem",
    "border": "1px solid var(--color-rule)",
    "border_radius": "4px",
    "width": "100%",
    "font_size": "0.85rem",
}
_HEADER_STYLE = {
    "padding": "0.4rem 0.75rem",
    "background": "var(--color-surface)",
    "border": "1px solid var(--color-rule)",
    "border_radius": "4px 4px 0 0",
    "width": "100%",
    "font_size": "0.8rem",
    "font_weight": "600",
    "color": "var(--color-muted)",
}


def _ay_banner() -> rx.Component:
    return rx.cond(
        LeaveBalanceImportState.ay_resolved,
        rx.box(
            rx.hstack(
                rx.text("Importing into AY:", font_weight="600", font_size="0.875rem"),
                rx.text(
                    LeaveBalanceImportState.resolved_ay_name,
                    font_weight="700",
                    font_size="0.875rem",
                    color="var(--color-success-border)",
                ),
                rx.text(
                    rx.text.span("(ID: ", color="var(--color-muted)"),
                    rx.text.span(LeaveBalanceImportState.resolved_ay_id,
                                 color="var(--color-muted)", font_size="0.75rem"),
                    rx.text.span(")", color="var(--color-muted)"),
                    font_size="0.75rem",
                ),
                gap="0.5rem",
                align="center",
                flex_wrap="wrap",
            ),
            background="var(--color-success-bg)",
            border="1px solid var(--color-success-border)",
            border_radius="6px",
            padding="0.75rem 1rem",
            width="100%",
        ),
        rx.box(
            rx.hstack(
                rx.text("⚠", font_size="1.1rem", color="var(--color-warning-border)"),
                rx.text(
                    "No unlocked academic year found. "
                    "Create or unlock an AY before importing.",
                    font_size="0.875rem",
                    color="var(--color-warning-border)",
                ),
                gap="0.5rem",
                align="center",
            ),
            background="var(--color-warning-bg)",
            border="1px solid var(--color-warning-border)",
            border_radius="6px",
            padding="0.75rem 1rem",
            width="100%",
        ),
    )


def _preview_invalid_table() -> rx.Component:
    return rx.cond(
        LeaveBalanceImportState.preview_invalid.length() > 0,
        rx.vstack(
            rx.hstack(
                rx.badge(
                    LeaveBalanceImportState.preview_invalid.length().to_string()
                    + " invalid row(s) — fix CSV before committing",
                    color_scheme="red",
                ),
                padding_bottom="0.25rem",
            ),
            rx.box(
                rx.hstack(
                    rx.text("Row", min_width="3rem", font_size="0.8rem", font_weight="600"),
                    rx.text("Employee", min_width="10rem", font_size="0.8rem", font_weight="600"),
                    rx.text("Leave Type", min_width="6rem", font_size="0.8rem", font_weight="600"),
                    rx.text("Error", font_size="0.8rem", font_weight="600", flex="1"),
                    **_HEADER_STYLE,
                ),
            ),
            rx.foreach(
                LeaveBalanceImportState.preview_invalid,
                lambda row: rx.hstack(
                    rx.text(row["row"], min_width="3rem", font_size="0.85rem"),
                    rx.text(row["employee"], min_width="10rem", font_size="0.85rem"),
                    rx.text(row["leave_type"], min_width="6rem", font_size="0.85rem"),
                    rx.text(
                        row["error"],
                        flex="1",
                        font_size="0.85rem",
                        color="var(--color-error-border)",
                    ),
                    background="var(--color-error-bg)",
                    **_ROW_STYLE,
                ),
            ),
            gap="0",
            align="start",
            width="100%",
            overflow_x="auto",
        ),
        rx.fragment(),
    )


def _preview_valid_table() -> rx.Component:
    return rx.cond(
        LeaveBalanceImportState.preview_valid.length() > 0,
        rx.vstack(
            rx.hstack(
                rx.badge(
                    LeaveBalanceImportState.preview_valid.length().to_string()
                    + " valid row(s)",
                    color_scheme="green",
                ),
                padding_bottom="0.25rem",
            ),
            rx.box(
                rx.hstack(
                    rx.text("Row", min_width="3rem", font_size="0.8rem", font_weight="600"),
                    rx.text("Employee", min_width="10rem", font_size="0.8rem", font_weight="600"),
                    rx.text("Type", min_width="5rem", font_size="0.8rem", font_weight="600"),
                    rx.text("Opening", min_width="5rem", font_size="0.8rem", font_weight="600"),
                    rx.text("Credited", min_width="5rem", font_size="0.8rem", font_weight="600"),
                    rx.text("Availed", min_width="5rem", font_size="0.8rem", font_weight="600"),
                    rx.text("Closing", min_width="5rem", font_size="0.8rem", font_weight="600"),
                    **_HEADER_STYLE,
                ),
            ),
            rx.foreach(
                LeaveBalanceImportState.preview_valid,
                lambda row: rx.hstack(
                    rx.text(row["row"], min_width="3rem", font_size="0.85rem"),
                    rx.text(row["employee"], min_width="10rem", font_size="0.85rem"),
                    rx.text(row["leave_type"], min_width="5rem", font_size="0.85rem"),
                    rx.text(row["opening"], min_width="5rem", font_size="0.85rem"),
                    rx.text(row["credited"], min_width="5rem", font_size="0.85rem"),
                    rx.text(row["availed"], min_width="5rem", font_size="0.85rem"),
                    rx.text(row["closing"], min_width="5rem", font_size="0.85rem"),
                    background="var(--color-success-bg)",
                    **_ROW_STYLE,
                ),
            ),
            gap="0",
            align="start",
            width="100%",
            overflow_x="auto",
        ),
        rx.fragment(),
    )


def _preview_area() -> rx.Component:
    return rx.cond(
        LeaveBalanceImportState.preview_ready,
        rx.vstack(
            _preview_invalid_table(),
            _preview_valid_table(),
            rx.hstack(
                primary_btn(
                    "Commit Import",
                    on_click=LeaveBalanceImportState.commit_import,
                    disabled=~LeaveBalanceImportState.commit_enabled,
                    opacity=rx.cond(LeaveBalanceImportState.commit_enabled, "1", "0.5"),
                ),
                secondary_btn(
                    "Reset",
                    on_click=LeaveBalanceImportState.reset_import,
                    type="button",
                ),
                gap="0.75rem",
                margin_top="0.5rem",
            ),
            gap="0.75rem",
            align="start",
            width="100%",
        ),
        rx.fragment(),
    )


def _import_complete_banner() -> rx.Component:
    return rx.cond(
        LeaveBalanceImportState.import_complete,
        rx.box(
            rx.hstack(
                rx.text("✓", color="var(--color-success-border)", font_size="1.1rem"),
                rx.text(
                    "Successfully processed ",
                    rx.text.span(
                        LeaveBalanceImportState.import_success_count.to_string(),
                        font_weight="700",
                    ),
                    " balance record(s).",
                    font_size="0.9rem",
                ),
                secondary_btn(
                    "Import Another",
                    on_click=LeaveBalanceImportState.reset_import,
                    type="button",
                    size="1",
                ),
                gap="0.75rem",
                align="center",
            ),
            background="var(--color-success-bg)",
            border="1px solid var(--color-success-border)",
            border_radius="6px",
            padding="0.75rem 1rem",
            width="100%",
        ),
        rx.fragment(),
    )


def _field_row(label: str, name: str, value, setter, placeholder: str = "0.0") -> rx.Component:
    return rx.vstack(
        rx.text(label, font_size="0.85rem", font_weight="500"),
        rx.input(
            name=name,
            type="number",
            step="0.5",
            value=value,
            on_change=setter,
            placeholder=placeholder,
            size="2",
            width="100%",
        ),
        gap="0.25rem",
        align="start",
        width="100%",
    )


def _single_form_modal() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                "Set / Update Employee Balance",
                size="4",
                font_family="var(--font-sans)",
            ),
            rx.form(
                rx.vstack(
                    # Hidden inputs to pass select values into form_data
                    rx.input(
                        type="hidden",
                        name="form_employee_username",
                        value=LeaveBalanceImportState.form_employee_username,
                    ),
                    rx.input(
                        type="hidden",
                        name="form_leave_type",
                        value=LeaveBalanceImportState.form_leave_type,
                    ),
                    # Employee selector
                    rx.vstack(
                        rx.text("Employee *", font_size="0.85rem", font_weight="500"),
                        rx.select.root(
                            rx.select.trigger(
                                placeholder="Select employee",
                                width="100%",
                            ),
                            rx.select.content(
                                rx.foreach(
                                    LeaveBalanceImportState.employees,
                                    lambda emp: rx.select.item(
                                        emp["display"], value=emp["username"]
                                    ),
                                ),
                            ),
                            value=LeaveBalanceImportState.form_employee_username,
                            on_value_change=LeaveBalanceImportState.set_form_employee_username,
                            width="100%",
                        ),
                        gap="0.25rem",
                        align="start",
                        width="100%",
                    ),
                    # Leave type selector
                    rx.vstack(
                        rx.text("Leave Type *", font_size="0.85rem", font_weight="500"),
                        rx.select.root(
                            rx.select.trigger(
                                placeholder="Select leave type",
                                width="100%",
                            ),
                            rx.select.content(
                                rx.select.item("CL – Casual Leave", value="CL"),
                                rx.select.item("SCL – Special Casual Leave", value="SCL"),
                                rx.select.item("EL – Earned Leave", value="EL"),
                                rx.select.item("HPL – Half Pay Leave", value="HPL"),
                                rx.select.item("CML – Commuted Leave", value="CML"),
                                rx.select.item("EOL – Extra Ordinary Leave", value="EOL"),
                                rx.select.item("ML – Maternity Leave", value="ML"),
                                rx.select.item("SL – Study Leave", value="SL"),
                            ),
                            value=LeaveBalanceImportState.form_leave_type,
                            on_value_change=LeaveBalanceImportState.set_form_leave_type,
                            width="100%",
                        ),
                        gap="0.25rem",
                        align="start",
                        width="100%",
                    ),
                    # Numeric balance fields
                    _field_row(
                        "Opening Balance",
                        "form_opening",
                        LeaveBalanceImportState.form_opening,
                        LeaveBalanceImportState.set_form_opening,
                    ),
                    _field_row(
                        "Credited",
                        "form_credited",
                        LeaveBalanceImportState.form_credited,
                        LeaveBalanceImportState.set_form_credited,
                    ),
                    _field_row(
                        "Availed",
                        "form_availed",
                        LeaveBalanceImportState.form_availed,
                        LeaveBalanceImportState.set_form_availed,
                    ),
                    _field_row(
                        "Forfeited",
                        "form_forfeited",
                        LeaveBalanceImportState.form_forfeited,
                        LeaveBalanceImportState.set_form_forfeited,
                    ),
                    _field_row(
                        "Encashed",
                        "form_encashed",
                        LeaveBalanceImportState.form_encashed,
                        LeaveBalanceImportState.set_form_encashed,
                    ),
                    rx.text(
                        "Closing = Opening + Credited − Availed − Forfeited − Encashed "
                        "(computed server-side).",
                        font_size="0.75rem",
                        color="var(--color-muted)",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=LeaveBalanceImportState.cancel_single_form,
                            type="button",
                        ),
                        gap="0.75rem",
                        justify="end",
                        width="100%",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=LeaveBalanceImportState.submit_single_form,
                reset_on_submit=False,
                width="100%",
            ),
            gap="1rem",
            align="start",
            width="100%",
        ),
        is_open=LeaveBalanceImportState.show_single_form,
        max_width="560px",
    )


def admin_leave_balance_import() -> rx.Component:
    return rx.cond(
        LeaveBalanceImportState.admin_authorized,
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.vstack(
                    rx.heading(
                        "Leave Balance Import",
                        size="6",
                        font_family="var(--font-sans)",
                        font_weight="700",
                        color="var(--color-primary)",
                    ),
                    rx.text(
                        "Import legacy leave balances from a CSV file, or enter records manually.",
                        font_size="0.9rem",
                        color="var(--color-muted)",
                    ),

                    # AY status banner
                    _ay_banner(),

                    # ── CSV Bulk Import section ────────────────────────────────
                    rx.heading(
                        "CSV Bulk Import",
                        size="4",
                        font_family="var(--font-sans)",
                        font_weight="600",
                        margin_top="0.5rem",
                    ),
                    rx.text(
                        "Upload a 7-column CSV: employee_username, leave_type, "
                        "opening_balance, credited, availed, forfeited, encashed.",
                        font_size="0.85rem",
                        color="var(--color-muted)",
                    ),

                    file_upload_zone(
                        on_drop=LeaveBalanceImportState.upload_csv,
                        accept={"text/csv": [".csv"], "application/vnd.ms-excel": [".csv"]},
                        label="Drag & drop CSV file here, or click to browse",
                    ),

                    _preview_area(),
                    _import_complete_banner(),

                    # ── Per-employee section ───────────────────────────────────
                    rx.divider(margin_y="0.5rem"),
                    rx.heading(
                        "Per-Employee Entry",
                        size="4",
                        font_family="var(--font-sans)",
                        font_weight="600",
                    ),
                    rx.text(
                        "Set or update a single employee's leave balance for the active AY.",
                        font_size="0.85rem",
                        color="var(--color-muted)",
                    ),
                    primary_btn(
                        "+ Add / Update Balance",
                        on_click=LeaveBalanceImportState.open_single_form,
                    ),

                    _single_form_modal(),

                    config_toast(
                        LeaveBalanceImportState.flash,
                        LeaveBalanceImportState.flash_type,
                        LeaveBalanceImportState.dismiss_flash,
                    ),

                    gap="1rem",
                    align="start",
                    width="100%",
                    max_width="960px",
                ),
                padding="2rem",
                width="100%",
            ),
            align="start",
            width="100%",
            min_height="100vh",
        ),
        rx.fragment(),
    )
