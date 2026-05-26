"""Unit tests for MentalHealthCounsellorService."""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.models.config_anchors import MentalHealthCounsellor
from durgam.services.mental_health_counsellor import (
    CounsellorError,
    MentalHealthCounsellorService,
)


def _make_svc():
    repo = MagicMock()
    svc = MentalHealthCounsellorService(repo=repo)
    return svc, repo


class TestCounsellorCreate:
    def test_create_success(self):
        svc, repo = _make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            academic_year_id=uuid4(),
            campus_id=uuid4(),
            name="Dr. Test",
            qualification="PhD Psychology",
            specialisation="Clinical",
            mode_of_appointment="inhouse",
            appointment_start=date(2025, 7, 1),
            appointment_end=date(2026, 4, 30),
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()
        assert result.name == "Dr. Test"

    def test_create_blank_name_raises(self):
        svc, repo = _make_svc()
        with pytest.raises(CounsellorError, match="name is required"):
            svc.create(
                academic_year_id=uuid4(),
                campus_id=uuid4(),
                name="   ",
                qualification="PhD",
                specialisation="Clinical",
                mode_of_appointment="inhouse",
                appointment_start=date(2025, 7, 1),
                appointment_end=date(2026, 4, 30),
                actor_id=uuid4(),
            )

    def test_create_end_before_start_raises(self):
        svc, repo = _make_svc()
        with pytest.raises(CounsellorError, match="end date must be on or after"):
            svc.create(
                academic_year_id=uuid4(),
                campus_id=uuid4(),
                name="Dr. Test",
                qualification="PhD",
                specialisation="Clinical",
                mode_of_appointment="inhouse",
                appointment_start=date(2026, 4, 30),
                appointment_end=date(2025, 7, 1),
                actor_id=uuid4(),
            )

    def test_create_invalid_mode_raises(self):
        svc, repo = _make_svc()
        with pytest.raises(CounsellorError, match="Mode of appointment"):
            svc.create(
                academic_year_id=uuid4(),
                campus_id=uuid4(),
                name="Dr. Test",
                qualification="PhD",
                specialisation="Clinical",
                mode_of_appointment="contract",
                appointment_start=date(2025, 7, 1),
                appointment_end=date(2026, 4, 30),
                actor_id=uuid4(),
            )

    def test_create_with_optional_fields(self):
        svc, repo = _make_svc()
        repo.save.side_effect = lambda r: r
        file_id = uuid4()
        result = svc.create(
            academic_year_id=uuid4(),
            campus_id=uuid4(),
            name="Dr. Test",
            qualification="PhD",
            specialisation="Clinical",
            mode_of_appointment="external",
            appointment_start=date(2025, 7, 1),
            appointment_end=date(2026, 4, 30),
            actor_id=uuid4(),
            phone="+91-9876543210",
            email="test@example.dev",
            appointment_letter_file_id=file_id,
            display_order=3,
        )
        assert result.phone == "+91-9876543210"
        assert result.appointment_letter_file_id == file_id
        assert result.display_order == 3


class TestCounsellorUpdate:
    def test_update_success(self):
        svc, repo = _make_svc()
        existing = MagicMock(spec=MentalHealthCounsellor)
        repo.get_by_id.return_value = existing
        repo.save.side_effect = lambda r: r
        svc.update(uuid4(), {"name": "Updated"}, uuid4())
        repo.save.assert_called_once()

    def test_update_not_found_raises(self):
        svc, repo = _make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(CounsellorError, match="not found"):
            svc.update(uuid4(), {"name": "Updated"}, uuid4())


class TestCounsellorDelete:
    def test_soft_delete_success(self):
        svc, repo = _make_svc()
        existing = MagicMock(spec=MentalHealthCounsellor)
        repo.get_by_id.return_value = existing
        repo.soft_delete.return_value = existing
        svc.soft_delete(uuid4(), uuid4())
        repo.soft_delete.assert_called_once()

    def test_soft_delete_not_found_raises(self):
        svc, repo = _make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(CounsellorError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())
