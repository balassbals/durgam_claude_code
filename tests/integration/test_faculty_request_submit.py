"""Integration tests for FacultyRequestService.submit_for_approval (M10 Phase 5B).

Uses db_session (function-scoped, rolls back) with synthetic Faculty chains.
Tests that need the faculty_noc process look it up from db_session (seeded_db_engine
runs first in the smoke-check invocation, so the seeded process is visible); they skip
gracefully when run standalone without test_faculty_noc_seed.py.
Tests for requestor-pick mode use a synthetic faculty_address_change process (not seeded).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.crosscutting import ApprovalProcess, ApprovalRequest, ApprovalStageOption
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.faculty_request import (
    REQUEST_TYPE_ADDRESS_CHANGE,
    REQUEST_TYPE_NOC,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
)
from durgam.models.identity import User
from durgam.models.school import School
from durgam.services.faculty_request import (
    EmptyApproverPoolError,
    FacultyRequestService,
    InvalidRequestStatusTransitionError,
    UnknownRequestTypeError,
)


# ── Synthetic factory helpers ─────────────────────────────────────────────────


def _make_faculty(session: Session) -> Faculty:
    """Create Campus → School → Designation → Department → User → Faculty chain."""
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)

    campus = Campus(code=f"SC{uid[:4]}", name=f"Sub Campus {uid}")
    session.add(campus)
    session.flush()

    school = School(code=f"SS{uid[:4]}", name=f"Sub School {uid}")
    session.add(school)
    session.flush()

    desig = Designation(code=f"SD{uid[:4]}", name=f"Sub Desig {uid}", rank=99)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"SDP{uid[:3]}",
        name=f"Sub Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()

    user = User(
        username=f"subf_{uid}",
        email=f"subf_{uid}@dev.local",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()

    faculty = Faculty(
        user_id=user.id,
        employee_id=f"SUBM-{uid}",
        title="Dr",
        first_name="Submit",
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


def _get_seeded_noc_process(session: Session) -> ApprovalProcess:
    """Look up the seeded faculty_noc process. Skips the test if not available."""
    process = session.exec(
        select(ApprovalProcess).where(
            ApprovalProcess.code == "faculty_noc",
            ApprovalProcess.is_deleted == False,  # noqa: E712
        )
    ).first()
    if process is None:
        pytest.skip(
            "faculty_noc process not seeded — run smoke check with test_faculty_noc_seed.py"
        )
    return process


def _make_requestor_pick_process(session: Session) -> tuple[ApprovalProcess, ApprovalStageOption]:
    """Create a synthetic faculty_address_change process with requestor-pick Stage 1.

    address_change is not seeded in Phase 5B — safe to create synthetically.
    """
    now = datetime.now(UTC)
    process = ApprovalProcess(
        code="faculty_address_change",
        title="Faculty Address Change",
        requestor_role_codes=["FACULTY"],
        channel_role_codes=["HOD", "REGISTRAR"],
        is_finance=False,
        stage_pick_modes_json={"1": "requestor"},
        created_at=now,
        updated_at=now,
    )
    session.add(process)
    session.flush()

    option = ApprovalStageOption(
        approval_process_id=process.id,
        stage_index=1,
        resolver_name="dept_head_at_requestor_campus",
        label="Head of Department",
        sort_order=0,
        created_at=now,
        updated_at=now,
    )
    session.add(option)
    session.flush()
    return process, option


def _make_synthetic_approver(session: Session) -> User:
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)
    user = User(
        username=f"hod_{uid}",
        email=f"hod_{uid}@dev.local",
        password_hash="x",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.flush()
    return user


# ── Tests ────────────────────────────────────────────────────────────────────


class TestSubmitForApproval:
    def test_submit_rejects_when_not_draft(self, db_session: Session) -> None:
        """submit_for_approval raises when FacultyRequest is not in draft status."""
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        actor = uuid4()

        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=actor,
        )
        from durgam.repositories.faculty_request import FacultyRequestRepository
        repo = FacultyRequestRepository(db_session)
        repo.update(req.id, {"status": STATUS_SUBMITTED}, actor)

        with pytest.raises(InvalidRequestStatusTransitionError, match="submitted"):
            svc.submit_for_approval(req.id, actor_id=actor)

    def test_submit_rejects_when_no_approval_process_configured(
        self, db_session: Session
    ) -> None:
        """submit_for_approval raises when no process is seeded for the request_type."""
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        actor = uuid4()

        # bonafide_certificate → looks up "faculty_bonafide_certificate" which is not seeded
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type="bonafide_certificate",
            payload=None,
            actor_id=actor,
        )

        with pytest.raises(UnknownRequestTypeError, match="faculty_bonafide_certificate"):
            svc.submit_for_approval(req.id, actor_id=actor)

    def test_submit_creates_approval_request(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Happy path: submit creates an ApprovalRequest row."""
        faculty = _make_faculty(db_session)
        process = _get_seeded_noc_process(db_session)
        approver = _make_synthetic_approver(db_session)

        from durgam.services import approval_resolvers
        monkeypatch.setitem(
            approval_resolvers.RESOLVERS,
            "dept_head_at_requestor_campus",
            lambda ctx, s: [approver],
        )

        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload={"conference": "ICSE 2027"},
            actor_id=faculty.user_id,
        )

        updated = svc.submit_for_approval(req.id, actor_id=faculty.user_id)

        assert updated.approval_request_id is not None
        approval_req = db_session.exec(
            select(ApprovalRequest).where(ApprovalRequest.id == updated.approval_request_id)
        ).first()
        assert approval_req is not None

    def test_submit_links_faculty_request_to_approval_request(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FacultyRequest.approval_request_id is set after submit."""
        faculty = _make_faculty(db_session)
        _get_seeded_noc_process(db_session)
        approver = _make_synthetic_approver(db_session)

        from durgam.services import approval_resolvers
        monkeypatch.setitem(
            approval_resolvers.RESOLVERS,
            "dept_head_at_requestor_campus",
            lambda ctx, s: [approver],
        )

        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty.user_id,
        )
        assert req.approval_request_id is None

        updated = svc.submit_for_approval(req.id, actor_id=faculty.user_id)
        assert updated.approval_request_id is not None

    def test_submit_sets_status_to_submitted(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FacultyRequest.status becomes 'submitted' after submit."""
        faculty = _make_faculty(db_session)
        _get_seeded_noc_process(db_session)
        approver = _make_synthetic_approver(db_session)

        from durgam.services import approval_resolvers
        monkeypatch.setitem(
            approval_resolvers.RESOLVERS,
            "dept_head_at_requestor_campus",
            lambda ctx, s: [approver],
        )

        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty.user_id,
        )

        updated = svc.submit_for_approval(req.id, actor_id=faculty.user_id)
        assert updated.status == STATUS_SUBMITTED

    def test_submit_approval_request_title_contains_faculty_name(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ApprovalRequest title contains process title and faculty name."""
        faculty = _make_faculty(db_session)
        process = _get_seeded_noc_process(db_session)
        approver = _make_synthetic_approver(db_session)

        from durgam.services import approval_resolvers
        monkeypatch.setitem(
            approval_resolvers.RESOLVERS,
            "dept_head_at_requestor_campus",
            lambda ctx, s: [approver],
        )

        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty.user_id,
        )
        updated = svc.submit_for_approval(req.id, actor_id=faculty.user_id)

        approval_req = db_session.exec(
            select(ApprovalRequest).where(ApprovalRequest.id == updated.approval_request_id)
        ).first()
        assert approval_req is not None
        assert "Submit" in approval_req.title  # Faculty.first_name = "Submit"
        assert process.title in approval_req.title

    def test_submit_approval_request_has_correct_process_id(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ApprovalRequest.process_id matches the seeded faculty_noc process."""
        faculty = _make_faculty(db_session)
        process = _get_seeded_noc_process(db_session)
        approver = _make_synthetic_approver(db_session)

        from durgam.services import approval_resolvers
        monkeypatch.setitem(
            approval_resolvers.RESOLVERS,
            "dept_head_at_requestor_campus",
            lambda ctx, s: [approver],
        )

        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty.user_id,
        )
        updated = svc.submit_for_approval(req.id, actor_id=faculty.user_id)

        approval_req = db_session.exec(
            select(ApprovalRequest).where(ApprovalRequest.id == updated.approval_request_id)
        ).first()
        assert approval_req is not None
        assert approval_req.process_id == process.id

    def test_submit_rejects_when_pool_empty(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """EmptyApproverPoolError when resolver returns no users."""
        faculty = _make_faculty(db_session)
        _get_seeded_noc_process(db_session)

        from durgam.services import approval_resolvers
        monkeypatch.setitem(
            approval_resolvers.RESOLVERS,
            "dept_head_at_requestor_campus",
            lambda ctx, s: [],  # empty pool
        )

        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty.user_id,
        )

        with pytest.raises(EmptyApproverPoolError):
            svc.submit_for_approval(req.id, actor_id=faculty.user_id)

    def test_submit_rejects_requestor_pick_without_option_id(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """pending_pick status raises InvalidRequestStatusTransitionError."""
        faculty = _make_faculty(db_session)
        _make_requestor_pick_process(db_session)
        approver = _make_synthetic_approver(db_session)

        from durgam.services import approval_resolvers
        monkeypatch.setitem(
            approval_resolvers.RESOLVERS,
            "dept_head_at_requestor_campus",
            lambda ctx, s: [approver],
        )

        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_ADDRESS_CHANGE,
            payload=None,
            actor_id=faculty.user_id,
        )

        with pytest.raises(InvalidRequestStatusTransitionError, match="requestor pick"):
            svc.submit_for_approval(req.id, actor_id=faculty.user_id)  # no picked_option_ids

    def test_submit_rejects_invalid_option_id(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """StageOptionMismatchError when picked option_id is not in Stage 1."""
        from durgam.services.approval_engine import StageOptionMismatchError

        faculty = _make_faculty(db_session)
        _make_requestor_pick_process(db_session)
        approver = _make_synthetic_approver(db_session)

        from durgam.services import approval_resolvers
        monkeypatch.setitem(
            approval_resolvers.RESOLVERS,
            "dept_head_at_requestor_campus",
            lambda ctx, s: [approver],
        )

        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_ADDRESS_CHANGE,
            payload=None,
            actor_id=faculty.user_id,
        )

        with pytest.raises(StageOptionMismatchError):
            svc.submit_for_approval(
                req.id,
                actor_id=faculty.user_id,
                picked_option_ids={1: uuid4()},  # random UUID — not a valid option
            )

    def test_submit_picked_option_ids_json_stored(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """picked_option_ids_json is stored on ApprovalRequest when provided."""
        faculty = _make_faculty(db_session)
        _, option = _make_requestor_pick_process(db_session)
        approver = _make_synthetic_approver(db_session)

        from durgam.services import approval_resolvers
        monkeypatch.setitem(
            approval_resolvers.RESOLVERS,
            "dept_head_at_requestor_campus",
            lambda ctx, s: [approver],
        )

        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_ADDRESS_CHANGE,
            payload=None,
            actor_id=faculty.user_id,
        )

        updated = svc.submit_for_approval(
            req.id,
            actor_id=faculty.user_id,
            picked_option_ids={1: option.id},
        )

        approval_req = db_session.exec(
            select(ApprovalRequest).where(ApprovalRequest.id == updated.approval_request_id)
        ).first()
        assert approval_req is not None
        assert approval_req.picked_option_ids_json == {"1": str(option.id)}

    def test_submit_real_noc_process_resolves_seeded_hod(
        self, db_session: Session
    ) -> None:
        """Full integration: seeded faculty_noc process + seeded faculty_user + hod_dmacs resolver.

        This test relies on seeded_db_engine running before db_engine (which it will in the
        smoke check invocation). Skips gracefully when run standalone.
        """
        process = db_session.exec(
            select(ApprovalProcess).where(
                ApprovalProcess.code == "faculty_noc",
                ApprovalProcess.is_deleted == False,  # noqa: E712
            )
        ).first()
        if process is None:
            pytest.skip(
                "faculty_noc not seeded — run smoke check with test_faculty_noc_seed.py"
            )

        faculty_user_row = db_session.exec(
            select(User).where(
                User.username == "faculty_user",
                User.is_deleted == False,  # noqa: E712
            )
        ).first()
        if faculty_user_row is None:
            pytest.skip("faculty_user not seeded")

        faculty = db_session.exec(
            select(Faculty).where(
                Faculty.user_id == faculty_user_row.id,
                Faculty.is_deleted == False,  # noqa: E712
            )
        ).first()
        if faculty is None:
            pytest.skip("faculty backfill not seeded")

        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty_user_row.id,
        )

        updated = svc.submit_for_approval(req.id, actor_id=faculty_user_row.id)

        assert updated.status == STATUS_SUBMITTED
        assert updated.approval_request_id is not None

        approval_req = db_session.exec(
            select(ApprovalRequest).where(ApprovalRequest.id == updated.approval_request_id)
        ).first()
        assert approval_req is not None
        assert approval_req.process_id == process.id
        assert approval_req.requestor_user_id == faculty_user_row.id
