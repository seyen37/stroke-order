"""Phase 5g — gallery core: db schema + auth + smtp dev mode.

These tests cover the **5g Batch 1** modules in isolation (no FastAPI
endpoints yet — those land in Batch 2). They exercise:

  * gallery.db          — schema initialisation, idempotency, FK on
  * gallery.auth        — token sign/verify roundtrip, magic-link
                           consume one-shot semantics, sessions
  * gallery.smtp        — dev mode console fallback (no SMTP traffic)

Each test redirects gallery storage to a fresh tempdir via env vars
+ ``reset_schema_cache()`` so they're hermetic.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

import pytest


# --------------------------------------------------------------- fixtures

@pytest.fixture
def gallery_env(monkeypatch):
    """Each test gets its own gallery dir + auth secret."""
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("STROKE_ORDER_GALLERY_DIR", td)
        monkeypatch.setenv("STROKE_ORDER_AUTH_SECRET",
                           "test-secret-32-bytes-aaaaaaaaaaaaa")
        monkeypatch.setenv("STROKE_ORDER_BASE_URL", "http://test.local")
        # Force re-init in the new tempdir.
        from stroke_order.gallery.db import reset_schema_cache
        reset_schema_cache()
        yield Path(td)


# =============================================================== db schema

def test_db_schema_creates_all_tables(gallery_env):
    from stroke_order.gallery.db import db_connection
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "ORDER BY name",
        ).fetchall()
    names = sorted(r["name"] for r in rows
                   if not r["name"].startswith("sqlite_"))
    assert names == ["login_tokens", "sessions", "uploads", "users"]


def test_db_unique_email_constraint(gallery_env):
    from stroke_order.gallery.db import db_connection
    import sqlite3
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO users (email, created_at) VALUES (?, ?)",
            ("a@example.com", "2026-04-26T00:00:00+00:00"),
        )
    with pytest.raises(sqlite3.IntegrityError):
        with db_connection() as conn:
            conn.execute(
                "INSERT INTO users (email, created_at) VALUES (?, ?)",
                ("a@example.com", "2026-04-26T00:00:01+00:00"),
            )


def test_db_uploads_per_user_hash_dedup(gallery_env):
    """Same user + same file_hash → unique-index rejects duplicate."""
    from stroke_order.gallery.db import db_connection
    import sqlite3
    with db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, created_at) VALUES (?, ?)",
            ("a@example.com", "2026-04-26T00:00:00+00:00"),
        )
        uid = cur.lastrowid
        conn.execute(
            "INSERT INTO uploads "
            "(user_id, title, file_path, file_size, file_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "T1", "/p/1.json", 100, "deadbeef" * 8,
             "2026-04-26T00:00:00+00:00"),
        )
    with pytest.raises(sqlite3.IntegrityError):
        with db_connection() as conn:
            conn.execute(
                "INSERT INTO uploads "
                "(user_id, title, file_path, file_size, file_hash, "
                " created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (uid, "T2-different-title", "/p/2.json", 100,
                 "deadbeef" * 8, "2026-04-26T00:00:01+00:00"),
            )


def test_db_init_is_idempotent(gallery_env):
    from stroke_order.gallery.db import db_connection
    # Open & close many times; schema should still be one of each.
    for _ in range(3):
        with db_connection() as conn:
            assert conn.execute(
                "SELECT count(*) FROM sqlite_master "
                "WHERE type='table' AND name='users'"
            ).fetchone()[0] == 1


# ============================================================ token format

def test_sign_verify_roundtrip(gallery_env):
    from stroke_order.gallery.auth import sign_token, verify_token
    payload = {"x": 1, "y": "hello", "exp": int(time.time()) + 60}
    tok = sign_token(payload)
    assert tok.count(".") == 1
    out = verify_token(tok)
    assert out is not None
    assert out["x"] == 1
    assert out["y"] == "hello"


def test_verify_rejects_tampered_payload(gallery_env):
    from stroke_order.gallery.auth import sign_token, verify_token
    tok = sign_token({"a": 1, "exp": int(time.time()) + 60})
    body, sig = tok.rsplit(".", 1)
    # Flip a body character; signature now mismatches
    bad = body[:-1] + ("X" if body[-1] != "X" else "Y") + "." + sig
    assert verify_token(bad) is None


def test_verify_rejects_expired(gallery_env):
    from stroke_order.gallery.auth import sign_token, verify_token
    tok = sign_token({"a": 1, "exp": int(time.time()) - 5})
    assert verify_token(tok) is None


def test_verify_rejects_garbage(gallery_env):
    from stroke_order.gallery.auth import verify_token
    for bad in ["", "x", "x.y", "....", "no-dot-at-all", None]:
        assert verify_token(bad) is None


# =========================================================== magic link

def test_magic_link_consume_creates_user(gallery_env):
    from stroke_order.gallery.auth import (
        make_login_token, consume_login_token,
    )
    from stroke_order.gallery.db import db_connection

    token = make_login_token("Alice@Example.COM")     # mixed case → normalised
    user_id = consume_login_token(token)
    assert isinstance(user_id, int) and user_id > 0
    # User row created, email lower-cased
    with db_connection() as conn:
        row = conn.execute(
            "SELECT email, last_login_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    assert row["email"] == "alice@example.com"
    assert row["last_login_at"] is not None


def test_magic_link_one_shot(gallery_env):
    """Same token consumed twice → second call must fail."""
    from stroke_order.gallery.auth import (
        make_login_token, consume_login_token,
    )
    token = make_login_token("a@example.com")
    assert consume_login_token(token) is not None     # first OK
    assert consume_login_token(token) is None         # second blocked


def test_magic_link_returning_user_keeps_id(gallery_env):
    from stroke_order.gallery.auth import (
        make_login_token, consume_login_token,
    )
    uid1 = consume_login_token(make_login_token("a@example.com"))
    uid2 = consume_login_token(make_login_token("a@example.com"))
    assert uid1 == uid2     # same email → same row


def test_magic_link_forged_token_rejected(gallery_env):
    """A signed token whose hash isn't in login_tokens (e.g. attacker
    forged with the secret somehow leaked) is rejected."""
    from stroke_order.gallery.auth import (
        sign_token, consume_login_token,
    )
    # Pretend we own the secret and craft a token directly — never
    # routed through make_login_token, so no DB row.
    forged = sign_token({
        "email": "evil@example.com",
        "exp": int(time.time()) + 600,
        "purp": "login",
        "n":    "deadbeef",
    })
    assert consume_login_token(forged) is None


def test_magic_link_url_uses_base_url(gallery_env):
    from stroke_order.gallery.auth import (
        make_login_token, magic_link_url,
    )
    token = make_login_token("a@example.com")
    url = magic_link_url(token)
    assert url.startswith("http://test.local/api/gallery/auth/consume?")
    assert "token=" in url


# ============================================================ sessions

def test_session_create_resolve_invalidate(gallery_env):
    from stroke_order.gallery.auth import (
        make_login_token, consume_login_token,
        create_session, get_session_user, invalidate_session,
    )
    uid = consume_login_token(make_login_token("a@example.com"))
    assert uid is not None

    sess = create_session(uid)
    assert isinstance(sess, str) and len(sess) > 20

    user = get_session_user(sess)
    assert user is not None
    assert user["id"] == uid
    assert user["email"] == "a@example.com"

    invalidate_session(sess)
    assert get_session_user(sess) is None


def test_session_unknown_token_returns_none(gallery_env):
    from stroke_order.gallery.auth import get_session_user
    assert get_session_user(None) is None
    assert get_session_user("") is None
    assert get_session_user("nonexistent") is None


def test_purge_expired(gallery_env):
    """purge_expired sweeps the login_tokens + sessions tables."""
    from stroke_order.gallery.auth import purge_expired
    from stroke_order.gallery.db import db_connection

    past   = "2020-01-01T00:00:00+00:00"
    future = "2099-01-01T00:00:00+00:00"

    with db_connection() as conn:
        conn.execute(
            "INSERT INTO login_tokens "
            "(token_hash, email, expires_at, consumed) "
            "VALUES (?, ?, ?, 0)",
            ("h-old", "a@example.com", past),
        )
        conn.execute(
            "INSERT INTO login_tokens "
            "(token_hash, email, expires_at, consumed) "
            "VALUES (?, ?, ?, 0)",
            ("h-new", "a@example.com", future),
        )
        cur = conn.execute(
            "INSERT INTO users (email, created_at) VALUES (?, ?)",
            ("a@example.com", past),
        )
        uid = cur.lastrowid
        conn.execute(
            "INSERT INTO sessions "
            "(session_token, user_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            ("s-old", uid, past, past),
        )
        conn.execute(
            "INSERT INTO sessions "
            "(session_token, user_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            ("s-new", uid, past, future),
        )

    out = purge_expired()
    assert out == {"login_tokens": 1, "sessions": 1}

    with db_connection() as conn:
        assert conn.execute(
            "SELECT count(*) FROM login_tokens",
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT count(*) FROM sessions",
        ).fetchone()[0] == 1


# ============================================================ smtp dev mode

def test_smtp_dev_mode_prints_to_stdout(gallery_env, monkeypatch):
    """The project doesn't ship pytest-asyncio; we drive async funcs
    via asyncio.run rather than adding a dev dependency."""
    monkeypatch.setenv("STROKE_ORDER_AUTH_DEV_MODE", "true")
    from stroke_order.gallery.smtp import send_magic_link_email
    buf = io.StringIO()
    with redirect_stdout(buf):
        asyncio.run(send_magic_link_email(
            "a@example.com", "http://test.local/x?token=abc",
        ))
    out = buf.getvalue()
    assert "DEV MODE" in out
    assert "a@example.com" in out
    assert "http://test.local/x?token=abc" in out


def test_smtp_live_mode_without_config_raises(gallery_env, monkeypatch):
    """Without SMTP config + dev mode off → must raise with clear msg
    rather than silently swallowing the email."""
    monkeypatch.delenv("STROKE_ORDER_AUTH_DEV_MODE", raising=False)
    monkeypatch.delenv("STROKE_ORDER_SMTP_HOST", raising=False)
    monkeypatch.delenv("STROKE_ORDER_SMTP_USER", raising=False)
    from stroke_order.gallery.smtp import send_magic_link_email
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(send_magic_link_email("a@example.com", "http://x"))
    msg = str(exc.value)
    assert "STROKE_ORDER_SMTP" in msg
    assert "STROKE_ORDER_AUTH_DEV_MODE" in msg


# ============================================================ end-to-end

def test_end_to_end_auth_flow(gallery_env, monkeypatch):
    """Magic-link issuance → email (dev mode) → consume → session."""
    monkeypatch.setenv("STROKE_ORDER_AUTH_DEV_MODE", "true")

    from stroke_order.gallery.auth import (
        make_login_token, magic_link_url, consume_login_token,
        create_session, get_session_user,
    )
    from stroke_order.gallery.smtp import send_magic_link_email

    # 1. user types email → server makes token + 'sends' email
    token = make_login_token("a@example.com")
    url = magic_link_url(token)
    buf = io.StringIO()
    with redirect_stdout(buf):
        asyncio.run(send_magic_link_email("a@example.com", url))
    assert token in buf.getvalue()

    # 2. user clicks link → server consumes → session created
    uid = consume_login_token(token)
    sess = create_session(uid)

    # 3. browser sends session cookie → server resolves
    user = get_session_user(sess)
    assert user["email"] == "a@example.com"
