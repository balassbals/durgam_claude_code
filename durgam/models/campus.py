"""Campus model (§8.2)."""

import sqlalchemy as sa
from sqlmodel import Field

from .base import TimestampedSoftDelete


class Campus(TimestampedSoftDelete, table=True):
    __tablename__ = "campuses"
    __table_args__ = (sa.UniqueConstraint("code", name="uq_campuses_code"),)

    code: str = Field(max_length=10, nullable=False)  # PSN | BRN | NDG | ATP
    name: str = Field(max_length=200, nullable=False)
    address: str | None = Field(default=None, max_length=500, nullable=True)
