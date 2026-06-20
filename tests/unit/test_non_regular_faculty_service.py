"""Unit tests for NonRegularFacultyService — CRUD + approval + validation."""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.non_regular_faculty import NonRegularFacultyError, NonRegularFacultyService


class TestNonRegularFacultyCreate:
    def _make_svc(self):
        repo = MagicMock()
        return NonRegularFacultyService(repo=repo), repo

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
        assert result.non_regular_type == "visiting"

    def test_create_with_type(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            department_id=uuid4(),
            name="Dr. Bob",
            designation="Professor",
            organization="MIT",
            expertise="AI",
            available_from=date(2025, 7, 1),
            available_to=date(2025, 12, 31),
            actor_id=uuid4(),
            non_regular_type="adjunct",
        )
        assert result.non_regular_type == "adjunct"

    def test_create_invalid_type_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(NonRegularFacultyError, match="Invalid type"):
            svc.create(
                department_id=uuid4(),
                name="Dr. Alice",
                designation="Professor",
                organization="IISc",
                expertise="Physics",
                available_from=date(2025, 7, 1),
                available_to=date(2025, 12, 31),
                actor_id=uuid4(),
                non_regular_type="invalid_type",
            )

    def test_create_blank_name_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(NonRegularFacultyError, match="Name is required"):
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
        with pytest.raises(NonRegularFacultyError, match="Designation is required"):
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
        with pytest.raises(NonRegularFacultyError, match="Organization is required"):
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
        with pytest.raises(NonRegularFacultyError, match="Expertise is required"):
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
        with pytest.raises(NonRegularFacultyError, match="Available-to date"):
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


class TestNonRegularFacultyUpdate:
    def _make_svc(self):
        repo = MagicMock()
        return NonRegularFacultyService(repo=repo), repo

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
        with pytest.raises(NonRegularFacultyError, match="not found"):
            svc.update(uuid4(), {}, uuid4())


class TestNonRegularFacultySoftDelete:
    def _make_svc(self):
        repo = MagicMock()
        return NonRegularFacultyService(repo=repo), repo

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
        with pytest.raises(NonRegularFacultyError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())


class TestNonRegularFacultyApproval:
    def _make_svc(self):
        repo = MagicMock()
        return NonRegularFacultyService(repo=repo), repo

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
        with pytest.raises(NonRegularFacultyError, match="not found"):
            svc.set_approval(uuid4(), True, uuid4())


# ── Phase 9A: contract-term expansion (renewal) ───────────────────────────────


class TestNonRegularFacultyRenewal:
    def _make_svc(self):
        repo = MagicMock()
        return NonRegularFacultyService(repo=repo), repo

    def test_create_accepts_renewal_count_and_contract_file(self):
        from uuid import uuid4 as _u
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        fid = _u()
        result = svc.create(
            department_id=_u(), name="Dr. C", designation="Prof",
            organization="Org", expertise="X",
            available_from=date(2025, 1, 1), available_to=date(2025, 12, 31),
            actor_id=_u(), renewal_count=2, latest_contract_file_id=fid,
        )
        assert result.renewal_count == 2
        assert result.latest_contract_file_id == fid

    def test_create_negative_renewal_count_raises(self):
        from uuid import uuid4 as _u
        svc, repo = self._make_svc()
        with pytest.raises(NonRegularFacultyError, match="negative"):
            svc.create(
                department_id=_u(), name="Dr. C", designation="Prof",
                organization="Org", expertise="X",
                available_from=date(2025, 1, 1), available_to=date(2025, 12, 31),
                actor_id=_u(), renewal_count=-1,
            )

    def test_renew_increments_count_and_extends_term(self):
        from uuid import uuid4 as _u
        svc, repo = self._make_svc()
        existing = MagicMock()
        existing.id = _u()
        existing.available_to = date(2025, 12, 31)
        existing.renewal_count = 1
        existing.latest_contract_file_id = None
        repo.get_by_id.return_value = existing
        repo.save.side_effect = lambda r: r

        result = svc.renew(
            existing.id, new_end_date=date(2026, 12, 31), actor_id=_u(),
        )
        assert result.available_to == date(2026, 12, 31)
        assert result.renewal_count == 2

    def test_renew_with_contract_file(self):
        from uuid import uuid4 as _u
        svc, repo = self._make_svc()
        existing = MagicMock()
        existing.available_to = date(2025, 12, 31)
        existing.renewal_count = 0
        existing.latest_contract_file_id = None
        repo.get_by_id.return_value = existing
        repo.save.side_effect = lambda r: r
        fid = _u()
        result = svc.renew(
            _u(), new_end_date=date(2026, 6, 30), actor_id=_u(),
            latest_contract_file_id=fid,
        )
        assert result.latest_contract_file_id == fid

    def test_renew_not_after_current_raises(self):
        from uuid import uuid4 as _u
        from durgam.services.non_regular_faculty import RenewalDateInvalidError
        svc, repo = self._make_svc()
        existing = MagicMock()
        existing.available_to = date(2025, 12, 31)
        existing.renewal_count = 0
        repo.get_by_id.return_value = existing
        with pytest.raises(RenewalDateInvalidError, match="after the current end date"):
            svc.renew(_u(), new_end_date=date(2025, 6, 30), actor_id=_u())

    def test_renew_not_found_raises(self):
        from uuid import uuid4 as _u
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(NonRegularFacultyError, match="not found"):
            svc.renew(_u(), new_end_date=date(2030, 1, 1), actor_id=_u())
