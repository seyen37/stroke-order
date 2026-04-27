"""
Stamp / 印章 mode (Phase 5ay).

Designed for laser-engraving wood seals — a sister of the Phase-5ax
patch mode but with traditional Chinese seal conventions baked in.

Why a separate mode (not just another patch preset)
---------------------------------------------------
- **Single-layer output** — the laser doesn't care about cut vs write;
  one black outline path per element.
- **Right-to-left vertical reading** — official-stamp text follows
  the 右起直書 convention; patch mode reads left-to-right.
- **Multi-row grid layouts** — 公司章 / 官章 traditionally arrange
  6-9 chars in a 2×3 or 3×3 grid, not a horizontal line.
- **Optional double border** — typical 公司章 has two concentric
  rectangles separated by ~0.8mm; patch mode never needs that.
- **Arc text + centre** — 圓戳章 puts a unit name around the rim and
  a single anchor character (e.g. "業務") in the middle.

Both modes share :class:`SvgDecoration` (Phase 5ax) and
:func:`show_border=False` for "give me just the inside, I'll add my
own border in a design tool later."
"""
from __future__ import annotations

import math

from typing import Callable, Literal, Optional

from ..ir import Character, EM_SIZE
from .patch import (
    SvgDecoration,
    _char_cut_paths,
    _ensure_polygon,
    _polygon_to_svg_path,
    _decoration_svg,
    _polygon_to_gcode_path,
    _outline_to_polyline,
    _transform_pt,
)
from ..shapes import Circle, Ellipse, Polygon, make_shape


StampPreset = Literal[
    "square_name",      # 1-4 chars, individual signature seal
    "square_official",  # 2-9 chars, company / official seal
    "round",            # ring text + centre char
    "oval",             # 1-2 horizontal lines, acceptance seal
    "rectangle_title",  # 2 lines: title row + name row
]


CharLoader = Callable[[str], Optional[Character]]


# ---------------------------------------------------------------------------
# Layout helpers — auto-grid + arc text
# ---------------------------------------------------------------------------


def _auto_grid_dims(n: int) -> tuple[int, int]:
    """Pick (rows, cols) for ``square_official`` based on character count.

    Traditional rules:
    - 1-3 chars → 1 column (vertical strip)
    - 4 chars   → 2×2
    - 5-6 chars → 2×3 (2 cols × 3 rows, right-to-left columns)
    - 7-9 chars → 3×3
    """
    if n <= 0:
        return (1, 1)
    if n <= 3:
        return (n, 1)
    if n == 4:
        return (2, 2)
    if n <= 6:
        return (3, 2)
    return (3, 3)


def _grid_positions_right_to_left(
    n: int, rows: int, cols: int,
    inner_w: float, inner_h: float,
    centre_x: float, centre_y: float,
) -> list[tuple[float, float]]:
    """Position ``n`` chars in a (rows × cols) grid, **right column first**.

    Reading order: top-right → bottom-right → top-(right-1) → … →
    bottom-left. This is the traditional Chinese seal convention; it
    looks alien to left-to-right readers but is what every 公司章 uses.

    Returns ``[(cx, cy), ...]`` in reading order — the caller pairs
    them with ``chars[i]`` directly.
    """
    if rows <= 0 or cols <= 0 or n <= 0:
        return []
    cell_w = inner_w / cols
    cell_h = inner_h / rows
    # Top-left corner of the grid (in absolute mm).
    grid_x0 = centre_x - inner_w / 2 + cell_w / 2
    grid_y0 = centre_y - inner_h / 2 + cell_h / 2
    out: list[tuple[float, float]] = []
    # Right column first (traditional). For each column, top-to-bottom.
    for col in range(cols - 1, -1, -1):
        for row in range(rows):
            if len(out) >= n:
                return out
            cx = grid_x0 + col * cell_w
            cy = grid_y0 + row * cell_h
            out.append((cx, cy))
    return out


def _arc_text_positions(
    n: int, ring_radius: float, centre_x: float, centre_y: float,
    *, span_deg: float = 240.0, start_deg: float = -120.0,
) -> list[tuple[float, float, float]]:
    """Distribute ``n`` chars along a circular arc, returning
    ``(cx, cy, rotation_deg)`` for each.

    Defaults span 240° centred on top — the classic 圓戳章 outer ring,
    leaving the bottom 120° clear for an optional star / dot decoration.
    """
    if n <= 0:
        return []
    if n == 1:
        # Single char goes at the apex.
        theta_deg = start_deg + span_deg / 2.0
        rad = math.radians(theta_deg)
        return [(
            centre_x + ring_radius * math.cos(rad),
            centre_y + ring_radius * math.sin(rad),
            theta_deg + 90.0,   # tangent rotation
        )]
    out: list[tuple[float, float, float]] = []
    for i in range(n):
        # Even spacing INCLUDING endpoints.
        t = i / (n - 1)
        theta_deg = start_deg + span_deg * t
        rad = math.radians(theta_deg)
        out.append((
            centre_x + ring_radius * math.cos(rad),
            centre_y + ring_radius * math.sin(rad),
            theta_deg + 90.0,   # rotate so chars stand "up" on the arc
        ))
    return out


# ---------------------------------------------------------------------------
# Border builders
# ---------------------------------------------------------------------------


def _stamp_border_polys(
    preset: StampPreset,
    width_mm: float,
    height_mm: float,
    *,
    double_border: bool = False,
    double_gap_mm: float = 0.8,
) -> list:
    """Return the border shapes (one or two concentric polygons).

    Single-border default; ``double_border=True`` adds an inner shrunk
    copy ``double_gap_mm`` smaller on each side. Returns a list of
    Polygon-or-Circle-or-Ellipse objects so the caller can render
    each independently.
    """
    cx, cy = width_mm / 2, height_mm / 2

    def _outer():
        if preset == "round":
            return Circle(cx, cy, min(width_mm, height_mm) / 2)
        if preset == "oval":
            return Ellipse(cx, cy, width_mm / 2, height_mm / 2)
        # rectangular / square presets
        return Polygon(vertices=[
            (0, 0), (width_mm, 0), (width_mm, height_mm), (0, height_mm),
        ])

    polys = [_outer()]
    if double_border:
        gap = double_gap_mm
        if preset == "round":
            r = min(width_mm, height_mm) / 2 - gap
            if r > 0:
                polys.append(Circle(cx, cy, r))
        elif preset == "oval":
            polys.append(Ellipse(
                cx, cy,
                max(width_mm / 2 - gap, 0.1),
                max(height_mm / 2 - gap, 0.1),
            ))
        else:
            polys.append(Polygon(vertices=[
                (gap, gap),
                (width_mm - gap, gap),
                (width_mm - gap, height_mm - gap),
                (gap, height_mm - gap),
            ]))
    return polys


# ---------------------------------------------------------------------------
# Per-preset placement
# ---------------------------------------------------------------------------


def _placements_for_preset(
    preset: StampPreset,
    chars: list[Character],
    width_mm: float, height_mm: float,
    char_size_mm: float,
    *,
    border_padding_mm: float = 2.0,
    double_border: bool,
    double_gap_mm: float,
) -> list[tuple[Character, float, float, float]]:
    """Return ``[(char, cx_mm, cy_mm, rotation_deg), ...]``."""
    cx, cy = width_mm / 2.0, height_mm / 2.0
    inset = border_padding_mm + (double_gap_mm if double_border else 0)
    inner_w = max(width_mm - 2 * inset, char_size_mm)
    inner_h = max(height_mm - 2 * inset, char_size_mm)
    n = len(chars)
    if n == 0:
        return []

    placements: list[tuple[Character, float, float, float]] = []

    if preset == "square_name":
        # 1-4 chars: vertical strip if N≤3, 2×2 if N=4. Right column
        # first (single-column case is unaffected).
        if n <= 3:
            rows, cols = n, 1
        else:
            rows, cols = 2, 2
        coords = _grid_positions_right_to_left(
            n, rows, cols, inner_w, inner_h, cx, cy)
        for c, (x, y) in zip(chars, coords):
            placements.append((c, x, y, 0.0))

    elif preset == "square_official":
        rows, cols = _auto_grid_dims(n)
        coords = _grid_positions_right_to_left(
            n, rows, cols, inner_w, inner_h, cx, cy)
        for c, (x, y) in zip(chars, coords):
            placements.append((c, x, y, 0.0))

    elif preset == "round":
        # First (n-1) chars on outer arc, last char in centre.
        radius = min(width_mm, height_mm) / 2 - inset - char_size_mm * 0.55
        if n >= 2:
            arc_chars = chars[:-1]
            ring = _arc_text_positions(
                len(arc_chars), radius, cx, cy,
                span_deg=240.0, start_deg=-120.0,
            )
            for c, (x, y, rot) in zip(arc_chars, ring):
                placements.append((c, x, y, rot))
            # Centre char larger to stand out.
            placements.append((chars[-1], cx, cy, 0.0))
        else:
            # Single char goes in the centre with no ring.
            placements.append((chars[0], cx, cy, 0.0))

    elif preset == "oval":
        # 1-2 horizontal lines, top-to-bottom reading.
        # Splits chars roughly in half if > 4 chars.
        if n <= 4:
            # Single horizontal row.
            spacing = inner_w / max(n, 1)
            x0 = cx - inner_w / 2 + spacing / 2
            for i, c in enumerate(chars):
                placements.append((c, x0 + i * spacing, cy, 0.0))
        else:
            # Two rows (top, bottom).
            half = (n + 1) // 2
            top_row = chars[:half]
            bot_row = chars[half:]
            for row_chars, y_off in [
                (top_row, cy - inner_h * 0.22),
                (bot_row, cy + inner_h * 0.22),
            ]:
                m = len(row_chars)
                if m == 0:
                    continue
                spacing = inner_w / m
                x0 = cx - inner_w / 2 + spacing / 2
                for i, c in enumerate(row_chars):
                    placements.append((c, x0 + i * spacing, y_off, 0.0))

    elif preset == "rectangle_title":
        # Two horizontal rows: top = first half, bottom = second half.
        half = (n + 1) // 2
        top_row = chars[:half]
        bot_row = chars[half:]
        for row_chars, y_off in [
            (top_row, cy - inner_h * 0.25),
            (bot_row, cy + inner_h * 0.25),
        ]:
            m = len(row_chars)
            if m == 0:
                continue
            spacing = inner_w / m
            x0 = cx - inner_w / 2 + spacing / 2
            for i, c in enumerate(row_chars):
                placements.append((c, x0 + i * spacing, y_off, 0.0))

    return placements


# ---------------------------------------------------------------------------
# Public renderers
# ---------------------------------------------------------------------------


def render_stamp_svg(
    text: str,
    char_loader: CharLoader,
    *,
    preset: StampPreset = "square_name",
    stamp_width_mm: float = 25.0,
    stamp_height_mm: float = 25.0,
    char_size_mm: float = 10.0,
    show_border: bool = True,
    double_border: bool = False,
    double_gap_mm: float = 0.8,
    border_padding_mm: float = 2.0,
    decorations: list[SvgDecoration] = None,
    color: str = "#000",
    stroke_width: float = 0.3,
) -> str:
    """Render a single stamp as one-layer SVG (laser-engrave-friendly)."""
    decorations = decorations or []
    chars: list[Character] = []
    for ch in text:
        if ch.isspace():
            continue
        c = char_loader(ch)
        if c is None:
            continue
        chars.append(c)

    placements = _placements_for_preset(
        preset, chars, stamp_width_mm, stamp_height_mm, char_size_mm,
        border_padding_mm=border_padding_mm,
        double_border=double_border, double_gap_mm=double_gap_mm,
    )

    # Border polygons (may be hidden via show_border=False).
    pieces: list[str] = []
    if show_border:
        for shape in _stamp_border_polys(
            preset, stamp_width_mm, stamp_height_mm,
            double_border=double_border, double_gap_mm=double_gap_mm,
        ):
            poly = _ensure_polygon(shape)
            d = _polygon_to_svg_path(poly)
            if d:
                pieces.append(f'<path class="stamp-border" d="{d}"/>')

    # Char outlines.
    for c, x, y, rot in placements:
        # Round preset: centre char gets bigger size for visual weight.
        size = char_size_mm
        if preset == "round" and len(chars) >= 2:
            if (c, x, y, rot) == placements[-1]:
                size = char_size_mm * 1.4
        pieces.append(_char_cut_paths(c, x, y, size, rot))

    # Decorations.
    for d in decorations:
        pieces.append(_decoration_svg(d))

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {stamp_width_mm:.3f} {stamp_height_mm:.3f}" '
        f'width="{stamp_width_mm:.3f}mm" height="{stamp_height_mm:.3f}mm">'
        f'<g id="stamp-engrave" stroke="{color}" stroke-width="{stroke_width}" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round">'
        f'{"".join(pieces)}</g></svg>'
    )


def render_stamp_gcode(
    text: str,
    char_loader: CharLoader,
    *,
    preset: StampPreset = "square_name",
    stamp_width_mm: float = 25.0,
    stamp_height_mm: float = 25.0,
    char_size_mm: float = 10.0,
    show_border: bool = True,
    double_border: bool = False,
    double_gap_mm: float = 0.8,
    border_padding_mm: float = 2.0,
    decorations: list[SvgDecoration] = None,
    feed: float = 1500.0,
    laser_power: int = 255,
    laser_on: str = None,
    laser_off: str = "M5",
) -> str:
    """G-code for a laser engraver. ``M3 S{laser_power}`` at full power
    by default; override ``laser_on`` / ``laser_off`` for diode-laser
    firmwares that use ``M106``/``M107`` etc."""
    if laser_on is None:
        laser_on = f"M3 S{laser_power}"
    decorations = decorations or []
    chars: list[Character] = []
    for ch in text:
        if ch.isspace():
            continue
        c = char_loader(ch)
        if c is None:
            continue
        chars.append(c)

    placements = _placements_for_preset(
        preset, chars, stamp_width_mm, stamp_height_mm, char_size_mm,
        border_padding_mm=border_padding_mm,
        double_border=double_border, double_gap_mm=double_gap_mm,
    )

    out: list[str] = [
        "; --- stroke-order stamp G-code (laser engrave) ---",
        f"; preset={preset}  stamp={stamp_width_mm}x{stamp_height_mm}mm  "
        f"char={char_size_mm}mm  show_border={show_border}",
        "G21 ; mm",
        "G90 ; absolute",
        laser_off,
    ]

    if show_border:
        for shape in _stamp_border_polys(
            preset, stamp_width_mm, stamp_height_mm,
            double_border=double_border, double_gap_mm=double_gap_mm,
        ):
            poly = _ensure_polygon(shape)
            out.extend(_polygon_to_gcode_path(
                poly, feed, laser_on, laser_off,
            ))

    scale = char_size_mm / EM_SIZE
    half = char_size_mm / 2.0
    for c, cx_mm, cy_mm, rot in placements:
        size = char_size_mm
        if preset == "round" and len(chars) >= 2:
            if (c, cx_mm, cy_mm, rot) == placements[-1]:
                size = char_size_mm * 1.4
        glyph_scale = size / EM_SIZE
        glyph_half = size / 2.0
        for stroke in c.strokes:
            if not stroke.outline:
                continue
            pts_em = _outline_to_polyline(stroke)
            if not pts_em:
                continue
            local_origin_x = cx_mm - glyph_half
            local_origin_y = cy_mm - glyph_half
            pts_mm: list[tuple[float, float]] = []
            for px, py in pts_em:
                mx, my = _transform_pt(
                    px, py,
                    local_origin_x, local_origin_y,
                    glyph_scale, glyph_half, glyph_half, rot,
                )
                pts_mm.append((mx, my))
            if len(pts_mm) < 2:
                continue
            x0, y0 = pts_mm[0]
            out.append(f"G0 X{x0:.3f} Y{y0:.3f}")
            out.append(laser_on)
            out.append("G4 P50")
            for px, py in pts_mm[1:]:
                out.append(f"G1 X{px:.3f} Y{py:.3f} F{feed}")
            out.append("G4 P50")
            out.append(laser_off)

    if decorations:
        out.append(
            f"; — {len(decorations)} decoration(s) skipped in G-code "
            "(use SVG download to keep them)"
        )
    out.append(laser_off)
    out.append("; done")
    return "\n".join(out) + "\n"


def stamp_capacity(
    *,
    preset: StampPreset,
    stamp_width_mm: float,
    stamp_height_mm: float,
    char_size_mm: float,
    border_padding_mm: float = 2.0,
    double_border: bool = False,
    double_gap_mm: float = 0.8,
) -> dict:
    """How many characters fit at the chosen size?"""
    inset = border_padding_mm + (double_gap_mm if double_border else 0)
    inner_w = max(stamp_width_mm - 2 * inset, 1.0)
    inner_h = max(stamp_height_mm - 2 * inset, 1.0)
    if preset == "square_name":
        max_chars = 4   # spec
    elif preset == "square_official":
        max_chars = 9   # 3×3 cap
    elif preset == "round":
        # Outer arc fits ~2πr/spacing chars + 1 centre.
        r = min(stamp_width_mm, stamp_height_mm) / 2 - inset
        arc_len = (240.0 / 360.0) * 2 * math.pi * r   # span 240°
        max_chars = max(int(arc_len / (char_size_mm * 1.2)), 1) + 1
    elif preset == "oval":
        per_row = max(int(inner_w / (char_size_mm * 1.1)), 1)
        max_chars = per_row * 2
    elif preset == "rectangle_title":
        per_row = max(int(inner_w / (char_size_mm * 1.1)), 1)
        max_chars = per_row * 2
    else:
        max_chars = 0
    return {
        "preset": preset,
        "max_chars": max_chars,
        "inner_size_mm": [round(inner_w, 2), round(inner_h, 2)],
    }


__all__ = [
    "StampPreset",
    "render_stamp_svg",
    "render_stamp_gcode",
    "stamp_capacity",
]
