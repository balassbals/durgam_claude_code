"""Unit tests for calendar phase-transition email notifications."""

from unittest.mock import AsyncMock, patch

import pytest

from durgam.notifications.calendar_emails import (
    _IQAC_ROLES,
    _PHASE3_ROLES,
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
        with (
            patch(
                "durgam.notifications.calendar_emails._get_role_emails",
                return_value=["director@example.dev", "hod.office@example.dev"],
            ) as mock_get,
            patch(
                "durgam.notifications.calendar_emails.send_email",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            await send_iqac_confirmed_email("2025-26")

        mock_get.assert_called_once_with(_PHASE3_ROLES)
        assert mock_send.call_count == 2
        subjects = [c.kwargs["subject"] for c in mock_send.call_args_list]
        assert all("2025-26" in s for s in subjects)

    @pytest.mark.asyncio
    async def test_ay_code_in_body(self):
        with (
            patch(
                "durgam.notifications.calendar_emails._get_role_emails",
                return_value=["director@example.dev"],
            ),
            patch(
                "durgam.notifications.calendar_emails.send_email",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            await send_iqac_confirmed_email("2025-26")

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
            await send_iqac_confirmed_email("2025-26")

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_failure_does_not_raise(self):
        with (
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
            await send_iqac_confirmed_email("2025-26")


class TestRoleConstants:
    def test_iqac_roles(self):
        assert "IQAC_COORDINATOR" in _IQAC_ROLES

    def test_phase3_roles_include_director_family(self):
        assert "DIRECTOR" in _PHASE3_ROLES
        assert "DEPUTY_DIRECTOR" in _PHASE3_ROLES
        assert "DIRECTOR_OFFICE" in _PHASE3_ROLES

    def test_phase3_roles_include_dean_sw(self):
        assert "DEAN_STUDENT_WELFARE" in _PHASE3_ROLES

    def test_phase3_roles_include_hod_family(self):
        assert "HOD" in _PHASE3_ROLES
        assert "AHOD" in _PHASE3_ROLES
        assert "HOD_OFFICE" in _PHASE3_ROLES

    def test_phase3_roles_include_deans(self):
        assert "DEAN" in _PHASE3_ROLES
        assert "DEAN_SCI" in _PHASE3_ROLES

    def test_phase3_excludes_registrar_and_iqac(self):
        assert "REGISTRAR" not in _PHASE3_ROLES
        assert "IQAC_COORDINATOR" not in _PHASE3_ROLES
        assert "STUDENT" not in _PHASE3_ROLES
