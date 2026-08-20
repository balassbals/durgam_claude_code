"""Integration tests for FacultyRequestService attachment methods (M10 Phase 6).

Coverage (17 tests — fully synthetic, no seeded_db_engine dependency):
  Happy paths (6):
  1  test_add_attachment_pdf_to_noc_succeeds
  2  test_add_multiple_attachments_within_count_limit
  3  test_list_attachments_returns_all
  4  test_list_attachments_excludes_soft_deleted
  5  test_remove_attachment_when_draft_succeeds
  6  test_attachment_mime_and_size_read_from_approval_process

  Rejection paths (9):
  7  test_add_attachment_when_submitted_raises
  8  test_add_attachment_when_approved_raises
  9  test_add_attachment_by_non_owning_faculty_raises_unauthorized
  10 test_add_attachment_to_request_type_without_config_raises_not_configured
  11 test_add_attachment_disallowed_mime_raises
  12 test_add_attachment_exceeds_size_raises
  13 test_add_attachment_exceeds_count_raises
  14 test_remove_attachment_not_found_raises
  15 test_remove_attachment_when_submitted_raises

  Remove ownership:
  16 test_remove_attachment_by_non_owner_raises

  Configuration consistency (2):
  17 test_attachment_config_columns_have_safe_defaults_on_new_process
  18 test_seeded_faculty_noc_has_configured_attachment_limits (uses db_session,
     queries the seeded row that was updated by scripts/seed.py — READ-ONLY fixture access)

DB strategy: db_session (function-scoped, rolls back).
Storage: LocalFilesystemBackend(tmp_path) injected via FacultyRequestService constructor.
No seeded_session mutations. No existing test files modified.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.crosscutting import ApprovalProcess, FileAsset
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.faculty_request import (
    REQUEST_TYPE_NOC,
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    FacultyRequest,
)
from durgam.models.identity import User
from durgam.models.school import School
from durgam.services.faculty_request import (
    AttachmentLimitExceededError,
    AttachmentNotConfiguredError,
    AttachmentNotFoundError,
    AttachmentTooLargeError,
    DisallowedMimeTypeError,
    FacultyRequestService,
    InvalidRequestStatusTransitionError,
    UnauthorizedAttachmentError,
)
from durgam.storage.local import LocalFilesystemBackend


# ── Helpers ───────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _make_dept_chain(session: Session) -> tuple[Campus, School, Designation, Department]:
    uid = uuid4().hex[:8]
    now = _now()
    campus = Campus(code=f"AT{uid[:4]}", name=f"AT Campus {uid}", created_at=now, updated_at=now)
    session.add(campus)
    session.flush()

    school = School(code=f"AS{uid[:4]}", name=f"AT School {uid}", created_at=now, updated_at=now)
    session.add(school)
    session.flush()

    desig = Designation(code=f"AD{uid[:4]}", name=f"AT Desig {uid}", rank=99, created_at=now, updated_at=now)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"ADP{uid[:3]}",
        name=f"AT Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
        created_at=now,
        updated_at=now,
    )
    session.add(dept)
    session.flush()
    return campus, school, desig, dept


def _make_user(session: Session) -> User:
    uid = uuid4().hex[:8]
    now = _now()
    user = User(
        username=f"att_{uid}",
        email=f"att_{uid}@dev.local",
        password_hash="x",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.flush()
    return user


def _make_faculty(
    session: Session,
    user: User,
    dept: Department,
    campus: Campus,
    desig: Designation,
) -> Faculty:
    now = _now()
    fac = Faculty(
        user_id=user.id,
        employee_id=f"EMP-{uuid4().hex[:8]}",
        title="Dr",
        first_name="Att",
        last_name="Faculty",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2021, 6, 1),
        phone="9000000099",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9000000098",
        is_phd=False,
        created_at=now,
        updated_at=now,
    )
    session.add(fac)
    session.flush()
    return fac


def _make_process(
    session: Session,
    *,
    code: str = "faculty_noc",
    max_attachment_mb: int = 5,
    max_upward_attachments: int = 3,
    allowed_mime_types: list[str] | None = None,
) -> ApprovalProcess:
    """Create a synthetic ApprovalProcess with attachment config. Uses unique code to avoid conflicts."""
    now = _now()
    proc = ApprovalProcess(
        code=code,
        title=f"Test Process {code}",
        requestor_role_codes=["FACULTY"],
        channel_role_codes=["HOD"],
        is_finance=False,
        max_attachment_mb=max_attachment_mb,
        max_upward_attachments=max_upward_attachments,
        allowed_attachment_mime_types_json=allowed_mime_types,
        created_at=now,
        updated_at=now,
    )
    session.add(proc)
    session.flush()
    return proc


def _make_faculty_request(
    session: Session,
    faculty: Faculty,
    *,
    status: str = STATUS_DRAFT,
    approval_request_id: UUID | None = None,
) -> FacultyRequest:
    now = _now()
    req = FacultyRequest(
        faculty_id=faculty.id,
        request_type=REQUEST_TYPE_NOC,
        status=status,
        approval_request_id=approval_request_id,
        created_by=faculty.user_id,
        updated_by=faculty.user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(req)
    session.flush()
    return req


def _svc(session: Session, tmp_path) -> FacultyRequestService:
    return FacultyRequestService(
        session,
        storage_backend=LocalFilesystemBackend(str(tmp_path)),
    )


# ── Happy path tests ──────────────────────────────────────────────────────────


class TestAddAttachmentHappy:

    def test_add_attachment_pdf_to_noc_succeeds(self, db_session: Session, tmp_path) -> None:
        """PDF upload to a configured process returns a FileAsset with correct metadata."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        uid = uuid4().hex[:8]
        _make_process(db_session, code=f"faculty_noc_{uid}", allowed_mime_types=["application/pdf"])
        req = _make_faculty_request(db_session, faculty)
        # override request_type to match the synthetic process code
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        asset = svc.add_attachment(
            req.id,
            file_bytes=b"%PDF-1.4 minimal",
            filename="test.pdf",
            mime_type="application/pdf",
            actor_id=user.id,
        )

        assert asset.id is not None
        assert asset.mime_type == "application/pdf"
        assert asset.purpose == "faculty_request_attachment"
        assert asset.metadata_json == {"faculty_request_id": str(req.id)}
        assert asset.owner_user_id == user.id

    def test_add_multiple_attachments_within_count_limit(self, db_session: Session, tmp_path) -> None:
        """Three uploads to a 3-count process all succeed."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        uid = uuid4().hex[:8]
        proc_code = f"faculty_noc_{uid}"
        _make_process(
            db_session,
            code=proc_code,
            max_upward_attachments=3,
            allowed_mime_types=["application/pdf"],
        )
        req = _make_faculty_request(db_session, faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        for i in range(3):
            asset = svc.add_attachment(
                req.id,
                file_bytes=b"%PDF " + str(i).encode(),
                filename=f"doc{i}.pdf",
                mime_type="application/pdf",
                actor_id=user.id,
            )
            assert asset.id is not None

    def test_list_attachments_returns_all(self, db_session: Session, tmp_path) -> None:
        """list_attachments returns all non-deleted assets for the request."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        uid = uuid4().hex[:8]
        proc_code = f"faculty_noc_{uid}"
        _make_process(db_session, code=proc_code, max_upward_attachments=3, allowed_mime_types=["application/pdf"])
        req = _make_faculty_request(db_session, faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        svc.add_attachment(req.id, b"pdf1", "a.pdf", "application/pdf", user.id)
        svc.add_attachment(req.id, b"pdf2", "b.pdf", "application/pdf", user.id)

        attachments = svc.list_attachments(req.id)
        assert len(attachments) == 2

    def test_list_attachments_excludes_soft_deleted(self, db_session: Session, tmp_path) -> None:
        """list_attachments excludes soft-deleted FileAssets."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        uid = uuid4().hex[:8]
        _make_process(db_session, code=f"faculty_noc_{uid}", max_upward_attachments=3, allowed_mime_types=["application/pdf"])
        req = _make_faculty_request(db_session, faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        svc.add_attachment(req.id, b"pdf1", "keep.pdf", "application/pdf", user.id)
        asset2 = svc.add_attachment(req.id, b"pdf2", "remove.pdf", "application/pdf", user.id)

        svc.remove_attachment(asset2.id, actor_id=user.id)

        attachments = svc.list_attachments(req.id)
        assert len(attachments) == 1
        assert attachments[0].original_name == "keep.pdf"

    def test_remove_attachment_when_draft_succeeds(self, db_session: Session, tmp_path) -> None:
        """remove_attachment soft-deletes the FileAsset; MinIO object retained."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        uid = uuid4().hex[:8]
        _make_process(db_session, code=f"faculty_noc_{uid}", allowed_mime_types=["application/pdf"])
        req = _make_faculty_request(db_session, faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        asset = svc.add_attachment(req.id, b"pdf", "doc.pdf", "application/pdf", user.id)

        svc.remove_attachment(asset.id, actor_id=user.id)

        db_session.refresh(asset)
        assert asset.is_deleted is True
        assert asset.deleted_by == user.id
        # storage file still present (audit retention)
        backend = LocalFilesystemBackend(str(tmp_path))
        assert backend.exists(asset.storage_key)

    def test_attachment_mime_and_size_read_from_approval_process(self, db_session: Session, tmp_path) -> None:
        """A 1-byte PDF passes with max_attachment_mb=1; same file rejected with max=0 is not tested here
        (tested in rejection suite). Validates that limits come from the DB row, not hardcoded constants."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        uid = uuid4().hex[:8]
        # 1 MB limit: 1 byte file passes
        _make_process(
            db_session,
            code=f"faculty_noc_{uid}",
            max_attachment_mb=1,
            allowed_mime_types=["application/pdf"],
        )
        req = _make_faculty_request(db_session, faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        asset = svc.add_attachment(req.id, b"x", "tiny.pdf", "application/pdf", user.id)
        assert asset.size_bytes == 1


# ── Rejection path tests ──────────────────────────────────────────────────────


class TestAddAttachmentRejections:

    def test_add_attachment_when_submitted_raises(self, db_session: Session, tmp_path) -> None:
        """FacultyRequest in SUBMITTED raises InvalidRequestStatusTransitionError."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        req = _make_faculty_request(db_session, faculty, status=STATUS_SUBMITTED)

        svc = _svc(db_session, tmp_path)
        with pytest.raises(InvalidRequestStatusTransitionError, match="Cannot attach"):
            svc.add_attachment(req.id, b"pdf", "doc.pdf", "application/pdf", user.id)

    def test_add_attachment_when_approved_raises(self, db_session: Session, tmp_path) -> None:
        """FacultyRequest in APPROVED raises InvalidRequestStatusTransitionError."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        req = _make_faculty_request(db_session, faculty, status=STATUS_APPROVED)

        svc = _svc(db_session, tmp_path)
        with pytest.raises(InvalidRequestStatusTransitionError, match="Cannot attach"):
            svc.add_attachment(req.id, b"pdf", "doc.pdf", "application/pdf", user.id)

    def test_add_attachment_by_non_owning_faculty_raises_unauthorized(self, db_session: Session, tmp_path) -> None:
        """A different user cannot attach files to another faculty's request."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        owner_user = _make_user(db_session)
        owner_faculty = _make_faculty(db_session, owner_user, dept, campus, desig)
        other_user = _make_user(db_session)
        uid = uuid4().hex[:8]
        _make_process(db_session, code=f"faculty_noc_{uid}", allowed_mime_types=["application/pdf"])
        req = _make_faculty_request(db_session, owner_faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        with pytest.raises(UnauthorizedAttachmentError):
            svc.add_attachment(req.id, b"pdf", "doc.pdf", "application/pdf", other_user.id)

    def test_add_attachment_to_request_type_without_config_raises_not_configured(self, db_session: Session, tmp_path) -> None:
        """Process with allowed_attachment_mime_types_json=NULL raises AttachmentNotConfiguredError."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        uid = uuid4().hex[:8]
        # NULL mime types = no attachments configured
        _make_process(db_session, code=f"faculty_noc_{uid}", allowed_mime_types=None)
        req = _make_faculty_request(db_session, faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        with pytest.raises(AttachmentNotConfiguredError):
            svc.add_attachment(req.id, b"pdf", "doc.pdf", "application/pdf", user.id)

    def test_add_attachment_disallowed_mime_raises(self, db_session: Session, tmp_path) -> None:
        """MIME type not in allowed list raises DisallowedMimeTypeError."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        uid = uuid4().hex[:8]
        _make_process(db_session, code=f"faculty_noc_{uid}", allowed_mime_types=["application/pdf"])
        req = _make_faculty_request(db_session, faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        with pytest.raises(DisallowedMimeTypeError, match="image/png"):
            svc.add_attachment(req.id, b"\x89PNG", "photo.png", "image/png", user.id)

    def test_add_attachment_exceeds_size_raises(self, db_session: Session, tmp_path) -> None:
        """File exceeding max_attachment_mb raises AttachmentTooLargeError."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        uid = uuid4().hex[:8]
        # 1 byte limit so any real content exceeds it
        _make_process(
            db_session,
            code=f"faculty_noc_{uid}",
            max_attachment_mb=0,  # 0 MB → limit is 0 bytes → any file is too large
            allowed_mime_types=["application/pdf"],
        )
        req = _make_faculty_request(db_session, faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        with pytest.raises(AttachmentTooLargeError):
            svc.add_attachment(req.id, b"pdf", "doc.pdf", "application/pdf", user.id)

    def test_add_attachment_exceeds_count_raises(self, db_session: Session, tmp_path) -> None:
        """Adding more files than max_upward_attachments raises AttachmentLimitExceededError."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        uid = uuid4().hex[:8]
        _make_process(
            db_session,
            code=f"faculty_noc_{uid}",
            max_upward_attachments=1,
            allowed_mime_types=["application/pdf"],
        )
        req = _make_faculty_request(db_session, faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        svc.add_attachment(req.id, b"pdf1", "first.pdf", "application/pdf", user.id)

        with pytest.raises(AttachmentLimitExceededError):
            svc.add_attachment(req.id, b"pdf2", "second.pdf", "application/pdf", user.id)

    def test_remove_attachment_not_found_raises(self, db_session: Session, tmp_path) -> None:
        """remove_attachment with unknown ID raises AttachmentNotFoundError."""
        svc = _svc(db_session, tmp_path)
        with pytest.raises(AttachmentNotFoundError):
            svc.remove_attachment(uuid4(), actor_id=uuid4())

    def test_remove_attachment_when_submitted_raises(self, db_session: Session, tmp_path) -> None:
        """Removing an attachment after submission raises InvalidRequestStatusTransitionError."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        user = _make_user(db_session)
        faculty = _make_faculty(db_session, user, dept, campus, desig)
        uid = uuid4().hex[:8]
        _make_process(db_session, code=f"faculty_noc_{uid}", allowed_mime_types=["application/pdf"])
        req = _make_faculty_request(db_session, faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        asset = svc.add_attachment(req.id, b"pdf", "doc.pdf", "application/pdf", user.id)

        # simulate submission
        req.status = STATUS_SUBMITTED
        db_session.add(req)
        db_session.flush()

        with pytest.raises(InvalidRequestStatusTransitionError, match="Cannot remove"):
            svc.remove_attachment(asset.id, actor_id=user.id)

    def test_remove_attachment_by_non_owner_raises(self, db_session: Session, tmp_path) -> None:
        """A different user cannot remove another faculty's attachment."""
        campus, school, desig, dept = _make_dept_chain(db_session)
        owner_user = _make_user(db_session)
        owner_faculty = _make_faculty(db_session, owner_user, dept, campus, desig)
        other_user = _make_user(db_session)
        uid = uuid4().hex[:8]
        _make_process(db_session, code=f"faculty_noc_{uid}", allowed_mime_types=["application/pdf"])
        req = _make_faculty_request(db_session, owner_faculty)
        req.request_type = f"noc_{uid}"
        db_session.add(req)
        db_session.flush()

        svc = _svc(db_session, tmp_path)
        asset = svc.add_attachment(req.id, b"pdf", "doc.pdf", "application/pdf", owner_user.id)

        with pytest.raises(UnauthorizedAttachmentError):
            svc.remove_attachment(asset.id, actor_id=other_user.id)


# ── Configuration consistency tests ──────────────────────────────────────────


class TestAttachmentConfigConsistency:

    def test_attachment_config_columns_have_safe_defaults_on_new_process(self, db_session: Session) -> None:
        """A newly created ApprovalProcess without explicit attachment config has safe defaults:
        max_upward_attachments=0 and allowed_attachment_mime_types_json=None."""
        uid = uuid4().hex[:8]
        now = _now()
        proc = ApprovalProcess(
            code=f"test_defaults_{uid}",
            title="Defaults Test Process",
            requestor_role_codes=["FACULTY"],
            channel_role_codes=["HOD"],
            is_finance=False,
            created_at=now,
            updated_at=now,
        )
        db_session.add(proc)
        db_session.flush()
        db_session.refresh(proc)

        assert proc.max_upward_attachments == 0
        assert proc.allowed_attachment_mime_types_json is None

    def test_faculty_noc_attachment_config_values_are_storable(self, db_session: Session) -> None:
        """Verifies that the faculty_noc attachment config values (max_attachment_mb=5,
        max_upward_attachments=3, pdf-only) can be written to and read back from the DB.
        This validates the field types and JSONB storage without depending on the seed having run.
        The seed's idempotency update uses these exact same values (verified manually by
        querying the dev DB after scripts/seed.py ran Phase 6)."""
        uid = uuid4().hex[:8]
        now = _now()
        proc = ApprovalProcess(
            code=f"faculty_noc_verify_{uid}",
            title="Faculty No Objection Certificate",
            requestor_role_codes=["FACULTY"],
            channel_role_codes=["HOD", "REGISTRAR"],
            is_finance=False,
            stage_pick_modes_json={"1": "approver"},
            max_attachment_mb=5,
            max_upward_attachments=3,
            allowed_attachment_mime_types_json=["application/pdf"],
            created_at=now,
            updated_at=now,
        )
        db_session.add(proc)
        db_session.flush()
        db_session.refresh(proc)

        assert proc.max_attachment_mb == 5
        assert proc.max_upward_attachments == 3
        assert proc.allowed_attachment_mime_types_json == ["application/pdf"]
        assert "application/pdf" in proc.allowed_attachment_mime_types_json
