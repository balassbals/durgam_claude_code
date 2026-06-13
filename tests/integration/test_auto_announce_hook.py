"""Integration tests for the auto-announcement hook in _run_post_approval (M9 Phase 8a).

5 tests exercising the hook via direct _run_post_approval invocation on a minimal
ApprovalRequest + ApprovalProcess fixture. Avoids setting up full submit/approve
routing (scope chains, role matching) since the hook logic is independent of how
the approval reached terminal state.

Deviations from spec:
- Model field is source_ref_id (not source_approval_request_id); assertions use that.
- approver_user_id is the _run_post_approval param (not actor_user_id).
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlmodel import select

from durgam.models.announcement import Announcement, AnnouncementCategory, AudienceGroup
from durgam.models.crosscutting import ApprovalProcess, ApprovalRequest
from durgam.models.identity import User
from durgam.services.announcement import AnnouncementService
from durgam.services.approval_request import ApprovalRequestService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(session, *, username: str | None = None) -> User:
    from durgam.services.password import hash_password

    tag = uuid4().hex[:8]
    u = User(
        username=username or f"h8_{tag}",
        email=f"h8_{tag}@test.local",
        full_name="Hook Test User",
        password_hash=hash_password("Test_Dev1!XZ"),
        is_active=True,
    )
    session.add(u)
    session.flush()
    return u


def _category(session, code: str = "NOTIFICATION") -> AnnouncementCategory:
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


def _audience_group(session, code: str = "ALL", *, filter_json: dict | None = None) -> AudienceGroup:
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


def _process(
    session,
    *,
    code: str | None = None,
    auto_announce: bool = False,
    target_json: dict | None = None,
) -> ApprovalProcess:
    now = datetime.now(UTC)
    proc = ApprovalProcess(
        code=code or f"TST_HOOK_{uuid4().hex[:6]}",
        title="Hook Test Process",
        requestor_role_codes=["BASIC_USER"],
        channel_role_codes=["BASIC_USER"],
        requires_upward_attachments=False,
        max_upward_attachments=0,
        requires_downward_attachments=False,
        max_downward_attachments=0,
        is_finance=False,
        auto_announce_on_approve=auto_announce,
        auto_announce_target_json=target_json,
        created_by=uuid4(),
        updated_by=uuid4(),
        created_at=now,
        updated_at=now,
    )
    session.add(proc)
    session.flush()
    return proc


def _request(session, *, process_id: UUID, requestor_id: UUID) -> ApprovalRequest:
    now = datetime.now(UTC)
    req = ApprovalRequest(
        process_id=process_id,
        requestor_user_id=requestor_id,
        title="Hook Test Request",
        state="approved",
        current_stage=1,
        created_by=requestor_id,
        updated_by=requestor_id,
        created_at=now,
        updated_at=now,
    )
    session.add(req)
    session.flush()
    return req


def _count_announcements(session, *, source_type: str = "auto") -> int:
    rows = session.exec(
        select(Announcement).where(
            Announcement.source_type == source_type,
            Announcement.is_deleted == False,  # noqa: E712
        )
    ).all()
    return len(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAutoAnnounceHook:
    def test_hook_fires_when_process_has_auto_announce_true(self, db_session) -> None:
        """_run_post_approval creates an Announcement when auto_announce_on_approve=True."""
        _category(db_session, "NOTIFICATION")
        _audience_group(db_session, "H8_ALL", filter_json={})

        approver = _user(db_session)
        requestor = _user(db_session)

        proc = _process(
            db_session,
            auto_announce=True,
            target_json={
                "category_code": "NOTIFICATION",
                "audience_group_codes": ["H8_ALL"],
            },
        )
        req = _request(db_session, process_id=proc.id, requestor_id=requestor.id)

        before_count = _count_announcements(db_session)
        svc = ApprovalRequestService(db_session)
        svc._run_post_approval(req, proc, approver.id)

        after_count = _count_announcements(db_session)
        assert after_count == before_count + 1, (
            "Hook must create exactly 1 auto-announcement on approval"
        )

        created = db_session.exec(
            select(Announcement).where(
                Announcement.source_ref_id == req.id,
                Announcement.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert created is not None
        assert created.source_type == "auto"
        assert created.source_ref_id == req.id

    def test_hook_skips_when_process_has_auto_announce_false(self, db_session) -> None:
        """_run_post_approval creates no announcement when auto_announce_on_approve=False (default)."""
        _category(db_session, "NOTIFICATION")
        _audience_group(db_session, "H8_SKIP", filter_json={})

        approver = _user(db_session)
        requestor = _user(db_session)

        proc = _process(db_session, auto_announce=False)  # default — no hook
        req = _request(db_session, process_id=proc.id, requestor_id=requestor.id)

        before_count = _count_announcements(db_session)
        svc = ApprovalRequestService(db_session)
        svc._run_post_approval(req, proc, approver.id)

        after_count = _count_announcements(db_session)
        assert after_count == before_count, "No announcement when auto_announce_on_approve=False"

    def test_hook_uses_audience_from_target_json(self, db_session) -> None:
        """audience_group_codes in the created announcement matches target_json."""
        _category(db_session, "NOTIFICATION")
        _audience_group(db_session, "FACULTY_ALL", filter_json={})

        approver = _user(db_session)
        requestor = _user(db_session)

        proc = _process(
            db_session,
            auto_announce=True,
            target_json={
                "category_code": "NOTIFICATION",
                "audience_group_codes": ["FACULTY_ALL"],
            },
        )
        req = _request(db_session, process_id=proc.id, requestor_id=requestor.id)

        svc = ApprovalRequestService(db_session)
        svc._run_post_approval(req, proc, approver.id)

        created = db_session.exec(
            select(Announcement).where(
                Announcement.source_ref_id == req.id,
                Announcement.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert created is not None
        assert created.audience_group_codes == ["FACULTY_ALL"]

    def test_hook_renders_template_placeholders(self, db_session) -> None:
        """title_template with {process_title} is expanded using the process's title."""
        _category(db_session, "NOTIFICATION")
        _audience_group(db_session, "H8_TMPL", filter_json={})

        approver = _user(db_session)
        requestor = _user(db_session)

        proc = _process(
            db_session,
            auto_announce=True,
            target_json={
                "category_code": "NOTIFICATION",
                "audience_group_codes": ["H8_TMPL"],
                "title_template": "Approved: {process_title}",
                "message_template": "Request {request_id} approved by {approver_username}.",
            },
        )
        req = _request(db_session, process_id=proc.id, requestor_id=requestor.id)

        svc = ApprovalRequestService(db_session)
        svc._run_post_approval(req, proc, approver.id)

        created = db_session.exec(
            select(Announcement).where(
                Announcement.source_ref_id == req.id,
                Announcement.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert created is not None
        assert "Hook Test Process" in created.title, (
            f"Expected process title in announcement title; got: {created.title!r}"
        )
        assert approver.username in created.message_text, (
            f"Expected approver username in message; got: {created.message_text!r}"
        )

    def test_hook_failure_does_not_fail_approval(self, db_session) -> None:
        """A bad target_json (nonexistent category) logs a warning but does not raise.

        The approval workflow must complete regardless of whether the auto-announcement
        hook succeeds — create_auto_announcement raises AnnouncementError for unknown
        category, which the hook catches and logs.
        """
        # Intentionally do NOT create category "DOES_NOT_EXIST"
        _audience_group(db_session, "H8_FAIL", filter_json={})

        approver = _user(db_session)
        requestor = _user(db_session)

        proc = _process(
            db_session,
            auto_announce=True,
            target_json={
                "category_code": "DOES_NOT_EXIST",  # unknown — will raise inside hook
                "audience_group_codes": ["H8_FAIL"],
            },
        )
        req = _request(db_session, process_id=proc.id, requestor_id=requestor.id)

        before_count = _count_announcements(db_session)
        svc = ApprovalRequestService(db_session)

        # Must not raise — hook failures are caught and logged
        svc._run_post_approval(req, proc, approver.id)

        # No announcement was created (the attempt raised, was caught, and logged)
        after_count = _count_announcements(db_session)
        assert after_count == before_count, (
            "Hook failure must not create a partial announcement row"
        )
