"""Admin role list and detail pages — /admin/roles and /admin/roles/new."""

import reflex as rx

from durgam.pages.components import admin_page, app_shell
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.pages.shared.permission_check_widget import permission_check_widget
from durgam.states.admin_roles import AdminRolesState


def admin_roles() -> rx.Component:
    columns = [
        TableColumn(key="name", label="Name"),
        TableColumn(key="code", label="Code"),
        TableColumn(key="level", label="Level", hidden_on_card=True),
        TableColumn(key="permission_count", label="Permissions"),
    ]

    def role_actions(row: dict) -> rx.Component:
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
                rx.menu.item("Edit", on_click=rx.redirect(f"/admin/roles/{row['id']}")),
                rx.menu.item(
                    "Delete",
                    on_click=AdminRolesState.open_delete_confirm(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["name"]
                    ),
                    color="var(--color-danger, #c0392b)",
                ),
            ),
        )

    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.heading("Roles", size="5", font_family="var(--font-sans)"),
                    rx.spacer(),
                    rx.link(
                        rx.button(
                            "+ New role",
                            background="var(--color-primary)",
                            color="white",
                            border="none",
                            padding="0.4rem 1rem",
                            border_radius="4px",
                            cursor="pointer",
                            font_family="var(--font-sans)",
                        ),
                        href="/admin/roles/new",
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1rem",
                ),
                rx.cond(
                    AdminRolesState.flash != "",
                    rx.box(
                        rx.text(AdminRolesState.flash, font_size="0.875rem"),
                        background="var(--color-surface, #faf9f7)",
                        border="1px solid var(--color-rule)",
                        border_radius="4px",
                        padding="0.75rem 1rem",
                        margin_bottom="1rem",
                    ),
                    rx.fragment(),
                ),
                data_table(
                    rows=AdminRolesState.roles,
                    columns=columns,
                    card_primary_key="name",
                    is_mobile=False,
                    actions=role_actions,
                    empty_message="No roles yet. Create your first role →",
                ),
                confirmation_dialog(
                    is_open=AdminRolesState.confirm_open,
                    title=AdminRolesState.confirm_title,
                    body=AdminRolesState.confirm_body,
                    on_confirm=AdminRolesState.soft_delete_role,
                    on_cancel=AdminRolesState.cancel_confirm,
                    confirm_label="Delete role",
                ),
                align="start",
                width="100%",
            ),
            container="lg",
        )
    )


def admin_role_create() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.link(
                        "← Roles",
                        href="/admin/roles",
                        color="var(--color-primary)",
                        font_size="0.875rem",
                    ),
                    rx.heading("New Role", size="5", font_family="var(--font-sans)"),
                    gap="1rem",
                    align="center",
                    margin_bottom="1.5rem",
                ),
                rx.cond(
                    AdminRolesState.flash != "",
                    rx.box(
                        rx.text(AdminRolesState.flash, font_size="0.875rem"),
                        background="var(--color-surface, #faf9f7)",
                        border="1px solid var(--color-rule)",
                        border_radius="4px",
                        padding="0.75rem 1rem",
                        margin_bottom="1rem",
                    ),
                    rx.fragment(),
                ),
                rx.form(
                    rx.vstack(
                        rx.box(
                            rx.text(
                                "Code *",
                                font_size="0.875rem",
                                font_weight="600",
                                margin_bottom="0.25rem",
                            ),
                            rx.input(
                                name="code", placeholder="e.g. HOD", font_family="var(--font-sans)"
                            ),
                            width="100%",
                        ),
                        rx.box(
                            rx.text(
                                "Name *",
                                font_size="0.875rem",
                                font_weight="600",
                                margin_bottom="0.25rem",
                            ),
                            rx.input(
                                name="name",
                                placeholder="e.g. Head of Department",
                                font_family="var(--font-sans)",
                            ),
                            width="100%",
                        ),
                        rx.box(
                            rx.text(
                                "Level",
                                font_size="0.875rem",
                                font_weight="600",
                                margin_bottom="0.25rem",
                            ),
                            rx.input(
                                name="level",
                                placeholder="0–100 (higher = more privileged)",
                                default_value="10",
                                font_family="var(--font-sans)",
                            ),
                            width="100%",
                        ),
                        rx.box(
                            rx.text(
                                "Description",
                                font_size="0.875rem",
                                font_weight="600",
                                margin_bottom="0.25rem",
                            ),
                            rx.text_area(
                                name="description",
                                placeholder="Optional description",
                                font_family="var(--font-sans)",
                            ),
                            width="100%",
                        ),
                        rx.hstack(
                            rx.button(
                                "Create role",
                                type="submit",
                                background="var(--color-primary)",
                                color="white",
                                border="none",
                                padding="0.5rem 1.5rem",
                                border_radius="4px",
                                cursor="pointer",
                                font_family="var(--font-sans)",
                            ),
                            rx.link(
                                "Cancel",
                                href="/admin/roles",
                                color="var(--color-muted)",
                                font_size="0.875rem",
                            ),
                            gap="1rem",
                            align="center",
                            margin_top="1rem",
                        ),
                        align="start",
                        gap="1rem",
                        width="min(480px, 100%)",
                    ),
                    on_submit=AdminRolesState.create_role,
                ),
                permission_check_widget(),
                align="start",
                width="100%",
            ),
            container="md",
        )
    )


def admin_role_detail() -> rx.Component:
    """Role detail page — grouped permission list with pre-checked existing grants."""

    def perm_table_row(item: rx.Var) -> rx.Component:
        """Renders a resource header (with count badge) or a permission checkbox row."""
        return rx.cond(
            item["type"] == "header",  # type: ignore[index]
            # Resource group header with "{n granted}/{m total}" badge.
            rx.hstack(
                rx.text(
                    item["resource"],  # type: ignore[index]
                    font_weight="700",
                    font_size="0.85rem",
                    color="var(--color-body)",
                    text_transform="capitalize",
                ),
                rx.badge(item["badge"], variant="soft", color_scheme="indigo"),  # type: ignore[index]
                width="100%",
                padding="0.6rem 0 0.2rem",
                border_top="1px solid var(--color-rule)",
                margin_top="0.75rem",
                align="center",
                gap="0.5rem",
            ),
            # Permission row — controlled checkbox bound to role_perm_ids_checked.
            # Uses checked= (controlled) instead of default_checked= (uncontrolled)
            # so the state updates reactively when navigating between roles.
            rx.hstack(
                rx.checkbox(
                    checked=AdminRolesState.role_perm_ids_checked.contains(  # type: ignore[attr-defined]
                        item["id"]  # type: ignore[index]
                    ),
                    on_change=AdminRolesState.toggle_perm(  # type: ignore[call-arg, func-returns-value]
                        item["id"]  # type: ignore[index]
                    ),
                    color_scheme="indigo",
                ),
                rx.text(
                    item["action"],  # type: ignore[index]
                    " · ",
                    item["scope"],  # type: ignore[index]
                    font_size="0.875rem",
                    color="var(--color-body)",
                ),
                gap="0.6rem",
                align="center",
                padding="0.2rem 1rem",
                cursor="pointer",
            ),
        )

    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.link(
                        "← Roles",
                        href="/admin/roles",
                        color="var(--color-primary)",
                        font_size="0.875rem",
                    ),
                    rx.heading(
                        AdminRolesState.current_role_name, size="5", font_family="var(--font-sans)"
                    ),
                    rx.text(
                        AdminRolesState.current_role_code,
                        font_size="0.8rem",
                        color="var(--color-muted)",
                        font_family="monospace",
                    ),
                    gap="1rem",
                    align="center",
                    margin_bottom="1.5rem",
                ),
                rx.cond(
                    AdminRolesState.flash != "",
                    rx.box(
                        rx.text(AdminRolesState.flash, font_size="0.875rem"),
                        background="var(--color-surface, #faf9f7)",
                        border="1px solid var(--color-rule)",
                        border_radius="4px",
                        padding="0.75rem 1rem",
                        margin_bottom="1rem",
                    ),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.heading("Permissions", size="3"),
                    rx.spacer(),
                    rx.text(
                        AdminRolesState.perm_granted_count,
                        " of ",
                        AdminRolesState.perm_total_count,
                        " granted",
                        font_size="0.8rem",
                        color="var(--color-muted)",
                    ),
                    align="center",
                    margin_bottom="0.5rem",
                ),
                rx.text(
                    "Check the permissions to grant to this role, then click Save. "
                    "Existing grants are pre-checked.",
                    font_size="0.8rem",
                    color="var(--color-muted)",
                    margin_bottom="0.5rem",
                ),
                rx.vstack(
                    rx.box(
                        rx.foreach(AdminRolesState.perm_table, perm_table_row),
                        width="100%",
                        padding_bottom="0.5rem",
                    ),
                    rx.button(
                        "Save permissions",
                        on_click=AdminRolesState.save_role_permissions,
                        background="var(--color-primary)",
                        color="white",
                        border="none",
                        padding="0.5rem 1.5rem",
                        border_radius="4px",
                        cursor="pointer",
                        font_family="var(--font-sans)",
                        margin_top="1rem",
                    ),
                    rx.cond(
                        AdminRolesState.flash != "",
                        rx.box(
                            rx.text(AdminRolesState.flash, font_size="0.875rem"),
                            background="var(--color-surface, #faf9f7)",
                            border="1px solid var(--color-rule)",
                            border_radius="4px",
                            padding="0.5rem 1rem",
                            margin_top="0.5rem",
                        ),
                        rx.fragment(),
                    ),
                    align="start",
                    gap="0.5rem",
                ),
                permission_check_widget(),
                align="start",
                width="100%",
            ),
            container="md",
        )
    )
