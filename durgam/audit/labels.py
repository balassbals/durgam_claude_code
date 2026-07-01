"""Audit log resource label resolver — batch-resolves human-readable labels for UUIDs.

Resolvers are live-sourced (hit DB at call time, no caching). Soft-deleted entities
still resolve because they are forensically relevant in audit logs.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

ResolverFn = Callable[[list[str], Session], dict[str, str]]

_RESOURCE_RESOLVERS: dict[str, ResolverFn] = {}

_BASE_MODEL_USER_FIELDS = frozenset({"created_by", "updated_by", "deleted_by"})

FK_FIELDS: dict[str, dict[str, str]] = {
    "department":                   {"school_id": "school", "main_campus_id": "campus"},
    "course":                       {"program_id": "program", "department_id": "department"},
    "centre":                       {"campus_id": "campus"},
    "holiday":                      {"academic_year_id": "academic_year"},
    "calendar_entry":               {"academic_year_id": "academic_year", "owner_user_id": "user"},
    "mental_health_counsellor":     {"academic_year_id": "academic_year", "campus_id": "campus"},
    "faculty_mentor_assignment":    {"academic_year_id": "academic_year", "campus_id": "campus"},
    "class_teacher_assignment":     {"academic_year_id": "academic_year", "department_id": "department"},
    "non_regular_faculty":          {"department_id": "department", "approved_by_user_id": "user"},
    "non_owned_course":             {"academic_year_id": "academic_year"},
    "ug_timetable":                 {"academic_year_id": "academic_year"},
    "student_category_count":       {"academic_year_id": "academic_year"},
    "letterhead_asset":             {"file_id": "file_asset"},
    "template_asset":               {"file_id": "file_asset"},
    "department_vision_mission":    {"department_id": "department"},
}


def register_resolver(resource: str) -> Callable[[ResolverFn], ResolverFn]:
    def decorator(fn: ResolverFn) -> ResolverFn:
        _RESOURCE_RESOLVERS[resource] = fn
        return fn
    return decorator


def _parse_uuids(id_strings: list[str]) -> list[UUID]:
    result: list[UUID] = []
    for s in id_strings:
        try:
            result.append(UUID(s))
        except (ValueError, AttributeError):
            continue
    return result


def _is_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def _simple_resolver(
    model_class: Any,
    label_fn: Callable[[Any], str],
) -> ResolverFn:
    def resolver(ids: list[str], session: Session) -> dict[str, str]:
        uuids = _parse_uuids(ids)
        if not uuids:
            return {}
        stmt = select(model_class).where(model_class.id.in_(uuids))
        rows = session.exec(stmt).all()
        return {str(row.id): label_fn(row) for row in rows}
    return resolver


# ── Simple resolvers ─────────────────────────────────────────────────────────


@register_resolver("user")
def _resolve_user(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.identity import User
    return _simple_resolver(
        User,
        lambda u: f"{u.username} — {u.full_name}" if u.full_name else u.username,
    )(ids, session)


@register_resolver("role")
def _resolve_role(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.identity import Role
    return _simple_resolver(Role, lambda r: r.code)(ids, session)


@register_resolver("campus")
def _resolve_campus(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.campus import Campus
    return _simple_resolver(Campus, lambda c: f"{c.code} — {c.name}")(ids, session)


@register_resolver("school")
def _resolve_school(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.school import School
    return _simple_resolver(School, lambda s: f"{s.code} — {s.name}")(ids, session)


@register_resolver("department")
def _resolve_department(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.department import Department
    return _simple_resolver(Department, lambda d: f"{d.code} — {d.name}")(ids, session)


@register_resolver("centre")
def _resolve_centre(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.centre import CentreOfExcellence
    return _simple_resolver(CentreOfExcellence, lambda c: f"{c.code} — {c.name}")(ids, session)


@register_resolver("course")
def _resolve_course(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.course import Course
    return _simple_resolver(Course, lambda c: f"{c.code} — {c.name}")(ids, session)


@register_resolver("academic_year")
def _resolve_academic_year(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import AcademicYear
    return _simple_resolver(AcademicYear, lambda a: a.code)(ids, session)


@register_resolver("holiday")
def _resolve_holiday(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import Holiday
    return _simple_resolver(Holiday, lambda h: f"{h.name} ({h.holiday_date})")(ids, session)


@register_resolver("calendar_entry")
def _resolve_calendar_entry(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import CalendarEntry
    return _simple_resolver(CalendarEntry, lambda e: e.title)(ids, session)


@register_resolver("designation")
def _resolve_designation(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import Designation
    return _simple_resolver(Designation, lambda d: f"{d.code} — {d.name}")(ids, session)


@register_resolver("approval_process")
def _resolve_approval_process(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.crosscutting import ApprovalProcess
    return _simple_resolver(ApprovalProcess, lambda a: f"{a.code} — {a.title}")(ids, session)


@register_resolver("role_email")
def _resolve_role_email(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import RoleEmail
    return _simple_resolver(RoleEmail, lambda r: f"{r.role_code}: {r.email}")(ids, session)


@register_resolver("mental_health_counsellor")
def _resolve_mhc(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import MentalHealthCounsellor
    return _simple_resolver(MentalHealthCounsellor, lambda m: m.name)(ids, session)


@register_resolver("faculty_mentor_assignment")
def _resolve_fma(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import FacultyMentorAssignment
    return _simple_resolver(
        FacultyMentorAssignment,
        lambda f: f"{f.faculty_id} → {f.student_id_placeholder}",
    )(ids, session)


@register_resolver("class_teacher_assignment")
def _resolve_cta(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import ClassTeacherAssignment
    return _simple_resolver(
        ClassTeacherAssignment,
        lambda c: f"{c.faculty_id} ({c.class_identifier})",
    )(ids, session)


@register_resolver("non_regular_faculty")
def _resolve_nrf(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import NonRegularFaculty
    return _simple_resolver(
        NonRegularFaculty, lambda n: f"{n.name} ({n.organization})",
    )(ids, session)


@register_resolver("non_owned_course")
def _resolve_noc(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import NonOwnedCourse
    return _simple_resolver(
        NonOwnedCourse, lambda n: f"{n.course_code} — {n.course_name}",
    )(ids, session)


@register_resolver("ug_timetable")
def _resolve_ugt(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import UGTimetable
    return _simple_resolver(
        UGTimetable,
        lambda u: f"{u.course_code} D{u.day_of_week}P{u.period_number}",
    )(ids, session)


@register_resolver("purchase_procedure_rule")
def _resolve_ppr(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import PurchaseProcedureRule
    return _simple_resolver(
        PurchaseProcedureRule, lambda p: f"{p.fund_source} T{p.tier}",
    )(ids, session)


@register_resolver("purchase_committee_template")
def _resolve_pct(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import PurchaseCommitteeTemplate
    return _simple_resolver(PurchaseCommitteeTemplate, lambda p: p.committee_type)(ids, session)


# ── Singleton resolvers ──────────────────────────────────────────────────────


@register_resolver("university_vision_mission")
def _resolve_uvm(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.vision_mission import UniversityVisionMission
    return _simple_resolver(
        UniversityVisionMission, lambda _: "(university singleton)",
    )(ids, session)


@register_resolver("class_timings_config")
def _resolve_ctc(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import ClassTimingsConfig
    return _simple_resolver(ClassTimingsConfig, lambda _: "(singleton)")(ids, session)


@register_resolver("working_days_config")
def _resolve_wdc(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import WorkingDaysConfig
    return _simple_resolver(WorkingDaysConfig, lambda _: "(singleton)")(ids, session)


# ── No-op resolver ───────────────────────────────────────────────────────────


@register_resolver("session")
def _resolve_session(ids: list[str], session: Session) -> dict[str, str]:
    return {}


# ── Custom join resolvers ────────────────────────────────────────────────────


@register_resolver("student_category_count")
def _resolve_scc(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import AcademicYear, StudentCategoryCount
    uuids = _parse_uuids(ids)
    if not uuids:
        return {}
    stmt = (
        select(StudentCategoryCount, AcademicYear)
        .join(AcademicYear, StudentCategoryCount.academic_year_id == AcademicYear.id)
        .where(StudentCategoryCount.id.in_(uuids))
    )
    result: dict[str, str] = {}
    for scc, ay in session.exec(stmt).all():
        result[str(scc.id)] = f"AY {ay.code}"
    return result


@register_resolver("department_vision_mission")
def _resolve_dvm(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.department import Department
    from durgam.models.vision_mission import DepartmentVisionMission
    uuids = _parse_uuids(ids)
    if not uuids:
        return {}
    stmt = (
        select(DepartmentVisionMission, Department)
        .join(Department, DepartmentVisionMission.department_id == Department.id)
        .where(DepartmentVisionMission.id.in_(uuids))
    )
    result: dict[str, str] = {}
    for dvm, dept in session.exec(stmt).all():
        result[str(dvm.id)] = f"{dept.code} — {dept.name}"
    return result


@register_resolver("letterhead_asset")
def _resolve_letterhead(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import DocumentTemplate
    uuids = _parse_uuids(ids)
    if not uuids:
        return {}
    stmt = select(DocumentTemplate).where(
        DocumentTemplate.id.in_(uuids),
        DocumentTemplate.purpose == "letterhead",
    )
    result: dict[str, str] = {}
    for row in session.exec(stmt).all():
        label = f"Letterhead ({row.role_code})" if row.role_code else "Letterhead"
        result[str(row.id)] = label
    return result


@register_resolver("template_asset")
def _resolve_template(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.config_anchors import DocumentTemplate
    uuids = _parse_uuids(ids)
    if not uuids:
        return {}
    stmt = select(DocumentTemplate).where(
        DocumentTemplate.id.in_(uuids),
        DocumentTemplate.purpose != "letterhead",
    )
    result: dict[str, str] = {}
    for row in session.exec(stmt).all():
        result[str(row.id)] = f"Template ({row.purpose})"
    return result


# ── FK-only resolvers (not audit resources themselves) ───────────────────────


@register_resolver("program")
def _resolve_program(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.program import Program
    return _simple_resolver(Program, lambda p: f"{p.code} — {p.name}")(ids, session)


@register_resolver("file_asset")
def _resolve_file_asset(ids: list[str], session: Session) -> dict[str, str]:
    from durgam.models.crosscutting import FileAsset
    return _simple_resolver(FileAsset, lambda f: f.original_name)(ids, session)


# ── Core function ────────────────────────────────────────────────────────────


def bulk_resolve_labels(
    rows: list[Any],
    session: Session,
) -> list[dict[str, Any]]:
    """Batch-resolve human-readable labels for all UUIDs in a set of AuditLog rows.

    Returns enriched row dicts with added keys:
    - actor_label, resource_label, actor_roles_resolved, diff_labels
    """
    needed: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        if row.actor_user_id is not None:
            needed["user"].add(str(row.actor_user_id))

        if row.resource_id is not None and _is_uuid(row.resource_id):
            if row.resource in _RESOURCE_RESOLVERS:
                needed[row.resource].add(row.resource_id)

        if row.diff_json:
            fk_map = FK_FIELDS.get(row.resource, {})
            for field_name, target_resource in fk_map.items():
                if field_name in row.diff_json:
                    diff_pair = row.diff_json[field_name]
                    if isinstance(diff_pair, list) and len(diff_pair) == 2:
                        for val in diff_pair:
                            if val is not None and _is_uuid(str(val)):
                                needed[target_resource].add(str(val))

            for field_name in _BASE_MODEL_USER_FIELDS:
                if field_name in row.diff_json:
                    diff_pair = row.diff_json[field_name]
                    if isinstance(diff_pair, list) and len(diff_pair) == 2:
                        for val in diff_pair:
                            if val is not None and _is_uuid(str(val)):
                                needed["user"].add(str(val))

        if row.actor_roles_json:
            for role_entry in row.actor_roles_json:
                scope_type = role_entry.get("scope_type")
                scope_id = role_entry.get("scope_id")
                if scope_type and scope_id and _is_uuid(str(scope_id)):
                    needed[scope_type].add(str(scope_id))

    labels: dict[str, str] = {}
    for resource_type, id_set in needed.items():
        resolver = _RESOURCE_RESOLVERS.get(resource_type)
        if resolver is None:
            continue
        resolved = resolver(list(id_set), session)
        for id_str, label in resolved.items():
            labels[f"{resource_type}:{id_str}"] = label

    enriched: list[dict[str, Any]] = []
    for row in rows:
        row_dict = row.model_dump()

        actor_label: str | None = None
        if row.actor_user_id is not None:
            actor_label = labels.get(f"user:{row.actor_user_id}")

        resource_label: str | None = None
        if row.resource_id is not None and _is_uuid(row.resource_id):
            resource_label = labels.get(f"{row.resource}:{row.resource_id}")

        actor_roles_resolved: list[dict[str, Any]] = []
        if row.actor_roles_json:
            for role_entry in row.actor_roles_json:
                scope_type = role_entry.get("scope_type")
                scope_id = role_entry.get("scope_id")
                if scope_type is None:
                    scope_label = "universitywide"
                elif scope_id:
                    scope_label = labels.get(
                        f"{scope_type}:{scope_id}", "<deleted>",
                    )
                else:
                    scope_label = "<deleted>"
                actor_roles_resolved.append({
                    "role_code": role_entry.get("role_code"),
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    "scope_label": scope_label,
                })

        diff_labels: dict[str, list[str | None]] = {}
        if row.diff_json:
            fk_map = FK_FIELDS.get(row.resource, {})
            all_fk_fields = dict(fk_map)
            for field_name in _BASE_MODEL_USER_FIELDS:
                if field_name in row.diff_json:
                    all_fk_fields[field_name] = "user"

            for field_name, target_resource in all_fk_fields.items():
                if field_name not in row.diff_json:
                    continue
                diff_pair = row.diff_json[field_name]
                if not isinstance(diff_pair, list) or len(diff_pair) != 2:
                    continue
                before_val, after_val = diff_pair
                before_label: str | None = None
                after_label: str | None = None
                if before_val is not None and _is_uuid(str(before_val)):
                    before_label = labels.get(f"{target_resource}:{before_val}")
                if after_val is not None and _is_uuid(str(after_val)):
                    after_label = labels.get(f"{target_resource}:{after_val}")
                diff_labels[field_name] = [before_label, after_label]

        row_dict["actor_label"] = actor_label
        row_dict["resource_label"] = resource_label
        row_dict["actor_roles_resolved"] = actor_roles_resolved
        row_dict["diff_labels"] = diff_labels
        enriched.append(row_dict)

    return enriched
