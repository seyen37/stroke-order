"""
Sutra (抄經) mode — A4 landscape vector pages for a writing-robot/plotter
to draw onto blank A4 paper, producing trace-style pages users can then
overwrite by hand.

Layout (per body page)
----------------------
- A4 landscape (297 × 210 mm)
- 20 columns × 15 rows = 300 cells per page
- **Right-to-left vertical** reading order — the cell at column 0 (right
  edge) row 0 (top) holds char #0; chars flow top→bottom within a column,
  then move one column to the LEFT for char 15.
- Each cell carries a faint 米字 (eight-point) dotted helper grid.
- Outer rectangle is a thick black frame; inter-cell grid is a thin grey.
- Header: 「日期：____」「抄寫者：____」 — both label and underline are
  emitted as vector glyphs/lines so the plotter draws them too.
- Footer: optional signature text (default 「時時抄經」).

Page types
----------
- ``cover``      : large title + subtitle + scribe field
- ``body``       : trace-style page with a slice of the text
- ``dedication`` : tail page with a dedication verse + 弟子/迴向 fill-ins

Trace styling
-------------
Body pages render character outlines as **fill** in a light grey
(``trace_fill``, default ``#cccccc``) rather than as stroked outlines.
The plotter draws the outlines; once printed, the character looks faded
enough to be overwritten by hand.

Reuses :func:`stroke_order.exporters.patch._char_cut_paths` for glyph
embedding — that helper emits raw ``<path d=...>`` elements with no
stroke/fill of their own, so we just set the desired colour on our outer
``<g>`` wrapper.
"""
from __future__ import annotations

import math
import unicodedata
from typing import Callable, Iterable, Literal, Optional

from ..ir import Character, EM_SIZE
from ..sutras import SUTRAS, SutraInfo, load_text, text_to_chars
from .patch import _char_cut_paths, _char_write_polylines

# 5bw / 5bx / 5by: stroke-width for skeleton-fallback glyphs as a *ratio*
# of char_size (not a fixed mm value). 隸書/篆書 default to skeleton mode
# (outline=[], centerline tracks only), so we render them as stroked
# polylines. A filled outline glyph (楷/宋) covers ~30-40% of its bbox
# in pixel area; a single centerline at the same width would cover < 5%
# and read as far fainter — a confusingly thin trace hint.
#
# Calibrating from real font data: a typical kaishu brush stroke is
# ~10-13% of the glyph's height. We pick 0.12 (12%) so the skeleton's
# visual weight matches real handwriting, and the line scales with the
# page geometry — landscape gets ~1.13mm, portrait ~1.33mm — keeping
# both orientations equally legible without further tuning.
_SKELETON_TRACE_STROKE_RATIO = 0.12

# 5ca / 5cb: skeleton-group opacity.
#
# Earlier (5ca) we matched skeleton and reference at 0.55 each so they
# read as a single, even 描紅 grey. In practice the skeletonization
# algorithm produces incomplete or slightly mispositioned centerlines
# for some glyphs (Zhang-Suen thinning struggles with very thin or
# branching strokes), and a visible skeleton with mistakes is more
# distracting than helpful — the user has the reference letterform
# layer for shape guidance.
#
# 0.03 effectively makes the skeleton an extremely faint hint:
#   - Browsers still render it (vector-effect=non-scaling-stroke ensures
#     the 1.13mm width survives the inner EM scale).
#   - Laser printers may dither it into white below ~5% grey, which is
#     fine for the print-to-trace use case — the printed page reads as
#     "reference-only", with the skeleton effectively invisible.
#   - The polylines remain in the SVG, so we keep the option to dial
#     this back up later without re-plumbing.
_SKELETON_TRACE_OPACITY = 0.03


def _render_skeleton_glyph(c: Character, x_mm: float, y_mm: float,
                            size_mm: float) -> str:
    """Render a Character via its centerline ``raw_track`` polylines —
    used by sutra body when ``_char_cut_paths`` returns empty (skeleton-
    mode 隸書/篆書 produce no outline data).

    The glyph is wrapped in a ``<g transform="... scale(EM→mm)">`` to
    place each track in mm space. Crucially, every ``<polyline>`` carries
    ``vector-effect="non-scaling-stroke"`` so the outer trace-skeleton
    group's ``stroke-width`` (in mm) is honoured regardless of the inner
    scale transform — without this, the stroke would shrink by ~217×
    (EM_SIZE / size_mm) and render as a sub-pixel hairline. cairosvg ≥
    2.5 honours this attribute, matching browser behaviour.
    """
    if not c.strokes:
        return ""
    scale = size_mm / EM_SIZE
    half = size_mm / 2.0
    parts: list[str] = []
    for stroke in c.strokes:
        track = stroke.smoothed_track or stroke.raw_track
        if track and len(track) >= 2:
            pts = " ".join(f"{p.x:.2f},{p.y:.2f}" for p in track)
            parts.append(
                f'<polyline points="{pts}" '
                f'vector-effect="non-scaling-stroke"/>'
            )
    if not parts:
        return ""
    return (f'<g transform="translate({x_mm - half:.3f},{y_mm - half:.3f}) '
            f'scale({scale:.6f})">{"".join(parts)}</g>')


# 5bu: render the 句讀 mark as an SVG <text> element using the system's
# built-in CJK font, instead of tracing the punctuation source's polylines.
# Visual quality is much higher at small sizes, and Unicode 全形 punctuation
# already centres itself inside its glyph box — no bbox math needed.
_MARK_FONT_STACK = (
    "'Noto Sans CJK TC', 'Noto Serif CJK TC', "
    "'Microsoft JhengHei', 'PingFang TC', 'PMingLiU', "
    "'SimSun', 'Source Han Sans TC', sans-serif"
)


def _xml_escape_char(ch: str) -> str:
    return (ch.replace("&", "&amp;").replace("<", "&lt;")
              .replace(">", "&gt;").replace('"', "&quot;"))


def _render_mark_text(mark_ch: str, x_mm: float, y_mm: float,
                       size_mm: float) -> str:
    """Render a 句讀 mark as a centred <text> element at (x, y) with
    ``size_mm`` font-size. Relies on a CJK system font being available."""
    if not mark_ch:
        return ""
    return (
        f'<text x="{x_mm:.3f}" y="{y_mm:.3f}" '
        f'font-size="{size_mm:.3f}" '
        f'font-family="{_MARK_FONT_STACK}" '
        f'text-anchor="middle" dominant-baseline="central">'
        f'{_xml_escape_char(mark_ch)}</text>'
    )


# Legacy polyline/path renderer kept for fallback use; no longer the
# primary mark renderer.
def _render_mark_glyph(c: "Character", x_mm: float, y_mm: float,
                        size_mm: float) -> str:
    """Render a punctuation glyph so its bbox centre lands at (x, y),
    while preserving the natural per-glyph size relative to a canonical
    ``size_mm × size_mm`` EM-box display size.
    """
    if not c.strokes:
        return ""
    all_x: list[float] = []
    all_y: list[float] = []
    for s in c.strokes:
        track = s.smoothed_track or s.raw_track
        if track:
            all_x.extend(p.x for p in track)
            all_y.extend(p.y for p in track)
        if s.outline:
            for cmd in s.outline:
                if "x" in cmd and "y" in cmd:
                    all_x.append(cmd["x"])
                    all_y.append(cmd["y"])
    if not all_x or not all_y:
        return ""
    bbox_cx = (min(all_x) + max(all_x)) / 2.0
    bbox_cy = (min(all_y) + max(all_y)) / 2.0
    # 5br: uniform EM-based scale; bbox is used for centring only.
    scale = size_mm / EM_SIZE
    dx = x_mm - bbox_cx * scale
    dy = y_mm - bbox_cy * scale
    parts: list[str] = []
    for s in c.strokes:
        if s.outline:
            from .patch import _outline_path_d
            d = _outline_path_d(s)
            if d:
                parts.append(f'<path d="{d}"/>')
    for s in c.strokes:
        if not s.outline:
            track = s.smoothed_track or s.raw_track
            if track and len(track) >= 2:
                pts = " ".join(f"{p.x:.2f},{p.y:.2f}" for p in track)
                parts.append(f'<polyline points="{pts}"/>')
    if not parts:
        return ""
    return (f'<g transform="translate({dx:.3f},{dy:.3f}) '
            f'scale({scale:.6f})">{"".join(parts)}</g>')


# ---------------------------------------------------------------------------
# Page geometry
# ---------------------------------------------------------------------------

PAGE_W_MM = 297.0
PAGE_H_MM = 210.0
COLS = 20
ROWS = 15
CELLS_PER_PAGE = COLS * ROWS  # 300

# Default margins (mm). Tuned to leave room for header + footer.
DEFAULT_MARGIN_TOP_MM    = 22.0    # extra room for header text + underline
DEFAULT_MARGIN_BOTTOM_MM = 22.0    # extra room for footer signature
DEFAULT_MARGIN_LEFT_MM   = 14.0
DEFAULT_MARGIN_RIGHT_MM  = 14.0

# Visual styling
TRACE_FILL_DEFAULT   = "#cccccc"   # faded glyph fill
INK_FILL             = "#000000"   # title / header text
GRID_LINE_COLOR      = "#888888"   # thin cell border
GRID_LINE_WIDTH      = 0.15
HELPER_LINE_COLOR    = "#cccccc"
HELPER_LINE_WIDTH    = 0.10
HELPER_DASH          = "0.5,0.5"
OUTER_FRAME_COLOR    = "#000000"
OUTER_FRAME_WIDTH    = 0.6
HEADER_LABEL_COLOR   = "#000000"
HEADER_UNDERLINE_COLOR = "#000000"

PageType = Literal["cover", "body", "dedication"]
TextMode = Literal["compact", "compact_marks", "with_punct", "raw"]
PaperOrientation = Literal["landscape", "portrait"]
TextDirection = Literal["vertical", "horizontal"]
# 5bv: how to render the 句讀 marks.
#   "text"     — SVG <text> element with a CJK font stack (default).
#                Best visual quality in browser previews; depends on the
#                renderer having a CJK system font installed.
#   "polyline" — Trace the punctuation glyph via char_loader and emit
#                <path>/<polyline>. Zero font dependency, so the PDF
#                pipeline (cairosvg → server-side raster) renders it
#                identically on any host.
MarkRenderer = Literal["text", "polyline"]
CharLoader = Callable[[str], Optional[Character]]


# ---------------------------------------------------------------------------
# Phase 5bj: page geometry — landscape default + portrait variant.
# Each orientation keeps the **same 300-cell capacity** but swaps the grid
# shape (20×15 ↔ 15×20) and the page dimensions.
# ---------------------------------------------------------------------------


from dataclasses import dataclass


@dataclass(frozen=True)
class PageGeometry:
    page_w_mm: float
    page_h_mm: float
    cols: int
    rows: int

    @property
    def cells_per_page(self) -> int:
        return self.cols * self.rows


_GEOMETRIES: dict[str, PageGeometry] = {
    # Default: A4 landscape, 20 cols × 15 rows = 300 cells (matches reference).
    "landscape": PageGeometry(297.0, 210.0, 20, 15),
    # Portrait variant: A4 portrait, 15 cols × 20 rows = still 300 cells.
    "portrait":  PageGeometry(210.0, 297.0, 15, 20),
}


def get_geometry(orientation: PaperOrientation = "landscape") -> PageGeometry:
    return _GEOMETRIES.get(orientation, _GEOMETRIES["landscape"])


# ---------------------------------------------------------------------------
# Phase 5bh: text preparation modes
# ---------------------------------------------------------------------------
#
# Three modes for laying chars into 300-cell grid pages:
#   - "compact"     (default) — drop ALL whitespace + punctuation; every cell
#                                holds a real glyph (one 字 per cell).
#   - "with_punct"  — keep punctuation; apply line-head 禁則 (no closing punct
#                                at column top) + paragraph alignment (each
#                                paragraph starts at the top of a new column).
#   - "raw"         — original behaviour: one cell per char including punct
#                                and whitespace. Preserved for back-compat.

# Closing punctuation forbidden at line-head (top of a column).
# When such a char would land at index k * ROWS, we swap it with the prior
# cell so it ends up at the bottom of the previous column instead.
_LINE_HEAD_FORBIDDEN: frozenset[str] = frozenset(
    "。，、！？；：）」』》】〉〗·…—｡､：；！？)]}>"
)


def _is_real_glyph(ch: str) -> bool:
    """Return True if ``ch`` should occupy a cell in compact mode.

    Letters (CJK + ASCII) and numbers count as glyphs; punctuation and
    whitespace do not.
    """
    if not ch:
        return False
    cat = unicodedata.category(ch)
    return cat[0] in ("L", "N")


def prepare_text(text: str, mode: TextMode = "compact",
                  *, rows: int = ROWS) -> list[str]:
    """Convert raw text into the per-cell token list for a sutra-mode page.

    The returned list is then sliced into per-page chunks.
    Empty-string entries are placeholders that render as blank cells.

    ``rows`` controls the column-stride for ``with_punct`` mode (paragraph
    alignment + 行首禁則). Defaults to module-level ROWS (15, landscape).
    Pass the per-orientation rows for portrait (=20).

    Modes:
        compact         drop punctuation + whitespace; one 字 per cell.
        compact_marks   like compact (marks via prepare_text_with_marks).
        with_punct      keep punctuation; paragraph alignment + 行首禁則.
        raw             one char per cell incl. whitespace as blank.
    """
    if not text:
        return []
    if mode in ("compact", "compact_marks"):
        return [c for c in text if _is_real_glyph(c)]

    if mode == "raw":
        # Whitespace stays as a blank cell, everything else is a glyph.
        return ["" if c.isspace() else c for c in text]

    # "with_punct" — keep punctuation, apply paragraph + line-head rules.
    cells: list[str] = []
    paragraphs = text.split("\n")
    for p_idx, para in enumerate(paragraphs):
        # Drop horizontal whitespace inside a paragraph (we don't want
        # mid-paragraph spaces to consume cells).
        para = "".join(c for c in para if not c.isspace())
        if not para:
            continue
        # Paragraph alignment: pad the previous column to its bottom so this
        # paragraph starts at the top of a new column.
        if p_idx > 0 and (len(cells) % rows) != 0:
            pad = rows - (len(cells) % rows)
            cells.extend([""] * pad)
        cells.extend(para)

    # Line-head 禁則: a forbidden punctuation at column-top (cell index
    # divisible by rows, k>0) gets swapped with the cell above it.
    n = len(cells)
    for col_top in range(rows, n, rows):
        if cells[col_top] and cells[col_top] in _LINE_HEAD_FORBIDDEN:
            # Move the punct up one cell to the bottom of the previous column.
            cells[col_top - 1], cells[col_top] = (
                cells[col_top], cells[col_top - 1] or ""
            )
    return cells


# Punctuation that participates in 古籍 sentence-marking (句讀). When a
# run of punct sits between two glyphs in compact_marks mode, we keep the
# *first* one and attach it to the previous cell as a tiny mark.
_SENTENCE_PUNCT: frozenset[str] = frozenset(
    "，。、；：！？〃·…—｡､：；！？!?;,."
)


def prepare_text_with_marks(text: str) -> tuple[list[str], list[str]]:
    """Compact-mode tokens **plus** a parallel list of "句讀" marks.

    For each glyph, the corresponding ``marks[i]`` is either ``""`` (no
    punctuation followed this glyph in the source) or the first sentence-
    punctuation char that immediately followed it. The render layer then
    draws the mark below the glyph cell as a faded mini-glyph.

    Only sentence-marking punct counts (closing punct, period, comma,
    pause, semicolon, colon, exclamation, question). Brackets / quotes
    are ignored — they wouldn't be drawn as 句讀 marks anyway.
    """
    if not text:
        return [], []
    cells: list[str] = []
    marks: list[str] = []
    pending_mark: str = ""
    for ch in text:
        if _is_real_glyph(ch):
            # Attach the buffered mark to the *previous* cell (if any),
            # then push this glyph with no mark yet.
            if pending_mark and cells:
                marks[-1] = pending_mark
            pending_mark = ""
            cells.append(ch)
            marks.append("")
        elif ch in _SENTENCE_PUNCT:
            if not pending_mark:        # keep only the first punct in a run
                pending_mark = ch
        # else: bracket/quote/whitespace → ignored
    return cells, marks


# ---------------------------------------------------------------------------
# Text-to-page slicing
# ---------------------------------------------------------------------------


def total_body_pages(text: str, mode: TextMode = "compact",
                      *, orientation: PaperOrientation = "landscape") -> int:
    """How many body pages does ``text`` need under ``mode`` + orientation?"""
    if not text:
        return 0
    geom = get_geometry(orientation)
    cells = prepare_text(text, mode, rows=geom.rows)
    if not cells:
        return 0
    cap = geom.cells_per_page
    return (len(cells) + cap - 1) // cap


def page_slice(
    text: str, page_index: int, mode: TextMode = "compact",
    *, orientation: PaperOrientation = "landscape",
) -> list[str]:
    """Return the per-cell tokens for body page ``page_index`` (0-based)."""
    geom = get_geometry(orientation)
    cells = prepare_text(text, mode, rows=geom.rows)
    cap = geom.cells_per_page
    start = page_index * cap
    end = start + cap
    return cells[start:end]


def page_slice_with_marks(
    text: str, page_index: int,
    *, orientation: PaperOrientation = "landscape",
) -> tuple[list[str], list[str]]:
    """Compact_marks variant: returns (cells, marks) for one body page."""
    geom = get_geometry(orientation)
    cells, marks = prepare_text_with_marks(text)
    cap = geom.cells_per_page
    start = page_index * cap
    end = start + cap
    return cells[start:end], marks[start:end]


# ---------------------------------------------------------------------------
# Cell layout (right-to-left vertical)
# ---------------------------------------------------------------------------


def _cell_size(geom: PageGeometry,
               margin_top_mm: float, margin_bottom_mm: float,
               margin_left_mm: float, margin_right_mm: float
               ) -> tuple[float, float]:
    """Return (cell_width_mm, cell_height_mm) for the body grid."""
    inner_w = geom.page_w_mm - margin_left_mm - margin_right_mm
    inner_h = geom.page_h_mm - margin_top_mm - margin_bottom_mm
    return inner_w / geom.cols, inner_h / geom.rows


def _cell_origin(col: int, row: int, *,
                 geom: PageGeometry,
                 direction: TextDirection,
                 margin_top_mm: float,
                 margin_left_mm: float,
                 margin_right_mm: float,
                 cell_w: float, cell_h: float) -> tuple[float, float]:
    """Top-left corner (x, y) of the cell at logical (col, row).

    Direction:
        - "vertical"  : col=0 is the RIGHTMOST column (右起直書)
        - "horizontal": col=0 is the LEFTMOST column (左起橫書)
    """
    if direction == "vertical":
        x = geom.page_w_mm - margin_right_mm - (col + 1) * cell_w
    else:
        x = margin_left_mm + col * cell_w
    y = margin_top_mm + row * cell_h
    return x, y


def _index_to_cell(n: int, *, geom: PageGeometry,
                   direction: TextDirection) -> tuple[int, int]:
    """Linear char index → (col, row).

    - vertical  : col-major (chars flow top→bottom in a column,
                  then move to the next column to the LEFT).
    - horizontal: row-major (chars flow left→right across a row,
                  then drop to the next row).
    """
    if direction == "vertical":
        return n // geom.rows, n % geom.rows
    return n % geom.cols, n // geom.cols


# ---------------------------------------------------------------------------
# Grid + helper-line emitters
# ---------------------------------------------------------------------------


def _outer_frame(geom: PageGeometry,
                 margin_top_mm: float, margin_bottom_mm: float,
                 margin_left_mm: float, margin_right_mm: float) -> str:
    x = margin_left_mm
    y = margin_top_mm
    w = geom.page_w_mm - margin_left_mm - margin_right_mm
    h = geom.page_h_mm - margin_top_mm - margin_bottom_mm
    return (
        f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" '
        f'fill="none" stroke="{OUTER_FRAME_COLOR}" '
        f'stroke-width="{OUTER_FRAME_WIDTH}"/>'
    )


def _grid_lines(geom: PageGeometry,
                margin_top_mm: float, margin_bottom_mm: float,
                margin_left_mm: float, margin_right_mm: float) -> str:
    """Thin horizontal + vertical lines dividing the body grid."""
    cell_w, cell_h = _cell_size(geom, margin_top_mm, margin_bottom_mm,
                                 margin_left_mm, margin_right_mm)
    inner_left = margin_left_mm
    inner_right = geom.page_w_mm - margin_right_mm
    inner_top = margin_top_mm
    inner_bottom = geom.page_h_mm - margin_bottom_mm
    parts: list[str] = []
    # Verticals (column separators)
    for c in range(1, geom.cols):
        x = inner_left + c * cell_w
        parts.append(
            f'<line x1="{x:.3f}" y1="{inner_top:.3f}" '
            f'x2="{x:.3f}" y2="{inner_bottom:.3f}" '
            f'stroke="{GRID_LINE_COLOR}" stroke-width="{GRID_LINE_WIDTH}"/>'
        )
    # Horizontals (row separators)
    for r in range(1, geom.rows):
        y = inner_top + r * cell_h
        parts.append(
            f'<line x1="{inner_left:.3f}" y1="{y:.3f}" '
            f'x2="{inner_right:.3f}" y2="{y:.3f}" '
            f'stroke="{GRID_LINE_COLOR}" stroke-width="{GRID_LINE_WIDTH}"/>'
        )
    return "".join(parts)


def _helper_lines(geom: PageGeometry,
                  direction: TextDirection,
                  margin_top_mm: float, margin_bottom_mm: float,
                  margin_left_mm: float, margin_right_mm: float) -> str:
    """Per-cell 米字 dotted helper guides (cross + two diagonals)."""
    cell_w, cell_h = _cell_size(geom, margin_top_mm, margin_bottom_mm,
                                 margin_left_mm, margin_right_mm)
    parts: list[str] = []
    for col in range(geom.cols):
        for row in range(geom.rows):
            x0, y0 = _cell_origin(
                col, row,
                geom=geom, direction=direction,
                margin_top_mm=margin_top_mm,
                margin_left_mm=margin_left_mm,
                margin_right_mm=margin_right_mm,
                cell_w=cell_w, cell_h=cell_h,
            )
            x_mid = x0 + cell_w / 2
            y_mid = y0 + cell_h / 2
            x1 = x0 + cell_w
            y1 = y0 + cell_h
            common = (f'stroke="{HELPER_LINE_COLOR}" '
                      f'stroke-width="{HELPER_LINE_WIDTH}" '
                      f'stroke-dasharray="{HELPER_DASH}"')
            # Horizontal centre line
            parts.append(
                f'<line x1="{x0:.3f}" y1="{y_mid:.3f}" '
                f'x2="{x1:.3f}" y2="{y_mid:.3f}" {common}/>'
            )
            # Vertical centre line
            parts.append(
                f'<line x1="{x_mid:.3f}" y1="{y0:.3f}" '
                f'x2="{x_mid:.3f}" y2="{y1:.3f}" {common}/>'
            )
            # Diagonal \
            parts.append(
                f'<line x1="{x0:.3f}" y1="{y0:.3f}" '
                f'x2="{x1:.3f}" y2="{y1:.3f}" {common}/>'
            )
            # Diagonal /
            parts.append(
                f'<line x1="{x0:.3f}" y1="{y1:.3f}" '
                f'x2="{x1:.3f}" y2="{y0:.3f}" {common}/>'
            )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Header / footer text rendering — vector glyphs via char_loader
# ---------------------------------------------------------------------------


def _render_text_run(text: str, *, char_loader: CharLoader,
                     start_x_mm: float, baseline_y_mm: float,
                     char_size_mm: float, gap_mm: float = 0.5
                     ) -> tuple[str, float]:
    """Render a horizontal vector text run starting at (start_x, baseline).

    Returns ``(svg_inner, end_x_mm)``. Missing glyphs are silently skipped
    (no fallback text glyph) so the plotter never tries to draw something
    we don't have outlines for.

    The baseline is treated as the *vertical centre* of each glyph for
    simplicity; ``baseline_y_mm`` is the cell centre y.
    """
    parts: list[str] = []
    cursor = start_x_mm
    for ch in text:
        if ch.isspace():
            cursor += char_size_mm * 0.5 + gap_mm
            continue
        c = char_loader(ch)
        if c is None:
            cursor += char_size_mm * 0.5 + gap_mm
            continue
        cx = cursor + char_size_mm / 2
        parts.append(_char_cut_paths(c, cx, baseline_y_mm, char_size_mm))
        cursor += char_size_mm + gap_mm
    return "".join(parts), cursor


def _header(scribe: str, date_str: str,
            *, char_loader: CharLoader, margin_top_mm: float,
            margin_left_mm: float, margin_right_mm: float
            ) -> str:
    """Header line above the grid: 「日期：____   抄寫者：____」"""
    label_size = 4.0
    underline_w_date   = 35.0
    underline_w_scribe = 40.0
    baseline_y = margin_top_mm * 0.45    # halfway up the top margin
    # Date block (left)
    inner_left = margin_left_mm
    date_label_svg, after_date_label = _render_text_run(
        "日期：", char_loader=char_loader,
        start_x_mm=inner_left, baseline_y_mm=baseline_y,
        char_size_mm=label_size, gap_mm=0.4,
    )
    date_value_svg, after_date_value = _render_text_run(
        date_str, char_loader=char_loader,
        start_x_mm=after_date_label + 1.0, baseline_y_mm=baseline_y,
        char_size_mm=label_size, gap_mm=0.4,
    )
    date_underline_x = after_date_label + 1.0
    date_underline = (
        f'<line x1="{date_underline_x:.3f}" '
        f'y1="{baseline_y + label_size * 0.55:.3f}" '
        f'x2="{date_underline_x + underline_w_date:.3f}" '
        f'y2="{baseline_y + label_size * 0.55:.3f}" '
        f'stroke="{HEADER_UNDERLINE_COLOR}" stroke-width="0.25"/>'
    )

    # Scribe block (right of date, ~70% across page)
    scribe_label_x = inner_left + 90.0
    scribe_label_svg, after_scribe_label = _render_text_run(
        "抄寫者：", char_loader=char_loader,
        start_x_mm=scribe_label_x, baseline_y_mm=baseline_y,
        char_size_mm=label_size, gap_mm=0.4,
    )
    scribe_value_svg, after_scribe_value = _render_text_run(
        scribe, char_loader=char_loader,
        start_x_mm=after_scribe_label + 1.0, baseline_y_mm=baseline_y,
        char_size_mm=label_size, gap_mm=0.4,
    )
    scribe_underline_x = after_scribe_label + 1.0
    scribe_underline = (
        f'<line x1="{scribe_underline_x:.3f}" '
        f'y1="{baseline_y + label_size * 0.55:.3f}" '
        f'x2="{scribe_underline_x + underline_w_scribe:.3f}" '
        f'y2="{baseline_y + label_size * 0.55:.3f}" '
        f'stroke="{HEADER_UNDERLINE_COLOR}" stroke-width="0.25"/>'
    )
    return (
        f'<g fill="{HEADER_LABEL_COLOR}" stroke="none">'
        f'{date_label_svg}{date_value_svg}{date_underline}'
        f'{scribe_label_svg}{scribe_value_svg}{scribe_underline}'
        f'</g>'
    )


def _footer(signature: str, *, char_loader: CharLoader,
            geom: PageGeometry,
            margin_bottom_mm: float) -> str:
    """Centred footer line."""
    if not signature:
        return ""
    size = 3.5
    baseline_y = geom.page_h_mm - margin_bottom_mm * 0.45
    # Approximate width to centre — use char_size * len + gaps.
    approx_w = size * len(signature) + 0.4 * (len(signature) - 1)
    start_x = (geom.page_w_mm - approx_w) / 2
    inner, _ = _render_text_run(
        signature, char_loader=char_loader,
        start_x_mm=start_x, baseline_y_mm=baseline_y,
        char_size_mm=size, gap_mm=0.4,
    )
    return f'<g fill="{HEADER_LABEL_COLOR}" stroke="none">{inner}</g>'


# ---------------------------------------------------------------------------
# Body page
# ---------------------------------------------------------------------------


def render_sutra_page(
    chars: list[str],
    *,
    char_loader: CharLoader,
    scribe: str = "",
    date_str: str = "",
    signature: str = "",
    trace_fill: str = TRACE_FILL_DEFAULT,
    show_helper_lines: bool = True,
    show_grid: bool = True,
    margin_top_mm: float = DEFAULT_MARGIN_TOP_MM,
    margin_bottom_mm: float = DEFAULT_MARGIN_BOTTOM_MM,
    margin_left_mm: float = DEFAULT_MARGIN_LEFT_MM,
    margin_right_mm: float = DEFAULT_MARGIN_RIGHT_MM,
    punct_marks: Optional[list[str]] = None,
    # 5bj: page orientation + text direction
    orientation: PaperOrientation = "landscape",
    direction: TextDirection = "vertical",
    # 5bv: how to render 句讀 marks (text by default, polyline for PDF)
    mark_renderer: MarkRenderer = "text",
    # 5bz: optional second loader returning *outline-bearing* characters
    # for skeleton-only glyphs (隸/篆 in default skeleton mode). When
    # supplied, render_sutra_page draws the original outline as a faded
    # reference layer beneath the skeleton tracks — useful for browser
    # preview and PDF, where humans want to see the full letterform.
    # SVG downloads (for plotters) leave this None to keep the file
    # purely centerline tracks.
    outline_glyph_loader: Optional[CharLoader] = None,
    # 5ca/5cb: reference layer carries the visual weight on its own
    # (~12% grey, a typical 描紅紙 tone). The skeleton group is now
    # near-invisible (0.03) so users aren't distracted by the imperfect
    # centerline traces; tweak `_SKELETON_TRACE_OPACITY` to dial it back.
    reference_glyph_opacity: float = 0.55,
) -> str:
    """Render one body page (trace grid + header + footer).

    Args (5bj):
        orientation : "landscape" (297×210, 20×15 cells) or
                      "portrait"  (210×297, 15×20 cells).
        direction   : "vertical"   — right-to-left col-major (傳統直書)
                      "horizontal" — left-to-right row-major (現代橫書)

    Args (5bv):
        mark_renderer : "text" (default) — emit each 句讀 mark as an SVG
                                  ``<text>`` element rendered with a CJK
                                  font stack. Best browser preview quality;
                                  requires the renderer to have a CJK
                                  system font.
                        "polyline"      — trace the punctuation glyph via
                                  ``char_loader`` and emit ``<path>`` /
                                  ``<polyline>``. Renders identically on
                                  any host (e.g. cairosvg → PDF), with no
                                  system-font dependency.

    Args (5bz):
        outline_glyph_loader   : Optional second loader returning the
                                 *outline-bearing* version of each char
                                 (lishu/seal with mode="skip"). When the
                                 main ``char_loader`` returns a skeleton-
                                 only Character (隸/篆 default), this
                                 loader is consulted to draw a faded
                                 reference letterform beneath the
                                 skeleton tracks. Outline-bearing chars
                                 (kaishu/sung) never trigger this layer
                                 even when the loader is provided —
                                 prevents double-rendering.
        reference_glyph_opacity: Opacity of the reference letterform
                                 layer. Default 0.55 prints as ≈12%
                                 grey — a typical 描紅紙 tone. The
                                 skeleton group is rendered separately
                                 at a much fainter opacity (5cb).

    ``chars`` is the slice of characters to place — up to ``cells_per_page``;
    missing cells are left empty.
    ``punct_marks`` (optional) is a list parallel to ``chars`` carrying
    a 句讀 punctuation mark to draw beside each cell.
    """
    geom = get_geometry(orientation)
    cell_w, cell_h = _cell_size(geom, margin_top_mm, margin_bottom_mm,
                                 margin_left_mm, margin_right_mm)
    char_size = min(cell_w, cell_h) * 0.85
    pieces: list[str] = []

    # 1. Grid (helpers first → cell borders → outer frame)
    if show_helper_lines:
        pieces.append(_helper_lines(geom, direction,
                                     margin_top_mm, margin_bottom_mm,
                                     margin_left_mm, margin_right_mm))
    if show_grid:
        pieces.append(_grid_lines(geom,
                                   margin_top_mm, margin_bottom_mm,
                                   margin_left_mm, margin_right_mm))
    pieces.append(_outer_frame(geom,
                                margin_top_mm, margin_bottom_mm,
                                margin_left_mm, margin_right_mm))

    # 2. Header / footer (vector text)
    pieces.append(_header(
        scribe=scribe, date_str=date_str,
        char_loader=char_loader,
        margin_top_mm=margin_top_mm,
        margin_left_mm=margin_left_mm,
        margin_right_mm=margin_right_mm,
    ))
    pieces.append(_footer(
        signature=signature, char_loader=char_loader,
        geom=geom,
        margin_bottom_mm=margin_bottom_mm,
    ))

    # 3. Char glyphs (trace-fill, no stroke)
    # 5bw: split into two groups —
    #   glyph_parts          : outline-bearing chars (楷/宋 — filled paths)
    #   skeleton_glyph_parts : skeleton-only chars (隸/篆 default mode —
    #                          centerline tracks, outline=[]). Without this
    #                          fallback the page would silently render blank
    #                          for those styles.
    glyph_parts: list[str] = []
    skeleton_glyph_parts: list[str] = []
    # 5bz: reference-letterform layer for skeleton-only chars. Populated
    # only when outline_glyph_loader is supplied AND the main loader
    # returned skeleton-only data — avoids double-drawing for kaishu/sung.
    reference_glyph_parts: list[str] = []
    mark_parts: list[str] = []         # 5bi: 句讀 marks
    # 5bt: bigger marks (~33% larger than 5bs). The user prefers a more
    # legible 句讀 mark and accepts edge contact with the BOTTOM frame.
    # Numbers (landscape, "黃" worst-case glyph bottom +4.25mm):
    #   mark_size  = char_size × 0.40    → "，" visual ≈ 0.63 × 1.18 mm
    #   pad_inside = mark_size × 0.15
    #   mark TOP    distance to glyph bottom: +0.13 mm (no contact)
    #   mark BOTTOM distance to cell bottom:  -0.02 mm (touches frame, OK)
    #   mark RIGHT  distance to cell right:   +0.28 mm (no contact)
    mark_size = char_size * 0.40
    pad_inside = mark_size * 0.15
    mark_offset_x = (cell_w / 2.0) - pad_inside
    mark_offset_y = (cell_h / 2.0) - pad_inside
    has_marks = bool(punct_marks)
    cap = geom.cells_per_page
    for n, ch in enumerate(chars[:cap]):
        col, row = _index_to_cell(n, geom=geom, direction=direction)
        x0, y0 = _cell_origin(
            col, row,
            geom=geom, direction=direction,
            margin_top_mm=margin_top_mm,
            margin_left_mm=margin_left_mm,
            margin_right_mm=margin_right_mm,
            cell_w=cell_w, cell_h=cell_h,
        )
        cx = x0 + cell_w / 2
        cy = y0 + cell_h / 2
        # Draw the glyph if we have one
        if ch and not ch.isspace():
            c_glyph = char_loader(ch)
            if c_glyph is not None:
                outline_svg = _char_cut_paths(c_glyph, cx, cy, char_size)
                if outline_svg:
                    # Outline-bearing glyph (楷書 / 宋體 / outline-mode lishu).
                    glyph_parts.append(outline_svg)
                else:
                    # 5bw / 5bx: skeleton-only glyph (隸書 / 篆書 default
                    # mode): outline=[] but raw_track has the centerline.
                    # Use the local helper that adds vector-effect so the
                    # outer group's mm stroke-width survives the inner
                    # EM→mm scale transform.
                    poly_svg = _render_skeleton_glyph(
                        c_glyph, cx, cy, char_size,
                    )
                    if poly_svg:
                        skeleton_glyph_parts.append(poly_svg)
                    # 5bz: also draw the original outline letterform as a
                    # faded reference, so the user sees the lishu/seal
                    # shape behind the skeleton. Only triggered for
                    # skeleton-only chars (the `else` branch) — kaishu
                    # already showed in the main trace group.
                    if outline_glyph_loader is not None:
                        ref_glyph = outline_glyph_loader(ch)
                        if ref_glyph is not None:
                            ref_svg = _char_cut_paths(
                                ref_glyph, cx, cy, char_size,
                            )
                            if ref_svg:
                                reference_glyph_parts.append(ref_svg)
        # 5bv: dispatch on mark_renderer:
        #   "text"     — emit <text> with CJK font (5bu, browser-friendly)
        #   "polyline" — trace via char_loader (cairosvg / PDF: zero font dep)
        if has_marks and n < len(punct_marks):
            mark_ch = punct_marks[n]
            if mark_ch:
                mx = cx + mark_offset_x
                my = cy + mark_offset_y
                if mark_renderer == "polyline":
                    mark_glyph = char_loader(mark_ch)
                    if mark_glyph is not None:
                        mark_parts.append(_render_mark_glyph(
                            mark_glyph, mx, my, mark_size,
                        ))
                else:  # "text" (default)
                    mark_parts.append(_render_mark_text(
                        mark_ch, mx, my, mark_size,
                    ))
    # 5bz: reference glyph layer first — sits *underneath* the skeleton
    # so the centerline reads as the foreground stroke.
    if reference_glyph_parts:
        # Clamp opacity into [0, 1] for SVG validity.
        op = max(0.0, min(1.0, reference_glyph_opacity))
        pieces.append(
            f'<g id="sutra-glyph-reference" fill="{trace_fill}" '
            f'stroke="none" opacity="{op:.3f}">'
            f'{"".join(reference_glyph_parts)}</g>'
        )
    if glyph_parts:
        pieces.append(
            f'<g id="sutra-trace" fill="{trace_fill}" stroke="none">'
            f'{"".join(glyph_parts)}</g>'
        )
    if skeleton_glyph_parts:
        # 5bw: skeleton-mode chars rendered as stroked polylines. Same
        # `trace_fill` colour as the outline group keeps the visual weight
        # consistent across mixed pages (e.g. a kaishu fallback char among
        # seal-script chars when the seal font is missing a glyph).
        # 5by: stroke-width tracks char_size so landscape (smaller cells)
        # and portrait (square cells, larger glyph) keep matching weight.
        # 5ca: opacity tuned to match the reference glyph layer for an
        # even, print-friendly 描紅 grey across both layers.
        skel_stroke_w = char_size * _SKELETON_TRACE_STROKE_RATIO
        pieces.append(
            f'<g id="sutra-trace-skeleton" fill="none" '
            f'stroke="{trace_fill}" '
            f'stroke-width="{skel_stroke_w:.3f}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'opacity="{_SKELETON_TRACE_OPACITY:.3f}">'
            f'{"".join(skeleton_glyph_parts)}</g>'
        )
    if mark_parts:
        if mark_renderer == "polyline":
            # 5bv: traced glyphs may emit <polyline> (raw_track only) so the
            # group needs *both* fill (for any <path> from outline) AND
            # stroke (for polylines). Slightly higher opacity than text mode
            # to keep thin strokes legible after raster downscaling.
            pieces.append(
                f'<g id="sutra-marks" fill="#888888" '
                f'stroke="#888888" stroke-width="0.18" '
                f'stroke-linecap="round" stroke-linejoin="round" '
                f'opacity="0.65">'
                f'{"".join(mark_parts)}</g>'
            )
        else:
            # 5bu: <text> elements — only fill + opacity needed.
            pieces.append(
                f'<g id="sutra-marks" fill="#888888" '
                f'opacity="0.55">'
                f'{"".join(mark_parts)}</g>'
            )

    return _wrap_svg("".join(pieces), geom=geom)


# ---------------------------------------------------------------------------
# Cover + dedication pages
# ---------------------------------------------------------------------------


def render_sutra_cover(
    info: SutraInfo,
    *,
    char_loader: CharLoader,
    scribe: str = "",
    signature: str = "",
    orientation: PaperOrientation = "landscape",
) -> str:
    """Cover page: vector title + subtitle + scribe field."""
    geom = get_geometry(orientation)
    pieces: list[str] = []
    title_size = 14.0
    title_y    = geom.page_h_mm * 0.36
    approx_w = title_size * len(info.title) + 1.0 * (len(info.title) - 1)
    start_x = (geom.page_w_mm - approx_w) / 2
    title_svg, _ = _render_text_run(
        info.title, char_loader=char_loader,
        start_x_mm=start_x, baseline_y_mm=title_y,
        char_size_mm=title_size, gap_mm=1.0,
    )
    pieces.append(
        f'<g fill="{INK_FILL}" stroke="none">{title_svg}</g>'
    )
    sub_size = 6.0
    sub_y    = title_y + title_size * 0.9
    approx_sub = sub_size * len(info.subtitle) + 0.8 * (len(info.subtitle) - 1)
    sub_x = (geom.page_w_mm - approx_sub) / 2
    sub_svg, _ = _render_text_run(
        info.subtitle, char_loader=char_loader,
        start_x_mm=sub_x, baseline_y_mm=sub_y,
        char_size_mm=sub_size, gap_mm=0.8,
    )
    pieces.append(
        f'<g fill="#888888" stroke="none">{sub_svg}</g>'
    )
    if scribe is not None:
        label_size = 5.0
        label_y    = geom.page_h_mm * 0.62
        label_text = "抄寫者："
        approx_label = label_size * len(label_text) + 0.5 * (len(label_text) - 1)
        underline_w  = 50.0
        block_w = approx_label + underline_w + 2.0
        block_x = (geom.page_w_mm - block_w) / 2
        label_svg, after_label = _render_text_run(
            label_text, char_loader=char_loader,
            start_x_mm=block_x, baseline_y_mm=label_y,
            char_size_mm=label_size, gap_mm=0.5,
        )
        scribe_svg, _ = _render_text_run(
            scribe, char_loader=char_loader,
            start_x_mm=after_label + 1.0, baseline_y_mm=label_y,
            char_size_mm=label_size, gap_mm=0.5,
        )
        underline = (
            f'<line x1="{after_label + 1.0:.3f}" '
            f'y1="{label_y + label_size * 0.55:.3f}" '
            f'x2="{after_label + 1.0 + underline_w:.3f}" '
            f'y2="{label_y + label_size * 0.55:.3f}" '
            f'stroke="#000" stroke-width="0.3"/>'
        )
        pieces.append(
            f'<g fill="{INK_FILL}" stroke="none">'
            f'{label_svg}{scribe_svg}{underline}</g>'
        )
    pieces.append(_footer(signature=signature, char_loader=char_loader,
                           geom=geom,
                           margin_bottom_mm=DEFAULT_MARGIN_BOTTOM_MM))
    return _wrap_svg("".join(pieces), geom=geom)


def render_sutra_dedication(
    *,
    char_loader: CharLoader,
    dedicator: str = "",
    target: str = "",
    body_text: Optional[str] = None,
    signature: str = "",
    orientation: PaperOrientation = "landscape",
) -> str:
    """Dedication page — fill-ins + (optionally) trace-style verse.

    ``body_text`` is rendered as faded trace text in the centre when
    provided. The fill-in line goes below it.
    """
    geom = get_geometry(orientation)
    pieces: list[str] = []
    # Title
    title_size = 10.0
    title_y    = geom.page_h_mm * 0.18
    title = "迴向文"
    approx = title_size * len(title) + 1.0 * (len(title) - 1)
    title_x = (geom.page_w_mm - approx) / 2
    title_svg, _ = _render_text_run(
        title, char_loader=char_loader,
        start_x_mm=title_x, baseline_y_mm=title_y,
        char_size_mm=title_size, gap_mm=1.0,
    )
    pieces.append(f'<g fill="{INK_FILL}" stroke="none">{title_svg}</g>')

    # Body verse (trace fill) — wrap into multiple lines for layout
    if body_text:
        verse_size = 7.0
        verse_line_gap = 3.0
        # Naive wrapping every 12 chars (matches the verse length pattern)
        chunks: list[str] = []
        chars = text_to_chars(body_text)
        line_len = 12
        for i in range(0, len(chars), line_len):
            chunks.append("".join(chars[i:i + line_len]))
        verse_y0 = geom.page_h_mm * 0.36
        verse_parts: list[str] = []
        for li, line in enumerate(chunks):
            line_w = verse_size * len(line) + 0.6 * (len(line) - 1)
            x = (geom.page_w_mm - line_w) / 2
            y = verse_y0 + li * (verse_size + verse_line_gap)
            line_svg, _ = _render_text_run(
                line, char_loader=char_loader,
                start_x_mm=x, baseline_y_mm=y,
                char_size_mm=verse_size, gap_mm=0.6,
            )
            verse_parts.append(line_svg)
        pieces.append(
            f'<g fill="{TRACE_FILL_DEFAULT}" stroke="none">'
            f'{"".join(verse_parts)}</g>'
        )

    # Fill-in line: 「弟子 _____ 願以此功德，迴向 _____」
    fill_size = 5.5
    fill_y = geom.page_h_mm * 0.78
    # Build run with two underline gaps
    parts_svg: list[str] = []
    cursor_x = 30.0
    seg1, after1 = _render_text_run(
        "弟子", char_loader=char_loader,
        start_x_mm=cursor_x, baseline_y_mm=fill_y,
        char_size_mm=fill_size, gap_mm=0.5,
    )
    parts_svg.append(seg1)
    cursor_x = after1 + 1.5
    underline_w = 40.0
    seg_dedicator, _ = _render_text_run(
        dedicator, char_loader=char_loader,
        start_x_mm=cursor_x, baseline_y_mm=fill_y,
        char_size_mm=fill_size, gap_mm=0.5,
    )
    parts_svg.append(seg_dedicator)
    parts_svg.append(
        f'<line x1="{cursor_x:.3f}" '
        f'y1="{fill_y + fill_size * 0.55:.3f}" '
        f'x2="{cursor_x + underline_w:.3f}" '
        f'y2="{fill_y + fill_size * 0.55:.3f}" '
        f'stroke="#000" stroke-width="0.3"/>'
    )
    cursor_x += underline_w + 2.0
    seg2, after2 = _render_text_run(
        "願以此功德，迴向", char_loader=char_loader,
        start_x_mm=cursor_x, baseline_y_mm=fill_y,
        char_size_mm=fill_size, gap_mm=0.5,
    )
    parts_svg.append(seg2)
    cursor_x = after2 + 1.5
    seg_target, _ = _render_text_run(
        target, char_loader=char_loader,
        start_x_mm=cursor_x, baseline_y_mm=fill_y,
        char_size_mm=fill_size, gap_mm=0.5,
    )
    parts_svg.append(seg_target)
    parts_svg.append(
        f'<line x1="{cursor_x:.3f}" '
        f'y1="{fill_y + fill_size * 0.55:.3f}" '
        f'x2="{cursor_x + underline_w:.3f}" '
        f'y2="{fill_y + fill_size * 0.55:.3f}" '
        f'stroke="#000" stroke-width="0.3"/>'
    )
    pieces.append(
        f'<g fill="{INK_FILL}" stroke="none">{"".join(parts_svg)}</g>'
    )

    pieces.append(_footer(signature=signature, char_loader=char_loader,
                           geom=geom,
                           margin_bottom_mm=DEFAULT_MARGIN_BOTTOM_MM))
    return _wrap_svg("".join(pieces), geom=geom)


# ---------------------------------------------------------------------------
# Page-count helper
# ---------------------------------------------------------------------------


def sutra_page_count(
    text: str,
    *,
    mode: TextMode = "compact",
    orientation: PaperOrientation = "landscape",
    include_cover: bool = True,
    include_dedication: bool = False,
) -> dict:
    """Return ``{cover, body_pages, dedication, total}`` for a given text."""
    body = total_body_pages(text, mode, orientation=orientation)
    return {
        "cover": 1 if include_cover else 0,
        "body_pages": body,
        "dedication": 1 if include_dedication else 0,
        "total": (1 if include_cover else 0) + body
                 + (1 if include_dedication else 0),
    }


# ---------------------------------------------------------------------------
# SVG envelope
# ---------------------------------------------------------------------------


def _wrap_svg(inner: str, *, geom: PageGeometry = None) -> str:
    if geom is None:
        geom = _GEOMETRIES["landscape"]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {geom.page_w_mm:.3f} {geom.page_h_mm:.3f}" '
        f'width="{geom.page_w_mm:.3f}mm" height="{geom.page_h_mm:.3f}mm">'
        f'{inner}</svg>'
    )


__all__ = [
    "PAGE_W_MM", "PAGE_H_MM", "COLS", "ROWS", "CELLS_PER_PAGE",
    "PageType", "TextMode", "TRACE_FILL_DEFAULT",
    # 5bj
    "PaperOrientation", "TextDirection", "PageGeometry", "get_geometry",
    # 5bv
    "MarkRenderer",
    "render_sutra_page",
    "render_sutra_cover",
    "render_sutra_dedication",
    "sutra_page_count",
    "total_body_pages",
    "page_slice",
    # 5bh
    "prepare_text",
    # 5bi
    "prepare_text_with_marks", "page_slice_with_marks",
]
