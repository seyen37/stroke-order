"""
gallery/auth.py — magic-link token + session management.

Design choices
--------------
* **No PyJWT / no third-party auth library.** We sign tokens with
  HMAC-SHA256 using stdlib ``hmac`` + ``base64``. Format is
  ``<base64url(payload)>.<base64url(sig)>`` — 25-line equivalent of
  JWT's HS256 mode, without the spec's footguns (no ``alg=none``,
  no key confusion).

* **One-shot magic links.** Even though the HMAC signature would
  let a token be replayed until it expires, we additionally record
  every issued token's hash in ``login_tokens`` and refuse a token
  whose row is already ``consumed``. So a leaked link in a browser
  history can be used at most once.

* **Random session tokens, server-side state.** Sessions are stored
  in SQLite (not signed JWTs) so revocation is a single DELETE.

Public API
----------
    make_login_token(email)        → opaque str (the magic-link token)
    magic_link_url(token)          → full URL the user should click
    consume_login_token(token)     → user_id or None
    create_session(user_id)        → opaque session_token
    get_session_user(session_token) → dict | None
    invalidate_session(session_token)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from .config import auth_secret, base_url
from .db import db_connection


LOGIN_TOKEN_TTL_SEC = 15 * 60               # 15 minutes
SESSION_TTL_SEC     = 30 * 24 * 60 * 60     # 30 days


# ---------------------------------------------------------------- HMAC tokens

def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def sign_token(payload: dict) -> str:
    """HMAC-SHA256-sign a JSON payload. Returns ``<body>.<sig>``."""
    body = _b64u(json.dumps(payload, separators=(",", ":"),
                            sort_keys=True).encode("utf-8"))
    sig = hmac.new(auth_secret(), body.encode("ascii"),
                   hashlib.sha256).digest()
    return body + "." + _b64u(sig)


def verify_token(token: str) -> Optional[dict]:
    """Verify HMAC + expiry. Returns the payload dict or None."""
    if not token or "." not in token:
        return None
    try:
        body, sig_b64 = token.rsplit(".", 1)
        expected = hmac.new(auth_secret(), body.encode("ascii"),
                            hashlib.sha256).digest()
        provided = _b64u_decode(sig_b64)
    except Exception:
        return None
    if not hmac.compare_digest(expected, provided):
        return None
    try:
        payload = json.loads(_b64u_decode(body).decode("utf-8"))
    except Exception:
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < time.time():
        return None
    return payload


# ------------------------------------------------------------- magic links

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalise_email(email: str) -> str:
    return (email or "").strip().lower()


def make_login_token(email: str) -> str:
    """Sign a fresh magic-link token + record its hash in login_tokens
    so consume can mark it one-shot."""
    email = _normalise_email(email)
    if not email or "@" not in email:
        raise ValueError("invalid email")

    payload = {
        "email": email,
        "exp":   int(time.time()) + LOGIN_TOKEN_TTL_SEC,
        "purp":  "login",
        # Random nonce so two tokens issued to the same email back-to-
        # back are distinct (otherwise they'd HMAC to the same string
        # and only the first would survive the UNIQUE token_hash key).
        "n":     secrets.token_urlsafe(8),
    }
    token = sign_token(payload)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.fromtimestamp(
        payload["exp"], tz=timezone.utc).isoformat(timespec="seconds")

    with db_connection() as conn:
        conn.execute(
            "INSERT INTO login_tokens "
            "(token_hash, email, expires_at, consumed) "
            "VALUES (?, ?, ?, 0)",
            (token_hash, email, expires_at),
        )
    return token


def magic_link_url(token: str) -> str:
    return f"{base_url()}/api/gallery/auth/consume?token={token}"


def consume_login_token(token: str) -> Optional[int]:
    """Validate the magic-link token, mark it consumed, find-or-create
    the user, return user_id. Returns None on any failure (forged /
    expired / already consumed / unknown)."""
    payload = verify_token(token)
    if not payload or payload.get("purp") != "login":
        return None
    email = _normalise_email(payload.get("email", ""))
    if not email:
        return None

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = _utcnow_iso()

    with db_connection() as conn:
        row = conn.execute(
            "SELECT consumed FROM login_tokens WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
        if row is None:
            # Forged: HMAC verifies but we never issued this exact token.
            return None
        if row["consumed"]:
            return None
        conn.execute(
            "UPDATE login_tokens SET consumed = 1 WHERE token_hash = ?",
            (token_hash,),
        )

        user_row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,),
        ).fetchone()
        if user_row is None:
            cur = conn.execute(
                "INSERT INTO users (email, created_at, last_login_at) "
                "VALUES (?, ?, ?)",
                (email, now, now),
            )
            return cur.lastrowid
        else:
            user_id = user_row["id"]
            conn.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?",
                (now, user_id),
            )
            return user_id


# --------------------------------------------------------------- sessions

def create_session(user_id: int) -> str:
    """Issue a 30-day session token for ``user_id``. Returns the
    opaque token (hand to the browser as an httpOnly cookie)."""
    session_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=SESSION_TTL_SEC)
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO sessions "
            "(session_token, user_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (session_token, user_id,
             now.isoformat(timespec="seconds"),
             expires.isoformat(timespec="seconds")),
        )
    return session_token


def get_session_user(session_token: Optional[str]) -> Optional[dict]:
    """Resolve session_token → user record (id, email, display_name,
    bio, created_at, avatar_url) or None if invalid/expired.

    Phase 5b r29j: 多帶 avatar_url（None 若無 avatar；否則 cache-busted URL）。
    """
    if not session_token:
        return None
    now = _utcnow_iso()
    with db_connection() as conn:
        row = conn.execute(
            "SELECT u.id, u.email, u.display_name, u.bio, u.created_at, "
            "       u.avatar_path "
            "FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.session_token = ? AND s.expires_at > ?",
            (session_token, now),
        ).fetchone()
        if not row:
            return None
        # delayed import 避免 service ↔ auth 環依賴
        from .service import _user_dict_with_avatar
        return _user_dict_with_avatar(row)


def invalidate_session(session_token: Optional[str]) -> None:
    """Log out: delete the session row. No-op if token is empty."""
    if not session_token:
        return
    with db_connection() as conn:
        conn.execute(
            "DELETE FROM sessions WHERE session_token = ?",
            (session_token,),
        )


# --------------------------------------------------------------- maintenance

def purge_expired() -> dict:
    """Sweep expired login_tokens + sessions. Returns counts removed.
    Cheap to call; safe to invoke at server startup."""
    now = _utcnow_iso()
    with db_connection() as conn:
        c1 = conn.execute(
            "DELETE FROM login_tokens WHERE expires_at < ?", (now,),
        ).rowcount
        c2 = conn.execute(
            "DELETE FROM sessions WHERE expires_at < ?", (now,),
        ).rowcount
    return {"login_tokens": c1, "sessions": c2}
