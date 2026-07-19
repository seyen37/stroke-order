"""
Phase 5bo: 九九乘法表描紅字帖 exporter.

Classic lower-triangle 九九表 (45 口訣) on one A4-landscape page:
row *j* holds the mnemonics ending in ×j — row 1 is 「一一得一」,
row 9 runs 「一九得九 … 九九八十一」. Each cell carries a small
Arabic hint (``3×7=21``) plus the Chinese mnemonic as faded trace
glyphs, drawn through the same outline pipeline as sutra body pages.

Mnemonic spelling follows the Taiwan primary-school convention:

- product < 10   → 「得」 + digit      (三三得九)
- product == 10  → 「一十」            (二五一十)
- 11 ≤ p ≤ 19    → 「十」 + unit       (三四十二)
- p ≥ 20         → tens [+ unit]       (四五二十, 三七二十一)

Only 11 distinct chars are used (一二三四五六七八九十得), so the
renderer memoises the char loader — one glyph load per distinct char
per page, not per cell.
"""
from __future__ import annotations

from .patch import _char_cut_paths
from .sutra import (
    CharLoader, get_geometry, TRACE_FILL_DEFAULT,
    _render_skeleton_glyph, _wrap_svg, traced_run,
)

_ZH_DIGITS = "〇一二三四五六七八九"


def _zh_product(p: int) -> str:
    """Chinese reading of a 1-81 product, mnemonic convention."""
    if p < 10:
        return "得" + _ZH_DIGITS[p]
    if p == 10:
        return "一十"
    if p < 20:
        return "十" + _ZH_DIGITS[p - 10]
    tens, unit = divmod(p, 10)
    return _ZH_DIGITS[tens] + "十" + (_ZH_DIGITS[unit] if unit else "")


def mnemonic(i: int, j: int) -> str:
    """口訣 for i×j (i ≤ j), e.g. mnemonic(3, 7) == "三七二十一"."""
    if not (1 <= i <= j <= 9):
        raise ValueError(f"need 1 <= i <= j <= 9, got {i}, {j}")
    return _ZH_DIGITS[i] + _ZH_DIGITS[j] + _zh_product(i * j)


#: All 45 mnemonics, row-major (row j = multiplier, i = 1..j).
MNEMONICS: list[tuple[int, int, str]] = [
    (i, j, mnemonic(i, j)) for j in range(1, 10) for i in range(1, j + 1)
]

MNEMONICS_TEXT: str = "".join(m for _i, _j, m in MNEMONICS)

# --- page geometry (A4 landscape, mm) --------------------------------------

_MARGIN_L = 8.0
_MARGIN_R = 8.0
_GRID_TOP = 20.0
_CELL_H = 19.6
_TITLE_CY = 9.0
_TITLE_SIZE = 7.5

_ROW_TINTS = ("#F7F1E1", "#E7EEE7", "#E9E9F2")   # soft 3-colour cycle
_TEXT_COLOR = "#666666"
_FONT_STACK = "'Helvetica Neue', Arial, 'Noto Sans', sans-serif"


def _traced(chars: str, cx: float, cy: float, size_mm: float,
            loader: CharLoader, *, fill: str, gap_ratio: float = 1.12,
            outline_glyph_loader=None) -> str:
    # 5fg：委派共用 traced_run——舊版把骨架 fallback 包進 stroke="none"
    # 群組，篆/隸（骨架字）整串隱形（5ff 週期表同病的自繪版）。
    return traced_run(
        chars, cx, cy, size_mm, loader, fill=fill, gap_ratio=gap_ratio,
        outline_glyph_loader=outline_glyph_loader)


def render_multiplication_table_page(
    *,
    char_loader: CharLoader,
    trace_fill: str = TRACE_FILL_DEFAULT,
    show_grid: bool = True,
    # 5fg：參考字形層（route 端 5ff 能力偵測轉發，同 週期表）
    outline_glyph_loader=None,
    show_row_tints: bool = True,
    title: str = "九九乘法表",
) -> str:
    """Render the 45-口訣 lower-triangle 九九表 page (SVG, mm)."""
    geom = get_geometry("landscape")
    # 5fg：把參考層 loader 綁進本頁所有描紅呼叫
    _t = lambda *a, **kw: _traced(
        *a, outline_glyph_loader=outline_glyph_loader, **kw)
    cell_w = (geom.page_w_mm - _MARGIN_L - _MARGIN_R) / 9.0

    # memoise: only 11 distinct chars on the whole page
    cache: dict = {}

    def loader(ch: str):
        if ch not in cache:
            cache[ch] = char_loader(ch)
        return cache[ch]

    bg, grid, hints, glyphs = [], [], [], []

    title_svg = _t(title, geom.page_w_mm / 2.0, _TITLE_CY,
                        _TITLE_SIZE, loader, fill="#333333")

    for i, j, phrase in MNEMONICS:
        x0 = _MARGIN_L + (i - 1) * cell_w
        y0 = _GRID_TOP + (j - 1) * _CELL_H
        if show_row_tints:
            bg.append(
                f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{cell_w:.2f}" '
                f'height="{_CELL_H:.2f}" '
                f'fill="{_ROW_TINTS[(j - 1) % len(_ROW_TINTS)]}"/>'
            )
        if show_grid:
            grid.append(
                f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{cell_w:.2f}" '
                f'height="{_CELL_H:.2f}" fill="none" stroke="#999999" '
                f'stroke-width="0.18"/>'
            )
        hints.append(
            f'<text x="{x0 + 1.4:.2f}" y="{y0 + 3.4:.2f}" '
            f'font-size="2.6" font-family="{_FONT_STACK}" '
            f'fill="{_TEXT_COLOR}">{i}×{j}={i * j}</text>'
        )
        # mnemonic centred in the space below the hint strip
        char_size = min(cell_w / (len(phrase) * 1.12), _CELL_H - 6.5)
        cy = y0 + 4.0 + (_CELL_H - 4.0) / 2.0
        traced = _t(phrase, x0 + cell_w / 2.0, cy, char_size,
                         loader, fill=trace_fill)
        if traced:
            glyphs.append(traced)

    inner = (
        f'<g id="mt-bg">{"".join(bg)}</g>'
        f'<g id="mt-grid">{"".join(grid)}</g>'
        f'<g id="mt-title">{title_svg}</g>'
        f'<g id="mt-hints">{"".join(hints)}</g>'
        f'<g id="mt-trace">{"".join(glyphs)}</g>'
    )
    return _wrap_svg(inner, geom=geom)


__all__ = ["MNEMONICS", "MNEMONICS_TEXT", "mnemonic",
           "render_multiplication_table_page"]
