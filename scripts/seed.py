"""Idempotent seed script for M3 development and CI.

Upserts data keyed on natural identifiers (codes, emails) — never on UUIDs.
All personal data is synthetic. Real names / emails / IDs are NEVER hardcoded
here; see CLAUDE.md seed-data rules.

Run:
    uv run python scripts/seed.py

Safe to run multiple times. Second run shows 0 rows inserted for stable
entities and 1 (upserted) for users (password re-hash on every run).
"""

from datetime import date

import structlog
from faker import Faker
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, create_engine, select

import sqlalchemy as sa

from durgam.config import settings
from durgam.logging import configure_logging
from durgam.models.campus import Campus
from durgam.models.centre import CentreOfExcellence
from durgam.models.config_anchors import (
    AcademicYear,
    ClassTimingsConfig,
    Holiday,
    RoleEmail,
    StudentCategoryCount,
    WorkingDaysConfig,
)
from durgam.models.course import Course
from durgam.models.department import (
    Department,
    DepartmentCampus,
    SubDepartment,
    SubDepartmentCampus,
)
from durgam.models.identity import Permission, Role, RolePermission, User, UserRole
from durgam.models.program import (
    Program,
    ProgramExitLevel,
    ProgramOutcome,
    ProgramRegulation,
    ProgramScheme,
    ProgramSchemeCourse,
    ProgramSpecialisation,
)
from durgam.models.school import School
from durgam.models.vision_mission import (
    DepartmentMission,
    DepartmentVisionMission,
    UniversityMission,
    UniversityVisionMission,
)
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
    # Role levels reflect organisational hierarchy (Refinement 1-b):
    # SYSTEM_ADMIN=100 · REGISTRAR family=80-73 · DEAN_*=70 · HOD family=50-42
    # · STUDENT=10 · BASIC_USER=1
    # on_conflict_do_update so re-seeding repairs any level drift (e.g. DEAN 50→70).
    roles_data = [
        # Technical admin (cross-cutting; not in org hierarchy)
        {"code": "SYSTEM_ADMIN",       "name": "System Administrator",    "level": 100},
        # Registrar family
        {"code": "REGISTRAR",          "name": "Registrar",               "level": 80},
        {"code": "DEPUTY_REGISTRAR",   "name": "Deputy Registrar",        "level": 77},
        {"code": "REGISTRAR_OFFICE",   "name": "Registrar Office",        "level": 73},
        # School deans (one per school; school.dean_role_code references these)
        {"code": "DEAN",               "name": "Dean",                    "level": 70},
        {"code": "DEAN_SCI",           "name": "Dean — School of Sciences",                        "level": 70},
        {"code": "DEAN_HSS",           "name": "Dean — School of Humanities & Social Sciences",    "level": 70},
        {"code": "DEAN_LL",            "name": "Dean — School of Languages & Literature",          "level": 70},
        {"code": "DEAN_MC",            "name": "Dean — School of Management & Commerce",           "level": 70},
        # HoD family
        {"code": "HOD",                "name": "Head of Department",                 "level": 50},
        {"code": "AHOD",               "name": "Associate Head of Department",       "level": 45},
        {"code": "HOD_OFFICE",         "name": "Head of Department Office",          "level": 42},
        # Students and base
        {"code": "STUDENT",            "name": "Student",                            "level": 10},
        {"code": "BASIC_USER",         "name": "Basic User",                         "level": 1},
    ]
    role_counts = 0
    for r in roles_data:
        result = session.execute(
            pg_insert(Role)
            .values(**r)
            .on_conflict_do_update(
                constraint="uq_roles_code",
                set_={"name": r["name"], "level": r["level"]},
            )
            .returning(sa.literal(1).label("x"))
        )
        role_counts += len(result.fetchall())
    counts["roles"] = role_counts

    roles = {
        r.code: r
        for r in session.exec(select(Role).where(Role.is_deleted == False)).all()  # noqa: E712
    }

    # ── Permissions ───────────────────────────────────────────────────────────
    # Permissions are seed-only; no create form exists in the UI (project policy).
    # Existing M2 triples are included so a fresh DB seeds everything at once.
    perms_data = [
        # System (M2)
        {"resource": "system",           "action": "read",      "scope": "*"},
        {"resource": "system",           "action": "write",     "scope": "*"},
        {"resource": "system",           "action": "configure", "scope": "*"},
        # User management (M2)
        {"resource": "user",             "action": "read",      "scope": "*"},
        {"resource": "user",             "action": "write",     "scope": "*"},
        {"resource": "user",             "action": "delete",    "scope": "*"},
        # Role management (M2)
        {"resource": "role",             "action": "read",      "scope": "*"},
        {"resource": "role",             "action": "write",     "scope": "*"},
        {"resource": "role",             "action": "delete",    "scope": "*"},
        # Permission (M2)
        {"resource": "permission",       "action": "read",      "scope": "*"},
        # Academic year (M0)
        {"resource": "academic_year",    "action": "read",      "scope": "*"},
        {"resource": "academic_year",    "action": "write",     "scope": "*"},
        # Department — scoped variants (M2)
        {"resource": "department",       "action": "read",      "scope": "*"},
        {"resource": "department",       "action": "read",      "scope": "campus"},
        {"resource": "department",       "action": "read",      "scope": "school"},
        {"resource": "department",       "action": "read",      "scope": "department"},
        {"resource": "department",       "action": "write",     "scope": "department"},
        # Leave request (M2 placeholder)
        {"resource": "leave_request",    "action": "read",      "scope": "department"},
        {"resource": "leave_request",    "action": "approve",   "scope": "department"},
        # Audit log (M2 placeholder)
        {"resource": "audit_log",        "action": "read",      "scope": "*"},
        # ── M3 new triples ────────────────────────────────────────────────────
        # Campus
        {"resource": "campus",                     "action": "read",      "scope": "*"},
        {"resource": "campus",                     "action": "write",     "scope": "*"},
        {"resource": "campus",                     "action": "delete",    "scope": "*"},
        # School
        {"resource": "school",                     "action": "read",      "scope": "*"},
        {"resource": "school",                     "action": "write",     "scope": "*"},
        {"resource": "school",                     "action": "delete",    "scope": "*"},
        # Department write/delete at * scope (M3 adds global write)
        {"resource": "department",                 "action": "write",     "scope": "*"},
        {"resource": "department",                 "action": "delete",    "scope": "*"},
        # SubDepartment
        {"resource": "subdepartment",              "action": "read",      "scope": "*"},
        {"resource": "subdepartment",              "action": "write",     "scope": "*"},
        # Centre
        {"resource": "centre",                     "action": "read",      "scope": "*"},
        {"resource": "centre",                     "action": "write",     "scope": "*"},
        {"resource": "centre",                     "action": "delete",    "scope": "*"},
        # Program
        {"resource": "program",                    "action": "read",      "scope": "*"},
        {"resource": "program",                    "action": "write",     "scope": "*"},
        # Course
        {"resource": "course",                     "action": "read",      "scope": "*"},
        {"resource": "course",                     "action": "write",     "scope": "*"},
        {"resource": "course",                     "action": "delete",    "scope": "*"},
        # University vision/mission (E-001)
        {"resource": "university_vision_mission",  "action": "read",      "scope": "*"},
        {"resource": "university_vision_mission",  "action": "write",     "scope": "*"},
        # Department vision/mission (E-001)
        {"resource": "department_vision_mission",  "action": "read",      "scope": "*"},
        {"resource": "department_vision_mission",  "action": "write",     "scope": "department"},
        # Class timings config
        {"resource": "class_timings_config",       "action": "read",      "scope": "*"},
        {"resource": "class_timings_config",       "action": "configure", "scope": "*"},
        # Working days config
        {"resource": "working_days_config",        "action": "read",      "scope": "*"},
        {"resource": "working_days_config",        "action": "configure", "scope": "*"},
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
        for p in session.exec(
            select(Permission).where(Permission.is_deleted == False)  # noqa: E712
        ).all()
    }

    # ── RolePermissions ───────────────────────────────────────────────────────
    # SYSTEM_ADMIN: all permissions.
    rp_inserted = 0
    for perm in perms.values():
        rp_inserted += _exec_insert(
            session,
            pg_insert(RolePermission)
            .values(role_id=roles["SYSTEM_ADMIN"].id, permission_id=perm.id)
            .on_conflict_do_nothing(),
        )

    # Permissions shared by all read-capable roles (everything M3 added as read:*)
    _PUBLIC_READ = [
        ("campus",                    "read", "*"),
        ("school",                    "read", "*"),
        ("department",                "read", "*"),
        ("department",                "read", "campus"),
        ("department",                "read", "school"),
        ("department",                "read", "department"),
        ("subdepartment",             "read", "*"),
        ("centre",                    "read", "*"),
        ("program",                   "read", "*"),
        ("course",                    "read", "*"),
        ("university_vision_mission", "read", "*"),
        ("department_vision_mission", "read", "*"),
        ("class_timings_config",      "read", "*"),
        ("working_days_config",       "read", "*"),
        ("academic_year",             "read", "*"),
    ]

    _REGISTRAR_SPECIFIC = [
        ("university_vision_mission",  "write",     "*"),
        ("class_timings_config",       "configure", "*"),
        ("working_days_config",        "configure", "*"),
        # department:write:* intentionally NOT included — §9.3: only SYSTEM_ADMIN
        # manages department structure. Registrar has read access via _PUBLIC_READ.
    ]

    _HOD_SPECIFIC = [
        ("department_vision_mission",  "write",     "department"),
        ("leave_request",              "read",      "department"),
        ("leave_request",              "approve",   "department"),
    ]

    _DEAN_SPECIFIC = [
        ("department",                 "read",      "school"),
        ("leave_request",              "read",      "department"),
        ("leave_request",              "approve",   "department"),
    ]

    role_perm_map: dict[str, list[tuple[str, str, str]]] = {
        "REGISTRAR":        _PUBLIC_READ + _REGISTRAR_SPECIFIC,
        "DEPUTY_REGISTRAR": _PUBLIC_READ + _REGISTRAR_SPECIFIC,
        "REGISTRAR_OFFICE": _PUBLIC_READ + _REGISTRAR_SPECIFIC,
        "DEAN":             _PUBLIC_READ + _DEAN_SPECIFIC,
        "DEAN_SCI":         _PUBLIC_READ + _DEAN_SPECIFIC,
        "DEAN_HSS":         _PUBLIC_READ + _DEAN_SPECIFIC,
        "DEAN_LL":          _PUBLIC_READ + _DEAN_SPECIFIC,
        "DEAN_MC":          _PUBLIC_READ + _DEAN_SPECIFIC,
        "HOD":              _PUBLIC_READ + _HOD_SPECIFIC,
        "AHOD":             _PUBLIC_READ + _HOD_SPECIFIC,
        "HOD_OFFICE":       _PUBLIC_READ,
        "STUDENT":          _PUBLIC_READ,
        "BASIC_USER":       _PUBLIC_READ,
    }

    for role_code, perm_keys in role_perm_map.items():
        role = roles[role_code]
        seen: set[tuple[str, str, str]] = set()
        for key in perm_keys:
            if key in seen:
                continue
            seen.add(key)
            if key not in perms:
                continue
            rp_inserted += _exec_insert(
                session,
                pg_insert(RolePermission)
                .values(role_id=role.id, permission_id=perms[key].id)
                .on_conflict_do_nothing(),
            )

    counts["role_permissions"] = rp_inserted

    # ── Cleanup: remove incorrect REGISTRAR-department:write:* assignments ────
    # department:write:* was erroneously assigned to the Registrar family at M3
    # Session 2. Only SYSTEM_ADMIN manages department structure per §9.3.
    # This DELETE is idempotent — safe to re-run if already cleaned up.
    if ("department", "write", "*") in perms:
        dept_write_perm = perms[("department", "write", "*")]
        for role_code in ("REGISTRAR", "DEPUTY_REGISTRAR", "REGISTRAR_OFFICE"):
            if role_code in roles:
                session.execute(
                    sa.delete(RolePermission).where(
                        RolePermission.role_id == roles[role_code].id,
                        RolePermission.permission_id == dept_write_perm.id,
                    )
                )

    # ── Users ─────────────────────────────────────────────────────────────────
    # Read-only seeded fixtures (CLAUDE.md Testing rules):
    #   sys_admin / SysAdmin_Dev1!XZ      — SYSTEM_ADMIN
    #   dean_sci / DeanSci_Dev1!XZ        — DEAN (+ DEAN_SCI added below)
    #   firstlogin_user / FirstLogin_Dev1!XZ — STUDENT, must_change_password=True
    #   inactive_user / Inactive_Dev1!XZ  — STUDENT, is_active=False
    #   student_001 / Student_Dev1!XZ     — STUDENT
    #   registrar_user / Registrar_Dev1!XZ — REGISTRAR  (new at M3)
    #   hod_dmacs / HodDmacs_Dev1!XZ     — HOD scoped to DMACS (new at M3; scoped role added after depts)
    users_data = [
        {
            "email": "sys.admin@sssihl.edu.in",
            "username": "sys_admin",
            "full_name": "System Administrator",
            "role_code": "SYSTEM_ADMIN",
            "plain_password": "SysAdmin_Dev1!XZ",
        },
        {
            "email": "dean.sci@sssihl.edu.in",
            "username": "dean_sci",
            "full_name": "Dean Sciences",
            "role_code": "DEAN",
            "plain_password": "DeanSci_Dev1!XZ",
        },
        {
            "email": "student.001@sssihl.edu.in",
            "username": "student_001",
            "full_name": "Student One",
            "role_code": "STUDENT",
            "plain_password": "Student_Dev1!XZ",
        },
        {
            "email": "inactive.user@sssihl.edu.in",
            "username": "inactive_user",
            "full_name": "Inactive User",
            "role_code": "STUDENT",
            "plain_password": "Inactive_Dev1!XZ",
            "is_active": False,
        },
        {
            "email": "firstlogin.user@sssihl.edu.in",
            "username": "firstlogin_user",
            "full_name": "First Login User",
            "role_code": "STUDENT",
            "plain_password": "FirstLogin_Dev1!XZ",
            "must_change_password": True,
        },
        # M3 demo users
        {
            "email": "registrar@sssihl.edu.in",
            "username": "registrar_user",
            "full_name": "University Registrar",
            "role_code": "REGISTRAR",
            "plain_password": "Registrar_Dev1!XZ",
        },
        {
            "email": "hod.dmacs@sssihl.edu.in",
            "username": "hod_dmacs",
            "full_name": "HoD Mathematics and Computer Science",
            # HOD role is scoped to DMACS — assigned after departments are seeded.
            # Only BASIC_USER is assigned here; see the scoped-roles block below.
            "role_code": "BASIC_USER",
            "plain_password": "HodDmacs_Dev1!XZ",
        },
    ]
    user_inserted = 0
    for u in users_data:
        role_code = u.pop("role_code")
        plain = u.pop("plain_password")
        is_active = u.pop("is_active", True)
        must_change = u.pop("must_change_password", False)
        new_hash = hash_password(plain)

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
        # Every user gets BASIC_USER in addition to their primary role.
        if role_code != "BASIC_USER":
            _exec_insert(
                session,
                pg_insert(UserRole)
                .values(user_id=user.id, role_id=roles["BASIC_USER"].id)
                .on_conflict_do_nothing(),
            )
    counts["users"] = user_inserted

    # ── Holidays ──────────────────────────────────────────────────────────────
    holidays_data = [
        {"holiday_date": date(2025, 10, 2),  "name": "Gandhi Jayanti"},
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

    # ─────────────────────────────────────────────────────────────────────────
    # M3 Organisational Core (§12 M3 gate clause)
    # ─────────────────────────────────────────────────────────────────────────

    # ── Campuses ──────────────────────────────────────────────────────────────
    # Gate: "all four campuses seeded"
    campuses_raw = [
        ("PSN", "Prasanthi Nilayam", "Prasanthi Nilayam, Puttaparthi, Andhra Pradesh 515134"),
        ("BRN", "Brindavan",         "Kadugodi, Whitefield, Bengaluru, Karnataka 560067"),
        ("NDG", "Muddenahalli",      "Muddenahalli, Chikkaballapur, Karnataka 562101"),
        ("ATP", "Anantapur",         "Anantapur, Andhra Pradesh 515001"),
    ]
    campus_inserted = 0
    for code, name, address in campuses_raw:
        campus_inserted += _exec_insert(
            session,
            pg_insert(Campus)
            .values(code=code, name=name, address=address)
            .on_conflict_do_nothing(constraint="uq_campuses_code"),
        )
    counts["campuses"] = campus_inserted
    campuses = {
        c.code: c
        for c in session.exec(
            select(Campus).where(Campus.is_deleted == False)  # noqa: E712
        ).all()
    }

    # ── Schools ───────────────────────────────────────────────────────────────
    # Gate: "four schools seeded"; dean_role_code is a plain string reference (OQ-M3-6)
    schools_raw = [
        ("SCI", "School of Sciences",                        "DEAN_SCI"),
        ("HSS", "School of Humanities and Social Sciences",  "DEAN_HSS"),
        ("LL",  "School of Languages and Literature",        "DEAN_LL"),
        ("MC",  "School of Management and Commerce",         "DEAN_MC"),
    ]
    school_inserted = 0
    for code, name, dean_code in schools_raw:
        school_inserted += _exec_insert(
            session,
            pg_insert(School)
            .values(code=code, name=name, dean_role_code=dean_code)
            .on_conflict_do_nothing(constraint="uq_schools_code"),
        )
    counts["schools"] = school_inserted
    schools = {
        s.code: s
        for s in session.exec(
            select(School).where(School.is_deleted == False)  # noqa: E712
        ).all()
    }

    # ── Departments ───────────────────────────────────────────────────────────
    # Gate: "ten departments seeded"
    # Fields: (code, name, school_code, main_campus_code)
    departments_raw = [
        ("DBIO",  "Biosciences",                    "SCI", "PSN"),
        ("DCHEM", "Chemistry",                      "SCI", "PSN"),
        ("DEDN",  "Education",                      "HSS", "ATP"),
        ("DFNS",  "Food and Nutritional Sciences",  "SCI", "ATP"),
        ("DHSS",  "Humanities and Social Sciences", "HSS", "PSN"),
        ("DLL",   "Languages and Literature",       "LL",  "PSN"),
        ("DMACS", "Mathematics and Computer Science","SCI", "PSN"),
        ("DMC",   "Management and Commerce",        "MC",  "BRN"),
        ("DPHY",  "Physics",                        "SCI", "PSN"),
        ("DPA",   "Performing Arts",                "HSS", "PSN"),
    ]
    dept_inserted = 0
    for code, name, school_code, main_campus_code in departments_raw:
        dept_inserted += _exec_insert(
            session,
            pg_insert(Department)
            .values(
                code=code,
                name=name,
                school_id=schools[school_code].id,
                main_campus_id=campuses[main_campus_code].id,
            )
            .on_conflict_do_nothing(constraint="uq_departments_code"),
        )
    counts["departments"] = dept_inserted
    departments = {
        d.code: d
        for d in session.exec(
            select(Department).where(Department.is_deleted == False)  # noqa: E712
        ).all()
    }

    # ── DepartmentCampus ──────────────────────────────────────────────────────
    # (dept_code, campus_code) — per Appendix A campus mapping
    dept_campus_raw = [
        ("DBIO",  "ATP"), ("DBIO",  "PSN"),
        ("DCHEM", "ATP"), ("DCHEM", "PSN"),
        ("DEDN",  "ATP"),
        ("DFNS",  "ATP"),
        ("DHSS",  "ATP"), ("DHSS",  "BRN"), ("DHSS",  "PSN"),
        ("DLL",   "PSN"), ("DLL",   "BRN"), ("DLL",   "NDG"), ("DLL",   "ATP"),
        ("DMACS", "PSN"), ("DMACS", "BRN"), ("DMACS", "NDG"), ("DMACS", "ATP"),
        ("DMC",   "ATP"), ("DMC",   "BRN"),
        ("DPHY",  "ATP"), ("DPHY",  "PSN"),
        ("DPA",   "PSN"),
    ]
    dc_inserted = 0
    for dept_code, campus_code in dept_campus_raw:
        dc_inserted += _exec_insert(
            session,
            pg_insert(DepartmentCampus)
            .values(
                department_id=departments[dept_code].id,
                campus_id=campuses[campus_code].id,
                has_ahod=False,
            )
            .on_conflict_do_nothing(),
        )
    counts["department_campuses"] = dc_inserted

    # ── SubDepartments ────────────────────────────────────────────────────────
    # Gate: "sub-departments seeded" — 9 rows (5 under DHSS, 4 under DLL)
    subdepts_raw = [
        # Under DHSS
        ("SDPHIL", "Philosophy",        "DHSS"),
        ("SDPSY",  "Psychology",        "DHSS"),
        ("SDHIST", "History",           "DHSS"),
        ("SDPOL",  "Political Science", "DHSS"),
        ("SDECON", "Economics",         "DHSS"),
        # Under DLL
        ("SDENG",  "English",           "DLL"),
        ("SDTEL",  "Telugu",            "DLL"),
        ("SDHIN",  "Hindi",             "DLL"),
        ("SDSAN",  "Sanskrit",          "DLL"),
    ]
    subdept_inserted = 0
    for code, name, parent_code in subdepts_raw:
        subdept_inserted += _exec_insert(
            session,
            pg_insert(SubDepartment)
            .values(
                code=code,
                name=name,
                parent_department_id=departments[parent_code].id,
            )
            .on_conflict_do_nothing(constraint="uq_sub_departments_code"),
        )
    counts["sub_departments"] = subdept_inserted
    subdepts = {
        s.code: s
        for s in session.exec(
            select(SubDepartment).where(SubDepartment.is_deleted == False)  # noqa: E712
        ).all()
    }

    # ── SubDepartmentCampus ───────────────────────────────────────────────────
    # Per Appendix A: 23 join rows
    subdept_campus_raw = [
        # DHSS sub-departments
        ("SDPHIL", "ATP"),
        ("SDPSY",  "ATP"), ("SDPSY",  "PSN"),
        ("SDHIST", "PSN"), ("SDHIST", "ATP"),
        ("SDPOL",  "PSN"), ("SDPOL",  "ATP"),
        ("SDECON", "BRN"), ("SDECON", "ATP"),
        # DLL sub-departments
        ("SDENG",  "PSN"), ("SDENG",  "BRN"), ("SDENG",  "NDG"), ("SDENG",  "ATP"),
        ("SDTEL",  "PSN"), ("SDTEL",  "ATP"),
        ("SDHIN",  "PSN"), ("SDHIN",  "BRN"), ("SDHIN",  "NDG"), ("SDHIN",  "ATP"),
        ("SDSAN",  "PSN"), ("SDSAN",  "BRN"), ("SDSAN",  "NDG"), ("SDSAN",  "ATP"),
    ]
    sdc_inserted = 0
    for subdept_code, campus_code in subdept_campus_raw:
        sdc_inserted += _exec_insert(
            session,
            pg_insert(SubDepartmentCampus)
            .values(
                sub_department_id=subdepts[subdept_code].id,
                campus_id=campuses[campus_code].id,
            )
            .on_conflict_do_nothing(),
        )
    counts["sub_department_campuses"] = sdc_inserted

    # ── Centres of Excellence ─────────────────────────────────────────────────
    # Gate: "centres seeded" — 4 rows
    centres_raw = [
        ("CMB",  "Centre for Mathematical Biology",          "PSN"),
        ("CSSS", "Centre for Sri Sathya Sai Studies",        "PSN"),
        ("CADS", "Centre for Actuarial and Data Sciences",   "BRN"),
        ("CSD",  "Centre for Sustainable Development",       "PSN"),
    ]
    centre_inserted = 0
    for code, name, campus_code in centres_raw:
        centre_inserted += _exec_insert(
            session,
            pg_insert(CentreOfExcellence)
            .values(code=code, name=name, campus_id=campuses[campus_code].id)
            .on_conflict_do_nothing(constraint="uq_centres_of_excellence_code"),
        )
    counts["centres_of_excellence"] = centre_inserted

    # ── Example Program — BSCMATH ─────────────────────────────────────────────
    # Gate: "one program seeded with full PEO/PO/PSO/regulation/scheme/exit-level data"
    # Program belongs to DMACS; degree type unconstrained string at M3 (OQ-M3-10).
    prog_inserted = _exec_insert(
        session,
        pg_insert(Program)
        .values(
            code="BSCMATH",
            name="Bachelor of Science in Mathematics",
            department_id=departments["DMACS"].id,
            degree_type="BSc",
            duration_years=3,
            is_active=True,
        )
        .on_conflict_do_nothing(constraint="uq_programs_code"),
    )
    counts["programs"] = prog_inserted
    bscmath = session.exec(
        select(Program).where(Program.code == "BSCMATH")
    ).one()

    # ── Seed Courses ──────────────────────────────────────────────────────────
    # Three courses linked to BSCMATH / DMACS.  M13 extends with full taxonomy.
    # Refinement 3 fields: code, name, program_id, department_id, credits,
    # lecture, tutorial, practical, evaluation.
    courses_raw = [
        ("MAT101", "Calculus and Differential Equations", 4, 3, 1, 0, "E"),
        ("MAT102", "Linear Algebra and Abstract Algebra", 4, 3, 1, 0, "E"),
        ("PHY101", "Classical Mechanics",                 4, 3, 0, 2, "IE"),
    ]
    course_inserted = 0
    for code, name, credits, lec, tut, prac, evaluation in courses_raw:
        course_inserted += _exec_insert(
            session,
            pg_insert(Course)
            .values(
                code=code,
                name=name,
                program_id=bscmath.id,
                department_id=departments["DMACS"].id,
                credits=credits,
                lecture=lec,
                tutorial=tut,
                practical=prac,
                evaluation=evaluation,
                is_active=True,
            )
            .on_conflict_do_nothing(constraint="uq_courses_code"),
        )
    counts["courses"] = course_inserted
    courses = {
        c.code: c
        for c in session.exec(
            select(Course).where(Course.is_deleted == False)  # noqa: E712
        ).all()
    }

    # ── ProgramOutcomes: PEOs, POs, PSOs ──────────────────────────────────────
    outcomes_raw = [
        # (outcome_type, code, display_order, description)
        ("PEO", "PEO1", 1,
         "Graduates will apply mathematical foundations to solve complex "
         "scientific and engineering problems."),
        ("PEO", "PEO2", 2,
         "Graduates will contribute to research, industry, or higher education "
         "through sound mathematical reasoning."),
        ("PEO", "PEO3", 3,
         "Graduates will demonstrate professional integrity, teamwork, and "
         "commitment to lifelong learning."),
        ("PO",  "PO1",  1,
         "Apply knowledge of mathematics, statistics, and computing to solve problems."),
        ("PO",  "PO2",  2,
         "Design algorithms and mathematical models for real-world phenomena."),
        ("PO",  "PO3",  3,
         "Analyse and interpret quantitative data using appropriate mathematical tools."),
        ("PO",  "PO4",  4,
         "Formulate and prove mathematical propositions with rigour."),
        ("PO",  "PO5",  5,
         "Communicate mathematical ideas clearly in written and oral form."),
        ("PO",  "PO6",  6,
         "Apply ethical reasoning in professional and academic contexts."),
        ("PSO", "PSO1", 1,
         "Demonstrate proficiency in real analysis, abstract algebra, and topology."),
        ("PSO", "PSO2", 2,
         "Apply numerical methods and computational tools to mathematical problems."),
        ("PSO", "PSO3", 3,
         "Model and solve optimisation problems using linear and nonlinear techniques."),
    ]
    outcome_inserted = 0
    for outcome_type, code, display_order, description in outcomes_raw:
        outcome_inserted += _exec_insert(
            session,
            pg_insert(ProgramOutcome)
            .values(
                program_id=bscmath.id,
                outcome_type=outcome_type,
                code=code,
                description=description,
                display_order=display_order,
            )
            .on_conflict_do_nothing(
                constraint="uq_program_outcomes_program_type_code"
            ),
        )
    counts["program_outcomes"] = outcome_inserted

    # ── ProgramRegulation ─────────────────────────────────────────────────────
    reg_inserted = _exec_insert(
        session,
        pg_insert(ProgramRegulation)
        .values(
            program_id=bscmath.id,
            code="R2021",
            effective_from_year=2021,
            description=(
                "Regulation 2021 — Choice Based Credit System aligned "
                "with NEP 2020 guidelines."
            ),
        )
        .on_conflict_do_nothing(constraint="uq_program_regulations_program_code"),
    )
    counts["program_regulations"] = reg_inserted
    regulation = session.exec(
        select(ProgramRegulation).where(
            ProgramRegulation.program_id == bscmath.id,
            ProgramRegulation.code == "R2021",
        )
    ).one()

    # ── ProgramScheme — Semester 1 ────────────────────────────────────────────
    scheme_inserted = _exec_insert(
        session,
        pg_insert(ProgramScheme)
        .values(
            program_id=bscmath.id,
            regulation_id=regulation.id,
            semester=1,
            total_credits=12,
        )
        .on_conflict_do_nothing(constraint="uq_program_schemes_program_reg_sem"),
    )
    counts["program_schemes"] = scheme_inserted
    scheme = session.exec(
        select(ProgramScheme).where(
            ProgramScheme.program_id == bscmath.id,
            ProgramScheme.regulation_id == regulation.id,
            ProgramScheme.semester == 1,
        )
    ).one()

    # ── ProgramSchemeCourse ───────────────────────────────────────────────────
    psc_inserted = 0
    for course_code in ("MAT101", "MAT102", "PHY101"):
        psc_inserted += _exec_insert(
            session,
            pg_insert(ProgramSchemeCourse)
            .values(scheme_id=scheme.id, course_id=courses[course_code].id)
            .on_conflict_do_nothing(),
        )
    counts["program_scheme_courses"] = psc_inserted

    # ── ProgramSpecialisation ─────────────────────────────────────────────────
    spec_inserted = _exec_insert(
        session,
        pg_insert(ProgramSpecialisation)
        .values(
            program_id=bscmath.id,
            code="APPMATH",
            name="Applied Mathematics",
            description=(
                "Specialisation in numerical analysis, optimisation, "
                "and mathematical modelling."
            ),
        )
        .on_conflict_do_nothing(constraint="uq_program_specialisations_program_code"),
    )
    counts["program_specialisations"] = spec_inserted

    # ── ProgramExitLevel ──────────────────────────────────────────────────────
    exit_levels_raw = [
        ("UG Certificate",    40,  "Exit after completing UG Certificate requirements."),
        ("UG Diploma",        80,  "Exit after completing UG Diploma requirements."),
        ("BSc Mathematics",  120,  "Full three-year BSc programme completion."),
    ]
    el_inserted = 0
    for level_name, required_credits, description in exit_levels_raw:
        el_inserted += _exec_insert(
            session,
            pg_insert(ProgramExitLevel)
            .values(
                program_id=bscmath.id,
                level_name=level_name,
                required_credits=required_credits,
                description=description,
            )
            .on_conflict_do_nothing(
                constraint="uq_program_exit_levels_program_level"
            ),
        )
    counts["program_exit_levels"] = el_inserted

    # ── University Vision/Mission (singleton, E-001) ───────────────────────────
    # Synthetic placeholder text — real text from sponsor at a later milestone.
    # Application-level singleton enforcement (OQ-M3-9): insert if none exists.
    _UNIV_VISION = (
        "To awaken humanity to the divinity within through excellence "
        "in education, inquiry, and character formation."
    )
    uvm = session.exec(
        select(UniversityVisionMission).where(
            UniversityVisionMission.is_deleted == False  # noqa: E712
        )
    ).first()
    if uvm is None:
        session.execute(
            pg_insert(UniversityVisionMission).values(vision=_UNIV_VISION)
        )
        session.flush()
        uvm = session.exec(select(UniversityVisionMission)).first()
        counts["university_vision_missions"] = 1
    else:
        counts["university_vision_missions"] = 0

    assert uvm is not None
    mission_count = session.exec(
        select(sa.func.count(UniversityMission.id)).where(
            UniversityMission.university_vision_id == uvm.id,
            UniversityMission.is_deleted == False,  # noqa: E712
        )
    ).one()
    if mission_count == 0:
        for i, statement in enumerate(
            [
                "To provide value-based education that integrates academic excellence "
                "with spiritual and ethical formation.",
                "To foster a community of scholars committed to the pursuit of truth, "
                "service, and sustainable development.",
                "To serve as a model of educational innovation that bridges ancient "
                "wisdom and modern knowledge.",
            ],
            start=1,
        ):
            session.execute(
                pg_insert(UniversityMission).values(
                    university_vision_id=uvm.id,
                    statement=statement,
                    display_order=i,
                )
            )
        counts["university_missions"] = 3
    else:
        counts["university_missions"] = 0

    # ── DMACS Vision/Mission (E-001) ───────────────────────────────────────────
    _DMACS_VISION = (
        "To nurture mathematical thinkers who bring rigour, creativity, "
        "and purpose to the service of society."
    )
    dvm = session.exec(
        select(DepartmentVisionMission).where(
            DepartmentVisionMission.department_id == departments["DMACS"].id,
            DepartmentVisionMission.is_deleted == False,  # noqa: E712
        )
    ).first()
    if dvm is None:
        session.execute(
            pg_insert(DepartmentVisionMission).values(
                department_id=departments["DMACS"].id,
                vision=_DMACS_VISION,
            )
        )
        session.flush()
        dvm = session.exec(
            select(DepartmentVisionMission).where(
                DepartmentVisionMission.department_id == departments["DMACS"].id
            )
        ).first()
        counts["department_vision_missions"] = 1
    else:
        counts["department_vision_missions"] = 0

    assert dvm is not None
    dept_mission_count = session.exec(
        select(sa.func.count(DepartmentMission.id)).where(
            DepartmentMission.department_vision_id == dvm.id,
            DepartmentMission.is_deleted == False,  # noqa: E712
        )
    ).one()
    if dept_mission_count == 0:
        for i, statement in enumerate(
            [
                "To provide deep training in core mathematical disciplines "
                "and their interdisciplinary applications.",
                "To cultivate a culture of collaborative inquiry, integrity, "
                "and lifelong mathematical learning.",
            ],
            start=1,
        ):
            session.execute(
                pg_insert(DepartmentMission).values(
                    department_vision_id=dvm.id,
                    statement=statement,
                    display_order=i,
                )
            )
        counts["department_missions"] = 2
    else:
        counts["department_missions"] = 0

    # ── ClassTimingsConfig (singleton) ───────────────────────────────────────
    # Default: 8 periods × 50 min, starting 08:00, lunch break after period 4.
    ctc = session.exec(
        select(ClassTimingsConfig).where(ClassTimingsConfig.is_deleted == False)  # noqa: E712
    ).first()
    if ctc is None:
        session.execute(
            pg_insert(ClassTimingsConfig).values(
                periods_per_day=8,
                period_duration_minutes=50,
                first_period_start="08:00",
                break_after_period=4,
                break_duration_minutes=45,
            )
        )
        counts["class_timings_configs"] = 1
    else:
        counts["class_timings_configs"] = 0

    # ── WorkingDaysConfig (singleton) ─────────────────────────────────────────
    wdc = session.exec(
        select(WorkingDaysConfig).where(WorkingDaysConfig.is_deleted == False)  # noqa: E712
    ).first()
    if wdc is None:
        session.execute(pg_insert(WorkingDaysConfig).values(days_per_week=5))
        counts["working_days_configs"] = 1
    else:
        counts["working_days_configs"] = 0

    # ── Scoped role assignments (requires departments to be seeded first) ─────
    # dean_sci → DEAN_SCI role (school-level, unscoped)
    dean_sci_user = session.exec(
        select(User).where(User.username == "dean_sci")
    ).first()
    if dean_sci_user:
        _exec_insert(
            session,
            pg_insert(UserRole)
            .values(user_id=dean_sci_user.id, role_id=roles["DEAN_SCI"].id)
            .on_conflict_do_nothing(),
        )

    # hod_dmacs → HOD role scoped to DMACS department
    hod_dmacs_user = session.exec(
        select(User).where(User.username == "hod_dmacs")
    ).first()
    if hod_dmacs_user and "DMACS" in departments:
        session.execute(
            pg_insert(UserRole)
            .values(
                user_id=hod_dmacs_user.id,
                role_id=roles["HOD"].id,
                scope_type="department",
                scope_id=departments["DMACS"].id,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "role_id"],
                set_={
                    "scope_type": "department",
                    "scope_id": departments["DMACS"].id,
                },
            )
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
