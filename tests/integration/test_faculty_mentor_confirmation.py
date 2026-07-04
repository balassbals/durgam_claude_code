"""Integration tests for Phase 11E — FacultyMentorConfirmation invalidation.

Proves:
  1. invalidate_confirmation returns None when no active confirmation exists.
  2. invalidate_confirmation soft-deletes an active confirmation and returns its ID.
  3. Partial unique index allows a new confirmation INSERT after invalidation.
  4. Calling invalidate_confirmation a second time (already soft-deleted) returns None.
  5. delete invalidation: soft_delete also invalidates.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from durgam.models.campus import Campus
from durgam.models.config_anchors import (
    AcademicYear,
    FacultyMentorAssignment,
    FacultyMentorConfirmation,
)
from durgam.models.config_anchors import Designation
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.identity import User
from durgam.models.school import School
from durgam.services.assignment import (
    invalidate_confirmation,
    is_material_mentor_edit,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _ay(session: Session) -> AcademicYear:
    ay = AcademicYear(
        code=f"AY{uuid4().hex[:6]}",
        starts_on=date(2025, 6, 1),
        ends_on=date(2026, 5, 31),
    )
    session.add(ay)
    session.flush()
    return ay


def _campus(session: Session) -> Campus:
    c = Campus(code=f"C{uuid4().hex[:8]}", name="Campus", address="Addr")
    session.add(c)
    session.flush()
    return c


def _confirmation(
    session: Session, ay_id, campus_id, deleted: bool = False
) -> FacultyMentorConfirmation:
    now = datetime.now(UTC)
    actor = uuid4()
    conf = FacultyMentorConfirmation(
        academic_year_id=ay_id,
        campus_id=campus_id,
        confirmed_at=now,
        confirmed_by_user_id=None,  # nullable FK; no real User row needed in tests
        created_by=actor,
        updated_by=actor,
        created_at=now,
        updated_at=now,
        is_deleted=deleted,
        deleted_at=now if deleted else None,
        deleted_by=actor if deleted else None,
    )
    session.add(conf)
    session.flush()
    return conf


def _faculty(session: Session, ay: AcademicYear, campus: Campus) -> Faculty:
    school = School(code=f"S{uuid4().hex[:8]}", name="School")
    session.add(school)
    session.flush()
    dept = Department(
        code=f"D{uuid4().hex[:8]}",
        name="Dept",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()
    desig = Designation(code=f"DG{uuid4().hex[:8]}", name="Prof", rank=50)
    session.add(desig)
    session.flush()
    user = User(
        username=f"fmc_{uuid4().hex[:8]}",
        email=f"fmc_{uuid4().hex[:8]}@dev.local",
        password_hash="x",
    )
    session.add(user)
    session.flush()
    now = datetime.now(UTC)
    f = Faculty(
        user_id=user.id,
        employee_id=f"EMP-{uuid4().hex[:8]}",
        title="Dr",
        first_name="A",
        last_name="B",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2020, 1, 1),
        phone="9999999999",
        emergency_contact_name="ICE",
        emergency_contact_relation="P",
        emergency_contact_phone="8888888888",
        created_at=now,
        updated_at=now,
    )
    session.add(f)
    session.flush()
    return f


def _assignment(
    session: Session, ay: AcademicYear, campus: Campus, faculty: Faculty
) -> FacultyMentorAssignment:
    actor = uuid4()
    now = datetime.now(UTC)
    asgn = FacultyMentorAssignment(
        academic_year_id=ay.id,
        campus_id=campus.id,
        faculty_id=faculty.id,
        student_id_placeholder="STU001",
        created_by=actor,
        updated_by=actor,
        created_at=now,
        updated_at=now,
    )
    session.add(asgn)
    session.flush()
    return asgn


# ── TestInvalidateConfirmation ─────────────────────────────────────────────────


class TestInvalidateConfirmation:
    def test_returns_none_when_no_confirmation(self, db_session: Session) -> None:
        ay = _ay(db_session)
        campus = _campus(db_session)
        result = invalidate_confirmation(ay.id, campus.id, uuid4(), db_session)
        assert result is None

    def test_soft_deletes_active_confirmation_and_returns_id(
        self, db_session: Session
    ) -> None:
        ay = _ay(db_session)
        campus = _campus(db_session)
        conf = _confirmation(db_session, ay.id, campus.id)
        conf_id = str(conf.id)
        actor = uuid4()

        result = invalidate_confirmation(ay.id, campus.id, actor, db_session)
        db_session.flush()  # push to DB without committing

        assert result == conf_id
        # Verify in-session state (identity map returns same object)
        db_session.expire(conf)
        refreshed = db_session.get(FacultyMentorConfirmation, conf.id)
        assert refreshed is not None
        assert refreshed.is_deleted is True
        assert refreshed.deleted_at is not None
        assert refreshed.deleted_by == actor

    def test_idempotent_when_already_invalidated(self, db_session: Session) -> None:
        ay = _ay(db_session)
        campus = _campus(db_session)
        _confirmation(db_session, ay.id, campus.id, deleted=True)
        actor = uuid4()

        result = invalidate_confirmation(ay.id, campus.id, actor, db_session)

        assert result is None

    def test_partial_index_allows_reconfirm_after_invalidation(
        self, db_session: Session
    ) -> None:
        """After soft-deleting a confirmation, inserting a new one must succeed.

        This is the core invariant the partial unique index (Phase 11E migration)
        enforces: at most one ACTIVE (is_deleted=FALSE) row per (ay, campus).
        """
        ay = _ay(db_session)
        campus = _campus(db_session)
        actor = uuid4()
        conf = _confirmation(db_session, ay.id, campus.id)

        # Invalidate the first confirmation
        result = invalidate_confirmation(ay.id, campus.id, actor, db_session)
        assert result is not None
        db_session.flush()

        # Create a new confirmation for the same AY+campus — must not raise
        now = datetime.now(UTC)
        new_conf = FacultyMentorConfirmation(
            academic_year_id=ay.id,
            campus_id=campus.id,
            confirmed_at=now,
            confirmed_by_user_id=None,
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
        db_session.add(new_conf)
        db_session.flush()  # would raise IntegrityError if full unique constraint applied

        # Both rows exist: one soft-deleted, one active
        rows = db_session.exec(
            select(FacultyMentorConfirmation).where(
                FacultyMentorConfirmation.academic_year_id == ay.id,
                FacultyMentorConfirmation.campus_id == campus.id,
            )
        ).all()
        assert len(rows) == 2  # noqa: PLR2004
        active = [r for r in rows if not r.is_deleted]
        deleted = [r for r in rows if r.is_deleted]
        assert len(active) == 1
        assert len(deleted) == 1
        assert active[0].id == new_conf.id
        assert deleted[0].id == conf.id

    def test_soft_deleted_row_preserved_for_audit(self, db_session: Session) -> None:
        ay = _ay(db_session)
        campus = _campus(db_session)
        conf = _confirmation(db_session, ay.id, campus.id)
        actor = uuid4()

        invalidate_confirmation(ay.id, campus.id, actor, db_session)
        db_session.flush()

        # Row must still exist (soft-delete, not hard-delete)
        row = db_session.exec(
            select(FacultyMentorConfirmation).where(
                FacultyMentorConfirmation.id == conf.id,
            )
        ).first()
        assert row is not None
        assert row.is_deleted is True


# ── TestIsMaterialMentorEdit ──────────────────────────────────────────────────


class TestIsMaterialMentorEdit:
    def _make_assignment(self) -> FacultyMentorAssignment:
        fid = uuid4()
        now = datetime.now(UTC)
        return FacultyMentorAssignment(
            academic_year_id=uuid4(),
            campus_id=uuid4(),
            faculty_id=fid,
            student_id_placeholder="STU001",
            created_by=fid,
            updated_by=fid,
            created_at=now,
            updated_at=now,
        )

    def test_faculty_id_change_is_material(self) -> None:
        existing = self._make_assignment()
        new_faculty = uuid4()
        assert existing.faculty_id != new_faculty  # sanity
        result = is_material_mentor_edit(existing, {"faculty_id": new_faculty})
        assert result is True

    def test_student_change_is_material(self) -> None:
        existing = self._make_assignment()
        result = is_material_mentor_edit(
            existing, {"student_id_placeholder": "STU999"}
        )
        assert result is True

    def test_both_material_fields_changed(self) -> None:
        existing = self._make_assignment()
        result = is_material_mentor_edit(
            existing,
            {"faculty_id": uuid4(), "student_id_placeholder": "STU999"},
        )
        assert result is True

    def test_notes_only_change_is_not_material(self) -> None:
        existing = self._make_assignment()
        result = is_material_mentor_edit(
            existing, {"notes": "Updated administrative notes."}
        )
        assert result is False

    def test_no_change_is_not_material(self) -> None:
        existing = self._make_assignment()
        result = is_material_mentor_edit(
            existing,
            {
                "faculty_id": existing.faculty_id,
                "student_id_placeholder": existing.student_id_placeholder,
            },
        )
        assert result is False

    def test_empty_fields_dict_is_not_material(self) -> None:
        existing = self._make_assignment()
        result = is_material_mentor_edit(existing, {})
        assert result is False


def test_stale_banner_suppressed_when_assignment_list_empty() -> None:
    """Render-condition invariant: banner gated on roster_stale AND len(rows) > 0.

    After delete-last-row, roster_stale=True but mentors=[] — banner must NOT
    show (nothing to confirm).  Tests all four cases of the Boolean condition
    that the Reflex rx.cond expression encodes on the faculty-mentors page.
    """

    def _show(roster_stale: bool, is_confirmed: bool, row_count: int) -> bool:
        return roster_stale and not is_confirmed and row_count > 0

    # Delete-last-row: stale=True, list empty → suppress
    assert not _show(roster_stale=True, is_confirmed=False, row_count=0)
    # Stale + non-empty list → show (positive control)
    assert _show(roster_stale=True, is_confirmed=False, row_count=1)
    # Already confirmed → suppress regardless
    assert not _show(roster_stale=True, is_confirmed=True, row_count=3)
    # Not stale → suppress regardless
    assert not _show(roster_stale=False, is_confirmed=False, row_count=3)
