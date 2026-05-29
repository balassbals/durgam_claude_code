"""Calendar phase-transition email notifications (M4)."""

from __future__ import annotations

import structlog
from sqlmodel import select

from durgam.config import settings
from durgam.db import open_session
from durgam.models.identity import Role, User, UserRole
from durgam.notifications.email import send_email

log = structlog.get_logger(__name__)

_IQAC_ROLES = frozenset({"IQAC_COORDINATOR"})

_PHASE3_ROLES = frozenset({
    "DIRECTOR", "DEPUTY_DIRECTOR", "DIRECTOR_OFFICE",
    "DEAN_STUDENT_WELFARE",
    "HOD", "AHOD", "HOD_OFFICE",
    "DEAN",
})


def _get_role_emails(role_codes: frozenset[str]) -> list[str]:
    with open_session() as session:
        rows = session.exec(
            select(User.email)
            .join(UserRole, UserRole.user_id == User.id)  # type: ignore[arg-type]
            .join(Role, Role.id == UserRole.role_id)  # type: ignore[arg-type]
            .where(
                Role.code.in_(role_codes),  # type: ignore[union-attr]
                User.is_active == True,  # noqa: E712
                User.is_deleted == False,  # noqa: E712
            )
        ).all()
        return list(set(rows))


async def send_registrar_confirmed_email(ay_code: str) -> None:
    recipients = _get_role_emails(_IQAC_ROLES)
    if not recipients:
        log.warning("calendar_email_no_iqac_recipients", ay_code=ay_code)
        return
    calendar_url = f"{settings.app_base_url}/admin/config/calendar"
    subject = f"Master calendar confirmed for {ay_code} — IQAC may now add activities"
    for email_addr in recipients:
        try:
            await send_email(
                to=email_addr,
                subject=subject,
                body_html=_registrar_confirmed_html(ay_code, calendar_url),
                body_text=_registrar_confirmed_text(ay_code, calendar_url),
            )
        except Exception:
            log.exception("calendar_email_send_failed", to=email_addr, ay_code=ay_code)


async def send_iqac_confirmed_email(ay_code: str) -> None:
    recipients = _get_role_emails(_PHASE3_ROLES)
    if not recipients:
        log.warning("calendar_email_no_phase3_recipients", ay_code=ay_code)
        return
    calendar_url = f"{settings.app_base_url}/admin/config/calendar"
    subject = f"Calendar open for {ay_code} — you may now add your entries"
    for email_addr in recipients:
        try:
            await send_email(
                to=email_addr,
                subject=subject,
                body_html=_iqac_confirmed_html(ay_code, calendar_url),
                body_text=_iqac_confirmed_text(ay_code, calendar_url),
            )
        except Exception:
            log.exception("calendar_email_send_failed", to=email_addr, ay_code=ay_code)


def _registrar_confirmed_html(ay_code: str, calendar_url: str) -> str:
    return (
        "<html><body>"
        "<p>The Registrar has confirmed the master calendar for "
        f"<strong>{ay_code}</strong>.</p>"
        "<p>IQAC may now add activity entries on the Calendar page, "
        "then confirm to open the calendar to other roles.</p>"
        f'<p><a href="{calendar_url}">Open Calendar</a></p>'
        "</body></html>"
    )


def _registrar_confirmed_text(ay_code: str, calendar_url: str) -> str:
    return (
        f"The Registrar has confirmed the master calendar for {ay_code}.\n\n"
        "IQAC may now add activity entries on the Calendar page, "
        "then confirm to open the calendar to other roles.\n\n"
        f"Calendar: {calendar_url}"
    )


def _iqac_confirmed_html(ay_code: str, calendar_url: str) -> str:
    return (
        "<html><body>"
        f"<p>IQAC has confirmed for <strong>{ay_code}</strong>.</p>"
        "<p>All eligible roles may now add their own calendar entries. "
        "Existing entries are visible on the Calendar page to help avoid scheduling clashes.</p>"
        f'<p><a href="{calendar_url}">Open Calendar</a></p>'
        "</body></html>"
    )


def _iqac_confirmed_text(ay_code: str, calendar_url: str) -> str:
    return (
        f"IQAC has confirmed for {ay_code}.\n\n"
        "All eligible roles may now add their own calendar entries. "
        "Existing entries are visible on the Calendar page to help avoid scheduling clashes.\n\n"
        f"Calendar: {calendar_url}"
    )
