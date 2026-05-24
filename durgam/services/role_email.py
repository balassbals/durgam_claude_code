"""RoleEmailService — CRUD for role-bound email addresses (§8.5, E-004)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import RoleEmail
from durgam.repositories.role_email import RoleEmailRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RoleEmailError(OrgServiceError):
    pass


class RoleEmailService:
    def __init__(self, repo: RoleEmailRepository) -> None:
        self._repo = repo

    def list_all(self) -> list[RoleEmail]:
        return self._repo.list_active_ordered()

    def get(self, record_id: UUID) -> RoleEmail:
        row = self._repo.get_by_id(record_id)
        if row is None:
            raise RoleEmailError("Role email not found.")
        return row

    def create(
        self,
        role_code: str,
        email: str,
        actor_id: UUID,
        *,
        scope_type: str | None = None,
        scope_id: UUID | None = None,
    ) -> RoleEmail:
        role_code = role_code.strip().upper()
        email = email.strip().lower()
        if not role_code:
            raise RoleEmailError("Role code is required.")
        if not _EMAIL_RE.match(email):
            raise RoleEmailError("Invalid email address format.")
        self._check_scope_consistency(scope_type, scope_id)
        if self._repo.get_by_role_and_scope(role_code, scope_type, scope_id):
            raise RoleEmailError(
                f"An email for role '{role_code}' with this scope already exists."
            )
        now = datetime.now(UTC)
        row = RoleEmail(
            role_code=role_code,
            email=email,
            scope_type=scope_type,
            scope_id=scope_id,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        row = self._repo.save(row)
        log.info("role_email_created", id=str(row.id), role=role_code, actor=str(actor_id))
        return row

    def update(self, record_id: UUID, fields: dict, actor_id: UUID) -> RoleEmail:
        row = self.get(record_id)
        if "email" in fields:
            email = fields["email"].strip().lower()
            if not _EMAIL_RE.match(email):
                raise RoleEmailError("Invalid email address format.")
            row.email = email
        if "role_code" in fields:
            rc = fields["role_code"].strip().upper()
            if not rc:
                raise RoleEmailError("Role code is required.")
            row.role_code = rc
        if "scope_type" in fields or "scope_id" in fields:
            st = fields.get("scope_type", row.scope_type)
            si = fields.get("scope_id", row.scope_id)
            self._check_scope_consistency(st, si)
            row.scope_type = st
            row.scope_id = si
        row.updated_by = actor_id
        row = self._repo.save(row)
        log.info("role_email_updated", id=str(record_id), actor=str(actor_id))
        return row

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> RoleEmail:
        row = self.get(record_id)
        row = self._repo.soft_delete(row, actor_id)
        log.info("role_email_soft_deleted", id=str(record_id), actor=str(actor_id))
        return row

    @staticmethod
    def _check_scope_consistency(scope_type: str | None, scope_id: UUID | None) -> None:
        if (scope_type is None) != (scope_id is None):
            raise RoleEmailError(
                "scope_type and scope_id must both be set or both be empty."
            )
