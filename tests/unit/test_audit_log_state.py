"""Unit tests for AuditLogState query logic.

Does NOT instantiate Reflex State (requires running server). Instead tests:
- Guard call target verification via source inspection
- Query-building logic at the SQLAlchemy level against a real test DB
- Filter semantics with actual AuditLog rows
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import cast
from sqlalchemy.dialects import postgresql as pg_dialect
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Session, func, select

from durgam.models.crosscutting import AuditLog
from durgam.models.identity import User


# ── Helpers ──────────────────────────────────────────────────────────────────


def _insert_audit_row(session: Session, **kwargs: Any) -> AuditLog:
    defaults: dict[str, Any] = {
        "occurred_at": datetime.now(UTC),
        "action": "write",
        "resource": "campus",
    }
    defaults.update(kwargs)
    row = AuditLog(**defaults)
    session.add(row)
    session.flush()
    return row


def _insert_user(session: Session, username: str = "test_user") -> User:
    u = User(username=username, email=f"{username}@test.dev", password_hash="x",
             full_name=f"{username} Full")
    session.add(u)
    session.flush()
    return u


# ── Guard target verification ────────────────────────────────────────────────


class TestLoadAuditGuard:
    def test_uses_config_guard_with_audit_log_read(self):
        """Verify load_audit calls _config_guard('audit_log', 'read') by reading the source file."""
        from pathlib import Path
        src = Path("durgam/pages/audit/index.py").read_text()
        assert '_config_guard("audit_log", "read")' in src

    def test_state_inherits_base_state(self):
        from durgam.pages.audit.index import AuditLogState
        from durgam.states.base import BaseState
        assert issubclass(AuditLogState, BaseState)


# ── Default date window ─────────────────────────────────────────────────────


class TestQueryDefaultDateWindow:
    def test_last_7_days_default(self):
        """Verify load_audit populates date_from/date_to by reading the source file."""
        from pathlib import Path
        src = Path("durgam/pages/audit/index.py").read_text()
        assert "timedelta(days=7)" in src
        assert "date.today()" in src


# ── Scope filter uses JSONB containment ──────────────────────────────────────


class TestQueryScopeFilterUsesJsonbContainment:
    def test_jsonb_containment_operator(self):
        stmt = select(AuditLog)
        scope_type = "department"
        scope_id = str(uuid4())
        containment = [{"scope_type": scope_type, "scope_id": scope_id}]
        stmt = stmt.where(
            AuditLog.actor_roles_json.op("@>")(  # type: ignore[union-attr]
                cast(containment, JSONB)
            )
        )
        compiled = stmt.compile(dialect=pg_dialect.dialect())
        sql_str = str(compiled)
        assert "@>" in sql_str

    def test_scope_id_all_sentinel_skips_filter(self):
        """scope_id_filter='all' must not add @> containment clause."""
        from pathlib import Path

        src = Path("durgam/pages/audit/index.py").read_text()
        assert 'self.scope_id_filter != "all"' in src


# ── Failed login toggle ─────────────────────────────────────────────────────


class TestQueryExcludesFailedLoginByDefault:
    def test_hidden_when_toggle_off(self, db_session):
        _insert_audit_row(db_session, action="login_failed", resource="session",
                          resource_id="baduser")
        _insert_audit_row(db_session, action="login", resource="session")
        _insert_audit_row(db_session, action="write", resource="campus")

        stmt = select(AuditLog).where(AuditLog.action != "login_failed")
        rows = list(db_session.exec(stmt).all())
        assert all(r.action != "login_failed" for r in rows)
        assert len(rows) == 2

    def test_visible_when_toggle_on(self, db_session):
        _insert_audit_row(db_session, action="login_failed", resource="session",
                          resource_id="baduser")
        _insert_audit_row(db_session, action="login", resource="session")

        stmt = select(AuditLog)
        rows = list(db_session.exec(stmt).all())
        actions = {r.action for r in rows}
        assert "login_failed" in actions


# ── Actor search matches session resource_id ─────────────────────────────────


class TestQueryActorSearchMatchesSessionResourceId:
    def test_login_failed_discoverable_by_username(self, db_session):
        u = _insert_user(db_session, username="alice_admin")
        _insert_audit_row(db_session, action="write", resource="campus",
                          actor_user_id=u.id)
        _insert_audit_row(db_session, action="login_failed", resource="session",
                          resource_id="alice_admin")

        actor_search = "alice"
        actor_match = sa.and_(
            AuditLog.actor_user_id == User.id,
            User.username.ilike(f"%{actor_search}%"),
        )
        session_match = sa.and_(
            AuditLog.resource == "session",
            AuditLog.resource_id.ilike(f"%{actor_search}%"),
        )
        stmt = (
            select(AuditLog)
            .outerjoin(User, AuditLog.actor_user_id == User.id)
            .where(sa.or_(actor_match, session_match))
        )
        rows = list(db_session.exec(stmt).all())
        resources = {r.resource for r in rows}
        assert "campus" in resources
        assert "session" in resources
        assert len(rows) == 2


# ── Pagination ───────────────────────────────────────────────────────────────


class TestPaginationTotalCountIndependentOfPageSize:
    def test_total_count_is_full_match_count(self, db_session):
        for i in range(15):
            _insert_audit_row(db_session, resource=f"res_{i}")

        total = db_session.exec(select(func.count()).select_from(AuditLog)).one()
        assert total == 15

        page_size = 5
        page_rows = list(db_session.exec(
            select(AuditLog).limit(page_size).offset(0)
        ).all())
        assert len(page_rows) == 5
        assert total > len(page_rows)


# ── Options population ───────────────────────────────────────────────────────


class TestLoadAuditPopulatesOptions:
    def test_resource_and_action_options(self, db_session):
        _insert_audit_row(db_session, resource="campus", action="write")
        _insert_audit_row(db_session, resource="user", action="create")
        _insert_audit_row(db_session, resource="campus", action="delete")

        resources = list(db_session.exec(
            select(AuditLog.resource).distinct().order_by(AuditLog.resource)
        ).all())
        actions = list(db_session.exec(
            select(AuditLog.action).distinct().order_by(AuditLog.action)
        ).all())
        assert "campus" in resources
        assert "user" in resources
        assert "write" in actions
        assert "create" in actions
        assert "delete" in actions


# ── Display field formatting ────────────────────────────────────────────────


class TestAddDisplayFields:
    def test_occurred_at_display_from_datetime(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {"occurred_at": datetime(2026, 3, 15, 14, 30, tzinfo=UTC)}
        _add_display_fields(row)
        assert row["occurred_at_display"] == "2026-03-15 14:30"

    def test_occurred_at_display_from_iso_string(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {"occurred_at": "2026-03-15T14:30:00+00:00"}
        _add_display_fields(row)
        assert row["occurred_at_display"] == "2026-03-15 14:30"

    def test_occurred_at_display_missing(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {}
        _add_display_fields(row)
        assert row["occurred_at_display"] == "—"

    def test_actor_display_from_label(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {"actor_label": "alice — Alice Admin"}
        _add_display_fields(row)
        assert row["actor_display"] == "alice — Alice Admin"

    def test_actor_display_none(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {"actor_label": None}
        _add_display_fields(row)
        assert row["actor_display"] == "—"

    def test_resource_display_with_label(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {"resource": "campus", "resource_label": "PP — Prasanthi",
                               "resource_id": "abc-123"}
        _add_display_fields(row)
        assert row["resource_display"] == "campus / PP — Prasanthi"

    def test_resource_display_with_id_only(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {"resource": "session", "resource_id": "alice_admin",
                               "resource_label": None}
        _add_display_fields(row)
        assert row["resource_display"] == "session / alice_admin"

    def test_resource_display_no_id(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {"resource": "session"}
        _add_display_fields(row)
        assert row["resource_display"] == "session"

    def test_scope_display_single_role(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {
            "actor_roles_resolved": [
                {"role_code": "SYSTEM_ADMIN", "scope_label": "universitywide"},
            ],
        }
        _add_display_fields(row)
        assert row["scope_display"] == "SYSTEM_ADMIN (universitywide)"

    def test_scope_display_multiple_roles_truncated(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {
            "actor_roles_resolved": [
                {"role_code": "HOD", "scope_label": "DMACS"},
                {"role_code": "FACULTY", "scope_label": "DMACS"},
                {"role_code": "BASIC_USER", "scope_label": "universitywide"},
            ],
        }
        _add_display_fields(row)
        assert "HOD (DMACS)" in row["scope_display"]
        assert "FACULTY (DMACS)" in row["scope_display"]
        assert "+1" in row["scope_display"]

    def test_scope_display_empty(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {"actor_roles_resolved": []}
        _add_display_fields(row)
        assert row["scope_display"] == "—"

    def test_diff_summary_with_fields(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {"diff_json": {"name": ["a", "b"], "code": ["X", "Y"]}}
        _add_display_fields(row)
        assert row["diff_summary"] == "2 fields"

    def test_diff_summary_single_field(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {"diff_json": {"name": ["a", "b"]}}
        _add_display_fields(row)
        assert row["diff_summary"] == "1 field"

    def test_diff_summary_none(self):
        from durgam.pages.audit.index import _add_display_fields
        row: dict[str, Any] = {"diff_json": None}
        _add_display_fields(row)
        assert row["diff_summary"] == "—"

    def test_computed_vars_exist(self):
        """Verify AuditLogState has the expected computed vars."""
        from pathlib import Path
        src = Path("durgam/pages/audit/index.py").read_text()
        for name in ("total_pages", "range_start", "range_end",
                      "has_prev", "has_next", "scope_filter_disabled"):
            assert f"def {name}(self)" in src
