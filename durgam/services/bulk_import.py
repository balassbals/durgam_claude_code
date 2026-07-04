"""BulkImportService — two-stage CSV import for users, courses, programs, faculty (§9.2(d), §16).

Stage 1: validate_*_csv — parse bytes, check schema, validate each row.
Stage 2: commit_*_import — insert valid rows, return (success_count, errors).

Errors do not commit the row (per §16 risk note). Valid rows commit individually.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
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


# ── Faculty CSV import ───────────────────────────────────────────────────────

_FACULTY_REQUIRED_COLS = {
    "employee_id", "username", "first_name", "last_name",
    "designation_code", "dept_code", "campus_code", "joining_date", "gender",
}
_FACULTY_VALID_GENDERS = {"M", "F", "O"}
_FACULTY_ROW_CAP = 1000


@dataclass
class ValidFacultyRow:
    row_number: int
    employee_id: str
    username: str
    user_id: UUID
    first_name: str
    last_name: str
    middle_name: str
    title: str
    designation_id: UUID
    designation_code: str
    department_id: UUID
    dept_code: str
    campus_id: UUID
    campus_code: str
    joining_date: date
    gender: str
    phone: str
    whatsapp: str
    alt_phone: str
    alt_email: str
    emergency_contact_name: str
    emergency_contact_relation: str
    emergency_contact_phone: str
    is_phd: bool
    phd_thesis_title: str
    phd_registration_number: str
    phd_awarding_institution: str
    phd_year: int | None
    orcid: str
    linkedin: str
    google_scholar: str
    researchgate: str


def validate_faculty_csv(
    file_bytes: bytes,
    *,
    user_repo: "UserRepository",
    faculty_repo: "FacultyRepository",
    campus_repo: "CampusRepository",
    dept_repo: "DepartmentRepository",
    designation_repo: "DesignationRepository",
    max_rows: int = _FACULTY_ROW_CAP,
) -> tuple[list[ValidFacultyRow], list[InvalidRow]]:
    """Parse a CSV and validate each row against the faculty import schema.

    Mandatory cols: employee_id, username, first_name, last_name,
    designation_code, dept_code, campus_code, joining_date, gender.
    Optional cols: all other faculty profile fields per Q11.
    User must pre-exist with employee_type='regular_teaching' (Q-P12.4).
    """
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], [InvalidRow(row_number=0, raw={}, error="File appears to be empty.")]

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = _FACULTY_REQUIRED_COLS - headers
    if missing:
        return [], [
            InvalidRow(row_number=0, raw={},
                       error=f"Missing required columns: {', '.join(sorted(missing))}.")
        ]

    # Build lookup caches keyed by uppercased code to match CSV normalisation.
    campus_cache: dict[str, UUID] = {c.code.upper(): c.id for c in campus_repo.list_active()}
    dept_cache: dict[str, UUID] = {d.code.upper(): d.id for d in dept_repo.list_active()}
    desig_cache: dict[str, UUID] = {d.code.upper(): d.id for d in designation_repo.list_all_active()}

    valid: list[ValidFacultyRow] = []
    invalid: list[InvalidRow] = []
    seen_usernames: set[str] = set()
    seen_employee_ids: set[str] = set()

    for i, raw_row in enumerate(reader, start=2):
        if i - 1 > max_rows:
            invalid.append(InvalidRow(row_number=i, raw={},
                                      error=f"Row cap exceeded (max {max_rows})."))
            break
        row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}
        errors: list[str] = []

        employee_id = row.get("employee_id", "")
        username = row.get("username", "")
        first_name = row.get("first_name", "")
        last_name = row.get("last_name", "")
        designation_code = row.get("designation_code", "").upper()
        dept_code = row.get("dept_code", "").upper()
        campus_code = row.get("campus_code", "").upper()
        joining_date_str = row.get("joining_date", "")
        gender = row.get("gender", "").upper()

        if not employee_id:
            errors.append("employee_id is required")
        if not username:
            errors.append("username is required")
        if not first_name:
            errors.append("first_name is required")
        if not last_name:
            errors.append("last_name is required")
        if not designation_code:
            errors.append("designation_code is required")
        if not dept_code:
            errors.append("dept_code is required")
        if not campus_code:
            errors.append("campus_code is required")
        if not joining_date_str:
            errors.append("joining_date is required")
        if not gender:
            errors.append("gender is required")
        elif gender not in _FACULTY_VALID_GENDERS:
            errors.append(f"gender must be M, F, or O (got '{gender}')")

        joining_date_parsed: date | None = None
        if joining_date_str:
            try:
                joining_date_parsed = date.fromisoformat(joining_date_str)
            except ValueError:
                errors.append(f"joining_date must be YYYY-MM-DD (got '{joining_date_str}')")

        campus_id: UUID | None = None
        dept_id: UUID | None = None
        desig_id: UUID | None = None

        if campus_code and campus_code not in campus_cache:
            errors.append(f"campus_code '{campus_code}' not found")
        elif campus_code:
            campus_id = campus_cache[campus_code]

        if dept_code and dept_code not in dept_cache:
            errors.append(f"dept_code '{dept_code}' not found")
        elif dept_code:
            dept_id = dept_cache[dept_code]

        if designation_code and designation_code not in desig_cache:
            errors.append(f"designation_code '{designation_code}' not found")
        elif designation_code:
            desig_id = desig_cache[designation_code]

        if employee_id and employee_id in seen_employee_ids:
            errors.append(f"duplicate employee_id '{employee_id}' within this file")
        if username and username in seen_usernames:
            errors.append(f"duplicate username '{username}' within this file")

        user_id: UUID | None = None
        if not errors:
            existing_emp = faculty_repo.get_by_employee_id(employee_id)
            if existing_emp is not None:
                errors.append(f"employee_id '{employee_id}' already in use")

            user = user_repo.get_by_username(username)
            if user is None:
                errors.append(f"username '{username}' not found in the system")
            elif user.employee_type != "regular_teaching":
                errors.append(
                    f"user '{username}' employee_type is '{user.employee_type}'"
                    " — must be 'regular_teaching'"
                )
            else:
                existing_fac = faculty_repo.get_by_user_id(user.id)
                if existing_fac is not None:
                    errors.append(f"user '{username}' already has a faculty record")
                else:
                    user_id = user.id

        if errors:
            invalid.append(InvalidRow(row_number=i, raw=dict(row), error="; ".join(errors)))
        else:
            seen_employee_ids.add(employee_id)
            seen_usernames.add(username)
            valid.append(ValidFacultyRow(
                row_number=i,
                employee_id=employee_id,
                username=username,
                user_id=user_id,  # type: ignore[arg-type]
                first_name=first_name,
                last_name=last_name,
                middle_name=row.get("middle_name", ""),
                title=row.get("title", ""),
                designation_id=desig_id,  # type: ignore[arg-type]
                designation_code=designation_code,
                department_id=dept_id,  # type: ignore[arg-type]
                dept_code=dept_code,
                campus_id=campus_id,  # type: ignore[arg-type]
                campus_code=campus_code,
                joining_date=joining_date_parsed,  # type: ignore[arg-type]
                gender=gender,
                phone=row.get("phone", ""),
                whatsapp=row.get("whatsapp", ""),
                alt_phone=row.get("alt_phone", ""),
                alt_email=row.get("alt_email", ""),
                emergency_contact_name=row.get("emergency_contact_name", ""),
                emergency_contact_relation=row.get("emergency_contact_relation", ""),
                emergency_contact_phone=row.get("emergency_contact_phone", ""),
                is_phd=row.get("is_phd", "").lower() in ("true", "1", "yes"),
                phd_thesis_title=row.get("phd_thesis_title", ""),
                phd_registration_number=row.get("phd_registration_number", ""),
                phd_awarding_institution=row.get("phd_awarding_institution", ""),
                phd_year=int(row["phd_year"]) if row.get("phd_year", "").isdigit() else None,
                orcid=row.get("orcid", ""),
                linkedin=row.get("linkedin", ""),
                google_scholar=row.get("google_scholar", ""),
                researchgate=row.get("researchgate", ""),
            ))

    return valid, invalid


def commit_faculty_import(
    valid_rows: list[ValidFacultyRow],
    actor_id: UUID,
    *,
    faculty_repo: "FacultyRepository",
    user_repo: "UserRepository",
) -> ImportResult:
    """Commit valid rows from a prior validate_faculty_csv call.

    Creates Faculty rows for each valid entry and updates User.gender.
    All rows share one outer session/transaction managed by the caller.
    """
    from datetime import UTC, datetime as _dt

    from durgam.models.faculty import Faculty as _Faculty

    success = 0
    late_errors: list[InvalidRow] = []

    for vrow in valid_rows:
        try:
            now = _dt.now(UTC)
            faculty = _Faculty(
                user_id=vrow.user_id,
                employee_id=vrow.employee_id,
                title=vrow.title,
                first_name=vrow.first_name,
                middle_name=vrow.middle_name or None,
                last_name=vrow.last_name,
                designation_id=vrow.designation_id,
                department_id=vrow.department_id,
                campus_id=vrow.campus_id,
                joining_date=vrow.joining_date,
                phone=vrow.phone,
                whatsapp=vrow.whatsapp,
                alt_phone=vrow.alt_phone,
                alt_email=vrow.alt_email,
                emergency_contact_name=vrow.emergency_contact_name,
                emergency_contact_relation=vrow.emergency_contact_relation,
                emergency_contact_phone=vrow.emergency_contact_phone,
                is_phd=vrow.is_phd,
                phd_thesis_title=vrow.phd_thesis_title or None,
                phd_registration_number=vrow.phd_registration_number or None,
                phd_awarding_institution=vrow.phd_awarding_institution or None,
                phd_year=vrow.phd_year,
                orcid=vrow.orcid or None,
                linkedin=vrow.linkedin or None,
                google_scholar=vrow.google_scholar or None,
                researchgate=vrow.researchgate or None,
                created_by=actor_id,
                updated_by=actor_id,
                created_at=now,
                updated_at=now,
            )
            faculty_repo.create(faculty)

            if vrow.gender:
                user = user_repo.get_by_username(vrow.username)
                if user is not None:
                    user.gender = vrow.gender
                    user_repo.save(user)

            success += 1
            log.info("bulk_import_faculty_created",
                     employee_id=vrow.employee_id, actor=str(actor_id))
        except Exception as exc:
            log.warning("bulk_import_faculty_failed", row=vrow.row_number, error=str(exc))
            late_errors.append(InvalidRow(
                row_number=vrow.row_number,
                raw={"employee_id": vrow.employee_id, "username": vrow.username},
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
