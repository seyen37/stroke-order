"""
Phase 5bo / 5ds: 元素週期表描紅字帖 exporter.

Renders the 118-element periodic table as a single A4-landscape 描紅
page in the **米字格抄經 style**: every occupied position is a 米字格
cell (thin border + faint 米-shaped helper guides) carrying only the
element's Chinese name as a faded trace glyph (描紅) — no atomic
numbers, no Latin symbols, no category tint, no legend.

5ds layout (per user spec): read **column-major, left → right**, each
column is a group and reads top → bottom:

- Group 1 (leftmost column): 氫 鋰 鈉 鉀 銣 銫 鍅
- Group 2: (blank period-1 cell) 鈹 鎂 鈣 鍶 鋇 鐳
- Group 3: (three blank cells) 鈧 釔 鑭 錒
- …the 18-group × 7-period main block, 氦 at the top-right (group 18)
- 鑭系 (58-71) and 錒系 (90-103) pulled out into two rows below a
  blank row; 鑭 (57) / 錒 (89) themselves sit in the main block (group 3).

Empty periodic-table gaps are left as true white space (no 米字格) so
the table's characteristic silhouette is visible. Only the title
「元素週期表」is drawn besides the cells.

CJK glyphs (title + names) are *traced* via the char loader — the same
``_char_cut_paths`` outline pipeline as sutra body pages, with skeleton
fallback — so the SVG renders correctly under cairosvg on hosts without
a CJK system font.
"""
from __future__ import annotations

from .patch import _char_cut_paths
from .sutra import (
    CharLoader, PageGeometry, get_geometry,
    TRACE_FILL_DEFAULT, _render_skeleton_glyph, _wrap_svg,
    GRID_LINE_COLOR, GRID_LINE_WIDTH,
    HELPER_LINE_COLOR, HELPER_LINE_WIDTH, HELPER_DASH,
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
# Category classification (retained for downstream reference / tests; the
# 米字格 render deliberately draws no category tint or legend).
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
    鑭系 / 錒系 pull-out rows (cols 3-16).

    5ds: 鑭 (57) / 錒 (89) sit in the main block at group 3 (rows 6/7);
    the pull-out rows carry the *remaining* series members (58-71 /
    90-103), matching the printed-table convention the user requested.
    """
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
    if z == 57:                     # 鑭 La → main block, group 3
        return (6, 3)
    if 58 <= z <= 71:               # 鑭系 (Ce…Lu) → pull-out row 8
        return (8, (z - 58) + 3)
    if 72 <= z <= 86:
        return (6, z - 68)
    if z in (87, 88):
        return (7, z - 86)
    if z == 89:                     # 錒 Ac → main block, group 3
        return (7, 3)
    if 90 <= z <= 103:              # 錒系 (Th…Lr) → pull-out row 9
        return (9, (z - 90) + 3)
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
_MARGIN_R = 8.0
_GRID_TOP = 24.0
_ROW_GAP  = 8.0          # blank row between period 7 and the pull-out rows
_TITLE_CY = 12.0
_TITLE_SIZE = 6.5
_N_GROUPS = 18


def _grid_metrics(geom: PageGeometry) -> tuple[float, float]:
    """Square 米字格 cell sized to fit 18 groups across the page width."""
    grid_w = geom.page_w_mm - _MARGIN_L - _MARGIN_R
    cell = grid_w / _N_GROUPS
    return cell, cell


def _cell_origin(row: int, col: int, cell_w: float,
                 cell_h: float) -> tuple[float, float]:
    x = _MARGIN_L + (col - 1) * cell_w
    y = _GRID_TOP + (row - 1) * cell_h
    if row >= 8:                 # pull-out rows sit below a blank row
        y += _ROW_GAP
    return x, y


def _mizige_cell(x0: float, y0: float, cell_w: float, cell_h: float) -> str:
    """One 米字格 cell: thin border + faint dashed cross + two diagonals
    (identical helper geometry to sutra body pages)."""
    x_mid = x0 + cell_w / 2
    y_mid = y0 + cell_h / 2
    x1 = x0 + cell_w
    y1 = y0 + cell_h
    hc = (f'stroke="{HELPER_LINE_COLOR}" stroke-width="{HELPER_LINE_WIDTH}" '
          f'stroke-dasharray="{HELPER_DASH}"')
    return (
        f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{cell_w:.2f}" '
        f'height="{cell_h:.2f}" fill="none" stroke="{GRID_LINE_COLOR}" '
        f'stroke-width="{GRID_LINE_WIDTH}"/>'
        f'<line x1="{x0:.2f}" y1="{y_mid:.2f}" x2="{x1:.2f}" '
        f'y2="{y_mid:.2f}" {hc}/>'
        f'<line x1="{x_mid:.2f}" y1="{y0:.2f}" x2="{x_mid:.2f}" '
        f'y2="{y1:.2f}" {hc}/>'
        f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" '
        f'{hc}/>'
        f'<line x1="{x0:.2f}" y1="{y1:.2f}" x2="{x1:.2f}" y2="{y0:.2f}" '
        f'{hc}/>'
    )


def _traced_chars(chars: str, cx: float, cy: float, size_mm: float,
                  char_loader: CharLoader, *, fill: str = "#555555",
                  gap_ratio: float = 1.15) -> str:
    """Draw a short CJK label (e.g. the title) as dark filled glyphs via
    the loader, centred at ``cx``. Missing glyphs fall back to ``<text>``."""
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


def render_periodic_table_page(
    *,
    char_loader: CharLoader,
    trace_fill: str = TRACE_FILL_DEFAULT,
    show_grid: bool = True,
    title: str = "元素週期表",
) -> str:
    """Render the 118-element periodic table as a 米字格 描紅 page (SVG, mm).

    Each occupied periodic-table position gets a 米字格 cell with the
    element's Chinese name as a faded trace glyph; gaps are white space.
    Cells whose name cannot be loaded keep the 米字格 (empty) rather than
    failing the page. ``show_grid=False`` omits the 米字格 lines (glyphs
    only). ``trace_fill`` tints the 描紅 glyphs.
    """
    geom = get_geometry("landscape")
    cell_w, cell_h = _grid_metrics(geom)
    char_size = min(cell_w, cell_h) * 0.78

    grid_parts: list[str] = []
    glyph_parts: list[str] = []
    skeleton_parts: list[str] = []

    # --- title -----------------------------------------------------------
    title_svg = _traced_chars(
        title, geom.page_w_mm / 2.0, _TITLE_CY, _TITLE_SIZE, char_loader,
    )

    # --- element cells ---------------------------------------------------
    for el in ELEMENTS:
        row, col = el["cell"]
        x0, y0 = _cell_origin(row, col, cell_w, cell_h)
        if show_grid:
            grid_parts.append(_mizige_cell(x0, y0, cell_w, cell_h))
        cx = x0 + cell_w / 2.0
        cy = y0 + cell_h / 2.0
        c = char_loader(el["zh"])
        if c is None:
            continue
        drawn = _char_cut_paths(c, cx, cy, char_size)
        if drawn:
            glyph_parts.append(
                f'<g fill="{trace_fill}" stroke="none">{drawn}</g>')
        else:
            poly = _render_skeleton_glyph(c, cx, cy, char_size)
            if poly:
                skeleton_parts.append(poly)

    inner = (
        f'<g id="pt-grid">{"".join(grid_parts)}</g>'
        f'<g id="pt-title">{title_svg}</g>'
        f'<g id="pt-trace">{"".join(glyph_parts)}</g>'
        + (
            f'<g id="pt-trace-skeleton" fill="none" stroke="{trace_fill}" '
            f'stroke-width="0.5" stroke-linecap="round">'
            f'{"".join(skeleton_parts)}</g>'
            if skeleton_parts else ""
        )
    )
    return _wrap_svg(inner, geom=geom)


__all__ = [
    "ELEMENTS", "CATEGORY_COLORS", "CATEGORY_LABELS_ZH",
    "render_periodic_table_page",
]
