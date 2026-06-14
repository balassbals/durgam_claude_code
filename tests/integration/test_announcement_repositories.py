"""Integration tests for M9 announcement repositories.

10 tests covering: CRUD, list filtering, JSONB visibility query, soft-delete,
withdraw, and list_by_composer. All use db_session (rollback per test).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from durgam.models.announcement import (
    Announcement,
    AnnouncementCategory,
    AnnouncementComposerConfig,
    AudienceGroup,
)
from durgam.models.identity import User
from durgam.repositories.announcement import (
    AnnouncementCategoryRepository,
    AnnouncementComposerConfigRepository,
    AnnouncementRepository,
    AudienceGroupRepository,
)
from durgam.services.password import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(session) -> User:
    u = User(
        username=f"t{uuid4().hex[:8]}",
        email=f"t{uuid4().hex[:8]}@test.local",
        full_name="Test User",
        password_hash=hash_password("Test_Dev1!XZ"),
        is_active=True,
    )
    session.add(u)
    session.flush()
    return u


def _now() -> datetime:
    return datetime.now(UTC)


def _ann(composer_id: UUID, audience_group_codes: list[str], *, scheduled_at: datetime | None = None, importance: str = "normal") -> Announcement:
    return Announcement(
        title=f"Ann {uuid4().hex[:6]}",
        message_text="Test message",
        scheduled_at=scheduled_at or _now(),
        importance=importance,
        category_code="NOTICE",
        audience_group_codes=audience_group_codes,
        composer_user_id=composer_id,
        composer_role_code="FACULTY",
        source_type="manual",
    )


# ---------------------------------------------------------------------------
# AnnouncementCategoryRepository
# ---------------------------------------------------------------------------

def test_category_create_get_by_code(db_session):
    repo = AnnouncementCategoryRepository(db_session)
    cat = AnnouncementCategory(code="CAT_REPO1", name="Repo Test 1", display_order=50)
    created = repo.create(cat)
    assert created.id is not None

    found = repo.get_by_code("CAT_REPO1")
    assert found is not None
    assert found.name == "Repo Test 1"


def test_category_list_active_excludes_inactive(db_session):
    repo = AnnouncementCategoryRepository(db_session)
    repo.create(AnnouncementCategory(code="CAT_ACTIVE", name="Active", is_active=True, display_order=1))
    repo.create(AnnouncementCategory(code="CAT_INACTIVE", name="Inactive", is_active=False, display_order=2))

    active_codes = {c.code for c in repo.list_active()}
    assert "CAT_ACTIVE" in active_codes
    assert "CAT_INACTIVE" not in active_codes


def test_category_soft_delete_excluded_from_get(db_session):
    repo = AnnouncementCategoryRepository(db_session)
    cat = repo.create(AnnouncementCategory(code="CAT_DEL", name="To Delete", display_order=99))
    actor = _user(db_session)

    repo.soft_delete(cat.id, actor.id)
    assert repo.get_by_code("CAT_DEL") is None
    assert repo.get(cat.id) is None


# ---------------------------------------------------------------------------
# AnnouncementComposerConfigRepository
# ---------------------------------------------------------------------------

def test_composer_config_list_enabled_ordered(db_session):
    repo = AnnouncementComposerConfigRepository(db_session)
    repo.create(AnnouncementComposerConfig(role_code="ROLE_A", priority_rank=20, enabled=True))
    repo.create(AnnouncementComposerConfig(role_code="ROLE_B", priority_rank=10, enabled=True))
    repo.create(AnnouncementComposerConfig(role_code="ROLE_C", priority_rank=30, enabled=False))

    ordered = repo.list_enabled_ordered()
    enabled_codes = [r.role_code for r in ordered]
    assert "ROLE_A" in enabled_codes
    assert "ROLE_B" in enabled_codes
    assert "ROLE_C" not in enabled_codes
    # Verify order: ROLE_B (rank 10) before ROLE_A (rank 20)
    assert enabled_codes.index("ROLE_B") < enabled_codes.index("ROLE_A")


# ---------------------------------------------------------------------------
# AudienceGroupRepository
# ---------------------------------------------------------------------------

def test_audience_group_create_and_list_active(db_session):
    repo = AudienceGroupRepository(db_session)
    repo.create(AudienceGroup(code="AG_ACTIVE", name="Active Group", filter_json={"role_codes": ["FACULTY"]}, is_active=True))
    repo.create(AudienceGroup(code="AG_INACTIVE", name="Inactive Group", filter_json={}, is_active=False))

    active_codes = {g.code for g in repo.list_active()}
    assert "AG_ACTIVE" in active_codes
    assert "AG_INACTIVE" not in active_codes


# ---------------------------------------------------------------------------
# AnnouncementRepository
# ---------------------------------------------------------------------------

def test_announcement_create_and_get(db_session):
    repo = AnnouncementRepository(db_session)
    user = _user(db_session)
    ann = repo.create(_ann(user.id, ["FACULTY_ALL"]))

    found = repo.get(ann.id)
    assert found is not None
    assert found.audience_group_codes == ["FACULTY_ALL"]


def test_list_visible_to_user_group_match(db_session):
    """Announcements targeting user's group are returned."""
    repo = AnnouncementRepository(db_session)
    composer = _user(db_session)
    viewer = _user(db_session)

    # Two announcements: one for FACULTY_ALL (user's group), one for HOD_ALL (not user's)
    ann_visible = repo.create(_ann(composer.id, ["FACULTY_ALL"]))
    ann_hidden = repo.create(_ann(composer.id, ["HOD_ALL"]))

    now = _now() + timedelta(seconds=1)
    results = repo.list_visible_to_user(viewer.id, {"FACULTY_ALL"}, now)
    result_ids = {r.id for r in results}

    assert ann_visible.id in result_ids
    assert ann_hidden.id not in result_ids


def test_list_visible_to_user_ad_hoc_inclusion(db_session):
    """Ad-hoc user is visible even without group membership."""
    repo = AnnouncementRepository(db_session)
    composer = _user(db_session)
    viewer = _user(db_session)

    ann = Announcement(
        title="Ad hoc announcement",
        message_text="Only for you",
        scheduled_at=_now(),
        importance="normal",
        category_code="NOTICE",
        audience_group_codes=["HOD_ALL"],  # viewer is NOT in HOD_ALL
        ad_hoc_user_ids=[str(viewer.id)],
        composer_user_id=composer.id,
        composer_role_code="FACULTY",
        source_type="manual",
    )
    repo.create(ann)

    now = _now() + timedelta(seconds=1)
    results = repo.list_visible_to_user(viewer.id, set(), now)  # empty groups
    assert any(r.id == ann.id for r in results)


def test_list_visible_to_user_exclude_overrides_group(db_session):
    """User in the group but in exclude list does NOT see announcement."""
    repo = AnnouncementRepository(db_session)
    composer = _user(db_session)
    viewer = _user(db_session)

    ann = Announcement(
        title="Excluded announcement",
        message_text="Not for you",
        scheduled_at=_now(),
        importance="normal",
        category_code="NOTICE",
        audience_group_codes=["FACULTY_ALL"],
        exclude_user_ids=[str(viewer.id)],
        composer_user_id=composer.id,
        composer_role_code="FACULTY",
        source_type="manual",
    )
    repo.create(ann)

    now = _now() + timedelta(seconds=1)
    results = repo.list_visible_to_user(viewer.id, {"FACULTY_ALL"}, now)
    assert not any(r.id == ann.id for r in results)


def test_announcement_withdraw_hides_from_list(db_session):
    """Withdrawn (soft-deleted) announcement is excluded from list_visible."""
    repo = AnnouncementRepository(db_session)
    composer = _user(db_session)
    viewer = _user(db_session)

    ann = repo.create(_ann(composer.id, ["FACULTY_ALL"]))
    repo.withdraw(ann.id, composer.id)

    now = _now() + timedelta(seconds=1)
    results = repo.list_visible_to_user(viewer.id, {"FACULTY_ALL"}, now)
    assert not any(r.id == ann.id for r in results)


def test_list_by_composer_includes_own_withdrawn(db_session):
    """list_by_composer with include_withdrawn=True shows withdrawn announcements."""
    repo = AnnouncementRepository(db_session)
    composer = _user(db_session)

    ann = repo.create(_ann(composer.id, ["ALL"]))
    repo.withdraw(ann.id, composer.id)

    all_by_composer = repo.list_by_composer(composer.id, include_withdrawn=True)
    active_only = repo.list_by_composer(composer.id, include_withdrawn=False)

    assert any(r.id == ann.id for r in all_by_composer)
    assert not any(r.id == ann.id for r in active_only)
