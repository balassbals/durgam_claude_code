"""Unit tests for ConfigSingletonService — validation and singleton access."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.config_singleton import ConfigError, ConfigSingletonService


def _make_svc(config_repo=None) -> ConfigSingletonService:
    return ConfigSingletonService(config_repo=config_repo or MagicMock())


class TestClassTimings:
    def test_get_delegates_to_repo(self):
        repo = MagicMock()
        fake = MagicMock()
        repo.get_or_create_class_timings.return_value = fake
        svc = _make_svc(repo)
        result = svc.get_class_timings()
        assert result is fake
        repo.get_or_create_class_timings.assert_called_once()

    def test_invalid_periods_raises(self):
        repo = MagicMock()
        ctc = MagicMock()
        repo.get_or_create_class_timings.return_value = ctc
        svc = _make_svc(repo)
        with pytest.raises(ConfigError, match="between 1 and 20"):
            svc.save_class_timings(ctc, uuid4(), periods_per_day=25)

    def test_invalid_period_duration_raises(self):
        repo = MagicMock()
        ctc = MagicMock()
        svc = _make_svc(repo)
        with pytest.raises(ConfigError, match="between 10 and 180"):
            svc.save_class_timings(ctc, uuid4(), period_duration_minutes=5)

    def test_invalid_hhmm_raises(self):
        repo = MagicMock()
        ctc = MagicMock()
        svc = _make_svc(repo)
        with pytest.raises(ConfigError, match="HH:MM format"):
            svc.save_class_timings(ctc, uuid4(), first_period_start="8:00")

    def test_valid_hhmm_accepted(self):
        repo = MagicMock()
        ctc = MagicMock()
        repo.save_class_timings.return_value = ctc
        svc = _make_svc(repo)
        svc.save_class_timings(ctc, uuid4(), first_period_start="08:30")
        repo.save_class_timings.assert_called_once()

    def test_save_sets_actor(self):
        repo = MagicMock()
        ctc = MagicMock()
        repo.save_class_timings.return_value = ctc
        actor = uuid4()
        svc = _make_svc(repo)
        svc.save_class_timings(ctc, actor, periods_per_day=8)
        assert ctc.updated_by == actor


class TestWorkingDays:
    def test_invalid_days_raises(self):
        repo = MagicMock()
        wdc = MagicMock()
        svc = _make_svc(repo)
        with pytest.raises(ConfigError, match="5 or 6"):
            svc.save_working_days(wdc, uuid4(), days_per_week=4)

    def test_valid_6_day_week_accepted(self):
        repo = MagicMock()
        wdc = MagicMock()
        repo.save_working_days.return_value = wdc
        svc = _make_svc(repo)
        svc.save_working_days(wdc, uuid4(), days_per_week=6)
        assert wdc.days_per_week == 6
