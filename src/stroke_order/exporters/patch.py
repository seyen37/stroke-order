"""
Patch / 布章 mode (Phase 5ax).

Single-purpose exporter for cutting-machine and writing-plotter
workflows. Unlike the wordart family (11 layouts × 18 shapes × many
knobs), the patch mode picks ONE preset patch shape and lays out the
text in one of four trivial positions (center / top / bottom /
on_arc). The output is a **two-layer SVG** — one ``<g>`` for cut
paths (patch outline + char outlines + decorations) and another for
write paths (char centerlines for the writing plotter).

Why a separate mode (not just another wordart sublayout)
--------------------------------------------------------
- Patch users want **explicit cut vs write separation** so their
  cutting / sewing software can route each layer to the right tool.
- They typically tile multiple identical patches on one A4 sheet to
  save material; wordart has no concept of tile.
- They don't need orientation / align / direction / auto_cycle /
  auto_fit — those parameters were designed for posters, not patches.

Two-layer SVG schema
--------------------
::

    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 W H">
      <g id="patch-cut" stroke="#000" stroke-width="0.3" fill="none">
        <!-- per tile: patch outline → char outlines → decoration paths -->
      </g>
      <g id="patch-write" stroke="#c33" stroke-width="0.3" fill="none">
        <!-- per tile: char raw_track polylines for the writing plotter -->
      </g>
    </svg>

Cutting-machine vendors typically import all paths in a colour-keyed
file; "select all black, set as cut, all red, set as draw" is a
universal one-click workflow.

G-code
------
:func:`render_patch_gcode_cut` and :func:`render_patch_gcode_write`
emit machine code for the two layers separately. Cut and write
typically need different feed rates and pen-up/down settings, so
mixing them in one file would force the operator to fiddle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

import math

from ..ir import Character, EM_SIZE
from ..shapes import Circle, Ellipse, Polygon, make_shape
from .svg import _outline_path_d


def _ensure_polygon(shape, sides: int = 64) -> Polygon:
    """Sample a Circle / Ellipse into a Polygon so the rest of the
    pipeline can treat every shape uniformly. Polygon passes through."""
    if isinstance(shape, Polygon):
        return shape
    verts: list[tuple[float, float]] = []
    if isinstance(shape, Circle):
        cx, cy, r = shape.cx_mm, shape.cy_mm, shape.radius_mm
        for i in range(sides):
            t = (i / sides) * 2 * math.pi
            verts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    elif isinstance(shape, Ellipse):
        cx, cy = shape.cx_mm, shape.cy_mm
        rx, ry = shape.rx_mm, shape.ry_mm
        for i in range(sides):
            t = (i / sides) * 2 * math.pi
            verts.append((cx + rx * math.cos(t), cy + ry * math.sin(t)))
    else:
        raise TypeError(f"unsupported shape type: {type(shape).__name__}")
    return Polygon(vertices=verts)


# Patch presets — a closed taxonomy. The 6 shared with wordart map to
# their make_shape kinds; the 4 patch-only ones are the new shapes
# added in 5ax (arch_strip / banner).
PatchPreset = Literal[
    "rectangle",     # plain rectangle  (size=w, aspect → h)
    "name_tag",      # rounded rectangle (uses 5ah `rounded`)
    "oval",          # ellipse (5ah `ellipse`-ish)
    "circle",        # circle
    "shield",        # 5-vertex shield (uses 5ah `pentagon`-ish)
    "hexagon",       # 6-vertex
    "arch_top",      # 5ax arch curving up
    "arch_bottom",   # 5ax arch curving down
    "banner_left",   # 5ax flag with notch on left
    "banner_right",  # 5ax flag with notch on right
]


TextPosition = Literal["center", "top", "bottom", "on_arc"]


@dataclass
class SvgDecoration:
    """One decorative SVG snippet to drop on top of a patch.

    ``svg_content`` is a fragment (or full <svg>) of paths to embed.
    Coordinates are interpreted in its source viewBox; we transform-
    fit it into the (x_mm, y_mm, w_mm, h_mm) box on the patch.

    12m-7 r30: ``clip_circle`` 為 True 時將 deco 內容裁切成正圓形
    （inscribed circle of bbox），用於圓戳章內框圖視覺上整體呈正圓。
    """
    svg_content: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    clip_circle: bool = False


# Loader signature shared with the wordart pipeline.
CharLoader = Callable[[str], Optional[Character]]


# ---------------------------------------------------------------------------
# Internal: build one patch (cut paths + write polylines) at origin (0, 0)
# ---------------------------------------------------------------------------


def _build_patch_shape(
    preset: PatchPreset,
    width_mm: float,
    height_mm: float,
):
    """Make the patch outline polygon, centred on (width/2, height/2)."""
    cx, cy = width_mm / 2.0, height_mm / 2.0
    # Map preset → make_shape kind + aspect handling.
    aspect = height_mm / width_mm if width_mm > 0 else 1.0
    if preset == "rectangle":
        return Polygon(vertices=[
            (0, 0), (width_mm, 0), (width_mm, height_mm), (0, height_mm),
        ])
    if preset == "name_tag":
        return make_shape("rounded", cx, cy, width_mm, aspect=aspect,
                          rounded_corner_ratio=0.18)
    if preset == "oval":
        return make_shape("ellipse", cx, cy, width_mm, aspect=aspect)
    if preset == "circle":
        # Circle ignores aspect; use the smaller dimension as diameter.
        diam = min(width_mm, height_mm)
        return make_shape("circle", cx, cy, diam)
    if preset == "shield":
        # 5-vertex pentagon-ish; rotate so flat edge is on top.
        return make_shape("pentagon", cx, cy, min(width_mm, height_mm))
    if preset == "hexagon":
        return make_shape("hexagon", cx, cy, min(width_mm, height_mm))
    if preset == "arch_top":
        return make_shape("arch_top", cx, cy, width_mm, aspect=aspect,
                          arch_curvature=0.5)
    if preset == "arch_bottom":
        return make_shape("arch_bottom", cx, cy, width_mm, aspect=aspect,
                          arch_curvature=0.5)
    if preset == "banner_left":
        return make_shape("banner_left", cx, cy, width_mm, aspect=aspect,
                          banner_notch_depth=0.25)
    if preset == "banner_right":
        return make_shape("banner_right", cx, cy, width_mm, aspect=aspect,
                          banner_notch_depth=0.25)
    raise ValueError(f"unknown patch preset {preset!r}")


def _polygon_to_svg_path(poly: Polygon) -> str:
    """Closed-path d-string for a polygon."""
    if not poly.vertices:
        return ""
    head = f"M {poly.vertices[0][0]:.3f} {poly.vertices[0][1]:.3f}"
    tail = " ".join(f"L {x:.3f} {y:.3f}" for x, y in poly.vertices[1:])
    return f"{head} {tail} Z"


#: 5br: minimum centre-to-centre spacing as a multiple of char size —
#: 1.0 would be edge-to-edge; 1.08 leaves a small visual gap.
_CHAR_GAP_RATIO = 1.08


def _fit_char_size(n_chars: int, patch_w_mm: float,
                   char_size_mm: float) -> float:
    """5br: largest char size (≤ requested) at which ``n_chars`` glyphs
    plus gaps and edge margins fit the patch width.

    Fixes the overlap bug where e.g. 4 × 22 mm chars were squeezed into
    an 80 mm patch (centre spacing 12 mm < glyph width 22 mm).

    5dd note: this is only the **bbox upper bound**——造型感知的最終
    大小由 :func:`_fit_row_to_shape` 依文字列高度的水平弦決定。
    """
    if n_chars <= 0:
        return char_size_mm
    max_eff = patch_w_mm / (n_chars * _CHAR_GAP_RATIO + 0.3)
    return min(char_size_mm, max_eff)


#: 5dd: 字級下限（mm）——弦再窄也不縮到看不見。
_MIN_CHAR_MM = 3.0


def _widest_chord(poly: Polygon, y: float):
    """水平線 ``y`` 與造型的最寬弦 ``(L, R)``；無交點回 ``None``。"""
    from .engrave import scanline_intersections
    verts = list(poly.vertices)
    if not verts:
        return None
    if verts[0] != verts[-1]:
        verts = verts + [verts[0]]
    xs = scanline_intersections([verts], y)
    best = None
    for i in range(0, len(xs) - 1, 2):
        if best is None or xs[i + 1] - xs[i] > best[1] - best[0]:
            best = (xs[i], xs[i + 1])
    return best


def _usable_interval(poly: Polygon, cy: float, size_mm: float,
                     margin_mm: float):
    """字列在 ``cy``、字高 ``size_mm`` 時的可用水平區間。

    取字框上/中/下三條掃描線最寬弦的**交集**再內縮 margin——
    對圓/盾/六角/拱/旗等非矩形造型是保守正確的（凸形精確、
    凹形取安全側）。回傳 ``(L, R)`` 或 ``None``（放不下）。
    """
    lo: Optional[float] = None
    hi: Optional[float] = None
    for y in (cy - size_mm / 2.0, cy, cy + size_mm / 2.0):
        c = _widest_chord(poly, y)
        if c is None:
            return None
        lo = c[0] if lo is None else max(lo, c[0])
        hi = c[1] if hi is None else min(hi, c[1])
    lo += margin_mm
    hi -= margin_mm
    return (lo, hi) if hi > lo else None


def _fit_row_to_shape(poly: Polygon, cy: float, n_chars: int,
                      size0_mm: float):
    """5dd 造型感知適配核心：回傳 ``(size, cy, L, R)``（L/R＝原始弦）。

    使用者實測：預設 4 字下只有矩形/圓角/橢圓包得住，其餘造型
    （圓/盾/六角/拱/旗）溢出——因為舊邏輯只看 bbox 寬。本函式
    在文字列的實際高度取造型水平弦：
    1. 可行性判定用「弦寬 − 2×硬邊距 ≥ N 字最小列寬」；不夠則
       字大小逐步縮（×0.93）
    2. 縮到下限仍放不下 → **位置同步向造型中心收斂**、字級
       回復重試（top/bottom 在窄造型上自動向中線靠）
    3. 回傳原始弦區間——列心對齊弦中點（旗形缺口/盾形斜邊等
       不對稱造型自動偏移）；鋪排慣例由呼叫端沿用 5br 舊公式
       （usable＝弦寬−2×字寬），矩形滿弦時與舊版位置全等零回歸
    """
    bbox = poly.bbox()
    h_mid = (bbox[1] + bbox[3]) / 2.0
    s = max(size0_mm, _MIN_CHAR_MM)
    for _ in range(80):
        hard = max(0.8, s * 0.08)             # 邊界淨空（縫線/切割位）
        iv = _usable_interval(poly, cy, s, 0.0)
        if iv is not None:
            need = s + s * _CHAR_GAP_RATIO * (n_chars - 1)
            if (iv[1] - iv[0]) - 2.0 * hard >= need:
                return s, cy, iv[0], iv[1]
        if s > _MIN_CHAR_MM:
            s = max(_MIN_CHAR_MM, s * 0.93)
        elif abs(cy - h_mid) > 0.5:
            cy = cy + (h_mid - cy) * 0.3      # 位置同步調整
            s = max(size0_mm, _MIN_CHAR_MM)   # 回復字級重試
        else:
            break
    # 保底：中線、最小字級、弦（或 bbox）
    iv = _usable_interval(poly, h_mid, _MIN_CHAR_MM, 0.0)
    if iv is None:
        iv = (bbox[0] + 0.5, bbox[2] - 0.5)
    return _MIN_CHAR_MM, h_mid, iv[0], iv[1]


def _layout_text_positions(
    n_chars: int,
    preset: PatchPreset,
    position: TextPosition,
    patch_w_mm: float,
    patch_h_mm: float,
    char_size_mm: float,
    poly: Polygon,
    auto_size: bool = False,
) -> tuple[list[tuple[float, float, float]], float]:
    """Return ``([(cx_mm, cy_mm, rotation_deg), ...], eff_char_size_mm)``.

    - ``center`` / ``top`` / ``bottom`` — straight horizontal row.
    - ``on_arc`` — for arch_top / arch_bottom presets, distribute along
      the inner arc curvature; for any other preset falls through to
      ``center``.

    5br: ``eff_char_size_mm`` is the auto-fitted glyph size (see
    :func:`_fit_char_size`); centre spacing is clamped to at least
    ``eff × _CHAR_GAP_RATIO`` so glyphs can never overlap. Callers must
    draw glyphs at the returned effective size.
    """
    if n_chars <= 0:
        return [], char_size_mm
    if position == "on_arc" and preset not in ("arch_top", "arch_bottom"):
        position = "center"
    eff = _fit_char_size(n_chars, patch_w_mm, char_size_mm)
    if auto_size:
        # 5de：auto 字級——起點改「造型 bbox 對角尺度」，由
        # _fit_row_to_shape 從大往下收斂到最大可容字級：字少自動
        # 放大（1 字可近乎填滿造型高）、字多自動縮小。使用者的
        # char_size_mm 在 auto 模式不設上限（僅非 auto 生效）。
        bb = poly.bbox()
        eff = max(bb[2] - bb[0], bb[3] - bb[1], _MIN_CHAR_MM)

    if position == "on_arc":
        # 5dd：拱形弦位的可用寬度也改走造型感知（舊版用 bbox 全寬，
        # 拱帶在 offset 高度的實際弦長更短）。旋轉扇形邏輯維持。
        bbox = poly.bbox()
        bbox_h = bbox[3] - bbox[1]
        offset = bbox_h * 0.25 * (-1 if preset == "arch_top" else 1)
        cy0 = patch_h_mm / 2.0 + offset
        s, cy0, lo, hi = _fit_row_to_shape(poly, cy0, n_chars, eff)
        if n_chars == 1:
            return [((lo + hi) / 2.0, cy0, 0.0)], s
        usable = max((hi - lo) - 2.0 * s, s)      # 5br 慣例（弦版）
        spacing = max(usable / (n_chars - 1), s * _CHAR_GAP_RATIO)
        x0 = (lo + hi) / 2.0 - spacing * (n_chars - 1) / 2.0
        slots = []
        for i in range(n_chars):
            t = i / (n_chars - 1)
            alpha_deg = (t - 0.5) * 25.0   # gentle 25° total span
            if preset == "arch_bottom":
                alpha_deg = -alpha_deg
            slots.append((x0 + i * spacing, cy0, alpha_deg))
        return slots, s

    # Straight horizontal row.
    cy_map = {
        "center": patch_h_mm / 2.0,
        "top":    patch_h_mm * 0.30,
        "bottom": patch_h_mm * 0.70,
    }
    cy = cy_map.get(position, patch_h_mm / 2.0)
    # 5dd：造型感知——字大小/間距/列心全部跟著「文字列高度的造型
    # 水平弦」走；弦太窄時位置自動向中心收斂（見 _fit_row_to_shape）。
    s, cy, lo, hi = _fit_row_to_shape(poly, cy, n_chars, eff)
    if n_chars == 1:
        return [((lo + hi) / 2.0, cy, 0.0)], s
    # 5br 鋪排慣例的弦版：usable＝弦寬−2×字寬（矩形滿弦時與舊
    # margin 公式全等）；間距夾最小字距後對弦中點置中。
    usable = max((hi - lo) - 2.0 * s, s)
    spacing = max(usable / (n_chars - 1), s * _CHAR_GAP_RATIO)
    x0 = (lo + hi) / 2.0 - spacing * (n_chars - 1) / 2.0
    return [(x0 + i * spacing, cy, 0.0) for i in range(n_chars)], s


def _char_cut_paths(c: Character, x_mm: float, y_mm: float,
                    size_mm: float, rotation_deg: float = 0.0,
                    stroke_width_mm: Optional[float] = None) -> str:
    """Embed a Character's outlines as <path> elements at (x, y).

    Uniform scale (width = height = size_mm). For non-uniform stretch
    (e.g. stamp 3-字 traditional layout where surname is elongated),
    use :func:`_char_cut_paths_stretched`.

    Phase 5cc: ``stroke_width_mm`` — 給「描邊型」消費者（布章 cut 線）
    用的線寬補償。外層群組的 stroke-width 會被這裡的 scale(1/93~1/118)
    一起縮小成髮絲線（cairosvg 光柵化直接隱形；瀏覽器靠反鋸齒勉強可
    見）。給值時在內層 g 以 EM 座標補回 stroke-width = w/scale，讓
    有效線寬回到 w mm。填色型消費者（印章／表格頁）不受 stroke-width
    影響，維持 None 即可（輸出位元組不變）。
    """
    scale = size_mm / EM_SIZE
    # SVG transform: translate to centre, then rotate, then scale,
    # then offset by half-em so the glyph sits centred.
    half = size_mm / 2.0
    tform_parts = [f"translate({x_mm - half:.3f},{y_mm - half:.3f})"]
    if abs(rotation_deg) > 1e-6:
        tform_parts.append(
            f"rotate({rotation_deg:.2f},{half:.3f},{half:.3f})"
        )
    tform_parts.append(f"scale({scale:.6f})")
    parts = []
    for stroke in c.strokes:
        if stroke.outline:
            d = _outline_path_d(stroke)
            parts.append(f'<path d="{d}"/>')
    if not parts:
        return ""
    sw = ""
    if stroke_width_mm is not None and scale > 0:
        sw = f' stroke-width="{stroke_width_mm / scale:.2f}"'
    return (f'<g transform="{" ".join(tform_parts)}"{sw}>'
            f'{"".join(parts)}</g>')


def _char_outline_bbox_em(c: Character) -> Optional[tuple]:
    """Return (cx, cy) of the character's outline bbox in EM coordinates.

    Convenience wrapper around :func:`_char_outline_bbox_full_em`.
    """
    bb = _char_outline_bbox_full_em(c)
    if bb is None:
        return None
    min_x, min_y, max_x, max_y = bb
    return ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)


def _char_outline_bbox_full_em(
    c: Character,
) -> Optional[tuple]:
    """Return (min_x, min_y, max_x, max_y) of the character's outline
    in EM coordinates, or None if the glyph has no outline data.

    Used by stamp render for **bbox-based scaling** (Phase 11g): instead
    of scaling the EM frame to fit the cell (which leaves padding because
    glyphs typically don't fill EM 0..2048), scale the actual bbox to
    fit. Result: glyphs render visually filling the cell — matching the
    visual density of physical 印章 designs (好福印 / 大小章 reference).
    """
    all_x: list[float] = []
    all_y: list[float] = []
    for s in c.strokes:
        if s.outline:
            for cmd in s.outline:
                if "x" in cmd and "y" in cmd:
                    all_x.append(cmd["x"])
                    all_y.append(cmd["y"])
                for k in ("begin", "mid", "end"):
                    if k in cmd:
                        all_x.append(cmd[k]["x"])
                        all_y.append(cmd[k]["y"])
    if not all_x or not all_y:
        return None
    return (min(all_x), min(all_y), max(all_x), max(all_y))


def _char_cut_paths_stretched(c: Character, cx_mm: float, cy_mm: float,
                              w_mm: float, h_mm: float,
                              rotation_deg: float = 0.0,
                              stroke_width_mm: Optional[float] = None) -> str:
    """Like :func:`_char_cut_paths` but with **bbox-based** non-uniform
    scale: the outline's actual bbox is scaled to fill (w_mm, h_mm) and
    centred on (cx_mm, cy_mm).

    Phase 11g change: previously used EM-based scale (w_mm / EM_SIZE),
    which left typically 10-20% padding around the glyph because outline
    fonts don't fill EM 0..2048. Now scales the actual bbox so the glyph
    visually fills the cell — matching physical 印章 reference
    (好福印 / 大小章, where each char fills its grid cell tightly).

    Used by stamp render for all chars (uniform OR stretched) — the
    "stretched" name is historical; the function handles both via
    independent w_mm / h_mm. Pass w == h to get uniform-aspect scale
    while still benefiting from bbox-based fill.
    """
    bbox = _char_outline_bbox_full_em(c)
    if bbox is None:
        return ""
    min_x, min_y, max_x, max_y = bbox
    bbox_w = max_x - min_x
    bbox_h = max_y - min_y
    if bbox_w <= 0 or bbox_h <= 0:
        return ""
    # Bbox-based scale: bbox_w * scale_x = w_mm, bbox_h * scale_y = h_mm.
    scale_x = w_mm / bbox_w
    scale_y = h_mm / bbox_h
    bcx = (min_x + max_x) / 2.0
    bcy = (min_y + max_y) / 2.0
    # Translate so bbox-centre at (bcx, bcy) in EM lands at (cx_mm, cy_mm).
    dx = cx_mm - bcx * scale_x
    dy = cy_mm - bcy * scale_y
    tform_parts = [f"translate({dx:.3f},{dy:.3f})"]
    if abs(rotation_deg) > 1e-6:
        # SVG transform 從右到左套用到 point — rotate 在 scale 後、
        # translate 前的座標系統運作，所以 rotation centre 必須是
        # post-scale 的 bbox-centre，亦即 (bcx*scale_x, bcy*scale_y)。
        tform_parts.append(
            f"rotate({rotation_deg:.2f},"
            f"{bcx * scale_x:.3f},{bcy * scale_y:.3f})"
        )
    tform_parts.append(f"scale({scale_x:.6f},{scale_y:.6f})")
    parts = []
    for stroke in c.strokes:
        if stroke.outline:
            d = _outline_path_d(stroke)
            parts.append(f'<path d="{d}"/>')
    if not parts:
        return ""
    sw = ""
    if stroke_width_mm is not None and scale_x > 0 and scale_y > 0:
        # 非等比縮放下無法精確補償，取幾何平均近似（Phase 5cc）
        import math
        sw = (f' stroke-width='
              f'"{stroke_width_mm / math.sqrt(scale_x * scale_y):.2f}"')
    return (f'<g transform="{" ".join(tform_parts)}"{sw}>'
            f'{"".join(parts)}</g>')


def _char_write_polylines(c: Character, x_mm: float, y_mm: float,
                          size_mm: float, rotation_deg: float = 0.0,
                          stroke_width_mm: Optional[float] = None) -> str:
    """Embed a Character's raw_tracks as <polyline> for the writer.

    Phase 5cc: ``stroke_width_mm`` 同 :func:`_char_cut_paths` —— 補償
    scale transform 對外層 stroke-width 的縮小。
    """
    scale = size_mm / EM_SIZE
    half = size_mm / 2.0
    tform_parts = [f"translate({x_mm - half:.3f},{y_mm - half:.3f})"]
    if abs(rotation_deg) > 1e-6:
        tform_parts.append(
            f"rotate({rotation_deg:.2f},{half:.3f},{half:.3f})"
        )
    tform_parts.append(f"scale({scale:.6f})")
    parts = []
    for stroke in c.strokes:
        track = stroke.smoothed_track or stroke.raw_track
        if len(track) >= 2:
            pts = " ".join(f"{p.x:.2f},{p.y:.2f}" for p in track)
            parts.append(f'<polyline points="{pts}"/>')
    if not parts:
        return ""
    sw = ""
    if stroke_width_mm is not None and scale > 0:
        sw = f' stroke-width="{stroke_width_mm / scale:.2f}"'
    return (f'<g transform="{" ".join(tform_parts)}"{sw}>'
            f'{"".join(parts)}</g>')


def _decoration_svg(d: SvgDecoration) -> str:
    """Place a decoration SVG fragment at (x, y) with size (w, h).

    The decoration's source viewBox is honoured; we wrap with an outer
    ``<svg>`` so the inner draws scale into the requested mm box.
    Output is a fragment (one ``<svg>`` element).

    12m-7 r30: ``clip_circle=True`` 會 wrap 整段 in clipPath，把可視
    區域裁成 inscribed circle of bbox（半徑 = min(w, h)/2，圓心於
    bbox 中央）。用於圓戳章內框圖視覺上呈正圓。
    """
    # Trust the caller's SVG content; only escape if obviously bare path data.
    body = d.svg_content.strip()
    if not body.startswith("<"):
        return ""
    inner_svg = (
        f'<svg x="{d.x_mm:.3f}" y="{d.y_mm:.3f}" '
        f'width="{d.w_mm:.3f}" height="{d.h_mm:.3f}" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'{body}</svg>'
    )
    if not d.clip_circle:
        return inner_svg
    # Wrap with clipPath（unique id 用 hash 避免 collision；加 deco_ 前綴）
    cid = f"deco_clip_{abs(hash((d.x_mm, d.y_mm, d.w_mm, d.h_mm))) % 10**8}"
    cx = d.x_mm + d.w_mm / 2.0
    cy = d.y_mm + d.h_mm / 2.0
    r = min(d.w_mm, d.h_mm) / 2.0
    return (
        f'<defs><clipPath id="{cid}">'
        f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}"/>'
        f'</clipPath></defs>'
        f'<g clip-path="url(#{cid})">{inner_svg}</g>'
    )


# ---------------------------------------------------------------------------
# Public renderers
# ---------------------------------------------------------------------------


def render_patch_svg(
    text: str,
    char_loader: CharLoader,
    *,
    preset: PatchPreset = "rectangle",
    patch_width_mm: float = 80.0,
    patch_height_mm: float = 40.0,
    char_size_mm: float = 18.0,
    text_position: TextPosition = "center",
    decorations: list[SvgDecoration] = None,
    tile_rows: int = 1,
    tile_cols: int = 1,
    tile_gap_mm: float = 5.0,
    page_width_mm: float = 210.0,
    page_height_mm: float = 297.0,
    cut_color: str = "#000",
    write_color: str = "#c33",
    cut_width: float = 0.3,
    write_width: float = 0.3,
    show_border: bool = True,           # Phase 5ay
    auto_size: bool = False,            # 5de：auto 字級
) -> str:
    """Render a patch (or tiled grid of identical patches) as two-layer SVG."""
    decorations = decorations or []
    chars: list[Character] = []
    for ch in text:
        if ch.isspace():
            continue
        c = char_loader(ch)
        if c is None:
            continue
        chars.append(c)

    poly = _ensure_polygon(_build_patch_shape(
        preset, patch_width_mm, patch_height_mm,
    ))
    poly_path_d = _polygon_to_svg_path(poly)
    positions, eff_char_size = _layout_text_positions(
        len(chars), preset, text_position,
        patch_width_mm, patch_height_mm, char_size_mm, poly,
        auto_size=auto_size,
    )

    # Build single-patch fragments (cut + write) referenced from each tile.
    cut_inner: list[str] = []
    write_inner: list[str] = []
    if poly_path_d and show_border:
        cut_inner.append(f'<path class="patch-outline" d="{poly_path_d}"/>')
    for c, (x, y, rot) in zip(chars, positions):
        # Phase 5cc: 傳入線寬讓內層群組補償 scale——否則有效線寬變
        # cut_width×(size/2048) ≈ 0.003mm 髮絲線（cairosvg 下隱形）
        cs = _char_cut_paths(c, x, y, eff_char_size, rot,
                             stroke_width_mm=cut_width)
        if cs:
            cut_inner.append(cs)
        ws = _char_write_polylines(c, x, y, eff_char_size, rot,
                                   stroke_width_mm=write_width)
        if ws:
            write_inner.append(ws)
    for d in decorations:
        cut_inner.append(_decoration_svg(d))

    cut_inner_str = "".join(cut_inner)
    write_inner_str = "".join(write_inner)

    # Tile placement.
    rows = max(1, int(tile_rows))
    cols = max(1, int(tile_cols))
    cell_w = patch_width_mm + tile_gap_mm
    cell_h = patch_height_mm + tile_gap_mm
    total_w = cols * patch_width_mm + max(cols - 1, 0) * tile_gap_mm
    total_h = rows * patch_height_mm + max(rows - 1, 0) * tile_gap_mm

    cut_tiles: list[str] = []
    write_tiles: list[str] = []
    for r in range(rows):
        for c_ in range(cols):
            tx = c_ * cell_w
            ty = r * cell_h
            cut_tiles.append(
                f'<g transform="translate({tx:.3f},{ty:.3f})">{cut_inner_str}</g>'
            )
            if write_inner_str:
                write_tiles.append(
                    f'<g transform="translate({tx:.3f},{ty:.3f})">{write_inner_str}</g>'
                )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {total_w:.3f} {total_h:.3f}" '
        f'width="{total_w:.3f}mm" height="{total_h:.3f}mm" '
        f'shape-rendering="geometricPrecision">'
        f'<g id="patch-cut" stroke="{cut_color}" stroke-width="{cut_width}" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round" '
        f'shape-rendering="geometricPrecision">'
        f'{"".join(cut_tiles)}</g>'
        f'<g id="patch-write" stroke="{write_color}" stroke-width="{write_width}" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round" '
        f'shape-rendering="geometricPrecision">'
        f'{"".join(write_tiles)}</g>'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# G-code — separate cut / write artefacts, the same path data as SVG.
# ---------------------------------------------------------------------------


def _polygon_to_gcode_path(
    poly: Polygon,
    feed: float,
    pen_down: str,
    pen_up: str,
    delay_ms: int = 150,
) -> list[str]:
    """G-code for tracing a closed polygon (cut path)."""
    if not poly.vertices:
        return []
    out: list[str] = []
    x0, y0 = poly.vertices[0]
    out.append(f"G0 X{x0:.3f} Y{y0:.3f}")
    out.append(pen_down)
    out.append(f"G4 P{delay_ms}")
    for x, y in poly.vertices[1:]:
        out.append(f"G1 X{x:.3f} Y{y:.3f} F{feed}")
    # Close: return to the starting vertex.
    out.append(f"G1 X{x0:.3f} Y{y0:.3f} F{feed}")
    out.append(f"G4 P{delay_ms}")
    out.append(pen_up)
    return out


def _outline_to_polyline(stroke, samples_per_curve: int = 8):
    """Sample a Stroke's outline commands into a flat list of (x, y)."""
    pts: list[tuple[float, float]] = []
    for cmd in stroke.outline:
        t = cmd.get("type", "")
        if t == "M":
            pts.append((cmd["x"], cmd["y"]))
        elif t == "L":
            pts.append((cmd["x"], cmd["y"]))
        elif t == "Q":
            if not pts:
                continue
            p0 = pts[-1]
            p1 = (cmd["begin"]["x"], cmd["begin"]["y"])
            p2 = (cmd["end"]["x"],   cmd["end"]["y"])
            for i in range(1, samples_per_curve + 1):
                tt = i / samples_per_curve
                u = 1.0 - tt
                pts.append((u * u * p0[0] + 2 * u * tt * p1[0] + tt * tt * p2[0],
                            u * u * p0[1] + 2 * u * tt * p1[1] + tt * tt * p2[1]))
        elif t == "C":
            if not pts:
                continue
            p0 = pts[-1]
            p1 = (cmd["begin"]["x"], cmd["begin"]["y"])
            p2 = (cmd["mid"]["x"],   cmd["mid"]["y"])
            p3 = (cmd["end"]["x"],   cmd["end"]["y"])
            for i in range(1, samples_per_curve + 1):
                tt = i / samples_per_curve
                u = 1.0 - tt
                pts.append((
                    u**3 * p0[0] + 3 * u**2 * tt * p1[0]
                    + 3 * u * tt**2 * p2[0] + tt**3 * p3[0],
                    u**3 * p0[1] + 3 * u**2 * tt * p1[1]
                    + 3 * u * tt**2 * p2[1] + tt**3 * p3[1],
                ))
    return pts


def _transform_pt(x: float, y: float,
                  tx: float, ty: float, scale: float,
                  cx_local: float, cy_local: float,
                  rotation_deg: float = 0.0) -> tuple[float, float]:
    """Mirror the SVG ``translate→rotate→scale`` chain in plain math."""
    import math
    # 1. scale around (0,0)
    x2, y2 = x * scale, y * scale
    # 2. rotate around (cx_local, cy_local) — both in scaled space
    if abs(rotation_deg) > 1e-6:
        a = math.radians(rotation_deg)
        ca, sa = math.cos(a), math.sin(a)
        dx, dy = x2 - cx_local, y2 - cy_local
        x2 = ca * dx - sa * dy + cx_local
        y2 = sa * dx + ca * dy + cy_local
    # 3. translate
    return x2 + tx, y2 + ty


# ---------------------------------------------------------------------------
# 5bq: geometry collector — the single source of truth consumed by the
# G-code emitter below AND the layered DXF exporter (render_patch_dxf).
# Coordinates are mm in SVG-like space (Y down); emitters flip as needed.
# ---------------------------------------------------------------------------


def _patch_polylines(
    text: str,
    char_loader: CharLoader,
    *,
    preset: PatchPreset,
    patch_width_mm: float,
    patch_height_mm: float,
    char_size_mm: float,
    text_position: TextPosition,
    tile_rows: int,
    tile_cols: int,
    tile_gap_mm: float,
    show_border: bool = True,
    auto_size: bool = False,            # 5de：auto 字級
) -> list[dict]:
    """Collect per-tile polylines for the patch.

    Returns one dict per tile::

        {"tile": (row, col),
         "border":        list[(x, y)] | None,   # closed loop (start not repeated)
         "char_outlines": list[list[(x, y)]],    # sampled stroke-outline loops
         "write_tracks":  list[list[(x, y)]]}    # open centreline pen tracks
    """
    chars: list[Character] = []
    for ch in text:
        if ch.isspace():
            continue
        c = char_loader(ch)
        if c is None:
            continue
        chars.append(c)

    poly = _ensure_polygon(_build_patch_shape(
        preset, patch_width_mm, patch_height_mm,
    ))
    positions, eff_char_size = _layout_text_positions(
        len(chars), preset, text_position,
        patch_width_mm, patch_height_mm, char_size_mm, poly,
        auto_size=auto_size,
    )
    rows = max(1, int(tile_rows))
    cols = max(1, int(tile_cols))
    cell_w = patch_width_mm + tile_gap_mm
    cell_h = patch_height_mm + tile_gap_mm
    scale = eff_char_size / EM_SIZE
    half = eff_char_size / 2.0

    tiles: list[dict] = []
    for r in range(rows):
        for c_ in range(cols):
            tx = c_ * cell_w
            ty = r * cell_h
            border = None
            if show_border:
                border = [(x + tx, y + ty) for x, y in poly.vertices]
            char_outlines: list[list[tuple[float, float]]] = []
            write_tracks: list[list[tuple[float, float]]] = []
            for c, (cx, cy, rot) in zip(chars, positions):
                local_origin_x = cx + tx - half
                local_origin_y = cy + ty - half
                for stroke in c.strokes:
                    if stroke.outline:
                        pts_em = _outline_to_polyline(stroke)
                        if pts_em:
                            pts_mm = [
                                _transform_pt(px, py,
                                              local_origin_x, local_origin_y,
                                              scale, half, half, rot)
                                for px, py in pts_em
                            ]
                            if len(pts_mm) >= 2:
                                char_outlines.append(pts_mm)
                    track = stroke.smoothed_track or stroke.raw_track
                    if track and len(track) >= 2:
                        write_tracks.append([
                            _transform_pt(p.x, p.y,
                                          local_origin_x, local_origin_y,
                                          scale, half, half, rot)
                            for p in track
                        ])
            tiles.append({
                "tile": (r, c_),
                "border": border,
                "char_outlines": char_outlines,
                "write_tracks": write_tracks,
            })
    return tiles


def _patch_gcode_payload(
    text: str,
    char_loader: CharLoader,
    layer: str,                       # "cut" | "write"
    *,
    preset: PatchPreset,
    patch_width_mm: float,
    patch_height_mm: float,
    char_size_mm: float,
    text_position: TextPosition,
    decorations: list[SvgDecoration],
    tile_rows: int,
    tile_cols: int,
    tile_gap_mm: float,
    feed_cut: float,
    feed_write: float,
    pen_down: str,
    pen_up: str,
    show_border: bool = True,
    auto_size: bool = False,
) -> str:
    tiles = _patch_polylines(
        text, char_loader,
        preset=preset, patch_width_mm=patch_width_mm,
        patch_height_mm=patch_height_mm, char_size_mm=char_size_mm,
        text_position=text_position, tile_rows=tile_rows,
        tile_cols=tile_cols, tile_gap_mm=tile_gap_mm,
        show_border=show_border, auto_size=auto_size,
    )
    rows = max(1, int(tile_rows))
    cols = max(1, int(tile_cols))

    feed = feed_cut if layer == "cut" else feed_write
    label = "cut (patch outline + char outlines + decorations)" \
        if layer == "cut" else "write (char raw_tracks for plotter)"

    out: list[str] = []
    out.append(f"; --- stroke-order patch G-code (layer: {layer}) ---")
    out.append(f"; {label}")
    out.append(f"; preset={preset}  patch={patch_width_mm}x{patch_height_mm}mm  "
               f"char={char_size_mm}mm  tiles={rows}x{cols}")
    out.append("G21 ; mm")
    out.append("G90 ; absolute")
    out.append(pen_up)

    def _emit_open_path(pts_mm) -> None:
        x0, y0 = pts_mm[0]
        out.append(f"G0 X{x0:.3f} Y{y0:.3f}")
        out.append(pen_down)
        out.append("G4 P150")
        for px, py in pts_mm[1:]:
            out.append(f"G1 X{px:.3f} Y{py:.3f} F{feed}")
        out.append("G4 P150")
        out.append(pen_up)

    for t in tiles:
        r, c_ = t["tile"]
        if layer == "cut":
            # 1. patch outline (skipped when show_border=False — user
            # plans to add custom border in their design tool).
            if t["border"] is not None:
                out.append(f"; tile ({r},{c_}) patch outline")
                out.extend(_polygon_to_gcode_path(
                    Polygon(vertices=t["border"]), feed, pen_down, pen_up,
                ))
            # 2. char outlines (sampled to polylines by the collector)
            for pts_mm in t["char_outlines"]:
                _emit_open_path(pts_mm)
            # 3. decorations are SVG fragments — G-code conversion is
            #    out of scope (would need a full SVG path interpreter);
            #    leave a trailer note instead so the operator knows.
            if decorations:
                out.append(
                    f"; tile ({r},{c_}) — {len(decorations)} decoration(s) "
                    "skipped in G-code (use SVG download for those)"
                )
        else:  # write
            for pts_mm in t["write_tracks"]:
                _emit_open_path(pts_mm)

    out.append(pen_up)
    out.append("; done")
    return "\n".join(out) + "\n"


def render_patch_gcode_cut(
    text: str,
    char_loader: CharLoader,
    *,
    preset: PatchPreset = "rectangle",
    patch_width_mm: float = 80.0,
    patch_height_mm: float = 40.0,
    char_size_mm: float = 18.0,
    text_position: TextPosition = "center",
    decorations: list[SvgDecoration] = None,
    tile_rows: int = 1,
    tile_cols: int = 1,
    tile_gap_mm: float = 5.0,
    feed: float = 800.0,                   # cut feed (slow)
    pen_down: str = "M3 S90",
    pen_up: str = "M5",
    show_border: bool = True,              # Phase 5ay
    auto_size: bool = False,               # 5de
) -> str:
    """G-code for the cut layer (patch outline + char outlines)."""
    return _patch_gcode_payload(
        text, char_loader, "cut",
        preset=preset, patch_width_mm=patch_width_mm,
        patch_height_mm=patch_height_mm, char_size_mm=char_size_mm,
        text_position=text_position, decorations=decorations or [],
        tile_rows=tile_rows, tile_cols=tile_cols, tile_gap_mm=tile_gap_mm,
        feed_cut=feed, feed_write=feed,
        pen_down=pen_down, pen_up=pen_up,
        show_border=show_border, auto_size=auto_size,
    )


def render_patch_gcode_write(
    text: str,
    char_loader: CharLoader,
    *,
    preset: PatchPreset = "rectangle",
    patch_width_mm: float = 80.0,
    patch_height_mm: float = 40.0,
    char_size_mm: float = 18.0,
    text_position: TextPosition = "center",
    tile_rows: int = 1,
    tile_cols: int = 1,
    tile_gap_mm: float = 5.0,
    feed: float = 3000.0,                  # write feed (fast)
    pen_down: str = "M3 S90",
    pen_up: str = "M5",
    auto_size: bool = False,               # 5de
) -> str:
    """G-code for the write layer (char raw_track polylines)."""
    return _patch_gcode_payload(
        text, char_loader, "write",
        preset=preset, patch_width_mm=patch_width_mm,
        patch_height_mm=patch_height_mm, char_size_mm=char_size_mm,
        text_position=text_position, decorations=[],
        tile_rows=tile_rows, tile_cols=tile_cols, tile_gap_mm=tile_gap_mm,
        feed_cut=feed, feed_write=feed,
        pen_down=pen_down, pen_up=pen_up, auto_size=auto_size,
    )


# ---------------------------------------------------------------------------
# Capacity preflight
# ---------------------------------------------------------------------------


def patch_capacity(
    *,
    preset: PatchPreset,
    patch_width_mm: float,
    patch_height_mm: float,
    char_size_mm: float,
    tile_rows: int = 1,
    tile_cols: int = 1,
    tile_gap_mm: float = 5.0,
    page_width_mm: float = 210.0,
    page_height_mm: float = 297.0,
) -> dict:
    """Estimate fit, characters per patch, and page utilisation."""
    margin = char_size_mm * 0.5
    usable = max(patch_width_mm - 2 * margin - char_size_mm, char_size_mm)
    chars_per_patch = max(int(usable / max(char_size_mm, 1)) + 1, 1)
    rows = max(1, int(tile_rows))
    cols = max(1, int(tile_cols))
    used_w = cols * patch_width_mm + max(cols - 1, 0) * tile_gap_mm
    used_h = rows * patch_height_mm + max(rows - 1, 0) * tile_gap_mm
    fits_page = used_w <= page_width_mm and used_h <= page_height_mm
    # Maximum tile rows × cols that fits on the page given the patch size.
    max_cols = max(1, int((page_width_mm + tile_gap_mm)
                          // (patch_width_mm + tile_gap_mm)))
    max_rows = max(1, int((page_height_mm + tile_gap_mm)
                          // (patch_height_mm + tile_gap_mm)))
    return {
        "preset": preset,
        "chars_per_patch": chars_per_patch,
        "tiles_used": rows * cols,
        "used_size_mm": [round(used_w, 2), round(used_h, 2)],
        "page_size_mm": [page_width_mm, page_height_mm],
        "fits_page": fits_page,
        "max_tiles_per_page": max_rows * max_cols,
        "max_grid": [max_rows, max_cols],
    }


__all__ = [
    "PatchPreset",
    "TextPosition",
    "SvgDecoration",
    "render_patch_svg",
    "render_patch_gcode_cut",
    "render_patch_gcode_write",
    "patch_capacity",
]


def render_patch_dxf(
    text: str,
    char_loader: CharLoader,
    *,
    preset: PatchPreset = "rectangle",
    patch_width_mm: float = 80.0,
    patch_height_mm: float = 40.0,
    char_size_mm: float = 18.0,
    text_position: TextPosition = "center",
    tile_rows: int = 1,
    tile_cols: int = 1,
    tile_gap_mm: float = 5.0,
    show_border: bool = True,
    auto_size: bool = False,               # 5de
) -> str:
    """5bq: layered DXF R12 export (VectorLine convention).

    Layers: CUT (red) = patch outline, ENGRAVE (black) = sampled char
    outlines, WRITE (blue) = centreline pen tracks. Laser users import
    into LightBurn / Beam Studio and assign per-layer power; plotter
    users take the WRITE layer. Decorations (SVG fragments) are not
    representable — same limitation as the G-code path.
    """
    from .dxf import DxfPolyline, layers_to_dxf

    tiles = _patch_polylines(
        text, char_loader,
        preset=preset, patch_width_mm=patch_width_mm,
        patch_height_mm=patch_height_mm, char_size_mm=char_size_mm,
        text_position=text_position, tile_rows=tile_rows,
        tile_cols=tile_cols, tile_gap_mm=tile_gap_mm,
        show_border=show_border, auto_size=auto_size,
    )
    cut: list[DxfPolyline] = []
    engrave: list[DxfPolyline] = []
    write: list[DxfPolyline] = []
    for t in tiles:
        if t["border"]:
            cut.append(DxfPolyline(list(t["border"]), closed=True))
        for pts in t["char_outlines"]:
            # sampled outlines return to their start point — mark closed
            # and drop the duplicate final vertex for a clean loop.
            if len(pts) > 2 and pts[0] == pts[-1]:
                engrave.append(DxfPolyline(list(pts[:-1]), closed=True))
            else:
                engrave.append(DxfPolyline(list(pts), closed=False))
        for pts in t["write_tracks"]:
            write.append(DxfPolyline(list(pts), closed=False))
    return layers_to_dxf([("CUT", cut), ("ENGRAVE", engrave),
                          ("WRITE", write)])
