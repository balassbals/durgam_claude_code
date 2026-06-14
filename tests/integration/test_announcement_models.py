"""Model smoke tests for M9 Announcement schema (Phase 1).

Five tests; each inserts one row, queries it back, and asserts the round-trip.
All use db_session (clean DB, rollback per test) — no seeded_session.
"""
from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from durgam.models.announcement import (
    Announcement,
    AnnouncementCategory,
    AnnouncementComposerConfig,
    AudienceGroup,
)
from durgam.models.crosscutting import ApprovalProcess
from durgam.models.identity import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(session) -> User:
    from durgam.services.password import hash_password

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_announcement_category_unique_code(db_session):
    """Second insert with the same code raises IntegrityError."""
    cat1 = AnnouncementCategory(code="TEST_CAT", name="Test Category", display_order=99)
    db_session.add(cat1)
    db_session.flush()

    cat2 = AnnouncementCategory(code="TEST_CAT", name="Duplicate Code")
    db_session.add(cat2)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_audience_group_filter_json_roundtrip(db_session):
    """filter_json JSONB round-trips correctly through PostgreSQL."""
    fj = {"role_codes": ["FACULTY"], "scope_type": "school", "scope_codes": ["SCI"]}
    ag = AudienceGroup(code="TEST_AG", name="Test Audience Group", filter_json=fj)
    db_session.add(ag)
    db_session.flush()
    db_session.refresh(ag)

    assert ag.filter_json == fj
    assert ag.filter_json["role_codes"] == ["FACULTY"]
    assert ag.filter_json["scope_codes"] == ["SCI"]


def test_announcement_composer_config_unique_role(db_session):
    """Second row with the same role_code raises IntegrityError."""
    cfg1 = AnnouncementComposerConfig(role_code="FACULTY", priority_rank=999)
    db_session.add(cfg1)
    db_session.flush()

    cfg2 = AnnouncementComposerConfig(role_code="FACULTY", priority_rank=998)
    db_session.add(cfg2)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_announcement_insert_with_audience_groups(db_session):
    """Full Announcement row inserts and all fields round-trip correctly."""
    user = _make_user(db_session)
    now = _now()

    ann = Announcement(
        title="Test Announcement",
        message_text="This is a test message.",
        scheduled_at=now,
        importance="normal",
        category_code="NOTICE",
        audience_group_codes=["FACULTY_SCI"],
        ad_hoc_user_ids=None,
        exclude_user_ids=None,
        composer_user_id=user.id,
        composer_role_code="FACULTY",
        source_type="manual",
    )
    db_session.add(ann)
    db_session.flush()
    db_session.refresh(ann)

    assert ann.id is not None
    assert ann.title == "Test Announcement"
    assert ann.importance == "normal"
    assert ann.category_code == "NOTICE"
    assert ann.audience_group_codes == ["FACULTY_SCI"]
    assert ann.ad_hoc_user_ids is None
    assert ann.source_type == "manual"
    assert ann.composer_user_id == user.id
    assert ann.important_until is None


def test_approval_process_auto_announce_columns(db_session):
    """ApprovalProcess new columns round-trip correctly."""
    proc = ApprovalProcess(
        code=f"TEST_PROC_{uuid4().hex[:6]}",
        title="Test Process",
        auto_announce_on_approve=True,
        auto_announce_target_json={"audience_group_codes": ["ALL"]},
    )
    db_session.add(proc)
    db_session.flush()
    db_session.refresh(proc)

    assert proc.auto_announce_on_approve is True
    assert proc.auto_announce_target_json == {"audience_group_codes": ["ALL"]}
