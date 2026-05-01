"""
Stamp / 印章 mode (Phase 5ay).

Designed for laser-engraving wood seals — a sister of the Phase-5ax
patch mode but with traditional Chinese seal conventions baked in.

Why a separate mode (not just another patch preset)
---------------------------------------------------
- **Single-layer output** — the laser doesn't care about cut vs write;
  one black outline path per element.
- **Right-to-left vertical reading** — official-stamp text follows
  the 右起直書 convention; patch mode reads left-to-right.
- **Multi-row grid layouts** — 公司章 / 官章 traditionally arrange
  6-9 chars in a 2×3 or 3×3 grid, not a horizontal line.
- **Optional double border** — typical 公司章 has two concentric
  rectangles separated by ~0.8mm; patch mode never needs that.
- **Arc text + centre** — 圓戳章 puts a unit name around the rim and
  a single anchor character (e.g. "業務") in the middle.

Both modes share :class:`SvgDecoration` (Phase 5ax) and
:func:`show_border=False` for "give me just the inside, I'll add my
own border in a design tool later."
"""
from __future__ import annotations

import math

from typing import Callable, Literal, Optional

from ..ir import Character, EM_SIZE
from .patch import (
    SvgDecoration,
    _char_cut_paths,
    _char_cut_paths_stretched,
    _ensure_polygon,
    _polygon_to_svg_path,
    _decoration_svg,
    _polygon_to_gcode_path,
    _outline_to_polyline,
    _transform_pt,
)
from ..shapes import Circle, Ellipse, Polygon, make_shape


StampPreset = Literal[
    "square_name",      # 1-4 chars, individual signature seal
    "square_official",  # 2-9 chars, company / official seal
    "round",            # ring text + centre char
    "oval",             # 1-2 horizontal lines, acceptance seal
    "rectangle_title",  # 2 lines: title row + name row
]


# Phase 12c: 陰刻 (concave, 白文) vs 陽刻 (convex, 朱文)
# 陰刻：字凹下、雷射沿字筆劃路徑走、白底紅字描邊
# 陽刻：字凸出、雷射光柵掃描鋪滿背景、紅底白字
EngraveMode = Literal["concave", "convex"]


CharLoader = Callable[[str], Optional[Character]]


# ---------------------------------------------------------------------------
# Layout helpers — auto-grid + arc text
# ---------------------------------------------------------------------------


def _auto_grid_dims(n: int) -> tuple[int, int]:
    """Pick (rows, cols) for ``square_official`` based on character count.

    Traditional rules:
    - 1-3 chars → 1 column (vertical strip)
    - 4 chars   → 2×2
    - 5-6 chars → 2×3 (2 cols × 3 rows, right-to-left columns)
    - 7-9 chars → 3×3
    """
    if n <= 0:
        return (1, 1)
    if n <= 3:
        return (n, 1)
    if n == 4:
        return (2, 2)
    if n <= 6:
        return (3, 2)
    return (3, 3)


def _grid_positions_right_to_left(
    n: int, rows: int, cols: int,
    inner_w: float, inner_h: float,
    centre_x: float, centre_y: float,
) -> list[tuple[float, float]]:
    """Position ``n`` chars in a (rows × cols) grid, **right column first**.

    Reading order: top-right → bottom-right → top-(right-1) → … →
    bottom-left. This is the traditional Chinese seal convention; it
    looks alien to left-to-right readers but is what every 公司章 uses.

    Returns ``[(cx, cy), ...]`` in reading order — the caller pairs
    them with ``chars[i]`` directly.
    """
    if rows <= 0 or cols <= 0 or n <= 0:
        return []
    cell_w = inner_w / cols
    cell_h = inner_h / rows
    # Top-left corner of the grid (in absolute mm).
    grid_x0 = centre_x - inner_w / 2 + cell_w / 2
    grid_y0 = centre_y - inner_h / 2 + cell_h / 2
    out: list[tuple[float, float]] = []
    # Right column first (traditional). For each column, top-to-bottom.
    for col in range(cols - 1, -1, -1):
        for row in range(rows):
            if len(out) >= n:
                return out
            cx = grid_x0 + col * cell_w
            cy = grid_y0 + row * cell_h
            out.append((cx, cy))
    return out


def _arc_text_positions(
    n: int, ring_radius: float, centre_x: float, centre_y: float,
    *, span_deg: float = 240.0, start_deg: float = -120.0,
) -> list[tuple[float, float, float]]:
    """Distribute ``n`` chars along a circular arc, returning
    ``(cx, cy, rotation_deg)`` for each.

    Defaults span 240° centred on top — the classic 圓戳章 outer ring,
    leaving the bottom 120° clear for an optional star / dot decoration.
    """
    if n <= 0:
        return []
    if n == 1:
        # Single char goes at the apex.
        theta_deg = start_deg + span_deg / 2.0
        rad = math.radians(theta_deg)
        return [(
            centre_x + ring_radius * math.cos(rad),
            centre_y + ring_radius * math.sin(rad),
            theta_deg + 90.0,   # tangent rotation
        )]
    out: list[tuple[float, float, float]] = []
    for i in range(n):
        # Even spacing INCLUDING endpoints.
        t = i / (n - 1)
        theta_deg = start_deg + span_deg * t
        rad = math.radians(theta_deg)
        out.append((
            centre_x + ring_radius * math.cos(rad),
            centre_y + ring_radius * math.sin(rad),
            theta_deg + 90.0,   # rotate so chars stand "up" on the arc
        ))
    return out


# ---------------------------------------------------------------------------
# Border builders
# ---------------------------------------------------------------------------


def _stamp_border_polys(
    preset: StampPreset,
    width_mm: float,
    height_mm: float,
    *,
    double_border: bool = False,
    double_gap_mm: float = 0.8,
) -> list:
    """Return the border shapes (one or two concentric polygons).

    Single-border default; ``double_border=True`` adds an inner shrunk
    copy ``double_gap_mm`` smaller on each side. Returns a list of
    Polygon-or-Circle-or-Ellipse objects so the caller can render
    each independently.
    """
    cx, cy = width_mm / 2, height_mm / 2

    def _outer():
        if preset == "round":
            return Circle(cx, cy, min(width_mm, height_mm) / 2)
        if preset == "oval":
            return Ellipse(cx, cy, width_mm / 2, height_mm / 2)
        # rectangular / square presets
        return Polygon(vertices=[
            (0, 0), (width_mm, 0), (width_mm, height_mm), (0, height_mm),
        ])

    polys = [_outer()]
    if double_border:
        gap = double_gap_mm
        if preset == "round":
            r = min(width_mm, height_mm) / 2 - gap
            if r > 0:
                polys.append(Circle(cx, cy, r))
        elif preset == "oval":
            polys.append(Ellipse(
                cx, cy,
                max(width_mm / 2 - gap, 0.1),
                max(height_mm / 2 - gap, 0.1),
            ))
        else:
            polys.append(Polygon(vertices=[
                (gap, gap),
                (width_mm - gap, gap),
                (width_mm - gap, height_mm - gap),
                (gap, height_mm - gap),
            ]))
    return polys


# ---------------------------------------------------------------------------
# Per-preset placement
# ---------------------------------------------------------------------------


def _placements_for_preset(
    preset: StampPreset,
    chars: list[Character],
    width_mm: float, height_mm: float,
    char_size_mm: float,
    *,
    border_padding_mm: float = 0.8,
    double_border: bool,
    double_gap_mm: float,
    layout_5char: str = "2plus3",
    char_offsets: list[tuple[float, float]] = None,
) -> list[tuple[Character, float, float, float, float, float]]:
    """Return ``[(char, cx_mm, cy_mm, rotation_deg, w_mm, h_mm), ...]``.

    ``(w_mm, h_mm)`` are independent per-character width / height. Most
    presets pass ``w == h == char_size_mm`` (uniform scale, identical to
    pre-refactor behaviour). Specific layouts override:
    - ``square_name`` 3-字 1+2 traditional: surname stretched (w small,
      h large) — see line ~233.
    - ``round`` centre char: 1.4× uniform scale.

    Non-uniform stretch (w != h) renders via
    :func:`_char_cut_paths_stretched` instead of the uniform-scale
    :func:`_char_cut_paths`.
    """
    cx, cy = width_mm / 2.0, height_mm / 2.0
    inset = border_padding_mm + (double_gap_mm if double_border else 0)
    # Bug fix (12b-5): 過去用 max(_, char_size_mm) 會讓 user 改 char_size_mm
    # 時意外把 inner 拉大、外框 inset 縮小，造成「字大小設大 → 章面也跟著
    # 變大」的錯覺。改成純安全下限（1.0 mm 避免 inner 變負）。
    inner_w = max(width_mm - 2 * inset, 1.0)
    inner_h = max(height_mm - 2 * inset, 1.0)
    n = len(chars)
    if n == 0:
        return []

    placements: list[
        tuple[Character, float, float, float, float, float]] = []

    def _add(c, x, y, rot, sz):
        """Uniform-scale placement helper: width = height = sz."""
        placements.append((c, x, y, rot, sz, sz))

    if preset == "square_name":
        # Phase 12e: square_name 上限 5 字（業界 1.2cm 章 1-5 字常見），
        # 6+ 字截斷只取前 5（呼叫端應在前端警示，後端做 safety net）。
        if n > 5:
            chars = chars[:5]
            n = 5
        if n == 1:
            # Phase 12d: 1 字章業界慣例 — 字撐滿章面，不套 char_size_mm cap。
            # 豬豬小姐 0.7-1.5cm 1 字章「檀」「福」字佔 90%+，不留 cell padding。
            # ratio 0.96 比 4 字 2×2 的 0.92 更滿（沒有字之間互碰問題）。
            SINGLE_CHAR_FILL_RATIO = 0.96
            sz = min(inner_w, inner_h) * SINGLE_CHAR_FILL_RATIO
            _add(chars[0], cx, cy, 0.0, sz)
        elif n == 5:
            # Phase 12e: 5 字 layout — 兩種變體可切（layout_5char 參數）：
            #   "3plus2"（預設）：右欄 3 字 + 左欄 2 字（傳統台灣印章右起讀）
            #   "2plus3"：右欄 2 字 + 左欄 3 字（日本姓名章 / 特殊變體）
            #
            # 共通：欄寬 50% inner_w；3 字欄字 cell h 30%；2 字欄 cell h 46%。
            # 字身用 non-uniform scale，多字欄字會稍扁。
            right_x = cx + inner_w * 0.25
            left_x = cx - inner_w * 0.25
            half_w = inner_w * 0.50
            cell_h_3 = inner_h * 0.30  # 3 字欄每格 h
            cell_h_2 = inner_h * 0.46  # 2 字欄每格 h
            top_3 = cy - inner_h * 0.32
            mid_3 = cy
            bot_3 = cy + inner_h * 0.32
            top_2 = cy - inner_h * 0.23
            bot_2 = cy + inner_h * 0.23

            if layout_5char == "2plus3":
                # 右 2 + 左 3：右欄 chars[0/1]、左欄 chars[2/3/4]
                placements.append((chars[0], right_x, top_2, 0.0, half_w, cell_h_2))
                placements.append((chars[1], right_x, bot_2, 0.0, half_w, cell_h_2))
                placements.append((chars[2], left_x, top_3, 0.0, half_w, cell_h_3))
                placements.append((chars[3], left_x, mid_3, 0.0, half_w, cell_h_3))
                placements.append((chars[4], left_x, bot_3, 0.0, half_w, cell_h_3))
            else:  # "3plus2"（預設）
                # 右 3 + 左 2：右欄 chars[0/1/2]、左欄 chars[3/4]
                placements.append((chars[0], right_x, top_3, 0.0, half_w, cell_h_3))
                placements.append((chars[1], right_x, mid_3, 0.0, half_w, cell_h_3))
                placements.append((chars[2], right_x, bot_3, 0.0, half_w, cell_h_3))
                placements.append((chars[3], left_x, top_2, 0.0, half_w, cell_h_2))
                placements.append((chars[4], left_x, bot_2, 0.0, half_w, cell_h_2))
        elif n == 3:
            # Taiwan traditional 1+2 layout (Phase 11f tuned for fuller fill):
            # Right column: surname (chars[0]) NON-UNIFORMLY stretched —
            #   width = ~50% inner_w, height = ~92% inner_h (filling almost
            #   to the border for visual weight). Surname is the focal
            #   point of 私章.
            # Left column: given names (chars[1], chars[2]), uniform scale,
            #   stacked top/bottom each ~46% of inner height.
            right_x = cx + inner_w * 0.25
            right_w = inner_w * 0.50
            right_h = inner_h * 0.92
            placements.append((chars[0], right_x, cy, 0.0, right_w, right_h))
            left_x = cx - inner_w * 0.25
            left_size = min(inner_h * 0.46, inner_w * 0.50)
            top_y = cy - inner_h * 0.23
            bot_y = cy + inner_h * 0.23
            _add(chars[1], left_x, top_y, 0.0, left_size)
            _add(chars[2], left_x, bot_y, 0.0, left_size)
        else:
            # 1-2 chars: vertical strip; 4+ chars: 2×2 grid (5+ overflow).
            if n <= 2:
                rows, cols = n, 1
            else:  # n >= 4
                rows, cols = 2, 2
            coords = _grid_positions_right_to_left(
                n, rows, cols, inner_w, inner_h, cx, cy)
            # Bug fix (12b-5): 過去用 char_size_mm 當字身大小，搭配 11g
            # bbox-based scale 會把字 outline 撐到 char_size_mm（不管 cell
            # 多小），4 字 cell ≈ 4mm 但 char_size_mm 預設 5mm 就會超出 →
            # 字嚴重重疊。改用 cell-based size，char_size_mm 當「上限 cap」。
            cell_w = inner_w / cols
            cell_h = inner_h / rows
            cell_size = min(cell_w, cell_h)
            # 12b-7: cell 內留 8% padding，字 outline bbox 撐到 cell 92%。
            # 防 4 字 2×2 layout 字邊互碰、提升視覺呼吸感。3 字 1+2 layout
            # 因為已有 inner_h*0.92 比例不需此處再縮。
            CELL_FILL_RATIO = 0.92
            cell_fill = cell_size * CELL_FILL_RATIO
            sz = (min(cell_fill, char_size_mm)
                  if char_size_mm > 0 else cell_fill)
            for c, (x, y) in zip(chars, coords):
                _add(c, x, y, 0.0, sz)

    elif preset == "square_official":
        rows, cols = _auto_grid_dims(n)
        coords = _grid_positions_right_to_left(
            n, rows, cols, inner_w, inner_h, cx, cy)
        for c, (x, y) in zip(chars, coords):
            _add(c, x, y, 0.0, char_size_mm)

    elif preset == "round":
        # First (n-1) chars on outer arc, last char in centre.
        radius = min(width_mm, height_mm) / 2 - inset - char_size_mm * 0.55
        if n >= 2:
            arc_chars = chars[:-1]
            ring = _arc_text_positions(
                len(arc_chars), radius, cx, cy,
                span_deg=240.0, start_deg=-120.0,
            )
            for c, (x, y, rot) in zip(arc_chars, ring):
                _add(c, x, y, rot, char_size_mm)
            # Centre char 1.4× larger for visual weight.
            _add(chars[-1], cx, cy, 0.0, char_size_mm * 1.4)
        else:
            _add(chars[0], cx, cy, 0.0, char_size_mm)

    elif preset == "oval":
        # 1-2 horizontal lines, top-to-bottom reading.
        if n <= 4:
            spacing = inner_w / max(n, 1)
            x0 = cx - inner_w / 2 + spacing / 2
            for i, c in enumerate(chars):
                _add(c, x0 + i * spacing, cy, 0.0, char_size_mm)
        else:
            half = (n + 1) // 2
            top_row = chars[:half]
            bot_row = chars[half:]
            for row_chars, y_off in [
                (top_row, cy - inner_h * 0.22),
                (bot_row, cy + inner_h * 0.22),
            ]:
                m = len(row_chars)
                if m == 0:
                    continue
                spacing = inner_w / m
                x0 = cx - inner_w / 2 + spacing / 2
                for i, c in enumerate(row_chars):
                    _add(c, x0 + i * spacing, y_off, 0.0, char_size_mm)

    elif preset == "rectangle_title":
        half = (n + 1) // 2
        top_row = chars[:half]
        bot_row = chars[half:]
        for row_chars, y_off in [
            (top_row, cy - inner_h * 0.25),
            (bot_row, cy + inner_h * 0.25),
        ]:
            m = len(row_chars)
            if m == 0:
                continue
            spacing = inner_w / m
            x0 = cx - inner_w / 2 + spacing / 2
            for i, c in enumerate(row_chars):
                _add(c, x0 + i * spacing, y_off, 0.0, char_size_mm)

    # Phase 12g: 每字位移微調（char_offsets）+ bounds clamp。
    # char_offsets[i] = (dx, dy) mm，套用後字 outline bbox 不能超出 inner box
    # （邊框內側留 inset 邊距）。超過則 clamp 到合法範圍。
    if char_offsets:
        clamped: list[tuple[Character, float, float, float, float, float]] = []
        inner_left = inset
        inner_right = width_mm - inset
        inner_top = inset
        inner_bot = height_mm - inset
        for i, (c, pcx, pcy, prot, pw, ph) in enumerate(placements):
            dx, dy = (0.0, 0.0)
            if i < len(char_offsets):
                ofs = char_offsets[i]
                if ofs is not None and len(ofs) >= 2:
                    dx, dy = float(ofs[0]), float(ofs[1])
            new_cx = pcx + dx
            new_cy = pcy + dy
            # bounds clamp（字 outline bbox = (cx ± w/2, cy ± h/2)）
            half_w, half_h = pw / 2.0, ph / 2.0
            new_cx = max(inner_left + half_w, min(inner_right - half_w, new_cx))
            new_cy = max(inner_top + half_h, min(inner_bot - half_h, new_cy))
            clamped.append((c, new_cx, new_cy, prot, pw, ph))
        return clamped

    return placements


# ---------------------------------------------------------------------------
# Public renderers
# ---------------------------------------------------------------------------


def render_stamp_svg(
    text: str,
    char_loader: CharLoader,
    *,
    preset: StampPreset = "square_name",
    stamp_width_mm: float = 25.0,
    stamp_height_mm: float = 25.0,
    char_size_mm: float = 10.0,
    show_border: bool = True,
    double_border: bool = False,
    double_gap_mm: float = 0.8,
    border_padding_mm: float = 0.8,
    decorations: list[SvgDecoration] = None,
    color: str = "#000",
    stroke_width: float = 0.6,
    engrave_mode: EngraveMode = "concave",
    layout_5char: str = "2plus3",
    char_offsets: list[tuple[float, float]] = None,
) -> str:
    """Render a single stamp as one-layer SVG (laser-engrave-friendly).

    ``stroke_width`` (default 0.6mm, was 0.3mm in earlier phases) controls
    both the border line and the character-outline stroke. Bumped to 0.6mm
    for visual presence — 0.3mm rendered too thin on the screen preview
    given typical 25mm stamp sizes (ratio 1.2%). Laser engravers can still
    handle 0.6mm cleanly; further customisation via the parameter.

    ``engrave_mode`` (Phase 12c)：
    - ``"concave"``（陰刻、白文，預設、向後相容）：字凹下、白底紅字描邊
    - ``"convex"``（陽刻、朱文）：字凸出、紅底白字（fill 模式）
    """
    decorations = decorations or []
    chars: list[Character] = []
    for ch in text:
        if ch.isspace():
            continue
        c = char_loader(ch)
        if c is None:
            continue
        chars.append(c)

    placements = _placements_for_preset(
        preset, chars, stamp_width_mm, stamp_height_mm, char_size_mm,
        border_padding_mm=border_padding_mm,
        double_border=double_border, double_gap_mm=double_gap_mm,
        layout_5char=layout_5char,
        char_offsets=char_offsets,
    )

    # Build border path d-strings (used by both modes).
    border_d_list: list[str] = []
    if show_border:
        for shape in _stamp_border_polys(
            preset, stamp_width_mm, stamp_height_mm,
            double_border=double_border, double_gap_mm=double_gap_mm,
        ):
            poly = _ensure_polygon(shape)
            d = _polygon_to_svg_path(poly)
            if d:
                border_d_list.append(d)

    # Char outline SVG snippets (already EM-coords inside <g transform>).
    # Phase 11g uses _char_cut_paths_stretched uniformly with bbox-center alignment.
    char_pieces: list[str] = []
    for c, x, y, rot, w, h in placements:
        char_pieces.append(_char_cut_paths_stretched(c, x, y, w, h, rot))

    # Decorations.
    deco_pieces: list[str] = []
    for d in decorations:
        deco_pieces.append(_decoration_svg(d))

    svg_open = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {stamp_width_mm:.3f} {stamp_height_mm:.3f}" '
        f'width="{stamp_width_mm:.3f}mm" height="{stamp_height_mm:.3f}mm" '
        f'shape-rendering="geometricPrecision">'
    )

    if engrave_mode == "convex":
        # 陽刻 (朱文)：紅底 + 字白色填實。
        # Layer order (z-index 從低到高):
        #   1. 邊框 fill 紅色（章面內全部紅，傳統朱印色 #c33）
        #   2. 字 outline fill 白色（凸出效果）
        #   3. 邊框黑線描邊（清楚邊界）
        #   4. Decorations（透明可疊）
        # NB: 顏色硬編碼是傳統印章色彩慣例（朱印紅 + 白字 + 黑邊框），
        # 不像陰刻 stroke 顏色可由 UI 改 tint。
        CONVEX_BASE_RED = "#c33"
        CONVEX_CHAR_WHITE = "#fff"
        CONVEX_BORDER_BLACK = "#000"
        body_pieces: list[str] = []
        # Red fill base — outer border + 雙邊框時 inner 也填紅
        if border_d_list:
            for d in border_d_list:
                body_pieces.append(
                    f'<path d="{d}" fill="{CONVEX_BASE_RED}" stroke="none"/>'
                )
        # 字白色 fill — _char_cut_paths_stretched 路徑已封閉 (M ... Z)
        body_pieces.append(
            f'<g id="stamp-chars" fill="{CONVEX_CHAR_WHITE}" stroke="none">'
            f'{"".join(char_pieces)}</g>'
        )
        # 邊框描邊（在字上面，視覺上邊界清楚）
        if border_d_list:
            for d in border_d_list:
                body_pieces.append(
                    f'<path d="{d}" fill="none" stroke="{CONVEX_BORDER_BLACK}" '
                    f'stroke-width="{stroke_width}"/>'
                )
        body_pieces.extend(deco_pieces)
        return f'{svg_open}{"".join(body_pieces)}</svg>'

    # 陰刻 (concave，預設，向後相容)：字凹下、白底、字 outline 用 stroke
    border_pieces = [f'<path class="stamp-border" d="{d}"/>'
                     for d in border_d_list]
    return (
        f'{svg_open}'
        f'<g id="stamp-engrave" stroke="{color}" stroke-width="{stroke_width}" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round" '
        f'shape-rendering="geometricPrecision">'
        f'{"".join(border_pieces + char_pieces + deco_pieces)}</g></svg>'
    )


def render_stamp_gcode(
    text: str,
    char_loader: CharLoader,
    *,
    preset: StampPreset = "square_name",
    stamp_width_mm: float = 25.0,
    stamp_height_mm: float = 25.0,
    char_size_mm: float = 10.0,
    show_border: bool = True,
    double_border: bool = False,
    double_gap_mm: float = 0.8,
    border_padding_mm: float = 0.8,
    decorations: list[SvgDecoration] = None,
    feed: float = 1500.0,
    laser_power: int = 255,
    laser_on: str = None,
    laser_off: str = "M5",
    engrave_mode: EngraveMode = "concave",
    line_pitch_mm: float = 0.1,
    layout_5char: str = "2plus3",
    char_offsets: list[tuple[float, float]] = None,
) -> str:
    """G-code for a laser engraver. ``M3 S{laser_power}`` at full power
    by default; override ``laser_on`` / ``laser_off`` for diode-laser
    firmwares that use ``M106``/``M107`` etc.

    ``engrave_mode`` (Phase 12c)：
    - ``"concave"``（陰刻、預設）：雷射沿字 outline 走，字凹下
    - ``"convex"``（陽刻）：雷射光柵掃描鋪滿『字外』背景區域，字凸出。
      ``line_pitch_mm`` 控制掃描密度（0.05 細緻 / 0.10 標準 / 0.20 粗略）。
    """
    if laser_on is None:
        laser_on = f"M3 S{laser_power}"
    decorations = decorations or []
    chars: list[Character] = []
    for ch in text:
        if ch.isspace():
            continue
        c = char_loader(ch)
        if c is None:
            continue
        chars.append(c)

    placements = _placements_for_preset(
        preset, chars, stamp_width_mm, stamp_height_mm, char_size_mm,
        border_padding_mm=border_padding_mm,
        double_border=double_border, double_gap_mm=double_gap_mm,
        layout_5char=layout_5char,
        char_offsets=char_offsets,
    )

    out: list[str] = [
        "; --- stroke-order stamp G-code (laser engrave) ---",
        f"; preset={preset}  stamp={stamp_width_mm}x{stamp_height_mm}mm  "
        f"char={char_size_mm}mm  show_border={show_border}",
        "G21 ; mm",
        "G90 ; absolute",
        laser_off,
    ]

    if show_border:
        for shape in _stamp_border_polys(
            preset, stamp_width_mm, stamp_height_mm,
            double_border=double_border, double_gap_mm=double_gap_mm,
        ):
            poly = _ensure_polygon(shape)
            out.extend(_polygon_to_gcode_path(
                poly, feed, laser_on, laser_off,
            ))

    # G-code 採 **bbox-based** non-uniform scale（與 SVG render 對齊）：
    # 字 outline bbox 撐滿 (w_mm, h_mm) cell，bbox 中心對到 (cx_mm, cy_mm)。
    # Phase 11g：跟 _char_cut_paths_stretched 一致使用 bbox-fill 而非
    # EM-fill，避免雷射雕刻的字也比 SVG 預覽小一圈（兩邊現在會視覺一致）。
    from .patch import _char_outline_bbox_full_em

    # 為了 12c 陽刻支援，先把所有 char outline 轉成 mm-space polylines.
    # 陰刻直接用這些當雕刻路徑；陽刻把它們當成「不該被光柵掃描」的禁區
    # 餵給 scanline_engrave_gcode（even-odd 自動處理 ON/OFF 區段）。
    char_polylines_mm: list[list[tuple[float, float]]] = []
    for c, cx_mm, cy_mm, rot, w_mm, h_mm in placements:
        bbox = _char_outline_bbox_full_em(c)
        if bbox is None:
            continue
        min_x, min_y, max_x, max_y = bbox
        bbox_w_em = max_x - min_x
        bbox_h_em = max_y - min_y
        if bbox_w_em <= 0 or bbox_h_em <= 0:
            continue
        glyph_scale_x = w_mm / bbox_w_em
        glyph_scale_y = h_mm / bbox_h_em
        bcx_em = (min_x + max_x) / 2.0
        bcy_em = (min_y + max_y) / 2.0
        dx = cx_mm - bcx_em * glyph_scale_x
        dy = cy_mm - bcy_em * glyph_scale_y
        for stroke in c.strokes:
            if not stroke.outline:
                continue
            pts_em = _outline_to_polyline(stroke)
            if not pts_em:
                continue
            pts_mm: list[tuple[float, float]] = []
            for px, py in pts_em:
                sx = px * glyph_scale_x
                sy = py * glyph_scale_y
                if abs(rot) > 1e-6:
                    import math
                    rad = math.radians(rot)
                    cosr, sinr = math.cos(rad), math.sin(rad)
                    rcx, rcy = bcx_em * glyph_scale_x, bcy_em * glyph_scale_y
                    rx = (sx - rcx) * cosr - (sy - rcy) * sinr + rcx
                    ry = (sx - rcx) * sinr + (sy - rcy) * cosr + rcy
                    sx, sy = rx, ry
                pts_mm.append((dx + sx, dy + sy))
            if len(pts_mm) >= 2:
                char_polylines_mm.append(pts_mm)

    if engrave_mode == "convex":
        # 陽刻：scanline 鋪滿『字外』背景；字 outline 不單獨雕（會被光柵
        # 自動處理，雷射在字內 OFF）
        # Polygons 需要封閉首尾相同點才能 even-odd intersection 計算
        closed_polys = []
        for poly in char_polylines_mm:
            if poly[0] != poly[-1]:
                poly = poly + [poly[0]]
            closed_polys.append(poly)
        # 內框邊界 = 外框 - border_padding（雙邊框時再 - double_gap）
        inset = border_padding_mm + (double_gap_mm if double_border else 0)
        b_left = inset
        b_right = stamp_width_mm - inset
        b_top = inset
        b_bottom = stamp_height_mm - inset
        from .engrave import scanline_engrave_gcode
        scan_lines, stats = scanline_engrave_gcode(
            closed_polys,
            border_left=b_left, border_right=b_right,
            border_top=b_top, border_bottom=b_bottom,
            line_pitch=line_pitch_mm,
            feed=feed, laser_power=laser_power,
            laser_on="M3", laser_off=laser_off,
        )
        out.append(
            f"; engrave_mode=convex (陽刻)  scan_lines={stats['scan_lines']}  "
            f"on_segments={stats['on_segments']}  "
            f"cut={stats['total_cut_mm']:.1f}mm  "
            f"~{stats['estimated_min']:.2f}min @ {feed}mm/min"
        )
        out.extend(scan_lines)
    else:
        # 陰刻 (concave，預設)：每條 polyline 是一條雷射路徑
        for pts_mm in char_polylines_mm:
            x0, y0 = pts_mm[0]
            out.append(f"G0 X{x0:.3f} Y{y0:.3f}")
            out.append(laser_on)
            out.append("G4 P50")
            for px, py in pts_mm[1:]:
                out.append(f"G1 X{px:.3f} Y{py:.3f} F{feed}")
            out.append("G4 P50")
            out.append(laser_off)

    if decorations:
        out.append(
            f"; — {len(decorations)} decoration(s) skipped in G-code "
            "(use SVG download to keep them)"
        )
    out.append(laser_off)
    out.append("; done")
    return "\n".join(out) + "\n"


def stamp_capacity(
    *,
    preset: StampPreset,
    stamp_width_mm: float,
    stamp_height_mm: float,
    char_size_mm: float,
    border_padding_mm: float = 0.8,
    double_border: bool = False,
    double_gap_mm: float = 0.8,
) -> dict:
    """How many characters fit at the chosen size?"""
    inset = border_padding_mm + (double_gap_mm if double_border else 0)
    inner_w = max(stamp_width_mm - 2 * inset, 1.0)
    inner_h = max(stamp_height_mm - 2 * inset, 1.0)
    if preset == "square_name":
        max_chars = 4   # spec
    elif preset == "square_official":
        max_chars = 9   # 3×3 cap
    elif preset == "round":
        # Outer arc fits ~2πr/spacing chars + 1 centre.
        r = min(stamp_width_mm, stamp_height_mm) / 2 - inset
        arc_len = (240.0 / 360.0) * 2 * math.pi * r   # span 240°
        max_chars = max(int(arc_len / (char_size_mm * 1.2)), 1) + 1
    elif preset == "oval":
        per_row = max(int(inner_w / (char_size_mm * 1.1)), 1)
        max_chars = per_row * 2
    elif preset == "rectangle_title":
        per_row = max(int(inner_w / (char_size_mm * 1.1)), 1)
        max_chars = per_row * 2
    else:
        max_chars = 0
    return {
        "preset": preset,
        "max_chars": max_chars,
        "inner_size_mm": [round(inner_w, 2), round(inner_h, 2)],
    }


__all__ = [
    "StampPreset",
    "render_stamp_svg",
    "render_stamp_gcode",
    "stamp_capacity",
]
