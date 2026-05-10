"""Verify that every §15.1 colour token is present in theme.py with the correct hex value."""

import re
from pathlib import Path

from durgam.theme import TOKENS, apply_theme

# §15.1 verbatim token values
REQUIRED_TOKENS = {
    "--color-primary": "#1F3A6E",
    "--color-accent": "#C75B12",
    "--color-surface": "#FAF7F2",
    "--color-body": "#2C2C2C",
    "--color-muted": "#6B6B6B",
    "--color-rule": "#B89B6A",
}


def test_all_colour_tokens_present():
    for var, expected_hex in REQUIRED_TOKENS.items():
        assert var in TOKENS, f"Missing CSS variable: {var}"
        assert TOKENS[var] == expected_hex, f"{var}: expected {expected_hex!r}, got {TOKENS[var]!r}"


def test_apply_theme_returns_all_tokens():
    style = apply_theme()
    for var in REQUIRED_TOKENS:
        assert var in style, f"apply_theme() missing {var}"


def test_no_hardcoded_hex_in_component_files():
    """No file under durgam/pages/ or durgam/states/ should hardcode a §15.1 hex colour."""
    hex_pattern = re.compile(r"#[0-9A-Fa-f]{6}\b")
    allowed_in = {"theme.py"}  # only theme.py may hardcode hex values

    durgam_root = Path(__file__).parent.parent.parent / "durgam"
    violations: list[str] = []

    for path in durgam_root.rglob("*.py"):
        if path.name in allowed_in:
            continue
        source = path.read_text()
        for match in hex_pattern.finditer(source):
            hex_val = match.group(0).upper()
            if hex_val in {v.upper() for v in REQUIRED_TOKENS.values()}:
                violations.append(f"{path.relative_to(durgam_root)}: {hex_val}")

    assert not violations, "Hardcoded §15.1 colours found outside theme.py:\n" + "\n".join(
        violations
    )


def test_font_tokens_present():
    assert "--font-sans" in TOKENS
    assert "--font-serif" in TOKENS
