"""Admin user list page — /admin/users."""

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.admin_users import AdminUsersState


def _kebab_menu(row: dict) -> rx.Component:
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
                "Reset password",
                on_click=AdminUsersState.open_reset_password_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["username"]
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=AdminUsersState.open_soft_delete_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["username"]
                ),
                color="var(--color-danger, #c0392b)",
            ),
        ),
    )


def _confirm_dispatch() -> rx.Component:
    """Route the confirmation dialog's confirm button to the correct handler."""
    return rx.cond(
        AdminUsersState.confirm_action == "soft_delete",
        confirmation_dialog(
            is_open=AdminUsersState.confirm_open,
            title=AdminUsersState.confirm_title,
            body=AdminUsersState.confirm_body,
            on_confirm=AdminUsersState.soft_delete_user,
            on_cancel=AdminUsersState.cancel_confirm,
            confirm_label="Deactivate",
        ),
        rx.cond(
            AdminUsersState.confirm_action == "hard_delete",
            confirmation_dialog(
                is_open=AdminUsersState.confirm_open,
                title=AdminUsersState.confirm_title,
                body=AdminUsersState.confirm_body,
                on_confirm=AdminUsersState.hard_delete_user,
                on_cancel=AdminUsersState.cancel_confirm,
                confirm_label="Delete permanently",
            ),
            confirmation_dialog(
                is_open=AdminUsersState.confirm_open,
                title=AdminUsersState.confirm_title,
                body=AdminUsersState.confirm_body,
                on_confirm=AdminUsersState.reset_user_password,
                on_cancel=AdminUsersState.cancel_confirm,
                confirm_label="Reset password",
                danger=False,
            ),
        ),
    )


def admin_users() -> rx.Component:
    columns = [
        TableColumn(key="username", label="Username"),
        TableColumn(key="email", label="Email"),
        TableColumn(key="is_active", label="Active"),
        TableColumn(key="last_login_at", label="Last login", hidden_on_card=True),
    ]

    return admin_page(rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.heading("Users", size="5", font_family="var(--font-sans)"),
                rx.spacer(),
                rx.link(
                    rx.button(
                        "+ New user",
                        background="var(--color-primary)",
                        color="white",
                        border="none",
                        padding="0.4rem 1rem",
                        border_radius="4px",
                        cursor="pointer",
                        font_family="var(--font-sans)",
                    ),
                    href="/admin/users/new",
                ),
                align="center",
                width="100%",
                margin_bottom="1rem",
            ),
            # Flash
            rx.cond(
                AdminUsersState.flash != "",
                rx.box(
                    rx.text(AdminUsersState.flash, font_size="0.875rem"),
                    background="var(--color-surface, #faf9f7)",
                    border="1px solid var(--color-rule)",
                    border_radius="4px",
                    padding="0.75rem 1rem",
                    margin_bottom="1rem",
                ),
                rx.fragment(),
            ),
            # Generated password one-time display
            rx.cond(
                AdminUsersState.generated_password != "",
                rx.box(
                    rx.text(
                        "Temporary password (shown once):",
                        font_weight="600",
                        font_size="0.875rem",
                        margin_bottom="0.25rem",
                    ),
                    rx.hstack(
                        rx.code(
                            AdminUsersState.generated_password,
                            font_size="1rem",
                        ),
                        rx.button(
                            "Dismiss",
                            on_click=AdminUsersState.dismiss_generated_password,
                            background="transparent",
                            border="1px solid var(--color-rule)",
                            padding="0.2rem 0.75rem",
                            border_radius="4px",
                            cursor="pointer",
                            font_size="0.8rem",
                        ),
                        align="center",
                        gap="1rem",
                    ),
                    background="#fff8e1",
                    border="1px solid #f9c74f",
                    border_radius="4px",
                    padding="0.75rem 1rem",
                    margin_bottom="1rem",
                ),
                rx.fragment(),
            ),
            # Search — uses on_submit to avoid the on_change auto-setter issue (Reflex 0.9.2).
            rx.form(
                rx.hstack(
                    rx.input(
                        name="search",
                        placeholder="Search by username or email…",
                        default_value=AdminUsersState.search_query,
                        width="min(360px, 100%)",
                        font_family="var(--font-sans)",
                    ),
                    rx.button(
                        "Search",
                        type="submit",
                        background="var(--color-primary)",
                        color="white",
                        border="none",
                        padding="0.4rem 0.9rem",
                        border_radius="4px",
                        cursor="pointer",
                        font_family="var(--font-sans)",
                    ),
                    gap="0.5rem",
                    align="center",
                ),
                on_submit=AdminUsersState.search_users,
                margin_bottom="1rem",
            ),
            # Table
            data_table(
                rows=AdminUsersState.users,
                columns=columns,
                card_primary_key="username",
                is_mobile=False,  # simplified — real mobile detection via state var
                actions=_kebab_menu,
                empty_message="No users found. Create your first user →",
            ),
            padding="2rem",
            max_width="1200px",
            width="100%",
        ),
        _confirm_dispatch(),
        page_footer(),
        align="start",
        width="100%",
        min_height="100vh",
        background="var(--color-background, #f5f0eb)",
    ))
