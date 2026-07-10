"""
Phase 5bo: 二十四節氣描紅字帖 exporter.

One A4-landscape page: 4 season rows × 6 term columns, plus a traced
season label band on the left. Each cell carries the term's typical
Gregorian date as a small hint (``2/4`` style, Arabic-only text so hosts without CJK fonts render it correctly) and the
two-character term name as faded trace glyphs — same outline pipeline
as the sutra body pages.

Term order runs 立春 → 大寒 (the traditional list starting from the
first spring term); dates are the typical mid-range day and can shift
±1 day year to year.
"""
from __future__ import annotations

from .patch import _char_cut_paths
from .sutra import (
    CharLoader, get_geometry, TRACE_FILL_DEFAULT,
    _render_skeleton_glyph, _wrap_svg,
)

#: (term, typical Gregorian date) × 24, season-major from 立春.
SOLAR_TERMS: list[tuple[str, str]] = [
    ("立春", "2/4"),  ("雨水", "2/19"),  ("驚蟄", "3/6"),
    ("春分", "3/21"), ("清明", "4/5"),   ("穀雨", "4/20"),
    ("立夏", "5/6"),  ("小滿", "5/21"),  ("芒種", "6/6"),
    ("夏至", "6/21"), ("小暑", "7/7"),   ("大暑", "7/23"),
    ("立秋", "8/8"),  ("處暑", "8/23"),  ("白露", "9/8"),
    ("秋分", "9/23"), ("寒露", "10/8"),  ("霜降", "10/23"),
    ("立冬", "11/7"), ("小雪", "11/22"), ("大雪", "12/7"),
    ("冬至", "12/22"), ("小寒", "1/6"),  ("大寒", "1/20"),
]

SOLAR_TERMS_TEXT: str = "".join(t for t, _d in SOLAR_TERMS)

_SEASONS = ("春", "夏", "秋", "冬")
_SEASON_TINTS = {
    "春": "#E3F0DA",   # 淡綠
    "夏": "#F9DFD8",   # 淡紅
    "秋": "#F7EFCF",   # 淡金
    "冬": "#DCE8F4",   # 淡藍
}

# --- page geometry (A4 landscape, mm) --------------------------------------

_MARGIN_L = 8.0
_MARGIN_R = 8.0
_LABEL_W = 22.0          # season label band
_GRID_TOP = 22.0
_CELL_H = 42.0
_TITLE_CY = 10.0
_TITLE_SIZE = 8.0

_TEXT_COLOR = "#666666"
_FONT_STACK = "'Helvetica Neue', Arial, 'Noto Sans', sans-serif"


def _traced(chars: str, cx: float, cy: float, size_mm: float,
            loader: CharLoader, *, fill: str, gap_ratio: float = 1.15) -> str:
    step = size_mm * gap_ratio
    x0 = cx - step * (len(chars) - 1) / 2.0
    parts: list[str] = []
    for k, ch in enumerate(chars):
        c = loader(ch)
        if c is None:
            continue
        drawn = _char_cut_paths(c, x0 + k * step, cy, size_mm)
        if not drawn:
            drawn = _render_skeleton_glyph(c, x0 + k * step, cy, size_mm)
        if drawn:
            parts.append(drawn)
    return f'<g fill="{fill}" stroke="none">{"".join(parts)}</g>' if parts else ""


def render_solar_terms_page(
    *,
    char_loader: CharLoader,
    trace_fill: str = TRACE_FILL_DEFAULT,
    show_grid: bool = True,
    show_season_tints: bool = True,
    title: str = "二十四節氣",
) -> str:
    """Render the 4×6 二十四節氣 trace page (SVG, mm)."""
    geom = get_geometry("landscape")
    cell_w = (geom.page_w_mm - _MARGIN_L - _MARGIN_R - _LABEL_W) / 6.0
    grid_x0 = _MARGIN_L + _LABEL_W

    cache: dict = {}

    def loader(ch: str):
        if ch not in cache:
            cache[ch] = char_loader(ch)
        return cache[ch]

    bg, grid, hints, glyphs = [], [], [], []

    title_svg = _traced(title, geom.page_w_mm / 2.0, _TITLE_CY,
                        _TITLE_SIZE, loader, fill="#333333")

    for s, season in enumerate(_SEASONS):
        y0 = _GRID_TOP + s * _CELL_H
        tint = _SEASON_TINTS[season]
        # season label band (tinted darker by keeping tint + traced char)
        if show_season_tints:
            bg.append(
                f'<rect x="{_MARGIN_L:.2f}" y="{y0:.2f}" '
                f'width="{_LABEL_W:.2f}" height="{_CELL_H:.2f}" '
                f'fill="{tint}"/>'
            )
        if show_grid:
            grid.append(
                f'<rect x="{_MARGIN_L:.2f}" y="{y0:.2f}" '
                f'width="{_LABEL_W:.2f}" height="{_CELL_H:.2f}" '
                f'fill="none" stroke="#999999" stroke-width="0.18"/>'
            )
        glyphs.append(_traced(
            season, _MARGIN_L + _LABEL_W / 2.0, y0 + _CELL_H / 2.0,
            10.0, loader, fill="#555555"))
        for t in range(6):
            term, date = SOLAR_TERMS[s * 6 + t]
            x0 = grid_x0 + t * cell_w
            if show_season_tints:
                bg.append(
                    f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{cell_w:.2f}" '
                    f'height="{_CELL_H:.2f}" fill="{tint}" opacity="0.55"/>'
                )
            if show_grid:
                grid.append(
                    f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{cell_w:.2f}" '
                    f'height="{_CELL_H:.2f}" fill="none" stroke="#999999" '
                    f'stroke-width="0.18"/>'
                )
            hints.append(
                f'<text x="{x0 + 2.0:.2f}" y="{y0 + 4.4:.2f}" '
                f'font-size="3.0" font-family="{_FONT_STACK}" '
                f'fill="{_TEXT_COLOR}">{date}</text>'
            )
            # two-char term, centred below the hint strip
            char_size = min((cell_w - 4.0) / 2.3, _CELL_H - 12.0)
            cy = y0 + 5.5 + (_CELL_H - 5.5) / 2.0
            traced = _traced(term, x0 + cell_w / 2.0, cy, char_size,
                             loader, fill=trace_fill)
            if traced:
                glyphs.append(traced)

    inner = (
        f'<g id="st-bg">{"".join(bg)}</g>'
        f'<g id="st-grid">{"".join(grid)}</g>'
        f'<g id="st-title">{title_svg}</g>'
        f'<g id="st-hints">{"".join(hints)}</g>'
        f'<g id="st-trace">{"".join(glyphs)}</g>'
    )
    return _wrap_svg(inner, geom=geom)


__all__ = ["SOLAR_TERMS", "SOLAR_TERMS_TEXT", "render_solar_terms_page"]
