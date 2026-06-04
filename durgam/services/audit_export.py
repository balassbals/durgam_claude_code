"""AuditCsvExportService — CSV export for audit log entries (M6b)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

_CSV_COLUMNS = (
    "id", "occurred_at", "actor_user_id", "actor_label", "actor_role_code",
    "action", "resource", "resource_id", "resource_label", "request_id",
    "ip", "user_agent", "diff_json", "actor_roles_json",
)

_UTF8_BOM = b"\xef\xbb\xbf"


class AuditCsvExportService:
    def export(self, rows: list[dict[str, Any]]) -> bytes:
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
        writer.writerow(_CSV_COLUMNS)
        for row in rows:
            writer.writerow(self._row_values(row))
        return _UTF8_BOM + buf.getvalue().encode("utf-8")

    @staticmethod
    def _row_values(row: dict[str, Any]) -> tuple[str, ...]:
        occ = row.get("occurred_at")
        if hasattr(occ, "strftime"):
            occurred_at = occ.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif isinstance(occ, str):
            occurred_at = occ[:19].replace(" ", "T") + "Z"
        else:
            occurred_at = ""

        def _json_cell(val: Any) -> str:
            if val is None:
                return ""
            return json.dumps(val, default=str)

        return (
            str(row.get("id", "")),
            occurred_at,
            str(row.get("actor_user_id") or ""),
            row.get("actor_label") or "",
            row.get("actor_role_code") or "",
            row.get("action") or "",
            row.get("resource") or "",
            row.get("resource_id") or "",
            row.get("resource_label") or "",
            str(row.get("request_id") or ""),
            row.get("ip") or "",
            row.get("user_agent") or "",
            _json_cell(row.get("diff_json")),
            _json_cell(row.get("actor_roles_json")),
        )
