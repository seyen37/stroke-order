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
    "square_name",      # 1-5 chars, individual signature seal (rectangular)
    "round_name",       # 1-5 chars, individual signature seal (circular) — Phase 12i
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
    - 10-12 chars → 3 cols × 4 rows (perfect for 12)  -- Phase 12l
    - 13-16 chars → 4×4 (perfect for 16)              -- Phase 12l
    """
    if n <= 0:
        return (1, 1)
    if n <= 3:
        return (n, 1)
    if n == 4:
        return (2, 2)
    if n <= 6:
        return (3, 2)
    if n <= 9:
        return (3, 3)
    if n <= 12:
        return (4, 3)
    return (4, 4)


# Phase 12l: square_official multi-short-col helpers ------------------------


def _square_official_grid_for(n: int) -> tuple[int, int] | None:
    """Return (cols, max_rows) for square_official non-uniform layouts.

    Only returns dims for "needs-short-col" char counts (deficit > 0
    within the canonical grid). Perfect counts (9/12/16) and 1-6 char
    layouts use the regular ``_auto_grid_dims`` path.
    """
    if n in (7, 8):
        return (3, 3)
    if n in (10, 11):
        return (3, 4)
    if n in (13, 14, 15):
        return (4, 4)
    return None


def _short_col_name_to_idx(name: str, cols: int) -> int | None:
    """Map a short-col position name to a column index (0=left).

    3-col stamps: ``right`` / ``middle`` / ``left``
    4-col stamps: ``right`` / ``mid-right`` / ``mid-left`` / ``left``

    Returns None for invalid name/cols combos so callers can skip.
    """
    if cols == 3:
        return {"right": 2, "middle": 1, "left": 0}.get(name)
    if cols == 4:
        return {
            "right": 3, "mid-right": 2, "mid-left": 1, "left": 0,
        }.get(name)
    return None


def _normalize_short_cols(value) -> list[str]:
    """Normalize layout_official_short_col into a clean string list.

    Accepts: None / "" / str / list[str]. Empty result falls back to
    the global default ``["right"]`` (Phase 12l 預設右行短).
    """
    if value is None:
        return ["right"]
    if isinstance(value, str):
        return [value] if value else ["right"]
    if isinstance(value, (list, tuple)):
        cleaned = [str(v) for v in value if v]
        return cleaned if cleaned else ["right"]
    return ["right"]


def _distribute_official_short(
    n: int, cols: int, max_rows: int, short_indices: list[int],
) -> list[int] | None:
    """Compute per-column char counts for a non-uniform square_official.

    Args:
        n: total char count.
        cols: column count.
        max_rows: max chars per col when col is "full".
        short_indices: col indices to be "short" (each shorted by ≥1).

    Returns a list of ``cols`` ints (chars per col), or ``None`` if
    the request is structurally impossible (e.g. more short cols than
    deficit, or a short col would end up with ≤0 chars).

    Distribution rule (Phase 12l 解讀 Y, "集中短"):
        deficit = cols * max_rows - n
        Each selected short col loses ``deficit // k`` chars; the
        first ``deficit % k`` short cols (rightmost first) lose one
        extra. So k=1 lumps the entire deficit on a single col.
    """
    deficit = cols * max_rows - n
    counts = [max_rows] * cols
    if deficit == 0:
        return counts
    if not short_indices:
        # No selection ⇒ default to rightmost col (matches UI default).
        short_indices = [cols - 1]
    short_indices = sorted(set(short_indices))
    if any(i < 0 or i >= cols for i in short_indices):
        return None
    k = len(short_indices)
    if k > deficit:
        return None  # can't shorten more cols than deficit allows
    base = deficit // k
    extra = deficit % k
    # Rightmost selected col gets the leftover-extra first (傳統右先收縮).
    sorted_desc = sorted(short_indices, reverse=True)
    for i, ci in enumerate(sorted_desc):
        amt = base + (1 if i < extra else 0)
        counts[ci] = max_rows - amt
        if counts[ci] <= 0:
            return None
    return counts


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


# Phase 12m-1: oval stamp structured layout helpers ------------------------


def _oval_arc_positions(
    n: int, *, inner_w: float, inner_h: float, cx: float, cy: float,
    top: bool, span_deg: float = 160.0, padding_ratio: float = 0.13,
) -> list[tuple[float, float, float]]:
    """Place ``n`` chars along the upper or lower half of an inner ellipse.

    Returns ``[(cx_mm, cy_mm, rotation_deg), ...]`` — caller pairs with
    ``Character`` objects + size.

    Rotation conventions (Phase 12m-1 patch — per-arc 朝外 direction):
    - **Top arc 頂部朝外**: ``rotation = theta + 90°`` — char's HEAD points
      OUTWARD (upward at top). Reads left→right at top.
    - **Bottom arc 底部朝外**: ``rotation = theta - 90°`` — char's FEET
      point OUTWARD (downward at bottom). Char remains UPRIGHT in viewer's
      frame (head up, feet down). Reads left→right.

    The two arcs together produce the classic 業界橢圓章 visual where
    BOTH top and bottom text reads naturally upright when viewing the
    stamp face — matching T-02 and similar industry references.

    ``padding_ratio`` shrinks the ellipse so chars don't touch the
    border (default 13% — patched up from 10% per visual feedback).
    """
    if n <= 0:
        return []
    a = (inner_w / 2.0) * (1.0 - padding_ratio)
    b = (inner_h / 2.0) * (1.0 - padding_ratio)
    if top:
        # Top half: left to right == theta increases from -90-span/2 → -90+span/2
        start_deg = -90.0 - span_deg / 2.0
        sweep_deg = span_deg
        rot_offset = 90.0       # 頂部朝外 — head outward at top
    else:
        # Bottom half: left to right == theta DECREASES from 90+span/2 → 90-span/2
        start_deg = 90.0 + span_deg / 2.0
        sweep_deg = -span_deg
        rot_offset = -90.0      # 底部朝外 — feet outward at bottom (12m-1 patch)
    out: list[tuple[float, float, float]] = []
    if n == 1:
        # Single char at apex (top or bottom centre)
        theta_deg = -90.0 if top else 90.0
        rad = math.radians(theta_deg)
        out.append((
            cx + a * math.cos(rad),
            cy + b * math.sin(rad),
            theta_deg + rot_offset,
        ))
        return out
    for i in range(n):
        t = i / (n - 1)
        theta_deg = start_deg + sweep_deg * t
        rad = math.radians(theta_deg)
        out.append((
            cx + a * math.cos(rad),
            cy + b * math.sin(rad),
            theta_deg + rot_offset,
        ))
    return out


def _oval_arc_char_size(
    n: int, *, inner_w: float, inner_h: float, span_deg: float = 160.0,
    padding_ratio: float = 0.13, char_size_cap: float,
    fill_ratio: float = 0.92,
) -> float:
    """Auto-fit char size for arc text — limited by per-char arc chord.

    Approximates ellipse arc length via average-radius × span_rad, then
    divides by N for per-char chord. Capped by ``char_size_cap`` (the
    user-supplied ``char_size_mm`` upper bound).
    """
    if n <= 0:
        return char_size_cap
    a = (inner_w / 2.0) * (1.0 - padding_ratio)
    b = (inner_h / 2.0) * (1.0 - padding_ratio)
    avg_r = (a + b) / 2.0
    arc_len_approx = avg_r * math.radians(span_deg)
    per_char = arc_len_approx / max(n, 1)
    return min(char_size_cap, per_char * fill_ratio)


def _oval_body_layout(
    lines_chars: list[list[Character]], *,
    inner_w: float, inner_h: float, cx: float, cy: float,
    char_size_cap: float,
) -> list[tuple[Character, float, float, float, float, float]]:
    """Lay out 1-3 horizontal body lines centred inside an oval.

    Args:
        lines_chars: list of (already-loaded) Character lists, one per line.
            Empty inner lists are skipped. Outer list capped at 3.
        char_size_cap: upper bound on char width/height (matches the
            user's ``char_size_mm`` setting).

    Each line auto-fits its width based on the ellipse's available
    horizontal span at the line's y, so a 3-char title line gets large
    chars while a 15-char contact line gets compact chars — matching
    real-world 橢圓章 visual hierarchy (cf. T-02 reference).

    Returns ``[(char, cx, cy, rot, w, h), ...]``.
    """
    # Drop empty lines, cap to 3
    lines_chars = [ln for ln in lines_chars if ln][:3]
    n_lines = len(lines_chars)
    if n_lines == 0:
        return []
    # Per-line y offset (ratio of inner_h half) and max char height (ratio
    # of inner_h). Tuned to match T-01/T-02/T-04 reference visual.
    # 12m-1 patch: 拉近 2/3 行 spacing 給上下 arc 留更多空間（user 反映兩
    # body line 之間距太大，title 跟 contact 互相隔開過遠）。
    Y_OFFSETS = {
        1: [0.0],
        2: [-0.10, 0.10],     # was ±0.18 → 更緊湊置中
        3: [-0.20, 0.0, 0.20],  # was ±0.25 → 同上邏輯
    }
    MAX_H_PER_LINE = {1: 0.40, 2: 0.20, 3: 0.15}  # 2/3 行字身略縮
    offs = Y_OFFSETS[n_lines]
    max_h = MAX_H_PER_LINE[n_lines] * inner_h
    a = inner_w / 2.0
    b = inner_h / 2.0
    USABLE_WIDTH_RATIO = 0.80   # leave 10% margin each side at full width
    out: list[tuple[Character, float, float, float, float, float]] = []
    for line_chars, y_off_ratio in zip(lines_chars, offs):
        n = len(line_chars)
        if n == 0:
            continue
        y = cy + y_off_ratio * inner_h
        # Available x-half-width at this y from ellipse equation
        y_norm = (y - cy) / b
        if abs(y_norm) >= 0.999:
            continue  # line off the ellipse — skip silently
        x_half = a * math.sqrt(1.0 - y_norm * y_norm)
        usable_w = USABLE_WIDTH_RATIO * 2.0 * x_half
        cell_w = usable_w / n
        # Char size: limited by cell width AND vertical band height AND cap
        sz = min(char_size_cap, cell_w * 0.92, max_h)
        # Centre line horizontally
        total_w = cell_w * n
        x_start = cx - total_w / 2.0 + cell_w / 2.0
        for i, c in enumerate(line_chars):
            x = x_start + i * cell_w
            out.append((c, x, y, 0.0, sz, sz))
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
        if preset in ("round", "round_name"):
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
        if preset in ("round", "round_name"):
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
    layout_2char: str = "horizontal",
    layout_official_short_col=("right",),
    char_offsets: list[tuple[float, float]] = None,
    # Phase 12m-1: oval structured fields (only consumed when preset="oval")
    oval_arc_top_chars: list[Character] = None,
    oval_arc_bottom_chars: list[Character] = None,
    oval_body_lines_chars: list[list[Character]] = None,
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
    # Phase 12m-1: oval preset 結構化 fields 可能讓 `chars` 是空的（user 只填
    # oval_arc_top / oval_arc_bottom / oval_body_lines），此時不能 early-return。
    _has_oval_structured = preset == "oval" and (
        (oval_arc_top_chars and len(oval_arc_top_chars) > 0)
        or (oval_arc_bottom_chars and len(oval_arc_bottom_chars) > 0)
        or (oval_body_lines_chars and any(
            ln for ln in oval_body_lines_chars if ln))
    )
    if n == 0 and not _has_oval_structured:
        return []

    placements: list[
        tuple[Character, float, float, float, float, float]] = []

    def _add(c, x, y, rot, sz):
        """Uniform-scale placement helper: width = height = sz."""
        placements.append((c, x, y, rot, sz, sz))

    # Phase 12i: square_name 跟 round_name 共用 1-5 字 layout 邏輯。
    # 差別在 effective inner area：方章 = 整 inner，圓章 = inner * shrink
    # （shrink 因字數而異，因為角落 cell 距圓心遠，越多字越要收縮）。
    if preset in ("square_name", "round_name"):
        if preset == "round_name":
            # 圓章字身收縮 ratio 依字數而定（角落 cell 在 4-5 字最嚴格）：
            # 1 字：置中，bbox 角落到圓心距離 = bbox 半邊長
            # 2 字：左右排列 cell 中心離圓心 0.23×inner，角落還在圓內
            # 3 字：1+2 layout 中央 cell 在圓心附近
            # 4 字：2×2 角落 cell，bbox 角落到圓心距離大
            # 5 字：2+3 column 角落 cell 最遠
            n_clamped = min(n, 5)
            # Phase 12j: 圓章字 outline 預留 padding 不貼圓邊（解 user
            # 抱怨『字碰外框 stroke』）。1/3 字 ratio 從 0.96/0.93 → 0.85；
            # 5 字從 0.72 → 0.78（OTF 字筆劃不到 bbox 角落，視覺 OK）。
            ROUND_SHRINK_BY_N = {
                1: 0.85, 2: 0.90, 3: 0.85,
                4: 0.78, 5: 0.78,
            }
            shrink = ROUND_SHRINK_BY_N.get(n_clamped, 0.85)
            inner_w = inner_w * shrink
            inner_h = inner_h * shrink
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
        elif n == 2:
            # Phase 12h: 2 字 layout — 字身 non-uniform stretch（跟 3 字 1+2
            # 左欄堆疊 0.46 ratio + 0.92 拉長比例一致）：
            #   "horizontal"（預設，右起讀）：左右排列，右字 chars[0] + 左字 chars[1]
            #   "vertical"：上下排列，上字 chars[0] + 下字 chars[1]
            # 字身 cell：在排列方向 ~46% inner（兩字共 92%，留 4% 中央 gap），
            # 垂直方向 ~92% inner（拉長到接近上下邊框）。
            STRETCH_LONG = 0.92   # 拉長方向比例（接近邊框）
            STRETCH_PAIR = 0.46   # 對偶字方向比例（兩字共 92%）
            CENTER_OFFSET = 0.23  # 兩字偏移（cell 中心離章面中心 = inner * 0.23）
            if layout_2char == "vertical":
                # 上下排列：寬拉長、高 46%
                cell_w = inner_w * STRETCH_LONG
                cell_h = inner_h * STRETCH_PAIR
                top_y = cy - inner_h * CENTER_OFFSET
                bot_y = cy + inner_h * CENTER_OFFSET
                placements.append((chars[0], cx, top_y, 0.0, cell_w, cell_h))
                placements.append((chars[1], cx, bot_y, 0.0, cell_w, cell_h))
            else:  # "horizontal"（預設）
                # 左右排列右起讀：右字 chars[0]、左字 chars[1]
                cell_w = inner_w * STRETCH_PAIR
                cell_h = inner_h * STRETCH_LONG
                right_x = cx + inner_w * CENTER_OFFSET
                left_x = cx - inner_w * CENTER_OFFSET
                placements.append((chars[0], right_x, cy, 0.0, cell_w, cell_h))
                placements.append((chars[1], left_x, cy, 0.0, cell_w, cell_h))
        else:
            # 1 char vertical strip (n=1 不會跑到這邊因為前面 n==1 分支)
            # 4+ chars: 2×2 grid (5+ overflow).
            if n == 1:
                rows, cols = 1, 1
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
        # Phase 12k-1: cell-based size + char_size_mm cap (跟 12b-5 一致)。
        # Phase 12l: 7-16 字統一 multi-short-col layout（最多 16 字，4×4 grid）。
        #   - 7-8 字 → 3 cols × 3 rows（deficit 2 / 1）
        #   - 10-11 字 → 3 cols × 4 rows（deficit 2 / 1）
        #   - 13-15 字 → 4 cols × 4 rows（deficit 3 / 2 / 1）
        #   - 9 / 12 / 16 字 perfect grid 走 _auto_grid_dims fallback
        #   layout_official_short_col 接受 list[str] 或 str，預設 ["right"]。
        official_dims = _square_official_grid_for(n)
        if official_dims is not None:
            cols, max_rows = official_dims
            short_names = _normalize_short_cols(layout_official_short_col)
            # Map name → idx (skip names invalid for this cols size)
            short_indices: list[int] = []
            for nm in short_names:
                idx = _short_col_name_to_idx(nm, cols)
                if idx is not None:
                    short_indices.append(idx)
            counts = _distribute_official_short(
                n, cols, max_rows, short_indices)
            if counts is None:
                # User-supplied combo invalid → safe fallback to default
                # (rightmost col absorbs entire deficit, 集中短).
                counts = _distribute_official_short(
                    n, cols, max_rows, [cols - 1])
            assert counts is not None  # default is always valid
            col_w = inner_w / cols
            CELL_PADDING = 0.92
            cell_w = col_w * CELL_PADDING
            char_idx = 0
            # right → left fill order (傳統右起讀)
            for col_idx in range(cols - 1, -1, -1):
                col_count = counts[col_idx]
                if col_count <= 0:
                    continue
                col_x = cx - inner_w / 2 + col_w / 2 + col_idx * col_w
                cell_h = inner_h / col_count * CELL_PADDING
                row_step = inner_h / col_count
                row_y0 = cy - inner_h / 2 + row_step / 2
                for row_idx in range(col_count):
                    if char_idx >= len(chars):
                        break
                    cell_y = row_y0 + row_idx * row_step
                    sz_w = (min(cell_w, char_size_mm)
                            if char_size_mm > 0 else cell_w)
                    sz_h = (min(cell_h, char_size_mm)
                            if char_size_mm > 0 else cell_h)
                    placements.append(
                        (chars[char_idx], col_x, cell_y, 0.0, sz_w, sz_h))
                    char_idx += 1
        else:
            # 一般 grid layout (1-6, 9, 12, 16 字)：cell-based + cap
            rows, cols = _auto_grid_dims(n)
            coords = _grid_positions_right_to_left(
                n, rows, cols, inner_w, inner_h, cx, cy)
            cell_w = inner_w / cols
            cell_h = inner_h / rows
            cell_size = min(cell_w, cell_h)
            CELL_FILL_RATIO = 0.92
            cell_fill = cell_size * CELL_FILL_RATIO
            sz = (min(cell_fill, char_size_mm)
                  if char_size_mm > 0 else cell_fill)
            for c, (x, y) in zip(chars, coords):
                _add(c, x, y, 0.0, sz)

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
        # Phase 12m-1: 結構化 oval layout — 上弧文 + 中央 1-3 行 + 下弧文。
        # 偵測任一 oval_* 欄位非空 → 走新 layout，否則 fallback 1-2 行 horizontal
        # （向後兼容：既有 oval test / 簡單橢圓章 用 text 一字串依然 work）。
        has_arc_top = oval_arc_top_chars and len(oval_arc_top_chars) > 0
        has_arc_bot = oval_arc_bottom_chars and len(oval_arc_bottom_chars) > 0
        has_body = oval_body_lines_chars and any(
            ln for ln in oval_body_lines_chars if ln)
        if has_arc_top or has_arc_bot or has_body:
            # --- 新 structured layout ---
            # Arc top (公司名沿上弧)
            if has_arc_top:
                arc_n = len(oval_arc_top_chars)
                arc_sz = _oval_arc_char_size(
                    arc_n, inner_w=inner_w, inner_h=inner_h,
                    char_size_cap=char_size_mm,
                )
                positions = _oval_arc_positions(
                    arc_n, inner_w=inner_w, inner_h=inner_h,
                    cx=cx, cy=cy, top=True,
                )
                for ch, (x, y, rot) in zip(oval_arc_top_chars, positions):
                    placements.append((ch, x, y, rot, arc_sz, arc_sz))
            # Arc bottom (地址 / 統編沿下弧)
            if has_arc_bot:
                arc_n = len(oval_arc_bottom_chars)
                arc_sz = _oval_arc_char_size(
                    arc_n, inner_w=inner_w, inner_h=inner_h,
                    char_size_cap=char_size_mm,
                )
                positions = _oval_arc_positions(
                    arc_n, inner_w=inner_w, inner_h=inner_h,
                    cx=cx, cy=cy, top=False,
                )
                for ch, (x, y, rot) in zip(oval_arc_bottom_chars, positions):
                    placements.append((ch, x, y, rot, arc_sz, arc_sz))
            # Body 1-3 行水平文字
            if has_body:
                body_placements = _oval_body_layout(
                    oval_body_lines_chars,
                    inner_w=inner_w, inner_h=inner_h,
                    cx=cx, cy=cy, char_size_cap=char_size_mm,
                )
                placements.extend(body_placements)
        else:
            # --- 向後兼容 fallback：既有 1-2 行 horizontal layout ---
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
    layout_2char: str = "horizontal",
    layout_official_short_col=("right",),
    char_offsets: list[tuple[float, float]] = None,
    # Phase 12m-1: oval structured fields
    oval_arc_top: str = "",
    oval_arc_bottom: str = "",
    oval_body_lines: list[str] = None,
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

    Phase 12m-1: ``oval_arc_top`` / ``oval_arc_bottom`` / ``oval_body_lines``
    are oval-only structured fields. When any is non-empty AND preset=oval,
    they replace the simple ``text`` 1-2 row horizontal fallback with a real
    business-style oval layout (上弧文 + 中央 1-3 行 + 下弧文).
    """
    decorations = decorations or []
    oval_body_lines = oval_body_lines or []

    def _load_chars(s: str) -> list[Character]:
        out: list[Character] = []
        for ch in s:
            if ch.isspace():
                continue
            c = char_loader(ch)
            if c is None:
                continue
            out.append(c)
        return out

    chars: list[Character] = _load_chars(text)
    # Phase 12m-1: oval structured field char loading
    oval_arc_top_chars = _load_chars(oval_arc_top) if oval_arc_top else []
    oval_arc_bottom_chars = (
        _load_chars(oval_arc_bottom) if oval_arc_bottom else []
    )
    oval_body_lines_chars = [_load_chars(line) for line in oval_body_lines]

    placements = _placements_for_preset(
        preset, chars, stamp_width_mm, stamp_height_mm, char_size_mm,
        border_padding_mm=border_padding_mm,
        double_border=double_border, double_gap_mm=double_gap_mm,
        layout_5char=layout_5char,
        layout_2char=layout_2char,
        layout_official_short_col=layout_official_short_col,
        char_offsets=char_offsets,
        oval_arc_top_chars=oval_arc_top_chars,
        oval_arc_bottom_chars=oval_arc_bottom_chars,
        oval_body_lines_chars=oval_body_lines_chars,
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

    # Phase 12j: viewBox 加 stroke padding 防外框 stroke 外緣被切
    # （圓 path 邊在 width/2，stroke 從中心向外延伸 stroke_width/2，
    # 過去 viewBox=(0, 0, w, h) 會切掉 stroke 外緣 0.3mm）。
    vb_pad = stroke_width / 2
    svg_open = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{-vb_pad:.3f} {-vb_pad:.3f} '
        f'{stamp_width_mm + 2 * vb_pad:.3f} {stamp_height_mm + 2 * vb_pad:.3f}" '
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
    layout_2char: str = "horizontal",
    layout_official_short_col=("right",),
    char_offsets: list[tuple[float, float]] = None,
    # Phase 12m-1: oval structured fields (mirror of render_stamp_svg)
    oval_arc_top: str = "",
    oval_arc_bottom: str = "",
    oval_body_lines: list[str] = None,
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
    oval_body_lines = oval_body_lines or []

    def _load_chars(s: str) -> list[Character]:
        out: list[Character] = []
        for ch in s:
            if ch.isspace():
                continue
            c = char_loader(ch)
            if c is None:
                continue
            out.append(c)
        return out

    chars: list[Character] = _load_chars(text)
    oval_arc_top_chars = _load_chars(oval_arc_top) if oval_arc_top else []
    oval_arc_bottom_chars = (
        _load_chars(oval_arc_bottom) if oval_arc_bottom else []
    )
    oval_body_lines_chars = [_load_chars(line) for line in oval_body_lines]

    placements = _placements_for_preset(
        preset, chars, stamp_width_mm, stamp_height_mm, char_size_mm,
        border_padding_mm=border_padding_mm,
        double_border=double_border, double_gap_mm=double_gap_mm,
        layout_5char=layout_5char,
        layout_2char=layout_2char,
        layout_official_short_col=layout_official_short_col,
        char_offsets=char_offsets,
        oval_arc_top_chars=oval_arc_top_chars,
        oval_arc_bottom_chars=oval_arc_bottom_chars,
        oval_body_lines_chars=oval_body_lines_chars,
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
