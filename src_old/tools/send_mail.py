"""Email sending tool using standard library smtplib and email.message."""

from __future__ import annotations

import logging
import re
import smtplib
from email.message import EmailMessage
from typing import Any

from src_old.config import get_config
from src_old.storage.user_info import load_user_info

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email_address(addr: str) -> bool:
    return bool(EMAIL_REGEX.match(addr.strip()))


def prepare_mail_preview(to: str, subject: str, body: str) -> dict[str, Any]:
    """
    Validate email fields and prepare a structured preview for user confirmation.
    """
    cfg = get_config()
    profile_data = load_user_info()
    sender_name = profile_data.get("profile", {}).get("name", "").strip()
    sender_email = profile_data.get("profile", {}).get("email", "").strip()

    errors = []
    if not sender_email:
        errors.append("Sender email is not configured in your profile. Please set it in the sidebar.")
    elif not _validate_email_address(sender_email):
        errors.append(f"Invalid sender email format: '{sender_email}'.")

    clean_to = str(to).strip()
    if not clean_to:
        errors.append("Recipient email ('to') cannot be empty.")
    elif not _validate_email_address(clean_to):
        errors.append(f"Invalid recipient email format: '{clean_to}'.")

    clean_subject = str(subject).strip()
    if not clean_subject:
        errors.append("Subject cannot be empty.")

    clean_body = str(body).strip()
    if not clean_body:
        errors.append("Email body cannot be empty.")

    if errors:
        return {
            "ok": False,
            "tool": "send_mail",
            "error": " | ".join(errors),
            "preview": None,
        }

    from_header = f"{sender_name} <{sender_email}>" if sender_name else sender_email

    return {
        "ok": True,
        "tool": "send_mail",
        "requires_confirmation": True,
        "preview": {
            "from": from_header,
            "to": clean_to,
            "subject": clean_subject,
            "body": clean_body,
            "smtp_host": cfg.smtp_host or "(not configured)",
            "smtp_port": cfg.smtp_port,
        },
    }


def send_mail(
    to: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """
    Send an email using SMTP credentials from .env and sender identity from profile.
    Requires explicit user confirmation in the UI.
    """
    preview_res = prepare_mail_preview(to, subject, body)
    if not preview_res["ok"]:
        return preview_res

    preview = preview_res["preview"]
    cfg = get_config()

    if not cfg.smtp_host:
        return {
            "ok": False,
            "tool": "send_mail",
            "error": "SMTP_HOST is not configured in .env. Cannot send email.",
            "preview": preview,
        }

    if not cfg.mail_password:
        return {
            "ok": False,
            "tool": "send_mail",
            "error": "MAIL_PASSWORD is not configured in .env. Cannot send email.",
            "preview": preview,
        }

    msg = EmailMessage()
    msg["Subject"] = preview["subject"]
    msg["From"] = preview["from"]
    msg["To"] = preview["to"]
    msg.set_content(preview["body"])

    profile_data = load_user_info()
    sender_email = profile_data.get("profile", {}).get("email", "").strip()

    try:
        if cfg.smtp_use_tls:
            server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=15)
            server.ehlo()

        server.login(sender_email, cfg.mail_password)
        server.send_message(msg)
        server.quit()

        return {
            "ok": True,
            "tool": "send_mail",
            "result": {
                "message": f"Email successfully sent to {preview['to']}.",
                "details": {
                    "from": preview["from"],
                    "to": preview["to"],
                    "subject": preview["subject"],
                },
            },
        }
    except smtplib.SMTPAuthenticationError:
        return {
            "ok": False,
            "tool": "send_mail",
            "error": "SMTP Authentication failed. Please verify your MAIL_PASSWORD and sender email.",
            "preview": preview,
        }
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", preview["to"], exc)
        return {
            "ok": False,
            "tool": "send_mail",
            "error": f"Failed to send email: {exc}",
            "preview": preview,
        }
