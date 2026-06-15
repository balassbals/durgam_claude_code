"""Integration tests for FacultyRequestService (M10 Phase 5A).

Uses db_session (function-scoped, rolls back) with synthetic Faculty chain.
No seeded_session access.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.faculty_request import (
    REQUEST_TYPE_NOC,
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
)
from durgam.models.identity import User
from durgam.models.school import School
from durgam.services.faculty_request import (
    FacultyRequestNotFoundError,
    FacultyRequestService,
    InvalidRequestStatusTransitionError,
    UnknownRequestTypeError,
)


# ── Synthetic Faculty helper (same pattern as repo tests) ─────────────────────


def _make_faculty(session: Session) -> Faculty:
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)

    campus = Campus(code=f"SC{uid[:4]}", name=f"Svc Campus {uid}")
    session.add(campus)
    session.flush()

    school = School(code=f"SS{uid[:4]}", name=f"Svc School {uid}")
    session.add(school)
    session.flush()

    desig = Designation(code=f"SD{uid[:4]}", name=f"Svc Desig {uid}", rank=99)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"SDT{uid[:3]}",
        name=f"Svc Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()

    user = User(
        username=f"svcu_{uid}",
        email=f"svcu_{uid}@dev.local",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()

    faculty = Faculty(
        user_id=user.id,
        employee_id=f"SEMP-{uid}",
        title="Dr",
        first_name="Svc",
        last_name="Faculty",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2021, 6, 1),
        phone="9000000010",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9000000011",
        is_phd=False,
        created_at=now,
        updated_at=now,
    )
    session.add(faculty)
    session.flush()
    return faculty


# ── Tests ────────────────────────────────────────────────────────────────────


class TestFacultyRequestService:
    def test_create_request_happy_path(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)

        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload={"conference": "ICSE 2027"},
            actor_id=uuid4(),
        )

        assert req.id is not None
        assert req.faculty_id == faculty.id
        assert req.request_type == REQUEST_TYPE_NOC
        assert req.status == STATUS_DRAFT
        assert req.payload_json == {"conference": "ICSE 2027"}
        assert not req.is_deleted

    def test_create_rejects_unknown_type(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)

        with pytest.raises(UnknownRequestTypeError, match="not_a_type"):
            svc.create_request(
                faculty_id=faculty.id,
                request_type="not_a_type",
                payload=None,
                actor_id=uuid4(),
            )

    def test_create_rejects_nonexistent_faculty(self, db_session: Session) -> None:
        svc = FacultyRequestService(db_session)

        with pytest.raises(ValueError, match="not found"):
            svc.create_request(
                faculty_id=uuid4(),  # no Faculty row in DB
                request_type=REQUEST_TYPE_NOC,
                payload=None,
                actor_id=uuid4(),
            )

    def test_update_payload_only_on_draft(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        actor = uuid4()

        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload={"v": 1},
            actor_id=actor,
        )

        # Allowed on draft
        updated = svc.update_payload(req.id, {"v": 2}, actor)
        assert updated.payload_json == {"v": 2}

        # Manually advance status to submitted (bypassing service)
        from durgam.repositories.faculty_request import FacultyRequestRepository
        repo = FacultyRequestRepository(db_session)
        repo.update(req.id, {"status": STATUS_SUBMITTED}, actor)

        # Now update_payload must be refused
        with pytest.raises(InvalidRequestStatusTransitionError, match=STATUS_SUBMITTED):
            svc.update_payload(req.id, {"v": 3}, actor)

    def test_soft_delete_at_any_status(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        actor = uuid4()

        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=actor,
        )

        # Soft-delete while in draft — allowed
        svc.soft_delete_request(req.id, actor)

        with pytest.raises(FacultyRequestNotFoundError):
            svc.get_request(req.id)
