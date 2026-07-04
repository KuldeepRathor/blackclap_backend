"""Email transport.

A tiny swappable interface (`EmailSender`) with an SMTP implementation. Callers
depend on the interface / module-level `email_sender` singleton, so we can move
to Azure Communication Services (or SendGrid/Resend) later without touching
call sites.

Dev fallback: if SMTP_HOST is not configured, emails are logged instead of sent
so the reset flow stays testable locally.
"""
import logging
import ssl
from email.message import EmailMessage
from typing import Protocol

import aiosmtplib
import certifi

from app.core.config.settings import settings

# Some Python.org macOS installs ship without the system CA trust store wired
# up, which makes STARTTLS handshakes fail with CERTIFICATE_VERIFY_FAILED.
# Building the context from certifi's bundle makes this work regardless of
# how the interpreter was installed.
_TLS_CONTEXT = ssl.create_default_context(cafile=certifi.where())

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send(
        self, *, to: str, subject: str, text: str, html: str | None = None
    ) -> None: ...


class SMTPEmailSender:
    async def send(
        self, *, to: str, subject: str, text: str, html: str | None = None
    ) -> None:
        # Dev fallback: no SMTP configured → log so the flow is still testable.
        if not settings.SMTP_HOST:
            logger.warning(
                "SMTP not configured; email NOT sent. to=%s subject=%s\n%s",
                to,
                subject,
                text,
            )
            return

        message = EmailMessage()
        message["From"] = settings.EMAIL_FROM
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text)
        if html:
            message.add_alternative(html, subtype="html")

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER or None,
                password=settings.SMTP_PASSWORD or None,
                start_tls=settings.SMTP_USE_TLS,
                tls_context=_TLS_CONTEXT,
            )
        except Exception:
            # Never propagate email failures to the caller — the reset code is
            # already stored; we don't want to leak send failures or crash the
            # background task.
            logger.exception("Failed to send email to %s", to)


email_sender: EmailSender = SMTPEmailSender()
