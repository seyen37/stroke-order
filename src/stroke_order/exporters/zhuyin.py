"""
Phase 5bo: 注音符號描紅字帖 exporter（聲母／介音／韻母分帶＋大千鍵位）.

One A4-landscape page: all 37 Bopomofo symbols grouped into the three
phonological categories — 聲母 21, 介音 3, 韻母 13 — each category a
tinted multi-row band with a traced label, 7 symbols per row. Every
cell shows the symbol's standard (大千式) keyboard key as a small
Latin/digit hint plus the symbol as a faded trace glyph.

All 37 symbols have real stroke-order data in the MOE-lineage sources
(no CNS outline fallback needed) — verified 2026-07-11.
"""
from __future__ import annotations

from .patch import _char_cut_paths
from .sutra import (
    CharLoader, get_geometry, TRACE_FILL_DEFAULT,
    _render_skeleton_glyph, _wrap_svg, traced_run,
    cellmap_rect, cellmap_group,
)

#: (category_label, [(symbol, standard-keyboard key), ...])
ZHUYIN_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("聲母", [
        ("ㄅ", "1"), ("ㄆ", "q"), ("ㄇ", "a"), ("ㄈ", "z"),
        ("ㄉ", "2"), ("ㄊ", "w"), ("ㄋ", "s"), ("ㄌ", "x"),
        ("ㄍ", "e"), ("ㄎ", "d"), ("ㄏ", "c"),
        ("ㄐ", "r"), ("ㄑ", "f"), ("ㄒ", "v"),
        ("ㄓ", "5"), ("ㄔ", "t"), ("ㄕ", "g"), ("ㄖ", "b"),
        ("ㄗ", "y"), ("ㄘ", "h"), ("ㄙ", "n"),
    ]),
    ("介音", [
        ("ㄧ", "u"), ("ㄨ", "j"), ("ㄩ", "m"),
    ]),
    ("韻母", [
        ("ㄚ", "8"), ("ㄛ", "i"), ("ㄜ", "k"), ("ㄝ", ","),
        ("ㄞ", "9"), ("ㄟ", "o"), ("ㄠ", "l"), ("ㄡ", "."),
        ("ㄢ", "0"), ("ㄣ", "p"), ("ㄤ", ";"), ("ㄥ", "/"),
        ("ㄦ", "-"),
    ]),
]

ZHUYIN_TEXT: str = "".join(
    sym for _label, pairs in ZHUYIN_GROUPS for sym, _k in pairs)

_GROUP_TINTS = {"聲母": "#E2ECE2", "介音": "#F5EAD8", "韻母": "#E4E4EF"}

# --- page geometry (A4 landscape, mm) --------------------------------------

_COLS = 7
_MARGIN_L = 8.0
_MARGIN_R = 8.0
_LABEL_W = 24.0
_GRID_TOP = 21.0
_CELL_H = 28.0
_TITLE_CY = 9.5
_TITLE_SIZE = 8.0

_FONT_STACK = "'Helvetica Neue', Arial, 'Noto Sans', sans-serif"


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _traced(chars: str, cx: float, cy: float, size_mm: float,
            loader: CharLoader, *, fill: str, gap_ratio: float = 1.15,
            outline_glyph_loader=None) -> str:
    # 5fg：委派共用 traced_run——舊版把骨架 fallback 包進 stroke="none"
    # 群組，篆/隸（骨架字）整串隱形（5ff 週期表同病的自繪版）。
    return traced_run(
        chars, cx, cy, size_mm, loader, fill=fill, gap_ratio=gap_ratio,
        outline_glyph_loader=outline_glyph_loader)


def render_zhuyin_page(
    *,
    char_loader: CharLoader,
    trace_fill: str = TRACE_FILL_DEFAULT,
    show_grid: bool = True,
    # 5fg：參考字形層（route 端 5ff 能力偵測轉發，同 週期表）
    outline_glyph_loader=None,
    show_group_tints: bool = True,
    title: str = "注音符號",
    emit_cellmap: bool = False,
) -> str:
    """Render the 37-symbol Bopomofo trace page (SVG, mm).

    5dw: ``emit_cellmap`` adds the transparent ``#sutra-cellmap`` overlay —
    one ``data-char`` click rect per symbol cell (category label bands get
    none) — for the 逐字手寫 popup (preview only). Each cell is a single
    Bopomofo symbol, fitting the per-char handwriting model.
    """
    geom = get_geometry("landscape")
    # 5fg：把參考層 loader 綁進本頁所有描紅呼叫
    _t = lambda *a, **kw: _traced(
        *a, outline_glyph_loader=outline_glyph_loader, **kw)
    cell_w = (geom.page_w_mm - _MARGIN_L - _MARGIN_R - _LABEL_W) / _COLS
    grid_x0 = _MARGIN_L + _LABEL_W

    cache: dict = {}

    def loader(ch: str):
        if ch not in cache:
            cache[ch] = char_loader(ch)
        return cache[ch]

    bg, grid, hints, glyphs = [], [], [], []
    cm: list[str] = []
    cell_pos = 0

    title_svg = _t(title, geom.page_w_mm / 2.0, _TITLE_CY,
                        _TITLE_SIZE, loader, fill="#333333")

    row = 0
    for label, pairs in ZHUYIN_GROUPS:
        n_rows = (len(pairs) + _COLS - 1) // _COLS
        band_y0 = _GRID_TOP + row * _CELL_H
        band_h = n_rows * _CELL_H
        tint = _GROUP_TINTS[label]
        if show_group_tints:
            bg.append(
                f'<rect x="{_MARGIN_L:.2f}" y="{band_y0:.2f}" '
                f'width="{_LABEL_W:.2f}" height="{band_h:.2f}" '
                f'fill="{tint}"/>'
            )
        if show_grid:
            grid.append(
                f'<rect x="{_MARGIN_L:.2f}" y="{band_y0:.2f}" '
                f'width="{_LABEL_W:.2f}" height="{band_h:.2f}" '
                f'fill="none" stroke="#999999" stroke-width="0.18"/>'
            )
        glyphs.append(_t(
            label, _MARGIN_L + _LABEL_W / 2.0, band_y0 + band_h / 2.0,
            6.0, loader, fill="#555555"))
        for k, (sym, key) in enumerate(pairs):
            col = k % _COLS
            y0 = band_y0 + (k // _COLS) * _CELL_H
            x0 = grid_x0 + col * cell_w
            if emit_cellmap:
                cm.append(cellmap_rect(sym, x0, y0, cell_w, _CELL_H, cell_pos,
                                       loaded=loader(sym) is not None))
            cell_pos += 1
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
                f'<text x="{x0 + 2.0:.2f}" y="{y0 + 5.6:.2f}" '
                f'font-size="4.2" font-weight="bold" '
                f'font-family="{_FONT_STACK}" '
                f'fill="#B0523C">{_xml_escape(key)}</text>'
            )
            char_size = min(cell_w - 6.0, _CELL_H - 9.0) * 0.85
            cy = y0 + 3.5 + (_CELL_H - 3.5) / 2.0
            traced = _t(sym, x0 + cell_w / 2.0, cy, char_size,
                             loader, fill=trace_fill)
            if traced:
                glyphs.append(traced)
        row += n_rows

    inner = (
        f'<g id="zy-bg">{"".join(bg)}</g>'
        f'<g id="zy-grid">{"".join(grid)}</g>'
        f'<g id="zy-title">{title_svg}</g>'
        f'<g id="zy-hints">{"".join(hints)}</g>'
        f'<g id="zy-trace">{"".join(glyphs)}</g>'
        f'{cellmap_group(cm)}'
    )
    return _wrap_svg(inner, geom=geom)


__all__ = ["ZHUYIN_GROUPS", "ZHUYIN_TEXT", "render_zhuyin_page"]
