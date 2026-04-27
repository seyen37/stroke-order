"""
Shared helpers for rendering a Page object into SVG.

Both ``notebook`` and ``letter`` exporters sit on top of this. Centralises
the common logic: page background, character placement, annotations, etc.

All coordinates are in **millimetres** — the SVG viewBox is in mm, so
browsers/printers render at 1:1 physical size when the resulting file
is embedded with matching width/height attributes.
"""
from __future__ import annotations

from typing import Literal

from ..ir import EM_SIZE
from ..layouts import Annotation, GridStyle, Page, PlacedChar
from .svg import _outline_path_d, _track_points_str


CellStyle = Literal["outline", "trace", "filled", "ghost", "blank"]


# ---------------------------------------------------------------------------
# Grid rendering helpers
# ---------------------------------------------------------------------------


def _grid_svg(style: GridStyle, page: Page) -> str:
    """SVG <g> with page-wide grid lines.

    Phase 5o changes:
    - Respects ``layout.first_line_offset_mm`` so the grid origin shifts with
      the text's initial cursor (so chars sit in the cells / on the rules).
    - Respects ``layout.direction``: ``vertical`` + ruled style draws
      vertical column-separator lines instead of horizontal row lines.
    - Shrinks the last row/column if leftover content space is smaller than
      the nominal cell — the grid closes at content_bottom (or content_left
      for 直書) to avoid overhang.
    """
    layout = page.layout
    row = layout.row_step
    col = layout.char_width_mm

    if style == "none" or row <= 0 or col <= 0:
        return ""

    direction = getattr(layout, "direction", "horizontal")
    offset = getattr(layout, "first_line_offset_mm", None)

    content_x = layout.content_x
    content_y = layout.content_y
    content_right = layout.content_right
    content_bottom = layout.content_bottom
    page_w = layout.size.width_mm

    # --- Effective grid bounds ---
    if direction == "vertical":
        # Columns stack right→left. Optional offset = distance from page right
        # to first column's LEFT edge. The grid's RIGHTMOST edge is the first
        # column's RIGHT edge.
        if offset is not None:
            first_col_left = max(content_x, page_w - offset)
            grid_right = min(content_right, first_col_left + col)
        else:
            grid_right = content_right
        grid_left = content_x
        grid_top = content_y
        grid_bottom = content_bottom
    else:
        # Rows stack top→bottom. Optional offset = distance from page top to
        # first row's BOTTOM edge (= first row bottom line). Grid top moves to
        # match so that the first row drawn aligns with the first text row.
        if offset is not None:
            grid_top = max(content_y, offset - row)
        else:
            grid_top = content_y
        grid_bottom = content_bottom
        grid_left = content_x
        grid_right = content_right

    if grid_bottom - grid_top < 0.5 or grid_right - grid_left < 0.5:
        return ""  # no space

    # --- Vertical line x-positions ---
    vlines: list[float] = []
    if direction == "vertical":
        # Step leftward from grid_right
        x = grid_right
        while x >= grid_left - 0.01:
            vlines.append(x)
            x -= col
        # Ensure grid_left is included (partial leftmost column)
        if not vlines or vlines[-1] > grid_left + 0.5:
            vlines.append(grid_left)
    else:
        x = grid_left
        while x <= grid_right + 0.01:
            vlines.append(x)
            x += col
        if not vlines or vlines[-1] < grid_right - 0.5:
            vlines.append(grid_right)

    # --- Horizontal line y-positions ---
    hlines: list[float] = []
    y = grid_top
    while y <= grid_bottom + 0.01:
        hlines.append(y)
        y += row
    if not hlines or hlines[-1] < grid_bottom - 0.5:
        hlines.append(grid_bottom)

    # Dedupe (sometimes grid_left/grid_bottom exactly matches a step)
    def _dedupe(seq):
        out = []
        for v in seq:
            if not out or abs(v - out[-1]) > 0.1:
                out.append(v)
        return out
    vlines = sorted(set(round(v, 3) for v in vlines))
    hlines = sorted(set(round(v, 3) for v in hlines))

    out = ['<g class="grid" fill="none" stroke="#c8c8c8" stroke-width="0.2">']

    if style == "ruled":
        if direction == "vertical":
            # Vertical column-separator lines (skip the outermost right edge
            # so we draw separators to the LEFT of each column; first col has
            # its separator at its left edge — students write to the right
            # of each line, just like horizontal ruled paper works upside-down).
            # We skip the rightmost line (= grid_right) so the outermost
            # column is open-topped and doesn't get an extra line.
            for x in vlines:
                if abs(x - grid_right) < 0.5:
                    continue   # skip outermost right boundary
                out.append(f'<line x1="{x:.2f}" y1="{grid_top:.2f}" '
                           f'x2="{x:.2f}" y2="{grid_bottom:.2f}"/>')
        else:
            # Horizontal row-separator lines (skip the top boundary)
            for y in hlines:
                if abs(y - grid_top) < 0.5:
                    continue
                out.append(f'<line x1="{grid_left:.2f}" y1="{y:.2f}" '
                           f'x2="{grid_right:.2f}" y2="{y:.2f}"/>')
    elif style == "square":
        for y in hlines:
            out.append(f'<line x1="{grid_left:.2f}" y1="{y:.2f}" '
                       f'x2="{grid_right:.2f}" y2="{y:.2f}"/>')
        for x in vlines:
            out.append(f'<line x1="{x:.2f}" y1="{grid_top:.2f}" '
                       f'x2="{x:.2f}" y2="{grid_bottom:.2f}"/>')
    elif style == "dotted":
        out[0] = '<g class="grid" fill="#aaaaaa">'
        for y in hlines:
            for x in vlines:
                out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.25"/>')
    out.append("</g>")
    return "\n  ".join(out)


def _zones_svg(page: Page, label: bool = False,
               show_outlines: bool = False) -> str:
    """Render reserve zones. Phase 5w:

    - ``svg_content`` is ALWAYS embedded (when present)
    - Outline + label are OPT-IN via ``show_outlines=True`` (default False,
      keeping the exported SVG clean — the interactive web preview draws its
      own blue drag-handle overlay separately in JS)
    """
    if not page.layout.reserve_zones:
        return ""
    out = ['<g class="zones">']
    for z in page.layout.reserve_zones:
        if show_outlines:
            out.append(
                f'<rect x="{z.x_mm}" y="{z.y_mm}" '
                f'width="{z.width_mm}" height="{z.height_mm}" '
                f'fill="none" stroke="#d0d0d0" stroke-width="0.3" '
                f'stroke-dasharray="2 2"/>'
            )
            if label and z.label:
                out.append(
                    f'<text x="{z.x_mm + 2}" y="{z.y_mm + 4}" '
                    f'fill="#bbb" font-size="2.5">{_xml_escape(z.label)}</text>'
                )
        if z.svg_content:
            out.append(_embed_zone_content(z))
    out.append("</g>")
    return "\n  ".join(out)


def _embed_zone_content(z) -> str:
    """Embed ``z.svg_content`` into the zone box.

    Default: **fit-within** (preserve aspect ratio, center). Set
    ``z.stretch=True`` to force-fill the zone by scaling X and Y
    independently — useful when the source SVG has outlier elements that
    inflate the bbox and fit-within leaves unwanted gaps.
    """
    content = z.svg_content
    if not content:
        return ""
    vb = z.content_viewbox
    if vb is None:
        vb = (0.0, 0.0, 100.0, 100.0)
    vb_x, vb_y, vb_w, vb_h = vb
    if vb_w <= 0 or vb_h <= 0:
        return ""
    if getattr(z, "stretch", False):
        # Phase 5u: stretch — independent sx / sy, fill zone, no aspect preserve
        sx = z.width_mm / vb_w
        sy = z.height_mm / vb_h
        dx = z.x_mm - vb_x * sx
        dy = z.y_mm - vb_y * sy
        return (f'<g class="zone-content" '
                f'transform="matrix({sx:.6f},0,0,{sy:.6f},{dx:.3f},{dy:.3f})">'
                f'{content}</g>')
    # Fit-within (D1)
    sx = z.width_mm / vb_w
    sy = z.height_mm / vb_h
    scale = min(sx, sy)
    dx = z.x_mm + (z.width_mm - vb_w * scale) / 2 - vb_x * scale
    dy = z.y_mm + (z.height_mm - vb_h * scale) / 2 - vb_y * scale
    return (f'<g class="zone-content" '
            f'transform="translate({dx:.3f},{dy:.3f}) scale({scale:.6f})">'
            f'{content}</g>')


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
              .replace(">", "&gt;").replace('"', "&quot;"))


def _char_svg(pc: PlacedChar, cell_style: CellStyle = "outline") -> str:
    """Render one placed char at its mm coords.

    The character is in canonical 2048 em coords; we scale to its cell size.

    Two rendering fallbacks handled here (Phase 5aj):

    1. Strokes with an empty ``outline`` list (e.g. hand-authored
       punctuation, Phase 5ai) are rendered as track polylines even in
       ``outline`` / ``ghost`` modes — otherwise they produce invisible
       ``Z``-only paths.
    2. ``trace`` / ``filled`` stroke-widths honour the stroke's
       ``pen_size`` when set (non-None). The Bold / Mingti style
       filters (Phase 5aj) use this to modulate rendered line weight.
    """
    if not pc.char.strokes or cell_style == "blank":
        return ""
    scale_x = pc.width_mm / EM_SIZE
    scale_y = pc.height_mm / EM_SIZE
    transform = (f'translate({pc.x_mm},{pc.y_mm}) '
                 f'scale({scale_x},{scale_y})')

    def _has_outline(s):
        return bool(s.outline)

    def _width(s, default: float) -> float:
        return s.pen_size if s.pen_size is not None else default

    parts = [f'<g transform="{transform}">']
    if cell_style in ("ghost", "outline"):
        color = "#d5d5d5" if cell_style == "ghost" else "#222"
        # Split into outline-backed and track-only groups so we pick the
        # right renderer per stroke.
        outline_strokes = [s for s in pc.char.strokes if _has_outline(s)]
        track_strokes = [s for s in pc.char.strokes if not _has_outline(s)]
        if outline_strokes:
            parts.append(f'<g fill="{color}">' +
                         "".join(f'<path d="{_outline_path_d(s)}"/>'
                                 for s in outline_strokes) + "</g>")
        if track_strokes:
            # Render empty-outline strokes (punctuation, text-fallback) as
            # polylines in the same colour. Per-stroke stroke-width honours
            # pen_size so Bold/Mingti still have an effect here.
            parts.append('<g fill="none" stroke-linecap="round" '
                         f'stroke-linejoin="round" stroke="{color}">')
            for s in track_strokes:
                w = _width(s, 40.0)
                parts.append(
                    f'<polyline stroke-width="{w}" '
                    f'points="{_track_points_str(s)}"/>'
                )
            parts.append("</g>")
    elif cell_style == "trace":
        parts.append('<g fill="none" stroke="#c22" '
                     'stroke-linecap="round" stroke-linejoin="round">')
        for s in pc.char.strokes:
            w = _width(s, 18.0)
            parts.append(
                f'<polyline stroke-width="{w}" '
                f'points="{_track_points_str(s)}"/>'
            )
        parts.append("</g>")
    else:  # "filled"
        # Outline fill (where available) for ink; track overlay for motion.
        outline_strokes = [s for s in pc.char.strokes if _has_outline(s)]
        if outline_strokes:
            parts.append('<g fill="#ccc">' +
                         "".join(f'<path d="{_outline_path_d(s)}"/>'
                                 for s in outline_strokes) + "</g>")
        parts.append('<g fill="none" stroke="#c22" '
                     'stroke-linecap="round" stroke-linejoin="round">')
        for s in pc.char.strokes:
            w = _width(s, 14.0)
            parts.append(
                f'<polyline stroke-width="{w}" '
                f'points="{_track_points_str(s)}"/>'
            )
        parts.append("</g>")
    parts.append("</g>")
    return "".join(parts)


def _annotations_svg(annotations: list[Annotation]) -> str:
    if not annotations:
        return ""
    parts = ['<g class="annotations" font-family="sans-serif">']
    for a in annotations:
        parts.append(
            f'<text x="{a.x_mm}" y="{a.y_mm}" font-size="{a.size_mm}" '
            f'fill="{_xml_escape(a.color)}">{_xml_escape(a.text)}</text>'
        )
    parts.append("</g>")
    return "".join(parts)


def _page_number_svg(page: Page, show: bool) -> str:
    if not show:
        return ""
    layout = page.layout
    y = layout.size.height_mm - 5
    x = layout.size.width_mm / 2
    return (
        f'<g class="page-number">'
        f'<text x="{x}" y="{y}" font-size="3" fill="#999" '
        f'font-family="sans-serif" text-anchor="middle">'
        f'- {page.page_num} -</text></g>'
    )


def render_page_svg(
    page: Page,
    *,
    cell_style: CellStyle = "outline",
    draw_border: bool = False,
    show_page_number: bool = True,
    show_zones: bool = True,
    show_grid: bool = True,
) -> str:
    """Render one Page into a standalone SVG string (unit = mm).

    ``show_grid`` (Phase 5af): when False, the ruled/square/dotted grid
    defined by ``layout.grid_style`` is omitted from the output. The
    layout itself is preserved — useful for a "pure text" view without
    mutating the layout spec.
    """
    layout = page.layout
    W, H = layout.size.width_mm, layout.size.height_mm
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {W} {H}" '
        f'width="{W}mm" height="{H}mm">'
    ]
    # white background
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="white"/>')
    # optional page border
    if draw_border:
        parts.append(
            f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" '
            'fill="none" stroke="#aaa" stroke-width="0.4"/>'
        )
    # grid
    if show_grid:
        g = _grid_svg(layout.grid_style, page)
        if g:
            parts.append(g)
    # reserve zones (light outline)
    if show_zones:
        z = _zones_svg(page)
        if z:
            parts.append(z)
    # characters
    if page.chars:
        parts.append('<g class="chars">')
        for pc in page.chars:
            parts.append(_char_svg(pc, cell_style=cell_style))
        parts.append("</g>")
    # Phase 5ai: SVG <text> fallback for characters with no stroke data
    # (e.g. emoji, rare symbols not in any loaded source). Rendered below
    # the chars group so stroke characters still dominate visually. Uses
    # CJK-first font-family so Chinese / Japanese characters look right;
    # viewers without those fonts installed will fall back to sans-serif.
    tgs = getattr(page, "text_glyphs", None)
    if tgs:
        parts.append('<g class="text-fallback" fill="#333" '
                     'font-family="\'Noto Sans TC\', \'PingFang TC\', '
                     '\'Microsoft JhengHei\', \'Hiragino Sans\', sans-serif">')
        for tg in tgs:
            size = min(tg.width_mm, tg.height_mm) * 0.8
            cx = tg.x_mm + tg.width_mm / 2
            # Baseline ~78% down the cell lines the glyph visually
            # close to where a Han character's ink box would sit.
            cy = tg.y_mm + tg.height_mm * 0.78
            parts.append(
                f'<text x="{cx:.2f}" y="{cy:.2f}" '
                f'font-size="{size:.2f}" text-anchor="middle">'
                f'{_xml_escape(tg.char)}</text>'
            )
        parts.append("</g>")
    # annotations
    parts.append(_annotations_svg(page.annotations))
    # page number footer
    parts.append(_page_number_svg(page, show_page_number))
    parts.append("</svg>")
    return "\n".join(parts)


__all__ = ["render_page_svg", "CellStyle"]
