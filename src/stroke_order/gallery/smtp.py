"""
gallery/smtp.py — magic-link email delivery.

Two modes:

  * **Dev mode** (``STROKE_ORDER_AUTH_DEV_MODE=true``) — print the
    magic link to stdout + log; no SMTP traffic. Useful when you
    haven't set up an SMTP account yet, or in CI / sandboxes.

  * **Live mode** — talk to an SMTP server using stdlib ``smtplib``
    via ``asyncio.to_thread`` so the FastAPI request handler stays
    async-friendly.

We deliberately avoid third-party libraries (``aiosmtplib`` etc.) to
keep the dependency surface small.
"""
from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

from .config import is_dev_mode


log = logging.getLogger(__name__)


def _smtp_settings() -> dict:
    return {
        "host":      os.environ.get("STROKE_ORDER_SMTP_HOST", "").strip(),
        "port":      int(os.environ.get("STROKE_ORDER_SMTP_PORT", "587")),
        "user":      os.environ.get("STROKE_ORDER_SMTP_USER", "").strip(),
        "password":  os.environ.get("STROKE_ORDER_SMTP_PASS", ""),
        "from_addr": os.environ.get(
            "STROKE_ORDER_SMTP_FROM",
            "stroke-order PSD <noreply@example.com>",
        ).strip(),
    }


def _compose_message(to: str, magic_url: str, settings: dict) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "[stroke-order] 公眾分享庫登入連結"
    msg["From"]    = settings["from_addr"]
    msg["To"]      = to
    body = (
        "您好，\n\n"
        "請點以下連結登入 stroke-order 公眾分享庫：\n\n"
        f"  {magic_url}\n\n"
        "連結 15 分鐘內有效，使用一次後即失效。\n"
        "如果您沒有要求登入，請直接忽略此信。\n\n"
        "— stroke-order PSD\n"
    )
    msg.set_content(body)
    return msg


def _sync_send(msg: EmailMessage, settings: dict) -> None:
    """Run on a worker thread (called via asyncio.to_thread)."""
    host, port = settings["host"], settings["port"]
    if port == 465:
        # Implicit TLS (SMTPS)
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as smtp:
            smtp.login(settings["user"], settings["password"])
            smtp.send_message(msg)
    else:
        # STARTTLS (most providers, port 587)
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(settings["user"], settings["password"])
            smtp.send_message(msg)


async def send_magic_link_email(to: str, magic_url: str) -> None:
    """Send the magic-link email.

    Raises ``RuntimeError`` when not in dev mode and SMTP is not
    configured — propagates upward to a 500 in the API layer with a
    helpful message instead of pretending to send.
    """
    to = (to or "").strip()
    if not to:
        raise ValueError("recipient email is required")

    if is_dev_mode():
        # Dev mode: stdout + log. Don't talk to SMTP at all so this
        # works in sandboxes / CI without any setup.
        banner = (
            "\n"
            "============================================================\n"
            "[stroke-order DEV MODE] Magic-link login\n"
            f"  to:  {to}\n"
            f"  url: {magic_url}\n"
            "============================================================\n"
        )
        print(banner, flush=True)
        log.info("dev-mode magic link issued: to=%s url=%s", to, magic_url)
        return

    settings = _smtp_settings()
    if not settings["host"] or not settings["user"]:
        raise RuntimeError(
            "SMTP is not configured. Set STROKE_ORDER_SMTP_HOST + "
            "STROKE_ORDER_SMTP_USER + STROKE_ORDER_SMTP_PASS, OR set "
            "STROKE_ORDER_AUTH_DEV_MODE=true to print magic links to "
            "the console instead of sending email.",
        )

    msg = _compose_message(to, magic_url, settings)
    await asyncio.to_thread(_sync_send, msg, settings)
    log.info("magic link sent via SMTP: to=%s host=%s", to, settings["host"])
