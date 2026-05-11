from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

# SQLModel 0.0.38 stubs declare sa_type as type[Any], but the implementation
# also accepts SQLAlchemy type instances (e.g. DateTime(timezone=True)).
# cast() satisfies mypy without any type: ignore comment.
_TIMESTAMPTZ: type[Any] = cast(type[Any], sa.DateTime(timezone=True))


class TimestampedSoftDelete(SQLModel):
    """Base mixin for every DURGAM model.

    created_by / updated_by / deleted_by store the actor UUID but carry no FK
    constraint — they may reference deleted users or system operations.
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # TODO(tech-debt-utcnow): see docs/tech_debt.md
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=_TIMESTAMPTZ,
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=_TIMESTAMPTZ,
        nullable=False,
    )
    created_by: UUID | None = Field(default=None)
    updated_by: UUID | None = Field(default=None)

    is_deleted: bool = Field(default=False, nullable=False)
    deleted_at: datetime | None = Field(
        default=None,
        sa_type=_TIMESTAMPTZ,
        nullable=True,
    )
    deleted_by: UUID | None = Field(default=None)
