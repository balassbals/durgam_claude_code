"""Integration tests for M10 Phase 1B Faculty seed backfill.

Verifies that scripts/seed.py creates the 7 Faculty rows for regular_teaching
users as specified in the Phase 1B backfill table.
"""

from sqlmodel import Session, func, select

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.identity import User

# Expected backfill rows: (username, employee_id, designation_code)
_EXPECTED_ROWS = [
    ("vc_user",             "DEV-FAC-0001", "sr_prof"),
    ("dean_sci",            "DEV-FAC-0002", "prof"),
    ("director_psn",        "DEV-FAC-0003", "prof"),
    ("hod_dmacs",           "DEV-FAC-0004", "prof"),
    ("ahod_dmacs",          "DEV-FAC-0005", "assoc_prof"),
    ("deputy_director_psn", "DEV-FAC-0006", "assoc_prof"),
    ("faculty_user",        "DEV-FAC-0007", "asst_prof_l10"),
]

_EXPECTED_DEPT_CODE = "DMACS"
_EXPECTED_CAMPUS_CODE = "PSN"


class TestFacultySeedBackfill:
    def test_seven_faculty_rows_seeded(self, seeded_session: Session) -> None:
        """All 7 Faculty rows from the Phase 1B backfill table are present."""
        count = seeded_session.exec(
            select(func.count()).select_from(Faculty).where(
                Faculty.is_deleted == False,  # noqa: E712
                Faculty.employee_id.like("DEV-FAC-%"),
            )
        ).one()
        assert count == 7, (
            f"Expected 7 seed-marker Faculty rows (DEV-FAC-%), got {count}"
        )

    def test_each_faculty_row_maps_correctly(self, seeded_session: Session) -> None:
        """Each Faculty row has the correct employee_id, designation, dept, campus."""
        # Build lookup maps once.
        users = {
            u.username: u.id
            for u in seeded_session.exec(select(User)).all()
        }
        designations = {
            d.code: d.id
            for d in seeded_session.exec(
                select(Designation).where(Designation.is_deleted == False)  # noqa: E712
            ).all()
        }
        dept_row = seeded_session.exec(
            select(Department).where(Department.code == _EXPECTED_DEPT_CODE)
        ).first()
        assert dept_row is not None, f"Department {_EXPECTED_DEPT_CODE!r} not found"

        campus_row = seeded_session.exec(
            select(Campus).where(Campus.code == _EXPECTED_CAMPUS_CODE)
        ).first()
        assert campus_row is not None, f"Campus {_EXPECTED_CAMPUS_CODE!r} not found"

        for username, employee_id, desig_code in _EXPECTED_ROWS:
            fac = seeded_session.exec(
                select(Faculty).where(
                    Faculty.employee_id == employee_id,
                    Faculty.is_deleted == False,  # noqa: E712
                )
            ).first()
            assert fac is not None, (
                f"Faculty row for employee_id={employee_id!r} (username={username!r}) "
                f"not found"
            )
            assert fac.user_id == users[username], (
                f"Faculty {employee_id}: user_id mismatch — "
                f"expected user {username!r}"
            )
            assert fac.designation_id == designations[desig_code], (
                f"Faculty {employee_id}: designation_id mismatch — "
                f"expected {desig_code!r}"
            )
            assert fac.department_id == dept_row.id, (
                f"Faculty {employee_id}: department_id should be DMACS"
            )
            assert fac.campus_id == campus_row.id, (
                f"Faculty {employee_id}: campus_id should be PSN"
            )

    def test_seed_idempotent_faculty_count(self, db_engine) -> None:
        """Re-running seed leaves Faculty count unchanged (idempotent via uq_faculties_employee_id)."""
        from scripts.seed import seed

        with Session(db_engine) as session:
            seed(session)
            session.commit()

        with Session(db_engine) as session:
            count1 = session.exec(
                select(func.count()).select_from(Faculty).where(
                    Faculty.is_deleted == False,  # noqa: E712
                    Faculty.employee_id.like("DEV-FAC-%"),
                )
            ).one()

        with Session(db_engine) as session:
            seed(session)
            session.commit()

        with Session(db_engine) as session:
            count2 = session.exec(
                select(func.count()).select_from(Faculty).where(
                    Faculty.is_deleted == False,  # noqa: E712
                    Faculty.employee_id.like("DEV-FAC-%"),
                )
            ).one()

        assert count1 == count2 == 7, (
            f"Seed-marker Faculty count not idempotent: "
            f"run1={count1}, run2={count2} (expected 7)"
        )
