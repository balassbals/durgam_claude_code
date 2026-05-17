"""Unit tests for generate_temp_password() (§6.1, M2)."""

from durgam.services.password import generate_temp_password, validate_policy


class TestGenerateTempPassword:
    def test_passes_policy(self):
        """Generated password must pass validate_policy() without exceptions."""
        pw = generate_temp_password()
        validate_policy(pw)  # raises on failure

    def test_is_16_chars(self):
        pw = generate_temp_password()
        assert len(pw) == 16

    def test_successive_calls_differ(self):
        """Non-deterministic: two back-to-back calls must produce different values."""
        a = generate_temp_password()
        b = generate_temp_password()
        assert a != b

    def test_has_uppercase(self):
        pw = generate_temp_password()
        assert any(c.isupper() for c in pw)

    def test_has_lowercase(self):
        pw = generate_temp_password()
        assert any(c.islower() for c in pw)

    def test_has_digit(self):
        pw = generate_temp_password()
        assert any(c.isdigit() for c in pw)

    def test_has_symbol(self):
        pw = generate_temp_password()
        assert any(c in "!@#$%" for c in pw)
