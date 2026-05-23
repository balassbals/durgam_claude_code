"""Unit tests for the AY rollover lock task."""

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

from durgam.tasks.ay_rollover import lock_expired_academic_years


def _make_ay(code: str, ends_on: date, *, is_locked: bool = False) -> MagicMock:
    ay = MagicMock()
    ay.code = code
    ay.ends_on = ends_on
    ay.is_locked = is_locked
    ay.is_deleted = False
    ay.id = uuid4()
    return ay


class TestLockExpiredAcademicYears:
    @patch("durgam.tasks.ay_rollover.open_session")
    def test_locks_expired_unlocked_ay(self, mock_open):
        ay = _make_ay("2023-24", date(2024, 4, 30))
        session = MagicMock()
        session.exec.return_value.all.return_value = [ay]
        mock_open.return_value.__enter__ = MagicMock(return_value=session)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        result = lock_expired_academic_years()

        assert ay.is_locked is True
        session.add.assert_called_once_with(ay)
        session.commit.assert_called_once()
        assert result["locked"] == ["2023-24"]

    @patch("durgam.tasks.ay_rollover.open_session")
    def test_skips_already_locked_ay(self, mock_open):
        session = MagicMock()
        session.exec.return_value.all.return_value = []
        mock_open.return_value.__enter__ = MagicMock(return_value=session)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        result = lock_expired_academic_years()

        session.commit.assert_not_called()
        assert result["locked"] == []

    @patch("durgam.tasks.ay_rollover.open_session")
    def test_skips_non_expired_ay(self, mock_open):
        session = MagicMock()
        session.exec.return_value.all.return_value = []
        mock_open.return_value.__enter__ = MagicMock(return_value=session)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        result = lock_expired_academic_years()

        session.commit.assert_not_called()
        assert result["locked"] == []

    @patch("durgam.tasks.ay_rollover.open_session")
    def test_locks_multiple_expired_ays(self, mock_open):
        ay1 = _make_ay("2022-23", date(2023, 4, 30))
        ay2 = _make_ay("2023-24", date(2024, 4, 30))
        session = MagicMock()
        session.exec.return_value.all.return_value = [ay1, ay2]
        mock_open.return_value.__enter__ = MagicMock(return_value=session)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        result = lock_expired_academic_years()

        assert ay1.is_locked is True
        assert ay2.is_locked is True
        assert session.add.call_count == 2
        session.commit.assert_called_once()
        assert result["locked"] == ["2022-23", "2023-24"]

    @patch("durgam.tasks.ay_rollover.open_session")
    def test_seeded_ays_not_over_locked(self, mock_open):
        """The seeded 2024-25 (already locked) and 2025-26 (not expired)
        should both be absent from the query results — neither gets locked."""
        session = MagicMock()
        session.exec.return_value.all.return_value = []
        mock_open.return_value.__enter__ = MagicMock(return_value=session)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        result = lock_expired_academic_years()

        session.commit.assert_not_called()
        assert result["locked"] == []

    @patch("durgam.tasks.ay_rollover.open_session")
    def test_returns_date_in_result(self, mock_open):
        session = MagicMock()
        session.exec.return_value.all.return_value = []
        mock_open.return_value.__enter__ = MagicMock(return_value=session)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        result = lock_expired_academic_years()

        assert result["date"] == str(date.today())
