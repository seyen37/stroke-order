"""
字帖 / practice-worksheet generator.

Render a grid of characters with configurable guide lines (田字格, 米字格,
回宮格, 方格). Output is a single SVG document that can be printed directly
or rasterized to PNG/PDF.

Unlike the single-char SVG exporter, each cell uses the FULL em square as
its canvas, so characters display at proper proportions.
"""
from __future__ import annotations

from typing import Literal, Optional

from ..ir import EM_SIZE, Character
from .svg import _outline_path_d, _track_points_str

GridStyle = Literal["tian", "mi", "hui", "plain", "none"]
CellStyle = Literal["filled", "outline", "trace", "ghost", "blank"]


def auto_tier_counts(cols: int) -> tuple[int, int]:
    """Given the user's ``cols`` input, return (ghost_copies, blank_copies)
    defaults for the tier-based worksheet.

    cols=1 → (0, 0)  — primary only
    cols=2 → (1, 0)  — primary + 1 ghost
    cols≥3 → (1, cols-2) — primary + 1 ghost + (cols-2) blanks
    """
    if cols <= 1:
        return (0, 0)
    if cols == 2:
        return (1, 0)
    return (1, cols - 2)


def _guide_paths(style: GridStyle, size: int = EM_SIZE) -> str:
    """
    Return SVG <g> content for the guide lines of one cell.
    Uses light grey dashed lines so they're visible but not obtrusive.
    """
    half = size // 2
    third_l, third_r = size // 3, 2 * size // 3
    # stroke-width in em-units; 12 ≈ 1.2% of em = visible at typical print sizes
    g = ['<g class="guides" stroke="#bbbbbb" stroke-width="12" fill="none" '
         'stroke-dasharray="40 30">']
    # outer border always (except 'none') — solid, slightly darker
    if style != "none":
        g.append(f'<rect x="0" y="0" width="{size}" height="{size}" '
                 f'stroke="#888" stroke-width="14" stroke-dasharray="none"/>')

    if style == "tian":
        # 田字格: cross through centre
        g.append(f'<line x1="{half}" y1="0" x2="{half}" y2="{size}"/>')
        g.append(f'<line x1="0" y1="{half}" x2="{size}" y2="{half}"/>')
    elif style == "mi":
        # 米字格: tian + two diagonals
        g.append(f'<line x1="{half}" y1="0" x2="{half}" y2="{size}"/>')
        g.append(f'<line x1="0" y1="{half}" x2="{size}" y2="{half}"/>')
        g.append(f'<line x1="0" y1="0" x2="{size}" y2="{size}"/>')
        g.append(f'<line x1="{size}" y1="0" x2="{0}" y2="{size}"/>')
    elif style == "hui":
        # 回宮格: outer + inner 1/3 rectangle
        g.append(f'<rect x="{third_l}" y="{third_l}" '
                 f'width="{third_r - third_l}" height="{third_r - third_l}"/>')
    # 'plain' = just the border (already added)
    # 'none' = nothing
    g.append("</g>")
    return "\n    ".join(g)


def _cell_content(char: Character, style: CellStyle) -> str:
    """Render one character into one cell's SVG content (no border/guides)."""
    if style == "blank" or not char.strokes:
        return ""
    if style == "ghost":
        # light grey outline — for tracing practice
        return (f'<g class="ghost" fill="#e0e0e0">' +
                "".join(f'<path d="{_outline_path_d(s)}"/>'
                        for s in char.strokes) + "</g>")
    if style == "outline":
        # filled stroke outlines (standard display)
        return ('<g class="outline" fill="#222">' +
                "".join(f'<path d="{_outline_path_d(s)}"/>'
                        for s in char.strokes) + "</g>")
    if style == "trace":
        # centerline track (thin red line) — what the robot will follow
        return ('<g class="trace" fill="none" stroke="#c22" stroke-width="14" '
                'stroke-linecap="round" stroke-linejoin="round">' +
                "".join(f'<polyline points="{_track_points_str(s)}"/>'
                        for s in char.strokes) + "</g>")
    # 'filled' = outline + trace overlay
    return (
        '<g class="outline" fill="#ccc">' +
        "".join(f'<path d="{_outline_path_d(s)}"/>' for s in char.strokes) +
        "</g>"
        '<g class="trace" fill="none" stroke="#c22" stroke-width="10" '
        'stroke-linecap="round" stroke-linejoin="round">' +
        "".join(f'<polyline points="{_track_points_str(s)}"/>'
                for s in char.strokes) +
        "</g>"
    )


def render_grid_svg(
    chars: list[Character],
    *,
    cols: int = 1,
    guide: GridStyle = "tian",
    cell_style: CellStyle = "outline",
    cell_size_px: int = 120,
    ghost_copies: Optional[int] = None,
    blank_copies: Optional[int] = None,
    direction: Literal["horizontal", "vertical"] = "horizontal",
    repeat_per_char: int = 1,   # kept for back-compat; no longer affects layout
) -> str:
    """
    Render a 字帖-style worksheet SVG with **tier-based** layout (Phase 5j).

    Given ``N`` input characters (= string length), this function builds a
    grid of exactly ``N`` cells per "tier" (row in 橫書, column in 直書)
    and stacks multiple tiers:

    - Tier 1: primary (full characters in ``cell_style``)
    - Tiers 2..1+ghost_copies: ghost (light grey for tracing practice)
    - Tiers 2+ghost..: blank (empty cells for freehand practice)

    ``cols`` sets the **total tier count**. If ``ghost_copies`` or
    ``blank_copies`` are ``None``, they are auto-derived from ``cols``:

    ======  ======  ======
    cols    ghost   blank
    ======  ======  ======
    1       0       0
    2       1       0
    3       1       1
    4       1       2
    N≥3     1       N-2
    ======  ======  ======

    Layout orientation
    ------------------
    - ``horizontal`` (橫書): each tier is a ROW of N cells; tiers stack
      top-to-bottom (row 0 = primary, last row = last blank tier).
    - ``vertical`` (直書): each tier is a COLUMN of N cells; tiers stack
      right-to-left (rightmost column = primary, leftmost = last tier).

    ``repeat_per_char`` is kept in the signature for backward-compatibility
    but no longer affects layout — the new semantic always uses exactly one
    primary tier per worksheet.
    """
    if not chars:
        return ('<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 1 1"></svg>')

    N = len(chars)

    auto_g, auto_b = auto_tier_counts(cols)
    if ghost_copies is None:
        ghost_copies = auto_g
    if blank_copies is None:
        blank_copies = auto_b
    ghost_copies = max(0, ghost_copies)
    blank_copies = max(0, blank_copies)

    # Build tiers (each tier has exactly N cells — one per character)
    tiers: list[list[tuple[Character, CellStyle]]] = []
    tiers.append([(c, cell_style) for c in chars])          # primary
    for _ in range(ghost_copies):
        tiers.append([(c, "ghost") for c in chars])
    for _ in range(blank_copies):
        tiers.append([(c, "blank") for c in chars])
    num_tiers = len(tiers)

    if direction == "vertical":
        grid_cols = num_tiers
        grid_rows = N
    else:
        grid_cols = N
        grid_rows = num_tiers

    total_w_em = grid_cols * EM_SIZE
    total_h_em = grid_rows * EM_SIZE
    total_w_px = grid_cols * cell_size_px
    total_h_px = grid_rows * cell_size_px

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{total_w_px}" height="{total_h_px}" '
        f'viewBox="0 0 {total_w_em} {total_h_em}">'
    ]
    out.append(f'<rect x="0" y="0" width="{total_w_em}" '
               f'height="{total_h_em}" fill="white"/>')
    guide_svg = _guide_paths(guide)

    for tier_idx, tier in enumerate(tiers):
        for char_idx, (ch, style) in enumerate(tier):
            if direction == "vertical":
                # Rightmost column is tier 0 (primary); stacked leftward
                col = (num_tiers - 1) - tier_idx
                row = char_idx
            else:
                col = char_idx
                row = tier_idx
            tx = col * EM_SIZE
            ty = row * EM_SIZE
            out.append(f'<g transform="translate({tx},{ty})">')
            out.append(f'  {guide_svg}')
            out.append(f'  {_cell_content(ch, style)}')
            out.append("</g>")
    out.append("</svg>")
    return "\n".join(out)


def save_grid_svg(chars: list[Character], path: str, **kwargs) -> None:
    svg = render_grid_svg(chars, **kwargs)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


# ---------------------------------------------------------------------------
# Cell positioning helper (shared across SVG / G-code / JSON renderers)
# ---------------------------------------------------------------------------


def _grid_cell_positions(
    chars: list[Character],
    cols: int,
    ghost_copies: Optional[int],
    blank_copies: Optional[int],
    direction: Literal["horizontal", "vertical"],
) -> tuple[list[dict], int, int]:
    """Compute per-cell metadata for the grid layout.

    Returns ``(cells, grid_cols, grid_rows)`` where each cell dict has:
    ``{char, char_idx, tier_idx, tier_kind, col, row, cell_style_default}``.

    ``tier_kind`` ∈ {"primary", "ghost", "blank"}.
    """
    N = len(chars)
    if N == 0:
        return [], 1, 1

    auto_g, auto_b = auto_tier_counts(cols)
    g = auto_g if ghost_copies is None else max(0, ghost_copies)
    b = auto_b if blank_copies is None else max(0, blank_copies)
    num_tiers = 1 + g + b

    cells: list[dict] = []
    for tier_idx in range(num_tiers):
        if tier_idx == 0:
            kind = "primary"
        elif tier_idx <= g:
            kind = "ghost"
        else:
            kind = "blank"
        for char_idx in range(N):
            if direction == "vertical":
                col = (num_tiers - 1) - tier_idx  # rightmost = primary
                row = char_idx
            else:
                col = char_idx
                row = tier_idx
            cells.append({
                "char": chars[char_idx],
                "char_idx": char_idx,
                "tier_idx": tier_idx,
                "tier_kind": kind,
                "col": col,
                "row": row,
            })

    if direction == "vertical":
        grid_cols, grid_rows = num_tiers, N
    else:
        grid_cols, grid_rows = N, num_tiers
    return cells, grid_cols, grid_rows


# ---------------------------------------------------------------------------
# G-code renderer — primary tier only (A1 rule)
# ---------------------------------------------------------------------------


def render_grid_gcode(
    chars: list[Character],
    *,
    cols: int = 1,
    ghost_copies: Optional[int] = None,
    blank_copies: Optional[int] = None,
    direction: Literal["horizontal", "vertical"] = "horizontal",
    cell_size_mm: float = 20.0,
    cell_gap_mm: float = 0.0,
    feed_rate: int = 3000,
    travel_rate: int = 6000,
    pen_up_cmd: str = "M5",
    pen_down_cmd: str = "M3 S90",
    pen_dwell_sec: float = 0.15,
    flip_y: bool = True,
    origin_x_mm: float = 10.0,
    origin_y_mm: float = 10.0,
) -> str:
    """Emit G-code for the grid's primary tier only.

    Ghost (pre-traced example) and blank (student practice) tiers are skipped
    — the writing robot only needs to write the primary/master cells.

    Cells are emitted in **tier order**: horizontal mode scans the primary
    row left-to-right; vertical mode scans the primary column top-to-bottom.
    This keeps pen motion visually predictable (B1 rule).
    """
    from io import StringIO
    from ..ir import EM_SIZE

    cells, grid_cols, grid_rows = _grid_cell_positions(
        chars, cols, ghost_copies, blank_copies, direction,
    )
    primary_cells = [c for c in cells if c["tier_kind"] == "primary"]
    # Order: left-to-right for horizontal, top-to-bottom for vertical
    if direction == "vertical":
        primary_cells.sort(key=lambda c: c["row"])
    else:
        primary_cells.sort(key=lambda c: c["col"])

    cell_pitch = cell_size_mm + cell_gap_mm
    scale = cell_size_mm / EM_SIZE

    buf = StringIO()
    buf.write("; --- stroke-order 字帖 G-code (primary tier only) ---\n")
    buf.write(f"; chars: {''.join(c.char for c in chars)}\n")
    buf.write(f"; cell_size={cell_size_mm}mm gap={cell_gap_mm}mm "
              f"direction={direction} feed={feed_rate}\n")
    buf.write("G21 ; mm\n")
    buf.write("G90 ; absolute\n")
    buf.write(f"{pen_up_cmd} ; pen up (start)\n")
    if pen_dwell_sec > 0:
        buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")
    buf.write(f"G0 X{origin_x_mm:.3f} Y{origin_y_mm:.3f} F{travel_rate} ; home\n")

    for cell in primary_cells:
        ch = cell["char"]
        # Cell origin in the output coordinate system
        # horizontal: column increases → X increases; row increases → Y increases
        cell_x = origin_x_mm + cell["col"] * cell_pitch
        cell_y = origin_y_mm + cell["row"] * cell_pitch

        buf.write(f"\n; --- cell ({cell['row']},{cell['col']}): "
                  f"{ch.char} (U+{ch.unicode_hex.upper()}) ---\n")

        for s in ch.strokes:
            pts = s.track
            if not pts:
                continue
            buf.write(f"; stroke {s.index + 1}: {s.kind_name}\n")

            def _xform(p):
                x_mm = cell_x + p.x * scale
                y_ir = (EM_SIZE - p.y) if flip_y else p.y
                y_mm = cell_y + y_ir * scale
                return x_mm, y_mm

            x, y = _xform(pts[0])
            buf.write(f"G0 X{x:.3f} Y{y:.3f} F{travel_rate}\n")
            buf.write(f"{pen_down_cmd}\n")
            if pen_dwell_sec > 0:
                buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")
            for p in pts[1:]:
                x, y = _xform(p)
                buf.write(f"G1 X{x:.3f} Y{y:.3f} F{feed_rate}\n")
            if pen_dwell_sec > 0:
                buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")
            buf.write(f"{pen_up_cmd}\n")

    buf.write("\n; --- epilogue ---\n")
    buf.write(f"{pen_up_cmd} ; ensure pen up\n")
    buf.write(f"G0 X{origin_x_mm:.3f} Y{origin_y_mm:.3f} F{travel_rate} ; return home\n")
    buf.write("; done\n")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# JSON renderer — full grid metadata + all cells (C2 rule)
# ---------------------------------------------------------------------------


def render_grid_json(
    chars: list[Character],
    *,
    cols: int = 1,
    ghost_copies: Optional[int] = None,
    blank_copies: Optional[int] = None,
    direction: Literal["horizontal", "vertical"] = "horizontal",
    cell_size_mm: float = 20.0,
    cell_gap_mm: float = 0.0,
    guide: GridStyle = "tian",
    cell_style: CellStyle = "filled",
    indent: int = 2,
) -> str:
    """Render the grid as structured JSON.

    Output shape::

        {
          "grid": {
            "chars": [...],
            "N": 4,
            "cols": 3,
            "direction": "horizontal",
            "grid_cols": 4, "grid_rows": 3,
            "cell_size_mm": 20.0, "cell_gap_mm": 0.0,
            "guide": "tian",
            "tier_counts": {"primary": 1, "ghost": 1, "blank": 1}
          },
          "cells": [
            {
              "char": "日", "unicode": "U+65E5",
              "tier_idx": 0, "tier_kind": "primary",
              "col": 0, "row": 0,
              "x_mm": 0.0, "y_mm": 0.0,
              "cell_style": "filled",
              "strokes": [ [[x,y], ...], ... ]   # only if primary
            },
            ...
          ]
        }

    Non-primary cells omit ``strokes`` (they're empty for practice anyway).
    """
    import json

    cells, grid_cols_n, grid_rows_n = _grid_cell_positions(
        chars, cols, ghost_copies, blank_copies, direction,
    )
    cell_pitch = cell_size_mm + cell_gap_mm

    auto_g, auto_b = auto_tier_counts(cols)
    g = auto_g if ghost_copies is None else max(0, ghost_copies)
    b = auto_b if blank_copies is None else max(0, blank_copies)

    cells_out = []
    for cell in cells:
        ch = cell["char"]
        style = cell_style if cell["tier_kind"] == "primary" else cell["tier_kind"]
        cell_out: dict = {
            "char": ch.char,
            "unicode": f"U+{ch.unicode_hex.upper()}",
            "tier_idx": cell["tier_idx"],
            "tier_kind": cell["tier_kind"],
            "col": cell["col"],
            "row": cell["row"],
            "x_mm": round(cell["col"] * cell_pitch, 3),
            "y_mm": round(cell["row"] * cell_pitch, 3),
            "cell_style": style,
        }
        if cell["tier_kind"] == "primary":
            # Emit stroke polylines scaled to the cell's mm coord frame
            from ..ir import EM_SIZE
            scale = cell_size_mm / EM_SIZE
            strokes = []
            for s in ch.strokes:
                track = [[round(p.x * scale, 3), round(p.y * scale, 3)]
                         for p in s.track]
                strokes.append({
                    "index": s.index,
                    "kind_name": s.kind_name,
                    "has_hook": s.has_hook,
                    "track_mm": track,
                })
            cell_out["strokes"] = strokes
        cells_out.append(cell_out)

    payload = {
        "grid": {
            "chars": [c.char for c in chars],
            "N": len(chars),
            "cols": cols,
            "direction": direction,
            "grid_cols": grid_cols_n,
            "grid_rows": grid_rows_n,
            "cell_size_mm": cell_size_mm,
            "cell_gap_mm": cell_gap_mm,
            "guide": guide,
            "tier_counts": {"primary": 1, "ghost": g, "blank": b},
        },
        "cells": cells_out,
    }
    return json.dumps(payload, ensure_ascii=False, indent=indent)


__all__ = ["render_grid_svg", "save_grid_svg", "auto_tier_counts",
           "render_grid_gcode", "render_grid_json",
           "GridStyle", "CellStyle"]
