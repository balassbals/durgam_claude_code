"""Integration tests for AnnouncementRepository (M9 Phase 2.1).

10 tests covering CRUD, JSONB audience-filter list_visible_to_user
(?| group overlap, @> ad-hoc inclusion, @> exclude), future-scheduled
exclusion, and soft-delete / withdraw behaviour.
Uses db_session (rollback per test, clean DB, no seed required).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

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

def _make_user(session) -> User:
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


def _make_announcement(
    composer_id: UUID,
    audience_group_codes: list[str],
    *,
    scheduled_at: datetime | None = None,
    ad_hoc_user_ids: list[str] | None = None,
    exclude_user_ids: list[str] | None = None,
) -> Announcement:
    return Announcement(
        title=f"Ann {uuid4().hex[:6]}",
        message_text="Test body.",
        scheduled_at=scheduled_at or (_now() - timedelta(hours=1)),
        importance="normal",
        category_code="TEST_CIRCULAR",
        audience_group_codes=audience_group_codes,
        ad_hoc_user_ids=ad_hoc_user_ids,
        exclude_user_ids=exclude_user_ids,
        composer_user_id=composer_id,
        composer_role_code="FACULTY",
        source_type="manual",
    )


# ---------------------------------------------------------------------------
# 1. AnnouncementCategoryRepository
# ---------------------------------------------------------------------------

def test_category_create_and_get_by_code(db_session):
    repo = AnnouncementCategoryRepository(db_session)
    repo.create(AnnouncementCategory(code="TEST_CIRCULAR", name="Test Circular", display_order=99))

    found = repo.get_by_code("TEST_CIRCULAR")
    assert found is not None
    assert found.name == "Test Circular"


def test_category_list_active_excludes_inactive(db_session):
    repo = AnnouncementCategoryRepository(db_session)
    repo.create(AnnouncementCategory(code="CAT_A1", name="Active 1", is_active=True, display_order=1))
    repo.create(AnnouncementCategory(code="CAT_A2", name="Active 2", is_active=True, display_order=2))
    repo.create(AnnouncementCategory(code="CAT_I1", name="Inactive 1", is_active=False, display_order=3))

    active = repo.list_active()
    active_codes = {c.code for c in active}
    assert "CAT_A1" in active_codes
    assert "CAT_A2" in active_codes
    assert "CAT_I1" not in active_codes
    assert len([c for c in active if c.code in {"CAT_A1", "CAT_A2", "CAT_I1"}]) == 2


# ---------------------------------------------------------------------------
# 2. AnnouncementComposerConfigRepository
# ---------------------------------------------------------------------------

def test_composer_config_unique_role_code_enforced(db_session):
    repo = AnnouncementComposerConfigRepository(db_session)
    repo.create(AnnouncementComposerConfig(role_code="TEST_ROLE", priority_rank=10))

    dup = AnnouncementComposerConfig(role_code="TEST_ROLE", priority_rank=20)
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.flush()


# ---------------------------------------------------------------------------
# 3. AudienceGroupRepository
# ---------------------------------------------------------------------------

def test_audience_group_jsonb_filter_roundtrip(db_session):
    repo = AudienceGroupRepository(db_session)
    fj = {"role_codes": ["FACULTY"], "scope_type": "school", "scope_codes": ["SCI"]}
    repo.create(AudienceGroup(code="TEST_GRP", name="Test Group", filter_json=fj, is_active=True))

    found = repo.get_by_code("TEST_GRP")
    assert found is not None
    assert found.filter_json == fj


# ---------------------------------------------------------------------------
# 4. AnnouncementRepository — list_visible_to_user
# ---------------------------------------------------------------------------

def test_announcement_list_visible_audience_match(db_session):
    """Announcement whose audience_group_codes overlaps user_groups is returned."""
    user = _make_user(db_session)
    composer = _make_user(db_session)
    repo = AnnouncementRepository(db_session)

    ann = repo.create(_make_announcement(composer.id, ["GROUP_A"]))

    results = repo.list_visible_to_user(user.id, {"GROUP_A"}, _now())
    assert any(r.id == ann.id for r in results)


def test_announcement_list_visible_ad_hoc_inclusion(db_session):
    """Ad-hoc user sees announcement even with no matching group."""
    user = _make_user(db_session)
    composer = _make_user(db_session)
    repo = AnnouncementRepository(db_session)

    ann = repo.create(
        _make_announcement(
            composer.id,
            ["GROUP_X"],  # user is NOT in GROUP_X
            ad_hoc_user_ids=[str(user.id)],
        )
    )

    results = repo.list_visible_to_user(user.id, set(), _now())
    assert any(r.id == ann.id for r in results)


def test_announcement_list_visible_exclude_wins(db_session):
    """User in group but in exclude list does NOT see the announcement."""
    user = _make_user(db_session)
    composer = _make_user(db_session)
    repo = AnnouncementRepository(db_session)

    ann = repo.create(
        _make_announcement(
            composer.id,
            ["GROUP_A"],
            exclude_user_ids=[str(user.id)],
        )
    )

    results = repo.list_visible_to_user(user.id, {"GROUP_A"}, _now())
    assert not any(r.id == ann.id for r in results)


def test_announcement_list_visible_scheduled_in_future_excluded(db_session):
    """Announcement with scheduled_at in the future is not returned."""
    user = _make_user(db_session)
    composer = _make_user(db_session)
    repo = AnnouncementRepository(db_session)

    future = _now() + timedelta(hours=1)
    ann = repo.create(
        _make_announcement(composer.id, ["GROUP_A"], scheduled_at=future)
    )

    results = repo.list_visible_to_user(user.id, {"GROUP_A"}, _now())
    assert not any(r.id == ann.id for r in results)


# ---------------------------------------------------------------------------
# 5. list_by_composer and withdraw
# ---------------------------------------------------------------------------

def test_announcement_list_by_composer_includes_withdrawn_when_flag_set(db_session):
    composer = _make_user(db_session)
    repo = AnnouncementRepository(db_session)

    ann1 = repo.create(_make_announcement(composer.id, ["ALL"]))
    ann2 = repo.create(_make_announcement(composer.id, ["ALL"]))
    repo.withdraw(ann2.id, composer.id)

    active_only = repo.list_by_composer(composer.id, include_withdrawn=False)
    all_incl = repo.list_by_composer(composer.id, include_withdrawn=True)

    active_ids = {r.id for r in active_only}
    all_ids = {r.id for r in all_incl}

    assert ann1.id in active_ids
    assert ann2.id not in active_ids
    assert ann1.id in all_ids
    assert ann2.id in all_ids


def test_announcement_withdraw_sets_soft_delete_fields(db_session):
    """withdraw() sets is_deleted, deleted_at, deleted_by on the row."""
    from sqlmodel import Session

    composer = _make_user(db_session)
    withdrawer = _make_user(db_session)
    repo = AnnouncementRepository(db_session)

    ann = repo.create(_make_announcement(composer.id, ["ALL"]))
    repo.withdraw(ann.id, withdrawer.id)

    # Fetch directly via session to bypass is_deleted filter
    row = db_session.get(Announcement, ann.id)
    assert row is not None
    assert row.is_deleted is True
    assert row.deleted_at is not None
    assert row.deleted_by == withdrawer.id
