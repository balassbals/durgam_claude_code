"""M8 Phase 1: User employment fields + vacation-employee helper."""
from datetime import date

import pytest

from durgam.models.identity import User
from durgam.services.leave_rules import (
    VACATION_EMPLOYEE_TYPES,
    is_vacation_employee,
)


def test_user_employment_defaults() -> None:
    u = User(username="x", email="x@example.dev", password_hash="h")
    assert u.gender is None
    assert u.joined_on is None
    assert u.employee_type == "regular_non_teaching"


@pytest.mark.parametrize(
    "etype",
    [
        "regular_teaching",
        "regular_non_teaching",
        "honorary_teaching",
        "honorary_non_teaching",
        "superannuated_teaching",
        "superannuated_non_teaching",
        "visiting_fellow",
    ],
)
def test_employee_type_accepts_all_valid_values(etype: str) -> None:
    u = User(
        username="x",
        email="x@example.dev",
        password_hash="h",
        employee_type=etype,
    )
    assert u.employee_type == etype


def test_joined_on_accepts_date() -> None:
    u = User(
        username="x",
        email="x@example.dev",
        password_hash="h",
        joined_on=date(2018, 6, 1),
    )
    assert u.joined_on == date(2018, 6, 1)


def test_vacation_employee_helper_teaching_types() -> None:
    assert is_vacation_employee("regular_teaching") is True
    assert is_vacation_employee("honorary_teaching") is True
    assert is_vacation_employee("superannuated_teaching") is True


def test_vacation_employee_helper_non_vacation_types() -> None:
    assert is_vacation_employee("regular_non_teaching") is False
    assert is_vacation_employee("honorary_non_teaching") is False
    assert is_vacation_employee("superannuated_non_teaching") is False
    assert is_vacation_employee("visiting_fellow") is False


def test_vacation_employee_types_frozen() -> None:
    assert isinstance(VACATION_EMPLOYEE_TYPES, frozenset)
    assert "regular_teaching" in VACATION_EMPLOYEE_TYPES
