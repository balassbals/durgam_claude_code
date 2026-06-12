"""Integration tests for AudienceResolver (M9).

11 tests covering: empty filter (ALL), role_codes filter, scope_type filter,
scope_codes resolution, combined role+scope, exclusion, ad_hoc, program_degree_types
forward concern, resolve_recipients, user_can_see, groups_user_belongs_to.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.announcement import Announcement, AudienceGroup
from durgam.models.campus import Campus
from durgam.models.department import Department
from durgam.models.identity import Role, User, UserRole
from durgam.models.school import School
from durgam.services.audience_resolver import AudienceResolver
from durgam.services.password import hash_password

from datetime import UTC, datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(session) -> User:
    u = User(
        username=f"t{uuid4().hex[:8]}",
        email=f"t{uuid4().hex[:8]}@test.local",
        full_name="Test",
        password_hash=hash_password("Test_Dev1!XZ"),
        is_active=True,
    )
    session.add(u)
    session.flush()
    return u


def _role(session, code: str) -> Role:
    from sqlmodel import select
    existing = session.exec(select(Role).where(Role.code == code)).first()
    if existing:
        return existing
    r = Role(code=code, name=code, level=10)
    session.add(r)
    session.flush()
    return r


def _assign_role(session, user_id, role_id, scope_type=None, scope_id=None) -> UserRole:
    ur = UserRole(user_id=user_id, role_id=role_id, scope_type=scope_type, scope_id=scope_id)
    session.add(ur)
    session.flush()
    return ur


def _group(code: str, filter_json: dict) -> AudienceGroup:
    return AudienceGroup(code=code, name=code, filter_json=filter_json, is_active=True)


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_filter_matches_all_users(db_session):
    """Empty filter_json means ALL users — resolver returns True."""
    resolver = AudienceResolver()
    user = _user(db_session)
    assert resolver._evaluate_filter(user.id, {}, db_session) is True


def test_role_codes_filter_match(db_session):
    """User with the specified role returns True."""
    resolver = AudienceResolver()
    user = _user(db_session)
    role = _role(db_session, f"ROLE_{uuid4().hex[:6]}")
    _assign_role(db_session, user.id, role.id)

    result = resolver._evaluate_filter(user.id, {"role_codes": [role.code]}, db_session)
    assert result is True


def test_role_codes_filter_no_match(db_session):
    """User without the specified role returns False."""
    resolver = AudienceResolver()
    user = _user(db_session)
    # Do not assign any roles

    result = resolver._evaluate_filter(user.id, {"role_codes": ["NONEXISTENT_ROLE_X"]}, db_session)
    assert result is False


def test_scope_type_filter_match(db_session):
    """User with matching scope_type returns True."""
    resolver = AudienceResolver()
    user = _user(db_session)
    role = _role(db_session, f"HOD_{uuid4().hex[:6]}")

    school = School(code=f"SC{uuid4().hex[:4]}", name="Test School")
    db_session.add(school)
    db_session.flush()

    campus = Campus(code=f"CP{uuid4().hex[:4]}", name="Test Campus")
    db_session.add(campus)
    db_session.flush()

    dept = Department(
        code=f"D{uuid4().hex[:4]}", name="Test Dept",
        school_id=school.id, main_campus_id=campus.id,
    )
    db_session.add(dept)
    db_session.flush()

    _assign_role(db_session, user.id, role.id, scope_type="department", scope_id=dept.id)

    result = resolver._evaluate_filter(
        user.id,
        {"role_codes": [role.code], "scope_type": "department"},
        db_session,
    )
    assert result is True


def test_scope_codes_resolution(db_session):
    """scope_codes are resolved to IDs via the scope table lookup."""
    resolver = AudienceResolver()
    user = _user(db_session)
    role = _role(db_session, f"DIR_{uuid4().hex[:6]}")

    campus = Campus(code=f"C{uuid4().hex[:4]}", name="Test Campus")
    db_session.add(campus)
    db_session.flush()

    _assign_role(db_session, user.id, role.id, scope_type="campus", scope_id=campus.id)

    result = resolver._evaluate_filter(
        user.id,
        {"role_codes": [role.code], "scope_type": "campus", "scope_codes": [campus.code]},
        db_session,
    )
    assert result is True


def test_scope_codes_wrong_campus(db_session):
    """User scoped to campus A does not match filter for campus B code."""
    resolver = AudienceResolver()
    user = _user(db_session)
    role = _role(db_session, f"DIR2_{uuid4().hex[:6]}")

    campus_a = Campus(code=f"CA{uuid4().hex[:4]}", name="Campus A")
    campus_b = Campus(code=f"CB{uuid4().hex[:4]}", name="Campus B")
    db_session.add(campus_a)
    db_session.add(campus_b)
    db_session.flush()

    _assign_role(db_session, user.id, role.id, scope_type="campus", scope_id=campus_a.id)

    result = resolver._evaluate_filter(
        user.id,
        {"role_codes": [role.code], "scope_type": "campus", "scope_codes": [campus_b.code]},
        db_session,
    )
    assert result is False


def test_program_degree_types_returns_false_forward_concern(db_session):
    """program_degree_types filter returns False (no enrollment model yet)."""
    resolver = AudienceResolver()
    user = _user(db_session)

    result = resolver._evaluate_filter(
        user.id,
        {"program_degree_types": ["BSc"]},
        db_session,
    )
    assert result is False


def test_groups_user_belongs_to(db_session):
    """Returns only the groups the user matches."""
    resolver = AudienceResolver()
    user = _user(db_session)
    role = _role(db_session, f"FAC_{uuid4().hex[:6]}")
    _assign_role(db_session, user.id, role.id)

    groups = [
        _group("ALL", {}),                               # matches everyone
        _group("FAC_GROUP", {"role_codes": [role.code]}), # matches this user
        _group("HOD_GROUP", {"role_codes": ["HOD_ONLY_FAKE"]}),  # doesn't match
    ]
    db_session.add_all(groups)
    db_session.flush()

    codes = resolver.groups_user_belongs_to(user.id, groups, db_session)
    assert "ALL" in codes
    assert "FAC_GROUP" in codes
    assert "HOD_GROUP" not in codes


def test_user_can_see_exclusion_overrides_group(db_session):
    """User in group but in exclude list cannot see announcement."""
    resolver = AudienceResolver()
    composer = _user(db_session)
    viewer = _user(db_session)

    group = _group("SOME_GROUP", {})
    db_session.add(group)
    db_session.flush()

    ann = Announcement(
        title="Excluded",
        message_text="Not for you",
        scheduled_at=_now(),
        importance="normal",
        category_code="NOTICE",
        audience_group_codes=["SOME_GROUP"],
        exclude_user_ids=[str(viewer.id)],
        composer_user_id=composer.id,
        composer_role_code="FACULTY",
        source_type="manual",
    )
    db_session.add(ann)
    db_session.flush()

    groups_by_code = {"SOME_GROUP": group}
    assert resolver.user_can_see(viewer.id, ann, groups_by_code, db_session) is False


def test_user_can_see_ad_hoc_overrides_no_group(db_session):
    """Ad-hoc user can see announcement even without group membership."""
    resolver = AudienceResolver()
    composer = _user(db_session)
    viewer = _user(db_session)

    group = _group("SOME_GROUP2", {"role_codes": ["NONEXISTENT_ROLE"]})
    db_session.add(group)
    db_session.flush()

    ann = Announcement(
        title="Ad hoc",
        message_text="Just for you",
        scheduled_at=_now(),
        importance="normal",
        category_code="NOTICE",
        audience_group_codes=["SOME_GROUP2"],
        ad_hoc_user_ids=[str(viewer.id)],
        composer_user_id=composer.id,
        composer_role_code="FACULTY",
        source_type="manual",
    )
    db_session.add(ann)
    db_session.flush()

    groups_by_code = {"SOME_GROUP2": group}
    assert resolver.user_can_see(viewer.id, ann, groups_by_code, db_session) is True


def test_resolve_recipients_empty_filter_returns_active_users(db_session):
    """Empty filter → all active users returned in recipient list."""
    resolver = AudienceResolver()
    user1 = _user(db_session)
    user2 = _user(db_session)

    group = _group("ALL_GROUP", {})
    db_session.add(group)
    db_session.flush()

    recipients = resolver.resolve_recipients(
        ["ALL_GROUP"],
        {"ALL_GROUP": group},
        db_session,
    )
    recipient_ids = set(recipients)
    assert user1.id in recipient_ids
    assert user2.id in recipient_ids
