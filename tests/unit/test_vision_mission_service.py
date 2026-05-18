"""Unit tests for VisionMissionService — update-only enforcement and add-mission logic."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.org_exceptions import NotDeletableError
from durgam.services.vision_mission import VisionMissionError, VisionMissionService


def _make_svc(vm_repo=None) -> VisionMissionService:
    return VisionMissionService(vm_repo=vm_repo or MagicMock())


class TestDeleteStubs:
    def test_delete_university_vm_always_raises(self):
        svc = _make_svc()
        with pytest.raises(NotDeletableError):
            svc.delete_university_vm()

    def test_delete_department_vm_always_raises(self):
        svc = _make_svc()
        with pytest.raises(NotDeletableError):
            svc.delete_department_vm()

    def test_not_deletable_message_is_clear(self):
        svc = _make_svc()
        with pytest.raises(NotDeletableError, match="cannot be deleted"):
            svc.delete_university_vm()


class TestUpdateUniversityVision:
    def test_empty_vision_raises(self):
        repo = MagicMock()
        repo.get_university_vm.return_value = MagicMock()
        svc = _make_svc(repo)
        with pytest.raises(VisionMissionError, match="required"):
            svc.update_university_vision("   ", uuid4())

    def test_creates_singleton_if_absent(self):
        repo = MagicMock()
        repo.get_university_vm.return_value = None
        fake_uvm = MagicMock()
        repo.create_university_vm.return_value = fake_uvm
        repo.save_university_vm.return_value = fake_uvm
        svc = _make_svc(repo)
        svc.update_university_vision("New vision", uuid4())
        repo.create_university_vm.assert_called_once()

    def test_updates_existing_singleton(self):
        repo = MagicMock()
        fake_uvm = MagicMock()
        fake_uvm.vision = "Old"
        repo.get_university_vm.return_value = fake_uvm
        repo.save_university_vm.return_value = fake_uvm
        svc = _make_svc(repo)
        svc.update_university_vision("New vision", uuid4())
        assert fake_uvm.vision == "New vision"
        repo.save_university_vm.assert_called_once()


class TestAddMission:
    def test_empty_statement_raises(self):
        repo = MagicMock()
        repo.get_university_vm.return_value = MagicMock()
        repo.list_university_missions.return_value = []
        svc = _make_svc(repo)
        with pytest.raises(VisionMissionError, match="required"):
            svc.add_university_mission("  ", uuid4())

    def test_display_order_increments_from_existing(self):
        repo = MagicMock()
        uvm = MagicMock()
        uvm.id = uuid4()
        repo.get_university_vm.return_value = uvm
        m1 = MagicMock()
        m1.display_order = 1
        m2 = MagicMock()
        m2.display_order = 3
        repo.list_university_missions.return_value = [m1, m2]
        repo.create_university_mission.return_value = MagicMock()
        svc = _make_svc(repo)
        svc.add_university_mission("New mission", uuid4())
        call_args = repo.create_university_mission.call_args[0]
        assert call_args[2] == 4  # next after max(1, 3) = 4

    def test_display_order_starts_at_1_when_no_existing(self):
        repo = MagicMock()
        uvm = MagicMock()
        uvm.id = uuid4()
        repo.get_university_vm.return_value = uvm
        repo.list_university_missions.return_value = []
        repo.create_university_mission.return_value = MagicMock()
        svc = _make_svc(repo)
        svc.add_university_mission("First mission", uuid4())
        call_args = repo.create_university_mission.call_args[0]
        assert call_args[2] == 1


class TestUpdateDepartmentVision:
    def test_creates_vm_if_absent(self):
        repo = MagicMock()
        repo.get_department_vm.return_value = None
        fake_dvm = MagicMock()
        repo.create_department_vm.return_value = fake_dvm
        repo.save_department_vm.return_value = fake_dvm
        svc = _make_svc(repo)
        svc.update_department_vision(uuid4(), "Dept vision", uuid4())
        repo.create_department_vm.assert_called_once()

    def test_empty_vision_raises(self):
        svc = _make_svc()
        with pytest.raises(VisionMissionError, match="required"):
            svc.update_department_vision(uuid4(), "", uuid4())
