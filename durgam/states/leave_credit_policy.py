"""CL Credit Policy admin state — /admin/leave/credit-policy (M8.1 TD-036)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from durgam.audit.log import write_audit_row
from durgam.audit.snapshot import audit_snapshot
from durgam.db import open_session
from durgam.states.base import BaseState

log = structlog.get_logger(__name__)


class LeaveCreditPolicyState(BaseState):
    policies: list[dict[str, Any]] = []
    loading: bool = True
    flash: str = ""
    flash_type: str = "info"

    # Edit form state
    show_form: bool = False
    editing_id: str = ""
    form_vacation_entitlement: str = ""
    form_non_vacation_entitlement: str = ""
    form_enabled: bool = True

    # ── Setters ──────────────────────────────────────────────────────────

    def set_form_vacation_entitlement(self, v: str) -> None:
        self.form_vacation_entitlement = v

    def set_form_non_vacation_entitlement(self, v: str) -> None:
        self.form_non_vacation_entitlement = v

    def set_form_enabled(self, v: bool) -> None:
        self.form_enabled = v

    def dismiss_flash(self) -> None:
        self.flash = ""
        self.flash_type = "info"

    # ── Load ─────────────────────────────────────────────────────────────

    async def load_policies(self) -> None:
        guard = self._config_guard("leave_credit_policy", "configure")
        if guard is not None:
            return guard
        self.loading = True
        self.policies = []
        self.flash = ""
        self.flash_type = "info"

        from durgam.repositories.leave import LeaveCreditPolicyRepository

        rows: list[dict[str, Any]] = []
        with open_session() as session:
            repo = LeaveCreditPolicyRepository(session)
            for p in repo.list_active():
                rows.append({
                    "id": str(p.id),
                    "leave_type": p.leave_type,
                    "vacation_entitlement": p.vacation_entitlement,
                    "non_vacation_entitlement": p.non_vacation_entitlement,
                    "enabled": p.enabled,
                })

        self.policies = rows
        self.loading = False
        self._load_nav_entries()

    # ── Open / close form ────────────────────────────────────────────────

    def open_edit(self, policy_id: str) -> None:
        self.flash = ""
        self.flash_type = "info"
        policy = next((p for p in self.policies if p["id"] == policy_id), None)
        if policy is None:
            self.flash = "Policy not found."
            self.flash_type = "error"
            return
        self.editing_id = policy_id
        self.form_vacation_entitlement = str(policy["vacation_entitlement"])
        self.form_non_vacation_entitlement = str(policy["non_vacation_entitlement"])
        self.form_enabled = policy["enabled"]
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self.editing_id = ""
        self.form_vacation_entitlement = ""
        self.form_non_vacation_entitlement = ""
        self.form_enabled = True
        self.flash = ""
        self.flash_type = "info"

    # ── Save ─────────────────────────────────────────────────────────────

    async def save_policy(self, form_data: dict) -> None:
        actor_id = UUID(self.current_user_id)
        editing_id = form_data.get("editing_id", "").strip()

        try:
            vacation_ent = float(form_data.get("form_vacation_entitlement", "").strip())
            non_vacation_ent = float(form_data.get("form_non_vacation_entitlement", "").strip())
        except (ValueError, AttributeError):
            self.flash = "Entitlement values must be numbers."
            self.flash_type = "error"
            return

        if vacation_ent <= 0 or non_vacation_ent <= 0:
            self.flash = "Entitlement values must be positive."
            self.flash_type = "error"
            return

        enabled_raw = form_data.get("form_enabled", "true")
        enabled = enabled_raw not in ("false", "False", False, "0", "")

        from durgam.models.leave import LeaveCreditPolicy
        from durgam.repositories.leave import LeaveCreditPolicyRepository

        resource_id = ""
        with open_session() as session:
            policy = session.get(LeaveCreditPolicy, UUID(editing_id))
            if policy is None or policy.is_deleted:
                self.flash = "Policy not found."
                self.flash_type = "error"
                return

            before_snap = audit_snapshot(policy)
            policy.vacation_entitlement = vacation_ent
            policy.non_vacation_entitlement = non_vacation_ent
            policy.enabled = enabled
            policy.updated_by = actor_id
            repo = LeaveCreditPolicyRepository(session)
            saved = repo.save(policy)
            after_snap = audit_snapshot(saved)
            resource_id = str(saved.id)

            write_audit_row(
                actor_user_id=actor_id,
                actor_role_code=None,
                action="configure",
                resource="leave_credit_policy",
                resource_id=resource_id,
                request_id=None,
                ip=None,
                user_agent=None,
                before=before_snap,
                after=after_snap,
                session=session,
            )
            session.commit()

        self.show_form = False
        self.editing_id = ""
        await self.load_policies()
        self.flash = "CL credit policy updated."
        self.flash_type = "success"
