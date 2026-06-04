"""Audit Log — sys-admin-only audit viewer."""

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
from durgam.pages.components import (
    admin_page, nav_shell, page_footer, primary_btn, secondary_btn,
)
from durgam.pages.shared.data_table import TableColumn, data_table
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

    # ── Computed vars ────────────────────────────────────────────────────────

    @rx.var
    def total_pages(self) -> int:
        return max(1, math.ceil(self.total_count / self.page_size))

    @rx.var
    def range_start(self) -> int:
        if self.total_count == 0:
            return 0
        return (self.page - 1) * self.page_size + 1

    @rx.var
    def range_end(self) -> int:
        return min(self.page * self.page_size, self.total_count)

    @rx.var
    def has_prev(self) -> bool:
        return self.page > 1

    @rx.var
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @rx.var
    def scope_filter_disabled(self) -> bool:
        return self.scope_type_filter == "all"

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
            if self.selected_row is not None:
                _add_display_fields(self.selected_row)
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

        for rd in self.rows:
            _add_display_fields(rd)
        self.loading = False


def _add_display_fields(row_dict: dict[str, Any]) -> None:
    """Add display-ready string fields to an enriched audit row dict."""
    occ = row_dict.get("occurred_at")
    if isinstance(occ, datetime):
        row_dict["occurred_at_display"] = occ.strftime("%Y-%m-%d %H:%M")
    elif isinstance(occ, str) and len(occ) >= 16:
        row_dict["occurred_at_display"] = occ[:16].replace("T", " ")
    else:
        row_dict["occurred_at_display"] = "—"

    row_dict["actor_display"] = row_dict.get("actor_label") or "—"

    resource = row_dict.get("resource", "")
    rlabel = row_dict.get("resource_label")
    rid = row_dict.get("resource_id")
    if rlabel:
        row_dict["resource_display"] = f"{resource} / {rlabel}"
    elif rid:
        row_dict["resource_display"] = f"{resource} / {rid}"
    else:
        row_dict["resource_display"] = resource

    roles: list[dict[str, Any]] = row_dict.get("actor_roles_resolved", [])
    if roles:
        parts: list[str] = []
        for r in roles[:2]:
            sl = r.get("scope_label", "")
            parts.append(f"{r.get('role_code', '')} ({sl})")
        s = "; ".join(parts)
        if len(roles) > 2:
            s += f" +{len(roles) - 2}"
        row_dict["scope_display"] = s
    else:
        row_dict["scope_display"] = "—"

    diff = row_dict.get("diff_json")
    if diff and isinstance(diff, dict):
        n = len(diff)
        row_dict["diff_summary"] = f"{n} field{'s' if n != 1 else ''}"
    else:
        row_dict["diff_summary"] = "—"


# ── UI helpers ──────────────────────────────────────────────────────────────


def _row_actions(row: rx.Var) -> rx.Component:
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
                "View Details",
                on_click=AuditLogState.open_detail(row["id"]),  # type: ignore[call-arg, func-returns-value]
            ),
        ),
    )


def _filter_strip() -> rx.Component:
    return rx.flex(
        rx.vstack(
            rx.text("From", font_size="0.75rem", color="var(--color-muted)",
                     font_family="var(--font-sans)"),
            rx.input(
                type="date",
                value=AuditLogState.date_from,
                on_change=AuditLogState.set_date_from,
                width="150px",
            ),
            gap="0.25rem",
        ),
        rx.vstack(
            rx.text("To", font_size="0.75rem", color="var(--color-muted)",
                     font_family="var(--font-sans)"),
            rx.input(
                type="date",
                value=AuditLogState.date_to,
                on_change=AuditLogState.set_date_to,
                width="150px",
            ),
            gap="0.25rem",
        ),
        rx.vstack(
            rx.text("Actor", font_size="0.75rem", color="var(--color-muted)",
                     font_family="var(--font-sans)"),
            rx.input(
                placeholder="username…",
                value=AuditLogState.actor_search,
                on_change=AuditLogState.set_actor_search,
                width="150px",
            ),
            gap="0.25rem",
        ),
        rx.vstack(
            rx.text("Resource", font_size="0.75rem", color="var(--color-muted)",
                     font_family="var(--font-sans)"),
            rx.select.root(
                rx.select.trigger(placeholder="All"),
                rx.select.content(
                    rx.select.item("All", value="all"),
                    rx.foreach(
                        AuditLogState.resource_options,
                        lambda o: rx.select.item(o, value=o),
                    ),
                ),
                value=AuditLogState.resource_filter,
                on_change=AuditLogState.set_resource_filter,
                width="150px",
            ),
            gap="0.25rem",
        ),
        rx.vstack(
            rx.text("Action", font_size="0.75rem", color="var(--color-muted)",
                     font_family="var(--font-sans)"),
            rx.select.root(
                rx.select.trigger(placeholder="All"),
                rx.select.content(
                    rx.select.item("All", value="all"),
                    rx.foreach(
                        AuditLogState.action_options,
                        lambda o: rx.select.item(o, value=o),
                    ),
                ),
                value=AuditLogState.action_filter,
                on_change=AuditLogState.set_action_filter,
                width="140px",
            ),
            gap="0.25rem",
        ),
        rx.vstack(
            rx.text("Scope", font_size="0.75rem", color="var(--color-muted)",
                     font_family="var(--font-sans)"),
            rx.select.root(
                rx.select.trigger(placeholder="All"),
                rx.select.content(
                    rx.select.item("All", value="all"),
                    rx.select.item("Campus", value="campus"),
                    rx.select.item("School", value="school"),
                    rx.select.item("Department", value="department"),
                    rx.select.item("Centre", value="centre"),
                ),
                value=AuditLogState.scope_type_filter,
                on_change=AuditLogState.on_scope_type_change,
                width="140px",
            ),
            gap="0.25rem",
        ),
        rx.vstack(
            rx.text("Scope entity", font_size="0.75rem", color="var(--color-muted)",
                     font_family="var(--font-sans)"),
            rx.cond(
                AuditLogState.scope_filter_disabled,
                rx.select.root(
                    rx.select.trigger(placeholder="Select scope first"),
                    rx.select.content(rx.select.item("—", value="")),
                    disabled=True,
                    width="160px",
                ),
                rx.select.root(
                    rx.select.trigger(placeholder="Select entity"),
                    rx.select.content(
                        rx.foreach(
                            AuditLogState.scope_options,
                            lambda o: rx.select.item(
                                o["label"], value=o["id"],  # type: ignore[index]
                            ),
                        ),
                    ),
                    value=AuditLogState.scope_id_filter,
                    on_change=AuditLogState.set_scope_id_filter,
                    width="160px",
                ),
            ),
            gap="0.25rem",
        ),
        rx.vstack(
            rx.text("", font_size="0.75rem"),
            rx.hstack(
                rx.checkbox(
                    checked=AuditLogState.include_failed_login,
                    on_change=AuditLogState.set_include_failed_login,
                ),
                rx.text("Show failed logins", font_size="0.85rem",
                         font_family="var(--font-sans)"),
                align="center",
                gap="0.5rem",
                height="2rem",
            ),
            gap="0.25rem",
        ),
        rx.vstack(
            rx.text("", font_size="0.75rem"),
            rx.hstack(
                primary_btn("Apply", on_click=AuditLogState.apply_filters),
                secondary_btn("Reset", on_click=AuditLogState.reset_filters),
                secondary_btn(
                    "↻", on_click=AuditLogState.refresh,
                    padding="0.5rem 0.75rem",
                ),
                gap="0.5rem",
            ),
            gap="0.25rem",
        ),
        wrap="wrap",
        gap="0.75rem",
        align="end",
        padding="1rem",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        background="white",
        margin_bottom="1rem",
    )


def _result_summary() -> rx.Component:
    return rx.cond(
        AuditLogState.total_count > 0,
        rx.text(
            rx.text.span("Showing "),
            rx.text.span(AuditLogState.range_start, font_weight="600"),
            rx.text.span("–"),
            rx.text.span(AuditLogState.range_end, font_weight="600"),
            rx.text.span(" of "),
            rx.text.span(AuditLogState.total_count, font_weight="600"),
            font_size="0.85rem",
            color="var(--color-muted)",
            font_family="var(--font-sans)",
            margin_bottom="0.75rem",
        ),
        rx.text(
            "No matching audit entries.",
            font_size="0.85rem",
            color="var(--color-muted)",
            font_family="var(--font-sans)",
            margin_bottom="0.75rem",
        ),
    )


def _pagination() -> rx.Component:
    return rx.hstack(
        secondary_btn(
            "← Prev",
            on_click=AuditLogState.prev_page,
            disabled=~AuditLogState.has_prev,
            opacity=rx.cond(AuditLogState.has_prev, "1", "0.4"),
        ),
        rx.text(
            rx.text.span("Page "),
            rx.text.span(AuditLogState.page, font_weight="600"),
            rx.text.span(" of "),
            rx.text.span(AuditLogState.total_pages, font_weight="600"),
            font_size="0.85rem",
            color="var(--color-muted)",
            font_family="var(--font-sans)",
        ),
        secondary_btn(
            "Next →",
            on_click=AuditLogState.next_page,
            disabled=~AuditLogState.has_next,
            opacity=rx.cond(AuditLogState.has_next, "1", "0.4"),
        ),
        justify="center",
        align="center",
        gap="1rem",
        margin_top="1rem",
        width="100%",
    )


def _detail_field(label: str, value: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.text(
            label + ":",
            font_size="0.75rem",
            color="var(--color-muted)",
            font_family="var(--font-sans)",
            min_width="100px",
            font_weight="600",
        ),
        rx.text(value, font_size="0.875rem", font_family="var(--font-sans)"),
        align="start",
        gap="0.75rem",
        width="100%",
        padding_y="0.25rem",
    )


def _detail_drawer() -> rx.Component:
    row = AuditLogState.selected_row
    return rx.drawer.root(
        rx.drawer.overlay(z_index="50"),
        rx.drawer.portal(
            rx.drawer.content(
                rx.cond(
                    row,
                    rx.vstack(
                        rx.hstack(
                            rx.heading(
                                "Audit Entry",
                                size="4",
                                font_family="var(--font-sans)",
                            ),
                            rx.spacer(),
                            rx.button(
                                "✕",
                                on_click=AuditLogState.close_detail,
                                background="transparent",
                                border="none",
                                cursor="pointer",
                                font_size="1.1rem",
                                color="var(--color-muted)",
                                padding="0.25rem",
                            ),
                            align="center",
                            width="100%",
                        ),
                        rx.divider(),
                        _detail_field("When", row["occurred_at_display"]),  # type: ignore[index]
                        _detail_field("Actor", row["actor_display"]),  # type: ignore[index]
                        _detail_field("Role", row["actor_role_code"]),  # type: ignore[index]
                        _detail_field("Action", row["action"]),  # type: ignore[index]
                        _detail_field("Resource", row["resource_display"]),  # type: ignore[index]
                        _detail_field("Scope", row["scope_display"]),  # type: ignore[index]
                        _detail_field("Changes", row["diff_summary"]),  # type: ignore[index]
                        _detail_field("Request ID", row["request_id"]),  # type: ignore[index]
                        _detail_field("IP", row["ip"]),  # type: ignore[index]
                        _detail_field("User Agent", row["user_agent"]),  # type: ignore[index]
                        rx.divider(),
                        rx.text(
                            "Full diff and change history view coming in a future phase.",
                            font_size="0.8rem",
                            color="var(--color-muted)",
                            font_style="italic",
                            font_family="var(--font-sans)",
                        ),
                        align="start",
                        gap="0.25rem",
                        padding="1.5rem",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                top="0",
                right="0",
                height="100%",
                width="min(480px, 90vw)",
                background="white",
                border_left="1px solid var(--color-rule)",
                overflow_y="auto",
            ),
        ),
        open=AuditLogState.detail_open,
        on_open_change=AuditLogState.set_detail_open,
        direction="right",
    )


_AUDIT_COLUMNS = [
    TableColumn(key="occurred_at_display", label="When"),
    TableColumn(key="actor_display", label="Who"),
    TableColumn(key="action", label="Action"),
    TableColumn(key="resource_display", label="Resource"),
    TableColumn(key="scope_display", label="Scope", hidden_on_card=True),
    TableColumn(key="diff_summary", label="Changes", hidden_on_card=True),
]


def audit_log() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.link(
                        "← Admin", href="/admin",
                        color="var(--color-primary)", font_size="0.875rem",
                    ),
                    rx.vstack(
                        rx.heading(
                            "Audit Log", size="5",
                            font_family="var(--font-sans)",
                        ),
                        rx.text(
                            "System-wide activity log",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                            font_family="var(--font-sans)",
                        ),
                        gap="0.125rem",
                    ),
                    gap="1rem",
                    align="center",
                    margin_bottom="1.5rem",
                ),
                _filter_strip(),
                _result_summary(),
                rx.cond(
                    AuditLogState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=AuditLogState.rows,
                        columns=_AUDIT_COLUMNS,
                        card_primary_key="occurred_at_display",
                        is_mobile=False,
                        actions=_row_actions,
                        empty_message="No audit entries found.",
                    ),
                ),
                _pagination(),
                padding="2rem",
                max_width="1200px",
                width="100%",
            ),
            _detail_drawer(),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
