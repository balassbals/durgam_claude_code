"""Leave Sanction Matrix admin state — CRUD for LeaveSanctionAuthorityRule (M8 Phase 8)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import reflex as rx
import structlog

from durgam.auth.permissions import PermissionDenied
from durgam.db import open_session
from durgam.states.base import BaseState

log = structlog.get_logger(__name__)


def _svc(session):
    from durgam.repositories.leave import LeaveSanctionRuleRepository
    from durgam.services.leave_sanction_rule import LeaveSanctionRuleService

    return LeaveSanctionRuleService(session, LeaveSanctionRuleRepository(session))


class LeaveMatrixState(BaseState):
    rules: list[dict[str, Any]] = []
    loading: bool = True
    flash: str = ""
    flash_type: str = "info"

    # Modal state
    is_open: bool = False
    edit_mode: bool = False
    editing_rule_id: str = ""

    # Delete confirm
    confirm_open: bool = False
    deleting_rule_id: str = ""
    deleting_rule_label: str = ""

    # Form fields
    form_leave_type: str = ""
    form_applicant_role_code: str = ""
    form_sanctioner_role_code: str = ""
    form_recommend_via_role_code: str = ""
    form_requires_in_charge: bool = False
    form_scope_type: str = ""
    form_priority: str = "100"
    form_notes: str = ""

    # ── Setters ──────────────────────────────────────────────────────

    def set_form_leave_type(self, v: str) -> None:
        self.form_leave_type = v

    def set_form_applicant_role_code(self, v: str) -> None:
        self.form_applicant_role_code = v

    def set_form_sanctioner_role_code(self, v: str) -> None:
        self.form_sanctioner_role_code = v

    def set_form_recommend_via_role_code(self, v: str) -> None:
        self.form_recommend_via_role_code = v

    def set_form_requires_in_charge(self, v: bool) -> None:
        self.form_requires_in_charge = v

    def set_form_scope_type(self, v: str) -> None:
        self.form_scope_type = v

    def set_form_priority(self, v: str) -> None:
        self.form_priority = v

    def set_form_notes(self, v: str) -> None:
        self.form_notes = v

    # ── Load ─────────────────────────────────────────────────────────

    async def load_rules(self) -> None:
        guard = self._config_guard("leave_sanction_rule", "configure")
        if guard is not None:
            return guard
        self.loading = True
        self.rules = []
        self.flash = ""
        self.flash_type = "info"

        with open_session() as session:
            svc = _svc(session)
            for r in svc.list_rules():
                self.rules.append({
                    "id": str(r.id),
                    "leave_type": r.leave_type,
                    "applicant_role_code": r.applicant_role_code,
                    "sanctioner_role_code": r.sanctioner_role_code,
                    "recommend_via": r.recommend_via_role_code or "—",
                    "requires_in_charge": "Yes" if r.requires_in_charge else "No",
                    "scope_type": r.scope_type or "—",
                    "priority": r.priority,
                    "notes": r.notes or "",
                    # raw for edit
                    "raw_recommend_via": r.recommend_via_role_code or "",
                    "raw_requires_in_charge": r.requires_in_charge,
                    "raw_scope_type": r.scope_type or "",
                    "raw_notes": r.notes or "",
                })

        self._load_nav_entries()
        self.loading = False

    # ── Modal open/close ──────────────────────────────────────────────

    def open_create(self) -> None:
        self.flash = ""
        self.flash_type = "info"
        self._reset_form()
        self.edit_mode = False
        self.editing_rule_id = ""
        self.is_open = True

    def open_edit(self, rule_id: str) -> None:
        self.flash = ""
        self.flash_type = "info"
        self._reset_form()
        rule = next((r for r in self.rules if r["id"] == rule_id), None)
        if rule is None:
            return
        self.form_leave_type = rule["leave_type"]
        self.form_applicant_role_code = rule["applicant_role_code"]
        self.form_sanctioner_role_code = rule["sanctioner_role_code"]
        self.form_recommend_via_role_code = rule["raw_recommend_via"]
        self.form_requires_in_charge = rule["raw_requires_in_charge"]
        self.form_scope_type = rule["raw_scope_type"]
        self.form_priority = str(rule["priority"])
        self.form_notes = rule["raw_notes"]
        self.edit_mode = True
        self.editing_rule_id = rule_id
        self.is_open = True

    def close_form(self) -> None:
        self.is_open = False
        self._reset_form()

    def _reset_form(self) -> None:
        self.form_leave_type = ""
        self.form_applicant_role_code = ""
        self.form_sanctioner_role_code = ""
        self.form_recommend_via_role_code = ""
        self.form_requires_in_charge = False
        self.form_scope_type = ""
        self.form_priority = "100"
        self.form_notes = ""
        self.editing_rule_id = ""
        self.edit_mode = False

    # ── Save ─────────────────────────────────────────────────────────

    async def submit_form(self, form_data: dict) -> None:
        leave_type = form_data.get("form_leave_type", "").strip() or self.form_leave_type.strip()
        applicant = form_data.get("form_applicant_role_code", "").strip() or self.form_applicant_role_code.strip()
        sanctioner = form_data.get("form_sanctioner_role_code", "").strip() or self.form_sanctioner_role_code.strip()
        priority_str = form_data.get("form_priority", "").strip() or self.form_priority.strip()
        notes = form_data.get("form_notes", "").strip() or self.form_notes.strip()

        if not leave_type:
            self.flash = "Leave type is required."
            self.flash_type = "error"
            return
        if not applicant:
            self.flash = "Applicant role code is required."
            self.flash_type = "error"
            return
        if not sanctioner:
            self.flash = "Sanctioner role code is required."
            self.flash_type = "error"
            return

        try:
            priority = int(priority_str) if priority_str else 100
        except ValueError:
            self.flash = "Priority must be an integer."
            self.flash_type = "error"
            return

        actor_id = UUID(self.current_user_id)
        recommend_via = self.form_recommend_via_role_code.strip() or None
        scope_type = self.form_scope_type.strip() or None

        from durgam.services.leave_sanction_rule import LeaveSanctionRuleError

        try:
            with open_session() as session:
                svc = _svc(session)
                if not self.edit_mode:
                    svc.create_rule(
                        leave_type=leave_type,
                        applicant_role_code=applicant,
                        sanctioner_role_code=sanctioner,
                        priority=priority,
                        actor_id=actor_id,
                        recommend_via_role_code=recommend_via,
                        requires_in_charge=self.form_requires_in_charge,
                        scope_type=scope_type,
                        notes=notes or None,
                    )
                else:
                    svc.update_rule(
                        UUID(self.editing_rule_id),
                        {
                            "leave_type": leave_type,
                            "applicant_role_code": applicant,
                            "sanctioner_role_code": sanctioner,
                            "priority": priority,
                            "recommend_via_role_code": recommend_via,
                            "requires_in_charge": self.form_requires_in_charge,
                            "scope_type": scope_type,
                            "notes": notes or None,
                        },
                        actor_id,
                    )
                session.commit()
        except PermissionDenied:
            self.flash = "You do not have permission to configure the leave sanction matrix."
            self.flash_type = "error"
            return
        except LeaveSanctionRuleError as e:
            self.flash = str(e)
            self.flash_type = "error"
            return
        except Exception:
            log.error("leave_matrix_save_failed", exc_info=True)
            self.flash = "An unexpected error occurred. Please try again."
            self.flash_type = "error"
            return

        self.close_form()
        await self.load_rules()
        self.flash = "Rule saved." if not self.edit_mode else "Rule updated."
        self.flash_type = "success"

    # ── Delete confirm ────────────────────────────────────────────────

    def open_delete_confirm(self, rule_id: str) -> None:
        self.flash = ""
        self.flash_type = "info"
        rule = next((r for r in self.rules if r["id"] == rule_id), None)
        if rule is None:
            return
        self.deleting_rule_id = rule_id
        self.deleting_rule_label = (
            f"{rule['leave_type']} / {rule['applicant_role_code']} → {rule['sanctioner_role_code']}"
        )
        self.confirm_open = True

    def cancel_delete(self) -> None:
        self.confirm_open = False
        self.deleting_rule_id = ""
        self.deleting_rule_label = ""

    async def soft_delete(self) -> None:
        self.confirm_open = False
        if not self.deleting_rule_id:
            return

        actor_id = UUID(self.current_user_id)
        from durgam.services.leave_sanction_rule import LeaveSanctionRuleError

        try:
            with open_session() as session:
                svc = _svc(session)
                svc.soft_delete_rule(UUID(self.deleting_rule_id), actor_id)
                session.commit()
        except PermissionDenied:
            self.flash = "You do not have permission to delete rules."
            self.flash_type = "error"
            self.deleting_rule_id = ""
            return
        except LeaveSanctionRuleError as e:
            self.flash = str(e)
            self.flash_type = "error"
            self.deleting_rule_id = ""
            return

        self.deleting_rule_id = ""
        self.deleting_rule_label = ""
        await self.load_rules()
        self.flash = "Rule deleted."
        self.flash_type = "success"

    def dismiss_flash(self) -> None:
        self.flash = ""
        self.flash_type = "info"
