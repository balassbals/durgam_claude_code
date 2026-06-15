"""Integration tests for M10 Phase 2 permission catalog (D-010, D-011).

Verifies that the 13 new permission triples are seeded and assigned to
the correct roles. Uses the seeded_session fixture (real PostgreSQL, rolled
back after each test).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from durgam.models.identity import Permission, Role, RolePermission


def _get_perm(
    session: Session, resource: str, action: str, scope: str
) -> Permission | None:
    return session.exec(
        select(Permission).where(
            Permission.resource == resource,
            Permission.action == action,
            Permission.scope == scope,
            Permission.is_deleted == False,  # noqa: E712
        )
    ).first()


def _role_has_perm(
    session: Session, role_code: str, resource: str, action: str, scope: str
) -> bool:
    perm = _get_perm(session, resource, action, scope)
    if perm is None:
        return False
    role = session.exec(
        select(Role).where(Role.code == role_code, Role.is_deleted == False)  # noqa: E712
    ).first()
    if role is None:
        return False
    # RolePermission has no is_deleted — it's a plain junction table
    rp = session.exec(
        select(RolePermission).where(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == perm.id,
        )
    ).first()
    return rp is not None


_M10_NEW_TRIPLES = [
    ("faculty",           "read",        "*"),
    ("faculty",           "write",       "own"),
    ("faculty",           "write",       "*"),
    ("faculty_sensitive", "read",        "*"),
    ("faculty_document",  "read",        "*"),
    ("faculty_request",   "create",      "own"),
    ("faculty_request",   "read",        "own"),
    ("faculty_request",   "read",        "*"),
    ("faculty_workload",  "read",        "*"),
    ("faculty_workload",  "write",       "own"),
    ("faculty",           "bulk_import", "*"),
    ("designation",       "configure",   "*"),
    ("approval_process",  "configure",   "*"),
]


class TestM10PermissionTriples:
    def test_all_13_new_triples_seeded(self, seeded_session: Session) -> None:
        missing = []
        for resource, action, scope in _M10_NEW_TRIPLES:
            perm = _get_perm(seeded_session, resource, action, scope)
            if perm is None:
                missing.append(f"{resource}:{action}:{scope}")
        assert not missing, f"Missing permission triples after seed: {missing}"

    def test_faculty_read_star_assigned_to_faculty_role(
        self, seeded_session: Session
    ) -> None:
        assert _role_has_perm(seeded_session, "FACULTY", "faculty", "read", "*")

    def test_faculty_write_own_assigned_to_faculty_role(
        self, seeded_session: Session
    ) -> None:
        assert _role_has_perm(seeded_session, "FACULTY", "faculty", "write", "own")

    def test_faculty_write_star_assigned_to_registrar(
        self, seeded_session: Session
    ) -> None:
        assert _role_has_perm(seeded_session, "REGISTRAR", "faculty", "write", "*")

    def test_faculty_write_star_assigned_to_hr_head(
        self, seeded_session: Session
    ) -> None:
        assert _role_has_perm(seeded_session, "HR_HEAD", "faculty", "write", "*")

    def test_faculty_write_star_not_assigned_to_faculty_role(
        self, seeded_session: Session
    ) -> None:
        # Faculty self-edit only; admin-write must NOT be granted to faculty role
        assert not _role_has_perm(seeded_session, "FACULTY", "faculty", "write", "*")

    def test_faculty_sensitive_read_assigned_to_registrar(
        self, seeded_session: Session
    ) -> None:
        assert _role_has_perm(
            seeded_session, "REGISTRAR", "faculty_sensitive", "read", "*"
        )

    def test_faculty_sensitive_read_assigned_to_iqac_coordinator(
        self, seeded_session: Session
    ) -> None:
        assert _role_has_perm(
            seeded_session, "IQAC_COORDINATOR", "faculty_sensitive", "read", "*"
        )

    def test_faculty_sensitive_read_assigned_to_iqac_office(
        self, seeded_session: Session
    ) -> None:
        """IQAC_OFFICE mirrors IQAC_COORDINATOR per Q-P2.1."""
        assert _role_has_perm(
            seeded_session, "IQAC_OFFICE", "faculty_sensitive", "read", "*"
        )

    def test_faculty_sensitive_read_not_assigned_to_hod(
        self, seeded_session: Session
    ) -> None:
        # HoD can see faculty requests but NOT sensitive PII
        assert not _role_has_perm(
            seeded_session, "HOD", "faculty_sensitive", "read", "*"
        )

    def test_professor_inherits_faculty_own(self, seeded_session: Session) -> None:
        assert _role_has_perm(seeded_session, "PROFESSOR", "faculty", "write", "own")
        assert _role_has_perm(
            seeded_session, "PROFESSOR", "faculty_request", "create", "own"
        )

    def test_hod_has_faculty_request_read_star(self, seeded_session: Session) -> None:
        assert _role_has_perm(
            seeded_session, "HOD", "faculty_request", "read", "*"
        )

    def test_ahod_has_faculty_request_read_star(self, seeded_session: Session) -> None:
        assert _role_has_perm(
            seeded_session, "AHOD", "faculty_request", "read", "*"
        )

    def test_system_admin_has_designation_configure(
        self, seeded_session: Session
    ) -> None:
        assert _role_has_perm(
            seeded_session, "SYSTEM_ADMIN", "designation", "configure", "*"
        )

    def test_system_admin_has_approval_process_configure(
        self, seeded_session: Session
    ) -> None:
        assert _role_has_perm(
            seeded_session, "SYSTEM_ADMIN", "approval_process", "configure", "*"
        )

    def test_iqac_office_role_exists(self, seeded_session: Session) -> None:
        role = seeded_session.exec(
            select(Role).where(
                Role.code == "IQAC_OFFICE",
                Role.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert role is not None, "IQAC_OFFICE role must be seeded (added at Phase 1A)"
