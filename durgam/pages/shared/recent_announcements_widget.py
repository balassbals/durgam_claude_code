"""Recent Announcements dashboard widget (M9 Phase 7).

Renders top 3 received announcements for the current user. Read-only.
Click → navigate to /announcements.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import reflex as rx
import structlog

from durgam.db import open_session
from durgam.repositories.announcement import (
    AnnouncementCategoryRepository,
    AnnouncementComposerConfigRepository,
    AnnouncementRepository,
    AudienceGroupRepository,
)
from durgam.services.announcement import AnnouncementService
from durgam.states.base import BaseState

log = structlog.get_logger(__name__)


class RecentAnnouncementsState(BaseState):
    rows: list[dict[str, Any]] = []
    loading: bool = True
    has_announcements: bool = False

    async def load_widget_data(self) -> None:
        """Populate top-3 received for current user. Called via on_mount.

        No @require_role: this is an on_mount handler on a page already protected
        by rx.cond(AuthState.current_user_id != ""). Adding @require_role causes a
        PermissionDenied timing race (same issue as PermissionCheckState.load_widget_data).
        """
        if not self.current_user_id:
            self.rows = []
            self.has_announcements = False
            self.loading = False
            return

        try:
            with open_session() as session:
                svc = AnnouncementService(
                    repo=AnnouncementRepository(session),
                    config_repo=AnnouncementComposerConfigRepository(session),
                    category_repo=AnnouncementCategoryRepository(session),
                    audience_repo=AudienceGroupRepository(session),
                    session=session,
                )
                items, _ = svc.list_for_browse(
                    viewer_user_id=UUID(self.current_user_id),
                    tab="received",
                    offset=0,
                    limit=3,
                )
                self.rows = [
                    {
                        "id": str(a.id),
                        "title": a.title,
                        "importance": a.importance,
                        "composer_role_code": a.composer_role_code,
                        "scheduled_at_str": (
                            a.scheduled_at.strftime("%Y-%m-%d %H:%M")
                            if a.scheduled_at
                            else ""
                        ),
                    }
                    for a in items
                ]
                self.has_announcements = len(self.rows) > 0
        except Exception as e:
            log.exception("recent_announcements_widget.load_failed", error=str(e))
            self.rows = []
            self.has_announcements = False
        finally:
            self.loading = False


def _row(row: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.cond(
            row["importance"] == "very_important",
            rx.badge("Important", color_scheme="red", size="1"),
            rx.fragment(),
        ),
        rx.text(
            row["title"],
            font_weight="500",
            color="var(--color-body)",
            flex="1",
        ),
        rx.text(
            row["composer_role_code"],
            font_size="0.75rem",
            color="var(--color-muted)",
        ),
        rx.text(
            row["scheduled_at_str"],
            font_size="0.75rem",
            color="var(--color-muted)",
        ),
        align_items="center",
        gap="0.75rem",
        padding="0.5rem 0",
        border_bottom="1px solid var(--color-rule)",
        on_click=rx.redirect("/announcements"),
        cursor="pointer",
        width="100%",
        _hover={"background_color": "var(--color-surface-hover, #f0ede8)"},
    )


def recent_announcements_widget() -> rx.Component:
    """Render top 3 received announcements with link to /announcements."""
    return rx.box(
        rx.heading(
            "Recent Announcements",
            size="5",
            color="var(--color-primary)",
            font_family="var(--font-serif)",
            margin_bottom="0.75rem",
        ),
        rx.cond(
            RecentAnnouncementsState.loading,
            rx.text("Loading…", color="var(--color-muted)", font_size="0.875rem"),
            rx.cond(
                RecentAnnouncementsState.has_announcements,
                rx.vstack(
                    rx.foreach(RecentAnnouncementsState.rows, _row),
                    rx.link(
                        "View all announcements →",
                        href="/announcements",
                        color="var(--color-accent)",
                        font_size="0.875rem",
                        margin_top="0.5rem",
                    ),
                    align_items="stretch",
                    gap="0",
                ),
                rx.text(
                    "No announcements yet.",
                    color="var(--color-muted)",
                    font_style="italic",
                    font_size="0.875rem",
                ),
            ),
        ),
        padding="1rem",
        border="1px solid var(--color-rule)",
        border_radius="6px",
        background_color="var(--color-surface)",
        on_mount=RecentAnnouncementsState.load_widget_data,
        width="100%",
    )
