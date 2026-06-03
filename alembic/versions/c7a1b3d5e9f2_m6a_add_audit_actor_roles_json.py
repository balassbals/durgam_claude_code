"""m6a_add_audit_actor_roles_json

Revision ID: c7a1b3d5e9f2
Revises: bb5c4d197ec5
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c7a1b3d5e9f2'
down_revision: Union[str, Sequence[str], None] = 'bb5c4d197ec5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("actor_roles_json", postgresql.JSONB, nullable=True),
    )
    op.create_index(
        "ix_audit_logs_actor_roles_gin",
        "audit_logs",
        ["actor_roles_json"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_actor_roles_gin", table_name="audit_logs")
    op.drop_column("audit_logs", "actor_roles_json")
