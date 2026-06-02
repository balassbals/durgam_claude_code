"""Unit tests for counsellor roster DOCX export logic.

Tests the render_docx_template integration and the purpose-based download
gate rather than the Reflex state (which requires the full runtime).
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.docgen.merge import DocgenError, render_docx_template
from durgam.repositories.document_template import DocumentTemplateRepository


def _make_minimal_docx() -> bytes:
    """Create a minimal valid DOCX file for testing."""
    from docx import Document
    import io

    doc = Document()
    doc.add_paragraph("{{ academic_year }}")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestRenderDocxTemplate:
    def test_render_returns_bytes(self):
        template_bytes = _make_minimal_docx()
        result, warnings = render_docx_template(template_bytes, {"academic_year": "2025-26"})
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert warnings == []

    def test_render_invalid_bytes_raises_docgen_error(self):
        with pytest.raises(DocgenError, match="rendering failed"):
            render_docx_template(b"not-a-valid-docx", {"key": "value"})


class TestDirectorLetterheadLookup:
    def test_get_letterhead_returns_none_when_missing(self):
        session = MagicMock()
        session.exec.return_value.first.return_value = None
        repo = DocumentTemplateRepository(session)
        result = repo.get_letterhead_by_role("DIRECTOR")
        assert result is None

    def test_get_letterhead_returns_record_when_present(self):
        mock_record = MagicMock()
        mock_record.role_code = "DIRECTOR"
        session = MagicMock()
        session.exec.return_value.first.return_value = mock_record
        repo = DocumentTemplateRepository(session)
        result = repo.get_letterhead_by_role("DIRECTOR")
        assert result is mock_record


class TestPurposeMapCounsellorRoster:
    def test_counsellor_roster_in_purpose_map(self):
        from durgam.api.download import _PURPOSE_PERMISSION_MAP
        assert "counsellor_roster" in _PURPOSE_PERMISSION_MAP
        assert _PURPOSE_PERMISSION_MAP["counsellor_roster"] == "mental_health_counsellor"

    def test_counsellor_document_not_in_purpose_map(self):
        from durgam.api.download import _PURPOSE_PERMISSION_MAP
        assert "counsellor_document" not in _PURPOSE_PERMISSION_MAP


class TestExportContextShape:
    def test_counsellor_context_dict_structure(self):
        from types import SimpleNamespace
        rows = [
            SimpleNamespace(
                name="Dr. Test",
                qualification="PhD",
                specialisation="Clinical",
                mode_of_appointment="inhouse",
                appointment_start="2025-07-01",
                appointment_end="2026-04-30",
                phone="+91-9876543210",
                email="test@example.dev",
            ),
        ]
        context = {
            "academic_year": "2025-26",
            "campus": "PSN — Prasanthi Nilayam",
            "counsellors": [
                {
                    "sno": i + 1,
                    "name": r.name,
                    "qualification": r.qualification,
                    "specialisation": r.specialisation,
                    "mode_of_appointment": r.mode_of_appointment,
                    "appointment_start": str(r.appointment_start),
                    "appointment_end": str(r.appointment_end),
                    "phone": r.phone or "",
                    "email": r.email or "",
                }
                for i, r in enumerate(rows)
            ],
        }
        assert len(context["counsellors"]) == 1
        assert context["counsellors"][0]["sno"] == 1
        assert context["counsellors"][0]["name"] == "Dr. Test"
        assert context["counsellors"][0]["mode_of_appointment"] == "inhouse"
