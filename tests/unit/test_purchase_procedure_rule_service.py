"""Unit tests for PurchaseProcedureRuleService — CRUD + overlap validation."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.purchase_procedure_rule import (
    PurchaseProcedureRuleError,
    PurchaseProcedureRuleService,
)


class TestPurchaseProcedureRuleCreate:
    def _make_svc(self):
        repo = MagicMock()
        repo.list_by_fund_source.return_value = []
        return PurchaseProcedureRuleService(repo=repo), repo

    def test_create_success(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            fund_source="institute",
            tier=1,
            floor_amount=0,
            ceiling_amount=10_000,
            approving_authority_role_codes=["DIRECTOR"],
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()
        assert result.fund_source == "institute"
        assert result.tier == 1

    def test_invalid_fund_source_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(PurchaseProcedureRuleError, match="Fund source"):
            svc.create(
                fund_source="invalid",
                tier=1,
                floor_amount=0,
                ceiling_amount=10_000,
                approving_authority_role_codes=["DIRECTOR"],
                actor_id=uuid4(),
            )

    def test_tier_zero_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(PurchaseProcedureRuleError, match="Tier must be"):
            svc.create(
                fund_source="institute",
                tier=0,
                floor_amount=0,
                ceiling_amount=10_000,
                approving_authority_role_codes=["DIRECTOR"],
                actor_id=uuid4(),
            )

    def test_negative_floor_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(PurchaseProcedureRuleError, match="Floor amount"):
            svc.create(
                fund_source="institute",
                tier=1,
                floor_amount=-1,
                ceiling_amount=10_000,
                approving_authority_role_codes=["DIRECTOR"],
                actor_id=uuid4(),
            )

    def test_ceiling_less_than_floor_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(PurchaseProcedureRuleError, match="Ceiling must be greater"):
            svc.create(
                fund_source="institute",
                tier=1,
                floor_amount=10_000,
                ceiling_amount=5_000,
                approving_authority_role_codes=["DIRECTOR"],
                actor_id=uuid4(),
            )

    def test_empty_approvers_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(PurchaseProcedureRuleError, match="approving authority"):
            svc.create(
                fund_source="institute",
                tier=1,
                floor_amount=0,
                ceiling_amount=10_000,
                approving_authority_role_codes=[],
                actor_id=uuid4(),
            )

    def test_invalid_committee_level_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(PurchaseProcedureRuleError, match="Committee level"):
            svc.create(
                fund_source="institute",
                tier=1,
                floor_amount=0,
                ceiling_amount=10_000,
                approving_authority_role_codes=["DIRECTOR"],
                committee_level="invalid_committee",
                actor_id=uuid4(),
            )

    def test_no_ceiling_allowed(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            fund_source="institute",
            tier=5,
            floor_amount=1_000_000,
            ceiling_amount=None,
            approving_authority_role_codes=["BOM"],
            committee_level="central_purchase_committee",
            actor_id=uuid4(),
        )
        assert result.ceiling_amount is None


class TestPurchaseProcedureRuleOverlap:
    def _make_svc_with_existing(self, existing_rules):
        repo = MagicMock()
        repo.list_by_fund_source.return_value = existing_rules
        return PurchaseProcedureRuleService(repo=repo), repo

    def test_overlap_on_create_raises(self):
        existing = MagicMock()
        existing.id = uuid4()
        existing.tier = 1
        existing.floor_amount = 0
        existing.ceiling_amount = 10_000
        svc, repo = self._make_svc_with_existing([existing])
        repo.save.side_effect = lambda r: r

        with pytest.raises(PurchaseProcedureRuleError, match="overlaps"):
            svc.create(
                fund_source="institute",
                tier=2,
                floor_amount=5_000,
                ceiling_amount=20_000,
                approving_authority_role_codes=["DIRECTOR"],
                actor_id=uuid4(),
            )

    def test_no_overlap_on_create_succeeds(self):
        existing = MagicMock()
        existing.id = uuid4()
        existing.tier = 1
        existing.floor_amount = 0
        existing.ceiling_amount = 10_000
        svc, repo = self._make_svc_with_existing([existing])
        repo.save.side_effect = lambda r: r

        result = svc.create(
            fund_source="institute",
            tier=2,
            floor_amount=10_001,
            ceiling_amount=50_000,
            approving_authority_role_codes=["DIRECTOR"],
            actor_id=uuid4(),
        )
        assert result.tier == 2


class TestPurchaseProcedureRuleUpdate:
    def _make_svc(self):
        repo = MagicMock()
        return PurchaseProcedureRuleService(repo=repo), repo

    def test_update_success(self):
        svc, repo = self._make_svc()
        existing = MagicMock()
        existing.id = uuid4()
        existing.fund_source = "institute"
        existing.tier = 1
        existing.floor_amount = 0
        existing.ceiling_amount = 10_000
        existing.committee_level = None
        repo.get_by_id.return_value = existing
        repo.list_by_fund_source.return_value = [existing]
        repo.save.side_effect = lambda r: r

        result = svc.update(existing.id, {"notes": "Updated"}, uuid4())
        assert result.notes == "Updated"
        repo.save.assert_called_once()

    def test_update_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(PurchaseProcedureRuleError, match="not found"):
            svc.update(uuid4(), {}, uuid4())


class TestPurchaseProcedureRuleSoftDelete:
    def _make_svc(self):
        repo = MagicMock()
        return PurchaseProcedureRuleService(repo=repo), repo

    def test_soft_delete_success(self):
        svc, repo = self._make_svc()
        existing = MagicMock()
        repo.get_by_id.return_value = existing
        repo.soft_delete.side_effect = lambda r, a: r
        svc.soft_delete(uuid4(), uuid4())
        repo.soft_delete.assert_called_once()

    def test_soft_delete_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(PurchaseProcedureRuleError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())
