"""CourseConfigState — /admin/config/courses (placeholder; CRUD in Session 6)."""

from __future__ import annotations

from durgam.states.base import BaseState


class CourseConfigState(BaseState):
    async def load_courses(self) -> None:
        guard = self._config_guard("course", "write")
        if guard is not None:
            return guard
        self._load_nav_entries()
