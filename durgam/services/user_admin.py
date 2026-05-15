"""UserAdminService — admin-facing user CRUD and password management (§9.2)."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlmodel import func, select

from durgam.models.crosscutting import AuditLog
from durgam.models.identity import User
from durgam.repositories.user import UserRepository
from durgam.repositories.user_role import UserRoleRepository
from durgam.services.password import (
    WeakPasswordError,  # noqa: F401 — re-exported
    generate_temp_password,
    hash_password,
)

log = structlog.get_logger(__name__)


class UserAdminError(Exception):
    """Raised for user-visible admin failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class HardDeleteBlockedError(UserAdminError):
    """Raised when hard-delete is blocked because the user has audit history."""


class UserAdminService:
    def __init__(
        self,
        user_repo: UserRepository,
        user_role_repo: UserRoleRepository,
    ) -> None:
        self._users = user_repo
        self._user_roles = user_role_repo

    def list_users(
        self,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[User], int]:
        offset = (page - 1) * page_size
        return self._users.list_paginated(search, offset, page_size)

    def get_user(self, user_id: UUID) -> User | None:
        return self._users.get_by_id(user_id)

    def create_user(
        self,
        username: str,
        email: str,
        actor_id: UUID,
        role_ids: list[UUID] | None = None,
    ) -> tuple[User, str]:
        """Create a new user with an auto-generated temporary password.

        Returns (user, temp_password). The temp_password is plain text and must
        be shown exactly once; it is not recoverable after this call.
        Raises UserAdminError for duplicate username/email.
        """
        username = username.strip()
        email = email.strip().lower()
        if not username:
            raise UserAdminError("Username is required.")
        if not email or "@" not in email:
            raise UserAdminError("A valid email address is required.")

        if self._users.get_by_username(username) is not None:
            raise UserAdminError(f"Username '{username}' is already taken.")
        if self._users.get_by_email(email) is not None:
            raise UserAdminError(f"Email '{email}' is already registered.")

        temp_password = generate_temp_password()
        password_hash = hash_password(temp_password)
        user = self._users.create(
            username=username,
            email=email,
            password_hash=password_hash,
            actor_id=actor_id,
            must_change_password=True,
        )
        if role_ids:
            self._user_roles.replace_user_roles(user.id, role_ids, actor_id)

        log.info("admin_user_created", user_id=str(user.id), actor=str(actor_id))
        return user, temp_password

    def update_user(
        self,
        user_id: UUID,
        fields: dict,
        actor_id: UUID,
        role_ids: list[UUID] | None = None,
    ) -> User:
        """Update a user's fields (email, is_active, etc.) and optionally replace roles.

        Raises UserAdminError if the user is not found.
        """
        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserAdminError("User not found.")
        user = self._users.update_fields(user, fields, actor_id)
        if role_ids is not None:
            self._user_roles.replace_user_roles(user_id, role_ids, actor_id)
        log.info("admin_user_updated", user_id=str(user_id), actor=str(actor_id))
        return user

    def soft_delete_user(self, user_id: UUID, actor_id: UUID) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserAdminError("User not found.")
        user = self._users.soft_delete(user, actor_id)
        log.info("admin_user_soft_deleted", user_id=str(user_id), actor=str(actor_id))
        return user

    def hard_delete_user(self, user_id: UUID, actor_id: UUID) -> None:
        """Permanently delete a user row.

        Blocked (raises HardDeleteBlockedError) if the user has any audit log
        rows — the auditlog table is append-only and those rows cannot be updated.
        The user must be soft-deleted before hard-deleting.
        """
        # Look up including soft-deleted rows so admins can hard-delete deactivated users.
        user = self._users._session.get(User, user_id)
        if user is None:
            raise UserAdminError("User not found.")
        if not user.is_deleted:
            raise UserAdminError(
                "User must be deactivated (soft-deleted) before permanent deletion."
            )

        # The auditlog table is INSERT+SELECT only, so actor_user_id cannot be
        # nulled out — block hard-delete when audit rows exist (plan refinement 1).

        audit_count: int = self._users._session.exec(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.actor_user_id == user_id
            )
        ).one()
        if audit_count > 0:
            raise HardDeleteBlockedError(
                f"User '{user.username}' has {audit_count} audit log record(s) and "
                "cannot be permanently deleted. Soft-delete retains the audit trail."
            )

        self._users.hard_delete(user)
        log.info("admin_user_hard_deleted", user_id=str(user_id), actor=str(actor_id))

    def reset_user_password(self, user_id: UUID, actor_id: UUID) -> tuple[User, str]:
        """Generate a new temporary password for a user and set must_change_password=True.

        Returns (user, temp_password). The temp_password is plain text, must be
        shown exactly once and sent by email; it is not recoverable after this call.
        """
        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserAdminError("User not found.")
        temp_password = generate_temp_password()
        user = self._users.update_fields(
            user,
            {"password_hash": hash_password(temp_password), "must_change_password": True},
            actor_id,
        )
        log.info("admin_password_reset", user_id=str(user_id), actor=str(actor_id))
        return user, temp_password

    def assign_roles(self, user_id: UUID, role_ids: list[UUID], actor_id: UUID) -> None:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserAdminError("User not found.")
        self._user_roles.replace_user_roles(user_id, role_ids, actor_id)
        log.info("admin_roles_assigned", user_id=str(user_id), actor=str(actor_id))
