"""Unit tests for calendar phase-transition email notifications."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from durgam.notifications.calendar_emails import (
    _EXCLUDED_FROM_PHASE3,
    _IQAC_ROLES,
    _get_phase3_roles,
    send_iqac_confirmed_email,
    send_registrar_confirmed_email,
)


class TestSendRegistrarConfirmedEmail:
    @pytest.mark.asyncio
    async def test_sends_to_iqac_recipients(self):
        with (
            patch(
                "durgam.notifications.calendar_emails._get_role_emails",
                return_value=["iqac@example.dev"],
            ) as mock_get,
            patch(
                "durgam.notifications.calendar_emails.send_email",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            await send_registrar_confirmed_email("2025-26")

        mock_get.assert_called_once_with(_IQAC_ROLES)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["to"] == "iqac@example.dev"
        assert "2025-26" in call_kwargs["subject"]
        assert "IQAC" in call_kwargs["subject"]

    @pytest.mark.asyncio
    async def test_ay_code_in_body(self):
        with (
            patch(
                "durgam.notifications.calendar_emails._get_role_emails",
                return_value=["iqac@example.dev"],
            ),
            patch(
                "durgam.notifications.calendar_emails.send_email",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            await send_registrar_confirmed_email("2025-26")

        call_kwargs = mock_send.call_args.kwargs
        assert "2025-26" in call_kwargs["body_html"]
        assert "2025-26" in call_kwargs["body_text"]

    @pytest.mark.asyncio
    async def test_no_recipients_does_not_send(self):
        with (
            patch(
                "durgam.notifications.calendar_emails._get_role_emails",
                return_value=[],
            ),
            patch(
                "durgam.notifications.calendar_emails.send_email",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            await send_registrar_confirmed_email("2025-26")

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_failure_does_not_raise(self):
        with (
            patch(
                "durgam.notifications.calendar_emails._get_role_emails",
                return_value=["iqac@example.dev"],
            ),
            patch(
                "durgam.notifications.calendar_emails.send_email",
                new_callable=AsyncMock,
                side_effect=ConnectionError("SMTP down"),
            ),
        ):
            await send_registrar_confirmed_email("2025-26")

    @pytest.mark.asyncio
    async def test_multiple_recipients(self):
        with (
            patch(
                "durgam.notifications.calendar_emails._get_role_emails",
                return_value=["iqac1@example.dev", "iqac2@example.dev"],
            ),
            patch(
                "durgam.notifications.calendar_emails.send_email",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            await send_registrar_confirmed_email("2025-26")

        assert mock_send.call_count == 2


class TestSendIqacConfirmedEmail:
    @pytest.mark.asyncio
    async def test_sends_to_phase3_recipients(self):
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = [
            "DIRECTOR", "HOD", "DEAN", "STUDENT", "BASIC_USER",
        ]
        with (
            patch(
                "durgam.notifications.calendar_emails.open_session",
            ) as mock_open,
            patch(
                "durgam.notifications.calendar_emails._get_role_emails",
                return_value=["director@example.dev", "hod.office@example.dev"],
            ) as mock_get,
            patch(
                "durgam.notifications.calendar_emails.send_email",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_open.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            await send_iqac_confirmed_email("2025-26")

        called_roles = mock_get.call_args[0][0]
        assert "DIRECTOR" in called_roles
        assert "HOD" in called_roles
        assert "DEAN" in called_roles
        assert "STUDENT" not in called_roles
        assert "BASIC_USER" not in called_roles
        assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_ay_code_in_body(self):
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = ["DIRECTOR"]
        with (
            patch(
                "durgam.notifications.calendar_emails.open_session",
            ) as mock_open,
            patch(
                "durgam.notifications.calendar_emails._get_role_emails",
                return_value=["director@example.dev"],
            ),
            patch(
                "durgam.notifications.calendar_emails.send_email",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_open.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            await send_iqac_confirmed_email("2025-26")

        call_kwargs = mock_send.call_args.kwargs
        assert "2025-26" in call_kwargs["body_html"]
        assert "2025-26" in call_kwargs["body_text"]

    @pytest.mark.asyncio
    async def test_no_recipients_does_not_send(self):
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = ["DIRECTOR"]
        with (
            patch(
                "durgam.notifications.calendar_emails.open_session",
            ) as mock_open,
            patch(
                "durgam.notifications.calendar_emails._get_role_emails",
                return_value=[],
            ),
            patch(
                "durgam.notifications.calendar_emails.send_email",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_open.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            await send_iqac_confirmed_email("2025-26")

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_failure_does_not_raise(self):
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = ["DIRECTOR"]
        with (
            patch(
                "durgam.notifications.calendar_emails.open_session",
            ) as mock_open,
            patch(
                "durgam.notifications.calendar_emails._get_role_emails",
                return_value=["director@example.dev"],
            ),
            patch(
                "durgam.notifications.calendar_emails.send_email",
                new_callable=AsyncMock,
                side_effect=ConnectionError("SMTP down"),
            ),
        ):
            mock_open.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            await send_iqac_confirmed_email("2025-26")


class TestGetPhase3Roles:
    def test_excludes_student_basic_sysadmin(self):
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = [
            "REGISTRAR", "DIRECTOR", "HOD", "DEAN",
            "STUDENT", "BASIC_USER", "SYSTEM_ADMIN",
            "VC", "FACULTY", "LIBRARIAN",
        ]
        result = _get_phase3_roles(mock_session)
        assert "REGISTRAR" in result
        assert "DIRECTOR" in result
        assert "HOD" in result
        assert "DEAN" in result
        assert "VC" in result
        assert "FACULTY" in result
        assert "LIBRARIAN" in result
        assert "STUDENT" not in result
        assert "BASIC_USER" not in result
        assert "SYSTEM_ADMIN" not in result

    def test_exclusion_set_is_correct(self):
        assert _EXCLUDED_FROM_PHASE3 == frozenset({"STUDENT", "BASIC_USER", "SYSTEM_ADMIN"})

    def test_iqac_roles(self):
        assert "IQAC_COORDINATOR" in _IQAC_ROLES
