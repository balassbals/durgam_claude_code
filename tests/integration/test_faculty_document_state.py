"""Integration tests for FacultyService document methods (M10 Phase P4).

Tests verify: upload / update_metadata / remove / list_documents with real
PostgreSQL + LocalFilesystemBackend for storage (no MinIO). Uses db_session.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.crosscutting import FileAsset
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.identity import User
from durgam.models.school import School
from durgam.repositories.faculty import (
    FacultyDocumentRepository,
    FacultyEducationRepository,
    FacultyExperienceRepository,
    FacultyExpertiseRepository,
    FacultyRepository,
    FacultyWorkloadRepository,
)
from durgam.services.faculty import (
    DocumentInvalidMimeError,
    DocumentNotFoundError,
    DocumentTooLargeError,
    FacultyService,
    NotOwnerError,
)
from durgam.storage.local import LocalFilesystemBackend

_SMALL_PDF = b"%PDF-1.4\n" + b"x" * 200
_OVER_2MB = b"x" * (2 * 1024 * 1024 + 1)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_faculty(session: Session) -> Faculty:
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)

    campus = Campus(code=f"DC{uid[:4]}", name=f"Doc Campus {uid}")
    session.add(campus)
    session.flush()

    school = School(code=f"DS{uid[:4]}", name=f"Doc School {uid}")
    session.add(school)
    session.flush()

    desig = Designation(code=f"DD{uid[:4]}", name=f"Doc Desig {uid}", rank=44)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"DDP{uid[:3]}",
        name=f"Doc Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()

    user = User(
        username=f"doc_{uid}",
        email=f"doc_{uid}@dev.local",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()

    faculty = Faculty(
        user_id=user.id,
        employee_id=f"DEMP-{uid}",
        title="Dr",
        first_name="Doc",
        last_name="Test",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2020, 7, 1),
        phone="9000555000",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9000555001",
        is_phd=False,
        created_at=now,
        updated_at=now,
    )
    session.add(faculty)
    session.flush()
    return faculty


def _make_svc(session: Session) -> FacultyService:
    return FacultyService(
        faculty_repo=FacultyRepository(session),
        education_repo=FacultyEducationRepository(session),
        experience_repo=FacultyExperienceRepository(session),
        expertise_repo=FacultyExpertiseRepository(session),
        document_repo=FacultyDocumentRepository(session),
        workload_repo=FacultyWorkloadRepository(session),
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestUploadDocumentIntegration:
    def test_upload_pdf_creates_asset_and_document(
        self, db_session: Session, tmp_path
    ) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with patch(
            "durgam.storage.get_storage_backend",
            return_value=LocalFilesystemBackend(str(tmp_path)),
        ):
            doc = svc.upload_document(
                faculty.id,
                document_type="PhD Certificate",
                description="Awarded 2018",
                file_bytes=_SMALL_PDF,
                original_filename="phd.pdf",
                mime_type="application/pdf",
                actor_id=faculty.user_id,
            )
        assert doc.doc_type == "PhD Certificate"
        assert doc.description == "Awarded 2018"
        # FileAsset row created with purpose faculty_document
        asset = db_session.get(FileAsset, doc.file_asset_id)
        assert asset is not None
        assert asset.purpose == "faculty_document"
        assert asset.mime_type == "application/pdf"

    def test_upload_jpeg_raises_invalid_mime(
        self, db_session: Session, tmp_path
    ) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with patch(
            "durgam.storage.get_storage_backend",
            return_value=LocalFilesystemBackend(str(tmp_path)),
        ):
            with pytest.raises(DocumentInvalidMimeError):
                svc.upload_document(
                    faculty.id,
                    document_type="X",
                    description=None,
                    file_bytes=b"\xff\xd8\xff",
                    original_filename="x.jpg",
                    mime_type="image/jpeg",
                    actor_id=faculty.user_id,
                )

    def test_upload_oversized_raises(self, db_session: Session, tmp_path) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with patch(
            "durgam.storage.get_storage_backend",
            return_value=LocalFilesystemBackend(str(tmp_path)),
        ):
            with pytest.raises(DocumentTooLargeError):
                svc.upload_document(
                    faculty.id,
                    document_type="X",
                    description=None,
                    file_bytes=_OVER_2MB,
                    original_filename="big.pdf",
                    mime_type="application/pdf",
                    actor_id=faculty.user_id,
                )

    def test_upload_not_owner_raises(self, db_session: Session, tmp_path) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with patch(
            "durgam.storage.get_storage_backend",
            return_value=LocalFilesystemBackend(str(tmp_path)),
        ):
            with pytest.raises(NotOwnerError):
                svc.upload_document(
                    faculty.id,
                    document_type="X",
                    description=None,
                    file_bytes=_SMALL_PDF,
                    original_filename="x.pdf",
                    mime_type="application/pdf",
                    actor_id=uuid4(),
                )


class TestUpdateRemoveListDocumentIntegration:
    def _upload(self, svc, faculty, tmp_path, *, doc_type="Cert", desc=None):
        with patch(
            "durgam.storage.get_storage_backend",
            return_value=LocalFilesystemBackend(str(tmp_path)),
        ):
            return svc.upload_document(
                faculty.id,
                document_type=doc_type,
                description=desc,
                file_bytes=_SMALL_PDF,
                original_filename="x.pdf",
                mime_type="application/pdf",
                actor_id=faculty.user_id,
            )

    def test_update_metadata_keeps_file_asset(
        self, db_session: Session, tmp_path
    ) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        doc = self._upload(svc, faculty, tmp_path, doc_type="Old", desc="old")
        original_asset_id = doc.file_asset_id
        updated = svc.update_document_metadata(
            doc.id,
            document_type="New Type",
            description="new desc",
            actor_id=faculty.user_id,
        )
        assert updated.doc_type == "New Type"
        assert updated.description == "new desc"
        assert updated.file_asset_id == original_asset_id

    def test_remove_soft_deletes_doc_and_asset(
        self, db_session: Session, tmp_path
    ) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        doc = self._upload(svc, faculty, tmp_path)
        asset_id = doc.file_asset_id
        svc.remove_document_and_file(doc.id, faculty.user_id)

        remaining = svc.list_documents(faculty.id)
        assert doc.id not in [d.id for d in remaining]
        asset = db_session.get(FileAsset, asset_id)
        assert asset is not None
        assert asset.is_deleted is True

    def test_remove_not_found_raises(self, db_session: Session) -> None:
        svc = _make_svc(db_session)
        with pytest.raises(DocumentNotFoundError):
            svc.remove_document_and_file(uuid4(), uuid4())

    def test_list_sorted_created_at_desc(
        self, db_session: Session, tmp_path
    ) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        for i in range(3):
            self._upload(svc, faculty, tmp_path, doc_type=f"Doc-{i}")
        result = svc.list_documents(faculty.id)
        ats = [d.created_at for d in result]
        assert ats == sorted(ats, reverse=True)
