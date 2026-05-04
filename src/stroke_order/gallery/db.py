"""
gallery/db.py — SQLite schema + connection helper.

Schema is created on first connection (idempotent — `IF NOT EXISTS`).
Per-DB-path init guard avoids re-running the DDL on every connection
in the hot path.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import db_path, gallery_dir, uploads_dir


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT UNIQUE NOT NULL,
    display_name    TEXT,
    bio             TEXT,
    created_at      TEXT NOT NULL,
    last_login_at   TEXT
);

CREATE TABLE IF NOT EXISTS uploads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    comment         TEXT,
    filename        TEXT,
    file_path       TEXT NOT NULL,
    file_size       INTEGER NOT NULL,
    file_hash       TEXT NOT NULL,
    -- Phase 5b r28: 多 upload 種類（psd / mandala / 未來其他）
    kind            TEXT NOT NULL DEFAULT 'psd',
    -- Phase 5b r28: kind-specific summary (JSON dict)，取代硬塞 trace_count
    summary_json    TEXT,
    -- Legacy PSD 專用（5d r5e 階段，保留向後相容；新 kind 改用 summary_json）
    trace_count     INTEGER NOT NULL DEFAULT 0,
    unique_chars    INTEGER NOT NULL DEFAULT 0,
    styles_used     TEXT,           -- JSON array, e.g. ["kaishu","lishu"]
    hidden          INTEGER NOT NULL DEFAULT 0,
    hide_reason     TEXT,
    created_at      TEXT NOT NULL
);

-- Per-user dedup: same hash from same user → reject upload (Phase 5g)
CREATE UNIQUE INDEX IF NOT EXISTS uploads_user_hash
    ON uploads(user_id, file_hash);

-- Cross-user listings: by created_at for the default 'newest' sort
CREATE INDEX IF NOT EXISTS uploads_created_at
    ON uploads(created_at);

-- Phase 5b r28: kind filter（gallery 列表 tabs）
CREATE INDEX IF NOT EXISTS uploads_kind
    ON uploads(kind);

CREATE TABLE IF NOT EXISTS login_tokens (
    token_hash      TEXT PRIMARY KEY,    -- sha256(token), so leaking
                                         -- the DB doesn't reveal usable
                                         -- magic-link URLs
    email           TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    consumed        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS login_tokens_expires
    ON login_tokens(expires_at);

CREATE TABLE IF NOT EXISTS sessions (
    session_token   TEXT PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS sessions_user
    ON sessions(user_id);
CREATE INDEX IF NOT EXISTS sessions_expires
    ON sessions(expires_at);
"""


# Per-process cache of "I've already run the schema on this DB file".
# `set` keyed on str(db_path) so tests can rotate gallery_dir freely.
_schema_initialised: set[str] = set()


def _migrate_uploads_kind_columns(conn: sqlite3.Connection) -> None:
    """Phase 5b r28: 加 `kind` + `summary_json` 給 uploads（existing DB 升版）。

    新建 DB 透過 SCHEMA 已含這兩欄；existing DB（5d / 5g 部署）需 ALTER TABLE
    補上。SQLite ALTER TABLE ADD COLUMN 不支援 IF NOT EXISTS，故先查
    PRAGMA table_info 判斷。

    既有 rows 會因 DEFAULT 'psd' 自動 backfill，無需 UPDATE。
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(uploads)")}
    if "kind" not in cols:
        conn.execute(
            "ALTER TABLE uploads ADD COLUMN kind TEXT NOT NULL DEFAULT 'psd'"
        )
    if "summary_json" not in cols:
        conn.execute("ALTER TABLE uploads ADD COLUMN summary_json TEXT")


def _ensure_schema(path_str: str) -> None:
    if path_str in _schema_initialised:
        return
    # Make the parent directories before opening the DB file.
    gallery_dir().mkdir(parents=True, exist_ok=True)
    uploads_dir().mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path_str)
    try:
        conn.executescript(SCHEMA)
        # r28 migration: existing DB 補 column（idempotent）
        _migrate_uploads_kind_columns(conn)
        conn.commit()
    finally:
        conn.close()
    _schema_initialised.add(path_str)


def _connect() -> sqlite3.Connection:
    p = str(db_path())
    _ensure_schema(p)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    # Enforce FK cascades — sqlite has them off by default.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    """Context-managed SQLite connection. Auto-commits on clean exit."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_schema_cache() -> None:
    """Tests use this when they swap STROKE_ORDER_GALLERY_DIR mid-run
    so the next connection re-creates the schema in the new location."""
    _schema_initialised.clear()
