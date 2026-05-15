"""Unit tests for non-trivial admin state handler logic (M2 design question vi).

These tests verify the business logic of non-trivial handlers by testing
the service-layer calls and state var mutations they would perform, without
constructing a live Reflex state (which requires a running Reflex server).

The patterns tested:
- Error → flash (UserAdminError propagation)
- Success → generated_password population
- CSV validation → preview state vars (valid/invalid split)

Full end-to-end handler execution is covered by the E2E suite.
Thin handlers (load_users, load_roles, etc.) are E2E-only per M2.md decision.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.services.bulk_import import validate_user_csv
from durgam.services.user_admin import UserAdminError

# ── create_user logic ─────────────────────────────────────────────────────────

class TestCreateUserLogic:
    """Verify the branching logic inside create_user without Reflex state."""

    def test_empty_username_triggers_early_return_flash(self) -> None:
        from durgam.services.user_admin import UserAdminService

        user_repo = MagicMock()
        user_role_repo = MagicMock()
        svc = UserAdminService(user_repo=user_repo, user_role_repo=user_role_repo)

        with pytest.raises(UserAdminError, match="Username is required"):
            svc.create_user("", "a@b.com", uuid4())

    def test_duplicate_username_raises_admin_error(self) -> None:
        from durgam.services.user_admin import UserAdminService

        user_repo = MagicMock()
        user_repo.get_by_username.return_value = MagicMock()  # already exists
        user_role_repo = MagicMock()
        svc = UserAdminService(user_repo=user_repo, user_role_repo=user_role_repo)

        with pytest.raises(UserAdminError, match="already taken"):
            svc.create_user("jdoe", "jdoe@test.com", uuid4())

    def test_success_returns_user_and_password(self) -> None:
        from durgam.services.user_admin import UserAdminService

        user_repo = MagicMock()
        user_repo.get_by_username.return_value = None
        user_repo.get_by_email.return_value = None
        fake_user = MagicMock()
        fake_user.id = uuid4()
        user_repo.create.return_value = fake_user
        user_role_repo = MagicMock()
        svc = UserAdminService(user_repo=user_repo, user_role_repo=user_role_repo)

        with patch("durgam.services.user_admin.generate_temp_password",
                   return_value="TmpPw1!Abc999"):
            user, pw = svc.create_user("jdoe", "jdoe@test.com", uuid4())

        assert user is fake_user
        assert pw == "TmpPw1!Abc999"
        assert len(pw) > 0


# ── reset_user_password logic ─────────────────────────────────────────────────

class TestResetPasswordLogic:
    def test_not_found_raises(self) -> None:
        from durgam.services.user_admin import UserAdminService

        user_repo = MagicMock()
        user_repo.get_by_id.return_value = None
        svc = UserAdminService(user_repo=user_repo, user_role_repo=MagicMock())

        with pytest.raises(UserAdminError, match="not found"):
            svc.reset_user_password(uuid4(), uuid4())

    def test_success_returns_user_and_new_password(self) -> None:
        from durgam.services.user_admin import UserAdminService

        fake_user = MagicMock()
        fake_user.id = uuid4()
        user_repo = MagicMock()
        user_repo.get_by_id.return_value = fake_user
        user_repo.update_fields.return_value = fake_user
        svc = UserAdminService(user_repo=user_repo, user_role_repo=MagicMock())

        with patch("durgam.services.user_admin.generate_temp_password",
                   return_value="NewPw1!Xyz777"):
            user, pw = svc.reset_user_password(uuid4(), uuid4())

        assert pw == "NewPw1!Xyz777"
        user_repo.update_fields.assert_called_once()

    def test_new_password_differs_from_old(self) -> None:
        """Generated password must be non-deterministic."""
        from durgam.services.password import generate_temp_password

        p1 = generate_temp_password()
        p2 = generate_temp_password()
        assert p1 != p2


# ── upload_csv state var logic ────────────────────────────────────────────────

class TestUploadCsvLogic:
    """Verify validate_user_csv produces the expected valid/invalid split
    that upload_csv uses to set preview_valid and preview_invalid."""

    def _role_repo(self, codes: list[str]) -> MagicMock:
        roles = [MagicMock(code=c) for c in codes]
        repo = MagicMock()
        repo.list_active.return_value = roles
        return repo

    def _clean_user_repo(self) -> MagicMock:
        repo = MagicMock()
        repo.get_by_username.return_value = None
        repo.get_by_email.return_value = None
        return repo

    def _csv(self, rows: list[dict]) -> bytes:
        header = ",".join(rows[0].keys())
        lines = [header] + [",".join(str(v) for v in r.values()) for r in rows]
        return "\n".join(lines).encode()

    def test_empty_file_produces_global_error(self) -> None:
        valid, invalid = validate_user_csv(
            b"",
            role_repo=self._role_repo([]),
            user_repo=self._clean_user_repo(),
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert invalid[0].row_number == 0  # global error at row 0

    def test_valid_rows_set_preview_valid(self) -> None:
        csv_bytes = self._csv([
            {"username": "u1", "email": "u1@t.com", "role_code": "STUDENT"},
        ])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=self._role_repo(["STUDENT"]),
            user_repo=self._clean_user_repo(),
        )
        assert len(valid) == 1
        assert len(invalid) == 0
        # upload_csv sets: preview_ready = True when valid rows exist
        preview_ready = len(valid) > 0 or len(invalid) > 0
        assert preview_ready is True

    def test_mixed_rows_split_into_valid_and_invalid(self) -> None:
        csv_bytes = self._csv([
            {"username": "good", "email": "good@t.com", "role_code": "STUDENT"},
            {"username": "", "email": "bad@t.com", "role_code": "STUDENT"},
        ])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=self._role_repo(["STUDENT"]),
            user_repo=self._clean_user_repo(),
        )
        assert len(valid) == 1
        assert len(invalid) == 1
        # upload_csv sets both preview_valid and preview_invalid lists
        assert valid[0].username == "good"
        assert "username" in invalid[0].error.lower() or "required" in invalid[0].error.lower()
