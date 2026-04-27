"""
gallery/config.py — environment-variable–driven runtime configuration.

All values are read on every call (no caching) so tests can monkey-patch
``os.environ`` to reroute storage or flip dev mode within a single
process.

Required env vars
-----------------
    STROKE_ORDER_AUTH_SECRET   — HMAC key for signing tokens. MUST be
                                  set in production (>= 32 bytes); a
                                  hard-coded dev fallback prints a
                                  warning otherwise.

Optional env vars
-----------------
    STROKE_ORDER_GALLERY_DIR   — root for SQLite + uploaded files.
                                  Default ~/.stroke-order/gallery
    STROKE_ORDER_BASE_URL      — base URL for magic-link callbacks.
                                  Default http://127.0.0.1:8000
    STROKE_ORDER_AUTH_DEV_MODE — when truthy, magic-link prints to
                                  console + log instead of sending email.
                                  Default off.
    STROKE_ORDER_SMTP_HOST/PORT/USER/PASS/FROM — when not in dev mode.
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path


_TRUE_STRINGS = {"1", "true", "yes", "on", "y", "t"}


def gallery_dir() -> Path:
    raw = os.environ.get("STROKE_ORDER_GALLERY_DIR",
                         "~/.stroke-order/gallery")
    return Path(raw).expanduser()


def db_path() -> Path:
    return gallery_dir() / "gallery.db"


def uploads_dir() -> Path:
    return gallery_dir() / "uploads"


def base_url() -> str:
    return os.environ.get("STROKE_ORDER_BASE_URL",
                          "http://127.0.0.1:8000").rstrip("/")


def is_dev_mode() -> bool:
    return os.environ.get("STROKE_ORDER_AUTH_DEV_MODE",
                          "").strip().lower() in _TRUE_STRINGS


# Sentinel logged once per process so the warning isn't spammy.
_warned_no_secret = False


def auth_secret() -> bytes:
    """HMAC key. **Never** hard-code in production: set
    STROKE_ORDER_AUTH_SECRET (e.g. ``openssl rand -hex 32``).

    A constant fallback is provided for dev/test convenience but issues
    a one-shot warning so nobody accidentally ships it.
    """
    global _warned_no_secret
    raw = os.environ.get("STROKE_ORDER_AUTH_SECRET", "").strip()
    if raw:
        return raw.encode("utf-8")
    if not _warned_no_secret:
        warnings.warn(
            "STROKE_ORDER_AUTH_SECRET is unset — using an INSECURE "
            "default. Set it before deploying to production.",
            stacklevel=2,
        )
        _warned_no_secret = True
    # 32-byte deterministic key; safe only because magic-link tokens are
    # also one-shot via the login_tokens table.
    return b"stroke-order-dev-only-secret-key!!"
