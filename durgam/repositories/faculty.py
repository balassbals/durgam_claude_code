"""Faculty module repositories (M10 Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, func, select

from durgam.models.faculty import (
    Faculty,
    FacultyDocument,
    FacultyEducation,
    FacultyExperience,
    FacultyExpertise,
    FacultyWorkload,
)


class FacultyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, faculty_id: UUID) -> Faculty | None:
        row = self._session.get(Faculty, faculty_id)
        if row is None or row.is_deleted:
            return None
        return row

    def get_by_user_id(self, user_id: UUID) -> Faculty | None:
        return self._session.exec(
            select(Faculty).where(
                Faculty.user_id == user_id,
                Faculty.is_deleted == False,  # noqa: E712
            )
        ).first()

    def get_by_employee_id(self, employee_id: str) -> Faculty | None:
        return self._session.exec(
            select(Faculty).where(
                Faculty.employee_id == employee_id,
                Faculty.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_by_department(self, department_id: UUID) -> list[Faculty]:
        return list(
            self._session.exec(
                select(Faculty).where(
                    Faculty.department_id == department_id,
                    Faculty.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def list_by_campus(self, campus_id: UUID) -> list[Faculty]:
        return list(
            self._session.exec(
                select(Faculty).where(
                    Faculty.campus_id == campus_id,
                    Faculty.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def list_all_active(self) -> list[Faculty]:
        return list(
            self._session.exec(
                select(Faculty).where(Faculty.is_deleted == False)  # noqa: E712
            ).all()
        )

    def list_paginated(
        self, offset: int = 0, limit: int = 50
    ) -> tuple[list[Faculty], int]:
        base = select(Faculty).where(Faculty.is_deleted == False)  # noqa: E712
        total = self._session.exec(
            select(func.count()).select_from(base.subquery())
        ).one()
        rows = list(
            self._session.exec(base.offset(offset).limit(limit)).all()
        )
        return rows, total

    def list_with_filters(
        self,
        *,
        search: str | None = None,
        department_codes: list[str] | None = None,
        campus_codes: list[str] | None = None,
        designations: list[str] | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple], int]:
        """Admin directory listing — joins designation/department/campus for
        display + filtering. Returns (rows, total). Each row is a tuple:
        (faculty_id, employee_id, title, first_name, middle_name, last_name,
         designation_name, department_code, campus_code). No PII fields.
        Active faculty only.
        """
        from durgam.models.campus import Campus
        from durgam.models.config_anchors import Designation
        from durgam.models.department import Department

        base = (
            select(
                Faculty.id,
                Faculty.employee_id,
                Faculty.title,
                Faculty.first_name,
                Faculty.middle_name,
                Faculty.last_name,
                Designation.name,
                Department.code,
                Campus.code,
            )
            .join(Designation, Designation.id == Faculty.designation_id)
            .join(Department, Department.id == Faculty.department_id)
            .join(Campus, Campus.id == Faculty.campus_id)
            .where(Faculty.is_deleted == False)  # noqa: E712
        )

        if search:
            pattern = f"%{search.strip().lower()}%"
            base = base.where(
                func.lower(
                    Faculty.first_name
                    + " "
                    + func.coalesce(Faculty.middle_name, "")
                    + " "
                    + Faculty.last_name
                ).like(pattern)
                | func.lower(Faculty.employee_id).like(pattern)
            )
        if department_codes:
            base = base.where(Department.code.in_(department_codes))
        if campus_codes:
            base = base.where(Campus.code.in_(campus_codes))
        if designations:
            base = base.where(Designation.name.in_(designations))

        total = self._session.exec(
            select(func.count()).select_from(base.subquery())
        ).one()
        ordered = base.order_by(Faculty.employee_id).offset(offset).limit(limit)
        rows = list(self._session.exec(ordered).all())
        return rows, total

    def distinct_filter_options(self) -> tuple[list[str], list[str], list[str]]:
        """Return (department_codes, campus_codes, designation_names) for active
        faculty, each sorted and deduplicated — used to populate filter dropdowns.
        """
        from durgam.models.campus import Campus
        from durgam.models.config_anchors import Designation
        from durgam.models.department import Department

        dept_rows = self._session.exec(
            select(Department.code)
            .join(Faculty, Faculty.department_id == Department.id)
            .where(Faculty.is_deleted == False)  # noqa: E712
            .distinct()
        ).all()
        campus_rows = self._session.exec(
            select(Campus.code)
            .join(Faculty, Faculty.campus_id == Campus.id)
            .where(Faculty.is_deleted == False)  # noqa: E712
            .distinct()
        ).all()
        desig_rows = self._session.exec(
            select(Designation.name)
            .join(Faculty, Faculty.designation_id == Designation.id)
            .where(Faculty.is_deleted == False)  # noqa: E712
            .distinct()
        ).all()
        return (
            sorted(dept_rows),
            sorted(campus_rows),
            sorted(desig_rows),
        )

    def create(self, faculty: Faculty) -> Faculty:
        self._session.add(faculty)
        self._session.flush()
        self._session.refresh(faculty)
        return faculty

    def update(self, faculty_id: UUID, fields: dict, actor_id: UUID) -> Faculty:
        row = self._session.get(Faculty, faculty_id)
        if row is None:
            raise ValueError(f"Faculty {faculty_id} not found")
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_by = actor_id
        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def soft_delete(self, faculty_id: UUID, actor_id: UUID) -> Faculty:
        row = self._session.get(Faculty, faculty_id)
        if row is None:
            raise ValueError(f"Faculty {faculty_id} not found")
        now = datetime.now(UTC)
        row.is_deleted = True
        row.deleted_at = now
        row.deleted_by = actor_id
        row.updated_at = now
        row.updated_by = actor_id
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row


class FacultyEducationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, edu_id: UUID) -> FacultyEducation | None:
        row = self._session.get(FacultyEducation, edu_id)
        if row is None or row.is_deleted:
            return None
        return row

    def list_by_faculty(self, faculty_id: UUID) -> list[FacultyEducation]:
        return list(
            self._session.exec(
                select(FacultyEducation).where(
                    FacultyEducation.faculty_id == faculty_id,
                    FacultyEducation.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def create(self, edu: FacultyEducation) -> FacultyEducation:
        self._session.add(edu)
        self._session.flush()
        self._session.refresh(edu)
        return edu

    def update(self, edu_id: UUID, fields: dict, actor_id: UUID) -> FacultyEducation:
        row = self._session.get(FacultyEducation, edu_id)
        if row is None:
            raise ValueError(f"FacultyEducation {edu_id} not found")
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_by = actor_id
        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def soft_delete(self, edu_id: UUID, actor_id: UUID) -> FacultyEducation:
        row = self._session.get(FacultyEducation, edu_id)
        if row is None:
            raise ValueError(f"FacultyEducation {edu_id} not found")
        now = datetime.now(UTC)
        row.is_deleted = True
        row.deleted_at = now
        row.deleted_by = actor_id
        row.updated_at = now
        row.updated_by = actor_id
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row


class FacultyExperienceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, exp_id: UUID) -> FacultyExperience | None:
        row = self._session.get(FacultyExperience, exp_id)
        if row is None or row.is_deleted:
            return None
        return row

    def list_by_faculty(self, faculty_id: UUID) -> list[FacultyExperience]:
        return list(
            self._session.exec(
                select(FacultyExperience).where(
                    FacultyExperience.faculty_id == faculty_id,
                    FacultyExperience.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def create(self, exp: FacultyExperience) -> FacultyExperience:
        self._session.add(exp)
        self._session.flush()
        self._session.refresh(exp)
        return exp

    def update(
        self, exp_id: UUID, fields: dict, actor_id: UUID
    ) -> FacultyExperience:
        row = self._session.get(FacultyExperience, exp_id)
        if row is None:
            raise ValueError(f"FacultyExperience {exp_id} not found")
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_by = actor_id
        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def soft_delete(self, exp_id: UUID, actor_id: UUID) -> FacultyExperience:
        row = self._session.get(FacultyExperience, exp_id)
        if row is None:
            raise ValueError(f"FacultyExperience {exp_id} not found")
        now = datetime.now(UTC)
        row.is_deleted = True
        row.deleted_at = now
        row.deleted_by = actor_id
        row.updated_at = now
        row.updated_by = actor_id
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row


class FacultyExpertiseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, exp_id: UUID) -> FacultyExpertise | None:
        row = self._session.get(FacultyExpertise, exp_id)
        if row is None or row.is_deleted:
            return None
        return row

    def list_by_faculty(self, faculty_id: UUID) -> list[FacultyExpertise]:
        return list(
            self._session.exec(
                select(FacultyExpertise).where(
                    FacultyExpertise.faculty_id == faculty_id,
                    FacultyExpertise.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def create(self, exp: FacultyExpertise) -> FacultyExpertise:
        self._session.add(exp)
        self._session.flush()
        self._session.refresh(exp)
        return exp

    def update(
        self, exp_id: UUID, fields: dict, actor_id: UUID
    ) -> FacultyExpertise:
        row = self._session.get(FacultyExpertise, exp_id)
        if row is None:
            raise ValueError(f"FacultyExpertise {exp_id} not found")
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_by = actor_id
        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def soft_delete(self, exp_id: UUID, actor_id: UUID) -> FacultyExpertise:
        row = self._session.get(FacultyExpertise, exp_id)
        if row is None:
            raise ValueError(f"FacultyExpertise {exp_id} not found")
        now = datetime.now(UTC)
        row.is_deleted = True
        row.deleted_at = now
        row.deleted_by = actor_id
        row.updated_at = now
        row.updated_by = actor_id
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row


class FacultyDocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, doc_id: UUID) -> FacultyDocument | None:
        row = self._session.get(FacultyDocument, doc_id)
        if row is None or row.is_deleted:
            return None
        return row

    def list_by_faculty(self, faculty_id: UUID) -> list[FacultyDocument]:
        return list(
            self._session.exec(
                select(FacultyDocument).where(
                    FacultyDocument.faculty_id == faculty_id,
                    FacultyDocument.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def list_by_faculty_and_type(
        self, faculty_id: UUID, doc_type: str
    ) -> list[FacultyDocument]:
        return list(
            self._session.exec(
                select(FacultyDocument).where(
                    FacultyDocument.faculty_id == faculty_id,
                    FacultyDocument.doc_type == doc_type,
                    FacultyDocument.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def create(self, doc: FacultyDocument) -> FacultyDocument:
        self._session.add(doc)
        self._session.flush()
        self._session.refresh(doc)
        return doc

    def update(self, doc_id: UUID, fields: dict, actor_id: UUID) -> FacultyDocument:
        row = self._session.get(FacultyDocument, doc_id)
        if row is None:
            raise ValueError(f"FacultyDocument {doc_id} not found")
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_by = actor_id
        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def soft_delete(self, doc_id: UUID, actor_id: UUID) -> FacultyDocument:
        row = self._session.get(FacultyDocument, doc_id)
        if row is None:
            raise ValueError(f"FacultyDocument {doc_id} not found")
        now = datetime.now(UTC)
        row.is_deleted = True
        row.deleted_at = now
        row.deleted_by = actor_id
        row.updated_at = now
        row.updated_by = actor_id
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row


class FacultyWorkloadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, wl_id: UUID) -> FacultyWorkload | None:
        row = self._session.get(FacultyWorkload, wl_id)
        if row is None or row.is_deleted:
            return None
        return row

    def list_by_faculty(self, faculty_id: UUID) -> list[FacultyWorkload]:
        return list(
            self._session.exec(
                select(FacultyWorkload).where(
                    FacultyWorkload.faculty_id == faculty_id,
                    FacultyWorkload.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def list_by_faculty_ay(
        self, faculty_id: UUID, academic_year_id: UUID
    ) -> list[FacultyWorkload]:
        return list(
            self._session.exec(
                select(FacultyWorkload).where(
                    FacultyWorkload.faculty_id == faculty_id,
                    FacultyWorkload.academic_year_id == academic_year_id,
                    FacultyWorkload.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def create(self, wl: FacultyWorkload) -> FacultyWorkload:
        self._session.add(wl)
        self._session.flush()
        self._session.refresh(wl)
        return wl

    def update(self, wl_id: UUID, fields: dict, actor_id: UUID) -> FacultyWorkload:
        row = self._session.get(FacultyWorkload, wl_id)
        if row is None:
            raise ValueError(f"FacultyWorkload {wl_id} not found")
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_by = actor_id
        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def upsert(
        self,
        faculty_id: UUID,
        academic_year_id: UUID,
        semester: str,
        entries: list[dict],
        notes: str | None,
        actor_id: UUID,
    ) -> FacultyWorkload:
        existing = self._session.exec(
            select(FacultyWorkload).where(
                FacultyWorkload.faculty_id == faculty_id,
                FacultyWorkload.academic_year_id == academic_year_id,
                FacultyWorkload.semester == semester,
                FacultyWorkload.is_deleted == False,  # noqa: E712
            )
        ).first()
        now = datetime.now(UTC)
        if existing is not None:
            existing.entries_json = entries
            existing.notes = notes
            existing.updated_by = actor_id
            existing.updated_at = now
            self._session.add(existing)
            self._session.flush()
            self._session.refresh(existing)
            return existing
        wl = FacultyWorkload(
            faculty_id=faculty_id,
            academic_year_id=academic_year_id,
            semester=semester,
            entries_json=entries,
            notes=notes,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(wl)
        self._session.flush()
        self._session.refresh(wl)
        return wl

    def soft_delete(self, wl_id: UUID, actor_id: UUID) -> FacultyWorkload:
        row = self._session.get(FacultyWorkload, wl_id)
        if row is None:
            raise ValueError(f"FacultyWorkload {wl_id} not found")
        now = datetime.now(UTC)
        row.is_deleted = True
        row.deleted_at = now
        row.deleted_by = actor_id
        row.updated_at = now
        row.updated_by = actor_id
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row
