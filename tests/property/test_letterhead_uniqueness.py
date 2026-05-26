"""Property test: at most one active DocumentTemplate letterhead per (role_code, scope) pair.

Uses Hypothesis to generate sequences of upload/delete operations and asserts
the invariant holds after each operation.
"""

from unittest.mock import MagicMock
from uuid import uuid4

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from durgam.models.config_anchors import DocumentTemplate
from durgam.services.document_template import DocumentTemplateService


def _make_svc():
    """Build a service with in-memory tracking repo mock."""
    repo = MagicMock()
    upload_svc = MagicMock()

    active: dict[tuple[str, str | None, str | None], DocumentTemplate] = {}

    def get_lh(role_code, scope_type=None, scope_id=None):
        return active.get((role_code, scope_type, str(scope_id) if scope_id else None))

    def save(row):
        key = (row.role_code, row.scope_type, str(row.scope_id) if row.scope_id else None)
        active[key] = row
        return row

    def soft_delete(row, actor_id):
        key = (row.role_code, row.scope_type, str(row.scope_id) if row.scope_id else None)
        active.pop(key, None)
        row.is_deleted = True
        return row

    def get_by_id(rid):
        for v in active.values():
            if v.id == rid:
                return v
        return None

    repo.get_letterhead_by_role_and_scope = get_lh
    repo.save = save
    repo.soft_delete = soft_delete
    repo.get_by_id = get_by_id

    fa = MagicMock()
    fa.id = uuid4()
    upload_svc.upload.return_value = fa

    return DocumentTemplateService(repo=repo, upload_svc=upload_svc), active


_ROLE_CODES = st.sampled_from(["REGISTRAR", "DIRECTOR", "HOD", "DEAN"])
_ACTIONS = st.sampled_from(["upload", "delete"])


@given(
    ops=st.lists(
        st.tuples(_ROLE_CODES, _ACTIONS),
        min_size=1,
        max_size=20,
    )
)
@hyp_settings(max_examples=200)
def test_at_most_one_active_per_role_scope(ops):
    svc, active = _make_svc()
    actor = uuid4()

    for role_code, action in ops:
        if action == "upload":
            svc.upload_letterhead(
                role_code, b"data", "f.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                actor,
            )
        elif action == "delete":
            existing = active.get((role_code, None, None))
            if existing is not None:
                svc.soft_delete(existing.id, actor)

        counts: dict[tuple, int] = {}
        for key in active:
            counts[key] = counts.get(key, 0) + 1
        for key, count in counts.items():
            assert count <= 1, f"Multiple active letterheads for {key}: {count}"
