"""LeaveRequestService — orchestrates leave submission, withdrawal, approval, and cancellation.

Follows M7 ApprovalRequestService pattern: no @require_role/@audit_action decorators;
page-state handlers own permission enforcement. Service owns domain rules and audit emission.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlmodel import Session, select

from durgam.audit.log import write_audit_row
from durgam.audit.snapshot import audit_snapshot
from durgam.models.config_anchors import Holiday
from durgam.models.identity import Role, User, UserRole
from durgam.models.leave import LeaveBalance, LeaveRequest
from durgam.repositories.approval_process import ApprovalProcessRepository
from durgam.repositories.leave import (
    LeaveBalanceRepository,
    LeaveSanctionRuleRepository,
    LeaveRepository,
)
from durgam.services.approval_request import ApprovalRequestError, ApprovalRequestService
from durgam.services.leave_rules import (
    LeaveRuleError,
    check_balance,
    check_combination,
    check_eligibility,
    check_max_at_a_time,
    compute_leave_days,
    resolve_channel,
)

log = structlog.get_logger(__name__)


class LeaveRequestError(Exception):
    """Domain errors for the leave request service (non-rules-engine failures)."""


class LeaveRequestService:
    """Owns the LeaveRequest domain. Delegates state machine to ApprovalRequestService."""

    def __init__(
        self,
        session: Session,
        leave_repo: LeaveRepository,
        balance_repo: LeaveBalanceRepository,
        rule_repo: LeaveSanctionRuleRepository,
        approval_service: ApprovalRequestService,
    ) -> None:
        self._session = session
        self._leave_repo = leave_repo
        self._balance_repo = balance_repo
        self._rule_repo = rule_repo
        self._approval_service = approval_service

    def submit(
        self,
        *,
        requestor_user_id: UUID,
        leave_type: str,
        starts_on: date,
        ends_on: date,
        academic_year_id: UUID,
        reason: str,
        half_day: bool = False,
        half_day_which: str | None = None,
        address_during_leave: str | None = None,
        headquarters_left: bool = False,
        alternate_arrangement: str | None = None,
        intended_outside_india: bool = False,
        in_charge_designation: str | None = None,
        medical_cert_file_id: UUID | None = None,
        fitness_cert_file_id: UUID | None = None,
        bond_file_id: UUID | None = None,
        has_medical_cert: bool = False,
        exception_reason: str | None = None,
    ) -> LeaveRequest:
        # 1+2. Load user and build user_fields dict for eligibility checks.
        user = self._session.get(User, requestor_user_id)
        if user is None or user.is_deleted:
            raise LeaveRequestError("Requestor not found.")
        user_fields: dict[str, Any] = {
            "is_active": user.is_active,
            "gender": user.gender,
            "joined_on": user.joined_on,
            "employee_type": user.employee_type,
        }

        # 3. Fetch user role codes for channel resolution.
        user_role_rows = self._session.exec(
            select(UserRole).where(UserRole.user_id == requestor_user_id)
        ).all()
        user_roles: list[str] = []
        for ur in user_role_rows:
            role = self._session.get(Role, ur.role_id)
            if role is not None and not role.is_deleted:
                user_roles.append(role.code)

        # 4. Fetch holiday dates for the AY (CL excludes internal holidays).
        holidays_list = self._session.exec(
            select(Holiday).where(
                Holiday.academic_year_id == academic_year_id,
                Holiday.is_deleted == False,  # noqa: E712
            )
        ).all()
        holidays: set[date] = {h.holiday_date for h in holidays_list}

        # 5. Compute chargeable leave days.
        chargeable_days = compute_leave_days(
            starts_on, ends_on, leave_type, half_day, half_day_which, holidays
        )

        # 6. Total calendar span (prefix/suffix boundary-exclusion is caller's responsibility).
        total_span_days = (ends_on - starts_on).days + 1

        # 7. Eligibility check (ML service ≥ 1yr; SL service ≥ 5yr; active status).
        check_eligibility(user_fields, leave_type, chargeable_days)

        # 8. Balance check — EOL/SL have no running balance; CML debits HPL at 2×.
        if leave_type not in {"EOL", "SL"}:
            bal_leave_type = "HPL" if leave_type == "CML" else leave_type
            balance = self._balance_repo.get_or_create(
                requestor_user_id,
                bal_leave_type,
                academic_year_id,
                actor_id=requestor_user_id,
            )
            check_balance(leave_type, chargeable_days, balance)

        # 9. Max-at-a-time check (span limits, medical cert rules per §11.5–11.7).
        check_max_at_a_time(
            leave_type,
            chargeable_days,
            total_span_days=total_span_days,
            intended_outside_india=intended_outside_india,
            has_medical_cert=has_medical_cert,
            exception_reason=exception_reason,
        )

        # 10. Combination check — no overlapping active requests.
        overlapping = self._leave_repo.list_overlapping(requestor_user_id, starts_on, ends_on)
        check_combination(leave_type, overlapping)

        # 11. Resolve sanctioning channel from the active matrix (may raise LeaveChannelError).
        rules = self._rule_repo.list_active()
        channel = resolve_channel(user_roles, leave_type, rules)

        # 11b. If the matched rule requires an in-charge designation, validate it.
        matched_rule = self._match_rule(user_roles, leave_type, rules)
        if matched_rule is not None and matched_rule.requires_in_charge:
            if not in_charge_designation or not in_charge_designation.strip():
                raise LeaveRuleError("in-charge faculty designation required")

        # 12. Pre-generate the leave request ID so the approval payload can reference it
        #     before the LeaveRequest row exists. This resolves the circular FK:
        #     LeaveRequest.approval_request_id → ApprovalRequest (NOT NULL),
        #     ApprovalRequest.payload_json.leave_request_id → LeaveRequest (soft-ref).
        leave_req_id = uuid4()

        # 13. Submit to approval engine — persists ApprovalRequest and writes its audit row.
        proc_repo = ApprovalProcessRepository(self._session)
        process = proc_repo.get_by_code("LEAVE_APPROVAL")
        if process is None:
            raise LeaveRequestError("LEAVE_APPROVAL approval process not configured.")
        approval_request = self._approval_service.submit(
            process_id=process.id,
            requestor_user_id=requestor_user_id,
            title=f"{leave_type} {starts_on} to {ends_on}",
            payload={"leave_request_id": str(leave_req_id)},
            resolved_channel=channel,
        )

        # 14. Now approval_request.id is known — create and persist the LeaveRequest.
        now = datetime.now(UTC)
        leave_req = LeaveRequest(
            id=leave_req_id,
            requestor_user_id=requestor_user_id,
            academic_year_id=academic_year_id,
            leave_type=leave_type,
            starts_on=starts_on,
            ends_on=ends_on,
            half_day=half_day,
            half_day_which=half_day_which,
            chargeable_days=chargeable_days,
            reason=reason,
            address_during_leave=address_during_leave,
            headquarters_left=headquarters_left,
            alternate_arrangement=alternate_arrangement,
            intended_outside_india=intended_outside_india,
            in_charge_designation=in_charge_designation,
            state="submitted",
            medical_cert_file_id=medical_cert_file_id,
            fitness_cert_file_id=fitness_cert_file_id,
            bond_file_id=bond_file_id,
            approval_request_id=approval_request.id,
            created_by=requestor_user_id,
            updated_by=requestor_user_id,
            created_at=now,
            updated_at=now,
        )
        self._leave_repo.add(leave_req)

        # 15. Post-add sync for the auto-approval (skip-self) case.
        #     When the approval engine skips all stages during submit(), it calls
        #     _finalize_leave_from_approval BEFORE the LeaveRequest row is in the DB.
        #     That call returns early (leave_req not found). Re-run it now that the
        #     row is persisted so state and balance are correctly applied.
        if approval_request.state == "approved":
            self._approval_service.finalize_leave_if_auto_approved(
                approval_request.id, requestor_user_id
            )

        self._session.refresh(leave_req)  # pick up state change from finalize callback

        after_snap = audit_snapshot(leave_req)
        write_audit_row(
            actor_user_id=requestor_user_id,
            actor_role_code=None,
            action="create",
            resource="leave_request",
            resource_id=str(leave_req.id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=None,
            after=after_snap,
            session=self._session,
        )

        log.info(
            "leave_request_submitted",
            leave_id=str(leave_req.id),
            leave_type=leave_type,
            requestor=str(requestor_user_id),
            chargeable_days=chargeable_days,
            channel_stages=len(channel),
        )
        return leave_req

    def withdraw(
        self,
        leave_request_id: UUID,
        requestor_user_id: UUID,
    ) -> LeaveRequest:
        leave_req = self._leave_repo.get(leave_request_id)
        if leave_req is None:
            raise LeaveRequestError("Leave request not found.")
        if leave_req.requestor_user_id != requestor_user_id:
            raise LeaveRequestError("Only the requestor can withdraw their own leave request.")

        before_snap = audit_snapshot(leave_req)
        # Engine's _run_post_withdrawal callback mirrors state to leave_req via _update_leave_state.
        self._approval_service.withdraw(
            request_id=leave_req.approval_request_id,
            requestor_user_id=requestor_user_id,
        )
        # Re-fetch after callback has updated the state.
        refreshed = self._leave_repo.get(leave_request_id)
        if refreshed is None:
            raise LeaveRequestError("Leave request disappeared after withdrawal.")

        write_audit_row(
            actor_user_id=requestor_user_id,
            actor_role_code=None,
            action="withdraw",
            resource="leave_request",
            resource_id=str(leave_request_id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap,
            after={"state": "withdrawn"},
            session=self._session,
        )
        return refreshed

    def cancel(
        self,
        leave_request_id: UUID,
        actor_id: UUID,
        reason: str,
    ) -> LeaveRequest:
        leave_req = self._leave_repo.get(leave_request_id)
        if leave_req is None:
            raise LeaveRequestError("Leave request not found.")

        before_snap = audit_snapshot(leave_req)
        self._approval_service.cancel(
            request_id=leave_req.approval_request_id,
            sys_admin_user_id=actor_id,
            comment=reason,
        )
        leave_req.cancellation_reason = reason
        leave_req.state = "cancelled"
        self._leave_repo.save(leave_req)

        write_audit_row(
            actor_user_id=actor_id,
            actor_role_code=None,
            action="cancel",
            resource="leave_request",
            resource_id=str(leave_request_id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap,
            after={"state": "cancelled", "cancellation_reason": reason},
            session=self._session,
        )
        return leave_req

    def set_sanctioned_days(
        self,
        leave_request_id: UUID,
        approver_user_id: UUID,
        sanctioned_days: float,
    ) -> LeaveRequest:
        leave_req = self._leave_repo.get(leave_request_id)
        if leave_req is None:
            raise LeaveRequestError("Leave request not found.")
        if sanctioned_days <= 0 or sanctioned_days > leave_req.chargeable_days:
            raise LeaveRequestError(
                f"sanctioned_days must be > 0 and ≤ chargeable_days "
                f"({leave_req.chargeable_days}); got {sanctioned_days}"
            )

        before_snap = audit_snapshot(leave_req)
        leave_req.sanctioned_days = sanctioned_days
        self._leave_repo.save(leave_req)

        write_audit_row(
            actor_user_id=approver_user_id,
            actor_role_code=None,
            action="set_sanctioned_days",
            resource="leave_request",
            resource_id=str(leave_request_id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap,
            after={"sanctioned_days": sanctioned_days},
            session=self._session,
        )
        return leave_req

    def get_balances_for_user(
        self,
        user_id: UUID,
        academic_year_id: UUID,
    ) -> list[LeaveBalance]:
        return self._balance_repo.list_for_user(user_id, academic_year_id)

    # ── Private helpers ─────────────────────────────────────────────────

    def _match_rule(
        self, user_roles: list[str], leave_type: str, rules: list[Any]
    ) -> Any | None:
        """Return the highest-priority matching sanctioning rule, or None.

        Mirrors the rule-selection algorithm in resolve_channel so the service
        can inspect requires_in_charge without re-opening that function.
        """
        candidates = [
            r for r in rules
            if (r.leave_type == leave_type or r.leave_type == "*")
            and (r.applicant_role_code in user_roles or r.applicant_role_code == "*")
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda r: r.priority)[0]
