"""
gallery/service.py — upload / list / get / delete business logic.

Responsibilities
----------------
* Validate uploaded payload against per-kind schema:
  - ``psd``     — ``stroke-order-psd-v1`` (5d 抄經軌跡)
  - ``mandala`` — ``stroke-order-mandala-v1`` (5b r27 曼陀羅，.md/.svg)
* Enforce upload limits: file size ≤ 10 MB, ≤ 20 / user / day,
  per-user file_hash dedup.
* Compute kind-specific summary stats for list-page display.
* Manage on-disk file storage at ``<gallery_dir>/uploads/<user>/<file>.<ext>``.
* Provide paginated listing + per-upload metadata + download path.

This module is the single place that touches the filesystem for
uploaded blobs. The FastAPI endpoint layer (Phase 5g-5) calls this
module and never reaches into ``uploads_dir()`` directly.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from textwrap import shorten
from typing import Optional

from .config import uploads_dir
from .db import db_connection


# ----------------------------------------------------------- constants

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024     # 10 MB
MAX_TITLE_LEN       = 50                   # chars
MAX_COMMENT_LEN     = 200                  # chars
DAILY_UPLOAD_LIMIT  = 20                   # uploads / user / 24h

# Phase 5b r28: 多 kind 支援
KIND_PSD            = "psd"
KIND_MANDALA        = "mandala"
ALLOWED_KINDS       = (KIND_PSD, KIND_MANDALA)

PSD_SCHEMA_TAG      = "stroke-order-psd-v1"
MANDALA_SCHEMA_TAG  = "stroke-order-mandala-v1"
MANDALA_REQUIRED_TOP = ("schema", "canvas", "center", "ring", "mandala")

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


# ------------------- Phase 5b r28: mandala validators ---------------------

# 共用基本檢查（size + utf-8 解碼），psd / mandala 都先過這層
def _common_size_decode(content_bytes: bytes) -> str:
    if len(content_bytes) == 0:
        raise InvalidUpload("檔案是空的")
    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        raise InvalidUpload(
            f"檔案過大 ({len(content_bytes) / 1024 / 1024:.1f} MB)；"
            f"上限 {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB",
        )
    try:
        return content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidUpload("檔案不是 UTF-8 編碼") from None


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_SVG_METADATA_RE = re.compile(
    r"<mandala-config[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?"
    r"</mandala-config>",
)


def parse_and_validate_mandala(content_bytes: bytes) -> tuple[dict, str]:
    """Parse a `.mandala.md` (YAML frontmatter) or `.svg` (embedded
    `<mandala-config>` JSON metadata) upload.

    Returns ``(state_dict, source_format)`` where ``source_format`` is
    ``"md"`` or ``"svg"`` (used by ``create_upload`` to pick the on-disk
    file extension). Raises ``InvalidUpload`` on failure.

    Schema validation: must declare ``schema: stroke-order-mandala-v1``
    in frontmatter / metadata. Required top-level sections: ``canvas``,
    ``center``, ``ring``, ``mandala``.
    """
    text = _common_size_decode(content_bytes)
    text_stripped = text.lstrip()

    # 偵測 SVG：開頭 <svg 或 <?xml
    if text_stripped.startswith("<svg") or text_stripped.startswith("<?xml"):
        m = _SVG_METADATA_RE.search(text)
        if not m:
            raise InvalidUpload(
                "SVG 內未找到 <mandala-config> metadata；"
                "請從本系統 mandala 模式重新匯出 SVG（會自動內嵌設定）",
            )
        json_text = m.group(1).replace("]]]]><![CDATA[>", "]]>")
        try:
            state = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise InvalidUpload(f"SVG metadata JSON 解析失敗：{e.msg}") from None
        source_format = "svg"
    else:
        # MD path — split frontmatter + parse YAML
        m = _FRONTMATTER_RE.match(text)
        if not m:
            raise InvalidUpload(
                "檔案缺少 YAML frontmatter（--- ... --- 區塊）；"
                "預期 .mandala.md 格式（從 mandala 模式 📥 匯出）",
            )
        try:
            import yaml  # PyYAML
        except ImportError:
            raise InvalidUpload("伺服器缺少 PyYAML；請通知管理員") from None
        try:
            state = yaml.safe_load(m.group(1))
        except yaml.YAMLError as e:
            raise InvalidUpload(f"YAML frontmatter 解析失敗：{e}") from None
        source_format = "md"

    if not isinstance(state, dict):
        raise InvalidUpload("mandala state 必須是 object（YAML mapping）")

    actual_schema = state.get("schema")
    if actual_schema != MANDALA_SCHEMA_TAG:
        raise InvalidUpload(
            f"不支援的 schema：{actual_schema!r}；"
            f"需 {MANDALA_SCHEMA_TAG}",
        )

    missing = [k for k in MANDALA_REQUIRED_TOP if k not in state]
    if missing:
        raise InvalidUpload(
            f"frontmatter 缺少必要欄位：{', '.join(missing)}",
        )

    return state, source_format


def summarise_mandala(state: dict) -> dict:
    """Compute summary stats for mandala upload list-page display.

    Defensive: 容忍 state 部分欄位缺漏，不爆 — 只 extract 拿得到的。
    """
    extra = state.get("extra_layers") or []
    rings: set[int] = set()
    for layer in extra:
        if isinstance(layer, dict):
            r = layer.get("ring")
            if isinstance(r, int):
                rings.add(r)

    center = state.get("center") or {}
    ring = state.get("ring") or {}
    mandala = state.get("mandala") or {}

    return {
        "layer_count": len([l for l in extra if isinstance(l, dict)]),
        "ring_count": len(rings),
        "center_text": str(center.get("text", ""))[:8],
        "ring_text_short": shorten(
            str(ring.get("text", "")), width=20, placeholder="…"),
        "mandala_style": str(mandala.get("style", "")),
        "composition_scheme": str(mandala.get("composition_scheme", "")),
    }


# Validator dispatch — call site: `state, ext = VALIDATORS[kind](bytes)`
# psd 包一層 lambda 統一返回 (state, ext) 形式（ext 給 on-disk 副檔名）
VALIDATORS = {
    KIND_PSD:     lambda b: (parse_and_validate_psd(b), "json"),
    KIND_MANDALA: parse_and_validate_mandala,
}

SUMMARIZERS = {
    KIND_PSD:     summarise_traces,
    KIND_MANDALA: summarise_mandala,
}


# ------------------- Phase 5b r28b: thumbnail generation ------------------

# Gallery card 用的縮圖尺寸（PNG 像素，正方形）
THUMBNAIL_SIZE_PX = 256
THUMBNAIL_SUFFIX  = ".thumb.png"


def thumbnail_path_of(upload: dict) -> Path:
    """從 upload record 推算 thumbnail 絕對路徑（同層 .thumb.png）。

    file_path = "<user_id>/<nonce>.svg" → thumbnail = "<user_id>/<nonce>.thumb.png"
    """
    fp = uploads_dir() / upload["file_path"]
    return fp.with_suffix(THUMBNAIL_SUFFIX)


def _generate_svg_thumbnail(svg_bytes: bytes,
                             *, size_px: int = THUMBNAIL_SIZE_PX) -> bytes:
    """SVG → PNG（縮圖）。cairosvg 直接轉，不需 char loader。"""
    import cairosvg
    return cairosvg.svg2png(
        bytestring=svg_bytes,
        output_width=size_px,
        output_height=size_px,
    )


def _generate_md_thumbnail(state: dict, *, char_loader,
                           size_px: int = THUMBNAIL_SIZE_PX) -> bytes:
    """MD state → render → cairosvg PNG 縮圖。

    Phase 5b r28c: 需 ``char_loader`` (CharLoader) DI — 由 API 層構造，
    含 style / source / cns_mode pipeline。本 module 不知道 loader 細節。

    缺字時 render_mandala_svg 跳過該字（auto-shrink 補償），thumbnail 仍
    生成（部分字可能缺）。
    """
    from ..exporters.mandala import render_mandala_from_state
    import cairosvg
    svg_str, _info = render_mandala_from_state(state, char_loader)
    return cairosvg.svg2png(
        bytestring=svg_str.encode("utf-8"),
        output_width=size_px,
        output_height=size_px,
    )


def _maybe_generate_thumbnail(
    content_bytes: bytes, *, kind: str, source_format: str,
    abs_path: Path, char_loader=None,
) -> bool:
    """根據 kind / source_format 生成 thumbnail（如可能），存到 abs_path 旁邊。

    Returns True if thumbnail written, False if skipped or failed.

    失敗時回 False（不 raise）— thumbnail 缺漏不該擋上傳完成。

    Phase 5b r28c: ``char_loader`` 為可選 DI；若 None，MD path 跳過
    thumbnail（保 r28b 行為向後相容）。
    """
    if kind != KIND_MANDALA:
        return False  # PSD 沒 thumbnail 概念

    import logging
    try:
        if source_format == "svg":
            png_bytes = _generate_svg_thumbnail(content_bytes)
        elif source_format == "md":
            if char_loader is None:
                # 沒 loader 時跳過 — 跟 r28b 行為一致
                return False
            # parse MD state → render with loader → PNG
            state, _ = parse_and_validate_mandala(content_bytes)
            png_bytes = _generate_md_thumbnail(
                state, char_loader=char_loader)
        else:
            return False  # 未知 source_format
    except Exception as e:
        logging.warning(
            "thumbnail generation failed for %s (source=%s): %s",
            abs_path, source_format, e,
        )
        return False

    thumb_path = abs_path.with_suffix(THUMBNAIL_SUFFIX)
    try:
        thumb_path.write_bytes(png_bytes)
    except Exception as e:
        logging.warning("thumbnail write failed for %s: %s", thumb_path, e)
        return False
    return True


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
    title: str, comment: str, kind: str = KIND_PSD,
    char_loader=None,
    char_loader_factory=None,
) -> dict:
    """Validate + persist an uploaded payload. Returns the new
    upload's full record dict.

    Phase 5b r28: ``kind`` 派遣到對應 validator + summarizer：
    - ``"psd"`` → JSON, ``stroke-order-psd-v1``，副檔名 .json
    - ``"mandala"`` → MD frontmatter / SVG 內嵌 metadata,
      ``stroke-order-mandala-v1``，副檔名依內容 .md / .svg

    Phase 5b r28c: ``char_loader`` (CharLoader) 為 mandala MD upload 生成
    thumbnail 用的 DI；靜態（不依 state）。

    Phase 5b r28d: ``char_loader_factory`` (callable[state] → CharLoader) 接受
    state 動態構造 loader — 從 state.style.font / source / cns_outline_mode
    建出對應的 loader，使 thumbnail 字體 / 字源跟 user 的 mandala 看到的一致。

    優先：``char_loader_factory(state)`` > ``char_loader``（None → MD
    upload skip thumbnail，保 r28b 向後相容）。

    Raises:
        InvalidUpload    — schema / size / format / 不認識的 kind
        DuplicateUpload  — same hash already uploaded by this user
        RateLimited      — > 20 uploads in last 24h
    """
    if kind not in ALLOWED_KINDS:
        raise InvalidUpload(
            f"不支援的 kind: {kind!r}（已知：{', '.join(ALLOWED_KINDS)}）",
        )

    title   = _safe_unicode_str(title,   MAX_TITLE_LEN,   name="title")
    comment = _safe_unicode_str(comment, MAX_COMMENT_LEN, name="comment")
    if not title:
        raise InvalidUpload("title 不可空白")

    if daily_upload_count(user_id) >= DAILY_UPLOAD_LIMIT:
        raise RateLimited(
            f"每日上傳上限 {DAILY_UPLOAD_LIMIT} 次，請明天再試",
        )

    # Validate schema first — cheap-fails before we touch disk.
    state, ext = VALIDATORS[kind](content_bytes)
    summary = SUMMARIZERS[kind](state)
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
    rel_path = Path(str(user_id)) / f"{nonce}.{ext}"
    abs_path = uploads_dir() / rel_path
    _user_uploads_dir(user_id)         # ensure parent exists
    abs_path.write_bytes(content_bytes)

    # Phase 5b r28b/r28c/r28d: 生成 thumbnail
    # - mandala+svg：cairosvg 直接轉，不需 loader
    # - mandala+md：先 factory(state) 拿 state-aware loader（r28d），否則用
    #   靜態 char_loader（r28c），都無則 skip
    # - 失敗 graceful 不擋上傳
    loader_for_thumbnail = char_loader
    if char_loader_factory is not None:
        try:
            loader_for_thumbnail = char_loader_factory(state)
        except Exception as e:
            import logging
            logging.warning(
                "char_loader_factory failed (state.style maybe malformed): "
                "%s — fall back to static char_loader", e,
            )
            # loader_for_thumbnail 維持 char_loader（fall back）
    _maybe_generate_thumbnail(
        content_bytes, kind=kind, source_format=ext, abs_path=abs_path,
        char_loader=loader_for_thumbnail,
    )

    safe_filename = (filename or "").strip()[:200] or f"upload.{ext}"

    # Backward compat: PSD 仍寫 trace_count / unique_chars / styles_used
    # （legacy 列為 5d 視覺所用）；其他 kind 那 3 欄留 0/null，
    # 改靠 summary_json 通用欄位。
    if kind == KIND_PSD:
        legacy_trace_count = summary["trace_count"]
        legacy_unique_chars = summary["unique_chars"]
        legacy_styles_used = json.dumps(summary["styles_used"])
    else:
        legacy_trace_count = 0
        legacy_unique_chars = 0
        legacy_styles_used = None

    try:
        with db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO uploads "
                "(user_id, title, comment, filename, file_path, "
                " file_size, file_hash, kind, summary_json, "
                " trace_count, unique_chars, styles_used, "
                " hidden, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                (
                    user_id, title, comment, safe_filename, str(rel_path),
                    len(content_bytes), file_hash,
                    kind, json.dumps(summary, ensure_ascii=False),
                    legacy_trace_count, legacy_unique_chars,
                    legacy_styles_used,
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
    Raises NotFound.

    Phase 5b r29: 同時返 like_count（來自 likes table aggregate）。
    """
    with db_connection() as conn:
        row = conn.execute(
            "SELECT u.*, "
            "  usr.email         AS uploader_email, "
            "  usr.display_name  AS uploader_display_name, "
            "  (SELECT count(*) FROM likes l WHERE l.upload_id = u.id) "
            "    AS like_count "
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
    kind: Optional[str] = None,
    viewer_user_id: Optional[int] = None,
) -> dict:
    """Paginated upload list, newest first. Returns:
        { items: [...], total, page, size }

    Phase 5b r28: ``kind`` filter（``"psd"`` / ``"mandala"`` / None=全部）。
    Phase 5b r29: ``viewer_user_id`` 若提供，每個 item 加 ``liked_by_me`` 欄
    （該 user 是否 like 過此 upload）；匿名 / 未登入 → 全 False。
    """
    page = max(1, int(page))
    size = max(1, min(MAX_PAGE_SIZE, int(size)))
    offset = (page - 1) * size

    where_parts: list[str] = []
    params: list = []
    if not include_hidden:
        where_parts.append("u.hidden = 0")
    if kind is not None:
        if kind not in ALLOWED_KINDS:
            raise InvalidUpload(
                f"不支援的 kind filter: {kind!r}（已知：{', '.join(ALLOWED_KINDS)}）",
            )
        where_parts.append("u.kind = ?")
        params.append(kind)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    # r29: viewer_user_id 若 None → 用 -1 placeholder（不存在的 user_id），
    # EXISTS subquery 永遠 false → liked_by_me 全 0
    viewer_id = viewer_user_id if viewer_user_id is not None else -1

    with db_connection() as conn:
        total = conn.execute(
            f"SELECT count(*) AS n FROM uploads u {where}",
            params,
        ).fetchone()["n"]
        rows = conn.execute(
            f"SELECT u.*, "
            f"  usr.email        AS uploader_email, "
            f"  usr.display_name AS uploader_display_name, "
            f"  (SELECT count(*) FROM likes l WHERE l.upload_id = u.id) "
            f"    AS like_count, "
            f"  EXISTS(SELECT 1 FROM likes l WHERE l.user_id = ? "
            f"    AND l.upload_id = u.id) AS liked_by_me "
            f"FROM uploads u "
            f"JOIN users usr ON usr.id = u.user_id "
            f"{where} "
            f"ORDER BY u.created_at DESC, u.id DESC "
            f"LIMIT ? OFFSET ?",
            [viewer_id] + params + [size, offset],
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


# ----------------------------------------------------------- likes (r29)

def toggle_like(*, user_id: int, upload_id: int) -> dict:
    """Toggle like for (user_id, upload_id)。

    Atomically INSERT 若沒 like，否則 DELETE。Returns:
        {"liked": bool, "like_count": int}

    Raises NotFound 若 upload 不存在。
    """
    # Verify upload exists（會 raise NotFound）
    get_upload(upload_id)
    now = _utcnow_iso()
    with db_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM likes WHERE user_id = ? AND upload_id = ?",
            (user_id, upload_id),
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO likes (user_id, upload_id, created_at) "
                "VALUES (?, ?, ?)",
                (user_id, upload_id, now),
            )
            liked = True
        else:
            conn.execute(
                "DELETE FROM likes WHERE user_id = ? AND upload_id = ?",
                (user_id, upload_id),
            )
            liked = False
        count_row = conn.execute(
            "SELECT count(*) AS n FROM likes WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()
    return {"liked": liked, "like_count": int(count_row["n"])}


def get_like_info(*, upload_id: int, user_id: Optional[int] = None) -> dict:
    """查單一 upload 的 like 狀態。

    Returns:
        {"like_count": int, "liked_by_me": bool}
        ``liked_by_me`` 在 ``user_id`` 為 None 時固定 False（匿名）。
    """
    with db_connection() as conn:
        count_row = conn.execute(
            "SELECT count(*) AS n FROM likes WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()
        liked_by_me = False
        if user_id is not None:
            r = conn.execute(
                "SELECT 1 FROM likes WHERE user_id = ? AND upload_id = ?",
                (user_id, upload_id),
            ).fetchone()
            liked_by_me = r is not None
    return {
        "like_count": int(count_row["n"]) if count_row else 0,
        "liked_by_me": liked_by_me,
    }


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
    # r28b: 連 thumbnail 也清掉（如有）
    try:
        thumbnail_path_of(upload).unlink()
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
    """Convert a sqlite3.Row to a dict + parse JSON columns.

    Phase 5b r28: 同步 parse ``summary_json`` 為 ``summary`` dict（給
    gallery 列表用 kind-specific 摘要顯示），legacy ``styles_used``
    維持原解析路徑給 PSD 使用。
    """
    d = dict(row)
    styles = d.get("styles_used")
    if isinstance(styles, str):
        try:
            d["styles_used"] = json.loads(styles)
        except json.JSONDecodeError:
            d["styles_used"] = []
    sj = d.get("summary_json")
    if isinstance(sj, str):
        try:
            d["summary"] = json.loads(sj)
        except json.JSONDecodeError:
            d["summary"] = {}
    else:
        d["summary"] = {}
    # 確保 kind 欄位永遠有值（既有 row 經 migration 後 default 'psd'）
    if not d.get("kind"):
        d["kind"] = KIND_PSD
    # r29: like_count 預設 0（既有 query 沒帶 like_count column 時不爆）
    d["like_count"] = int(d.get("like_count") or 0)
    # r29: liked_by_me bool（SQLite EXISTS 回 0/1，cast 成 bool）
    if "liked_by_me" in d:
        d["liked_by_me"] = bool(d["liked_by_me"])
    return d
