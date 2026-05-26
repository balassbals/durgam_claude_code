"""DOCX template-fill primitive — Jinja2-based DOCX generation (E-005)."""

from __future__ import annotations

import io
from typing import Any

from docxtpl import DocxTemplate


class DocgenError(Exception):
    pass


def render_docx_template(
    template_bytes: bytes,
    context: dict[str, Any],
) -> bytes:
    """Fill a DOCX template with Jinja2 context variables and return DOCX bytes.

    Args:
        template_bytes: Raw bytes of a DOCX file containing ``{{ var }}`` placeholders.
        context: Dict of variable names → values to render into the template.

    Returns:
        Rendered DOCX file bytes.

    Raises:
        DocgenError: If the template is not a valid DOCX or rendering fails.
    """
    try:
        tpl = DocxTemplate(io.BytesIO(template_bytes))
        tpl.render(context)
        buf = io.BytesIO()
        tpl.save(buf)
        return buf.getvalue()
    except Exception as exc:
        raise DocgenError(f"DOCX template rendering failed: {exc}") from exc
