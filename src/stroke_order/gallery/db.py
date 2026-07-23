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
    -- Phase 5b r29j: 頭像檔路徑（NULL = 用 initials fallback）
    -- 實際檔存 gallery_dir/avatars/<user_id>.png（256x256 PNG）
    avatar_path     TEXT,
    -- 5fx: 作者治理狀態（normal / review / blacklisted）
    --   review      → 該作者新上傳先隱藏（pending-review），管理員放行才公開
    --   blacklisted → 禁止上傳；勾選當下既有作品全部隱藏
    moderation_status TEXT NOT NULL DEFAULT 'normal',
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

-- Phase 5b r29: 公眾分享庫 like 機制
-- (user_id, upload_id) UNIQUE PK 自動 dedup（同 user × upload 只能 like 一次）
-- ON DELETE CASCADE 給 user / upload 任一邊刪除時自動清 like row
CREATE TABLE IF NOT EXISTS likes (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    upload_id  INTEGER NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, upload_id)
);

-- 列表 / detail 查 like_count 用（COUNT WHERE upload_id = ?）
CREATE INDEX IF NOT EXISTS likes_upload
    ON likes(upload_id);

-- Phase 5b r29b: 私人 bookmark 收藏（mirror likes 結構）
-- (user_id, upload_id) UNIQUE PK 自動 dedup
-- ON DELETE CASCADE 給 user / upload 任一邊刪除時自動清 bookmark row
CREATE TABLE IF NOT EXISTS bookmarks (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    upload_id  INTEGER NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, upload_id)
);

-- 「我的收藏」list: 給 user 撈自己 bookmark 的 upload list 用
CREATE INDEX IF NOT EXISTS bookmarks_user
    ON bookmarks(user_id);

-- 5fx: 檢舉（匿名＋登入皆可；threshold 自動隱藏）
--   reporter_user_id NULL ＝ 匿名件；匿名件以 reporter_ip_hash（加鹽
--   SHA-256，不存明文 IP）去重。部分唯一索引：登入件同人同作品一次、
--   匿名件同 IP 同作品一次。
CREATE TABLE IF NOT EXISTS reports (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id        INTEGER NOT NULL REFERENCES uploads(id)
                         ON DELETE CASCADE,
    reporter_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reporter_ip_hash TEXT,
    reason           TEXT NOT NULL,
    detail           TEXT,
    created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS reports_upload
    ON reports(upload_id);
CREATE INDEX IF NOT EXISTS reports_created
    ON reports(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS reports_dedup_user
    ON reports(upload_id, reporter_user_id)
    WHERE reporter_user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS reports_dedup_ip
    ON reports(upload_id, reporter_ip_hash)
    WHERE reporter_user_id IS NULL AND reporter_ip_hash IS NOT NULL;
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


def _migrate_users_moderation(conn: sqlite3.Connection) -> None:
    """5fx: 加 ``moderation_status`` 給 users（existing DB 升版）。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    if "moderation_status" not in cols:
        conn.execute(
            "ALTER TABLE users ADD COLUMN moderation_status TEXT "
            "NOT NULL DEFAULT 'normal'"
        )


def _migrate_users_avatar(conn: sqlite3.Connection) -> None:
    """Phase 5b r29j: 加 ``avatar_path`` 給 users（existing DB 升版）。

    新建 DB 透過 SCHEMA 已含；existing DB（pre-r29j 部署）需 ALTER TABLE
    補上。NULL 表示無 avatar，frontend 走 initials fallback。
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    if "avatar_path" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_path TEXT")


def _ensure_schema(path_str: str) -> None:
    if path_str in _schema_initialised:
        return
    # Make the parent directories before opening the DB file.
    gallery_dir().mkdir(parents=True, exist_ok=True)
    uploads_dir().mkdir(parents=True, exist_ok=True)
    # Phase 5b r29j: 頭像目錄（每 user 一張 256x256 PNG）
    (gallery_dir() / "avatars").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path_str)
    try:
        conn.executescript(SCHEMA)
        # r28 migration: existing DB 補 column（idempotent）
        _migrate_uploads_kind_columns(conn)
        # r29j migration: existing DB 補 avatar_path（idempotent）
        _migrate_users_avatar(conn)
        # 5fx migration: existing DB 補 moderation_status（idempotent）
        _migrate_users_moderation(conn)
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
