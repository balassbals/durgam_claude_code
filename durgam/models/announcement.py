"""Announcement Module models (M9 — RFP §9.3, §9.6, §10.1)."""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field

from .base import TimestampedSoftDelete

_TIMESTAMPTZ: type[Any] = cast(type[Any], sa.DateTime(timezone=True))


class Announcement(TimestampedSoftDelete, table=True):
    """Single announcement entry.

    Audience is resolved lazily at query time via AudienceResolver (Q1).
    audience_group_codes is a JSONB list of AudienceGroup.code values.
    See RFP §9.6 and frozen design decisions Q1–Q16 in docs/milestones/M9.md.
    """

    __tablename__ = "announcements"
    __table_args__ = (
        sa.Index("ix_announcements_scheduled_at", "scheduled_at"),
        sa.Index("ix_announcements_composer_user", "composer_user_id"),
        sa.Index("ix_announcements_category_code", "category_code"),
        sa.Index("ix_announcements_importance", "importance"),
        sa.Index("ix_announcements_source_type", "source_type"),
    )

    title: str = Field(max_length=255, nullable=False)
    message_text: str = Field(nullable=False, sa_type=sa.Text())
    scheduled_at: datetime = Field(sa_type=_TIMESTAMPTZ, nullable=False)
    # valid values: "very_important" | "normal" — enforced at service layer
    importance: str = Field(max_length=16, nullable=False)
    category_code: str = Field(max_length=32, nullable=False)
    audience_group_codes: list[str] = Field(
        sa_column=Column(JSONB, nullable=False)
    )
    ad_hoc_user_ids: list[str] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    exclude_user_ids: list[str] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    composer_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    composer_role_code: str = Field(max_length=64, nullable=False)
    # valid values: "manual" | "auto" — enforced at service layer
    source_type: str = Field(max_length=16, nullable=False, default="manual")
    source_ref_id: UUID | None = Field(default=None)
    expires_at: datetime | None = Field(
        default=None, sa_type=_TIMESTAMPTZ, nullable=True
    )
    important_until: datetime | None = Field(
        default=None, sa_type=_TIMESTAMPTZ, nullable=True
    )


class AnnouncementComposerConfig(TimestampedSoftDelete, table=True):
    """Sys-admin-managed roster of roles that may compose announcements.

    priority_rank uses sparse integers (Q2) — lower value = higher priority
    in the dashboard widget and browse list. Seeded with 19 rows in Phase 4
    (see frozen Q11 composer-config seed in docs/milestones/M9.md).
    """

    __tablename__ = "announcement_composer_configs"
    __table_args__ = (
        sa.UniqueConstraint(
            "role_code", name="uq_announcement_composer_configs_role_code"
        ),
        sa.Index(
            "ix_announcement_composer_configs_priority_rank", "priority_rank"
        ),
        sa.Index(
            "ix_announcement_composer_configs_enabled", "enabled"
        ),
    )

    role_code: str = Field(max_length=64, nullable=False)
    priority_rank: int = Field(nullable=False)
    # valid values: "department" | "campus" | "school" | "centre" | null
    scope_restriction: str | None = Field(
        default=None, max_length=32
    )
    enabled: bool = Field(default=True, nullable=False)
    notes: str | None = Field(default=None, sa_type=sa.Text())


class AnnouncementCategory(TimestampedSoftDelete, table=True):
    """Operational taxonomy for announcements (Q17 — 9-row default seed).

    Default seed: CIRCULAR, ORDER, NOTICE, NOTIFICATION, MEMORANDUM,
    INVITATION, RESULT, ADVISORY, GENERAL. Registrar-tier governance for
    post-launch additions via /admin/announcement-categories (Phase 5).
    """

    __tablename__ = "announcement_categories"
    __table_args__ = (
        sa.UniqueConstraint("code", name="uq_announcement_categories_code"),
        sa.Index("ix_announcement_categories_display_order", "display_order"),
        sa.Index("ix_announcement_categories_is_active", "is_active"),
    )

    code: str = Field(max_length=32, nullable=False)
    name: str = Field(max_length=100, nullable=False)
    display_order: int = Field(default=0, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    notes: str | None = Field(default=None, sa_type=sa.Text())


class AudienceGroup(TimestampedSoftDelete, table=True):
    """Institutional audience grouping for announcement targeting (Q18).

    filter_json schema (validated by AudienceResolver service in Phase 2):
      role_codes:           list[str] | None
      scope_type:           "school" | "department" | "campus" | "program" | "centre" | None
      scope_codes:          list[str] | None
      scope_ids:            list[str] | None    (UUIDs as strings)
      program_degree_types: list[str] | None

    Default seed: 23 explicit rows + dynamic per-campus rows (Phase 4).
    Registrar-tier governance for post-launch edits via /admin/audience-groups.
    """

    __tablename__ = "audience_groups"
    __table_args__ = (
        sa.UniqueConstraint("code", name="uq_audience_groups_code"),
        sa.Index("ix_audience_groups_is_active", "is_active"),
    )

    code: str = Field(max_length=64, nullable=False)
    name: str = Field(max_length=200, nullable=False)
    description: str | None = Field(default=None, sa_type=sa.Text())
    filter_json: dict[str, Any] = Field(
        sa_column=Column(JSONB, nullable=False)
    )
    is_active: bool = Field(default=True, nullable=False)
