"""Unit tests for DepartmentService (non-trivial handlers only)."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.department import (
    CannotRemoveMainCampusError,
    DepartmentError,
    DepartmentService,
)
from durgam.services.org_exceptions import HardDeleteBlockedError


def _make_svc(dept_repo=None, subdept_repo=None) -> DepartmentService:
    return DepartmentService(
        dept_repo=dept_repo or MagicMock(),
        subdept_repo=subdept_repo or MagicMock(),
    )


class TestCreate:
    def test_empty_code_raises(self):
        svc = _make_svc()
        with pytest.raises(DepartmentError, match="code is required"):
            svc.create("", "Name", uuid4(), uuid4(), uuid4())

    def test_empty_name_raises(self):
        svc = _make_svc()
        with pytest.raises(DepartmentError, match="name is required"):
            svc.create("DMACS", "", uuid4(), uuid4(), uuid4())

    def test_duplicate_code_raises(self):
        repo = MagicMock()
        repo.get_by_code.return_value = MagicMock()
        svc = _make_svc(dept_repo=repo)
        with pytest.raises(DepartmentError, match="already in use"):
            svc.create("DMACS", "Maths", uuid4(), uuid4(), uuid4())

    def test_creates_successfully(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        fake = MagicMock()
        repo.save.return_value = fake
        svc = _make_svc(dept_repo=repo)
        result = svc.create("DMACS", "Maths", uuid4(), uuid4(), uuid4())
        assert result is fake


class TestHardDelete:
    def _fake_deleted_dept(self):
        dept = MagicMock()
        dept.is_deleted = True
        return dept

    def test_blocked_by_programs_or_courses(self):
        repo = MagicMock()
        repo._session.get.return_value = self._fake_deleted_dept()
        repo.count_programs.return_value = 2
        repo.count_courses.return_value = 5
        svc = _make_svc(dept_repo=repo)
        with pytest.raises(HardDeleteBlockedError, match="2 program"):
            svc.hard_delete(uuid4(), uuid4())

    def test_blocked_by_audit(self):
        repo = MagicMock()
        repo._session.get.return_value = self._fake_deleted_dept()
        repo.count_programs.return_value = 0
        repo.count_courses.return_value = 0
        repo._session.exec.return_value.one.return_value = 4
        svc = _make_svc(dept_repo=repo)
        with pytest.raises(HardDeleteBlockedError, match="4 audit"):
            svc.hard_delete(uuid4(), uuid4())

    def test_requires_soft_delete_first(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = False
        repo._session.get.return_value = fake
        svc = _make_svc(dept_repo=repo)
        with pytest.raises(DepartmentError, match="deactivated"):
            svc.hard_delete(uuid4(), uuid4())

    def test_succeeds_when_clean(self):
        repo = MagicMock()
        repo._session.get.return_value = self._fake_deleted_dept()
        repo.count_programs.return_value = 0
        repo.count_courses.return_value = 0
        repo._session.exec.return_value.one.return_value = 0
        svc = _make_svc(dept_repo=repo)
        svc.hard_delete(uuid4(), uuid4())
        repo.hard_delete.assert_called_once()


class TestUpdate:
    def test_update_nonexistent_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(dept_repo=repo)
        with pytest.raises(DepartmentError, match="not found"):
            svc.update(uuid4(), {"name": "New Name"}, uuid4())

    def test_update_changes_fields(self):
        repo = MagicMock()
        fake = MagicMock()
        repo.get_by_id.return_value = fake
        repo.save.return_value = fake
        actor_id = uuid4()
        svc = _make_svc(dept_repo=repo)
        result = svc.update(uuid4(), {"name": "Updated Name"}, actor_id)
        assert result is fake
        assert fake.name == "Updated Name"
        assert fake.updated_by == actor_id
        repo.save.assert_called_once_with(fake)


class TestAddCampus:
    def test_add_campus_nonexistent_dept_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(dept_repo=repo)
        with pytest.raises(DepartmentError, match="not found"):
            svc.add_campus(uuid4(), uuid4(), uuid4())

    def test_add_campus_calls_upsert(self):
        repo = MagicMock()
        repo.get_by_id.return_value = MagicMock()
        svc = _make_svc(dept_repo=repo)
        dept_id = uuid4()
        campus_id = uuid4()
        svc.add_campus(dept_id, campus_id, uuid4())
        repo.upsert_campus_link.assert_called_once_with(dept_id, campus_id, has_ahod=False)


class TestRemoveCampus:
    def _dept_with_main(self, main_campus_id):
        dept = MagicMock()
        dept.main_campus_id = main_campus_id
        return dept

    def test_remove_non_main_campus_calls_remove_link(self):
        main_id = uuid4()
        campus_id = uuid4()  # different from main
        repo = MagicMock()
        repo.get_by_id.return_value = self._dept_with_main(main_id)
        repo.list_campus_links.return_value = [MagicMock(), MagicMock()]
        svc = _make_svc(dept_repo=repo)
        dept_id = uuid4()
        svc.remove_campus(dept_id, campus_id, uuid4())
        repo.remove_campus_link.assert_called_once_with(dept_id, campus_id)

    def test_remove_main_campus_raises(self):
        """Bug B: removing the main campus raises CannotRemoveMainCampusError."""
        campus_id = uuid4()
        repo = MagicMock()
        repo.get_by_id.return_value = self._dept_with_main(campus_id)  # same ID = main
        repo.list_campus_links.return_value = [MagicMock(), MagicMock()]
        svc = _make_svc(dept_repo=repo)
        with pytest.raises(CannotRemoveMainCampusError, match="main campus"):
            svc.remove_campus(uuid4(), campus_id, uuid4())

    def test_remove_last_campus_raises(self):
        main_id = uuid4()
        campus_id = uuid4()  # different from main
        repo = MagicMock()
        repo.get_by_id.return_value = self._dept_with_main(main_id)
        repo.list_campus_links.return_value = [MagicMock()]
        svc = _make_svc(dept_repo=repo)
        with pytest.raises(DepartmentError, match="last campus"):
            svc.remove_campus(uuid4(), campus_id, uuid4())


class TestPromoteAndRemoveMainCampus:
    def _dept_with_main(self, main_campus_id):
        dept = MagicMock()
        dept.main_campus_id = main_campus_id
        return dept

    def _link_with_campus_id(self, campus_id):
        link = MagicMock()
        link.campus_id = campus_id
        return link

    def test_promote_succeeds(self):
        old_main_id = uuid4()
        new_main_id = uuid4()
        dept = self._dept_with_main(old_main_id)
        repo = MagicMock()
        repo.get_by_id.return_value = dept
        repo.list_campus_links.return_value = [
            self._link_with_campus_id(old_main_id),
            self._link_with_campus_id(new_main_id),
        ]
        repo.save.return_value = dept
        svc = _make_svc(dept_repo=repo)
        dept_id = uuid4()
        svc.promote_and_remove_main_campus(dept_id, new_main_id, old_main_id, uuid4())
        assert dept.main_campus_id == new_main_id
        repo.remove_campus_link.assert_called_once_with(dept_id, old_main_id)

    def test_promote_fails_if_wrong_old_main(self):
        old_main_id = uuid4()
        wrong_id = uuid4()
        dept = self._dept_with_main(old_main_id)
        repo = MagicMock()
        repo.get_by_id.return_value = dept
        svc = _make_svc(dept_repo=repo)
        with pytest.raises(DepartmentError, match="not the current main"):
            svc.promote_and_remove_main_campus(uuid4(), uuid4(), wrong_id, uuid4())

    def test_promote_fails_if_new_main_not_a_link(self):
        old_main_id = uuid4()
        new_main_id = uuid4()  # not in campus links
        dept = self._dept_with_main(old_main_id)
        repo = MagicMock()
        repo.get_by_id.return_value = dept
        repo.list_campus_links.return_value = [
            self._link_with_campus_id(old_main_id),
            self._link_with_campus_id(uuid4()),  # different campus
        ]
        svc = _make_svc(dept_repo=repo)
        with pytest.raises(DepartmentError, match="not linked"):
            svc.promote_and_remove_main_campus(uuid4(), new_main_id, old_main_id, uuid4())


class TestSoftDelete:
    def test_soft_delete_nonexistent_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(dept_repo=repo)
        with pytest.raises(DepartmentError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())


class TestSubDepartmentCreate:
    def test_empty_code_raises(self):
        svc = _make_svc()
        with pytest.raises(DepartmentError, match="code is required"):
            svc.create_sub_department("", "Name", uuid4(), uuid4())

    def test_duplicate_code_raises(self):
        subdept_repo = MagicMock()
        subdept_repo.get_by_code.return_value = MagicMock()
        svc = _make_svc(subdept_repo=subdept_repo)
        with pytest.raises(DepartmentError, match="already in use"):
            svc.create_sub_department("SDPHIL", "Philosophy", uuid4(), uuid4())
