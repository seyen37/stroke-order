"""
Phase 5bo / 5ds / 5du: 元素週期表描紅字帖 exporter.

5du (per user): render the periodic table on a **plain blank 抄經 sheet** —
i.e. reuse the real ``render_sutra_page`` (full 米字格 grid + 日期/抄寫者
header + outer frame, exactly like every other 抄經 body page) and simply
place the 118 element names at their periodic-table cell positions. The
empty periodic-table gaps (blank cells / blank rows / blank columns) are
just ordinary blank 米字格 cells — the "原味" of a practice sheet.

Column-major, left → right: group 1 (氫 鋰 鈉 鉀 銣 銫 鍅) is the leftmost
column; 氦 sits top-right (group 18); 鑭 (57) / 錒 (89) live in the main
block at group 3; 鑭系 (58-71) / 錒系 (90-103) drop to two pull-out rows
below a blank row. The whole thing is left-aligned in the standard 20×15
landscape grid, so a couple of columns and several rows stay blank.

CJK glyphs are traced via the char loader (``render_sutra_page`` handles
this), so the SVG renders correctly under cairosvg on hosts without a CJK
system font.
"""
from __future__ import annotations

from .sutra import (
    CharLoader, PageGeometry, get_geometry,
    TRACE_FILL_DEFAULT, render_sutra_page,
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
# 描紅 sheet deliberately draws no category tint or legend).
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
    """(row, col), 1-indexed. Rows 1-7 = periods; rows 8/9 = 鑭系 / 錒系
    pull-out rows (cols 3-16).

    鑭 (57) / 錒 (89) sit in the main block at group 3 (rows 6/7); the
    pull-out rows carry the remaining series members (58-71 / 90-103).
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


# 5dv: 版面偏移（使用者指定）——整體向下 3 行（上面空 3 格）、向右 1 格，
# 使 18 欄的週期表在 20 欄格中左右各留 1 空欄（水平置中）。
_ROW_OFFSET = 3
_COL_OFFSET = 1


def _grid_row(my_row: int) -> int:
    """Map the logical periodic-table row to a 0-indexed grid row.

    Periods 1-7 → grid rows 0-6; 鑭系/錒系 (logical rows 8/9) → grid rows
    8/9 (leaving grid row 7 blank as the 空白列). The whole block is then
    shifted down by ``_ROW_OFFSET`` so the top rows stay blank.
    """
    base = (my_row - 1) if my_row <= 7 else my_row
    return base + _ROW_OFFSET


def periodic_table_cells(geom: PageGeometry) -> list[str]:
    """Build the ``chars`` list for ``render_sutra_page`` (row-major /
    ``direction="horizontal"``): element names at their periodic-table
    grid positions, blank strings everywhere else.

    5dv: shifted down ``_ROW_OFFSET`` rows and right ``_COL_OFFSET`` cols
    so the 18-group table sits with one blank column on each side and a
    few blank rows above (centred, per the user's request).
    """
    cols, rows = geom.cols, geom.rows
    cells = [""] * (cols * rows)
    for el in ELEMENTS:
        my_row, my_col = el["cell"]
        grid_col = (my_col - 1) + _COL_OFFSET
        n = _grid_row(my_row) * cols + grid_col
        cells[n] = el["zh"]
    return cells


def render_periodic_table_page(
    *,
    char_loader: CharLoader,
    trace_fill: str = TRACE_FILL_DEFAULT,
    show_grid: bool = True,
    emit_cellmap: bool = False,
) -> str:
    """Render the periodic table on a standard blank 抄經 body sheet.

    Reuses ``render_sutra_page`` verbatim (full 米字格 grid + 日期/抄寫者
    header + outer frame); the 118 element names are placed at their
    periodic-table cell positions and every other cell stays a blank
    米字格. ``show_grid`` / helper lines follow the 抄經 convention.

    5dw: ``emit_cellmap`` forwards straight to ``render_sutra_page``. With
    it on, each element cell (one CJK glyph per 米字格) gets a transparent
    ``data-char`` click rect, so the 逐字手寫 popup works on the periodic
    table exactly as it does on a 抄經 body page (preview only — download
    buttons leave it off). Blank periodic gaps emit no rect.
    """
    geom = get_geometry("landscape")
    cells = periodic_table_cells(geom)
    return render_sutra_page(
        cells,
        char_loader=char_loader,
        orientation="landscape",
        direction="horizontal",
        show_grid=show_grid,
        show_helper_lines=show_grid,
        trace_fill=trace_fill,
        emit_cellmap=emit_cellmap,
    )


__all__ = [
    "ELEMENTS", "CATEGORY_COLORS", "CATEGORY_LABELS_ZH",
    "periodic_table_cells", "render_periodic_table_page",
]
