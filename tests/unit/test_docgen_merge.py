"""Unit tests for docgen merge primitive — DOCX generation with letterhead."""

import io

import pytest
from docx import Document

from durgam.docgen.merge import DocgenError, merge_letterhead_and_content

_2x2_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02"
    b"\x00\x00\x00\x02\x08\x02\x00\x00\x00\xfd\xd4\x9as"
    b"\x00\x00\x00\x10IDATx\x9cc\xf8\xcf\xc0\x00D\x0c\x10"
    b"\n\x00\x1f\xee\x03\xfd\x8b_\x14\xd4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestMergeLetterheadAndContent:
    def test_empty_content_produces_valid_docx(self):
        result = merge_letterhead_and_content(_2x2_PNG, [])
        doc = Document(io.BytesIO(result))
        assert len(doc.paragraphs) == 0

    def test_heading_block(self):
        blocks = [{"type": "heading", "text": "Test Heading", "level": 2}]
        result = merge_letterhead_and_content(_2x2_PNG, blocks)
        doc = Document(io.BytesIO(result))
        assert any("Test Heading" in p.text for p in doc.paragraphs)

    def test_paragraph_block(self):
        blocks = [{"type": "paragraph", "text": "Hello world"}]
        result = merge_letterhead_and_content(_2x2_PNG, blocks)
        doc = Document(io.BytesIO(result))
        assert any("Hello world" in p.text for p in doc.paragraphs)

    def test_table_block(self):
        blocks = [{"type": "table", "rows": [["A", "B"], ["C", "D"]]}]
        result = merge_letterhead_and_content(_2x2_PNG, blocks)
        doc = Document(io.BytesIO(result))
        assert len(doc.tables) == 1
        assert doc.tables[0].rows[0].cells[0].text == "A"
        assert doc.tables[0].rows[1].cells[1].text == "D"

    def test_letterhead_in_header(self):
        result = merge_letterhead_and_content(_2x2_PNG, [])
        doc = Document(io.BytesIO(result))
        header = doc.sections[0].header
        assert header is not None
        runs = header.paragraphs[0].runs
        assert len(runs) == 1

    def test_pdf_letterhead_raises_error(self):
        with pytest.raises(DocgenError, match="PDF letterheads not yet supported"):
            merge_letterhead_and_content(
                b"%PDF-1.4 fake", [], mime_type="application/pdf"
            )

    def test_multiple_content_blocks(self):
        blocks = [
            {"type": "heading", "text": "Title", "level": 1},
            {"type": "paragraph", "text": "Body text"},
            {"type": "table", "rows": [["X"]]},
        ]
        result = merge_letterhead_and_content(_2x2_PNG, blocks)
        doc = Document(io.BytesIO(result))
        assert any("Title" in p.text for p in doc.paragraphs)
        assert any("Body text" in p.text for p in doc.paragraphs)
        assert len(doc.tables) == 1
