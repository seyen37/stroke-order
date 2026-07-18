"""圖藝類模式：文字雲（wordart）、曼陀羅（mandala）、禪繞（zentangle）、塗鴉（doodle）、布章（patch）、印章（stamp）。

W3-R1（架構健檢 Wave 3）：自 server.py create_app() 機械搬遷，行為零變。
共用 helpers 暫由 ``..server`` 匯入（R2 收斂到專屬模組）。
"""
from __future__ import annotations

from pydantic import BaseModel

import io
from fastapi import File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from typing import Optional
from fastapi import APIRouter

from ..char_pipeline import (
    _CNS_MODE_PATTERN,
    _STYLE_PATTERN,
    build_mandala_char_loader,
    make_char_loader,
)
from ..responses import SVG_MEDIA_TYPE, _content_disposition, svg_response

class PatchDecorationSpec(BaseModel):
    svg_content: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    # 12m-7 r30: 圓戳章內框圖用，True = clip 成 inscribed circle
    clip_circle: bool = False


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
    show_border: bool = True


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


router = APIRouter()

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

@router.get("/api/wordart/capacity")
def wordart_capacity(
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
    from ...shapes import Circle, Ellipse, make_shape
    from ...exporters.wordart import capacity, three_band_capacity
    from ...exporters.wordcloud import wordcloud_capacity
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

@router.get("/api/wordart")
def wordart(
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
    from ...shapes import Circle, Ellipse, Polygon, make_shape
    from ...exporters.wordart import (
        Layout, capacity, compute_fill, compute_linear,
        compute_linear_groups, compute_linear_ordered,
        compute_ring, compute_three_band, render_wordart_svg,
        three_band_capacity,
    )
    from ...exporters.wordcloud import (
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

    loader = make_char_loader(
        source, hook_policy, style, cns_outline_mode=cns_outline_mode)

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
    return svg_response(svg, headers=headers)

# ------ 曼陀羅模式 (mandala) — Phase 5b r4 ------------------------
# Case B: 中心 1 字 + 字環 N 字 + 外圍半圓交織 mandala band
# 預設: center "咒" + ring 「臨兵鬥者皆陣列在前」(九字真言, N=9)

@router.get("/api/mandala")
def mandala(
    center_text: str = Query("咒", max_length=10),
    ring_text: str = Query("臨兵鬥者皆陣列在前", max_length=200),
    n_fold: Optional[int] = Query(
        None, ge=2, le=24,
        description="Mandala 對稱軸數；空 → 自動取字環長度"),
    size_mm: float = Query(140.0, ge=20, le=400),
    page_width_mm: float = Query(210.0, ge=50, le=600),
    page_height_mm: float = Query(297.0, ge=50, le=600),
    char_size_center_mm: float = Query(24.0, gt=2, le=80),
    char_size_ring_mm: float = Query(10.0, gt=2, le=40),
    r_ring_ratio: float = Query(0.45, ge=0.1, le=0.9),
    r_band_ratio: float = Query(0.78, ge=0.1, le=0.95),
    overlap_ratio: float = Query(1.25, ge=0.5, le=2.0),
    stroke_width: float = Query(0.6, ge=0.1, le=5.0),
    orientation: str = Query(
        "bottom_to_center",
        pattern="^(bottom_to_center|top_to_center|upright|tangent)$"),
    show_chars: bool = Query(True),
    show_mandala: bool = Query(True),
    show_outline: bool = Query(False, description="畫輔助同心圓 (debug)"),
    protect_chars: bool = Query(
        True, description="字保護 halo 防止 mandala 線切過字"),
    protect_radius_factor: float = Query(
        0.55, ge=0.1, le=1.0,
        description="halo 半徑 / char_size_mm (0.5 內切、0.55 緊貼、0.7 外接)"),
    mandala_style: str = Query(
        "interlocking_arcs",
        pattern="^(interlocking_arcs|lotus_petal|radial_rays)$",
        description="Mandala primitive 樣式"),
    lotus_length_ratio: float = Query(1.25, ge=0.3, le=2.5),
    lotus_width_ratio: float = Query(0.6, ge=0.2, le=1.0),
    rays_length_ratio: float = Query(1.25, ge=0.3, le=2.5),
    # Phase 5b r8: composition_scheme — 字佈局原則
    composition_scheme: str = Query(
        "vesica",
        pattern="^(freeform|vesica|inscribed)$",
        description="字佈局：freeform / vesica（字在圓交集）/ inscribed（字在圓內）"),
    char_spacing: float = Query(
        2.0, ge=0.5, le=20.0,
        description="中心字外緣到字環內緣距離（單位=字身長度），1~N+1 合理"),
    inscribed_padding_factor: float = Query(
        0.7, ge=0.4, le=1.5,
        description="inscribed mode: 圓半徑 / char_size_ring (0.7=外接圓略小)"),
    # Phase 5b r9: 自動縮小字體避免碰觸 mandala 線
    auto_shrink_chars: bool = Query(
        True,
        description="自動縮小字環字大小避免碰觸 mandala 線（vesica/inscribed mode）"),
    shrink_safety_margin: float = Query(
        0.85, ge=0.5, le=1.0,
        description="auto_shrink margin：字 bbox / clearance 比例 (越小越保守)"),
    # Phase 5b r10: 額外裝飾層（純視覺，不跟字環互動）
    extra_layers_json: str = Query(
        "[]", max_length=2000,
        description='JSON array of {style, n_fold, r_ratio, ...} layer dicts'),
    # Phase 5b r15: 中心類型 (Case A/B/C)
    center_type: str = Query(
        "char", pattern="^(char|icon|empty)$",
        description="中心類型：char=字（B 默認）/ icon=小 mandala (C) / empty=空 (A)"),
    center_icon_style: str = Query(
        "lotus_petal",
        pattern=("^(interlocking_arcs|lotus_petal|radial_rays|dots|"
                 "triangles|wave|zigzag|spiral|squares|hearts|"
                 "teardrops|leaves|clouds|crosses|stars|eyes|lattice)$")),
    center_icon_n: int = Query(8, ge=2, le=24),
    center_icon_size_mm: float = Query(12.0, ge=2.0, le=80.0),
    # Phase 5b r18: 下載格式
    format: str = Query(
        "svg", pattern="^(svg|png|png_transparent|pdf|gcode)$",
        description="輸出格式：svg / png / png_transparent / pdf / gcode（機器軌跡）"),
    png_size_px: int = Query(
        2400, ge=256, le=8192,
        description="PNG 解析度（像素）。1024=中、2400=大、4096=超大"),
    # Phase 5b r19: G-code 參數
    gcode_feed_rate: float = Query(1000.0, ge=10, le=10000),
    gcode_pen_up_z: float = Query(2.0, ge=0, le=20),
    gcode_pen_down_z: float = Query(-1.0, ge=-20, le=0),
    gcode_flip_y: bool = Query(True),
    # Phase 5b r26: 線條顏色（hex #rrggbb；G-code 按色分組以利寫字機換筆）
    mandala_line_color: str = Query(
        "#000000", pattern=r"^#[0-9a-fA-F]{6}$",
        description="主 mandala 線條 fill/stroke 顏色 (#rrggbb)"),
    char_line_color: str = Query(
        "#000000", pattern=r"^#[0-9a-fA-F]{6}$",
        description="中心字 + 字環的字筆畫 fill/stroke 顏色 (#rrggbb)"),
    source: str = Query("auto"),
    hook_policy: str = Query("animation"),
    style: str = Query("kaishu", pattern=_STYLE_PATTERN),
    cns_outline_mode: str = Query("skip", pattern=_CNS_MODE_PATTERN),
    download: bool = Query(False),
):
    import json
    from ...exporters.mandala import render_mandala_svg

    # 5b r10: parse extra_layers_json (容錯 — 壞 JSON 視為空 list)
    try:
        extra_layers_parsed = json.loads(extra_layers_json or "[]")
        if not isinstance(extra_layers_parsed, list):
            extra_layers_parsed = []
    except (ValueError, TypeError):
        extra_layers_parsed = []

    # r28c: 用共用 builder（跟 gallery upload thumbnail 同 pipeline）
    loader = build_mandala_char_loader(
        style=style, source=source,
        hook_policy=hook_policy, cns_outline_mode=cns_outline_mode,
    )

    # 5b r18: 透明 PNG 不畫白色背景（其餘格式維持 white bg）
    include_bg = (format != "png_transparent")
    svg, info = render_mandala_svg(
        center_text, ring_text, loader,
        size_mm=size_mm,
        page_width_mm=page_width_mm,
        page_height_mm=page_height_mm,
        n_fold=n_fold,
        show_chars=show_chars,
        show_mandala=show_mandala,
        char_size_center_mm=char_size_center_mm,
        char_size_ring_mm=char_size_ring_mm,
        r_ring_ratio=r_ring_ratio,
        r_band_ratio=r_band_ratio,
        overlap_ratio=overlap_ratio,
        stroke_width=stroke_width,
        orient=orientation,  # type: ignore[arg-type]
        show_outline=show_outline,
        protect_chars=protect_chars,
        protect_radius_factor=protect_radius_factor,
        mandala_style=mandala_style,
        lotus_length_ratio=lotus_length_ratio,
        lotus_width_ratio=lotus_width_ratio,
        rays_length_ratio=rays_length_ratio,
        composition_scheme=composition_scheme,
        char_spacing=char_spacing,
        inscribed_padding_factor=inscribed_padding_factor,
        auto_shrink_chars=auto_shrink_chars,
        shrink_safety_margin=shrink_safety_margin,
        extra_layers=extra_layers_parsed,
        center_type=center_type,
        center_icon_style=center_icon_style,
        center_icon_n=center_icon_n,
        center_icon_size_mm=center_icon_size_mm,
        include_background=include_bg,
        mandala_line_color=mandala_line_color,
        char_line_color=char_line_color,
    )
    headers = {
        "X-Mandala-Placed": str(info["placed_count"]),
        "X-Mandala-Missing": str(info["missing_count"]),
        "X-Mandala-N-Fold": str(info["n_fold"]),
        "X-Mandala-Ring-Count": str(info["ring_chars_count"]),
        "X-Mandala-Scheme": str(info.get("composition_scheme", "")),
        "X-Mandala-R-Ring-Mm": str(info.get("r_ring_mm", "")),
        "X-Mandala-R-Band-Mm": str(info.get("r_band_mm", "")),
        "X-Mandala-Char-Size-Original-Mm": str(
            info.get("char_size_ring_original_mm", "")),
        "X-Mandala-Char-Size-Effective-Mm": str(
            info.get("char_size_ring_effective_mm", "")),
        "X-Mandala-Char-Shrunk": "1" if info.get("char_shrunk") else "0",
        "X-Mandala-Extra-Layers": str(info.get("extra_layers_count", 0)),
        "X-Mandala-Center-Type": str(info.get("center_type", "char")),
    }
    # Phase 5b r18/r19: 依 format 轉換並回傳對應 content-type
    if format == "png" or format == "png_transparent":
        import cairosvg
        png_bytes = cairosvg.svg2png(
            bytestring=svg.encode("utf-8"),
            output_width=png_size_px,
            output_height=png_size_px,
        )
        ext, mime = "png", "image/png"
        content = png_bytes
    elif format == "pdf":
        import cairosvg
        pdf_bytes = cairosvg.svg2pdf(bytestring=svg.encode("utf-8"))
        ext, mime = "pdf", "application/pdf"
        content = pdf_bytes
    elif format == "gcode":
        from ...exporters.mandala import render_mandala_gcode
        gcode_text = render_mandala_gcode(
            svg,
            feed_rate_mm_per_min=gcode_feed_rate,
            pen_up_z=gcode_pen_up_z,
            pen_down_z=gcode_pen_down_z,
            flip_y=gcode_flip_y,
        )
        ext, mime = "gcode", "text/plain"
        content = gcode_text
    else:
        ext, mime = "svg", SVG_MEDIA_TYPE
        content = svg

    if download:
        base = f"mandala-{info['n_fold']}"
        if format == "png_transparent":
            base += "-transparent"
        headers["Content-Disposition"] = _content_disposition(base, ext)
    return Response(content=content, media_type=mime, headers=headers)

# ------ 曼陀羅 preset 主題（5b r12） ----------------------------
@router.get("/api/mandala/presets")
def mandala_presets():
    """List all mandala presets。前端用 dropdown change 套設定到 inputs。"""
    from ...exporters.mandala import list_mandala_presets
    return {"presets": list_mandala_presets()}

# ------ 禪繞字模式 (zentangle, phase 6z-1) ------------------------
# Outline 抽取 — 給 char 回 polyline contours。前端 canvas mapper
# 把 EM-scaled Y-down coords 轉成 tile-local。
# Source 預設 moe_kaishu (per Q1 user decision)；其他源透過下拉選
# 暴露但不 silent default (D-C 強紀律弱預設)。

@router.get("/api/zentangle/outline")
def zentangle_outline(
    char: str = Query(..., min_length=1, max_length=1, description="single CJK char"),
    source: str = Query("moe_kaishu", description="font source key"),
    samples_per_curve: int = Query(8, ge=1, le=64, description="Bezier sampling density"),
):
    """Return polyline contours for a single character.

    Returns
    -------
    ``{contours: [[[x, y], ...], ...], char, source, samples_per_curve, em_size}``

    ``contours`` is a list of closed polylines, each a list of
    ``[x, y]`` floats in EM-scaled Y-down coordinates. The frontend
    maps them into tile-local space using ``em_size``.
    """
    from ...exporters import zentangle as zt
    from ...ir import EM_SIZE
    from ...sources.g0v import CharacterNotFound
    try:
        polylines = zt.extract_outline_polylines(
            char, source=source, samples_per_curve=samples_per_curve
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e
    except CharacterNotFound as e:
        raise HTTPException(404, detail=str(e)) from e
    except RuntimeError as e:
        # font file missing on disk → 503 service-unavailable so the
        # client can degrade gracefully (try another source / show
        # install hint) rather than treat as a permanent 4xx error.
        raise HTTPException(503, detail=str(e)) from e
    # Tuple → list for JSON serialisation.
    contours = [[[x, y] for (x, y) in poly] for poly in polylines]
    return {
        "contours": contours,
        "char": char,
        "source": source,
        "samples_per_curve": samples_per_curve,
        "em_size": EM_SIZE,
    }

@router.get("/api/zentangle/sources")
def zentangle_sources():
    """List available outline sources for the UI dropdown.

    Each entry: ``{key, label, ready}``. ``ready=False`` means the
    font file is missing — the UI should grey out that option and
    show an install tooltip rather than letting the user 503 on it.
    """
    from ...exporters import zentangle as zt
    return {"sources": zt.list_sources()}

# ------ 塗鴉模式 (doodle) ------------------------------------------


@router.post("/api/doodle")
def doodle(
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
    # Phase 5ch: 取樣方式 — contour（輪廓向量，預設）/ scanline（掃描線）
    vector_style: str = Form("contour"),
):
    """Upload an image → return doodle SVG."""
    if vector_style not in ("contour", "scanline"):
        raise HTTPException(
            422, detail="vector_style must be 'contour' or 'scanline'")
    import json
    from PIL import Image as PILImage
    from ...exporters.doodle import auto_crop_image, render_doodle_svg
    from ...layouts import Annotation

    # Read uploaded image
    body = image.file.read()
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
        style=vector_style,
    )
    headers: dict[str, str] = {}
    if download:
        headers["Content-Disposition"] = _content_disposition(
            "doodle", "svg"
        )
    return svg_response(svg, headers=headers)


# ------ 布章 (patch) — Phase 5ax -----------------------------------

_PATCH_PRESET_PATTERN = (
    "^(rectangle|name_tag|oval|circle|shield|hexagon|"
    "arch_top|arch_bottom|banner_left|banner_right)$"
)
_PATCH_TEXTPOS_PATTERN = "^(center|top|bottom|on_arc)$"
# 5bq: "dxf" — layered DXF R12 (CUT/ENGRAVE/WRITE) for laser software
_PATCH_FORMAT_PATTERN = "^(svg|gcode_cut|gcode_write|dxf)$"

@router.get("/api/patch/capacity")
def patch_capacity_endpoint(
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
    from ...exporters.patch import patch_capacity
    return patch_capacity(
        preset=preset,                                    # type: ignore[arg-type]
        patch_width_mm=patch_width_mm,
        patch_height_mm=patch_height_mm,
        char_size_mm=char_size_mm,
        tile_rows=tile_rows, tile_cols=tile_cols,
        tile_gap_mm=tile_gap_mm,
        page_width_mm=page_width_mm, page_height_mm=page_height_mm,
    )

@router.post("/api/patch")
def patch_post(req: PatchPostRequest):
    """POST variant — needed because GET URL length caps at ~2KB
    and a single base64-embedded SVG decoration easily blows past."""
    from ...exporters.patch import (
        render_patch_svg, render_patch_gcode_cut,
        render_patch_gcode_write, render_patch_dxf, SvgDecoration,
    )
    if req.format not in ("svg", "gcode_cut", "gcode_write", "dxf"):
        raise HTTPException(422, detail=f"unknown format {req.format!r}")

    loader = make_char_loader(req.source, req.hook_policy, req.style)

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
        auto_size=req.auto_size,                          # 5de
    )

    if req.format == "svg":
        svg = render_patch_svg(
            **common, decorations=decorations,
            page_width_mm=req.page_width_mm,
            page_height_mm=req.page_height_mm,
        )
        return svg_response(svg, headers={"Content-Disposition":
                                 _content_disposition("patch", "svg")})
    if req.format == "dxf":
        # 5bq: layered DXF R12 — CUT/ENGRAVE/WRITE, one file.
        # Decorations are SVG fragments and not representable (same
        # limitation as G-code).
        dxf = render_patch_dxf(**common)
        return Response(content=dxf, media_type="image/vnd.dxf",
                        headers={"Content-Disposition":
                                 _content_disposition("patch_layers", "dxf")})
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

@router.get("/api/patch")
def patch_get(
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
    auto_size: bool = Query(False, description="5de：auto 字級"),
):
    """GET variant — no decorations (use POST for those)."""
    req = PatchPostRequest(
        auto_size=auto_size,
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
    return patch_post(req)

# ------ 印章 (stamp) — Phase 5ay --------------------------------------

_STAMP_PRESET_PATTERN = (
    "^(square_name|round_name|square_official|round|oval|"
    "tax_invoice|rectangle_title)$"
)
# 5bs: "dxf" — layered DXF R12（CUT=邊框 / ENGRAVE=陰刻輪廓或陽刻 hatch）
_STAMP_FORMAT_PATTERN = "^(svg|gcode|pdf|dxf)$"
_STAMP_ENGRAVE_PATTERN = "^(concave|convex)$"
_STAMP_LAYOUT5_PATTERN = "^(3plus2|2plus3)$"
_STAMP_LAYOUT2_PATTERN = "^(horizontal|vertical)$"
# 12l: short_col 名稱集合（3-col 用 right/middle/left，4-col 改 right/
# mid-right/mid-left/left；統一驗證合法名單即可，cols 對應在 stamp.py
# 內 _short_col_name_to_idx 過濾，無效名跳過不報 422）。
_STAMP_OFF_SHORTCOL_NAMES = (
    "right", "middle", "left", "mid-right", "mid-left",
)
_STAMP_OFF_SHORTCOL_PATTERN = "^(right|middle|left|mid-right|mid-left)$"

@router.get("/api/stamp/capacity")
def stamp_capacity_endpoint(
    preset: str = Query("square_name", pattern=_STAMP_PRESET_PATTERN),
    stamp_width_mm: float = Query(25.0, ge=5, le=200),
    stamp_height_mm: float = Query(25.0, ge=5, le=200),
    char_size_mm: float = Query(10.0, gt=1, le=100),
    border_padding_mm: float = Query(0.8, ge=0, le=20),
    double_border: bool = Query(False),
):
    from ...exporters.stamp import stamp_capacity
    return stamp_capacity(
        preset=preset,                                    # type: ignore[arg-type]
        stamp_width_mm=stamp_width_mm,
        stamp_height_mm=stamp_height_mm,
        char_size_mm=char_size_mm,
        border_padding_mm=border_padding_mm,
        double_border=double_border,
    )

@router.post("/api/stamp")
def stamp_post(req: StampPostRequest):
    from ...exporters.stamp import (
        render_stamp_svg, render_stamp_gcode, render_stamp_dxf,
    )
    from ...exporters.patch import SvgDecoration
    if req.format not in ("svg", "gcode", "pdf", "dxf"):
        raise HTTPException(422, detail=f"unknown format {req.format!r}")

    # stamp 是 outline-only 渲染（_char_cut_paths 只看 stroke.outline，
    # 跳過 stroke.raw_track）。預設 *_outline_mode="skeleton" 會把 outline
    # 轉成 centerline polylines → stamp 渲染時跳過 → 預覽空白。
    # 用 "skip" 保留原 outline 才能被 stamp 雕刻 path 渲染（對應 patch
    # endpoint 的設計）。
    loader = make_char_loader(
        req.source, req.hook_policy, req.style,
        seal_outline_mode="skip", lishu_outline_mode="skip")

    decorations = [
        SvgDecoration(svg_content=d.svg_content, x_mm=d.x_mm, y_mm=d.y_mm,
                      w_mm=d.w_mm, h_mm=d.h_mm,
                      clip_circle=bool(getattr(d, "clip_circle", False)))
        for d in req.decorations
    ]

    # 12c: validate engrave_mode（POST body 沒走 Query pattern 驗證）
    if req.engrave_mode not in ("concave", "convex"):
        raise HTTPException(
            422, detail=f"unknown engrave_mode {req.engrave_mode!r}")
    # 12e: validate layout_5char
    if req.layout_5char not in ("3plus2", "2plus3"):
        raise HTTPException(
            422, detail=f"unknown layout_5char {req.layout_5char!r}")
    # 12h: validate layout_2char
    if req.layout_2char not in ("horizontal", "vertical"):
        raise HTTPException(
            422, detail=f"unknown layout_2char {req.layout_2char!r}")
    # 12l: validate layout_official_short_col list (or single str
    # backward compat). Empty / None ⇒ stamp.py defaults to ["right"].
    raw_short = req.layout_official_short_col
    if isinstance(raw_short, str):
        short_cols_list = [raw_short] if raw_short else []
    elif isinstance(raw_short, (list, tuple)):
        short_cols_list = list(raw_short)
    else:
        short_cols_list = []
    for nm in short_cols_list:
        if nm not in _STAMP_OFF_SHORTCOL_NAMES:
            raise HTTPException(
                422, detail=f"unknown layout_official_short_col {nm!r}")

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
        engrave_mode=req.engrave_mode,              # type: ignore[arg-type]
        layout_5char=req.layout_5char,
        layout_2char=req.layout_2char,
        layout_official_short_col=short_cols_list,
        char_offsets=[tuple(o[:2]) for o in req.char_offsets if len(o) >= 2],
        # 12m-1: oval structured fields (其他 preset 一律忽略，無 side effect)
        oval_arc_top=req.oval_arc_top,
        oval_arc_bottom=req.oval_arc_bottom,
        oval_body_lines=list(req.oval_body_lines or []),
        oval_body_bold=list(req.oval_body_bold or []),
        oval_decoration=req.oval_decoration or "plum",
        oval_sawtooth=bool(req.oval_sawtooth),
        # 12m-7: tax_invoice 上方標題 + 縣市 + 縣市位置
        oval_top_title=req.oval_top_title or "",
        oval_location=req.oval_location or "",
        oval_location_position=req.oval_location_position or "bottom",
        # 12m-7 r26: 圓戳章單圓周模式
        round_continuous_arc=bool(req.round_continuous_arc),
        # 12m-7 r31: body slot overrides
        body_slot_overrides=dict(req.body_slot_overrides or {}),
        # 12m-7 r39: 職名章 2-column 欄位
        rect_left_line1=req.rect_left_line1 or "",
        rect_left_line2=req.rect_left_line2 or "",
        rect_right=req.rect_right or "",
        rect_left_2rows=bool(req.rect_left_2rows),
    )

    if req.format == "svg":
        svg = render_stamp_svg(**common)
        return svg_response(svg, headers={"Content-Disposition":
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
    if req.format == "dxf":
        # 5bs: CUT=邊框、ENGRAVE=陰刻輪廓或陽刻 hatch 掃描段
        dxf = render_stamp_dxf(**common, line_pitch_mm=req.line_pitch_mm)
        return Response(content=dxf, media_type="image/vnd.dxf",
                        headers={"Content-Disposition":
                                 _content_disposition("stamp_layers", "dxf")})
    gc = render_stamp_gcode(
        **common, feed=req.feed, laser_power=req.laser_power,
        line_pitch_mm=req.line_pitch_mm,
    )
    return Response(content=gc, media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition":
                             _content_disposition("stamp", "gcode")})

@router.get("/api/stamp")
def stamp_get(
    text: str = Query("", max_length=200),
    preset: str = Query("square_name", pattern=_STAMP_PRESET_PATTERN),
    stamp_width_mm: float = Query(25.0, ge=5, le=200),
    stamp_height_mm: float = Query(25.0, ge=5, le=200),
    char_size_mm: float = Query(10.0, gt=1, le=100),
    show_border: bool = Query(True),
    double_border: bool = Query(False),
    border_padding_mm: float = Query(0.8, ge=0, le=20),
    style: str = Query("kaishu", pattern=_STYLE_PATTERN),
    source: str = Query("auto"),
    hook_policy: str = Query("animation"),
    feed: float = Query(1500.0, gt=0, le=10000),
    laser_power: int = Query(255, ge=1, le=1000),
    format: str = Query("svg", pattern=_STAMP_FORMAT_PATTERN),
    engrave_mode: str = Query("concave", pattern=_STAMP_ENGRAVE_PATTERN),
    line_pitch_mm: float = Query(0.1, gt=0, le=2.0),
    layout_5char: str = Query("2plus3", pattern=_STAMP_LAYOUT5_PATTERN),
    layout_2char: str = Query("horizontal", pattern=_STAMP_LAYOUT2_PATTERN),
    # 12l: GET 用逗號分隔字串（query string 沒原生 list），預設 "right"
    # 例：?layout_official_short_col=right,mid-right
    layout_official_short_col: str = Query("right"),
    # 12m-1: oval structured fields. body_lines 用 `||` 分隔（單 `|` 對
    # URL 是合法字元，但 `||` 在自然文本極罕見、區隔效果好）。例：
    # ?oval_body_lines=收發章||電話:02-2234567
    oval_arc_top: str = Query("", max_length=80),
    oval_arc_bottom: str = Query("", max_length=80),
    oval_body_lines: str = Query("", max_length=240),
):
    # 12l: parse + validate comma-separated short col names
    short_raw = [s.strip() for s in layout_official_short_col.split(",")
                 if s.strip()]
    if not short_raw:
        short_raw = ["right"]
    for nm in short_raw:
        if nm not in _STAMP_OFF_SHORTCOL_NAMES:
            raise HTTPException(
                422, detail=f"unknown layout_official_short_col {nm!r}")
    req = StampPostRequest(
        text=text, preset=preset,
        stamp_width_mm=stamp_width_mm, stamp_height_mm=stamp_height_mm,
        char_size_mm=char_size_mm,
        show_border=show_border, double_border=double_border,
        border_padding_mm=border_padding_mm,
        style=style, source=source, hook_policy=hook_policy,
        feed=feed, laser_power=laser_power, format=format,
        engrave_mode=engrave_mode, line_pitch_mm=line_pitch_mm,
        layout_5char=layout_5char,
        layout_2char=layout_2char,
        layout_official_short_col=short_raw,
        oval_arc_top=oval_arc_top,
        oval_arc_bottom=oval_arc_bottom,
        oval_body_lines=[
            ln for ln in oval_body_lines.split("||") if ln
        ] if oval_body_lines else [],
    )
    return stamp_post(req)
