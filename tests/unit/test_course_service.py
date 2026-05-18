"""Unit tests for CourseService."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.course import CourseError, CourseService
from durgam.services.org_exceptions import HardDeleteBlockedError


def _make_svc(course_repo=None) -> CourseService:
    return CourseService(course_repo=course_repo or MagicMock())


class TestCreate:
    def test_empty_code_raises(self):
        with pytest.raises(CourseError, match="code is required"):
            _make_svc().create("", "Name", uuid4(), uuid4(), 4, 3, 1, 0, "E", uuid4())

    def test_empty_name_raises(self):
        with pytest.raises(CourseError, match="name is required"):
            _make_svc().create("MAT101", "", uuid4(), uuid4(), 4, 3, 1, 0, "E", uuid4())

    def test_invalid_evaluation_raises(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        with pytest.raises(CourseError, match="Evaluation must be one of"):
            _make_svc(repo).create("MAT101", "Calc", uuid4(), uuid4(), 4, 3, 1, 0, "X", uuid4())

    def test_negative_credits_raises(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        with pytest.raises(CourseError, match="Credits cannot be negative"):
            _make_svc(repo).create("MAT101", "Calc", uuid4(), uuid4(), -1, 3, 1, 0, "E", uuid4())

    def test_duplicate_code_raises(self):
        repo = MagicMock()
        repo.get_by_code.return_value = MagicMock()
        with pytest.raises(CourseError, match="already in use"):
            _make_svc(repo).create("MAT101", "Calc", uuid4(), uuid4(), 4, 3, 1, 0, "E", uuid4())

    def test_creates_successfully(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        fake = MagicMock()
        repo.save.return_value = fake
        result = _make_svc(repo).create(
            "MAT101", "Calculus", uuid4(), uuid4(), 4, 3, 1, 0, "E", uuid4()
        )
        assert result is fake


class TestUpdate:
    def test_invalid_evaluation_in_update_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = MagicMock()
        with pytest.raises(CourseError, match="Evaluation must be one of"):
            _make_svc(repo).update(uuid4(), {"evaluation": "BAD"}, uuid4())

    def test_update_nonexistent_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        with pytest.raises(CourseError, match="not found"):
            _make_svc(repo).update(uuid4(), {"name": "New Name"}, uuid4())

    def test_update_changes_fields(self):
        repo = MagicMock()
        fake = MagicMock()
        repo.get_by_id.return_value = fake
        repo.save.return_value = fake
        actor_id = uuid4()
        result = _make_svc(repo).update(uuid4(), {"name": "Advanced Calculus"}, actor_id)
        assert result is fake
        assert fake.name == "Advanced Calculus"
        assert fake.updated_by == actor_id
        repo.save.assert_called_once_with(fake)


class TestHardDelete:
    def test_blocked_by_scheme_usages(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = True
        repo._session.get.return_value = fake
        repo.count_scheme_usages.return_value = 2
        with pytest.raises(HardDeleteBlockedError, match="2 scheme"):
            _make_svc(repo).hard_delete(uuid4(), uuid4())

    def test_blocked_by_audit(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = True
        repo._session.get.return_value = fake
        repo.count_scheme_usages.return_value = 0
        repo._session.exec.return_value.one.return_value = 1
        with pytest.raises(HardDeleteBlockedError, match="1 audit"):
            _make_svc(repo).hard_delete(uuid4(), uuid4())

    def test_requires_soft_delete_first(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = False
        repo._session.get.return_value = fake
        with pytest.raises(CourseError, match="deactivated"):
            _make_svc(repo).hard_delete(uuid4(), uuid4())


class TestSoftDelete:
    def test_soft_delete_nonexistent_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        with pytest.raises(CourseError, match="not found"):
            _make_svc(repo).soft_delete(uuid4(), uuid4())
