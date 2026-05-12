"""Password hashing and policy enforcement (RFP §6.1)."""

from __future__ import annotations

import re
from pathlib import Path

import bcrypt

_COMMON_PASSWORDS_PATH = (
    Path(__file__).parent.parent.parent / "scripts" / "data" / "common_passwords.txt"
)

_COMMON: frozenset[str] = frozenset(
    _COMMON_PASSWORDS_PATH.read_text(encoding="utf-8").splitlines()
)

_BCRYPT_ROUNDS = 12

_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"\d")
_SYMBOL = re.compile(r"[^A-Za-z0-9]")


class WeakPasswordError(ValueError):
    """Raised when a password fails the policy check."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def hash_password(plain: str) -> str:
    """Return a bcrypt hash (cost 12) of *plain*."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True iff *plain* matches *hashed*."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def validate_policy(
    plain: str,
    *,
    email: str = "",
    full_name: str = "",
) -> None:
    """Raise WeakPasswordError if *plain* violates the §6.1 password policy.

    Policy:
    - Minimum 12 characters.
    - At least one uppercase letter.
    - At least one lowercase letter.
    - At least one digit.
    - At least one symbol (any non-alphanumeric character).
    - Not in the top-10,000 common-password list.
    - Must not contain the email local-part or the user's full name
      (case-insensitive substring match).
    """
    if len(plain) < 12:
        raise WeakPasswordError("Password must be at least 12 characters.")
    if not _UPPER.search(plain):
        raise WeakPasswordError("Password must contain at least one uppercase letter.")
    if not _LOWER.search(plain):
        raise WeakPasswordError("Password must contain at least one lowercase letter.")
    if not _DIGIT.search(plain):
        raise WeakPasswordError("Password must contain at least one digit.")
    if not _SYMBOL.search(plain):
        raise WeakPasswordError("Password must contain at least one symbol.")
    if plain.lower() in _COMMON:
        raise WeakPasswordError("Password is too common. Choose a less predictable password.")
    lower = plain.lower()
    if email:
        local = email.split("@")[0].lower()
        if local and local in lower:
            raise WeakPasswordError("Password must not contain your username or email.")
    if full_name:
        for part in full_name.lower().split():
            if len(part) >= 3 and part in lower:
                raise WeakPasswordError("Password must not contain your name.")
