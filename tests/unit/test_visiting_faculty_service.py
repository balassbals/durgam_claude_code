"""Unit tests for VisitingFacultyService — CRUD + approval + validation."""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.visiting_faculty import VisitingFacultyError, VisitingFacultyService


class TestVisitingFacultyCreate:
    def _make_svc(self):
        repo = MagicMock()
        return VisitingFacultyService(repo=repo), repo

    def test_create_success(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            department_id=uuid4(),
            name="Dr. Alice",
            designation="Professor",
            organization="IISc Bangalore",
            expertise="Quantum Physics",
            available_from=date(2025, 7, 1),
            available_to=date(2025, 12, 31),
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()
        assert result.name == "Dr. Alice"
        assert result.is_admin_approved is False

    def test_create_blank_name_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(VisitingFacultyError, match="Name is required"):
            svc.create(
                department_id=uuid4(),
                name="  ",
                designation="Professor",
                organization="IISc",
                expertise="Physics",
                available_from=date(2025, 7, 1),
                available_to=date(2025, 12, 31),
                actor_id=uuid4(),
            )

    def test_create_blank_designation_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(VisitingFacultyError, match="Designation is required"):
            svc.create(
                department_id=uuid4(),
                name="Dr. Alice",
                designation="",
                organization="IISc",
                expertise="Physics",
                available_from=date(2025, 7, 1),
                available_to=date(2025, 12, 31),
                actor_id=uuid4(),
            )

    def test_create_blank_organization_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(VisitingFacultyError, match="Organization is required"):
            svc.create(
                department_id=uuid4(),
                name="Dr. Alice",
                designation="Professor",
                organization="  ",
                expertise="Physics",
                available_from=date(2025, 7, 1),
                available_to=date(2025, 12, 31),
                actor_id=uuid4(),
            )

    def test_create_blank_expertise_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(VisitingFacultyError, match="Expertise is required"):
            svc.create(
                department_id=uuid4(),
                name="Dr. Alice",
                designation="Professor",
                organization="IISc",
                expertise="",
                available_from=date(2025, 7, 1),
                available_to=date(2025, 12, 31),
                actor_id=uuid4(),
            )

    def test_create_end_before_start_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(VisitingFacultyError, match="Available-to date"):
            svc.create(
                department_id=uuid4(),
                name="Dr. Alice",
                designation="Professor",
                organization="IISc",
                expertise="Physics",
                available_from=date(2025, 12, 31),
                available_to=date(2025, 7, 1),
                actor_id=uuid4(),
            )


class TestVisitingFacultyUpdate:
    def _make_svc(self):
        repo = MagicMock()
        return VisitingFacultyService(repo=repo), repo

    def test_update_success(self):
        svc, repo = self._make_svc()
        existing = MagicMock()
        repo.get_by_id.return_value = existing
        repo.save.side_effect = lambda r: r
        result = svc.update(uuid4(), {"name": "Dr. Bob"}, uuid4())
        assert result.name == "Dr. Bob"
        repo.save.assert_called_once()

    def test_update_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(VisitingFacultyError, match="not found"):
            svc.update(uuid4(), {}, uuid4())


class TestVisitingFacultySoftDelete:
    def _make_svc(self):
        repo = MagicMock()
        return VisitingFacultyService(repo=repo), repo

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
        with pytest.raises(VisitingFacultyError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())


class TestVisitingFacultyApproval:
    def _make_svc(self):
        repo = MagicMock()
        return VisitingFacultyService(repo=repo), repo

    def test_set_approval_approve(self):
        svc, repo = self._make_svc()
        existing = MagicMock()
        existing.is_admin_approved = False
        repo.get_by_id.return_value = existing
        repo.save.side_effect = lambda r: r
        result = svc.set_approval(uuid4(), True, uuid4())
        assert result.is_admin_approved is True

    def test_set_approval_unapprove(self):
        svc, repo = self._make_svc()
        existing = MagicMock()
        existing.is_admin_approved = True
        repo.get_by_id.return_value = existing
        repo.save.side_effect = lambda r: r
        result = svc.set_approval(uuid4(), False, uuid4())
        assert result.is_admin_approved is False

    def test_set_approval_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(VisitingFacultyError, match="not found"):
            svc.set_approval(uuid4(), True, uuid4())
