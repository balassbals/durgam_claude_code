"""Integration tests for NRF contract-term expansion (M10 Phase 9A).

Verifies renewal_count + latest_contract_file_id persist, and that renew()
increments + extends against real PostgreSQL via db_session.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.campus import Campus
from durgam.models.department import Department
from durgam.models.school import School
from durgam.repositories.non_regular_faculty import NonRegularFacultyRepository
from durgam.services.non_regular_faculty import (
    NonRegularFacultyService,
    RenewalDateInvalidError,
)


def _dept(session: Session) -> Department:
    u = uuid4().hex[:6]
    campus = Campus(code=f"RC{u}", name="RC")
    session.add(campus)
    session.flush()
    school = School(code=f"RS{u}", name="RS")
    session.add(school)
    session.flush()
    dept = Department(code=f"RDP{u}", name="RD", school_id=school.id, main_campus_id=campus.id)
    session.add(dept)
    session.flush()
    return dept


def _svc(session: Session) -> NonRegularFacultyService:
    return NonRegularFacultyService(repo=NonRegularFacultyRepository(session))


class TestNrfContractTermIntegration:
    def test_create_persists_renewal_count(self, db_session: Session) -> None:
        dept = _dept(db_session)
        svc = _svc(db_session)
        rec = svc.create(
            department_id=dept.id, name="Dr. R", designation="Prof",
            organization="Org", expertise="X",
            available_from=date(2025, 1, 1), available_to=date(2025, 12, 31),
            actor_id=uuid4(), renewal_count=0,
        )
        fetched = NonRegularFacultyRepository(db_session).get_by_id(rec.id)
        assert fetched is not None
        assert fetched.renewal_count == 0
        assert fetched.latest_contract_file_id is None

    def test_renew_persists_increment_and_extension(self, db_session: Session) -> None:
        dept = _dept(db_session)
        svc = _svc(db_session)
        rec = svc.create(
            department_id=dept.id, name="Dr. S", designation="Prof",
            organization="Org", expertise="X",
            available_from=date(2025, 1, 1), available_to=date(2025, 12, 31),
            actor_id=uuid4(),
        )
        svc.renew(rec.id, new_end_date=date(2026, 12, 31), actor_id=uuid4())
        fetched = NonRegularFacultyRepository(db_session).get_by_id(rec.id)
        assert fetched.renewal_count == 1
        assert fetched.available_to == date(2026, 12, 31)

    def test_renew_rejects_earlier_end_date(self, db_session: Session) -> None:
        dept = _dept(db_session)
        svc = _svc(db_session)
        rec = svc.create(
            department_id=dept.id, name="Dr. T", designation="Prof",
            organization="Org", expertise="X",
            available_from=date(2025, 1, 1), available_to=date(2025, 12, 31),
            actor_id=uuid4(),
        )
        with pytest.raises(RenewalDateInvalidError):
            svc.renew(rec.id, new_end_date=date(2025, 6, 30), actor_id=uuid4())
