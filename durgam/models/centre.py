"""Centre of Excellence model (§8.2)."""

from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from .base import TimestampedSoftDelete


class CentreOfExcellence(TimestampedSoftDelete, table=True):
    __tablename__ = "centres_of_excellence"
    __table_args__ = (
        sa.UniqueConstraint("code", name="uq_centres_of_excellence_code"),
        sa.Index("ix_centres_of_excellence_campus_id", "campus_id"),
    )

    code: str = Field(max_length=10, nullable=False)  # CMB | CSSS | CADS | CSD
    name: str = Field(max_length=200, nullable=False)
    campus_id: UUID = Field(foreign_key="campuses.id", nullable=False)
