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
    """
    svg_content: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float


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


def _layout_text_positions(
    n_chars: int,
    preset: PatchPreset,
    position: TextPosition,
    patch_w_mm: float,
    patch_h_mm: float,
    char_size_mm: float,
    poly: Polygon,
) -> list[tuple[float, float, float]]:
    """Return ``[(cx_mm, cy_mm, rotation_deg), ...]`` for each char.

    - ``center`` / ``top`` / ``bottom`` — straight horizontal row.
    - ``on_arc`` — for arch_top / arch_bottom presets, distribute along
      the inner arc curvature; for any other preset falls through to
      ``center``.
    """
    if n_chars <= 0:
        return []
    if position == "on_arc" and preset not in ("arch_top", "arch_bottom"):
        position = "center"

    if position == "on_arc":
        # Drop the chars along the chord at the patch's vertical centre,
        # but rotate each one slightly so they tangentially fan around
        # the bbox centre. v1 keeps it simple — the visual on a wide
        # arch is already convincing without true polar layout.
        cx0 = patch_w_mm / 2.0
        cy0 = patch_h_mm / 2.0
        # Effective chord width (≈ patch width) divided by N chars.
        usable = patch_w_mm - char_size_mm * 1.2
        spacing = usable / max(n_chars - 1, 1) if n_chars > 1 else 0
        x0 = cx0 - usable / 2.0
        # Approximate radius from arch curvature (use bbox heights).
        # Apex offset = sagitta_inner ≈ curvature*hh; we move chars up
        # toward the apex for arch_top, down for arch_bottom.
        bbox = poly.bbox()
        bbox_h = bbox[3] - bbox[1]
        offset = bbox_h * 0.25 * (-1 if preset == "arch_top" else 1)
        # Estimate angular span from chord & approx radius.
        import math
        radius_est = max(usable, 1.0)
        slots = []
        for i in range(n_chars):
            x = x0 + i * spacing if n_chars > 1 else cx0
            # Rotation: linear angle from -alpha → +alpha across the chord.
            t = (i / (n_chars - 1)) if n_chars > 1 else 0.5
            alpha_deg = (t - 0.5) * 25.0   # gentle 25° total span
            if preset == "arch_bottom":
                alpha_deg = -alpha_deg
            slots.append((x, cy0 + offset, alpha_deg))
        return slots

    # Straight horizontal row.
    cy_map = {
        "center": patch_h_mm / 2.0,
        "top":    patch_h_mm * 0.30,
        "bottom": patch_h_mm * 0.70,
    }
    cy = cy_map.get(position, patch_h_mm / 2.0)
    if n_chars == 1:
        return [(patch_w_mm / 2.0, cy, 0.0)]
    # Even spacing; clamp so chars stay inside the patch with margin.
    margin = char_size_mm * 0.5
    usable = max(patch_w_mm - 2 * margin - char_size_mm, char_size_mm)
    spacing = usable / (n_chars - 1)
    x0 = margin + char_size_mm / 2.0
    return [(x0 + i * spacing, cy, 0.0) for i in range(n_chars)]


def _char_cut_paths(c: Character, x_mm: float, y_mm: float,
                    size_mm: float, rotation_deg: float = 0.0) -> str:
    """Embed a Character's outlines as <path> elements at (x, y).

    Uniform scale (width = height = size_mm). For non-uniform stretch
    (e.g. stamp 3-字 traditional layout where surname is elongated),
    use :func:`_char_cut_paths_stretched`.
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
    return f'<g transform="{" ".join(tform_parts)}">{"".join(parts)}</g>'


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
                              rotation_deg: float = 0.0) -> str:
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
    return f'<g transform="{" ".join(tform_parts)}">{"".join(parts)}</g>'


def _char_write_polylines(c: Character, x_mm: float, y_mm: float,
                          size_mm: float, rotation_deg: float = 0.0) -> str:
    """Embed a Character's raw_tracks as <polyline> for the writer."""
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
    return f'<g transform="{" ".join(tform_parts)}">{"".join(parts)}</g>'


def _decoration_svg(d: SvgDecoration) -> str:
    """Place a decoration SVG fragment at (x, y) with size (w, h).

    The decoration's source viewBox is honoured; we wrap with an outer
    ``<svg>`` so the inner draws scale into the requested mm box.
    Output is a fragment (one ``<svg>`` element).
    """
    # Trust the caller's SVG content; only escape if obviously bare path data.
    body = d.svg_content.strip()
    if not body.startswith("<"):
        return ""
    return (
        f'<svg x="{d.x_mm:.3f}" y="{d.y_mm:.3f}" '
        f'width="{d.w_mm:.3f}" height="{d.h_mm:.3f}" preserveAspectRatio="xMidYMid meet">'
        f'{body}</svg>'
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
    positions = _layout_text_positions(
        len(chars), preset, text_position,
        patch_width_mm, patch_height_mm, char_size_mm, poly,
    )

    # Build single-patch fragments (cut + write) referenced from each tile.
    cut_inner: list[str] = []
    write_inner: list[str] = []
    if poly_path_d and show_border:
        cut_inner.append(f'<path class="patch-outline" d="{poly_path_d}"/>')
    for c, (x, y, rot) in zip(chars, positions):
        cs = _char_cut_paths(c, x, y, char_size_mm, rot)
        if cs:
            cut_inner.append(cs)
        ws = _char_write_polylines(c, x, y, char_size_mm, rot)
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
        f'width="{total_w:.3f}mm" height="{total_h:.3f}mm">'
        f'<g id="patch-cut" stroke="{cut_color}" stroke-width="{cut_width}" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round">'
        f'{"".join(cut_tiles)}</g>'
        f'<g id="patch-write" stroke="{write_color}" stroke-width="{write_width}" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round">'
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
) -> str:
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
    positions = _layout_text_positions(
        len(chars), preset, text_position,
        patch_width_mm, patch_height_mm, char_size_mm, poly,
    )

    rows = max(1, int(tile_rows))
    cols = max(1, int(tile_cols))
    cell_w = patch_width_mm + tile_gap_mm
    cell_h = patch_height_mm + tile_gap_mm

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

    for r in range(rows):
        for c_ in range(cols):
            tx = c_ * cell_w
            ty = r * cell_h
            if layer == "cut":
                # 1. patch outline (skipped when show_border=False — user
                # plans to add custom border in their design tool).
                if show_border:
                    shifted = Polygon(vertices=[
                        (x + tx, y + ty) for x, y in poly.vertices
                    ])
                    out.append(f"; tile ({r},{c_}) patch outline")
                    out.extend(_polygon_to_gcode_path(
                        shifted, feed, pen_down, pen_up,
                    ))
                # 2. char outlines (sample to polylines)
                scale = char_size_mm / EM_SIZE
                half = char_size_mm / 2.0
                for c, (cx, cy, rot) in zip(chars, positions):
                    for stroke in c.strokes:
                        if not stroke.outline:
                            continue
                        pts_em = _outline_to_polyline(stroke)
                        if not pts_em:
                            continue
                        # Same translate-rotate-scale as SVG layer.
                        local_origin_x = cx + tx - half
                        local_origin_y = cy + ty - half
                        pts_mm: list[tuple[float, float]] = []
                        for px, py in pts_em:
                            mx, my = _transform_pt(
                                px, py,
                                local_origin_x, local_origin_y,
                                scale, half, half, rot,
                            )
                            pts_mm.append((mx, my))
                        if len(pts_mm) < 2:
                            continue
                        x0, y0 = pts_mm[0]
                        out.append(f"G0 X{x0:.3f} Y{y0:.3f}")
                        out.append(pen_down)
                        out.append("G4 P150")
                        for px, py in pts_mm[1:]:
                            out.append(f"G1 X{px:.3f} Y{py:.3f} F{feed}")
                        out.append("G4 P150")
                        out.append(pen_up)
                # 3. decorations are SVG fragments — G-code conversion is
                #    out of scope (would need a full SVG path interpreter);
                #    leave a trailer note instead so the operator knows.
                if decorations:
                    out.append(
                        f"; tile ({r},{c_}) — {len(decorations)} decoration(s) "
                        "skipped in G-code (use SVG download for those)"
                    )
            else:  # write
                scale = char_size_mm / EM_SIZE
                half = char_size_mm / 2.0
                for c, (cx, cy, rot) in zip(chars, positions):
                    for stroke in c.strokes:
                        track = stroke.smoothed_track or stroke.raw_track
                        if len(track) < 2:
                            continue
                        local_origin_x = cx + tx - half
                        local_origin_y = cy + ty - half
                        pts_mm: list[tuple[float, float]] = []
                        for p in track:
                            mx, my = _transform_pt(
                                p.x, p.y,
                                local_origin_x, local_origin_y,
                                scale, half, half, rot,
                            )
                            pts_mm.append((mx, my))
                        x0, y0 = pts_mm[0]
                        out.append(f"G0 X{x0:.3f} Y{y0:.3f}")
                        out.append(pen_down)
                        out.append("G4 P150")
                        for px, py in pts_mm[1:]:
                            out.append(f"G1 X{px:.3f} Y{py:.3f} F{feed}")
                        out.append("G4 P150")
                        out.append(pen_up)

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
        show_border=show_border,
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
) -> str:
    """G-code for the write layer (char raw_track polylines)."""
    return _patch_gcode_payload(
        text, char_loader, "write",
        preset=preset, patch_width_mm=patch_width_mm,
        patch_height_mm=patch_height_mm, char_size_mm=char_size_mm,
        text_position=text_position, decorations=[],
        tile_rows=tile_rows, tile_cols=tile_cols, tile_gap_mm=tile_gap_mm,
        feed_cut=feed, feed_write=feed,
        pen_down=pen_down, pen_up=pen_up,
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
