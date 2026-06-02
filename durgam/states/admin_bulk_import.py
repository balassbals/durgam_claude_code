"""BulkImportState — two-stage CSV import for users, courses, programs (§9.2(d), §16).

Per-entity import permissions (M5b-R3 V2):
- Users tab: gated on user:write (SysAdmin-only).
- Courses tab: gated on course_import:write (HOD family + HOD_OFFICE).
- Programs tab: gated on program_import:write (Registrar family).
SysAdmin gets all three via global permission grant.
"""

from __future__ import annotations

import csv
import io
from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.auth.permissions import can
from durgam.db import open_session
from durgam.repositories.course import CourseRepository
from durgam.repositories.department import DepartmentRepository
from durgam.repositories.program import ProgramRepository
from durgam.repositories.role import RoleRepository
from durgam.repositories.user import UserRepository
from durgam.repositories.user_role import UserRoleRepository
from durgam.services.bulk_import import (
    InvalidRow,
    ValidCourseRow,
    ValidProgramRow,
    ValidRow,
    commit_course_import,
    commit_program_import,
    commit_user_import,
    validate_course_csv,
    validate_program_csv,
    validate_user_csv,
)
from durgam.states.base import BaseState


_IMPORT_TYPES = ("users", "courses", "programs")

_RESOURCE_FOR_TYPE = {
    "users": "user",
    "courses": "course_import",
    "programs": "program_import",
}

_COLUMN_HEADERS = {
    "users": ("Username", "Email", "Role"),
    "courses": ("Code", "Name", "Program/Dept"),
    "programs": ("Code", "Name", "Dept/Degree"),
}


class BulkImportState(BaseState):
    import_type: str = "users"

    can_import_users: bool = False
    can_import_courses: bool = False
    can_import_programs: bool = False
    has_admin_access: bool = False

    preview_valid: list[dict[str, str]] = []
    preview_invalid: list[dict[str, str]] = []
    preview_ready: bool = False
    total_rows: int = 0

    # Stashed validated data for commit stage (JSON-serializable dicts).
    _stashed_valid: list[dict[str, str]] = []

    import_complete: bool = False
    import_success_count: int = 0
    late_errors: list[dict[str, str]] = []

    error_report_csv: str = ""

    col1_header: str = "Username"
    col2_header: str = "Email"
    col3_header: str = "Role"

    def set_import_type(self, value: str) -> None:
        if value not in _IMPORT_TYPES:
            return
        self.import_type = value
        self._reset_state()
        h = _COLUMN_HEADERS.get(value, _COLUMN_HEADERS["users"])
        self.col1_header, self.col2_header, self.col3_header = h

    def _reset_state(self) -> None:
        self.preview_valid = []
        self.preview_invalid = []
        self.preview_ready = False
        self.import_complete = False
        self.import_success_count = 0
        self.late_errors = []
        self.error_report_csv = ""
        self.flash = ""
        self._stashed_valid = []

    def _check_import_permission(self, session) -> bool:
        resource = _RESOURCE_FOR_TYPE.get(self.import_type, "user")
        return can(
            UUID(self.current_user_id), "write", resource,
            scope_type=None, scope_id=None, session=session,
        )

    def _can_any_import(self, session) -> bool:
        uid = UUID(self.current_user_id)
        return any(
            can(uid, "write", res, scope_type=None, scope_id=None, session=session)
            for res in _RESOURCE_FOR_TYPE.values()
        )

    async def load_import(self) -> None:
        guard = self._config_guard_any([
            ("write", "user", None),
            ("write", "program_import", None),
            ("write", "course_import", None),
        ])
        if guard is not None:
            return guard
        self._reset_state()

        with open_session() as session:
            uid = UUID(self.current_user_id)
            self.can_import_users = can(uid, "write", "user", scope_type=None, scope_id=None, session=session)
            self.can_import_courses = can(uid, "write", "course_import", scope_type=None, scope_id=None, session=session)
            self.can_import_programs = can(uid, "write", "program_import", scope_type=None, scope_id=None, session=session)
            self.has_admin_access = can(uid, "read", "user", scope_type=None, scope_id=None, session=session)

        if not self._can_current_type():
            for t in ("users", "courses", "programs"):
                if self._can_type(t):
                    self.import_type = t
                    break

        h = _COLUMN_HEADERS.get(self.import_type, _COLUMN_HEADERS["users"])
        self.col1_header, self.col2_header, self.col3_header = h
        self._load_nav_entries()

    def _can_type(self, import_type: str) -> bool:
        return {
            "users": self.can_import_users,
            "courses": self.can_import_courses,
            "programs": self.can_import_programs,
        }.get(import_type, False)

    def _can_current_type(self) -> bool:
        return self._can_type(self.import_type)

    @audit_action(action="upload_csv", resource="user")
    async def upload_csv(self, files: list[rx.UploadFile]) -> None:
        self.flash = ""
        self._reset_state()
        h = _COLUMN_HEADERS.get(self.import_type, _COLUMN_HEADERS["users"])
        self.col1_header, self.col2_header, self.col3_header = h

        if not files:
            self.flash = "No file selected."
            return

        upload_file = files[0]
        file_bytes: bytes = upload_file.file.read()

        with open_session() as session:
            if not self._check_import_permission(session):
                self.flash = f"You do not have write permission for {self.import_type}."
                return

            invalid: list[InvalidRow] = []

            if self.import_type == "users":
                valid_u, invalid = validate_user_csv(
                    file_bytes,
                    role_repo=RoleRepository(session),
                    user_repo=UserRepository(session),
                )
                self._stashed_valid = [
                    {"row": str(v.row_number), "username": v.username,
                     "email": v.email, "role_code": v.role_code,
                     "full_name": v.full_name}
                    for v in valid_u
                ]
                self.preview_valid = [
                    {"row": str(v.row_number), "col1": v.username,
                     "col2": v.email, "col3": v.role_code,
                     "status": "✓ Valid"}
                    for v in valid_u
                ]

            elif self.import_type == "courses":
                valid_c, invalid = validate_course_csv(
                    file_bytes,
                    program_repo=ProgramRepository(session),
                    department_repo=DepartmentRepository(session),
                    course_repo=CourseRepository(session),
                )
                self._stashed_valid = [
                    {"row": str(v.row_number), "code": v.code, "name": v.name,
                     "program_id": str(v.program_id), "department_id": str(v.department_id),
                     "credits": str(v.credits), "lecture": str(v.lecture),
                     "tutorial": str(v.tutorial), "practical": str(v.practical),
                     "evaluation": v.evaluation}
                    for v in valid_c
                ]
                self.preview_valid = [
                    {"row": str(v.row_number), "col1": v.code, "col2": v.name,
                     "col3": f"{v.program_code}/{v.department_code}",
                     "status": "✓ Valid"}
                    for v in valid_c
                ]

            elif self.import_type == "programs":
                valid_p, invalid = validate_program_csv(
                    file_bytes,
                    program_repo=ProgramRepository(session),
                    department_repo=DepartmentRepository(session),
                )
                self._stashed_valid = [
                    {"row": str(v.row_number), "code": v.code, "name": v.name,
                     "department_id": str(v.department_id),
                     "degree_type": v.degree_type,
                     "duration_years": str(v.duration_years)}
                    for v in valid_p
                ]
                self.preview_valid = [
                    {"row": str(v.row_number), "col1": v.code, "col2": v.name,
                     "col3": f"{v.department_code}/{v.degree_type}",
                     "status": "✓ Valid"}
                    for v in valid_p
                ]

            self.preview_invalid = [
                {"row": str(i.row_number),
                 "col1": i.raw.get("username", i.raw.get("code", "")),
                 "col2": i.raw.get("email", i.raw.get("name", "")),
                 "col3": i.raw.get("role_code", i.raw.get("department_code", "")),
                 "status": f"✗ {i.error}"}
                for i in invalid
            ]

        self.total_rows = len(self.preview_valid) + len(self.preview_invalid)
        self.preview_ready = True

        if invalid:
            self._build_error_report(invalid, [])

    @audit_action(action="commit_import", resource="user")
    async def commit_import(self) -> None:
        if not self._stashed_valid:
            self.flash = "Nothing valid to import."
            return

        with open_session() as session:
            if not self._check_import_permission(session):
                self.flash = f"You do not have write permission for {self.import_type}."
                return

            actor_id = UUID(self.current_user_id)

            if self.import_type == "users":
                rows = [
                    ValidRow(
                        row_number=int(v["row"]), username=v["username"],
                        email=v["email"], role_code=v["role_code"],
                        full_name=v.get("full_name", ""),
                    )
                    for v in self._stashed_valid
                ]
                result = commit_user_import(
                    rows, actor_id,
                    user_repo=UserRepository(session),
                    user_role_repo=UserRoleRepository(session),
                    role_repo=RoleRepository(session),
                )

            elif self.import_type == "courses":
                rows_c = [
                    ValidCourseRow(
                        row_number=int(v["row"]), code=v["code"], name=v["name"],
                        program_id=UUID(v["program_id"]),
                        program_code="",
                        department_id=UUID(v["department_id"]),
                        department_code="",
                        credits=int(v["credits"]), lecture=int(v["lecture"]),
                        tutorial=int(v["tutorial"]), practical=int(v["practical"]),
                        evaluation=v["evaluation"],
                    )
                    for v in self._stashed_valid
                ]
                result = commit_course_import(
                    rows_c, actor_id,
                    course_repo=CourseRepository(session),
                    program_repo=ProgramRepository(session),
                    department_repo=DepartmentRepository(session),
                )

            elif self.import_type == "programs":
                rows_p = [
                    ValidProgramRow(
                        row_number=int(v["row"]), code=v["code"], name=v["name"],
                        department_id=UUID(v["department_id"]),
                        department_code="",
                        degree_type=v["degree_type"],
                        duration_years=int(v["duration_years"]),
                    )
                    for v in self._stashed_valid
                ]
                result = commit_program_import(
                    rows_p, actor_id,
                    program_repo=ProgramRepository(session),
                )

            else:
                self.flash = "Unknown import type."
                return

            session.commit()

        self.import_success_count = result.success_count
        self.late_errors = [
            {"row": str(e.row_number), "error": e.error}
            for e in result.errors
        ]
        self.import_complete = True
        self.preview_ready = False

        if result.errors:
            self._build_error_report([], result.errors)

    def _build_error_report(
        self,
        preview_invalid: list[InvalidRow],
        late_errors: list[InvalidRow],
    ) -> None:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["row", "field1", "field2", "field3", "_status", "_error"])
        for row in preview_invalid:
            writer.writerow([
                row.row_number,
                row.raw.get("username", row.raw.get("code", "")),
                row.raw.get("email", row.raw.get("name", "")),
                row.raw.get("role_code", row.raw.get("department_code", "")),
                "invalid",
                row.error,
            ])
        for row in late_errors:
            writer.writerow([
                row.row_number,
                row.raw.get("username", row.raw.get("code", "")),
                row.raw.get("email", row.raw.get("name", "")),
                row.raw.get("role_code", ""),
                "commit_failed",
                row.error,
            ])
        self.error_report_csv = output.getvalue()

    def download_template(self):
        if self.import_type == "courses":
            content = (
                "code,name,program_code,department_code,credits,lecture,tutorial,practical,evaluation\n"
                "MAT201,Linear Algebra,BSCMATH,DMACS,4,3,1,0,IE\n"
            )
            return rx.download(data=content, filename="import_course_template.csv")
        elif self.import_type == "programs":
            content = (
                "code,name,department_code,degree_type,duration_years\n"
                "BSCPHY,BSc Physics,DPHY,BSc,3\n"
            )
            return rx.download(data=content, filename="import_program_template.csv")
        else:
            content = (
                "username,email,role_code,full_name\n"
                "example_user,example.user@sssihl.edu.in,STUDENT,Example User\n"
            )
            return rx.download(data=content, filename="import_user_template.csv")

    def reset_import(self):
        guard = self._config_guard_any([
            ("write", "user", None),
            ("write", "program_import", None),
            ("write", "course_import", None),
        ])
        if guard is not None:
            return guard
        self._reset_state()
        self._load_nav_entries()
