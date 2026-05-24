"""Role email management page — /admin/config/role-emails."""

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
from durgam.states.config_role_email import RoleEmailConfigState


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
                on_click=RoleEmailConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"],
                    row["role_code"],
                    row["email"],
                    row["scope_type"],
                    row["scope_id"],
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=RoleEmailConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["role_code"]
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
                    RoleEmailConfigState.editing_id == "",
                    "New Role Email",
                    "Edit Role Email",
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
                        value=RoleEmailConfigState.editing_id,
                    ),
                    rx.input(
                        type="hidden",
                        name="form_role_code",
                        value=RoleEmailConfigState.form_role_code,
                    ),
                    rx.input(
                        type="hidden",
                        name="form_scope_type",
                        value=RoleEmailConfigState.form_scope_type,
                    ),
                    rx.input(
                        type="hidden",
                        name="form_scope_id",
                        value=RoleEmailConfigState.form_scope_id,
                    ),
                    rx.vstack(
                        rx.text("Role", font_size="0.85rem", color="var(--color-muted)"),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select role"),
                            rx.select.content(
                                rx.foreach(
                                    RoleEmailConfigState.roles_dropdown,
                                    lambda item: rx.select.item(
                                        item["label"], value=item["id"],
                                    ),
                                ),
                            ),
                            value=RoleEmailConfigState.form_role_code,
                            on_change=RoleEmailConfigState.set_form_role_code,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Email", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_email",
                            value=RoleEmailConfigState.form_email,
                            on_change=RoleEmailConfigState.set_form_email,
                            placeholder="email@example.com",
                            max_length=254,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Scope",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                        ),
                        rx.select.root(
                            rx.select.trigger(placeholder="Global (no scope)"),
                            rx.select.content(
                                rx.select.item("Global (no scope)", value=""),
                                rx.select.item("Campus", value="campus"),
                                rx.select.item("Department", value="department"),
                                rx.select.item("School", value="school"),
                            ),
                            value=RoleEmailConfigState.form_scope_type,
                            on_change=RoleEmailConfigState.set_form_scope_type,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.cond(
                        RoleEmailConfigState.form_scope_type != "",
                        rx.vstack(
                            rx.text(
                                "Scope Object",
                                font_size="0.85rem",
                                color="var(--color-muted)",
                            ),
                            rx.select.root(
                                rx.select.trigger(placeholder="Select scope object"),
                                rx.select.content(
                                    rx.foreach(
                                        RoleEmailConfigState.scope_objects_dropdown,
                                        lambda item: rx.select.item(
                                            item["label"], value=item["id"],
                                        ),
                                    ),
                                ),
                                value=RoleEmailConfigState.form_scope_id,
                                on_change=RoleEmailConfigState.set_form_scope_id,
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            width="100%",
                        ),
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=RoleEmailConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=RoleEmailConfigState.save_role_email,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=RoleEmailConfigState.show_form,
    )


def admin_config_role_emails() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "Role Emails",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    primary_btn(
                        "+ New Role Email",
                        on_click=RoleEmailConfigState.open_create,
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    RoleEmailConfigState.flash,
                    RoleEmailConfigState.flash_type,
                    RoleEmailConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    RoleEmailConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=RoleEmailConfigState.role_emails,
                        columns=[
                            TableColumn(key="role_code", label="Role Code"),
                            TableColumn(key="scope", label="Scope"),
                            TableColumn(key="email", label="Email"),
                        ],
                        card_primary_key="role_code",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No role emails configured.",
                    ),
                ),
                confirmation_dialog(
                    is_open=RoleEmailConfigState.confirm_open,
                    title=RoleEmailConfigState.confirm_title,
                    body=RoleEmailConfigState.confirm_body,
                    on_confirm=RoleEmailConfigState.soft_delete_role_email,
                    on_cancel=RoleEmailConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                padding="2rem",
                max_width="1200px",
                width="100%",
                id="role-email-page-top",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
