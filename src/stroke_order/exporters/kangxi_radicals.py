"""
Phase 5bo: 康熙 214 部首描紅字帖 exporter（畫數分帶）.

One A4-landscape page: all 214 radicals (台灣教育部標準字形) flowing
left-to-right in an 18-column grid, colour-banded by stroke count
(1畫 → 17畫). Each cell carries the radical index (1-214) as a small
hint, the first cell of every band also shows the band's stroke count
(e.g. ``4畫``), and the radical itself as a faded trace glyph.

This preset is strategically aligned with docs/VISION.md: radicals are
the entry point to component-based glyph synthesis — the copybook doubles
as component-writing training material.

All 214 chars verified against the stroke DB (zero CNS fallback needed
with MOE forms, e.g. 青 not 靑).
"""
from __future__ import annotations

from .patch import _char_cut_paths
from .sutra import (
    CharLoader, get_geometry, TRACE_FILL_DEFAULT,
    _render_skeleton_glyph, _wrap_svg,
    cellmap_rect, cellmap_group,
)

#: (stroke_count, radicals) — 17 bands, 214 radicals total, MOE forms.
RADICAL_BANDS: list[tuple[int, str]] = [
    (1,  "一丨丶丿乙亅"),
    (2,  "二亠人儿入八冂冖冫几凵刀力勹匕匚匸十卜卩厂厶又"),
    (3,  "口囗土士夂夊夕大女子宀寸小尢尸屮山巛工己巾干幺广廴廾弋弓彐彡彳"),
    (4,  "心戈戶手支攴文斗斤方无日曰月木欠止歹殳毋比毛氏气水火爪父爻爿片牙牛犬"),
    (5,  "玄玉瓜瓦甘生用田疋疒癶白皮皿目矛矢石示禸禾穴立"),
    (6,  "竹米糸缶网羊羽老而耒耳聿肉臣自至臼舌舛舟艮色艸虍虫血行衣襾"),
    (7,  "見角言谷豆豕豸貝赤走足身車辛辰辵邑酉釆里"),
    (8,  "金長門阜隶隹雨青非"),
    (9,  "面革韋韭音頁風飛食首香"),
    (10, "馬骨高髟鬥鬯鬲鬼"),
    (11, "魚鳥鹵鹿麥麻"),
    (12, "黃黍黑黹"),
    (13, "黽鼎鼓鼠"),
    (14, "鼻齊"),
    (15, "齒"),
    (16, "龍龜"),
    (17, "龠"),
]

ALL_RADICALS: str = "".join(chars for _n, chars in RADICAL_BANDS)

#: (radical, index_1based, stroke_count, is_band_start)
RADICALS: list[tuple[str, int, int, bool]] = []
_idx = 0
for _n, _chars in RADICAL_BANDS:
    for _k, _ch in enumerate(_chars):
        _idx += 1
        RADICALS.append((_ch, _idx, _n, _k == 0))

# --- page geometry (A4 landscape, mm) --------------------------------------

_COLS = 18
_MARGIN_L = 8.0
_MARGIN_R = 8.0
_GRID_TOP = 19.0
_CELL_H = 14.6
_TITLE_CY = 8.5
_TITLE_SIZE = 7.0

#: soft 4-colour cycle — adjacent stroke-count bands always differ.
_BAND_TINTS = ("#F5EFDF", "#E4EDE4", "#E6E6F0", "#F4E4E0")
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


def render_kangxi_radicals_page(
    *,
    char_loader: CharLoader,
    trace_fill: str = TRACE_FILL_DEFAULT,
    show_grid: bool = True,
    show_band_tints: bool = True,
    title: str = "康熙二一四部首",
    emit_cellmap: bool = False,
) -> str:
    """Render the 214-radical stroke-count-banded page (SVG, mm).

    5dw: ``emit_cellmap`` adds a transparent ``#sutra-cellmap`` overlay — one
    ``data-char`` click rect per radical cell — so the 逐字手寫 popup works
    on this page (preview only). Each cell is a single radical glyph, so the
    per-char handwriting model fits directly.
    """
    geom = get_geometry("landscape")
    cell_w = (geom.page_w_mm - _MARGIN_L - _MARGIN_R) / _COLS

    cache: dict = {}

    def loader(ch: str):
        if ch not in cache:
            cache[ch] = char_loader(ch)
        return cache[ch]

    bg, grid, hints, glyphs = [], [], [], []
    cm: list[str] = []

    title_svg = _traced(title, geom.page_w_mm / 2.0, _TITLE_CY,
                        _TITLE_SIZE, loader, fill="#333333")

    band_of = {n: i for i, (n, _c) in enumerate(RADICAL_BANDS)}
    for pos, (ch, idx, strokes, band_start) in enumerate(RADICALS):
        col, row = pos % _COLS, pos // _COLS
        x0 = _MARGIN_L + col * cell_w
        y0 = _GRID_TOP + row * _CELL_H
        if emit_cellmap:
            cm.append(cellmap_rect(ch, x0, y0, cell_w, _CELL_H, pos,
                                   loaded=loader(ch) is not None))
        if show_band_tints:
            tint = _BAND_TINTS[band_of[strokes] % len(_BAND_TINTS)]
            bg.append(
                f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{cell_w:.2f}" '
                f'height="{_CELL_H:.2f}" fill="{tint}"/>'
            )
        if show_grid:
            grid.append(
                f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{cell_w:.2f}" '
                f'height="{_CELL_H:.2f}" fill="none" stroke="#999999" '
                f'stroke-width="0.15"/>'
            )
        hints.append(
            f'<text x="{x0 + 0.9:.2f}" y="{y0 + 2.6:.2f}" '
            f'font-size="2.0" font-family="{_FONT_STACK}" '
            f'fill="{_TEXT_COLOR}">{idx}</text>'
        )
        if band_start:
            # stroke-count marker: Arabic numeral only (ASCII-in-<text>
            # rule) — "4" at the band's first cell, top-right, bold.
            hints.append(
                f'<text x="{x0 + cell_w - 0.9:.2f}" y="{y0 + 2.8:.2f}" '
                f'font-size="2.4" font-family="{_FONT_STACK}" '
                f'text-anchor="end" font-weight="bold" '
                f'fill="#B0523C">{strokes}</text>'
            )
        char_size = min(cell_w, _CELL_H - 3.4) * 0.82
        cy = y0 + 3.0 + (_CELL_H - 3.0) / 2.0
        traced = _traced(ch, x0 + cell_w / 2.0, cy, char_size,
                         loader, fill=trace_fill)
        if traced:
            glyphs.append(traced)

    # footer note: band colour = stroke-count group (traced CJK, no
    # ASCII prefix — the red per-band markers already carry the numbers)
    footer_y = _GRID_TOP + ((len(RADICALS) + _COLS - 1) // _COLS) * _CELL_H
    glyphs.append(_traced(
        "色帶依畫數分組", _MARGIN_L + 12.0, footer_y + 3.8, 3.0,
        loader, fill="#777777"))

    inner = (
        f'<g id="kr-bg">{"".join(bg)}</g>'
        f'<g id="kr-grid">{"".join(grid)}</g>'
        f'<g id="kr-title">{title_svg}</g>'
        f'<g id="kr-hints">{"".join(hints)}</g>'
        f'<g id="kr-trace">{"".join(glyphs)}</g>'
        f'{cellmap_group(cm)}'
    )
    return _wrap_svg(inner, geom=geom)


__all__ = ["RADICAL_BANDS", "ALL_RADICALS", "RADICALS",
           "render_kangxi_radicals_page"]
