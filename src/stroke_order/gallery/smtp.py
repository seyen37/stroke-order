"""
gallery/smtp.py — magic-link email delivery.

Three modes（優先序由上而下）：

  * **Dev mode** (``STROKE_ORDER_AUTH_DEV_MODE=true``) — print the
    magic link to stdout + log; no network traffic. Useful when you
    haven't set up email yet, or in CI / sandboxes.

  * **Brevo HTTP API**（5fz，``STROKE_ORDER_BREVO_API_KEY`` 有值時）
    — 走 HTTPS 443 POST https://api.brevo.com/v3/smtp/email。
    **Render 免費層封鎖所有對外 SMTP 埠（25/465/587）**，傳統 SMTP
    連不出去（Errno 101 Network is unreachable）；HTTP 郵件 API 是
    免費層唯一可行的寄信通道。寄件人 email 沿用
    ``STROKE_ORDER_SMTP_FROM``（必須是 Brevo 後台驗證過的 sender）。

  * **SMTP fallback** — talk to an SMTP server using stdlib
    ``smtplib``（自架或付費層可用）。

皆經 ``asyncio.to_thread`` 保持 async-friendly。We deliberately avoid
third-party libraries (``aiosmtplib``/``requests`` etc.) to keep the
dependency surface small——Brevo 呼叫用 stdlib ``urllib.request``。
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


def _brevo_api_key() -> str:
    return os.environ.get("STROKE_ORDER_BREVO_API_KEY", "").strip()


def _parse_from_addr(from_addr: str) -> tuple[str, str]:
    """``"Name <a@b.c>"`` → ``("Name", "a@b.c")``；裸 email → 名稱同值。"""
    fa = (from_addr or "").strip()
    if "<" in fa and fa.endswith(">"):
        name, _, rest = fa.partition("<")
        return name.strip() or rest[:-1].strip(), rest[:-1].strip()
    return fa, fa


def _sync_send_brevo(to: str, subject: str, body: str,
                     settings: dict) -> None:
    """Brevo transactional email API（stdlib urllib；worker thread）。

    成功＝2xx（實務上 201）；非 2xx 或網路錯誤 raise RuntimeError
    帶可讀訊息（API 層轉 500）。
    """
    import json as _json
    import urllib.error
    import urllib.request

    sender_name, sender_email = _parse_from_addr(settings["from_addr"])
    payload = _json.dumps({
        "sender": {"name": sender_name or "stroke-order",
                   "email": sender_email},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={
            "api-key": _brevo_api_key(),
            "content-type": "application/json",
            "accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if not (200 <= resp.status < 300):
                raise RuntimeError(
                    f"Brevo API 非預期回應：HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise RuntimeError(
            f"Brevo 寄信失敗：HTTP {e.code}。常見原因：API key 錯誤、"
            f"寄件人 email 未在 Brevo 驗證"
            f"（STROKE_ORDER_SMTP_FROM={settings['from_addr']!r}）。"
            f"回應：{detail}",
        ) from None
    except OSError as e:
        raise RuntimeError(f"Brevo 連線失敗：{e}") from None


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

    # 5fz：Brevo HTTP API 優先於 SMTP——Render 免費層封鎖對外 SMTP 埠，
    # HTTPS 443 的郵件 API 是免費層唯一能寄信的通道。
    if _brevo_api_key():
        msg = _compose_message(to, magic_url, settings)
        await asyncio.to_thread(
            _sync_send_brevo, to, str(msg["Subject"]),
            msg.get_content(), settings)
        log.info("magic link sent via Brevo API: to=%s", to)
        return

    if not settings["host"] or not settings["user"]:
        raise RuntimeError(
            "Email is not configured. Set STROKE_ORDER_BREVO_API_KEY "
            "(HTTP API — works on Render free tier where outbound SMTP "
            "is blocked), OR STROKE_ORDER_SMTP_HOST + "
            "STROKE_ORDER_SMTP_USER + STROKE_ORDER_SMTP_PASS, OR "
            "STROKE_ORDER_AUTH_DEV_MODE=true to print magic links to "
            "the console instead of sending email.",
        )

    msg = _compose_message(to, magic_url, settings)
    await asyncio.to_thread(_sync_send, msg, settings)
    log.info("magic link sent via SMTP: to=%s host=%s", to, settings["host"])
