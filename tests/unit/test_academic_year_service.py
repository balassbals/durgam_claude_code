"""Unit tests for AcademicYearService."""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.academic_year import AcademicYearError, AcademicYearService
from durgam.services.org_exceptions import AcademicYearLockedError


def _make_svc(ay_repo=None) -> AcademicYearService:
    return AcademicYearService(ay_repo=ay_repo or MagicMock())


class TestCreate:
    def test_invalid_code_format_raises(self):
        svc = _make_svc()
        with pytest.raises(AcademicYearError, match="YYYY-YY"):
            svc.create("2025", date(2025, 7, 1), date(2026, 4, 30), uuid4())

    def test_empty_code_raises(self):
        svc = _make_svc()
        with pytest.raises(AcademicYearError, match="YYYY-YY"):
            svc.create("", date(2025, 7, 1), date(2026, 4, 30), uuid4())

    def test_start_not_before_end_raises(self):
        svc = _make_svc()
        with pytest.raises(AcademicYearError, match="before end"):
            svc.create("2025-26", date(2026, 7, 1), date(2025, 4, 30), uuid4())

    def test_same_start_end_raises(self):
        svc = _make_svc()
        with pytest.raises(AcademicYearError, match="before end"):
            svc.create("2025-26", date(2025, 7, 1), date(2025, 7, 1), uuid4())

    def test_duplicate_code_raises(self):
        repo = MagicMock()
        repo.get_by_code.return_value = MagicMock()
        svc = _make_svc(repo)
        with pytest.raises(AcademicYearError, match="already exists"):
            svc.create("2025-26", date(2025, 7, 1), date(2026, 4, 30), uuid4())

    def test_creates_successfully(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        fake = MagicMock()
        repo.save.return_value = fake
        svc = _make_svc(repo)
        result = svc.create("2025-26", date(2025, 7, 1), date(2026, 4, 30), uuid4())
        assert result is fake
        repo.save.assert_called_once()


class TestUpdate:
    def test_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(AcademicYearError, match="not found"):
            svc.update(uuid4(), {"code": "2025-26"}, uuid4())

    def test_locked_ay_raises(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_locked = True
        repo.get_by_id.return_value = fake
        svc = _make_svc(repo)
        with pytest.raises(AcademicYearLockedError):
            svc.update(uuid4(), {"code": "2025-26"}, uuid4())

    def test_updates_unlocked_ay(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_locked = False
        repo.get_by_id.return_value = fake
        repo.save.return_value = fake
        svc = _make_svc(repo)
        result = svc.update(uuid4(), {"code": "2025-26"}, uuid4())
        assert result is fake


class TestLockMasterCalendar:
    def test_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(AcademicYearError, match="not found"):
            svc.lock_master_calendar(uuid4(), uuid4())

    def test_locked_ay_raises(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_locked = True
        repo.get_by_id.return_value = fake
        svc = _make_svc(repo)
        with pytest.raises(AcademicYearLockedError):
            svc.lock_master_calendar(uuid4(), uuid4())

    def test_locks_master_calendar(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_locked = False
        repo.get_by_id.return_value = fake
        locked = MagicMock()
        locked.master_calendar_locked = True
        repo.lock_master_calendar.return_value = locked
        svc = _make_svc(repo)
        result = svc.lock_master_calendar(uuid4(), uuid4())
        assert result.master_calendar_locked is True


class TestLockExpired:
    def test_locks_expired_unlocked_ays(self):
        repo = MagicMock()
        ay1 = MagicMock()
        ay1.id = uuid4()
        ay1.code = "2023-24"
        ay2 = MagicMock()
        ay2.id = uuid4()
        ay2.code = "2022-23"
        repo.list_expired_unlocked.return_value = [ay1, ay2]
        svc = _make_svc(repo)
        count = svc.lock_expired_academic_years()
        assert count == 2
        assert repo.lock_for_rollover.call_count == 2

    def test_no_expired_returns_zero(self):
        repo = MagicMock()
        repo.list_expired_unlocked.return_value = []
        svc = _make_svc(repo)
        assert svc.lock_expired_academic_years() == 0
