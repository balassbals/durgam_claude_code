"""Integration tests for AnnouncementService (M9 Phase 6a).

12 tests covering: create (eligible composer, non-composer rejection, unknown
category, unknown audience group, normal importance, very_important importance),
withdraw (by composer, by non-composer, already-withdrawn, auto-source),
list_for_browse sent tab, list_for_browse received-excludes-withdrawn.

All tests use db_session (empty DB with schema) — no seed data assumed.
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
from durgam.models.crosscutting import AuditLog
from durgam.models.identity import Role, User, UserRole
from durgam.repositories.announcement import (
    AnnouncementCategoryRepository,
    AnnouncementComposerConfigRepository,
    AnnouncementRepository,
    AudienceGroupRepository,
)
from durgam.services.announcement import (
    AnnouncementComposerNotEligibleError,
    AnnouncementError,
    AnnouncementNotFoundError,
    AnnouncementService,
    AnnouncementWithdrawalNotAllowedError,
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


def _user(session, *, suffix: str | None = None) -> User:
    tag = suffix or uuid4().hex[:8]
    u = User(
        username=f"test_{tag}",
        email=f"test_{tag}@test.local",
        full_name="Test User",
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
    ur = UserRole(user_id=user_id, role_id=role_id)
    session.add(ur)
    session.flush()


def _composer_config(session, role_code: str, priority_rank: int = 50) -> AnnouncementComposerConfig:
    cfg = AnnouncementComposerConfig(
        role_code=role_code,
        priority_rank=priority_rank,
        enabled=True,
    )
    session.add(cfg)
    session.flush()
    return cfg


def _category(session, code: str = "NOTICE") -> AnnouncementCategory:
    existing = session.exec(
        select(AnnouncementCategory).where(
            AnnouncementCategory.code == code,
            AnnouncementCategory.is_deleted == False,  # noqa: E712
        )
    ).first()
    if existing:
        return existing
    cat = AnnouncementCategory(code=code, name=code, is_active=True)
    session.add(cat)
    session.flush()
    return cat


def _audience_group(session, code: str = "ALL", filter_json: dict | None = None) -> AudienceGroup:
    """Create an AudienceGroup with filter_json={} (matches everyone) by default."""
    existing = session.exec(
        select(AudienceGroup).where(
            AudienceGroup.code == code,
            AudienceGroup.is_deleted == False,  # noqa: E712
        )
    ).first()
    if existing:
        return existing
    ag = AudienceGroup(
        code=code,
        name=code,
        filter_json=filter_json if filter_json is not None else {},
        is_active=True,
    )
    session.add(ag)
    session.flush()
    return ag


def _now() -> datetime:
    return datetime.now(UTC)


def _audit_count(session, resource: str, action: str) -> int:
    rows = session.exec(
        select(AuditLog).where(
            AuditLog.resource == resource,
            AuditLog.action == action,
        )
    ).all()
    return len(rows)


# ---------------------------------------------------------------------------
# Test 1: create with eligible composer succeeds
# ---------------------------------------------------------------------------

class TestAnnouncementCreate:
    def test_create_announcement_with_eligible_composer_succeeds(self, db_session) -> None:
        """Eligible composer creates an announcement; row exists + audit emitted."""
        role = _role(db_session, "TST_FACULTY")
        _composer_config(db_session, "TST_FACULTY")
        composer = _user(db_session)
        _assign_role(db_session, composer.id, role.id)
        cat = _category(db_session, "CIRCULAR")
        ag = _audience_group(db_session, "ALL_TEST")

        svc = _svc(db_session)
        announcement = svc.create_announcement(
            composer_user_id=composer.id,
            composer_role_code="TST_FACULTY",
            category_code="CIRCULAR",
            audience_group_codes=["ALL_TEST"],
            title="Test announcement",
            body_text="Hello world.",
            importance="normal",
            actor_id=composer.id,
        )

        assert announcement.id is not None
        assert announcement.title == "Test announcement"
        assert announcement.message_text == "Hello world."
        assert announcement.category_code == "CIRCULAR"
        assert announcement.audience_group_codes == ["ALL_TEST"]
        assert announcement.composer_user_id == composer.id
        assert announcement.source_type == "manual"
        assert announcement.is_deleted is False

        # Audit row should have been emitted
        audit_rows = db_session.exec(
            select(AuditLog).where(
                AuditLog.resource == "announcement",
                AuditLog.action == "create",
                AuditLog.resource_id == str(announcement.id),
            )
        ).all()
        assert len(audit_rows) == 1
        assert audit_rows[0].diff_json is not None

    def test_create_announcement_rejects_non_composer(self, db_session) -> None:
        """User with no composer role gets AnnouncementComposerNotEligibleError."""
        # Set up one composer config row so the eligibility table is non-empty
        _composer_config(db_session, "TST_HOD")
        non_composer = _user(db_session)
        # non_composer has no roles at all
        _category(db_session, "CIRCULAR")
        _audience_group(db_session, "ALL_TEST")

        svc = _svc(db_session)
        with pytest.raises(AnnouncementComposerNotEligibleError):
            svc.create_announcement(
                composer_user_id=non_composer.id,
                composer_role_code="BASIC_USER",
                category_code="CIRCULAR",
                audience_group_codes=["ALL_TEST"],
                title="Should fail",
                body_text="Body.",
                importance="normal",
                actor_id=non_composer.id,
            )

    def test_create_announcement_rejects_unknown_category_code(self, db_session) -> None:
        """Unknown category_code raises AnnouncementError."""
        role = _role(db_session, "TST_FACULTY")
        _composer_config(db_session, "TST_FACULTY")
        composer = _user(db_session)
        _assign_role(db_session, composer.id, role.id)
        _audience_group(db_session, "ALL_TEST")

        svc = _svc(db_session)
        with pytest.raises(AnnouncementError, match="Unknown category"):
            svc.create_announcement(
                composer_user_id=composer.id,
                composer_role_code="TST_FACULTY",
                category_code="DOES_NOT_EXIST",
                audience_group_codes=["ALL_TEST"],
                title="Should fail",
                body_text="Body.",
                importance="normal",
                actor_id=composer.id,
            )

    def test_create_announcement_rejects_unknown_audience_group_code(self, db_session) -> None:
        """Unknown audience_group_code raises AnnouncementError."""
        role = _role(db_session, "TST_FACULTY")
        _composer_config(db_session, "TST_FACULTY")
        composer = _user(db_session)
        _assign_role(db_session, composer.id, role.id)
        _category(db_session, "CIRCULAR")

        svc = _svc(db_session)
        with pytest.raises(AnnouncementError, match="Unknown or inactive audience group"):
            svc.create_announcement(
                composer_user_id=composer.id,
                composer_role_code="TST_FACULTY",
                category_code="CIRCULAR",
                audience_group_codes=["NO_SUCH_GROUP"],
                title="Should fail",
                body_text="Body.",
                importance="normal",
                actor_id=composer.id,
            )

    def test_create_announcement_normal_importance_leaves_important_until_null(
        self, db_session
    ) -> None:
        """importance="normal" results in important_until IS NULL."""
        role = _role(db_session, "TST_FACULTY")
        _composer_config(db_session, "TST_FACULTY")
        composer = _user(db_session)
        _assign_role(db_session, composer.id, role.id)
        _category(db_session, "CIRCULAR")
        _audience_group(db_session, "ALL_TEST")

        svc = _svc(db_session)
        ann = svc.create_announcement(
            composer_user_id=composer.id,
            composer_role_code="TST_FACULTY",
            category_code="CIRCULAR",
            audience_group_codes=["ALL_TEST"],
            title="Normal announcement",
            body_text="Body.",
            importance="normal",
            actor_id=composer.id,
        )
        assert ann.important_until is None

    def test_create_announcement_very_important_computes_important_until(
        self, db_session
    ) -> None:
        """importance="very_important" sets important_until ≥ 2 working days from now."""
        role = _role(db_session, "TST_FACULTY")
        _composer_config(db_session, "TST_FACULTY")
        composer = _user(db_session)
        _assign_role(db_session, composer.id, role.id)
        _category(db_session, "CIRCULAR")
        _audience_group(db_session, "ALL_TEST")

        before = _now()
        svc = _svc(db_session)
        ann = svc.create_announcement(
            composer_user_id=composer.id,
            composer_role_code="TST_FACULTY",
            category_code="CIRCULAR",
            audience_group_codes=["ALL_TEST"],
            title="Very important",
            body_text="Body.",
            importance="very_important",
            actor_id=composer.id,
        )
        assert ann.important_until is not None
        # Should be at least 2 calendar days after scheduled_at (could be more if
        # Sundays are in the window; ±1 day tolerance for time-of-day boundary)
        assert ann.important_until >= before + timedelta(days=1), (
            f"important_until {ann.important_until} should be at least 1 day after creation"
        )


# ---------------------------------------------------------------------------
# Tests 7–10: withdraw
# ---------------------------------------------------------------------------

class TestAnnouncementWithdraw:
    def _make_announcement(
        self, session, source_type: str = "manual"
    ) -> tuple[Announcement, User]:
        """Create a minimal announcement and return (announcement, composer)."""
        role = _role(session, "TST_HOD_W")
        _composer_config(session, "TST_HOD_W")
        composer = _user(session)
        _assign_role(session, composer.id, role.id)
        _category(session, "NOTICE")
        _audience_group(session, "ALL_W")

        now = _now()
        ann = Announcement(
            title="Test",
            message_text="Body",
            scheduled_at=now,
            importance="normal",
            category_code="NOTICE",
            audience_group_codes=["ALL_W"],
            composer_user_id=composer.id,
            composer_role_code="TST_HOD_W",
            source_type=source_type,
            created_by=composer.id,
            updated_by=composer.id,
            created_at=now,
            updated_at=now,
        )
        session.add(ann)
        session.flush()
        return ann, composer

    def test_withdraw_by_composer_sets_withdrawn(self, db_session) -> None:
        """Composer withdraws their announcement; is_deleted=True; audit emitted."""
        ann, composer = self._make_announcement(db_session)

        audit_before = _audit_count(db_session, "announcement", "withdraw")
        svc = _svc(db_session)
        updated = svc.withdraw_announcement(
            announcement_id=ann.id,
            actor_id=composer.id,
        )

        assert updated.is_deleted is True
        assert updated.deleted_by == composer.id
        assert updated.deleted_at is not None
        assert _audit_count(db_session, "announcement", "withdraw") == audit_before + 1

    def test_withdraw_by_non_composer_raises(self, db_session) -> None:
        """Different user attempting withdraw raises AnnouncementWithdrawalNotAllowedError."""
        ann, _composer = self._make_announcement(db_session)
        other_user = _user(db_session)

        svc = _svc(db_session)
        with pytest.raises(AnnouncementWithdrawalNotAllowedError, match="Only the composer"):
            svc.withdraw_announcement(
                announcement_id=ann.id,
                actor_id=other_user.id,
            )

    def test_withdraw_already_withdrawn_raises(self, db_session) -> None:
        """Withdrawing an already-withdrawn announcement raises an error."""
        ann, composer = self._make_announcement(db_session)
        svc = _svc(db_session)
        # First withdraw
        svc.withdraw_announcement(announcement_id=ann.id, actor_id=composer.id)
        # Second withdraw — must raise
        with pytest.raises(AnnouncementWithdrawalNotAllowedError, match="Already withdrawn"):
            svc.withdraw_announcement(announcement_id=ann.id, actor_id=composer.id)

    def test_withdraw_auto_announcement_raises(self, db_session) -> None:
        """Auto-announcements (source_type='auto') cannot be withdrawn manually."""
        ann, composer = self._make_announcement(db_session, source_type="auto")

        svc = _svc(db_session)
        with pytest.raises(
            AnnouncementWithdrawalNotAllowedError,
            match="Auto-announcements cannot be withdrawn",
        ):
            svc.withdraw_announcement(
                announcement_id=ann.id,
                actor_id=composer.id,
            )


# ---------------------------------------------------------------------------
# Tests 11–12: list_for_browse
# ---------------------------------------------------------------------------

class TestAnnouncementListForBrowse:
    def _setup_composer(self, session, role_code: str) -> User:
        role = _role(session, role_code)
        _composer_config(session, role_code)
        composer = _user(session)
        _assign_role(session, composer.id, role.id)
        return composer

    def _make_announcement(
        self,
        session,
        composer: User,
        role_code: str,
        ag_code: str,
        title: str,
    ) -> Announcement:
        now = _now()
        ann = Announcement(
            title=title,
            message_text="Body",
            scheduled_at=now - timedelta(seconds=1),  # ensure visible (past scheduled_at)
            importance="normal",
            category_code="NOTICE",
            audience_group_codes=[ag_code],
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

    def test_list_for_browse_sent_returns_only_user_authored(self, db_session) -> None:
        """sent tab returns announcements by the viewer only, not others'."""
        _category(db_session, "NOTICE")
        _audience_group(db_session, "ALL_LIST")

        user_a = self._setup_composer(db_session, "TST_RC_A")
        user_b = self._setup_composer(db_session, "TST_RC_B")

        # User A: 3 announcements; User B: 2 announcements
        for i in range(3):
            self._make_announcement(db_session, user_a, "TST_RC_A", "ALL_LIST", f"A-{i}")
        for i in range(2):
            self._make_announcement(db_session, user_b, "TST_RC_B", "ALL_LIST", f"B-{i}")

        svc = _svc(db_session)
        rows, total = svc.list_for_browse(viewer_user_id=user_a.id, tab="sent")

        assert total == 3, f"Expected 3 sent by A; got {total}"
        assert len(rows) == 3
        for ann in rows:
            assert ann.composer_user_id == user_a.id

    def test_list_for_browse_received_excludes_withdrawn(self, db_session) -> None:
        """received tab excludes announcements that have been withdrawn (is_deleted=True)."""
        _category(db_session, "NOTICE")
        # Empty filter_json = matches all authenticated users (viewer will match)
        _audience_group(db_session, "RCVD_TEST", filter_json={})

        composer = self._setup_composer(db_session, "TST_RC_C")
        viewer = _user(db_session)

        ann_live = self._make_announcement(
            db_session, composer, "TST_RC_C", "RCVD_TEST", "Live"
        )
        ann_withdrawn = self._make_announcement(
            db_session, composer, "TST_RC_C", "RCVD_TEST", "Withdrawn"
        )
        # Withdraw the second announcement
        db_session.get(Announcement, ann_withdrawn.id).is_deleted = True
        db_session.flush()

        svc = _svc(db_session)
        rows, total = svc.list_for_browse(viewer_user_id=viewer.id, tab="received")

        # Only the live announcement should appear
        ann_ids = {str(r.id) for r in rows}
        assert str(ann_live.id) in ann_ids, "Live announcement must be in received feed"
        assert str(ann_withdrawn.id) not in ann_ids, "Withdrawn must be excluded from received feed"
