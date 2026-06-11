"""Leave Balance Import admin state — /admin/leave/balance-import (M8.1 E-016)."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.db import open_session
from durgam.states.base import BaseState


class LeaveBalanceImportState(BaseState):
    # ── CSV import vars (exact names from admin_bulk_import.py pattern) ──────
    preview_valid: list[dict[str, str]] = []
    preview_invalid: list[dict[str, str]] = []
    _stashed_valid: list[dict[str, str]] = []
    preview_ready: bool = False
    import_complete: bool = False
    import_success_count: int = 0

    # ── AY display (DD-M8.1-P3-4) ────────────────────────────────────────────
    resolved_ay_name: str = ""
    resolved_ay_id: str = ""

    # ── Employee options (exclude_ephemeral=True per DD-M8.1-P4-2) ───────────
    employees: list[dict[str, str]] = []

    # ── Per-employee form vars ────────────────────────────────────────────────
    show_single_form: bool = False
    form_employee_username: str = ""
    form_leave_type: str = ""
    form_opening: str = "0.0"
    form_credited: str = "0.0"
    form_availed: str = "0.0"
    form_forfeited: str = "0.0"
    form_encashed: str = "0.0"

    # ── Loading / notification ────────────────────────────────────────────────
    loading: bool = True
    flash_type: str = "info"

    # ── Computed vars ─────────────────────────────────────────────────────────

    @rx.var
    def ay_resolved(self) -> bool:
        return self.resolved_ay_name != ""

    @rx.var
    def commit_enabled(self) -> bool:
        """Commit allowed only when: preview_ready, zero invalid rows, and AY resolved."""
        return (
            self.preview_ready
            and len(self.preview_invalid) == 0
            and self.ay_resolved
        )

    # ── Setters ───────────────────────────────────────────────────────────────

    def set_form_employee_username(self, v: str) -> None:
        self.form_employee_username = v

    def set_form_leave_type(self, v: str) -> None:
        self.form_leave_type = v

    def set_form_opening(self, v: str) -> None:
        self.form_opening = v

    def set_form_credited(self, v: str) -> None:
        self.form_credited = v

    def set_form_availed(self, v: str) -> None:
        self.form_availed = v

    def set_form_forfeited(self, v: str) -> None:
        self.form_forfeited = v

    def set_form_encashed(self, v: str) -> None:
        self.form_encashed = v

    def dismiss_flash(self) -> None:
        self.flash = ""
        self.flash_type = "info"

    # ── Internal reset ────────────────────────────────────────────────────────

    def _reset_import_state(self) -> None:
        self.preview_valid = []
        self.preview_invalid = []
        self._stashed_valid = []
        self.preview_ready = False
        self.import_complete = False
        self.import_success_count = 0
        self.flash = ""
        self.flash_type = "info"

    # ── Load ──────────────────────────────────────────────────────────────────

    async def load(self) -> None:
        guard = self._config_guard("leave_balance_import", "write")
        if guard is not None:
            return guard
        self._reset_import_state()
        self.loading = True
        self.resolved_ay_name = ""
        self.resolved_ay_id = ""
        self.employees = []

        from durgam.repositories.user import UserRepository
        from durgam.services.leave_balance_import import LeaveBalanceImportService

        with open_session() as session:
            user_repo = UserRepository(session)
            users, _ = user_repo.list_paginated(
                search=None, offset=0, limit=500, exclude_ephemeral=True
            )
            self.employees = [
                {"username": u.username, "display": f"{u.username} ({u.email})"}
                for u in users
            ]
            svc = LeaveBalanceImportService(session)
            ay = svc.resolve_active_ay()
            if ay is not None:
                self.resolved_ay_name = ay.code
                self.resolved_ay_id = str(ay.id)

        self.loading = False
        self._load_nav_entries()

    # ── CSV Upload (two-phase: validate) ──────────────────────────────────────

    async def upload_csv(self, files: list[rx.UploadFile]) -> None:
        self.flash = ""
        self.flash_type = "info"
        self._reset_import_state()

        if not files:
            self.flash = "No file selected."
            self.flash_type = "error"
            return

        from durgam.services.leave_balance_import import (
            CSVFormatError,
            LeaveBalanceImportService,
        )

        upload_file = files[0]
        file_bytes: bytes = upload_file.file.read()
        csv_text = file_bytes.decode("utf-8", errors="replace")

        with open_session() as session:
            svc = LeaveBalanceImportService(session)
            ay = svc.resolve_active_ay()
            if ay is not None:
                self.resolved_ay_name = ay.code
                self.resolved_ay_id = str(ay.id)
            else:
                self.resolved_ay_name = ""
                self.resolved_ay_id = ""

            try:
                result = svc.validate(csv_text)
            except CSVFormatError as e:
                self.flash = str(e)
                self.flash_type = "error"
                return

        self._stashed_valid = [
            {
                "row": str(r.row_number),
                "employee_username": r.employee_username,
                "leave_type": r.leave_type,
                "opening_balance": str(r.opening_balance),
                "credited": str(r.credited),
                "availed": str(r.availed),
                "forfeited": str(r.forfeited),
                "encashed": str(r.encashed),
                "closing_balance": str(r.closing_balance),
                "user_id": str(r.user_id),
            }
            for r in result.valid_rows
        ]
        self.preview_valid = [
            {
                "row": str(r.row_number),
                "employee": r.employee_username,
                "leave_type": r.leave_type,
                "opening": str(r.opening_balance),
                "credited": str(r.credited),
                "availed": str(r.availed),
                "closing": str(r.closing_balance),
            }
            for r in result.valid_rows
        ]
        self.preview_invalid = [
            {
                "row": str(r.row_number),
                "employee": r.employee_username,
                "leave_type": r.leave_type,
                "error": r.error_reason,
            }
            for r in result.invalid_rows
        ]
        self.preview_ready = True

    # ── Commit (two-phase: commit) ────────────────────────────────────────────

    async def commit_import(self) -> None:
        if not self._stashed_valid:
            self.flash = "Nothing valid to import."
            self.flash_type = "error"
            return

        from durgam.services.leave_balance_import import (
            ImportPreviewRow,
            LeaveBalanceImportService,
        )
        from durgam.services.org_exceptions import AcademicYearLockedError

        actor_id = UUID(self.current_user_id)
        valid_rows = [
            ImportPreviewRow(
                row_number=int(v["row"]),
                employee_username=v["employee_username"],
                leave_type=v["leave_type"],
                opening_balance=float(v["opening_balance"]),
                credited=float(v["credited"]),
                availed=float(v["availed"]),
                forfeited=float(v["forfeited"]),
                encashed=float(v["encashed"]),
                closing_balance=float(v["closing_balance"]),
                user_id=UUID(v["user_id"]),
                is_valid=True,
            )
            for v in self._stashed_valid
        ]

        with open_session() as session:
            svc = LeaveBalanceImportService(session)
            try:
                result = svc.commit(valid_rows, actor_id=actor_id)
            except AcademicYearLockedError:
                self.flash = "No active academic year. Cannot import."
                self.flash_type = "error"
                return
            except Exception as e:
                self.flash = str(e)
                self.flash_type = "error"
                return

        self.import_success_count = result.created + result.updated
        self.import_complete = True
        self.preview_ready = False
        self.flash = (
            f"Import complete: {result.created} created, {result.updated} updated."
        )
        self.flash_type = "success"

    def reset_import(self) -> None:
        self._reset_import_state()

    # ── Per-employee form ─────────────────────────────────────────────────────

    def open_single_form(self) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.form_employee_username = ""
        self.form_leave_type = ""
        self.form_opening = "0.0"
        self.form_credited = "0.0"
        self.form_availed = "0.0"
        self.form_forfeited = "0.0"
        self.form_encashed = "0.0"
        self.show_single_form = True

    def cancel_single_form(self) -> None:
        self.show_single_form = False
        self.flash = ""
        self.flash_type = "info"

    async def submit_single_form(self, form_data: dict) -> None:
        username = form_data.get("form_employee_username", "").strip()
        leave_type = form_data.get("form_leave_type", "").strip()

        if not username:
            self.flash = "Employee username is required."
            self.flash_type = "error"
            return
        if not leave_type:
            self.flash = "Leave type is required."
            self.flash_type = "error"
            return

        try:
            opening = float(form_data.get("form_opening", "0").strip() or "0")
            credited = float(form_data.get("form_credited", "0").strip() or "0")
            availed = float(form_data.get("form_availed", "0").strip() or "0")
            forfeited = float(form_data.get("form_forfeited", "0").strip() or "0")
            encashed = float(form_data.get("form_encashed", "0").strip() or "0")
        except ValueError:
            self.flash = "All balance fields must be numeric."
            self.flash_type = "error"
            return

        from durgam.services.leave_balance_import import LeaveBalanceImportService
        from durgam.services.org_exceptions import AcademicYearLockedError

        actor_id = UUID(self.current_user_id)
        with open_session() as session:
            svc = LeaveBalanceImportService(session)
            try:
                svc.commit_single(
                    employee_username=username,
                    leave_type=leave_type,
                    opening_balance=opening,
                    credited=credited,
                    availed=availed,
                    forfeited=forfeited,
                    encashed=encashed,
                    actor_id=actor_id,
                )
            except AcademicYearLockedError:
                self.flash = "No active academic year. Cannot save balance."
                self.flash_type = "error"
                return
            except ValueError as e:
                self.flash = str(e)
                self.flash_type = "error"
                return

        self.show_single_form = False
        self.flash = f"Balance saved for {username} ({leave_type})."
        self.flash_type = "success"
