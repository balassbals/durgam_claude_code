"""Integration test for docgen merge — letterhead + content → valid DOCX."""

import io

from docx import Document

from durgam.docgen.merge import merge_letterhead_and_content

_2x2_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02"
    b"\x00\x00\x00\x02\x08\x02\x00\x00\x00\xfd\xd4\x9as"
    b"\x00\x00\x00\x10IDATx\x9cc\xf8\xcf\xc0\x00D\x0c\x10"
    b"\n\x00\x1f\xee\x03\xfd\x8b_\x14\xd4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestDocgenIntegration:
    def test_full_merge_produces_valid_docx(self):
        blocks = [
            {"type": "heading", "text": "Board of Studies Meeting", "level": 1},
            {"type": "paragraph", "text": "Minutes of the meeting held on 2025-10-15."},
            {"type": "table", "rows": [
                ["Item", "Description", "Action"],
                ["1", "Curriculum revision", "Approved"],
                ["2", "New elective proposal", "Deferred"],
            ]},
            {"type": "paragraph", "text": "Meeting adjourned at 4:00 PM."},
        ]
        result = merge_letterhead_and_content(_2x2_PNG, blocks)
        assert len(result) > 0

        doc = Document(io.BytesIO(result))
        assert any("Board of Studies Meeting" in p.text for p in doc.paragraphs)
        assert any("Minutes of the meeting" in p.text for p in doc.paragraphs)
        assert len(doc.tables) == 1
        assert doc.tables[0].rows[0].cells[0].text == "Item"
        assert doc.tables[0].rows[1].cells[2].text == "Approved"

        header = doc.sections[0].header
        assert len(header.paragraphs[0].runs) == 1
