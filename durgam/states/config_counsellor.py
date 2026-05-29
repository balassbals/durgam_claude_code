"""CounsellorConfigState — AY+campus-scoped counsellor roster CRUD + DOCX export."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.repositories.campus import CampusRepository
from durgam.repositories.document_template import DocumentTemplateRepository
from durgam.repositories.file_asset import FileAssetRepository
from durgam.repositories.mental_health_counsellor import (
    MentalHealthCounsellorRepository,
)
from durgam.services.mental_health_counsellor import (
    CounsellorError,
    MentalHealthCounsellorService,
)
from durgam.services.org_exceptions import AcademicYearLockedError
from durgam.services.upload import UploadService
from durgam.states.base import BaseState
from durgam.storage import get_storage_backend


def _svc(session) -> MentalHealthCounsellorService:
    return MentalHealthCounsellorService(
        repo=MentalHealthCounsellorRepository(session),
    )


class CounsellorConfigState(BaseState):
    # AY selector
    ay_options: list[dict[str, str]] = []
    selected_ay_id: str = ""
    ay_is_locked: bool = False

    # Campus selector
    campus_options: list[dict[str, str]] = []
    selected_campus_id: str = ""

    # List
    counsellors: list[dict[str, str]] = []
    loading: bool = True

    # Form
    show_form: bool = False
    editing_id: str = ""
    form_name: str = ""
    form_qualification: str = ""
    form_specialisation: str = ""
    form_mode: str = "inhouse"
    form_start: str = ""
    form_end: str = ""
    form_phone: str = ""
    form_email: str = ""
    form_display_order: str = "0"

    # Confirmation dialog
    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_counsellors(self) -> None:
        guard = self._config_guard("mental_health_counsellor", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.counsellors = []
        self.show_form = False
        self.ay_options = []
        self.campus_options = []

        with open_session() as session:
            ay_repo = AcademicYearRepository(session)
            for ay in ay_repo.list_active():
                self.ay_options.append({
                    "value": str(ay.id),
                    "label": ay.code,
                    "is_locked": "1" if ay.is_locked else "0",
                })
            if self.ay_options and not self.selected_ay_id:
                self.selected_ay_id = self.ay_options[0]["value"]

            campus_repo = CampusRepository(session)
            for c in campus_repo.list_active():
                self.campus_options.append({
                    "value": str(c.id),
                    "label": f"{c.code} — {c.name}",
                })
            if self.campus_options and not self.selected_campus_id:
                self.selected_campus_id = self.campus_options[0]["value"]

            self._load_data(session)

        self._load_nav_entries()
        self.loading = False

    def _load_data(self, session) -> None:
        self.counsellors = []
        if not self.selected_ay_id or not self.selected_campus_id:
            self.ay_is_locked = False
            return
        ay_repo = AcademicYearRepository(session)
        ay = ay_repo.get_by_id(UUID(self.selected_ay_id))
        self.ay_is_locked = ay.is_locked if ay else False

        svc = _svc(session)
        for c in svc.list_by_ay_campus(
            UUID(self.selected_ay_id), UUID(self.selected_campus_id),
        ):
            self.counsellors.append({
                "id": str(c.id),
                "name": c.name,
                "qualification": c.qualification,
                "specialisation": c.specialisation,
                "mode": c.mode_of_appointment,
                "period": f"{c.appointment_start} — {c.appointment_end}",
                "phone": c.phone or "",
                "email": c.email or "",
                "display_order": str(c.display_order),
                "start": str(c.appointment_start),
                "end": str(c.appointment_end),
                "appt_file_id": str(c.appointment_letter_file_id) if c.appointment_letter_file_id else "",
                "qual_file_id": str(c.qualification_proof_file_id) if c.qualification_proof_file_id else "",
            })

    async def on_ay_change(self, value: str) -> None:
        self.selected_ay_id = value
        self.show_form = False
        self.flash = ""
        self.flash_type = "info"
        with open_session() as session:
            self._load_data(session)
        matched = [o for o in self.ay_options if o["value"] == value]
        self.ay_is_locked = bool(matched and matched[0]["is_locked"] == "1")

    async def on_campus_change(self, value: str) -> None:
        self.selected_campus_id = value
        self.show_form = False
        self.flash = ""
        self.flash_type = "info"
        with open_session() as session:
            self._load_data(session)

    # ── Form setters ──────────────────────────────────────────────────────────

    def set_form_name(self, v: str) -> None:
        self.form_name = v

    def set_form_qualification(self, v: str) -> None:
        self.form_qualification = v

    def set_form_specialisation(self, v: str) -> None:
        self.form_specialisation = v

    def set_form_mode(self, v: str) -> None:
        self.form_mode = v

    def set_form_start(self, v: str) -> None:
        self.form_start = v

    def set_form_end(self, v: str) -> None:
        self.form_end = v

    def set_form_phone(self, v: str) -> None:
        self.form_phone = v

    def set_form_email(self, v: str) -> None:
        self.form_email = v

    def set_form_display_order(self, v: str) -> None:
        self.form_display_order = v

    # ── Form open / cancel ────────────────────────────────────────────────────

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_name = ""
        self.form_qualification = ""
        self.form_specialisation = ""
        self.form_mode = "inhouse"
        self.form_start = ""
        self.form_end = ""
        self.form_phone = ""
        self.form_email = ""
        self.form_display_order = "0"
        self.show_form = True

    def open_edit(
        self,
        cid: str,
        name: str,
        qualification: str,
        specialisation: str,
        mode: str,
        start: str,
        end: str,
        phone: str,
        email: str,
        display_order: str,
    ):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = cid
        self.form_name = name
        self.form_qualification = qualification
        self.form_specialisation = specialisation
        self.form_mode = mode
        self.form_start = start
        self.form_end = end
        self.form_phone = phone
        self.form_email = email
        self.form_display_order = display_order
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    # ── Save (create / update) ────────────────────────────────────────────────

    @require_role(action="write", resource="mental_health_counsellor")
    @audit_action(action="write", resource="mental_health_counsellor")
    async def save_counsellor(self, form_data: dict) -> None:
        from datetime import date

        name = form_data.get("form_name", "").strip()
        qualification = form_data.get("form_qualification", "").strip()
        specialisation = form_data.get("form_specialisation", "").strip()
        mode = form_data.get("form_mode", "").strip()
        start_raw = form_data.get("form_start", "").strip()
        end_raw = form_data.get("form_end", "").strip()
        phone = form_data.get("form_phone", "").strip() or None
        email_val = form_data.get("form_email", "").strip() or None
        display_order_raw = form_data.get("form_display_order", "0").strip()
        editing_id = form_data.get("editing_id", "").strip()

        if not start_raw or not end_raw:
            self.flash = "Start and end dates are required."
            self.flash_type = "error"
            return

        try:
            start_date = date.fromisoformat(start_raw)
            end_date = date.fromisoformat(end_raw)
        except ValueError:
            self.flash = "Invalid date format."
            self.flash_type = "error"
            return

        try:
            display_order = int(display_order_raw)
        except ValueError:
            display_order = 0

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.create(
                        academic_year_id=UUID(self.selected_ay_id),
                        campus_id=UUID(self.selected_campus_id),
                        name=name,
                        qualification=qualification,
                        specialisation=specialisation,
                        mode_of_appointment=mode,
                        appointment_start=start_date,
                        appointment_end=end_date,
                        actor_id=actor_id,
                        phone=phone,
                        email=email_val,
                        display_order=display_order,
                    )
                else:
                    record = svc.update(
                        UUID(editing_id),
                        {
                            "name": name,
                            "qualification": qualification,
                            "specialisation": specialisation,
                            "mode_of_appointment": mode,
                            "appointment_start": start_date,
                            "appointment_end": end_date,
                            "phone": phone,
                            "email": email_val,
                            "display_order": display_order,
                        },
                        actor_id,
                    )

                if self.staged_appt_letter:
                    upload_svc = UploadService(
                        file_repo=FileAssetRepository(session),
                        backend=get_storage_backend(),
                        allowed_mimes=frozenset({"application/pdf"}),
                        max_size_mb=2,
                    )
                    asset = upload_svc.upload(
                        self.staged_appt_letter,
                        self.staged_appt_letter_name,
                        "application/pdf",
                        actor_id,
                        purpose="counsellor_document",
                    )
                    if editing_id:
                        svc.update(UUID(editing_id), {"appointment_letter_file_id": asset.id}, actor_id)
                if self.staged_qual_proof:
                    upload_svc = UploadService(
                        file_repo=FileAssetRepository(session),
                        backend=get_storage_backend(),
                        allowed_mimes=frozenset({"application/pdf"}),
                        max_size_mb=2,
                    )
                    asset = upload_svc.upload(
                        self.staged_qual_proof,
                        self.staged_qual_proof_name,
                        "application/pdf",
                        actor_id,
                        purpose="counsellor_document",
                    )
                    if editing_id:
                        svc.update(UUID(editing_id), {"qualification_proof_file_id": asset.id}, actor_id)
                session.commit()
                self.staged_appt_letter = b""
                self.staged_appt_letter_name = ""
                self.staged_qual_proof = b""
                self.staged_qual_proof_name = ""
        except (CounsellorError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_counsellors()
        self.flash = "Counsellor saved."
        self.flash_type = "success"

    # ── Staged file uploads (M5a pattern — files staged in state, committed on Save)

    staged_appt_letter: bytes = b""
    staged_appt_letter_name: str = ""
    staged_qual_proof: bytes = b""
    staged_qual_proof_name: str = ""

    async def stage_appt_letter(self, files: list[rx.UploadFile]) -> None:
        if not files:
            return
        f = files[0]
        self.staged_appt_letter = await f.read()
        self.staged_appt_letter_name = f.filename or "appointment_letter.pdf"

    async def stage_qual_proof(self, files: list[rx.UploadFile]) -> None:
        if not files:
            return
        f = files[0]
        self.staged_qual_proof = await f.read()
        self.staged_qual_proof_name = f.filename or "qualification_proof.pdf"

    # ── Soft delete ───────────────────────────────────────────────────────────

    def open_deactivate_confirm(self, record_id: str, name: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate counsellor '{name}'?"
        self.confirm_body = "This will remove the counsellor from the roster."
        self.confirm_open = True

    @require_role(action="delete", resource="mental_health_counsellor")
    @audit_action(action="delete", resource="mental_health_counsellor")
    async def soft_delete_counsellor(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id),
                )
                session.commit()
        except (CounsellorError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""
            return
        self.confirm_open = False
        self.confirm_id = ""
        await self.load_counsellors()
        self.flash = "Counsellor deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""

    # ── DOCX export ───────────────────────────────────────────────────────────

    @require_role(action="read", resource="mental_health_counsellor")
    @audit_action(action="read", resource="mental_health_counsellor")
    async def export_roster(self) -> None:
        from durgam.docgen.merge import DocgenError, render_docx_template

        if not self.selected_ay_id or not self.selected_campus_id:
            self.flash = "Select an academic year and campus first."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                dt_repo = DocumentTemplateRepository(session)
                letterhead = dt_repo.get_letterhead_by_role("DIRECTOR")
                if letterhead is None:
                    self.flash = (
                        "No Director letterhead configured — upload one "
                        "under Config → Letterheads before exporting the roster."
                    )
                    self.flash_type = "error"
                    return

                file_asset_repo = FileAssetRepository(session)
                lh_asset = file_asset_repo.get_by_id(letterhead.file_id)
                if lh_asset is None:
                    self.flash = "Director letterhead file not found."
                    self.flash_type = "error"
                    return

                backend = get_storage_backend()
                template_bytes = backend.get(lh_asset.storage_key)

                svc = _svc(session)
                rows = svc.list_by_ay_campus(
                    UUID(self.selected_ay_id), UUID(self.selected_campus_id),
                )

                ay_label = ""
                for opt in self.ay_options:
                    if opt["value"] == self.selected_ay_id:
                        ay_label = opt["label"]
                        break
                campus_label = ""
                for opt in self.campus_options:
                    if opt["value"] == self.selected_campus_id:
                        campus_label = opt["label"]
                        break

                context = {
                    "academic_year": ay_label,
                    "campus": campus_label,
                    "counsellors": [
                        {
                            "sno": i + 1,
                            "name": r.name,
                            "qualification": r.qualification,
                            "specialisation": r.specialisation,
                            "mode_of_appointment": r.mode_of_appointment,
                            "appointment_start": str(r.appointment_start),
                            "appointment_end": str(r.appointment_end),
                            "phone": r.phone or "",
                            "email": r.email or "",
                        }
                        for i, r in enumerate(rows)
                    ],
                }
                rendered = render_docx_template(template_bytes, context)

                upload_svc = UploadService(
                    file_repo=file_asset_repo,
                    backend=backend,
                    allowed_mimes=frozenset({
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document",
                    }),
                    max_size_mb=10,
                )
                roster_filename = f"counsellor_roster_{ay_label}_{campus_label}.docx"

        except DocgenError as e:
            self.flash = f"Export failed: {e}"
            self.flash_type = "error"
            return
        except Exception as e:
            self.flash = f"Export failed: {e}"
            self.flash_type = "error"
            return

        self.flash = "Roster exported."
        self.flash_type = "success"
        return rx.download(data=rendered, filename=roster_filename)
