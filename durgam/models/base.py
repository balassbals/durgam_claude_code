from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class TimestampedSoftDelete(SQLModel):
    """Base mixin for every DURGAM model.

    created_by / updated_by / deleted_by store the actor UUID but carry no FK
    constraint — they may reference deleted users or system operations.
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    created_by: UUID | None = Field(default=None)
    updated_by: UUID | None = Field(default=None)

    is_deleted: bool = Field(default=False, nullable=False)
    deleted_at: datetime | None = Field(default=None)
    deleted_by: UUID | None = Field(default=None)
