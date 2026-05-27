"""BulkImportService — two-stage CSV import for users, courses, programs (§9.2(d), §16).

Stage 1: validate_*_csv — parse bytes, check schema, validate each row.
Stage 2: commit_*_import — insert valid rows, return (success_count, errors).

Errors do not commit the row (per §16 risk note). Valid rows commit individually.
Faculty and student bulk import deferred to M10/M12 (models don't exist yet).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from uuid import UUID

import structlog

from durgam.repositories.role import RoleRepository
from durgam.repositories.user import UserRepository
from durgam.repositories.user_role import UserRoleRepository
from durgam.services.password import generate_temp_password, hash_password

log = structlog.get_logger(__name__)

_REQUIRED_COLS = {"username", "email", "role_code"}
_OPTIONAL_COLS = {"full_name"}  # optional; stored on User.full_name (added M2 close-out)
_ALL_COLS = _REQUIRED_COLS | _OPTIONAL_COLS


@dataclass
class ValidRow:
    row_number: int
    username: str
    email: str
    role_code: str
    full_name: str = ""


@dataclass
class InvalidRow:
    row_number: int
    raw: dict
    error: str


@dataclass
class ImportResult:
    success_count: int
    errors: list[InvalidRow] = field(default_factory=list)


def validate_user_csv(
    file_bytes: bytes,
    *,
    role_repo: RoleRepository,
    user_repo: UserRepository,
    max_preview_rows: int = 100,
) -> tuple[list[ValidRow], list[InvalidRow]]:
    """Parse a CSV and validate each row against the user import schema.

    Returns (valid_rows, invalid_rows). Only the first max_preview_rows are
    validated and returned (preview cap); the rest are ignored.

    CSV schema: username, email, role_code (required); full_name (optional).
    Unknown extra columns are accepted and silently ignored.
    """
    try:
        text = file_bytes.decode("utf-8-sig")  # handle BOM from Excel exports
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], [InvalidRow(row_number=0, raw={}, error="File appears to be empty.")]

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = _REQUIRED_COLS - headers
    if missing:
        return [], [
            InvalidRow(
                row_number=0,
                raw={},
                error=f"Missing required columns: {', '.join(sorted(missing))}.",
            )
        ]

    # Build a set of valid role codes for fast lookup.
    valid_roles = {r.code for r in role_repo.list_active()}

    valid: list[ValidRow] = []
    invalid: list[InvalidRow] = []
    seen_usernames: set[str] = set()
    seen_emails: set[str] = set()

    for i, raw_row in enumerate(reader, start=2):  # row 1 is the header
        if i - 1 > max_preview_rows:
            break
        row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}

        username = row.get("username", "")
        email = row.get("email", "").lower()
        role_code = row.get("role_code", "").upper()

        errors_for_row = []

        if not username:
            errors_for_row.append("username is required")
        if not email or "@" not in email:
            errors_for_row.append("valid email is required")
        if not role_code:
            errors_for_row.append("role_code is required")
        elif role_code not in valid_roles:
            errors_for_row.append(f"unknown role_code '{role_code}'")

        if username and username in seen_usernames:
            errors_for_row.append(f"duplicate username '{username}' within this file")
        if email and email in seen_emails:
            errors_for_row.append(f"duplicate email '{email}' within this file")

        if not errors_for_row and username and user_repo.get_by_username(username) is not None:
            errors_for_row.append(f"username '{username}' already exists in the system")
        if not errors_for_row and email and user_repo.get_by_email(email) is not None:
            errors_for_row.append(f"email '{email}' already registered in the system")

        if errors_for_row:
            invalid.append(InvalidRow(row_number=i, raw=dict(row), error="; ".join(errors_for_row)))
        else:
            seen_usernames.add(username)
            seen_emails.add(email)
            full_name = row.get("full_name", "")
            valid.append(ValidRow(row_number=i, username=username, email=email,
                                  role_code=role_code, full_name=full_name))

    return valid, invalid


def commit_user_import(
    valid_rows: list[ValidRow],
    actor_id: UUID,
    *,
    user_repo: UserRepository,
    user_role_repo: UserRoleRepository,
    role_repo: RoleRepository,
) -> ImportResult:
    """Commit valid rows from a prior validate_user_csv call.

    Each row is committed individually (partial success per §16). If a row fails
    at commit time (e.g. race condition on username), it is added to errors.
    Returns ImportResult with success_count and any late errors.
    """
    roles = {r.code: r for r in role_repo.list_active()}
    success = 0
    late_errors: list[InvalidRow] = []

    for vrow in valid_rows:
        try:
            temp_pw = generate_temp_password()
            user = user_repo.create(
                username=vrow.username,
                email=vrow.email,
                password_hash=hash_password(temp_pw),
                actor_id=actor_id,
                must_change_password=True,
                full_name=vrow.full_name or None,
            )
            role = roles.get(vrow.role_code)
            if role:
                user_role_repo.replace_user_roles(user.id, [role.id], actor_id)
            success += 1
            log.info("bulk_import_user_created", username=vrow.username, actor=str(actor_id))
        except Exception as exc:
            log.warning("bulk_import_row_failed", row=vrow.row_number, error=str(exc))
            late_errors.append(InvalidRow(
                row_number=vrow.row_number,
                raw={"username": vrow.username, "email": vrow.email, "role_code": vrow.role_code},
                error=str(exc),
            ))

    return ImportResult(success_count=success, errors=late_errors)


# ── Course CSV import ────────────────────────────────────────────────────────

_COURSE_REQUIRED_COLS = {"code", "name", "program_code", "department_code", "credits", "evaluation"}
_COURSE_OPTIONAL_COLS = {"lecture", "tutorial", "practical"}


@dataclass
class ValidCourseRow:
    row_number: int
    code: str
    name: str
    program_id: UUID
    program_code: str
    department_id: UUID
    department_code: str
    credits: int
    lecture: int
    tutorial: int
    practical: int
    evaluation: str


def validate_course_csv(
    file_bytes: bytes,
    *,
    program_repo: "ProgramRepository",
    department_repo: "DepartmentRepository",
    course_repo: "CourseRepository",
    max_preview_rows: int = 100,
) -> tuple[list[ValidCourseRow], list[InvalidRow]]:
    from durgam.repositories.course import CourseRepository as _CR
    from durgam.repositories.department import DepartmentRepository as _DR
    from durgam.repositories.program import ProgramRepository as _PR

    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], [InvalidRow(row_number=0, raw={}, error="File appears to be empty.")]

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = _COURSE_REQUIRED_COLS - headers
    if missing:
        return [], [
            InvalidRow(row_number=0, raw={}, error=f"Missing required columns: {', '.join(sorted(missing))}.")
        ]

    valid: list[ValidCourseRow] = []
    invalid: list[InvalidRow] = []
    seen_codes: set[str] = set()

    for i, raw_row in enumerate(reader, start=2):
        if i - 1 > max_preview_rows:
            break
        row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}
        errors_for_row: list[str] = []

        code = row.get("code", "").upper()
        name = row.get("name", "")
        program_code = row.get("program_code", "").upper()
        department_code = row.get("department_code", "").upper()
        credits_str = row.get("credits", "")
        evaluation = row.get("evaluation", "").upper()
        lecture_str = row.get("lecture", "0")
        tutorial_str = row.get("tutorial", "0")
        practical_str = row.get("practical", "0")

        if not code:
            errors_for_row.append("code is required")
        if not name:
            errors_for_row.append("name is required")
        if not program_code:
            errors_for_row.append("program_code is required")
        if not department_code:
            errors_for_row.append("department_code is required")
        if evaluation not in ("I", "E", "IE"):
            errors_for_row.append("evaluation must be one of: I, E, IE")

        credits = _parse_int(credits_str, "credits", errors_for_row, min_val=0)
        lecture = _parse_int(lecture_str, "lecture", errors_for_row, min_val=0)
        tutorial = _parse_int(tutorial_str, "tutorial", errors_for_row, min_val=0)
        practical = _parse_int(practical_str, "practical", errors_for_row, min_val=0)

        program_id: UUID | None = None
        department_id: UUID | None = None

        if not errors_for_row and program_code:
            prog = program_repo.get_by_code(program_code)
            if prog is None:
                errors_for_row.append(f"program_code '{program_code}' not found")
            else:
                program_id = prog.id

        if not errors_for_row and department_code:
            dept = department_repo.get_by_code(department_code)
            if dept is None:
                errors_for_row.append(f"department_code '{department_code}' not found")
            else:
                department_id = dept.id

        if code and code in seen_codes:
            errors_for_row.append(f"duplicate code '{code}' within this file")

        if not errors_for_row and code and course_repo.get_by_code(code) is not None:
            errors_for_row.append(f"code '{code}' already exists in the system")

        if errors_for_row:
            invalid.append(InvalidRow(row_number=i, raw=dict(row), error="; ".join(errors_for_row)))
        else:
            seen_codes.add(code)
            valid.append(ValidCourseRow(
                row_number=i, code=code, name=name,
                program_id=program_id,  # type: ignore[arg-type]
                program_code=program_code,
                department_id=department_id,  # type: ignore[arg-type]
                department_code=department_code,
                credits=credits, lecture=lecture, tutorial=tutorial,
                practical=practical, evaluation=evaluation,
            ))

    return valid, invalid


def commit_course_import(
    valid_rows: list[ValidCourseRow],
    actor_id: UUID,
    *,
    course_repo: "CourseRepository",
    program_repo: "ProgramRepository",
    department_repo: "DepartmentRepository",
) -> ImportResult:
    from durgam.services.course import CourseService

    svc = CourseService(course_repo=course_repo)
    success = 0
    late_errors: list[InvalidRow] = []

    for vrow in valid_rows:
        try:
            svc.create(
                code=vrow.code, name=vrow.name,
                program_id=vrow.program_id, department_id=vrow.department_id,
                credits=vrow.credits, lecture=vrow.lecture,
                tutorial=vrow.tutorial, practical=vrow.practical,
                evaluation=vrow.evaluation, actor_id=actor_id,
            )
            success += 1
            log.info("bulk_import_course_created", code=vrow.code, actor=str(actor_id))
        except Exception as exc:
            log.warning("bulk_import_course_failed", row=vrow.row_number, error=str(exc))
            late_errors.append(InvalidRow(
                row_number=vrow.row_number,
                raw={"code": vrow.code, "name": vrow.name},
                error=str(exc),
            ))

    return ImportResult(success_count=success, errors=late_errors)


# ── Program CSV import ───────────────────────────────────────────────────────

_PROGRAM_REQUIRED_COLS = {"code", "name", "department_code", "degree_type", "duration_years"}


@dataclass
class ValidProgramRow:
    row_number: int
    code: str
    name: str
    department_id: UUID
    department_code: str
    degree_type: str
    duration_years: int


def validate_program_csv(
    file_bytes: bytes,
    *,
    program_repo: "ProgramRepository",
    department_repo: "DepartmentRepository",
    max_preview_rows: int = 100,
) -> tuple[list[ValidProgramRow], list[InvalidRow]]:
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], [InvalidRow(row_number=0, raw={}, error="File appears to be empty.")]

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = _PROGRAM_REQUIRED_COLS - headers
    if missing:
        return [], [
            InvalidRow(row_number=0, raw={}, error=f"Missing required columns: {', '.join(sorted(missing))}.")
        ]

    valid: list[ValidProgramRow] = []
    invalid: list[InvalidRow] = []
    seen_codes: set[str] = set()

    for i, raw_row in enumerate(reader, start=2):
        if i - 1 > max_preview_rows:
            break
        row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}
        errors_for_row: list[str] = []

        code = row.get("code", "").upper()
        name = row.get("name", "")
        department_code = row.get("department_code", "").upper()
        degree_type = row.get("degree_type", "").strip()
        duration_str = row.get("duration_years", "")

        if not code:
            errors_for_row.append("code is required")
        if not name:
            errors_for_row.append("name is required")
        if not department_code:
            errors_for_row.append("department_code is required")
        if not degree_type:
            errors_for_row.append("degree_type is required")

        duration_years = _parse_int(duration_str, "duration_years", errors_for_row, min_val=1)

        department_id: UUID | None = None

        if not errors_for_row and department_code:
            dept = department_repo.get_by_code(department_code)
            if dept is None:
                errors_for_row.append(f"department_code '{department_code}' not found")
            else:
                department_id = dept.id

        if code and code in seen_codes:
            errors_for_row.append(f"duplicate code '{code}' within this file")

        if not errors_for_row and code and program_repo.get_by_code(code) is not None:
            errors_for_row.append(f"code '{code}' already exists in the system")

        if errors_for_row:
            invalid.append(InvalidRow(row_number=i, raw=dict(row), error="; ".join(errors_for_row)))
        else:
            seen_codes.add(code)
            valid.append(ValidProgramRow(
                row_number=i, code=code, name=name,
                department_id=department_id,  # type: ignore[arg-type]
                department_code=department_code,
                degree_type=degree_type, duration_years=duration_years,
            ))

    return valid, invalid


def commit_program_import(
    valid_rows: list[ValidProgramRow],
    actor_id: UUID,
    *,
    program_repo: "ProgramRepository",
) -> ImportResult:
    from durgam.services.program import ProgramService

    svc = ProgramService(program_repo=program_repo)
    success = 0
    late_errors: list[InvalidRow] = []

    for vrow in valid_rows:
        try:
            svc.create(
                code=vrow.code, name=vrow.name,
                department_id=vrow.department_id,
                degree_type=vrow.degree_type,
                duration_years=vrow.duration_years,
                actor_id=actor_id,
            )
            success += 1
            log.info("bulk_import_program_created", code=vrow.code, actor=str(actor_id))
        except Exception as exc:
            log.warning("bulk_import_program_failed", row=vrow.row_number, error=str(exc))
            late_errors.append(InvalidRow(
                row_number=vrow.row_number,
                raw={"code": vrow.code, "name": vrow.name},
                error=str(exc),
            ))

    return ImportResult(success_count=success, errors=late_errors)


# ── Shared helpers ───────────────────────────────────────────────────────────

def _parse_int(value: str, field_name: str, errors: list[str], *, min_val: int = 0) -> int:
    if not value:
        errors.append(f"{field_name} is required")
        return 0
    try:
        n = int(value)
    except ValueError:
        errors.append(f"{field_name} must be an integer")
        return 0
    if n < min_val:
        errors.append(f"{field_name} must be at least {min_val}")
    return n
