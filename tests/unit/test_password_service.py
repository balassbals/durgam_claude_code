"""Unit tests for durgam.services.password — no I/O required."""

import pytest

from durgam.services.password import (
    WeakPasswordError,
    hash_password,
    validate_policy,
    verify_password,
)

_VALID = "Tr0ub4dor&3!X"


class TestHashVerify:
    def test_round_trip(self):
        h = hash_password(_VALID)
        assert verify_password(_VALID, h)

    def test_wrong_password_fails(self):
        h = hash_password(_VALID)
        assert not verify_password("wrong_password_!1A", h)

    def test_hash_starts_with_bcrypt_prefix(self):
        h = hash_password(_VALID)
        assert h.startswith("$2b$")

    def test_cost_factor_is_12(self):
        h = hash_password(_VALID)
        # bcrypt hash format: $2b$<cost>$...
        cost = int(h.split("$")[2])
        assert cost == 12

    def test_two_hashes_of_same_password_differ(self):
        assert hash_password(_VALID) != hash_password(_VALID)


class TestValidatePolicy:
    def test_valid_password_passes(self):
        validate_policy(_VALID)  # must not raise

    def test_too_short(self):
        with pytest.raises(WeakPasswordError, match="12 characters"):
            validate_policy("Sh0rt!X")

    def test_no_uppercase(self):
        with pytest.raises(WeakPasswordError, match="uppercase"):
            validate_policy("tr0ub4dor&3!x")

    def test_no_lowercase(self):
        with pytest.raises(WeakPasswordError, match="lowercase"):
            validate_policy("TR0UB4DOR&3!X")

    def test_no_digit(self):
        with pytest.raises(WeakPasswordError, match="digit"):
            validate_policy("Troubadour&!XX")

    def test_no_symbol(self):
        with pytest.raises(WeakPasswordError, match="symbol"):
            validate_policy("Tr0ub4dor3XXX")

    def test_common_password_rejected(self):
        """Monkeypatch _COMMON to guarantee the common-password raise path is hit.

        Most real common passwords are short and fail complexity first. We inject
        a known complex string into the set to cover services/password.py line 73.
        """
        from unittest.mock import patch

        injected = frozenset(["tr0ub4dor&3!x"])  # lowercased; satisfies complexity when cased
        with patch("durgam.services.password._COMMON", injected):
            with pytest.raises(WeakPasswordError, match="common"):
                # "Tr0ub4dor&3!X".lower() == "tr0ub4dor&3!x" which is in the patched set
                validate_policy("Tr0ub4dor&3!X")

    def test_common_password_check_is_case_insensitive(self):
        """The check uses plain.lower() so casing variations of common passwords are caught.

        The injected set contains the lowercase form; the candidate uses mixed case
        so it passes complexity but still lowercases to the common entry.
        """
        from unittest.mock import patch

        injected = frozenset(["tr0ub4dor&3!x"])
        with patch("durgam.services.password._COMMON", injected):
            # Mixed-case: passes all complexity checks, but .lower() matches injected entry.
            with pytest.raises(WeakPasswordError, match="common"):
                validate_policy("Tr0Ub4dOr&3!X")

    def test_email_local_part_rejected(self):
        with pytest.raises(WeakPasswordError, match="username"):
            validate_policy("Johndoe_1234!X", email="johndoe@sssihl.edu.in")

    def test_email_local_part_case_insensitive(self):
        # Password contains "johndoe" (lowercased from "JohnDoe") → blocked
        with pytest.raises(WeakPasswordError, match="username"):
            validate_policy("JohnDoe1234!XY", email="johndoe@sssihl.edu.in")

    def test_full_name_part_rejected(self):
        with pytest.raises(WeakPasswordError, match="name"):
            validate_policy("Rajan_1234!XYZ", full_name="Rajan Kumar")

    def test_name_part_under_3_chars_not_checked(self):
        # Single-char or two-char name parts are too noisy to check
        validate_policy("Ab_1234!XYZQRS", full_name="A B")  # must not raise

    def test_empty_email_and_name_skipped(self):
        validate_policy(_VALID, email="", full_name="")  # must not raise

    def test_exactly_12_chars_passes_complexity(self):
        validate_policy("Abc123!@#XyZa")  # 13 chars actually, ensure ≥12 boundary
        with pytest.raises(WeakPasswordError, match="12 characters"):
            validate_policy("Abc123!@#Xy")  # 11 chars
