"""
gallery/service.py — upload / list / get / delete business logic.

Responsibilities
----------------
* Validate uploaded JSON against the 5d PSD schema (`stroke-order-psd-v1`).
* Enforce upload limits: file size ≤ 10 MB, ≤ 20 / user / day,
  per-user file_hash dedup.
* Compute summary stats (trace_count, unique_chars, styles_used) for
  list-page display.
* Manage on-disk file storage at ``<gallery_dir>/uploads/<user>/<file>.json``.
* Provide paginated listing + per-upload metadata + download path.

This module is the single place that touches the filesystem for
uploaded blobs. The FastAPI endpoint layer (Phase 5g-5) calls this
module and never reaches into ``uploads_dir()`` directly.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import uploads_dir
from .db import db_connection


# ----------------------------------------------------------- constants

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024     # 10 MB
MAX_TITLE_LEN       = 50                   # chars
MAX_COMMENT_LEN     = 200                  # chars
DAILY_UPLOAD_LIMIT  = 20                   # uploads / user / 24h
PSD_SCHEMA_TAG      = "stroke-order-psd-v1"

DEFAULT_PAGE_SIZE   = 20
MAX_PAGE_SIZE       = 100


# ----------------------------------------------------------- exceptions

class GalleryError(Exception):
    """Base for service-layer errors. ``code`` is HTTP-status-friendly."""
    code = 400
    def __init__(self, message: str):
        super().__init__(message)


class InvalidUpload(GalleryError):
    """Bad upload payload (size, JSON, schema, etc)."""
    code = 422


class DuplicateUpload(GalleryError):
    """Same user already uploaded a file with this exact content hash."""
    code = 409


class RateLimited(GalleryError):
    """Too many uploads in the rolling 24h window."""
    code = 429


class NotFound(GalleryError):
    code = 404


class Forbidden(GalleryError):
    code = 403


# ----------------------------------------------------------- helpers

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_unicode_str(value, max_len: int, *, name: str) -> str:
    """Trim & length-check a string field. Raise InvalidUpload on bust."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise InvalidUpload(f"{name} must be text")
    s = value.strip()
    if len(s) > max_len:
        raise InvalidUpload(f"{name} 過長（最多 {max_len} 字）")
    return s


def _user_uploads_dir(user_id: int) -> Path:
    p = uploads_dir() / str(user_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ----------------------------------------------------------- validators

def parse_and_validate_psd(content_bytes: bytes) -> dict:
    """Parse the JSON content + assert it's a 5d PSD export.

    Returns the parsed dict on success; raises ``InvalidUpload``
    otherwise. The exception message is in 中文 — surfaced straight
    to the user.
    """
    if len(content_bytes) == 0:
        raise InvalidUpload("檔案是空的")
    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        raise InvalidUpload(
            f"檔案過大 ({len(content_bytes) / 1024 / 1024:.1f} MB)；"
            f"上限 {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB",
        )
    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidUpload("檔案不是 UTF-8 編碼") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise InvalidUpload(f"JSON 解析失敗：{e.msg}") from None
    if not isinstance(data, dict):
        raise InvalidUpload("JSON 必須是 object（{...}）")
    if data.get("schema") != PSD_SCHEMA_TAG:
        raise InvalidUpload(
            f"不支援的 schema：{data.get('schema')!r}；"
            f"需 {PSD_SCHEMA_TAG}（請從 /handwriting 匯出）",
        )
    traces = data.get("traces")
    if not isinstance(traces, list):
        raise InvalidUpload("JSON 缺少 traces 陣列")
    if len(traces) == 0:
        raise InvalidUpload("traces 陣列是空的；無法上傳沒有筆順的檔案")
    return data


def summarise_traces(psd: dict) -> dict:
    """Compute trace_count / unique_chars / styles_used for the list
    page. Defensive: doesn't trust caller to supply a clean PSD —
    just extracts what it can."""
    traces = psd.get("traces") or []
    chars = set()
    styles = set()
    for t in traces:
        if not isinstance(t, dict):
            continue
        ch = t.get("char")
        if isinstance(ch, str) and ch:
            chars.add(ch)
        st = t.get("style")
        if isinstance(st, str) and st:
            styles.add(st)
    return {
        "trace_count":  len(traces),
        "unique_chars": len(chars),
        "styles_used":  sorted(styles),
    }


def file_hash_sha256(content_bytes: bytes) -> str:
    """Hex digest used to dedup uploads + (Phase 5h) for the
    cross-user duplicate-detection heuristic."""
    return hashlib.sha256(content_bytes).hexdigest()


# ----------------------------------------------------------- rate limit

def daily_upload_count(user_id: int) -> int:
    """Number of upload rows the user has created in the last 24h."""
    cutoff_iso = (
        datetime.now(timezone.utc) - _ONE_DAY
    ).isoformat(timespec="seconds")
    with db_connection() as conn:
        row = conn.execute(
            "SELECT count(*) AS n FROM uploads "
            "WHERE user_id = ? AND created_at > ?",
            (user_id, cutoff_iso),
        ).fetchone()
    return int(row["n"]) if row else 0


from datetime import timedelta as _td
_ONE_DAY = _td(hours=24)


# ----------------------------------------------------------- create

def create_upload(
    *, user_id: int, content_bytes: bytes, filename: Optional[str],
    title: str, comment: str,
) -> dict:
    """Validate + persist an uploaded PSD JSON. Returns the new
    upload's full record dict.

    Raises:
        InvalidUpload    — schema / size / format problem
        DuplicateUpload  — same hash already uploaded by this user
        RateLimited      — > 20 uploads in last 24h
    """
    title   = _safe_unicode_str(title,   MAX_TITLE_LEN,   name="title")
    comment = _safe_unicode_str(comment, MAX_COMMENT_LEN, name="comment")
    if not title:
        raise InvalidUpload("title 不可空白")

    if daily_upload_count(user_id) >= DAILY_UPLOAD_LIMIT:
        raise RateLimited(
            f"每日上傳上限 {DAILY_UPLOAD_LIMIT} 次，請明天再試",
        )

    # Validate schema first — cheap-fails before we touch disk.
    psd = parse_and_validate_psd(content_bytes)
    summary = summarise_traces(psd)
    file_hash = file_hash_sha256(content_bytes)

    # Pre-check the per-user uniqueness (the DB UNIQUE INDEX is the
    # ultimate guard, but we want a friendly error rather than a raw
    # IntegrityError).
    with db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM uploads WHERE user_id = ? AND file_hash = ?",
            (user_id, file_hash),
        ).fetchone()
        if row is not None:
            raise DuplicateUpload(
                "您已上傳過內容完全相同的檔案（id = "
                f"{row['id']}）",
            )

    # Generate the on-disk filename now (before we know the upload id);
    # using a UUID avoids needing the autoincrement id to write.
    nonce = secrets.token_hex(8)
    rel_path = Path(str(user_id)) / f"{nonce}.json"
    abs_path = uploads_dir() / rel_path
    _user_uploads_dir(user_id)         # ensure parent exists
    abs_path.write_bytes(content_bytes)

    safe_filename = (filename or "").strip()[:200] or "upload.json"

    try:
        with db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO uploads "
                "(user_id, title, comment, filename, file_path, "
                " file_size, file_hash, trace_count, unique_chars, "
                " styles_used, hidden, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                (
                    user_id, title, comment, safe_filename, str(rel_path),
                    len(content_bytes), file_hash,
                    summary["trace_count"], summary["unique_chars"],
                    json.dumps(summary["styles_used"]),
                    _utcnow_iso(),
                ),
            )
            upload_id = cur.lastrowid
    except Exception:
        # DB insert failed — clean up the orphan file.
        try:
            abs_path.unlink()
        except FileNotFoundError:
            pass
        raise

    return get_upload(upload_id)


# ----------------------------------------------------------- read

def get_upload(upload_id: int) -> dict:
    """Single upload's full record (joined with uploader display info).
    Raises NotFound."""
    with db_connection() as conn:
        row = conn.execute(
            "SELECT u.*, "
            "  usr.email         AS uploader_email, "
            "  usr.display_name  AS uploader_display_name "
            "FROM uploads u "
            "JOIN users usr ON usr.id = u.user_id "
            "WHERE u.id = ?",
            (upload_id,),
        ).fetchone()
    if row is None:
        raise NotFound(f"upload {upload_id} 不存在")
    return _row_to_dict(row)


def list_uploads(
    *, page: int = 1, size: int = DEFAULT_PAGE_SIZE,
    include_hidden: bool = False,
) -> dict:
    """Paginated upload list, newest first. Returns:
        { items: [...], total, page, size }
    """
    page = max(1, int(page))
    size = max(1, min(MAX_PAGE_SIZE, int(size)))
    offset = (page - 1) * size

    where = "" if include_hidden else "WHERE u.hidden = 0"

    with db_connection() as conn:
        total = conn.execute(
            f"SELECT count(*) AS n FROM uploads u {where}",
        ).fetchone()["n"]
        rows = conn.execute(
            f"SELECT u.*, "
            f"  usr.email        AS uploader_email, "
            f"  usr.display_name AS uploader_display_name "
            f"FROM uploads u "
            f"JOIN users usr ON usr.id = u.user_id "
            f"{where} "
            f"ORDER BY u.created_at DESC, u.id DESC "
            f"LIMIT ? OFFSET ?",
            (size, offset),
        ).fetchall()

    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": int(total),
        "page":  page,
        "size":  size,
    }


def absolute_path_of(upload: dict) -> Path:
    """Resolve an upload record's relative ``file_path`` to absolute."""
    return uploads_dir() / upload["file_path"]


# ----------------------------------------------------------- delete

def delete_upload(*, upload_id: int, user_id: int) -> None:
    """Delete an upload (DB row + on-disk file). Only the original
    uploader may delete their own.

    Raises NotFound / Forbidden.
    """
    upload = get_upload(upload_id)         # raises NotFound
    if upload["user_id"] != user_id:
        raise Forbidden("只能刪除自己上傳的檔案")
    abs_path = absolute_path_of(upload)
    with db_connection() as conn:
        conn.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
    try:
        abs_path.unlink()
    except FileNotFoundError:
        pass


# ----------------------------------------------------------- profile

def update_profile(
    *, user_id: int,
    display_name: Optional[str], bio: Optional[str],
) -> dict:
    """Update the user's public profile fields. Returns the new user
    record."""
    if display_name is not None:
        display_name = _safe_unicode_str(
            display_name, 50, name="display_name",
        )
    if bio is not None:
        bio = _safe_unicode_str(bio, 500, name="bio")

    with db_connection() as conn:
        if display_name is not None and bio is not None:
            conn.execute(
                "UPDATE users SET display_name = ?, bio = ? WHERE id = ?",
                (display_name or None, bio or None, user_id),
            )
        elif display_name is not None:
            conn.execute(
                "UPDATE users SET display_name = ? WHERE id = ?",
                (display_name or None, user_id),
            )
        elif bio is not None:
            conn.execute(
                "UPDATE users SET bio = ? WHERE id = ?",
                (bio or None, user_id),
            )
        row = conn.execute(
            "SELECT id, email, display_name, bio, created_at, "
            "       last_login_at "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        raise NotFound(f"user {user_id} 不存在")
    return dict(row)


# ----------------------------------------------------------- helpers

def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a dict + parse styles_used JSON."""
    d = dict(row)
    styles = d.get("styles_used")
    if isinstance(styles, str):
        try:
            d["styles_used"] = json.loads(styles)
        except json.JSONDecodeError:
            d["styles_used"] = []
    return d
