"""Admin-triggered email notifications (§9.2(e)(f)(f2))."""

from __future__ import annotations

import structlog

from durgam.config import settings
from durgam.models.identity import User
from durgam.notifications.email import send_email

log = structlog.get_logger(__name__)


async def send_user_created_email(user: User, temp_password: str) -> None:
    """Notify a newly created user of their account and temporary password."""
    login_url = f"{settings.app_base_url}/login"
    await send_email(
        to=user.email,
        subject="Your DURGAM account has been created",
        body_html=_user_created_html(user.username, temp_password, login_url),
        body_text=_user_created_text(user.username, temp_password, login_url),
    )
    log.info("admin_email_user_created", user_id=str(user.id))


async def send_user_updated_email(user: User, change_summary: str) -> None:
    """Notify a user when their account is modified by an admin."""
    await send_email(
        to=user.email,
        subject="Your DURGAM account has been updated",
        body_html=_user_updated_html(user.username, change_summary),
        body_text=_user_updated_text(user.username, change_summary),
    )
    log.info("admin_email_user_updated", user_id=str(user.id))


async def send_user_deleted_email(user: User) -> None:
    """Notify a user when their account is deactivated."""
    await send_email(
        to=user.email,
        subject="Your DURGAM account has been deactivated",
        body_html=_user_deleted_html(user.username),
        body_text=_user_deleted_text(user.username),
    )
    log.info("admin_email_user_deleted", user_id=str(user.id))


async def send_user_password_reset_email(user: User, temp_password: str) -> None:
    """Notify a user when an admin resets their password."""
    login_url = f"{settings.app_base_url}/login"
    await send_email(
        to=user.email,
        subject="Your DURGAM password has been reset",
        body_html=_password_reset_html(user.username, temp_password, login_url),
        body_text=_password_reset_text(user.username, temp_password, login_url),
    )
    log.info("admin_email_password_reset", user_id=str(user.id))


def _user_created_html(username: str, temp_password: str, login_url: str) -> str:
    return (
        "<html><body>"
        f"<p>Welcome to DURGAM, <strong>{username}</strong>.</p>"
        f"<p>Your temporary password is: <code>{temp_password}</code></p>"
        "<p>This password will expire on first login — you will be required to set a new one.</p>"
        f'<p><a href="{login_url}">Log in to DURGAM</a></p>'
        "<p>If you did not expect this message, contact your system administrator.</p>"
        "</body></html>"
    )


def _user_created_text(username: str, temp_password: str, login_url: str) -> str:
    return (
        f"Welcome to DURGAM, {username}.\n\n"
        f"Your temporary password is: {temp_password}\n\n"
        "This password will expire on first login — you will be required to set a new one.\n\n"
        f"Log in at: {login_url}\n\n"
        "If you did not expect this message, contact your system administrator."
    )


def _user_updated_html(username: str, change_summary: str) -> str:
    return (
        "<html><body>"
        f"<p>Hello <strong>{username}</strong>,</p>"
        f"<p>Your DURGAM account has been updated: {change_summary}</p>"
        "<p>If you did not expect this change, contact your system administrator.</p>"
        "</body></html>"
    )


def _user_updated_text(username: str, change_summary: str) -> str:
    return (
        f"Hello {username},\n\n"
        f"Your DURGAM account has been updated: {change_summary}\n\n"
        "If you did not expect this change, contact your system administrator."
    )


def _user_deleted_html(username: str) -> str:
    return (
        "<html><body>"
        f"<p>Hello <strong>{username}</strong>,</p>"
        "<p>Your DURGAM account has been deactivated. "
        "You can no longer log in.</p>"
        "<p>If you believe this is an error, contact your system administrator.</p>"
        "</body></html>"
    )


def _user_deleted_text(username: str) -> str:
    return (
        f"Hello {username},\n\n"
        "Your DURGAM account has been deactivated. You can no longer log in.\n\n"
        "If you believe this is an error, contact your system administrator."
    )


def _password_reset_html(username: str, temp_password: str, login_url: str) -> str:
    return (
        "<html><body>"
        f"<p>Hello <strong>{username}</strong>,</p>"
        "<p>An administrator has reset your DURGAM password.</p>"
        f"<p>Your new temporary password is: <code>{temp_password}</code></p>"
        "<p>You will be required to set a new password on your next login.</p>"
        f'<p><a href="{login_url}">Log in to DURGAM</a></p>'
        "<p>If you did not expect this reset, contact your system administrator immediately.</p>"
        "</body></html>"
    )


def _password_reset_text(username: str, temp_password: str, login_url: str) -> str:
    return (
        f"Hello {username},\n\n"
        "An administrator has reset your DURGAM password.\n\n"
        f"Your new temporary password is: {temp_password}\n\n"
        "You will be required to set a new password on your next login.\n\n"
        f"Log in at: {login_url}\n\n"
        "If you did not expect this reset, contact your system administrator immediately."
    )
