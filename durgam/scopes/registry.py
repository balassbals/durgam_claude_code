"""E-006 scope-type registry.

Centralises scope-type metadata so that UI pages (role-emails, letterheads)
derive scope-type dropdowns from a single source of truth. Adding a new scope
type here makes it available in all scope-type dropdowns without UI changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from sqlmodel import Session


@dataclass(frozen=True)
class ScopeTypeConfig:
    key: str
    label: str
    list_options: Callable[["Session"], list[dict[str, str]]]


def _list_campuses(session: "Session") -> list[dict[str, str]]:
    from durgam.repositories.campus import CampusRepository
    from durgam.services.campus import CampusService

    return [
        {"id": str(c.id), "label": f"{c.code} — {c.name}"}
        for c in CampusService(CampusRepository(session)).list()
    ]


def _list_departments(session: "Session") -> list[dict[str, str]]:
    from durgam.repositories.department import (
        DepartmentRepository,
        SubDepartmentRepository,
    )
    from durgam.services.department import DepartmentService

    return [
        {"id": str(d.id), "label": f"{d.code} — {d.name}"}
        for d in DepartmentService(
            dept_repo=DepartmentRepository(session),
            subdept_repo=SubDepartmentRepository(session),
        ).list()
    ]


def _list_schools(session: "Session") -> list[dict[str, str]]:
    from durgam.repositories.school import SchoolRepository
    from durgam.services.school import SchoolService

    return [
        {"id": str(s.id), "label": f"{s.code} — {s.name}"}
        for s in SchoolService(SchoolRepository(session)).list()
    ]


SCOPE_TYPE_REGISTRY: dict[str, ScopeTypeConfig] = {
    "campus": ScopeTypeConfig(key="campus", label="Campus", list_options=_list_campuses),
    "department": ScopeTypeConfig(key="department", label="Department", list_options=_list_departments),
    "school": ScopeTypeConfig(key="school", label="School", list_options=_list_schools),
}


def get_scope_type_keys() -> list[str]:
    """Return scope-type keys in display order."""
    return list(SCOPE_TYPE_REGISTRY.keys())


def get_scope_type_dropdown_options() -> list[dict[str, str]]:
    """Return options for a scope-type UI dropdown (value + label pairs)."""
    return [
        {"value": cfg.key, "label": cfg.label}
        for cfg in SCOPE_TYPE_REGISTRY.values()
    ]


def load_scope_objects(scope_type: str, session: "Session") -> list[dict[str, str]]:
    """Load dropdown options for a given scope type. Returns [] if scope_type is unknown."""
    cfg = SCOPE_TYPE_REGISTRY.get(scope_type)
    if cfg is None:
        return []
    return cfg.list_options(session)


def resolve_scope_label(scope_type: str, scope_id_str: str, session: "Session") -> str:
    """Resolve a scope_type + scope_id UUID to a human-readable label."""
    objects = load_scope_objects(scope_type, session)
    for obj in objects:
        if obj["id"] == scope_id_str:
            return obj["label"]
    return scope_id_str
