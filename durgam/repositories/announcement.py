"""Announcement-module repositories (M9).

Four classes — one per main config table plus the Announcement table itself.
All follow the codebase's session-inject + flush pattern (durgam/repositories/leave.py).
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Session, select

from durgam.models.announcement import (
    Announcement,
    AnnouncementCategory,
    AnnouncementComposerConfig,
    AudienceGroup,
)


class AnnouncementCategoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, category: AnnouncementCategory) -> AnnouncementCategory:
        self._session.add(category)
        self._session.flush()
        self._session.refresh(category)
        return category

    def get(self, id_: UUID) -> AnnouncementCategory | None:
        row = self._session.get(AnnouncementCategory, id_)
        if row is None or row.is_deleted:
            return None
        return row

    def get_by_code(self, code: str) -> AnnouncementCategory | None:
        return self._session.exec(
            select(AnnouncementCategory).where(
                AnnouncementCategory.code == code,
                AnnouncementCategory.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_active(self) -> list[AnnouncementCategory]:
        return list(
            self._session.exec(
                select(AnnouncementCategory)
                .where(
                    AnnouncementCategory.is_active == True,  # noqa: E712
                    AnnouncementCategory.is_deleted == False,  # noqa: E712
                )
                .order_by(AnnouncementCategory.display_order)
            ).all()
        )

    def list_all(self) -> list[AnnouncementCategory]:
        return list(
            self._session.exec(
                select(AnnouncementCategory)
                .where(AnnouncementCategory.is_deleted == False)  # noqa: E712
                .order_by(AnnouncementCategory.display_order)
            ).all()
        )

    def update(self, id_: UUID, **fields: object) -> AnnouncementCategory:
        row = self._session.get(AnnouncementCategory, id_)
        if row is None:
            raise ValueError(f"AnnouncementCategory {id_} not found")
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def soft_delete(self, id_: UUID, by_user_id: UUID) -> None:
        row = self._session.get(AnnouncementCategory, id_)
        if row is None or row.is_deleted:
            return
        row.is_deleted = True
        row.deleted_at = datetime.now(UTC)
        row.deleted_by = by_user_id
        self._session.add(row)
        self._session.flush()


class AnnouncementComposerConfigRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, config: AnnouncementComposerConfig) -> AnnouncementComposerConfig:
        self._session.add(config)
        self._session.flush()
        self._session.refresh(config)
        return config

    def get(self, id_: UUID) -> AnnouncementComposerConfig | None:
        row = self._session.get(AnnouncementComposerConfig, id_)
        if row is None or row.is_deleted:
            return None
        return row

    def get_by_role_code(self, role_code: str) -> AnnouncementComposerConfig | None:
        return self._session.exec(
            select(AnnouncementComposerConfig).where(
                AnnouncementComposerConfig.role_code == role_code,
                AnnouncementComposerConfig.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_enabled_ordered(self) -> list[AnnouncementComposerConfig]:
        return list(
            self._session.exec(
                select(AnnouncementComposerConfig)
                .where(
                    AnnouncementComposerConfig.enabled == True,  # noqa: E712
                    AnnouncementComposerConfig.is_deleted == False,  # noqa: E712
                )
                .order_by(AnnouncementComposerConfig.priority_rank)
            ).all()
        )

    def list_all(self) -> list[AnnouncementComposerConfig]:
        return list(
            self._session.exec(
                select(AnnouncementComposerConfig)
                .where(AnnouncementComposerConfig.is_deleted == False)  # noqa: E712
                .order_by(AnnouncementComposerConfig.priority_rank)
            ).all()
        )

    def update(self, id_: UUID, **fields: object) -> AnnouncementComposerConfig:
        row = self._session.get(AnnouncementComposerConfig, id_)
        if row is None:
            raise ValueError(f"AnnouncementComposerConfig {id_} not found")
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def soft_delete(self, id_: UUID, by_user_id: UUID) -> None:
        row = self._session.get(AnnouncementComposerConfig, id_)
        if row is None or row.is_deleted:
            return
        row.is_deleted = True
        row.deleted_at = datetime.now(UTC)
        row.deleted_by = by_user_id
        self._session.add(row)
        self._session.flush()


class AudienceGroupRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, group: AudienceGroup) -> AudienceGroup:
        self._session.add(group)
        self._session.flush()
        self._session.refresh(group)
        return group

    def get(self, id_: UUID) -> AudienceGroup | None:
        row = self._session.get(AudienceGroup, id_)
        if row is None or row.is_deleted:
            return None
        return row

    def get_by_code(self, code: str) -> AudienceGroup | None:
        return self._session.exec(
            select(AudienceGroup).where(
                AudienceGroup.code == code,
                AudienceGroup.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_active(self) -> list[AudienceGroup]:
        return list(
            self._session.exec(
                select(AudienceGroup)
                .where(
                    AudienceGroup.is_active == True,  # noqa: E712
                    AudienceGroup.is_deleted == False,  # noqa: E712
                )
                .order_by(AudienceGroup.code)
            ).all()
        )

    def list_all(self) -> list[AudienceGroup]:
        return list(
            self._session.exec(
                select(AudienceGroup)
                .where(AudienceGroup.is_deleted == False)  # noqa: E712
                .order_by(AudienceGroup.code)
            ).all()
        )

    def update(self, id_: UUID, **fields: object) -> AudienceGroup:
        row = self._session.get(AudienceGroup, id_)
        if row is None:
            raise ValueError(f"AudienceGroup {id_} not found")
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def soft_delete(self, id_: UUID, by_user_id: UUID) -> None:
        row = self._session.get(AudienceGroup, id_)
        if row is None or row.is_deleted:
            return
        row.is_deleted = True
        row.deleted_at = datetime.now(UTC)
        row.deleted_by = by_user_id
        self._session.add(row)
        self._session.flush()


class AnnouncementRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, announcement: Announcement) -> Announcement:
        self._session.add(announcement)
        self._session.flush()
        self._session.refresh(announcement)
        return announcement

    def get(self, id_: UUID) -> Announcement | None:
        row = self._session.get(Announcement, id_)
        if row is None or row.is_deleted:
            return None
        return row

    def list_visible_to_user(
        self,
        user_id: UUID,
        user_groups: set[str],
        now: datetime,
        *,
        importance: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Announcement]:
        """Return announcements visible to user, scheduled at or before now.

        Audience filter (Q1 lazy resolution): the caller pre-computes
        user_groups via AudienceResolver.groups_user_belongs_to().

        JSONB operations:
        - ?|   checks if any element of user_groups_array exists in audience_group_codes
        - @>   checks JSONB containment (ad_hoc / exclude arrays)
        """
        uid_str = str(user_id)
        uid_json = sa.cast([uid_str], JSONB)

        # Audience match: in a named group OR explicitly included ad-hoc.
        # ad_hoc_user_ids may be NULL — handle with coalesce-style IS NULL OR @>
        if user_groups:
            groups_list = list(user_groups)
            audience_cond = sa.or_(
                Announcement.audience_group_codes.op("?|")(  # type: ignore[union-attr]
                    sa.cast(groups_list, sa.ARRAY(sa.String()))
                ),
                sa.and_(
                    Announcement.ad_hoc_user_ids.isnot(None),
                    Announcement.ad_hoc_user_ids.op("@>")(uid_json),  # type: ignore[union-attr]
                ),
            )
        else:
            # No groups — only ad_hoc inclusion can match
            audience_cond = sa.and_(
                Announcement.ad_hoc_user_ids.isnot(None),
                Announcement.ad_hoc_user_ids.op("@>")(uid_json),  # type: ignore[union-attr]
            )

        # Exclude condition: user NOT in exclude list (NULL exclude list = no exclusion)
        not_excluded_cond = sa.or_(
            Announcement.exclude_user_ids.is_(None),
            sa.not_(
                Announcement.exclude_user_ids.op("@>")(uid_json)  # type: ignore[union-attr]
            ),
        )

        stmt = (
            select(Announcement)
            .where(
                Announcement.is_deleted == False,  # noqa: E712
                Announcement.scheduled_at <= now,
                audience_cond,
                not_excluded_cond,
            )
            .order_by(Announcement.scheduled_at.desc())
        )

        if importance is not None:
            stmt = stmt.where(Announcement.importance == importance)
        if since is not None:
            stmt = stmt.where(Announcement.scheduled_at >= since)
        if until is not None:
            stmt = stmt.where(Announcement.scheduled_at <= until)

        return list(self._session.exec(stmt).all())

    def list_by_composer(
        self,
        composer_user_id: UUID,
        *,
        include_withdrawn: bool = False,
    ) -> list[Announcement]:
        stmt = select(Announcement).where(
            Announcement.composer_user_id == composer_user_id
        )
        if not include_withdrawn:
            stmt = stmt.where(Announcement.is_deleted == False)  # noqa: E712
        stmt = stmt.order_by(Announcement.scheduled_at.desc())
        return list(self._session.exec(stmt).all())

    def list_pending_schedule(self, now: datetime) -> list[Announcement]:
        return list(
            self._session.exec(
                select(Announcement)
                .where(
                    Announcement.scheduled_at > now,
                    Announcement.is_deleted == False,  # noqa: E712
                )
                .order_by(Announcement.scheduled_at.asc())
            ).all()
        )

    def update(self, id_: UUID, **fields: object) -> Announcement:
        row = self._session.get(Announcement, id_)
        if row is None:
            raise ValueError(f"Announcement {id_} not found")
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def withdraw(self, id_: UUID, by_user_id: UUID) -> Announcement:
        """Soft-delete (withdraw) an announcement."""
        row = self._session.get(Announcement, id_)
        if row is None:
            raise ValueError(f"Announcement {id_} not found")
        row.is_deleted = True
        row.deleted_at = datetime.now(UTC)
        row.deleted_by = by_user_id
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row
