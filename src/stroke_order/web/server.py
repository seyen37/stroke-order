"""
FastAPI backend for the local Web UI.

Endpoints
---------

- ``GET  /``                    — serve index.html
- ``GET  /api/character/{ch}`` — hanzi-writer-compatible JSON for `ch`
- ``GET  /api/meta/{ch}``      — diagnostic metadata (stroke kinds, bbox,
                                  validation warnings, signature)
- ``GET  /api/export/{ch}``    — file download; ``?format=svg|gcode|json``
- ``GET  /static/…``           — static assets (JS, CSS)

Query params shared by /api/character, /api/meta, /api/export:

    source=g0v|mmh|auto      (default auto)
    hook_policy=animation|static (default animation)
    char_size=<float mm>     (gcode only; default 20)
    feed_rate=<int>          (gcode only; default 3000)

Run with::

    stroke-order serve --port 8000
    # then open http://localhost:8000/
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


# ---- Phase 5s: request models for POST /api/notebook ----

class ZoneSpec(BaseModel):
    x: float
    y: float
    w: float
    h: float
    label: Optional[str] = None
    svg_content: Optional[str] = None
    content_viewbox: Optional[list[float]] = None
    stretch: bool = False   # Phase 5u: force-fill zone ignoring aspect


class UserDictPostRequest(BaseModel):
    """Phase 5ak: POST /api/user-dict body. Three input formats:

    - ``format=json``        : ``strokes`` is the canonical track list
    - ``format=svg``         : ``svg_content`` is parsed by svgpathtools
    - ``format=handwriting`` : ``handwriting`` carries canvas-coord points
    """
    char: str
    format: str = "json"
    strokes: Optional[list[dict]] = None
    svg_content: Optional[str] = None
    handwriting: Optional[dict] = None


class NotebookPostRequest(BaseModel):
    """JSON body for POST /api/notebook — supports arbitrary-sized
    svg_content per zone (vs. the URL-length-limited GET variant)."""
    text: str
    preset: str = "large"
    grid_style: str = "square"
    line_height_mm: Optional[float] = None
    margin_mm: Optional[float] = None
    cell_style: str = "ghost"
    direction: str = "horizontal"
    lines_per_page: Optional[int] = None
    first_line_offset_mm: Optional[float] = None
    source: str = "auto"
    hook_policy: str = "animation"
    zones: list[ZoneSpec] = []
    page: Optional[int] = None
    format: str = "svg"   # Phase 5v: svg | gcode | json
    style: str = "kaishu" # Phase 5aj: kaishu | mingti | lishu | bold


# Phase 5ax — module-scope so FastAPI's Pydantic introspection works.
class PatchDecorationSpec(BaseModel):
    svg_content: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    # 12m-7 r30: 圓戳章內框圖用，True = clip 成 inscribed circle
    clip_circle: bool = False


# 5et-R4：卡片印刷 PDF 請求（⚠ 必須在模組層——from __future__ import
# annotations 下，create_app 內的區域類別無法被 FastAPI 解析型別註記，
# 會被誤判成 query 參數）。
_CARD_PDF_DENY = re.compile(
    r"(xlink:href|href\s*=|url\s*\(|<\s*(script|image|foreignObject|iframe|use|embed|object))",
    re.IGNORECASE,
)


class CardPdfRequest(BaseModel):
    svg: str
    filename: str = "card"


class PatchPostRequest(BaseModel):
    # 5de：auto 字級——字少自動放大、字多自動縮小（造型感知，
    # 見 patch._fit_row_to_shape）；False＝沿用 char_size_mm 上限
    auto_size: bool = False
    text: str = ""
    preset: str = "rectangle"
    patch_width_mm: float = 80.0
    patch_height_mm: float = 40.0
    char_size_mm: float = 18.0
    text_position: str = "center"
    style: str = "kaishu"
    source: str = "auto"
    hook_policy: str = "animation"
    decorations: list[PatchDecorationSpec] = []
    tile_rows: int = 1
    tile_cols: int = 1
    tile_gap_mm: float = 5.0
    page_width_mm: float = 210.0
    page_height_mm: float = 297.0
    format: str = "svg"
    show_border: bool = True   # Phase 5ay: hide patch outline for post-processing


class StampPostRequest(BaseModel):
    text: str = ""
    preset: str = "square_name"
    stamp_width_mm: float = 25.0
    stamp_height_mm: float = 25.0
    char_size_mm: float = 10.0
    show_border: bool = True
    double_border: bool = False
    border_padding_mm: float = 0.8  # 12b-6: 對齊業界小章 inset
    style: str = "kaishu"
    source: str = "auto"
    hook_policy: str = "animation"
    decorations: list[PatchDecorationSpec] = []
    laser_power: int = 255
    feed: float = 1500.0
    format: str = "svg"   # svg | gcode | pdf
    engrave_mode: str = "concave"  # 12c: concave (陰刻) | convex (陽刻)
    line_pitch_mm: float = 0.1     # 12c: convex 光柵掃描密度
    layout_5char: str = "2plus3"   # 12f: 5 字 layout 2plus3 (姓名章預設) | 3plus2 (職名章變體)
    layout_2char: str = "horizontal"  # 12h: 2 字 layout horizontal (預設右起讀) | vertical (上下)
    # 12l: 公司章短列位置升級成 list (預設 ["right"]，可複選 / 集中短)。
    # 接受 list[str] 或單一 str（向後兼容 12k）：
    #   3-col (7-12 字): right|middle|left
    #   4-col (13-16 字): right|mid-right|mid-left|left
    layout_official_short_col: list[str] | str = ["right"]
    char_offsets: list[list[float]] = []  # 12g: 每字 [dx, dy] mm 微調（list of [dx, dy]）
    # 12m-1: 橢圓章結構化欄位（preset=oval 時使用，否則忽略）。
    # 任一非空 → 走業界標準 layout（上弧 + 中央 1-3 行 + 下弧）；
    # 全空 → fallback 既有 1-2 行 horizontal layout（向後兼容）。
    oval_arc_top: str = ""           # 上弧文（典型：公司名稱）
    oval_arc_bottom: str = ""        # 下弧文（典型：地址 / 統一編號）
    oval_body_lines: list[str] = []  # 中央 1-3 行水平文字（順序 = 上→下）
    # 12m-1 patch r12: 中央 1/2/3 加粗 flags（list of 3 bool；False default）。
    oval_body_bold: list[bool] = []
    # 12m-1 patch r13: 裝飾符號 — 'plum'/'star'/'circle'/'none'
    oval_decoration: str = "plum"
    # 12m-1 patch r18: 鋸齒外框（zigzag tooth pattern on outer ellipse）
    oval_sawtooth: bool = False
    # 12m-7: tax_invoice 上方標題（如「統一發票專用章」）
    oval_top_title: str = ""
    # 12m-7: tax_invoice 縣市名（如「台北市」）
    oval_location: str = ""
    # 12m-7: 縣市位置 — "bottom" (中央 3 下方) | "left" (左側直立)
    oval_location_position: str = "bottom"
    # 12m-7 r26: 圓戳章單圓周模式 — 上弧文 wrap 300° + 單一梅花在底部
    round_continuous_arc: bool = False
    # 12m-7 r31: 動態 body slot overrides — 圓戳章內框圖搭配 body 文字時，
    # frontend 計算 case-specific slot y/height 後傳入。dict 鍵：
    # "slot_0", "slot_1", "slot_2"。值 = [y_ratio, max_h_ratio]
    body_slot_overrides: dict = {}
    # 12m-7 r39: 職名章 (rectangle_title) 2-column 欄位
    rect_left_line1: str = ""
    rect_left_line2: str = ""
    rect_right: str = ""
    rect_left_2rows: bool = False


class SutraPostRequest(BaseModel):
    """抄經模式 (Phase 5az) — 單頁 SVG 渲染請求。"""
    preset: str = "heart_sutra"
    page_index: int = 0
    page_type: str = "body"          # cover | body | dedication
    style: str = "kaishu"
    source: str = "auto"
    hook_policy: str = "animation"
    scribe: str = ""
    date_str: str = ""
    dedicator: str = ""
    target: str = ""
    signature: str = ""              # 5bh: empty by default; user may add
    show_grid: bool = True
    show_helper_lines: bool = True
    # 5bm: default to no cover so the trace pages are immediately useful
    # for plotter output (cover/dedication are opt-in).
    include_cover: bool = False
    include_dedication: bool = False
    trace_fill: str = "#cccccc"
    dedication_verse: str = ""       # empty → no faded verse on dedication page
    # 5bh / 5bi: text processing mode
    # compact | compact_marks | with_punct | raw
    text_mode: str = "compact_marks"
    # 5bj: page geometry
    paper_orientation: str = "landscape"   # landscape | portrait
    text_direction: str = "vertical"       # vertical | horizontal
    # 5bz: when True, lay a faded outline of the original lishu/seal
    # letterform behind the skeleton tracks so the user sees the full
    # glyph shape (preview + PDF). False keeps the SVG as pure skeleton
    # tracks (the writing-robot/plotter format). No effect on
    # outline-bearing styles (kaishu/sung) — they already render filled.
    show_original_glyph: bool = False
    # 5dt: emit a transparent per-cell click-map (data-char/data-pos) so the
    # browser preview can make each 描紅 cell clickable (逐字手寫). Preview
    # sets this True; SVG/PDF downloads leave it False.
    emit_cellmap: bool = False


class ClosingPageSpec(BaseModel):
    """5bg: 結語頁設定（單一經典 override 用）。"""
    title: str = ""
    verse: str = ""
    blank1_label: str = ""
    blank2_label: str = ""


class SutraUploadRequest(BaseModel):
    """抄經自訂上傳 (Phase 5bb / 5bd / 5bg) — 純文字 + metadata + 學術欄位。"""
    text: str
    title: str = ""
    subtitle: str = "手抄本"
    category: str = "user_custom"
    source: str = ""
    description: str = ""
    language: str = "zh-TW"
    is_mantra_repeat: bool = False
    repeat_count: int = 1
    tags: list[str] = []
    desired_key: str = ""        # blank → derive from title
    # 5bd scholarly metadata
    author: str = ""
    editor: str = ""
    notes: str = ""
    source_url: str = ""
    # 5bg closing override (None → use category template)
    closing: Optional[ClosingPageSpec] = None


class SutraMetaPatch(BaseModel):
    """抄經自訂 metadata 局部更新 (Phase 5bb / 5bd / 5bg)."""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    is_mantra_repeat: Optional[bool] = None
    repeat_count: Optional[int] = None
    tags: Optional[list[str]] = None
    # 5bd scholarly metadata
    author: Optional[str] = None
    editor: Optional[str] = None
    notes: Optional[str] = None
    source_url: Optional[str] = None
    # 5bg closing override
    closing: Optional[ClosingPageSpec] = None


class SutraBuiltinPatch(BaseModel):
    """內建經文 metadata override + 內文覆寫 (Phase 5be / 5bg)."""
    # Same metadata fields as SutraMetaPatch, plus optional `text` for
    # overwriting the builtin's .txt content.
    title: Optional[str] = None
    subtitle: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    tags: Optional[list[str]] = None
    author: Optional[str] = None
    editor: Optional[str] = None
    notes: Optional[str] = None
    source_url: Optional[str] = None
    closing: Optional[ClosingPageSpec] = None
    text: Optional[str] = None       # if non-None, overwrites builtin/{key}.txt


# ---------------------------------------------------------------------------
# Phase 5g — gallery (公眾分享庫) request bodies
# ---------------------------------------------------------------------------


class GalleryLoginRequest(BaseModel):
    email: str


class GalleryProfilePatch(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase A (6b) — component coverage analyzer request bodies
# ---------------------------------------------------------------------------


class CoverageRecommendRequest(BaseModel):
    """POST body for /api/coverage/recommend.

    Attributes:
        written_chars: Concatenated string of characters the user has
            already written (e.g. ``"明林永"``). Order doesn't matter.
        coverset: Built-in cover-set name (default ``"cjk_common_808"``).
        top_k: How many recommendations to return (default 5).
    """
    written_chars: str = ""
    coverset: str = "cjk_common_808"
    top_k: int = 5


def _parse_zhuyin_map(zhuyin_map: Optional[str], source: str,
                      hook_policy: str) -> tuple[Optional[dict], dict]:
    """5cz：解析「字:注音,字:注音」映射並載入符號 Character。

    5cu 起的共用邏輯——grid（SVG＋G-code）、notebook、letter 三處
    消費，抽成單一 helper。聲調記號（手作 polyline）與載不到的
    符號靜默跳過。回傳 ``(zmap, zchars)``；``zhuyin_map=None`` 時
    ``zmap=None``（＝功能關閉）。
    """
    zmap: Optional[dict] = None
    zchars: dict = {}
    if zhuyin_map is not None:
        zmap = {}
        for pair in zhuyin_map.split(","):
            if ":" not in pair:
                continue
            k, v = pair.split(":", 1)
            if k:
                zmap[k] = v
        for val in zmap.values():
            for sym in val:
                if sym in zchars or sym in "ˊˇˋ˙ˉ":
                    continue
                try:
                    zc, _r2, _2 = _load(sym, source, hook_policy)
                    zchars[sym] = zc
                except HTTPException:
                    continue
    return zmap, zchars


def _content_disposition(basename: str, ext: str) -> str:
    """RFC 5987-compliant attachment header supporting Unicode filenames."""
    ascii_fallback = f"char.{ext}"  # plain ASCII for old clients
    utf8_encoded = quote(f"{basename}.{ext}", safe="")
    return (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{utf8_encoded}"
    )


# 5dz: 下載檔名友善化——字型風格代碼 → 顯示標籤（與前端 su-style 一致）。
_STYLE_LABELS = {
    "kaishu": "楷書",
    "mingti": "宋體",
    "lishu": "隸書",
    "bold": "粗楷",
    "seal_script": "篆書",
}


def _style_label(style: str) -> str:
    """字型風格代碼 → 中文標籤（未知代碼原樣返回）。"""
    return _STYLE_LABELS.get(style, style or "楷書")


def _safe_filename_part(s: str) -> str:
    """去掉檔名不合法字元（Windows/macOS/Linux 通用），保留中英數。"""
    out = []
    for ch in (s or "").strip():
        out.append("_" if ch in '\\/:*?"<>|' else ch)
    return "".join(out).strip() or "sutra"

# NOTE（W3-R1）：下方相對 import 有一部分在本檔已無直接使用——但
# web/routes/* 以 ``from ..server import X`` 取用（re-export 面），
# pyflakes 的 unused 警告是誤報、勿刪。R2 會把共用 helpers 與這批
# re-export 收斂到專屬模組，屆時一併清理。
from ..classifier import classify_character
from ..decomposition import default_db as default_decomp_db
from ..radicals import lookup as radical_lookup
from ..exporters.gcode import GCodeOptions, characters_to_gcode
from ..exporters.hanzi_writer import (
    character_to_hanzi_writer_dict,
)
from ..exporters.json_polyline import character_to_dict, character_to_json
from ..exporters.svg import character_to_svg
from ..hook_policy import apply_hook_policy
from ..smoothing import smooth_character
from ..sources import CharacterNotFound, make_source
from ..sources.cns_font import (
    apply_cns_outline_mode as _apply_cns_mode,
    get_cns_sung_source as _get_sung,
)
from ..sources.chongxi_seal import (
    apply_seal_outline_mode as _apply_seal_mode,
    get_seal_source as _get_seal,
    attribution_notice as _seal_attribution,
)
from ..sources.moe_lishu import (
    apply_lishu_outline_mode as _apply_lishu_mode,
    get_lishu_source as _get_lishu,
    attribution_notice as _lishu_attribution,
)
from ..sources.moe_song import (
    apply_song_outline_mode as _apply_song_mode,
    get_song_source as _get_song,
    attribution_notice as _song_attribution,
)
from ..sources.moe_kaishu import (
    get_kaishu_source as _get_kaishu_font,
    attribution_notice as _kaishu_attribution,
)
from .. import cache_bus
from ..styles import STYLES as _STYLES, apply_style as _apply_style
from ..validation import apply_known_bug_fix, validate_character

#: Phase 5al: validator for ``cns_outline_mode`` query param.
_CNS_MODE_PATTERN = "^(skip|trace|skeleton)$"

#: Phase 5aj: validator for the ``style`` query param across all multi-char
#: endpoints. Built from the styles registry so adding a new style in
#: stroke_order.styles automatically expands the pattern.
_STYLE_PATTERN = "^(" + "|".join(sorted(_STYLES)) + ")$"


WEB_ROOT = Path(__file__).resolve().parent
STATIC_DIR = WEB_ROOT / "static"


def _resolve_app_version() -> str:
    """5ev（W2b）：?v= 快取鍵的單一事實源＝pyproject 版本。

    ⚠ 順序刻意「pyproject 優先、importlib.metadata 後備」：editable
    install（pip install -e）的 metadata 凍結在安裝當下，pyproject 升版
    不會反映——本機 .venv 會拿到舊版本號。checkout 內直讀 pyproject
    永遠是現值；wheel 部署（無 pyproject 同行）才退 metadata。
    """
    try:
        import tomllib
        root = WEB_ROOT.parents[2]  # src/stroke_order/web → repo root
        with open(root / "pyproject.toml", "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        pass
    try:
        from importlib.metadata import version
        return version("stroke-order")
    except Exception:
        return "dev"


APP_VERSION = _resolve_app_version()

#: 前端檔案裡的 ?v=__V__ 佔位符，吐出時換成 APP_VERSION。
#: vendor pin（opencv 4.11.0／opentype 1.3.4）是語意版本、刻意不用佔位符
#: ——換成 app 版本會讓每次升版重抓 10MB 級大檔。
_VERSION_PLACEHOLDER = "?v=__V__"
_INJECT_SUFFIXES = (".js", ".mjs", ".html", ".css")
#: (path str) → (mtime_ns, version, body bytes, etag)
_versioned_cache: dict = {}


def _versioned_text(full_path: Path) -> tuple[bytes, str]:
    """讀檔＋佔位符注入，帶 (mtime, version) 快取。"""
    st = full_path.stat()
    key = str(full_path)
    hit = _versioned_cache.get(key)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == APP_VERSION:
        return hit[2], hit[3]
    text = full_path.read_text("utf-8")
    body = text.replace(_VERSION_PLACEHOLDER, f"?v={APP_VERSION}").encode("utf-8")
    etag = f'W/"{st.st_mtime_ns:x}-{APP_VERSION}"'
    _versioned_cache[key] = (st.st_mtime_ns, APP_VERSION, body, etag)
    return body, etag


_MEDIA_BY_SUFFIX = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


def _versioned_page(full_path: Path, if_none_match: str | None = None) -> Response:
    body, etag = _versioned_text(full_path)
    if if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        content=body,
        media_type=_MEDIA_BY_SUFFIX.get(full_path.suffix, "text/plain"),
        headers={"ETag": etag},
    )


class _VersionedStaticFiles(StaticFiles):
    """5ev：只攔 .js/.mjs/.html/.css 做 ?v=__V__ 注入；其餘（json/圖/字型）
    原封走 StaticFiles（保留 Range／304 條件請求等原生行為）。"""

    async def get_response(self, path: str, scope):
        if not path.endswith(_INJECT_SUFFIXES):
            return await super().get_response(path, scope)
        base = Path(self.directory).resolve()
        full = (base / path).resolve()
        if not str(full).startswith(str(base) + os.sep) or not full.is_file():
            return await super().get_response(path, scope)  # 404/traversal 交回原邏輯
        req_headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        return _versioned_page(full, req_headers.get("if-none-match"))

# ---------------------------------------------------------------------------
# 5eu（架構健檢 W2）：重渲染回應快取常數。模組層以便測試 monkeypatch。
# 可快取＝GET 且輸出完全由 query 決定的渲染/資料端點；gallery/認證類刻意
# 不在列。資料異動入口有二：HTTP 變更端點（下方 MUTATING 前綴，middleware
# 自己看得到）與直接呼叫 reset_*_singleton()（測試換字型）——後者經
# cache_bus.bump() 通知，epoch 納入快取 key 即自然失效。
RENDER_CACHE_PREFIXES = (
    "/api/sutra", "/api/grid", "/api/notebook", "/api/letter",
    "/api/manuscript", "/api/wordart", "/api/mandala", "/api/patch",
    "/api/stamp", "/api/stencil", "/api/export",
    "/api/handwriting/reference",
)
RENDER_CACHE_MUTATING_PREFIXES = (
    "/api/user-dict", "/api/sutra/upload", "/api/sutra/user",
    "/api/sutra/builtin",
)
RENDER_CACHE_MAX_ITEM = 4 * 1024 * 1024    # 單條上限（篆書整頁 ~3.4MB）
RENDER_CACHE_MAX_TOTAL = 48 * 1024 * 1024  # 總預算（Render free 512MB 下保守）


def _load(char: str, source: str, hook_policy: str, auto_fix: bool = True):
    """Shared character loading pipeline for all endpoints."""
    if len(char) != 1:
        raise HTTPException(400, detail=f"expected a single character, got {char!r}")
    try:
        src = make_source(source)
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e
    try:
        c = src.get_character(char)
    except CharacterNotFound as e:
        raise HTTPException(404, detail=str(e)) from e
    # Phase 5ai-5av: characters from non-Han / outline-only pipelines
    # (punctuation, user dict, CNS-font fallback in Kai/Sung, MoE Song
    # 5av, MoE Lishu 5au, Chongxi Seal 5at) skip the Han-specific
    # validation / classification / smoothing — those assume MOE-grade
    # kaishu structure and would mis-classify hand-authored or
    # outline-only glyphs.
    ds_skip = c.data_source in (
        "punctuation", "user",
        "moe_song", "moe_lishu", "moe_kaishu", "chongxi_seal",
    )
    if ds_skip or (c.data_source or "").startswith("cns_font"):
        from ..validation import ValidationResult
        return c, ValidationResult(is_valid=True), False
    r = validate_character(c)
    applied_fix = False
    if auto_fix and r.fixable:
        c, applied_fix = apply_known_bug_fix(c)
    classify_character(c)
    apply_hook_policy(c, hook_policy)
    smooth_character(c)
    # Attach 5000.TXT decomposition (Phase 3)
    decomp = default_decomp_db().get(char)
    if decomp is not None:
        c.decomposition = decomp
    # Attach radical classification (Phase 4)
    radical = radical_lookup(char)
    if radical is not None:
        c.radical_category = f"{radical.category}/{radical.subcategory}"
    return c, r, applied_fix


def _upgrade_to_sung(c, style: str):
    """Phase 5am + 5av: layered Sung swap when ``style="mingti"``.

    Resolution order:

    1. **MoE 標準宋體** (``"moe_song"`` data_source, 25k Unicode chars,
       台灣權威) — Phase 5av addition. Try first because it's the
       authoritative Sung for Taiwan and ships with a clean BMP+Plane2
       cmap.
    2. **CNS 全字庫 Sung** (``"cns_font_sung"`` data_source, ~95k chars,
       broader rare-character coverage) — Phase 5am fallback for chars
       MoE doesn't carry.
    3. **No swap** — caller's downstream ``_apply_style`` falls back to
       the existing 5aj fake-Mingti filter.

    Both sources tag ``data_source`` so :class:`MingtiStyle` short-
    circuits and doesn't add fake serifs on top of real Sung outlines.
    """
    if c is None or style != "mingti":
        return c
    # Tier 1 — MoE 標準宋體 (5av).
    song = _get_song()
    if song.is_ready():
        try:
            return song.get_character(c.char)
        except CharacterNotFound:
            pass
    # Tier 2 — CNS Sung fallback for Plane-2/15 rare chars (5am).
    sung = _get_sung()
    if sung.is_ready():
        try:
            return sung.get_character(c.char)
        except CharacterNotFound:
            pass
    return c


def _upgrade_to_seal(c, style: str, *, seal_outline_mode: str = "skeleton"):
    """Phase 5at: swap a kaishu character for its 崇羲篆體 outline.

    Triggered when *all three* hold:

    1. The user requested ``style="seal_script"``.
    2. The seal-font source is ready (OTF installed).
    3. The font actually has a glyph for ``c.char``.

    On any failure the original ``c`` is returned unchanged — caller
    sees kaishu and a console warning rather than an error. Unlike
    :func:`_upgrade_to_sung`, the seal swap is **structural** (篆書 has
    different glyph composition than 楷書), so there is no graceful
    "filter fallback" — only "real seal font, or vanilla kaishu".

    The returned character then runs through the requested
    ``seal_outline_mode`` (default ``"skeleton"`` — v1 walker, which
    handles seal's simple topology well; see
    :mod:`stroke_order.sources.chongxi_seal`).
    """
    if c is None or style != "seal_script":
        return c
    seal = _get_seal()
    if not seal.is_ready():
        return c
    try:
        seal_c = seal.get_character(c.char)
        return _apply_seal_mode(seal_c, seal_outline_mode)
    except CharacterNotFound:
        return c
    except Exception:
        # 5ea: 真崇羲篆體某些 dense/degenerate 字形，其 skeleton/thinning
        # （見 chongxi_seal 警語「runs slow / OOMs on dense outlines」）會
        # 拋非 HTTPException 例外。呼叫端的 loader 只 catch HTTPException →
        # 單一字形失敗整頁 500、篆體全不出現。這裡在根部擋住：任何處理失敗
        # 一律退回楷書基底字（符合本函式「真篆體，或 vanilla 楷書」設計），
        # 讓其餘字形照常出篆體、整頁不 500。
        return c


def _upgrade_to_lishu(c, style: str, *, lishu_outline_mode: str = "skeleton"):
    """Phase 5au: swap a kaishu character for its 教育部隸書 outline.

    Mirrors :func:`_upgrade_to_sung` (the Phase-5am pattern): the user
    asked for ``style="lishu"``, and if MoE 隸書 is installed we hand
    back the real-font character with ``data_source = "moe_lishu"``.
    The 5aj :class:`LishuStyle` filter then short-circuits on that
    tag so it doesn't double-up the 波磔 + vertical squash.

    Falls through silently to kaishu when the font isn't present —
    user sees the existing 5aj fake-lishu filter.
    """
    if c is None or style != "lishu":
        return c
    lishu = _get_lishu()
    if not lishu.is_ready():
        return c
    try:
        lishu_c = lishu.get_character(c.char)
        return _apply_lishu_mode(lishu_c, lishu_outline_mode)
    except CharacterNotFound:
        return c
    except Exception:
        # 5ea: 同 _upgrade_to_seal——隸書亦走 skeleton 抽取（警語同上），
        # 單一字形處理失敗一律退回楷書基底字，絕不讓整頁 500。
        return c


# ---------------------------------------------------------------------------
# 5dp: 抄經預覽 502 修復——per-request char-loader 記憶化
# ---------------------------------------------------------------------------
# render_sutra_page 對**每個字位**都呼叫 char_loader(ch)（一頁 260 位），
# 而 _load 不快取——重複字每次重載，一頁心經（117 唯一字 / 260 位）純
# 載入就數秒~十幾秒，且端點是 async def、重活凍住 event loop（§9/5ck
# 應驗）→ Render 單 worker 逾時回 502。記憶化把「每字只載一次」，同一
# request 內同字回同一（唯讀）Character；PDF 多頁共用 loader 時省更多
# （跨頁重複字只載一次）。輸出與非記憶化逐位元相同（已驗）。
def _memoize_char_loader(fn):
    """Wrap a char-loader so each unique char is resolved at most once."""
    cache: dict = {}

    def cached(ch: str):
        if ch not in cache:
            cache[ch] = fn(ch)
        return cache[ch]

    return cached


# 5bz: outline-preserving loader for sutra preview + PDF
# ---------------------------------------------------------------------------
#
# render_sutra_page accepts an *optional* second char-loader that returns
# the outline-bearing version of skeleton-style chars. We build that loader
# by re-running the same upgrade chain as the main loader, but pass
# ``*_outline_mode="skip"`` to ``_upgrade_to_seal`` / ``_upgrade_to_lishu``
# so the lishu/seal sources hand back their original outline data
# (instead of skeletonising it).
#
# For kaishu/sung this returns the same Character as the main loader, but
# render_sutra_page will not consult outline_glyph_loader for them — the
# `_char_cut_paths` path already renders kaishu — so there's no double-
# render risk. We keep the helper simple.


def _build_sutra_outline_loader(
    *, source: str, style: str, hook_policy: str,
):
    """Return a CharLoader that yields *outline-bearing* Characters.

    Used as render_sutra_page's ``outline_glyph_loader`` when the user
    asks for the original-glyph preview (browser preview + PDF). For
    隸書 / 篆書 this swaps in the real font outline; for everything
    else it falls through to the standard kaishu loader.
    """
    def _loader(ch: str):
        try:
            c, _r, _ = _load(ch, source, hook_policy)
            c = _upgrade_to_sung(c, style)
            # IMPORTANT: pass mode="skip" to keep the outline intact for
            # the reference layer (default skeleton mode would discard
            # it, which is exactly the case we're working around).
            c = _upgrade_to_seal(c, style, seal_outline_mode="skip")
            c = _upgrade_to_lishu(c, style, lishu_outline_mode="skip")
            if style != "kaishu":
                c = _apply_style(c, style)
            return c
        except HTTPException:
            return None
    return _loader


# Phase 5b r28c: 共用 mandala char loader builder
# /api/mandala endpoint 跟 gallery upload thumbnail 都用這個構造 loader，
# 確保 server-side 渲染 mandala 字環時的 source / style / cns_mode pipeline 一致。
def build_mandala_char_loader(
    *, style: str = "kaishu", source: str = "auto",
    hook_policy: str = "animation", cns_outline_mode: str = "skip",
):
    """Return a CharLoader for mandala rendering.

    跟 /api/mandala endpoint 內 inline loader 邏輯一致：load → upgrade
    sung/seal/lishu → apply style filter → apply CNS outline mode。
    所有失敗路徑（HTTPException / 其他例外）回 None — 對應 mandala 模式的
    「missing chars 跳過 + auto-shrink 逃」邏輯。
    """
    def _loader(ch: str):
        try:
            c, _r, _ = _load(ch, source, hook_policy)
            c = _upgrade_to_sung(c, style)
            c = _upgrade_to_seal(c, style)
            c = _upgrade_to_lishu(c, style)
            if style != "kaishu":
                c = _apply_style(c, style)
            if cns_outline_mode != "skip":
                c = _apply_cns_mode(c, cns_outline_mode)
            return c
        except HTTPException:
            return None
        except Exception:
            return None
    return _loader


# ---- Phase 5cj/5ck: OpenCV.js 同源代抓 --------------------------------
#
# 5cj：校網防火牆擋外部 CDN → 本伺服器代抓＋落地快取（同源永不被擋）。
# 5ck：使用者實測仍卡「產生中…」，兩個根因一起修：
#   ① 原端點 async def ＋ 同步 requests.get —— 下載 11MB 期間整個
#      event loop 被凍住，全站無回應（最壞 120s×2 來源）。
#   ② 惰性下載 —— Render 免費 tier 每次部署/喚醒後快取皆空，第一個
#      使用者要全程陪等。
# 修法：抓檔邏輯抽到模組層同步函式（threadpool 與背景執行緒共用）、
# 啟動時背景預熱、串流下載＋原子換檔、/vendor/status 可觀察性。

# 5cl：Render 實測 docs.opencv.org 對資料中心出站回 403（bot 防護；
# 4.x 還會轉跳 4.13.0 再 403）。改以 npm 鏡像為主源——
# @techstark/opencv-js 的 dist/opencv.js 是官方原檔（其 README
# 明載），bits 相同、CDN 對 hotlink/資料中心友善。
# docs.opencv.org 降末位備援並補瀏覽器 UA（其 403 疑似 UA 過濾）。
#
# 5da：家用機實測破案——4.9.0-release.3 的 WASM runtime init 在
# 新版 Chrome（149 實測）永久懸掛：importScripts 數百 ms 完成、
# cv Promise 永不 resolve；微型 WASM 模組同機秒過＝非 WASM 封鎖。
# 4.11.0-release.1 同機同管道 759ms 完整就緒（cv.Mat ready）。
# 回頭看，先前判定的「受管理電腦環境層懸掛」極可能一直就是這個
# 版本不相容。pin 升 4.11，且把版本寫進快取檔名——升級自動失效
# 舊快取（Render 燒入檔與本機 ~/.stroke-order/vendor 都適用）。
_OPENCV_VERSION = "4.11.0-release.1"
_OPENCV_CACHE_FNAME = "opencv-4.11.0.js"
# 5da：docs.opencv.org 退出清單——實測只掛 4.9.0/4.13.0（4.11.0
# 回 404），且它對資料中心 403（5cl）、4.9.0 又會懸掛；同源＋
# 兩個 npm CDN 已足（§8.2：實測不存在的 URL 不入 pin 清單）。
_OPENCV_SOURCES = (
    f"https://cdn.jsdelivr.net/npm/@techstark/opencv-js@{_OPENCV_VERSION}"
    "/dist/opencv.js",
    f"https://unpkg.com/@techstark/opencv-js@{_OPENCV_VERSION}"
    "/dist/opencv.js",
)
_OPENCV_FETCH_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
}
_OPENCV_MIN_BYTES = 1_000_000

# 5cn：opentype.js（MIT）——「自訂字型」瀏覽器端解析 TTF/OTF 用。
# 同一套同源代抓管線（校網/防火牆免疫、零執行期外網依賴給前端）。
_OPENTYPE_SOURCES = (
    "https://cdn.jsdelivr.net/npm/opentype.js@1.3.4/dist/opentype.min.js",
    "https://unpkg.com/opentype.js@1.3.4/dist/opentype.min.js",
)
_OPENTYPE_MIN_BYTES = 100_000
_vendor_fetch_lock = threading.Lock()
_opencv_prewarm_started = False


def _vendor_cache_path(fname: str) -> Path:
    vendor_dir = Path(os.environ.get(
        "STROKE_ORDER_VENDOR_DIR",
        str(Path.home() / ".stroke-order" / "vendor")))
    return vendor_dir / fname


def _opencv_cache_path() -> Path:
    # 5da：檔名帶版本——pin 升級自動失效舊快取
    return _vendor_cache_path(_OPENCV_CACHE_FNAME)


def _ensure_vendor_cached(fname: str, sources: tuple[str, ...],
                          min_bytes: int, timeout: float = 90.0) -> Path:
    """確保 vendor 檔已落地快取；缺檔時同步代抓（可重入）。

    - 快取命中：不進鎖直接回（熱路徑零開銷）。
    - 缺檔：單一執行緒下載（鎖防預熱與端點重複抓），串流寫入
      .part 暫存檔、驗尺寸後原子 replace——絕不 serve 半檔。
    """
    cache = _vendor_cache_path(fname)
    if cache.is_file() and cache.stat().st_size >= min_bytes:
        return cache
    import requests as _rq
    with _vendor_fetch_lock:
        if cache.is_file() and cache.stat().st_size >= min_bytes:
            return cache                    # 等鎖期間別人已抓完
        cache.parent.mkdir(parents=True, exist_ok=True)
        last_err: Optional[Exception] = None
        for url in sources:
            try:
                with _rq.get(url, timeout=(10, timeout), stream=True,
                             headers=_OPENCV_FETCH_HEADERS) as r:
                    r.raise_for_status()
                    tmp = cache.with_name(fname + ".part")
                    size = 0
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            f.write(chunk)
                            size += len(chunk)
                    if size < min_bytes:
                        raise ValueError(f"{fname} 過小：{size}B")
                    tmp.replace(cache)
                    return cache
            except Exception as e:          # noqa: BLE001 — 逐源重試
                last_err = e
        raise RuntimeError(f"{fname} 代抓失敗：{last_err}")


def _ensure_opencv_cached(timeout: float = 90.0) -> Path:
    return _ensure_vendor_cached(
        _OPENCV_CACHE_FNAME, _OPENCV_SOURCES, _OPENCV_MIN_BYTES, timeout)


def _ensure_opentype_cached(timeout: float = 90.0) -> Path:
    return _ensure_vendor_cached(
        "opentype.min.js", _OPENTYPE_SOURCES, _OPENTYPE_MIN_BYTES, timeout)


def _prewarm_opencv_cache() -> None:
    """5ck：啟動時背景預熱（daemon thread；失敗不影響服務，
    端點屆時會在 threadpool 內補抓）。每個行程只啟動一次。
    5cn：一併預熱 opentype.min.js。"""
    global _opencv_prewarm_started
    if _opencv_prewarm_started or os.environ.get("STROKE_ORDER_NO_PREFETCH"):
        return
    _opencv_prewarm_started = True

    def _job() -> None:
        for fn in (_ensure_opencv_cached, _ensure_opentype_cached):
            try:
                fn()
            except Exception:               # noqa: BLE001 — 預熱盡力而為
                pass

    threading.Thread(target=_job, name="vendor-prewarm", daemon=True).start()


def create_app() -> FastAPI:
    app = FastAPI(
        title="stroke-order",
        version="0.3.0",
        description="中文字 → 向量筆跡轉換器（寫字機器人專用）",
    )

    # 5eu（W2）：重渲染回應快取＋ETag。**純 ASGI middleware**、不用
    # BaseHTTPMiddleware——後者會把所有回應轉成無 content-length 的
    # streaming，讓外層 GZip 的 minimum_size 失效（小回應也被壓）。
    # 純 ASGI 讓不匹配路徑原封穿過；只有可快取渲染路徑才緩衝本體。
    # 註冊在 GZip 之前＝最內層：存未壓縮本體，壓縮仍由外層 GZip 處理。
    render_cache: "OrderedDict[str, tuple[bytes, list]]" = OrderedDict()
    render_cache_stat = {"bytes": 0, "hits": 0, "misses": 0}

    def _render_cache_evict():
        while (
            render_cache_stat["bytes"] > RENDER_CACHE_MAX_TOTAL and render_cache
        ):
            _, (old_body, _h) = render_cache.popitem(last=False)
            render_cache_stat["bytes"] -= len(old_body)

    class _RenderCacheMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                return await self.app(scope, receive, send)
            path = scope["path"]
            method = scope["method"]

            if method != "GET":
                if not path.startswith(RENDER_CACHE_MUTATING_PREFIXES):
                    return await self.app(scope, receive, send)
                # 資料異動端點：成功（<400）才 bump 全域失效
                seen = {}

                async def send_watch(message):
                    if message["type"] == "http.response.start":
                        seen["status"] = message["status"]
                    await send(message)

                await self.app(scope, receive, send_watch)
                if seen.get("status", 500) < 400:
                    cache_bus.bump()
                return

            if not path.startswith(RENDER_CACHE_PREFIXES):
                return await self.app(scope, receive, send)

            query = scope.get("query_string", b"").decode("latin-1")
            key = f"{cache_bus.epoch()}|{path}?{query}"
            req_headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in scope.get("headers", [])
            }

            hit = render_cache.get(key)
            if hit is not None:
                body, headers = hit
                render_cache.move_to_end(key)
                render_cache_stat["hits"] += 1
                etag = dict(headers)["etag"]
                if req_headers.get("if-none-match") == etag:
                    await _send_simple(send, 304, [(b"etag", etag.encode())], b"")
                    return
                out = [
                    (k.encode(), v.encode()) for k, v in headers
                    if k != "etag"
                ]
                out += [
                    (b"content-length", str(len(body)).encode()),
                    (b"etag", etag.encode()),
                    (b"x-render-cache", b"hit"),
                ]
                await _send_simple(send, 200, out, body)
                return

            # miss：緩衝完整回應 → 計 ETag → 入庫 → 補 header 後送出
            cap = {"status": None, "headers": [], "body": bytearray()}

            async def send_capture(message):
                if message["type"] == "http.response.start":
                    cap["status"] = message["status"]
                    cap["headers"] = list(message.get("headers", []))
                elif message["type"] == "http.response.body":
                    cap["body"] += message.get("body", b"")
                    if message.get("more_body"):
                        return
                # 全部收齊才動作（在結尾統一送出）

            await self.app(scope, receive, send_capture)
            body = bytes(cap["body"])
            status = cap["status"] if cap["status"] is not None else 500
            hdr_pairs = [
                (k.decode("latin-1").lower(), v.decode("latin-1"))
                for k, v in cap["headers"]
            ]
            hdr_map = dict(hdr_pairs)
            if status != 200 or "set-cookie" in hdr_map:
                out = [
                    (k.encode(), v.encode()) for k, v in hdr_pairs
                ]
                await _send_simple(send, status, out, body)
                return

            render_cache_stat["misses"] += 1
            etag = f'W/"{hashlib.md5(body).hexdigest()[:20]}"'
            keep = [
                (k, v) for k, v in hdr_pairs
                if k in ("content-type", "content-disposition")
                or k.startswith("x-")
            ]
            if len(body) <= RENDER_CACHE_MAX_ITEM:
                render_cache[key] = (body, keep + [("etag", etag)])
                render_cache_stat["bytes"] += len(body)
                _render_cache_evict()
            out = [(k.encode(), v.encode()) for k, v in keep]
            out += [
                (b"content-length", str(len(body)).encode()),
                (b"etag", etag.encode()),
                (b"x-render-cache", b"miss"),
            ]
            await _send_simple(send, 200, out, body)

    async def _send_simple(send, status, headers, body):
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": headers,
        })
        await send({"type": "http.response.body", "body": body})

    app.add_middleware(_RenderCacheMiddleware)
    app.state.render_cache_stat = render_cache_stat

    # W1-B（架構健檢 2026-07-18）：大型 SVG/JSON 回應壓縮。心經整頁 SVG
    # 1.25MB → 約 150KB；zhuyin_tw.json 454KB → 約 60KB。
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # W1-B：/static 快取策略——帶 ?v= 版本參數的資源可長快取（URL 即快取
    # 鍵，改版即失效，見 PRINCIPLES §11.4）；未帶版本的短快取靠 ETag 再驗證。
    @app.middleware("http")
    async def _static_cache_headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/") and response.status_code == 200:
            if "v" in request.query_params:
                response.headers.setdefault(
                    "Cache-Control", "public, max-age=604800"
                )
            else:
                response.headers.setdefault("Cache-Control", "public, max-age=3600")
        return response

    if STATIC_DIR.is_dir():
        # 5ev：版本注入型靜態服務（?v=__V__ → APP_VERSION）
        app.mount(
            "/static", _VersionedStaticFiles(directory=STATIC_DIR), name="static"
        )

    # ------ W3-R1：路由分組（機械搬遷，行為零變） -----------------------
    # 87 條路由拆進 web/routes/ 七群 APIRouter；include 順序＝拆檔前
    # 註冊順序。延遲 import 見 routes/__init__.py 說明（避免循環）。
    from . import routes as _routes
    from .routes import gallery as _routes_gallery

    for _router in _routes.all_routers():
        app.include_router(_router)

    # gallery 開機清掃：保留「每次 create_app 都掃」的原行為
    _routes_gallery.on_boot()

    return app


def __getattr__(name: str):
    """W3-R1：``app`` 改惰性建立（PEP 562）。

    模組層 ``app = create_app()`` 會在 server 模組還沒執行完時就去
    import routes——若使用端先 import routes 模組，兩邊互等成循環。
    uvicorn 的 "stroke_order.web.server:app" 走屬性存取，第一次取用
    才建 app，行為不變。
    """
    if name == "app":
        application = create_app()
        globals()["app"] = application
        return application
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def run(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Start the uvicorn dev server."""
    import uvicorn
    uvicorn.run(
        "stroke_order.web.server:app",
        host=host, port=port, reload=reload,
    )


__all__ = ["app", "create_app", "run"]


if __name__ == "__main__":
    # Allows `python -m stroke_order.web.server`
    import argparse
    ap = argparse.ArgumentParser(description="stroke-order Web UI")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action="store_true")
    args = ap.parse_args()
    print(f"[ok] starting stroke-order web UI on "
          f"http://{args.host}:{args.port}/")
    run(host=args.host, port=args.port, reload=args.reload)