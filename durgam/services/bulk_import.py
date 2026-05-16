"""BulkImportService — two-stage CSV import for users (§9.2(d), §16).

Stage 1: validate_user_csv — parse bytes, check schema, validate each row.
Stage 2: commit_user_import — insert valid rows, return (success_count, errors).

Errors do not commit the row (per §16 risk note). Valid rows commit individually.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from uuid import UUID

import structlog

from durgam.repositories.role import RoleRepository
from durgam.repositories.user import UserRepository
from durgam.repositories.user_role import UserRoleRepository
from durgam.services.password import generate_temp_password, hash_password

log = structlog.get_logger(__name__)

_REQUIRED_COLS = {"username", "email", "role_code"}
_OPTIONAL_COLS: set[str] = set()  # no optional cols at M2; User has no name field
_ALL_COLS = _REQUIRED_COLS | _OPTIONAL_COLS


@dataclass
class ValidRow:
    row_number: int
    username: str
    email: str
    role_code: str


@dataclass
class InvalidRow:
    row_number: int
    raw: dict
    error: str


@dataclass
class ImportResult:
    success_count: int
    errors: list[InvalidRow] = field(default_factory=list)


def validate_user_csv(
    file_bytes: bytes,
    *,
    role_repo: RoleRepository,
    user_repo: UserRepository,
    max_preview_rows: int = 100,
) -> tuple[list[ValidRow], list[InvalidRow]]:
    """Parse a CSV and validate each row against the user import schema.

    Returns (valid_rows, invalid_rows). Only the first max_preview_rows are
    validated and returned (preview cap); the rest are ignored.

    CSV schema: username, email, role_code (required). No optional columns at M2
    (the User model has no name/description field; full_name column removed).
    Unknown extra columns are accepted and silently ignored.
    """
    try:
        text = file_bytes.decode("utf-8-sig")  # handle BOM from Excel exports
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], [InvalidRow(row_number=0, raw={}, error="File appears to be empty.")]

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = _REQUIRED_COLS - headers
    if missing:
        return [], [
            InvalidRow(
                row_number=0,
                raw={},
                error=f"Missing required columns: {', '.join(sorted(missing))}.",
            )
        ]

    # Build a set of valid role codes for fast lookup.
    valid_roles = {r.code for r in role_repo.list_active()}

    valid: list[ValidRow] = []
    invalid: list[InvalidRow] = []
    seen_usernames: set[str] = set()
    seen_emails: set[str] = set()

    for i, raw_row in enumerate(reader, start=2):  # row 1 is the header
        if i - 1 > max_preview_rows:
            break
        row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}

        username = row.get("username", "")
        email = row.get("email", "").lower()
        role_code = row.get("role_code", "").upper()

        errors_for_row = []

        if not username:
            errors_for_row.append("username is required")
        if not email or "@" not in email:
            errors_for_row.append("valid email is required")
        if not role_code:
            errors_for_row.append("role_code is required")
        elif role_code not in valid_roles:
            errors_for_row.append(f"unknown role_code '{role_code}'")

        if username and username in seen_usernames:
            errors_for_row.append(f"duplicate username '{username}' within this file")
        if email and email in seen_emails:
            errors_for_row.append(f"duplicate email '{email}' within this file")

        if not errors_for_row and username and user_repo.get_by_username(username) is not None:
            errors_for_row.append(f"username '{username}' already exists in the system")
        if not errors_for_row and email and user_repo.get_by_email(email) is not None:
            errors_for_row.append(f"email '{email}' already registered in the system")

        if errors_for_row:
            invalid.append(InvalidRow(row_number=i, raw=dict(row), error="; ".join(errors_for_row)))
        else:
            seen_usernames.add(username)
            seen_emails.add(email)
            valid.append(ValidRow(row_number=i, username=username, email=email,
                                  role_code=role_code))

    return valid, invalid


def commit_user_import(
    valid_rows: list[ValidRow],
    actor_id: UUID,
    *,
    user_repo: UserRepository,
    user_role_repo: UserRoleRepository,
    role_repo: RoleRepository,
) -> ImportResult:
    """Commit valid rows from a prior validate_user_csv call.

    Each row is committed individually (partial success per §16). If a row fails
    at commit time (e.g. race condition on username), it is added to errors.
    Returns ImportResult with success_count and any late errors.
    """
    roles = {r.code: r for r in role_repo.list_active()}
    success = 0
    late_errors: list[InvalidRow] = []

    for vrow in valid_rows:
        try:
            temp_pw = generate_temp_password()
            user = user_repo.create(
                username=vrow.username,
                email=vrow.email,
                password_hash=hash_password(temp_pw),
                actor_id=actor_id,
                must_change_password=True,
            )
            role = roles.get(vrow.role_code)
            if role:
                user_role_repo.replace_user_roles(user.id, [role.id], actor_id)
            success += 1
            log.info("bulk_import_user_created", username=vrow.username, actor=str(actor_id))
        except Exception as exc:
            log.warning("bulk_import_row_failed", row=vrow.row_number, error=str(exc))
            late_errors.append(InvalidRow(
                row_number=vrow.row_number,
                raw={"username": vrow.username, "email": vrow.email, "role_code": vrow.role_code},
                error=str(exc),
            ))

    return ImportResult(success_count=success, errors=late_errors)
