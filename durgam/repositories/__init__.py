from .base import BaseRepository
from .campus import CampusRepository
from .centre import CentreRepository
from .config_singleton import ConfigSingletonRepository
from .course import CourseRepository
from .department import DepartmentRepository, SubDepartmentRepository
from .permission import PermissionRepository
from .program import ProgramRepository
from .role import RoleRepository
from .school import SchoolRepository
from .user_role import UserRoleRepository
from .vision_mission import VisionMissionRepository

__all__ = [
    "BaseRepository",
    "CampusRepository",
    "CentreRepository",
    "ConfigSingletonRepository",
    "CourseRepository",
    "DepartmentRepository",
    "PermissionRepository",
    "ProgramRepository",
    "RoleRepository",
    "SchoolRepository",
    "SubDepartmentRepository",
    "UserRoleRepository",
    "VisionMissionRepository",
]
