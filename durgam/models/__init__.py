from .auth import PasswordResetToken, UserSession
from .base import TimestampedSoftDelete
from .campus import Campus
from .centre import CentreOfExcellence
from .config_anchors import (
    AcademicYear,
    ClassTimingsConfig,
    Holiday,
    LetterheadAsset,
    RoleEmail,
    StudentCategoryCount,
    WorkingDaysConfig,
)
from .course import Course
from .crosscutting import (
    ApprovalProcess,
    ApprovalRequest,
    ApprovalStep,
    AuditLog,
    FileAsset,
    Notification,
)
from .department import Department, DepartmentCampus, SubDepartment, SubDepartmentCampus
from .identity import Permission, Role, RolePermission, User, UserRole
from .program import (
    Program,
    ProgramDepartment,
    ProgramExitLevel,
    ProgramOutcome,
    ProgramRegulation,
    ProgramScheme,
    ProgramSchemeCourse,
    ProgramSpecialisation,
)
from .school import School
from .vision_mission import (
    DepartmentMission,
    DepartmentVisionMission,
    UniversityMission,
    UniversityVisionMission,
)

__all__ = [
    # Base
    "TimestampedSoftDelete",
    # Identity
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "UserRole",
    # Cross-cutting
    "AuditLog",
    "FileAsset",
    "Notification",
    "ApprovalProcess",
    "ApprovalRequest",
    "ApprovalStep",
    # Config anchors (pre-M3)
    "AcademicYear",
    "Holiday",
    "RoleEmail",
    "LetterheadAsset",
    "StudentCategoryCount",
    # Config anchors (M3)
    "ClassTimingsConfig",
    "WorkingDaysConfig",
    # Auth sessions
    "UserSession",
    "PasswordResetToken",
    # M3 Organisational Core
    "Campus",
    "School",
    "Department",
    "DepartmentCampus",
    "SubDepartment",
    "SubDepartmentCampus",
    "CentreOfExcellence",
    "Program",
    "ProgramDepartment",
    "ProgramOutcome",
    "ProgramRegulation",
    "ProgramScheme",
    "ProgramSchemeCourse",
    "ProgramSpecialisation",
    "ProgramExitLevel",
    "Course",
    "UniversityVisionMission",
    "UniversityMission",
    "DepartmentVisionMission",
    "DepartmentMission",
]
