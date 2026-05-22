"""Unit tests for CalendarEntryService."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.calendar_entry import (
    CalendarEntryError,
    CalendarEntryService,
    MASTER_TYPES,
    VALID_ENTRY_TYPES,
)


def _make_svc(entry_repo=None, ay_repo=None) -> CalendarEntryService:
    return CalendarEntryService(
        entry_repo=entry_repo or MagicMock(),
        ay_repo=ay_repo or MagicMock(),
    )


def _dt(year=2025, month=8, day=1, hour=9) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


class TestCreate:
    def test_empty_title_raises(self):
        svc = _make_svc()
        with pytest.raises(CalendarEntryError, match="Title is required"):
            svc.create(
                uuid4(), "  ", "master", _dt(), _dt(hour=10),
                uuid4(), "REGISTRAR", uuid4(),
            )

    def test_invalid_entry_type_raises(self):
        svc = _make_svc()
        with pytest.raises(CalendarEntryError, match="Invalid entry type"):
            svc.create(
                uuid4(), "Test", "bogus", _dt(), _dt(hour=10),
                uuid4(), "REGISTRAR", uuid4(),
            )

    def test_start_not_before_end_raises(self):
        svc = _make_svc()
        t = _dt()
        with pytest.raises(CalendarEntryError, match="Start must be before end"):
            svc.create(
                uuid4(), "Test", "master", t, t,
                uuid4(), "REGISTRAR", uuid4(),
            )

    def test_start_after_end_raises(self):
        svc = _make_svc()
        with pytest.raises(CalendarEntryError, match="Start must be before end"):
            svc.create(
                uuid4(), "Test", "master", _dt(hour=10), _dt(hour=9),
                uuid4(), "REGISTRAR", uuid4(),
            )

    def test_invalid_role_for_entry_type_raises(self):
        svc = _make_svc()
        with pytest.raises(CalendarEntryError, match="cannot create"):
            svc.create(
                uuid4(), "Test", "master", _dt(), _dt(hour=10),
                uuid4(), "HOD", uuid4(),
            )

    def test_invalid_role_for_activity_raises(self):
        svc = _make_svc()
        with pytest.raises(CalendarEntryError, match="cannot create"):
            svc.create(
                uuid4(), "Test", "activity", _dt(), _dt(hour=10),
                uuid4(), "REGISTRAR", uuid4(),
            )

    def test_invalid_role_for_sports_raises(self):
        svc = _make_svc()
        with pytest.raises(CalendarEntryError, match="cannot create"):
            svc.create(
                uuid4(), "Test", "sports", _dt(), _dt(hour=10),
                uuid4(), "IQAC_COORDINATOR", uuid4(),
            )

    def test_invalid_role_for_department_raises(self):
        svc = _make_svc()
        with pytest.raises(CalendarEntryError, match="cannot create"):
            svc.create(
                uuid4(), "Test", "department", _dt(), _dt(hour=10),
                uuid4(), "DIRECTOR", uuid4(),
            )

    def test_meeting_allows_any_role(self):
        ay = MagicMock()
        ay.master_calendar_locked = True
        ay_repo = MagicMock()
        ay_repo.get_by_id.return_value = ay

        entry_repo = MagicMock()
        entry_repo.save.side_effect = lambda e: e

        svc = _make_svc(entry_repo, ay_repo)
        result = svc.create(
            uuid4(), "Staff Sync", "meeting", _dt(), _dt(hour=10),
            uuid4(), "BASIC_USER", uuid4(),
        )
        assert result.entry_type == "meeting"

    def test_ay_not_found_raises(self):
        ay_repo = MagicMock()
        ay_repo.get_by_id.return_value = None
        svc = _make_svc(ay_repo=ay_repo)
        with pytest.raises(CalendarEntryError, match="Academic year not found"):
            svc.create(
                uuid4(), "Test", "master", _dt(), _dt(hour=10),
                uuid4(), "REGISTRAR", uuid4(),
            )

    def test_non_master_before_master_lock_raises(self):
        ay = MagicMock()
        ay.master_calendar_locked = False
        ay_repo = MagicMock()
        ay_repo.get_by_id.return_value = ay

        svc = _make_svc(ay_repo=ay_repo)
        with pytest.raises(CalendarEntryError, match="master calendar must be locked"):
            svc.create(
                uuid4(), "IQAC Orientation", "activity", _dt(), _dt(hour=10),
                uuid4(), "IQAC_COORDINATOR", uuid4(),
            )

    def test_master_type_allowed_before_master_lock(self):
        ay = MagicMock()
        ay.master_calendar_locked = False
        ay_repo = MagicMock()
        ay_repo.get_by_id.return_value = ay

        entry_repo = MagicMock()
        entry_repo.save.side_effect = lambda e: e

        svc = _make_svc(entry_repo, ay_repo)
        result = svc.create(
            uuid4(), "Semester 1 Begins", "sem_begin", _dt(), _dt(hour=10),
            uuid4(), "REGISTRAR", uuid4(),
        )
        assert result.entry_type == "sem_begin"

    def test_non_master_allowed_after_master_lock(self):
        ay = MagicMock()
        ay.master_calendar_locked = True
        ay_repo = MagicMock()
        ay_repo.get_by_id.return_value = ay

        entry_repo = MagicMock()
        entry_repo.save.side_effect = lambda e: e

        svc = _make_svc(entry_repo, ay_repo)
        result = svc.create(
            uuid4(), "Annual Sports Day", "sports", _dt(), _dt(hour=10),
            uuid4(), "DIRECTOR", uuid4(),
        )
        assert result.entry_type == "sports"

    def test_creates_with_scope(self):
        ay = MagicMock()
        ay.master_calendar_locked = True
        ay_repo = MagicMock()
        ay_repo.get_by_id.return_value = ay

        entry_repo = MagicMock()
        entry_repo.save.side_effect = lambda e: e

        svc = _make_svc(entry_repo, ay_repo)
        campus_id = uuid4()
        result = svc.create(
            uuid4(), "Campus Cultural Fest", "cultural", _dt(), _dt(hour=10),
            uuid4(), "DIRECTOR", uuid4(),
            scope_type="campus", scope_id=campus_id,
        )
        assert result.scope_type == "campus"
        assert result.scope_id == campus_id

    def test_all_master_types_allowed_with_registrar(self):
        ay = MagicMock()
        ay.master_calendar_locked = False
        ay_repo = MagicMock()
        ay_repo.get_by_id.return_value = ay

        entry_repo = MagicMock()
        entry_repo.save.side_effect = lambda e: e

        svc = _make_svc(entry_repo, ay_repo)
        for mt in MASTER_TYPES:
            result = svc.create(
                uuid4(), f"Test {mt}", mt, _dt(), _dt(hour=10),
                uuid4(), "REGISTRAR", uuid4(),
            )
            assert result.entry_type == mt


class TestUpdate:
    def test_not_found_raises(self):
        entry_repo = MagicMock()
        entry_repo.get_by_id.return_value = None
        svc = _make_svc(entry_repo)
        with pytest.raises(CalendarEntryError, match="not found"):
            svc.update(uuid4(), {"title": "New"}, uuid4(), uuid4())

    def test_non_owner_raises(self):
        entry = MagicMock()
        entry.owner_user_id = uuid4()
        entry_repo = MagicMock()
        entry_repo.get_by_id.return_value = entry

        svc = _make_svc(entry_repo)
        with pytest.raises(CalendarEntryError, match="Only the entry owner"):
            svc.update(uuid4(), {"title": "New"}, uuid4(), uuid4())

    def test_owner_updates_successfully(self):
        owner_id = uuid4()
        entry = MagicMock()
        entry.owner_user_id = owner_id
        entry_repo = MagicMock()
        entry_repo.get_by_id.return_value = entry
        entry_repo.save.return_value = entry

        svc = _make_svc(entry_repo)
        result = svc.update(uuid4(), {"title": "Updated"}, owner_id, uuid4())
        assert result is entry
        entry_repo.save.assert_called_once()


class TestSoftDelete:
    def test_not_found_raises(self):
        entry_repo = MagicMock()
        entry_repo.get_by_id.return_value = None
        svc = _make_svc(entry_repo)
        with pytest.raises(CalendarEntryError, match="not found"):
            svc.soft_delete(uuid4(), uuid4(), uuid4())

    def test_non_owner_raises(self):
        entry = MagicMock()
        entry.owner_user_id = uuid4()
        entry_repo = MagicMock()
        entry_repo.get_by_id.return_value = entry

        svc = _make_svc(entry_repo)
        with pytest.raises(CalendarEntryError, match="Only the entry owner"):
            svc.soft_delete(uuid4(), uuid4(), uuid4())

    def test_owner_deletes_successfully(self):
        owner_id = uuid4()
        entry = MagicMock()
        entry.owner_user_id = owner_id
        entry_repo = MagicMock()
        entry_repo.get_by_id.return_value = entry
        entry_repo.soft_delete.return_value = entry

        svc = _make_svc(entry_repo)
        result = svc.soft_delete(uuid4(), owner_id, uuid4())
        assert result is entry
        entry_repo.soft_delete.assert_called_once()


class TestListMethods:
    def test_list_by_ay(self):
        entries = [MagicMock(), MagicMock()]
        entry_repo = MagicMock()
        entry_repo.list_by_ay.return_value = entries
        svc = _make_svc(entry_repo)
        ay_id = uuid4()
        result = svc.list_by_ay(ay_id)
        assert result == entries
        entry_repo.list_by_ay.assert_called_once_with(ay_id)

    def test_list_by_ay_and_type(self):
        entries = [MagicMock()]
        entry_repo = MagicMock()
        entry_repo.list_by_ay_and_type.return_value = entries
        svc = _make_svc(entry_repo)
        ay_id = uuid4()
        result = svc.list_by_ay_and_type(ay_id, "sports")
        assert result == entries
        entry_repo.list_by_ay_and_type.assert_called_once_with(ay_id, "sports")

    def test_list_by_ay_and_owner(self):
        entries = [MagicMock()]
        entry_repo = MagicMock()
        entry_repo.list_by_ay_and_owner.return_value = entries
        svc = _make_svc(entry_repo)
        ay_id, user_id = uuid4(), uuid4()
        result = svc.list_by_ay_and_owner(ay_id, user_id)
        assert result == entries
        entry_repo.list_by_ay_and_owner.assert_called_once_with(ay_id, user_id)


class TestEntryTypeConstants:
    def test_all_master_types_in_valid_types(self):
        assert MASTER_TYPES <= VALID_ENTRY_TYPES

    def test_valid_types_count(self):
        assert len(VALID_ENTRY_TYPES) == 10
