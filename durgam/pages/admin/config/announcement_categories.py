"""Announcement categories management page — /admin/config/announcement-categories."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    config_toast,
    form_modal,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.config_announcement_category import AnnouncementCategoryConfigState


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
                on_click=AnnouncementCategoryConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["code"], row["name"],
                    row["display_order"], row["raw_is_active"], row["raw_notes"],
                ),
            ),
            rx.menu.item(
                "Remove",
                on_click=AnnouncementCategoryConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
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
                    AnnouncementCategoryConfigState.editing_id == "",
                    "New Announcement Category",
                    "Edit Announcement Category",
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
                        value=AnnouncementCategoryConfigState.editing_id,
                    ),
                    rx.input(
                        type="hidden",
                        name="form_display_order",
                        value=AnnouncementCategoryConfigState.form_display_order.to(str),
                    ),
                    rx.vstack(
                        rx.text("Code *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_code",
                            value=AnnouncementCategoryConfigState.form_code,
                            on_change=AnnouncementCategoryConfigState.set_form_code,
                            placeholder="e.g. ADVISORY",
                            width="100%",
                            disabled=AnnouncementCategoryConfigState.editing_id != "",
                        ),
                        rx.text(
                            "Short uppercase code. Cannot be changed after creation.",
                            font_size="0.72rem",
                            color="var(--color-muted)",
                            font_style="italic",
                        ),
                        align="start", gap="0.2rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Name *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_name",
                            value=AnnouncementCategoryConfigState.form_name,
                            on_change=AnnouncementCategoryConfigState.set_form_name,
                            placeholder="e.g. Advisory",
                            width="100%",
                        ),
                        align="start", gap="0.2rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Display Order", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            type="number",
                            min="0",
                            value=AnnouncementCategoryConfigState.form_display_order.to(str),
                            on_change=AnnouncementCategoryConfigState.set_form_display_order,
                            width="120px",
                        ),
                        rx.text(
                            "Lower number appears first in dropdowns.",
                            font_size="0.72rem",
                            color="var(--color-muted)",
                        ),
                        align="start", gap="0.2rem", width="100%",
                    ),
                    rx.vstack(
                        rx.hstack(
                            rx.checkbox(
                                checked=AnnouncementCategoryConfigState.form_is_active,
                                on_change=AnnouncementCategoryConfigState.set_form_is_active,
                            ),
                            rx.text("Active", font_size="0.9rem"),
                            align="center", gap="0.5rem",
                        ),
                        rx.text(
                            "Inactive categories are hidden from the composer form.",
                            font_size="0.72rem",
                            color="var(--color-muted)",
                        ),
                        align="start", gap="0.25rem", margin_y="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Notes", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(
                            value=AnnouncementCategoryConfigState.form_notes,
                            on_change=AnnouncementCategoryConfigState.set_form_notes,
                            placeholder="Optional notes",
                            width="100%",
                            rows="2",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=AnnouncementCategoryConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem", align="start", width="100%",
                ),
                on_submit=AnnouncementCategoryConfigState.save_category,
                reset_on_submit=False,
            ),
            gap="0", align="start", width="100%",
        ),
        is_open=AnnouncementCategoryConfigState.show_form,
    )


def admin_config_announcement_categories() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading("Announcement Categories", size="5",
                               font_family="var(--font-sans)"),
                    rx.spacer(),
                    primary_btn("+ New Category",
                                on_click=AnnouncementCategoryConfigState.open_create),
                    align="center", width="100%", margin_bottom="1rem",
                ),
                config_toast(
                    AnnouncementCategoryConfigState.flash,
                    AnnouncementCategoryConfigState.flash_type,
                    AnnouncementCategoryConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    AnnouncementCategoryConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=AnnouncementCategoryConfigState.categories,
                        columns=[
                            TableColumn(key="code", label="Code"),
                            TableColumn(key="name", label="Name"),
                            TableColumn(key="display_order", label="Display Order"),
                            TableColumn(key="active", label="Active"),
                            TableColumn(key="notes", label="Notes"),
                        ],
                        card_primary_key="code",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No announcement categories configured.",
                    ),
                ),
                confirmation_dialog(
                    is_open=AnnouncementCategoryConfigState.confirm_open,
                    title=AnnouncementCategoryConfigState.confirm_title,
                    body=AnnouncementCategoryConfigState.confirm_body,
                    on_confirm=AnnouncementCategoryConfigState.soft_delete_category,
                    on_cancel=AnnouncementCategoryConfigState.cancel_confirm,
                    confirm_label="Remove",
                ),
                padding="2rem", max_width="1200px", width="100%",
            ),
            page_footer(),
            align="start", width="100%", min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
