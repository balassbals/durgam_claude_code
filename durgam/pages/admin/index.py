"""Admin landing page — /admin."""

import reflex as rx

from durgam.pages.components import nav_shell, page_footer
from durgam.states.admin_index import AdminIndexState


def _stat_card(label: str, value: object) -> rx.Component:
    return rx.box(
        rx.text(label, font_size="0.8rem", color="var(--color-muted)",
                font_family="var(--font-sans)"),
        rx.text(
            value,
            font_size="2rem",
            font_weight="700",
            color="var(--color-primary)",
            font_family="var(--font-sans)",
        ),
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="1rem 1.5rem",
        background="white",
        flex="1",
        min_width="140px",
    )


def _nav_tile(label: str, href: str, description: str) -> rx.Component:
    return rx.link(
        rx.box(
            rx.text(label, font_weight="600", font_family="var(--font-sans)"),
            rx.text(description, font_size="0.8rem", color="var(--color-muted)",
                    font_family="var(--font-sans)"),
            border="1px solid var(--color-rule)",
            border_radius="8px",
            padding="1.25rem",
            background="white",
            _hover={"border_color": "var(--color-primary)",
                    "box_shadow": "0 2px 8px rgba(0,0,0,0.08)"},
            transition="border-color 0.15s, box-shadow 0.15s",
        ),
        href=href,
        text_decoration="none",
        color="var(--color-body)",
    )


def admin_index() -> rx.Component:
    return rx.vstack(
        nav_shell(),
        rx.box(
            rx.heading("Admin Dashboard", size="5", font_family="var(--font-sans)",
                       margin_bottom="1.5rem"),

            # Stats row
            rx.flex(
                _stat_card("Active Users", AdminIndexState.active_user_count),
                _stat_card("Roles", AdminIndexState.role_count),
                _stat_card(
                    "Pending Password Changes",
                    AdminIndexState.pending_password_change_count,
                ),
                gap="1rem",
                flex_wrap="wrap",
                margin_bottom="2rem",
            ),

            # Navigation tiles
            rx.heading("Quick Access", size="3", font_family="var(--font-sans)",
                       margin_bottom="1rem"),
            rx.grid(
                _nav_tile("Users", "/admin/users", "Create, edit, and manage user accounts"),
                _nav_tile("Roles", "/admin/roles", "Define roles and assign permissions"),
                _nav_tile("Permissions", "/admin/permissions", "View the permission catalog"),
                _nav_tile("Import Users", "/admin/import", "Bulk-import users from CSV"),
                _nav_tile("Audit Log", "/audit", "View system audit history (M6)"),
                columns="repeat(auto-fill, minmax(220px, 1fr))",
                gap="1rem",
            ),
            padding="2rem",
            max_width="1200px",
            width="100%",
        ),
        page_footer(),
        align="start",
        width="100%",
        min_height="100vh",
        background="var(--color-background, #f5f0eb)",
    )
