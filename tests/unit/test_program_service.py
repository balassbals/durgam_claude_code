"""Unit tests for ProgramService."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.org_exceptions import HardDeleteBlockedError
from durgam.services.program import ProgramError, ProgramService


def _make_svc(program_repo=None) -> ProgramService:
    return ProgramService(program_repo=program_repo or MagicMock())


class TestCreate:
    def test_empty_code_raises(self):
        with pytest.raises(ProgramError, match="code is required"):
            _make_svc().create("", "Name", uuid4(), "BSc", 3, uuid4())

    def test_zero_duration_raises(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        with pytest.raises(ProgramError, match="at least 1 year"):
            _make_svc(repo).create("BSCMATH", "BSc Math", uuid4(), "BSc", 0, uuid4())

    def test_duplicate_code_raises(self):
        repo = MagicMock()
        repo.get_by_code.return_value = MagicMock()
        with pytest.raises(ProgramError, match="already in use"):
            _make_svc(repo).create("BSCMATH", "BSc Math", uuid4(), "BSc", 3, uuid4())

    def test_creates_successfully(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        fake = MagicMock()
        repo.save.return_value = fake
        result = _make_svc(repo).create("BSCMATH", "BSc Math", uuid4(), "BSc", 3, uuid4())
        assert result is fake


class TestHardDelete:
    def _setup_soft_deleted(self, repo, n_courses=0, n_audit=0):
        fake = MagicMock()
        fake.is_deleted = True
        repo._session.get.return_value = fake
        # First exec call: course count; second: audit count
        repo._session.exec.return_value.one.side_effect = [n_courses, n_audit]

    def test_blocked_by_courses(self):
        repo = MagicMock()
        self._setup_soft_deleted(repo, n_courses=3, n_audit=0)
        with pytest.raises(HardDeleteBlockedError, match="3 course"):
            _make_svc(repo).hard_delete(uuid4(), uuid4())

    def test_blocked_by_audit(self):
        repo = MagicMock()
        self._setup_soft_deleted(repo, n_courses=0, n_audit=2)
        with pytest.raises(HardDeleteBlockedError, match="2 audit"):
            _make_svc(repo).hard_delete(uuid4(), uuid4())

    def test_requires_soft_delete_first(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = False
        repo._session.get.return_value = fake
        with pytest.raises(ProgramError, match="deactivated"):
            _make_svc(repo).hard_delete(uuid4(), uuid4())


class TestSubEntityReads:
    def test_get_outcomes_delegates_to_repo(self):
        repo = MagicMock()
        repo.list_outcomes.return_value = []
        svc = _make_svc(repo)
        svc.get_outcomes(uuid4())
        repo.list_outcomes.assert_called_once()

    def test_get_outcomes_by_type_delegates(self):
        repo = MagicMock()
        repo.list_outcomes_by_type.return_value = []
        svc = _make_svc(repo)
        svc.get_outcomes(uuid4(), outcome_type="PEO")
        repo.list_outcomes_by_type.assert_called_once()
