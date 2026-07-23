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
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from textwrap import shorten
from typing import Optional

from .config import avatars_dir, uploads_dir
from .db import db_connection


# ----------------------------------------------------------- constants

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024     # 10 MB
MAX_TITLE_LEN       = 50                   # chars
MAX_COMMENT_LEN     = 200                  # chars
DAILY_UPLOAD_LIMIT  = 20                   # uploads / user / 24h

# Phase 5b r28: 多 kind 支援
KIND_PSD            = "psd"
KIND_MANDALA        = "mandala"
KIND_POPUP          = "popup"        # 5ft：立體字（鏤空 pop-up SVG）

# 5fw：主頁各模式匯出 SVG（統一出口信封 stroke-order-export-v1；5fv 供給側）
# kind 字串＝信封 mode 字串——分類由檔案聲明，不可能放錯類。
EXPORT_MODE_KINDS   = (
    "single", "grid", "manuscript", "notebook", "letter", "sutra",
    "doodle", "patch", "stamp", "stencil", "wordart", "zentangle",
)
ALLOWED_KINDS       = (KIND_PSD, KIND_MANDALA, KIND_POPUP,
                       *EXPORT_MODE_KINDS)

PSD_SCHEMA_TAG      = "stroke-order-psd-v1"
MANDALA_SCHEMA_TAG  = "stroke-order-mandala-v1"
POPUP_SCHEMA_TAG    = "stroke-order-popup-v1"     # 5ft
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


# ------------------- 5ft: popup（立體字）validators ---------------------

_POPUP_METADATA_RE = re.compile(
    r"<popup-config[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?"
    r"</popup-config>",
)


def parse_and_validate_popup(content_bytes: bytes) -> tuple[dict, str]:
    """Parse a popup（立體字）SVG upload——必須是本系統匯出、內嵌
    ``<popup-config>``（schema=stroke-order-popup-v1）的 SVG。"""
    text = _common_size_decode(content_bytes)
    ts = text.lstrip()
    if not (ts.startswith("<svg") or ts.startswith("<?xml")):
        raise InvalidUpload(
            "立體字上傳需為 SVG 檔（請從立體字模式下載 SVG）")
    m = _POPUP_METADATA_RE.search(text)
    if not m:
        raise InvalidUpload(
            "SVG 內未找到 <popup-config> metadata；"
            "請從本系統立體字模式重新下載 SVG（會自動內嵌設定）",
        )
    try:
        state = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise InvalidUpload(f"SVG metadata JSON 解析失敗：{e.msg}") from None
    if not isinstance(state, dict):
        raise InvalidUpload("popup metadata 必須是 object")
    if state.get("schema") != POPUP_SCHEMA_TAG:
        raise InvalidUpload(
            f"不支援的 schema：{state.get('schema')!r}；"
            f"需 {POPUP_SCHEMA_TAG}",
        )
    if not str(state.get("upper", "")).strip():
        raise InvalidUpload("popup metadata 缺 upper（上排文字）")
    return state, "svg"


def summarise_popup(state: dict) -> dict:
    """立體字清單頁摘要——上/下排文字、字數、卡片尺寸。防禦式取值。"""
    upper = str(state.get("upper", ""))
    lower = str(state.get("lower", ""))
    return {
        "upper_text": upper[:12],
        "lower_text": lower[:12],
        "char_count": len(upper) + len(lower),
        "card_w_mm": state.get("card_w_mm"),
        "card_h_mm": state.get("card_h_mm"),
        "tiers": state.get("tiers"),
    }


# ------------------- 5fw: 統一出口信封 kinds（12 模式） -------------------

# 危險構件——本站匯出器從不產生這些，命中一律拒收（拒收比消毒乾淨：
# 合法檔零誤傷，錯誤訊息直接引導重新匯出）。url( 放行內部參照 url(#
# （布章 clip-path 合法使用），僅擋外部參照。
_SVG_FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"<\s*script\b",        "script 標籤"),
    (r"<\s*foreignobject\b", "foreignObject 標籤"),
    (r"<\s*iframe\b",        "iframe 標籤"),
    (r"<\s*embed\b",         "embed 標籤"),
    (r"<\s*object\b",        "object 標籤"),
    (r"<\s*image\b",         "image 標籤"),
    (r"<\s*use\b",           "use 標籤"),
    (r"<\s*style\b",         "style 標籤"),
    (r"\son[a-z]+\s*=",      "事件屬性（on*=）"),
    (r"javascript:",          "javascript: URL"),
    (r"href\s*=",             "href 屬性（外部參照）"),
    (r"url\(\s*(?!#)",       "外部 url() 參照"),
)
_SVG_FORBIDDEN_RES = tuple(
    (re.compile(pat, re.IGNORECASE), label)
    for pat, label in _SVG_FORBIDDEN_PATTERNS
)


def _reject_dangerous_svg(text: str) -> None:
    """XSS 防禦（縱深；下載端已是 attachment）。命中即拒收。"""
    for regex, label in _SVG_FORBIDDEN_RES:
        if regex.search(text):
            raise InvalidUpload(
                f"SVG 內含不允許的內容（{label}）；"
                "請從本站對應模式重新匯出後上傳",
            )


def parse_and_validate_export_svg(
    content_bytes: bytes, *, expected_mode: str,
) -> tuple[dict, str]:
    """5fw：主頁模式匯出 SVG 的通用驗證器（一個蓋 12 分類）。

    准入條件：是 SVG、無危險構件、內嵌統一出口信封
    （schema=stroke-order-export-v1）且 ``mode`` 與分類一致。
    回 ``(envelope_dict, "svg")``。
    """
    from ..exporters.envelope import (
        EXPORT_SCHEMA_TAG, parse_export_envelope,
    )
    text = _common_size_decode(content_bytes)
    ts = text.lstrip()
    if not (ts.startswith("<svg") or ts.startswith("<?xml")):
        raise InvalidUpload(
            "此分類需上傳本站匯出的 SVG 檔（副檔名 .svg）")
    _reject_dangerous_svg(text)
    env = parse_export_envelope(text)
    if env is None:
        raise InvalidUpload(
            "SVG 內未找到本站出口憑據（stroke-order-export）；"
            "只接受 v0.14.271 之後從本站各模式匯出的 SVG——"
            "請回對應模式重新產生並下載",
        )
    if env.get("schema") != EXPORT_SCHEMA_TAG:
        raise InvalidUpload(
            f"不支援的 schema：{env.get('schema')!r}；需 {EXPORT_SCHEMA_TAG}",
        )
    actual_mode = env.get("mode")
    if actual_mode != expected_mode:
        raise InvalidUpload(
            f"檔案聲明的模式（{actual_mode!r}）與上傳分類"
            f"（{expected_mode!r}）不符",
        )
    return env, "svg"


def summarise_export_svg(state: dict) -> dict:
    """匯出 SVG 清單頁摘要——模式與匯出版本（信封欄位，防禦式取值）。"""
    return {
        "mode": str(state.get("mode", "")),
        "app_version": str(state.get("app_version", "")),
    }


def _make_export_validator(mode: str):
    """綁定分類的 validator（VALIDATORS 契約：``fn(bytes) → (state, ext)``）。"""
    def _validate(content_bytes: bytes) -> tuple[dict, str]:
        return parse_and_validate_export_svg(
            content_bytes, expected_mode=mode)
    return _validate


# Validator dispatch — call site: `state, ext = VALIDATORS[kind](bytes)`
# psd 包一層 lambda 統一返回 (state, ext) 形式（ext 給 on-disk 副檔名）
VALIDATORS = {
    KIND_PSD:     lambda b: (parse_and_validate_psd(b), "json"),
    KIND_MANDALA: parse_and_validate_mandala,
    KIND_POPUP:   parse_and_validate_popup,      # 5ft
}

SUMMARIZERS = {
    KIND_PSD:     summarise_traces,
    KIND_MANDALA: summarise_mandala,
    KIND_POPUP:   summarise_popup,               # 5ft
}

# 5fw：12 個匯出模式分類——registry 派遣，上傳/列表/下載 API 零改動
for _mode in EXPORT_MODE_KINDS:
    VALIDATORS[_mode]  = _make_export_validator(_mode)
    SUMMARIZERS[_mode] = summarise_export_svg


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
    if kind not in (KIND_MANDALA, *EXPORT_MODE_KINDS):
        return False  # PSD/popup 沒 thumbnail（popup 縮圖列 backlog）

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

    # 5fx: 作者治理——blacklisted 禁止上傳；review 上傳先隱藏待管理員放行
    author_status = get_user_moderation_status(user_id)
    if author_status == "blacklisted":
        raise Forbidden("此帳號已被停權，無法上傳")
    initial_hidden = 1 if author_status == "review" else 0
    initial_hide_reason = (HIDE_REASON_PENDING
                           if author_status == "review" else None)

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
                " hidden, hide_reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id, title, comment, safe_filename, str(rel_path),
                    len(content_bytes), file_hash,
                    kind, json.dumps(summary, ensure_ascii=False),
                    legacy_trace_count, legacy_unique_chars,
                    legacy_styles_used,
                    initial_hidden, initial_hide_reason,
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
            "  usr.avatar_path   AS uploader_avatar_path, "
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


SORT_NEWEST = "newest"
SORT_LIKES  = "likes"
SORT_HOT    = "hot"
ALLOWED_SORTS = (SORT_NEWEST, SORT_LIKES, SORT_HOT)

# r29c: Search query 字串長度上限（避免巨大 LIKE pattern 拖慢）
MAX_SEARCH_QUERY_LEN = 100


def list_uploads(
    *, page: int = 1, size: int = DEFAULT_PAGE_SIZE,
    include_hidden: bool = False,
    kind: Optional[str] = None,
    viewer_user_id: Optional[int] = None,
    sort: str = SORT_NEWEST,
    bookmarked_by: Optional[int] = None,
    q: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict:
    """Paginated upload list. Returns:
        { items: [...], total, page, size }

    Phase 5b r28: ``kind`` filter（``"psd"`` / ``"mandala"`` / None=全部）。
    Phase 5b r29: ``viewer_user_id`` 若提供，每個 item 加 ``liked_by_me``
    + ``bookmarked_by_me`` 欄；匿名 / 未登入 → 全 False。
    Phase 5b r29b:
    - ``sort`` ∈ {``"newest"``, ``"likes"``}：default newest（created_at DESC），
      ``"likes"`` 改 like_count DESC + created_at DESC tiebreak
    - ``bookmarked_by`` 若提供（user_id），只列出該 user bookmark 過的 uploads
      （給「我的收藏」filter tab 用）
    Phase 5b r29c:
    - ``sort`` 加 ``"hot"``：linear ranking ``like_count * 5 + julianday(created_at)``，
      每 like 抵 5 天 recency boost，自然 surface 最近 + 受歡迎的內容
    - ``q``：search query，比對 title / comment / uploader email / display_name
      （SQLite LIKE ``%q%``，max_length=100；空字串視同 None）

    Phase 5b r29d:
    - ``user_id``：只列指定 user 的 uploads（profile page filter）
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
    # r29d: user_id filter（profile page — 只列該 user 的 uploads）
    if user_id is not None:
        where_parts.append("u.user_id = ?")
        params.append(user_id)
    # r29b: bookmarked_by filter（「我的收藏」）— 只列該 user bookmark 的 uploads
    if bookmarked_by is not None:
        where_parts.append(
            "EXISTS(SELECT 1 FROM bookmarks b "
            "WHERE b.user_id = ? AND b.upload_id = u.id)",
        )
        params.append(bookmarked_by)
    # r29c: search query — 比對 title / comment / uploader email / display_name
    q_clean = (q or "").strip() if q is not None else ""
    if q_clean:
        if len(q_clean) > MAX_SEARCH_QUERY_LEN:
            raise InvalidUpload(
                f"search query 過長（最多 {MAX_SEARCH_QUERY_LEN} 字）",
            )
        # LIKE 特殊字元 escape（_ % 都是 wildcard，純字面 user 搜尋不該 match wildcards）
        q_escaped = q_clean.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")
        like_pat = f"%{q_escaped}%"
        where_parts.append(
            "(u.title LIKE ? ESCAPE '\\' "
            "OR COALESCE(u.comment, '') LIKE ? ESCAPE '\\' "
            "OR usr.email LIKE ? ESCAPE '\\' "
            "OR COALESCE(usr.display_name, '') LIKE ? ESCAPE '\\')",
        )
        params.extend([like_pat, like_pat, like_pat, like_pat])
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    # r29: viewer_user_id 若 None → 用 -1 placeholder（不存在的 user_id），
    # EXISTS subquery 永遠 false → liked_by_me / bookmarked_by_me 全 0
    viewer_id = viewer_user_id if viewer_user_id is not None else -1

    # r29b/r29c: sort 選項
    if sort not in ALLOWED_SORTS:
        raise InvalidUpload(
            f"不支援的 sort: {sort!r}（已知：{', '.join(ALLOWED_SORTS)}）",
        )
    if sort == SORT_LIKES:
        # like_count column 來自 SELECT，可直接用做 ORDER BY
        order_by = "ORDER BY like_count DESC, u.created_at DESC, u.id DESC"
    elif sort == SORT_HOT:
        # r29c: hot ranking — log-scale likes + julianday recency
        # log(like_count) * 5 + julianday(created_at)，每 log10 點 likes（10x）
        # = 5 天 boost。例：50 likes (≈log10=1.7×5≈8.5 days boost) vs
        # 0 likes today: 法輪 (5 likes 1d ago) > 古寺 (0 likes today) >
        # 九字 (20 likes 9d) > 漢字 (50 likes 19d)，符合「最近受歡迎」直覺。
        # SQLite log() = log10()，CASE 處理 0 likes（log10(0) = -inf）
        order_by = (
            "ORDER BY ("
            "CASE WHEN COALESCE(like_count, 0) > 0 "
            "  THEN log(like_count) * 5.0 ELSE 0 END "
            "+ julianday(u.created_at)"
            ") DESC, u.id DESC"
        )
    else:
        order_by = "ORDER BY u.created_at DESC, u.id DESC"

    with db_connection() as conn:
        # r29c: count query 也 JOIN users（給 search 比對 usr.email / display_name 用）
        total = conn.execute(
            f"SELECT count(*) AS n "
            f"FROM uploads u JOIN users usr ON usr.id = u.user_id {where}",
            params,
        ).fetchone()["n"]
        # SELECT params order: [viewer_id (liked), viewer_id (bookmarked)] +
        # WHERE params + LIMIT/OFFSET
        rows = conn.execute(
            f"SELECT u.*, "
            f"  usr.email        AS uploader_email, "
            f"  usr.display_name AS uploader_display_name, "
            f"  usr.avatar_path  AS uploader_avatar_path, "
            f"  (SELECT count(*) FROM likes l WHERE l.upload_id = u.id) "
            f"    AS like_count, "
            f"  EXISTS(SELECT 1 FROM likes l WHERE l.user_id = ? "
            f"    AND l.upload_id = u.id) AS liked_by_me, "
            f"  EXISTS(SELECT 1 FROM bookmarks b WHERE b.user_id = ? "
            f"    AND b.upload_id = u.id) AS bookmarked_by_me "
            f"FROM uploads u "
            f"JOIN users usr ON usr.id = u.user_id "
            f"{where} "
            f"{order_by} "
            f"LIMIT ? OFFSET ?",
            [viewer_id, viewer_id] + params + [size, offset],
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


# ----------------------------------------------------------- profile (r29d)

PROFILE_TOP_UPLOADS_LIMIT = 3


def get_user_profile(user_id: int) -> dict:
    """Public profile + stats + top uploads for a user.

    Returns:
        {
            "user": {id, email, display_name, bio, created_at},
            "stats": {
                "total_uploads": int,
                "total_likes_received": int,  # sum of likes on user's uploads
                "member_since": str (ISO),
            },
            "top_uploads": [
                {id, title, kind, like_count},  # 最多 PROFILE_TOP_UPLOADS_LIMIT 筆
                ...
            ]  # r29e: like_count DESC, created_at DESC, id DESC tie-break
        }

    Raises NotFound 若 user 不存在。
    """
    with db_connection() as conn:
        u = conn.execute(
            "SELECT id, email, display_name, bio, created_at, avatar_path "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if u is None:
            raise NotFound(f"user {user_id} 不存在")
        # 統計（一次 query 同時拿 upload count + like sum，避免 N+1）
        stats_row = conn.execute(
            "SELECT "
            "  COUNT(DISTINCT u.id) AS upload_count, "
            "  COUNT(l.user_id) AS like_count "
            "FROM uploads u "
            "LEFT JOIN likes l ON l.upload_id = u.id "
            "WHERE u.user_id = ? AND u.hidden = 0",
            (user_id,),
        ).fetchone()
        # r29e: top N 受歡迎作品（精簡欄位，僅 banner strip 用）
        top_rows = conn.execute(
            "SELECT u.id, u.title, u.kind, "
            "  (SELECT count(*) FROM likes l WHERE l.upload_id = u.id) "
            "    AS like_count "
            "FROM uploads u "
            "WHERE u.user_id = ? AND u.hidden = 0 "
            "ORDER BY like_count DESC, u.created_at DESC, u.id DESC "
            "LIMIT ?",
            (user_id, PROFILE_TOP_UPLOADS_LIMIT),
        ).fetchall()
    user_dict = _user_dict_with_avatar(u)
    return {
        "user": {
            "id": int(u["id"]),
            "email": u["email"],
            "display_name": u["display_name"],
            "bio": u["bio"],
            "created_at": u["created_at"],
            "avatar_url": user_dict["avatar_url"],
        },
        "stats": {
            "total_uploads": int(stats_row["upload_count"] or 0),
            "total_likes_received": int(stats_row["like_count"] or 0),
            "member_since": u["created_at"],
        },
        "top_uploads": [
            {
                "id": int(r["id"]),
                "title": r["title"],
                "kind": r["kind"],
                "like_count": int(r["like_count"] or 0),
            }
            for r in top_rows
        ],
    }


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


# ----------------------------------------------------------- bookmarks (r29b)

def toggle_bookmark(*, user_id: int, upload_id: int) -> dict:
    """Toggle bookmark for (user_id, upload_id)。

    Bookmark 跟 like 不同：私人收藏，他人不可見計數。Returns:
        {"bookmarked": bool}

    Raises NotFound 若 upload 不存在。
    """
    get_upload(upload_id)  # raises NotFound
    now = _utcnow_iso()
    with db_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM bookmarks WHERE user_id = ? AND upload_id = ?",
            (user_id, upload_id),
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO bookmarks (user_id, upload_id, created_at) "
                "VALUES (?, ?, ?)",
                (user_id, upload_id, now),
            )
            bookmarked = True
        else:
            conn.execute(
                "DELETE FROM bookmarks WHERE user_id = ? AND upload_id = ?",
                (user_id, upload_id),
            )
            bookmarked = False
    return {"bookmarked": bookmarked}


def is_bookmarked_by(*, upload_id: int, user_id: int) -> bool:
    """User 是否 bookmark 過此 upload。"""
    with db_connection() as conn:
        r = conn.execute(
            "SELECT 1 FROM bookmarks WHERE user_id = ? AND upload_id = ?",
            (user_id, upload_id),
        ).fetchone()
    return r is not None


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
            "       last_login_at, avatar_path "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        raise NotFound(f"user {user_id} 不存在")
    return _user_dict_with_avatar(row)


# ----------------------------------------------------------- avatar (r29j)

AVATAR_MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB raw upload
AVATAR_RESIZE_PX = 256
ALLOWED_AVATAR_TYPES = ("image/png", "image/jpeg", "image/jpg")


def _avatar_path_on_disk(user_id: int) -> Path:
    """檔在 gallery_dir/avatars/<user_id>.png（固定路徑覆寫）。

    DB 的 avatar_path 欄位存 nonce（不是這檔的 path），單純做 cache-bust
    版本標識用。NULL 表示無 avatar。
    """
    return avatars_dir() / f"{user_id}.png"


def _user_dict_with_avatar(row) -> dict:
    """Convert user row → dict + derive ``avatar_url``。

    avatar_url = ``/api/gallery/users/{id}/avatar?v=<nonce>`` 含版本以強制
    瀏覽器在更新 avatar 後重抓；NULL avatar_path 時 avatar_url=None。
    """
    d = dict(row)
    nonce = d.get("avatar_path")
    if nonce:
        d["avatar_url"] = f"/api/gallery/users/{d['id']}/avatar?v={nonce}"
    else:
        d["avatar_url"] = None
    # avatar_path 是內部 nonce，不外洩到 API response（避免混淆 frontend）
    d.pop("avatar_path", None)
    return d


def update_avatar(*, user_id: int, file_bytes: bytes,
                  content_type: str) -> dict:
    """驗證 + Pillow resize 256x256 + 寫入 disk + 更新 DB。

    Args:
        user_id: 目標 user
        file_bytes: 上傳原始 binary
        content_type: HTTP content-type（限 PNG / JPEG）

    Raises:
        InvalidUpload: 格式 / 大小 / 解析失敗
        NotFound: user 不存在

    Returns:
        Updated user dict with avatar_url。
    """
    # 延遲 import — 避免 cli / scripts 引到非必要 dep
    import io
    from PIL import Image, UnidentifiedImageError

    ct = (content_type or "").lower().split(";")[0].strip()
    if ct not in ALLOWED_AVATAR_TYPES:
        raise InvalidUpload(
            f"avatar 格式須為 PNG 或 JPEG（收到 {content_type!r}）"
        )
    if len(file_bytes) > AVATAR_MAX_SIZE_BYTES:
        mb = AVATAR_MAX_SIZE_BYTES // 1024 // 1024
        raise InvalidUpload(f"avatar 大小超過上限 {mb} MB")
    if len(file_bytes) == 0:
        raise InvalidUpload("avatar 檔案為空")

    try:
        # 第一次 open + verify（消耗 stream，不能 reuse）
        Image.open(io.BytesIO(file_bytes)).verify()
        # 重 open 進行實際 decode + resize
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode != "RGB":
            # PNG with alpha → 平面 white background composite
            if img.mode in ("RGBA", "LA"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[-1])
                img = bg
            else:
                img = img.convert("RGB")
        # Square crop center → resize 256x256
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize(
            (AVATAR_RESIZE_PX, AVATAR_RESIZE_PX),
            Image.Resampling.LANCZOS,
        )
    except UnidentifiedImageError:
        raise InvalidUpload("avatar 不是合法 image 檔")
    except Exception as e:
        raise InvalidUpload(f"avatar 解析失敗：{e}")

    # Ensure dir + write file（覆寫舊 avatar）
    avatars_dir().mkdir(parents=True, exist_ok=True)
    target = _avatar_path_on_disk(user_id)
    img.save(target, format="PNG", optimize=True)

    # DB 寫 nonce 做 cache-bust
    nonce = secrets.token_hex(8)
    with db_connection() as conn:
        conn.execute(
            "UPDATE users SET avatar_path = ? WHERE id = ?",
            (nonce, user_id),
        )
        row = conn.execute(
            "SELECT id, email, display_name, bio, created_at, "
            "       last_login_at, avatar_path "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        # rollback file（保 DB 一致）
        try:
            target.unlink()
        except OSError:
            pass
        raise NotFound(f"user {user_id} 不存在")
    return _user_dict_with_avatar(row)


def clear_avatar(*, user_id: int) -> dict:
    """移除 avatar（file + DB nonce）。Idempotent — 沒檔也不爆。"""
    target = _avatar_path_on_disk(user_id)
    if target.exists():
        try:
            target.unlink()
        except OSError:
            pass  # best-effort，缺檔不該擋 DB clear
    with db_connection() as conn:
        conn.execute(
            "UPDATE users SET avatar_path = NULL WHERE id = ?",
            (user_id,),
        )
        row = conn.execute(
            "SELECT id, email, display_name, bio, created_at, "
            "       last_login_at, avatar_path "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        raise NotFound(f"user {user_id} 不存在")
    return _user_dict_with_avatar(row)


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
    # r29b: bookmarked_by_me 同樣 cast
    if "bookmarked_by_me" in d:
        d["bookmarked_by_me"] = bool(d["bookmarked_by_me"])
    # r29j: uploader_avatar_path → uploader_avatar_url（cache-busted）
    nonce = d.pop("uploader_avatar_path", None)
    uploader_id = d.get("user_id")
    if nonce and uploader_id is not None:
        d["uploader_avatar_url"] = (
            f"/api/gallery/users/{uploader_id}/avatar?v={nonce}"
        )
    else:
        d["uploader_avatar_url"] = None
    return d


# =====================================================================
# 5fx: 檢舉（匿名＋登入）＋作者治理（moderation）
# =====================================================================

REPORT_REASONS = ("inappropriate", "spam", "copyright", "other")
REPORT_HIDE_THRESHOLD = 3          # 獨立檢舉源達此數 → 自動隱藏
DAILY_REPORT_LIMIT   = 10          # 每來源（帳號或 IP）每 24h 上限
CHALLENGE_MIN_SECONDS = 3          # 防機器人：發題到送出最短停留
CHALLENGE_MAX_AGE_SECONDS = 600    # 挑戰題有效期

HIDE_REASON_REPORTS   = "community-reports"
HIDE_REASON_ADMIN     = "admin-takedown"
HIDE_REASON_PENDING   = "pending-review"
HIDE_REASON_BLACKLIST = "author-blacklisted"

MODERATION_STATUSES = ("normal", "review", "blacklisted")


def _auth_secret_bytes() -> bytes:
    from .config import auth_secret
    sec = auth_secret()
    return sec if isinstance(sec, bytes) else str(sec).encode("utf-8")


def hash_report_ip(ip: str) -> str:
    """IP 加鹽雜湊（HMAC-auth-secret）——匿名檢舉去重用，不存明文 IP。"""
    import hmac as _hmac
    return _hmac.new(_auth_secret_bytes(),
                     ("report-ip:" + (ip or "")).encode("utf-8"),
                     hashlib.sha256).hexdigest()[:32]


# ---------------- 防機器人挑戰（蜜罐＋停留時間＋算術題） ----------------
#
# 無外部服務：伺服器發「a + b = ?」與簽章 token（含發題時間）；驗證時
# 以「使用者送來的答案」重算簽章——答案錯 → 簽章不合。停留時間由
# token 時間戳驗（太快送出 → 機器人；過期 → 重新取題）。蜜罐欄位由
# route 層驗（有值 → 拒）。

def issue_report_challenge() -> dict:
    """發挑戰題。回 {a, b, token}；token = ts.nonce.sig。"""
    import hmac as _hmac
    import time as _time
    a = secrets.randbelow(8) + 1
    b = secrets.randbelow(8) + 1
    ts = int(_time.time())
    nonce = secrets.token_hex(4)
    body = f"report-challenge:{ts}:{nonce}:{a + b}"
    sig = _hmac.new(_auth_secret_bytes(), body.encode("ascii"),
                    hashlib.sha256).hexdigest()[:16]
    return {"a": a, "b": b, "token": f"{ts}.{nonce}.{sig}"}


def verify_report_challenge(token: str, answer) -> None:
    """驗挑戰題；不過就 raise InvalidUpload（訊息可直接呈現）。"""
    import hmac as _hmac
    import time as _time
    try:
        ts_str, nonce, sig = str(token or "").split(".")
        ts = int(ts_str)
        ans = int(answer)
    except (ValueError, AttributeError):
        raise InvalidUpload("驗證資料格式不正確，請重新取得驗證題") from None
    now = int(_time.time())
    if now - ts > CHALLENGE_MAX_AGE_SECONDS:
        raise InvalidUpload("驗證題已過期，請重新取得")
    if now - ts < CHALLENGE_MIN_SECONDS:
        raise InvalidUpload("送出太快，請稍候幾秒再送出")
    body = f"report-challenge:{ts}:{nonce}:{ans}"
    expected = _hmac.new(_auth_secret_bytes(), body.encode("ascii"),
                         hashlib.sha256).hexdigest()[:16]
    if not _hmac.compare_digest(expected, sig):
        raise InvalidUpload("驗證題答案不正確")


# ---------------- 檢舉 ----------------

def _daily_report_count(*, user_id=None, ip_hash=None) -> int:
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with db_connection() as conn:
        if user_id is not None:
            row = conn.execute(
                "SELECT COUNT(*) FROM reports "
                "WHERE reporter_user_id = ? AND created_at >= ?",
                (user_id, cutoff)).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM reports "
                "WHERE reporter_ip_hash = ? AND created_at >= ?",
                (ip_hash, cutoff)).fetchone()
        return int(row[0])


def create_report(
    *, upload_id: int, reason: str, detail: str = "",
    reporter_user_id: Optional[int] = None,
    reporter_ip: Optional[str] = None,
) -> dict:
    """建檢舉。登入件以帳號去重；匿名件以 IP 雜湊去重（route 層已過
    蜜罐＋挑戰題）。獨立來源數達門檻 → 自動隱藏該作品。

    Returns {"total_reports", "auto_hidden"}。
    """
    if reason not in REPORT_REASONS:
        raise InvalidUpload(
            f"不支援的檢舉原因：{reason!r}"
            f"（可用：{', '.join(REPORT_REASONS)}）")
    detail = _safe_unicode_str(detail, MAX_COMMENT_LEN, name="detail")

    upload = get_upload(upload_id)          # NotFound if missing
    if reporter_user_id is not None and             upload.get("user_id") == reporter_user_id:
        raise InvalidUpload("不能檢舉自己的作品")

    ip_hash = None
    if reporter_user_id is None:
        if not reporter_ip:
            raise InvalidUpload("匿名檢舉缺少來源資訊")
        ip_hash = hash_report_ip(reporter_ip)

    if _daily_report_count(user_id=reporter_user_id,
                           ip_hash=ip_hash) >= DAILY_REPORT_LIMIT:
        raise RateLimited(
            f"檢舉過於頻繁（每日上限 {DAILY_REPORT_LIMIT} 次），請明天再試")

    with db_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO reports (upload_id, reporter_user_id, "
                "reporter_ip_hash, reason, detail, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (upload_id, reporter_user_id, ip_hash, reason,
                 detail or None, _utcnow_iso()),
            )
        except sqlite3.IntegrityError:
            raise DuplicateUpload("此作品您已檢舉過") from None

        total = int(conn.execute(
            "SELECT COUNT(*) FROM reports WHERE upload_id = ?",
            (upload_id,)).fetchone()[0])

        auto_hidden = False
        if total >= REPORT_HIDE_THRESHOLD and not upload.get("hidden"):
            conn.execute(
                "UPDATE uploads SET hidden = 1, hide_reason = ? "
                "WHERE id = ? AND hidden = 0",
                (HIDE_REASON_REPORTS, upload_id))
            auto_hidden = True

    return {"total_reports": total, "auto_hidden": auto_hidden}


# ---------------- 管理端 ----------------

def is_admin_email(email: Optional[str]) -> bool:
    from .config import admin_emails
    return bool(email) and email.strip().lower() in admin_emails()


def admin_set_upload_hidden(*, upload_id: int, hidden: bool,
                            reason: str = HIDE_REASON_ADMIN) -> dict:
    """緊急下架／恢復指定作品（管理員；route 層已驗身分）。"""
    upload = get_upload(upload_id)          # NotFound if missing
    with db_connection() as conn:
        if hidden:
            conn.execute(
                "UPDATE uploads SET hidden = 1, hide_reason = ? "
                "WHERE id = ?", (reason, upload_id))
        else:
            conn.execute(
                "UPDATE uploads SET hidden = 0, hide_reason = NULL "
                "WHERE id = ?", (upload_id,))
    out = get_upload(upload_id)
    out["was_hidden"] = bool(upload.get("hidden"))
    return out


def get_user_moderation_status(user_id: int) -> str:
    with db_connection() as conn:
        row = conn.execute(
            "SELECT moderation_status FROM users WHERE id = ?",
            (user_id,)).fetchone()
    if row is None:
        raise NotFound(f"user {user_id} 不存在")
    status = row[0] or "normal"
    return status if status in MODERATION_STATUSES else "normal"


def admin_set_user_moderation(*, user_id: int, status: str) -> dict:
    """勾選作者治理狀態（管理員）。

    - ``review``      → 之後的上傳一律先隱藏（pending-review）待放行。
    - ``blacklisted`` → 禁止上傳＋既有作品全部隱藏。
    - ``normal``      → 解除；先前因黑名單隱藏的作品自動恢復
      （pending-review 與其他隱藏原因不動，由管理員逐件放行）。
    """
    if status not in MODERATION_STATUSES:
        raise InvalidUpload(
            f"不支援的治理狀態：{status!r}"
            f"（可用：{', '.join(MODERATION_STATUSES)}）")
    prev = get_user_moderation_status(user_id)   # NotFound if missing
    hidden_count = 0
    restored_count = 0
    with db_connection() as conn:
        conn.execute(
            "UPDATE users SET moderation_status = ? WHERE id = ?",
            (status, user_id))
        if status == "blacklisted":
            cur = conn.execute(
                "UPDATE uploads SET hidden = 1, hide_reason = ? "
                "WHERE user_id = ? AND hidden = 0",
                (HIDE_REASON_BLACKLIST, user_id))
            hidden_count = cur.rowcount
        elif status == "normal" and prev == "blacklisted":
            cur = conn.execute(
                "UPDATE uploads SET hidden = 0, hide_reason = NULL "
                "WHERE user_id = ? AND hide_reason = ?",
                (user_id, HIDE_REASON_BLACKLIST))
            restored_count = cur.rowcount
    return {"user_id": user_id, "status": status, "previous": prev,
            "hidden_count": hidden_count, "restored_count": restored_count}


def list_reports(*, page: int = 1, size: int = DEFAULT_PAGE_SIZE) -> dict:
    """檢舉清單（管理員）。附作品標題/分類/隱藏狀態＋作者＋檢舉來源。"""
    page = max(1, int(page))
    size = max(1, min(MAX_PAGE_SIZE, int(size)))
    offset = (page - 1) * size
    with db_connection() as conn:
        total = int(conn.execute(
            "SELECT COUNT(*) FROM reports").fetchone()[0])
        rows = conn.execute(
            "SELECT r.id, r.upload_id, r.reason, r.detail, r.created_at, "
            "       r.reporter_user_id, "
            "       rep.email AS reporter_email, "
            "       u.title AS upload_title, u.kind AS upload_kind, "
            "       u.hidden AS upload_hidden, "
            "       u.hide_reason AS upload_hide_reason, "
            "       u.user_id AS author_id, "
            "       au.email AS author_email, "
            "       au.display_name AS author_display_name, "
            "       au.moderation_status AS author_moderation_status "
            "FROM reports r "
            "JOIN uploads u ON u.id = r.upload_id "
            "JOIN users au ON au.id = u.user_id "
            "LEFT JOIN users rep ON rep.id = r.reporter_user_id "
            "ORDER BY r.created_at DESC, r.id DESC "
            "LIMIT ? OFFSET ?",
            (size, offset)).fetchall()
    items = []
    for row in rows:
        d = dict(row)
        d["upload_hidden"] = bool(d.get("upload_hidden"))
        d["anonymous"] = d.get("reporter_user_id") is None
        items.append(d)
    return {"items": items, "total": total, "page": page, "size": size}
