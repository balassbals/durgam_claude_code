"""BulkImportState — two-stage CSV import for users (§9.2(d), §16)."""

from __future__ import annotations

import csv
import io
from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.role import RoleRepository
from durgam.repositories.user import UserRepository
from durgam.repositories.user_role import UserRoleRepository
from durgam.services.bulk_import import (
    InvalidRow,
    ValidRow,
    commit_user_import,
    validate_user_csv,
)
from durgam.states.base import BaseState


class BulkImportState(BaseState):
    # Preview state (non-trivial: multiple state vars, conditional rendering)
    preview_valid: list[dict[str, str]] = []
    preview_invalid: list[dict[str, str]] = []
    preview_ready: bool = False
    total_rows: int = 0

    # Commit state
    import_complete: bool = False
    import_success_count: int = 0
    late_errors: list[dict[str, str]] = []

    # Error report CSV (base64-encoded for download)
    error_report_csv: str = ""

    @require_role(action="write", resource="user")
    @audit_action(action="upload_csv", resource="user")
    async def upload_csv(self, files: list[rx.UploadFile]) -> None:
        """Non-trivial handler: parses CSV, validates rows, sets preview state.

        Reflex 0.9.2 on_drop passes list[rx.UploadFile]; read bytes via
        file.file.read() (BinaryIO sync read) or await file.read() (async).
        """
        self.flash = ""
        self.preview_valid = []
        self.preview_invalid = []
        self.preview_ready = False
        self.import_complete = False

        if not files:
            self.flash = "No file selected."
            return

        upload_file = files[0]
        file_bytes: bytes = upload_file.file.read()

        with open_session() as session:
            valid, invalid = validate_user_csv(
                file_bytes,
                role_repo=RoleRepository(session),
                user_repo=UserRepository(session),
            )

        self.preview_valid = [
            {"row": str(v.row_number), "username": v.username, "email": v.email,
             "role_code": v.role_code, "status": "✓ Valid"}
            for v in valid
        ]
        self.preview_invalid = [
            {"row": str(i.row_number), "username": i.raw.get("username", ""),
             "email": i.raw.get("email", ""), "role_code": i.raw.get("role_code", ""),
             "status": f"✗ {i.error}"}
            for i in invalid
        ]
        self.total_rows = len(valid) + len(invalid)
        self.preview_ready = True

        if invalid:
            self._build_error_report(invalid, [])

    @require_role(action="write", resource="user")
    @audit_action(action="commit_import", resource="user")
    async def commit_import(self) -> None:
        if not self.preview_valid:
            self.flash = "Nothing valid to import."
            return

        valid_rows = [
            ValidRow(
                row_number=int(v["row"]),
                username=v["username"],
                email=v["email"],
                role_code=v["role_code"],
            )
            for v in self.preview_valid
        ]

        with open_session() as session:
            result = commit_user_import(
                valid_rows,
                actor_id=UUID(self.current_user_id),
                user_repo=UserRepository(session),
                user_role_repo=UserRoleRepository(session),
                role_repo=RoleRepository(session),
            )
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
        """Build a CSV error report and store as a string for download."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["row", "username", "email", "role_code", "_status", "_error"])
        for row in preview_invalid:
            writer.writerow([
                row.row_number,
                row.raw.get("username", ""),
                row.raw.get("email", ""),
                row.raw.get("role_code", ""),
                "invalid",
                row.error,
            ])
        for row in late_errors:
            writer.writerow([
                row.row_number,
                row.raw.get("username", ""),
                row.raw.get("email", ""),
                row.raw.get("role_code", ""),
                "commit_failed",
                row.error,
            ])
        self.error_report_csv = output.getvalue()

    def download_template(self):
        """Serve the CSV import template as a client-side download (Bug 1).

        Uses rx.download to push the file to the browser without a separate
        HTTP route. The template content is the canonical source of truth for
        the CSV schema expected by validate_user_csv().
        """
        content = (
            "username,email,role_code,full_name\n"
            "example_user,example.user@sssihl.edu.in,STUDENT,Example User\n"
        )
        return rx.download(data=content, filename="import_user_template.csv")

    def reset_import(self):
        """on_load for /admin/import — guards session then resets import state."""
        guard = self._admin_guard()
        if guard is not None:
            return guard
        self.preview_valid = []
        self.preview_invalid = []
        self.preview_ready = False
        self.import_complete = False
        self.import_success_count = 0
        self.late_errors = []
        self.error_report_csv = ""
        self.flash = ""
