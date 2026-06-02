"""Integration tests for Designation — CRUD + unique constraint.

Key tests:
- Designation CRUD with real database
- Unique constraint: duplicate code raises IntegrityError
- list_all_active returns ordered by rank
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from durgam.models.config_anchors import Designation
from durgam.models.identity import User
from durgam.repositories.designation import DesignationRepository
from durgam.services.designation import DesignationError, DesignationService


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


def _svc(session) -> DesignationService:
    return DesignationService(repo=DesignationRepository(session))


class TestDesignationCRUD:
    def test_create_and_list(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            code="test_professor",
            name="Test Professor",
            rank=10,
            actor_id=user.id,
        )
        assert created.id is not None
        assert created.code == "test_professor"
        assert created.rank == 10

        results = svc.list_all()
        assert any(r.id == created.id for r in results)

    def test_update(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            code="test_assoc_prof",
            name="Test Associate Professor",
            rank=11,
            actor_id=user.id,
        )
        updated = svc.update(created.id, {"name": "Updated Name"}, user.id)
        assert updated.name == "Updated Name"

    def test_soft_delete_excludes_from_list(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            code="test_del_desig",
            name="To Delete",
            rank=99,
            actor_id=user.id,
        )
        svc.soft_delete(created.id, user.id)
        results = svc.list_all()
        assert not any(r.id == created.id for r in results)

    def test_list_ordered_by_rank(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        svc.create(code="rank_high", name="High Rank", rank=50, actor_id=user.id)
        svc.create(code="rank_low", name="Low Rank", rank=5, actor_id=user.id)

        results = svc.list_all()
        test_results = [r for r in results if r.code in ("rank_high", "rank_low")]
        assert len(test_results) == 2
        assert test_results[0].rank <= test_results[1].rank


class TestDesignationUniqueConstraint:
    def test_duplicate_code_raises(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)

        svc.create(code="dup_test", name="First", rank=1, actor_id=user.id)
        with pytest.raises(IntegrityError):
            svc.create(code="dup_test", name="Second", rank=2, actor_id=user.id)
