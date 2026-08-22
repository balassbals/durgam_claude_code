"""Admin permission listing page — /admin/permissions (read-only, seed-only policy)."""

import reflex as rx

from durgam.db import open_session
from durgam.pages.components import admin_page, app_shell
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.repositories.permission import PermissionRepository
from durgam.states.base import BaseState


class AdminPermissionsState(BaseState):
    permissions: list[dict[str, str]] = []

    async def load_permissions(self) -> None:
        """on_load for /admin/permissions — guards session then loads list."""
        guard = self._admin_guard()
        if guard is not None:
            return guard
        with open_session() as session:
            repo = PermissionRepository(session)
            grouped = repo.list_grouped_by_resource()
            perms = []
            for perms_list in grouped.values():
                for p in perms_list:
                    perms.append(
                        {
                            "id": str(p.id),
                            "resource": p.resource,
                            "action": p.action,
                            "scope": p.scope,
                        }
                    )
            self.permissions = perms
        self._load_nav_entries()


def admin_permissions() -> rx.Component:
    columns = [
        TableColumn(key="resource", label="Resource"),
        TableColumn(key="action", label="Action"),
        TableColumn(key="scope", label="Scope"),
    ]

    return admin_page(
        app_shell(
            rx.vstack(
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
                align="start",
                width="100%",
            ),
            container="lg",
        )
    )
