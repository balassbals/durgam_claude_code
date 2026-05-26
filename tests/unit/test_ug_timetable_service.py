"""Unit tests for UGTimetableService — CRUD + validation."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.ug_timetable import UGTimetableError, UGTimetableService


class TestUGTimetableCreate:
    def _make_svc(self):
        repo = MagicMock()
        return UGTimetableService(repo=repo), repo

    def test_create_success(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            academic_year_id=uuid4(),
            semester="odd",
            year_of_study=1,
            day_of_week=1,
            period_number=1,
            course_code="PHY101",
            course_name="General Physics",
            faculty_id_placeholder="faculty-001",
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()
        assert result.course_code == "PHY101"

    def test_create_blank_code_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(UGTimetableError, match="Course code is required"):
            svc.create(
                academic_year_id=uuid4(),
                semester="odd",
                year_of_study=1,
                day_of_week=1,
                period_number=1,
                course_code="  ",
                course_name="Test",
                faculty_id_placeholder="f1",
                actor_id=uuid4(),
            )

    def test_create_blank_name_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(UGTimetableError, match="Course name is required"):
            svc.create(
                academic_year_id=uuid4(),
                semester="odd",
                year_of_study=1,
                day_of_week=1,
                period_number=1,
                course_code="PHY101",
                course_name="",
                faculty_id_placeholder="f1",
                actor_id=uuid4(),
            )

    def test_create_blank_faculty_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(UGTimetableError, match="Faculty identifier is required"):
            svc.create(
                academic_year_id=uuid4(),
                semester="odd",
                year_of_study=1,
                day_of_week=1,
                period_number=1,
                course_code="PHY101",
                course_name="Test",
                faculty_id_placeholder="  ",
                actor_id=uuid4(),
            )

    def test_create_invalid_semester_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(UGTimetableError, match="Semester must be"):
            svc.create(
                academic_year_id=uuid4(),
                semester="summer",
                year_of_study=1,
                day_of_week=1,
                period_number=1,
                course_code="PHY101",
                course_name="Test",
                faculty_id_placeholder="f1",
                actor_id=uuid4(),
            )

    def test_create_invalid_year_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(UGTimetableError, match="Year of study must be 1 or 2"):
            svc.create(
                academic_year_id=uuid4(),
                semester="odd",
                year_of_study=3,
                day_of_week=1,
                period_number=1,
                course_code="PHY101",
                course_name="Test",
                faculty_id_placeholder="f1",
                actor_id=uuid4(),
            )

    def test_create_invalid_day_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(UGTimetableError, match="Day of week must be"):
            svc.create(
                academic_year_id=uuid4(),
                semester="odd",
                year_of_study=1,
                day_of_week=7,
                period_number=1,
                course_code="PHY101",
                course_name="Test",
                faculty_id_placeholder="f1",
                actor_id=uuid4(),
            )

    def test_create_invalid_period_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(UGTimetableError, match="Period number must be 1 or greater"):
            svc.create(
                academic_year_id=uuid4(),
                semester="odd",
                year_of_study=1,
                day_of_week=1,
                period_number=0,
                course_code="PHY101",
                course_name="Test",
                faculty_id_placeholder="f1",
                actor_id=uuid4(),
            )

    def test_create_with_room_and_notes(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            academic_year_id=uuid4(),
            semester="even",
            year_of_study=2,
            day_of_week=5,
            period_number=4,
            course_code="CHE201",
            course_name="Organic Chemistry",
            faculty_id_placeholder="f1",
            actor_id=uuid4(),
            room="LH-1",
            notes="Lab session follows",
        )
        assert result.room == "LH-1"
        assert result.notes == "Lab session follows"


class TestUGTimetableUpdate:
    def _make_svc(self):
        repo = MagicMock()
        return UGTimetableService(repo=repo), repo

    def test_update_success(self):
        svc, repo = self._make_svc()
        existing = MagicMock()
        repo.get_by_id.return_value = existing
        repo.save.side_effect = lambda r: r
        result = svc.update(uuid4(), {"course_name": "Updated"}, uuid4())
        assert result.course_name == "Updated"
        repo.save.assert_called_once()

    def test_update_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(UGTimetableError, match="not found"):
            svc.update(uuid4(), {}, uuid4())


class TestUGTimetableSoftDelete:
    def _make_svc(self):
        repo = MagicMock()
        return UGTimetableService(repo=repo), repo

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
        with pytest.raises(UGTimetableError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())
