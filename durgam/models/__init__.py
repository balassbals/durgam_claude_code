from .announcement import (
    Announcement,
    AnnouncementCategory,
    AnnouncementComposerConfig,
    AudienceGroup,
)
from .auth import PasswordResetToken, UserSession
from .base import TimestampedSoftDelete
from .campus import Campus
from .centre import CentreOfExcellence
from .config_anchors import (
    AcademicYear,
    CalendarEntry,
    ClassCoordinatorAssignment,
    ClassTeacherAssignment,
    ClassTimingsConfig,
    Designation,
    DocumentTemplate,
    FacultyMentorAssignment,
    FacultyMentorConfirmation,
    Holiday,
    MentalHealthCounsellor,
    NonOwnedCourse,
    PurchaseCommitteeTemplate,
    PurchaseProcedureRule,
    RoleEmail,
    StudentCategoryCount,
    UGTimetable,
    NonRegularFaculty,
    WorkingDaysConfig,
)
from .course import Course
from .crosscutting import (
    ApprovalProcess,
    ApprovalRequest,
    ApprovalStageOption,
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
from .leave import (
    LateAttendanceMarker,
    LeaveBalance,
    LeaveCreditPolicy,
    LeaveCreditRun,
    LeaveRequest,
    LeaveSanctionAuthorityRule,
)
from .vision_mission import (
    DepartmentMission,
    DepartmentVisionMission,
    UniversityMission,
    UniversityVisionMission,
)
from .faculty import (
    Faculty,
    FacultyDocument,
    FacultyEducation,
    FacultyExperience,
    FacultyExpertise,
    FacultyWorkload,
)
from .faculty_request import FacultyRequest

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
    "ApprovalStageOption",
    # Config anchors (pre-M3)
    "AcademicYear",
    "Holiday",
    "RoleEmail",
    "DocumentTemplate",
    "StudentCategoryCount",
    # Config anchors (M3)
    "ClassTimingsConfig",
    "WorkingDaysConfig",
    # Config anchors (M4)
    "CalendarEntry",
    # Config anchors (M5b)
    "MentalHealthCounsellor",
    "FacultyMentorAssignment",
    "FacultyMentorConfirmation",
    "ClassTeacherAssignment",
    "ClassCoordinatorAssignment",
    "NonRegularFaculty",
    "NonOwnedCourse",
    "UGTimetable",
    "Designation",
    "PurchaseProcedureRule",
    "PurchaseCommitteeTemplate",
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
    # M10 Faculty
    "Faculty",
    "FacultyDocument",
    "FacultyEducation",
    "FacultyExperience",
    "FacultyExpertise",
    "FacultyWorkload",
    "FacultyRequest",
    # M9 Announcements
    "Announcement",
    "AnnouncementCategory",
    "AnnouncementComposerConfig",
    "AudienceGroup",
    # M8 Leave
    "LeaveBalance",
    "LeaveRequest",
    "LateAttendanceMarker",
    "LeaveSanctionAuthorityRule",
    # M8.1 Leave credit
    "LeaveCreditPolicy",
    "LeaveCreditRun",
]
