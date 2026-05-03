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
    _char_outline_bbox_full_em,
    _ensure_polygon,
    _polygon_to_svg_path,
    _decoration_svg,
    _polygon_to_gcode_path,
    _outline_to_polyline,
    _transform_pt,
)
from .svg import _outline_path_d
from ..shapes import Circle, Ellipse, Polygon, make_shape


def _char_capped_stretch_svg(
    c: Character, cx_mm: float, cy_mm: float,
    cell_w_mm: float, cell_h_mm: float,
    rotation_deg: float = 0.0,
    max_aspect_ratio: float = 2.0,
) -> str:
    """Render a Character bbox-fit to (cell_w, cell_h) with **scale-ratio
    capped** at ``max_aspect_ratio`` to prevent extreme distortion.

    12m-7 r2: Pure bbox-fit (`_char_cut_paths_stretched`) breaks chars
    with extreme bbox aspect — e.g. 「一」 has bbox aspect 7:1 wide-short,
    fitting it into a 1:1 cell stretches y-axis 7× → thin vertical bar
    (visually wrong). Pure uniform scale fixes 一 but makes square chars
    much smaller than cells in wide-short slots (label / title rows).

    This helper bridges: it computes independent scale_x / scale_y but
    CAPS the ratio between them at ``max_aspect_ratio``. So:
    - 一 (bbox aspect 7:1): natural scale_y/scale_x = 7 → capped to 2.0
      → renders as wide thin line (proportional, not distorted bar).
    - 王 / 大 / 同 (square bbox): scale_x ≈ scale_y → no cap, fills cell.
    - 月 (bbox aspect 0.5:1): natural scale_x/scale_y = 2 → at threshold
      → fills cell normally.

    Centred on (cx_mm, cy_mm). ``max_aspect_ratio = 2.0`` keeps 一 visibly
    wide-short while allowing standard chars to fill 1:1 cells.
    """
    bbox = _char_outline_bbox_full_em(c)
    if bbox is None:
        return ""
    min_x, min_y, max_x, max_y = bbox
    bbox_w = max_x - min_x
    bbox_h = max_y - min_y
    if bbox_w <= 0 or bbox_h <= 0:
        return ""
    scale_x = cell_w_mm / bbox_w
    scale_y = cell_h_mm / bbox_h
    # Cap scale-ratio: neither axis stretches beyond max_aspect_ratio
    # times the other. Reduces the OVER-scaled axis to fit.
    if scale_y > scale_x * max_aspect_ratio:
        scale_y = scale_x * max_aspect_ratio
    elif scale_x > scale_y * max_aspect_ratio:
        scale_x = scale_y * max_aspect_ratio
    bcx = (min_x + max_x) / 2.0
    bcy = (min_y + max_y) / 2.0
    dx = cx_mm - bcx * scale_x
    dy = cy_mm - bcy * scale_y
    tform_parts = [f"translate({dx:.3f},{dy:.3f})"]
    if abs(rotation_deg) > 1e-6:
        tform_parts.append(
            f"rotate({rotation_deg:.2f},"
            f"{bcx * scale_x:.3f},{bcy * scale_y:.3f})"
        )
    tform_parts.append(f"scale({scale_x:.6f},{scale_y:.6f})")
    parts = []
    for stroke in c.strokes:
        if stroke.outline:
            d = _outline_path_d(stroke)
            parts.append(f'<path d="{d}"/>')
    if not parts:
        return ""
    return f'<g transform="{" ".join(tform_parts)}">{"".join(parts)}</g>'


StampPreset = Literal[
    "square_name",      # 1-5 chars, individual signature seal (rectangular)
    "round_name",       # 1-5 chars, individual signature seal (circular) — Phase 12i
    "square_official",  # 2-9 chars, company / official seal
    "round",            # ring text + centre char
    "oval",             # 1-2 horizontal lines, acceptance seal
    "tax_invoice",      # 統一發票章「電視章」— Phase 12m-6
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


def _ellipse_arc_length_table(
    t_start: float, t_end: float, a: float, b: float,
    samples: int = 200,
) -> tuple[list[float], list[float]]:
    """Build a (parametric_t, cumulative_arc_length) lookup table.

    For an ellipse parametrized as (a·cos t, b·sin t), the arc length
    from parameter ``t_start`` to ``t`` is the integral of
    √(a²·sin²t + b²·cos²t) dt. We integrate numerically (trapezoidal)
    over ``samples`` sub-intervals. Direction-aware: works for both
    increasing (``t_end > t_start``) and decreasing iteration.

    Returns ``(ts, cumlens)`` — both length ``samples + 1``, monotonic.
    """
    direction = 1.0 if t_end >= t_start else -1.0
    abs_step = abs(t_end - t_start) / samples
    ts: list[float] = [t_start + direction * i * abs_step
                       for i in range(samples + 1)]

    def speed(t: float) -> float:
        return math.sqrt(a * a * math.sin(t) ** 2 + b * b * math.cos(t) ** 2)

    cumlens: list[float] = [0.0]
    prev_speed = speed(ts[0])
    for i in range(1, samples + 1):
        cur_speed = speed(ts[i])
        cumlens.append(cumlens[-1] + (prev_speed + cur_speed) / 2.0 * abs_step)
        prev_speed = cur_speed
    return ts, cumlens


def _t_at_arc_length(
    target_len: float, ts: list[float], cumlens: list[float],
) -> float:
    """Linear-interpolate the parametric t whose cumulative arc length
    equals ``target_len``. Saturates at endpoints if out of range."""
    if target_len <= cumlens[0]:
        return ts[0]
    if target_len >= cumlens[-1]:
        return ts[-1]
    # Binary search the right interval
    lo, hi = 0, len(cumlens) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if cumlens[mid] <= target_len:
            lo = mid
        else:
            hi = mid
    span = cumlens[hi] - cumlens[lo]
    if span == 0:
        return ts[lo]
    frac = (target_len - cumlens[lo]) / span
    return ts[lo] + frac * (ts[hi] - ts[lo])


def _oval_arc_positions(
    n: int, *, inner_w: float, inner_h: float, cx: float, cy: float,
    top: bool, char_size: float = 0.0,
    span_deg: float = 140.0, safety_margin_mm: float = 0.5,
    padding_ratio: float = 0.13,  # legacy fallback (only used if char_size <= 0)
    inner_ellipse_a: float = 0.0,  # 12m-1 patch r15: ring-band midpoint
    inner_ellipse_b: float = 0.0,
) -> list[tuple[float, float, float]]:
    """Place ``n`` chars along the upper or lower half of an inner ellipse.

    Returns ``[(cx_mm, cy_mm, rotation_deg), ...]`` — caller pairs with
    ``Character`` objects + size.

    **Spacing**: Phase 12m-1 patch r2 — chars are distributed by **equal
    arc length** instead of equal angular increment. This eliminates the
    visual disparity where chars near the apex looked further apart than
    chars near the sides (because ellipse curvature varies with theta).
    Numerical integration via trapezoidal rule (200 samples) is fast
    enough for typical use (called once per stamp render).

    Rotation conventions (per-arc 朝外 direction):
    - **Top arc 頂部朝外**: ``rotation = phi + 90°`` — char's HEAD points
      OUTWARD along ellipse normal (upward at top). Reads left→right.
    - **Bottom arc 底部朝外**: ``rotation = phi - 90°`` — char's FEET
      point OUTWARD along ellipse normal (downward at bottom). Char
      upright. Reads left→right.

    Where ``phi = atan2(a·sin t, b·cos t)`` is the ELLIPSE OUTWARD
    NORMAL angle (gradient of ellipse equation), NOT the radius vector
    angle. Phase 12m-1 patch r10 fix: r8 used radius angle
    ``atan2(b sin, a cos)`` which is wrong for ellipses — it makes
    edge chars rotate INWARD toward the geometric center instead of
    along the ellipse's actual curvature. For circles (a=b) the two
    formulas coincide; for elongated ellipses they differ ~10°+ at
    shoulders, visibly mis-aligning chars with the outer frame.

    **Placement padding**: Phase 12m-1 patch r8 — char-size aware.
    Instead of fixed ``padding_ratio``, position chars on an ellipse
    sized so that the bbox edge sits ``safety_margin_mm`` inside the
    outer boundary. Small chars push closer to border, big chars pull
    in to avoid overflow → consistent visual margin across all char
    counts. Falls back to ``padding_ratio`` if ``char_size <= 0``
    (legacy behaviour).
    """
    if n <= 0:
        return []
    if char_size > 0 and inner_ellipse_a > 0 and inner_ellipse_b > 0:
        # 12m-1 patch r15: arc text 放在 outer 跟 inner ellipse 的 midpoint。
        # `inner_w/h` 是 outer 扣掉 border_padding 後的尺寸，但是 arc text
        # 應該以 OUTER ellipse 完整半徑為基準算 midpoint（不然會偏內 0.4mm
        # 導致 inner side gap 只有 0.1mm 太近内框）。
        # 推導：caller 傳 inner_w 是 OUTER 扣 border_padding 0.8mm，所以
        # outer_a = inner_w / 2 + border_padding。border_padding 假設 0.8。
        outer_a_full = (inner_w / 2.0) + 0.8
        outer_b_full = (inner_h / 2.0) + 0.8
        a = (outer_a_full + inner_ellipse_a) / 2.0
        b = (outer_b_full + inner_ellipse_b) / 2.0
    elif char_size > 0:
        # Char-size aware padding (12m-1 patch r8): bbox edge ≈ border −
        # safety_margin (legacy when inner ellipse not provided).
        a = max((inner_w / 2.0) - char_size / 2.0 - safety_margin_mm,
                inner_w / 2.0 * 0.5)
        b = max((inner_h / 2.0) - char_size / 2.0 - safety_margin_mm,
                inner_h / 2.0 * 0.5)
    else:
        # Legacy fallback (called without char_size — use fixed ratio)
        a = (inner_w / 2.0) * (1.0 - padding_ratio)
        b = (inner_h / 2.0) * (1.0 - padding_ratio)

    if top:
        start_deg = -90.0 - span_deg / 2.0
        end_deg = -90.0 + span_deg / 2.0
        rot_offset = 90.0       # 頂部朝外 — head outward at top
    else:
        start_deg = 90.0 + span_deg / 2.0
        end_deg = 90.0 - span_deg / 2.0
        rot_offset = -90.0      # 底部朝外 — feet outward at bottom

    def _ellipse_phi_deg(rad: float) -> float:
        """ELLIPSE outward normal angle (12m-1 patch r10).

        Uses ``atan2(a·sin t, b·cos t)`` = gradient direction of
        ellipse equation = outward normal direction. Differs from
        the simpler radius-vector angle ``atan2(b sin, a cos)`` for
        non-circles. Edge chars now align with ellipse curvature
        (matches outer frame), instead of pointing toward geometric
        center.
        """
        return math.degrees(math.atan2(a * math.sin(rad), b * math.cos(rad)))

    if n == 1:
        # Single char at apex (top or bottom centre)
        theta_deg = -90.0 if top else 90.0
        rad = math.radians(theta_deg)
        return [(
            cx + a * math.cos(rad),
            cy + b * math.sin(rad),
            _ellipse_phi_deg(rad) + rot_offset,
        )]

    # Phase 12m-1 patch r2: arc-length-equal spacing
    start_rad = math.radians(start_deg)
    end_rad = math.radians(end_deg)
    ts, cumlens = _ellipse_arc_length_table(start_rad, end_rad, a, b)
    total_arc = cumlens[-1]

    out: list[tuple[float, float, float]] = []
    for i in range(n):
        target = (i / (n - 1)) * total_arc
        rad = _t_at_arc_length(target, ts, cumlens)
        out.append((
            cx + a * math.cos(rad),
            cy + b * math.sin(rad),
            _ellipse_phi_deg(rad) + rot_offset,
        ))
    return out


def _oval_arc_char_size(
    n: int, *, inner_w: float, inner_h: float, span_deg: float = 140.0,
    padding_ratio: float = 0.13, char_size_cap: float,
    fill_ratio: float = 0.92,
    ring_band_width: float = 0.0,
) -> float:
    """Auto-fit char size for arc text — limited by per-char arc chord.

    Approximates ellipse arc length via average-radius × span_rad, then
    divides by N for per-char chord. Capped by ``char_size_cap`` (the
    user-supplied ``char_size_mm`` upper bound).

    12m-1 patch r14: ``ring_band_width`` (= outer_b − inner_b) caps char
    size so chars don't span both outer and inner ellipse edges.
    12m-7 r27: 收緊 1.0 → 1.4mm，含 0.6mm stroke + 0.4mm 各側 safety margin。
    """
    if n <= 0:
        return char_size_cap
    a = (inner_w / 2.0) * (1.0 - padding_ratio)
    b = (inner_h / 2.0) * (1.0 - padding_ratio)
    avg_r = (a + b) / 2.0
    arc_len_approx = avg_r * math.radians(span_deg)
    per_char = arc_len_approx / max(n, 1)
    candidates = [char_size_cap, per_char * fill_ratio]
    if ring_band_width > 0:
        candidates.append(max(ring_band_width - 1.4, 0.5))
    return min(candidates)


def _oval_body_layout(
    lines_chars: list[list[Character]], *,
    inner_w: float, inner_h: float, cx: float, cy: float,
    char_size_cap: float,
    inner_ellipse_a: float = 0.0,
    inner_ellipse_b: float = 0.0,
    bold_flags: list[bool] = None,
    slot_y_offsets: list[float] = None,    # 12m-6: tax_invoice override
    slot_max_h_ratios: list[float] = None,
) -> list[tuple[Character, float, float, float, float, float, bool]]:
    """Lay out body slots（中央 1/2/3）at FIXED positions inside an oval.

    Phase 12m-1 patch r11: **slot-based positioning** — each slot has
    its own fixed y_offset and max_h regardless of which other slots
    are filled. Empty slot = skip rendering (leaves visual gap).

    Slot semantics (跟 T-02 / 印面樣式 reference 對齊):
    - **中央 1** (lines_chars[0]): TOP, normal-size title line
    - **中央 2** (lines_chars[1]): MIDDLE, **大字**（強調用）
    - **中央 3** (lines_chars[2]): BOTTOM, **小字**（聯絡 / 統編）

    Args:
        lines_chars: position-indexed list of Character lists.
            Index 0 = 中央 1, 1 = 中央 2, 2 = 中央 3.
            Empty inner list = skip that slot.
        char_size_cap: upper bound on char width/height (matches user's
            ``char_size_mm`` setting).
        inner_ellipse_b: half-height of inner ellipse (12m-1 patch r12).
            If > 0, char_size auto-shrinks so char top/bottom doesn't
            cross inner ellipse boundary at slot's y position.
        bold_flags: position-indexed list of bool, one per slot. True
            for slot ⇒ chars in that slot rendered with thicker stroke.

    Returns ``[(char, cx, cy, rot, w, h, bold), ...]`` — 7-tuple
    (bold added in patch r12 for 中央 1/2 加粗 feature).
    """
    # 12m-1 patch r11: pad/truncate to exactly 3 slots, preserve slot index
    lines_chars = list(lines_chars)[:3]
    while len(lines_chars) < 3:
        lines_chars.append([])
    if not any(lines_chars):
        return []
    # 12m-1 patch r12: bold flags per slot (default False)
    bold_flags = (list(bold_flags or []) + [False, False, False])[:3]

    # Per-SLOT y_offset (ratio of inner_h) + max char height (ratio of inner_h).
    # 中央 2 大字 (max_h 0.30 inner_h)；中央 3 小字 (0.15) 給聯絡資訊縮排；
    # 中央 1 normal title (0.18)。三個 slot 互相獨立。
    # 12m-1 patch r13: bump slot_max_h 讓 chars 自動長大（受 inner_bound_h
    # 動態 cap 封頂，不會碰內框）。0.30/0.40/0.13 比舊 0.18/0.30/0.15 大。
    # 12m-6: tax_invoice 用不同 slot 分布（統編大字 / 負責人小 / 電話小），
    # caller 可 override（pass slot_y_offsets / slot_max_h_ratios）。
    SLOT_Y_OFFSETS = slot_y_offsets if slot_y_offsets else [-0.15, 0.0, 0.15]
    SLOT_MAX_H = slot_max_h_ratios if slot_max_h_ratios else [0.30, 0.40, 0.13]
    INNER_ELLIPSE_SAFETY = 0.5  # mm gap between char edge and inner ellipse

    a = inner_w / 2.0
    b = inner_h / 2.0
    USABLE_WIDTH_RATIO = 0.80
    out: list[tuple[Character, float, float, float, float, float, bool]] = []
    for slot_idx, line_chars in enumerate(lines_chars):
        n = len(line_chars)
        if n == 0:
            continue
        y_off_ratio = SLOT_Y_OFFSETS[slot_idx]
        slot_max_h = SLOT_MAX_H[slot_idx] * inner_h
        y = cy + y_off_ratio * inner_h
        # 12m-1 patch r14: usable_w 用 INNER ellipse 算（body 字必須在內框內），
        # fallback 到 OUTER ellipse 如果沒提供 inner ellipse 參數。
        if inner_ellipse_a > 0 and inner_ellipse_b > 0:
            y_norm_inner = (y - cy) / inner_ellipse_b
            if abs(y_norm_inner) >= 0.999:
                continue  # off inner ellipse
            x_half = inner_ellipse_a * math.sqrt(
                1.0 - y_norm_inner * y_norm_inner)
        else:
            y_norm = (y - cy) / b
            if abs(y_norm) >= 0.999:
                continue  # line off the ellipse — skip silently
            x_half = a * math.sqrt(1.0 - y_norm * y_norm)
        usable_w = USABLE_WIDTH_RATIO * 2.0 * x_half
        cell_w = usable_w / n
        # 12m-1 patch r12: dynamic max_h cap from inner ellipse boundary
        # (char top/bottom must not cross inner ellipse line at this y)
        if inner_ellipse_b > 0:
            slot_offset_abs = abs(y_off_ratio * inner_h)
            inner_bound_h = 2.0 * (inner_ellipse_b - slot_offset_abs
                                   - INNER_ELLIPSE_SAFETY)
            inner_bound_h = max(inner_bound_h, 0.5)  # never below 0.5mm
            sz = min(char_size_cap, cell_w * 0.92, slot_max_h, inner_bound_h)
        else:
            sz = min(char_size_cap, cell_w * 0.92, slot_max_h)
        total_w = cell_w * n
        x_start = cx - total_w / 2.0 + cell_w / 2.0
        bold = bold_flags[slot_idx]
        for i, c in enumerate(line_chars):
            x = x_start + i * cell_w
            out.append((c, x, y, 0.0, sz, sz, bold))
    return out


def _oval_flower_svg(cx_mm: float, cy_mm: float, radius_mm: float,
                     stroke_width: float = 0.3) -> str:
    """5-petal plum blossom (梅花) SVG decoration for oval stamp ring band."""
    petal_r = radius_mm * 0.55
    parts = [f'<g class="stamp-deco" '
             f'transform="translate({cx_mm:.3f},{cy_mm:.3f})" '
             f'fill="none" stroke-width="{stroke_width:.3f}">']
    parts.append(f'<circle cx="0" cy="0" r="{petal_r * 0.30:.3f}"/>')
    for i in range(5):
        angle_rad = math.radians(-90.0 + i * 72.0)
        px = radius_mm * 0.55 * math.cos(angle_rad)
        py = radius_mm * 0.55 * math.sin(angle_rad)
        parts.append(
            f'<circle cx="{px:.3f}" cy="{py:.3f}" r="{petal_r:.3f}"/>'
        )
    parts.append('</g>')
    return "".join(parts)


def _oval_star_svg(cx_mm: float, cy_mm: float, radius_mm: float,
                   stroke_width: float = 0.3) -> str:
    """5-pointed star (五角星) SVG decoration. Outer points at radius_mm,
    inner points at radius_mm × 0.4 (golden-ratio-ish proportion)."""
    inner_r = radius_mm * 0.4
    pts = []
    for i in range(10):
        # Alternate outer/inner radii every 36°
        r = radius_mm if i % 2 == 0 else inner_r
        angle_rad = math.radians(-90.0 + i * 36.0)
        x = r * math.cos(angle_rad)
        y = r * math.sin(angle_rad)
        pts.append(f"{x:.3f},{y:.3f}")
    points = " ".join(pts)
    return (f'<g class="stamp-deco" '
            f'transform="translate({cx_mm:.3f},{cy_mm:.3f})" '
            f'fill="none" stroke-width="{stroke_width:.3f}">'
            f'<polygon points="{points}"/></g>')


def _oval_circle_svg(cx_mm: float, cy_mm: float, radius_mm: float,
                     stroke_width: float = 0.3) -> str:
    """Simple filled circle SVG decoration. Outer ring at radius_mm,
    small inner dot for visual focus."""
    return (f'<g class="stamp-deco" '
            f'transform="translate({cx_mm:.3f},{cy_mm:.3f})" '
            f'fill="none" stroke-width="{stroke_width:.3f}">'
            f'<circle cx="0" cy="0" r="{radius_mm:.3f}"/>'
            f'<circle cx="0" cy="0" r="{radius_mm * 0.35:.3f}"/></g>')


def _oval_decoration_svg(kind: str, cx_mm: float, cy_mm: float,
                         radius_mm: float, stroke_width: float = 0.3) -> str:
    """Dispatch decoration SVG by kind. kind ∈ {'plum', 'star', 'circle',
    'none'}. Returns empty string for 'none' or unknown."""
    if kind == "plum":
        return _oval_flower_svg(cx_mm, cy_mm, radius_mm, stroke_width)
    if kind == "star":
        return _oval_star_svg(cx_mm, cy_mm, radius_mm, stroke_width)
    if kind == "circle":
        return _oval_circle_svg(cx_mm, cy_mm, radius_mm, stroke_width)
    return ""  # 'none' or unknown — no decoration


# ---------------------------------------------------------------------------
# Border builders
# ---------------------------------------------------------------------------


def _oval_sawtooth_teeth_svg(
    cx: float, cy: float, a: float, b: float, *,
    num_teeth: int = 80, depth_outward_mm: float = 1.0,
) -> str:
    """Generate SVG path string for filled sawtooth teeth attached OUTSIDE
    smooth ellipse (Phase 12m-1 patch r19 redesign).

    Each tooth is a triangle:
      - base: chord between two adjacent ellipse sample points (P_left, P_right)
      - apex: pushed OUTWARD radially by ``depth_outward_mm`` at midangle

    Result: outer rim shows zigzag teeth pointing outward; inner side
    of stamp (smooth ellipse) stays smooth — matches traditional 印章
    鋸齒 邊飾 visual where teeth are decorative protrusions.

    Returns concatenated SVG path data string (M ... L ... L ... Z per
    tooth). Caller renders as filled `<path>`.
    """
    parts = []
    for i in range(num_teeth):
        theta_left = 2.0 * math.pi * i / num_teeth
        theta_right = 2.0 * math.pi * (i + 1) / num_teeth
        theta_apex = 2.0 * math.pi * (i + 0.5) / num_teeth
        bxl = cx + a * math.cos(theta_left)
        byl = cy + b * math.sin(theta_left)
        bxr = cx + a * math.cos(theta_right)
        byr = cy + b * math.sin(theta_right)
        ax = cx + (a + depth_outward_mm) * math.cos(theta_apex)
        ay = cy + (b + depth_outward_mm) * math.sin(theta_apex)
        parts.append(
            f"M {bxl:.3f},{byl:.3f} L {ax:.3f},{ay:.3f} "
            f"L {bxr:.3f},{byr:.3f} Z"
        )
    return " ".join(parts)


# Phase 12m-7: tax_invoice stadium / 「電視章」shape constants
#
# Stadium = top half-ellipse + straight L/R sides + bottom half-ellipse.
# Looks like an old CRT TV — origin of「電視章」nickname. ED2/ED4 reference
# stamps follow this. Different from橢圓 (full ellipse) which lacks straight
# sides.
#
# curve_h_ratio = 上下弧 高度 / 總高度。0.30 = 上 30% + 下 30% = 60% curve，
# 中間 40% 直線部分。對齊 ED2/ED4 reference 視覺。
TAX_INVOICE_CURVE_H_RATIO = 0.30   # legacy fallback (used when straight
                                   # length spec disabled)
TAX_INVOICE_STRAIGHT_LENGTH_MM = 27.0  # 12m-7 r11: 外框 L/R 直線 = 27mm
                                       # curve_h = (height - 27) / 2
                                       # For 45×40: outer curve_h = 6.5mm
TAX_INVOICE_INNER_SHOULDER_DIST_MM = 37.0  # 12m-7 r11: legacy
TAX_INVOICE_INNER_SEP_APEX_OFFSET_MM = 6.0   # 12m-7 r16: 內 sep apex 更深
                                              # （之前 4.0），給 arc text
                                              # 更多 ring band 空間
TAX_INVOICE_INNER_SEP_CHORD_HALF_MM = 18.5   # 12m-7 r16: chord_half = 18.5
                                              # → chord = 37mm（user spec）
                                              # sagitta 自動由 chord+R 推算
TAX_INVOICE_BODY_USABLE_W_MM = 36.0  # 12m-7 r14: 中央 1 (slot_0) 文字
                                     # 左右邊界 = 36mm（user spec）。其他
                                     # body slots 共用此寬。Clamp 至 stamp
                                     # width × 0.90 避免超過 narrow stamps。
TAX_INVOICE_POLYGON_CURVE_VERTICES = 32   # per top/bottom curve


def _tax_invoice_curve_h(height_mm: float) -> float:
    """12m-7 r8/r11: 計算 tax_invoice stamp outer frame 的 curve_h。

    L/R 直線長度固定 = TAX_INVOICE_STRAIGHT_LENGTH_MM (27mm in r11)。
    curve_h = (height - 27) / 2
    For default 45×40: curve_h = 6.5mm

    For height < 27 + 2，clamp 至最小 1.0mm。
    """
    target = (height_mm - TAX_INVOICE_STRAIGHT_LENGTH_MM) / 2.0
    return max(target, 1.0)


def _tax_invoice_inner_sep_geometry(
    width_mm: float, height_mm: float,
) -> tuple[float, float, float, float]:
    """12m-7 r11: 計算 inner sep arc 的幾何參數（不再 derive from
    "inner stadium"，而是直接由 outer + INNER_SHOULDER_DIST 推算）。

    Returns: (shoulder_y_top, shoulder_y_bot, inner_a, inner_curve_h)
    where:
    - shoulder_y_top, shoulder_y_bot: 內 sep arc 上下 shoulders 的 y
        位置（用 INNER_SHOULDER_DIST_MM = 37 計算）
    - inner_a: chord half-length（受 outer frame 限制 — shoulders 必須
        在 outer 內）
    - inner_curve_h: same as outer curve_h（parallel curvature）

    For default 45×40:
        shoulder_y_top = 1.5, shoulder_y_bot = 38.5
        inner_curve_h = 6.5
        inner_a ≈ 10.65 (constrained by outer at y=1.5)
        inner chord ≈ 21.3 mm
    """
    # 12m-7 r16: chord_half 固定（user spec 37mm chord）→ sagitta 由 R+chord
    # 推算（same curvature as outer R）。∩ top / ∪ bot 方向 with apex_offset
    # 控制深度。
    half_w = width_mm / 2.0
    curve_h_outer = _tax_invoice_curve_h(height_mm)

    # Same R as outer
    if curve_h_outer > 0:
        R_outer = (half_w * half_w + curve_h_outer * curve_h_outer) / (
            2.0 * curve_h_outer)
    else:
        R_outer = float('inf')

    # 12m-7 r16: chord_half 由 user spec 固定 = 18.5
    inner_a = TAX_INVOICE_INNER_SEP_CHORD_HALF_MM
    # Cap at half_w-1 for safety on small stamps
    inner_a = min(inner_a, half_w - 1.0)

    # Sagitta from R + chord_half (same curvature as outer):
    # R = (a² + h²) / (2h)  →  h = R - sqrt(R² - a²)
    if R_outer < float('inf') and inner_a < R_outer:
        sagitta = R_outer - math.sqrt(R_outer * R_outer - inner_a * inner_a)
    else:
        sagitta = inner_a * 0.2   # fallback
    sagitta = max(sagitta, 0.5)
    inner_curve_h = sagitta

    # ∩ top direction with deeper apex_offset (r16 = 6 vs r15 = 4)
    apex_offset = TAX_INVOICE_INNER_SEP_APEX_OFFSET_MM
    apex_y_top = apex_offset
    shoulder_y_top = apex_y_top + sagitta
    apex_y_bot = height_mm - apex_offset
    shoulder_y_bot = apex_y_bot - sagitta

    return shoulder_y_top, shoulder_y_bot, inner_a, inner_curve_h


def _stadium_polygon_vertices(
    cx: float, cy: float,
    half_w: float, half_h: float,
    *,
    curve_h_ratio: float = TAX_INVOICE_CURVE_H_RATIO,
    n_curve: int = TAX_INVOICE_POLYGON_CURVE_VERTICES,
    curve_type: str = "circle",
) -> list[tuple[float, float]]:
    """Build a stadium / TV-shape polygon as a vertex list.

    Stadium geometry (axis-aligned, centered at cx/cy):
    - Top:    sphere-cap arc with chord 2*half_w, sagitta curve_h
    - Sides:  straight vertical lines, length = 2*(half_h - curve_h)
    - Bottom: sphere-cap arc mirroring top

    Where curve_h = curve_h_ratio * (2*half_h).

    ``curve_type`` selects the curve geometry:
    - ``"circle"`` (default, 12m-7 r4): circular arc — tangent at the
      shoulder (curve↔straight joint) is NOT vertical, so the joint
      has a VISIBLE corner (對齊 ED2/ED4 reference 的轉折感)。Tangent
      angle = arctan(half_w / (R - curve_h)) ≠ 90°.
    - ``"ellipse"`` (legacy): half-ellipse — tangent at shoulder is
      vertical, matches straight side tangent → smooth (no visible
      corner)。Used by older code paths if explicitly requested.

    Vertex order goes clockwise starting at top-left
    (left edge meets curve at y = top of straight section):

        ─►──  top curve  ──►─┐
        ▲                    ▼
        │  left straight     right straight
        │                    │
        ▲                    ▼
        └──◄── bottom curve ◄┘
    """
    height = 2.0 * half_h
    curve_h = curve_h_ratio * height
    top_curve_center_y = cy - (half_h - curve_h)
    bot_curve_center_y = cy + (half_h - curve_h)
    pts: list[tuple[float, float]] = []

    if curve_type == "circle":
        # Circular arc: chord = 2*half_w, sagitta = curve_h.
        # R = (half_w² + curve_h²) / (2 × curve_h) (geometry derivation).
        # Center of top circle is BELOW apex by R (in y-down coords),
        # so center_y = apex_y + R = (cy - half_h) + R.
        # Half-angle subtended from circle center to chord endpoints:
        #   alpha = arcsin(half_w / R)
        # Top arc: theta from -alpha (left shoulder) to +alpha (right
        # shoulder), 0 = apex.
        if curve_h <= 0:
            R = float("inf")
        else:
            R = (half_w * half_w + curve_h * curve_h) / (2.0 * curve_h)
        top_circle_cy = (cy - half_h) + R
        bot_circle_cy = (cy + half_h) - R
        alpha = math.asin(min(half_w / R, 1.0)) if R > 0 else math.pi / 2

        # Top arc: left shoulder (-alpha) → apex (0) → right shoulder (+alpha)
        for i in range(n_curve + 1):
            theta = -alpha + (i / n_curve) * 2 * alpha
            x = cx + R * math.sin(theta)
            y = top_circle_cy - R * math.cos(theta)
            pts.append((x, y))

        pts.append((cx + half_w, bot_curve_center_y))

        # Bottom arc: right shoulder (+alpha) → apex (0) → left shoulder (-alpha)
        for i in range(n_curve + 1):
            theta = alpha - (i / n_curve) * 2 * alpha
            x = cx + R * math.sin(theta)
            y = bot_circle_cy + R * math.cos(theta)
            pts.append((x, y))

        pts.append((cx - half_w, top_curve_center_y))
        return pts

    # ---- Ellipse curve (legacy / fallback) ----
    for i in range(n_curve + 1):
        theta = math.pi - (i / n_curve) * math.pi
        x = cx + half_w * math.cos(theta)
        y = top_curve_center_y - curve_h * math.sin(theta)
        pts.append((x, y))
    pts.append((cx + half_w, bot_curve_center_y))
    for i in range(n_curve + 1):
        theta = (i / n_curve) * math.pi
        x = cx + half_w * math.cos(theta)
        y = bot_curve_center_y + curve_h * math.sin(theta)
        pts.append((x, y))
    pts.append((cx - half_w, top_curve_center_y))
    return pts


def _stadium_inner_separator_paths(
    width_mm: float, height_mm: float,
    *,
    n_curve: int = TAX_INVOICE_POLYGON_CURVE_VERTICES,
    span_ratio: float = 1.0,
) -> tuple[str, str]:
    """Return SVG path d-strings (top_arc, bot_arc) — the 2 OPEN
    inner separator arcs for tax_invoice stamps.

    12m-7 r11: 重新設計 — 用 _tax_invoice_inner_sep_geometry() 計算所有
    參數。內框上下弧 shoulders 之間 vertical 距離 = 37mm（user 要求）。
    inner_a 由 outer frame 限制（shoulders 不超出 outer）。

    For default 45×40:
        shoulder_y_top = 1.5, shoulder_y_bot = 38.5
        inner_curve_h = 6.5 (matches outer)
        inner_a ≈ 10.65 (constrained by outer)

    span_ratio: 弧橫向佔 chord 比例。1.0 = 全 chord（shoulders 各
    端點），<1.0 = 中間部分。Default 1.0 因為 inner_a 已被 outer
    constraint 算好，不需再縮。
    """
    cx = width_mm / 2.0
    shoulder_y_top, shoulder_y_bot, inner_a, inner_curve_h = (
        _tax_invoice_inner_sep_geometry(width_mm, height_mm))

    if inner_curve_h <= 0 or inner_a <= 0:
        return "", ""

    # Circular arc: chord = 2 × inner_a, sagitta = inner_curve_h
    R = (inner_a * inner_a + inner_curve_h * inner_curve_h) / (
        2.0 * inner_curve_h)
    alpha_full = math.asin(min(inner_a / R, 1.0))
    alpha_used = alpha_full * span_ratio

    # 12m-7 r15: ∩ top / ∪ bot 方向（user spec），shoulders 移深以保
    # visibility 跟 arc text 不撞。
    #
    # Top arc ∩: apex y < shoulder y (apex toward outer top, smaller y)
    #   apex_y = shoulder_y_top - inner_curve_h
    #   circle center y = shoulder_y_top + (R - sagitta) (BELOW shoulders)
    # Bot arc ∪: apex y > shoulder y (apex toward outer bot, greater y)
    #   apex_y = shoulder_y_bot + inner_curve_h
    #   circle center y = shoulder_y_bot - (R - sagitta) (ABOVE shoulders)
    top_circle_cy = shoulder_y_top + R - inner_curve_h
    bot_circle_cy = shoulder_y_bot - R + inner_curve_h

    top_pts = []
    bot_pts = []
    for i in range(n_curve + 1):
        theta = -alpha_used + (i / n_curve) * 2 * alpha_used
        x = cx + R * math.sin(theta)
        # Top: y = top_circle_cy - R cos(theta) (apex at theta=0, MIN y)
        top_pts.append((x, top_circle_cy - R * math.cos(theta)))
        # Bot: y = bot_circle_cy + R cos(theta) (apex at theta=0, MAX y)
        bot_pts.append((x, bot_circle_cy + R * math.cos(theta)))

    def _polyline_d(verts):
        if not verts:
            return ""
        parts = [f"M {verts[0][0]:.3f} {verts[0][1]:.3f}"]
        for x, y in verts[1:]:
            parts.append(f"L {x:.3f} {y:.3f}")
        return " ".join(parts)

    return _polyline_d(top_pts), _polyline_d(bot_pts)


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

    Phase 12m-1 patch r19: sawtooth 鋸齒邊飾 不再 polygon-replace 外框
    （那會讓 inner side 也呈鋸齒）。改成：smooth ellipse 維持原樣，鋸齒
    teeth 另以 filled triangle paths 黏在 outer side（render 時 inject）。
    這個 helper 不再處理 sawtooth — 只回傳 smooth shapes。

    Phase 12m-7: tax_invoice 從 oval 拆出 → stadium / 「電視章」shape
    （上下圓弧 + 左右直線），匹配 ED2/ED4 reference。Polygon 用 stadium
    helper 生 ~66 vertices。
    """
    cx, cy = width_mm / 2, height_mm / 2

    def _outer():
        if preset in ("round", "round_name"):
            return Circle(cx, cy, min(width_mm, height_mm) / 2)
        if preset == "oval":
            return Ellipse(cx, cy, width_mm / 2, height_mm / 2)
        if preset == "tax_invoice":   # 12m-7: stadium shape
            # 12m-7 r8: curve_h 由 fixed straight length 27mm 推算
            ratio = _tax_invoice_curve_h(height_mm) / height_mm
            return Polygon(vertices=_stadium_polygon_vertices(
                cx, cy, width_mm / 2, height_mm / 2,
                curve_h_ratio=ratio,
            ))
        # rectangular / square presets
        return Polygon(vertices=[
            (0, 0), (width_mm, 0), (width_mm, height_mm), (0, height_mm),
        ])

    polys = [_outer()]
    if double_border:
        gap = double_gap_mm
        if preset == "round_name":
            r = min(width_mm, height_mm) / 2 - gap
            if r > 0:
                polys.append(Circle(cx, cy, r))
        elif preset in ("oval", "round"):
            # 12m-1 patch r9 / r10 / r11: oval double_border = body-wrapping
            # inner ellipse + 內外框等距 ring band（user 觀察「內外框距離
            # 恆定」→ 用 constant offset (a-d, b-d) 取代 uniform scale）。
            # 12m-7 r25: round 共用相同邏輯（w==h ⇒ ellipse 退化為正圓）。
            half_a = width_mm / 2.0
            half_b = height_mm / 2.0
            d = 0.30 * min(half_a, half_b)
            polys.append(Ellipse(
                cx, cy,
                max(half_a - d, 0.1),
                max(half_b - d, 0.1),
            ))
        elif preset == "tax_invoice":
            # 12m-7 r3: tax_invoice double_border 不是 closed inner
            # stadium，而是 2 個 OPEN separator arcs — 渲染時另外處理
            # （見 render_stamp_svg 的 _stadium_inner_separator_paths
            # 注入段）。這裡不 append polygon — 維持 polys = [outer 唯一]。
            pass
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
    # Phase 12m-1 patch r12: oval body slot bold flags (length 3, default
    # all False). When True, char rendered with thicker stroke for emphasis.
    oval_body_bold: list[bool] = None,
    # Phase 12m-6: tax_invoice 固定「統一編號」4 字標題（位於 中央 1 上方）
    oval_label_chars: list[Character] = None,
    # Phase 12m-7: tax_invoice optional 上方標題（位於 統一編號 label 上方），
    # 典型「統一發票專用章」/「免用發票專用章」。空 list = 不顯示
    oval_top_title_chars: list[Character] = None,
    # Phase 12m-7: tax_invoice optional 縣市名（如「台北市」），位置由
    # oval_location_position 控制
    oval_location_chars: list[Character] = None,
    # Phase 12m-7: 縣市顯示位置：
    #   "bottom" = 中央 3 下方 horizontal（預設）
    #   "left"   = 章面最左側 vertical 直立（取代左梅花裝飾）
    oval_location_position: str = "bottom",
    # Phase 12m-7 r26: 圓戳章 (round) 單圓周模式
    round_continuous_arc: bool = False,
) -> list[tuple]:
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
    # 12m-1 patch r9: oval 雙框 semantic 變了（body-wrapping 不再 concentric），
    # 弧文要佔外-內框環帶 → inset 不加 double_gap_mm，弧文 placement 用 outer
    # 邊距即可。其他 preset 維持既有 concentric 語意。
    if preset in ("oval", "tax_invoice", "round"):
        inset = border_padding_mm
    else:
        inset = border_padding_mm + (double_gap_mm if double_border else 0)
    # Bug fix (12b-5): 過去用 max(_, char_size_mm) 會讓 user 改 char_size_mm
    # 時意外把 inner 拉大、外框 inset 縮小，造成「字大小設大 → 章面也跟著
    # 變大」的錯覺。改成純安全下限（1.0 mm 避免 inner 變負）。
    inner_w = max(width_mm - 2 * inset, 1.0)
    inner_h = max(height_mm - 2 * inset, 1.0)
    n = len(chars)
    # Phase 12m-1: oval preset 結構化 fields 可能讓 `chars` 是空的（user 只填
    # oval_arc_top / oval_arc_bottom / oval_body_lines），此時不能 early-return。
    _has_oval_structured = preset in ("oval", "tax_invoice", "round") and (
        (oval_arc_top_chars and len(oval_arc_top_chars) > 0)
        or (oval_arc_bottom_chars and len(oval_arc_bottom_chars) > 0)
        or (oval_body_lines_chars and any(
            ln for ln in oval_body_lines_chars if ln))
        # 12m-7: tax_invoice 額外 fields
        or (preset == "tax_invoice" and oval_label_chars
            and len(oval_label_chars) > 0)
        or (preset == "tax_invoice" and oval_top_title_chars
            and len(oval_top_title_chars) > 0)
        or (preset == "tax_invoice" and oval_location_chars
            and len(oval_location_chars) > 0)
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

    elif preset == "tax_invoice":
        # Phase 12m-7: tax_invoice 統一發票章 / 「電視章」— stadium shape
        # （上下圓弧 + 左右直線）。跟 oval 不同：
        #   - 邊框：stadium polygon（_stamp_border_polys 已處理）
        #   - 上下弧文：沿 stadium 上下半圓弧（half-ellipse 切片，axes
        #     = (half_w, curve_h)）
        #   - Body：中央 rectangular area（左右直邊 → 全 inner_w 可用）
        #   - 上方標題：可選，於 統一編號 label 上方
        #   - 縣市：可選，下方 horizontal 或 左側 vertical 直立
        has_arc_top = oval_arc_top_chars and len(oval_arc_top_chars) > 0
        has_arc_bot = oval_arc_bottom_chars and len(oval_arc_bottom_chars) > 0
        has_body = oval_body_lines_chars and any(
            ln for ln in oval_body_lines_chars if ln)
        has_top_title = (oval_top_title_chars
                         and len(oval_top_title_chars) > 0)
        has_location = oval_location_chars and len(oval_location_chars) > 0

        # Stadium geometry (mirrors _stadium_polygon_vertices).
        _half_w_outer = width_mm / 2.0
        _half_h_outer = height_mm / 2.0
        _curve_h = _tax_invoice_curve_h(height_mm)   # 12m-7 r8
        _top_curve_cy = cy - (_half_h_outer - _curve_h)
        _bot_curve_cy = cy + (_half_h_outer - _curve_h)
        # 12m-7 r14: 用 sep arc geometry 的 inner_a 算 arc text X spread
        # （之前用 d_offset-based 16.5 → arc text 邊邊字碰 outer frame）。
        # New arc_a 用 sep_inner_a (≈10.65)，arc text 縮 width 進 outer 內。
        _sep_shoulder_y, _, _sep_inner_a, _ = _tax_invoice_inner_sep_geometry(
            width_mm, height_mm)
        _d_offset = 0.30 * min(_half_w_outer, _half_h_outer)
        _inner_a = max(_half_w_outer - _d_offset, 0.1)   # legacy, body 不用
        _inner_b_curve = max(_curve_h - _d_offset, 0.1)
        _ring_band_width = _d_offset

        # --- Top arc (公司名沿上半弧) ---
        # 沿 top half-ellipse curve，centered at (cx, _top_curve_cy)，axes
        # (a, curve_h)。char 落在 outer 與 inner stadium curve 中點 ring band。
        # 12m-7 r19: arc text 圓弧 path（a=b=R_outer）→ 曲率 = inner sep
        # arc 曲率（同 R）。User spec: 上/下弧文文字曲率與內框弧相同。
        if _curve_h > 0:
            _R_outer = (_half_w_outer * _half_w_outer
                        + _curve_h * _curve_h) / (2.0 * _curve_h)
        else:
            _R_outer = float('inf')

        if has_arc_top:
            arc_n = len(oval_arc_top_chars)
            arc_chord_half = max(_sep_inner_a - 1.5, _half_w_outer * 0.4)
            target_apex_y_top = TAX_INVOICE_INNER_SEP_APEX_OFFSET_MM / 2.0
            # span derived from chord_half on circle of radius R_outer
            if _R_outer < float('inf') and arc_chord_half < _R_outer:
                arc_span_deg = math.degrees(
                    2.0 * math.asin(arc_chord_half / _R_outer))
            else:
                arc_span_deg = 130.0
            arc_a_full = _R_outer
            arc_b_full = _R_outer
            cy_arc_top = target_apex_y_top + _R_outer
            arc_len_approx = _R_outer * math.radians(arc_span_deg)
            arc_w = min(arc_len_approx / arc_n * 0.92, char_size_mm)
            ring_band_h = TAX_INVOICE_INNER_SEP_APEX_OFFSET_MM
            arc_h = min(ring_band_h * 0.55, arc_w * 1.6, char_size_mm)
            arc_w = max(arc_w, 1.5)
            arc_h = max(arc_h, 1.8)
            positions = _oval_arc_positions(
                arc_n,
                inner_w=2 * arc_a_full, inner_h=2 * arc_b_full,
                cx=cx, cy=cy_arc_top, top=True, char_size=0,
                span_deg=arc_span_deg, padding_ratio=0.0,
            )
            for ch, (x, y, rot) in zip(oval_arc_top_chars, positions):
                placements.append(
                    (ch, x, y, rot, arc_w, arc_h, False, True)
                )

        # --- Bottom arc (地址沿下半弧) ---
        if has_arc_bot:
            arc_n = len(oval_arc_bottom_chars)
            arc_chord_half = max(_sep_inner_a - 1.5, _half_w_outer * 0.4)
            # 12m-7 r19: 對稱 top arc — 圓弧 path（同 R = R_outer）
            target_apex_y_top = TAX_INVOICE_INNER_SEP_APEX_OFFSET_MM / 2.0
            target_apex_y_bot = height_mm - target_apex_y_top
            if _R_outer < float('inf') and arc_chord_half < _R_outer:
                arc_span_deg = math.degrees(
                    2.0 * math.asin(arc_chord_half / _R_outer))
            else:
                arc_span_deg = 130.0
            arc_a_full = _R_outer
            arc_b_full = _R_outer
            cy_arc_bot = target_apex_y_bot - _R_outer
            arc_len_approx = _R_outer * math.radians(arc_span_deg)
            arc_w = min(arc_len_approx / arc_n * 0.92, char_size_mm)
            ring_band_h = TAX_INVOICE_INNER_SEP_APEX_OFFSET_MM
            arc_h = min(ring_band_h * 0.55, arc_w * 1.6, char_size_mm)
            arc_w = max(arc_w, 1.5)
            arc_h = max(arc_h, 1.8)
            positions = _oval_arc_positions(
                arc_n,
                inner_w=2 * arc_a_full, inner_h=2 * arc_b_full,
                cx=cx, cy=cy_arc_bot, top=False, char_size=0,
                span_deg=arc_span_deg, padding_ratio=0.0,
            )
            for ch, (x, y, rot) in zip(oval_arc_bottom_chars, positions):
                placements.append(
                    (ch, x, y, rot, arc_w, arc_h, False, True)
                )

        # --- Body / 中央 1-3 + 統一編號 label + 上方標題 + 縣市 ---
        # Stadium 中央 = rectangular area。usable_w = inner_w（全寬可用）。
        # Y offsets：以 cy 為中心，ratio 乘 inner_h。
        #   slot ↑↑    上方標題 (optional, e.g.「統一發票專用章」)  y=-0.32
        #   slot ↑     統一編號 label (fixed)                        y=-0.20
        #   slot 0     中央 1：統編 number (大粗字)                  y=-0.05
        #   slot 1     中央 2：負責人                                y=+0.10
        #   slot 2     中央 3：電話                                  y=+0.22
        #   slot ↓     縣市 (optional, position=bottom)               y=+0.34
        # 縣市 position=left → 替換 left plum decoration，不放 body slot
        if has_body or has_top_title or has_location or oval_label_chars:
            # 12m-7 r14: body_usable_w 直接用常數 36mm (user spec)
            # Clamp at stamp width × 0.90 for narrow stamps to avoid overflow.
            body_usable_w = min(TAX_INVOICE_BODY_USABLE_W_MM,
                                width_mm * 0.90)

            # 12m-7 r4/r15/r21: slot Y + 高度校準，避免 title/location
            # 碰上下 inner separator 弧。
            # tuple = (y_ratio, max_h_ratio, tight, spacing_mul)
            # r21: title 抬高 (-0.20→-0.22) + 字大 0.07→0.085 + 字距 1.30
            # （45×40 7 chars: x0=10.57, char top y=10.55 vs inner_sep at
            # x=10.57 y=7.73, gap=2.82mm ✓; title bot 13.61 vs label top
            # 14.06, gap 0.45 ✓）。label 不動 — title 抬高後自然產生間距。
            # location 字小 0.06→0.045 避免碰下弧（char bot y=30.53 vs
            # inner sep bot apex y=34, gap=3.47mm）
            STADIUM_BODY_SLOTS = {
                "top_title":  (-0.22, 0.085, True,  1.30),
                "label":      (-0.13, 0.07,  True,  1.15),
                "slot_0":     (-0.02, 0.12,  False, 1.15),
                "slot_1":     (+0.10, 0.06,  False, 1.15),
                "slot_2":     (+0.18, 0.06,  False, 1.15),
                "location":   (+0.27, 0.045, True,  1.15),
            }

            def _stadium_body_row(line_chars, y_ratio, max_h_ratio,
                                  bold=False, tight=False,
                                  spacing_mul=1.15):
                """Place horizontal row of chars at given slot.
                12m-7 r2: 8-tuple with capped_stretch=True (8th elem) →
                render uses _char_capped_stretch_svg, prevents 「一」 etc.
                extreme-aspect distortion while letting square chars fill.

                tight=True (label/title/location): chars pack tight
                (spacing = ch_sz × 1.15), centered in row — matches
                ED2/ED4 reference visuals where 4-char labels don't span
                full width.

                tight=False (body slots): chars fill cells uniformly
                across body_usable_w — for primary content rows.
                """
                if not line_chars:
                    return
                m = len(line_chars)
                slot_max_h = max_h_ratio * inner_h
                # 12m-7 r20: 偵測 blank_half cells（separator placeholder
                # with 0.5 cell width）— 用於「負責人」prefix 與用戶文字
                # 之間的細空格 separator。
                is_blank_half = [
                    getattr(c, 'data_source', '') == 'blank_half'
                    for c in line_chars
                ]
                n_blank_half = sum(is_blank_half)
                if tight:
                    # Tight pack: char size driven by slot_max_h, NOT cell_w
                    ch_sz = min(slot_max_h, char_size_mm)
                    ch_sz = max(ch_sz, 2.5)
                    # 12m-7 r21: spacing_mul 由 caller 傳入（title 用 1.30 加大字距）
                    spacing = ch_sz * spacing_mul
                    # Centre row horizontally; ensure not exceeding body_usable_w
                    total_w = spacing * m
                    if total_w > body_usable_w:
                        spacing = body_usable_w / m
                        ch_sz = min(spacing * 0.90, slot_max_h, char_size_mm)
                    x0 = cx - (spacing * m) / 2.0 + spacing / 2.0
                    y = cy + y_ratio * inner_h
                    for i, ch in enumerate(line_chars):
                        placements.append(
                            (ch, x0 + i * spacing, y, 0.0, ch_sz, ch_sz,
                             bold, True)
                        )
                    return
                # Body slot: cell-based (full usable_w). 12m-7 r20: 支援
                # 非等寬 cell — blank_half = 0.5 standard cell width。
                total_units = (m - n_blank_half) + 0.5 * n_blank_half
                if total_units <= 0:
                    return
                cell_w = body_usable_w / total_units
                # 12m-7 r15: FILL_W 0.90 → 0.78（chars 縮小，user spec B）
                FILL_W = 0.78
                ch_sz = min(cell_w * FILL_W, slot_max_h, char_size_mm)
                ch_sz = max(ch_sz, 2.5) if ch_sz > 0 else ch_sz
                x_left = cx - body_usable_w / 2.0
                y = cy + y_ratio * inner_h
                x_cur = x_left
                for i, ch in enumerate(line_chars):
                    cw = cell_w * (0.5 if is_blank_half[i] else 1.0)
                    placements.append(
                        (ch, x_cur + cw / 2.0, y, 0.0, ch_sz, ch_sz,
                         bold, True)
                    )
                    x_cur += cw

            # 上方標題 (optional, tight)
            if has_top_title:
                y_r, h_r, tight, sp_mul = STADIUM_BODY_SLOTS["top_title"]
                _stadium_body_row(oval_top_title_chars, y_r, h_r,
                                  tight=tight, spacing_mul=sp_mul)
            # 統一編號 label (fixed when oval_label_chars provided, tight)
            if oval_label_chars:
                y_r, h_r, tight, sp_mul = STADIUM_BODY_SLOTS["label"]
                _stadium_body_row(list(oval_label_chars), y_r, h_r,
                                  tight=tight, spacing_mul=sp_mul)
            # Body slots (中央 1/2/3, fill cells)
            # 12m-7 r3: 中央 2 (slot_1) 自動加「負責人：」前綴對齊 ED2/ED4
            # reference visual。若 user 已在 slot_1 加「負責人」字串，不重複。
            # Slot 1 expected to be a copy of oval_body_lines_chars[1]; we
            # can't easily re-load chars here (loader not in scope), so do
            # the prefix at render_stamp_svg level (see _load_chars wrap).
            if has_body:
                bold_flags = oval_body_bold or [False] * 3
                slot_keys = ["slot_0", "slot_1", "slot_2"]
                for i, line in enumerate(oval_body_lines_chars[:3]):
                    if not line:
                        continue
                    y_r, h_r, tight, sp_mul = STADIUM_BODY_SLOTS[
                        slot_keys[i]]
                    bold = (bold_flags[i] if i < len(bold_flags) else False)
                    _stadium_body_row(line, y_r, h_r, bold=bold,
                                      tight=tight, spacing_mul=sp_mul)
            # 縣市 (optional, position=bottom, tight)
            if has_location and oval_location_position == "bottom":
                y_r, h_r, tight, sp_mul = STADIUM_BODY_SLOTS["location"]
                _stadium_body_row(list(oval_location_chars), y_r, h_r,
                                  tight=tight, spacing_mul=sp_mul)
            # 縣市 (position=left) — 直立排列於章面最左邊，取代左側梅花。
            # 位置 x = 左 ring band 中點 (_d_offset / 2)。
            # 12m-7 r23: 字體大小 = slot_0 (中央 1) max_h_ratio (0.12)，與
            # 大字統編 row 視覺一致；spacing_mul 1.05→1.20 增加字距。
            # 仍由 ring_band_width * 0.85 上限保護避免字寬超出 ring band。
            if has_location and oval_location_position == "left":
                loc_chars = list(oval_location_chars)
                m = len(loc_chars)
                loc_x = _d_offset / 2.0
                slot_0_max_h_ratio = STADIUM_BODY_SLOTS["slot_0"][1]
                ch_sz = min(slot_0_max_h_ratio * inner_h,
                            _ring_band_width * 0.85, char_size_mm)
                ch_sz = max(ch_sz, 2.0)
                spacing = ch_sz * 1.20
                total_h = spacing * m
                y0 = cy - total_h / 2.0 + spacing / 2.0
                for i, ch in enumerate(loc_chars):
                    placements.append(
                        (ch, loc_x, y0 + i * spacing, 0.0, ch_sz, ch_sz,
                         False, True)
                    )

    elif preset in ("oval", "round"):
        # Phase 12m-1: 結構化 oval layout — 上弧文 + 中央 1-3 行 + 下弧文。
        # 12m-7 r25: round (圓戳章) 共用 oval 結構化 layout。w==h ⇒ ellipse
        # 退化為正圓，arc text 弧為上下半圓，inner frame 也為正圓（d_offset
        # 邏輯 a==b 結果 a-d==b-d）。
        # 偵測任一 oval_* 欄位非空 → 走新 layout，否則 fallback 1-2 行 horizontal
        # （向後兼容：既有 oval test / 簡單橢圓章 用 text 一字串依然 work）。
        has_arc_top = oval_arc_top_chars and len(oval_arc_top_chars) > 0
        has_arc_bot = oval_arc_bottom_chars and len(oval_arc_bottom_chars) > 0
        has_body = oval_body_lines_chars and any(
            ln for ln in oval_body_lines_chars if ln)
        if has_arc_top or has_arc_bot or has_body:
            # --- 新 structured layout ---
            # 12m-1 patch r15: precompute inner ellipse axes for arc & body
            # — both share the same inner ellipse (consistent geometry).
            _half_a_outer = width_mm / 2.0
            _half_b_outer = height_mm / 2.0
            _d_offset = 0.30 * min(_half_a_outer, _half_b_outer)
            _inner_a = max(_half_a_outer - _d_offset, 0.1)
            _inner_b = max(_half_b_outer - _d_offset, 0.1)
            # 12m-7 r26: 圓戳章單圓周模式（round_continuous_arc）—
            # 上弧文 wrap 300° 環繞（從 7 點鐘起 CW 到 5 點鐘），
            # 下弧文輸入忽略，body 在中央維持。底部 6 點鐘留 60° gap 給梅花。
            if preset == "round" and round_continuous_arc:
                if has_arc_top:
                    arc_n = len(oval_arc_top_chars)
                    # Ring band midpoint as radius
                    ring_radius = (_half_a_outer + _inner_a) / 2.0
                    # 12m-7 r27: char size cap 收緊避免碰觸內外框
                    # ring_band_width - 1.4mm（含 stroke 0.6mm + 0.4mm 各側
                    # safety margin）。保證 char visual extent (含 stroke)
                    # 不碰 inner/outer 框線。
                    arc_len_300 = ring_radius * math.radians(300.0)
                    arc_sz_by_spacing = arc_len_300 / max(arc_n, 1) * 0.85
                    ring_band_cap = max(_d_offset - 1.4, 0.5)
                    arc_sz = min(ring_band_cap, char_size_mm,
                                 arc_sz_by_spacing)
                    arc_sz = max(arc_sz, 2.0)
                    # span 300° start 120° (7 點鐘); _arc_text_positions
                    # theta 增加 = CW direction in screen coords。
                    positions = _arc_text_positions(
                        arc_n, ring_radius, cx, cy,
                        span_deg=300.0, start_deg=120.0,
                    )
                    for ch, (x, y, rot) in zip(oval_arc_top_chars, positions):
                        placements.append((ch, x, y, rot, arc_sz, arc_sz))
                # 下弧文 ignored in continuous arc mode
                if has_body:
                    body_placements = _oval_body_layout(
                        oval_body_lines_chars,
                        inner_w=inner_w, inner_h=inner_h,
                        cx=cx, cy=cy, char_size_cap=char_size_mm,
                        inner_ellipse_a=_inner_a,
                        inner_ellipse_b=_inner_b,
                        bold_flags=oval_body_bold,
                    )
                    placements.extend(body_placements)
            else:
                # Arc top (公司名沿上弧) — 既有 oval/round 結構化 layout
                # 12m-1 patch r8/r14/r15: char-size aware placement +
                # ring-band cap + ring-band midpoint placement.
                if has_arc_top:
                    arc_n = len(oval_arc_top_chars)
                    arc_sz = _oval_arc_char_size(
                        arc_n, inner_w=inner_w, inner_h=inner_h,
                        char_size_cap=char_size_mm,
                        ring_band_width=_d_offset,
                    )
                    positions = _oval_arc_positions(
                        arc_n, inner_w=inner_w, inner_h=inner_h,
                        cx=cx, cy=cy, top=True, char_size=arc_sz,
                        inner_ellipse_a=_inner_a, inner_ellipse_b=_inner_b,
                    )
                    for ch, (x, y, rot) in zip(oval_arc_top_chars, positions):
                        placements.append((ch, x, y, rot, arc_sz, arc_sz))
                # Arc bottom (地址沿下弧)
                if has_arc_bot:
                    arc_n = len(oval_arc_bottom_chars)
                    arc_sz = _oval_arc_char_size(
                        arc_n, inner_w=inner_w, inner_h=inner_h,
                        char_size_cap=char_size_mm,
                        ring_band_width=_d_offset,
                    )
                    positions = _oval_arc_positions(
                        arc_n, inner_w=inner_w, inner_h=inner_h,
                        cx=cx, cy=cy, top=False, char_size=arc_sz,
                        inner_ellipse_a=_inner_a, inner_ellipse_b=_inner_b,
                    )
                    for ch, (x, y, rot) in zip(oval_arc_bottom_chars, positions):
                        placements.append((ch, x, y, rot, arc_sz, arc_sz))
                # Body 1-3 行水平文字
                # 12m-1 patch r12: 傳 inner_ellipse_b 給 dynamic max_h cap +
                # bold flags 給 slot-level 加粗 (中央 1 / 中央 2 強調用)
                if has_body:
                    body_placements = _oval_body_layout(
                        oval_body_lines_chars,
                        inner_w=inner_w, inner_h=inner_h,
                        cx=cx, cy=cy, char_size_cap=char_size_mm,
                        inner_ellipse_a=_inner_a,
                        inner_ellipse_b=_inner_b,
                        bold_flags=oval_body_bold,
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
        # 12m-1 patch r12: handle both 6-tuple and 7-tuple placements
        # (oval body chars carry bold flag; other presets remain 6-tuple)
        for i, placement in enumerate(placements):
            c, pcx, pcy, prot, pw, ph = placement[:6]
            extra = placement[6:]   # bold flag if present
            dx, dy = (0.0, 0.0)
            if i < len(char_offsets):
                ofs = char_offsets[i]
                if ofs is not None and len(ofs) >= 2:
                    dx, dy = float(ofs[0]), float(ofs[1])
            new_cx = pcx + dx
            new_cy = pcy + dy
            half_w, half_h = pw / 2.0, ph / 2.0
            new_cx = max(inner_left + half_w, min(inner_right - half_w, new_cx))
            new_cy = max(inner_top + half_h, min(inner_bot - half_h, new_cy))
            clamped.append((c, new_cx, new_cy, prot, pw, ph, *extra))
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
    # Phase 12m-1 patch r12: bold flags per slot (中央 1/2/3)
    oval_body_bold: list[bool] = None,
    # Phase 12m-1 patch r13: 裝飾符號 ('plum' / 'star' / 'circle' / 'none')
    oval_decoration: str = "plum",
    oval_sawtooth: bool = False,
    # Phase 12m-7: tax_invoice 上方標題（如「統一發票專用章」）
    oval_top_title: str = "",
    # Phase 12m-7: tax_invoice 縣市名（如「台北市」）
    oval_location: str = "",
    # Phase 12m-7: 縣市位置 ("bottom" | "left")
    oval_location_position: str = "bottom",
    # Phase 12m-7 r26: 圓戳章 (round) 單圓周模式 — 上弧文 wrap 300°，
    # 取消左右梅花，只保留底部梅花。僅 round preset 啟用時生效。
    round_continuous_arc: bool = False,
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
    # Phase 12m-7 r19: tax_invoice 中央 2 (slot_1) auto-prepend「負責人」
    # + 1 空白 cell separator（取代 r3 的「負責人：」冒號）。User spec：
    # 預設「負責人」與填報文字之間 = 1 cell 空格。Blank Character (strokes=[])
    # 佔 1 cell 但 render 時 0 strokes → visual gap。
    oval_body_lines_chars = []
    for _idx, _line in enumerate(oval_body_lines):
        _line_str = _line if _line else ""
        if (preset == "tax_invoice" and _idx == 1
                and _line_str and "負責人" not in _line_str):
            _prefix_chars = _load_chars("負責人")
            _blank = Character(char=" ", unicode_hex="0020",
                               strokes=[], data_source="blank_half")
            oval_body_lines_chars.append(
                _prefix_chars + [_blank] + _load_chars(_line_str))
        else:
            oval_body_lines_chars.append(_load_chars(_line_str))
    # Phase 12m-6: tax_invoice 固定「統一編號」標題
    oval_label_chars = (_load_chars("統一編號")
                        if preset == "tax_invoice" else [])
    # Phase 12m-7: tax_invoice optional 上方標題 + 縣市
    oval_top_title_chars = (_load_chars(oval_top_title)
                            if (preset == "tax_invoice" and oval_top_title)
                            else [])
    oval_location_chars = (_load_chars(oval_location)
                           if (preset == "tax_invoice" and oval_location)
                           else [])

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
        oval_body_bold=oval_body_bold,
        oval_label_chars=oval_label_chars,
        oval_top_title_chars=oval_top_title_chars,
        oval_location_chars=oval_location_chars,
        oval_location_position=oval_location_position,
        round_continuous_arc=round_continuous_arc,
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
    # 12m-1 patch r12: bold flag optional 7th element (oval body chars).
    # 12m-7 r2: capped_stretch optional 8th element (tax_invoice all chars
    # — fixes 「一」 etc. extreme-aspect chars getting bbox-stretched into
    # vertical bars while still letting square chars fill cells).
    char_pieces: list[str] = []
    for placement in placements:
        c, x, y, rot, w, h = placement[:6]
        bold = placement[6] if len(placement) > 6 else False
        capped_stretch = placement[7] if len(placement) > 7 else False
        if capped_stretch:
            piece = _char_capped_stretch_svg(c, x, y, w, h, rot)
        else:
            piece = _char_cut_paths_stretched(c, x, y, w, h, rot)
        if bold:
            # Bold render：wrap with thicker stroke override (×2 outer stroke)
            piece = (f'<g stroke-width="{stroke_width * 2.0:.3f}">'
                     f'{piece}</g>')
        char_pieces.append(piece)

    # Decorations.
    deco_pieces: list[str] = []
    for d in decorations:
        deco_pieces.append(_decoration_svg(d))

    # 12m-1 patch r11/r13: oval 裝飾符號（梅花 / 五角星 / 圓形 / 不顯示），
    # 左右兩側 ring band 中央。佔位避免弧文延伸到最左/最右。
    # 12m-7: tax_invoice 縣市 position=left 時隱藏 LEFT 裝飾（讓位給縣市直立字）
    # 12m-7 r6: tax_invoice 梅花尺寸 + 位置 fill side compartment：
    # 內邊接近中央 1 文字邊緣，外邊接近外框 L/R 直線，恰好不碰觸。
    if (preset in ("oval", "tax_invoice", "round")
            and show_border and oval_decoration != "none"):
        cx_mid = stamp_width_mm / 2.0
        cy_mid = stamp_height_mm / 2.0
        outer_a = stamp_width_mm / 2.0
        outer_b = stamp_height_mm / 2.0
        d_offset = 0.30 * min(outer_a, outer_b)
        inner_a = max(outer_a - d_offset, 0.1)
        deco_stroke = stroke_width * 0.5
        if preset == "tax_invoice":
            # 12m-7 r7: 梅花尺寸 = 中央 1 字體大小（user 要求）。
            # 仍用 x_fill / y_fill 當上限避免梅花超出 side compartment 或
            # 撞 label/slot_1 row。
            # X: side compartment midpoint
            # Y: slot_0 row level
            # 12m-7 r14: 跟 _placements_for_preset 一致用常數 36mm
            body_usable_w_calc = min(TAX_INVOICE_BODY_USABLE_W_MM,
                                     stamp_width_mm * 0.90)
            inner_h_calc = stamp_height_mm - 2 * border_padding_mm
            # 12m-7 r15: 同步 STADIUM_BODY_SLOTS（r21: label 不動仍 -0.13）
            slot_0_y = cy_mid + (-0.02) * inner_h_calc
            label_y = cy_mid + (-0.13) * inner_h_calc
            slot_1_y = cy_mid + (+0.10) * inner_h_calc
            # Char heights (slot max_h ratios from STADIUM_BODY_SLOTS r15)
            ch_sz_label = 0.07 * inner_h_calc
            ch_sz_slot_1 = 0.06 * inner_h_calc
            margin = 0.3
            n_slot_0 = (
                len(oval_body_lines[0])
                if (oval_body_lines and len(oval_body_lines) > 0
                    and oval_body_lines[0])
                else 8
            )
            cell_w_slot_0 = body_usable_w_calc / max(n_slot_0, 1)
            slot_0_max_h = 0.12 * inner_h_calc   # r15
            # 12m-7 r15: 0.9 → 0.78 一致 with _stadium_body_row
            ch_sz_slot_0 = min(cell_w_slot_0 * 0.78, slot_0_max_h,
                               char_size_mm)
            ch_sz_slot_0 = max(ch_sz_slot_0, 2.5)  # 2.5mm min legibility
            # x_fill / y_fill 當上限，目標尺寸 = ch_sz_slot_0
            side_compartment_w = outer_a - body_usable_w_calc / 2.0
            plum_r_x_max = side_compartment_w / 2.0 - margin
            plum_r_y_max = min(
                (slot_0_y - label_y) - ch_sz_label / 2.0 - margin,
                (slot_1_y - slot_0_y) - ch_sz_slot_1 / 2.0 - margin,
            )
            plum_r_target = ch_sz_slot_0 / 2.0
            deco_r = max(min(plum_r_target, plum_r_x_max, plum_r_y_max),
                         0.5)
            # X: side compartment midpoint
            plum_x_offset = (body_usable_w_calc / 2.0 + outer_a) / 2.0
            right_x = cx_mid + plum_x_offset
            left_x = cx_mid - plum_x_offset
            deco_y = slot_0_y
        else:
            # oval / others: 既有 ring band midpoint 邏輯 + d_offset×0.30 plum
            mid_a = (outer_a + inner_a) / 2.0
            deco_r = d_offset * 0.30
            right_x = cx_mid + mid_a
            left_x = cx_mid - mid_a
            deco_y = cy_mid
        # 12m-7 r26: 圓戳章單圓周模式 — 取消左右梅花，改放單一梅花在 6 點鐘
        if preset == "round" and round_continuous_arc:
            mid_a = (outer_a + inner_a) / 2.0
            bottom_x = cx_mid
            bottom_y = cy_mid + mid_a   # ring band 底部中點 (6 點鐘方向)
            bottom_deco = _oval_decoration_svg(
                oval_decoration, bottom_x, bottom_y, deco_r, deco_stroke)
            if bottom_deco:
                deco_pieces.append(bottom_deco)
        else:
            right_deco = _oval_decoration_svg(
                oval_decoration, right_x, deco_y, deco_r, deco_stroke)
            # 12m-7: 隱藏 LEFT 裝飾 if tax_invoice 且 縣市放左邊
            suppress_left = (preset == "tax_invoice"
                             and oval_location_position == "left"
                             and oval_location)
            left_deco = "" if suppress_left else _oval_decoration_svg(
                oval_decoration, left_x, deco_y, deco_r, deco_stroke)
            if right_deco:
                deco_pieces.append(right_deco)
            if left_deco:
                deco_pieces.append(left_deco)

    # 12m-1 patch r19: oval 鋸齒邊飾 — smooth ellipse 外側貼填三角形。
    # 設計上 inner side（朝印面內）保持 smooth（user 要求），outer side
    # 呈鋸齒。filled 三角形 fill 用同 stroke 顏色，stroke=none。
    if (preset in ("oval", "tax_invoice", "round")
            and show_border and oval_sawtooth):
        teeth_d = _oval_sawtooth_teeth_svg(
            stamp_width_mm / 2.0, stamp_height_mm / 2.0,
            stamp_width_mm / 2.0, stamp_height_mm / 2.0,
            num_teeth=80, depth_outward_mm=1.0,
        )
        # Concave: fill black (or color) so teeth render as solid triangles
        sawtooth_fill = ("#000" if engrave_mode == "concave"
                         else "#c33")  # match convex base red
        deco_pieces.append(
            f'<path d="{teeth_d}" fill="{sawtooth_fill}" stroke="none"/>'
        )

    # Phase 12j: viewBox 加 stroke padding 防外框 stroke 外緣被切
    # （圓 path 邊在 width/2，stroke 從中心向外延伸 stroke_width/2，
    # 過去 viewBox=(0, 0, w, h) 會切掉 stroke 外緣 0.3mm）。
    # 12m-1 patch r14/r16/r19: oval outer × 1.5 + inner × 0.3 (5:1
    # ratio for visible double-line)。viewBox padding 用 outer 完整半徑
    # （0.45mm）；sawtooth 開啟時加 tooth depth（1mm）防 teeth 超出 viewBox
    # 被切。
    SAWTOOTH_DEPTH_MM = 1.0
    max_stroke_mult = (1.5 if preset in ("oval", "tax_invoice", "round") else 1.0)
    sawtooth_extra = (SAWTOOTH_DEPTH_MM
                      if (oval_sawtooth
                          and preset in ("oval", "tax_invoice", "round")) else 0.0)
    vb_pad = max(stroke_width * max_stroke_mult / 2,
                 sawtooth_extra + stroke_width * 0.5)
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
        # 邊框描邊（在字上面，視覺上邊界清楚）。
        # 12m-1 patch r10/r13: oval outer ×1.5 + inner ×0.5 (3:1 ratio for
        # visible double-line). 對齊 T-02 / TT-* reference visual。
        if border_d_list:
            for i, d in enumerate(border_d_list):
                if preset in ("oval", "round"):
                    # 12m-1 r16: oval 5:1 ratio (粗 outer + thin inner) for
                    # visible double-line contrast — user 明確要求。
                    # 12m-7 r25: round 共用相同視覺對比規則。
                    stroke_w = stroke_width * (1.5 if i == 0 else 0.3)
                elif preset == "tax_invoice":
                    # 12m-7 r3: 更細外框（×0.7）
                    stroke_w = stroke_width * 0.5
                else:
                    stroke_w = stroke_width
                body_pieces.append(
                    f'<path d="{d}" fill="none" stroke="{CONVEX_BORDER_BLACK}" '
                    f'stroke-width="{stroke_w}"/>'
                )
        # 12m-7 r3: tax_invoice convex separator arcs
        if preset == "tax_invoice" and show_border and double_border:
            top_sep_d, bot_sep_d = _stadium_inner_separator_paths(
                stamp_width_mm, stamp_height_mm)
            sep_stroke = stroke_width * 0.5
            for sep_d in (top_sep_d, bot_sep_d):
                if sep_d:
                    body_pieces.append(
                        f'<path d="{sep_d}" fill="none" '
                        f'stroke="{CONVEX_BORDER_BLACK}" '
                        f'stroke-width="{sep_stroke}"/>'
                    )
        body_pieces.extend(deco_pieces)
        return f'{svg_open}{"".join(body_pieces)}</svg>'

    # 陰刻 (concave，預設，向後相容)：字凹下、白底、字 outline 用 stroke
    # 12m-1 patch r10/r13: oval outer ×1.5 (粗 visible) + inner ×0.5 (細 visible)，
    # 兩線粗細差 3:1 雙線外框 visually distinct。
    border_pieces = []
    for i, d in enumerate(border_d_list):
        if preset in ("oval", "round"):
            # 12m-1 r16: oval 5:1 visible double-line（user 明確要對比）
            # 12m-7 r25: round 共用
            mult = 1.5 if i == 0 else 0.3
            border_pieces.append(
                f'<path class="stamp-border" d="{d}" '
                f'stroke-width="{stroke_width * mult}"/>'
            )
        elif preset == "tax_invoice":
            # 12m-7 r3: 更細外框（×0.7 比 char stroke 細，~0.42mm）
            # 配合 separator arcs 統一視覺粗細，對齊 ED2/ED4 reference
            border_pieces.append(
                f'<path class="stamp-border" d="{d}" '
                f'stroke-width="{stroke_width * 0.5}"/>'
            )
        else:
            border_pieces.append(f'<path class="stamp-border" d="{d}"/>')
    # 12m-7 r3: tax_invoice double_border → render 2 OPEN separator arcs
    # （上下分隔弧），不是 closed inner stadium。Reference (ED2/ED4) 顯示
    # inner 邊只有上下弧，不含左右直線。
    if preset == "tax_invoice" and show_border and double_border:
        top_sep_d, bot_sep_d = _stadium_inner_separator_paths(
            stamp_width_mm, stamp_height_mm)
        sep_stroke = stroke_width * 0.5
        for sep_d in (top_sep_d, bot_sep_d):
            if sep_d:
                border_pieces.append(
                    f'<path class="stamp-border" d="{sep_d}" '
                    f'fill="none" stroke-width="{sep_stroke}"/>'
                )
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
    oval_body_bold: list[bool] = None,
    oval_decoration: str = "plum",
    oval_sawtooth: bool = False,
    # Phase 12m-7: tax_invoice 上方標題 / 縣市
    oval_top_title: str = "",
    oval_location: str = "",
    oval_location_position: str = "bottom",
    # Phase 12m-7 r26: 圓戳章 (round) 單圓周模式
    round_continuous_arc: bool = False,
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
    # Phase 12m-7 r19: tax_invoice slot_1 auto-prepend「負責人」+ blank cell
    oval_body_lines_chars = []
    for _idx, _line in enumerate(oval_body_lines):
        _line_str = _line if _line else ""
        if (preset == "tax_invoice" and _idx == 1
                and _line_str and "負責人" not in _line_str):
            _prefix_chars = _load_chars("負責人")
            _blank = Character(char=" ", unicode_hex="0020",
                               strokes=[], data_source="blank_half")
            oval_body_lines_chars.append(
                _prefix_chars + [_blank] + _load_chars(_line_str))
        else:
            oval_body_lines_chars.append(_load_chars(_line_str))
    # Phase 12m-6: tax_invoice 固定「統一編號」標題
    oval_label_chars = (_load_chars("統一編號")
                        if preset == "tax_invoice" else [])
    # Phase 12m-7: tax_invoice optional 上方標題 + 縣市
    oval_top_title_chars = (_load_chars(oval_top_title)
                            if (preset == "tax_invoice" and oval_top_title)
                            else [])
    oval_location_chars = (_load_chars(oval_location)
                           if (preset == "tax_invoice" and oval_location)
                           else [])

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
        oval_body_bold=oval_body_bold,
        oval_label_chars=oval_label_chars,
        oval_top_title_chars=oval_top_title_chars,
        oval_location_chars=oval_location_chars,
        oval_location_position=oval_location_position,
        round_continuous_arc=round_continuous_arc,
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
    # 12m-1 patch r12: handle 6-tuple or 7-tuple (with bold flag) placements
    for placement in placements:
        c, cx_mm, cy_mm, rot, w_mm, h_mm = placement[:6]
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
    # 12m-1 patch r9: oval double_border 是 body-wrapping inner ellipse，
    # 不再是 concentric — 弧文佔外-內框環帶，inset 只算 border_padding。
    if preset in ("oval", "tax_invoice", "round"):
        inset = border_padding_mm
    else:
        inset = border_padding_mm + (double_gap_mm if double_border else 0)
    inner_w = max(stamp_width_mm - 2 * inset, 1.0)
    inner_h = max(stamp_height_mm - 2 * inset, 1.0)
    if preset == "square_name":
        max_chars = 4   # spec
    elif preset == "square_official":
        max_chars = 9   # 3×3 cap
    elif preset in ("oval", "tax_invoice", "round"):
        # 12m-7 r25: round (圓戳章) 共用 oval 結構化 caps（移除舊
        # 簡單 ring text + center 計算邏輯）
        # 12m-1 patch r4 / 12m-6: oval 結構化後 max_chars single number 不再
        # 有意義；改回傳結構化 caps（弧文 / body 各自）。Legacy max_chars 保留
        # 為估計值。tax_invoice 共用 oval shape + caps logic。
        # Cap 計算用「最小可讀字身 2.5mm」當下限，因為 _oval_arc_char_size
        # 跟 _oval_body_layout 都會 auto-shrink 字身來容納更多字 — 真實 cap
        # 是 readability，不是 char_size_mm。
        MIN_LEGIBLE_MM = 2.5
        a = (inner_w / 2.0) * (1.0 - 0.13)   # match _oval_arc_positions padding
        b = (inner_h / 2.0) * (1.0 - 0.13)
        # Arc length approximation: average-radius × span_rad（160° span）
        arc_len = ((a + b) / 2.0) * math.radians(140.0)  # r13: span 140
        # 字身 auto-shrink 到 MIN_LEGIBLE_MM 為止（fill_ratio 0.92）
        arc_max = max(int(arc_len * 0.92 / MIN_LEGIBLE_MM), 1)
        # Body per-line: 最寬 y=0 處可用 80% × inner_w，字身可 auto-shrink
        body_per_line = max(
            int((0.80 * inner_w) / (MIN_LEGIBLE_MM * 0.92)), 1)
        # Legacy max_chars: 上弧 + 下弧 + 3 行 body 總和上限估計
        max_chars = arc_max * 2 + body_per_line * 3
        oval_caps = {
            "arc_top_max": arc_max,
            "arc_bottom_max": arc_max,
            "body_per_line_max": body_per_line,
            "body_lines_max": 3,
            "min_legible_mm": MIN_LEGIBLE_MM,
        }
    elif preset == "rectangle_title":
        per_row = max(int(inner_w / (char_size_mm * 1.1)), 1)
        max_chars = per_row * 2
    else:
        max_chars = 0
    result = {
        "preset": preset,
        "max_chars": max_chars,
        "inner_size_mm": [round(inner_w, 2), round(inner_h, 2)],
    }
    # 12m-1 patch r4 / 12m-6: oval & tax_invoice extra structured caps
    if preset in ("oval", "tax_invoice", "round"):
        result["oval_caps"] = oval_caps  # type: ignore[name-defined]
    return result


__all__ = [
    "StampPreset",
    "render_stamp_svg",
    "render_stamp_gcode",
    "stamp_capacity",
]
