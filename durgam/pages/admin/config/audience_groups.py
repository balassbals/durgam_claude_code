"""Audience groups management page — /admin/config/audience-groups."""

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
from durgam.states.config_audience_group import AudienceGroupConfigState

_SCOPE_TYPE_OPTIONS = [
    ("none",       "No scope restriction"),
    ("school",     "School"),
    ("department", "Department"),
    ("campus",     "Campus"),
    ("program",    "Program"),
    ("centre",     "Centre"),
]


def _scope_codes_picker() -> rx.Component:
    """Checkbox list for selecting scope codes; visible only when scope_type != 'none'."""
    return rx.cond(
        AudienceGroupConfigState.form_scope_type != "none",
        rx.vstack(
            rx.text(
                "Scope Codes",
                font_size="0.85rem",
                color="var(--color-muted)",
            ),
            rx.cond(
                AudienceGroupConfigState.available_scope_codes_for_current_type.length() > 0,
                rx.box(
                    rx.foreach(
                        AudienceGroupConfigState.available_scope_codes_for_current_type,
                        lambda code: rx.hstack(
                            rx.checkbox(
                                checked=AudienceGroupConfigState.form_scope_codes.contains(code),
                                on_change=AudienceGroupConfigState.toggle_scope_code(code),  # type: ignore[call-arg]
                            ),
                            rx.text(code, font_size="0.875rem"),
                            spacing="2",
                            align="center",
                        ),
                    ),
                    max_height="180px",
                    overflow_y="auto",
                    border="1px solid var(--color-rule)",
                    border_radius="var(--radius-2)",
                    padding="0.5rem",
                    width="100%",
                ),
                rx.text(
                    "No codes found for this scope type.",
                    font_size="0.8rem",
                    color="var(--color-muted)",
                    font_style="italic",
                ),
            ),
            rx.text(
                "Leave empty to match any scope of this type.",
                font_size="0.72rem",
                color="var(--color-muted)",
            ),
            align="start", gap="0.25rem", width="100%",
        ),
        rx.box(),
    )


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
                on_click=AudienceGroupConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"],
                    row["code"],
                    row["name"],
                    row["raw_description"],
                    row["raw_is_active"],
                    row["raw_filter_json"],
                ),
            ),
            rx.menu.item(
                "Remove",
                on_click=AudienceGroupConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["code"],
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
                    AudienceGroupConfigState.editing_id == "",
                    "New Audience Group",
                    "Edit Audience Group",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.input(
                        type="hidden",
                        name="editing_id",
                        value=AudienceGroupConfigState.editing_id,
                    ),
                    # ── Code ───────────────────────────────────────────────
                    rx.vstack(
                        rx.text("Code *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_code",
                            value=AudienceGroupConfigState.form_code,
                            on_change=AudienceGroupConfigState.set_form_code,
                            placeholder="e.g. FACULTY_SCI",
                            width="100%",
                            disabled=AudienceGroupConfigState.editing_id != "",
                        ),
                        rx.text(
                            "Uppercase, letters/digits/underscore, starts with a letter. "
                            "Cannot be changed after creation.",
                            font_size="0.72rem",
                            color="var(--color-muted)",
                            font_style="italic",
                        ),
                        align="start", gap="0.2rem", width="100%",
                    ),
                    # ── Name ───────────────────────────────────────────────
                    rx.vstack(
                        rx.text("Name *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_name",
                            value=AudienceGroupConfigState.form_name,
                            on_change=AudienceGroupConfigState.set_form_name,
                            placeholder="e.g. Science Faculty",
                            width="100%",
                        ),
                        align="start", gap="0.2rem", width="100%",
                    ),
                    # ── Description ────────────────────────────────────────
                    rx.vstack(
                        rx.text("Description", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(
                            value=AudienceGroupConfigState.form_description,
                            on_change=AudienceGroupConfigState.set_form_description,
                            placeholder="Optional description",
                            width="100%",
                            rows="2",
                        ),
                        align="start", gap="0.2rem", width="100%",
                    ),
                    # ── Role codes multi-select ─────────────────────────────
                    rx.vstack(
                        rx.text("Role Filter", font_size="0.85rem", color="var(--color-muted)"),
                        role_multi_select(
                            options=AudienceGroupConfigState.role_options,
                            selected_codes=AudienceGroupConfigState.form_role_codes,
                            toggle_handler=AudienceGroupConfigState.toggle_role_code,
                        ),
                        rx.text(
                            "Leave empty to match all roles.",
                            font_size="0.72rem",
                            color="var(--color-muted)",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    # ── Scope type ─────────────────────────────────────────
                    rx.vstack(
                        rx.text("Scope Type", font_size="0.85rem", color="var(--color-muted)"),
                        rx.select.root(
                            rx.select.trigger(width="100%"),
                            rx.select.content(
                                *[
                                    rx.select.item(label, value=val)
                                    for val, label in _SCOPE_TYPE_OPTIONS
                                ],
                            ),
                            value=AudienceGroupConfigState.form_scope_type,
                            on_change=AudienceGroupConfigState.set_scope_type,
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    # ── Scope codes (conditional) ───────────────────────────
                    _scope_codes_picker(),
                    # ── Program degree types ────────────────────────────────
                    rx.vstack(
                        rx.text("Program Degree Types", font_size="0.85rem",
                                color="var(--color-muted)"),
                        rx.input(
                            value=AudienceGroupConfigState.form_program_degree_types_text,
                            on_change=AudienceGroupConfigState.set_form_program_degree_types_text,
                            placeholder="e.g. PhD, DPhil",
                            width="100%",
                        ),
                        rx.text(
                            "Comma-separated. Leave empty for all degree types.",
                            font_size="0.72rem",
                            color="var(--color-muted)",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    # ── Is active ──────────────────────────────────────────
                    rx.vstack(
                        rx.hstack(
                            rx.checkbox(
                                checked=AudienceGroupConfigState.form_is_active,
                                on_change=AudienceGroupConfigState.set_form_is_active,
                            ),
                            rx.text("Active", font_size="0.9rem"),
                            align="center", gap="0.5rem",
                        ),
                        rx.text(
                            "Inactive groups are excluded from the audience picker.",
                            font_size="0.72rem",
                            color="var(--color-muted)",
                        ),
                        align="start", gap="0.25rem", margin_y="0.25rem", width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=AudienceGroupConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem", align="start", width="100%",
                ),
                on_submit=AudienceGroupConfigState.save,
                reset_on_submit=False,
            ),
            gap="0", align="start", width="100%",
        ),
        is_open=AudienceGroupConfigState.show_form,
        max_width="600px",
    )


def admin_config_audience_groups() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading("Audience Groups", size="5",
                               font_family="var(--font-sans)"),
                    rx.spacer(),
                    primary_btn("+ Add Audience Group",
                                on_click=AudienceGroupConfigState.open_create),
                    align="center", width="100%", margin_bottom="1rem",
                ),
                config_toast(
                    AudienceGroupConfigState.flash,
                    AudienceGroupConfigState.flash_type,
                    AudienceGroupConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    AudienceGroupConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=AudienceGroupConfigState.rows,
                        columns=[
                            TableColumn(key="code", label="Code"),
                            TableColumn(key="name", label="Name"),
                            TableColumn(key="filter_summary", label="Filter"),
                            TableColumn(key="active", label="Active"),
                        ],
                        card_primary_key="code",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No audience groups configured.",
                    ),
                ),
                confirmation_dialog(
                    is_open=AudienceGroupConfigState.confirm_open,
                    title=AudienceGroupConfigState.confirm_title,
                    body=AudienceGroupConfigState.confirm_body,
                    on_confirm=AudienceGroupConfigState.confirm_deactivate,
                    on_cancel=AudienceGroupConfigState.cancel_confirm,
                    confirm_label="Remove",
                ),
                padding="2rem", max_width="1200px", width="100%",
            ),
            page_footer(),
            align="start", width="100%", min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
