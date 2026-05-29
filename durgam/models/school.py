"""School model (§8.2)."""

import sqlalchemy as sa
from sqlmodel import Field

from .base import TimestampedSoftDelete


class School(TimestampedSoftDelete, table=True):
    __tablename__ = "schools"
    __table_args__ = (sa.UniqueConstraint("code", name="uq_schools_code"),)

    code: str = Field(max_length=10, nullable=False)  # SCI | HSS | LL | MC
    name: str = Field(max_length=200, nullable=False)
