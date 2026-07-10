"""
Phase 5bo: 倉頡字根描紅字帖 exporter（四類分帶＋鍵位）.

One A4-landscape page: the 24 basic Cangjie radicals plus X 難, grouped
into the traditional four philosophical categories (each its own tinted
row with a traced label band) — 哲理類 A-G, 筆畫類 H-N, 人身類 O-R,
字形類 S-Y — plus the 特殊 row for X. Each cell shows the keyboard key
(Latin letter, plain SVG text) and the radical as a faded trace glyph.

Pairs naturally with the project's Cangjie lineage (SCG reference
analyses, 5g 倉頡口訣 wordcloud samples).
"""
from __future__ import annotations

from .patch import _char_cut_paths
from .sutra import (
    CharLoader, get_geometry, TRACE_FILL_DEFAULT,
    _render_skeleton_glyph, _wrap_svg,
)

#: (category_label, keys, radicals) — parallel key/radical strings.
CANGJIE_GROUPS: list[tuple[str, str, str]] = [
    ("哲理類", "ABCDEFG", "日月金木水火土"),
    ("筆畫類", "HIJKLMN", "竹戈十大中一弓"),
    ("人身類", "OPQR",    "人心手口"),
    ("字形類", "STUVWY",  "尸廿山女田卜"),
    ("特殊",   "X",       "難"),
]

CANGJIE_TEXT: str = "".join(r for _l, _k, r in CANGJIE_GROUPS)

_GROUP_TINTS = ("#F5EAD8", "#E2ECE2", "#E4E4EF", "#F3E2DE", "#EDEDE0")

# --- page geometry (A4 landscape, mm) --------------------------------------

_MARGIN_L = 8.0
_MARGIN_R = 8.0
_LABEL_W = 26.0
_GRID_TOP = 21.0
_CELL_H = 33.0
_TITLE_CY = 9.5
_TITLE_SIZE = 8.0
_COLS = 7

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


def render_cangjie_roots_page(
    *,
    char_loader: CharLoader,
    trace_fill: str = TRACE_FILL_DEFAULT,
    show_grid: bool = True,
    show_group_tints: bool = True,
    title: str = "倉頡字根",
) -> str:
    """Render the 25-radical Cangjie key page (SVG, mm)."""
    geom = get_geometry("landscape")
    cell_w = (geom.page_w_mm - _MARGIN_L - _MARGIN_R - _LABEL_W) / _COLS
    grid_x0 = _MARGIN_L + _LABEL_W

    cache: dict = {}

    def loader(ch: str):
        if ch not in cache:
            cache[ch] = char_loader(ch)
        return cache[ch]

    bg, grid, hints, glyphs = [], [], [], []

    title_svg = _traced(title, geom.page_w_mm / 2.0, _TITLE_CY,
                        _TITLE_SIZE, loader, fill="#333333")

    for g, (label, keys, radicals) in enumerate(CANGJIE_GROUPS):
        y0 = _GRID_TOP + g * _CELL_H
        tint = _GROUP_TINTS[g % len(_GROUP_TINTS)]
        if show_group_tints:
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
            label, _MARGIN_L + _LABEL_W / 2.0, y0 + _CELL_H / 2.0,
            5.2, loader, fill="#555555"))
        for k, (key, ch) in enumerate(zip(keys, radicals)):
            x0 = grid_x0 + k * cell_w
            if show_group_tints:
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
                f'<text x="{x0 + 2.2:.2f}" y="{y0 + 6.2:.2f}" '
                f'font-size="5.0" font-weight="bold" '
                f'font-family="{_FONT_STACK}" '
                f'fill="#B0523C">{key}</text>'
            )
            char_size = min(cell_w - 6.0, _CELL_H - 10.0) * 0.85
            cy = y0 + 4.0 + (_CELL_H - 4.0) / 2.0
            traced = _traced(ch, x0 + cell_w / 2.0, cy, char_size,
                             loader, fill=trace_fill)
            if traced:
                glyphs.append(traced)

    inner = (
        f'<g id="cj-bg">{"".join(bg)}</g>'
        f'<g id="cj-grid">{"".join(grid)}</g>'
        f'<g id="cj-title">{title_svg}</g>'
        f'<g id="cj-hints">{"".join(hints)}</g>'
        f'<g id="cj-trace">{"".join(glyphs)}</g>'
    )
    return _wrap_svg(inner, geom=geom)


__all__ = ["CANGJIE_GROUPS", "CANGJIE_TEXT", "render_cangjie_roots_page"]
