"""Admin permission listing page — /admin/permissions (read-only, seed-only policy)."""

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.pages.components import nav_shell, page_footer
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.repositories.permission import PermissionRepository
from durgam.states.base import BaseState


class AdminPermissionsState(BaseState):
    permissions: list[dict] = []

    @require_role(action="read", resource="permission")
    @audit_action(action="list", resource="permission")
    async def load_permissions(self) -> None:
        with open_session() as session:
            repo = PermissionRepository(session)
            grouped = repo.list_grouped_by_resource()
            perms = []
            for perms_list in grouped.values():
                for p in perms_list:
                    perms.append({
                        "id": str(p.id),
                        "resource": p.resource,
                        "action": p.action,
                        "scope": p.scope,
                    })
            self.permissions = perms
        self._load_nav_entries()


def admin_permissions() -> rx.Component:
    columns = [
        TableColumn(key="resource", label="Resource"),
        TableColumn(key="action", label="Action"),
        TableColumn(key="scope", label="Scope"),
    ]

    return rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.heading("Permissions", size="5", font_family="var(--font-sans)"),
                rx.spacer(),
                rx.text(
                    "Read-only — permissions are defined in the seed script.",
                    font_size="0.8rem",
                    color="var(--color-muted)",
                    font_family="var(--font-sans)",
                ),
                align="center",
                width="100%",
                margin_bottom="1rem",
            ),
            data_table(
                rows=AdminPermissionsState.permissions,
                columns=columns,
                card_primary_key="resource",
                is_mobile=False,
                empty_message="No permissions seeded. Run scripts/seed.py.",
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
