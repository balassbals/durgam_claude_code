"""Unit tests for BulkImportService CSV validation (§9.2(d), §16)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from durgam.services.bulk_import import (
    validate_course_csv,
    validate_program_csv,
    validate_user_csv,
)


def _role_repo_with(codes: list[str]) -> MagicMock:
    roles = []
    for code in codes:
        r = MagicMock()
        r.code = code
        roles.append(r)
    repo = MagicMock()
    repo.list_active.return_value = roles
    return repo


def _clean_user_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_username.return_value = None
    repo.get_by_email.return_value = None
    return repo


def _csv(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    header = ",".join(rows[0].keys())
    lines = [header] + [",".join(str(v) for v in r.values()) for r in rows]
    return "\n".join(lines).encode()


class TestValidateUserCsv:
    def test_valid_rows_all_pass(self):
        csv_bytes = _csv([
            {"username": "u1", "email": "u1@t.com", "role_code": "STUDENT"},
            {"username": "u2", "email": "u2@t.com", "role_code": "STUDENT"},
        ])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=_clean_user_repo(),
        )
        assert len(valid) == 2
        assert len(invalid) == 0

    def test_missing_required_email_column_fails_entirely(self):
        csv_bytes = b"username,role_code\nu1,STUDENT"
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=_clean_user_repo(),
        )
        # Returns one global error row at row_number=0
        assert len(valid) == 0
        assert len(invalid) == 1
        assert invalid[0].row_number == 0
        assert "email" in invalid[0].error.lower()

    def test_empty_file_returns_global_error(self):
        valid, invalid = validate_user_csv(
            b"",
            role_repo=_role_repo_with([]),
            user_repo=_clean_user_repo(),
        )
        assert len(valid) == 0
        assert len(invalid) == 1

    def test_unknown_role_code_marks_row_invalid(self):
        csv_bytes = _csv([
            {"username": "u1", "email": "u1@t.com", "role_code": "NONEXISTENT"},
        ])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=_clean_user_repo(),
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "NONEXISTENT" in invalid[0].error

    def test_duplicate_username_within_file_marks_second_row_invalid(self):
        csv_bytes = _csv([
            {"username": "u1", "email": "u1@t.com", "role_code": "STUDENT"},
            {"username": "u1", "email": "u2@t.com", "role_code": "STUDENT"},
        ])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=_clean_user_repo(),
        )
        assert len(valid) == 1
        assert len(invalid) == 1
        assert "duplicate" in invalid[0].error.lower()

    def test_existing_username_in_system_marks_row_invalid(self):
        user_repo = _clean_user_repo()
        user_repo.get_by_username.return_value = MagicMock()  # already exists
        csv_bytes = _csv([{"username": "taken", "email": "taken@t.com", "role_code": "STUDENT"}])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=user_repo,
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "already exists" in invalid[0].error

    def test_mixed_valid_and_invalid_rows(self):
        csv_bytes = _csv([
            {"username": "good", "email": "good@t.com", "role_code": "STUDENT"},
            {"username": "", "email": "bad@t.com", "role_code": "STUDENT"},     # missing username
            {"username": "good2", "email": "good2@t.com", "role_code": "STUDENT"},
        ])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=_clean_user_repo(),
        )
        assert len(valid) == 2
        assert len(invalid) == 1


# ── Course CSV validation tests ──────────────────────────────────────────────


def _program_repo_with(codes: dict[str, MagicMock]) -> MagicMock:
    repo = MagicMock()

    def _get_by_code(code):
        return codes.get(code)

    repo.get_by_code.side_effect = _get_by_code
    return repo


def _department_repo_with(codes: dict[str, MagicMock]) -> MagicMock:
    repo = MagicMock()

    def _get_by_code(code):
        return codes.get(code)

    repo.get_by_code.side_effect = _get_by_code
    return repo


def _clean_course_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_code.return_value = None
    return repo


def _make_entity(code: str) -> MagicMock:
    e = MagicMock()
    e.code = code
    e.id = uuid4()
    return e


class TestValidateCourseCsv:
    def test_valid_rows_all_pass(self):
        prog = _make_entity("BSCMATH")
        dept = _make_entity("DMACS")
        csv_bytes = _csv([
            {"code": "MAT101", "name": "Algebra", "program_code": "BSCMATH",
             "department_code": "DMACS", "credits": "4", "lecture": "3",
             "tutorial": "1", "practical": "0", "evaluation": "IE"},
        ])
        valid, invalid = validate_course_csv(
            csv_bytes,
            program_repo=_program_repo_with({"BSCMATH": prog}),
            department_repo=_department_repo_with({"DMACS": dept}),
            course_repo=_clean_course_repo(),
        )
        assert len(valid) == 1
        assert len(invalid) == 0
        assert valid[0].code == "MAT101"
        assert valid[0].program_id == prog.id

    def test_missing_required_column_fails(self):
        csv_bytes = b"code,name,program_code,credits,evaluation\nMAT101,Algebra,BSCMATH,4,IE"
        valid, invalid = validate_course_csv(
            csv_bytes,
            program_repo=MagicMock(),
            department_repo=MagicMock(),
            course_repo=_clean_course_repo(),
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "department_code" in invalid[0].error.lower()

    def test_invalid_program_code_marks_invalid(self):
        dept = _make_entity("DMACS")
        csv_bytes = _csv([
            {"code": "MAT101", "name": "Algebra", "program_code": "NOPROG",
             "department_code": "DMACS", "credits": "4", "lecture": "3",
             "tutorial": "1", "practical": "0", "evaluation": "IE"},
        ])
        valid, invalid = validate_course_csv(
            csv_bytes,
            program_repo=_program_repo_with({}),
            department_repo=_department_repo_with({"DMACS": dept}),
            course_repo=_clean_course_repo(),
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "NOPROG" in invalid[0].error

    def test_invalid_department_code_marks_invalid(self):
        prog = _make_entity("BSCMATH")
        csv_bytes = _csv([
            {"code": "MAT101", "name": "Algebra", "program_code": "BSCMATH",
             "department_code": "NODEPT", "credits": "4", "lecture": "3",
             "tutorial": "1", "practical": "0", "evaluation": "IE"},
        ])
        valid, invalid = validate_course_csv(
            csv_bytes,
            program_repo=_program_repo_with({"BSCMATH": prog}),
            department_repo=_department_repo_with({}),
            course_repo=_clean_course_repo(),
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "NODEPT" in invalid[0].error

    def test_duplicate_code_within_file(self):
        prog = _make_entity("BSCMATH")
        dept = _make_entity("DMACS")
        csv_bytes = _csv([
            {"code": "MAT101", "name": "Algebra I", "program_code": "BSCMATH",
             "department_code": "DMACS", "credits": "4", "lecture": "3",
             "tutorial": "1", "practical": "0", "evaluation": "IE"},
            {"code": "MAT101", "name": "Algebra II", "program_code": "BSCMATH",
             "department_code": "DMACS", "credits": "4", "lecture": "3",
             "tutorial": "1", "practical": "0", "evaluation": "IE"},
        ])
        valid, invalid = validate_course_csv(
            csv_bytes,
            program_repo=_program_repo_with({"BSCMATH": prog}),
            department_repo=_department_repo_with({"DMACS": dept}),
            course_repo=_clean_course_repo(),
        )
        assert len(valid) == 1
        assert len(invalid) == 1
        assert "duplicate" in invalid[0].error.lower()

    def test_existing_code_in_db(self):
        prog = _make_entity("BSCMATH")
        dept = _make_entity("DMACS")
        course_repo = MagicMock()
        course_repo.get_by_code.return_value = MagicMock()  # exists
        csv_bytes = _csv([
            {"code": "MAT101", "name": "Algebra", "program_code": "BSCMATH",
             "department_code": "DMACS", "credits": "4", "lecture": "3",
             "tutorial": "1", "practical": "0", "evaluation": "IE"},
        ])
        valid, invalid = validate_course_csv(
            csv_bytes,
            program_repo=_program_repo_with({"BSCMATH": prog}),
            department_repo=_department_repo_with({"DMACS": dept}),
            course_repo=course_repo,
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "already exists" in invalid[0].error

    def test_invalid_evaluation(self):
        prog = _make_entity("BSCMATH")
        dept = _make_entity("DMACS")
        csv_bytes = _csv([
            {"code": "MAT101", "name": "Algebra", "program_code": "BSCMATH",
             "department_code": "DMACS", "credits": "4", "lecture": "3",
             "tutorial": "1", "practical": "0", "evaluation": "X"},
        ])
        valid, invalid = validate_course_csv(
            csv_bytes,
            program_repo=_program_repo_with({"BSCMATH": prog}),
            department_repo=_department_repo_with({"DMACS": dept}),
            course_repo=_clean_course_repo(),
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "evaluation" in invalid[0].error.lower()

    def test_optional_columns_default_to_zero(self):
        prog = _make_entity("BSCMATH")
        dept = _make_entity("DMACS")
        csv_bytes = _csv([
            {"code": "MAT101", "name": "Algebra", "program_code": "BSCMATH",
             "department_code": "DMACS", "credits": "4", "evaluation": "IE"},
        ])
        valid, invalid = validate_course_csv(
            csv_bytes,
            program_repo=_program_repo_with({"BSCMATH": prog}),
            department_repo=_department_repo_with({"DMACS": dept}),
            course_repo=_clean_course_repo(),
        )
        assert len(valid) == 1
        assert valid[0].lecture == 0
        assert valid[0].tutorial == 0
        assert valid[0].practical == 0


# ── Program CSV validation tests ─────────────────────────────────────────────


class TestValidateProgramCsv:
    def test_valid_rows_all_pass(self):
        dept = _make_entity("DMACS")
        prog_repo = MagicMock()
        prog_repo.get_by_code.return_value = None
        csv_bytes = _csv([
            {"code": "BSCMATH", "name": "BSc Mathematics",
             "department_code": "DMACS", "degree_type": "BSc",
             "duration_years": "3"},
        ])
        valid, invalid = validate_program_csv(
            csv_bytes,
            program_repo=prog_repo,
            department_repo=_department_repo_with({"DMACS": dept}),
        )
        assert len(valid) == 1
        assert len(invalid) == 0
        assert valid[0].code == "BSCMATH"

    def test_missing_required_column_fails(self):
        csv_bytes = b"code,name,degree_type,duration_years\nBSCMATH,BSc Math,BSc,3"
        valid, invalid = validate_program_csv(
            csv_bytes,
            program_repo=MagicMock(),
            department_repo=MagicMock(),
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "department_code" in invalid[0].error.lower()

    def test_invalid_department_code(self):
        prog_repo = MagicMock()
        prog_repo.get_by_code.return_value = None
        csv_bytes = _csv([
            {"code": "BSCMATH", "name": "BSc Math",
             "department_code": "NODEPT", "degree_type": "BSc",
             "duration_years": "3"},
        ])
        valid, invalid = validate_program_csv(
            csv_bytes,
            program_repo=prog_repo,
            department_repo=_department_repo_with({}),
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "NODEPT" in invalid[0].error

    def test_duplicate_code_within_file(self):
        dept = _make_entity("DMACS")
        prog_repo = MagicMock()
        prog_repo.get_by_code.return_value = None
        csv_bytes = _csv([
            {"code": "BSCMATH", "name": "BSc Math I",
             "department_code": "DMACS", "degree_type": "BSc",
             "duration_years": "3"},
            {"code": "BSCMATH", "name": "BSc Math II",
             "department_code": "DMACS", "degree_type": "BSc",
             "duration_years": "3"},
        ])
        valid, invalid = validate_program_csv(
            csv_bytes,
            program_repo=prog_repo,
            department_repo=_department_repo_with({"DMACS": dept}),
        )
        assert len(valid) == 1
        assert len(invalid) == 1
        assert "duplicate" in invalid[0].error.lower()

    def test_zero_duration_marks_invalid(self):
        dept = _make_entity("DMACS")
        prog_repo = MagicMock()
        prog_repo.get_by_code.return_value = None
        csv_bytes = _csv([
            {"code": "BSCMATH", "name": "BSc Math",
             "department_code": "DMACS", "degree_type": "BSc",
             "duration_years": "0"},
        ])
        valid, invalid = validate_program_csv(
            csv_bytes,
            program_repo=prog_repo,
            department_repo=_department_repo_with({"DMACS": dept}),
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "duration_years" in invalid[0].error

    def test_existing_code_in_db(self):
        dept = _make_entity("DMACS")
        prog_repo = MagicMock()
        prog_repo.get_by_code.return_value = MagicMock()  # exists
        csv_bytes = _csv([
            {"code": "BSCMATH", "name": "BSc Math",
             "department_code": "DMACS", "degree_type": "BSc",
             "duration_years": "3"},
        ])
        valid, invalid = validate_program_csv(
            csv_bytes,
            program_repo=prog_repo,
            department_repo=_department_repo_with({"DMACS": dept}),
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "already exists" in invalid[0].error
