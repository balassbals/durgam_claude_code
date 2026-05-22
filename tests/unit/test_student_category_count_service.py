"""Unit tests for StudentCategoryCountService."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.student_category_count import (
    StudentCategoryCountError,
    StudentCategoryCountService,
)


def _make_svc(scc_repo=None) -> StudentCategoryCountService:
    return StudentCategoryCountService(scc_repo=scc_repo or MagicMock())


class TestGetByAy:
    def test_delegates_to_repo(self):
        fake = MagicMock()
        repo = MagicMock()
        repo.get_by_ay.return_value = fake
        svc = _make_svc(repo)
        ay_id = uuid4()
        result = svc.get_by_ay(ay_id)
        assert result is fake
        repo.get_by_ay.assert_called_once_with(ay_id)

    def test_returns_none_when_missing(self):
        repo = MagicMock()
        repo.get_by_ay.return_value = None
        svc = _make_svc(repo)
        assert svc.get_by_ay(uuid4()) is None


class TestGetOrCreateByAy:
    def test_returns_existing(self):
        existing = MagicMock()
        repo = MagicMock()
        repo.get_by_ay.return_value = existing
        svc = _make_svc(repo)
        result = svc.get_or_create_by_ay(uuid4(), uuid4())
        assert result is existing
        repo.save.assert_not_called()

    def test_creates_when_missing(self):
        repo = MagicMock()
        repo.get_by_ay.return_value = None
        repo.save.side_effect = lambda s: s
        svc = _make_svc(repo)
        result = svc.get_or_create_by_ay(uuid4(), uuid4())
        assert result.sc_count == 0
        assert result.st_count == 0
        assert result.obc_count == 0
        assert result.ews_count == 0
        assert result.general_count == 0
        repo.save.assert_called_once()


class TestUpdate:
    def test_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(StudentCategoryCountError, match="not found"):
            svc.update(uuid4(), {"sc_count": 10}, uuid4())

    def test_negative_count_raises(self):
        repo = MagicMock()
        fake = MagicMock()
        repo.get_by_id.return_value = fake
        svc = _make_svc(repo)
        with pytest.raises(StudentCategoryCountError, match="non-negative"):
            svc.update(uuid4(), {"sc_count": -1}, uuid4())

    def test_non_integer_count_raises(self):
        repo = MagicMock()
        fake = MagicMock()
        repo.get_by_id.return_value = fake
        svc = _make_svc(repo)
        with pytest.raises(StudentCategoryCountError, match="non-negative"):
            svc.update(uuid4(), {"obc_count": "ten"}, uuid4())

    def test_updates_successfully(self):
        repo = MagicMock()
        fake = MagicMock()
        repo.get_by_id.return_value = fake
        repo.save.return_value = fake
        svc = _make_svc(repo)
        result = svc.update(uuid4(), {"sc_count": 50, "notes": "Updated"}, uuid4())
        assert result is fake
        repo.save.assert_called_once()

    def test_notes_field_not_validated_as_count(self):
        repo = MagicMock()
        fake = MagicMock()
        repo.get_by_id.return_value = fake
        repo.save.return_value = fake
        svc = _make_svc(repo)
        result = svc.update(uuid4(), {"notes": "Some notes"}, uuid4())
        assert result is fake

    def test_all_count_fields_validated(self):
        repo = MagicMock()
        fake = MagicMock()
        repo.get_by_id.return_value = fake
        svc = _make_svc(repo)
        for field in ("sc_count", "st_count", "obc_count", "ews_count", "general_count"):
            with pytest.raises(StudentCategoryCountError, match="non-negative"):
                svc.update(uuid4(), {field: -5}, uuid4())
