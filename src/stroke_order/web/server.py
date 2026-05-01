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

import io
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi import Path as ApiPath
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
)
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


class PatchPostRequest(BaseModel):
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
    border_padding_mm: float = 2.0
    style: str = "kaishu"
    source: str = "auto"
    hook_policy: str = "animation"
    decorations: list[PatchDecorationSpec] = []
    laser_power: int = 255
    feed: float = 1500.0
    format: str = "svg"   # svg | gcode


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


def _content_disposition(basename: str, ext: str) -> str:
    """RFC 5987-compliant attachment header supporting Unicode filenames."""
    ascii_fallback = f"char.{ext}"  # plain ASCII for old clients
    utf8_encoded = quote(f"{basename}.{ext}", safe="")
    return (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{utf8_encoded}"
    )

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
    except CharacterNotFound:
        return c
    return _apply_seal_mode(seal_c, seal_outline_mode)


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
    except CharacterNotFound:
        return c
    return _apply_lishu_mode(lishu_c, lishu_outline_mode)


# ---------------------------------------------------------------------------
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


def create_app() -> FastAPI:
    app = FastAPI(
        title="stroke-order",
        version="0.3.0",
        description="中文字 → 向量筆跡轉換器（寫字機器人專用）",
    )

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # ------ root index ---------------------------------------------------

    @app.get("/", include_in_schema=False)
    async def index():
        index_path = STATIC_DIR / "index.html"
        if not index_path.is_file():
            return PlainTextResponse(
                "Web UI not bundled. See source at /api/character/{char}",
                status_code=200,
            )
        return FileResponse(index_path)

    # 5bd: dedicated full-screen sutra editor (subpage)
    @app.get("/sutra-editor", include_in_schema=False)
    async def sutra_editor_page():
        page = STATIC_DIR / "sutra-editor.html"
        if not page.is_file():
            return PlainTextResponse(
                "Editor page missing — static/sutra-editor.html not bundled.",
                status_code=404,
            )
        return FileResponse(page)

    # 5d-1: dedicated handwriting practice page (PSD — Personal Stroke
    # Database). Independent web app; collects stroke trajectories with
    # timestamps + pressure + tilt for driving handwriting robots,
    # especially valuable for fonts that lack real stroke-order data
    # (隸書 / 篆書 / 草書 / 行書).
    @app.get("/handwriting", include_in_schema=False)
    async def handwriting_page():
        page = STATIC_DIR / "handwriting.html"
        if not page.is_file():
            return PlainTextResponse(
                "Handwriting practice page missing — "
                "static/handwriting.html not bundled.",
                status_code=404,
            )
        return FileResponse(page)

    # ------ data endpoints ----------------------------------------------

    @app.get("/api/character/{char}")
    async def character_data(
        char: str,
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
    ):
        """hanzi-writer-compatible stroke data (for the front-end canvas)."""
        c, _r, _ = _load(char, source, hook_policy)
        return character_to_hanzi_writer_dict(c)

    # 5d-7: outline-only character data in native EM 2048 (Y-down) for the
    # handwriting practice page's reference layer. Unlike /api/character
    # which serves hanzi-writer-coord JSON, this returns raw outline cmds
    # so the practice canvas can render the reference glyph at exactly the
    # same coord system the user's strokes are captured in (EM 2048).
    # Lishu/seal force outline_mode='skip' to preserve the outline (the
    # default 'skeleton' mode would discard it — see 5bz).
    @app.get("/api/handwriting/reference/{char}")
    async def handwriting_reference(
        char: str,
        style: str = Query("kaishu", pattern=_STYLE_PATTERN),
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
    ):
        from ..ir import EM_SIZE
        try:
            c, _r, _ = _load(char, source, hook_policy)
            c = _upgrade_to_sung(c, style)
            c = _upgrade_to_seal(c, style, seal_outline_mode="skip")
            c = _upgrade_to_lishu(c, style, lishu_outline_mode="skip")
            if style != "kaishu":
                c = _apply_style(c, style)
        except HTTPException:
            raise
        return {
            "char": char,
            "style": style,
            "em_size": EM_SIZE,
            "strokes": [
                {"outline": s.outline} for s in c.strokes if s.outline
            ],
        }

    @app.get("/api/meta/{char}")
    async def character_meta(
        char: str,
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
    ):
        """Diagnostics — classification codes, bbox, validation notes."""
        c, report, applied_fix = _load(char, source, hook_policy)
        d = character_to_dict(c)
        d["validation"] = {
            "is_valid": report.is_valid,
            "fixable": report.fixable,
            "fix_description": report.fix_description,
            "errors": report.errors,
            "warnings": report.warnings,
            "fix_was_applied": applied_fix,
        }
        return d

    # ------ 組件分析 (Phase A, 6b) ---------------------------------------
    # See docs/VISION.md and docs/decisions/2026-04-28_phase_a_backend.md.
    # Backend logic lives in stroke_order.components.

    @app.get("/api/components/{char}")
    async def components_data(char: str):
        """Component decomposition for a single character.

        Returns:
            char: input character
            ids: IDS structure string (e.g. ``⿰木目`` for 相);
                 equals char itself for atomic chars
            leaves: ordered list of leaf components (atomic-level)
            leaves_distinct: deduplicated leaves (set as list)
            is_atomic: True if char has no IDS structure
        """
        from ..components import decompose, default_ids_map, is_atomic
        if len(char) != 1:
            raise HTTPException(400, detail="Single character required")
        ids_map = default_ids_map()
        leaves = decompose(char, ids_map)
        return {
            "char": char,
            "ids": ids_map.get(char, char),
            "leaves": leaves,
            "leaves_distinct": list(dict.fromkeys(leaves)),
            "is_atomic": is_atomic(char, ids_map),
        }

    @app.get("/api/coverset/list")
    async def coverset_list():
        """List built-in cover-sets (metadata only — no char lists)."""
        from ..components import list_coversets
        return {"coversets": list_coversets()}

    @app.get("/api/coverset/{name}")
    async def coverset_data(name: str):
        """Detailed cover-set: chars + decomposition stats.

        Returns name, title, source, url, size, chars (trad), chars_simp,
        and ``distinct_components`` (computed from current IDS data).
        """
        from ..components import (
            collect_components,
            default_ids_map,
            load_coverset,
        )
        try:
            cs = load_coverset(name)
        except KeyError:
            raise HTTPException(404, detail=f"Unknown cover-set {name!r}")

        ids_map = default_ids_map()
        components = collect_components(cs.chars, ids_map)
        return {
            "name": cs.name,
            "title": cs.title,
            "description": cs.description,
            "size": cs.size,
            "source": cs.source,
            "url": cs.url,
            "chars": list(cs.chars),
            "chars_simp": list(cs.chars_simp),
            "distinct_components": len(components),
        }

    @app.post("/api/coverage/recommend")
    async def coverage_recommend(req: CoverageRecommendRequest):
        """Greedy set-cover: recommend next char(s) to write.

        Returns top-k recommendations + overall coverage status (covered
        component count, target component count, composable char count).
        Zero-gain candidates are excluded.
        """
        from ..components import (
            coverage_status,
            default_ids_map,
            load_coverset,
            recommend_next,
        )
        try:
            cs = load_coverset(req.coverset)
        except KeyError:
            raise HTTPException(
                404, detail=f"Unknown cover-set {req.coverset!r}"
            )

        ids_map = default_ids_map()
        written = list(req.written_chars)
        recs = recommend_next(written, cs.chars, ids_map, top_k=req.top_k)
        status = coverage_status(written, cs.chars, ids_map)

        return {
            "coverset": cs.name,
            "written_count": len(written),
            "recommendations": [
                {
                    "char": r.char,
                    "new_components": list(r.new_components),
                    "existing_components": list(r.existing_components),
                    "gain": r.gain,
                }
                for r in recs
            ],
            "coverage": {
                "covered_count": status["covered_count"],
                "target_count": status["target_count"],
                "coverage_ratio": status["coverage_ratio"],
                "composable_count": status["composable_count"],
                "composable_ratio": status["composable_ratio"],
            },
        }

    # ------ 筆記模式 (notebook) -----------------------------------------

    @app.get("/api/notebook/capacity")
    async def notebook_capacity(
        text: str = Query("", max_length=8000),
        preset: str = Query("large", pattern="^(small|medium|large|letter)$"),
        grid_style: str = Query("square",
                                pattern="^(square|ruled|dotted|none)$"),
        line_height_mm: Optional[float] = Query(None, gt=3, le=30),
        margin_mm: Optional[float] = Query(None, ge=0, le=50),
        doodle_zone: bool = Query(False),
        doodle_zone_size_mm: float = Query(40.0, gt=10, le=200),
        doodle_zone_x_mm: Optional[float] = Query(None, ge=0, le=500),
        doodle_zone_y_mm: Optional[float] = Query(None, ge=0, le=500),
        doodle_zone_width_mm: Optional[float] = Query(None, gt=5, le=400),
        doodle_zone_height_mm: Optional[float] = Query(None, gt=5, le=400),
        zones_json: Optional[str] = Query(
            None, description="Phase 5s: JSON array of zones [{x,y,w,h,...}]"
        ),
        direction: str = Query("horizontal",
                               pattern="^(horizontal|vertical)$"),
        lines_per_page: Optional[int] = Query(None, ge=1, le=100,
            description="Override line_height to fit exactly N rows/columns"),
    ):
        """Preflight: how many chars fit per page with these settings?"""
        import json
        from ..exporters.notebook import build_notebook_layout
        from ..layouts import layout_capacity, estimate_pages

        zones_list = None
        if zones_json:
            try:
                zones_list = json.loads(zones_json)
            except json.JSONDecodeError:
                raise HTTPException(422, detail="invalid zones_json")

        layout = build_notebook_layout(
            preset=preset, grid_style=grid_style,           # type: ignore
            line_height_mm=line_height_mm, margin_mm=margin_mm,
            doodle_zone=doodle_zone,
            doodle_zone_size_mm=doodle_zone_size_mm,
            doodle_zone_x_mm=doodle_zone_x_mm,
            doodle_zone_y_mm=doodle_zone_y_mm,
            doodle_zone_width_mm=doodle_zone_width_mm,
            doodle_zone_height_mm=doodle_zone_height_mm,
            lines_per_page=lines_per_page,
            direction=direction,  # type: ignore
            zones=zones_list,
        )
        cap = layout_capacity(layout, direction=direction)  # type: ignore
        cap["total_chars"] = sum(1 for c in text if not c.isspace())
        cap["pages_estimated"] = estimate_pages(text, layout,
                                                direction=direction)  # type: ignore
        cap["page_size_mm"] = [layout.size.width_mm, layout.size.height_mm]
        cap["line_height_mm"] = layout.line_height_mm
        cap["margin_mm"] = {
            "top": layout.margin_top_mm, "bottom": layout.margin_bottom_mm,
            "left": layout.margin_left_mm, "right": layout.margin_right_mm,
        }
        # Phase 5p: auto default for first_line_offset_mm (also = minimum)
        if direction == "vertical":
            cap["default_first_line_offset_mm"] = round(
                layout.margin_right_mm + layout.char_width_mm, 3)
        else:
            cap["default_first_line_offset_mm"] = round(
                layout.margin_top_mm + layout.line_height_mm, 3)
        return cap

    @app.get("/api/notebook")
    async def notebook(
        text: str = Query(..., min_length=1, max_length=4000),
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
        preset: str = Query("large", pattern="^(small|medium|large|letter)$"),
        grid_style: str = Query("square",
                                pattern="^(square|ruled|dotted|none)$"),
        line_height_mm: Optional[float] = Query(None, gt=3, le=30),
        margin_mm: Optional[float] = Query(None, ge=0, le=50),
        doodle_zone: bool = Query(False),
        doodle_zone_size_mm: float = Query(40.0, gt=10, le=200),
        doodle_zone_x_mm: Optional[float] = Query(None, ge=0, le=500),
        doodle_zone_y_mm: Optional[float] = Query(None, ge=0, le=500),
        doodle_zone_width_mm: Optional[float] = Query(None, gt=5, le=400),
        doodle_zone_height_mm: Optional[float] = Query(None, gt=5, le=400),
        zones_json: Optional[str] = Query(
            None, description="Phase 5s: JSON array of zones [{x,y,w,h,...}]"
        ),
        cell_style: str = Query("ghost",
                                pattern="^(outline|trace|filled|ghost|blank)$"),
        page: Optional[int] = Query(None, ge=1),
        download: bool = Query(False),
        direction: str = Query("horizontal",
                               pattern="^(horizontal|vertical)$"),
        lines_per_page: Optional[int] = Query(None, ge=1, le=100,
            description="Override line_height to fit exactly N rows/columns"),
        first_line_offset_mm: Optional[float] = Query(
            None, ge=0, le=400,
            description="First row bottom (橫) / first col left-from-right (直)"
        ),
        format: str = Query("svg", pattern="^(svg|gcode|json)$",
                            description="Phase 5v: svg | gcode | json"),
        style: str = Query(
            "kaishu", pattern=_STYLE_PATTERN,
            description="Phase 5aj: stroke-filter style (kaishu/mingti/lishu/bold)",
        ),
        cns_outline_mode: str = Query(
            "skip", pattern=_CNS_MODE_PATTERN,
            description="Phase 5al: how to render CNS-font fallback chars "
                        "(skip/trace/skeleton)",
        ),
    ):
        from ..exporters.notebook import (
            flow_notebook, render_notebook_page_svg,
            render_notebook_gcode, render_notebook_json,
        )
        from ..exporters.multi_page import render_pages_as_single_or_zip
        from ..layouts import layout_capacity

        def loader(ch: str):
            try:
                c, _r, _ = _load(ch, source, hook_policy)
                c = _upgrade_to_sung(c, style)   # Phase 5am: real Sung outline
                c = _upgrade_to_seal(c, style)   # Phase 5at: real seal outline
                c = _upgrade_to_lishu(c, style)  # Phase 5au: real lishu outline
                if style != "kaishu":
                    c = _apply_style(c, style)
                if cns_outline_mode != "skip":
                    c = _apply_cns_mode(c, cns_outline_mode)
                return c
            except HTTPException:
                return None

        import json as _json
        zones_list = None
        if zones_json:
            try:
                zones_list = _json.loads(zones_json)
            except _json.JSONDecodeError:
                raise HTTPException(422, detail="invalid zones_json")

        pages = flow_notebook(
            text, loader, preset=preset, grid_style=grid_style,  # type: ignore
            line_height_mm=line_height_mm, margin_mm=margin_mm,
            doodle_zone=doodle_zone,
            doodle_zone_size_mm=doodle_zone_size_mm,
            doodle_zone_x_mm=doodle_zone_x_mm,
            doodle_zone_y_mm=doodle_zone_y_mm,
            doodle_zone_width_mm=doodle_zone_width_mm,
            doodle_zone_height_mm=doodle_zone_height_mm,
            direction=direction,  # type: ignore
            lines_per_page=lines_per_page,
            first_line_offset_mm=first_line_offset_mm,
            zones=zones_list,
        )
        cap_headers = {
            "X-Capacity-Per-Page":
                str(layout_capacity(pages[0].layout, direction=direction)  # type: ignore
                    ["chars_per_page"])
                if pages else "0"
        }

        # Phase 5v: alternate output formats
        if format == "gcode":
            body = render_notebook_gcode(pages, cell_style=cell_style)  # type: ignore
            headers = {**cap_headers,
                       "X-Stroke-Order-Pages": str(len(pages))}
            if download:
                headers["Content-Disposition"] = _content_disposition(
                    "notebook", "gcode")
            return Response(content=body,
                            media_type="text/plain; charset=utf-8",
                            headers=headers)
        if format == "json":
            body = render_notebook_json(pages, cell_style=cell_style)  # type: ignore
            headers = {**cap_headers,
                       "X-Stroke-Order-Pages": str(len(pages))}
            if download:
                headers["Content-Disposition"] = _content_disposition(
                    "notebook", "json")
            return Response(content=body,
                            media_type="application/json; charset=utf-8",
                            headers=headers)

        # Single-page request: ?page=N returns that page's SVG
        if page is not None:
            if page > len(pages):
                raise HTTPException(
                    404, detail=f"page {page} not found; only {len(pages)} pages"
                )
            svg = render_notebook_page_svg(pages[page - 1], cell_style=cell_style)
            headers = {}
            if download:
                headers["Content-Disposition"] = _content_disposition(
                    f"notebook-page-{page:02d}", "svg"
                )
            return Response(content=svg, media_type="image/svg+xml",
                            headers=headers)

        def _render(p):
            return render_notebook_page_svg(p, cell_style=cell_style)

        body, mime, ext = render_pages_as_single_or_zip(
            pages, _render, filename_prefix="notebook-page"
        )
        headers: dict[str, str] = {
            "X-Stroke-Order-Pages": str(len(pages)),
            **cap_headers,
        }
        if download:
            headers["Content-Disposition"] = _content_disposition(
                "notebook", ext
            )
        return Response(content=body, media_type=mime, headers=headers)

    # ------ Phase 5s: POST variant for zones with svg_content ------------

    @app.post("/api/notebook")
    async def notebook_post(req: NotebookPostRequest):
        """POST variant — accepts arbitrary-sized SVG content in zones."""
        from ..exporters.notebook import (
            flow_notebook, render_notebook_page_svg,
            render_notebook_gcode, render_notebook_json,
        )
        from ..exporters.multi_page import render_pages_as_single_or_zip

        def loader(ch: str):
            try:
                c, _r, _ = _load(ch, req.source, req.hook_policy)
                c = _upgrade_to_sung(c, req.style)   # Phase 5am
                c = _upgrade_to_seal(c, req.style)   # Phase 5at
                c = _upgrade_to_lishu(c, req.style)  # Phase 5au
                if req.style != "kaishu":
                    c = _apply_style(c, req.style)
                # Phase 5al: NotebookPostRequest doesn't expose cns_outline_mode
                # yet; default "skip" matches the existing behaviour.
                return c
            except HTTPException:
                return None

        zones_dicts = [z.model_dump() for z in req.zones]

        pages = flow_notebook(
            req.text, loader, preset=req.preset,   # type: ignore
            grid_style=req.grid_style,              # type: ignore
            line_height_mm=req.line_height_mm, margin_mm=req.margin_mm,
            direction=req.direction,                # type: ignore
            lines_per_page=req.lines_per_page,
            first_line_offset_mm=req.first_line_offset_mm,
            zones=zones_dicts,
        )

        # Phase 5v: non-svg formats
        if req.format == "gcode":
            body = render_notebook_gcode(pages,
                                          cell_style=req.cell_style)  # type: ignore
            return Response(content=body,
                            media_type="text/plain; charset=utf-8",
                            headers={"X-Stroke-Order-Pages": str(len(pages))})
        if req.format == "json":
            body = render_notebook_json(pages,
                                         cell_style=req.cell_style)  # type: ignore
            return Response(content=body,
                            media_type="application/json; charset=utf-8",
                            headers={"X-Stroke-Order-Pages": str(len(pages))})

        if req.page is not None:
            if req.page > len(pages):
                raise HTTPException(
                    404, detail=f"page {req.page} not found; only {len(pages)} pages"
                )
            svg = render_notebook_page_svg(
                pages[req.page - 1], cell_style=req.cell_style)  # type: ignore
            return Response(content=svg, media_type="image/svg+xml",
                            headers={"X-Stroke-Order-Pages": str(len(pages))})

        def _render(p):
            return render_notebook_page_svg(p, cell_style=req.cell_style)  # type: ignore

        body, mime, ext = render_pages_as_single_or_zip(
            pages, _render, filename_prefix="notebook-page"
        )
        return Response(
            content=body, media_type=mime,
            headers={"X-Stroke-Order-Pages": str(len(pages))},
        )

    # ------ 信紙模式 (letter) ------------------------------------------

    @app.get("/api/letter/capacity")
    async def letter_capacity(
        text: str = Query("", max_length=8000),
        preset: str = Query("A4", pattern="^(A4|A5|Letter)$"),
        line_height_mm: Optional[float] = Query(None, gt=3, le=30),
        margin_mm: Optional[float] = Query(None, ge=0, le=50),
        title_space_mm: float = Query(0.0, ge=0, le=80),
        signature_space_mm: float = Query(0.0, ge=0, le=80),
        direction: str = Query("horizontal",
                               pattern="^(horizontal|vertical)$"),
        lines_per_page: Optional[int] = Query(
            None, ge=1, le=100,
            description="Phase 5ab: override line_height to fit exactly N rows/columns",
        ),
    ):
        from ..exporters.letter import build_letter_layout
        from ..layouts import layout_capacity, estimate_pages
        layout = build_letter_layout(
            preset=preset, line_height_mm=line_height_mm,  # type: ignore
            margin_mm=margin_mm,
            title_space_mm=title_space_mm,
            signature_space_mm=signature_space_mm,
            direction=direction,  # type: ignore
            lines_per_page=lines_per_page,
        )
        cap = layout_capacity(layout, direction=direction)  # type: ignore
        cap["total_chars"] = sum(1 for c in text if not c.isspace())
        cap["pages_estimated"] = estimate_pages(text, layout,
                                                direction=direction)  # type: ignore
        cap["page_size_mm"] = [layout.size.width_mm, layout.size.height_mm]
        cap["line_height_mm"] = layout.line_height_mm
        cap["margin_mm"] = {
            "top": layout.margin_top_mm, "bottom": layout.margin_bottom_mm,
            "left": layout.margin_left_mm, "right": layout.margin_right_mm,
        }
        # Phase 5aa: auto default for first_line_offset_mm (also = minimum).
        # Note: for 橫 letter the "top edge" of content includes the reserved
        # title_space (layout.margin_top_mm already = my + title_space_mm),
        # so the first row's ending-edge auto = margin_top + line_height
        # lands right below the title band — identical semantics to notebook.
        if direction == "vertical":
            cap["default_first_line_offset_mm"] = round(
                layout.margin_right_mm + layout.char_width_mm, 3)
        else:
            cap["default_first_line_offset_mm"] = round(
                layout.margin_top_mm + layout.line_height_mm, 3)
        return cap

    @app.get("/api/letter")
    async def letter(
        text: str = Query(..., min_length=1, max_length=8000),
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
        preset: str = Query("A4", pattern="^(A4|A5|Letter)$"),
        line_height_mm: Optional[float] = Query(None, gt=3, le=30),
        margin_mm: Optional[float] = Query(None, ge=0, le=50),
        title_space_mm: float = Query(0.0, ge=0, le=80),
        signature_space_mm: float = Query(0.0, ge=0, le=80),
        cell_style: str = Query("outline",
                                pattern="^(outline|trace|filled|ghost|blank)$"),
        decorative_border: bool = Query(True),
        title_text: str = Query(""),
        signature_text: str = Query(""),
        date_text: str = Query(""),
        title_size_mm: Optional[float] = Query(None, gt=1, le=50),
        signature_size_mm: Optional[float] = Query(None, gt=1, le=50),
        date_size_mm: Optional[float] = Query(None, gt=1, le=50),
        signature_lines_after_body: int = Query(1, ge=0, le=20),
        signature_align: str = Query("right", pattern="^(left|right|center)$"),
        page: Optional[int] = Query(None, ge=1),
        download: bool = Query(False),
        direction: str = Query("horizontal",
                               pattern="^(horizontal|vertical)$"),
        first_line_offset_mm: Optional[float] = Query(
            None, ge=0, le=400,
            description="Phase 5aa: first row bottom (橫) / first col left-from-right (直)",
        ),
        lines_per_page: Optional[int] = Query(
            None, ge=1, le=100,
            description="Phase 5ab: override line_height to fit exactly N rows/columns",
        ),
        format: str = Query(
            "svg", pattern="^(svg|gcode|json)$",
            description="Phase 5ac: svg | gcode | json",
        ),
        show_grid: bool = Query(
            True,
            description="Phase 5af: draw the ruled writing grid",
        ),
        style: str = Query(
            "kaishu", pattern=_STYLE_PATTERN,
            description="Phase 5aj: stroke-filter style",
        ),
        cns_outline_mode: str = Query(
            "skip", pattern=_CNS_MODE_PATTERN,
            description="Phase 5al: CNS-font fallback render mode",
        ),
    ):
        from ..exporters.letter import (
            flow_letter, render_letter_page_svg,
            render_letter_gcode, render_letter_json,
        )
        from ..exporters.multi_page import render_pages_as_single_or_zip
        from ..layouts import layout_capacity

        def loader(ch: str):
            try:
                c, _r, _ = _load(ch, source, hook_policy)
                c = _upgrade_to_sung(c, style)   # Phase 5am: real Sung outline
                c = _upgrade_to_seal(c, style)   # Phase 5at: real seal outline
                c = _upgrade_to_lishu(c, style)  # Phase 5au: real lishu outline
                if style != "kaishu":
                    c = _apply_style(c, style)
                if cns_outline_mode != "skip":
                    c = _apply_cns_mode(c, cns_outline_mode)
                return c
            except HTTPException:
                return None

        pages = flow_letter(
            text, loader, preset=preset,  # type: ignore
            line_height_mm=line_height_mm,
            margin_mm=margin_mm,
            title_space_mm=title_space_mm,
            signature_space_mm=signature_space_mm,
            title_text=title_text,
            title_size_mm=title_size_mm,
            signature_text=signature_text,
            signature_size_mm=signature_size_mm,
            date_text=date_text,
            date_size_mm=date_size_mm,
            signature_lines_after_body=signature_lines_after_body,
            signature_align=signature_align,
            direction=direction,  # type: ignore
            first_line_offset_mm=first_line_offset_mm,
            lines_per_page=lines_per_page,
        )
        cap_headers = {"X-Capacity-Per-Page":
                       str(layout_capacity(pages[0].layout,
                                           direction=direction)  # type: ignore
                           ["chars_per_page"])
                       if pages else "0"}

        # Phase 5ac: alternate output formats (mirrors notebook mode).
        # G-code / JSON are whole-job outputs — ignore ?page=N (a robot runs
        # the full file, not per page).
        if format == "gcode":
            body = render_letter_gcode(pages, cell_style=cell_style)  # type: ignore
            headers = {**cap_headers,
                       "X-Stroke-Order-Pages": str(len(pages))}
            if download:
                headers["Content-Disposition"] = _content_disposition(
                    "letter", "gcode")
            return Response(content=body,
                            media_type="text/plain; charset=utf-8",
                            headers=headers)
        if format == "json":
            body = render_letter_json(pages, cell_style=cell_style)  # type: ignore
            headers = {**cap_headers,
                       "X-Stroke-Order-Pages": str(len(pages))}
            if download:
                headers["Content-Disposition"] = _content_disposition(
                    "letter", "json")
            return Response(content=body,
                            media_type="application/json; charset=utf-8",
                            headers=headers)

        def _render(p):
            # title/signature placement already baked into p.title_block /
            # p.signature_block by flow_letter, so no need to pass the
            # legacy params here.
            return render_letter_page_svg(
                p, cell_style=cell_style,
                decorative_border=decorative_border,
                show_grid=show_grid,
            )

        if page is not None:
            if page > len(pages):
                raise HTTPException(
                    404, detail=f"page {page} of {len(pages)}"
                )
            svg = _render(pages[page - 1])
            headers = {}
            if download:
                headers["Content-Disposition"] = _content_disposition(
                    f"letter-page-{page:02d}", "svg"
                )
            return Response(content=svg, media_type="image/svg+xml",
                            headers=headers)

        body, mime, ext = render_pages_as_single_or_zip(
            pages, _render, filename_prefix="letter-page"
        )
        headers = {"X-Stroke-Order-Pages": str(len(pages)), **cap_headers}
        if download:
            headers["Content-Disposition"] = _content_disposition(
                "letter", ext
            )
        return Response(content=body, media_type=mime, headers=headers)

    # ------ 稿紙模式 (manuscript) ---------------------------------------

    @app.get("/api/manuscript/capacity")
    async def manuscript_capacity(
        text: str = Query("", max_length=8000),
        preset: str = Query("300", pattern="^(300|200)$",
                            description="300 字 (25×12) | 200 字 (20×10)"),
        margin_top_mm: float = Query(15.0, ge=0, le=80),
        margin_bottom_mm: float = Query(15.0, ge=0, le=80),
        margin_left_mm: float = Query(15.0, ge=0, le=80),
        margin_right_mm: float = Query(15.0, ge=0, le=80),
        zhuyin_width_mm: Optional[float] = Query(None, ge=0, le=20),
    ):
        """Return the preset's grid info plus current cell dimensions."""
        from ..exporters.manuscript import (
            build_manuscript_layout, MANUSCRIPT_PRESETS,
        )
        try:
            layout = build_manuscript_layout(
                preset=preset,
                margin_top_mm=margin_top_mm, margin_bottom_mm=margin_bottom_mm,
                margin_left_mm=margin_left_mm, margin_right_mm=margin_right_mm,
                zhuyin_width_mm=zhuyin_width_mm,
            )
        except ValueError as e:
            raise HTTPException(422, detail=str(e)) from e
        p = MANUSCRIPT_PRESETS[preset]
        capacity = p["capacity"]
        total = sum(1 for c in text if not c.isspace())
        pages_estimated = max(1, (total + capacity - 1) // capacity)
        return {
            "preset": preset,
            "rows": p["rows"],
            "cols": p["cols"],
            "chars_per_page": capacity,
            "char_width_mm": round(layout.char_width_mm, 3),
            "zhuyin_width_mm": round(layout.line_spacing_mm, 3),
            "cell_height_mm": round(layout.line_height_mm, 3),
            "page_size_mm": [layout.size.width_mm, layout.size.height_mm],
            "margin_mm": {
                "top": layout.margin_top_mm, "bottom": layout.margin_bottom_mm,
                "left": layout.margin_left_mm,
                # Report USER-VISIBLE right margin (exclude inflated zhuyin)
                "right": round(
                    layout.margin_right_mm - layout.line_spacing_mm, 3),
            },
            "total_chars": total,
            "pages_estimated": pages_estimated,
        }

    @app.get("/api/manuscript")
    async def manuscript(
        text: str = Query(..., min_length=1, max_length=8000),
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
        preset: str = Query("300", pattern="^(300|200)$",
                            description="300 字 (25×12) | 200 字 (20×10)"),
        margin_top_mm: float = Query(15.0, ge=0, le=80),
        margin_bottom_mm: float = Query(15.0, ge=0, le=80),
        margin_left_mm: float = Query(15.0, ge=0, le=80),
        margin_right_mm: float = Query(15.0, ge=0, le=80),
        zhuyin_width_mm: Optional[float] = Query(None, ge=0, le=20),
        cell_style: str = Query(
            "outline",
            pattern="^(outline|trace|filled|ghost|blank)$",
        ),
        page: Optional[int] = Query(None, ge=1),
        download: bool = Query(False),
        format: str = Query(
            "svg", pattern="^(svg|gcode|json)$",
            description="svg | gcode | json",
        ),
        style: str = Query(
            "kaishu", pattern=_STYLE_PATTERN,
            description="Phase 5aj: stroke-filter style",
        ),
        show_grid: bool = Query(
            True,
            description="Phase 5af: draw the 25×12 / 20×10 pair grid",
        ),
        cns_outline_mode: str = Query(
            "skip", pattern=_CNS_MODE_PATTERN,
            description="Phase 5al: CNS-font fallback render mode",
        ),
    ):
        from ..exporters.manuscript import (
            flow_manuscript, render_manuscript_page_svg,
            render_manuscript_gcode, render_manuscript_json,
            MANUSCRIPT_PRESETS,
        )
        from ..exporters.multi_page import render_pages_as_single_or_zip

        def loader(ch: str):
            try:
                c, _r, _ = _load(ch, source, hook_policy)
                c = _upgrade_to_sung(c, style)   # Phase 5am: real Sung outline
                c = _upgrade_to_seal(c, style)   # Phase 5at: real seal outline
                c = _upgrade_to_lishu(c, style)  # Phase 5au: real lishu outline
                if style != "kaishu":
                    c = _apply_style(c, style)
                if cns_outline_mode != "skip":
                    c = _apply_cns_mode(c, cns_outline_mode)
                return c
            except HTTPException:
                return None

        try:
            pages = flow_manuscript(
                text, loader, preset=preset,
                margin_top_mm=margin_top_mm, margin_bottom_mm=margin_bottom_mm,
                margin_left_mm=margin_left_mm, margin_right_mm=margin_right_mm,
                zhuyin_width_mm=zhuyin_width_mm,
            )
        except ValueError as e:
            raise HTTPException(422, detail=str(e)) from e

        cap_headers = {
            "X-Capacity-Per-Page": str(MANUSCRIPT_PRESETS[preset]["capacity"]),
            "X-Stroke-Order-Pages": str(len(pages)),
        }

        # Alternate output formats — whole-job outputs, ignore ?page=N.
        if format == "gcode":
            body = render_manuscript_gcode(pages, cell_style=cell_style)  # type: ignore
            headers = dict(cap_headers)
            if download:
                headers["Content-Disposition"] = _content_disposition(
                    "manuscript", "gcode")
            return Response(content=body,
                            media_type="text/plain; charset=utf-8",
                            headers=headers)
        if format == "json":
            body = render_manuscript_json(pages, cell_style=cell_style)  # type: ignore
            headers = dict(cap_headers)
            if download:
                headers["Content-Disposition"] = _content_disposition(
                    "manuscript", "json")
            return Response(content=body,
                            media_type="application/json; charset=utf-8",
                            headers=headers)

        def _render(p):
            return render_manuscript_page_svg(
                p, cell_style=cell_style, show_grid=show_grid)  # type: ignore

        if page is not None:
            if page > len(pages):
                raise HTTPException(
                    404, detail=f"page {page} of {len(pages)}"
                )
            svg = _render(pages[page - 1])
            headers = {}
            if download:
                headers["Content-Disposition"] = _content_disposition(
                    f"manuscript-page-{page:02d}", "svg"
                )
            return Response(content=svg, media_type="image/svg+xml",
                            headers=headers)

        body, mime, ext = render_pages_as_single_or_zip(
            pages, _render, filename_prefix="manuscript-page"
        )
        headers = dict(cap_headers)
        if download:
            headers["Content-Disposition"] = _content_disposition(
                "manuscript", ext
            )
        return Response(content=body, media_type=mime, headers=headers)

    # ------ 文字雲 (wordart) -----------------------------------------

    _SHAPE_KINDS = ("circle", "ellipse", "triangle", "square", "pentagon",
                    "hexagon", "heptagon", "octagon", "nonagon", "decagon",
                    "polygon",
                    # Phase 5ah: new geometric shapes
                    "star", "heart", "rounded", "trapezoid", "arc",
                    # Phase 5as
                    "cone", "capsule")
    _SHAPE_PATTERN = "^(" + "|".join(_SHAPE_KINDS) + ")$"
    _LAYOUT_PATTERN = (
        "^(ring|fill|linear|three_band|wordcloud|"
        "concentric|gradient_v|split_lr|"
        # Phase 5an
        "gradient_h|wave|radial_convex|radial_concave)$"
    )

    @app.get("/api/wordart/capacity")
    async def wordart_capacity(
        shape: str = Query("circle", pattern=_SHAPE_PATTERN),
        shape_size_mm: float = Query(140.0, ge=10, le=400),
        sides: int = Query(6, ge=3, le=20),
        aspect: float = Query(1.0, ge=0.2, le=5.0),
        char_size_mm: float = Query(10.0, gt=1, le=60),
        layout: str = Query("ring", pattern=_LAYOUT_PATTERN),
        page_width_mm: float = Query(210.0, ge=50, le=600),
        page_height_mm: float = Query(297.0, ge=50, le=600),
        mid_ratio: float = Query(0.9, ge=0.2, le=1.0),
        min_size_mm: float = Query(5.0, gt=1, le=60),
        max_size_mm: float = Query(20.0, gt=1, le=80),
        # Phase 5ah: shape-specific knobs (ignored when irrelevant to `shape`)
        star_inner_ratio: float = Query(0.382, ge=0.05, le=0.95),
        trapezoid_top_ratio: float = Query(0.6, ge=0.1, le=5.0),
        rounded_corner_ratio: float = Query(0.2, ge=0.0, le=0.5),
        arc_start_deg: float = Query(180.0, ge=-360, le=360),
        arc_extent_deg: float = Query(180.0, gt=0, le=360),
        # Phase 5as
        cone_taper: float = Query(0.5, ge=0.05, le=1.0),
        cone_invert: bool = Query(False),
        capsule_orientation: str = Query("horizontal",
                                         pattern="^(horizontal|vertical)$"),
    ):
        """Preflight capacity for any layout. Returns layout-specific dict."""
        from ..shapes import Circle, Ellipse, make_shape
        from ..exporters.wordart import capacity, three_band_capacity
        from ..exporters.wordcloud import wordcloud_capacity
        max_allow = min(page_width_mm, page_height_mm) - 10
        requested = shape_size_mm
        if shape_size_mm > max_allow:
            shape_size_mm = max_allow
        s = make_shape(shape, page_width_mm / 2, page_height_mm / 2,
                       shape_size_mm, sides=sides, aspect=aspect,
                       star_inner_ratio=star_inner_ratio,
                       trapezoid_top_ratio=trapezoid_top_ratio,
                       rounded_corner_ratio=rounded_corner_ratio,
                       arc_start_deg=arc_start_deg,
                       arc_extent_deg=arc_extent_deg,
                       cone_taper=cone_taper,
                       cone_invert=cone_invert,
                       capsule_orientation=capsule_orientation)

        if layout in ("ring", "fill", "linear"):
            info = capacity(layout, s, char_size_mm)
        elif layout == "three_band":
            if not isinstance(s, (Circle, Ellipse)):
                raise HTTPException(422,
                                    "three_band layout requires circle or ellipse shape")
            info = three_band_capacity(s, char_size_mm, mid_ratio=mid_ratio)
            info["layout"] = "three_band"
        elif layout == "concentric":
            # Rough estimate: rings per shape (step = char_size * 1.3)
            if isinstance(s, Circle):
                r_max = s.radius_mm
            elif isinstance(s, Ellipse):
                r_max = min(s.rx_mm, s.ry_mm)
            else:
                # Polygon: use centroid-to-vertex
                import math as _m
                cx, cy = page_width_mm / 2, page_height_mm / 2
                r_max = sum(_m.hypot(v[0] - cx, v[1] - cy) for v in s.vertices) / len(s.vertices)
            max_rings = max(1, int((r_max - char_size_mm * 1.5)
                                    // (char_size_mm * 1.3)) + 1)
            info = {
                "layout": "concentric",
                "max_rings": max_rings,
                "outer_ring_chars": int(s.perimeter() // char_size_mm),
            }
        elif layout in ("gradient_v", "split_lr",
                        # Phase 5an
                        "gradient_h", "radial_convex", "radial_concave"):
            cap = capacity("fill", s, char_size_mm)
            info = {
                "layout": layout,
                "approx_chars": cap.get("min_chars_for_full_fill", 0),
            }
        elif layout == "wave":
            # Wave capacity ≈ wave_lines × (perimeter-ish samples).
            # Use perimeter / char_size as a coarse upper bound.
            try:
                perim = s.perimeter()
            except Exception:
                perim = 2 * (s.bbox()[2] - s.bbox()[0])
            info = {
                "layout": "wave",
                "approx_chars": int(perim / max(char_size_mm, 1.0)),
            }
        elif layout == "wordcloud":
            info = wordcloud_capacity(s, min_size_mm, max_size_mm)
        else:
            raise HTTPException(422, f"unknown layout {layout!r}")

        info["shape_size_mm"] = shape_size_mm
        info["clamped"] = shape_size_mm < requested - 0.01
        return info

    @app.get("/api/wordart")
    async def wordart(
        shape: str = Query("circle", pattern=_SHAPE_PATTERN),
        shape_size_mm: float = Query(140.0, ge=10, le=400),
        sides: int = Query(6, ge=3, le=20),
        aspect: float = Query(1.0, ge=0.2, le=5.0),
        char_size_mm: float = Query(10.0, gt=1, le=60),
        layout: str = Query("ring", pattern=_LAYOUT_PATTERN),
        orientation: str = Query(
            "bottom_to_center",
            pattern="^(bottom_to_center|top_to_center|upright|tangent)$",
        ),
        text: str = Query("", max_length=4000),
        texts_per_edge: Optional[str] = Query(
            None, description="Pipe-separated per-edge texts"
        ),
        # Three-band
        text_top: str = Query("", max_length=2000),
        text_mid: str = Query("", max_length=2000),
        text_bot: str = Query("", max_length=2000),
        mid_ratio: float = Query(0.9, ge=0.2, le=1.0),
        orient_top: str = Query(
            "bottom_to_center",
            pattern="^(bottom_to_center|top_to_center)$",
        ),
        orient_mid: str = Query(
            "bottom_to_center",
            pattern="^(bottom_to_center|top_to_center)$",
        ),
        orient_bot: str = Query(
            "bottom_to_center",
            pattern="^(bottom_to_center|top_to_center)$",
        ),
        # Concentric
        texts_per_ring: Optional[str] = Query(
            None, description="Pipe-separated per-ring texts"
        ),
        # Gradient / split
        gradient_dir: str = Query("down", pattern="^(down|up)$"),
        # Phase 5an: gradient_h direction (right=big at left)
        gradient_h_dir: str = Query("right", pattern="^(right|left)$"),
        # Phase 5an: wave layout knobs (None → derived from char_size_mm)
        wave_amplitude_mm: Optional[float] = Query(None, ge=0, le=200),
        wave_wavelength_mm: Optional[float] = Query(None, gt=0, le=400),
        wave_lines: int = Query(3, ge=1, le=20),
        wave_tangent_rotation: bool = Query(True),
        text_left: str = Query("", max_length=2000),
        text_right: str = Query("", max_length=2000),
        # Wordcloud
        tokens: str = Query("", max_length=4000,
                            description="Pipe-separated tokens, optional :weight"),
        weight_mode: str = Query("manual",
                                 pattern="^(manual|frequency|random)$"),
        min_size_mm: float = Query(5.0, gt=1, le=60),
        max_size_mm: float = Query(20.0, gt=1, le=80),
        padding_mm: float = Query(1.0, ge=0, le=10),
        # Linear variants
        edge_groups: Optional[str] = Query(
            None, description="Edge groups: '0,1,2|3,4,5'"
        ),
        edge_start: int = Query(0, ge=0, le=30),
        edge_direction: str = Query("cw", pattern="^(cw|ccw)$"),
        # Auto-cycle / auto-fit (Phase 5e)
        auto_cycle: bool = Query(True, description="Cycle text to fill slots when short"),
        auto_fit: bool = Query(False, description="Shrink char size when text overflows"),
        min_char_size_mm: float = Query(3.0, ge=1.0, le=20.0),
        # Alignment when auto_cycle is off and text < slots (Phase 5h)
        align: str = Query(
            "spread", pattern="^(spread|center|left|right)$",
            description="Where to place chars when shorter than slots (auto_cycle off)",
        ),
        # Writing direction — only meaningful for fill layout (Phase 5i)
        direction: str = Query(
            "horizontal", pattern="^(horizontal|vertical)$",
            description="Writing direction (fill only): horizontal (橫書) or vertical (直書)",
        ),
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
        page_width_mm: float = Query(210.0, ge=50, le=600),
        page_height_mm: float = Query(297.0, ge=50, le=600),
        show_shape_outline: bool = Query(True),
        download: bool = Query(False),
        # Phase 5ah: shape-specific knobs
        star_inner_ratio: float = Query(0.382, ge=0.05, le=0.95),
        trapezoid_top_ratio: float = Query(0.6, ge=0.1, le=5.0),
        rounded_corner_ratio: float = Query(0.2, ge=0.0, le=0.5),
        arc_start_deg: float = Query(180.0, ge=-360, le=360),
        arc_extent_deg: float = Query(180.0, gt=0, le=360),
        # Phase 5as
        cone_taper: float = Query(0.5, ge=0.05, le=1.0),
        cone_invert: bool = Query(False),
        capsule_orientation: str = Query("horizontal",
                                         pattern="^(horizontal|vertical)$"),
        # Phase 5aj: stroke-filter style
        style: str = Query("kaishu", pattern=_STYLE_PATTERN),
        cns_outline_mode: str = Query("skip", pattern=_CNS_MODE_PATTERN),
    ):
        from ..shapes import Circle, Ellipse, Polygon, make_shape
        from ..exporters.wordart import (
            Layout, capacity, compute_fill, compute_linear,
            compute_linear_groups, compute_linear_ordered,
            compute_ring, compute_three_band, render_wordart_svg,
            three_band_capacity,
        )
        from ..exporters.wordcloud import (
            compute_concentric, compute_gradient_v, compute_split_lr,
            compute_wordcloud, parse_tokens, wordcloud_capacity,
            # Phase 5an
            compute_gradient_h, compute_radial_gradient, compute_wave,
        )

        # Clamp shape to page
        max_allow = min(page_width_mm, page_height_mm) - 10
        if shape_size_mm > max_allow:
            shape_size_mm = max_allow

        s = make_shape(shape, page_width_mm / 2, page_height_mm / 2,
                       shape_size_mm, sides=sides, aspect=aspect,
                       star_inner_ratio=star_inner_ratio,
                       trapezoid_top_ratio=trapezoid_top_ratio,
                       rounded_corner_ratio=rounded_corner_ratio,
                       arc_start_deg=arc_start_deg,
                       arc_extent_deg=arc_extent_deg,
                       cone_taper=cone_taper,
                       cone_invert=cone_invert,
                       capsule_orientation=capsule_orientation)

        def loader(ch: str):
            try:
                c, _r, _ = _load(ch, source, hook_policy)
                c = _upgrade_to_sung(c, style)   # Phase 5am: real Sung outline
                c = _upgrade_to_seal(c, style)   # Phase 5at: real seal outline
                c = _upgrade_to_lishu(c, style)  # Phase 5au: real lishu outline
                if style != "kaishu":
                    c = _apply_style(c, style)
                if cns_outline_mode != "skip":
                    c = _apply_cns_mode(c, cns_outline_mode)
                return c
            except HTTPException:
                return None

        # Dispatch by layout
        placed: list = []
        missing: list[str] = []
        dropped: list[str] = []
        cap_info: dict = {}

        # Auto-cycle/fit kwargs shared across most layouts
        ac_kwargs = dict(
            auto_cycle=auto_cycle, auto_fit=auto_fit,
            min_char_size_mm=min_char_size_mm,
        )
        # align applies only to layouts that expose it (linear family + three_band)
        ac_align = dict(ac_kwargs, align=align)
        # Subset for layouts that support only auto_cycle (no auto_fit)
        ac_cycle_only = dict(auto_cycle=auto_cycle)

        if layout == "ring":
            placed, missing = compute_ring(
                text, s, char_size_mm, orientation, loader,
                auto_fit=auto_fit, min_char_size_mm=min_char_size_mm,
            )
            cap_info = capacity("ring", s, char_size_mm)
        elif layout == "fill":
            placed, missing = compute_fill(
                text, s, char_size_mm, loader, orient=orientation,
                direction=direction,  # type: ignore
                **ac_kwargs,
            )
            cap_info = capacity("fill", s, char_size_mm)
        elif layout == "linear":
            if not isinstance(s, Polygon):
                raise HTTPException(422, "linear layout requires a polygon")
            if edge_groups:
                groups = [
                    [int(x) for x in g.split(",") if x.strip().isdigit()]
                    for g in edge_groups.split("|") if g.strip()
                ]
                group_texts = (texts_per_edge or text).split("|") if (texts_per_edge or text) else []
                placed, missing = compute_linear_groups(
                    group_texts, groups, s, char_size_mm, orientation, loader,
                    **ac_align,
                )
            else:
                edge_texts = (texts_per_edge.split("|")
                              if texts_per_edge else [text])
                if edge_start != 0 or edge_direction != "cw":
                    placed, missing = compute_linear_ordered(
                        edge_texts, s, char_size_mm, orientation, loader,
                        edge_start=edge_start, edge_direction=edge_direction,
                        **ac_align,
                    )
                else:
                    placed, missing = compute_linear(
                        edge_texts, s, char_size_mm, orientation, loader,
                        **ac_align,
                    )
            cap_info = capacity("linear", s, char_size_mm)
        elif layout == "three_band":
            if not isinstance(s, (Circle, Ellipse)):
                raise HTTPException(422,
                                    "three_band requires circle or ellipse")
            placed, missing = compute_three_band(
                text_top, text_mid, text_bot, s,
                char_size_mm, loader, mid_ratio=mid_ratio,
                orient_top=orient_top,  # type: ignore
                orient_mid=orient_mid,  # type: ignore
                orient_bot=orient_bot,  # type: ignore
                **ac_align,
            )
            cap_info = three_band_capacity(s, char_size_mm, mid_ratio=mid_ratio)
        elif layout == "concentric":
            ring_texts = (texts_per_ring.split("|")
                          if texts_per_ring else [text] if text else [])
            placed, missing = compute_concentric(
                ring_texts, s, char_size_mm, orientation, loader,
                **ac_cycle_only,
            )
        elif layout == "gradient_v":
            placed, missing = compute_gradient_v(
                text, s, loader,
                min_size_mm=min_size_mm, max_size_mm=max_size_mm,
                direction=gradient_dir,  # type: ignore
                **ac_cycle_only,
            )
        elif layout == "split_lr":
            placed, missing = compute_split_lr(
                text_left, text_right, s, char_size_mm, loader,
                **ac_kwargs,
            )
        elif layout == "wordcloud":
            parsed = parse_tokens(tokens or text, weight_mode=weight_mode)  # type: ignore
            placed, missing, dropped = compute_wordcloud(
                parsed, s, char_loader=loader,
                min_size_mm=min_size_mm, max_size_mm=max_size_mm,
                padding_mm=padding_mm,
            )
            cap_info = wordcloud_capacity(s, min_size_mm, max_size_mm)
        # Phase 5an
        elif layout == "gradient_h":
            placed, missing = compute_gradient_h(
                text, s, loader,
                min_size_mm=min_size_mm, max_size_mm=max_size_mm,
                direction=gradient_h_dir,  # type: ignore
                **ac_cycle_only,
            )
        elif layout == "wave":
            placed, missing = compute_wave(
                text, s, char_size_mm=char_size_mm, char_loader=loader,
                amplitude_mm=wave_amplitude_mm,
                wavelength_mm=wave_wavelength_mm,
                wave_lines=wave_lines,
                tangent_rotation=wave_tangent_rotation,
                **ac_cycle_only,
            )
        elif layout in ("radial_convex", "radial_concave"):
            radial_dir = "convex" if layout == "radial_convex" else "concave"
            placed, missing = compute_radial_gradient(
                text, s, loader,
                min_size_mm=min_size_mm, max_size_mm=max_size_mm,
                direction=radial_dir,  # type: ignore
                **ac_cycle_only,
            )
        else:
            raise HTTPException(422, f"unknown layout {layout!r}")

        svg = render_wordart_svg(
            placed,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            shape=s,
            show_shape_outline=show_shape_outline,
        )

        cap_n = (
            cap_info.get("min_chars_for_full_ring")
            or cap_info.get("min_chars_for_full_fill")
            or cap_info.get("min_chars_for_all_edges")
            or (cap_info.get("top", 0) + cap_info.get("mid", 0)
                + cap_info.get("bot", 0))
            or cap_info.get("approx_max_tokens", 0)
            or 0
        )
        # Report actual size used (may differ from requested when auto_fit kicks in).
        # placed items: (char, x, y, size, rot). Take the most-common size if any.
        if placed:
            sizes = [round(p[3], 2) for p in placed]
            # most frequent size (mode)
            from collections import Counter
            actual_size = Counter(sizes).most_common(1)[0][0]
        else:
            actual_size = char_size_mm

        headers: dict[str, str] = {
            "X-Wordart-Placed": str(len(placed)),
            "X-Wordart-Capacity": str(cap_n),
            "X-Wordart-Fitted-Size": f"{actual_size:.2f}",
            "X-Wordart-Requested-Size": f"{char_size_mm:.2f}",
        }
        if dropped:
            headers["X-Wordart-Dropped"] = str(len(dropped))
        if download:
            headers["Content-Disposition"] = _content_disposition(
                f"wordart-{shape}-{layout}", "svg"
            )
        return Response(content=svg, media_type="image/svg+xml",
                        headers=headers)

    # ------ 塗鴉模式 (doodle) ------------------------------------------

    @app.post("/api/doodle")
    async def doodle(
        image: UploadFile = File(...),
        canvas_width_mm: float = Form(150.0),
        max_side_px: int = Form(200),
        threshold: int = Form(50),
        line_color: str = Form("#222"),
        line_width: float = Form(0.4),
        annotations_json: str = Form("[]"),
        download: bool = Form(False),
        # Phase 5ag: pre-crop the uploaded image before edge detection
        auto_crop_whitespace: bool = Form(False),
        auto_crop_border: bool = Form(False),
    ):
        """Upload an image → return doodle SVG."""
        import json
        from PIL import Image as PILImage
        from ..exporters.doodle import auto_crop_image, render_doodle_svg
        from ..layouts import Annotation

        # Read uploaded image
        body = await image.read()
        try:
            img = PILImage.open(io.BytesIO(body))
        except Exception as e:
            raise HTTPException(400, detail=f"cannot read image: {e}") from e

        # Phase 5ag: optionally remove outer whitespace / frame BEFORE
        # edge-detection so the line-art actually tracks the subject.
        if auto_crop_whitespace or auto_crop_border:
            img = auto_crop_image(
                img,
                trim_whitespace=auto_crop_whitespace,
                remove_border=auto_crop_border,
            )

        try:
            anns_data = json.loads(annotations_json)
        except Exception as e:
            raise HTTPException(
                400, detail=f"invalid annotations_json: {e}"
            ) from e

        anns = [
            Annotation(
                text=a.get("text", ""),
                x_mm=float(a.get("x_mm", 0)),
                y_mm=float(a.get("y_mm", 0)),
                size_mm=float(a.get("size_mm", 3.0)),
                color=a.get("color", "#666"),
            )
            for a in anns_data
            if a.get("text")
        ]

        svg = render_doodle_svg(
            img,
            canvas_width_mm=canvas_width_mm,
            max_side_px=max_side_px,
            threshold=threshold,
            line_color=line_color,
            line_width=line_width,
            annotations=anns,
        )
        headers: dict[str, str] = {}
        if download:
            headers["Content-Disposition"] = _content_disposition(
                "doodle", "svg"
            )
        return Response(content=svg, media_type="image/svg+xml",
                        headers=headers)

    # ------ 字帖 grid mode ---------------------------------------------

    @app.get("/api/grid")
    async def grid(
        chars: str = Query(..., min_length=1, max_length=40,
                           description="Characters to put on worksheet"),
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
        cols: int = Query(1, ge=1, le=20,
                          description="Total tier count (primary+ghost+blank)"),
        guide: str = Query("tian", pattern="^(tian|mi|hui|plain|none)$"),
        cell_style: str = Query("filled",
                                pattern="^(outline|trace|filled|ghost|blank)$"),
        cell_size: int = Query(120, ge=40, le=400),
        repeat: int = Query(1, ge=0, le=20),
        ghost_copies: Optional[int] = Query(
            None, ge=0, le=20,
            description="Explicit ghost-tier count; omit for auto-from-cols",
        ),
        blank_copies: Optional[int] = Query(
            None, ge=0, le=20,
            description="Explicit blank-tier count; omit for auto-from-cols",
        ),
        download: bool = Query(False),
        direction: str = Query("horizontal",
                               pattern="^(horizontal|vertical)$"),
        format: str = Query("svg", pattern="^(svg|gcode|json)$",
                            description="Output format"),
        # G-code specific
        gc_cell_size_mm: float = Query(20.0, ge=5, le=100),
        gc_cell_gap_mm: float = Query(0.0, ge=0, le=20),
        gc_feed: int = Query(3000, ge=100, le=20000),
        # Phase 5aj: stroke-filter style (default kaishu preserves
        # tracing practice; users opt in for Mingti/Lishu/Bold variants).
        style: str = Query("kaishu", pattern=_STYLE_PATTERN),
        cns_outline_mode: str = Query("skip", pattern=_CNS_MODE_PATTERN),
    ):
        """Render a 字帖 for multiple characters in SVG / G-code / JSON.

        - ``format=svg`` (default): visual worksheet (all tiers).
        - ``format=gcode``: primary tier only, positioned per-cell for a
          writing-robot (AxiDraw-style defaults).
        - ``format=json``: full grid metadata + per-cell data.

        If ``download=true``, Content-Disposition is set for browser
        download behaviour.
        """
        from ..exporters.grid import (
            render_grid_svg, render_grid_gcode, render_grid_json,
        )
        loaded = []
        skipped: list[str] = []
        for ch in chars:
            if ch.isspace():
                continue
            try:
                c, _r, _ = _load(ch, source, hook_policy)
                c = _upgrade_to_sung(c, style)   # Phase 5am: real Sung outline
                c = _upgrade_to_seal(c, style)   # Phase 5at: real seal outline
                c = _upgrade_to_lishu(c, style)  # Phase 5au: real lishu outline
                if style != "kaishu":
                    c = _apply_style(c, style)
                loaded.append(c)
            except HTTPException as e:
                if e.status_code == 404:
                    skipped.append(ch)
                    continue
                raise
        if not loaded:
            raise HTTPException(
                400, detail=f"no characters loaded (skipped: {skipped!r})"
            )
        basename = "".join(c.char for c in loaded) + "_字帖"
        headers: dict[str, str] = {}

        if format == "gcode":
            body = render_grid_gcode(
                loaded, cols=cols,
                ghost_copies=ghost_copies, blank_copies=blank_copies,
                direction=direction,   # type: ignore
                cell_size_mm=gc_cell_size_mm, cell_gap_mm=gc_cell_gap_mm,
                feed_rate=gc_feed,
            )
            if download:
                headers["Content-Disposition"] = _content_disposition(
                    basename, "gcode"
                )
            return Response(content=body,
                            media_type="text/plain; charset=utf-8",
                            headers=headers)
        if format == "json":
            body = render_grid_json(
                loaded, cols=cols,
                ghost_copies=ghost_copies, blank_copies=blank_copies,
                direction=direction,   # type: ignore
                cell_size_mm=gc_cell_size_mm, cell_gap_mm=gc_cell_gap_mm,
                guide=guide,              # type: ignore
                cell_style=cell_style,    # type: ignore
            )
            if download:
                headers["Content-Disposition"] = _content_disposition(
                    basename, "json"
                )
            return Response(content=body,
                            media_type="application/json; charset=utf-8",
                            headers=headers)

        # format == "svg" (default)
        svg = render_grid_svg(
            loaded, cols=cols, guide=guide,
            cell_style=cell_style, cell_size_px=cell_size,
            ghost_copies=ghost_copies,   # None → auto
            blank_copies=blank_copies,   # None → auto
            direction=direction,  # type: ignore
            repeat_per_char=repeat,
        )
        if download:
            headers["Content-Disposition"] = _content_disposition(
                basename, "svg"
            )
        return Response(content=svg, media_type="image/svg+xml",
                        headers=headers)

    # ------ file download -----------------------------------------------

    @app.get("/api/export/{char}")
    async def export(
        char: str,
        format: str = Query("svg", pattern="^(svg|gcode|json)$"),
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
        mode: str = Query("both", pattern="^(outline|track|both)$"),
        show_numbers: bool = Query(False),
        rainbow: bool = Query(False),
        char_size: float = Query(20.0, gt=0.1, le=200.0),
        feed_rate: int = Query(3000, gt=0, le=50000),
    ):
        c, _r, _ = _load(char, source, hook_policy)

        if format == "svg":
            payload = character_to_svg(
                c, mode=mode, show_numbers=show_numbers, rainbow=rainbow
            )
            return Response(
                content=payload,
                media_type="image/svg+xml",
                headers={
                    "Content-Disposition": _content_disposition(char, "svg"),
                },
            )
        if format == "gcode":
            payload = characters_to_gcode(
                [c], GCodeOptions(char_size_mm=char_size, feed_rate=feed_rate)
            )
            return Response(
                content=payload,
                media_type="text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": _content_disposition(char, "gcode"),
                },
            )
        if format == "json":
            payload = character_to_json(c)
            return Response(
                content=payload,
                media_type="application/json; charset=utf-8",
                headers={
                    "Content-Disposition": _content_disposition(char, "json"),
                },
            )
        raise HTTPException(400, detail=f"unknown format {format!r}")

    # ------ CNS dictionary metadata (Phase 5al) -------------------------

    @app.get("/api/cns-status")
    async def cns_status():
        """Diagnostic: are the CNS fonts / Properties files present?"""
        from ..sources.cns_font import CNSFontSource, default_cns_font_dir
        from ..sources.cns_components import (
            CNSComponents, default_cns_properties_dir,
        )
        kai = CNSFontSource(style="kai")
        sung = CNSFontSource(style="sung")
        comps = CNSComponents()
        return {
            "font_dir": str(default_cns_font_dir()),
            "kai_planes":  kai.available_planes(),
            "sung_planes": sung.available_planes(),
            "fonts_ready": kai.is_ready() or sung.is_ready(),
            "properties_dir": str(default_cns_properties_dir()),
            "properties_ready": comps.is_ready(),
        }

    @app.get("/api/seal-status")
    async def seal_status():
        """Phase 5at: 崇羲篆體 source state + mandatory CC BY-ND attribution.

        Frontend banners must surface ``attribution`` whenever
        ``ready`` is True so the licence terms are met.
        """
        from ..sources.chongxi_seal import default_seal_font_path
        seal = _get_seal()
        return {
            "font_file": str(default_seal_font_path()),
            "ready": seal.is_ready(),
            "glyph_count": seal.available_glyph_count() if seal.is_ready() else 0,
            "attribution": _seal_attribution(),
            "license": "CC BY-ND 3.0 TW or later",
            "license_url": "https://xiaoxue.iis.sinica.edu.tw/chongxi/copyright.htm",
        }

    @app.get("/api/lishu-status")
    async def lishu_status():
        """Phase 5au: MoE 隸書 source state + mandatory attribution."""
        from ..sources.moe_lishu import default_lishu_font_path
        lishu = _get_lishu()
        return {
            "font_file": str(default_lishu_font_path()),
            "ready": lishu.is_ready(),
            "glyph_count": lishu.available_glyph_count() if lishu.is_ready() else 0,
            "attribution": _lishu_attribution(),
            "license": "CC BY-ND 3.0 TW",
            "license_url": "https://language.moe.gov.tw/result.aspx?classify_sn=23",
        }

    @app.get("/api/song-status")
    async def song_status():
        """Phase 5av: MoE 標準宋體 source state + mandatory attribution.

        When ``ready=True`` the layered :func:`_upgrade_to_sung` will
        try this source first when the user picks ``style="mingti"``,
        falling back to CNS Sung only for chars MoE doesn't carry.
        """
        from ..sources.moe_song import default_song_font_path
        song = _get_song()
        return {
            "font_file": str(default_song_font_path()),
            "ready": song.is_ready(),
            "glyph_count": song.available_glyph_count() if song.is_ready() else 0,
            "attribution": _song_attribution(),
            "license": "CC BY-ND 3.0 TW",
            "license_url": "https://language.moe.gov.tw/result.aspx?classify_sn=23",
        }

    @app.get("/api/kaishu-status")
    async def kaishu_status():
        """Phase 5aw: MoE 標準楷書 source state + mandatory attribution.

        When ``ready=True`` the source is wired into AutoSource as a
        Tier-3 outline fallback (after g0v/MMH, before CNS Kai), so
        chars not covered by stroke-data sources still render with
        MoE-quality outlines instead of falling all the way through.
        """
        from ..sources.moe_kaishu import default_kaishu_font_path
        ks = _get_kaishu_font()
        return {
            "font_file": str(default_kaishu_font_path()),
            "ready": ks.is_ready(),
            "glyph_count": ks.available_glyph_count() if ks.is_ready() else 0,
            "attribution": _kaishu_attribution(),
            "license": "CC BY-ND 3.0 TW",
            "license_url": "https://language.moe.gov.tw/result.aspx?classify_sn=23",
        }

    @app.get("/api/decompose/{char}")
    async def cns_decompose(char: str):
        """Return ``CNS_component.txt`` decomposition for ``char``."""
        from ..sources.cns_components import CNSComponents
        if len(char) != 1:
            raise HTTPException(400, detail="char must be a single character")
        comps = CNSComponents()
        parts = comps.decompose(char)
        return {
            "char": char,
            "unicode_hex": f"{ord(char):04x}",
            "cns_code": comps.cns_code_for(char),
            "components": parts,
            "count": len(parts),
        }

    @app.get("/api/cns-stroke-diagnostics/{char}")
    async def cns_stroke_diagnostics(char: str):
        """Phase 5ap-A3a: compare canonical stroke spec vs actual skeleton.

        Returns canonical N-stroke layout (from CNS_strokes_sequence.txt)
        alongside what the current skeleton pipeline produces, so we can
        measure how often the two agree. Used by the 5ap-3 measurement
        script to drive the decision on whether A3b junction-aware
        splitting is worth building.
        """
        from ..sources.cns_strokes import CNSStrokes
        from ..sources.cns_font import (
            CNSFontSource, apply_cns_outline_mode,
        )
        from ..sources.g0v import CharacterNotFound
        if len(char) != 1:
            raise HTTPException(400, detail="char must be a single character")
        strokes_db = CNSStrokes()
        canonical = strokes_db.canonical_strokes(char)
        canonical_names = strokes_db.canonical_names(char)
        # Actual skeleton — best-effort. Missing TTFs / missing glyph
        # both surface as ``actual_polyline_count = None`` so the caller
        # can distinguish "no canonical data" from "no font data".
        actual_count: Optional[int] = None
        actual_lens: list[int] = []
        try:
            src = CNSFontSource()
            if src.is_ready():
                c = src.get_character(char)
                sk = apply_cns_outline_mode(c, "skeleton")
                actual_count = len(sk.strokes)
                actual_lens = [len(s.raw_track) for s in sk.strokes]
        except CharacterNotFound:
            pass
        # mismatch only meaningful when BOTH sides have data.
        mismatch: bool = (
            bool(canonical) and actual_count is not None
            and actual_count != len(canonical)
        )
        return {
            "char": char,
            "unicode_hex": f"{ord(char):04x}",
            "canonical_count": len(canonical),
            "canonical_types": canonical,
            "canonical_names": canonical_names,
            "actual_polyline_count": actual_count,
            "actual_polyline_lens": actual_lens,
            "mismatch": mismatch,
        }

    # ------ User dictionary CRUD (Phase 5ak) ----------------------------

    @app.get("/api/user-dict")
    async def user_dict_list():
        """Return the list of user-authored characters with previews."""
        from ..sources.user_dict import UserDictSource
        src = UserDictSource()
        chars = src.list_chars()
        return {
            "dict_dir": str(src.dict_dir),
            "count": len(chars),
            "chars": [
                {
                    "char": ch,
                    "unicode_hex": f"{ord(ch):04x}",
                    "stroke_count": len(src.get_character(ch).strokes),
                }
                for ch in chars
            ],
        }

    # Phase 5ar — bulk endpoints. Registered BEFORE ``/{char}`` so FastAPI
    # doesn't route ``/export`` and ``/import`` into the single-char getter.
    @app.get("/api/user-dict/export")
    async def user_dict_export():
        """Stream every user-dict entry as one ZIP."""
        from datetime import datetime
        from ..sources.user_dict import UserDictSource
        src = UserDictSource()
        zip_bytes = src.export_zip_bytes()
        stamp = datetime.now().strftime("%Y%m%d")
        filename = f"stroke-order-user-dict-{stamp}.zip"
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    @app.post("/api/user-dict/import")
    async def user_dict_import(
        file: UploadFile = File(...),
        policy: str = Form("skip"),
    ):
        """Restore characters from a ZIP. ``policy`` is ``skip`` or ``replace``."""
        from ..sources.user_dict import UserDictSource
        if policy not in ("skip", "replace"):
            raise HTTPException(
                422, detail=f"policy must be 'skip' or 'replace', got {policy!r}",
            )
        try:
            zip_bytes = await file.read()
        except Exception as e:   # pragma: no cover
            raise HTTPException(400, detail=f"failed to read upload: {e}") from e
        src = UserDictSource()
        try:
            summary = src.import_zip_bytes(zip_bytes, policy=policy)
        except ValueError as e:
            raise HTTPException(400, detail=str(e)) from e
        return summary

    @app.get("/api/user-dict/{char}")
    async def user_dict_get(char: str):
        from ..sources.user_dict import UserDictSource
        if len(char) != 1:
            raise HTTPException(400, detail="char must be a single character")
        src = UserDictSource()
        try:
            c = src.get_character(char)
        except CharacterNotFound as e:
            raise HTTPException(404, detail=str(e)) from e
        return {
            "char": c.char,
            "unicode_hex": c.unicode_hex,
            "data_source": c.data_source,
            "strokes": [
                {
                    "track": [[p.x, p.y] for p in s.raw_track],
                    "kind_code": s.kind_code,
                    "kind_name": s.kind_name,
                    "has_hook": s.has_hook,
                }
                for s in c.strokes
            ],
        }

    @app.post("/api/user-dict")
    async def user_dict_post(req: UserDictPostRequest):
        """Add or replace a user-dict entry. Three input formats:

        - ``json``        : ``strokes`` is the canonical track list
        - ``svg``         : ``svg_content`` is parsed via svgpathtools
        - ``handwriting`` : ``handwriting`` carries canvas-coord points
        """
        from ..sources.user_dict import (
            UserDictSource, handwriting_to_strokes, svg_to_strokes,
        )
        if len(req.char) != 1:
            raise HTTPException(400, detail="char must be a single character")

        if req.format == "json":
            if not req.strokes:
                raise HTTPException(
                    400, detail="format=json needs strokes=[{track:...}, ...]")
            strokes = req.strokes
        elif req.format == "svg":
            if not req.svg_content:
                raise HTTPException(400, detail="format=svg needs svg_content")
            try:
                strokes = svg_to_strokes(req.svg_content)
            except ValueError as e:
                raise HTTPException(400, detail=f"SVG parse: {e}") from e
        elif req.format == "handwriting":
            hw = req.handwriting or {}
            try:
                strokes = handwriting_to_strokes(
                    hw.get("strokes") or [],
                    canvas_width=float(hw.get("canvas_width", 0)),
                    canvas_height=float(hw.get("canvas_height", 0)),
                )
            except (ValueError, TypeError) as e:
                raise HTTPException(400, detail=f"handwriting: {e}") from e
        else:
            raise HTTPException(
                400,
                detail=f"unknown format {req.format!r}; "
                       "expected json/svg/handwriting",
            )

        src = UserDictSource()
        try:
            path = src.save_character(req.char, strokes=strokes)
        except ValueError as e:
            raise HTTPException(400, detail=str(e)) from e
        return {
            "char": req.char,
            "unicode_hex": f"{ord(req.char):04x}",
            "stroke_count": len(strokes),
            "path": str(path),
        }

    @app.delete("/api/user-dict/{char}")
    async def user_dict_delete(char: str):
        from ..sources.user_dict import UserDictSource
        if len(char) != 1:
            raise HTTPException(400, detail="char must be a single character")
        src = UserDictSource()
        if not src.delete_character(char):
            raise HTTPException(
                404, detail=f"no user-dict entry for U+{ord(char):04X}")
        return {"deleted": char, "unicode_hex": f"{ord(char):04x}"}

    # ------ 布章 (patch) — Phase 5ax -----------------------------------

    _PATCH_PRESET_PATTERN = (
        "^(rectangle|name_tag|oval|circle|shield|hexagon|"
        "arch_top|arch_bottom|banner_left|banner_right)$"
    )
    _PATCH_TEXTPOS_PATTERN = "^(center|top|bottom|on_arc)$"
    _PATCH_FORMAT_PATTERN = "^(svg|gcode_cut|gcode_write)$"

    @app.get("/api/patch/capacity")
    async def patch_capacity_endpoint(
        preset: str = Query("rectangle", pattern=_PATCH_PRESET_PATTERN),
        patch_width_mm: float = Query(80.0, ge=10, le=500),
        patch_height_mm: float = Query(40.0, ge=10, le=500),
        char_size_mm: float = Query(18.0, gt=1, le=200),
        tile_rows: int = Query(1, ge=1, le=20),
        tile_cols: int = Query(1, ge=1, le=20),
        tile_gap_mm: float = Query(5.0, ge=0, le=100),
        page_width_mm: float = Query(210.0, ge=50, le=600),
        page_height_mm: float = Query(297.0, ge=50, le=600),
    ):
        from ..exporters.patch import patch_capacity
        return patch_capacity(
            preset=preset,                                    # type: ignore[arg-type]
            patch_width_mm=patch_width_mm,
            patch_height_mm=patch_height_mm,
            char_size_mm=char_size_mm,
            tile_rows=tile_rows, tile_cols=tile_cols,
            tile_gap_mm=tile_gap_mm,
            page_width_mm=page_width_mm, page_height_mm=page_height_mm,
        )

    @app.post("/api/patch")
    async def patch_post(req: PatchPostRequest):
        """POST variant — needed because GET URL length caps at ~2KB
        and a single base64-embedded SVG decoration easily blows past."""
        from ..exporters.patch import (
            render_patch_svg, render_patch_gcode_cut,
            render_patch_gcode_write, SvgDecoration,
        )
        if req.format not in ("svg", "gcode_cut", "gcode_write"):
            raise HTTPException(422, detail=f"unknown format {req.format!r}")

        def loader(ch: str):
            try:
                c, _r, _ = _load(ch, req.source, req.hook_policy)
                c = _upgrade_to_sung(c, req.style)
                c = _upgrade_to_seal(c, req.style)
                c = _upgrade_to_lishu(c, req.style)
                if req.style != "kaishu":
                    c = _apply_style(c, req.style)
                return c
            except HTTPException:
                return None

        decorations = [
            SvgDecoration(
                svg_content=d.svg_content, x_mm=d.x_mm, y_mm=d.y_mm,
                w_mm=d.w_mm, h_mm=d.h_mm,
            )
            for d in req.decorations
        ]

        common = dict(
            text=req.text, char_loader=loader,
            preset=req.preset,                                # type: ignore[arg-type]
            patch_width_mm=req.patch_width_mm,
            patch_height_mm=req.patch_height_mm,
            char_size_mm=req.char_size_mm,
            text_position=req.text_position,                  # type: ignore[arg-type]
            tile_rows=req.tile_rows, tile_cols=req.tile_cols,
            tile_gap_mm=req.tile_gap_mm,
            show_border=req.show_border,                      # Phase 5ay
        )

        if req.format == "svg":
            svg = render_patch_svg(
                **common, decorations=decorations,
                page_width_mm=req.page_width_mm,
                page_height_mm=req.page_height_mm,
            )
            return Response(content=svg, media_type="image/svg+xml",
                            headers={"Content-Disposition":
                                     _content_disposition("patch", "svg")})
        if req.format == "gcode_cut":
            gc = render_patch_gcode_cut(**common, decorations=decorations)
            return Response(content=gc, media_type="text/plain; charset=utf-8",
                            headers={"Content-Disposition":
                                     _content_disposition("patch_cut", "gcode")})
        # gcode_write
        # write layer skips decorations — they're for cutting, not writing.
        # show_border doesn't apply to the write layer (border is cut-only).
        gc = render_patch_gcode_write(**{
            k: v for k, v in common.items() if k != "show_border"
        })
        return Response(content=gc, media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition":
                                 _content_disposition("patch_write", "gcode")})

    @app.get("/api/patch")
    async def patch_get(
        text: str = Query("", max_length=2000),
        preset: str = Query("rectangle", pattern=_PATCH_PRESET_PATTERN),
        patch_width_mm: float = Query(80.0, ge=10, le=500),
        patch_height_mm: float = Query(40.0, ge=10, le=500),
        char_size_mm: float = Query(18.0, gt=1, le=200),
        text_position: str = Query("center", pattern=_PATCH_TEXTPOS_PATTERN),
        style: str = Query("kaishu", pattern=_STYLE_PATTERN),
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
        tile_rows: int = Query(1, ge=1, le=20),
        tile_cols: int = Query(1, ge=1, le=20),
        tile_gap_mm: float = Query(5.0, ge=0, le=100),
        page_width_mm: float = Query(210.0, ge=50, le=600),
        page_height_mm: float = Query(297.0, ge=50, le=600),
        format: str = Query("svg", pattern=_PATCH_FORMAT_PATTERN),
        show_border: bool = Query(True),                       # Phase 5ay
    ):
        """GET variant — no decorations (use POST for those)."""
        req = PatchPostRequest(
            text=text, preset=preset,
            patch_width_mm=patch_width_mm,
            patch_height_mm=patch_height_mm,
            char_size_mm=char_size_mm,
            text_position=text_position,
            style=style, source=source, hook_policy=hook_policy,
            tile_rows=tile_rows, tile_cols=tile_cols,
            tile_gap_mm=tile_gap_mm,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            format=format,
            show_border=show_border,
        )
        return await patch_post(req)

    # ------ 印章 (stamp) — Phase 5ay --------------------------------------

    _STAMP_PRESET_PATTERN = (
        "^(square_name|square_official|round|oval|rectangle_title)$"
    )
    _STAMP_FORMAT_PATTERN = "^(svg|gcode|pdf)$"

    @app.get("/api/stamp/capacity")
    async def stamp_capacity_endpoint(
        preset: str = Query("square_name", pattern=_STAMP_PRESET_PATTERN),
        stamp_width_mm: float = Query(25.0, ge=5, le=200),
        stamp_height_mm: float = Query(25.0, ge=5, le=200),
        char_size_mm: float = Query(10.0, gt=1, le=100),
        border_padding_mm: float = Query(2.0, ge=0, le=20),
        double_border: bool = Query(False),
    ):
        from ..exporters.stamp import stamp_capacity
        return stamp_capacity(
            preset=preset,                                    # type: ignore[arg-type]
            stamp_width_mm=stamp_width_mm,
            stamp_height_mm=stamp_height_mm,
            char_size_mm=char_size_mm,
            border_padding_mm=border_padding_mm,
            double_border=double_border,
        )

    @app.post("/api/stamp")
    async def stamp_post(req: StampPostRequest):
        from ..exporters.stamp import (
            render_stamp_svg, render_stamp_gcode,
        )
        from ..exporters.patch import SvgDecoration
        if req.format not in ("svg", "gcode", "pdf"):
            raise HTTPException(422, detail=f"unknown format {req.format!r}")

        def loader(ch: str):
            try:
                c, _r, _ = _load(ch, req.source, req.hook_policy)
                c = _upgrade_to_sung(c, req.style)
                # stamp 是 outline-only 渲染（_char_cut_paths 只看 stroke.outline，
                # 跳過 stroke.raw_track）。預設 *_outline_mode="skeleton" 會把 outline
                # 轉成 centerline polylines → stamp 渲染時跳過 → 預覽空白。
                # 用 "skip" 保留原 outline 才能被 stamp 雕刻 path 渲染。
                # 對應 patch endpoint 的設計（line 594-595）。
                c = _upgrade_to_seal(c, req.style, seal_outline_mode="skip")
                c = _upgrade_to_lishu(c, req.style, lishu_outline_mode="skip")
                if req.style != "kaishu":
                    c = _apply_style(c, req.style)
                return c
            except HTTPException:
                return None

        decorations = [
            SvgDecoration(svg_content=d.svg_content, x_mm=d.x_mm, y_mm=d.y_mm,
                          w_mm=d.w_mm, h_mm=d.h_mm)
            for d in req.decorations
        ]

        common = dict(
            text=req.text, char_loader=loader,
            preset=req.preset,                                # type: ignore[arg-type]
            stamp_width_mm=req.stamp_width_mm,
            stamp_height_mm=req.stamp_height_mm,
            char_size_mm=req.char_size_mm,
            show_border=req.show_border,
            double_border=req.double_border,
            border_padding_mm=req.border_padding_mm,
            decorations=decorations,
        )

        if req.format == "svg":
            svg = render_stamp_svg(**common)
            return Response(content=svg, media_type="image/svg+xml",
                            headers={"Content-Disposition":
                                     _content_disposition("stamp", "svg")})
        if req.format == "pdf":
            # 12b-4: SVG → PDF 直出（cairosvg svg2pdf）。印章是單頁，
            # 不需要走 sutra 的 SVG→PNG→Pillow 多頁合併流程。
            try:
                import cairosvg
            except ImportError as e:
                raise HTTPException(
                    500, detail=f"PDF backend unavailable: {e}. "
                                "Install with `pip install cairosvg`.",
                )
            svg = render_stamp_svg(**common)
            pdf_bytes = cairosvg.svg2pdf(bytestring=svg.encode("utf-8"))
            return Response(content=pdf_bytes, media_type="application/pdf",
                            headers={"Content-Disposition":
                                     _content_disposition("stamp", "pdf")})
        gc = render_stamp_gcode(
            **common, feed=req.feed, laser_power=req.laser_power,
        )
        return Response(content=gc, media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition":
                                 _content_disposition("stamp", "gcode")})

    @app.get("/api/stamp")
    async def stamp_get(
        text: str = Query("", max_length=200),
        preset: str = Query("square_name", pattern=_STAMP_PRESET_PATTERN),
        stamp_width_mm: float = Query(25.0, ge=5, le=200),
        stamp_height_mm: float = Query(25.0, ge=5, le=200),
        char_size_mm: float = Query(10.0, gt=1, le=100),
        show_border: bool = Query(True),
        double_border: bool = Query(False),
        border_padding_mm: float = Query(2.0, ge=0, le=20),
        style: str = Query("kaishu", pattern=_STYLE_PATTERN),
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
        feed: float = Query(1500.0, gt=0, le=10000),
        laser_power: int = Query(255, ge=1, le=1000),
        format: str = Query("svg", pattern=_STAMP_FORMAT_PATTERN),
    ):
        req = StampPostRequest(
            text=text, preset=preset,
            stamp_width_mm=stamp_width_mm, stamp_height_mm=stamp_height_mm,
            char_size_mm=char_size_mm,
            show_border=show_border, double_border=double_border,
            border_padding_mm=border_padding_mm,
            style=style, source=source, hook_policy=hook_policy,
            feed=feed, laser_power=laser_power, format=format,
        )
        return await stamp_post(req)

    # ------ 抄經 (sutra) — Phase 5az / 5bb -------------------------------

    # Filesystem-safe preset key — accepts builtins (eg. "heart_sutra") AND
    # user uploads (eg. "tao_te_ching", "我的座右銘"). 64 chars + CJK range.
    _SUTRA_PRESET_PATTERN = r"^[A-Za-z0-9_一-鿿\-]{1,64}$"
    _SUTRA_PAGE_TYPE_PATTERN = "^(cover|body|dedication)$"

    @app.get("/api/sutra/categories")
    async def sutra_categories_endpoint():
        """List the seven fixed categories + their preset counts."""
        from ..sutras import CATEGORY_ORDER, CATEGORY_LABELS, grouped_presets
        groups = grouped_presets()
        return {
            "categories": [
                {"key": cat, "label": CATEGORY_LABELS[cat],
                 "preset_count": len(g["presets"])}
                for cat, g in zip(CATEGORY_ORDER, groups)
            ],
        }

    @app.get("/api/sutra/closing-templates")
    async def sutra_closing_templates_endpoint():
        """5bg: list the closing-page template per category.

        UI uses this to populate the «載入分類預設模板» dropdown / button.
        """
        from ..sutras import (
            CATEGORY_ORDER, CATEGORY_LABELS,
            CLOSING_TEMPLATES, _closing_to_dict,
        )
        return {
            "templates": [
                {
                    "category": cat,
                    "label": CATEGORY_LABELS[cat],
                    "closing": _closing_to_dict(CLOSING_TEMPLATES[cat]),
                }
                for cat in CATEGORY_ORDER
            ],
        }

    @app.get("/api/sutra/presets")
    async def sutra_presets_endpoint(grouped: bool = Query(False)):
        """List all sutra presets (builtin + user) with load status.

        ``grouped=true`` returns ``categories`` array (UI optgroup);
        otherwise a flat ``presets`` list (back-compat).
        """
        from ..sutras import (
            available_presets, default_sutra_dir, grouped_presets, load_text,
        )
        from ..exporters.sutra import total_body_pages

        def _enrich(p: dict) -> dict:
            text = load_text(p["key"]) if p["ready"] else None
            # 5bh: page count uses default "compact" mode (matches UI default)
            return {**p,
                    "body_pages": total_body_pages(text) if text else 0}

        if grouped:
            cats = []
            for g in grouped_presets():
                cats.append({**g, "presets": [_enrich(p) for p in g["presets"]]})
            return {"sutra_dir": str(default_sutra_dir()), "categories": cats}
        return {
            "sutra_dir": str(default_sutra_dir()),
            "presets": [_enrich(p) for p in available_presets()],
        }

    # 5d-6: raw text of a sutra preset, for the handwriting practice
    # page's "經典" material picker. Returns plain UTF-8 text (no
    # rendering / no slicing — caller decides per-char iteration).
    @app.get("/api/sutra/text/{preset}")
    async def sutra_text_endpoint(
        preset: str = ApiPath(..., pattern=_SUTRA_PRESET_PATTERN),
    ):
        from ..sutras import get_sutra_info, load_text
        info = get_sutra_info(preset)
        if info is None:
            raise HTTPException(404, detail=f"unknown preset {preset!r}")
        text = load_text(preset)
        if text is None:
            raise HTTPException(
                422,
                detail=(f"sutra '{preset}' not loaded — drop "
                        f"{info.filename} into the sutra dir"),
            )
        return {
            "preset": preset,
            "title": info.title,
            "text": text,
            "char_count": sum(1 for ch in text if ch.strip()),
        }

    @app.get("/api/sutra/capacity")
    async def sutra_capacity_endpoint(
        preset: str = Query("heart_sutra", pattern=_SUTRA_PRESET_PATTERN),
        include_cover: bool = Query(False),
        include_dedication: bool = Query(False),
        text_mode: str = Query(
            "compact", pattern="^(compact|compact_marks|with_punct|raw)$"),
        # 5bj: orientation affects page count when geometry differs
        paper_orientation: str = Query(
            "landscape", pattern="^(landscape|portrait)$"),
    ):
        from ..sutras import load_text, get_sutra_info
        from ..exporters.sutra import sutra_page_count
        if get_sutra_info(preset) is None:
            raise HTTPException(404, detail=f"unknown preset {preset!r}")
        text = load_text(preset)
        if text is None:
            return {
                "preset": preset,
                "ready": False,
                "cover": 0, "body_pages": 0, "dedication": 0, "total": 0,
            }
        info = sutra_page_count(
            text, mode=text_mode,            # type: ignore[arg-type]
            orientation=paper_orientation,   # type: ignore[arg-type]
            include_cover=include_cover,
            include_dedication=include_dedication,
        )
        return {"preset": preset, "ready": True, **info}

    # --- User-uploaded preset CRUD -------------------------------------

    @app.post("/api/sutra/upload")
    async def sutra_upload_endpoint(req: SutraUploadRequest):
        """Save a new user-uploaded sutra. Returns the assigned key."""
        from ..sutras import save_user_preset, sanitize_key, CATEGORY_ORDER
        if req.category not in CATEGORY_ORDER:
            raise HTTPException(422,
                detail=f"unknown category {req.category!r}")
        if not (req.text or "").strip():
            raise HTTPException(422, detail="text is empty")
        desired = req.desired_key or req.title or "untitled"
        try:
            key = save_user_preset(
                desired_key=desired, text=req.text,
                title=req.title or sanitize_key(desired),
                subtitle=req.subtitle, category=req.category,
                source=req.source, description=req.description,
                language=req.language,
                is_mantra_repeat=req.is_mantra_repeat,
                repeat_count=req.repeat_count,
                tags=req.tags,
                # 5bd scholarly metadata
                author=req.author, editor=req.editor,
                notes=req.notes, source_url=req.source_url,
                # 5bg closing override
                closing=(req.closing.model_dump()
                         if req.closing is not None else None),
            )
        except ValueError as e:
            raise HTTPException(422, detail=str(e))
        return {"key": key, "ok": True}

    @app.get("/api/sutra/user/{key}")
    async def sutra_user_get_endpoint(key: str):
        from ..sutras import (
            get_sutra_info, read_user_text, _info_to_dict,
        )
        info = get_sutra_info(key)
        if info is None or info.is_builtin:
            raise HTTPException(404, detail=f"no user preset {key!r}")
        return {
            **_info_to_dict(info),
            "raw_text": read_user_text(key) or "",
        }

    # 5bd: read access to a builtin preset (metadata + raw text).
    # 5be: GET applies override; PUT writes override JSON / overwrites .txt.
    @app.get("/api/sutra/builtin/{key}")
    async def sutra_builtin_get_endpoint(key: str):
        from ..sutras import (
            BUILTIN_SUTRAS, _info_to_dict, _resolve_builtin_path,
            get_sutra_info,
        )
        if key not in BUILTIN_SUTRAS:
            raise HTTPException(404, detail=f"no builtin preset {key!r}")
        info = get_sutra_info(key)   # applies override
        path = _resolve_builtin_path(info)
        raw_text = path.read_text(encoding="utf-8") if path else ""
        return {**_info_to_dict(info), "raw_text": raw_text}

    @app.put("/api/sutra/builtin/{key}")
    async def sutra_builtin_put_endpoint(key: str, patch: SutraBuiltinPatch):
        """Persist metadata override + (optionally) overwrite the .txt file.

        Locked fields (key/filename/is_builtin/category/is_mantra_repeat/
        repeat_count) are silently ignored — see ``_BUILTIN_LOCKED_FIELDS``.
        """
        from ..sutras import (
            BUILTIN_SUTRAS, update_builtin_meta, write_builtin_text,
        )
        if key not in BUILTIN_SUTRAS:
            raise HTTPException(404, detail=f"no builtin preset {key!r}")
        payload = patch.model_dump(exclude_none=True)
        text_change = payload.pop("text", None)
        # Metadata override (drop empty submission gracefully)
        if payload:
            update_builtin_meta(key, payload)
        # Text overwrite (if provided and non-empty after strip)
        text_written = False
        if text_change is not None and text_change.strip():
            text_written = write_builtin_text(key, text_change)
        return {
            "ok": True,
            "meta_updated": bool(payload),
            "text_written": text_written,
        }

    @app.delete("/api/sutra/builtin/{key}")
    async def sutra_builtin_delete_endpoint(key: str):
        """Builtins cannot be deleted (5be). Always 405."""
        raise HTTPException(
            405, detail="builtin presets cannot be deleted; "
                        "consider clearing override.json or overwriting .txt",
        )

    @app.put("/api/sutra/user/{key}")
    async def sutra_user_put_endpoint(key: str, patch: SutraMetaPatch):
        from ..sutras import update_user_meta, get_sutra_info, CATEGORY_ORDER
        info = get_sutra_info(key)
        if info is None or info.is_builtin:
            raise HTTPException(404, detail=f"no user preset {key!r}")
        updates = {k: v for k, v in patch.model_dump().items() if v is not None}
        if "category" in updates and updates["category"] not in CATEGORY_ORDER:
            raise HTTPException(422,
                detail=f"unknown category {updates['category']!r}")
        ok = update_user_meta(key, updates)
        return {"ok": ok}

    @app.delete("/api/sutra/user/{key}")
    async def sutra_user_delete_endpoint(key: str):
        from ..sutras import delete_user_preset, get_sutra_info
        info = get_sutra_info(key)
        if info is None or info.is_builtin:
            raise HTTPException(404, detail=f"no user preset {key!r}")
        ok = delete_user_preset(key)
        return {"ok": ok}

    # --- Render endpoints (now accept any builtin or user key) ---------

    @app.post("/api/sutra")
    async def sutra_post(req: SutraPostRequest):
        from ..sutras import get_sutra_info, load_text
        from ..exporters.sutra import (
            render_sutra_page, render_sutra_cover, render_sutra_dedication,
            page_slice,
        )
        info = get_sutra_info(req.preset)
        if info is None:
            raise HTTPException(404, detail=f"unknown preset {req.preset!r}")
        if req.page_type not in ("cover", "body", "dedication"):
            raise HTTPException(422,
                detail=f"unknown page_type {req.page_type!r}")

        def loader(ch: str):
            try:
                c, _r, _ = _load(ch, req.source, req.hook_policy)
                c = _upgrade_to_sung(c, req.style)
                c = _upgrade_to_seal(c, req.style)
                c = _upgrade_to_lishu(c, req.style)
                if req.style != "kaishu":
                    c = _apply_style(c, req.style)
                return c
            except HTTPException:
                return None

        if req.page_type == "cover":
            svg = render_sutra_cover(
                info, char_loader=loader,
                scribe=req.scribe, signature=req.signature,
                orientation=req.paper_orientation,   # type: ignore[arg-type]
            )
        elif req.page_type == "dedication":
            # 5bg: if request didn't supply a verse, fall back to the
            # resolved closing metadata (per-sutra override > category template).
            from ..sutras import get_closing
            verse = req.dedication_verse
            if not verse:
                closing = get_closing(req.preset)
                verse = closing.verse
            svg = render_sutra_dedication(
                char_loader=loader,
                dedicator=req.dedicator, target=req.target,
                body_text=verse or None,
                signature=req.signature,
                orientation=req.paper_orientation,   # type: ignore[arg-type]
            )
        else:  # body
            text = load_text(req.preset)
            if text is None:
                raise HTTPException(
                    422,
                    detail=(f"sutra '{req.preset}' not loaded — "
                            f"drop {info.filename} into the sutra dir"),
                )
            # 5bh / 5bi: respect text_mode  /  5bj: geometry-aware slicing
            punct_marks: Optional[list[str]] = None
            if req.text_mode == "compact_marks":
                from ..exporters.sutra import page_slice_with_marks
                chars, punct_marks = page_slice_with_marks(
                    text, req.page_index,
                    orientation=req.paper_orientation,  # type: ignore[arg-type]
                )
            else:
                chars = page_slice(
                    text, req.page_index, mode=req.text_mode,  # type: ignore[arg-type]
                    orientation=req.paper_orientation,  # type: ignore[arg-type]
                )
            # 5bz: optionally build a second loader that keeps the
            # original outline (skip mode) so the renderer can lay a
            # faded reference letterform under the skeleton tracks.
            outline_loader = (
                _build_sutra_outline_loader(
                    source=req.source, style=req.style,
                    hook_policy=req.hook_policy,
                )
                if req.show_original_glyph
                else None
            )
            svg = render_sutra_page(
                chars, char_loader=loader,
                scribe=req.scribe, date_str=req.date_str,
                signature=req.signature,
                trace_fill=req.trace_fill,
                show_helper_lines=req.show_helper_lines,
                show_grid=req.show_grid,
                punct_marks=punct_marks,
                # 5bj: geometry
                orientation=req.paper_orientation,   # type: ignore[arg-type]
                direction=req.text_direction,         # type: ignore[arg-type]
                # 5bz: reference letterform (preview + PDF)
                outline_glyph_loader=outline_loader,
            )
        return Response(
            content=svg, media_type="image/svg+xml",
            headers={"Content-Disposition":
                     _content_disposition(f"sutra-{req.preset}", "svg")},
        )

    @app.get("/api/sutra")
    async def sutra_get(
        preset: str = Query("heart_sutra", pattern=_SUTRA_PRESET_PATTERN),
        page_index: int = Query(0, ge=0, le=200),
        page_type: str = Query("body", pattern=_SUTRA_PAGE_TYPE_PATTERN),
        style: str = Query("kaishu", pattern=_STYLE_PATTERN),
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
        scribe: str = Query(""),
        date_str: str = Query(""),
        dedicator: str = Query(""),
        target: str = Query(""),
        signature: str = Query(""),       # 5bh: empty default
        show_grid: bool = Query(True),
        show_helper_lines: bool = Query(True),
        trace_fill: str = Query("#cccccc"),
        dedication_verse: str = Query(""),
        # 5bh / 5bi: text processing mode (default = compact_marks)
        text_mode: str = Query(
            "compact_marks",
            pattern="^(compact|compact_marks|with_punct|raw)$"),
        # 5bj: page geometry
        paper_orientation: str = Query(
            "landscape", pattern="^(landscape|portrait)$"),
        text_direction: str = Query(
            "vertical", pattern="^(vertical|horizontal)$"),
        # 5bz: original-glyph reference layer (preview only)
        show_original_glyph: bool = Query(False),
    ):
        req = SutraPostRequest(
            preset=preset, page_index=page_index, page_type=page_type,
            style=style, source=source, hook_policy=hook_policy,
            scribe=scribe, date_str=date_str,
            dedicator=dedicator, target=target,
            signature=signature, show_grid=show_grid,
            show_helper_lines=show_helper_lines,
            trace_fill=trace_fill,
            dedication_verse=dedication_verse,
            text_mode=text_mode,
            paper_orientation=paper_orientation,
            text_direction=text_direction,
            show_original_glyph=show_original_glyph,
        )
        return await sutra_post(req)

    # ------ 5bi: PDF download — cover + body pages + dedication ----------

    @app.get("/api/sutra/pdf")
    async def sutra_pdf_endpoint(
        preset: str = Query("heart_sutra", pattern=_SUTRA_PRESET_PATTERN),
        style: str = Query("kaishu", pattern=_STYLE_PATTERN),
        source: str = Query("auto"),
        hook_policy: str = Query("animation"),
        scribe: str = Query(""),
        date_str: str = Query(""),
        dedicator: str = Query(""),
        target: str = Query(""),
        signature: str = Query(""),
        show_grid: bool = Query(True),
        show_helper_lines: bool = Query(True),
        trace_fill: str = Query("#cccccc"),
        dedication_verse: str = Query(""),
        text_mode: str = Query(
            "compact_marks",
            pattern="^(compact|compact_marks|with_punct|raw)$"),
        # 5bj: page geometry
        paper_orientation: str = Query(
            "landscape", pattern="^(landscape|portrait)$"),
        text_direction: str = Query(
            "vertical", pattern="^(vertical|horizontal)$"),
        include_cover: bool = Query(False),
        include_dedication: bool = Query(False),
        dpi: int = Query(200, ge=72, le=600),
        # 5bz: PDF defaults to *showing* the reference letterform — the
        # PDF is for human practice, so the original glyph shape behind
        # the skeleton is exactly what the user wants. Pass false to
        # opt out (e.g. plotter pipelines that print the PDF).
        show_original_glyph: bool = Query(True),
    ):
        """Render the full sutra (cover + body + dedication) and bundle the
        pages into a single PDF.

        SVG → PNG (cairosvg) → PDF (Pillow). dpi default 200 keeps output
        legible for printing while file size stays reasonable; 300 is the
        next step up for archival quality.
        """
        try:
            import io
            import cairosvg
            from PIL import Image
        except ImportError as e:
            raise HTTPException(
                500, detail=f"PDF backend unavailable: {e}. "
                            "Install with `pip install cairosvg Pillow`.",
            )
        from ..sutras import get_sutra_info, load_text
        from ..exporters.sutra import (
            get_geometry,
            render_sutra_cover, render_sutra_dedication, render_sutra_page,
            page_slice, page_slice_with_marks, total_body_pages,
        )
        geom = get_geometry(paper_orientation)  # type: ignore[arg-type]

        info = get_sutra_info(preset)
        if info is None:
            raise HTTPException(404, detail=f"unknown preset {preset!r}")
        text = load_text(preset)
        if text is None:
            raise HTTPException(
                422,
                detail=f"sutra '{preset}' not loaded — drop {info.filename} "
                       "into the sutra dir",
            )

        def loader(ch: str):
            try:
                c, _r, _ = _load(ch, source, hook_policy)
                c = _upgrade_to_sung(c, style)
                c = _upgrade_to_seal(c, style)
                c = _upgrade_to_lishu(c, style)
                if style != "kaishu":
                    c = _apply_style(c, style)
                return c
            except HTTPException:
                return None

        # 5bz: outline-bearing companion loader for the reference layer
        # (隸/篆 with mode="skip"). None when the user opts out.
        outline_loader = (
            _build_sutra_outline_loader(
                source=source, style=style, hook_policy=hook_policy,
            )
            if show_original_glyph
            else None
        )

        # Build the SVG for each page in order.
        svgs: list[str] = []
        if include_cover:
            svgs.append(render_sutra_cover(
                info, char_loader=loader,
                scribe=scribe, signature=signature,
                orientation=paper_orientation,    # type: ignore[arg-type]
            ))

        body_pages = total_body_pages(
            text, mode=text_mode,                  # type: ignore[arg-type]
            orientation=paper_orientation,         # type: ignore[arg-type]
        )
        for i in range(body_pages):
            punct_marks = None
            if text_mode == "compact_marks":
                chars, punct_marks = page_slice_with_marks(
                    text, i, orientation=paper_orientation,  # type: ignore[arg-type]
                )
            else:
                chars = page_slice(
                    text, i, mode=text_mode,                  # type: ignore[arg-type]
                    orientation=paper_orientation,            # type: ignore[arg-type]
                )
            svgs.append(render_sutra_page(
                chars, char_loader=loader,
                scribe=scribe, date_str=date_str,
                signature=signature,
                trace_fill=trace_fill,
                show_helper_lines=show_helper_lines,
                show_grid=show_grid,
                punct_marks=punct_marks,
                orientation=paper_orientation,    # type: ignore[arg-type]
                direction=text_direction,         # type: ignore[arg-type]
                # 5bv: PDF always uses polyline marks. cairosvg's <text>
                # rendering depends on the *server's* font stack, which can
                # be missing CJK fonts on a fresh Linux host (causing the
                # punctuation to render as empty boxes). Polyline tracing
                # uses our own glyph data, so the result is identical on
                # any deployment without requiring fonts-noto-cjk to be
                # installed first.
                mark_renderer="polyline",
                # 5bz: optional reference letterform under the skeleton.
                outline_glyph_loader=outline_loader,
            ))

        if include_dedication:
            from ..sutras import get_closing
            verse = dedication_verse or get_closing(preset).verse
            svgs.append(render_sutra_dedication(
                char_loader=loader,
                dedicator=dedicator, target=target,
                body_text=verse or None,
                signature=signature,
                orientation=paper_orientation,    # type: ignore[arg-type]
            ))

        if not svgs:
            raise HTTPException(422, detail="nothing to render")

        # 5bj: rasterise per-orientation (landscape 297×210 / portrait 210×297)
        px_w = int(round(geom.page_w_mm / 25.4 * dpi))
        px_h = int(round(geom.page_h_mm / 25.4 * dpi))
        images = []
        for svg in svgs:
            # 5bk: SVG has transparent bg by default; cairosvg outputs RGBA
            # with alpha=0 for non-painted pixels. Direct .convert("RGB")
            # collapses alpha=0 → BLACK on most PIL builds, not white. Two
            # fixes layered to be safe:
            #   1. tell cairosvg to paint a white background;
            #   2. composite RGBA over a white canvas before converting.
            png_bytes = cairosvg.svg2png(
                bytestring=svg.encode("utf-8"),
                output_width=px_w, output_height=px_h,
                background_color="white",
            )
            rgba = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            white = Image.new("RGB", rgba.size, "white")
            white.paste(rgba, mask=rgba.split()[3])  # alpha as mask
            images.append(white)

        buf = io.BytesIO()
        images[0].save(
            buf, format="PDF", save_all=True,
            append_images=images[1:],
            resolution=float(dpi),
        )
        return Response(
            content=buf.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition":
                     _content_disposition(f"sutra-{preset}", "pdf")},
        )

    # =================================================================
    # Phase 5g — 公眾分享庫 (gallery)
    # =================================================================
    #
    # Auth: magic-link via email, session cookie. All endpoints under
    # /api/gallery/* except auth/*.  The browser identifies itself with
    # the `psd_session` cookie, which we look up in the gallery's
    # SQLite DB. Anonymous read of the public list is allowed; uploads
    # / profile edits require a valid session.

    from fastapi import Cookie, Request
    from fastapi.responses import RedirectResponse
    from .. import gallery as _gallery
    from ..gallery.auth import (
        make_login_token, magic_link_url, consume_login_token,
        create_session, get_session_user, invalidate_session,
        purge_expired,
    )
    from ..gallery.smtp import send_magic_link_email
    from ..gallery import service as gallery_service

    SESSION_COOKIE = "psd_session"

    def _resolve_user(session_token: Optional[str]):
        """Returns user dict or None. Reusable across endpoints."""
        return get_session_user(session_token)

    def _require_user(session_token: Optional[str]):
        user = _resolve_user(session_token)
        if user is None:
            raise HTTPException(401, detail="請先登入")
        return user

    def _gallery_error_to_http(exc: gallery_service.GalleryError):
        raise HTTPException(exc.code, detail=str(exc))

    # Best-effort sweep on app boot — keeps the auth tables tidy.
    try:
        purge_expired()
    except Exception:
        pass  # never fatal

    # ----- /gallery (SPA shell) ----------------------------------------

    @app.get("/gallery", include_in_schema=False)
    async def gallery_page():
        page = STATIC_DIR / "gallery.html"
        if not page.is_file():
            return PlainTextResponse(
                "Gallery page missing — static/gallery.html not bundled.",
                status_code=404,
            )
        return FileResponse(page)

    # ----- magic-link auth ---------------------------------------------

    @app.post("/api/gallery/auth/request-login")
    async def gallery_auth_request_login(req: GalleryLoginRequest):
        email = (req.email or "").strip()
        if "@" not in email or len(email) > 200:
            raise HTTPException(422, detail="email 格式錯誤")
        try:
            token = make_login_token(email)
        except ValueError as e:
            raise HTTPException(422, detail=str(e))
        url = magic_link_url(token)
        try:
            await send_magic_link_email(email, url)
        except RuntimeError as e:
            # SMTP not configured + not in dev mode — surface clearly
            raise HTTPException(500, detail=str(e))
        return {"ok": True, "message": "登入連結已寄出，請查收信箱"}

    @app.get("/api/gallery/auth/consume", include_in_schema=False)
    async def gallery_auth_consume(token: str = Query(...)):
        user_id = consume_login_token(token)
        if user_id is None:
            return PlainTextResponse(
                "登入連結無效或已過期。請回到登入頁重新申請。",
                status_code=400,
            )
        session_token = create_session(user_id)
        # Redirect to the gallery SPA, with the session cookie set.
        resp = RedirectResponse(url="/gallery", status_code=303)
        resp.set_cookie(
            key=SESSION_COOKIE,
            value=session_token,
            max_age=30 * 24 * 60 * 60,
            httponly=True,
            samesite="lax",
            secure=False,    # dev convenience; production should
                             # be set via reverse proxy header
        )
        return resp

    @app.post("/api/gallery/auth/logout")
    async def gallery_auth_logout(
        psd_session: Optional[str] = Cookie(default=None),
    ):
        invalidate_session(psd_session)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(SESSION_COOKIE)
        return resp

    # ----- profile -----------------------------------------------------

    @app.get("/api/gallery/me")
    async def gallery_me(
        psd_session: Optional[str] = Cookie(default=None),
    ):
        user = _resolve_user(psd_session)
        if user is None:
            return {"logged_in": False}
        return {"logged_in": True, "user": user}

    @app.put("/api/gallery/me")
    async def gallery_me_update(
        patch: GalleryProfilePatch,
        psd_session: Optional[str] = Cookie(default=None),
    ):
        user = _require_user(psd_session)
        try:
            updated = gallery_service.update_profile(
                user_id=user["id"],
                display_name=patch.display_name,
                bio=patch.bio,
            )
        except gallery_service.GalleryError as e:
            _gallery_error_to_http(e)
        return {"user": updated}

    # ----- uploads -----------------------------------------------------

    @app.get("/api/gallery/uploads")
    async def gallery_uploads_list(
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=100),
    ):
        return gallery_service.list_uploads(page=page, size=size)

    @app.post("/api/gallery/uploads")
    async def gallery_uploads_create(
        file: UploadFile = File(...),
        title: str = Form(...),
        comment: str = Form(""),
        psd_session: Optional[str] = Cookie(default=None),
    ):
        user = _require_user(psd_session)
        content = await file.read()
        try:
            record = gallery_service.create_upload(
                user_id=user["id"],
                content_bytes=content,
                filename=file.filename,
                title=title,
                comment=comment,
            )
        except gallery_service.GalleryError as e:
            _gallery_error_to_http(e)
        return {"upload": record}

    @app.get("/api/gallery/uploads/{upload_id}")
    async def gallery_uploads_get(upload_id: int):
        try:
            return {"upload": gallery_service.get_upload(upload_id)}
        except gallery_service.GalleryError as e:
            _gallery_error_to_http(e)

    @app.get("/api/gallery/uploads/{upload_id}/download")
    async def gallery_uploads_download(upload_id: int):
        try:
            upload = gallery_service.get_upload(upload_id)
        except gallery_service.GalleryError as e:
            _gallery_error_to_http(e)
        if upload.get("hidden"):
            raise HTTPException(403, detail="這份檔案目前隱藏中")
        path = gallery_service.absolute_path_of(upload)
        if not path.is_file():
            raise HTTPException(
                500,
                detail="檔案在伺服器上遺失（DB 紀錄存在但實體檔不見）",
            )
        nice_name = (upload.get("filename") or
                     f"psd_{upload_id}.json")
        return FileResponse(
            path,
            media_type="application/json",
            filename=nice_name,
        )

    @app.delete("/api/gallery/uploads/{upload_id}")
    async def gallery_uploads_delete(
        upload_id: int,
        psd_session: Optional[str] = Cookie(default=None),
    ):
        user = _require_user(psd_session)
        try:
            gallery_service.delete_upload(
                upload_id=upload_id, user_id=user["id"],
            )
        except gallery_service.GalleryError as e:
            _gallery_error_to_http(e)
        return {"ok": True}

    # ------ health ------------------------------------------------------

    @app.get("/api/health")
    async def health():
        return {"ok": True, "version": "0.3.0"}

    return app


app = create_app()


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
