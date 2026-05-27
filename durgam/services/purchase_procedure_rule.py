"""PurchaseProcedureRuleService — CRUD + overlap validation (E-007)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import PurchaseProcedureRule
from durgam.repositories.purchase_procedure_rule import PurchaseProcedureRuleRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)

_VALID_FUND_SOURCES = ("institute", "projects_ugc")
_VALID_COMMITTEE_LEVELS = (None, "campus_purchase_committee", "central_purchase_committee")


class PurchaseProcedureRuleError(OrgServiceError):
    pass


class PurchaseProcedureRuleService:
    def __init__(self, repo: PurchaseProcedureRuleRepository) -> None:
        self._repo = repo

    def list_by_fund_source(self, fund_source: str) -> list[PurchaseProcedureRule]:
        return self._repo.list_by_fund_source(fund_source)

    def list_all(self) -> list[PurchaseProcedureRule]:
        return self._repo.list_all_active()

    def _validate_common(
        self,
        fund_source: str,
        tier: int,
        floor_amount: int,
        ceiling_amount: int | None,
        committee_level: str | None,
    ) -> None:
        if fund_source not in _VALID_FUND_SOURCES:
            raise PurchaseProcedureRuleError(
                f"Fund source must be one of: {', '.join(_VALID_FUND_SOURCES)}."
            )
        if tier < 1:
            raise PurchaseProcedureRuleError("Tier must be 1 or greater.")
        if floor_amount < 0:
            raise PurchaseProcedureRuleError("Floor amount must be non-negative.")
        if ceiling_amount is not None and ceiling_amount <= floor_amount:
            raise PurchaseProcedureRuleError("Ceiling must be greater than floor.")
        if committee_level not in _VALID_COMMITTEE_LEVELS:
            raise PurchaseProcedureRuleError(
                "Committee level must be None, 'campus_purchase_committee', "
                "or 'central_purchase_committee'."
            )

    def _check_overlap(
        self, fund_source: str, floor_amount: int,
        ceiling_amount: int | None, exclude_id: UUID | None = None,
    ) -> None:
        """Reject if any existing same-fund-source tier has overlapping range.

        exclude_id: when updating, exclude the row being updated from the
        overlap check (fix #1 — self-collision prevention).
        """
        existing = self._repo.list_by_fund_source(fund_source)
        for rule in existing:
            if exclude_id is not None and rule.id == exclude_id:
                continue
            existing_floor = rule.floor_amount
            existing_ceiling = rule.ceiling_amount
            if self._ranges_overlap(
                floor_amount, ceiling_amount, existing_floor, existing_ceiling,
            ):
                raise PurchaseProcedureRuleError(
                    f"Range {floor_amount}-{ceiling_amount} overlaps with "
                    f"tier {rule.tier} ({existing_floor}-{existing_ceiling})."
                )

    @staticmethod
    def _ranges_overlap(
        a_floor: int, a_ceiling: int | None,
        b_floor: int, b_ceiling: int | None,
    ) -> bool:
        a_max = a_ceiling if a_ceiling is not None else float("inf")
        b_max = b_ceiling if b_ceiling is not None else float("inf")
        return a_floor < b_max and b_floor < a_max

    def create(
        self,
        *,
        fund_source: str,
        tier: int,
        floor_amount: int,
        ceiling_amount: int | None,
        min_quotes_required: bool = True,
        min_quote_count: int = 3,
        quote_at_discretion: bool = False,
        comparative_statement_required: bool = False,
        approving_authority_role_codes: list[str],
        committee_level: str | None = None,
        actor_id: UUID,
        notes: str | None = None,
    ) -> PurchaseProcedureRule:
        fund_source = fund_source.strip()
        self._validate_common(
            fund_source, tier, floor_amount, ceiling_amount, committee_level,
        )
        if not approving_authority_role_codes:
            raise PurchaseProcedureRuleError("At least one approving authority is required.")
        self._check_overlap(fund_source, floor_amount, ceiling_amount)

        now = datetime.now(UTC)
        record = PurchaseProcedureRule(
            fund_source=fund_source,
            tier=tier,
            floor_amount=floor_amount,
            ceiling_amount=ceiling_amount,
            min_quotes_required=min_quotes_required,
            min_quote_count=min_quote_count,
            quote_at_discretion=quote_at_discretion,
            comparative_statement_required=comparative_statement_required,
            approving_authority_role_codes=approving_authority_role_codes,
            committee_level=committee_level,
            notes=notes,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("purchase_procedure_rule_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> PurchaseProcedureRule:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise PurchaseProcedureRuleError("Purchase procedure rule not found.")

        new_fund_source = fields.get("fund_source", record.fund_source)
        new_floor = fields.get("floor_amount", record.floor_amount)
        new_ceiling = fields.get("ceiling_amount", record.ceiling_amount)
        new_committee = fields.get("committee_level", record.committee_level)
        new_tier = fields.get("tier", record.tier)
        self._validate_common(
            new_fund_source, new_tier, new_floor, new_ceiling, new_committee,
        )
        self._check_overlap(
            new_fund_source, new_floor, new_ceiling, exclude_id=record_id,
        )

        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("purchase_procedure_rule_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> PurchaseProcedureRule:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise PurchaseProcedureRuleError("Purchase procedure rule not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("purchase_procedure_rule_deleted", id=str(record_id), actor=str(actor_id))
        return record
