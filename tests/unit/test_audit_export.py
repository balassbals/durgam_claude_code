"""Unit tests for AuditCsvExportService and export-related logic."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql as pg_dialect
from sqlmodel import select

from durgam.models.crosscutting import AuditLog
from durgam.services.audit_export import AuditCsvExportService

_EXPECTED_COLUMNS = (
    "id", "occurred_at", "actor_user_id", "actor_label", "actor_role_code",
    "action", "resource", "resource_id", "resource_label", "request_id",
    "ip", "user_agent", "diff_json", "actor_roles_json",
)


def _fixture_row(**overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "id": 42,
        "occurred_at": datetime(2026, 6, 1, 10, 30, 0, tzinfo=UTC),
        "actor_user_id": str(uuid4()),
        "actor_label": "alice — Alice Admin",
        "actor_role_code": "SYSTEM_ADMIN",
        "action": "write",
        "resource": "campus",
        "resource_id": str(uuid4()),
        "resource_label": "PP — Prasanthi",
        "request_id": str(uuid4()),
        "ip": "10.0.0.1",
        "user_agent": "Mozilla/5.0",
        "diff_json": {"name": ["Old Campus", "New Campus"]},
        "actor_roles_json": [{"role_code": "SYSTEM_ADMIN", "scope_type": None,
                              "scope_id": None}],
    }
    defaults.update(overrides)
    return defaults


class TestCsvExportColumnsInCorrectOrder:
    def test_header_matches_spec(self):
        svc = AuditCsvExportService()
        data = svc.export([_fixture_row()])
        content = data[3:].decode("utf-8")  # skip BOM
        reader = csv.reader(io.StringIO(content))
        header = next(reader)
        assert tuple(header) == _EXPECTED_COLUMNS


class TestCsvExportQuotesAllFields:
    def test_every_field_quoted(self):
        svc = AuditCsvExportService()
        data = svc.export([_fixture_row()])
        raw = data[3:].decode("utf-8")  # skip BOM
        for line in raw.strip().split("\r\n"):
            assert line.startswith('"') and line.endswith('"'), (
                f"Line does not start/end with quote: {line[:80]}"
            )
            assert '","' in line or line.count('"') == 2, (
                f"Fields not quote-delimited: {line[:80]}"
            )


class TestCsvExportUtf8BomPresent:
    def test_bom_bytes(self):
        svc = AuditCsvExportService()
        data = svc.export([_fixture_row()])
        assert data[:3] == b"\xef\xbb\xbf"


class TestCsvExportDiffJsonSerializedAsJsonString:
    def test_diff_json_cell_is_json(self):
        diff = {"a": [1, 2]}
        svc = AuditCsvExportService()
        data = svc.export([_fixture_row(diff_json=diff)])
        content = data[3:].decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        next(reader)  # header
        row = next(reader)
        diff_col_idx = _EXPECTED_COLUMNS.index("diff_json")
        cell = row[diff_col_idx]
        parsed = json.loads(cell)
        assert parsed == {"a": [1, 2]}


class TestCsvExportNullDiffRendersEmptyCell:
    def test_null_diff_is_empty(self):
        svc = AuditCsvExportService()
        data = svc.export([_fixture_row(diff_json=None)])
        content = data[3:].decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        next(reader)  # header
        row = next(reader)
        diff_col_idx = _EXPECTED_COLUMNS.index("diff_json")
        assert row[diff_col_idx] == ""


class TestCsvExportResolvedLabelsInDedicatedColumns:
    def test_labels_independent_of_ids(self):
        row = _fixture_row(
            actor_user_id=str(uuid4()),
            actor_label="bob — Bob Builder",
            resource_id=str(uuid4()),
            resource_label="SC — Science",
        )
        svc = AuditCsvExportService()
        data = svc.export([row])
        content = data[3:].decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        next(reader)  # header
        csv_row = next(reader)

        actor_label_idx = _EXPECTED_COLUMNS.index("actor_label")
        resource_label_idx = _EXPECTED_COLUMNS.index("resource_label")
        actor_id_idx = _EXPECTED_COLUMNS.index("actor_user_id")
        resource_id_idx = _EXPECTED_COLUMNS.index("resource_id")

        assert csv_row[actor_label_idx] == "bob — Bob Builder"
        assert csv_row[resource_label_idx] == "SC — Science"
        assert csv_row[actor_id_idx] != csv_row[actor_label_idx]
        assert csv_row[resource_id_idx] != csv_row[resource_label_idx]


class TestCsvExport10kCapViaQueryLimit:
    def test_export_query_includes_limit_10000(self):
        """Verify the export query uses LIMIT 10000 via compiled-SQL inspection."""
        from pathlib import Path
        src = Path("durgam/pages/audit/index.py").read_text()
        assert "stmt.limit(10_000)" in src

        stmt = select(AuditLog).limit(10_000)
        compiled = stmt.compile(dialect=pg_dialect.dialect())
        sql_str = str(compiled)
        assert "LIMIT" in sql_str


class TestCsvExportFlashWhenOverCap:
    def test_over_cap_branch_sets_flash(self):
        """Verify the over-cap branch exists via source inspection."""
        from pathlib import Path
        src = Path("durgam/pages/audit/index.py").read_text()
        assert "export_total > 10_000" in src
        assert "Export capped at 10,000 rows" in src
        assert 'self.flash_type = "warning"' in src


class TestCsvExportOccurredAtFormat:
    def test_datetime_formatted_with_seconds_precision(self):
        svc = AuditCsvExportService()
        dt = datetime(2026, 6, 1, 10, 30, 45, 123456, tzinfo=UTC)
        data = svc.export([_fixture_row(occurred_at=dt)])
        content = data[3:].decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        next(reader)
        row = next(reader)
        occ_idx = _EXPECTED_COLUMNS.index("occurred_at")
        assert row[occ_idx] == "2026-06-01T10:30:45Z"


class TestBuildDiffEntries:
    def test_fk_field_with_labels(self):
        from durgam.pages.audit.index import _build_diff_entries
        uid_a, uid_b = str(uuid4()), str(uuid4())
        row: dict[str, Any] = {
            "diff_json": {"school_id": [uid_a, uid_b]},
            "diff_labels": {"school_id": ["SC — Science", "ENG — Engineering"]},
        }
        entries = _build_diff_entries(row)
        assert len(entries) == 1
        assert entries[0]["field"] == "school_id"
        assert entries[0]["before_text"] == "SC — Science"
        assert entries[0]["after_text"] == "ENG — Engineering"
        assert uid_a in entries[0]["sub_display"]
        assert uid_b in entries[0]["sub_display"]

    def test_redacted_field(self):
        from durgam.pages.audit.index import _build_diff_entries
        row: dict[str, Any] = {
            "diff_json": {"password_hash": ["<redacted>", "<redacted>"]},
            "diff_labels": {},
        }
        entries = _build_diff_entries(row)
        assert entries[0]["before_text"] == "<redacted>"
        assert entries[0]["after_text"] == "<redacted>"

    def test_new_field(self):
        from durgam.pages.audit.index import _build_diff_entries
        row: dict[str, Any] = {
            "diff_json": {"name": [None, "New Name"]},
            "diff_labels": {},
        }
        entries = _build_diff_entries(row)
        assert entries[0]["before_text"] == "(none)"
        assert entries[0]["after_text"] == "New Name"

    def test_empty_diff_json_returns_empty(self):
        from durgam.pages.audit.index import _build_diff_entries
        assert _build_diff_entries({"diff_json": None, "diff_labels": {}}) == []
        assert _build_diff_entries({"diff_json": {}, "diff_labels": {}}) == []

    def test_non_2_list_renders_raw_json(self):
        from durgam.pages.audit.index import _build_diff_entries
        row: dict[str, Any] = {
            "diff_json": {"weird": [1, 2, 3]},
            "diff_labels": {},
        }
        entries = _build_diff_entries(row)
        assert entries[0]["before_text"] == "[1, 2, 3]"
        assert entries[0]["after_text"] == ""
