"""Integration tests for Phase 6b announcement state flows (M9).

12 tests covering the service-layer logic exercised by the three state classes:
AnnouncementBrowseState, AnnouncementComposerState, AnnouncementDetailState.

Pattern: direct service calls (same style as test_announcement_service.py) to
verify the flows that state handlers orchestrate.  No Reflex state machinery
needed — these are integration tests against the DB and service layer.

All tests use db_session (empty DB with schema) unless noted.
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
    AnnouncementComposerNotEligibleError,
    AnnouncementNotFoundError,
    AnnouncementService,
    AnnouncementWithdrawalNotAllowedError,
)
from durgam.services.password import hash_password


# ---------------------------------------------------------------------------
# Helpers (mirror test_announcement_service.py helpers for isolation)
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
        username=f"st6b_{tag}",
        email=f"st6b_{tag}@test.local",
        full_name="State Test User",
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
    cfg = AnnouncementComposerConfig(role_code=role_code, priority_rank=priority_rank, enabled=True)
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


def _raw_announcement(
    session,
    composer: User,
    role_code: str,
    ag_code: str,
    title: str,
    *,
    source_type: str = "manual",
    is_deleted: bool = False,
) -> Announcement:
    now = _now()
    ann = Announcement(
        title=title,
        message_text="Body text for " + title,
        scheduled_at=now - timedelta(seconds=1),
        importance="normal",
        category_code="NOTICE",
        audience_group_codes=[ag_code],
        composer_user_id=composer.id,
        composer_role_code=role_code,
        source_type=source_type,
        is_deleted=is_deleted,
        created_by=composer.id,
        updated_by=composer.id,
        created_at=now,
        updated_at=now,
    )
    session.add(ann)
    session.flush()
    return ann


# ---------------------------------------------------------------------------
# Tests 1–4: AnnouncementBrowseState flows (list_for_browse)
# ---------------------------------------------------------------------------

class TestBrowseStateFlows:
    def test_browse_received_returns_matching_announcement(self, db_session) -> None:
        """Viewer in matching audience group receives the announcement."""
        _category(db_session, "NOTICE")
        ag = _audience_group(db_session, "BROWSE_ALL", filter_json={})  # empty matches all

        role = _role(db_session, "ST_BROWSE_A")
        _composer_config(db_session, "ST_BROWSE_A")
        composer = _user(db_session)
        _assign_role(db_session, composer.id, role.id)

        viewer = _user(db_session)
        _raw_announcement(db_session, composer, "ST_BROWSE_A", "BROWSE_ALL", "Hello World")

        svc = _svc(db_session)
        rows, total = svc.list_for_browse(viewer_user_id=viewer.id, tab="received")

        assert total >= 1
        titles = [a.title for a in rows]
        assert "Hello World" in titles

    def test_browse_sent_returns_only_own(self, db_session) -> None:
        """sent tab returns only announcements composed by the viewer."""
        _category(db_session, "NOTICE")
        _audience_group(db_session, "SENT_GRP", filter_json={})

        role_a = _role(db_session, "ST_SENT_A")
        _composer_config(db_session, "ST_SENT_A")
        role_b = _role(db_session, "ST_SENT_B")
        _composer_config(db_session, "ST_SENT_B")

        composer_a = _user(db_session)
        _assign_role(db_session, composer_a.id, role_a.id)
        composer_b = _user(db_session)
        _assign_role(db_session, composer_b.id, role_b.id)

        _raw_announcement(db_session, composer_a, "ST_SENT_A", "SENT_GRP", "By A")
        _raw_announcement(db_session, composer_b, "ST_SENT_B", "SENT_GRP", "By B")

        svc = _svc(db_session)
        rows, total = svc.list_for_browse(viewer_user_id=composer_a.id, tab="sent")

        assert total == 1
        assert rows[0].composer_user_id == composer_a.id
        assert rows[0].title == "By A"

    def test_browse_sent_includes_withdrawn(self, db_session) -> None:
        """sent tab shows the composer's own withdrawn announcements."""
        _category(db_session, "NOTICE")
        _audience_group(db_session, "SENT_W_GRP", filter_json={})

        role = _role(db_session, "ST_SENT_W")
        _composer_config(db_session, "ST_SENT_W")
        composer = _user(db_session)
        _assign_role(db_session, composer.id, role.id)

        _raw_announcement(
            db_session, composer, "ST_SENT_W", "SENT_W_GRP", "Withdrawn Ann",
            is_deleted=True,
        )

        svc = _svc(db_session)
        rows, total = svc.list_for_browse(viewer_user_id=composer.id, tab="sent")

        assert total >= 1
        titles = [a.title for a in rows]
        assert "Withdrawn Ann" in titles

    def test_browse_received_excludes_withdrawn(self, db_session) -> None:
        """received tab excludes announcements withdrawn (is_deleted=True) from others."""
        _category(db_session, "NOTICE")
        _audience_group(db_session, "RCV_EX_GRP", filter_json={})

        role = _role(db_session, "ST_RCV_EX")
        _composer_config(db_session, "ST_RCV_EX")
        composer = _user(db_session)
        _assign_role(db_session, composer.id, role.id)

        viewer = _user(db_session)
        live_ann = _raw_announcement(
            db_session, composer, "ST_RCV_EX", "RCV_EX_GRP", "Live One"
        )
        _raw_announcement(
            db_session, composer, "ST_RCV_EX", "RCV_EX_GRP", "Dead One",
            is_deleted=True,
        )

        svc = _svc(db_session)
        rows, total = svc.list_for_browse(viewer_user_id=viewer.id, tab="received")

        ann_ids = {str(r.id) for r in rows}
        assert str(live_ann.id) in ann_ids, "Live announcement must be in received feed"
        for a in rows:
            assert not a.is_deleted, "Received feed must not contain withdrawn announcements"


# ---------------------------------------------------------------------------
# Tests 5–7: AnnouncementComposerState flows (open_composer / save)
# ---------------------------------------------------------------------------

class TestComposerStateFlows:
    def test_list_composer_eligible_roles_for_configured_user(self, db_session) -> None:
        """User with a role in an enabled composer config gets that role code."""
        role = _role(db_session, "ST_COMP_OK")
        _composer_config(db_session, "ST_COMP_OK", priority_rank=10)
        user = _user(db_session)
        _assign_role(db_session, user.id, role.id)

        svc = _svc(db_session)
        codes = svc.list_composer_eligible_roles(user.id)
        assert "ST_COMP_OK" in codes

    def test_list_composer_eligible_roles_empty_for_unconfigured_user(self, db_session) -> None:
        """User with NO configured composer role gets empty list — open_composer would block."""
        user = _user(db_session)
        # No role, no composer config
        svc = _svc(db_session)
        codes = svc.list_composer_eligible_roles(user.id)
        assert codes == []

    def test_composer_create_announcement_full_flow(self, db_session) -> None:
        """Full create flow: eligible composer → announcement row exists in DB."""
        role = _role(db_session, "ST_COMP_FULL")
        _composer_config(db_session, "ST_COMP_FULL")
        _category(db_session, "CIRCULAR")
        _audience_group(db_session, "ST_COMP_AG", filter_json={})

        composer = _user(db_session)
        _assign_role(db_session, composer.id, role.id)

        svc = _svc(db_session)
        ann = svc.create_announcement(
            composer_user_id=composer.id,
            composer_role_code="ST_COMP_FULL",
            category_code="CIRCULAR",
            audience_group_codes=["ST_COMP_AG"],
            title="Full Flow Test",
            body_text="Integration test body.",
            importance="normal",
            actor_id=composer.id,
        )

        assert ann.id is not None
        assert ann.title == "Full Flow Test"
        assert ann.source_type == "manual"
        db_session.flush()
        db_ann = db_session.get(Announcement, ann.id)
        assert db_ann is not None, "Announcement must be persisted after create"


# ---------------------------------------------------------------------------
# Tests 8–10: importance filter + date filter
# ---------------------------------------------------------------------------

class TestBrowseFilters:
    def _setup_pair(self, session):
        """Create one very_important and one normal announcement for the same viewer."""
        _category(session, "NOTICE")
        _audience_group(session, "FILT_GRP", filter_json={})

        role = _role(session, "ST_FILT_R")
        _composer_config(session, "ST_FILT_R")
        composer = _user(session)
        _assign_role(session, composer.id, role.id)
        viewer = _user(session)
        return composer, viewer

    def test_importance_filter_very_important_only(self, db_session) -> None:
        """importance_filter='very_important' returns only very_important rows."""
        composer, viewer = self._setup_pair(db_session)
        now = _now()
        for title, imp in [("Normal One", "normal"), ("VI One", "very_important")]:
            ann = Announcement(
                title=title,
                message_text="body",
                scheduled_at=now - timedelta(seconds=1),
                importance=imp,
                category_code="NOTICE",
                audience_group_codes=["FILT_GRP"],
                composer_user_id=composer.id,
                composer_role_code="ST_FILT_R",
                source_type="manual",
                created_by=composer.id,
                updated_by=composer.id,
                created_at=now,
                updated_at=now,
            )
            db_session.add(ann)
        db_session.flush()

        svc = _svc(db_session)
        rows, total = svc.list_for_browse(
            viewer_user_id=viewer.id, tab="received",
            importance_filter="very_important",
        )
        assert total >= 1
        for r in rows:
            assert r.importance == "very_important"

    def test_date_from_filter_excludes_earlier(self, db_session) -> None:
        """date_from filter excludes announcements scheduled before that date."""
        _category(db_session, "NOTICE")
        _audience_group(db_session, "DATE_GRP", filter_json={})
        role = _role(db_session, "ST_DATE_R")
        _composer_config(db_session, "ST_DATE_R")
        composer = _user(db_session)
        _assign_role(db_session, composer.id, role.id)
        viewer = _user(db_session)

        from datetime import date as dt_date
        today = dt_date.today()
        old_date = datetime(2020, 1, 1, tzinfo=UTC)
        new_date = datetime.now(UTC) - timedelta(seconds=1)

        for title, sched in [("Old", old_date), ("New", new_date)]:
            ann = Announcement(
                title=title,
                message_text="body",
                scheduled_at=sched,
                importance="normal",
                category_code="NOTICE",
                audience_group_codes=["DATE_GRP"],
                composer_user_id=composer.id,
                composer_role_code="ST_DATE_R",
                source_type="manual",
                created_by=composer.id,
                updated_by=composer.id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db_session.add(ann)
        db_session.flush()

        svc = _svc(db_session)
        rows, total = svc.list_for_browse(
            viewer_user_id=viewer.id,
            tab="received",
            date_from=today,  # today — excludes 2020 row
        )
        for r in rows:
            assert r.scheduled_at.date() >= today, f"Got old row '{r.title}'"

    def test_importance_filter_normal_only(self, db_session) -> None:
        """importance_filter='normal' returns only normal rows."""
        composer, viewer = self._setup_pair(db_session)
        now = _now()
        for title, imp in [("N2", "normal"), ("VI2", "very_important")]:
            ann = Announcement(
                title=title,
                message_text="body",
                scheduled_at=now - timedelta(seconds=1),
                importance=imp,
                category_code="NOTICE",
                audience_group_codes=["FILT_GRP"],
                composer_user_id=composer.id,
                composer_role_code="ST_FILT_R",
                source_type="manual",
                created_by=composer.id,
                updated_by=composer.id,
                created_at=now,
                updated_at=now,
            )
            db_session.add(ann)
        db_session.flush()

        svc = _svc(db_session)
        rows, total = svc.list_for_browse(
            viewer_user_id=viewer.id, tab="received",
            importance_filter="normal",
        )
        assert total >= 1
        for r in rows:
            assert r.importance == "normal"


# ---------------------------------------------------------------------------
# Tests 11–12: AnnouncementDetailState flows (get_by_id + withdraw)
# ---------------------------------------------------------------------------

class TestDetailStateFlows:
    def _setup_announcement(self, session, *, is_deleted: bool = False) -> tuple:
        _category(session, "NOTICE")
        ag = _audience_group(session, "DETAIL_GRP", filter_json={})
        role = _role(session, "ST_DETAIL_R")
        _composer_config(session, "ST_DETAIL_R")
        composer = _user(session)
        _assign_role(session, composer.id, role.id)
        ann = _raw_announcement(
            session, composer, "ST_DETAIL_R", "DETAIL_GRP", "Detail Test",
            is_deleted=is_deleted,
        )
        return ann, composer

    def test_get_by_id_composer_sees_own_withdrawn(self, db_session) -> None:
        """Composer can retrieve their own withdrawn announcement via get_by_id."""
        ann, composer = self._setup_announcement(db_session, is_deleted=True)

        svc = _svc(db_session)
        result = svc.get_by_id(announcement_id=ann.id, viewer_user_id=composer.id)
        assert result.id == ann.id
        assert result.is_deleted is True

    def test_get_by_id_non_recipient_raises_not_found(self, db_session) -> None:
        """Non-recipient gets AnnouncementNotFoundError — existence is not leaked."""
        _category(db_session, "NOTICE")
        # Audience group with role_codes filter that the outsider does NOT hold
        ag = _audience_group(
            db_session, "DETAIL_PRIV",
            filter_json={"role_codes": ["ST_PRIV_ROLE"]},
        )
        priv_role = _role(db_session, "ST_PRIV_ROLE")
        _composer_config(db_session, "ST_PRIV_ROLE")
        composer = _user(db_session)
        _assign_role(db_session, composer.id, priv_role.id)

        outsider = _user(db_session)  # has no ST_PRIV_ROLE

        ann = _raw_announcement(
            db_session, composer, "ST_PRIV_ROLE", "DETAIL_PRIV", "Private Ann"
        )

        svc = _svc(db_session)
        with pytest.raises(AnnouncementNotFoundError):
            svc.get_by_id(announcement_id=ann.id, viewer_user_id=outsider.id)
