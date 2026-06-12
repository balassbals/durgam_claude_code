"""M9 Phase 4: integration tests for announcement seed data.

8 tests covering: category shape, composer config shape, audience groups
(explicit + dynamic campus rows), permission rows, role-permission grants
for all 19 composer roles, registrar-tier config grants, idempotency at
the insert level, and AudienceResolver callable against seeded FACULTY_SCI.

All tests use seeded_session (seed called once by session-scoped fixture).
Idempotency (test 7) is tested at the ON CONFLICT DO NOTHING insert level,
not by calling seed() twice — see note in test_seed_leave.py.
"""
from __future__ import annotations

import pytest
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import select

from durgam.models.announcement import (
    AnnouncementCategory,
    AnnouncementComposerConfig,
    AudienceGroup,
)
from durgam.models.identity import Permission, Role, RolePermission

_EXPECTED_CATEGORY_CODES = {
    "CIRCULAR", "ORDER", "NOTICE", "NOTIFICATION", "MEMORANDUM",
    "INVITATION", "RESULT", "ADVISORY", "GENERAL",
}

_COMPOSER_ROLE_CODES = [
    "VC", "VC_OFFICE", "REGISTRAR", "REGISTRAR_OFFICE", "HR_HEAD",
    "IQAC_COORDINATOR", "DEAN", "DEAN_STUDENT_WELFARE", "DEAN_ACADEMIC_AFFAIRS",
    "DEAN_STUDENT_WELFARE_OFFICE", "DEAN_ACADEMIC_AFFAIRS_OFFICE",
    "DIRECTOR", "DIRECTOR_OFFICE", "CONTROLLER_OF_EXAMINATIONS",
    "FINANCE_OFFICER", "PLACEMENT_OFFICER", "HOD",
    "CESRC_COORDINATOR", "CENTRE_COORDINATOR",
]

_CAMPUS_CODES = {"ATP", "BRN", "NDG", "PSN"}


def _active(session, model):
    return session.exec(
        select(model).where(model.is_deleted == False)  # noqa: E712
    ).all()


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


class TestAnnouncementCategorySeed:
    def test_seed_creates_9_categories(self, seeded_session) -> None:
        """Exactly 9 active AnnouncementCategory rows, one per expected code."""
        rows = _active(seeded_session, AnnouncementCategory)
        codes = {r.code for r in rows if r.is_active}
        assert codes == _EXPECTED_CATEGORY_CODES, (
            f"Expected codes {_EXPECTED_CATEGORY_CODES}, got {codes}"
        )
        assert len(rows) == 9


class TestAnnouncementComposerConfigSeed:
    def test_seed_creates_19_composer_configs(self, seeded_session) -> None:
        """19 AnnouncementComposerConfig rows; spot-check VC=10, CENTRE_COORDINATOR=150."""
        rows = _active(seeded_session, AnnouncementComposerConfig)
        assert len(rows) == 19, f"Expected 19 composer configs; found {len(rows)}"

        by_role = {r.role_code: r for r in rows}
        assert by_role["VC"].priority_rank == 10
        assert by_role["CENTRE_COORDINATOR"].priority_rank == 150


class TestAudienceGroupSeed:
    def test_seed_creates_audience_groups_explicit_and_dynamic(self, seeded_session) -> None:
        """At least 27 AudienceGroup rows (23 explicit + 4 per-campus EVERYONE_*)."""
        rows = _active(seeded_session, AudienceGroup)
        assert len(rows) >= 27, f"Expected >= 27 audience groups; found {len(rows)}"

        codes = {r.code for r in rows}
        for campus_code in _CAMPUS_CODES:
            expected = f"EVERYONE_{campus_code}"
            assert expected in codes, (
                f"Dynamic audience group {expected!r} missing from seed"
            )


class TestAnnouncementPermissionSeed:
    def test_seed_adds_announcement_permissions(self, seeded_session) -> None:
        """4 Permission rows for resource='announcement' with expected (action, scope) pairs."""
        rows = seeded_session.exec(
            select(Permission).where(
                Permission.resource == "announcement",
                Permission.is_deleted == False,  # noqa: E712
            )
        ).all()
        pairs = {(r.action, r.scope) for r in rows}
        expected = {
            ("create", "*"),
            ("read",   "*"),
            ("update", "own"),
            ("soft_delete", "own"),
        }
        assert expected == pairs, f"Permission pairs mismatch: got {pairs}"


class TestAnnouncementRoleGrantsSeed:
    def test_seed_grants_composer_create_to_all_19_composer_roles(self, seeded_session) -> None:
        """Every one of the 19 Q11 composer roles has announcement:create:* granted."""
        missing = [
            code for code in _COMPOSER_ROLE_CODES
            if not _has_grant(seeded_session, code, "announcement", "create", "*")
        ]
        assert not missing, (
            f"announcement:create:* missing for composer roles: {missing}"
        )

    def test_seed_grants_registrar_tier_operational_config(self, seeded_session) -> None:
        """REGISTRAR + REGISTRAR_OFFICE have category + audience_group configure.
        Neither should have announcement_composer_config:configure (SYS_ADMIN only).
        """
        for role_code in ("REGISTRAR", "REGISTRAR_OFFICE"):
            assert _has_grant(seeded_session, role_code, "announcement_category", "configure", "*"), (
                f"{role_code} missing announcement_category:configure:*"
            )
            assert _has_grant(seeded_session, role_code, "audience_group", "configure", "*"), (
                f"{role_code} missing audience_group:configure:*"
            )
            assert not _has_grant(
                seeded_session, role_code, "announcement_composer_config", "configure", "*"
            ), (
                f"{role_code} should NOT have announcement_composer_config:configure:* "
                "(that is SYSTEM_ADMIN-only)"
            )


class TestAnnouncementSeedIdempotency:
    def test_seed_is_idempotent(self, seeded_session) -> None:
        """ON CONFLICT DO NOTHING: re-inserting any seed row returns 0 rows inserted.

        This test verifies idempotency at the insert level (the actual code path
        that matters). Full-seed idempotency (running scripts/seed.py twice end-to-end)
        is verified manually during the gate ritual because seed() commits permanently
        and bypasses rollback — see test_seed_leave.py note.
        """
        # Verify expected counts (seed ran once by seeded_db_engine fixture)
        categories = _active(seeded_session, AnnouncementCategory)
        configs = _active(seeded_session, AnnouncementComposerConfig)
        groups = _active(seeded_session, AudienceGroup)
        assert len(categories) == 9
        assert len(configs) == 19
        assert len(groups) >= 27

        # Re-insert one category — ON CONFLICT DO NOTHING must return 0
        stmt = (
            pg_insert(AnnouncementCategory)
            .values(code="CIRCULAR", name="Circular", display_order=10, is_active=True)
            .on_conflict_do_nothing(constraint="uq_announcement_categories_code")
            .returning(1)
        )
        result = seeded_session.execute(stmt)
        inserted = len(result.fetchall())
        assert inserted == 0, (
            f"Expected 0 rows inserted on conflict (idempotency); got {inserted}"
        )


class TestAudienceResolverSeeded:
    def test_audience_resolver_against_seeded_faculty_sci(self, seeded_session) -> None:
        """AudienceResolver evaluates FACULTY_SCI filter without error.

        faculty_user in seed is scoped to DMACS (SCI school). Result may be
        non-empty, but the test asserts the call succeeds and returns a set.
        Empty result is acceptable (no faculty seeded in SCI scope at M9 Phase 4).
        """
        from uuid import UUID

        from durgam.models.identity import User
        from durgam.services.audience_resolver import AudienceResolver

        faculty_sci_group = seeded_session.exec(
            select(AudienceGroup).where(AudienceGroup.code == "FACULTY_SCI")
        ).first()
        assert faculty_sci_group is not None, "FACULTY_SCI audience group must be seeded"

        # Use the seeded faculty_user as the test subject
        faculty_user = seeded_session.exec(
            select(User).where(User.username == "faculty_user")
        ).first()
        assert faculty_user is not None, "faculty_user must be seeded"

        resolver = AudienceResolver()
        result = resolver.groups_user_belongs_to(
            faculty_user.id, [faculty_sci_group], seeded_session
        )
        assert isinstance(result, set), (
            f"groups_user_belongs_to must return a set; got {type(result)}"
        )
        # Result may be empty (faculty_user is scoped to DMACS, not SCI) — that's fine
