"""Puttaparthi Saffron–Indigo–Ivory theme tokens (§15.1).

All colour values are verbatim from the RFP. Font families are system
placeholders pending the §17.3 institutional-font sign-off.
"""

from typing import Any

TOKENS: dict[str, str] = {
    # Colours
    "--color-primary": "#1F3A6E",  # indigo — structural elements
    "--color-accent": "#C75B12",  # saffron — primary CTA / highlights
    "--color-surface": "#FAF7F2",  # ivory — page / card backgrounds
    "--color-body": "#2C2C2C",  # slate — body text
    "--color-muted": "#6B6B6B",  # muted — secondary / caption text
    "--color-rule": "#B89B6A",  # gold — decorative rules / dividers
    # Fonts — §17.3 placeholders; replace with licensed typeface when approved
    "--font-sans": "system-ui, sans-serif",
    "--font-serif": "Georgia, serif",
}


def apply_theme() -> dict[Any, Any]:
    """Return a Reflex-compatible style dict that injects CSS variables onto body."""
    return dict(TOKENS)
