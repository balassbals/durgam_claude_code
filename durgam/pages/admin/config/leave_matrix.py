"""Leave Sanction Matrix admin page — /admin/config/leave-sanction-matrix (M8 Phase 8)."""

import reflex as rx

from durgam.pages.components import (
    app_shell,
    config_toast,
    destructive_btn,
    form_modal,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.auth import AuthState
from durgam.states.config_leave_matrix import LeaveMatrixState

_LEAVE_TYPE_CHOICES = ["CL", "SCL", "EL", "HPL", "CML", "EOL", "ML", "SL", "*"]

_COLUMNS: list[TableColumn] = [
    TableColumn(key="leave_type",           label="Leave Type"),
    TableColumn(key="applicant_role_code",  label="Applicant Role"),
    TableColumn(key="sanctioner_role_code", label="Sanctioner Role"),
    TableColumn(key="recommend_via",        label="Recommend Via", hidden_on_card=True),
    TableColumn(key="requires_in_charge",   label="In-Charge Reqd?", hidden_on_card=True),
    TableColumn(key="scope_type",           label="Scope",         hidden_on_card=True),
    TableColumn(key="priority",             label="Priority",      hidden_on_card=True),
    TableColumn(key="notes",                label="Notes",         hidden_on_card=True),
]


def _leave_type_opt(code: str) -> rx.Component:
    return rx.select.item(code, value=code)


def _kebab(row: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.button(
            rx.icon("pencil", size=14),
            on_click=LeaveMatrixState.open_edit(row["id"]),
            variant="ghost",
            size="1",
            cursor="pointer",
            aria_label="Edit rule",
        ),
        rx.button(
            rx.icon("trash-2", size=14),
            on_click=LeaveMatrixState.open_delete_confirm(row["id"]),
            variant="ghost",
            size="1",
            cursor="pointer",
            color="var(--color-destructive)",
            aria_label="Delete rule",
        ),
        gap="0.25rem",
    )


def _inline_form() -> rx.Component:
    form_body = rx.vstack(
        rx.heading(
            rx.cond(LeaveMatrixState.edit_mode, "Edit Rule", "New Rule"),
            size="4",
            font_family="var(--font-sans)",
        ),
        rx.form(
            rx.vstack(
                # Leave type
                rx.vstack(
                    rx.text("Leave Type *", font_size="0.85rem", font_weight="500"),
                    rx.select.root(
                        rx.select.trigger(placeholder="Select leave type"),
                        rx.select.content(
                            *[rx.select.item(t, value=t) for t in _LEAVE_TYPE_CHOICES]
                        ),
                        value=LeaveMatrixState.form_leave_type,
                        on_change=LeaveMatrixState.set_form_leave_type,
                        size="2",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Applicant role
                rx.vstack(
                    rx.text("Applicant Role Code *", font_size="0.85rem", font_weight="500"),
                    rx.input(
                        name="form_applicant_role_code",
                        placeholder="e.g. FACULTY or *",
                        value=LeaveMatrixState.form_applicant_role_code,
                        on_change=LeaveMatrixState.set_form_applicant_role_code,
                        size="2",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Sanctioner role
                rx.vstack(
                    rx.text("Sanctioner Role Code *", font_size="0.85rem", font_weight="500"),
                    rx.input(
                        name="form_sanctioner_role_code",
                        placeholder="e.g. HOD",
                        value=LeaveMatrixState.form_sanctioner_role_code,
                        on_change=LeaveMatrixState.set_form_sanctioner_role_code,
                        size="2",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Recommend via
                rx.vstack(
                    rx.text("Recommend Via (optional)", font_size="0.85rem", font_weight="500"),
                    rx.input(
                        name="form_recommend_via_role_code",
                        placeholder="e.g. DIRECTOR for SCL",
                        value=LeaveMatrixState.form_recommend_via_role_code,
                        on_change=LeaveMatrixState.set_form_recommend_via_role_code,
                        size="2",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Requires in-charge
                rx.hstack(
                    rx.checkbox(
                        checked=LeaveMatrixState.form_requires_in_charge,
                        on_change=LeaveMatrixState.set_form_requires_in_charge,
                    ),
                    rx.text("Requires in-charge designation", font_size="0.85rem"),
                    gap="0.5rem",
                    align="center",
                ),
                # Scope type
                rx.vstack(
                    rx.text("Scope Type (optional)", font_size="0.85rem", font_weight="500"),
                    rx.input(
                        name="form_scope_type",
                        placeholder="e.g. department (leave blank for universitywide)",
                        value=LeaveMatrixState.form_scope_type,
                        on_change=LeaveMatrixState.set_form_scope_type,
                        size="2",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Priority
                rx.vstack(
                    rx.text("Priority", font_size="0.85rem", font_weight="500"),
                    rx.input(
                        name="form_priority",
                        type="number",
                        placeholder="100",
                        value=LeaveMatrixState.form_priority,
                        on_change=LeaveMatrixState.set_form_priority,
                        size="2",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Notes
                rx.vstack(
                    rx.text("Notes (optional)", font_size="0.85rem", font_weight="500"),
                    rx.text_area(
                        name="form_notes",
                        value=LeaveMatrixState.form_notes,
                        on_change=LeaveMatrixState.set_form_notes,
                        placeholder="Human-readable description of this rule",
                        rows="2",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Buttons
                rx.hstack(
                    primary_btn("Save", type="submit"),
                    secondary_btn("Cancel", on_click=LeaveMatrixState.close_form, type="button"),
                    gap="0.75rem",
                    justify="end",
                    width="100%",
                ),
                gap="1rem",
                width="100%",
                align="start",
            ),
            on_submit=LeaveMatrixState.submit_form,
            reset_on_submit=False,
            width="100%",
        ),
        gap="1rem",
        align="start",
        width="100%",
    )

    return form_modal(
        content=form_body,
        is_open=LeaveMatrixState.is_open,
        max_width="560px",
    )


def admin_leave_sanction_matrix() -> rx.Component:
    page_content = app_shell(
        rx.fragment(
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        "Leave Sanction Matrix",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    primary_btn(
                        rx.icon("plus", size=14),
                        " Create Rule",
                        on_click=LeaveMatrixState.open_create,
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    LeaveMatrixState.flash,
                    LeaveMatrixState.flash_type,
                    LeaveMatrixState.dismiss_flash,
                ),
                rx.cond(
                    LeaveMatrixState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=LeaveMatrixState.rules,
                        columns=_COLUMNS,
                        card_primary_key="leave_type",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No rules configured. Create the first rule above.",
                    ),
                ),
                align="start",
                width="100%",
            ),
            _inline_form(),
            # Delete confirmation
            confirmation_dialog(
                is_open=LeaveMatrixState.confirm_open,
                title="Delete this rule?",
                body=rx.text(
                    "This will soft-delete: ",
                    rx.text(LeaveMatrixState.deleting_rule_label, font_weight="600", as_="span"),
                    ". Leave requests already submitted are unaffected.",
                ),
                on_confirm=LeaveMatrixState.soft_delete,
                on_cancel=LeaveMatrixState.cancel_delete,
                confirm_label="Delete",
            ),
        ),
        container="lg",
    )

    return rx.cond(
        AuthState.current_user_id != "",
        page_content,
        rx.fragment(),
    )
