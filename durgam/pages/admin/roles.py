"""Admin role list and detail pages — /admin/roles and /admin/roles/new."""

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer
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
                rx.button("⋮", background="transparent", border="none", cursor="pointer",
                          font_size="1.2rem", color="var(--color-muted)", padding="0.1rem 0.4rem")
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

    return admin_page(rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.heading("Roles", size="5", font_family="var(--font-sans)"),
                rx.spacer(),
                rx.link(
                    rx.button(
                        "+ New role",
                        background="var(--color-primary)", color="white",
                        border="none", padding="0.4rem 1rem", border_radius="4px",
                        cursor="pointer", font_family="var(--font-sans)",
                    ),
                    href="/admin/roles/new",
                ),
                align="center", width="100%", margin_bottom="1rem",
            ),
            rx.cond(
                AdminRolesState.flash != "",
                rx.box(rx.text(AdminRolesState.flash, font_size="0.875rem"),
                       background="var(--color-surface, #faf9f7)",
                       border="1px solid var(--color-rule)", border_radius="4px",
                       padding="0.75rem 1rem", margin_bottom="1rem"),
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
            padding="2rem", max_width="1200px", width="100%",
        ),
        page_footer(),
        align="start", width="100%", min_height="100vh",
        background="var(--color-background, #f5f0eb)",
    ))


def admin_role_create() -> rx.Component:
    return admin_page(rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.link("← Roles", href="/admin/roles", color="var(--color-primary)",
                        font_size="0.875rem"),
                rx.heading("New Role", size="5", font_family="var(--font-sans)"),
                gap="1rem", align="center", margin_bottom="1.5rem",
            ),
            rx.cond(
                AdminRolesState.flash != "",
                rx.box(rx.text(AdminRolesState.flash, font_size="0.875rem"),
                       background="var(--color-surface, #faf9f7)",
                       border="1px solid var(--color-rule)", border_radius="4px",
                       padding="0.75rem 1rem", margin_bottom="1rem"),
                rx.fragment(),
            ),
            rx.form(
                rx.vstack(
                    rx.box(
                        rx.text("Code *", font_size="0.875rem", font_weight="600",
                                margin_bottom="0.25rem"),
                        rx.input(name="code", placeholder="e.g. HOD",
                                 font_family="var(--font-sans)"),
                        width="100%",
                    ),
                    rx.box(
                        rx.text("Name *", font_size="0.875rem", font_weight="600",
                                margin_bottom="0.25rem"),
                        rx.input(name="name", placeholder="e.g. Head of Department",
                                 font_family="var(--font-sans)"),
                        width="100%",
                    ),
                    rx.box(
                        rx.text("Level", font_size="0.875rem", font_weight="600",
                                margin_bottom="0.25rem"),
                        rx.input(name="level", placeholder="0–100 (higher = more privileged)",
                                 default_value="10", font_family="var(--font-sans)"),
                        width="100%",
                    ),
                    rx.box(
                        rx.text("Description", font_size="0.875rem", font_weight="600",
                                margin_bottom="0.25rem"),
                        rx.text_area(name="description", placeholder="Optional description",
                                     font_family="var(--font-sans)"),
                        width="100%",
                    ),
                    rx.hstack(
                        rx.button("Create role", type="submit",
                                  background="var(--color-primary)", color="white",
                                  border="none", padding="0.5rem 1.5rem", border_radius="4px",
                                  cursor="pointer", font_family="var(--font-sans)"),
                        rx.link("Cancel", href="/admin/roles", color="var(--color-muted)",
                                font_size="0.875rem"),
                        gap="1rem", align="center", margin_top="1rem",
                    ),
                    align="start", gap="1rem", width="min(480px, 100%)",
                ),
                on_submit=AdminRolesState.create_role,
            ),
            permission_check_widget(),
            padding="2rem", max_width="800px", width="100%",
        ),
        page_footer(),
        align="start", width="100%", min_height="100vh",
        background="var(--color-background, #f5f0eb)",
    ))


def admin_role_detail() -> rx.Component:
    """Role detail page with resource-first permission accordion."""

    def perm_row(perm: dict) -> rx.Component:
        return rx.hstack(
            rx.checkbox(
                name=perm["id"],
                default_checked=perm["granted"] == "true",
                color_scheme="indigo",
            ),
            rx.text(perm["action"], font_size="0.875rem", min_width="80px"),
            rx.text(perm["scope"], font_size="0.875rem", color="var(--color-muted)"),
            gap="0.5rem",
            align="center",
        )

    return admin_page(rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.link("← Roles", href="/admin/roles", color="var(--color-primary)",
                        font_size="0.875rem"),
                rx.heading(AdminRolesState.current_role_name, size="5",
                           font_family="var(--font-sans)"),
                rx.text(AdminRolesState.current_role_code, font_size="0.8rem",
                        color="var(--color-muted)", font_family="monospace"),
                gap="1rem", align="center", margin_bottom="1.5rem",
            ),
            rx.cond(
                AdminRolesState.flash != "",
                rx.box(rx.text(AdminRolesState.flash, font_size="0.875rem"),
                       background="var(--color-surface, #faf9f7)",
                       border="1px solid var(--color-rule)", border_radius="4px",
                       padding="0.75rem 1rem", margin_bottom="1rem"),
                rx.fragment(),
            ),
            rx.heading("Permissions", size="3", margin_bottom="1rem"),
            rx.text(
                "Check the permissions to grant to this role, then click Save.",
                font_size="0.8rem", color="var(--color-muted)", margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.foreach(
                        AdminRolesState.permissions_by_resource,
                        lambda resource_entry: rx.box(
                            rx.text(resource_entry[0], font_weight="600", font_size="0.9rem",
                                    color="var(--color-body)", margin_bottom="0.5rem"),
                            rx.vstack(
                                rx.foreach(resource_entry[1], perm_row),
                                align="start", gap="0.25rem", padding_left="1rem",
                            ),
                            border="1px solid var(--color-rule)",
                            border_radius="6px",
                            padding="0.75rem 1rem",
                            margin_bottom="0.5rem",
                            background="white",
                        ),
                    ),
                    rx.button("Save permissions", type="submit",
                              background="var(--color-primary)", color="white",
                              border="none", padding="0.5rem 1.5rem", border_radius="4px",
                              cursor="pointer", font_family="var(--font-sans)",
                              margin_top="1rem"),
                    # Inline feedback near Save — visible at the user's scroll position.
                    rx.cond(
                        AdminRolesState.flash != "",
                        rx.box(rx.text(AdminRolesState.flash, font_size="0.875rem"),
                               background="var(--color-surface, #faf9f7)",
                               border="1px solid var(--color-rule)", border_radius="4px",
                               padding="0.5rem 1rem", margin_top="0.5rem"),
                        rx.fragment(),
                    ),
                    align="start", gap="0.5rem",
                ),
                on_submit=AdminRolesState.save_role_permissions,
            ),
            permission_check_widget(),
            padding="2rem", max_width="900px", width="100%",
        ),
        page_footer(),
        align="start", width="100%", min_height="100vh",
        background="var(--color-background, #f5f0eb)",
    ))
