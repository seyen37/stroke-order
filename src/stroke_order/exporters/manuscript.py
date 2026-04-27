"""
稿紙 mode — traditional Chinese manuscript paper (A4).

Two commercial formats are supported via ``preset``:

- ``"300"`` (default): 25 rows × 12 columns = 300 字 (matches reference PDF).
- ``"200"``: 20 rows × 10 columns = 200 字 (larger cells, more spacious).

Shared properties across presets:

- A4 portrait, vertical writing (直書): chars flow top→bottom within a
  column; columns flow right→left across the page.
- Each column is a PAIR of cells — a wider LEFT box (character) and
  a narrower RIGHT box (注音 zhuyin annotation) — matching traditional
  zhuyin placement for vertical text.

Only the four margins (top/bottom/left/right) are user-tunable. The
row/column count, paper size, and writing direction are fixed by the
preset. An advanced ``zhuyin_width_mm`` parameter is exposed for power
users who want to tune the annotation gutter.

Implementation note
-------------------
To reuse ``flow_text`` without any custom vertical-flow logic, we
internally inflate ``margin_right`` by ``zhuyin_width_mm`` so that
``content_right`` lands on the RIGHT edge of the character-column band.
The flow engine then positions character cells correctly and the grid
renderer reaches back INTO the inflated margin to draw the zhuyin
cells. ``line_spacing_mm`` is set to ``zhuyin_width_mm`` to produce the
correct column step (``char_w + zhuyin_w``) without affecting row
spacing (vertical flow steps rows by ``line_height_mm`` only).
"""
from __future__ import annotations

from typing import Iterable, Optional

from ..layouts import (
    Annotation, Page, PageLayout, PageSize,
    flow_text, layout_capacity,
)
from .page import CellStyle, render_page_svg


# Commercial A4 manuscript-paper formats
MANUSCRIPT_PAPER = "A4"
MANUSCRIPT_PRESETS: dict[str, dict] = {
    "300": {"rows": 25, "cols": 12, "capacity": 300},   # reference PDF
    "200": {"rows": 20, "cols": 10, "capacity": 200},   # spacious variant
}
DEFAULT_MANUSCRIPT_PRESET = "300"

# Back-compat constants — point at the default preset so legacy imports
# (``from stroke_order.exporters.manuscript import MANUSCRIPT_ROWS``)
# keep working.
MANUSCRIPT_ROWS = MANUSCRIPT_PRESETS[DEFAULT_MANUSCRIPT_PRESET]["rows"]
MANUSCRIPT_COLS = MANUSCRIPT_PRESETS[DEFAULT_MANUSCRIPT_PRESET]["cols"]
MANUSCRIPT_CAPACITY = MANUSCRIPT_PRESETS[DEFAULT_MANUSCRIPT_PRESET]["capacity"]

# Default margin (mm) tuned to match the reference PDF layout.
_DEFAULT_MARGIN_MM = 15.0
# Default zhuyin cell width as a fraction of the pair width.
# 1/3 → char:zhuyin = 2:1, matching the reference PDF.
_DEFAULT_ZHUYIN_FRACTION = 1.0 / 3.0


def _resolve_preset(preset: str) -> dict:
    if preset not in MANUSCRIPT_PRESETS:
        raise ValueError(
            f"unknown manuscript preset {preset!r}; "
            f"valid: {sorted(MANUSCRIPT_PRESETS)}"
        )
    return MANUSCRIPT_PRESETS[preset]


def _derive_dims(
    *,
    preset: str,
    margin_top_mm: float,
    margin_bottom_mm: float,
    margin_left_mm: float,
    margin_right_mm: float,
    zhuyin_width_mm: Optional[float],
) -> tuple[float, float, float, float]:
    """Return ``(char_w, zhuyin_w, cell_h, pair_w)`` for the chosen preset.

    Raises ``ValueError`` if the chosen margins leave no room for content.
    """
    p = _resolve_preset(preset)
    rows, cols = p["rows"], p["cols"]
    page = PageSize.named(MANUSCRIPT_PAPER)
    content_w = page.width_mm - margin_left_mm - margin_right_mm
    content_h = page.height_mm - margin_top_mm - margin_bottom_mm
    if content_w <= 0 or content_h <= 0:
        raise ValueError(
            "margins too large — content area would be non-positive "
            f"(w={content_w:.1f}mm, h={content_h:.1f}mm)"
        )
    pair_w = content_w / cols
    cell_h = content_h / rows
    if zhuyin_width_mm is None:
        zhuyin_w = pair_w * _DEFAULT_ZHUYIN_FRACTION
    else:
        # Clamp so char cell retains at least 10% of pair width.
        zhuyin_w = max(0.0, min(float(zhuyin_width_mm), pair_w * 0.9))
    char_w = pair_w - zhuyin_w
    return char_w, zhuyin_w, cell_h, pair_w


def build_manuscript_layout(
    *,
    preset: str = DEFAULT_MANUSCRIPT_PRESET,
    margin_top_mm: float = _DEFAULT_MARGIN_MM,
    margin_bottom_mm: float = _DEFAULT_MARGIN_MM,
    margin_left_mm: float = _DEFAULT_MARGIN_MM,
    margin_right_mm: float = _DEFAULT_MARGIN_MM,
    zhuyin_width_mm: Optional[float] = None,
) -> PageLayout:
    """Build the PageLayout for one manuscript page.

    ``preset`` picks the grid: ``"300"`` (25×12) or ``"200"`` (20×10).
    Default = ``"300"`` matches the reference manuscript paper.

    The returned layout:
    - ``char_width_mm`` / ``line_height_mm`` — size of the CHARACTER cell
      (what the flow engine writes into).
    - ``line_spacing_mm`` — equals zhuyin width, producing the pair-wide
      column step without affecting row spacing (vertical flow only uses
      ``line_height_mm`` between rows).
    - ``margin_right_mm`` — inflated by zhuyin width relative to the
      user-visible margin, so ``flow_text``'s ``content_right`` lands on
      the right edge of the character-column band. The grid renderer
      draws zhuyin cells into that phantom-margin strip.
    """
    char_w, zhuyin_w, cell_h, _pair_w = _derive_dims(
        preset=preset,
        margin_top_mm=margin_top_mm, margin_bottom_mm=margin_bottom_mm,
        margin_left_mm=margin_left_mm, margin_right_mm=margin_right_mm,
        zhuyin_width_mm=zhuyin_width_mm,
    )
    page = PageSize.named(MANUSCRIPT_PAPER)
    return PageLayout(
        size=page,
        margin_top_mm=margin_top_mm,
        margin_bottom_mm=margin_bottom_mm,
        margin_left_mm=margin_left_mm,
        margin_right_mm=margin_right_mm + zhuyin_w,   # inflated for flow math
        line_height_mm=cell_h,
        char_width_mm=char_w,
        grid_style="none",          # we draw our own pair grid
        line_spacing_mm=zhuyin_w,   # col_step = char_w + zhuyin_w = pair_w
        direction="vertical",
    )


def flow_manuscript(
    text: str,
    char_loader,
    *,
    preset: str = DEFAULT_MANUSCRIPT_PRESET,
    margin_top_mm: float = _DEFAULT_MARGIN_MM,
    margin_bottom_mm: float = _DEFAULT_MARGIN_MM,
    margin_left_mm: float = _DEFAULT_MARGIN_MM,
    margin_right_mm: float = _DEFAULT_MARGIN_MM,
    zhuyin_width_mm: Optional[float] = None,
    annotations: Optional[Iterable[Annotation]] = None,
) -> list[Page]:
    """Lay out ``text`` onto manuscript pages.

    Chars-per-page depends on the preset (300 or 200). Longer text
    auto-paginates (page 2 starts again at top-right of a fresh page).
    """
    layout = build_manuscript_layout(
        preset=preset,
        margin_top_mm=margin_top_mm, margin_bottom_mm=margin_bottom_mm,
        margin_left_mm=margin_left_mm, margin_right_mm=margin_right_mm,
        zhuyin_width_mm=zhuyin_width_mm,
    )
    pages = flow_text(text, layout, char_loader, direction="vertical")
    if annotations and pages:
        pages[0].annotations = list(annotations)
    return pages


def _rows_cols_from_layout(layout: PageLayout) -> tuple[int, int]:
    """Derive (rows, cols) from an already-built manuscript PageLayout.

    We don't need to know the preset name at render time: ``cols`` is the
    count of ``pair_w`` widths that fit in the USER-visible content width
    (i.e. ignoring the inflated zhuyin margin), and ``rows`` is the count
    of ``cell_h`` heights that fit in the content height. The divisions
    are exact-by-construction, so ``round(...)`` just absorbs any FP
    drift from the derivation.
    """
    pair_w = layout.char_width_mm + layout.line_spacing_mm
    cell_h = layout.line_height_mm
    page_w = layout.size.width_mm
    page_h = layout.size.height_mm
    # layout.margin_right_mm is inflated by zhuyin_w; recover user margin.
    user_margin_right = layout.margin_right_mm - layout.line_spacing_mm
    content_w_user = page_w - layout.margin_left_mm - user_margin_right
    content_h = page_h - layout.margin_top_mm - layout.margin_bottom_mm
    cols = max(1, int(round(content_w_user / pair_w)))
    rows = max(1, int(round(content_h / cell_h)))
    return rows, cols


def _grid_svg_manuscript(layout: PageLayout) -> str:
    """Draw the pair grid (char box + zhuyin box per cell). Grid
    dimensions come from the layout so the same function serves every
    preset (300 字 = 25×12, 200 字 = 20×10, and any future variant).
    """
    cell_h = layout.line_height_mm
    char_w = layout.char_width_mm
    zhuyin_w = layout.line_spacing_mm
    pair_w = char_w + zhuyin_w
    page_w = layout.size.width_mm

    # Right edge of the char-column band (char cells stop here; zhuyin
    # cells extend into the phantom-inflated margin on the right).
    char_band_right = page_w - layout.margin_right_mm
    content_top = layout.margin_top_mm
    rows, cols = _rows_cols_from_layout(layout)

    parts: list[str] = [
        '<g class="manuscript-grid" fill="none" stroke="#888" stroke-width="0.25">'
    ]
    for col in range(cols):
        # col=0 is the RIGHTMOST column (first column the user writes in).
        char_right = char_band_right - col * pair_w
        char_left = char_right - char_w
        zhu_left = char_right
        for row in range(rows):
            y_top = content_top + row * cell_h
            # Character cell — heavier outline
            parts.append(
                f'<rect x="{char_left:.3f}" y="{y_top:.3f}" '
                f'width="{char_w:.3f}" height="{cell_h:.3f}"/>'
            )
            # Zhuyin cell — lighter outline for visual hierarchy
            if zhuyin_w > 0.05:
                parts.append(
                    f'<rect x="{zhu_left:.3f}" y="{y_top:.3f}" '
                    f'width="{zhuyin_w:.3f}" height="{cell_h:.3f}" '
                    f'stroke="#bbb" stroke-width="0.15"/>'
                )
    parts.append('</g>')
    return ''.join(parts)


def render_manuscript_page_svg(
    page: Page,
    *,
    cell_style: CellStyle = "outline",
    show_page_number: bool = True,
    show_grid: bool = True,
) -> str:
    """Render one manuscript page.

    ``show_grid`` (Phase 5af): when False, the pair-cell grid (char boxes
    + zhuyin boxes) is omitted so only the character strokes remain on
    the page. Useful for a "pure text" view.
    """
    base = render_page_svg(
        page, cell_style=cell_style, draw_border=True,
        show_page_number=show_page_number, show_zones=False,
        show_grid=show_grid,
    )
    if not show_grid:
        # Manuscript pair grid lives separately from the generic grid
        # handled by render_page_svg, so also skip it here.
        return base
    grid = _grid_svg_manuscript(page.layout)
    # Place grid BENEATH the characters for correct z-order. If the chars
    # group is present, insert right before it; otherwise fall back to
    # inserting before </svg>.
    chars_anchor = '<g class="chars">'
    if chars_anchor in base:
        return base.replace(chars_anchor, grid + "\n" + chars_anchor, 1)
    return base.replace("</svg>", grid + "\n</svg>", 1)


# ---------------------------------------------------------------------------
# G-code / JSON exports — thin wrappers over notebook's generic page engines
# ---------------------------------------------------------------------------


def render_manuscript_gcode(
    pages: list[Page],
    *,
    cell_style: CellStyle = "outline",
    feed_rate: int = 3000,
    travel_rate: int = 6000,
    pen_up_cmd: str = "M5",
    pen_down_cmd: str = "M3 S90",
    pen_dwell_sec: float = 0.15,
    flip_y: bool = False,
) -> str:
    """Emit G-code for manuscript pages. Only body strokes are written —
    the printed grid and zhuyin cells are paper pre-print, not robot output."""
    from .notebook import render_notebook_gcode
    code = render_notebook_gcode(
        pages,
        cell_style=cell_style, feed_rate=feed_rate, travel_rate=travel_rate,
        pen_up_cmd=pen_up_cmd, pen_down_cmd=pen_down_cmd,
        pen_dwell_sec=pen_dwell_sec, flip_y=flip_y,
    )
    # Derive the grid dimensions from the first page's layout so the
    # banner reflects the actual preset the caller picked.
    if pages:
        rows, cols = _rows_cols_from_layout(pages[0].layout)
    else:
        rows, cols = MANUSCRIPT_ROWS, MANUSCRIPT_COLS
    return code.replace(
        "; --- stroke-order 筆記 G-code ---",
        f"; --- stroke-order 稿紙 G-code ---\n"
        f"; ({rows}×{cols}={rows*cols} grid is pre-printed; "
        f"robot writes only character strokes)",
        1,
    )


def render_manuscript_json(
    pages: list[Page],
    *,
    cell_style: CellStyle = "outline",
    indent: int = 2,
) -> str:
    """Render manuscript pages as JSON. Top-level key is "manuscript" and
    carries the fixed grid dimensions (rows / cols / capacity)."""
    import json as _json
    from .notebook import render_notebook_json
    base = _json.loads(
        render_notebook_json(pages, cell_style=cell_style, indent=indent)
    )
    meta = base.pop("notebook")
    # Attach manuscript-specific metadata — derive from the actual pages'
    # layout rather than module-level defaults so 200/300 presets both emit
    # correct grid dimensions.
    if pages:
        rows, cols = _rows_cols_from_layout(pages[0].layout)
    else:
        rows, cols = MANUSCRIPT_ROWS, MANUSCRIPT_COLS
    meta["rows"] = rows
    meta["cols"] = cols
    meta["chars_per_page"] = rows * cols
    base["manuscript"] = meta
    return _json.dumps(base, ensure_ascii=False, indent=indent)


__all__ = [
    "MANUSCRIPT_ROWS",
    "MANUSCRIPT_COLS",
    "MANUSCRIPT_CAPACITY",
    "MANUSCRIPT_PRESETS",
    "DEFAULT_MANUSCRIPT_PRESET",
    "build_manuscript_layout",
    "flow_manuscript",
    "render_manuscript_page_svg",
    "render_manuscript_gcode",
    "render_manuscript_json",
]
