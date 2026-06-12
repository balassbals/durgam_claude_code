"""AnnouncementService — announcement lifecycle orchestration (M9 Phase 6a).

Field-name deviations from spec (discovered via Task 1 model inspection):
- body_text (service param) → message_text (model field)
- importance: "very_important"|"normal" (model); spec said "important"
- source_type (model); spec said source_kind
- audience_group_codes: list[str] (model); spec said single audience_group_code
- withdraw() uses is_deleted=True via repo.withdraw() — no withdrawn_at field on model
- scheduled_at and composer_role_code added to create signature (required by model)
- compute_important_until (Phase 2 name); window_days=2 default (not 7)
- Pagination done at service layer (slice after load) — no repo.list_paginated method

Audit emitted via write_audit_row directly (M7 pattern) so the auto-announcement
hook in Phase 8 also records audit rows without needing a state handler context.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlmodel import Session, select

from durgam.audit.log import write_audit_row
from durgam.audit.snapshot import audit_snapshot
from durgam.models.announcement import (
    Announcement,
    AnnouncementComposerConfig,
    AudienceGroup,
)
from durgam.models.identity import Role, UserRole
from durgam.repositories.announcement import (
    AnnouncementCategoryRepository,
    AnnouncementComposerConfigRepository,
    AnnouncementRepository,
    AudienceGroupRepository,
)
from durgam.services.audience_resolver import AudienceResolver
from durgam.services.announcement_priority import (
    compute_important_until,
    sort_for_viewer,
)
from durgam.services.holiday import get_holiday_dates_in_window

log = structlog.get_logger(__name__)

_VALID_IMPORTANCE = frozenset({"very_important", "normal"})
_HOLIDAY_WINDOW_DAYS = 14  # safe upper bound for 2-working-day window


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------

class AnnouncementError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AnnouncementComposerNotEligibleError(AnnouncementError): ...


class AnnouncementWithdrawalNotAllowedError(AnnouncementError): ...


class AnnouncementNotFoundError(AnnouncementError): ...


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AnnouncementService:
    def __init__(
        self,
        repo: AnnouncementRepository,
        config_repo: AnnouncementComposerConfigRepository,
        category_repo: AnnouncementCategoryRepository,
        audience_repo: AudienceGroupRepository,
        session: Session,
    ) -> None:
        self._repo = repo
        self._config_repo = config_repo
        self._category_repo = category_repo
        self._audience_repo = audience_repo
        self._session = session
        self._resolver = AudienceResolver()

    # ── Public API ────────────────────────────────────────────────────────────

    def create_announcement(
        self,
        *,
        composer_user_id: UUID,
        composer_role_code: str,
        category_code: str,
        audience_group_codes: list[str],
        title: str,
        body_text: str,
        importance: str,
        scheduled_at: datetime | None = None,
        actor_id: UUID,
    ) -> Announcement:
        """Create and persist a new announcement.

        Deviations from Phase 6a spec:
        - composer_role_code added (required by model)
        - audience_group_codes is a list (model stores JSONB list)
        - scheduled_at added (required by model); defaults to utcnow if None
        - importance must be "very_important" or "normal" (model values)
        - body_text stored as message_text on the model
        """
        title = title.strip()
        body_text = body_text.strip()
        if not title:
            raise AnnouncementError("Title is required.")
        if len(title) > 255:
            raise AnnouncementError("Title must be 255 characters or fewer.")
        if not body_text:
            raise AnnouncementError("Body text is required.")
        if importance not in _VALID_IMPORTANCE:
            raise AnnouncementError(
                f"importance must be one of: {', '.join(sorted(_VALID_IMPORTANCE))}."
            )

        # Category must exist and be active
        category = self._category_repo.get_by_code(category_code)
        if category is None or not category.is_active:
            raise AnnouncementError(f"Unknown category: '{category_code}'.")

        # All audience_group_codes must exist and be active
        for ag_code in audience_group_codes:
            ag = self._audience_repo.get_by_code(ag_code)
            if ag is None or not ag.is_active:
                raise AnnouncementError(
                    f"Unknown or inactive audience group: '{ag_code}'."
                )

        # Composer eligibility: user must have ≥1 active UserRole whose
        # Role.code appears in announcement_composer_configs with enabled=True.
        self._check_composer_eligible(composer_user_id)

        now = datetime.now(UTC)
        scheduled_at = scheduled_at or now

        # Compute important_until for very_important announcements
        important_until: datetime | None = None
        if importance == "very_important":
            scheduled_date = scheduled_at.astimezone(
                UTC  # get_holiday_dates_in_window works on date objects
            ).date()
            window_end = scheduled_date + timedelta(days=_HOLIDAY_WINDOW_DAYS)
            holiday_dates = get_holiday_dates_in_window(
                self._session, scheduled_date, window_end
            )
            important_until = compute_important_until(
                scheduled_at, holiday_dates, window_days=2
            )

        announcement = Announcement(
            title=title,
            message_text=body_text,
            scheduled_at=scheduled_at,
            importance=importance,
            category_code=category_code,
            audience_group_codes=audience_group_codes,
            composer_user_id=composer_user_id,
            composer_role_code=composer_role_code,
            source_type="manual",
            source_ref_id=None,
            important_until=important_until,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        announcement = self._repo.create(announcement)

        write_audit_row(
            actor_user_id=actor_id,
            actor_role_code=composer_role_code,
            action="create",
            resource="announcement",
            resource_id=str(announcement.id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=None,
            after=audit_snapshot(announcement),
            session=self._session,
        )
        log.info(
            "announcement_created",
            announcement_id=str(announcement.id),
            composer=str(composer_user_id),
            category=category_code,
        )
        return announcement

    def withdraw_announcement(
        self,
        *,
        announcement_id: UUID,
        actor_id: UUID,
    ) -> Announcement:
        """Withdraw (soft-delete) an announcement.

        Only the composer may withdraw their own announcement.
        Auto-announcements (source_type="auto") cannot be withdrawn.
        Already-withdrawn (is_deleted=True) announcements raise an error.

        Deviation from spec: uses is_deleted=True (repo.withdraw) instead of
        a hypothetical withdrawn_at field — that field does not exist on the model.
        """
        # Bypass the is_deleted filter to detect double-withdraw attempts
        row = self._session.get(Announcement, announcement_id)
        if row is None:
            raise AnnouncementNotFoundError("Announcement not found.")
        if row.is_deleted:
            raise AnnouncementWithdrawalNotAllowedError("Already withdrawn.")
        if row.source_type == "auto":
            raise AnnouncementWithdrawalNotAllowedError(
                "Auto-announcements cannot be withdrawn manually."
            )
        if row.composer_user_id != actor_id:
            raise AnnouncementWithdrawalNotAllowedError(
                "Only the composer can withdraw their own announcement."
            )

        before_snap = audit_snapshot(row)
        announcement = self._repo.withdraw(announcement_id, actor_id)

        write_audit_row(
            actor_user_id=actor_id,
            actor_role_code=None,
            action="withdraw",
            resource="announcement",
            resource_id=str(announcement_id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=before_snap,
            after=audit_snapshot(announcement),
            session=self._session,
        )
        log.info(
            "announcement_withdrawn",
            announcement_id=str(announcement_id),
            actor=str(actor_id),
        )
        return announcement

    def list_for_browse(
        self,
        *,
        viewer_user_id: UUID,
        tab: str,
        offset: int = 0,
        limit: int = 20,
        importance_filter: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[Announcement], int]:
        """Return paginated announcements for the browse page.

        tab="sent": composer's own announcements (including withdrawn).
        tab="received": announcements visible to the viewer via audience resolution,
            ordered by Phase 2 priority engine then created_at DESC.

        Pagination is done at service layer (load all candidates, then slice) since
        AnnouncementRepository has no list_paginated method.

        Deviation from spec: received tab uses Phase 2 sort_for_viewer (not fallback
        to created_at DESC). sort_for_viewer requires config_by_role dict from
        config_repo.list_enabled_ordered().
        """
        now = datetime.now(UTC)

        if tab == "sent":
            candidates = self._repo.list_by_composer(
                viewer_user_id, include_withdrawn=True
            )
        else:
            # Received: lazy audience resolution via AudienceResolver
            active_groups = self._audience_repo.list_active()
            viewer_group_codes = self._resolver.groups_user_belongs_to(
                viewer_user_id, active_groups, self._session
            )
            # list_visible_to_user already excludes withdrawn (is_deleted) rows
            candidates = self._repo.list_visible_to_user(
                viewer_user_id,
                viewer_group_codes,
                now,
            )
            # Apply Phase 2 priority engine
            enabled_configs = self._config_repo.list_enabled_ordered()
            config_by_role = {c.role_code: c for c in enabled_configs}
            candidates = sort_for_viewer(candidates, config_by_role, now)

        # Apply optional filters
        if importance_filter is not None:
            candidates = [a for a in candidates if a.importance == importance_filter]
        if date_from is not None:
            candidates = [
                a for a in candidates
                if a.scheduled_at.date() >= date_from
            ]
        if date_to is not None:
            candidates = [
                a for a in candidates
                if a.scheduled_at.date() <= date_to
            ]

        total = len(candidates)
        page = candidates[offset: offset + limit]
        return page, total

    def get_by_id(
        self,
        *,
        announcement_id: UUID,
        viewer_user_id: UUID,
    ) -> Announcement:
        """Return the announcement if visible to viewer; raise NotFoundError otherwise.

        Visibility rules:
        - Composer can see their own announcement even if withdrawn.
        - Other viewers must be in the resolved audience and the announcement
          must not be withdrawn (is_deleted=False).
        - Non-recipients receive NotFoundError (existence is not leaked).
        """
        # Bypass is_deleted filter to allow composer to see their own withdrawal
        row = self._session.get(Announcement, announcement_id)
        if row is None:
            raise AnnouncementNotFoundError("Announcement not found.")

        # Composer can always see their own
        if row.composer_user_id == viewer_user_id:
            return row

        # Non-composer cannot see withdrawn announcements
        if row.is_deleted:
            raise AnnouncementNotFoundError("Announcement not found.")

        # Non-composer must be in the audience
        active_groups = self._audience_repo.list_active()
        groups_by_code = {g.code: g for g in active_groups}
        if not self._resolver.user_can_see(
            viewer_user_id, row, groups_by_code, self._session
        ):
            raise AnnouncementNotFoundError("Announcement not found.")

        return row

    # ── Private helpers ───────────────────────────────────────────────────────

    def _check_composer_eligible(self, user_id: UUID) -> None:
        """Raise AnnouncementComposerNotEligibleError if the user holds no
        active role that appears in the enabled announcement_composer_configs.
        """
        enabled_configs = self._config_repo.list_enabled_ordered()
        if not enabled_configs:
            raise AnnouncementComposerNotEligibleError(
                "No composer roles are currently configured."
            )
        eligible_role_codes = {c.role_code for c in enabled_configs}

        # Check if user has any UserRole whose Role.code is in eligible_role_codes
        stmt = (
            select(UserRole)
            .join(Role, UserRole.role_id == Role.id)  # type: ignore[arg-type]
            .where(
                UserRole.user_id == user_id,
                Role.code.in_(eligible_role_codes),  # type: ignore[arg-type]
                Role.is_deleted == False,  # noqa: E712
            )
        )
        match = self._session.exec(stmt).first()
        if match is None:
            raise AnnouncementComposerNotEligibleError(
                "You are not configured as an announcement composer."
            )
