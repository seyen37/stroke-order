"""
Phase 5bo: 元素週期表描紅字帖 exporter.

Renders the 118-element periodic table as a single A4-landscape 描紅
page: standard 18-group × 7-period layout with the lanthanide /
actinide series pulled out into two rows below, matching the layout
conventions of printed periodic tables.

Each element cell carries:

- atomic number (top-left, plain SVG text)
- element symbol (top-right, plain SVG text — Latin, universally
  available in any font)
- the element's Chinese name as a faded trace glyph (描紅), drawn via
  the shared ``_char_cut_paths`` outline pipeline (same as sutra body
  pages) with skeleton fallback for stroke-only sources

plus an optional light category tint (鹼金屬/過渡金屬/鹵素…) so the
printed sheet doubles as a chemistry reference.

CJK labels (title, series markers, legend) are *traced* via the char
loader rather than emitted as ``<text>``, so the SVG renders correctly
under cairosvg on hosts without a CJK system font (same reasoning as
sutra's ``mark_renderer="polyline"`` mode).
"""
from __future__ import annotations

from typing import Optional

from ..ir import Character
from .patch import _char_cut_paths
from .sutra import (
    CharLoader, PageGeometry, get_geometry,
    TRACE_FILL_DEFAULT, _render_skeleton_glyph, _wrap_svg,
)

# ---------------------------------------------------------------------------
# Element data — (Z, symbol, zh) in atomic-number order, Taiwan naming
# (國家教育研究院譯名: 43 鎝, 85 砈, 87 鍅, 71 鎦).
# ---------------------------------------------------------------------------

_SYMBOLS = (
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca "
    "Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr "
    "Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd "
    "Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg "
    "Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm "
    "Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og"
).split()

_ZH_NAMES = (
    "氫氦鋰鈹硼碳氮氧氟氖鈉鎂鋁矽磷硫氯氬鉀鈣"
    "鈧鈦釩鉻錳鐵鈷鎳銅鋅鎵鍺砷硒溴氪銣鍶釔鋯"
    "鈮鉬鎝釕銠鈀銀鎘銦錫銻碲碘氙銫鋇鑭鈰鐠釹"
    "鉕釤銪釓鋱鏑鈥鉺銩鐿鎦鉿鉭鎢錸鋨銥鉑金汞"
    "鉈鉛鉍釙砈氡鍅鐳錒釷鏷鈾錼鈽鋂鋦鉳鉲鑀鐨"
    "鍆鍩鐒鑪𨧀𨭎𨨏𨭆䥑鐽錀鎶鉨鈇鏌鉝鿬鿫"
)

assert len(_SYMBOLS) == 118 and len(_ZH_NAMES) == 118

# ---------------------------------------------------------------------------
# Category classification + print-friendly light tints
# ---------------------------------------------------------------------------

_CATEGORY_OF: dict[int, str] = {}


def _fill(zs, cat):
    for z in zs:
        _CATEGORY_OF[z] = cat


_fill((3, 11, 19, 37, 55, 87), "alkali")
_fill((4, 12, 20, 38, 56, 88), "alkaline")
_fill(tuple(range(21, 31)) + tuple(range(39, 49))
      + tuple(range(72, 81)) + tuple(range(104, 113)), "transition")
_fill((13, 31, 49, 50, 81, 82, 83, 84, 113, 114, 115, 116),
      "post_transition")
_fill((5, 14, 32, 33, 51, 52), "metalloid")
_fill((1, 6, 7, 8, 15, 16, 34), "nonmetal")
_fill((9, 17, 35, 53, 85, 117), "halogen")
_fill((2, 10, 18, 36, 54, 86, 118), "noble")
_fill(tuple(range(57, 72)), "lanthanide")
_fill(tuple(range(89, 104)), "actinide")

assert len(_CATEGORY_OF) == 118

CATEGORY_COLORS: dict[str, str] = {
    "alkali":          "#F9DCDC",
    "alkaline":        "#FAE8D2",
    "transition":      "#DCE9E6",
    "post_transition": "#E3E3EA",
    "metalloid":       "#EFEAD6",
    "nonmetal":        "#DFEEDA",
    "halogen":         "#F7F0CE",
    "noble":           "#DAE6F2",
    "lanthanide":      "#E6F1DA",
    "actinide":        "#E4E0EF",
}

CATEGORY_LABELS_ZH: dict[str, str] = {
    "alkali":          "鹼金屬",
    "alkaline":        "鹼土金屬",
    "transition":      "過渡金屬",
    "post_transition": "主族金屬",
    "metalloid":       "類金屬",
    "nonmetal":        "非金屬",
    "halogen":         "鹵素",
    "noble":           "惰性氣體",
    "lanthanide":      "鑭系",
    "actinide":        "錒系",
}


def _cell_of(z: int) -> tuple[int, int]:
    """(row, col) in display space. Rows 1-7 = periods; rows 8/9 =
    lanthanide / actinide pull-out rows (cols 3-17)."""
    if z == 1:
        return (1, 1)
    if z == 2:
        return (1, 18)
    if z in (3, 4):
        return (2, z - 2)
    if 5 <= z <= 10:
        return (2, z + 8)
    if z in (11, 12):
        return (3, z - 10)
    if 13 <= z <= 18:
        return (3, z)
    if 19 <= z <= 36:
        return (4, z - 18)
    if 37 <= z <= 54:
        return (5, z - 36)
    if z in (55, 56):
        return (6, z - 54)
    if 57 <= z <= 71:            # lanthanides → pull-out row
        return (8, z - 54)
    if 72 <= z <= 86:
        return (6, z - 68)
    if z in (87, 88):
        return (7, z - 86)
    if 89 <= z <= 103:           # actinides → pull-out row
        return (9, z - 86)
    if 104 <= z <= 118:
        return (7, z - 100)
    raise ValueError(f"bad atomic number {z}")


ELEMENTS: list[dict] = [
    {
        "z": z,
        "symbol": _SYMBOLS[z - 1],
        "zh": _ZH_NAMES[z - 1],
        "category": _CATEGORY_OF[z],
        "cell": _cell_of(z),
    }
    for z in range(1, 119)
]

# ---------------------------------------------------------------------------
# Page geometry (A4 landscape, mm)
# ---------------------------------------------------------------------------

_MARGIN_L = 10.0
_MARGIN_R = 6.0
_GRID_TOP = 20.0
_CELL_H   = 18.2
_ROW_GAP  = 5.0          # gap between period 7 and the pull-out rows
_TITLE_CY = 9.0
_TITLE_SIZE = 7.5
_LEGEND_Y = 197.0

_TEXT_COLOR = "#444444"
_FONT_STACK = "'Helvetica Neue', Arial, 'Noto Sans', sans-serif"


def _grid_metrics(geom: PageGeometry) -> tuple[float, float]:
    grid_w = geom.page_w_mm - _MARGIN_L - _MARGIN_R
    return grid_w / 18.0, _CELL_H


def _cell_origin(row: int, col: int, cell_w: float) -> tuple[float, float]:
    x = _MARGIN_L + (col - 1) * cell_w
    y = _GRID_TOP + (row - 1) * _CELL_H
    if row >= 8:                 # pull-out rows sit below a small gap
        y += _ROW_GAP
    return x, y


def _traced_chars(chars: str, cx: float, cy: float, size_mm: float,
                  char_loader: CharLoader, *, fill: str = "#333333",
                  gap_ratio: float = 1.15) -> str:
    """Draw a short CJK label as dark filled glyphs via the loader.

    Falls back to an SVG ``<text>`` element for any char the loader
    cannot supply (defensive — labels only use common chars).
    """
    n = len(chars)
    if n == 0:
        return ""
    step = size_mm * gap_ratio
    x0 = cx - step * (n - 1) / 2.0
    parts: list[str] = []
    for i, ch in enumerate(chars):
        x = x0 + i * step
        c = char_loader(ch)
        drawn = ""
        if c is not None:
            drawn = _char_cut_paths(c, x, cy, size_mm)
            if not drawn:
                drawn = _render_skeleton_glyph(c, x, cy, size_mm)
        if not drawn:
            drawn = (
                f'<text x="{x:.2f}" y="{cy + size_mm * 0.35:.2f}" '
                f'font-size="{size_mm:.2f}" text-anchor="middle" '
                f'fill="{fill}">{ch}</text>'
            )
        parts.append(drawn)
    return f'<g fill="{fill}" stroke="none">{"".join(parts)}</g>'


def _small_text(s: str, x: float, y: float, size: float,
                anchor: str = "start", weight: str = "normal") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size:.2f}" '
        f'font-family="{_FONT_STACK}" text-anchor="{anchor}" '
        f'font-weight="{weight}" fill="{_TEXT_COLOR}">{s}</text>'
    )


def render_periodic_table_page(
    *,
    char_loader: CharLoader,
    trace_fill: str = TRACE_FILL_DEFAULT,
    show_grid: bool = True,
    show_category_colors: bool = True,
    title: str = "元素週期表",
) -> str:
    """Render the full 118-element periodic-table 描紅 page (SVG, mm).

    Cells whose Chinese name cannot be loaded are left empty (grid +
    number + symbol still drawn) rather than failing the whole page.
    """
    geom = get_geometry("landscape")
    cell_w, cell_h = _grid_metrics(geom)

    bg_parts: list[str] = []
    grid_parts: list[str] = []
    text_parts: list[str] = []
    glyph_parts: list[str] = []
    skeleton_parts: list[str] = []

    # --- title -----------------------------------------------------------
    title_svg = _traced_chars(
        title, geom.page_w_mm / 2.0, _TITLE_CY, _TITLE_SIZE, char_loader,
    )

    # --- group / period labels -------------------------------------------
    for g in range(1, 19):
        x = _MARGIN_L + (g - 0.5) * cell_w
        text_parts.append(_small_text(str(g), x, _GRID_TOP - 1.5, 3.0,
                                      anchor="middle"))
    for p in range(1, 8):
        y = _GRID_TOP + (p - 0.5) * _CELL_H
        text_parts.append(_small_text(str(p), _MARGIN_L - 3.0, y + 1.0,
                                      3.0, anchor="middle"))

    # --- series pull-out row labels + in-table markers --------------------
    lan_color = CATEGORY_COLORS["lanthanide"]
    act_color = CATEGORY_COLORS["actinide"]
    for (row, marker, zh, color) in (
        (6, "57-71", "鑭系", lan_color),
        (7, "89-103", "錒系", act_color),
    ):
        x0, y0 = _cell_origin(row, 3, cell_w)
        if show_category_colors:
            bg_parts.append(
                f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{cell_w:.2f}" '
                f'height="{cell_h:.2f}" fill="{color}"/>'
            )
        text_parts.append(_small_text(
            marker, x0 + cell_w / 2, y0 + cell_h * 0.42, 2.8,
            anchor="middle"))
        glyph_parts.append(_traced_chars(
            zh, x0 + cell_w / 2, y0 + cell_h * 0.68, 3.2, char_loader,
            fill="#555555"))
    for (row, zh) in ((8, "鑭系元素"), (9, "錒系元素")):
        x0, y0 = _cell_origin(row, 1, cell_w)
        glyph_parts.append(_traced_chars(
            zh, x0 + cell_w, y0 + cell_h / 2, 3.4, char_loader,
            fill="#555555"))

    # --- element cells -----------------------------------------------------
    for el in ELEMENTS:
        row, col = el["cell"]
        x0, y0 = _cell_origin(row, col, cell_w)
        cx = x0 + cell_w / 2.0
        if show_category_colors:
            bg_parts.append(
                f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{cell_w:.2f}" '
                f'height="{cell_h:.2f}" '
                f'fill="{CATEGORY_COLORS[el["category"]]}"/>'
            )
        if show_grid:
            grid_parts.append(
                f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{cell_w:.2f}" '
                f'height="{cell_h:.2f}" fill="none" stroke="#999999" '
                f'stroke-width="0.18"/>'
            )
        text_parts.append(_small_text(str(el["z"]), x0 + 1.1, y0 + 3.1,
                                      2.4))
        text_parts.append(_small_text(el["symbol"], x0 + cell_w - 1.1,
                                      y0 + 3.4, 3.0, anchor="end",
                                      weight="bold"))
        # trace glyph — centred in the space below the number/symbol strip
        char_cy = y0 + 3.8 + (cell_h - 3.8) / 2.0
        char_size = min(cell_w, cell_h - 4.6) * 0.82
        c = char_loader(el["zh"])
        if c is None:
            continue
        drawn = _char_cut_paths(c, cx, char_cy, char_size)
        if drawn:
            glyph_parts.append(
                f'<g fill="{trace_fill}" stroke="none">{drawn}</g>')
        else:
            poly = _render_skeleton_glyph(c, cx, char_cy, char_size)
            if poly:
                skeleton_parts.append(poly)

    # --- legend -------------------------------------------------------------
    legend_parts: list[str] = []
    lx = _MARGIN_L
    for cat in ("alkali", "alkaline", "transition", "post_transition",
                "metalloid", "nonmetal", "halogen", "noble",
                "lanthanide", "actinide"):
        legend_parts.append(
            f'<rect x="{lx:.2f}" y="{_LEGEND_Y:.2f}" width="4" height="4" '
            f'fill="{CATEGORY_COLORS[cat]}" stroke="#999999" '
            f'stroke-width="0.15"/>'
        )
        zh = CATEGORY_LABELS_ZH[cat]
        legend_parts.append(_traced_chars(
            zh, lx + 6.0 + len(zh) * 1.5, _LEGEND_Y + 2.0, 3.0,
            char_loader, fill="#555555"))
        lx += 8.0 + len(zh) * 3.2 + 4.0

    inner = (
        f'<g id="pt-bg">{"".join(bg_parts)}</g>'
        f'<g id="pt-grid">{"".join(grid_parts)}</g>'
        f'<g id="pt-title">{title_svg}</g>'
        f'<g id="pt-text">{"".join(text_parts)}</g>'
        f'<g id="pt-trace">{"".join(glyph_parts)}</g>'
        + (
            f'<g id="pt-trace-skeleton" fill="none" stroke="{trace_fill}" '
            f'stroke-width="0.5" stroke-linecap="round">'
            f'{"".join(skeleton_parts)}</g>'
            if skeleton_parts else ""
        )
        + f'<g id="pt-legend">{"".join(legend_parts)}</g>'
    )
    return _wrap_svg(inner, geom=geom)


__all__ = [
    "ELEMENTS", "CATEGORY_COLORS", "CATEGORY_LABELS_ZH",
    "render_periodic_table_page",
]
