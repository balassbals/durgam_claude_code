"""Leave-module repositories: LeaveRepository, LeaveBalanceRepository,
LeaveSanctionRuleRepository (M8).

Follows the HolidayRepository pattern for AY-lock enforcement.
"""
from __future__ import annotations

from datetime import UTC, datetime
from datetime import date as date_type
from uuid import UUID, uuid4

from sqlmodel import Session, select

from durgam.models.config_anchors import AcademicYear
from durgam.models.leave import (
    LeaveBalance,
    LeaveSanctionAuthorityRule,
    LeaveRequest,
)
from durgam.services.org_exceptions import AcademicYearLockedError


class LeaveSanctionRuleRepository:
    """CRUD for LeaveSanctionAuthorityRule (sanctioning matrix)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active(self) -> list[LeaveSanctionAuthorityRule]:
        return list(
            self._session.exec(
                select(LeaveSanctionAuthorityRule).where(
                    LeaveSanctionAuthorityRule.is_deleted == False  # noqa: E712
                )
            ).all()
        )

    def get(self, rule_id: UUID) -> LeaveSanctionAuthorityRule | None:
        row = self._session.get(LeaveSanctionAuthorityRule, rule_id)
        if row is None or row.is_deleted:
            return None
        return row

    def find_by_natural_key(
        self,
        leave_type: str,
        applicant_role_code: str,
        sanctioner_role_code: str,
        priority: int,
    ) -> LeaveSanctionAuthorityRule | None:
        """Return the rule matching the YAML natural key, including soft-deleted rows."""
        return self._session.exec(
            select(LeaveSanctionAuthorityRule).where(
                LeaveSanctionAuthorityRule.leave_type == leave_type,
                LeaveSanctionAuthorityRule.applicant_role_code == applicant_role_code,
                LeaveSanctionAuthorityRule.sanctioner_role_code == sanctioner_role_code,
                LeaveSanctionAuthorityRule.priority == priority,
            )
        ).first()

    def add(self, rule: LeaveSanctionAuthorityRule) -> None:
        self._session.add(rule)
        self._session.flush()
        self._session.refresh(rule)

    def save(self, rule: LeaveSanctionAuthorityRule) -> LeaveSanctionAuthorityRule:
        rule.updated_at = datetime.now(UTC)
        self._session.add(rule)
        self._session.flush()
        self._session.refresh(rule)
        return rule

    def soft_delete(self, rule_id: UUID, actor_id: UUID) -> None:
        row = self._session.get(LeaveSanctionAuthorityRule, rule_id)
        if row is None:
            return
        row.is_deleted = True
        row.deleted_at = datetime.now(UTC)
        row.deleted_by = actor_id
        row.updated_at = datetime.now(UTC)
        row.updated_by = actor_id
        self._session.add(row)
        self._session.flush()


class LeaveBalanceRepository:
    """AY-scoped leave balance with lock enforcement."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _check_ay_locked(self, ay_id: UUID) -> None:
        ay = self._session.get(AcademicYear, ay_id)
        if ay is not None and ay.is_locked:
            raise AcademicYearLockedError()

    def get(
        self, user_id: UUID, leave_type: str, ay_id: UUID
    ) -> LeaveBalance | None:
        return self._session.exec(
            select(LeaveBalance).where(
                LeaveBalance.employee_user_id == user_id,
                LeaveBalance.leave_type == leave_type,
                LeaveBalance.academic_year_id == ay_id,
                LeaveBalance.is_deleted == False,  # noqa: E712
            )
        ).first()

    def get_or_create(
        self,
        user_id: UUID,
        leave_type: str,
        ay_id: UUID,
        *,
        actor_id: UUID,
    ) -> LeaveBalance:
        """Return existing balance or create an all-zero row. Honors AY lock."""
        existing = self.get(user_id, leave_type, ay_id)
        if existing is not None:
            return existing
        self._check_ay_locked(ay_id)
        now = datetime.now(UTC)
        balance = LeaveBalance(
            id=uuid4(),
            employee_user_id=user_id,
            leave_type=leave_type,
            academic_year_id=ay_id,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(balance)
        self._session.flush()
        self._session.refresh(balance)
        return balance

    def list_for_user(self, user_id: UUID, ay_id: UUID) -> list[LeaveBalance]:
        return list(
            self._session.exec(
                select(LeaveBalance).where(
                    LeaveBalance.employee_user_id == user_id,
                    LeaveBalance.academic_year_id == ay_id,
                    LeaveBalance.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def save(self, balance: LeaveBalance) -> LeaveBalance:
        """Recompute closing_balance then persist. Honors AY lock."""
        self._check_ay_locked(balance.academic_year_id)
        balance.closing_balance = (
            balance.opening_balance
            + balance.credited
            - balance.availed
            - balance.forfeited
            - balance.encashed
        )
        balance.updated_at = datetime.now(UTC)
        self._session.add(balance)
        self._session.flush()
        self._session.refresh(balance)
        return balance


class LeaveRepository:
    """AY-scoped leave requests with lock enforcement."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _check_ay_locked(self, ay_id: UUID) -> None:
        ay = self._session.get(AcademicYear, ay_id)
        if ay is not None and ay.is_locked:
            raise AcademicYearLockedError()

    def get(self, request_id: UUID) -> LeaveRequest | None:
        row = self._session.get(LeaveRequest, request_id)
        if row is None or row.is_deleted:
            return None
        return row

    def list_for_user(self, user_id: UUID, ay_id: UUID) -> list[LeaveRequest]:
        return list(
            self._session.exec(
                select(LeaveRequest)
                .where(
                    LeaveRequest.requestor_user_id == user_id,
                    LeaveRequest.academic_year_id == ay_id,
                    LeaveRequest.is_deleted == False,  # noqa: E712
                )
                .order_by(LeaveRequest.starts_on.desc())  # type: ignore[union-attr]
            ).all()
        )

    def list_overlapping(
        self, user_id: UUID, starts_on: date_type, ends_on: date_type
    ) -> list[LeaveRequest]:
        """Return non-terminal requests that overlap [starts_on, ends_on].

        Used by check_combination; includes submitted / in_review / approved.
        """
        active_states = ("submitted", "in_review", "approved")
        return list(
            self._session.exec(
                select(LeaveRequest).where(
                    LeaveRequest.requestor_user_id == user_id,
                    LeaveRequest.state.in_(active_states),  # type: ignore[union-attr]
                    LeaveRequest.is_deleted == False,  # noqa: E712
                    LeaveRequest.starts_on <= ends_on,  # type: ignore[union-attr]
                    LeaveRequest.ends_on >= starts_on,  # type: ignore[union-attr]
                )
            ).all()
        )

    def add(self, req: LeaveRequest) -> None:
        self._check_ay_locked(req.academic_year_id)
        self._session.add(req)
        self._session.flush()
        self._session.refresh(req)

    def save(self, req: LeaveRequest) -> LeaveRequest:
        self._check_ay_locked(req.academic_year_id)
        req.updated_at = datetime.now(UTC)
        self._session.add(req)
        self._session.flush()
        self._session.refresh(req)
        return req
