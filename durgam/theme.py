"""Puttaparthi Saffron-Indigo-Ivory design system tokens (§15.1, M10.5 Phase 1).

The RFP palette (indigo/saffron/ivory/gold/slate) is verbatim and unchanged.
This module expands it into a full token system: an explicit two-tone
surface system, a modular type scale, spacing/radius/elevation/motion
scales, and container widths — closing the gap between what the codebase
referenced via `var(--token, <fallback>)` and what was actually defined.
Every token below is deliberately palette-consistent; none reproduce the
accidental CSS fallback values found in the M10 close audit
(`#f5f0eb`, `#c0392b`, `#27ae60`, `#b45309`, `#d8d8de`).

Typefaces are self-hosted (see `assets/fonts/fonts.css`, loaded via
`rx.App(stylesheets=[...])` in `durgam/durgam.py`): Fraunces (display/serif)
and Inter (sans), both SIL Open Font License.
"""

from typing import Any

TOKENS: dict[str, str] = {
    # --- RFP palette (verbatim, unchanged) ---------------------------------
    "--color-primary": "#1F3A6E",  # indigo — structural elements
    "--color-accent": "#C75B12",  # saffron — primary CTA / highlights
    "--color-surface": "#FAF7F2",  # ivory — legacy surface token (kept)
    "--color-body": "#2C2C2C",  # slate — body text
    "--color-muted": "#6B6B6B",  # muted — secondary / caption text
    "--color-rule": "#B89B6A",  # gold — decorative rules / dividers
    "--color-destructive": "#A93226",  # dark red — destructive actions (WCAG AA on ivory)
    # --- Two-tone surface system (Phase 1 — was previously undefined) ------
    "--color-background": "#FAF7F2",  # ivory page background (same value as --color-surface)
    "--color-card-bg": "#FFFFFF",  # white cards sit on the ivory background
    "--color-surface-2": "#F6F1E9",  # nested/secondary panel surface, one step off background
    "--color-surface-hover": "#F1EAE0",  # hover tint for ivory rows/cards
    "--gray-2": "#F1EAE0",  # alternate-row background — kept in the warm family, not true grey
    "--radius-2": "var(--radius-md)",  # legacy alias — see radius scale below
    # --- Text tokens (aliases onto the slate body colour) ------------------
    "--color-text": "var(--color-body)",
    "--color-text-primary": "var(--color-body)",
    # --- Status colours — one definition per meaning, no accidental dupes --
    "--color-danger": "var(--color-destructive)",  # was a second, undefined red (#c0392b)
    "--color-success": "var(--color-success-border)",  # defined below; reused for consistency
    "--color-warning": "#B7650A",  # warm amber-brown — distinct from saffron accent, not #b45309
    "--color-warning-text": "#7A4508",  # darker warm shade for text on warning backgrounds
    # --- Standard action colours (Issues 6+7 — established at M2) ----------
    "--color-success-bg": "rgba(34,139,34,0.07)",
    "--color-success-border": "#228B22",
    "--color-warning-bg": "rgba(183,110,0,0.08)",
    "--color-warning-border": "#C75B12",
    "--color-error-bg": "rgba(169,50,38,0.07)",
    "--color-error-border": "#A93226",
    "--color-info-bg": "rgba(31,58,110,0.06)",
    "--color-info-border": "#1F3A6E",
    # --- Type scale — 7 steps, base body = 0.875rem/14px --------------------
    "--text-xs": "0.75rem",  # 12px — captions, timestamps, badges
    "--leading-xs": "1rem",
    "--text-sm": "0.8125rem",  # 13px — secondary text, table cells, helper text
    "--leading-sm": "1.125rem",
    "--text-base": "0.875rem",  # 14px — body text, inputs, buttons (default)
    "--leading-base": "1.25rem",
    "--text-lg": "1rem",  # 16px — card titles, emphasized labels
    "--leading-lg": "1.5rem",
    "--text-xl": "1.125rem",  # 18px — section headings
    "--leading-xl": "1.625rem",
    "--text-2xl": "1.5rem",  # 24px — page headings
    "--leading-2xl": "2rem",
    "--text-3xl": "2rem",  # 32px — hero / display headings
    "--leading-3xl": "2.5rem",
    # --- Font weights --------------------------------------------------------
    "--font-weight-regular": "400",
    "--font-weight-medium": "500",
    "--font-weight-semibold": "600",
    "--font-weight-bold": "700",
    # --- Spacing scale — base unit 0.25rem/4px --------------------------------
    "--space-1": "0.25rem",  # 4px
    "--space-2": "0.5rem",  # 8px
    "--space-3": "0.75rem",  # 12px
    "--space-4": "1rem",  # 16px
    "--space-5": "1.25rem",  # 20px
    "--space-6": "1.5rem",  # 24px
    "--space-8": "2rem",  # 32px — matches the current 129x-used 2rem padding
    "--space-10": "2.5rem",  # 40px
    "--space-12": "3rem",  # 48px
    "--space-16": "4rem",  # 64px
    # --- Radius scale ----------------------------------------------------------
    "--radius-sm": "4px",
    "--radius-md": "8px",
    "--radius-lg": "12px",
    "--radius-full": "999px",
    # --- Elevation — warm-tinted shadows (brown-black, not neutral grey) -----
    "--shadow-sm": "0 1px 2px rgba(44,28,16,0.06)",
    "--shadow-md": "0 2px 6px rgba(44,28,16,0.08)",
    "--shadow-lg": "0 6px 16px rgba(44,28,16,0.10)",
    "--shadow-xl": "0 16px 32px rgba(44,28,16,0.14)",
    # --- Motion ------------------------------------------------------------------
    "--motion-fast": "120ms",
    "--motion-base": "180ms",
    "--motion-slow": "280ms",
    "--ease-standard": "cubic-bezier(0.4, 0, 0.2, 1)",
    "--ease-emphasized": "cubic-bezier(0.2, 0, 0, 1)",
    # --- Container widths (widescreen target — M10.5 is desktop-only) ------------
    "--container-sm": "640px",  # forms, auth screens
    "--container-md": "1024px",
    "--container-lg": "1440px",  # standard content, widescreen default
    "--container-xl": "1760px",  # dense tables
    # --- Typefaces — self-hosted, see assets/fonts/fonts.css ---------------------
    "--font-sans": "'Inter', system-ui, -apple-system, sans-serif",
    "--font-serif": "'Fraunces', Georgia, serif",
    "--font-display": "var(--font-serif)",
    "--font-mono": "ui-monospace, 'SFMono-Regular', 'JetBrains Mono', Menlo, Consolas, monospace",
}


def apply_theme() -> dict[Any, Any]:
    """Return a Reflex-compatible style dict that injects CSS variables onto body."""
    return dict(TOKENS)
