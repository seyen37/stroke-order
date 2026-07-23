"""文字排版類模式：筆記（notebook）、信紙（letter）、字模（stencil）、稿紙（manuscript）、字帖（grid）、單字下載（export）。

W3-R1（架構健檢 Wave 3）：自 server.py create_app() 機械搬遷，行為零變。
共用 helpers 暫由 ``..server`` 匯入（R2 收斂到專屬模組）。
"""
from __future__ import annotations

from pydantic import BaseModel

from fastapi import HTTPException, Query
from fastapi.responses import Response
from typing import Optional
from fastapi import APIRouter

from ...exporters.gcode import GCodeOptions, characters_to_gcode
from ...exporters.json_polyline import character_to_json
from ...exporters.svg import character_to_svg
from .. import char_pipeline as _pipeline
from ..char_pipeline import (
    _CNS_MODE_PATTERN,
    _STYLE_PATTERN,
    _apply_style,
    _parse_zhuyin_map,
    _upgrade_to_lishu,
    _upgrade_to_seal,
    _upgrade_to_sung,
    make_char_loader,
)
from ..capacity import capacity_summary
from ..responses import svg_response, _content_disposition
from ..versioning import APP_VERSION

class ZoneSpec(BaseModel):
    x: float
    y: float
    w: float
    h: float
    label: Optional[str] = None
    svg_content: Optional[str] = None
    content_viewbox: Optional[list[float]] = None
    stretch: bool = False


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
    style: str = "kaishu"


router = APIRouter()

# ------ 筆記模式 (notebook) -----------------------------------------

@router.get("/api/notebook/capacity")
def notebook_capacity(
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
    from ...exporters.notebook import build_notebook_layout

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
    cap = capacity_summary(text, layout, direction=direction)  # type: ignore
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

@router.get("/api/notebook")
def notebook(
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
    # 5cz：注音欄——「字:注音,…」前端供給（同 5cu 字帖）；
    # 參數存在即開欄（pair 2:1 格寬）。SVG 先行、gcode/json v2
    zhuyin_map: Optional[str] = Query(None, max_length=8000),
):
    from ...exporters.notebook import (
        flow_notebook, render_notebook_page_svg,
        render_notebook_gcode, render_notebook_json,
    )
    from ...exporters.multi_page import render_pages_as_single_or_zip
    from ...layouts import layout_capacity

    loader = make_char_loader(
        source, hook_policy, style, cns_outline_mode=cns_outline_mode)

    import json as _json
    zones_list = None
    if zones_json:
        try:
            zones_list = _json.loads(zones_json)
        except _json.JSONDecodeError:
            raise HTTPException(422, detail="invalid zones_json")

    zmap, zchars = _parse_zhuyin_map(zhuyin_map, source, hook_policy)

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
        zhuyin=zmap is not None,
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
        svg = render_notebook_page_svg(pages[page - 1],
                                       cell_style=cell_style,
                                       zhuyin_map=zmap,
                                       zhuyin_chars=zchars)
        headers = {}
        if download:
            headers["Content-Disposition"] = _content_disposition(
                f"notebook-page-{page:02d}", "svg"
            )
        return svg_response(svg, headers=headers, mode="notebook")

    def _render(p):
        return render_notebook_page_svg(p, cell_style=cell_style,
                                        zhuyin_map=zmap,
                                        zhuyin_chars=zchars)

    body, mime, ext = render_pages_as_single_or_zip(
        pages, _render, filename_prefix="notebook-page",
        envelope_mode="notebook", app_version=APP_VERSION,
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

@router.post("/api/notebook")
def notebook_post(req: NotebookPostRequest):
    """POST variant — accepts arbitrary-sized SVG content in zones."""
    from ...exporters.notebook import (
        flow_notebook, render_notebook_page_svg,
        render_notebook_gcode, render_notebook_json,
    )
    from ...exporters.multi_page import render_pages_as_single_or_zip

    # Phase 5al: NotebookPostRequest doesn't expose cns_outline_mode yet;
    # factory default "skip" matches the existing behaviour.
    loader = make_char_loader(req.source, req.hook_policy, req.style)

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
        return svg_response(svg, headers={"X-Stroke-Order-Pages": str(len(pages))},
                            mode="notebook")

    def _render(p):
        return render_notebook_page_svg(p, cell_style=req.cell_style)  # type: ignore

    body, mime, ext = render_pages_as_single_or_zip(
        pages, _render, filename_prefix="notebook-page",
        envelope_mode="notebook", app_version=APP_VERSION,
    )
    return Response(
        content=body, media_type=mime,
        headers={"X-Stroke-Order-Pages": str(len(pages))},
    )

# ------ 信紙模式 (letter) ------------------------------------------

@router.get("/api/letter/capacity")
def letter_capacity(
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
    from ...exporters.letter import build_letter_layout
    layout = build_letter_layout(
        preset=preset, line_height_mm=line_height_mm,  # type: ignore
        margin_mm=margin_mm,
        title_space_mm=title_space_mm,
        signature_space_mm=signature_space_mm,
        direction=direction,  # type: ignore
        lines_per_page=lines_per_page,
    )
    cap = capacity_summary(text, layout, direction=direction)  # type: ignore
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

@router.get("/api/letter")
def letter(
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
    # 5cz：注音欄（同 notebook；SVG 先行、gcode/json v2）
    zhuyin_map: Optional[str] = Query(None, max_length=8000),
):
    from ...exporters.letter import (
        flow_letter, render_letter_page_svg,
        render_letter_gcode, render_letter_json,
    )
    from ...exporters.multi_page import render_pages_as_single_or_zip
    from ...layouts import layout_capacity

    loader = make_char_loader(
        source, hook_policy, style, cns_outline_mode=cns_outline_mode)

    zmap, zchars = _parse_zhuyin_map(zhuyin_map, source, hook_policy)

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
        zhuyin=zmap is not None,
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
            zhuyin_map=zmap,
            zhuyin_chars=zchars,
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
        return svg_response(svg, headers=headers, mode="letter")

    body, mime, ext = render_pages_as_single_or_zip(
        pages, _render, filename_prefix="letter-page",
        envelope_mode="letter", app_version=APP_VERSION,
    )
    headers = {"X-Stroke-Order-Pages": str(len(pages)), **cap_headers}
    if download:
        headers["Content-Disposition"] = _content_disposition(
            "letter", ext
        )
    return Response(content=body, media_type=mime, headers=headers)

# ------ Phase 5dc: 鏤空字／噴漆字模 (stencil / cutout) ----------------

@router.get("/api/stencil")
def api_stencil(
    chars: str = Query(..., min_length=1, max_length=12),
    kind: str = Query("stencil", pattern="^(stencil|cutout)$",
                      description="stencil=噴漆模板（板留、字挖掉、"
                                  "孔洞鑿白橋）；cutout=鏤空字（字即"
                                  "本體、斷件補連筋/掛邊框）"),
    source: str = Query("moe_kaishu"),
    style: str = Query("physical",
                       description="切割風格（切割策略 preset）；目前"
                                   "physical＝物理完整（全連派、殘腔 0）"),
    envelope_depth: int = Query(1, ge=1, le=8,
                                description="方正簡潔（envelope）連筋深度："
                                            "只鑿深度 ≤ 此值的孔、深層留島；"
                                            "越大連越深、留越少島。physical "
                                            "恆全連、不受此值影響"),
    char_height_mm: float = Query(50.0, ge=10, le=300),
    bridge_width_mm: float = Query(2.0, ge=0.5, le=10),
    bridge_count: int = Query(4, ge=2, le=4),
    bold_mm: float = Query(0.0, ge=0, le=5),
    spacing_mm: float = Query(5.0, ge=0, le=100),
    frame: bool = Query(True, description="cutout 限定：外掛邊框"),
    frame_width_mm: float = Query(4.0, ge=1, le=20),
    format: str = Query("svg", pattern="^(svg|dxf|gcode)$"),
    download: bool = Query(False),
):
    """5dc：雷切/噴漆字模。同步 def——光柵幾何運算走 threadpool
    （5ck 教訓：async def 內跑重活會凍 event loop）。"""
    from ...exporters import zentangle as _zt
    from ...exporters.stencil import (
        CUTTING_STYLES, render_stencil_dxf, render_stencil_gcode,
        render_stencil_svg, stencil_geometry,
    )
    if source not in _zt.SOURCE_REGISTRY:
        raise HTTPException(422, detail=f"unknown source: {source}")
    if style not in CUTTING_STYLES:
        raise HTTPException(
            422, detail=f"unknown cutting style: {style!r}; "
                        f"available: {sorted(CUTTING_STYLES)}")
    char_polys = []
    loaded_chars: list[str] = []
    missing: list[str] = []
    for ch in chars:
        if ch.isspace():
            continue
        try:
            polys = _zt.extract_outline_polylines(ch, source=source)
        except Exception:                  # noqa: BLE001 — 缺字/缺字型
            missing.append(ch)
            continue
        if polys:
            char_polys.append(polys)
            loaded_chars.append(ch)
        else:
            missing.append(ch)
    if not char_polys:
        raise HTTPException(
            400, detail=f"無可用字形（skipped: {missing!r}）——"
                        f"請確認字型檔已安裝或換資料源")
    loops, w_mm, h_mm, stats = stencil_geometry(
        char_polys, kind=kind,                     # type: ignore[arg-type]
        style=style, envelope_depth=envelope_depth,
        char_height_mm=char_height_mm,
        bridge_width_mm=bridge_width_mm,
        bridge_count=bridge_count,
        bold_mm=bold_mm, spacing_mm=spacing_mm,
        frame=frame, frame_width_mm=frame_width_mm,
    )
    basename = "".join(loaded_chars) + (
        "_噴漆字模" if kind == "stencil" else "_鏤空字")
    headers = {
        "X-Stencil-Loops": str(stats.get("cut_loops", 0)),
        "X-Stencil-Holes": str(stats.get("holes_bridged", -1)),
        "X-Stencil-Components": str(stats.get("components_before", -1)),
        "X-Stencil-Skipped": str(len(missing)),
        "X-Stencil-Style": str(stats.get("style", style)),
        "X-Stencil-Depth": str(stats.get("max_depth", 0)),
    }
    if format == "dxf":
        body = render_stencil_dxf(loops)
        if download:
            headers["Content-Disposition"] = _content_disposition(
                basename, "dxf")
        return Response(content=body,
                        media_type="application/dxf",
                        headers=headers)
    if format == "gcode":
        body = render_stencil_gcode(loops, height_mm=h_mm)
        if download:
            headers["Content-Disposition"] = _content_disposition(
                basename, "gcode")
        return Response(content=body,
                        media_type="text/plain; charset=utf-8",
                        headers=headers)
    svg = render_stencil_svg(loops, w_mm, h_mm,
                             kind=kind)          # type: ignore[arg-type]
    if download:
        headers["Content-Disposition"] = _content_disposition(
            basename, "svg")
    return svg_response(svg, headers=headers, mode="stencil")

# ------ 稿紙模式 (manuscript) ---------------------------------------

@router.get("/api/manuscript/capacity")
def manuscript_capacity(
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
    from ...exporters.manuscript import (
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

@router.get("/api/manuscript")
def manuscript(
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
    from ...exporters.manuscript import (
        flow_manuscript, render_manuscript_page_svg,
        render_manuscript_gcode, render_manuscript_json,
        MANUSCRIPT_PRESETS,
    )
    from ...exporters.multi_page import render_pages_as_single_or_zip

    loader = make_char_loader(
        source, hook_policy, style, cns_outline_mode=cns_outline_mode)

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
        return svg_response(svg, headers=headers, mode="manuscript")

    body, mime, ext = render_pages_as_single_or_zip(
        pages, _render, filename_prefix="manuscript-page",
        envelope_mode="manuscript", app_version=APP_VERSION,
    )
    headers = dict(cap_headers)
    if download:
        headers["Content-Disposition"] = _content_disposition(
            "manuscript", ext
        )
    return Response(content=body, media_type=mime, headers=headers)


# ------ 字帖 grid mode ---------------------------------------------

@router.get("/api/grid")
def grid(
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
    # 5cu：注音欄——「字:注音,字:注音」由前端算好傳入（pinyin-pro
    # ＋規則轉換表），伺服器零字典依賴；參數存在即開欄
    zhuyin_map: Optional[str] = Query(
        None, max_length=800,
        description="注音欄映射，格式：字:ㄅㄆㄇˊ,字:…（前端供給）"),
):
    """Render a 字帖 for multiple characters in SVG / G-code / JSON.

    - ``format=svg`` (default): visual worksheet (all tiers).
    - ``format=gcode``: primary tier only, positioned per-cell for a
      writing-robot (AxiDraw-style defaults).
    - ``format=json``: full grid metadata + per-cell data.

    If ``download=true``, Content-Disposition is set for browser
    download behaviour.
    """
    from ...exporters.grid import (
        render_grid_svg, render_grid_gcode, render_grid_json,
    )
    loaded = []
    skipped: list[str] = []
    for ch in chars:
        if ch.isspace():
            continue
        try:
            c, _r, _ = _pipeline._load(ch, source, hook_policy)
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

    # 5cu：注音欄——SVG 與 G-code（5cy）共用；解析抽 5cz 共用
    # helper（grid/notebook/letter 三消費者）
    zmap, zchars = _parse_zhuyin_map(zhuyin_map, source, hook_policy)

    if format == "gcode":
        body = render_grid_gcode(
            loaded, cols=cols,
            ghost_copies=ghost_copies, blank_copies=blank_copies,
            direction=direction,   # type: ignore
            cell_size_mm=gc_cell_size_mm, cell_gap_mm=gc_cell_gap_mm,
            feed_rate=gc_feed,
            zhuyin_map=zmap,
            zhuyin_chars=zchars,
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
        zhuyin_map=zmap,
        zhuyin_chars=zchars,
    )
    if download:
        headers["Content-Disposition"] = _content_disposition(
            basename, "svg"
        )
    return svg_response(svg, headers=headers, mode="grid")

# ------ file download -----------------------------------------------

@router.get("/api/export/{char}")
def export(
    char: str,
    format: str = Query("svg", pattern="^(svg|gcode|json)$"),
    source: str = Query("auto"),
    hook_policy: str = Query("animation"),
    mode: str = Query("both", pattern="^(outline|track|both)$"),
    show_numbers: bool = Query(False),
    rainbow: bool = Query(False),
    char_size: float = Query(20.0, gt=0.1, le=200.0),
    feed_rate: int = Query(3000, gt=0, le=50000),
    # 5bt (mm audit): 選配實體尺寸——雷切/繪圖軟體以 mm 匯入。
    # 省略時維持既有 300px 行為（Web 預覽相容）。
    size_mm: Optional[float] = Query(None, gt=0.1, le=500.0),
):
    c, _r, _ = _pipeline._load(char, source, hook_policy)

    if format == "svg":
        payload = character_to_svg(
            c, mode=mode, show_numbers=show_numbers, rainbow=rainbow,
            size_mm=size_mm,
        )
        return svg_response(payload, headers={
                "Content-Disposition": _content_disposition(char, "svg"),
            }, mode="single")
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
