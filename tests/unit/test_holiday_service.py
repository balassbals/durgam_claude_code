"""Unit tests for HolidayService."""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.holiday import HolidayError, HolidayService


def _make_svc(holiday_repo=None) -> HolidayService:
    return HolidayService(holiday_repo=holiday_repo or MagicMock())


class TestCreate:
    def test_empty_name_raises(self):
        svc = _make_svc()
        with pytest.raises(HolidayError, match="name is required"):
            svc.create(uuid4(), date(2025, 10, 2), "   ", uuid4())

    def test_duplicate_date_raises(self):
        repo = MagicMock()
        repo.get_by_date_and_ay.return_value = MagicMock()
        svc = _make_svc(repo)
        with pytest.raises(HolidayError, match="already exists on this date"):
            svc.create(uuid4(), date(2025, 10, 2), "Gandhi Jayanti", uuid4())

    def test_creates_successfully(self):
        repo = MagicMock()
        repo.get_by_date_and_ay.return_value = None
        repo.save.side_effect = lambda h: h
        svc = _make_svc(repo)
        result = svc.create(uuid4(), date(2025, 10, 2), "Gandhi Jayanti", uuid4())
        assert result.name == "Gandhi Jayanti"
        assert result.holiday_date == date(2025, 10, 2)
        repo.save.assert_called_once()

    def test_strips_name_whitespace(self):
        repo = MagicMock()
        repo.get_by_date_and_ay.return_value = None
        repo.save.side_effect = lambda h: h
        svc = _make_svc(repo)
        result = svc.create(uuid4(), date(2025, 10, 2), "  Gandhi Jayanti  ", uuid4())
        assert result.name == "Gandhi Jayanti"


class TestUpdate:
    def test_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(HolidayError, match="not found"):
            svc.update(uuid4(), {"name": "New Name"}, uuid4())

    def test_updates_successfully(self):
        repo = MagicMock()
        fake = MagicMock()
        repo.get_by_id.return_value = fake
        repo.save.return_value = fake
        svc = _make_svc(repo)
        result = svc.update(uuid4(), {"name": "Updated"}, uuid4())
        assert result is fake
        repo.save.assert_called_once()


class TestSoftDelete:
    def test_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(HolidayError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())

    def test_deletes_successfully(self):
        repo = MagicMock()
        fake = MagicMock()
        repo.get_by_id.return_value = fake
        repo.soft_delete.return_value = fake
        svc = _make_svc(repo)
        result = svc.soft_delete(uuid4(), uuid4())
        assert result is fake
        repo.soft_delete.assert_called_once()


class TestListByAy:
    def test_delegates_to_repo(self):
        holidays = [MagicMock(), MagicMock()]
        repo = MagicMock()
        repo.list_by_ay.return_value = holidays
        svc = _make_svc(repo)
        ay_id = uuid4()
        result = svc.list_by_ay(ay_id)
        assert result == holidays
        repo.list_by_ay.assert_called_once_with(ay_id)
