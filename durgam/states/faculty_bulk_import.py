"""FacultyBulkImportState — two-stage CSV import for faculty records (M10 Phase 12).

Permission: faculty:bulk_import:* (REGISTRAR, HR_HEAD, DEPUTY_REGISTRAR families).
Route: /admin/faculty/import
Pattern: same validate→stash→commit two-stage flow as BulkImportState (M5b).
"""

from __future__ import annotations

import csv
import io
from datetime import date
from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.campus import CampusRepository
from durgam.repositories.department import DepartmentRepository
from durgam.repositories.designation import DesignationRepository
from durgam.repositories.faculty import FacultyRepository
from durgam.repositories.user import UserRepository
from durgam.services.bulk_import import (
    InvalidRow,
    ValidFacultyRow,
    commit_faculty_import,
    validate_faculty_csv,
)
from durgam.states.base import BaseState


class FacultyBulkImportState(BaseState):
    preview_valid: list[dict[str, str]] = []
    preview_invalid: list[dict[str, str]] = []
    preview_ready: bool = False
    total_rows: int = 0

    # Backend-only stash — not synced to client.
    _stashed_valid: list[dict[str, str]] = []

    import_complete: bool = False
    import_success_count: int = 0
    late_errors: list[dict[str, str]] = []
    error_report_csv: str = ""

    flash: str = ""

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

    async def load_import(self) -> None:
        guard = self._config_guard("faculty", "bulk_import")
        if guard is not None:
            return guard
        self._reset_state()
        self._load_nav_entries()

    @audit_action(action="upload_csv", resource="faculty")
    async def upload_csv(self, files: list[rx.UploadFile]) -> None:
        self.flash = ""
        self._reset_state()

        if not files:
            self.flash = "No file selected."
            return

        file_bytes: bytes = files[0].file.read()
        filename = files[0].filename or "upload.csv"

        with open_session() as session:
            valid_rows, invalid_rows = validate_faculty_csv(
                file_bytes,
                user_repo=UserRepository(session),
                faculty_repo=FacultyRepository(session),
                campus_repo=CampusRepository(session),
                dept_repo=DepartmentRepository(session),
                designation_repo=DesignationRepository(session),
            )

        self._stashed_valid = [_row_to_dict(v) for v in valid_rows]
        self.preview_valid = [
            {
                "row": str(v.row_number),
                "col1": v.employee_id,
                "col2": v.username,
                "col3": f"{v.first_name} {v.last_name}",
                "status": "✓ Valid",
            }
            for v in valid_rows
        ]
        self.preview_invalid = [
            {
                "row": str(inv.row_number),
                "col1": inv.raw.get("employee_id", ""),
                "col2": inv.raw.get("username", ""),
                "col3": "",
                "status": f"✗ {inv.error}",
            }
            for inv in invalid_rows
        ]
        self.total_rows = len(self.preview_valid) + len(self.preview_invalid)
        self.preview_ready = True

        self._set_audit(
            resource_id=filename,
            after={
                "row_count": self.total_rows,
                "valid_count": len(self.preview_valid),
                "invalid_count": len(self.preview_invalid),
            },
        )

        if invalid_rows:
            self._build_error_report(invalid_rows, [])

    @require_role(action="bulk_import", resource="faculty", scope="*")
    @audit_action(action="commit_import", resource="faculty")
    async def commit_import(self) -> None:
        if not self._stashed_valid:
            self.flash = "Nothing valid to import."
            return

        actor_id = UUID(self.current_user_id)
        valid_rows = [_dict_to_row(d) for d in self._stashed_valid]

        with open_session() as session:
            result = commit_faculty_import(
                valid_rows,
                actor_id,
                faculty_repo=FacultyRepository(session),
                user_repo=UserRepository(session),
            )
            session.commit()

        self.import_success_count = result.success_count
        self.late_errors = [
            {"row": str(e.row_number), "error": e.error}
            for e in result.errors
        ]
        self.import_complete = True
        self.preview_ready = False

        self._set_audit(
            resource_id="faculty_csv",
            after={
                "committed_count": result.success_count,
                "error_count": len(result.errors),
            },
        )

        if result.errors:
            self._build_error_report([], result.errors)

    def _build_error_report(
        self,
        preview_invalid: list[InvalidRow],
        late_errors: list[InvalidRow],
    ) -> None:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["row", "employee_id", "username", "_status", "_error"])
        for inv in preview_invalid:
            writer.writerow([
                inv.row_number,
                inv.raw.get("employee_id", ""),
                inv.raw.get("username", ""),
                "invalid",
                inv.error,
            ])
        for err in late_errors:
            writer.writerow([
                err.row_number,
                err.raw.get("employee_id", ""),
                err.raw.get("username", ""),
                "commit_failed",
                err.error,
            ])
        self.error_report_csv = output.getvalue()

    def download_template(self):
        content = (
            "employee_id,username,first_name,last_name,designation_code,"
            "dept_code,campus_code,joining_date,gender,"
            "middle_name,title,phone,emergency_contact_name,"
            "emergency_contact_relation,emergency_contact_phone\n"
            "EMP001,john_doe,John,Doe,ASST_PROF_L10,"
            "DMACS,MAIN,2020-06-01,M,"
            ",Dr,9999999999,Jane Doe,Spouse,8888888888\n"
        )
        return rx.download(data=content, filename="import_faculty_template.csv")

    def reset_import(self):
        guard = self._config_guard("faculty", "bulk_import")
        if guard is not None:
            return guard
        self._reset_state()
        self._load_nav_entries()

    def set_flash(self, value: str) -> None:
        self.flash = value


# ── Serialisation helpers (ValidFacultyRow ↔ dict[str, str]) ─────────────────

def _row_to_dict(v: ValidFacultyRow) -> dict[str, str]:
    return {
        "row": str(v.row_number),
        "employee_id": v.employee_id,
        "username": v.username,
        "user_id": str(v.user_id),
        "first_name": v.first_name,
        "last_name": v.last_name,
        "middle_name": v.middle_name,
        "title": v.title,
        "designation_id": str(v.designation_id),
        "designation_code": v.designation_code,
        "department_id": str(v.department_id),
        "dept_code": v.dept_code,
        "campus_id": str(v.campus_id),
        "campus_code": v.campus_code,
        "joining_date": v.joining_date.isoformat(),
        "gender": v.gender,
        "phone": v.phone,
        "whatsapp": v.whatsapp,
        "alt_phone": v.alt_phone,
        "alt_email": v.alt_email,
        "emergency_contact_name": v.emergency_contact_name,
        "emergency_contact_relation": v.emergency_contact_relation,
        "emergency_contact_phone": v.emergency_contact_phone,
        "is_phd": "true" if v.is_phd else "false",
        "phd_thesis_title": v.phd_thesis_title,
        "phd_registration_number": v.phd_registration_number,
        "phd_awarding_institution": v.phd_awarding_institution,
        "phd_year": str(v.phd_year) if v.phd_year is not None else "",
        "orcid": v.orcid,
        "linkedin": v.linkedin,
        "google_scholar": v.google_scholar,
        "researchgate": v.researchgate,
    }


def _dict_to_row(d: dict[str, str]) -> ValidFacultyRow:
    return ValidFacultyRow(
        row_number=int(d["row"]),
        employee_id=d["employee_id"],
        username=d["username"],
        user_id=UUID(d["user_id"]),
        first_name=d["first_name"],
        last_name=d["last_name"],
        middle_name=d.get("middle_name", ""),
        title=d.get("title", ""),
        designation_id=UUID(d["designation_id"]),
        designation_code=d["designation_code"],
        department_id=UUID(d["department_id"]),
        dept_code=d["dept_code"],
        campus_id=UUID(d["campus_id"]),
        campus_code=d["campus_code"],
        joining_date=date.fromisoformat(d["joining_date"]),
        gender=d["gender"],
        phone=d.get("phone", ""),
        whatsapp=d.get("whatsapp", ""),
        alt_phone=d.get("alt_phone", ""),
        alt_email=d.get("alt_email", ""),
        emergency_contact_name=d.get("emergency_contact_name", ""),
        emergency_contact_relation=d.get("emergency_contact_relation", ""),
        emergency_contact_phone=d.get("emergency_contact_phone", ""),
        is_phd=d.get("is_phd", "false") == "true",
        phd_thesis_title=d.get("phd_thesis_title", ""),
        phd_registration_number=d.get("phd_registration_number", ""),
        phd_awarding_institution=d.get("phd_awarding_institution", ""),
        phd_year=int(d["phd_year"]) if d.get("phd_year") else None,
        orcid=d.get("orcid", ""),
        linkedin=d.get("linkedin", ""),
        google_scholar=d.get("google_scholar", ""),
        researchgate=d.get("researchgate", ""),
    )
