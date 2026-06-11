"""Leave Balance Import Service — two-phase bulk import (M8.1 E-016).

Two-phase API:
  validate(csv_text) → parse CSV, look up users, return valid + invalid rows (no DB writes).
  commit(valid_rows, actor_id) → upsert balances, write audit rows, session.commit().

AY resolution: most recent unlocked AY straddling today; fallback to most recent
unlocked AY; None if no unlocked AY exists (commit raises AcademicYearLockedError).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import UTC, date as date_type, datetime
from uuid import UUID

from sqlmodel import Session, select

from durgam.audit.log import write_audit_row
from durgam.models.config_anchors import AcademicYear
from durgam.models.identity import User
from durgam.models.leave import LeaveBalance
from durgam.repositories.leave import LeaveBalanceRepository
from durgam.services.org_exceptions import AcademicYearLockedError

# M8 leave types (excluding "*" wildcard which is only for the sanction matrix).
VALID_LEAVE_TYPES: frozenset[str] = frozenset(
    {"CL", "SCL", "EL", "HPL", "CML", "EOL", "ML", "SL"}
)

_CSV_COLUMNS = [
    "employee_username",
    "leave_type",
    "opening_balance",
    "credited",
    "availed",
    "forfeited",
    "encashed",
]
_BALANCE_NUMERIC_FIELDS = ["opening_balance", "credited", "availed", "forfeited", "encashed"]


class CSVFormatError(ValueError):
    """Raised when the CSV structure itself is malformed (wrong columns, empty file)."""


@dataclass
class ImportPreviewRow:
    """One parsed + validated row from the import CSV."""

    row_number: int
    employee_username: str
    leave_type: str
    opening_balance: float = 0.0
    credited: float = 0.0
    availed: float = 0.0
    forfeited: float = 0.0
    encashed: float = 0.0
    closing_balance: float = 0.0
    user_id: UUID | None = None
    error_reason: str = ""
    is_valid: bool = True


@dataclass
class ImportValidationResult:
    valid_rows: list[ImportPreviewRow] = field(default_factory=list)
    invalid_rows: list[ImportPreviewRow] = field(default_factory=list)


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    audit_rows_written: int = 0


class LeaveBalanceImportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._balances = LeaveBalanceRepository(session)

    # ── AY resolution ──────────────────────────────────────────────────────────

    def resolve_active_ay(self) -> AcademicYear | None:
        """Return the AY to import into.

        Preference:
        1. Unlocked AY where starts_on <= today <= ends_on (straddles today).
        2. Most recent (by starts_on DESC) unlocked AY as fallback.
        3. None if no unlocked AY exists.
        """
        today = date_type.today()
        straddle = self._session.exec(
            select(AcademicYear)
            .where(
                AcademicYear.is_locked == False,  # noqa: E712
                AcademicYear.is_deleted == False,  # noqa: E712
                AcademicYear.starts_on <= today,
                AcademicYear.ends_on >= today,
            )
            .order_by(AcademicYear.starts_on.desc())  # type: ignore[union-attr]
            .limit(1)
        ).first()
        if straddle is not None:
            return straddle
        return self._session.exec(
            select(AcademicYear)
            .where(
                AcademicYear.is_locked == False,  # noqa: E712
                AcademicYear.is_deleted == False,  # noqa: E712
            )
            .order_by(AcademicYear.starts_on.desc())  # type: ignore[union-attr]
            .limit(1)
        ).first()

    # ── Phase 1: validate ──────────────────────────────────────────────────────

    def validate(self, csv_text: str) -> ImportValidationResult:
        """Parse and validate CSV text. Pure read; NO DB mutations.

        Raises CSVFormatError for structural issues (wrong columns, empty file).
        Per-row errors (unknown user, bad value) are returned as invalid_rows.
        """
        parsed = _parse_csv(csv_text)
        valid: list[ImportPreviewRow] = []
        invalid: list[ImportPreviewRow] = []
        for row_num, raw in enumerate(parsed, start=2):
            result = self._validate_row(row_num, raw)
            if result.is_valid:
                valid.append(result)
            else:
                invalid.append(result)
        return ImportValidationResult(valid_rows=valid, invalid_rows=invalid)

    def _validate_row(self, row_num: int, raw: dict[str, str]) -> ImportPreviewRow:
        username = raw["employee_username"].strip()
        leave_type = raw["leave_type"].strip()

        # 1. Validate leave_type first (cheapest check, no DB).
        if leave_type not in VALID_LEAVE_TYPES:
            return ImportPreviewRow(
                row_number=row_num,
                employee_username=username,
                leave_type=leave_type,
                error_reason=f"unknown leave_type '{leave_type}'",
                is_valid=False,
            )

        # 2. Parse and range-check each numeric field.
        floats: dict[str, float] = {}
        for fname in _BALANCE_NUMERIC_FIELDS:
            raw_val = raw[fname].strip()
            try:
                floats[fname] = float(raw_val)
            except ValueError:
                return ImportPreviewRow(
                    row_number=row_num,
                    employee_username=username,
                    leave_type=leave_type,
                    error_reason=f"non-numeric value '{raw_val}' in column '{fname}'",
                    is_valid=False,
                )
            if floats[fname] < 0:
                return ImportPreviewRow(
                    row_number=row_num,
                    employee_username=username,
                    leave_type=leave_type,
                    error_reason=f"negative value {floats[fname]:.2f} in column '{fname}'",
                    is_valid=False,
                )

        # 3. Compute closing_balance; must be >= 0.
        closing = (
            floats["opening_balance"]
            + floats["credited"]
            - floats["availed"]
            - floats["forfeited"]
            - floats["encashed"]
        )
        if closing < 0:
            return ImportPreviewRow(
                row_number=row_num,
                employee_username=username,
                leave_type=leave_type,
                error_reason=f"negative closing balance ({closing:.2f})",
                is_valid=False,
            )

        # 4. Resolve user (first DB access — after all cheap checks pass).
        user = self._session.exec(
            select(User).where(
                User.username == username,
                User.is_deleted == False,  # noqa: E712
            )
        ).first()
        if user is None:
            return ImportPreviewRow(
                row_number=row_num,
                employee_username=username,
                leave_type=leave_type,
                error_reason=f"unknown employee_username '{username}'",
                is_valid=False,
            )

        return ImportPreviewRow(
            row_number=row_num,
            employee_username=username,
            leave_type=leave_type,
            opening_balance=floats["opening_balance"],
            credited=floats["credited"],
            availed=floats["availed"],
            forfeited=floats["forfeited"],
            encashed=floats["encashed"],
            closing_balance=closing,
            user_id=user.id,
            is_valid=True,
        )

    # ── Phase 2: commit ────────────────────────────────────────────────────────

    def commit(
        self, valid_rows: list[ImportPreviewRow], actor_id: UUID
    ) -> ImportResult:
        """Upsert all valid rows in a single transaction, write one audit row per row.

        DD-M8.1-P3-3: Audit rows are written even on re-import of identical data.
        One audit row per commit invocation per row is a faithful record of admin actions.
        """
        ay = self.resolve_active_ay()
        if ay is None:
            raise AcademicYearLockedError()

        result = ImportResult()
        for row in valid_rows:
            assert row.user_id is not None  # guaranteed valid by validate()
            fields = {
                "opening_balance": row.opening_balance,
                "credited": row.credited,
                "availed": row.availed,
                "forfeited": row.forfeited,
                "encashed": row.encashed,
                "closing_balance": row.closing_balance,
            }
            balance, before_snap, after_snap = self._balances.upsert_balance_from_import(
                user_id=row.user_id,
                leave_type=row.leave_type,
                ay_id=ay.id,
                fields=fields,
                actor_id=actor_id,
            )
            if before_snap:
                result.updated += 1
            else:
                result.created += 1

            # Audit row written by the SERVICE (not the repo) so the action reflects
            # the import operation. Before is None for new rows (creation diff).
            write_audit_row(
                actor_user_id=actor_id,
                actor_role_code=None,
                action="import",
                resource="leave_balance",
                resource_id=str(balance.id),
                request_id=None,
                ip=None,
                user_agent=None,
                before=before_snap if before_snap else None,
                after=after_snap,
                session=self._session,
            )
            result.audit_rows_written += 1

        self._session.commit()
        return result

    def commit_single(
        self,
        employee_username: str,
        leave_type: str,
        opening_balance: float,
        credited: float,
        availed: float,
        forfeited: float,
        encashed: float,
        actor_id: UUID,
    ) -> tuple[LeaveBalance, dict, dict]:
        """Single-row variant for the per-employee admin form (Phase 4 UI)."""
        closing = opening_balance + credited - availed - forfeited - encashed
        ay = self.resolve_active_ay()
        if ay is None:
            raise AcademicYearLockedError()

        user = self._session.exec(
            select(User).where(
                User.username == employee_username,
                User.is_deleted == False,  # noqa: E712
            )
        ).first()
        if user is None:
            raise ValueError(f"Unknown employee_username '{employee_username}'")

        fields = {
            "opening_balance": opening_balance,
            "credited": credited,
            "availed": availed,
            "forfeited": forfeited,
            "encashed": encashed,
            "closing_balance": closing,
        }
        balance, before_snap, after_snap = self._balances.upsert_balance_from_import(
            user_id=user.id,
            leave_type=leave_type,
            ay_id=ay.id,
            fields=fields,
            actor_id=actor_id,
        )
        write_audit_row(
            actor_user_id=actor_id,
            actor_role_code=None,
            action="import",
            resource="leave_balance",
            resource_id=str(balance.id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap if before_snap else None,
            after=after_snap,
            session=self._session,
        )
        self._session.commit()
        return balance, before_snap, after_snap

    def admin_edit_balance(
        self,
        balance_id: UUID,
        fields: dict,
        actor_id: UUID,
    ) -> "LeaveBalance":
        """Update a single balance row from the admin edit UI.

        Wraps the repo admin_update_balance call plus a write_audit_row inside
        the service transaction. The caller must session.commit() after this returns.
        Raises LeaveBalanceValidationError or AcademicYearLockedError on invalid input.
        """
        from durgam.repositories.leave import LeaveBalanceRepository

        repo = LeaveBalanceRepository(self._session)
        balance, before_snap, after_snap = repo.admin_update_balance(
            balance_id=balance_id,
            fields=fields,
            actor_id=actor_id,
        )
        write_audit_row(
            actor_user_id=actor_id,
            actor_role_code=None,
            action="admin_edit",
            resource="leave_balance",
            resource_id=str(balance.id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap if before_snap else None,
            after=after_snap,
            session=self._session,
        )
        return balance


# ── CSV parser (module-level, no DB dependency) ────────────────────────────────


def _parse_csv(csv_text: str) -> list[dict[str, str]]:
    """Parse raw CSV text into a list of row dicts.

    Raises CSVFormatError for structural issues: empty file, missing header,
    wrong column count, wrong column names.
    """
    if not csv_text or not csv_text.strip():
        raise CSVFormatError("Empty CSV: file has no content")

    reader = csv.reader(io.StringIO(csv_text))
    all_rows = list(reader)

    if not all_rows:
        raise CSVFormatError("Empty CSV: no rows found")

    # First row is the header.
    header = [h.strip() for h in all_rows[0]]
    if header != _CSV_COLUMNS:
        extra = sorted(set(header) - set(_CSV_COLUMNS))
        missing = sorted(set(_CSV_COLUMNS) - set(header))
        if extra and not missing:
            raise CSVFormatError(f"Extra CSV columns: {', '.join(extra)}")
        if missing and not extra:
            raise CSVFormatError(f"Missing CSV columns: {', '.join(missing)}")
        raise CSVFormatError(
            f"CSV columns do not match expected. Expected: {_CSV_COLUMNS}, got: {header}"
        )

    rows: list[dict[str, str]] = []
    for raw_row in all_rows[1:]:
        if len(raw_row) != len(_CSV_COLUMNS):
            raise CSVFormatError(
                f"Row has {len(raw_row)} columns, expected {len(_CSV_COLUMNS)}"
            )
        rows.append({k: v.strip() for k, v in zip(_CSV_COLUMNS, raw_row)})

    return rows
