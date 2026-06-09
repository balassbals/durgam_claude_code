"""20-employee synthetic fixture for M8 leave-rules acceptance tests.

NOT loaded by scripts/seed.py — opt-in from tests only.
Faker(seed=42) for determinism. All usernames prefixed 'm8test_'.
Use create_leave_test_employees() + delete_leave_test_employees() in try/finally.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from faker import Faker
from sqlalchemy import text
from sqlmodel import Session, select

from durgam.models.identity import Role, User, UserRole
from durgam.services.password import hash_password

fake = Faker()
fake.seed_instance(42)

_TODAY = date(2026, 6, 8)  # frozen reference date for reproducibility
_1Y_AGO = _TODAY - timedelta(days=400)   # safely > 1 year
_2Y_AGO = _TODAY - timedelta(days=750)   # safely > 2 years
_5Y_AGO = _TODAY - timedelta(days=1920)  # safely > 5 years
_LAST_MONTH = _TODAY - timedelta(days=30)  # < 1 year — ML-ineligible

_PASSWORD_HASH = hash_password("M8Test_Dev1!XZ")


def _make_user(
    username_suffix: str,
    gender: str,
    joined_on: date | None,
    employee_type: str,
    full_name: str,
) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=f"m8test_{username_suffix}",
        email=f"m8test_{username_suffix}@test.local",
        full_name=full_name,
        password_hash=_PASSWORD_HASH,
        gender=gender,
        joined_on=joined_on,
        employee_type=employee_type,
        is_active=True,
        must_change_password=False,
        created_at=now,
        updated_at=now,
    )


def _assign_role(session: Session, user_id: UUID, role_code: str) -> None:
    role = session.exec(select(Role).where(Role.code == role_code)).first()
    if role is None:
        return  # role not seeded — skip (tests run against seeded DB)
    ur = UserRole(user_id=user_id, role_id=role.id)
    session.add(ur)
    session.flush()


def create_leave_test_employees(
    session: Session, actor_id: UUID
) -> dict[str, User]:
    """Create 20 representative employees covering every §11 leave-rules scenario.

    Returns a dict keyed by descriptor string. All users have username prefix
    'm8test_' for grep-clean teardown.

    Requires the seed to have been applied (roles must exist).
    """
    specs: list[tuple[str, str, date | None, str, str, list[str]]] = [
        # (descriptor, gender, joined_on, employee_type, full_name, extra_roles)
        ("vac_teach_m_est",     "M", _5Y_AGO,    "regular_teaching",       "Test Vacation Teacher M",        ["FACULTY"]),
        ("vac_teach_f_est",     "F", _2Y_AGO,    "regular_teaching",       "Test Vacation Teacher F Est",    ["FACULTY"]),
        ("vac_teach_f_new",     "F", _LAST_MONTH, "regular_teaching",      "Test Vacation Teacher F New",    ["FACULTY"]),
        ("vac_teach_director",  "M", _5Y_AGO,    "regular_teaching",       "Test Director",                  ["FACULTY", "DIRECTOR"]),
        ("vac_teach_professor", "M", _5Y_AGO,    "regular_teaching",       "Test Professor",                 ["FACULTY", "PROFESSOR"]),
        ("vac_teach_assoc_prof","M", _5Y_AGO,    "regular_teaching",       "Test Assoc Professor",           ["FACULTY", "ASSOC_PROFESSOR"]),
        ("vac_teach_hod",       "M", _5Y_AGO,    "regular_teaching",       "Test HoD",                       ["FACULTY", "HOD"]),
        ("non_vac_admin_m",     "M", _5Y_AGO,    "regular_non_teaching",   "Test Admin M",                   ["REGISTRAR_OFFICE"]),
        ("non_vac_admin_f_el",  "F", _2Y_AGO,    "regular_non_teaching",   "Test Admin F Eligible",          ["FACULTY"]),
        ("non_vac_admin_fin",   "M", _5Y_AGO,    "regular_non_teaching",   "Test Finance Officer",           ["FINANCE_OFFICER"]),
        ("non_vac_admin_coe",   "M", _5Y_AGO,    "regular_non_teaching",   "Test Controller of Exams",       ["CONTROLLER_OF_EXAMINATIONS"]),
        ("non_vac_admin_vco",   "M", _5Y_AGO,    "regular_non_teaching",   "Test VC Office",                 ["VC_OFFICE"]),
        ("hon_teach_m",         "M", _5Y_AGO,    "honorary_teaching",      "Test Honorary Teacher",          ["FACULTY"]),
        ("hon_non_teach_m",     "M", _5Y_AGO,    "honorary_non_teaching",  "Test Honorary Non-Teacher",      []),
        ("super_teach_m",       "M", _5Y_AGO,    "superannuated_teaching", "Test Superannuated Teacher",     ["FACULTY"]),
        ("super_non_teach_m",   "M", _5Y_AGO,    "superannuated_non_teaching","Test Superannuated Non-Teacher",[]),
        ("visiting_fellow_m",   "M", _1Y_AGO,    "visiting_fellow",        "Test Visiting Fellow",           []),
        ("sl_eligible",         "M", _5Y_AGO,    "regular_teaching",       "Test SL Eligible Teacher",       ["FACULTY"]),
        ("sl_ineligible_new",   "M", date(2024, 6, 1), "regular_teaching", "Test SL Ineligible New",        ["FACULTY"]),
        ("sl_ineligible_admin", "M", _5Y_AGO,    "regular_non_teaching",   "Test SL Ineligible Admin",       []),
    ]

    descriptors = [
        "vacation_teaching_male_established",
        "vacation_teaching_female_established",
        "vacation_teaching_female_new",
        "vacation_teaching_director",
        "vacation_teaching_professor",
        "vacation_teaching_assoc_professor",
        "vacation_teaching_hod",
        "non_vacation_admin_male",
        "non_vacation_admin_female_eligible",
        "non_vacation_admin_finance",
        "non_vacation_admin_coe",
        "non_vacation_admin_vc_office",
        "honorary_teaching_male",
        "honorary_non_teaching_male",
        "superannuated_teaching_male",
        "superannuated_non_teaching_male",
        "visiting_fellow_male",
        "sl_eligible_teacher",
        "sl_ineligible_teacher_new",
        "study_leave_ineligible_admin",
    ]

    result: dict[str, User] = {}
    for descriptor, (suffix, gender, joined_on, emp_type, full_name, roles) in zip(
        descriptors, specs
    ):
        user = _make_user(suffix, gender, joined_on, emp_type, full_name)
        session.add(user)
        session.flush()
        # Assign BASIC_USER to all
        _assign_role(session, user.id, "BASIC_USER")
        # Assign extra roles
        for role_code in roles:
            _assign_role(session, user.id, role_code)
        result[descriptor] = user

    session.flush()
    return result


def delete_leave_test_employees(
    session: Session, user_ids: list[UUID]
) -> None:
    """Hard-delete test users and their associated leave/balance rows.

    Idempotent — safe to call even if rows are already gone.
    """
    from durgam.models.leave import LeaveBalance, LeaveRequest

    errors: list[tuple] = []
    for uid in user_ids:
        try:
            # Remove leave data first (FK references users)
            for balance in session.exec(
                select(LeaveBalance).where(LeaveBalance.employee_user_id == uid)
            ).all():
                session.delete(balance)
            for req in session.exec(
                select(LeaveRequest).where(LeaveRequest.requestor_user_id == uid)
            ).all():
                session.delete(req)
            # Remove user roles
            for ur in session.exec(
                select(UserRole).where(UserRole.user_id == uid)
            ).all():
                session.delete(ur)
            # Remove user
            user = session.get(User, uid)
            if user is not None:
                session.delete(user)
            session.flush()
        except Exception as exc:  # noqa: BLE001 — tests should surface cleanup failures
            errors.append((uid, exc))
    if errors:
        raise RuntimeError(f"Failed to delete {len(errors)} test users: {errors!r}")
