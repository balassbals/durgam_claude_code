"""FacultyDocumentState — PDF document CRUD for /faculty/profile/documents (M10 Phase P4).

Mirrors FacultyEducationState (P3a) with the P3a.1/P3a.2 modal-close pattern.
Upload flow: handle_document_upload stashes the dropped PDF (base64) into transient
state; save_record commits it via FacultyService.upload_document. Download URLs use
DOWNLOAD_PREFIX (P2.3 learning) — never a bare /api/files path.
"""

from __future__ import annotations

import base64
from uuid import UUID

import reflex as rx

from durgam.api import DOWNLOAD_PREFIX
from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.faculty import (
    FacultyDocumentRepository,
    FacultyEducationRepository,
    FacultyExperienceRepository,
    FacultyExpertiseRepository,
    FacultyRepository,
    FacultyWorkloadRepository,
)
from durgam.services.faculty import (
    DocumentInvalidMimeError,
    DocumentNotFoundError,
    DocumentTooLargeError,
    FacultyNotFoundError,
    FacultyService,
    NotOwnerError,
)
from durgam.states.base import BaseState


def _resolve_or_redirect(state: BaseState):
    state._resolve_session()
    if not state.current_user_id:
        return rx.redirect("/login")
    return None


def _build_svc(session) -> FacultyService:
    return FacultyService(
        faculty_repo=FacultyRepository(session),
        education_repo=FacultyEducationRepository(session),
        experience_repo=FacultyExperienceRepository(session),
        expertise_repo=FacultyExpertiseRepository(session),
        document_repo=FacultyDocumentRepository(session),
        workload_repo=FacultyWorkloadRepository(session),
    )


class FacultyDocumentState(BaseState):
    loading: bool = True
    faculty_id: str = ""
    has_faculty_record: bool = False
    documents: list[dict] = []

    # Form state
    show_form: bool = False
    form_doc_id: str = ""
    form_document_type: str = ""
    form_description: str = ""

    # Staged-file state (transient — set by handle_document_upload)
    staged_file_b64: str = ""
    staged_file_name: str = ""
    staged_file_mime: str = ""
    has_staged_file: bool = False
    uploading: bool = False

    # Delete confirm
    show_delete_confirm: bool = False
    deleting_id: str = ""
    deleting_type: str = ""

    # ── Setters ──────────────────────────────────────────────────────────────

    def set_form_document_type(self, v: str) -> None:
        self.form_document_type = v

    def set_form_description(self, v: str) -> None:
        self.form_description = v

    # ── Modal open / close helpers ────────────────────────────────────────────

    def _clear_form(self) -> None:
        self.form_doc_id = ""
        self.form_document_type = ""
        self.form_description = ""
        self.staged_file_b64 = ""
        self.staged_file_name = ""
        self.staged_file_mime = ""
        self.has_staged_file = False
        self.uploading = False

    def open_create_modal(self) -> None:
        self._clear_form()
        self.show_form = True

    def open_edit_by_id(self, doc_id: str) -> None:
        self._clear_form()
        self.form_doc_id = doc_id
        for r in self.documents:
            if r["id"] == doc_id:
                self.form_document_type = r.get("document_type", "")
                self.form_description = r.get("description", "")
                break
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self._clear_form()

    def open_delete_confirm_by_id(self, doc_id: str) -> None:
        self.deleting_id = doc_id
        self.deleting_type = ""
        for r in self.documents:
            if r["id"] == doc_id:
                self.deleting_type = r.get("document_type", "")
                break
        self.show_delete_confirm = True

    def cancel_delete(self) -> None:
        self.show_delete_confirm = False
        self.deleting_id = ""
        self.deleting_type = ""

    # ── On-load ───────────────────────────────────────────────────────────────

    async def load_documents(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.loading = True
        self.documents = []
        self.has_faculty_record = False
        self.faculty_id = ""
        self._load_nav_entries()

        with open_session() as session:
            repo = FacultyRepository(session)
            faculty = repo.get_by_user_id(UUID(self.current_user_id))
            if faculty is None:
                self.loading = False
                self.has_faculty_record = False
                return

            self.has_faculty_record = True
            self.faculty_id = str(faculty.id)

            from durgam.models.crosscutting import FileAsset

            svc = _build_svc(session)
            doc_list = svc.list_documents(faculty.id)
            rows: list[dict] = []
            for d in doc_list:
                asset = session.get(FileAsset, d.file_asset_id)
                file_name = asset.original_name if asset is not None else "document.pdf"
                rows.append(
                    {
                        "id": str(d.id),
                        "document_type": d.doc_type,
                        "description": d.description or "",
                        "file_name": file_name,
                        # DOWNLOAD_PREFIX is "" with a same-port reverse proxy (prod),
                        # or the backend origin in dev (P2.3 learning). Never a bare path.
                        "download_url": (
                            DOWNLOAD_PREFIX + "/api/files/" + str(d.file_asset_id)
                        ),
                        "uploaded_at_str": d.created_at.date().isoformat(),
                    }
                )
            self.documents = rows

        self.loading = False

    # ── Upload (stash dropped file) ───────────────────────────────────────────

    async def handle_document_upload(
        self, files: list[rx.UploadFile]
    ) -> rx.event.EventSpec | None:
        if not files:
            return rx.toast.error("No file received.")
        self.uploading = True
        f = files[0]
        file_bytes = await f.read()
        self.staged_file_b64 = base64.b64encode(file_bytes).decode("ascii")
        self.staged_file_name = f.filename or "document.pdf"
        self.staged_file_mime = f.content_type or "application/pdf"
        self.has_staged_file = True
        self.uploading = False
        return rx.toast.success("File ready: " + self.staged_file_name)

    # ── Save (create or update) ───────────────────────────────────────────────

    @require_role(action="write", resource="faculty", scope="own")
    @audit_action(action="write", resource="faculty")
    async def save_document(self, form_data: dict) -> rx.event.EventSpec | None:
        document_type = form_data.get("form_document_type", "").strip()
        description = form_data.get("form_description", "").strip() or None
        editing_id = self.form_doc_id.strip()

        if not document_type:
            return rx.toast.error("Document type is required.")

        after_snap: dict = {}
        resource_id_for_audit: str = ""
        with open_session() as session:
            svc = _build_svc(session)
            try:
                if not editing_id:
                    if not self.has_staged_file:
                        return rx.toast.error("Please upload a PDF file first.")
                    file_bytes = base64.b64decode(self.staged_file_b64)
                    doc = svc.upload_document(
                        UUID(self.faculty_id),
                        document_type=document_type,
                        description=description,
                        file_bytes=file_bytes,
                        original_filename=self.staged_file_name,
                        mime_type=self.staged_file_mime,
                        actor_id=UUID(self.current_user_id),
                    )
                else:
                    doc = svc.update_document_metadata(
                        UUID(editing_id),
                        document_type=document_type,
                        description=description,
                        actor_id=UUID(self.current_user_id),
                    )
                after_snap = audit_snapshot(doc)
                resource_id_for_audit = str(doc.id)
                session.commit()
            except (
                DocumentNotFoundError,
                DocumentInvalidMimeError,
                DocumentTooLargeError,
                FacultyNotFoundError,
                NotOwnerError,
            ) as exc:
                return rx.toast.error(str(exc))

        self._set_audit(resource_id=resource_id_for_audit, after=after_snap)
        self.show_form = False
        self._clear_form()
        return [
            rx.toast.success("Document saved."),
            rx.call_script("window.location.reload()"),
        ]

    # ── Delete ────────────────────────────────────────────────────────────────

    @require_role(action="write", resource="faculty", scope="own")
    @audit_action(action="write", resource="faculty")
    async def confirm_delete(self) -> rx.event.EventSpec | None:
        if not self.deleting_id:
            return rx.toast.error("No record selected for deletion.")

        before_snap: dict = {}
        with open_session() as session:
            doc_repo = FacultyDocumentRepository(session)
            doc_before = doc_repo.get(UUID(self.deleting_id))
            if doc_before is None:
                return rx.toast.error("Document not found.")
            before_snap = audit_snapshot(doc_before)
            svc = _build_svc(session)
            try:
                svc.remove_document_and_file(
                    UUID(self.deleting_id), UUID(self.current_user_id)
                )
                session.commit()
            except (DocumentNotFoundError, NotOwnerError) as exc:
                return rx.toast.error(str(exc))

        self._set_audit(resource_id=self.deleting_id, before=before_snap)
        self.show_delete_confirm = False
        self.deleting_id = ""
        self.deleting_type = ""
        return [
            rx.toast.success("Document deleted."),
            rx.call_script("window.location.reload()"),
        ]
