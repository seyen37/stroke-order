"""抄經模式（sutra）——presets／上傳／內建覆寫／渲染／PDF。

W3-R1（架構健檢 Wave 3）：自 server.py create_app() 機械搬遷，行為零變。
共用 helpers 暫由 ``..server`` 匯入（R2 收斂到專屬模組）。
"""
from __future__ import annotations

from pydantic import BaseModel

import inspect
from fastapi import HTTPException, Path as ApiPath, Query
from fastapi.responses import Response
from typing import Optional
from fastapi import APIRouter

from ..char_pipeline import (
    _STYLE_PATTERN,
    _build_sutra_outline_loader,
    _memoize_char_loader,
    make_char_loader,
)
from ..responses import (
    svg_response,
    _content_disposition,
    _safe_filename_part,
    _style_label,
)

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
    # 5ew-R2：預覽分段載入——給定時只渲染此集合內的字形，其餘描紅格
    # 留白（版面/格線/句讀/cellmap 照常）。空字串＝純空白描紅格（進度
    # 條第一階段，秒回）；None（預設）＝全部渲染（下載/PDF 路徑不變）。
    # 僅 body 頁生效。留白格的 cellmap 會帶 data-missing（loader 探測
    # 被過濾）——前端合併批次時逐格修正。
    glyph_chars: Optional[str] = None


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
    text: Optional[str] = None


router = APIRouter()

# ------ 抄經 (sutra) — Phase 5az / 5bb -------------------------------

# Filesystem-safe preset key — accepts builtins (eg. "heart_sutra") AND
# user uploads (eg. "tao_te_ching", "我的座右銘"). 64 chars + CJK range.
_SUTRA_PRESET_PATTERN = r"^[A-Za-z0-9_一-鿿\-]{1,64}$"
# 5bo: "table" — preset-specific table-layout page (週期表 / 九九乘法表)
_SUTRA_PAGE_TYPE_PATTERN = "^(cover|body|dedication|table)$"

def _table_page_renderer(preset: str):
    """5bo: return the table-layout renderer for ``preset``, or None.

    Presets with a dedicated single-page table layout register here;
    the sutra endpoints expose them via ``page_type=table`` and the
    PDF export appends the page after the sequential body pages.
    """
    if preset == "periodic_table":
        from ...exporters.periodic_table import render_periodic_table_page
        return render_periodic_table_page
    if preset == "multiplication_table":
        from ...exporters.multiplication_table import (
            render_multiplication_table_page,
        )
        return render_multiplication_table_page
    if preset == "solar_terms":
        from ...exporters.solar_terms import render_solar_terms_page
        return render_solar_terms_page
    if preset == "kangxi_radicals":
        from ...exporters.kangxi_radicals import (
            render_kangxi_radicals_page,
        )
        return render_kangxi_radicals_page
    if preset == "cangjie_roots":
        from ...exporters.cangjie_roots import render_cangjie_roots_page
        return render_cangjie_roots_page
    if preset == "zhuyin_symbols":
        from ...exporters.zhuyin import render_zhuyin_page
        return render_zhuyin_page
    return None

@router.get("/api/sutra/categories")
def sutra_categories_endpoint():
    """List the seven fixed categories + their preset counts."""
    from ...sutras import CATEGORY_ORDER, CATEGORY_LABELS, grouped_presets
    groups = grouped_presets()
    return {
        "categories": [
            {"key": cat, "label": CATEGORY_LABELS[cat],
             "preset_count": len(g["presets"])}
            for cat, g in zip(CATEGORY_ORDER, groups)
        ],
    }

@router.get("/api/sutra/closing-templates")
def sutra_closing_templates_endpoint():
    """5bg: list the closing-page template per category.

    UI uses this to populate the «載入分類預設模板» dropdown / button.
    """
    from ...sutras import (
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

@router.get("/api/sutra/presets")
def sutra_presets_endpoint(grouped: bool = Query(False)):
    """List all sutra presets (builtin + user) with load status.

    ``grouped=true`` returns ``categories`` array (UI optgroup);
    otherwise a flat ``presets`` list (back-compat).
    """
    from ...sutras import (
        available_presets, default_sutra_dir, grouped_presets, load_text,
    )
    from ...exporters.sutra import total_body_pages

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
@router.get("/api/sutra/text/{preset}")
def sutra_text_endpoint(
    preset: str = ApiPath(..., pattern=_SUTRA_PRESET_PATTERN),
):
    from ...sutras import get_sutra_info, load_text
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

@router.get("/api/sutra/capacity")
def sutra_capacity_endpoint(
    preset: str = Query("heart_sutra", pattern=_SUTRA_PRESET_PATTERN),
    include_cover: bool = Query(False),
    include_dedication: bool = Query(False),
    text_mode: str = Query(
        "compact", pattern="^(compact|compact_marks|with_punct|raw)$"),
    # 5bj: orientation affects page count when geometry differs
    paper_orientation: str = Query(
        "landscape", pattern="^(landscape|portrait)$"),
):
    from ...sutras import load_text, get_sutra_info
    from ...exporters.sutra import sutra_page_count
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

@router.post("/api/sutra/upload")
def sutra_upload_endpoint(req: SutraUploadRequest):
    """Save a new user-uploaded sutra. Returns the assigned key."""
    from ...sutras import save_user_preset, sanitize_key, CATEGORY_ORDER
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

@router.get("/api/sutra/user/{key}")
def sutra_user_get_endpoint(key: str):
    from ...sutras import (
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
@router.get("/api/sutra/builtin/{key}")
def sutra_builtin_get_endpoint(key: str):
    from ...sutras import (
        BUILTIN_SUTRAS, _info_to_dict, _resolve_builtin_path,
        get_sutra_info,
    )
    if key not in BUILTIN_SUTRAS:
        raise HTTPException(404, detail=f"no builtin preset {key!r}")
    info = get_sutra_info(key)   # applies override
    path = _resolve_builtin_path(info)
    raw_text = path.read_text(encoding="utf-8") if path else ""
    return {**_info_to_dict(info), "raw_text": raw_text}

@router.put("/api/sutra/builtin/{key}")
def sutra_builtin_put_endpoint(key: str, patch: SutraBuiltinPatch):
    """Persist metadata override + (optionally) overwrite the .txt file.

    Locked fields (key/filename/is_builtin/category/is_mantra_repeat/
    repeat_count) are silently ignored — see ``_BUILTIN_LOCKED_FIELDS``.
    """
    from ...sutras import (
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

@router.delete("/api/sutra/builtin/{key}")
def sutra_builtin_delete_endpoint(key: str):
    """Builtins cannot be deleted (5be). Always 405."""
    raise HTTPException(
        405, detail="builtin presets cannot be deleted; "
                    "consider clearing override.json or overwriting .txt",
    )

@router.put("/api/sutra/user/{key}")
def sutra_user_put_endpoint(key: str, patch: SutraMetaPatch):
    from ...sutras import update_user_meta, get_sutra_info, CATEGORY_ORDER
    info = get_sutra_info(key)
    if info is None or info.is_builtin:
        raise HTTPException(404, detail=f"no user preset {key!r}")
    updates = {k: v for k, v in patch.model_dump().items() if v is not None}
    if "category" in updates and updates["category"] not in CATEGORY_ORDER:
        raise HTTPException(422,
            detail=f"unknown category {updates['category']!r}")
    ok = update_user_meta(key, updates)
    return {"ok": ok}

@router.delete("/api/sutra/user/{key}")
def sutra_user_delete_endpoint(key: str):
    from ...sutras import delete_user_preset, get_sutra_info
    info = get_sutra_info(key)
    if info is None or info.is_builtin:
        raise HTTPException(404, detail=f"no user preset {key!r}")
    ok = delete_user_preset(key)
    return {"ok": ok}

# --- Render endpoints (now accept any builtin or user key) ---------

@router.post("/api/sutra")
def sutra_post(req: SutraPostRequest):
    # 5dp：sync def——重字形載入/SVG 渲染走 threadpool、不凍 event loop
    # （§9/5ck；stencil 端點同一策略）。避免 Render 單 worker 逾時 502。
    from ...sutras import get_sutra_info, load_text
    from ...exporters.sutra import (
        render_sutra_page, render_sutra_cover, render_sutra_dedication,
        page_slice,
    )
    info = get_sutra_info(req.preset)
    if info is None:
        raise HTTPException(404, detail=f"unknown preset {req.preset!r}")
    if req.page_type not in ("cover", "body", "dedication", "table"):
        raise HTTPException(422,
            detail=f"unknown page_type {req.page_type!r}")
    # 5bo: table-layout pages exist only for presets with a dedicated
    # table renderer — reject others early with a clear message.
    if req.page_type == "table" and \
            _table_page_renderer(req.preset) is None:
        raise HTTPException(422,
            detail="page_type 'table' is only available for presets "
                   "with a table layout (periodic_table, "
                   "multiplication_table, solar_terms, "
                   "kangxi_radicals, cangjie_roots, zhuyin_symbols)")

    # 5dp：每字只載一次
    loader = make_char_loader(
        req.source, req.hook_policy, req.style, memoize=True)

    if req.page_type == "table":
        # 5bo: preset-specific table layout, one A4-landscape page.
        render_table = _table_page_renderer(req.preset)
        table_kwargs = dict(
            char_loader=loader,
            trace_fill=req.trace_fill,
            show_grid=req.show_grid,
        )
        # 5dw: forward the 逐字手寫 click-map to any table renderer that
        # supports it (periodic_table reuses render_sutra_page, one glyph
        # per 米字格). Capability-detect via signature so future
        # single-glyph table renderers opt in for free — no hardcoded
        # preset name, and self-drawn multi-char tables stay untouched.
        if "emit_cellmap" in inspect.signature(render_table).parameters:
            table_kwargs["emit_cellmap"] = req.emit_cellmap
        svg = render_table(**table_kwargs)
    elif req.page_type == "cover":
        svg = render_sutra_cover(
            info, char_loader=loader,
            scribe=req.scribe, signature=req.signature,
            orientation=req.paper_orientation,   # type: ignore[arg-type]
        )
    elif req.page_type == "dedication":
        # 5bg: if request didn't supply a verse, fall back to the
        # resolved closing metadata (per-sutra override > category template).
        from ...sutras import get_closing
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
            from ...exporters.sutra import page_slice_with_marks
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
            _memoize_char_loader(_build_sutra_outline_loader(
                source=req.source, style=req.style,
                hook_policy=req.hook_policy,
            ))
            if req.show_original_glyph
            else None
        )
        # 5ew-R2：分段載入——glyph_chars 給定時把兩個 loader 都包成
        # 「集合外回 None」（描紅格留白＝既有缺字語意；載入成本只花在
        # 集合內的字）。空集合＝零載入、純版面，秒回。
        if req.glyph_chars is not None:
            _allowed = set(req.glyph_chars)
            _full_loader = loader
            loader = (
                lambda ch: _full_loader(ch) if ch in _allowed else None)
            if outline_loader is not None:
                _full_outline = outline_loader
                outline_loader = (
                    lambda ch: _full_outline(ch) if ch in _allowed else None)
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
            # 5dt: click-map overlay (preview only)
            emit_cellmap=req.emit_cellmap,
        )
    # 5dz: 友善下載檔名——{經典}_{字型風格}_{手寫|範例}。「手寫」＝該頁
    # 含使用者手寫層（sutra-trace-user，見 5dv）；否則「範例」。封面/迴向
    # 以頁型標示。前端讀 Content-Disposition 當下載檔名。
    _title = _safe_filename_part(info.title or req.preset)
    _slabel = _style_label(req.style)
    if req.page_type in ("body", "table"):
        _kind = "手寫" if "sutra-trace-user" in svg else "範例"
        _basename = f"{_title}_{_slabel}_{_kind}"
    elif req.page_type == "cover":
        _basename = f"{_title}_{_slabel}_封面"
    else:  # dedication
        _basename = f"{_title}_{_slabel}_迴向"
    return svg_response(svg, headers={"Content-Disposition":
                 _content_disposition(_basename, "svg")})

@router.get("/api/sutra")
def sutra_get(       # 5dp：sync def（見 sutra_post）
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
    # 5dt: per-cell click-map overlay (preview only)
    emit_cellmap: bool = Query(False),
    # 5ex-A1：R2 分段預覽參數補進 GET——預覽改 GET 走 5eu 回應快取
    # （None=完整；""=零載入純版面；字集=集合外回 None 描紅留白）
    glyph_chars: Optional[str] = Query(None),
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
        emit_cellmap=emit_cellmap,
        glyph_chars=glyph_chars,
    )
    return sutra_post(req)

# ------ 5bi: PDF download — cover + body pages + dedication ----------

@router.get("/api/sutra/pdf")
def sutra_pdf_endpoint(       # 5dp：sync def（見 sutra_post；PDF 最重）
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
    from ...sutras import get_sutra_info, load_text
    from ...exporters.sutra import (
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

    # 5dp：跨頁共用、每字只載一次（多頁 PDF 省最多）。
    loader = make_char_loader(source, hook_policy, style, memoize=True)

    # 5bz: outline-bearing companion loader for the reference layer
    # (隸/篆 with mode="skip"). None when the user opts out.
    outline_loader = (
        _memoize_char_loader(_build_sutra_outline_loader(
            source=source, style=style, hook_policy=hook_policy,
        ))
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

    # 5bo: presets with a table layout get that page appended after
    # the sequential body pages (landscape only — table pages have a
    # fixed A4-landscape geometry).
    render_table = _table_page_renderer(preset)
    if render_table is not None and paper_orientation == "landscape":
        svgs.append(render_table(
            char_loader=loader,
            trace_fill=trace_fill,
            show_grid=show_grid,
        ))

    if include_dedication:
        from ...sutras import get_closing
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
    # 5dz: 友善下載檔名——{經典}_{字型風格}_{手寫|範例}。整本 PDF 只要
    # 任一頁含使用者手寫層即標「手寫」，否則「範例」。
    _title = _safe_filename_part(info.title or preset)
    _slabel = _style_label(style)
    _kind = "手寫" if any("sutra-trace-user" in s for s in svgs) else "範例"
    _basename = f"{_title}_{_slabel}_{_kind}"
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition":
                 _content_disposition(_basename, "pdf")},
    )
