"""Identity, roles, and permission models (§8.1)."""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel

from .base import TimestampedSoftDelete

_TIMESTAMPTZ: type[Any] = cast(type[Any], sa.DateTime(timezone=True))


class User(TimestampedSoftDelete, table=True):
    __tablename__ = "users"
    __table_args__ = (
        sa.Index("ix_users_email_lower", sa.func.lower(sa.text("email")), unique=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    username: str = Field(max_length=64, nullable=False)
    email: str = Field(max_length=254, nullable=False)
    password_hash: str = Field(max_length=256, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    must_change_password: bool = Field(default=False, nullable=False)
    last_login_at: datetime | None = Field(
        default=None, sa_type=_TIMESTAMPTZ, nullable=True
    )
    profile_completed: bool = Field(default=False, nullable=False)
    aadhaar_enc: str | None = Field(default=None, max_length=512)
    pan_enc: str | None = Field(default=None, max_length=128)
    failed_login_count: int = Field(default=0, nullable=False)
    locked_until: datetime | None = Field(default=None, sa_type=_TIMESTAMPTZ, nullable=True)

    roles: list["UserRole"] = Relationship(back_populates="user")


class Role(TimestampedSoftDelete, table=True):
    __tablename__ = "roles"
    __table_args__ = (sa.UniqueConstraint("code", name="uq_roles_code"),)

    code: str = Field(max_length=64, nullable=False)
    name: str = Field(max_length=128, nullable=False)
    level: int = Field(default=0, nullable=False)
    description: str | None = Field(default=None, max_length=512)

    permissions: list["RolePermission"] = Relationship(back_populates="role")
    user_roles: list["UserRole"] = Relationship(back_populates="role")


class Permission(TimestampedSoftDelete, table=True):
    __tablename__ = "permissions"
    __table_args__ = (
        sa.UniqueConstraint(
            "resource", "action", "scope", name="uq_permissions_resource_action_scope"
        ),
    )

    resource: str = Field(max_length=64, nullable=False)
    action: str = Field(max_length=64, nullable=False)
    scope: str = Field(max_length=64, nullable=False)

    role_permissions: list["RolePermission"] = Relationship(back_populates="permission")


class RolePermission(SQLModel, table=True):
    """Junction table — no soft-delete; manage by adding/removing rows."""

    __tablename__ = "role_permissions"

    role_id: UUID = Field(foreign_key="roles.id", primary_key=True)
    permission_id: UUID = Field(foreign_key="permissions.id", primary_key=True)

    role: Role = Relationship(back_populates="permissions")
    permission: Permission = Relationship(back_populates="role_permissions")


class UserRole(SQLModel, table=True):
    """Maps a user to a role, optionally scoped to a department/campus."""

    __tablename__ = "user_roles"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    role_id: UUID = Field(foreign_key="roles.id", primary_key=True)
    scope_type: str | None = Field(default=None, max_length=32, primary_key=False)
    scope_id: UUID | None = Field(default=None)

    user: User = Relationship(back_populates="roles")
    role: Role = Relationship(back_populates="user_roles")
