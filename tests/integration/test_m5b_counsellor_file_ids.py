"""Integration tests: counsellor file ID persistence on create, edit-add, edit-replace.

Exercises the service layer directly (same path the state handler calls) to prove
file IDs are correctly linked on all three mutation paths.
"""

from datetime import date
from uuid import UUID, uuid4

import pytest

from durgam.models.campus import Campus
from durgam.models.config_anchors import AcademicYear, MentalHealthCounsellor
from durgam.models.crosscutting import FileAsset
from durgam.models.identity import User
from durgam.repositories.mental_health_counsellor import MentalHealthCounsellorRepository
from durgam.services.mental_health_counsellor import MentalHealthCounsellorService
from durgam.services.password import hash_password


def _ay(session) -> AcademicYear:
    ay = AcademicYear(
        code=f"T{uuid4().hex[:6]}",
        starts_on=date(2025, 7, 1),
        ends_on=date(2026, 4, 30),
        is_locked=False,
    )
    session.add(ay)
    session.flush()
    session.refresh(ay)
    return ay


def _campus(session) -> Campus:
    c = Campus(code=f"C{uuid4().hex[:4]}", name="Test Campus", address="Addr")
    session.add(c)
    session.flush()
    session.refresh(c)
    return c


def _user(session) -> User:
    u = User(
        username=f"t{uuid4().hex[:8]}",
        email=f"t{uuid4().hex[:8]}@test.com",
        full_name="Test User",
        password_hash=hash_password("Test_Pass1!XZ"),
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _file_asset(session, user: User) -> FileAsset:
    fa = FileAsset(
        storage_key=f"test/{uuid4().hex}.pdf",
        original_name="test.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        sha256=uuid4().hex + uuid4().hex,
        owner_user_id=user.id,
        purpose="counsellor_document",
    )
    session.add(fa)
    session.flush()
    session.refresh(fa)
    return fa


def _svc(session) -> MentalHealthCounsellorService:
    return MentalHealthCounsellorService(repo=MentalHealthCounsellorRepository(session))


class TestCounsellorFileIdPersistence:
    """Regression guard: file IDs must persist on create, edit-add, edit-replace."""

    def test_create_with_file_ids_persists(self, db_session):
        """Create path passes file IDs directly to svc.create() — they persist."""
        ay = _ay(db_session)
        campus = _campus(db_session)
        user = _user(db_session)
        svc = _svc(db_session)
        appt_asset = _file_asset(db_session, user)
        qual_asset = _file_asset(db_session, user)

        created = svc.create(
            academic_year_id=ay.id,
            campus_id=campus.id,
            name="Dr. CreateFiles",
            qualification="PhD",
            specialisation="Clinical",
            mode_of_appointment="inhouse",
            appointment_start=date(2025, 7, 1),
            appointment_end=date(2025, 12, 31),
            actor_id=user.id,
            appointment_letter_file_id=appt_asset.id,
            qualification_proof_file_id=qual_asset.id,
        )

        db_session.flush()
        db_session.refresh(created)

        assert created.appointment_letter_file_id == appt_asset.id
        assert created.qualification_proof_file_id == qual_asset.id

    def test_create_without_file_ids_leaves_null(self, db_session):
        """Create without file IDs leaves columns NULL (baseline)."""
        ay = _ay(db_session)
        campus = _campus(db_session)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            academic_year_id=ay.id,
            campus_id=campus.id,
            name="Dr. NoFiles",
            qualification="PhD",
            specialisation="Clinical",
            mode_of_appointment="inhouse",
            appointment_start=date(2025, 7, 1),
            appointment_end=date(2025, 12, 31),
            actor_id=user.id,
        )

        db_session.flush()
        db_session.refresh(created)

        assert created.appointment_letter_file_id is None
        assert created.qualification_proof_file_id is None

    def test_edit_add_files_persists(self, db_session):
        """Edit path: create without files, then update to add file IDs."""
        ay = _ay(db_session)
        campus = _campus(db_session)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            academic_year_id=ay.id,
            campus_id=campus.id,
            name="Dr. EditAdd",
            qualification="PhD",
            specialisation="Clinical",
            mode_of_appointment="inhouse",
            appointment_start=date(2025, 7, 1),
            appointment_end=date(2025, 12, 31),
            actor_id=user.id,
        )

        assert created.appointment_letter_file_id is None
        assert created.qualification_proof_file_id is None

        appt_asset = _file_asset(db_session, user)
        qual_asset = _file_asset(db_session, user)

        updated = svc.update(
            created.id,
            {
                "appointment_letter_file_id": appt_asset.id,
                "qualification_proof_file_id": qual_asset.id,
            },
            user.id,
        )

        db_session.flush()
        db_session.refresh(updated)

        assert updated.appointment_letter_file_id == appt_asset.id
        assert updated.qualification_proof_file_id == qual_asset.id

    def test_edit_replace_file_persists(self, db_session):
        """Edit path: create with files, then replace one file ID."""
        ay = _ay(db_session)
        campus = _campus(db_session)
        user = _user(db_session)
        svc = _svc(db_session)

        original_appt = _file_asset(db_session, user)
        original_qual = _file_asset(db_session, user)

        created = svc.create(
            academic_year_id=ay.id,
            campus_id=campus.id,
            name="Dr. EditReplace",
            qualification="PhD",
            specialisation="Clinical",
            mode_of_appointment="inhouse",
            appointment_start=date(2025, 7, 1),
            appointment_end=date(2025, 12, 31),
            actor_id=user.id,
            appointment_letter_file_id=original_appt.id,
            qualification_proof_file_id=original_qual.id,
        )

        assert created.appointment_letter_file_id == original_appt.id

        new_appt = _file_asset(db_session, user)
        updated = svc.update(
            created.id,
            {"appointment_letter_file_id": new_appt.id},
            user.id,
        )

        db_session.flush()
        db_session.refresh(updated)

        assert updated.appointment_letter_file_id == new_appt.id
        assert updated.qualification_proof_file_id == original_qual.id

    def test_row_dict_populates_file_id_strings(self, db_session):
        """The _load_data row dict produces non-empty UUID strings for file IDs."""
        ay = _ay(db_session)
        campus = _campus(db_session)
        user = _user(db_session)
        svc = _svc(db_session)

        appt_asset = _file_asset(db_session, user)
        qual_asset = _file_asset(db_session, user)

        created = svc.create(
            academic_year_id=ay.id,
            campus_id=campus.id,
            name="Dr. RowDict",
            qualification="PhD",
            specialisation="Clinical",
            mode_of_appointment="inhouse",
            appointment_start=date(2025, 7, 1),
            appointment_end=date(2025, 12, 31),
            actor_id=user.id,
            appointment_letter_file_id=appt_asset.id,
            qualification_proof_file_id=qual_asset.id,
        )

        db_session.flush()
        db_session.refresh(created)

        appt_str = str(created.appointment_letter_file_id) if created.appointment_letter_file_id else ""
        qual_str = str(created.qualification_proof_file_id) if created.qualification_proof_file_id else ""

        assert appt_str == str(appt_asset.id)
        assert qual_str == str(qual_asset.id)
        assert appt_str != ""
        assert qual_str != ""
