"""Audit Log — sys-admin-only audit viewer (M6b Phase 1: state shell)."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID

import reflex as rx
import sqlalchemy as sa
from sqlalchemy import cast, func
from sqlalchemy.dialects.postgresql import JSONB

from durgam.audit.labels import bulk_resolve_labels
from durgam.db import open_session
from durgam.pages.components import admin_page, nav_shell, page_footer
from durgam.scopes.registry import load_scope_objects
from durgam.states.base import BaseState


class AuditLogState(BaseState):
    """Full state shell for the audit log viewer. UI is Phase 2."""

    # ── Filter state vars ────────────────────────────────────────────────────
    date_from: str = ""
    date_to: str = ""
    actor_search: str = ""
    resource_filter: str = "all"
    action_filter: str = "all"
    scope_type_filter: str = "all"
    scope_id_filter: str = ""
    include_failed_login: bool = False
    page: int = 1
    page_size: int = 50

    # ── Result state vars ────────────────────────────────────────────────────
    rows: list[dict[str, Any]] = []
    total_count: int = 0
    resource_options: list[str] = []
    action_options: list[str] = []
    scope_options: list[dict[str, str]] = []
    selected_row: dict[str, Any] | None = None
    detail_open: bool = False
    loading: bool = True

    # ── Handlers ─────────────────────────────────────────────────────────────

    async def load_audit(self) -> None:
        guard = self._config_guard("audit_log", "read")
        if guard is not None:
            return guard
        self.loading = True
        self.rows = []
        self.total_count = 0
        self.page = 1

        if not self.date_from:
            self.date_from = (date.today() - timedelta(days=7)).isoformat()
        if not self.date_to:
            self.date_to = date.today().isoformat()

        self._populate_options()
        self._run_query()
        self._load_nav_entries()

    def apply_filters(self) -> None:
        self.page = 1
        self._run_query()

    def reset_filters(self) -> None:
        self.date_from = (date.today() - timedelta(days=7)).isoformat()
        self.date_to = date.today().isoformat()
        self.actor_search = ""
        self.resource_filter = "all"
        self.action_filter = "all"
        self.scope_type_filter = "all"
        self.scope_id_filter = ""
        self.include_failed_login = False
        self.page = 1
        self._run_query()

    def change_page(self, n: int) -> None:
        self.page = max(1, n)
        self._run_query()

    def next_page(self) -> None:
        max_page = max(1, math.ceil(self.total_count / self.page_size))
        if self.page < max_page:
            self.page += 1
            self._run_query()

    def prev_page(self) -> None:
        if self.page > 1:
            self.page -= 1
            self._run_query()

    def on_scope_type_change(self, value: str) -> None:
        self.scope_type_filter = value
        self.scope_id_filter = ""
        self.scope_options = []
        if value != "all":
            with open_session() as session:
                self.scope_options = load_scope_objects(value, session)

    def refresh(self) -> None:
        self._run_query()

    def open_detail(self, audit_id: int) -> None:
        from durgam.models.crosscutting import AuditLog

        with open_session() as session:
            from sqlmodel import select as sel
            stmt = sel(AuditLog).where(AuditLog.id == audit_id)
            row = session.exec(stmt).first()
            if row is None:
                self.selected_row = None
                self.detail_open = False
                return
            enriched = bulk_resolve_labels([row], session)
            self.selected_row = enriched[0] if enriched else None
            self.detail_open = True

    def close_detail(self) -> None:
        self.selected_row = None
        self.detail_open = False

    # ── Private ──────────────────────────────────────────────────────────────

    def _populate_options(self) -> None:
        from durgam.models.crosscutting import AuditLog

        with open_session() as session:
            from sqlmodel import select as sel
            res = session.exec(
                sel(AuditLog.resource).distinct().order_by(AuditLog.resource)
            ).all()
            self.resource_options = list(res)

            act = session.exec(
                sel(AuditLog.action).distinct().order_by(AuditLog.action)
            ).all()
            self.action_options = list(act)

    def _run_query(self) -> None:
        from durgam.models.crosscutting import AuditLog

        self.loading = True
        with open_session() as session:
            from sqlmodel import select as sel

            stmt = sel(AuditLog)
            conditions: list[Any] = []

            if self.date_from:
                dt_from = datetime.combine(
                    date.fromisoformat(self.date_from), time.min, tzinfo=UTC,
                )
                conditions.append(AuditLog.occurred_at >= dt_from)

            if self.date_to:
                dt_to = datetime.combine(
                    date.fromisoformat(self.date_to), time.max, tzinfo=UTC,
                )
                conditions.append(AuditLog.occurred_at <= dt_to)

            if self.actor_search:
                from durgam.models.identity import User
                actor_match = sa.and_(
                    AuditLog.actor_user_id == User.id,
                    User.username.ilike(f"%{self.actor_search}%"),
                )
                session_match = sa.and_(
                    AuditLog.resource == "session",
                    AuditLog.resource_id.ilike(f"%{self.actor_search}%"),
                )
                stmt = stmt.outerjoin(User, AuditLog.actor_user_id == User.id)
                conditions.append(sa.or_(actor_match, session_match))

            if self.resource_filter and self.resource_filter != "all":
                conditions.append(AuditLog.resource == self.resource_filter)

            if self.action_filter and self.action_filter != "all":
                conditions.append(AuditLog.action == self.action_filter)

            if (
                self.scope_type_filter
                and self.scope_type_filter != "all"
                and self.scope_id_filter
            ):
                containment = [{"scope_type": self.scope_type_filter, "scope_id": self.scope_id_filter}]
                conditions.append(
                    AuditLog.actor_roles_json.op("@>")(  # type: ignore[union-attr]
                        cast(containment, JSONB)
                    )
                )

            if not self.include_failed_login:
                conditions.append(AuditLog.action != "login_failed")

            for cond in conditions:
                stmt = stmt.where(cond)

            count_sub = stmt.with_only_columns(func.count()).order_by(None)
            self.total_count = session.exec(count_sub).one()

            stmt = stmt.order_by(
                AuditLog.occurred_at.desc(), AuditLog.id.desc(),
            )
            offset = (self.page - 1) * self.page_size
            stmt = stmt.offset(offset).limit(self.page_size)

            audit_rows = list(session.exec(stmt).all())
            self.rows = bulk_resolve_labels(audit_rows, session)

        self.loading = False


def audit_log() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.link("← Admin", href="/admin", color="var(--color-primary)",
                            font_size="0.875rem"),
                    rx.heading("Audit Log", size="5", font_family="var(--font-sans)"),
                    gap="1rem", align="center", margin_bottom="1.5rem",
                ),
                rx.box(
                    rx.vstack(
                        rx.text("🔒", font_size="2.5rem"),
                        rx.heading("Coming in M6", size="4",
                                   color="var(--color-body)", font_family="var(--font-sans)"),
                        rx.text(
                            "The Audit Log module ships at Milestone 6. "
                            "Until then, audit data can be queried directly via the database.",
                            font_size="0.9rem",
                            color="var(--color-muted)",
                            text_align="center",
                            max_width="420px",
                        ),
                        rx.text(
                            "Contact System Admin for direct database access.",
                            font_size="0.875rem",
                            color="var(--color-muted)",
                        ),
                        align="center",
                        gap="0.75rem",
                        padding="3rem",
                    ),
                    border="1px solid var(--color-rule)",
                    border_radius="8px",
                    background="white",
                ),
                padding="2rem",
                max_width="700px",
                width="100%",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
