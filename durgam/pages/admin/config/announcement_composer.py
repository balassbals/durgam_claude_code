"""Announcement composer config management page — /admin/config/announcement-composer."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    app_shell,
    config_toast,
    form_modal,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.config_announcement_composer import AnnouncementComposerConfigState

_SCOPE_OPTIONS = [
    ("", "No restriction (any scope)"),
    ("department", "Department"),
    ("campus", "Campus"),
    ("school", "School"),
    ("centre", "Centre"),
]


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
                on_click=AnnouncementComposerConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"],
                    row["role_code"],
                    row["priority_rank"],
                    row["raw_scope_restriction"],
                    row["raw_enabled"],
                    row["raw_notes"],
                ),
            ),
            rx.menu.item(
                "Remove",
                on_click=AnnouncementComposerConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"],
                    row["role_code"],
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
                    AnnouncementComposerConfigState.editing_id == "",
                    "Add Composer Role",
                    "Edit Composer Role",
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
                        value=AnnouncementComposerConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Role Code *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_role_code",
                            value=AnnouncementComposerConfigState.form_role_code,
                            on_change=AnnouncementComposerConfigState.set_form_role_code,
                            placeholder="e.g. HOD",
                            width="100%",
                            disabled=AnnouncementComposerConfigState.editing_id != "",
                        ),
                        rx.text(
                            "Role code is fixed after creation.",
                            font_size="0.72rem",
                            color="var(--color-muted)",
                            font_style="italic",
                        ),
                        align="start",
                        gap="0.2rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Priority Rank *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            type="number",
                            name="form_priority_rank",
                            min="1",
                            value=AnnouncementComposerConfigState.form_priority_rank.to(str),
                            on_change=AnnouncementComposerConfigState.set_form_priority_rank,
                            width="140px",
                        ),
                        rx.text(
                            "Lower rank = higher priority in the dashboard widget.",
                            font_size="0.72rem",
                            color="var(--color-muted)",
                        ),
                        align="start",
                        gap="0.2rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Scope Restriction", font_size="0.85rem", color="var(--color-muted)"
                        ),
                        rx.select.root(
                            rx.select.trigger(width="100%"),
                            rx.select.content(
                                *[
                                    rx.select.item(label, value=val or "none")
                                    for val, label in _SCOPE_OPTIONS
                                ],
                            ),
                            value=rx.cond(
                                AnnouncementComposerConfigState.form_scope_restriction == "",
                                "none",
                                AnnouncementComposerConfigState.form_scope_restriction,
                            ),
                            on_change=AnnouncementComposerConfigState.set_form_scope_restriction,
                            width="100%",
                        ),
                        rx.text(
                            "Limits the maximum audience this role may address.",
                            font_size="0.72rem",
                            color="var(--color-muted)",
                        ),
                        align="start",
                        gap="0.2rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.hstack(
                            rx.checkbox(
                                checked=AnnouncementComposerConfigState.form_enabled,
                                on_change=AnnouncementComposerConfigState.set_form_enabled,
                            ),
                            rx.text("Enabled", font_size="0.9rem"),
                            align="center",
                            gap="0.5rem",
                        ),
                        rx.text(
                            "When disabled, this role is excluded from the priority engine.",
                            font_size="0.72rem",
                            color="var(--color-muted)",
                        ),
                        align="start",
                        gap="0.25rem",
                        margin_y="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Notes", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(
                            value=AnnouncementComposerConfigState.form_notes,
                            on_change=AnnouncementComposerConfigState.set_form_notes,
                            placeholder="Optional admin notes",
                            width="100%",
                            rows="2",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=AnnouncementComposerConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=AnnouncementComposerConfigState.save_config,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=AnnouncementComposerConfigState.show_form,
    )


def admin_config_announcement_composer() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        "Announcement Composer Roles", size="5", font_family="var(--font-sans)"
                    ),
                    rx.spacer(),
                    primary_btn("+ Add Role", on_click=AnnouncementComposerConfigState.open_create),
                    align="center",
                    width="100%",
                    margin_bottom="1rem",
                ),
                config_toast(
                    AnnouncementComposerConfigState.flash,
                    AnnouncementComposerConfigState.flash_type,
                    AnnouncementComposerConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    AnnouncementComposerConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=AnnouncementComposerConfigState.configs,
                        columns=[
                            TableColumn(key="role_code", label="Role Code"),
                            TableColumn(key="priority_rank", label="Priority Rank"),
                            TableColumn(key="scope_restriction", label="Scope Restriction"),
                            TableColumn(key="enabled", label="Enabled"),
                            TableColumn(key="notes", label="Notes"),
                        ],
                        card_primary_key="role_code",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No composer roles configured.",
                    ),
                ),
                confirmation_dialog(
                    is_open=AnnouncementComposerConfigState.confirm_open,
                    title=AnnouncementComposerConfigState.confirm_title,
                    body=AnnouncementComposerConfigState.confirm_body,
                    on_confirm=AnnouncementComposerConfigState.soft_delete_config,
                    on_cancel=AnnouncementComposerConfigState.cancel_confirm,
                    confirm_label="Remove",
                ),
                align="start",
                width="100%",
            ),
            container="lg",
        )
    )
