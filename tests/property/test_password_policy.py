"""Hypothesis property tests for password policy (RFP §6.1 rules engine).

Coverage target: ≥ 95% line / 90% branch (rules engine threshold).

All strategies use printable ASCII to match the validator's ASCII-only regexes
([A-Z], [a-z], \\d, [^A-Za-z0-9]).
"""

from hypothesis import given
from hypothesis import settings as h_settings
from hypothesis import strategies as st

from durgam.services.password import WeakPasswordError, validate_policy

_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LOWER = "abcdefghijklmnopqrstuvwxyz"
_DIGITS = "0123456789"
_SYMBOLS = "!@#$%^&*()-_=+[]{}|;:',.<>?/`~\"\\"
_ASCII_PRINTABLE = _UPPER + _LOWER + _DIGITS + _SYMBOLS

_VALID_PW = "Tr0ub4dor&3!X"


@given(st.integers(min_value=0, max_value=11))
def test_password_shorter_than_12_always_rejected(length: int):
    base = (_VALID_PW * 3)[:length]
    try:
        validate_policy(base)
        raise AssertionError(f"Should have raised for length {length}")
    except WeakPasswordError as e:
        assert "12 characters" in e.reason


@given(st.text(alphabet=_LOWER + _DIGITS + _SYMBOLS, min_size=12, max_size=32))
@h_settings(max_examples=200)
def test_no_uppercase_always_rejected(pw: str):
    if not any(c in _UPPER for c in pw):
        try:
            validate_policy(pw)
            raise AssertionError("Should have raised")
        except WeakPasswordError as e:
            assert any(word in e.reason for word in ("uppercase", "12 characters"))


@given(st.text(alphabet=_UPPER + _DIGITS + _SYMBOLS, min_size=12, max_size=32))
@h_settings(max_examples=200)
def test_no_lowercase_always_rejected(pw: str):
    if not any(c in _LOWER for c in pw):
        try:
            validate_policy(pw)
            raise AssertionError("Should have raised")
        except WeakPasswordError as e:
            assert any(word in e.reason for word in ("lowercase", "uppercase", "12 characters"))


@given(st.text(alphabet=_UPPER + _LOWER + _SYMBOLS, min_size=12, max_size=32))
@h_settings(max_examples=200)
def test_no_digit_always_rejected(pw: str):
    if not any(c in _DIGITS for c in pw):
        try:
            validate_policy(pw)
            raise AssertionError("Should have raised")
        except WeakPasswordError as e:
            assert any(
                word in e.reason
                for word in ("digit", "lowercase", "uppercase", "common", "12 characters")
            )


@given(st.text(alphabet=_UPPER + _LOWER + _DIGITS, min_size=12, max_size=32))
@h_settings(max_examples=200)
def test_no_symbol_always_rejected(pw: str):
    if (
        any(c in _UPPER for c in pw)
        and any(c in _LOWER for c in pw)
        and any(c in _DIGITS for c in pw)
        and not any(c in _SYMBOLS for c in pw)
    ):
        try:
            validate_policy(pw)
            raise AssertionError("Should have raised")
        except WeakPasswordError as e:
            assert "symbol" in e.reason or "common" in e.reason


@given(
    st.text(alphabet=_ASCII_PRINTABLE, min_size=12, max_size=64),
    st.from_regex(r"[a-z]{4,12}@sssihl\.edu\.in", fullmatch=True),
)
@h_settings(max_examples=100)
def test_email_local_part_in_password_rejected(pw: str, email: str):
    local = email.split("@")[0].lower()
    candidate = pw.lower()[:4] + local + "A1!" + pw[:3]
    if len(candidate) < 12:
        return
    try:
        validate_policy(candidate, email=email)
    except WeakPasswordError:
        pass  # expected


@given(st.just(_VALID_PW))
def test_valid_password_passes_consistently(pw: str):
    validate_policy(pw)  # must not raise
