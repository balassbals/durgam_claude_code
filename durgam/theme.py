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
    # Standard action colors (Issues 6+7 — established at M2)
    "--color-destructive": "#A93226",  # dark red — destructive actions (WCAG AA on ivory)
    "--color-success-bg": "rgba(34,139,34,0.07)",  # success notification background
    "--color-success-border": "#228B22",            # success notification border
    "--color-warning-bg": "rgba(183,110,0,0.08)",  # warning notification background
    "--color-warning-border": "#C75B12",            # warning notification border (saffron)
    "--color-error-bg": "rgba(169,50,38,0.07)",    # error notification background
    "--color-error-border": "#A93226",              # error notification border
    "--color-info-bg": "rgba(31,58,110,0.06)",     # info notification background
    "--color-info-border": "#1F3A6E",               # info notification border (indigo)
    # Fonts — §17.3 placeholders; replace with licensed typeface when approved
    "--font-sans": "system-ui, sans-serif",
    "--font-serif": "Georgia, serif",
}


def apply_theme() -> dict[Any, Any]:
    """Return a Reflex-compatible style dict that injects CSS variables onto body."""
    return dict(TOKENS)
