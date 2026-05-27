"""Integration tests for PurchaseCommitteeTemplate — CRUD + unique constraint.

Key tests:
- PurchaseCommitteeTemplate CRUD with real database
- Unique constraint: duplicate committee_type raises IntegrityError
- Soft-delete exclusion from list
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from durgam.models.config_anchors import PurchaseCommitteeTemplate
from durgam.models.identity import User
from durgam.repositories.purchase_committee_template import (
    PurchaseCommitteeTemplateRepository,
)
from durgam.services.purchase_committee_template import (
    PurchaseCommitteeTemplateError,
    PurchaseCommitteeTemplateService,
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


def _svc(session) -> PurchaseCommitteeTemplateService:
    return PurchaseCommitteeTemplateService(
        repo=PurchaseCommitteeTemplateRepository(session),
    )


class TestPurchaseCommitteeTemplateCRUD:
    def test_create_and_list(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            committee_type="campus_purchase_committee",
            eligible_designations=["senior_professor", "professor"],
            faculty_member_count=3,
            members_from_different_departments=True,
            fixed_role_members=["HOD"],
            director_excluded=True,
            actor_id=user.id,
        )
        assert created.id is not None
        assert created.committee_type == "campus_purchase_committee"
        assert created.eligible_designations == ["senior_professor", "professor"]
        assert created.faculty_member_count == 3
        assert created.director_excluded is True

        results = svc.list_all()
        assert any(r.id == created.id for r in results)

    def test_update(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            committee_type="central_purchase_committee",
            eligible_designations=["senior_professor", "professor", "associate_professor"],
            faculty_member_count=3,
            members_from_different_departments=True,
            fixed_role_members=["HOD", "FINANCE_OFFICER", "REGISTRAR"],
            escalation_designate_role_code="REGISTRAR",
            actor_id=user.id,
        )
        updated = svc.update(created.id, {"notes": "Updated notes"}, user.id)
        assert updated.notes == "Updated notes"

    def test_soft_delete_excludes_from_list(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            committee_type="campus_purchase_committee",
            eligible_designations=["senior_professor"],
            faculty_member_count=2,
            members_from_different_departments=True,
            fixed_role_members=["HOD"],
            actor_id=user.id,
        )
        svc.soft_delete(created.id, user.id)
        results = svc.list_all()
        assert not any(r.id == created.id for r in results)


class TestPurchaseCommitteeTemplateUniqueConstraint:
    def test_duplicate_committee_type_raises(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        svc.create(
            committee_type="campus_purchase_committee",
            eligible_designations=["senior_professor"],
            faculty_member_count=3,
            members_from_different_departments=True,
            fixed_role_members=["HOD"],
            actor_id=user.id,
        )
        with pytest.raises(IntegrityError):
            svc.create(
                committee_type="campus_purchase_committee",
                eligible_designations=["professor"],
                faculty_member_count=2,
                members_from_different_departments=False,
                fixed_role_members=["HOD"],
                actor_id=user.id,
            )
