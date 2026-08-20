"""Integration tests for FacultyRequestRepository (M10 Phase 5A).

Uses db_session (function-scoped, rolls back). All FK dependencies created
synthetically within each test transaction — no seeded_session access.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.faculty_request import (
    FACULTY_REQUEST_TYPES,
    REQUEST_TYPE_INVITED_TALK,
    REQUEST_TYPE_NOC,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    FacultyRequest,
)
from durgam.models.identity import User
from durgam.models.school import School
from durgam.repositories.faculty_request import FacultyRequestRepository


# ── Synthetic FK chain helpers ────────────────────────────────────────────────


def _make_faculty(session: Session) -> Faculty:
    """Create Campus → School → Designation → Department → User → Faculty chain."""
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)

    campus = Campus(code=f"TC{uid[:4]}", name=f"Test Campus {uid}")
    session.add(campus)
    session.flush()

    school = School(code=f"TS{uid[:4]}", name=f"Test School {uid}")
    session.add(school)
    session.flush()

    desig = Designation(code=f"TD{uid[:4]}", name=f"Test Designation {uid}", rank=99)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"TDE{uid[:3]}",
        name=f"Test Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()

    user = User(
        username=f"tuser_{uid}",
        email=f"tuser_{uid}@dev.local",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()

    faculty = Faculty(
        user_id=user.id,
        employee_id=f"EMP-{uid}",
        title="Dr",
        first_name="Test",
        last_name="Faculty",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2020, 1, 1),
        phone="9000000000",
        emergency_contact_name="EC",
        emergency_contact_relation="Spouse",
        emergency_contact_phone="9000000001",
        is_phd=False,
        created_at=now,
        updated_at=now,
    )
    session.add(faculty)
    session.flush()
    return faculty


# ── Tests ────────────────────────────────────────────────────────────────────


class TestFacultyRequestRepository:
    def test_create_and_get(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        repo = FacultyRequestRepository(db_session)
        actor = uuid4()

        created = repo.create(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload={"reason": "conference"},
            actor_id=actor,
        )

        assert created.id is not None
        assert created.faculty_id == faculty.id
        assert created.request_type == REQUEST_TYPE_NOC
        assert created.status == STATUS_DRAFT
        assert created.payload_json == {"reason": "conference"}
        assert created.created_by == actor
        assert not created.is_deleted

        fetched = repo.get(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_list_by_faculty_orders_desc(self, db_session: Session) -> None:
        """Multiple requests for same faculty — returned newest-first."""
        faculty = _make_faculty(db_session)
        repo = FacultyRequestRepository(db_session)
        actor = uuid4()

        r1 = repo.create(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=actor,
        )
        # Small sleep to ensure distinct created_at values
        time.sleep(0.01)
        r2 = repo.create(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_INVITED_TALK,
            payload=None,
            actor_id=actor,
        )

        results = repo.list_by_faculty(faculty.id)
        assert len(results) == 2
        # Newest first (r2 created after r1)
        assert results[0].id == r2.id
        assert results[1].id == r1.id

    def test_list_by_faculty_filters_status(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        repo = FacultyRequestRepository(db_session)
        actor = uuid4()

        draft_req = repo.create(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=actor,
        )
        # Manually advance one to submitted
        submitted_req = repo.create(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_INVITED_TALK,
            payload=None,
            actor_id=actor,
        )
        repo.update(submitted_req.id, {"status": STATUS_SUBMITTED}, actor)

        draft_list = repo.list_by_faculty(faculty.id, status=STATUS_DRAFT)
        assert len(draft_list) == 1
        assert draft_list[0].id == draft_req.id

    def test_list_by_type_filters(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        repo = FacultyRequestRepository(db_session)
        actor = uuid4()

        repo.create(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=actor,
        )
        repo.create(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=actor,
        )
        repo.create(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_INVITED_TALK,
            payload=None,
            actor_id=actor,
        )

        noc_results = repo.list_by_type(REQUEST_TYPE_NOC)
        assert len(noc_results) == 2
        assert all(r.request_type == REQUEST_TYPE_NOC for r in noc_results)

    def test_soft_delete_excludes_from_list(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        repo = FacultyRequestRepository(db_session)
        actor = uuid4()

        req = repo.create(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=actor,
        )
        repo.soft_delete(req.id, actor)

        assert repo.get(req.id) is None
        assert repo.list_by_faculty(faculty.id) == []

    def test_update_mutates_fields(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        repo = FacultyRequestRepository(db_session)
        actor = uuid4()

        req = repo.create(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload={"v": 1},
            actor_id=actor,
        )
        original_updated_at = req.updated_at

        new_actor = uuid4()
        updated = repo.update(req.id, {"payload_json": {"v": 2}}, new_actor)

        assert updated.payload_json == {"v": 2}
        assert updated.updated_by == new_actor
        assert updated.updated_at >= original_updated_at

    def test_fk_to_nonexistent_faculty_raises_integrity(
        self, db_session: Session
    ) -> None:
        repo = FacultyRequestRepository(db_session)
        with pytest.raises(IntegrityError):
            repo.create(
                faculty_id=uuid4(),  # random UUID — no Faculty row exists
                request_type=REQUEST_TYPE_NOC,
                payload=None,
                actor_id=uuid4(),
            )
            db_session.flush()

    def test_check_constraint_rejects_invalid_status(
        self, db_session: Session
    ) -> None:
        faculty = _make_faculty(db_session)
        repo = FacultyRequestRepository(db_session)
        actor = uuid4()

        req = repo.create(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=actor,
        )
        with pytest.raises(IntegrityError):
            repo.update(req.id, {"status": "garbage_status"}, actor)
            db_session.flush()
