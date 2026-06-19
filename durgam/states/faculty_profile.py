"""FacultyProfileState — self-service profile for /faculty/profile (M10 Phase P1).

Handles: load (readonly identity + editable sections), save_contact,
save_external_ids, save_phd, PhD confirm-clear dialog.
"""

from __future__ import annotations

import re
from uuid import UUID

import reflex as rx

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
    FacultyNotFoundError,
    FacultyService,
    InvalidPhdYearError,
    NotOwnerError,
)
from durgam.states.base import BaseState

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


class FacultyProfileState(BaseState):
    # Loading / error
    loading: bool = True
    error: str = ""
    success_message: str = ""
    has_faculty_record: bool = False
    faculty_id: str = ""
    flash: str = ""
    flash_type: str = "info"

    # Identity readonly (populated on load)
    employee_id: str = ""
    title: str = ""
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    designation_label: str = ""
    department_label: str = ""
    campus_label: str = ""
    joining_date_display: str = ""
    is_vacation_employee: bool = False

    # Contact editable
    phone: str = ""
    whatsapp: str = ""
    alt_phone: str = ""
    alt_email: str = ""
    emergency_contact_name: str = ""
    emergency_contact_relation: str = ""
    emergency_contact_phone: str = ""

    # External IDs editable
    orcid: str = ""
    linkedin: str = ""
    google_scholar: str = ""
    researchgate: str = ""

    # PhD editable
    is_phd: bool = False
    phd_thesis_title: str = ""
    phd_registration_number: str = ""
    phd_awarding_institution: str = ""
    phd_year_str: str = ""

    # PhD confirm-clear dialog
    show_clear_phd_confirm: bool = False

    # ── Setters (M7 rule: explicit setters for form-bound vars) ──────────────

    def set_phone(self, value: str) -> None:
        self.phone = value

    def set_whatsapp(self, value: str) -> None:
        self.whatsapp = value

    def set_alt_phone(self, value: str) -> None:
        self.alt_phone = value

    def set_alt_email(self, value: str) -> None:
        self.alt_email = value

    def set_emergency_contact_name(self, value: str) -> None:
        self.emergency_contact_name = value

    def set_emergency_contact_relation(self, value: str) -> None:
        self.emergency_contact_relation = value

    def set_emergency_contact_phone(self, value: str) -> None:
        self.emergency_contact_phone = value

    def set_orcid(self, value: str) -> None:
        self.orcid = value

    def set_linkedin(self, value: str) -> None:
        self.linkedin = value

    def set_google_scholar(self, value: str) -> None:
        self.google_scholar = value

    def set_researchgate(self, value: str) -> None:
        self.researchgate = value

    def set_phd_thesis_title(self, value: str) -> None:
        self.phd_thesis_title = value

    def set_phd_registration_number(self, value: str) -> None:
        self.phd_registration_number = value

    def set_phd_awarding_institution(self, value: str) -> None:
        self.phd_awarding_institution = value

    def set_phd_year_str(self, value: str) -> None:
        self.phd_year_str = value

    def dismiss_flash(self) -> None:
        self.flash = ""
        self.flash_type = "info"

    # ── PhD confirm-clear dialog ─────────────────────────────────────────────

    def set_is_phd_with_confirm(self, value: bool) -> None:
        if not value and self.is_phd:
            self.show_clear_phd_confirm = True
        else:
            self.is_phd = value

    def open_clear_phd_confirm(self) -> None:
        self.show_clear_phd_confirm = True

    async def confirm_clear_phd(self) -> None:
        self.is_phd = False
        self.phd_thesis_title = ""
        self.phd_registration_number = ""
        self.phd_awarding_institution = ""
        self.phd_year_str = ""
        self.show_clear_phd_confirm = False
        await self.save_phd()

    def cancel_clear_phd(self) -> None:
        self.is_phd = True
        self.show_clear_phd_confirm = False

    # ── On-load handler ──────────────────────────────────────────────────────

    async def load_profile(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.loading = True
        self.error = ""
        self.flash = ""
        self.flash_type = "info"
        self.has_faculty_record = False
        self.faculty_id = ""
        self._load_nav_entries()

        with open_session() as session:
            from durgam.models.campus import Campus
            from durgam.models.config_anchors import Designation
            from durgam.models.department import Department

            repo = FacultyRepository(session)
            faculty = repo.get_by_user_id(UUID(self.current_user_id))
            if faculty is None:
                self.loading = False
                self.has_faculty_record = False
                self.error = "You do not have a Faculty profile in this system."
                return

            self.has_faculty_record = True
            self.faculty_id = str(faculty.id)

            # Identity readonly
            self.employee_id = faculty.employee_id or ""
            self.title = faculty.title or ""
            self.first_name = faculty.first_name or ""
            self.middle_name = faculty.middle_name or ""
            self.last_name = faculty.last_name or ""
            self.is_vacation_employee = bool(faculty.is_vacation_employee)
            self.joining_date_display = (
                faculty.joining_date.isoformat() if faculty.joining_date else ""
            )

            desig = session.get(Designation, faculty.designation_id)
            self.designation_label = desig.name if desig else ""

            dept = session.get(Department, faculty.department_id)
            self.department_label = dept.name if dept else ""

            campus = session.get(Campus, faculty.campus_id)
            self.campus_label = campus.name if campus else ""

            # Contact
            self.phone = faculty.phone or ""
            self.whatsapp = faculty.whatsapp or ""
            self.alt_phone = faculty.alt_phone or ""
            self.alt_email = faculty.alt_email or ""
            self.emergency_contact_name = faculty.emergency_contact_name or ""
            self.emergency_contact_relation = faculty.emergency_contact_relation or ""
            self.emergency_contact_phone = faculty.emergency_contact_phone or ""

            # External IDs
            self.orcid = faculty.orcid or ""
            self.linkedin = faculty.linkedin or ""
            self.google_scholar = faculty.google_scholar or ""
            self.researchgate = faculty.researchgate or ""

            # PhD
            self.is_phd = bool(faculty.is_phd)
            self.phd_thesis_title = faculty.phd_thesis_title or ""
            self.phd_registration_number = faculty.phd_registration_number or ""
            self.phd_awarding_institution = faculty.phd_awarding_institution or ""
            self.phd_year_str = str(faculty.phd_year) if faculty.phd_year else ""

        self.loading = False

    # ── Save handlers ────────────────────────────────────────────────────────

    @require_role(action="write", resource="faculty", scope="own")
    @audit_action(action="write", resource="faculty")
    async def save_contact(self) -> None:
        if not self.phone.strip():
            self.flash = "Phone number is required."
            self.flash_type = "error"
            return
        if not self.emergency_contact_name.strip():
            self.flash = "Emergency contact name is required."
            self.flash_type = "error"
            return
        if not self.emergency_contact_relation.strip():
            self.flash = "Emergency contact relation is required."
            self.flash_type = "error"
            return
        if not self.emergency_contact_phone.strip():
            self.flash = "Emergency contact phone is required."
            self.flash_type = "error"
            return
        if self.alt_email.strip() and not _EMAIL_RE.match(self.alt_email.strip()):
            self.flash = "Alternate email address is not valid."
            self.flash_type = "error"
            return

        with open_session() as session:
            svc = _build_svc(session)
            before_snap = audit_snapshot(svc.get_faculty(UUID(self.faculty_id)))
            try:
                entity = svc.update_contact(
                    UUID(self.faculty_id),
                    phone=self.phone.strip(),
                    whatsapp=self.whatsapp.strip() or None,
                    alt_phone=self.alt_phone.strip() or None,
                    alt_email=self.alt_email.strip() or None,
                    emergency_contact_name=self.emergency_contact_name.strip(),
                    emergency_contact_relation=self.emergency_contact_relation.strip(),
                    emergency_contact_phone=self.emergency_contact_phone.strip(),
                    actor_id=UUID(self.current_user_id),
                )
                after_snap = audit_snapshot(entity)
                session.commit()
            except (FacultyNotFoundError, NotOwnerError) as exc:
                self.flash = str(exc)
                self.flash_type = "error"
                return
        self._set_audit(resource_id=self.faculty_id, before=before_snap, after=after_snap)
        self.flash = "Contact information saved."
        self.flash_type = "success"

    @require_role(action="write", resource="faculty", scope="own")
    @audit_action(action="write", resource="faculty")
    async def save_external_ids(self) -> None:
        with open_session() as session:
            svc = _build_svc(session)
            before_snap = audit_snapshot(svc.get_faculty(UUID(self.faculty_id)))
            try:
                entity = svc.update_external_ids(
                    UUID(self.faculty_id),
                    orcid=self.orcid.strip() or None,
                    linkedin=self.linkedin.strip() or None,
                    google_scholar=self.google_scholar.strip() or None,
                    researchgate=self.researchgate.strip() or None,
                    actor_id=UUID(self.current_user_id),
                )
                after_snap = audit_snapshot(entity)
                session.commit()
            except (FacultyNotFoundError, NotOwnerError) as exc:
                self.flash = str(exc)
                self.flash_type = "error"
                return
        self._set_audit(resource_id=self.faculty_id, before=before_snap, after=after_snap)
        self.flash = "External IDs saved."
        self.flash_type = "success"

    @require_role(action="write", resource="faculty", scope="own")
    @audit_action(action="write", resource="faculty")
    async def save_phd(self) -> None:
        phd_year: int | None = None
        if self.phd_year_str.strip():
            try:
                phd_year = int(self.phd_year_str.strip())
            except ValueError:
                self.flash = "PhD year must be a 4-digit number."
                self.flash_type = "error"
                return

        with open_session() as session:
            svc = _build_svc(session)
            before_snap = audit_snapshot(svc.get_faculty(UUID(self.faculty_id)))
            try:
                entity = svc.update_phd_section(
                    UUID(self.faculty_id),
                    is_phd=self.is_phd,
                    phd_thesis_title=self.phd_thesis_title.strip() or None,
                    phd_registration_number=self.phd_registration_number.strip() or None,
                    phd_awarding_institution=self.phd_awarding_institution.strip() or None,
                    phd_year=phd_year,
                    actor_id=UUID(self.current_user_id),
                )
                after_snap = audit_snapshot(entity)
                session.commit()
            except InvalidPhdYearError as exc:
                self.flash = str(exc)
                self.flash_type = "error"
                return
            except (FacultyNotFoundError, NotOwnerError) as exc:
                self.flash = str(exc)
                self.flash_type = "error"
                return
        self._set_audit(resource_id=self.faculty_id, before=before_snap, after=after_snap)
        self.flash = "PhD section saved."
        self.flash_type = "success"
