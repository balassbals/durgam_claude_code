"""Integration tests for announcement file attachment (M9 Phase 8b).

4 tests covering: non-composer rejection, missing upload_svc guard,
metadata links correct announcement, list_attachments returns empty when none.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import select

from durgam.models.announcement import (
    AnnouncementCategory,
    AudienceGroup,
)
from durgam.models.identity import User
from durgam.repositories.announcement import (
    AnnouncementCategoryRepository,
    AnnouncementComposerConfigRepository,
    AnnouncementRepository,
    AudienceGroupRepository,
)
from durgam.repositories.file_asset import FileAssetRepository
from durgam.services.announcement import AnnouncementError, AnnouncementService
from durgam.services.password import hash_password
from durgam.services.upload import UploadService
from durgam.storage.local import LocalFilesystemBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(session, *, suffix: str | None = None) -> User:
    tag = suffix or uuid4().hex[:8]
    u = User(
        username=f"att_{tag}",
        email=f"att_{tag}@test.local",
        full_name="Att User",
        password_hash=hash_password("Test_Dev1!XZ"),
        is_active=True,
    )
    session.add(u)
    session.flush()
    return u


def _category(session, code: str) -> AnnouncementCategory:
    existing = session.exec(
        select(AnnouncementCategory).where(
            AnnouncementCategory.code == code,
            AnnouncementCategory.is_deleted == False,  # noqa: E712
        )
    ).first()
    if existing:
        return existing
    cat = AnnouncementCategory(code=code, name=code, is_active=True)
    session.add(cat)
    session.flush()
    return cat


def _audience_group(session, code: str) -> AudienceGroup:
    existing = session.exec(
        select(AudienceGroup).where(
            AudienceGroup.code == code,
            AudienceGroup.is_deleted == False,  # noqa: E712
        )
    ).first()
    if existing:
        return existing
    ag = AudienceGroup(code=code, name=code, filter_json={}, is_active=True)
    session.add(ag)
    session.flush()
    return ag


def _bare_svc(session) -> AnnouncementService:
    """AnnouncementService without upload_svc — for testing the guard."""
    return AnnouncementService(
        repo=AnnouncementRepository(session),
        config_repo=AnnouncementComposerConfigRepository(session),
        category_repo=AnnouncementCategoryRepository(session),
        audience_repo=AudienceGroupRepository(session),
        session=session,
    )


def _full_svc(session, tmp_path) -> AnnouncementService:
    file_asset_repo = FileAssetRepository(session)
    upload_svc = UploadService(
        file_repo=file_asset_repo,
        backend=LocalFilesystemBackend(str(tmp_path)),
        allowed_mimes=frozenset({"application/pdf", "image/png", "image/jpeg"}),
        max_size_mb=2,
    )
    return AnnouncementService(
        repo=AnnouncementRepository(session),
        config_repo=AnnouncementComposerConfigRepository(session),
        category_repo=AnnouncementCategoryRepository(session),
        audience_repo=AudienceGroupRepository(session),
        session=session,
        upload_svc=upload_svc,
        file_asset_repo=file_asset_repo,
    )


def _make_announcement(session, composer_user_id):
    _category(session, "ATT_CAT")
    _audience_group(session, "ATT_AUD")
    svc = _bare_svc(session)
    return svc.create_auto_announcement(
        composer_user_id=composer_user_id,
        composer_role_code="SYSTEM",
        category_code="ATT_CAT",
        audience_group_codes=["ATT_AUD"],
        title="Attachment Isolation Test",
        message_text="Body text.",
        source_approval_request_id=None,
        actor_id=composer_user_id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAttachFileEdgeCases:
    def test_attach_rejects_non_composer(self, db_session, tmp_path) -> None:
        """attach_file_to_announcement raises AnnouncementError when the actor is not
        the composer of the announcement."""
        composer = _user(db_session, suffix="compa")
        stranger = _user(db_session, suffix="strnga")
        ann = _make_announcement(db_session, composer.id)

        svc = _full_svc(db_session, tmp_path)
        with pytest.raises(AnnouncementError, match="Only the composer"):
            svc.attach_file_to_announcement(
                announcement_id=ann.id,
                file_bytes=b"some bytes",
                original_name="test.pdf",
                mime_type="application/pdf",
                actor_id=stranger.id,  # not the composer
            )

    def test_attach_requires_upload_svc(self, db_session) -> None:
        """attach_file_to_announcement raises AnnouncementError when the service was
        constructed without an UploadService."""
        user = _user(db_session, suffix="noupl")
        ann = _make_announcement(db_session, user.id)

        svc = _bare_svc(db_session)  # no upload_svc
        with pytest.raises(AnnouncementError, match="UploadService"):
            svc.attach_file_to_announcement(
                announcement_id=ann.id,
                file_bytes=b"bytes",
                original_name="file.pdf",
                mime_type="application/pdf",
                actor_id=user.id,
            )

    def test_attach_metadata_links_to_correct_announcement_id(
        self, db_session, tmp_path
    ) -> None:
        """metadata_json['announcement_id'] on the created FileAsset must equal the
        announcement's id — not a different announcement's id."""
        user = _user(db_session, suffix="metad")
        ann_a = _make_announcement(db_session, user.id)
        ann_b = _make_announcement(db_session, user.id)

        svc = _full_svc(db_session, tmp_path)
        asset_a = svc.attach_file_to_announcement(
            announcement_id=ann_a.id,
            file_bytes=b"content for A",
            original_name="a.pdf",
            mime_type="application/pdf",
            actor_id=user.id,
        )

        assert asset_a.metadata_json["announcement_id"] == str(ann_a.id)
        assert asset_a.metadata_json["announcement_id"] != str(ann_b.id)

    def test_list_attachments_returns_empty_for_announcement_with_none(
        self, db_session
    ) -> None:
        """list_attachments returns an empty list for an announcement that has no
        attached files."""
        user = _user(db_session, suffix="noneatt")
        ann = _make_announcement(db_session, user.id)

        svc = _bare_svc(db_session)  # no upload_svc needed for list
        attachments = svc.list_attachments(ann.id)
        assert attachments == []
