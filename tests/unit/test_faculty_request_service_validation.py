"""Unit tests for FacultyRequestService validation rules (M10 Phase 5A).

Pure-Python, no DB, no I/O. Repository calls replaced by MagicMock stubs.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.models.faculty_request import (
    FACULTY_REQUEST_STATUSES,
    FACULTY_REQUEST_TYPES,
    REQUEST_TYPE_FIELD_VISIT,
    REQUEST_TYPE_INVITED_TALK,
    REQUEST_TYPE_NOC,
    REQUEST_TYPE_PROFESSIONAL_MEMBERSHIP,
    REQUEST_TYPE_WFH,
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_REJECTED,
    STATUS_SUBMITTED,
    STATUS_WITHDRAWN,
    FacultyRequest,
)
from durgam.services.faculty_request import (
    FacultyRequestService,
    InvalidRequestStatusTransitionError,
    UnknownRequestTypeError,
)


def _make_service(faculty=None, existing_request=None):
    """Return a FacultyRequestService with mocked repositories."""
    session = MagicMock()
    svc = FacultyRequestService.__new__(FacultyRequestService)
    svc._session = session

    mock_repo = MagicMock()
    mock_faculty_repo = MagicMock()

    if faculty is not None:
        mock_faculty_repo.get.return_value = faculty
    else:
        mock_faculty_repo.get.return_value = MagicMock()  # always found

    if existing_request is not None:
        mock_repo.get.return_value = existing_request
    else:
        mock_repo.get.return_value = MagicMock()

    svc._repo = mock_repo
    svc._faculty_repo = mock_faculty_repo
    return svc


def _make_request(status: str = STATUS_DRAFT) -> FacultyRequest:
    return FacultyRequest(
        id=uuid4(),
        faculty_id=uuid4(),
        request_type=REQUEST_TYPE_NOC,
        status=status,
        is_deleted=False,
    )


class TestCreateValidation:
    def test_create_rejects_unknown_request_type(self):
        svc = _make_service()
        with pytest.raises(UnknownRequestTypeError, match="bogus_type"):
            svc.create_request(
                faculty_id=uuid4(),
                request_type="bogus_type",
                payload=None,
                actor_id=uuid4(),
            )

    @pytest.mark.parametrize(
        "rtype",
        [
            REQUEST_TYPE_NOC,
            REQUEST_TYPE_INVITED_TALK,
            REQUEST_TYPE_PROFESSIONAL_MEMBERSHIP,
            REQUEST_TYPE_WFH,
            REQUEST_TYPE_FIELD_VISIT,
        ],
    )
    def test_create_accepts_known_types(self, rtype):
        svc = _make_service()
        # Should not raise; repo.create is called
        svc.create_request(
            faculty_id=uuid4(),
            request_type=rtype,
            payload=None,
            actor_id=uuid4(),
        )
        svc._repo.create.assert_called_once()
        call_kwargs = svc._repo.create.call_args.kwargs
        assert call_kwargs["request_type"] == rtype


class TestUpdatePayloadValidation:
    @pytest.mark.parametrize(
        "bad_status",
        [STATUS_SUBMITTED, STATUS_APPROVED, STATUS_REJECTED, STATUS_WITHDRAWN],
    )
    def test_update_payload_rejects_non_draft_status(self, bad_status):
        req = _make_request(status=bad_status)
        svc = _make_service(existing_request=req)
        with pytest.raises(
            InvalidRequestStatusTransitionError, match=bad_status
        ):
            svc.update_payload(req.id, {"reason": "changed"}, uuid4())

    def test_update_payload_allowed_on_draft(self):
        req = _make_request(status=STATUS_DRAFT)
        svc = _make_service(existing_request=req)
        new_payload = {"reason": "new reason"}
        svc.update_payload(req.id, new_payload, uuid4())
        svc._repo.update.assert_called_once()
        call_args = svc._repo.update.call_args
        assert call_args.args[1] == {"payload_json": new_payload}


class TestConstants:
    def test_constants_frozen(self):
        assert isinstance(FACULTY_REQUEST_TYPES, frozenset)
        assert FACULTY_REQUEST_TYPES == frozenset({
            REQUEST_TYPE_NOC,
            REQUEST_TYPE_INVITED_TALK,
            REQUEST_TYPE_PROFESSIONAL_MEMBERSHIP,
            REQUEST_TYPE_WFH,
            REQUEST_TYPE_FIELD_VISIT,
        })

    def test_types_has_exactly_five_entries(self):
        assert len(FACULTY_REQUEST_TYPES) == 5

    @pytest.mark.parametrize("rtype", [
        REQUEST_TYPE_INVITED_TALK,
        REQUEST_TYPE_PROFESSIONAL_MEMBERSHIP,
        REQUEST_TYPE_WFH,
        REQUEST_TYPE_FIELD_VISIT,
    ])
    def test_new_types_in_frozenset(self, rtype):
        assert rtype in FACULTY_REQUEST_TYPES

    @pytest.mark.parametrize("dropped", ["bonafide_certificate", "address_change"])
    def test_dropped_types_not_in_frozenset(self, dropped):
        assert dropped not in FACULTY_REQUEST_TYPES

    @pytest.mark.parametrize("attr", ["REQUEST_TYPE_BONAFIDE_CERTIFICATE", "REQUEST_TYPE_ADDRESS_CHANGE"])
    def test_dropped_constants_not_exported(self, attr):
        import durgam.models.faculty_request as mod
        assert not hasattr(mod, attr), f"{attr} must be removed per Q-P5.1"

    @pytest.mark.parametrize("constant, expected", [
        (REQUEST_TYPE_INVITED_TALK, "invited_talk"),
        (REQUEST_TYPE_PROFESSIONAL_MEMBERSHIP, "professional_membership"),
        (REQUEST_TYPE_WFH, "wfh"),
        (REQUEST_TYPE_FIELD_VISIT, "field_visit"),
    ])
    def test_new_constant_string_values(self, constant, expected):
        assert constant == expected

    def test_statuses_frozen(self):
        assert isinstance(FACULTY_REQUEST_STATUSES, frozenset)
        assert FACULTY_REQUEST_STATUSES == frozenset({
            STATUS_DRAFT,
            STATUS_SUBMITTED,
            STATUS_APPROVED,
            STATUS_REJECTED,
            STATUS_WITHDRAWN,
        })
