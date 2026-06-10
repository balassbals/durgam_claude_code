"""State for leave request admin edit page — /admin/leave/request-edit (M8.1 E-022 Phase 8)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import reflex as rx

from durgam.db import open_session
from durgam.states.base import BaseState

_LEAVE_STATES = ["submitted", "in_review", "approved", "rejected", "withdrawn", "cancelled"]
_LEAVE_TYPES = ["CL", "SCL", "EL", "HPL", "CML", "EOL", "ML", "SL"]

_ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "submitted": ["cancelled", "rejected"],
    "in_review":  ["cancelled", "rejected"],
    "approved":   ["cancelled", "withdrawn"],
}


class LeaveRequestAdminState(BaseState):
    # ── Filter state ─────────────────────────────────────────────────
    username_filter: str = ""
    leave_type_filter: str = "all"
    state_filter: str = "all"

    # ── Results ──────────────────────────────────────────────────────
    rows: list[dict[str, Any]] = []
    loading: bool = True

    # ── Edit modal state ─────────────────────────────────────────────
    show_edit_modal: bool = False
    edit_request_id: str = ""
    edit_username: str = ""
    edit_leave_type: str = ""
    edit_starts_on: str = ""
    edit_ends_on: str = ""
    edit_sanctioned_days: str = ""
    edit_current_state: str = ""
    edit_is_post_facto: bool = False
    edit_new_state: str = ""
    edit_reason: str = ""

    # ── Flash ────────────────────────────────────────────────────────
    flash: str = ""
    flash_type: str = "info"

    # ── Computed vars ────────────────────────────────────────────────

    @rx.var
    def allowed_new_states(self) -> list[str]:
        return _ALLOWED_TRANSITIONS.get(self.edit_current_state, [])

    @rx.var
    def is_save_valid(self) -> bool:
        return (
            self.edit_new_state != ""
            and self.edit_new_state in _ALLOWED_TRANSITIONS.get(self.edit_current_state, [])
            and len(self.edit_reason.strip()) >= 1
        )

    # ── Filter setters ───────────────────────────────────────────────

    def set_username_filter(self, value: str) -> None:
        self.username_filter = value

    def set_leave_type_filter(self, value: str) -> None:
        self.leave_type_filter = value

    def set_state_filter(self, value: str) -> None:
        self.state_filter = value

    def set_edit_new_state(self, value: str) -> None:
        self.edit_new_state = value

    def set_edit_reason(self, value: str) -> None:
        self.edit_reason = value

    # ── Flash helper ─────────────────────────────────────────────────

    def dismiss_flash(self) -> None:
        self.flash = ""
        self.flash_type = "info"

    # ── Page-load / filter handlers ──────────────────────────────────

    async def load_admin_requests(self) -> rx.Component | None:
        guard = self._config_guard("leave_request_admin", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.rows = []
        with open_session() as session:
            from durgam.repositories.leave import LeaveRepository

            repo = LeaveRepository(session)
            lt_filter = self.leave_type_filter if self.leave_type_filter != "all" else None
            st_filter = self.state_filter if self.state_filter != "all" else None
            un_filter = self.username_filter.strip() or None

            results = repo.admin_search(
                username_filter=un_filter,
                leave_type_filter=lt_filter,
                state_filter=st_filter,
            )
            self.rows = [
                {
                    "id": str(req.id),
                    "username": user.username,
                    "leave_type": req.leave_type,
                    "starts_on": str(req.starts_on),
                    "ends_on": str(req.ends_on),
                    "sanctioned_days": str(req.sanctioned_days or req.chargeable_days),
                    "state": req.state,
                    "is_post_facto": req.is_post_facto,
                    "allowed_transitions": _ALLOWED_TRANSITIONS.get(req.state, []),
                }
                for req, user in results
            ]
        self.loading = False
        self._load_nav_entries()
        return None

    async def apply_filters(self) -> None:
        await self.load_admin_requests()

    async def clear_filters(self) -> None:
        self.username_filter = ""
        self.leave_type_filter = "all"
        self.state_filter = "all"
        await self.load_admin_requests()

    # ── Edit modal lifecycle ─────────────────────────────────────────

    def open_edit_modal(
        self,
        request_id: str,
        username: str,
        leave_type: str,
        starts_on: str,
        ends_on: str,
        sanctioned_days: str,
        current_state: str,
        is_post_facto: bool,
    ) -> None:
        self.edit_request_id = request_id
        self.edit_username = username
        self.edit_leave_type = leave_type
        self.edit_starts_on = starts_on
        self.edit_ends_on = ends_on
        self.edit_sanctioned_days = sanctioned_days
        self.edit_current_state = current_state
        self.edit_is_post_facto = is_post_facto
        self.edit_new_state = ""
        self.edit_reason = ""
        self.flash = ""
        self.flash_type = "info"
        self.show_edit_modal = True

    def close_edit_modal(self) -> None:
        self.show_edit_modal = False
        self.edit_request_id = ""
        self.edit_new_state = ""
        self.edit_reason = ""

    async def submit_edit(self, form_data: dict) -> None:
        guard = self._config_guard("leave_request_admin", "write")
        if guard is not None:
            return guard
        request_id = self.edit_request_id
        if not request_id:
            return
        new_state = self.edit_new_state.strip()
        reason = self.edit_reason.strip()
        if not new_state:
            self.flash = "Please select a new state."
            self.flash_type = "error"
            return
        if not reason:
            self.flash = "Reason is required."
            self.flash_type = "error"
            return
        actor_id = UUID(self.current_user_id)
        with open_session() as session:
            from durgam.repositories.leave import (
                LeaveBalanceRepository,
                LeaveSanctionRuleRepository,
                LeaveRepository,
            )
            from durgam.repositories.approval_process import ApprovalProcessRepository
            from durgam.repositories.approval_request import ApprovalRequestRepository
            from durgam.services.approval_request import ApprovalRequestService
            from durgam.services.leave_request import LeaveRequestError, LeaveRequestService

            try:
                approval_svc = ApprovalRequestService(
                    session=session,
                    repo=ApprovalRequestRepository(session),
                    process_repo=ApprovalProcessRepository(session),
                )
                svc = LeaveRequestService(
                    session=session,
                    leave_repo=LeaveRepository(session),
                    balance_repo=LeaveBalanceRepository(session),
                    rule_repo=LeaveSanctionRuleRepository(session),
                    approval_service=approval_svc,
                )
                svc.admin_change_state(
                    leave_request_id=UUID(request_id),
                    new_state=new_state,
                    actor_user_id=actor_id,
                    reason=reason,
                )
                session.commit()
            except (LeaveRequestError, ValueError) as e:
                self.flash = str(e)
                self.flash_type = "error"
                return

        self.close_edit_modal()
        await self.load_admin_requests()
        self.flash = f"Request state changed to '{new_state}'."
        self.flash_type = "success"
