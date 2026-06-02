"""Unit tests for NonOwnedCourseService — CRUD + validation."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.non_owned_course import NonOwnedCourseError, NonOwnedCourseService


class TestNonOwnedCourseCreate:
    def _make_svc(self):
        repo = MagicMock()
        return NonOwnedCourseService(repo=repo), repo

    def test_create_success(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            academic_year_id=uuid4(),
            course_code="MDC101",
            course_name="Moral and Divine Culture",
            credits=2,
            semester="odd",
            faculty_id_placeholder="faculty-001",
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()
        assert result.course_code == "MDC101"

    def test_create_blank_code_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(NonOwnedCourseError, match="Course code is required"):
            svc.create(
                academic_year_id=uuid4(),
                course_code="  ",
                course_name="Test",
                credits=2,
                semester="odd",
                faculty_id_placeholder="f1",
                actor_id=uuid4(),
            )

    def test_create_blank_name_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(NonOwnedCourseError, match="Course name is required"):
            svc.create(
                academic_year_id=uuid4(),
                course_code="MDC101",
                course_name="",
                credits=2,
                semester="odd",
                faculty_id_placeholder="f1",
                actor_id=uuid4(),
            )

    def test_create_blank_faculty_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(NonOwnedCourseError, match="Faculty identifier is required"):
            svc.create(
                academic_year_id=uuid4(),
                course_code="MDC101",
                course_name="Test",
                credits=2,
                semester="odd",
                faculty_id_placeholder="  ",
                actor_id=uuid4(),
            )

    def test_create_invalid_semester_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(NonOwnedCourseError, match="Semester must be"):
            svc.create(
                academic_year_id=uuid4(),
                course_code="MDC101",
                course_name="Test",
                credits=2,
                semester="summer",
                faculty_id_placeholder="f1",
                actor_id=uuid4(),
            )

    def test_create_with_notes(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            academic_year_id=uuid4(),
            course_code="AWR101",
            course_name="Awareness Course",
            credits=1,
            semester="even",
            faculty_id_placeholder="f1",
            actor_id=uuid4(),
            notes="Elective for all",
        )
        assert result.notes == "Elective for all"


class TestNonOwnedCourseUpdate:
    def _make_svc(self):
        repo = MagicMock()
        return NonOwnedCourseService(repo=repo), repo

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
        with pytest.raises(NonOwnedCourseError, match="not found"):
            svc.update(uuid4(), {}, uuid4())


class TestNonOwnedCourseSoftDelete:
    def _make_svc(self):
        repo = MagicMock()
        return NonOwnedCourseService(repo=repo), repo

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
        with pytest.raises(NonOwnedCourseError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())
