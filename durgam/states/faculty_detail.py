"""FacultyDetailState — peer-view read-only faculty detail (M10 Phase 8A).

Reads faculty_id from the URL param and renders a Faculty's public profile:
identity + contact + external IDs + PhD + Education/Experience/Expertise.
NO PAN/Aadhaar (deferred per TD-084 + Q-PP.7), NO Documents (private).
"""

from __future__ import annotations

from uuid import UUID

from durgam.api import DOWNLOAD_PREFIX
from durgam.db import open_session
from durgam.repositories.faculty import (
    FacultyDocumentRepository,
    FacultyEducationRepository,
    FacultyExperienceRepository,
    FacultyExpertiseRepository,
    FacultyRepository,
    FacultyWorkloadRepository,
)
from durgam.services.faculty import FacultyNotFoundError, FacultyService
from durgam.states.base import BaseState


def _build_svc(session) -> FacultyService:
    return FacultyService(
        faculty_repo=FacultyRepository(session),
        education_repo=FacultyEducationRepository(session),
        experience_repo=FacultyExperienceRepository(session),
        expertise_repo=FacultyExpertiseRepository(session),
        document_repo=FacultyDocumentRepository(session),
        workload_repo=FacultyWorkloadRepository(session),
    )


class FacultyDetailState(BaseState):
    loading: bool = True
    not_found: bool = False
    faculty_id: str = ""

    # Identity
    name: str = ""
    employee_id: str = ""
    designation: str = ""
    department_code: str = ""
    campus_code: str = ""
    joining_date: str = ""
    employee_type: str = ""

    # Contact + external IDs
    phone: str = ""
    whatsapp: str = ""
    alt_phone: str = ""
    alt_email: str = ""
    orcid: str = ""
    linkedin: str = ""
    google_scholar: str = ""
    researchgate: str = ""

    # PhD
    is_phd: bool = False
    phd_thesis_title: str = ""
    phd_registration_number: str = ""
    phd_awarding_institution: str = ""
    phd_year: str = ""

    # Photo
    photo_url: str = ""
    initials: str = ""

    # Sub-entities
    education: list[dict] = []
    experience: list[dict] = []
    expertise: list[dict] = []

    async def load_detail(self):
        guard = self._config_guard("faculty", "read")
        if guard is not None:
            return guard

        self.loading = True
        self.not_found = False
        self._reset()

        fid = self.router.page.params.get("fid", "")
        self.faculty_id = fid
        if not fid:
            self.not_found = True
            self.loading = False
            return

        try:
            faculty_uuid = UUID(fid)
        except ValueError:
            self.not_found = True
            self.loading = False
            return

        with open_session() as session:
            svc = _build_svc(session)
            try:
                d = svc.get_faculty_detail(
                    faculty_uuid, viewer_user_id=UUID(self.current_user_id)
                )
            except FacultyNotFoundError:
                self.not_found = True
                self.loading = False
                return

            self.name = d["name"]
            self.employee_id = d["employee_id"]
            self.designation = d["designation"]
            self.department_code = d["department_code"]
            self.campus_code = d["campus_code"]
            self.joining_date = d["joining_date"]
            self.employee_type = d["employee_type"]
            self.phone = d["phone"]
            self.whatsapp = d["whatsapp"]
            self.alt_phone = d["alt_phone"]
            self.alt_email = d["alt_email"]
            self.orcid = d["orcid"]
            self.linkedin = d["linkedin"]
            self.google_scholar = d["google_scholar"]
            self.researchgate = d["researchgate"]

            phd = d["phd"]
            self.is_phd = phd is not None
            if phd is not None:
                self.phd_thesis_title = phd["thesis_title"]
                self.phd_registration_number = phd["registration_number"]
                self.phd_awarding_institution = phd["awarding_institution"]
                self.phd_year = phd["year"]

            pid = d["photo_file_id"]
            self.photo_url = (DOWNLOAD_PREFIX + "/api/files/" + pid) if pid else ""
            self.initials = "".join(
                part[0] for part in d["name"].split() if part
            )[:2].upper()

            self.education = d["education"]
            self.experience = d["experience"]
            self.expertise = d["expertise"]

        self.loading = False
        self._load_nav_entries()

    def _reset(self) -> None:
        self.name = ""
        self.employee_id = ""
        self.designation = ""
        self.department_code = ""
        self.campus_code = ""
        self.joining_date = ""
        self.employee_type = ""
        self.phone = ""
        self.whatsapp = ""
        self.alt_phone = ""
        self.alt_email = ""
        self.orcid = ""
        self.linkedin = ""
        self.google_scholar = ""
        self.researchgate = ""
        self.is_phd = False
        self.phd_thesis_title = ""
        self.phd_registration_number = ""
        self.phd_awarding_institution = ""
        self.phd_year = ""
        self.photo_url = ""
        self.initials = ""
        self.education = []
        self.experience = []
        self.expertise = []
