"""CL Credit Policy admin page — /admin/leave/credit-policy (M8.1 TD-036)."""

import reflex as rx

from durgam.pages.components import (
    config_toast,
    form_modal,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.leave_credit_policy import LeaveCreditPolicyState


_COLUMNS: list[TableColumn] = [
    TableColumn(key="leave_type",               label="Leave Type"),
    TableColumn(key="vacation_entitlement",     label="Vacation Entitlement (days)"),
    TableColumn(key="non_vacation_entitlement", label="Non-Vacation Entitlement (days)"),
    TableColumn(key="enabled_label",            label="Enabled"),
]


def _edit_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading("Edit CL Credit Policy", size="4", font_family="var(--font-sans)"),
            rx.form(
                rx.vstack(
                    rx.input(
                        type="hidden",
                        name="editing_id",
                        value=LeaveCreditPolicyState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Vacation Entitlement (days) *",
                                font_size="0.85rem", font_weight="500"),
                        rx.input(
                            name="form_vacation_entitlement",
                            placeholder="e.g. 10.0",
                            value=LeaveCreditPolicyState.form_vacation_entitlement,
                            on_change=LeaveCreditPolicyState.set_form_vacation_entitlement,
                            size="2",
                            width="100%",
                        ),
                        gap="0.25rem", align="start", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Non-Vacation Entitlement (days) *",
                                font_size="0.85rem", font_weight="500"),
                        rx.input(
                            name="form_non_vacation_entitlement",
                            placeholder="e.g. 12.0",
                            value=LeaveCreditPolicyState.form_non_vacation_entitlement,
                            on_change=LeaveCreditPolicyState.set_form_non_vacation_entitlement,
                            size="2",
                            width="100%",
                        ),
                        gap="0.25rem", align="start", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Enabled", font_size="0.85rem", font_weight="500"),
                        rx.checkbox(
                            checked=LeaveCreditPolicyState.form_enabled,
                            on_change=LeaveCreditPolicyState.set_form_enabled,
                            name="form_enabled",
                        ),
                        gap="0.25rem", align="start", width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=LeaveCreditPolicyState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                        justify="end",
                        width="100%",
                    ),
                    gap="1rem", align="start", width="100%",
                ),
                on_submit=LeaveCreditPolicyState.save_policy,
                reset_on_submit=False,
                width="100%",
            ),
            gap="1rem", align="start", width="100%",
        ),
        is_open=LeaveCreditPolicyState.show_form,
    )


def _policies_table() -> rx.Component:
    def _row_actions(item: dict) -> rx.Component:
        return primary_btn(
            "Edit",
            on_click=LeaveCreditPolicyState.open_edit(item["id"]),  # type: ignore[arg-type]
            size="1",
        )

    def _enriched_row(item: dict) -> dict:
        return item

    return rx.cond(
        LeaveCreditPolicyState.loading,
        rx.center(rx.spinner(), padding="2rem"),
        rx.vstack(
            rx.foreach(
                LeaveCreditPolicyState.policies,
                lambda item: rx.hstack(
                    rx.text(item["leave_type"], font_weight="600", min_width="6rem"),
                    rx.text(item["vacation_entitlement"].to_string(),
                            min_width="10rem"),
                    rx.text(item["non_vacation_entitlement"].to_string(),
                            min_width="12rem"),
                    rx.cond(
                        item["enabled"],
                        rx.badge("Yes", color_scheme="green"),
                        rx.badge("No", color_scheme="gray"),
                    ),
                    primary_btn(
                        "Edit",
                        on_click=LeaveCreditPolicyState.open_edit(item["id"]),  # type: ignore[arg-type]
                        size="1",
                    ),
                    gap="1.5rem",
                    align="center",
                    padding="0.75rem",
                    border="1px solid var(--color-rule)",
                    border_radius="6px",
                    background="var(--color-surface)",
                    width="100%",
                ),
            ),
            rx.cond(
                LeaveCreditPolicyState.policies.length() == 0,
                rx.text(
                    "No credit policies configured. Run the seed script to bootstrap.",
                    color="var(--color-muted)",
                    font_size="0.9rem",
                ),
                rx.fragment(),
            ),
            gap="0.5rem",
            width="100%",
        ),
    )


def admin_leave_credit_policy() -> rx.Component:
    return rx.cond(
        LeaveCreditPolicyState.admin_authorized,
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.vstack(
                    rx.heading(
                        "CL Credit Policy",
                        size="6",
                        font_family="var(--font-sans)",
                        font_weight="700",
                        color="var(--color-primary)",
                    ),
                    rx.text(
                        "Configure annual CL entitlement credited by the credit_annual_cl task on Jan 1.",
                        font_size="0.9rem",
                        color="var(--color-muted)",
                    ),
                    _policies_table(),
                    _edit_form(),
                    config_toast(
                        LeaveCreditPolicyState.flash,
                        LeaveCreditPolicyState.flash_type,
                        LeaveCreditPolicyState.dismiss_flash,
                    ),
                    gap="1.5rem",
                    align="start",
                    width="100%",
                    max_width="900px",
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
