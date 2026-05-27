"""Purchase committee templates management page — /admin/config/purchase-committees."""

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
from durgam.states.config_purchase_committee import PurchaseCommitteeConfigState


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
                on_click=PurchaseCommitteeConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["committee_type"],
                    row["raw_designations"], row["faculty_count"],
                    row["raw_different_depts"], row["raw_fixed"],
                    row["raw_director_excluded"], row["raw_escalation"],
                    row["expert_mode"], row["topology"], row["notes"],
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=PurchaseCommitteeConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["committee_type"],
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
                    PurchaseCommitteeConfigState.editing_id == "",
                    "New Committee Template",
                    "Edit Committee Template",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.input(type="hidden", name="editing_id",
                             value=PurchaseCommitteeConfigState.editing_id),
                    rx.vstack(
                        rx.text("Committee Type *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select type"),
                            rx.select.content(
                                rx.select.item("Campus Purchase Committee", value="campus_purchase_committee"),
                                rx.select.item("Central Purchase Committee", value="central_purchase_committee"),
                            ),
                            name="form_committee_type",
                            value=PurchaseCommitteeConfigState.form_committee_type,
                            on_change=PurchaseCommitteeConfigState.set_form_committee_type,
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Eligible Designations *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text("Select in rank order (highest first)", font_size="0.75rem", color="var(--color-muted)"),
                        role_multi_select(
                            options=PurchaseCommitteeConfigState.designation_options,
                            selected_codes=PurchaseCommitteeConfigState.form_eligible_designations_selected,
                            toggle_handler=PurchaseCommitteeConfigState.toggle_designation,
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text("Faculty Count *", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(name="form_faculty_count", type="number",
                                     value=PurchaseCommitteeConfigState.form_faculty_count,
                                     on_change=PurchaseCommitteeConfigState.set_form_faculty_count,
                                     width="100%"),
                            align="start", gap="0.25rem", width="50%",
                        ),
                        rx.vstack(
                            rx.text("Escalation Designate", font_size="0.85rem", color="var(--color-muted)"),
                            rx.select.root(
                                rx.select.trigger(placeholder="Select role"),
                                rx.select.content(
                                    rx.select.item("None", value="__none__"),
                                    rx.foreach(
                                        PurchaseCommitteeConfigState.role_options,
                                        lambda o: rx.select.item(o["label"], value=o["code"]),
                                    ),
                                ),
                                name="form_escalation",
                                value=PurchaseCommitteeConfigState.form_escalation,
                                on_change=PurchaseCommitteeConfigState.set_form_escalation,
                                width="100%",
                            ),
                            align="start", gap="0.25rem", width="50%",
                        ),
                        width="100%", gap="1rem",
                    ),
                    rx.vstack(
                        rx.text("Fixed Role Members", font_size="0.85rem", color="var(--color-muted)"),
                        role_multi_select(
                            options=PurchaseCommitteeConfigState.role_options,
                            selected_codes=PurchaseCommitteeConfigState.form_fixed_members_selected,
                            toggle_handler=PurchaseCommitteeConfigState.toggle_fixed_member,
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.hstack(
                        rx.checkbox(
                            "Members from different departments",
                            checked=PurchaseCommitteeConfigState.form_different_depts,
                            on_change=PurchaseCommitteeConfigState.set_form_different_depts,
                        ),
                        rx.checkbox(
                            "Director excluded",
                            checked=PurchaseCommitteeConfigState.form_director_excluded,
                            on_change=PurchaseCommitteeConfigState.set_form_director_excluded,
                        ),
                        gap="1rem", flex_wrap="wrap",
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text("Expert Mode", font_size="0.85rem", color="var(--color-muted)"),
                            rx.select.root(
                                rx.select.trigger(placeholder="Select mode"),
                                rx.select.content(
                                    rx.select.item("Proxied with proof", value="proxied_with_proof"),
                                    rx.select.item("Guest user", value="guest_user"),
                                ),
                                name="form_expert_mode",
                                value=PurchaseCommitteeConfigState.form_expert_mode,
                                on_change=PurchaseCommitteeConfigState.set_form_expert_mode,
                                width="100%",
                            ),
                            align="start", gap="0.25rem", width="50%",
                        ),
                        rx.vstack(
                            rx.text("Topology", font_size="0.85rem", color="var(--color-muted)"),
                            rx.select.root(
                                rx.select.trigger(placeholder="Select topology"),
                                rx.select.content(
                                    rx.select.item("Concurrent", value="concurrent"),
                                    rx.select.item("Sequential", value="sequential"),
                                ),
                                name="form_topology",
                                value=PurchaseCommitteeConfigState.form_topology,
                                on_change=PurchaseCommitteeConfigState.set_form_topology,
                                width="100%",
                            ),
                            align="start", gap="0.25rem", width="50%",
                        ),
                        width="100%", gap="1rem",
                    ),
                    rx.vstack(
                        rx.text("Notes", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(name="form_notes",
                                     value=PurchaseCommitteeConfigState.form_notes,
                                     on_change=PurchaseCommitteeConfigState.set_form_notes,
                                     placeholder="Optional notes",
                                     width="100%", rows="2"),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn("Cancel",
                                      on_click=PurchaseCommitteeConfigState.cancel_form,
                                      type="button"),
                        gap="0.75rem",
                    ),
                    gap="1rem", align="start", width="100%",
                ),
                on_submit=PurchaseCommitteeConfigState.save_template,
                reset_on_submit=False,
            ),
            gap="0", align="start", width="100%",
        ),
        is_open=PurchaseCommitteeConfigState.show_form,
        max_width="600px",
    )


def admin_config_purchase_committees() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading("Purchase Committee Templates", size="5",
                               font_family="var(--font-sans)"),
                    rx.spacer(),
                    primary_btn("+ Add Template",
                                on_click=PurchaseCommitteeConfigState.open_create),
                    align="center", width="100%", margin_bottom="1rem",
                ),
                config_toast(
                    PurchaseCommitteeConfigState.flash,
                    PurchaseCommitteeConfigState.flash_type,
                    PurchaseCommitteeConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    PurchaseCommitteeConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=PurchaseCommitteeConfigState.templates,
                        columns=[
                            TableColumn(key="committee_type", label="Type"),
                            TableColumn(key="eligible_designations", label="Designations"),
                            TableColumn(key="faculty_count", label="Faculty Count"),
                            TableColumn(key="fixed_members", label="Fixed Members"),
                            TableColumn(key="director_excluded", label="Dir. Excluded"),
                            TableColumn(key="escalation", label="Escalation"),
                            TableColumn(key="topology", label="Topology"),
                        ],
                        card_primary_key="committee_type",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No committee templates configured.",
                    ),
                ),
                confirmation_dialog(
                    is_open=PurchaseCommitteeConfigState.confirm_open,
                    title=PurchaseCommitteeConfigState.confirm_title,
                    body=PurchaseCommitteeConfigState.confirm_body,
                    on_confirm=PurchaseCommitteeConfigState.soft_delete_template,
                    on_cancel=PurchaseCommitteeConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                padding="2rem", max_width="1200px", width="100%",
            ),
            page_footer(),
            align="start", width="100%", min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
