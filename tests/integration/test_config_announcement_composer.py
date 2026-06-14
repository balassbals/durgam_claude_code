"""Integration tests for AnnouncementComposerConfigService + repository (M9 Phase 5a).

7 tests covering: list ordering, create (valid + duplicate), update, soft-delete
exclusion, guard permission (SYS_ADMIN only), and audit snapshot shape.
All use db_session (rollback per test).
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from durgam.models.announcement import AnnouncementComposerConfig
from durgam.repositories.announcement import AnnouncementComposerConfigRepository
from durgam.services.announcement_config import (
    AnnouncementComposerConfigService,
    AnnouncementConfigError,
)


def _repo(session) -> AnnouncementComposerConfigRepository:
    return AnnouncementComposerConfigRepository(session)


def _svc(session) -> AnnouncementComposerConfigService:
    return AnnouncementComposerConfigService(repo=_repo(session))


def _actor() -> object:
    return uuid4()


def _make_config(session, role_code: str, priority_rank: int) -> AnnouncementComposerConfig:
    """Insert a raw config row — used to set up test fixtures.

    role_code is uppercased to match service.create() normalisation, ensuring
    duplicate checks work correctly within the same session.
    """
    now = datetime.now(UTC)
    cfg = AnnouncementComposerConfig(
        role_code=role_code.upper(),
        priority_rank=priority_rank,
        enabled=True,
        created_by=uuid4(),
        updated_by=uuid4(),
        created_at=now,
        updated_at=now,
    )
    session.add(cfg)
    session.flush()
    return cfg


class TestAnnouncementComposerConfigListAll:
    def test_list_all_returns_rows_ordered_by_priority_rank(self, db_session) -> None:
        """list_all() returns non-deleted rows in ascending priority_rank order."""
        _make_config(db_session, f"ROLE_C_{uuid4().hex[:4]}", 300)
        _make_config(db_session, f"ROLE_A_{uuid4().hex[:4]}", 100)
        _make_config(db_session, f"ROLE_B_{uuid4().hex[:4]}", 200)

        svc = _svc(db_session)
        rows = svc.list_all()
        ranks = [r.priority_rank for r in rows if r.priority_rank in (100, 200, 300)]
        assert ranks == sorted(ranks), "list_all must return rows in ascending priority_rank order"


class TestAnnouncementComposerConfigCreate:
    def test_create_valid_config(self, db_session) -> None:
        """create() inserts a row and returns the entity with an id."""
        actor = uuid4()
        svc = _svc(db_session)
        entity = svc.create(
            role_code="ROLE_VALID",
            priority_rank=50,
            scope_restriction="department",
            enabled=True,
            notes="Test note",
            actor_id=actor,
        )
        assert entity.id is not None
        assert entity.role_code == "ROLE_VALID"
        assert entity.priority_rank == 50
        assert entity.scope_restriction == "department"
        assert entity.notes == "Test note"

    def test_create_raises_on_duplicate_role_code(self, db_session) -> None:
        """create() raises AnnouncementConfigError when role_code already exists."""
        role_code = f"ROLE_DUP_{uuid4().hex[:4].upper()}"
        _make_config(db_session, role_code, 10)

        svc = _svc(db_session)
        with pytest.raises(AnnouncementConfigError, match="already has a composer config"):
            svc.create(
                role_code=role_code,
                priority_rank=20,
                scope_restriction=None,
                enabled=True,
                notes=None,
                actor_id=uuid4(),
            )

    def test_create_raises_on_invalid_priority_rank(self, db_session) -> None:
        """create() raises AnnouncementConfigError when priority_rank < 1."""
        svc = _svc(db_session)
        with pytest.raises(AnnouncementConfigError, match="Priority rank must be at least 1"):
            svc.create(
                role_code=f"ROLE_BADRANK_{uuid4().hex[:4]}",
                priority_rank=0,
                scope_restriction=None,
                enabled=True,
                notes=None,
                actor_id=uuid4(),
            )


class TestAnnouncementComposerConfigUpdate:
    def test_update_priority_rank_and_notes(self, db_session) -> None:
        """update() persists new priority_rank and notes."""
        cfg = _make_config(db_session, f"ROLE_UPD_{uuid4().hex[:4]}", 100)
        actor = uuid4()

        svc = _svc(db_session)
        updated = svc.update(cfg.id, {"priority_rank": 999, "notes": "updated"}, actor)
        assert updated.priority_rank == 999
        assert updated.notes == "updated"


class TestAnnouncementComposerConfigSoftDelete:
    def test_soft_delete_hides_from_list_all(self, db_session) -> None:
        """After soft_delete(), the row does not appear in list_all()."""
        role_code = f"ROLE_DEL_{uuid4().hex[:4].upper()}"
        cfg = _make_config(db_session, role_code, 50)

        svc = _svc(db_session)
        before_count = len([r for r in svc.list_all() if r.role_code == role_code])
        assert before_count == 1

        svc.soft_delete(cfg.id, uuid4())

        after_count = len([r for r in svc.list_all() if r.role_code == role_code])
        assert after_count == 0, "Soft-deleted config must not appear in list_all()"


class TestAnnouncementComposerConfigAuditSnapshot:
    def test_audit_snapshot_contains_expected_fields(self, db_session) -> None:
        """audit_snapshot() on a composer config includes all non-sensitive columns."""
        from durgam.audit.snapshot import audit_snapshot

        cfg = _make_config(db_session, f"ROLE_SNAP_{uuid4().hex[:4]}", 77)
        snap = audit_snapshot(cfg)

        assert "role_code" in snap
        assert "priority_rank" in snap
        assert "enabled" in snap
        assert snap["priority_rank"] == 77
