"""Purchase procedure rules management page — /admin/config/purchase-rules."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    config_toast,
    form_modal,
    nav_shell,
    page_footer,
    primary_btn,
    role_multi_select,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.config_purchase_rule import PurchaseRuleConfigState


def _kebab(row: dict) -> rx.Component:
    return rx.menu.root(
        rx.menu.trigger(
            rx.button(
                "⋮",
                background="transparent",
                border="none",
                cursor="pointer",
                font_size="1.2rem",
                color="var(--color-muted)",
                padding="0.1rem 0.4rem",
            )
        ),
        rx.menu.content(
            rx.menu.item(
                "Edit",
                on_click=PurchaseRuleConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["fund_source"], row["tier"],
                    row["raw_floor"], row["raw_ceiling"],
                    row["raw_min_quotes"], row["raw_quote_count"],
                    row["raw_discretion"], row["raw_comparative"],
                    row["raw_approvers"], row["raw_committee"],
                    row["notes"],
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=PurchaseRuleConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["tier"],
                ),
                color="var(--color-danger, #c0392b)",
            ),
        ),
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    PurchaseRuleConfigState.editing_id == "",
                    "New Purchase Procedure Rule",
                    "Edit Purchase Procedure Rule",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.input(type="hidden", name="editing_id",
                             value=PurchaseRuleConfigState.editing_id),
                    rx.vstack(
                        rx.text("Fund Source *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select fund source"),
                            rx.select.content(
                                rx.select.item("Institute", value="institute"),
                                rx.select.item("Projects / UGC", value="projects_ugc"),
                            ),
                            name="form_fund_source",
                            value=PurchaseRuleConfigState.form_fund_source,
                            on_change=PurchaseRuleConfigState.set_form_fund_source,
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text("Tier *", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(name="form_tier", type="number",
                                     value=PurchaseRuleConfigState.form_tier,
                                     on_change=PurchaseRuleConfigState.set_form_tier,
                                     width="100%"),
                            align="start", gap="0.25rem", width="50%",
                        ),
                        rx.vstack(
                            rx.text("Quote Count", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(name="form_quote_count", type="number",
                                     value=PurchaseRuleConfigState.form_quote_count,
                                     on_change=PurchaseRuleConfigState.set_form_quote_count,
                                     width="100%"),
                            align="start", gap="0.25rem", width="50%",
                        ),
                        width="100%", gap="1rem",
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text("Floor (INR) *", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(name="form_floor", type="number",
                                     value=PurchaseRuleConfigState.form_floor,
                                     on_change=PurchaseRuleConfigState.set_form_floor,
                                     width="100%"),
                            align="start", gap="0.25rem", width="50%",
                        ),
                        rx.vstack(
                            rx.text("Ceiling (INR)", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(name="form_ceiling",
                                     value=PurchaseRuleConfigState.form_ceiling,
                                     on_change=PurchaseRuleConfigState.set_form_ceiling,
                                     placeholder="Leave blank for no limit",
                                     width="100%"),
                            align="start", gap="0.25rem", width="50%",
                        ),
                        width="100%", gap="1rem",
                    ),
                    rx.hstack(
                        rx.checkbox(
                            "Min quotes required",
                            checked=PurchaseRuleConfigState.form_min_quotes,
                            on_change=PurchaseRuleConfigState.set_form_min_quotes,
                        ),
                        rx.checkbox(
                            "At discretion",
                            checked=PurchaseRuleConfigState.form_discretion,
                            on_change=PurchaseRuleConfigState.set_form_discretion,
                        ),
                        rx.checkbox(
                            "Comparative statement",
                            checked=PurchaseRuleConfigState.form_comparative,
                            on_change=PurchaseRuleConfigState.set_form_comparative,
                        ),
                        gap="1rem", flex_wrap="wrap",
                    ),
                    rx.vstack(
                        rx.text("Approving Authorities *", font_size="0.85rem", color="var(--color-muted)"),
                        role_multi_select(
                            options=PurchaseRuleConfigState.role_options,
                            selected_codes=PurchaseRuleConfigState.form_approvers_selected,
                            toggle_handler=PurchaseRuleConfigState.toggle_approver,
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Committee Level", font_size="0.85rem", color="var(--color-muted)"),
                        rx.select.root(
                            rx.select.trigger(placeholder="None"),
                            rx.select.content(
                                rx.select.item("None", value="__none__"),
                                rx.select.item("Campus Purchase Committee", value="campus_purchase_committee"),
                                rx.select.item("Central Purchase Committee", value="central_purchase_committee"),
                            ),
                            name="form_committee",
                            value=PurchaseRuleConfigState.form_committee,
                            on_change=PurchaseRuleConfigState.set_form_committee,
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Notes", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(name="form_notes",
                                     value=PurchaseRuleConfigState.form_notes,
                                     on_change=PurchaseRuleConfigState.set_form_notes,
                                     placeholder="Optional notes",
                                     width="100%", rows="2"),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn("Cancel",
                                      on_click=PurchaseRuleConfigState.cancel_form,
                                      type="button"),
                        gap="0.75rem",
                    ),
                    gap="1rem", align="start", width="100%",
                ),
                on_submit=PurchaseRuleConfigState.save_rule,
                reset_on_submit=False,
            ),
            gap="0", align="start", width="100%",
        ),
        is_open=PurchaseRuleConfigState.show_form,
        max_width="600px",
    )


def admin_config_purchase_rules() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading("Purchase Procedure Rules", size="5",
                               font_family="var(--font-sans)"),
                    rx.spacer(),
                    primary_btn("+ Add Rule",
                                on_click=PurchaseRuleConfigState.open_create),
                    align="center", width="100%", margin_bottom="1rem",
                ),
                config_toast(
                    PurchaseRuleConfigState.flash,
                    PurchaseRuleConfigState.flash_type,
                    PurchaseRuleConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    PurchaseRuleConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=PurchaseRuleConfigState.rules,
                        columns=[
                            TableColumn(key="fund_source", label="Fund Source"),
                            TableColumn(key="tier", label="Tier"),
                            TableColumn(key="floor", label="Floor"),
                            TableColumn(key="ceiling", label="Ceiling"),
                            TableColumn(key="quotes", label="Quotes"),
                            TableColumn(key="comparative", label="Comparative"),
                            TableColumn(key="approvers", label="Approver"),
                            TableColumn(key="committee", label="Committee"),
                        ],
                        card_primary_key="fund_source",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No purchase procedure rules configured.",
                    ),
                ),
                confirmation_dialog(
                    is_open=PurchaseRuleConfigState.confirm_open,
                    title=PurchaseRuleConfigState.confirm_title,
                    body=PurchaseRuleConfigState.confirm_body,
                    on_confirm=PurchaseRuleConfigState.soft_delete_rule,
                    on_cancel=PurchaseRuleConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                padding="2rem", max_width="1200px", width="100%",
            ),
            page_footer(),
            align="start", width="100%", min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
