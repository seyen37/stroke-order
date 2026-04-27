"""
SVG exporter.

Two rendering modes:

- ``outline`` — walks the g0v outline commands (M/L/Q) to produce a filled
  path per stroke. This is what characters "look like" in print.
- ``track``   — draws the smoothed track polyline as a stroked path. This
  is what the writing robot will follow.

Both use a 2048×2048 viewBox (the canonical em square). Multi-character
output is laid out horizontally.
"""
from __future__ import annotations

import colorsys
from typing import Literal

from ..ir import EM_SIZE, Character, Stroke


Mode = Literal["outline", "track", "both"]


def _rainbow_color(i: int, total: int) -> str:
    """Evenly spaced HSV hue for stroke i of total. Returns '#rrggbb'."""
    if total <= 1:
        return "#444"
    h = (i / total) * 0.85  # leave a gap so 1st and last aren't too similar
    r, g, b = colorsys.hsv_to_rgb(h, 0.75, 0.85)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def _outline_path_d(stroke: Stroke) -> str:
    """Convert outline commands to an SVG path 'd' attribute string.
    Handles M/L/Q (g0v format) and C (MMH cubic bezier)."""
    parts: list[str] = []
    for cmd in stroke.outline:
        t = cmd.get("type", "")
        if t == "M":
            parts.append(f"M {cmd['x']} {cmd['y']}")
        elif t == "L":
            parts.append(f"L {cmd['x']} {cmd['y']}")
        elif t == "Q":
            bx, by = cmd["begin"]["x"], cmd["begin"]["y"]
            ex, ey = cmd["end"]["x"], cmd["end"]["y"]
            parts.append(f"Q {bx} {by} {ex} {ey}")
        elif t == "C":
            # g0v + our MMH adapter both use begin/mid/end for cubic Bezier
            # (= first control, second control, endpoint)
            c1x, c1y = cmd["begin"]["x"], cmd["begin"]["y"]
            c2x, c2y = cmd["mid"]["x"],   cmd["mid"]["y"]
            ex,  ey  = cmd["end"]["x"],   cmd["end"]["y"]
            parts.append(f"C {c1x} {c1y} {c2x} {c2y} {ex} {ey}")
        # ignore unknown types
    parts.append("Z")  # outlines are closed
    return " ".join(parts)


def _track_points_str(stroke: Stroke) -> str:
    """Convert a stroke's track (prefers smoothed) to polyline points string."""
    pts = stroke.track
    return " ".join(f"{p.x:.2f},{p.y:.2f}" for p in pts)


def character_to_svg(
    char: Character,
    mode: Mode = "outline",
    *,
    show_numbers: bool = False,
    rainbow: bool = False,
    track_stroke_width: float = 8.0,
    outline_fill: str = "#222",
    track_color: str = "#c00",
    width_px: int | None = 300,
    height_px: int | None = 300,
) -> str:
    """
    Render a single Character to a standalone SVG document.

    Parameters
    ----------
    char
        Character IR (should have strokes populated; for track mode the
        smoothed_track will be preferred if present).
    mode
        'outline' = filled stroke shapes; 'track' = centerline polyline;
        'both' = outlines in gray behind, track in red on top.
    show_numbers
        Overlay 1,2,3,... at the start of each stroke for debug.
    rainbow
        Use a distinct color per stroke (overrides outline_fill / track_color).
    track_stroke_width
        Line width for track polylines (in em-space units, 0..2048).
    outline_fill
        CSS color for outline fill (mode=outline/both).
    track_color
        CSS color for track polyline (mode=track/both).
    width_px, height_px
        Rendered size attributes; None to omit (SVG defaults or CSS wins).

    Returns
    -------
    SVG document as a UTF-8 string.
    """
    if mode not in ("outline", "track", "both"):
        raise ValueError(f"unknown mode: {mode!r}")

    n = len(char.strokes)
    size_attrs = ""
    if width_px is not None:
        size_attrs += f' width="{width_px}"'
    if height_px is not None:
        size_attrs += f' height="{height_px}"'

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {EM_SIZE} {EM_SIZE}"{size_attrs} '
        f'data-char="{char.char}" data-unicode="U+{char.unicode_hex.upper()}">'
    ]
    # Light 田字格 guide lines to help eye calibrate (can be hidden with CSS)
    out.append(
        '  <g class="guides" stroke="#eee" stroke-width="2" fill="none">'
    )
    half = EM_SIZE // 2
    out.append(f'    <rect x="0" y="0" width="{EM_SIZE}" height="{EM_SIZE}"/>')
    out.append(f'    <line x1="{half}" y1="0" x2="{half}" y2="{EM_SIZE}"/>')
    out.append(f'    <line x1="0" y1="{half}" x2="{EM_SIZE}" y2="{half}"/>')
    out.append("  </g>")

    # Outlines (filled)
    if mode in ("outline", "both"):
        out.append('  <g class="outlines">')
        for i, s in enumerate(char.strokes):
            fill = _rainbow_color(i, n) if rainbow else outline_fill
            # in 'both' mode, dim the outlines so track stands out
            if mode == "both" and not rainbow:
                fill = "#ccc"
            d = _outline_path_d(s)
            out.append(
                f'    <path d="{d}" fill="{fill}" '
                f'data-stroke-index="{i}" data-kind="{s.kind_code}"/>'
            )
        out.append("  </g>")

    # Tracks (stroked polylines)
    if mode in ("track", "both"):
        out.append('  <g class="tracks" fill="none" stroke-linecap="round" '
                   'stroke-linejoin="round">')
        for i, s in enumerate(char.strokes):
            col = _rainbow_color(i, n) if rainbow else track_color
            pts = _track_points_str(s)
            out.append(
                f'    <polyline points="{pts}" '
                f'stroke="{col}" stroke-width="{track_stroke_width}" '
                f'data-stroke-index="{i}" data-kind="{s.kind_code}"/>'
            )
        out.append("  </g>")

    # Stroke numbers
    if show_numbers:
        out.append('  <g class="numbers" font-family="sans-serif" '
                   'font-weight="bold" fill="#008">')
        for i, s in enumerate(char.strokes):
            if not s.raw_track:
                continue
            p = s.raw_track[0]
            # Place number near start, offset slightly above
            out.append(
                f'    <text x="{p.x - 40}" y="{p.y - 20}" '
                f'font-size="140">{i + 1}</text>'
            )
        out.append("  </g>")

    out.append("</svg>")
    return "\n".join(out)


def save_svg(char: Character, path: str, **kwargs) -> None:
    """Convenience: render `char` and write to `path`."""
    svg = character_to_svg(char, **kwargs)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


__all__ = ["character_to_svg", "save_svg", "Mode"]
