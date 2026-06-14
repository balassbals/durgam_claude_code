"""Integration tests for Phase 8c — per-category publish_delay_seconds window.

8 tests:
1. create_announcement with zero delay sets scheduled_at ≈ now
2. create_announcement with 30-min delay sets scheduled_at ≈ now + 1800s
3. create_auto_announcement ignores category delay (always sets scheduled_at = now)
4. list_for_browse received tab excludes pending announcements
5. list_for_browse sent tab includes pending announcements for composer
6. withdraw allowed during pending window (future scheduled_at)
7. withdraw rejected after window expires (past scheduled_at)
8. category service validates delay range (0–86400 seconds)
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import select

from durgam.models.announcement import (
    Announcement,
    AnnouncementCategory,
    AnnouncementComposerConfig,
    AudienceGroup,
)
from durgam.models.identity import Role, User, UserRole
from durgam.repositories.announcement import (
    AnnouncementCategoryRepository,
    AnnouncementComposerConfigRepository,
    AnnouncementRepository,
    AudienceGroupRepository,
)
from durgam.services.announcement import (
    AnnouncementService,
    AnnouncementWithdrawalNotAllowedError,
)
from durgam.services.announcement_config import (
    AnnouncementCategoryService,
    AnnouncementConfigError,
)
from durgam.services.password import hash_password


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _svc(session) -> AnnouncementService:
    return AnnouncementService(
        repo=AnnouncementRepository(session),
        config_repo=AnnouncementComposerConfigRepository(session),
        category_repo=AnnouncementCategoryRepository(session),
        audience_repo=AudienceGroupRepository(session),
        session=session,
    )


def _cat_svc(session) -> AnnouncementCategoryService:
    return AnnouncementCategoryService(repo=AnnouncementCategoryRepository(session))


def _user(session) -> User:
    tag = uuid4().hex[:8]
    u = User(
        username=f"pd_{tag}",
        email=f"pd_{tag}@test.local",
        full_name="Test",
        password_hash=hash_password("Test_Dev1!XZ"),
        is_active=True,
    )
    session.add(u)
    session.flush()
    return u


def _role(session, code: str) -> Role:
    existing = session.exec(select(Role).where(Role.code == code)).first()
    if existing:
        return existing
    r = Role(code=code, name=code, level=50)
    session.add(r)
    session.flush()
    return r


def _assign_role(session, user_id, role_id) -> None:
    session.add(UserRole(user_id=user_id, role_id=role_id))
    session.flush()


def _composer_config(session, role_code: str) -> AnnouncementComposerConfig:
    cfg = AnnouncementComposerConfig(role_code=role_code, priority_rank=50, enabled=True)
    session.add(cfg)
    session.flush()
    return cfg


def _category(session, code: str, delay_seconds: int = 0) -> AnnouncementCategory:
    existing = session.exec(
        select(AnnouncementCategory).where(
            AnnouncementCategory.code == code,
            AnnouncementCategory.is_deleted == False,  # noqa: E712
        )
    ).first()
    if existing:
        existing.publish_delay_seconds = delay_seconds
        session.flush()
        return existing
    cat = AnnouncementCategory(
        code=code, name=code, is_active=True, publish_delay_seconds=delay_seconds
    )
    session.add(cat)
    session.flush()
    return cat


def _audience_group(session, code: str = "ALL_PD") -> AudienceGroup:
    existing = session.exec(
        select(AudienceGroup).where(
            AudienceGroup.code == code,
            AudienceGroup.is_deleted == False,  # noqa: E712
        )
    ).first()
    if existing:
        return existing
    ag = AudienceGroup(code=code, name=code, filter_json={}, is_active=True)
    session.add(ag)
    session.flush()
    return ag


def _make_composer(session) -> tuple[User, str]:
    role_code = f"PD_ROLE_{uuid4().hex[:6]}"
    role = _role(session, role_code)
    composer = _user(session)
    _assign_role(session, composer.id, role.id)
    _composer_config(session, role_code)
    return composer, role_code


# ---------------------------------------------------------------------------
# Test 1: zero delay → scheduled_at ≈ now
# ---------------------------------------------------------------------------

class TestPublishDelayOnCreate:
    def test_create_announcement_with_zero_delay_sets_scheduled_at_now(
        self, db_session
    ) -> None:
        """Category with publish_delay_seconds=0 → scheduled_at is approximately now."""
        composer, role_code = _make_composer(db_session)
        _category(db_session, "PD_ZERO", delay_seconds=0)
        _audience_group(db_session, "PD_ALL_Z")

        before = datetime.now(UTC)
        ann = _svc(db_session).create_announcement(
            composer_user_id=composer.id,
            composer_role_code=role_code,
            category_code="PD_ZERO",
            audience_group_codes=["PD_ALL_Z"],
            title="Zero delay",
            body_text="Body",
            importance="normal",
            actor_id=composer.id,
        )
        after = datetime.now(UTC)

        assert before <= ann.scheduled_at <= after, (
            f"scheduled_at={ann.scheduled_at} should be between {before} and {after}"
        )

    def test_create_announcement_with_30min_delay_sets_scheduled_at_in_future(
        self, db_session
    ) -> None:
        """Category with publish_delay_seconds=1800 → scheduled_at ≈ now + 30 min."""
        composer, role_code = _make_composer(db_session)
        _category(db_session, "PD_30M", delay_seconds=1800)
        _audience_group(db_session, "PD_ALL_30")

        before = datetime.now(UTC)
        ann = _svc(db_session).create_announcement(
            composer_user_id=composer.id,
            composer_role_code=role_code,
            category_code="PD_30M",
            audience_group_codes=["PD_ALL_30"],
            title="Thirty minute delay",
            body_text="Body",
            importance="normal",
            actor_id=composer.id,
        )
        after = datetime.now(UTC)

        expected_min = before + timedelta(seconds=1800)
        expected_max = after + timedelta(seconds=1800)
        assert expected_min <= ann.scheduled_at <= expected_max, (
            f"scheduled_at={ann.scheduled_at} should be ~now+1800s "
            f"(between {expected_min} and {expected_max})"
        )

    def test_create_auto_announcement_ignores_category_delay(
        self, db_session
    ) -> None:
        """create_auto_announcement always sets scheduled_at = now, ignoring category delay."""
        composer, role_code = _make_composer(db_session)
        _category(db_session, "PD_AUTO", delay_seconds=3600)
        _audience_group(db_session, "PD_ALL_A")

        before = datetime.now(UTC)
        ann = _svc(db_session).create_auto_announcement(
            composer_user_id=composer.id,
            composer_role_code=role_code,
            category_code="PD_AUTO",
            audience_group_codes=["PD_ALL_A"],
            title="Auto announcement",
            message_text="Body",
            source_approval_request_id=uuid4(),
            actor_id=composer.id,
        )
        after = datetime.now(UTC)

        assert before <= ann.scheduled_at <= after, (
            f"Auto-announcement scheduled_at={ann.scheduled_at} should be "
            f"immediately (between {before} and {after}), ignoring category delay."
        )


# ---------------------------------------------------------------------------
# Tests 4–5: list_for_browse pending filtering
# ---------------------------------------------------------------------------

class TestBrowseFiltering:
    def _make_pending_announcement(
        self, session, composer: User, role_code: str, future_at: datetime
    ) -> Announcement:
        """Insert an announcement with scheduled_at in the future (pending)."""
        now = datetime.now(UTC)
        ann = Announcement(
            title="Pending",
            message_text="Body",
            scheduled_at=future_at,
            importance="normal",
            category_code="PD_BROWSE",
            audience_group_codes=["PD_ALL_B"],
            composer_user_id=composer.id,
            composer_role_code=role_code,
            source_type="manual",
            created_by=composer.id,
            updated_by=composer.id,
            created_at=now,
            updated_at=now,
        )
        session.add(ann)
        session.flush()
        return ann

    def test_list_for_browse_received_excludes_pending(self, db_session) -> None:
        """Received tab must not show announcements whose scheduled_at is in the future."""
        composer, role_code = _make_composer(db_session)
        _category(db_session, "PD_BROWSE", delay_seconds=0)
        _audience_group(db_session, "PD_ALL_B")

        future = datetime.now(UTC) + timedelta(hours=1)
        self._make_pending_announcement(db_session, composer, role_code, future)

        # viewer is a different user who is in the audience (filter_json={} → matches all)
        viewer = _user(db_session)
        page, total = _svc(db_session).list_for_browse(
            viewer_user_id=viewer.id,
            tab="received",
        )
        ann_ids = [str(a.id) for a in page]
        assert total == 0, (
            f"Received tab should exclude pending announcements but got {total} rows"
        )

    def test_list_for_browse_sent_includes_pending_for_composer(
        self, db_session
    ) -> None:
        """Sent tab must include the composer's own pending announcements."""
        composer, role_code = _make_composer(db_session)
        _category(db_session, "PD_BROWSE", delay_seconds=0)
        _audience_group(db_session, "PD_ALL_B")

        future = datetime.now(UTC) + timedelta(hours=1)
        ann = self._make_pending_announcement(db_session, composer, role_code, future)

        page, total = _svc(db_session).list_for_browse(
            viewer_user_id=composer.id,
            tab="sent",
        )
        ids = [str(a.id) for a in page]
        assert str(ann.id) in ids, (
            "Sent tab should include composer's own pending announcements"
        )


# ---------------------------------------------------------------------------
# Tests 6–7: withdraw window enforcement
# ---------------------------------------------------------------------------

class TestWithdrawWindow:
    def _make_manual_announcement(
        self, session, composer: User, role_code: str, scheduled_at: datetime
    ) -> Announcement:
        now = datetime.now(UTC)
        ann = Announcement(
            title="Test",
            message_text="Body",
            scheduled_at=scheduled_at,
            importance="normal",
            category_code="PD_WD",
            audience_group_codes=["PD_ALL_WD"],
            composer_user_id=composer.id,
            composer_role_code=role_code,
            source_type="manual",
            created_by=composer.id,
            updated_by=composer.id,
            created_at=now,
            updated_at=now,
        )
        session.add(ann)
        session.flush()
        return ann

    def test_withdraw_allowed_during_pending_window(self, db_session) -> None:
        """Composer can withdraw an announcement whose scheduled_at is in the future."""
        composer, role_code = _make_composer(db_session)
        _category(db_session, "PD_WD", delay_seconds=0)
        _audience_group(db_session, "PD_ALL_WD")

        future = datetime.now(UTC) + timedelta(minutes=30)
        ann = self._make_manual_announcement(db_session, composer, role_code, future)

        updated = _svc(db_session).withdraw_announcement(
            announcement_id=ann.id,
            actor_id=composer.id,
        )
        assert updated.is_deleted is True

    def test_withdraw_rejected_after_window_expires(self, db_session) -> None:
        """Composer cannot withdraw an announcement whose scheduled_at is in the past."""
        composer, role_code = _make_composer(db_session)
        _category(db_session, "PD_WD", delay_seconds=0)
        _audience_group(db_session, "PD_ALL_WD")

        past = datetime.now(UTC) - timedelta(seconds=1)
        ann = self._make_manual_announcement(db_session, composer, role_code, past)

        with pytest.raises(
            AnnouncementWithdrawalNotAllowedError,
            match="already published",
        ):
            _svc(db_session).withdraw_announcement(
                announcement_id=ann.id,
                actor_id=composer.id,
            )


# ---------------------------------------------------------------------------
# Test 8: category service validates delay range
# ---------------------------------------------------------------------------

class TestCategoryServiceValidation:
    def test_category_service_validates_delay_range(self, db_session) -> None:
        """AnnouncementCategoryService rejects publish_delay_seconds outside 0–86400."""
        svc = _cat_svc(db_session)
        actor = _user(db_session)

        with pytest.raises(AnnouncementConfigError, match="between 0 and 86400"):
            svc.create(
                code="PD_BAD",
                name="Bad delay",
                display_order=0,
                is_active=True,
                publish_delay_seconds=86401,
                notes=None,
                actor_id=actor.id,
            )

        with pytest.raises(AnnouncementConfigError, match="between 0 and 86400"):
            svc.create(
                code="PD_NEG",
                name="Negative delay",
                display_order=0,
                is_active=True,
                publish_delay_seconds=-1,
                notes=None,
                actor_id=actor.id,
            )
