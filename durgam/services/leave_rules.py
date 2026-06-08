"""Pure-Python leave rules engine.

Phase 1 stub: only the vacation-employee helper is implemented.
The full rules engine (compute_leave_days, check_balance, ...) lands in Phase 3.
"""
from __future__ import annotations


VACATION_EMPLOYEE_TYPES: frozenset[str] = frozenset({
    "regular_teaching",
    "honorary_teaching",
    "superannuated_teaching",
})


def is_vacation_employee(employee_type: str) -> bool:
    """Return True if the employee_type denotes a vacation employee.

    Vacation employees (teachers) get 10 days CL/year; non-vacation employees
    get 12 days CL/year per SSSIHL Statutes §XXVIII clause 14.
    """
    return employee_type in VACATION_EMPLOYEE_TYPES
