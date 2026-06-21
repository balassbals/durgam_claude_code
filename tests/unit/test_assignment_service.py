"""Unit tests for assignment services — FacultyMentor, ClassTeacher, ClassCoordinator."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.models.config_anchors import (
    ClassCoordinatorAssignment,
    ClassTeacherAssignment,
    FacultyMentorAssignment,
)
from durgam.services.assignment import (
    AssignmentError,
    ClassCoordinatorService,
    ClassTeacherService,
    FacultyMentorService,
    MAX_COORDINATORS_PER_CLASS,
)


# ── FacultyMentorService ─────────────────────────────────────────────────────

class TestFacultyMentorCreate:
    def _make_svc(self):
        repo = MagicMock()
        return FacultyMentorService(repo=repo), repo

    def test_create_success(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        fid = uuid4()
        result = svc.create(
            academic_year_id=uuid4(),
            campus_id=uuid4(),
            faculty_id=fid,
            student_id_placeholder="STU001",
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()
        assert result.faculty_id == fid  # 11A: FK, not placeholder string

    def test_create_blank_student_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(AssignmentError, match="Student identifier"):
            svc.create(
                academic_year_id=uuid4(),
                campus_id=uuid4(),
                faculty_id=uuid4(),
                student_id_placeholder="",
                actor_id=uuid4(),
            )

    def test_update_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(AssignmentError, match="not found"):
            svc.update(uuid4(), {}, uuid4())

    def test_soft_delete_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(AssignmentError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())


# ── ClassTeacherService ──────────────────────────────────────────────────────

class TestClassTeacherCreate:
    def _make_svc(self):
        repo = MagicMock()
        return ClassTeacherService(repo=repo), repo

    def test_create_success(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        fid = uuid4()
        result = svc.create(
            academic_year_id=uuid4(),
            department_id=uuid4(),
            faculty_id=fid,
            class_identifier="BSc-I-A",
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()
        assert result.class_identifier == "BSc-I-A"
        assert result.faculty_id == fid

    def test_create_blank_class_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(AssignmentError, match="Class identifier"):
            svc.create(
                academic_year_id=uuid4(),
                department_id=uuid4(),
                faculty_id=uuid4(),
                class_identifier="  ",
                actor_id=uuid4(),
            )


# ── ClassCoordinatorService ──────────────────────────────────────────────────

class TestClassCoordinatorCreate:
    def _make_svc(self):
        repo = MagicMock()
        return ClassCoordinatorService(repo=repo), repo

    def test_create_success_when_under_limit(self):
        svc, repo = self._make_svc()
        repo.count_by_ay_class.return_value = 0
        repo.save.side_effect = lambda r: r
        result = svc.create(
            academic_year_id=uuid4(),
            department_id=uuid4(),
            faculty_id=uuid4(),
            class_identifier="BSc-II-A",
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()
        assert result.class_identifier == "BSc-II-A"

    def test_create_succeeds_at_one(self):
        svc, repo = self._make_svc()
        repo.count_by_ay_class.return_value = 1
        repo.save.side_effect = lambda r: r
        svc.create(
            academic_year_id=uuid4(),
            department_id=uuid4(),
            faculty_id=uuid4(),
            class_identifier="BSc-II-A",
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()

    def test_create_raises_at_max_coordinators(self):
        svc, repo = self._make_svc()
        repo.count_by_ay_class.return_value = MAX_COORDINATORS_PER_CLASS
        with pytest.raises(AssignmentError, match="Maximum 2"):
            svc.create(
                academic_year_id=uuid4(),
                department_id=uuid4(),
                faculty_id=uuid4(),
                class_identifier="BSc-II-A",
                actor_id=uuid4(),
            )

    def test_create_raises_above_max_coordinators(self):
        svc, repo = self._make_svc()
        repo.count_by_ay_class.return_value = 5
        with pytest.raises(AssignmentError, match="Maximum 2"):
            svc.create(
                academic_year_id=uuid4(),
                department_id=uuid4(),
                faculty_id=uuid4(),
                class_identifier="BSc-II-A",
                actor_id=uuid4(),
            )

    def test_create_blank_class_raises(self):
        svc, repo = self._make_svc()
        repo.count_by_ay_class.return_value = 0
        with pytest.raises(AssignmentError, match="Class identifier"):
            svc.create(
                academic_year_id=uuid4(),
                department_id=uuid4(),
                faculty_id=uuid4(),
                class_identifier="",
                actor_id=uuid4(),
            )

    def test_update_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(AssignmentError, match="not found"):
            svc.update(uuid4(), {}, uuid4())

    def test_soft_delete_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(AssignmentError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())
