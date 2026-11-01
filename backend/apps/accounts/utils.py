"""
Communication utilities for account verification and password reset.

Sends OTP codes via email (real SMTP or console backend in dev) and logs SMS
OTPs to the console (mock/dev-only provider — no real SMS gateway configured).
"""

import logging
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

OTP_CODE_LENGTH = getattr(settings, "OTP_CODE_LENGTH", 6)


def generate_otp(length=OTP_CODE_LENGTH):
    """Generate a numeric OTP code of the given length."""
    return "".join(secrets.choice("0123456789") for _ in range(length))


def send_otp_email(identifier, code, purpose, context=None):
    """
    Send an OTP code via email.

    Uses Django's configured email backend. In development with the console
    backend, the message is printed to stdout.
    """
    context = context or {}
    context.update({
        "identifier": identifier,
        "code": code,
        "purpose": purpose,
        "site_name": getattr(settings, "SITE_NAME", "FineFit"),
    })

    subject = f"[{context['site_name']}] Your {purpose} code is {code}"
    html_message = render_to_string("accounts/emails/otp_email.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@finefit.store"),
            recipient_list=[identifier],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info("OTP email sent to %s (purpose=%s)", identifier, purpose)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send OTP email to %s: %s", identifier, exc)
        return False


def send_reset_email(identifier, reset_url, context=None):
    """
    Send a password reset link via email.
    """
    context = context or {}
    context.update({
        "identifier": identifier,
        "reset_url": reset_url,
        "site_name": getattr(settings, "SITE_NAME", "FineFit"),
    })

    subject = f"[{context['site_name']}] Reset your password"
    html_message = render_to_string("accounts/emails/reset_email.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@finefit.store"),
            recipient_list=[identifier],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info("Reset email sent to %s", identifier)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send reset email to %s: %s", identifier, exc)
        return False


def send_otp_sms(identifier, code, purpose):
    """
    Send an OTP code via SMS (mock/dev-only).

    Logs the code to the console. No real SMS gateway is configured.
    Production must replace this with a real provider (e.g. Twilio).
    """
    logger.info("=" * 60)
    logger.info("MOCK SMS to %s", identifier)
    logger.info("Purpose: %s", purpose)
    logger.info("OTP Code: %s", code)
    logger.info("=" * 60)
    return True


def mask_email(email):
    """Mask an email address for display (e.g. e***@f****.com)."""
    if not email or "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    if len(local) <= 1:
        masked_local = local
    else:
        masked_local = local[0] + "*" * (len(local) - 1)
    return f"{masked_local}@{domain}"


def mask_phone(phone):
    """Mask a phone number for display (e.g. +1*******5678)."""
    if not phone:
        return phone
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) <= 4:
        return phone
    return "+" + "*" * (len(digits) - 4) + digits[-4:]
