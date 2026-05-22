"""Shared exception types for org-core and config services."""


class OrgServiceError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class HardDeleteBlockedError(OrgServiceError):
    """Hard-delete blocked because dependent rows or audit history exist."""


class NotDeletableError(OrgServiceError):
    """Entity type does not support deletion (e.g. vision/mission — E-001)."""


class AcademicYearLockedError(OrgServiceError):
    """Write attempted on a locked academic year."""

    def __init__(self, message: str = "This academic year is locked. Edits are not permitted.") -> None:
        super().__init__(message)
