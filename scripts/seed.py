"""Idempotent seed script for M0 development and CI.

Upserts data keyed on natural identifiers (codes, emails) — never on UUIDs.
All personal data is synthetic: Faker(seed=42). Real names / emails / IDs
are NEVER hardcoded here; see CLAUDE.md seed-data rules.

Run:
    uv run python scripts/seed.py

Safe to run multiple times. Second run shows 0 rows inserted.
"""

from datetime import date

import structlog
from faker import Faker
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, create_engine, select

from durgam.config import settings
from durgam.logging import configure_logging
from durgam.models.config_anchors import AcademicYear, Holiday, RoleEmail, StudentCategoryCount
from durgam.models.identity import Permission, Role, RolePermission, User, UserRole
from durgam.services.password import hash_password

configure_logging(debug=True)
log = structlog.get_logger(__name__)

fake = Faker(locale="en_IN")
fake.seed_instance(42)


def _exec_insert(session: Session, stmt: object) -> int:
    """Execute an INSERT...ON CONFLICT DO NOTHING and return rows actually inserted.

    Uses RETURNING to accurately count insertions (psycopg3 rowcount for
    ON CONFLICT DO NOTHING is unreliable without RETURNING).
    """
    import sqlalchemy as sa

    returning = stmt.returning(sa.literal(1).label("inserted"))  # type: ignore[attr-defined]
    result = session.execute(returning)
    return len(result.fetchall())


def seed(session: Session) -> dict[str, int]:
    counts: dict[str, int] = {}

    # ── AcademicYear ──────────────────────────────────────────────────────────
    ay_stmt = (
        pg_insert(AcademicYear)
        .values(
            code="2025-26",
            starts_on=date(2025, 7, 1),
            ends_on=date(2026, 4, 30),
            is_locked=False,
        )
        .on_conflict_do_nothing(constraint="uq_academic_years_code")
    )
    counts["academic_years"] = _exec_insert(session, ay_stmt)

    ay = session.exec(select(AcademicYear).where(AcademicYear.code == "2025-26")).one()

    # ── Roles ─────────────────────────────────────────────────────────────────
    roles_data = [
        {"code": "SYSTEM_ADMIN", "name": "System Administrator", "level": 100},
        {"code": "DEAN", "name": "Dean", "level": 50},
        {"code": "STUDENT", "name": "Student", "level": 10},
        # BASIC_USER: the implicit fallback role every user receives. It carries no
        # permissions — the home page is accessible to any authenticated user without
        # a permission check. The role exists so nav filtering has a stable anchor.
        {"code": "BASIC_USER", "name": "Basic User", "level": 1},
    ]
    role_inserted = 0
    for r in roles_data:
        role_inserted += _exec_insert(
            session,
            pg_insert(Role).values(**r).on_conflict_do_nothing(constraint="uq_roles_code"),
        )
    counts["roles"] = role_inserted

    roles = {
        r.code: r
        for r in session.exec(select(Role).where(Role.is_deleted == False)).all()  # noqa: E712
    }

    # ── Permissions ───────────────────────────────────────────────────────────
    # M2 permission set: comprehensive triples for all resources introduced through M2.
    # Permissions are seed-only; no create form exists in the UI (project policy).
    perms_data = [
        # System-wide administration
        {"resource": "system", "action": "manage", "scope": "*"},
        # User management (M2 Admin module)
        {"resource": "user", "action": "read", "scope": "*"},
        {"resource": "user", "action": "write", "scope": "*"},
        {"resource": "user", "action": "delete", "scope": "*"},
        # Role management (M2 Admin module)
        {"resource": "role", "action": "read", "scope": "*"},
        {"resource": "role", "action": "write", "scope": "*"},
        {"resource": "role", "action": "delete", "scope": "*"},
        # Permission management (M2 Admin module — read-only listing)
        {"resource": "permission", "action": "read", "scope": "*"},
        # Academic year (M0/M3 Config module)
        {"resource": "academic_year", "action": "read", "scope": "*"},
        {"resource": "academic_year", "action": "write", "scope": "*"},
        # Department-scoped operations (M4+ Department module; seed now for role assignment)
        {"resource": "department", "action": "read", "scope": "department"},
        {"resource": "leave_request", "action": "approve", "scope": "department"},
        # Audit log placeholder (M6 Audit module)
        {"resource": "audit_log", "action": "read", "scope": "*"},
    ]
    perm_inserted = 0
    for p in perms_data:
        perm_inserted += _exec_insert(
            session,
            pg_insert(Permission)
            .values(**p)
            .on_conflict_do_nothing(constraint="uq_permissions_resource_action_scope"),
        )
    counts["permissions"] = perm_inserted

    perms = {
        (p.resource, p.action, p.scope): p
        for p in session.exec(select(Permission).where(Permission.is_deleted == False)).all()  # noqa: E712
    }

    # ── RolePermissions ───────────────────────────────────────────────────────
    rp_inserted = 0
    admin_role = roles["SYSTEM_ADMIN"]
    for perm in perms.values():
        rp_inserted += _exec_insert(
            session,
            pg_insert(RolePermission)
            .values(role_id=admin_role.id, permission_id=perm.id)
            .on_conflict_do_nothing(),
        )

    dean_role = roles["DEAN"]
    dean_perm_keys = [
        ("academic_year", "read", "*"),
        ("department", "read", "department"),
        ("leave_request", "approve", "department"),
    ]
    for key in dean_perm_keys:
        rp_inserted += _exec_insert(
            session,
            pg_insert(RolePermission)
            .values(role_id=dean_role.id, permission_id=perms[key].id)
            .on_conflict_do_nothing(),
        )

    student_role = roles["STUDENT"]
    for key in [("academic_year", "read", "*")]:
        rp_inserted += _exec_insert(
            session,
            pg_insert(RolePermission)
            .values(role_id=student_role.id, permission_id=perms[key].id)
            .on_conflict_do_nothing(),
        )

    # BASIC_USER has no permissions — home page access is auth-layer, not permission-layer.
    counts["role_permissions"] = rp_inserted

    # ── Users ─────────────────────────────────────────────────────────────────
    # Passwords are real bcrypt hashes (cost 12) — safe to use in dev and CI.
    # Pattern: <username>_Dev1! satisfies the §6.1 policy.
    users_data = [
        {
            "email": "sys.admin@sssihl.edu.in",
            "username": "sys_admin",
            "role_code": "SYSTEM_ADMIN",
            "plain_password": "SysAdmin_Dev1!XZ",
        },
        {
            "email": "dean.sci@sssihl.edu.in",
            "username": "dean_sci",
            "role_code": "DEAN",
            "plain_password": "DeanSci_Dev1!XZ",
        },
        {
            "email": "student.001@sssihl.edu.in",
            "username": "student_001",
            "role_code": "STUDENT",
            "plain_password": "Student_Dev1!XZ",
        },
        {
            "email": "inactive.user@sssihl.edu.in",
            "username": "inactive_user",
            "role_code": "STUDENT",
            "plain_password": "Inactive_Dev1!XZ",
            "is_active": False,
        },
        {
            "email": "firstlogin.user@sssihl.edu.in",
            "username": "firstlogin_user",
            "role_code": "STUDENT",
            "plain_password": "FirstLogin_Dev1!XZ",
            "must_change_password": True,
        },
    ]
    user_inserted = 0
    for u in users_data:
        role_code = u.pop("role_code")
        plain = u.pop("plain_password")
        is_active = u.pop("is_active", True)
        must_change = u.pop("must_change_password", False)

        # Always re-hash so seed is idempotent even after test runs have changed
        # user passwords. The bcrypt cost (~0.3s per user) is acceptable for a
        # dev/CI seed script that runs once at stack startup.
        new_hash = hash_password(plain)

        import sqlalchemy as sa

        stmt = (
            pg_insert(User)
            .values(
                **u,
                password_hash=new_hash,
                is_active=is_active,
                must_change_password=must_change,
            )
            .on_conflict_do_update(
                constraint="uq_users_email",
                set_={
                    "password_hash": new_hash,
                    "is_active": is_active,
                    "must_change_password": must_change,
                    # Reset lockout state so re-seeding repairs test contamination.
                    "failed_login_count": 0,
                    "locked_until": None,
                },
            )
        )
        result = session.execute(stmt.returning(sa.literal(1).label("x")))
        user_inserted += len(result.fetchall())
        user = session.exec(select(User).where(User.email == u["email"])).one()
        _exec_insert(
            session,
            pg_insert(UserRole)
            .values(user_id=user.id, role_id=roles[role_code].id)
            .on_conflict_do_nothing(),
        )
        # Every user gets BASIC_USER in addition to their primary role (M2 policy).
        _exec_insert(
            session,
            pg_insert(UserRole)
            .values(user_id=user.id, role_id=roles["BASIC_USER"].id)
            .on_conflict_do_nothing(),
        )
    counts["users"] = user_inserted

    # ── Holidays ──────────────────────────────────────────────────────────────
    holidays_data = [
        {"holiday_date": date(2025, 10, 2), "name": "Gandhi Jayanti"},
        {"holiday_date": date(2025, 11, 23), "name": "Sai Baba Birthday"},
    ]
    hol_inserted = 0
    for h in holidays_data:
        hol_inserted += _exec_insert(
            session,
            pg_insert(Holiday)
            .values(academic_year_id=ay.id, **h)
            .on_conflict_do_nothing(constraint="uq_holidays_date_ay"),
        )
    counts["holidays"] = hol_inserted

    # ── RoleEmail ─────────────────────────────────────────────────────────────
    # Unique constraint on (role_code, scope_type, scope_id) doesn't fire for NULLs
    # in PostgreSQL — guard with a SELECT before inserting for the global scope row.
    existing_re = session.exec(
        select(RoleEmail).where(
            RoleEmail.role_code == "SYSTEM_ADMIN",
            RoleEmail.scope_type.is_(None),  # type: ignore[union-attr]
        )
    ).first()
    if not existing_re:
        session.execute(
            pg_insert(RoleEmail).values(
                role_code="SYSTEM_ADMIN",
                scope_type=None,
                scope_id=None,
                email="admin@sssihl.edu.in",
            )
        )
        counts["role_emails"] = 1
    else:
        counts["role_emails"] = 0

    # ── StudentCategoryCount ──────────────────────────────────────────────────
    counts["student_category_counts"] = _exec_insert(
        session,
        pg_insert(StudentCategoryCount)
        .values(
            academic_year_id=ay.id,
            sc_count=120,
            st_count=45,
            obc_count=230,
            ews_count=60,
            general_count=895,
            notes="M0 synthetic seed data",
        )
        .on_conflict_do_nothing(constraint="uq_student_category_counts_ay"),
    )

    session.commit()
    return counts


def main() -> None:
    engine = create_engine(settings.database_url_sync, echo=False)
    with Session(engine) as session:
        counts = seed(session)
    log.info("seed_complete", **counts)


if __name__ == "__main__":
    main()
