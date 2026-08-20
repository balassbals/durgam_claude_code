"""Integration tests for Phase 12 — Faculty bulk CSV import service.

Covers:
  - validate_faculty_csv: schema checks, per-row validation, cross-DB lookups,
    within-file duplicate detection, encoding handling.
  - commit_faculty_import: Faculty row creation, User.gender backfill,
    late-error handling.
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
from durgam.models.identity import User
from durgam.models.school import School
from durgam.repositories.campus import CampusRepository
from durgam.repositories.department import DepartmentRepository
from durgam.repositories.designation import DesignationRepository
from durgam.repositories.faculty import FacultyRepository
from durgam.repositories.user import UserRepository
from durgam.services.bulk_import import (
    commit_faculty_import,
    validate_faculty_csv,
)


# ── Shared helpers ────────────────────────────────────────────────────────────


def _campus(session: Session, code: str | None = None) -> Campus:
    c = Campus(code=code or f"C{uuid4().hex[:8]}", name="Campus", address="A")
    session.add(c)
    session.flush()
    return c


def _dept(session: Session, campus: Campus) -> Department:
    s = School(code=f"S{uuid4().hex[:8]}", name="School")
    session.add(s)
    session.flush()
    d = Department(
        code=f"D{uuid4().hex[:8]}", name="Dept",
        school_id=s.id, main_campus_id=campus.id,
    )
    session.add(d)
    session.flush()
    return d


def _desig(session: Session, code: str | None = None) -> Designation:
    dg = Designation(code=code or f"DG{uuid4().hex[:8]}", name="Prof", rank=50)
    session.add(dg)
    session.flush()
    return dg


def _user(
    session: Session,
    *,
    username: str | None = None,
    employee_type: str = "regular_teaching",
) -> User:
    u = User(
        username=username or f"fbi_{uuid4().hex[:8]}",
        email=f"fbi_{uuid4().hex[:8]}@dev.local",
        password_hash="x",
        employee_type=employee_type,
    )
    session.add(u)
    session.flush()
    return u


def _faculty(session: Session, user: User, campus: Campus, dept: Department,
             desig: Designation, employee_id: str | None = None) -> Faculty:
    now = datetime.now(UTC)
    f = Faculty(
        user_id=user.id,
        employee_id=employee_id or f"EMP-{uuid4().hex[:8]}",
        title="Dr", first_name="A", last_name="B",
        designation_id=desig.id, department_id=dept.id, campus_id=campus.id,
        joining_date=date(2020, 1, 1), phone="9", emergency_contact_name="E",
        emergency_contact_relation="P", emergency_contact_phone="9",
        created_at=now, updated_at=now,
    )
    session.add(f)
    session.flush()
    return f


def _repos(session: Session):
    return dict(
        user_repo=UserRepository(session),
        faculty_repo=FacultyRepository(session),
        campus_repo=CampusRepository(session),
        dept_repo=DepartmentRepository(session),
        designation_repo=DesignationRepository(session),
    )


def _csv(*rows: str, header: bool = True) -> bytes:
    lines = []
    if header:
        lines.append(
            "employee_id,username,first_name,last_name,"
            "designation_code,dept_code,campus_code,joining_date,gender"
        )
    lines.extend(rows)
    return "\n".join(lines).encode("utf-8")


def _csv_with_email(*rows: str) -> bytes:
    """Like _csv but includes an 'email' column in the header."""
    lines = [
        "employee_id,username,first_name,last_name,"
        "designation_code,dept_code,campus_code,joining_date,gender,email"
    ]
    lines.extend(rows)
    return "\n".join(lines).encode("utf-8")


# ── TestValidateFacultyCSV ────────────────────────────────────────────────────


class TestValidateFacultyCSV:
    def test_valid_minimal_row(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user = _user(db_session)

        content = _csv(
            f"EMP-{uuid4().hex[:8]},{user.username},Alice,Smith,"
            f"{desig.code},{dept.code},{campus.code},2022-01-15,F"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))

        assert len(valid) == 1
        assert len(invalid) == 0
        assert valid[0].first_name == "Alice"
        assert valid[0].gender == "F"
        assert valid[0].user_id == user.id

    def test_valid_row_with_optional_fields(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user = _user(db_session)
        emp_id = f"EMP-{uuid4().hex[:8]}"

        header = (
            "employee_id,username,first_name,last_name,"
            "designation_code,dept_code,campus_code,joining_date,gender,"
            "middle_name,title,phone,is_phd,orcid"
        )
        row = (
            f"{emp_id},{user.username},Alice,Smith,"
            f"{desig.code},{dept.code},{campus.code},2022-01-15,F,"
            f"Marie,Dr,9999999999,true,0000-0001-2345-6789"
        )
        content = (header + "\n" + row).encode("utf-8")
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))

        assert len(valid) == 1
        assert invalid == []
        v = valid[0]
        assert v.middle_name == "Marie"
        assert v.title == "Dr"
        assert v.phone == "9999999999"
        assert v.is_phd is True
        assert v.orcid == "0000-0001-2345-6789"

    def test_missing_required_column_returns_file_error(self, db_session: Session) -> None:
        # missing 'gender' column
        content = (
            "employee_id,username,first_name,last_name,"
            "designation_code,dept_code,campus_code,joining_date\n"
            "EMP001,alice,Alice,Smith,PROF,DMACS,MAIN,2022-01-01"
        ).encode("utf-8")
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))

        assert valid == []
        assert len(invalid) == 1
        assert invalid[0].row_number == 0
        assert "gender" in invalid[0].error

    def test_empty_file_returns_file_error(self, db_session: Session) -> None:
        valid, invalid = validate_faculty_csv(b"", **_repos(db_session))
        assert valid == []
        assert len(invalid) == 1
        assert "empty" in invalid[0].error.lower()

    def test_header_only_no_rows(self, db_session: Session) -> None:
        content = _csv()
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert invalid == []

    def test_invalid_gender_value(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user = _user(db_session)
        content = _csv(
            f"EMP-{uuid4().hex[:8]},{user.username},A,B,"
            f"{desig.code},{dept.code},{campus.code},2020-01-01,X"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert len(invalid) == 1
        assert "M, F, or O" in invalid[0].error

    def test_invalid_joining_date_format(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user = _user(db_session)
        content = _csv(
            f"EMP-{uuid4().hex[:8]},{user.username},A,B,"
            f"{desig.code},{dept.code},{campus.code},01-Jan-2020,M"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert "YYYY-MM-DD" in invalid[0].error

    def test_unknown_campus_code(self, db_session: Session) -> None:
        dept = _dept(db_session, _campus(db_session))
        desig = _desig(db_session)
        user = _user(db_session)
        content = _csv(
            f"EMP-{uuid4().hex[:8]},{user.username},A,B,"
            f"{desig.code},{dept.code},NOSUCHCAMPUS,2020-01-01,M"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert "campus_code" in invalid[0].error

    def test_unknown_dept_code(self, db_session: Session) -> None:
        campus = _campus(db_session)
        desig = _desig(db_session)
        user = _user(db_session)
        content = _csv(
            f"EMP-{uuid4().hex[:8]},{user.username},A,B,"
            f"{desig.code},NODEPT,{campus.code},2020-01-01,M"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert "dept_code" in invalid[0].error

    def test_unknown_designation_code(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        user = _user(db_session)
        content = _csv(
            f"EMP-{uuid4().hex[:8]},{user.username},A,B,"
            f"NODESIG,{dept.code},{campus.code},2020-01-01,M"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert "designation_code" in invalid[0].error

    def test_username_not_found_without_email_is_rejected(self, db_session: Session) -> None:
        """No email column → rejected; user must supply email for auto-create."""
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        content = _csv(
            f"EMP-{uuid4().hex[:8]},ghost_user_xyz,A,B,"
            f"{desig.code},{dept.code},{campus.code},2020-01-01,M"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert "not found" in invalid[0].error
        assert "email" in invalid[0].error

    def test_username_not_found_with_valid_email_sets_will_create_user(
        self, db_session: Session
    ) -> None:
        """New username + valid email → accepted with will_create_user=True."""
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        new_username = f"newuser_{uuid4().hex[:8]}"
        new_email = f"new_{uuid4().hex[:8]}@dev.local"
        content = _csv_with_email(
            f"EMP-{uuid4().hex[:8]},{new_username},Alice,Smith,"
            f"{desig.code},{dept.code},{campus.code},2022-01-15,F,{new_email}"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert invalid == []
        assert len(valid) == 1
        assert valid[0].will_create_user is True
        assert valid[0].email == new_email
        assert valid[0].user_id is None

    def test_username_not_found_with_invalid_email_is_rejected(
        self, db_session: Session
    ) -> None:
        """New username + malformed email (no @) → rejected."""
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        content = _csv_with_email(
            f"EMP-{uuid4().hex[:8]},ghost_xyz,A,B,"
            f"{desig.code},{dept.code},{campus.code},2020-01-01,M,not-an-email"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert "email" in invalid[0].error

    def test_username_not_found_email_already_registered_is_rejected(
        self, db_session: Session
    ) -> None:
        """New username but email already taken → rejected at validate time."""
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        existing = _user(db_session)  # existing user owns the email
        new_username = f"brandnew_{uuid4().hex[:8]}"
        content = _csv_with_email(
            f"EMP-{uuid4().hex[:8]},{new_username},A,B,"
            f"{desig.code},{dept.code},{campus.code},2020-01-01,M,{existing.email}"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert "already registered" in invalid[0].error

    def test_username_wrong_employee_type(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        non_teaching = _user(db_session, employee_type="regular_non_teaching")
        content = _csv(
            f"EMP-{uuid4().hex[:8]},{non_teaching.username},A,B,"
            f"{desig.code},{dept.code},{campus.code},2020-01-01,M"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert "regular_teaching" in invalid[0].error

    def test_user_already_has_faculty_record(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user = _user(db_session)
        _faculty(db_session, user, campus, dept, desig)

        content = _csv(
            f"EMP-{uuid4().hex[:8]},{user.username},A,B,"
            f"{desig.code},{dept.code},{campus.code},2020-01-01,M"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert "already has a faculty record" in invalid[0].error

    def test_employee_id_already_in_use(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user1 = _user(db_session)
        user2 = _user(db_session)
        existing_emp_id = f"EMP-{uuid4().hex[:8]}"
        _faculty(db_session, user1, campus, dept, desig, employee_id=existing_emp_id)

        content = _csv(
            f"{existing_emp_id},{user2.username},A,B,"
            f"{desig.code},{dept.code},{campus.code},2020-01-01,M"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert valid == []
        assert "already in use" in invalid[0].error

    def test_duplicate_username_within_file(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user = _user(db_session)

        row = (
            f"EMP-{uuid4().hex[:8]},{user.username},A,B,"
            f"{desig.code},{dept.code},{campus.code},2020-01-01,M"
        )
        dup_row = (
            f"EMP-{uuid4().hex[:8]},{user.username},C,D,"
            f"{desig.code},{dept.code},{campus.code},2020-01-01,F"
        )
        content = _csv(row, dup_row)
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))

        assert len(valid) == 1
        assert len(invalid) == 1
        assert "duplicate username" in invalid[0].error

    def test_duplicate_employee_id_within_file(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user1 = _user(db_session)
        user2 = _user(db_session)
        shared_emp_id = f"EMP-{uuid4().hex[:8]}"

        row1 = (
            f"{shared_emp_id},{user1.username},A,B,"
            f"{desig.code},{dept.code},{campus.code},2020-01-01,M"
        )
        row2 = (
            f"{shared_emp_id},{user2.username},C,D,"
            f"{desig.code},{dept.code},{campus.code},2021-01-01,F"
        )
        content = _csv(row1, row2)
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))

        assert len(valid) == 1
        assert len(invalid) == 1
        assert "duplicate employee_id" in invalid[0].error

    def test_bom_encoding_handled(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user = _user(db_session)
        emp_id = f"EMP-{uuid4().hex[:8]}"
        # utf-8-sig adds the BOM prefix — simulates an Excel CSV export
        content = (
            "employee_id,username,first_name,last_name,"
            "designation_code,dept_code,campus_code,joining_date,gender\n"
            f"{emp_id},{user.username},Alice,Smith,"
            f"{desig.code},{dept.code},{campus.code},2022-01-15,F"
        ).encode("utf-8-sig")
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))
        assert len(valid) == 1
        assert invalid == []

    def test_row_cap_enforced(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        rows = []
        for _ in range(3):
            user = _user(db_session)
            rows.append(
                f"EMP-{uuid4().hex[:8]},{user.username},A,B,"
                f"{desig.code},{dept.code},{campus.code},2020-01-01,M"
            )
        content = _csv(*rows)
        # cap of 2 — third row triggers cap error
        valid, invalid = validate_faculty_csv(content, max_rows=2, **_repos(db_session))
        assert len(valid) == 2
        assert len(invalid) == 1
        assert "cap exceeded" in invalid[0].error

    def test_mixed_valid_and_invalid_rows(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user = _user(db_session)

        good = (
            f"EMP-{uuid4().hex[:8]},{user.username},Alice,Smith,"
            f"{desig.code},{dept.code},{campus.code},2022-01-15,F"
        )
        bad = "EMP-BAD,ghost_xyz,B,B,NOCODE,NODEPT,NOCAMPUS,bad-date,Z"
        content = _csv(good, bad)
        valid, invalid = validate_faculty_csv(content, **_repos(db_session))

        assert len(valid) == 1
        assert len(invalid) == 1


# ── TestCommitFacultyImport ───────────────────────────────────────────────────


class TestCommitFacultyImport:
    def _make_valid_row(self, session, *, campus=None, dept=None, desig=None,
                        user=None) -> tuple:
        if campus is None:
            campus = _campus(session)
        if dept is None:
            dept = _dept(session, campus)
        if desig is None:
            desig = _desig(session)
        if user is None:
            user = _user(session)
        emp_id = f"EMP-{uuid4().hex[:8]}"

        content = _csv(
            f"{emp_id},{user.username},Test,User,"
            f"{desig.code},{dept.code},{campus.code},2023-06-01,M"
        )
        valid, _ = validate_faculty_csv(content, **_repos(session))
        assert len(valid) == 1, "fixture: expected 1 valid row"
        return valid[0], user

    def test_commit_creates_faculty_row(self, db_session: Session) -> None:
        vrow, user = self._make_valid_row(db_session)
        actor = uuid4()
        result = commit_faculty_import(
            [vrow], actor,
            faculty_repo=FacultyRepository(db_session),
            user_repo=UserRepository(db_session),
        )
        assert result.success_count == 1
        assert result.errors == []

        faculty = FacultyRepository(db_session).get_by_user_id(user.id)
        assert faculty is not None
        assert faculty.employee_id == vrow.employee_id
        assert faculty.first_name == "Test"
        assert faculty.last_name == "User"

    def test_commit_sets_user_gender(self, db_session: Session) -> None:
        vrow, user = self._make_valid_row(db_session)
        assert user.gender is None or user.gender != vrow.gender

        commit_faculty_import(
            [vrow], uuid4(),
            faculty_repo=FacultyRepository(db_session),
            user_repo=UserRepository(db_session),
        )
        db_session.expire(user)
        db_session.refresh(user)
        assert user.gender == "M"

    def test_commit_sets_optional_fields(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user = _user(db_session)
        emp_id = f"EMP-{uuid4().hex[:8]}"

        header = (
            "employee_id,username,first_name,last_name,"
            "designation_code,dept_code,campus_code,joining_date,gender,"
            "title,phone,orcid"
        )
        row = (
            f"{emp_id},{user.username},Test,User,"
            f"{desig.code},{dept.code},{campus.code},2023-06-01,F,"
            "Dr,9876543210,0000-0001-9999-0000"
        )
        content = (header + "\n" + row).encode("utf-8")
        valid, _ = validate_faculty_csv(content, **_repos(db_session))
        assert len(valid) == 1

        commit_faculty_import(
            valid, uuid4(),
            faculty_repo=FacultyRepository(db_session),
            user_repo=UserRepository(db_session),
        )
        faculty = FacultyRepository(db_session).get_by_user_id(user.id)
        assert faculty is not None
        assert faculty.title == "Dr"
        assert faculty.phone == "9876543210"
        assert faculty.orcid == "0000-0001-9999-0000"

    def test_commit_is_phd_fields(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        user = _user(db_session)
        emp_id = f"EMP-{uuid4().hex[:8]}"

        header = (
            "employee_id,username,first_name,last_name,"
            "designation_code,dept_code,campus_code,joining_date,gender,"
            "is_phd,phd_thesis_title,phd_year"
        )
        row = (
            f"{emp_id},{user.username},Test,User,"
            f"{desig.code},{dept.code},{campus.code},2023-06-01,M,"
            "true,My Thesis Title,2015"
        )
        content = (header + "\n" + row).encode("utf-8")
        valid, _ = validate_faculty_csv(content, **_repos(db_session))
        assert len(valid) == 1

        commit_faculty_import(
            valid, uuid4(),
            faculty_repo=FacultyRepository(db_session),
            user_repo=UserRepository(db_session),
        )
        faculty = FacultyRepository(db_session).get_by_user_id(user.id)
        assert faculty is not None
        assert faculty.is_phd is True
        assert faculty.phd_thesis_title == "My Thesis Title"
        assert faculty.phd_year == 2015  # noqa: PLR2004

    def test_commit_returns_correct_success_count(self, db_session: Session) -> None:
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        desig = _desig(db_session)
        rows = []
        for _ in range(3):
            user = _user(db_session)
            emp_id = f"EMP-{uuid4().hex[:8]}"
            content = _csv(
                f"{emp_id},{user.username},A,B,"
                f"{desig.code},{dept.code},{campus.code},2020-01-01,M"
            )
            valid, _ = validate_faculty_csv(content, **_repos(db_session))
            rows.extend(valid)

        result = commit_faculty_import(
            rows, uuid4(),
            faculty_repo=FacultyRepository(db_session),
            user_repo=UserRepository(db_session),
        )
        assert result.success_count == 3  # noqa: PLR2004
        assert result.errors == []

    def test_commit_late_error_on_duplicate_user_id(self, db_session: Session) -> None:
        """Race condition: faculty record created between validate and commit."""
        vrow, user = self._make_valid_row(db_session)
        # Simulate race: create the faculty record before commit runs
        _faculty(db_session, user, _campus(db_session), _dept(db_session, _campus(db_session)),
                 _desig(db_session), employee_id=f"EMP-RACE-{uuid4().hex[:8]}")

        result = commit_faculty_import(
            [vrow], uuid4(),
            faculty_repo=FacultyRepository(db_session),
            user_repo=UserRepository(db_session),
        )
        # Either user_id unique constraint or employee_id conflict causes late error
        assert result.success_count == 0
        assert len(result.errors) == 1

    def test_commit_empty_list_returns_zero(self, db_session: Session) -> None:
        result = commit_faculty_import(
            [], uuid4(),
            faculty_repo=FacultyRepository(db_session),
            user_repo=UserRepository(db_session),
        )
        assert result.success_count == 0
        assert result.errors == []

    def _make_will_create_row(self, session) -> tuple:
        """Return a ValidFacultyRow with will_create_user=True (new username path)."""
        campus = _campus(session)
        dept = _dept(session, campus)
        desig = _desig(session)
        new_username = f"autocreate_{uuid4().hex[:8]}"
        new_email = f"ac_{uuid4().hex[:8]}@dev.local"
        content = _csv_with_email(
            f"EMP-{uuid4().hex[:8]},{new_username},Auto,Create,"
            f"{desig.code},{dept.code},{campus.code},2024-01-01,M,{new_email}"
        )
        valid, invalid = validate_faculty_csv(content, **_repos(session))
        assert invalid == [], f"unexpected validation errors: {invalid}"
        assert len(valid) == 1
        assert valid[0].will_create_user is True
        return valid[0], new_username, new_email

    def test_commit_auto_creates_user_and_faculty(self, db_session: Session) -> None:
        """will_create_user=True path: User + Faculty rows both created."""
        vrow, username, email = self._make_will_create_row(db_session)
        actor = uuid4()
        result = commit_faculty_import(
            [vrow], actor,
            faculty_repo=FacultyRepository(db_session),
            user_repo=UserRepository(db_session),
        )
        assert result.success_count == 1
        assert result.errors == []

        user = UserRepository(db_session).get_by_username(username)
        assert user is not None
        faculty = FacultyRepository(db_session).get_by_user_id(user.id)
        assert faculty is not None
        assert faculty.employee_id == vrow.employee_id

    def test_auto_created_user_employee_type_is_regular_teaching(
        self, db_session: Session
    ) -> None:
        """Auto-created user must have employee_type='regular_teaching', not the default."""
        vrow, username, _ = self._make_will_create_row(db_session)
        commit_faculty_import(
            [vrow], uuid4(),
            faculty_repo=FacultyRepository(db_session),
            user_repo=UserRepository(db_session),
        )
        user = UserRepository(db_session).get_by_username(username)
        assert user is not None
        assert user.employee_type == "regular_teaching"

    def test_auto_created_user_must_change_password_is_true(
        self, db_session: Session
    ) -> None:
        """Auto-created user must be forced to set a new password on first login."""
        vrow, username, _ = self._make_will_create_row(db_session)
        commit_faculty_import(
            [vrow], uuid4(),
            faculty_repo=FacultyRepository(db_session),
            user_repo=UserRepository(db_session),
        )
        user = UserRepository(db_session).get_by_username(username)
        assert user is not None
        assert user.must_change_password is True

    def test_auto_created_user_password_hash_is_non_empty(
        self, db_session: Session
    ) -> None:
        """Auto-created user must have a real hashed password, not empty or placeholder."""
        vrow, username, _ = self._make_will_create_row(db_session)
        commit_faculty_import(
            [vrow], uuid4(),
            faculty_repo=FacultyRepository(db_session),
            user_repo=UserRepository(db_session),
        )
        user = UserRepository(db_session).get_by_username(username)
        assert user is not None
        assert user.password_hash
        assert len(user.password_hash) > 20  # noqa: PLR2004
