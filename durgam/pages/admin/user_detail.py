"""Admin user create/edit page — /admin/users/new and /admin/users/{id}."""

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer
from durgam.pages.shared.permission_check_widget import permission_check_widget
from durgam.states.admin_users import AdminUsersState


def admin_user_create() -> rx.Component:
    return admin_page(rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.link("← Users", href="/admin/users", color="var(--color-primary)",
                        font_size="0.875rem"),
                rx.heading("New User", size="5", font_family="var(--font-sans)"),
                gap="1rem",
                align="center",
                margin_bottom="1.5rem",
            ),
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
            rx.cond(
                AdminUsersState.generated_password != "",
                rx.box(
                    rx.text("Temporary password (shown once — copy it now):", font_weight="600",
                            font_size="0.875rem", margin_bottom="0.25rem"),
                    rx.hstack(
                        rx.code(AdminUsersState.generated_password, font_size="1rem"),
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
            rx.form(
                rx.vstack(
                    rx.box(
                        rx.text("Username *", font_size="0.875rem", font_weight="600",
                                margin_bottom="0.25rem"),
                        rx.input(name="username", placeholder="e.g. jsmith",
                                 font_family="var(--font-sans)"),
                        width="100%",
                    ),
                    rx.box(
                        rx.text("Email *", font_size="0.875rem", font_weight="600",
                                margin_bottom="0.25rem"),
                        rx.input(name="email", placeholder="jsmith@sssihl.edu.in",
                                 font_family="var(--font-sans)"),
                        width="100%",
                    ),
                    rx.box(
                        rx.text("Full name", font_size="0.875rem", font_weight="600",
                                margin_bottom="0.25rem"),
                        rx.input(name="full_name", placeholder="e.g. Jaya Smith (optional)",
                                 font_family="var(--font-sans)"),
                        width="100%",
                    ),
                    rx.text(
                        "Password is auto-generated and emailed to the user. "
                        "They must change it on first login.",
                        font_size="0.8rem",
                        color="var(--color-muted)",
                    ),
                    rx.hstack(
                        rx.button(
                            "Create user",
                            type="submit",
                            background="var(--color-primary)",
                            color="white",
                            border="none",
                            padding="0.5rem 1.5rem",
                            border_radius="4px",
                            cursor="pointer",
                            font_family="var(--font-sans)",
                        ),
                        rx.link("Cancel", href="/admin/users", color="var(--color-muted)",
                                font_size="0.875rem"),
                        gap="1rem",
                        align="center",
                        margin_top="1rem",
                    ),
                    align="start",
                    gap="1rem",
                    width="min(480px, 100%)",
                ),
                on_submit=AdminUsersState.create_user,
            ),
            permission_check_widget(),
            padding="2rem",
            max_width="800px",
            width="100%",
        ),
        page_footer(),
        align="start",
        width="100%",
        min_height="100vh",
        background="var(--color-background, #f5f0eb)",
    ))
