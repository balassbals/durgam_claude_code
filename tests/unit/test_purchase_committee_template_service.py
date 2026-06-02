"""Unit tests for PurchaseCommitteeTemplateService — CRUD + validation."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.purchase_committee_template import (
    PurchaseCommitteeTemplateError,
    PurchaseCommitteeTemplateService,
)


class TestPurchaseCommitteeTemplateCreate:
    def _make_svc(self):
        repo = MagicMock()
        return PurchaseCommitteeTemplateService(repo=repo), repo

    def test_create_success(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            committee_type="campus_purchase_committee",
            eligible_designations=["senior_professor", "professor"],
            faculty_member_count=3,
            members_from_different_departments=True,
            fixed_role_members=["HOD"],
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()
        assert result.committee_type == "campus_purchase_committee"

    def test_invalid_type_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(PurchaseCommitteeTemplateError, match="Committee type"):
            svc.create(
                committee_type="invalid",
                eligible_designations=["senior_professor"],
                faculty_member_count=3,
                members_from_different_departments=True,
                fixed_role_members=["HOD"],
                actor_id=uuid4(),
            )

    def test_empty_designations_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(PurchaseCommitteeTemplateError, match="eligible designation"):
            svc.create(
                committee_type="campus_purchase_committee",
                eligible_designations=[],
                faculty_member_count=3,
                members_from_different_departments=True,
                fixed_role_members=["HOD"],
                actor_id=uuid4(),
            )

    def test_zero_faculty_count_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(PurchaseCommitteeTemplateError, match="Faculty member count"):
            svc.create(
                committee_type="campus_purchase_committee",
                eligible_designations=["senior_professor"],
                faculty_member_count=0,
                members_from_different_departments=True,
                fixed_role_members=["HOD"],
                actor_id=uuid4(),
            )

    def test_invalid_topology_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(PurchaseCommitteeTemplateError, match="Topology"):
            svc.create(
                committee_type="campus_purchase_committee",
                eligible_designations=["senior_professor"],
                faculty_member_count=3,
                members_from_different_departments=True,
                fixed_role_members=["HOD"],
                topology="invalid",
                actor_id=uuid4(),
            )

    def test_invalid_expert_mode_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(PurchaseCommitteeTemplateError, match="External expert mode"):
            svc.create(
                committee_type="campus_purchase_committee",
                eligible_designations=["senior_professor"],
                faculty_member_count=3,
                members_from_different_departments=True,
                fixed_role_members=["HOD"],
                external_expert_mode="invalid",
                actor_id=uuid4(),
            )


class TestPurchaseCommitteeTemplateUpdate:
    def _make_svc(self):
        repo = MagicMock()
        return PurchaseCommitteeTemplateService(repo=repo), repo

    def test_update_success(self):
        svc, repo = self._make_svc()
        existing = MagicMock()
        repo.get_by_id.return_value = existing
        repo.save.side_effect = lambda r: r
        result = svc.update(uuid4(), {"notes": "Updated"}, uuid4())
        assert result.notes == "Updated"
        repo.save.assert_called_once()

    def test_update_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(PurchaseCommitteeTemplateError, match="not found"):
            svc.update(uuid4(), {}, uuid4())


class TestPurchaseCommitteeTemplateSoftDelete:
    def _make_svc(self):
        repo = MagicMock()
        return PurchaseCommitteeTemplateService(repo=repo), repo

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
        with pytest.raises(PurchaseCommitteeTemplateError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())
