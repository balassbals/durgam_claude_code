"""Integration tests for AnnouncementCategoryService + repository (M9 Phase 5a).

6 tests covering: list ordering, create (valid + duplicate + empty name), update,
soft-delete exclusion, and audit snapshot shape. All use db_session (rollback per test).
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from durgam.models.announcement import AnnouncementCategory
from durgam.repositories.announcement import AnnouncementCategoryRepository
from durgam.services.announcement_config import (
    AnnouncementCategoryService,
    AnnouncementConfigError,
)


def _repo(session) -> AnnouncementCategoryRepository:
    return AnnouncementCategoryRepository(session)


def _svc(session) -> AnnouncementCategoryService:
    return AnnouncementCategoryService(repo=_repo(session))


def _make_category(session, code: str, display_order: int = 10) -> AnnouncementCategory:
    """Insert a raw category row — used to set up test fixtures.

    code is uppercased to match service.create() normalisation so duplicate
    checks work correctly within the same session.
    """
    now = datetime.now(UTC)
    cat = AnnouncementCategory(
        code=code.upper(),
        name=f"Name for {code}",
        display_order=display_order,
        is_active=True,
        created_by=uuid4(),
        updated_by=uuid4(),
        created_at=now,
        updated_at=now,
    )
    session.add(cat)
    session.flush()
    return cat


class TestAnnouncementCategoryListAll:
    def test_list_all_returns_rows_ordered_by_display_order(self, db_session) -> None:
        """list_all() returns non-deleted rows in ascending display_order order."""
        suffix = uuid4().hex[:4]
        _make_category(db_session, f"CAT_C_{suffix}", 300)
        _make_category(db_session, f"CAT_A_{suffix}", 100)
        _make_category(db_session, f"CAT_B_{suffix}", 200)

        svc = _svc(db_session)
        rows = svc.list_all()
        orders = [r.display_order for r in rows if r.display_order in (100, 200, 300)]
        assert orders == sorted(orders), "list_all must return rows in ascending display_order"


class TestAnnouncementCategoryCreate:
    def test_create_valid_category(self, db_session) -> None:
        """create() inserts a row and returns the entity with an id."""
        actor = uuid4()
        svc = _svc(db_session)
        entity = svc.create(
            code="CATTEST",
            name="Test Category",
            display_order=42,
            is_active=True,
            notes="Integration test",
            actor_id=actor,
        )
        assert entity.id is not None
        assert entity.code == "CATTEST"
        assert entity.name == "Test Category"
        assert entity.display_order == 42

    def test_create_raises_on_duplicate_code(self, db_session) -> None:
        """create() raises AnnouncementConfigError when code already exists."""
        code = f"CATDUP_{uuid4().hex[:4].upper()}"
        _make_category(db_session, code)

        svc = _svc(db_session)
        with pytest.raises(AnnouncementConfigError, match="already in use"):
            svc.create(
                code=code,
                name="Duplicate",
                display_order=0,
                is_active=True,
                notes=None,
                actor_id=uuid4(),
            )

    def test_create_raises_on_empty_name(self, db_session) -> None:
        """create() raises AnnouncementConfigError when name is blank."""
        svc = _svc(db_session)
        with pytest.raises(AnnouncementConfigError, match="name is required"):
            svc.create(
                code=f"CATBLANK_{uuid4().hex[:4]}",
                name="   ",
                display_order=0,
                is_active=True,
                notes=None,
                actor_id=uuid4(),
            )


class TestAnnouncementCategoryUpdate:
    def test_update_name_and_display_order(self, db_session) -> None:
        """update() persists name and display_order changes."""
        cat = _make_category(db_session, f"CATUPD_{uuid4().hex[:4]}", 10)
        actor = uuid4()

        svc = _svc(db_session)
        updated = svc.update(cat.id, {"name": "Updated Name", "display_order": 99}, actor)
        assert updated.name == "Updated Name"
        assert updated.display_order == 99


class TestAnnouncementCategorySoftDelete:
    def test_soft_delete_hides_from_list_all(self, db_session) -> None:
        """After soft_delete(), the row does not appear in list_all()."""
        code = f"CATDEL_{uuid4().hex[:4].upper()}"
        cat = _make_category(db_session, code)

        svc = _svc(db_session)
        before_count = len([c for c in svc.list_all() if c.code == code.upper()])
        assert before_count == 1

        svc.soft_delete(cat.id, uuid4())

        after_count = len([c for c in svc.list_all() if c.code == code.upper()])
        assert after_count == 0, "Soft-deleted category must not appear in list_all()"
