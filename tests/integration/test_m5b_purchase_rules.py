"""Integration tests for PurchaseProcedureRule — CRUD + overlap + unique constraint.

Key tests:
- PurchaseProcedureRule CRUD with real database
- Overlap on insert: overlapping range raises PurchaseProcedureRuleError
- Overlap-excluding-self on update: updating a tier in place SUCCEEDS (fix #1)
- Overlap on update with different tier: still raises PurchaseProcedureRuleError
- Unique constraint: duplicate (fund_source, tier) raises IntegrityError
- list_by_fund_source returns active only, ordered by tier
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from durgam.models.config_anchors import PurchaseProcedureRule
from durgam.models.identity import User
from durgam.repositories.purchase_procedure_rule import PurchaseProcedureRuleRepository
from durgam.services.purchase_procedure_rule import (
    PurchaseProcedureRuleError,
    PurchaseProcedureRuleService,
)


def _user(session) -> User:
    from durgam.services.password import hash_password

    u = User(
        username=f"t{uuid4().hex[:8]}",
        email=f"t{uuid4().hex[:8]}@test.com",
        full_name="Test User",
        password_hash=hash_password("Test_Pass1!XZ"),
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _svc(session) -> PurchaseProcedureRuleService:
    return PurchaseProcedureRuleService(repo=PurchaseProcedureRuleRepository(session))


class TestPurchaseProcedureRuleCRUD:
    def test_create_and_list(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            fund_source="institute",
            tier=1,
            floor_amount=0,
            ceiling_amount=10_000,
            approving_authority_role_codes=["DIRECTOR"],
            actor_id=user.id,
        )
        assert created.id is not None
        assert created.fund_source == "institute"
        assert created.tier == 1
        assert created.approving_authority_role_codes == ["DIRECTOR"]

        results = svc.list_by_fund_source("institute")
        assert len(results) >= 1
        assert any(r.id == created.id for r in results)

    def test_update(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            fund_source="institute",
            tier=2,
            floor_amount=10_001,
            ceiling_amount=50_000,
            approving_authority_role_codes=["DIRECTOR"],
            actor_id=user.id,
        )
        updated = svc.update(created.id, {"notes": "Updated notes"}, user.id)
        assert updated.notes == "Updated notes"

    def test_soft_delete_excludes_from_list(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            fund_source="projects_ugc",
            tier=1,
            floor_amount=0,
            ceiling_amount=10_000,
            approving_authority_role_codes=["HOD", "DIRECTOR"],
            actor_id=user.id,
        )
        svc.soft_delete(created.id, user.id)
        results = svc.list_by_fund_source("projects_ugc")
        assert not any(r.id == created.id for r in results)


class TestPurchaseProcedureRuleOverlap:
    def test_overlap_on_create_raises(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        svc.create(
            fund_source="institute",
            tier=1,
            floor_amount=0,
            ceiling_amount=10_000,
            approving_authority_role_codes=["DIRECTOR"],
            actor_id=user.id,
        )
        with pytest.raises(PurchaseProcedureRuleError, match="overlaps"):
            svc.create(
                fund_source="institute",
                tier=2,
                floor_amount=5_000,
                ceiling_amount=20_000,
                approving_authority_role_codes=["DIRECTOR"],
                actor_id=user.id,
            )

    def test_no_overlap_on_create_succeeds(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        svc.create(
            fund_source="projects_ugc",
            tier=1,
            floor_amount=0,
            ceiling_amount=10_000,
            approving_authority_role_codes=["HOD"],
            actor_id=user.id,
        )
        tier2 = svc.create(
            fund_source="projects_ugc",
            tier=2,
            floor_amount=10_001,
            ceiling_amount=50_000,
            approving_authority_role_codes=["DIRECTOR"],
            actor_id=user.id,
        )
        assert tier2.id is not None

    def test_update_in_place_does_not_self_collide(self, db_session):
        """Fix #1: updating a tier's notes (no range change) must NOT raise overlap."""
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            fund_source="institute",
            tier=3,
            floor_amount=50_001,
            ceiling_amount=499_999,
            approving_authority_role_codes=["REGISTRAR"],
            committee_level="campus_purchase_committee",
            actor_id=user.id,
        )
        updated = svc.update(created.id, {"notes": "In-place update"}, user.id)
        assert updated.notes == "In-place update"

    def test_update_overlap_with_different_tier_raises(self, db_session):
        """Fix #1 complement: update to overlap a DIFFERENT tier still fails."""
        user = _user(db_session)
        svc = _svc(db_session)

        svc.create(
            fund_source="institute",
            tier=4,
            floor_amount=500_000,
            ceiling_amount=999_999,
            approving_authority_role_codes=["VC"],
            committee_level="central_purchase_committee",
            actor_id=user.id,
        )
        tier5 = svc.create(
            fund_source="institute",
            tier=5,
            floor_amount=1_000_000,
            ceiling_amount=None,
            approving_authority_role_codes=["BOM"],
            committee_level="central_purchase_committee",
            actor_id=user.id,
        )
        with pytest.raises(PurchaseProcedureRuleError, match="overlaps"):
            svc.update(
                tier5.id,
                {"floor_amount": 800_000},
                user.id,
            )


class TestPurchaseProcedureRuleUniqueConstraint:
    def test_duplicate_fund_source_tier_raises(self, db_session):
        """Bypass service overlap validation by inserting directly via repo,
        then use service create to hit the DB unique constraint."""
        user = _user(db_session)
        repo = PurchaseProcedureRuleRepository(db_session)

        from datetime import UTC, datetime

        now = datetime.now(UTC)
        row = PurchaseProcedureRule(
            fund_source="projects_ugc",
            tier=3,
            floor_amount=50_001,
            ceiling_amount=499_999,
            approving_authority_role_codes=["REGISTRAR"],
            committee_level="campus_purchase_committee",
            created_by=user.id,
            updated_by=user.id,
            created_at=now,
            updated_at=now,
        )
        repo.save(row)

        with pytest.raises(IntegrityError):
            dup = PurchaseProcedureRule(
                fund_source="projects_ugc",
                tier=3,
                floor_amount=600_000,
                ceiling_amount=999_999,
                approving_authority_role_codes=["VC"],
                committee_level="central_purchase_committee",
                created_by=user.id,
                updated_by=user.id,
                created_at=now,
                updated_at=now,
            )
            repo.save(dup)

    def test_different_fund_source_same_tier_succeeds(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        svc.create(
            fund_source="institute",
            tier=1,
            floor_amount=0,
            ceiling_amount=10_000,
            approving_authority_role_codes=["DIRECTOR"],
            actor_id=user.id,
        )
        rule2 = svc.create(
            fund_source="projects_ugc",
            tier=1,
            floor_amount=0,
            ceiling_amount=10_000,
            approving_authority_role_codes=["HOD", "DIRECTOR"],
            actor_id=user.id,
        )
        assert rule2.id is not None
