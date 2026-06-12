"""Integration tests for AudienceGroupService + repository (M9 Phase 5b).

12 tests covering: seeded data count, create with various filter_json shapes,
filter_json validation (unknown role, unknown scope code, invalid code format,
duplicate code), code immutability on update, scope-code query for school type,
and permission grants (REGISTRAR_OFFICE can configure, BASIC_USER cannot).
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlmodel import select

from durgam.models.announcement import AudienceGroup
from durgam.models.identity import Permission, Role, RolePermission
from durgam.models.school import School
from durgam.repositories.announcement import AudienceGroupRepository
from durgam.services.audience_group import AudienceGroupError, AudienceGroupService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo(session) -> AudienceGroupRepository:
    return AudienceGroupRepository(session)


def _svc(session) -> AudienceGroupService:
    return AudienceGroupService(repo=_repo(session), session=session)


def _actor() -> object:
    return uuid4()


def _unique_code() -> str:
    return f"TST_{uuid4().hex[:6].upper()}"


def _make_group(session, code: str, filter_json: dict | None = None) -> AudienceGroup:
    """Insert a raw AudienceGroup — used to set up test fixtures."""
    now = datetime.now(UTC)
    g = AudienceGroup(
        code=code.upper(),
        name=f"Name for {code}",
        filter_json=filter_json or {},
        is_active=True,
        created_by=uuid4(),
        updated_by=uuid4(),
        created_at=now,
        updated_at=now,
    )
    session.add(g)
    session.flush()
    return g


def _perm(session, resource: str, action: str, scope: str):
    return session.exec(
        select(Permission).where(
            Permission.resource == resource,
            Permission.action == action,
            Permission.scope == scope,
            Permission.is_deleted == False,  # noqa: E712
        )
    ).first()


def _role(session, code: str):
    return session.exec(
        select(Role).where(Role.code == code, Role.is_deleted == False)  # noqa: E712
    ).first()


def _has_grant(session, role_code: str, resource: str, action: str, scope: str) -> bool:
    role = _role(session, role_code)
    perm = _perm(session, resource, action, scope)
    if role is None or perm is None:
        return False
    rp = session.exec(
        select(RolePermission).where(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == perm.id,
        )
    ).first()
    return rp is not None


# ---------------------------------------------------------------------------
# Test 1: seeded data count
# ---------------------------------------------------------------------------

class TestAudienceGroupSeededData:
    def test_on_load_returns_seeded_audience_groups(self, seeded_session) -> None:
        """At least 27 audience group rows (23 explicit + 4 per-campus from Phase 4 seed)."""
        rows = seeded_session.exec(
            select(AudienceGroup).where(AudienceGroup.is_deleted == False)  # noqa: E712
        ).all()
        assert len(rows) >= 27, (
            f"Expected >= 27 seeded audience groups; found {len(rows)}"
        )


# ---------------------------------------------------------------------------
# Tests 2–4: create with valid filter_json shapes
# ---------------------------------------------------------------------------

class TestAudienceGroupCreate:
    def test_save_create_with_role_codes_only(self, db_session) -> None:
        """create() with only role_codes stores correct filter_json."""
        # Seeded role code FACULTY must exist — use BASIC_USER which is always seeded
        # (we verify via service which queries roles table)
        # Use a role code that definitely exists in a fresh db_session (seeded roles not
        # present in db_session — use a manually-inserted role).
        from durgam.models.identity import Role as RoleModel
        now = datetime.now(UTC)
        r = RoleModel(
            code="TMPTEACH",
            name="Temp Teacher",
            level=10,
            created_by=uuid4(),
            updated_by=uuid4(),
            created_at=now,
            updated_at=now,
        )
        db_session.add(r)
        db_session.flush()

        svc = _svc(db_session)
        code = _unique_code()
        entity = svc.create(
            code=code,
            name="Teachers only",
            description=None,
            filter_json={"role_codes": ["TMPTEACH"]},
            is_active=True,
            actor_id=uuid4(),
        )
        assert entity.id is not None
        assert entity.filter_json == {"role_codes": ["TMPTEACH"]}

    def test_save_create_with_scope_only(self, db_session) -> None:
        """create() with scope_type + scope_codes stores correct filter_json."""
        from durgam.models.school import School as SchoolModel
        now = datetime.now(UTC)
        s = SchoolModel(
            code="TSCI",
            name="Test School",
            created_by=uuid4(),
            updated_by=uuid4(),
            created_at=now,
            updated_at=now,
        )
        db_session.add(s)
        db_session.flush()

        svc = _svc(db_session)
        code = _unique_code()
        entity = svc.create(
            code=code,
            name="School group",
            description=None,
            filter_json={"scope_type": "school", "scope_codes": ["TSCI"]},
            is_active=True,
            actor_id=uuid4(),
        )
        assert entity.filter_json == {"scope_type": "school", "scope_codes": ["TSCI"]}

    def test_save_create_with_role_and_scope_and_degree_types(self, db_session) -> None:
        """create() with combined filter_json stores all keys."""
        from durgam.models.identity import Role as RoleModel
        from durgam.models.department import Department as DeptModel
        from durgam.models.campus import Campus as CampusModel
        from durgam.models.school import School as SchoolModel
        now = datetime.now(UTC)
        actor = uuid4()

        # Insert campus (needed for Department FK)
        camp = CampusModel(
            code="TCAMP",
            name="Test Campus",
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
        db_session.add(camp)
        db_session.flush()

        # Insert school (needed for Department school_id NOT NULL constraint)
        school = SchoolModel(
            code="TSCL",
            name="Test School",
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
        db_session.add(school)
        db_session.flush()

        dept = DeptModel(
            code="TDEPT",
            name="Test Dept",
            school_id=school.id,
            main_campus_id=camp.id,
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
        db_session.add(dept)
        db_session.flush()

        role = RoleModel(
            code="TSTFAC",
            name="Test Faculty",
            level=10,
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
        db_session.add(role)
        db_session.flush()

        svc = _svc(db_session)
        code = _unique_code()
        fj = {
            "role_codes": ["TSTFAC"],
            "scope_type": "department",
            "scope_codes": ["TDEPT"],
            "program_degree_types": ["PhD", "DPhil"],
        }
        entity = svc.create(
            code=code,
            name="Combined filter",
            description=None,
            filter_json=fj,
            is_active=True,
            actor_id=actor,
        )
        assert entity.filter_json["role_codes"] == ["TSTFAC"]
        assert entity.filter_json["scope_type"] == "department"
        assert entity.filter_json["scope_codes"] == ["TDEPT"]
        assert entity.filter_json["program_degree_types"] == ["PhD", "DPhil"]


# ---------------------------------------------------------------------------
# Tests 5–8: filter_json validation errors
# ---------------------------------------------------------------------------

class TestAudienceGroupValidation:
    def test_save_create_rejects_unknown_role_code(self, db_session) -> None:
        """create() raises AudienceGroupError for a role_code not in the roles table."""
        svc = _svc(db_session)
        with pytest.raises(AudienceGroupError, match="Unknown role codes"):
            svc.create(
                code=_unique_code(),
                name="Bad role",
                description=None,
                filter_json={"role_codes": ["FAKE_ROLE_DOESNOTEXIST"]},
                is_active=True,
                actor_id=uuid4(),
            )

    def test_save_create_rejects_scope_code_not_in_scope_table(self, db_session) -> None:
        """create() raises AudienceGroupError for a scope_code not in the schools table."""
        svc = _svc(db_session)
        with pytest.raises(AudienceGroupError, match="Unknown school codes"):
            svc.create(
                code=_unique_code(),
                name="Bad scope code",
                description=None,
                filter_json={"scope_type": "school", "scope_codes": ["FAKE_SCHOOL_X"]},
                is_active=True,
                actor_id=uuid4(),
            )

    def test_save_create_rejects_invalid_code_format(self, db_session) -> None:
        """create() raises AudienceGroupError when code doesn't match ^[A-Z][A-Z_0-9]*$."""
        svc = _svc(db_session)
        with pytest.raises(AudienceGroupError, match="Code must start with"):
            svc.create(
                code="lowercase-bad",
                name="Bad code format",
                description=None,
                filter_json={},
                is_active=True,
                actor_id=uuid4(),
            )

    def test_save_create_rejects_duplicate_code(self, db_session) -> None:
        """Second create() with same code raises AudienceGroupError."""
        code = _unique_code()
        _make_group(db_session, code)

        svc = _svc(db_session)
        with pytest.raises(AudienceGroupError, match="already exists"):
            svc.create(
                code=code,
                name="Duplicate",
                description=None,
                filter_json={},
                is_active=True,
                actor_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# Test 9: code immutability on update
# ---------------------------------------------------------------------------

class TestAudienceGroupUpdate:
    def test_save_edit_does_not_modify_code(self, db_session) -> None:
        """update() never changes the code; only name/description/filter_json/is_active."""
        original_code = _unique_code()
        group = _make_group(db_session, original_code, {})

        svc = _svc(db_session)
        updated = svc.update(
            id_=group.id,
            name="Updated Name",
            description="Some desc",
            filter_json={},
            is_active=True,
            actor_id=uuid4(),
        )
        assert updated.code == original_code.upper(), (
            f"Code must remain '{original_code.upper()}' after update; got '{updated.code}'"
        )
        assert updated.name == "Updated Name"


# ---------------------------------------------------------------------------
# Test 10: set_scope_type loads school codes
# ---------------------------------------------------------------------------

class TestAudienceGroupScopeCodeQuery:
    def test_scope_codes_for_school_type_returns_seeded_codes(self, seeded_session) -> None:
        """list_scope_codes_for_type('school') contains the 4 seeded school codes."""
        svc = _svc(seeded_session)
        codes = svc.list_scope_codes_for_type("school")
        expected = {"SCI", "HSS", "LL", "MC"}
        assert expected.issubset(set(codes)), (
            f"Expected seeded school codes {expected} in result; got {set(codes)}"
        )


# ---------------------------------------------------------------------------
# Tests 11–12: permission grants
# ---------------------------------------------------------------------------

class TestAudienceGroupPermissions:
    def test_permission_allows_registrar_office(self, seeded_session) -> None:
        """REGISTRAR_OFFICE has audience_group:configure:* grant in the seeded DB."""
        assert _has_grant(
            seeded_session, "REGISTRAR_OFFICE", "audience_group", "configure", "*"
        ), "REGISTRAR_OFFICE must have audience_group:configure:* (Registrar-tier governance)"

    def test_permission_denies_basic_user(self, seeded_session) -> None:
        """BASIC_USER does NOT have audience_group:configure:* — only read is public."""
        assert not _has_grant(
            seeded_session, "BASIC_USER", "audience_group", "configure", "*"
        ), "BASIC_USER must NOT have audience_group:configure:* (config is Registrar-tier only)"
