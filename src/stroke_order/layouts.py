"""
Text layout engine for notebook/letter modes.

Given a string of characters and a page layout spec, produces a sequence
of Pages, each containing the list of characters placed at specific
coordinates. Handles auto line-wrap, auto page-break, and optional
reserve zones (rectangles where text flows around).

Units throughout are **millimetres** (mm) for physical paper coordinates.
Characters are rendered inside cells of size ``char_width_mm × line_height_mm``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional

from .ir import Character


GridStyle = Literal["square", "ruled", "dotted", "none"]
WritingDirection = Literal["horizontal", "vertical"]
# horizontal = 橫書: chars flow L→R within a row, rows stack T→B
# vertical   = 直書: chars flow T→B within a column, columns stack R→L


# ---------------------------------------------------------------------------
# Preset page sizes (mm)
# ---------------------------------------------------------------------------

PAGE_SIZES: dict[str, tuple[float, float]] = {
    "A4":     (210.0, 297.0),
    "A5":     (148.0, 210.0),
    "A6":     (105.0, 148.0),
    "B5":     (176.0, 250.0),
    "Letter": (215.9, 279.4),
    # Named notebook sizes
    "notebook-small":  (105.0, 148.0),  # ≈ A6, pocket
    "notebook-medium": (148.0, 210.0),  # ≈ A5, standard
    "notebook-large":  (210.0, 297.0),  # ≈ A4
}


@dataclass
class PageSize:
    width_mm: float
    height_mm: float

    @classmethod
    def named(cls, name: str) -> "PageSize":
        w, h = PAGE_SIZES[name]
        return cls(w, h)


@dataclass
class ReserveZone:
    """A rectangle on the page where the text-flow engine will not place
    characters. Typically used for doodle spaces.

    Phase 5s: zones can optionally carry ``svg_content`` — an SVG fragment
    (string) that is embedded into the page output, fit-within the zone
    (preserving aspect ratio, centered). ``content_viewbox`` stores the
    intrinsic viewBox of the imported SVG (parsed on import) so the renderer
    knows the natural coordinate system to scale from.
    """
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    label: str = ""
    svg_content: Optional[str] = None       # inner SVG markup (no <svg> wrapper)
    content_viewbox: Optional[tuple[float, float, float, float]] = None
    stretch: bool = False                    # True = fill zone ignoring aspect

    def contains(self, x: float, y: float) -> bool:
        return (self.x_mm <= x < self.x_mm + self.width_mm
                and self.y_mm <= y < self.y_mm + self.height_mm)

    def overlaps_cell(self, x: float, y: float, w: float, h: float) -> bool:
        """Check if cell [x..x+w, y..y+h] overlaps this zone."""
        return not (x + w <= self.x_mm
                    or x >= self.x_mm + self.width_mm
                    or y + h <= self.y_mm
                    or y >= self.y_mm + self.height_mm)


@dataclass
class PageLayout:
    """Complete layout specification for a page."""
    size: PageSize
    margin_top_mm: float = 15.0
    margin_bottom_mm: float = 15.0
    margin_left_mm: float = 15.0
    margin_right_mm: float = 15.0
    line_height_mm: float = 12.0
    char_width_mm: float = 12.0
    grid_style: GridStyle = "square"
    reserve_zones: list[ReserveZone] = field(default_factory=list)
    line_spacing_mm: float = 0.0  # extra gap between lines
    # Phase 5o: grid rendering hints
    direction: "WritingDirection" = "horizontal"
    first_line_offset_mm: Optional[float] = None

    # Derived properties
    @property
    def content_x(self) -> float:
        return self.margin_left_mm

    @property
    def content_y(self) -> float:
        return self.margin_top_mm

    @property
    def content_right(self) -> float:
        return self.size.width_mm - self.margin_right_mm

    @property
    def content_bottom(self) -> float:
        return self.size.height_mm - self.margin_bottom_mm

    @property
    def row_step(self) -> float:
        return self.line_height_mm + self.line_spacing_mm


@dataclass
class PlacedChar:
    """A single character placed on a page, in mm coords."""
    char: Character
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float

    @property
    def center_x(self) -> float:
        return self.x_mm + self.width_mm / 2

    @property
    def center_y(self) -> float:
        return self.y_mm + self.height_mm / 2


@dataclass
class Annotation:
    """A text annotation placed at an arbitrary point on a page."""
    text: str
    x_mm: float
    y_mm: float
    size_mm: float = 3.0
    color: str = "#666"


@dataclass
class SignatureBlock:
    """Signature + optional date, placed at a specific Y below the body.

    Represents the "署名" block on a letter page. Typically appears one
    or more lines below the last body character, right-aligned.
    """
    signature_text: str = ""
    date_text: str = ""
    signature_size_mm: float = 9.0
    date_size_mm: float = 6.75
    y_mm: float = 0.0      # baseline Y of the SIGNATURE line
    align: str = "right"   # 'left' | 'right' | 'center'


@dataclass
class TitleBlock:
    """Letter header placed in the top margin of page 1."""
    text: str = ""
    size_mm: float = 9.0
    y_mm: float = 0.0
    align: str = "left"


@dataclass
class TextGlyph:
    """A character with no stroke data (Phase 5ai fallback).

    Populated by ``flow_text`` when ``char_loader`` returns ``None`` — i.e.
    the character isn't in any loaded source (not even the punctuation
    fallback). Rendered by ``render_page_svg`` as a plain ``<text>`` element
    so the SVG preview still shows the character, even though G-code / JSON
    cannot reproduce it (not stroke data).
    """
    char: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float


@dataclass
class Page:
    page_num: int
    layout: PageLayout
    chars: list[PlacedChar] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    # characters that couldn't be loaded; kept for diagnostics
    missing: list[str] = field(default_factory=list)
    # Phase 5ai: SVG-only fallback for chars without stroke data
    text_glyphs: list[TextGlyph] = field(default_factory=list)
    # letter-mode extras (optional; only set when relevant)
    title_block: Optional[TitleBlock] = None
    signature_block: Optional[SignatureBlock] = None


# ---------------------------------------------------------------------------
# Text flow algorithm
# ---------------------------------------------------------------------------


def _cell_blocked(layout: PageLayout, x: float, y: float,
                  w: float, h: float) -> bool:
    """True if this cell would overlap any reserve zone."""
    return any(z.overlaps_cell(x, y, w, h) for z in layout.reserve_zones)


def _skip_past_zones(layout: PageLayout, x: float, y: float,
                     w: float, h: float) -> float:
    """
    If (x,y) collides with a reserve zone, return the x past the rightmost
    zone whose overlap is blocking. If multiple zones, returns max.
    Used to shift the cursor rightward to skip over a zone on one line.
    """
    max_x = x
    for z in layout.reserve_zones:
        if z.overlaps_cell(x, y, w, h):
            past = z.x_mm + z.width_mm
            if past > max_x:
                max_x = past
    return max_x


def _skip_past_zones_vertical(layout: PageLayout, x: float, y: float,
                              w: float, h: float) -> float:
    """For vertical flow: if (x,y) collides with a reserve zone, return the
    y past the LOWEST edge of the blocking zone (shift cursor downward)."""
    max_y = y
    for z in layout.reserve_zones:
        if z.overlaps_cell(x, y, w, h):
            past = z.y_mm + z.height_mm
            if past > max_y:
                max_y = past
    return max_y


# Phase 5ad: tolerance for the overflow comparisons. Iteratively
# accumulating ``cursor_y += line_height`` (or cursor_x) drifts by ~1e-13
# per step; after ~25 steps the drift is still in the 1e-12 range. Without
# slack, a grid derived as ``content_h / N`` can fail to fit exactly N rows
# (the N-th row overflows by a sub-nanometre amount). A tolerance of 1e-6
# mm = 1 nanometre is invisible physically yet generous enough to absorb
# any plausible FP drift.
_FP_EPS_MM = 1e-6


def flow_text(
    text: str,
    layout: PageLayout,
    char_loader,
    *,
    max_pages: int = 50,
    direction: WritingDirection = "horizontal",
    first_line_offset_mm: Optional[float] = None,
) -> list[Page]:
    """
    Lay out ``text`` onto pages of ``layout``.

    Parameters
    ----------
    text
        The full text. ``\n`` forces a line/column break; other whitespace is
        treated like an empty cell (skipped but advances cursor).
    layout
        PageLayout spec. All characters use its char_width_mm × line_height_mm.
    char_loader
        Callable ``char_loader(c: str) -> Character | None`` returning the
        loaded IR for a character (or None if unavailable).
    max_pages
        Safety limit.
    direction
        ``horizontal`` (default, 橫書) — chars flow left-to-right, lines wrap
        top-to-bottom.
        ``vertical`` (直書) — chars flow top-to-bottom, columns wrap
        right-to-left.
    first_line_offset_mm
        Phase 5n: distance from the reference edge to the ENDING edge of the
        first row/column.
        - Horizontal: distance from page top to first row's BOTTOM.
          Default = margin_top + line_height (cursor_y = margin_top).
        - Vertical: distance from page right to first column's LEFT edge.
          Default = margin_right + char_width (cursor_x = content_right - cw).
        Min value = margin (to keep text on the page). Subsequent rows/columns
        continue at normal spacing from this initial position.
    """
    if direction == "vertical":
        return _flow_text_vertical(
            text, layout, char_loader, max_pages=max_pages,
            first_line_offset_mm=first_line_offset_mm,
        )
    return _flow_text_horizontal(
        text, layout, char_loader, max_pages=max_pages,
        first_line_offset_mm=first_line_offset_mm,
    )


def _flow_text_horizontal(text, layout, char_loader, *, max_pages,
                          first_line_offset_mm=None):
    pages: list[Page] = []
    page = Page(page_num=1, layout=layout)

    def new_page():
        nonlocal page
        pages.append(page)
        if len(pages) >= max_pages:
            raise ValueError(
                f"text layout exceeded max_pages={max_pages}; "
                f"shrink char size, enlarge paper, or raise the limit"
            )
        page = Page(page_num=len(pages) + 1, layout=layout)

    cursor_x = layout.content_x
    cw, ch_ = layout.char_width_mm, layout.line_height_mm
    # Phase 5n/5p: first_line_offset_mm shifts the initial cursor_y so that
    # the first row's BOTTOM lines up with the requested offset.
    # Min = margin_top + line_height (= auto default; ensures first row's
    # top edge sits at content_y, never inside the top margin).
    if first_line_offset_mm is not None:
        min_offset = layout.margin_top_mm + ch_
        max_offset = layout.content_bottom
        off = max(min_offset, min(first_line_offset_mm, max_offset))
        cursor_y = max(layout.content_y, off - ch_)
    else:
        cursor_y = layout.content_y

    for ch in text:
        if ch == "\n":
            cursor_x = layout.content_x
            cursor_y += layout.row_step
            if cursor_y + ch_ > layout.content_bottom + _FP_EPS_MM:
                new_page()
                cursor_x = layout.content_x
                cursor_y = layout.content_y
            continue
        if ch in (" ", "\t", "\u3000"):
            cursor_x += cw
            if cursor_x + cw > layout.content_right + _FP_EPS_MM:
                cursor_x = layout.content_x
                cursor_y += layout.row_step
                if cursor_y + ch_ > layout.content_bottom + _FP_EPS_MM:
                    new_page()
                    cursor_x = layout.content_x
                    cursor_y = layout.content_y
            continue

        if _cell_blocked(layout, cursor_x, cursor_y, cw, ch_):
            cursor_x = _skip_past_zones(layout, cursor_x, cursor_y, cw, ch_)

        if cursor_x + cw > layout.content_right + _FP_EPS_MM:
            cursor_x = layout.content_x
            cursor_y += layout.row_step
            if cursor_y + ch_ > layout.content_bottom + _FP_EPS_MM:
                new_page()
                cursor_x = layout.content_x
                cursor_y = layout.content_y
            if _cell_blocked(layout, cursor_x, cursor_y, cw, ch_):
                cursor_x = _skip_past_zones(layout, cursor_x, cursor_y, cw, ch_)
                if cursor_x + cw > layout.content_right + _FP_EPS_MM:
                    cursor_y += layout.row_step
                    cursor_x = layout.content_x
                    if cursor_y + ch_ > layout.content_bottom + _FP_EPS_MM:
                        new_page()
                        cursor_y = layout.content_y

        c = char_loader(ch)
        if c is None:
            # Phase 5ai: record for diagnostics AND leave a fallback glyph
            # so SVG rendering can at least show the character as <text>.
            page.missing.append(ch)
            page.text_glyphs.append(TextGlyph(
                char=ch, x_mm=cursor_x, y_mm=cursor_y,
                width_mm=cw, height_mm=ch_,
            ))
            cursor_x += cw
            continue

        page.chars.append(
            PlacedChar(char=c, x_mm=cursor_x, y_mm=cursor_y,
                       width_mm=cw, height_mm=ch_)
        )
        cursor_x += cw

    pages.append(page)
    return pages


def _flow_text_vertical(text, layout, char_loader, *, max_pages,
                         first_line_offset_mm=None):
    """Vertical writing (直書): chars T→B within column, columns R→L."""
    pages: list[Page] = []
    page = Page(page_num=1, layout=layout)

    def new_page():
        nonlocal page
        pages.append(page)
        if len(pages) >= max_pages:
            raise ValueError(
                f"text layout exceeded max_pages={max_pages}; "
                f"shrink char size, enlarge paper, or raise the limit"
            )
        page = Page(page_num=len(pages) + 1, layout=layout)

    cw, ch_ = layout.char_width_mm, layout.line_height_mm
    col_step = cw + layout.line_spacing_mm
    page_w = layout.size.width_mm
    # Phase 5n/5p: first_line_offset_mm measures from the RIGHT page edge to
    # the LEFT edge of the first (rightmost) column.
    # Min = margin_right + char_width (= auto default; ensures first column's
    # right edge stays inside content_right, not hugging the page edge).
    if first_line_offset_mm is not None:
        min_offset = layout.margin_right_mm + cw
        max_offset = page_w - layout.margin_left_mm
        off = max(min_offset, min(first_line_offset_mm, max_offset))
        cursor_x = max(layout.content_x, page_w - off)
    else:
        cursor_x = layout.content_right - cw
    cursor_y = layout.content_y

    for ch in text:
        if ch == "\n":
            # forced column break: jump to next column (leftward), reset y
            cursor_x -= col_step
            cursor_y = layout.content_y
            if cursor_x < layout.content_x - _FP_EPS_MM:
                new_page()
                cursor_x = layout.content_right - cw
                cursor_y = layout.content_y
            continue
        if ch in (" ", "\t", "\u3000"):
            cursor_y += ch_
            if cursor_y + ch_ > layout.content_bottom + _FP_EPS_MM:
                cursor_x -= col_step
                cursor_y = layout.content_y
                if cursor_x < layout.content_x - _FP_EPS_MM:
                    new_page()
                    cursor_x = layout.content_right - cw
                    cursor_y = layout.content_y
            continue

        # reserve-zone check for current cell
        if _cell_blocked(layout, cursor_x, cursor_y, cw, ch_):
            cursor_y = _skip_past_zones_vertical(layout, cursor_x, cursor_y, cw, ch_)

        # column overflow?
        if cursor_y + ch_ > layout.content_bottom + _FP_EPS_MM:
            cursor_x -= col_step
            cursor_y = layout.content_y
            if cursor_x < layout.content_x - _FP_EPS_MM:
                new_page()
                cursor_x = layout.content_right - cw
                cursor_y = layout.content_y
            if _cell_blocked(layout, cursor_x, cursor_y, cw, ch_):
                cursor_y = _skip_past_zones_vertical(
                    layout, cursor_x, cursor_y, cw, ch_)
                if cursor_y + ch_ > layout.content_bottom + _FP_EPS_MM:
                    cursor_x -= col_step
                    cursor_y = layout.content_y
                    if cursor_x < layout.content_x - _FP_EPS_MM:
                        new_page()
                        cursor_x = layout.content_right - cw
                        cursor_y = layout.content_y

        c = char_loader(ch)
        if c is None:
            # Phase 5ai: SVG text fallback (see horizontal flow comment)
            page.missing.append(ch)
            page.text_glyphs.append(TextGlyph(
                char=ch, x_mm=cursor_x, y_mm=cursor_y,
                width_mm=cw, height_mm=ch_,
            ))
            cursor_y += ch_
            continue

        page.chars.append(
            PlacedChar(char=c, x_mm=cursor_x, y_mm=cursor_y,
                       width_mm=cw, height_mm=ch_)
        )
        cursor_y += ch_

    pages.append(page)
    return pages


def layout_capacity(
    layout: PageLayout,
    direction: WritingDirection = "horizontal",
) -> dict:
    """
    Return capacity info for a layout WITHOUT actually rendering.

    For ``horizontal``: cells arranged as rows × cols (cols per line).
    For ``vertical``:   cells arranged as cols × rows (rows per column).
    """
    cw = max(layout.char_width_mm, 0.01)
    rh = max(layout.row_step, 0.01)
    col_step = max(layout.char_width_mm + layout.line_spacing_mm, 0.01)
    ch_ = max(layout.line_height_mm, 0.01)
    content_w = max(0.0, layout.content_right - layout.content_x)
    content_h = max(0.0, layout.content_bottom - layout.content_y)

    if direction == "vertical":
        # Columns across width, rows (chars) down each column
        cols = int(content_w / col_step)    # number of columns on page
        rows = int(content_h / ch_)          # chars per column
        gross = cols * rows
    else:
        cols = int(content_w / cw)           # cells per row
        rows = int(content_h / rh)           # rows per page
        gross = cols * rows

    blocked = 0
    for z in layout.reserve_zones:
        zc = max(1, int(-(-z.width_mm // cw)))
        zr = max(1, int(-(-z.height_mm // rh)))
        blocked += zc * zr

    chars = max(0, gross - blocked)
    return {
        "cols_per_line": cols,
        "lines_per_page": rows,
        "gross_cells": gross,
        "blocked_cells": blocked,
        "chars_per_page": chars,
        "direction": direction,
    }


def estimate_pages(
    text: str,
    layout: PageLayout,
    direction: WritingDirection = "horizontal",
) -> int:
    """
    Estimate how many pages ``text`` will occupy under ``layout``.
    Supports both horizontal and vertical writing directions.
    """
    cap = layout_capacity(layout, direction)
    ch_per_page = cap["chars_per_page"]
    if ch_per_page <= 0:
        return 0
    n_chars = sum(1 for c in text if not c.isspace())
    newlines = text.count("\n")
    # For vertical, \n wastes avg half-column
    if direction == "vertical":
        waste = newlines * max(0, cap["lines_per_page"] - 1) // 2
    else:
        waste = newlines * max(0, cap["cols_per_line"] - 1) // 2
    effective = n_chars + waste
    if effective == 0:
        return 1
    return max(1, -(-effective // ch_per_page))


__all__ = [
    "PAGE_SIZES",
    "GridStyle",
    "WritingDirection",
    "PageSize",
    "PageLayout",
    "PlacedChar",
    "ReserveZone",
    "Annotation",
    "Page",
    "TitleBlock",
    "SignatureBlock",
    "flow_text",
    "layout_capacity",
    "estimate_pages",
]
