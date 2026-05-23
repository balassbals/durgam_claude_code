from .academic_year import AcademicYearRepository
from .base import BaseRepository
from .calendar_entry import CalendarEntryRepository
from .campus import CampusRepository
from .centre import CentreRepository
from .config_singleton import ConfigSingletonRepository
from .course import CourseRepository
from .department import DepartmentRepository, SubDepartmentRepository
from .holiday import HolidayRepository
from .permission import PermissionRepository
from .program import ProgramRepository
from .role import RoleRepository
from .school import SchoolRepository
from .student_category_count import StudentCategoryCountRepository
from .user_role import UserRoleRepository
from .vision_mission import VisionMissionRepository

__all__ = [
    "AcademicYearRepository",
    "BaseRepository",
    "CalendarEntryRepository",
    "CampusRepository",
    "CentreRepository",
    "ConfigSingletonRepository",
    "CourseRepository",
    "DepartmentRepository",
    "HolidayRepository",
    "PermissionRepository",
    "ProgramRepository",
    "RoleRepository",
    "SchoolRepository",
    "StudentCategoryCountRepository",
    "SubDepartmentRepository",
    "UserRoleRepository",
    "VisionMissionRepository",
]
