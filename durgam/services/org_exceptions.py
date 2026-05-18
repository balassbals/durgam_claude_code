"""Shared exception types for M3 org-core services."""


class OrgServiceError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class HardDeleteBlockedError(OrgServiceError):
    """Hard-delete blocked because dependent rows or audit history exist."""


class NotDeletableError(OrgServiceError):
    """Entity type does not support deletion (e.g. vision/mission — E-001)."""
