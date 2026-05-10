"""Async SMTP client — routes to Mailpit in dev, real SMTP in prod."""

import aiosmtplib
import structlog

from durgam.config import settings

log = structlog.get_logger(__name__)


async def send_email(
    to: str,
    subject: str,
    body_html: str,
    body_text: str = "",
) -> None:
    """Send an email via the configured SMTP server (Mailpit in dev)."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject

    if body_text:
        msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        start_tls=False,
    )
    log.info("email_sent", to=to, subject=subject)
