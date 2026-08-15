"""單字資料端點（character/meta/components/coverset/radical-route/coverage）＋CNS 字集狀態與診斷。

W3-R1（架構健檢 Wave 3）：自 server.py create_app() 機械搬遷，行為零變。
共用 helpers 暫由 ``..server`` 匯入（R2 收斂到專屬模組）。
"""
from __future__ import annotations

from pydantic import BaseModel

from fastapi import HTTPException, Query
from typing import Optional
from fastapi import APIRouter

from ...exporters.hanzi_writer import character_to_hanzi_writer_dict
from ...exporters.json_polyline import character_to_dict
from ...sources.chongxi_seal import (
    attribution_notice as _seal_attribution,
    get_seal_source as _get_seal,
)
from ...sources.moe_kaishu import (
    attribution_notice as _kaishu_attribution,
    get_kaishu_source as _get_kaishu_font,
)
from ...sources.moe_lishu import (
    attribution_notice as _lishu_attribution,
    get_lishu_source as _get_lishu,
)
from ...sources.moe_song import (
    attribution_notice as _song_attribution,
    get_song_source as _get_song,
)
from .. import char_pipeline as _pipeline
from ..char_pipeline import (
    _STYLE_PATTERN,
    _apply_style,
    _upgrade_to_lishu,
    _upgrade_to_seal,
    _upgrade_to_sung,
)

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


router = APIRouter()

# ------ data endpoints ----------------------------------------------

@router.get("/api/character/{char}")
def character_data(
    char: str,
    source: str = Query("auto"),
    hook_policy: str = Query("animation"),
):
    """hanzi-writer-compatible stroke data (for the front-end canvas)."""
    c, _r, _ = _pipeline._load(char, source, hook_policy)
    return character_to_hanzi_writer_dict(c)

# 5d-7: outline-only character data in native EM 2048 (Y-down) for the
# handwriting practice page's reference layer. Unlike /api/character
# which serves hanzi-writer-coord JSON, this returns raw outline cmds
# so the practice canvas can render the reference glyph at exactly the
# same coord system the user's strokes are captured in (EM 2048).
# Lishu/seal force outline_mode='skip' to preserve the outline (the
# default 'skeleton' mode would discard it — see 5bz).
@router.get("/api/handwriting/reference/{char}")
def handwriting_reference(
    char: str,
    style: str = Query("kaishu", pattern=_STYLE_PATTERN),
    source: str = Query("auto"),
    hook_policy: str = Query("animation"),
):
    from ...ir import EM_SIZE
    try:
        c, _r, _ = _pipeline._load(char, source, hook_policy)
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

@router.get("/api/meta/{char}")
def character_meta(
    char: str,
    source: str = Query("auto"),
    hook_policy: str = Query("animation"),
):
    """Diagnostics — classification codes, bbox, validation notes."""
    c, report, applied_fix = _pipeline._load(char, source, hook_policy)
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

# T1（識字教學頁）：部首歸類查詢——radicals.lookup（朱邦復四大類）的
# 薄 API 包裝。單一事實源（§27）：表留在 radicals.py，不複製進前端。
@router.get("/api/radical-info/{char}")
def radical_info(char: str):
    from ...radicals import lookup
    char = (char or "").strip()
    if len(char) != 1:
        raise HTTPException(422, detail="請提供單一字元")
    cat = lookup(char)
    return {
        "char": char,
        "is_radical": cat is not None,
        "category": cat.category if cat else None,
        "subcategory": cat.subcategory if cat else None,
    }


# T2（識字教學頁字義來源）：教育部《國語辭典簡編本》開放資料查詢。
# 釋義／例句為教育部原文逐字回傳（CC BY-ND 3.0 TW 禁止改作），回應帶
# attribution 供前端標示出處；bundle 缺席時誠實回 found=false（不裝懂）。
@router.get("/api/dict/{char}")
def dict_lookup(char: str):
    from ...sources import moe_dict
    char = (char or "").strip()
    if len(char) != 1:
        raise HTTPException(422, detail="請提供單一字元")
    entry = moe_dict.lookup(char)
    if entry is None:
        return {
            "char": char,
            "found": False,
            "ready": moe_dict.is_ready(),
            "attribution": moe_dict.MOE_ATTRIBUTION,
        }
    return {
        **entry,
        "found": True,
        "ready": True,
        "attribution": moe_dict.MOE_ATTRIBUTION,
        "license": moe_dict.MOE_LICENSE,
        "source_url": moe_dict.MOE_SOURCE_URL,
    }


# ------ 組件分析 (Phase A, 6b) ---------------------------------------
# See docs/VISION.md and docs/decisions/2026-04-28_phase_a_backend.md.
# Backend logic lives in stroke_order.components.

@router.get("/api/components/{char}")
def components_data(char: str):
    """Component decomposition for a single character.

    Returns:
        char: input character
        ids: IDS structure string (e.g. ``⿰木目`` for 相);
             equals char itself for atomic chars
        leaves: ordered list of leaf components (atomic-level)
        leaves_distinct: deduplicated leaves (set as list)
        is_atomic: True if char has no IDS structure
    """
    from ...components import decompose, default_ids_map, is_atomic
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

@router.get("/api/coverset/list")
def coverset_list():
    """List built-in cover-sets (metadata only — no char lists)."""
    from ...components import list_coversets
    return {"coversets": list_coversets()}

@router.get("/api/coverset/{name}")
def coverset_data(name: str):
    """Detailed cover-set: chars + decomposition stats.

    Returns name, title, source, url, size, chars (trad), chars_simp,
    and ``distinct_components`` (computed from current IDS data).
    """
    from ...components import (
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

# ------ 組件家族反查＋部首教學路線 (Phase 5cd) ---------------------

@router.get("/api/components/{char}/family")
def components_family(
    char: str,
    coverset: str = Query("cjk_common_808"),
    limit: int = Query(50, ge=1, le=500),
    include_variants: bool = Query(True),
):
    """Cover-set 內所有含此組件（或其偏旁變體）的字。

    部首本字領頭，其餘按（IDS 葉數, 字碼）簡→繁排序。
    """
    from ...components import component_family
    if len(char) != 1:
        raise HTTPException(400, detail="Single character required")
    try:
        return component_family(char, coverset,
                                include_variants=include_variants,
                                limit=limit)
    except KeyError:
        raise HTTPException(404, detail=f"Unknown cover-set {coverset!r}")

@router.get("/api/radical-route")
def radical_route_endpoint(
    coverset: str = Query("cjk_common_808"),
    min_family: int = Query(1, ge=1),
):
    """214 康熙部首的組件教學路線（家族大的先教）。

    每單元含 radical / strokes（部首筆畫數）/ family_size /
    preview（家族前 5 字）。該 cover-set 用不到的部首自動剔除。
    """
    from ...components import radical_route
    from ...exporters.kangxi_radicals import ALL_RADICALS, RADICALS
    band_of = {r: s for r, _i, s, _b in RADICALS}
    try:
        route = radical_route(ALL_RADICALS, coverset,
                              band_of=band_of, min_family=min_family)
    except KeyError:
        raise HTTPException(404, detail=f"Unknown cover-set {coverset!r}")
    return {"coverset": coverset, "unit_count": len(route),
            "route": route}

@router.post("/api/coverage/recommend")
def coverage_recommend(req: CoverageRecommendRequest):
    """Greedy set-cover: recommend next char(s) to write.

    Returns top-k recommendations + overall coverage status (covered
    component count, target component count, composable char count).
    Zero-gain candidates are excluded.
    """
    from ...components import (
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


# ------ CNS dictionary metadata (Phase 5al) -------------------------

@router.get("/api/cns-status")
def cns_status():
    """Diagnostic: are the CNS fonts / Properties files present?"""
    from ...sources.cns_font import CNSFontSource, default_cns_font_dir
    from ...sources.cns_components import (
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

@router.get("/api/seal-status")
def seal_status():
    """Phase 5at: 崇羲篆體 source state + mandatory CC BY-ND attribution.

    Frontend banners must surface ``attribution`` whenever
    ``ready`` is True so the licence terms are met.
    """
    from ...sources.chongxi_seal import default_seal_font_path
    seal = _get_seal()
    return {
        "font_file": str(default_seal_font_path()),
        "ready": seal.is_ready(),
        "glyph_count": seal.available_glyph_count() if seal.is_ready() else 0,
        "attribution": _seal_attribution(),
        "license": "CC BY-ND 3.0 TW or later",
        "license_url": "https://xiaoxue.iis.sinica.edu.tw/chongxi/copyright.htm",
    }

@router.get("/api/lishu-status")
def lishu_status():
    """Phase 5au: MoE 隸書 source state + mandatory attribution."""
    from ...sources.moe_lishu import default_lishu_font_path
    lishu = _get_lishu()
    return {
        "font_file": str(default_lishu_font_path()),
        "ready": lishu.is_ready(),
        "glyph_count": lishu.available_glyph_count() if lishu.is_ready() else 0,
        "attribution": _lishu_attribution(),
        "license": "CC BY-ND 3.0 TW",
        "license_url": "https://language.moe.gov.tw/result.aspx?classify_sn=23",
    }

@router.get("/api/song-status")
def song_status():
    """Phase 5av: MoE 標準宋體 source state + mandatory attribution.

    When ``ready=True`` the layered :func:`_upgrade_to_sung` will
    try this source first when the user picks ``style="mingti"``,
    falling back to CNS Sung only for chars MoE doesn't carry.
    """
    from ...sources.moe_song import default_song_font_path
    song = _get_song()
    return {
        "font_file": str(default_song_font_path()),
        "ready": song.is_ready(),
        "glyph_count": song.available_glyph_count() if song.is_ready() else 0,
        "attribution": _song_attribution(),
        "license": "CC BY-ND 3.0 TW",
        "license_url": "https://language.moe.gov.tw/result.aspx?classify_sn=23",
    }

@router.get("/api/kaishu-status")
def kaishu_status():
    """Phase 5aw: MoE 標準楷書 source state + mandatory attribution.

    When ``ready=True`` the source is wired into AutoSource as a
    Tier-3 outline fallback (after g0v/MMH, before CNS Kai), so
    chars not covered by stroke-data sources still render with
    MoE-quality outlines instead of falling all the way through.
    """
    from ...sources.moe_kaishu import default_kaishu_font_path
    ks = _get_kaishu_font()
    return {
        "font_file": str(default_kaishu_font_path()),
        "ready": ks.is_ready(),
        "glyph_count": ks.available_glyph_count() if ks.is_ready() else 0,
        "attribution": _kaishu_attribution(),
        "license": "CC BY-ND 3.0 TW",
        "license_url": "https://language.moe.gov.tw/result.aspx?classify_sn=23",
    }

@router.get("/api/decompose/{char}")
def cns_decompose(char: str):
    """Return ``CNS_component.txt`` decomposition for ``char``."""
    from ...sources.cns_components import CNSComponents
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

@router.get("/api/cns-stroke-diagnostics/{char}")
def cns_stroke_diagnostics(char: str):
    """Phase 5ap-A3a: compare canonical stroke spec vs actual skeleton.

    Returns canonical N-stroke layout (from CNS_strokes_sequence.txt)
    alongside what the current skeleton pipeline produces, so we can
    measure how often the two agree. Used by the 5ap-3 measurement
    script to drive the decision on whether A3b junction-aware
    splitting is worth building.
    """
    from ...sources.cns_strokes import CNSStrokes
    from ...sources.cns_font import (
        CNSFontSource, apply_cns_outline_mode,
    )
    from ...sources.g0v import CharacterNotFound
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
