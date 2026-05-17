"""Unit tests for BulkImportService CSV validation (§9.2(d), §16)."""

from __future__ import annotations

from unittest.mock import MagicMock

from durgam.services.bulk_import import validate_user_csv


def _role_repo_with(codes: list[str]) -> MagicMock:
    roles = []
    for code in codes:
        r = MagicMock()
        r.code = code
        roles.append(r)
    repo = MagicMock()
    repo.list_active.return_value = roles
    return repo


def _clean_user_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_username.return_value = None
    repo.get_by_email.return_value = None
    return repo


def _csv(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    header = ",".join(rows[0].keys())
    lines = [header] + [",".join(str(v) for v in r.values()) for r in rows]
    return "\n".join(lines).encode()


class TestValidateUserCsv:
    def test_valid_rows_all_pass(self):
        csv_bytes = _csv([
            {"username": "u1", "email": "u1@t.com", "role_code": "STUDENT"},
            {"username": "u2", "email": "u2@t.com", "role_code": "STUDENT"},
        ])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=_clean_user_repo(),
        )
        assert len(valid) == 2
        assert len(invalid) == 0

    def test_missing_required_email_column_fails_entirely(self):
        csv_bytes = b"username,role_code\nu1,STUDENT"
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=_clean_user_repo(),
        )
        # Returns one global error row at row_number=0
        assert len(valid) == 0
        assert len(invalid) == 1
        assert invalid[0].row_number == 0
        assert "email" in invalid[0].error.lower()

    def test_empty_file_returns_global_error(self):
        valid, invalid = validate_user_csv(
            b"",
            role_repo=_role_repo_with([]),
            user_repo=_clean_user_repo(),
        )
        assert len(valid) == 0
        assert len(invalid) == 1

    def test_unknown_role_code_marks_row_invalid(self):
        csv_bytes = _csv([
            {"username": "u1", "email": "u1@t.com", "role_code": "NONEXISTENT"},
        ])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=_clean_user_repo(),
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "NONEXISTENT" in invalid[0].error

    def test_duplicate_username_within_file_marks_second_row_invalid(self):
        csv_bytes = _csv([
            {"username": "u1", "email": "u1@t.com", "role_code": "STUDENT"},
            {"username": "u1", "email": "u2@t.com", "role_code": "STUDENT"},
        ])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=_clean_user_repo(),
        )
        assert len(valid) == 1
        assert len(invalid) == 1
        assert "duplicate" in invalid[0].error.lower()

    def test_existing_username_in_system_marks_row_invalid(self):
        user_repo = _clean_user_repo()
        user_repo.get_by_username.return_value = MagicMock()  # already exists
        csv_bytes = _csv([{"username": "taken", "email": "taken@t.com", "role_code": "STUDENT"}])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=user_repo,
        )
        assert len(valid) == 0
        assert len(invalid) == 1
        assert "already exists" in invalid[0].error

    def test_mixed_valid_and_invalid_rows(self):
        csv_bytes = _csv([
            {"username": "good", "email": "good@t.com", "role_code": "STUDENT"},
            {"username": "", "email": "bad@t.com", "role_code": "STUDENT"},     # missing username
            {"username": "good2", "email": "good2@t.com", "role_code": "STUDENT"},
        ])
        valid, invalid = validate_user_csv(
            csv_bytes,
            role_repo=_role_repo_with(["STUDENT"]),
            user_repo=_clean_user_repo(),
        )
        assert len(valid) == 2
        assert len(invalid) == 1
