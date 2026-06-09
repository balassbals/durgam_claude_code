"""M8 Phase 4: integration tests for leave seed data and 20-employee fixture."""
from __future__ import annotations

import pytest
from sqlmodel import select

from durgam.models.crosscutting import ApprovalProcess
from durgam.models.identity import Role, User
from durgam.models.leave import LeaveSanctionAuthorityRule

_YAML_RULE_COUNT = 73  # 14 CL + 1 SCL + 56 EL/HPL/CML/ML + 2 EOL/SL


def _count(session, model) -> int:
    return len(
        session.exec(
            select(model).where(model.is_deleted == False)  # noqa: E712
        ).all()
    )


class TestLeaveSeed:
    def test_seed_creates_leave_approval_process(self, seeded_session) -> None:
        """LEAVE_APPROVAL process exists with the expected channel_role_codes union."""
        proc = seeded_session.exec(
            select(ApprovalProcess).where(ApprovalProcess.code == "LEAVE_APPROVAL")
        ).first()
        assert proc is not None, "LEAVE_APPROVAL ApprovalProcess must be seeded"
        assert proc.is_finance is False
        channel = proc.channel_role_codes or []
        # Union of all sanctioner roles in the leave matrix
        expected_roles = {
            "DIRECTOR", "VC", "REGISTRAR", "FINANCE_OFFICER", "CONTROLLER_OF_EXAMINATIONS",
        }
        assert expected_roles == set(channel), (
            f"channel_role_codes mismatch; expected {sorted(expected_roles)}, "
            f"got {sorted(channel)}"
        )

    def test_seed_creates_all_matrix_rules(self, seeded_session) -> None:
        """LeaveSanctionAuthorityRule count equals the YAML rule count after seeding."""
        count = _count(seeded_session, LeaveSanctionAuthorityRule)
        assert count == _YAML_RULE_COUNT, (
            f"Expected {_YAML_RULE_COUNT} leave sanction rules; found {count}"
        )

    def test_seed_creates_phase4_roles(self, seeded_session) -> None:
        """PROFESSOR and ASSOC_PROFESSOR roles exist after seeding."""
        for code in ("PROFESSOR", "ASSOC_PROFESSOR"):
            role = seeded_session.exec(
                select(Role).where(Role.code == code, Role.is_deleted == False)  # noqa: E712
            ).first()
            assert role is not None, f"Role {code!r} must be seeded in Phase 4"

    def test_seed_professor_level(self, seeded_session) -> None:
        """PROFESSOR is level 75; ASSOC_PROFESSOR is level 73."""
        prof = seeded_session.exec(
            select(Role).where(Role.code == "PROFESSOR")
        ).first()
        assoc = seeded_session.exec(
            select(Role).where(Role.code == "ASSOC_PROFESSOR")
        ).first()
        assert prof.level == 75
        assert assoc.level == 73

    # NOTE: Full-seed idempotency (scripts/seed.py end-to-end) is verified manually
    # by Bala during the milestone gate ritual, not in pytest, because running seed()
    # against the shared test DB commits permanently and bypasses rollback. Loader-
    # level idempotency (the actual code path that matters here) is covered by
    # test_load_from_yaml_idempotent in tests/unit/test_leave_sanction_rule.py.


class TestLeave20EmployeeFixture:
    def test_fixture_creates_20_employees_and_teardown(
        self, seeded_session
    ) -> None:
        """create_leave_test_employees creates 20 rows; delete removes them all."""
        from tests.fixtures.leave_20_employees import (
            create_leave_test_employees,
            delete_leave_test_employees,
        )

        sys_admin = seeded_session.exec(
            select(User).where(User.username == "sys_admin")
        ).one()

        employees = create_leave_test_employees(seeded_session, actor_id=sys_admin.id)
        seeded_session.flush()
        user_ids = [u.id for u in employees.values()]
        try:
            assert len(employees) == 20
            assert all(u.username.startswith("m8test_") for u in employees.values())

            # Spot-check key employees
            assert employees["vacation_teaching_female_new"].gender == "F"
            assert employees["sl_eligible_teacher"].employee_type == "regular_teaching"
            assert employees["study_leave_ineligible_admin"].employee_type == "regular_non_teaching"
        finally:
            delete_leave_test_employees(seeded_session, user_ids)
            seeded_session.flush()

        # Verify all are gone (only runs if assertions above passed)
        for uid in user_ids:
            user = seeded_session.get(User, uid)
            assert user is None, f"User {uid} should be deleted after teardown"

    def test_fixture_ml_eligible_employee_present(self, seeded_session) -> None:
        """The fixture includes a female employee with >= 1 year service (ML-eligible)."""
        from datetime import date, timedelta

        from tests.fixtures.leave_20_employees import (
            create_leave_test_employees,
            delete_leave_test_employees,
        )

        sys_admin = seeded_session.exec(
            select(User).where(User.username == "sys_admin")
        ).one()

        employees = create_leave_test_employees(seeded_session, actor_id=sys_admin.id)
        seeded_session.flush()

        eligible = employees["vacation_teaching_female_established"]
        assert eligible.gender == "F"
        assert eligible.joined_on is not None
        service_days = (date(2026, 6, 8) - eligible.joined_on).days
        assert service_days >= 365, "ML-eligible female must have >= 1 year service"

        delete_leave_test_employees(seeded_session, [u.id for u in employees.values()])
