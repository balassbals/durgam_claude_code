"""DOCX template-fill primitive — Jinja2-based DOCX generation (E-005)."""

from __future__ import annotations

import io
from typing import Any

import structlog
from docxtpl import DocxTemplate

log = structlog.get_logger(__name__)


class DocgenError(Exception):
    pass


def render_docx_template(
    template_bytes: bytes,
    context: dict[str, Any],
) -> tuple[bytes, list[str]]:
    """Fill a DOCX template with Jinja2 context variables and return DOCX bytes.

    Args:
        template_bytes: Raw bytes of a DOCX file containing ``{{ var }}`` placeholders.
        context: Dict of variable names → values to render into the template.

    Returns:
        Tuple of (rendered DOCX file bytes, list of warning messages).
        Warnings are non-fatal — the template still renders, but the caller
        should surface them to the user (e.g. as a flash).

    Raises:
        DocgenError: If the template is not a valid DOCX or rendering fails.
    """
    warnings: list[str] = []
    try:
        tpl = DocxTemplate(io.BytesIO(template_bytes))
        template_vars = tpl.get_undeclared_template_variables()
        if not template_vars:
            msg = (
                "The letterhead template has no {{ }} placeholders — "
                "the downloaded file is the unmodified letterhead. "
                "Update the template to include placeholders like "
                "{{ counsellors }}, {{ academic_year }}, {{ campus }} "
                "to embed the roster data."
            )
            log.warning(
                "Document template has no placeholders matching the provided context",
                context_keys=list(context.keys()),
            )
            warnings.append(msg)
        tpl.render(context)
        buf = io.BytesIO()
        tpl.save(buf)
        return buf.getvalue(), warnings
    except Exception as exc:
        raise DocgenError(f"DOCX template rendering failed: {exc}") from exc
