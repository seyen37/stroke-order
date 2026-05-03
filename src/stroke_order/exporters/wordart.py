"""
文字雲 / 藝術文字模式 (Word-art) exporter.

Arranges Chinese characters inside or around a geometric shape:

- **ring**    — characters distributed evenly along the whole perimeter
- **fill**    — characters flow row-by-row within the shape's interior,
                each row clipped to the shape's scanline (β-mode)
- **linear**  — for polygons, each edge gets an independent text field

Character orientation
---------------------

All modes support 4 orientations:

- ``bottom_to_center`` (default) — the bottom of each glyph faces the
  shape's centroid (classic seal / 印章 style)
- ``top_to_center`` — upside-down of the above
- ``upright`` — no rotation at all (characters all face up)
- ``tangent`` — baseline runs along the tangent direction of the boundary

Characters are rendered using their IR stroke data (canonical 2048 em),
transformed to ``char_size_mm`` and placed at computed (x, y) + rotation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

from ..ir import EM_SIZE, Character
from ..shapes import Circle, Ellipse, Polygon, Shape
from .svg import _outline_path_d


Orientation = Literal["bottom_to_center", "top_to_center", "upright", "tangent"]
BandOrient = Literal["bottom_to_center", "top_to_center"]  # three_band uses only these
Align = Literal["spread", "center", "left", "right"]
Layout = Literal["ring", "fill", "linear", "three_band",
                 "wordcloud", "concentric", "gradient_v", "split_lr",
                 # Phase 5an
                 "gradient_h", "wave",
                 "radial_convex", "radial_concave"]


MIN_CHAR_SIZE_MM = 3.0   # auto_fit floor (B1 fixed)


def _pick_slot_indices(n_chars: int, n_slots: int,
                       align: "Align" = "spread") -> list[int]:
    """Return which ``n_slots`` slot indices should receive characters.

    - ``spread``: evenly distributed across ``[0, n_slots-1]`` **including**
      both endpoints (B1). Single char → centered (C1).
    - ``center``: ``n_chars`` consecutive middle slots.
    - ``left``:   first ``n_chars`` slots.
    - ``right``:  last ``n_chars`` slots.

    Edge cases:
    - ``n_chars >= n_slots`` → all slots (alignment is a no-op).
    - ``n_chars == 1`` always returns ``[n_slots // 2]`` regardless of align (C1).
    - ``n_chars <= 0`` or ``n_slots <= 0`` → ``[]``.
    """
    if n_chars <= 0 or n_slots <= 0:
        return []
    if n_chars >= n_slots:
        return list(range(n_slots))
    # C1: single char always centered
    if n_chars == 1:
        return [n_slots // 2]

    if align == "left":
        return list(range(n_chars))
    if align == "right":
        return list(range(n_slots - n_chars, n_slots))
    if align == "center":
        start = (n_slots - n_chars) // 2
        return list(range(start, start + n_chars))
    # "spread" (default) — B1: endpoints included
    step = (n_slots - 1) / (n_chars - 1)
    return [int(i * step + 0.5) for i in range(n_chars)]


# ---------------------------------------------------------------------------
# Shared helpers: auto_cycle + auto_fit
# ---------------------------------------------------------------------------


def _cycle_chars(chars: list, target: int) -> list:
    """Repeat ``chars`` (by reference) until the list has exactly ``target``
    elements. Empty input or non-positive target returns an empty list."""
    if not chars or target <= 0:
        return []
    if len(chars) >= target:
        return chars[:target]
    out: list = []
    i = 0
    n = len(chars)
    while len(out) < target:
        out.append(chars[i % n])
        i += 1
    return out


def _fit_char_size_binary(
    enough_at_size: Callable[[float], bool],
    requested: float,
    min_size: float = MIN_CHAR_SIZE_MM,
    tol: float = 0.1,
) -> float:
    """Binary-search the largest char size in ``[min_size, requested]`` such
    that ``enough_at_size(size)`` returns True.

    If already ``enough_at_size(requested)``, returns ``requested``. If not
    even ``enough_at_size(min_size)``, returns ``min_size`` (caller can decide
    to truncate).
    """
    if enough_at_size(requested):
        return requested
    if not enough_at_size(min_size):
        return min_size
    lo, hi = min_size, requested
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if enough_at_size(mid):
            lo = mid
        else:
            hi = mid
    return lo

CharLoader = Callable[[str], Optional[Character]]


@dataclass
class WordArtPage:
    """Everything needed to emit one wordart SVG."""
    shape: Shape
    page_width_mm: float
    page_height_mm: float
    placed_chars: list[tuple[Character, float, float, float, float]] = field(
        default_factory=list
    )
    # tuple: (char, x_mm, y_mm, size_mm, rotation_deg)
    missing: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Orientation → rotation calculator
# ---------------------------------------------------------------------------


def _rotation_for(orient: Orientation, outward_angle_deg: float) -> float:
    """
    Given the outward-normal angle at a boundary point (SVG deg), return
    the SVG rotation to apply to the glyph (deg, clockwise positive).

    SVG conventions: 0° = 3 o'clock, 90° = 6, 180° = 9, 270° = 12.
    Glyph's native 'up' direction is 270° (on-screen up). For each
    orientation we compute what the glyph's 'up' should become and
    return (desired_up − 270°).
    """
    if orient == "upright":
        return 0.0
    if orient == "tangent":
        # char bottom walks along the tangent (perpendicular to outward)
        return (outward_angle_deg - 180.0) % 360
    if orient == "top_to_center":
        # glyph up points INWARD (toward center) = outward + 180°
        return ((outward_angle_deg + 180.0) - 270.0) % 360
    # default: bottom_to_center — glyph up points OUTWARD
    return (outward_angle_deg - 270.0) % 360


# ---------------------------------------------------------------------------
# Ring layout
# ---------------------------------------------------------------------------


def ring_positions(
    shape: Shape, char_size_mm: float,
    start_t: float = 0.0, max_chars: Optional[int] = None,
) -> list[tuple[float, float, float]]:
    """Evenly space points along shape perimeter at char-width intervals.

    Returns list of (x_mm, y_mm, outward_angle_deg) one per slot.
    """
    per = shape.perimeter()
    if per <= 0 or char_size_mm <= 0:
        return []
    n = int(per / char_size_mm)
    if max_chars is not None:
        n = min(n, max_chars)
    out = []
    for i in range(n):
        t = (start_t + i / n) % 1.0
        x, y = shape.point_at(t)
        ang = shape.tangent_at(t)
        out.append((x, y, ang))
    return out


def compute_ring(
    text: str, shape: Shape, char_size_mm: float,
    orient: Orientation, char_loader: CharLoader,
    *,
    auto_fit: bool = False,
    min_char_size_mm: float = MIN_CHAR_SIZE_MM,
) -> tuple[list, list[str]]:
    """Place text around the ring. Text is always cycled to fill the ring.
    If ``auto_fit`` is True and text is longer than the ring's slot count at
    the requested size, the size is shrunk (down to ``min_char_size_mm``) so
    the full text fits exactly in one revolution.
    """
    placed = []
    missing: list[str] = []

    # Gather loadable chars only (filter whitespace)
    chars: list[Character] = []
    for ch in text:
        if ch.isspace():
            continue
        c = char_loader(ch)
        if c is None:
            missing.append(ch)
        else:
            chars.append(c)
    if not chars:
        return placed, missing

    size = char_size_mm
    if auto_fit:
        size = _fit_char_size_binary(
            lambda s: len(ring_positions(shape, s)) >= len(chars),
            requested=char_size_mm, min_size=min_char_size_mm,
        )

    slots = ring_positions(shape, size)
    if not slots:
        return placed, missing

    # Always cycle (ring's natural behavior)
    for i, (x, y, outward) in enumerate(slots):
        c = chars[i % len(chars)]
        rot = _rotation_for(orient, outward)
        placed.append((c, x, y, size, rot))
    return placed, missing


# ---------------------------------------------------------------------------
# Fill layout (β-mode: scanline with per-row shape-clipped x-extents)
# ---------------------------------------------------------------------------


def fill_positions(
    shape: Shape, char_size_mm: float,
    line_spacing_factor: float = 1.0,
    direction: Literal["horizontal", "vertical"] = "horizontal",
) -> list[tuple[float, float]]:
    """Generate (x_center, y_center) slots inside the shape.

    - ``horizontal`` (default, 橫書): chars fill row-by-row, left-to-right.
    - ``vertical``   (直書): chars fill column-by-column, top-to-bottom within
      each column, columns from right to left.

    Each slot is one ``char_size_mm × char_size_mm`` cell fully within
    the shape.
    """
    xmin, ymin, xmax, ymax = shape.bbox()
    step = char_size_mm * line_spacing_factor

    if direction == "vertical":
        slots: list[tuple[float, float]] = []
        # Iterate columns right-to-left
        x = xmax - char_size_mm / 2
        while x - char_size_mm / 2 >= xmin:
            # Find the vertical extent of this column by stepping y and
            # testing shape.contains at top/bottom of cell.
            y = ymin + char_size_mm / 2
            col_cells: list[tuple[float, float]] = []
            while y + char_size_mm / 2 <= ymax:
                if (shape.contains(x - char_size_mm / 3, y - char_size_mm / 3)
                        and shape.contains(x + char_size_mm / 3, y - char_size_mm / 3)
                        and shape.contains(x - char_size_mm / 3, y + char_size_mm / 3)
                        and shape.contains(x + char_size_mm / 3, y + char_size_mm / 3)):
                    col_cells.append((x, y))
                y += char_size_mm
            slots.extend(col_cells)
            x -= step
        return slots

    # horizontal (original)
    y = ymin + char_size_mm / 2
    slots = []
    row_step = step
    while y + char_size_mm / 2 <= ymax:
        for left, right in shape.scanline(y):
            left_in = left + char_size_mm / 2
            right_in = right - char_size_mm / 2
            if right_in <= left_in:
                continue
            usable = right_in - left_in
            cells = int(usable / char_size_mm) + 1
            row_span = (cells - 1) * char_size_mm
            x0 = (left_in + right_in - row_span) / 2
            for k in range(cells):
                x = x0 + k * char_size_mm
                if (shape.contains(x - char_size_mm / 3, y - char_size_mm / 3)
                        and shape.contains(x + char_size_mm / 3, y - char_size_mm / 3)
                        and shape.contains(x - char_size_mm / 3, y + char_size_mm / 3)
                        and shape.contains(x + char_size_mm / 3, y + char_size_mm / 3)):
                    slots.append((x, y))
        y += row_step
    return slots


def compute_fill(
    text: str, shape: Shape, char_size_mm: float,
    char_loader: CharLoader, orient: Orientation = "upright",
    *,
    auto_cycle: bool = False,
    auto_fit: bool = False,
    min_char_size_mm: float = MIN_CHAR_SIZE_MM,
    direction: Literal["horizontal", "vertical"] = "horizontal",
) -> tuple[list, list[str]]:
    placed = []
    missing: list[str] = []
    chars: list[Character] = []
    for ch in text:
        if ch.isspace():
            continue
        c = char_loader(ch)
        if c is None:
            missing.append(ch)
        else:
            chars.append(c)
    if not chars:
        return placed, missing

    size = char_size_mm
    if auto_fit:
        size = _fit_char_size_binary(
            lambda s: len(fill_positions(shape, s, direction=direction)) >= len(chars),
            requested=char_size_mm, min_size=min_char_size_mm,
        )

    slots = fill_positions(shape, size, direction=direction)
    if not slots:
        return placed, missing

    if auto_cycle and len(chars) < len(slots):
        chars = _cycle_chars(chars, len(slots))

    for i, (x, y) in enumerate(slots):
        if i >= len(chars):
            break
        placed.append((chars[i], x, y, size, 0.0))
    return placed, missing


# ---------------------------------------------------------------------------
# Linear layout (polygon per-edge fields)
# ---------------------------------------------------------------------------


def edge_positions(
    edge_start: tuple[float, float], edge_end: tuple[float, float],
    char_size_mm: float,
) -> list[tuple[float, float, float]]:
    """Evenly distribute points along an edge. Returns (x, y, outward_angle)."""
    ax, ay = edge_start
    bx, by = edge_end
    L = math.hypot(bx - ax, by - ay)
    n = int(L / char_size_mm)
    if n < 1:
        return []
    # Outward normal: edge dir rotated 90° (we'll decide sign via fallback)
    dx, dy = bx - ax, by - ay
    # Default outward = edge dir rotated +90° CCW in math, = -90° in SVG y-down
    nx, ny = -dy, dx
    outward_angle = math.degrees(math.atan2(ny, nx)) % 360
    out = []
    for i in range(n):
        t = (i + 0.5) / n  # centered slots on edge
        x = ax + dx * t
        y = ay + dy * t
        out.append((x, y, outward_angle))
    return out


def _spread_positions_on_edge(
    edge_start: tuple[float, float],
    edge_end: tuple[float, float],
    n_chars: int,
) -> list[tuple[float, float]]:
    """Phase 5b r3: 沿邊均勻分布 n_chars 個位置，**邊首尾各留半個 inter-char gap**。

    與 ``_pick_slot_indices(spread)`` 從 ``edge_positions`` 預製 slot grid 中挑
    index（會產生不均勻 gap 當 chars < slots）不同，這裡直接以 n_chars 為基準
    重算位置：char j 位於邊長分數 ``(j + 0.5) / n_chars`` 處。

    視覺結果：邊內字距相同；邊首尾各 ``edge_length / (2 * n_chars)`` padding，
    讓多邊形邊與邊交接處左右兩字保留半 gap，不相黏。
    """
    if n_chars <= 0:
        return []
    ax, ay = edge_start
    bx, by = edge_end
    dx, dy = bx - ax, by - ay
    out: list[tuple[float, float]] = []
    for i in range(n_chars):
        t = (i + 0.5) / n_chars
        out.append((ax + dx * t, ay + dy * t))
    return out


def compute_linear(
    texts_per_edge: list[str],
    shape: Polygon,
    char_size_mm: float,
    orient: Orientation,
    char_loader: CharLoader,
    *,
    auto_cycle: bool = False,
    auto_fit: bool = False,
    min_char_size_mm: float = MIN_CHAR_SIZE_MM,
    align: Align = "spread",
) -> tuple[list, list[str]]:
    """Each edge of the polygon gets its own text string.

    ``auto_cycle`` — per edge, cycle text to fill that edge's slot count
    (when edge slots > text length).
    ``auto_fit`` — find one global char_size where every edge's slot count
    >= its text length (when text is longer than slots at requested size).
    ``align`` — when ``auto_cycle`` is False **and** edge has more slots than
    chars, choose which slots the chars occupy:
    ``spread`` (default, endpoints included) / ``center`` / ``left`` / ``right``.
    """
    placed: list = []
    missing: list[str] = []

    # Pre-load chars for each edge
    edges = shape.edges()
    per_edge_chars: list[list[Character]] = []
    for i in range(len(edges)):
        text = texts_per_edge[i] if i < len(texts_per_edge) else ""
        chars: list[Character] = []
        for ch in text:
            if ch.isspace():
                continue
            c = char_loader(ch)
            if c is None:
                missing.append(ch)
            else:
                chars.append(c)
        per_edge_chars.append(chars)

    size = char_size_mm
    if auto_fit:
        def all_edges_fit(s: float) -> bool:
            for (a, b, L), chars in zip(edges, per_edge_chars):
                if not chars:
                    continue
                slots = edge_positions(a, b, s)
                if len(slots) < len(chars):
                    return False
            return True
        size = _fit_char_size_binary(
            all_edges_fit, requested=char_size_mm, min_size=min_char_size_mm,
        )

    cx = sum(v[0] for v in shape.vertices) / len(shape.vertices)
    cy = sum(v[1] for v in shape.vertices) / len(shape.vertices)

    for i, (a, b, L) in enumerate(edges):
        chars = per_edge_chars[i] if i < len(per_edge_chars) else []
        if not chars:
            continue
        slots = edge_positions(a, b, size)
        if not slots:
            continue
        # Outward angle fix
        sx, sy, ang = slots[0]
        test_x = sx + math.cos(math.radians(ang))
        test_y = sy + math.sin(math.radians(ang))
        d_test = (test_x - cx) ** 2 + (test_y - cy) ** 2
        d_here = (sx - cx) ** 2 + (sy - cy) ** 2
        if d_test < d_here:
            slots = [(x, y, (a2 + 180) % 360) for (x, y, a2) in slots]

        if auto_cycle and len(chars) < len(slots):
            chars = _cycle_chars(chars, len(slots))

        if auto_cycle or len(chars) >= len(slots):
            # Fill slots in order (cycling or exactly-fitting)
            for j, (x, y, ang) in enumerate(slots):
                if j >= len(chars):
                    break
                rot = _rotation_for(orient, ang)
                placed.append((chars[j], x, y, size, rot))
        else:
            # auto_cycle off and chars < slots → apply alignment
            if align == "spread":
                # Phase 5b r3: spread = 「字之間 gap 一致 + 邊首尾各留半 gap」
                # cell-centered 分布。原本 _pick_slot_indices(spread) 會在 chars
                # < slots 時產生不均勻 gap（某 slot 跳過 → 該位置 gap 加倍），
                # 且首尾貼邊 → 多邊形角落字相黏。改成直接以 n_chars 為基準重算
                # 位置：char j 位於邊長分數 (j + 0.5) / n_chars。outward angle
                # 沿用上方 corner-flip 後的 slots[0][2]（邊上所有點同 normal）。
                _, _, ang0 = slots[0]
                positions = _spread_positions_on_edge(a, b, len(chars))
                rot0 = _rotation_for(orient, ang0)
                for j, (x, y) in enumerate(positions):
                    placed.append((chars[j], x, y, size, rot0))
            else:
                indices = _pick_slot_indices(len(chars), len(slots), align)
                for j, slot_idx in enumerate(indices):
                    x, y, ang = slots[slot_idx]
                    rot = _rotation_for(orient, ang)
                    placed.append((chars[j], x, y, size, rot))
    return placed, missing


# ---------------------------------------------------------------------------
# Three-band layout (circle / ellipse: top arc + mid line + bottom arc)
# ---------------------------------------------------------------------------


def _three_band_rotation(orient: BandOrient, outward_deg: float) -> float:
    """Rotation (deg) for an arc glyph given the outward-normal angle."""
    if orient == "top_to_center":
        # Glyph 'up' points toward centroid (inward)
        return (outward_deg - 90.0) % 360
    # bottom_to_center (default) — glyph 'up' points outward
    return (outward_deg - 270.0) % 360


def _three_band_mid_rotation(orient: BandOrient) -> float:
    """Rotation for middle-line glyphs.

    ``bottom_to_center`` = upright (rot 0); ``top_to_center`` = upside-down (rot 180).
    """
    return 180.0 if orient == "top_to_center" else 0.0


def compute_three_band(
    text_top: str, text_mid: str, text_bot: str,
    shape: Shape,
    char_size_mm: float,
    char_loader: CharLoader,
    mid_ratio: float = 0.9,
    *,
    orient_top: BandOrient = "bottom_to_center",
    orient_mid: BandOrient = "bottom_to_center",
    orient_bot: BandOrient = "bottom_to_center",
    auto_cycle: bool = False,
    auto_fit: bool = False,
    min_char_size_mm: float = MIN_CHAR_SIZE_MM,
    align: Align = "spread",
) -> tuple[list, list[str]]:
    """Arrange three texts: top arc, middle horizontal line, bottom arc.

    - Top arc:    traversed 9 o'clock → 12 → 3 (clockwise). Orientation per
                  ``orient_top`` — ``bottom_to_center`` (default) or
                  ``top_to_center``.
    - Bottom arc: traversed 9 o'clock → 6 → 3 (counter-clockwise). Orientation
                  per ``orient_bot``.
    - Middle:     horizontal row. ``orient_mid=bottom_to_center`` = upright;
                  ``orient_mid=top_to_center`` = upside-down (rot 180°). Width =
                  ``shape_x_extent * mid_ratio``.

    Only Circle / Ellipse are supported (polygons have no clean concept of
    "top arc" / "middle line"; use ``linear_groups`` for polygon variants).
    """
    if not isinstance(shape, (Circle, Ellipse)):
        raise ValueError("three_band layout requires Circle or Ellipse")

    placed: list = []
    missing: list[str] = []

    def _load(text: str) -> list[Character]:
        out = []
        for ch in text:
            if ch.isspace():
                continue
            c = char_loader(ch)
            if c is None:
                missing.append(ch)
            else:
                out.append(c)
        return out

    top_chars = _load(text_top)
    mid_chars = _load(text_mid)
    bot_chars = _load(text_bot)

    def _mid_cells(s: float) -> int:
        xmin, ymin, xmax, ymax = shape.bbox()
        cy = (ymin + ymax) / 2
        spans = shape.scanline(cy)
        if not spans:
            return 0
        left, right = spans[0]
        width = (right - left) * mid_ratio
        return int(width / s) if s > 0 else 0

    def _arc_slots(s: float) -> int:
        return int((shape.perimeter() / 2) / s) if s > 0 else 0

    size = char_size_mm
    if auto_fit:
        def all_fit(s: float) -> bool:
            arc = _arc_slots(s)
            mid = _mid_cells(s)
            if top_chars and arc < len(top_chars):
                return False
            if bot_chars and arc < len(bot_chars):
                return False
            if mid_chars and mid < len(mid_chars):
                return False
            return True
        size = _fit_char_size_binary(
            all_fit, requested=char_size_mm, min_size=min_char_size_mm,
        )

    n_half = _arc_slots(size)

    def _arc_char_placements(chars_seq: list, orient: BandOrient,
                             gt_for_local: Callable[[float], float]) -> None:
        """Shared arc-placement helper. Uses _pick_slot_indices unless auto_cycle."""
        if not chars_seq or n_half <= 0:
            return
        seq = chars_seq
        if auto_cycle and len(seq) < n_half:
            seq = _cycle_chars(seq, n_half)
        if auto_cycle or len(seq) >= n_half:
            # Fill slots 0..n_half-1 in order (auto_cycle already filled; or exact fit)
            idxs = list(range(min(n_half, len(seq))))
        else:
            idxs = _pick_slot_indices(len(seq), n_half, align)
        for j, slot_idx in enumerate(idxs):
            local_t = (slot_idx + 0.5) / n_half
            gt = gt_for_local(local_t)
            x, y = shape.point_at(gt)
            outward = shape.tangent_at(gt)
            rot = _three_band_rotation(orient, outward)
            placed.append((seq[j], x, y, size, rot))

    # --- top arc: 9 o'clock → 12 → 3 (clockwise)
    _arc_char_placements(top_chars, orient_top,
                         lambda lt: (0.75 + 0.5 * lt) % 1.0)
    # --- bottom arc: 3 o'clock → 6 → 9 (CCW in global t)
    _arc_char_placements(bot_chars, orient_bot,
                         lambda lt: (0.25 + 0.5 * lt) % 1.0)

    # --- middle line (horizontal row of cells aligned per `align`)
    if mid_chars:
        xmin, ymin, xmax, ymax = shape.bbox()
        cy = (ymin + ymax) / 2
        spans = shape.scanline(cy)
        if spans:
            left, right = spans[0]
            width = (right - left) * mid_ratio
            mid_left = (left + right - width) / 2
            mid_right = mid_left + width
            cells = int((mid_right - mid_left) / size)
            if cells > 0:
                chars = mid_chars
                if auto_cycle and len(chars) < cells:
                    chars = _cycle_chars(chars, cells)
                mid_rot = _three_band_mid_rotation(orient_mid)
                # Cell centers span from (mid_left + size/2) to (mid_right - size/2)
                cell_xs = [mid_left + size / 2 + k * size for k in range(cells)]
                if auto_cycle or len(chars) >= cells:
                    n_place = min(cells, len(chars))
                    for k in range(n_place):
                        placed.append((chars[k], cell_xs[k], cy, size, mid_rot))
                else:
                    indices = _pick_slot_indices(len(chars), cells, align)
                    for j, slot_idx in enumerate(indices):
                        placed.append((chars[j], cell_xs[slot_idx], cy, size,
                                       mid_rot))

    return placed, missing


def three_band_capacity(shape: Shape, char_size_mm: float,
                        mid_ratio: float = 0.9) -> dict:
    """Return {top, mid, bot} capacity for circle/ellipse three-band mode."""
    if not isinstance(shape, (Circle, Ellipse)):
        raise ValueError("three_band layout requires Circle or Ellipse")
    half_per = shape.perimeter() / 2
    n_half = int(half_per / char_size_mm)
    xmin, ymin, xmax, ymax = shape.bbox()
    cy = (ymin + ymax) / 2
    spans = shape.scanline(cy)
    n_mid = 0
    if spans:
        left, right = spans[0]
        n_mid = int((right - left) * mid_ratio / char_size_mm)
    return {"top": n_half, "mid": n_mid, "bot": n_half}


# ---------------------------------------------------------------------------
# Linear variants: edge groups and edge ordering
# ---------------------------------------------------------------------------


def compute_linear_groups(
    texts_per_group: list[str],
    edge_groups: list[list[int]],
    shape: Polygon,
    char_size_mm: float,
    orient: Orientation,
    char_loader: CharLoader,
    *,
    auto_cycle: bool = False,
    auto_fit: bool = False,
    min_char_size_mm: float = MIN_CHAR_SIZE_MM,
    align: Align = "spread",
) -> tuple[list, list[str]]:
    """Like compute_linear but edges can be **merged** into groups.

    ``edge_groups`` is a list of groups; each group is a list of edge
    indices that form one continuous path. A group gets one text string
    from ``texts_per_group`` and the text flows across edge boundaries
    (no char breaks at corners).

    Example: ``edge_groups=[[0,1,2],[3,4,5]]`` on a hexagon creates two
    L-shaped 3-edge paths, each carrying its own text.
    """
    placed: list = []
    missing: list[str] = []
    all_edges = shape.edges()
    n = len(all_edges)
    if n == 0 or not shape.vertices:
        return placed, missing
    cx = sum(v[0] for v in shape.vertices) / len(shape.vertices)
    cy = sum(v[1] for v in shape.vertices) / len(shape.vertices)

    # Pre-load chars per group
    group_chars: list[list[Character]] = []
    for gidx in range(len(edge_groups)):
        text = texts_per_group[gidx] if gidx < len(texts_per_group) else ""
        chars: list[Character] = []
        for ch in text:
            if ch.isspace():
                continue
            c = char_loader(ch)
            if c is None:
                missing.append(ch)
            else:
                chars.append(c)
        group_chars.append(chars)

    def _group_slot_count(s: float, ei_list: list[int]) -> int:
        total = 0
        for ei in ei_list:
            if 0 <= ei < n:
                a, b, _ = all_edges[ei]
                total += len(edge_positions(a, b, s))
        return total

    size = char_size_mm
    if auto_fit:
        def all_groups_fit(s: float) -> bool:
            for ei_list, chars in zip(edge_groups, group_chars):
                if chars and _group_slot_count(s, ei_list) < len(chars):
                    return False
            return True
        size = _fit_char_size_binary(
            all_groups_fit, requested=char_size_mm, min_size=min_char_size_mm,
        )

    for gidx, ei_list in enumerate(edge_groups):
        chars = group_chars[gidx] if gidx < len(group_chars) else []
        if not chars:
            continue

        group_slots: list[tuple[float, float, float]] = []
        for ei in ei_list:
            if ei < 0 or ei >= n:
                continue
            a, b, L = all_edges[ei]
            slots = edge_positions(a, b, size)
            if not slots:
                continue
            sx, sy, ang = slots[0]
            tx = sx + math.cos(math.radians(ang))
            ty = sy + math.sin(math.radians(ang))
            if (tx - cx) ** 2 + (ty - cy) ** 2 < (sx - cx) ** 2 + (sy - cy) ** 2:
                slots = [(x, y, (a2 + 180) % 360) for x, y, a2 in slots]
            group_slots.extend(slots)

        if auto_cycle and len(chars) < len(group_slots):
            chars = _cycle_chars(chars, len(group_slots))

        if auto_cycle or len(chars) >= len(group_slots):
            for j, (x, y, ang) in enumerate(group_slots):
                if j >= len(chars):
                    break
                rot = _rotation_for(orient, ang)
                placed.append((chars[j], x, y, size, rot))
        else:
            indices = _pick_slot_indices(len(chars), len(group_slots), align)
            for j, slot_idx in enumerate(indices):
                x, y, ang = group_slots[slot_idx]
                rot = _rotation_for(orient, ang)
                placed.append((chars[j], x, y, size, rot))

    return placed, missing


def compute_linear_ordered(
    texts_per_edge: list[str],
    shape: Polygon,
    char_size_mm: float,
    orient: Orientation,
    char_loader: CharLoader,
    *,
    edge_start: int = 0,
    edge_direction: Literal["cw", "ccw"] = "cw",
    auto_cycle: bool = False,
    auto_fit: bool = False,
    min_char_size_mm: float = MIN_CHAR_SIZE_MM,
    align: Align = "spread",
) -> tuple[list, list[str]]:
    """Like compute_linear but with a configurable edge traversal order.

    ``texts_per_edge[0]`` goes on edge ``edge_start``; subsequent texts
    follow ``edge_direction``:

    - ``cw``  — natural (increasing) index order
    - ``ccw`` — reversed (decreasing) index order
    """
    n = len(shape.edges())
    if n == 0:
        return [], []
    edge_start = edge_start % n
    if edge_direction == "cw":
        order = [(edge_start + i) % n for i in range(n)]
    else:
        order = [(edge_start - i) % n for i in range(n)]

    remapped = [""] * n
    for i, ei in enumerate(order):
        if i < len(texts_per_edge):
            remapped[ei] = texts_per_edge[i]
    return compute_linear(
        remapped, shape, char_size_mm, orient, char_loader,
        auto_cycle=auto_cycle, auto_fit=auto_fit,
        min_char_size_mm=min_char_size_mm, align=align,
    )


# ---------------------------------------------------------------------------
# Capacity helpers — "minimum N chars" hints for the UI
# ---------------------------------------------------------------------------


def capacity(layout: Layout, shape: Shape, char_size_mm: float) -> dict:
    """Return counts useful for UI hints."""
    info: dict = {
        "layout": layout,
        "char_size_mm": char_size_mm,
        "shape_perimeter_mm": shape.perimeter(),
    }
    if layout == "ring":
        info["min_chars_for_full_ring"] = int(shape.perimeter() // char_size_mm)
    elif layout == "fill":
        slots = fill_positions(shape, char_size_mm)
        info["min_chars_for_full_fill"] = len(slots)
    elif layout == "linear":
        if isinstance(shape, Polygon):
            per_edge = []
            for a, b, L in shape.edges():
                per_edge.append(int(L // char_size_mm))
            info["min_chars_per_edge"] = per_edge
            info["min_chars_for_all_edges"] = sum(per_edge)
    return info


# ---------------------------------------------------------------------------
# SVG rendering
# ---------------------------------------------------------------------------


def _place_char_svg(c: Character, x: float, y: float, size_mm: float,
                    rot: float, color: str = "#222") -> str:
    """Place a character on the wordart canvas.

    Phase 5aj: strokes with either an empty ``outline`` (punctuation,
    text-fallback) OR a non-None ``pen_size`` (any style filter was
    applied) render as stroked polylines so the visual contribution of
    the style filter actually shows. Remaining strokes render as
    outline-filled paths (original g0v/MMH look).

    Phase 5b r26: ``color`` 控制字筆畫的 fill (outline strokes) +
    stroke (track strokes) 顏色，預設 ``#222`` 維持向後相容。
    """
    from .svg import _track_points_str
    half = size_mm / 2
    scale = size_mm / EM_SIZE
    transform = (f'translate({x:.2f},{y:.2f}) rotate({rot:.2f}) '
                 f'translate({-half:.3f},{-half:.3f}) '
                 f'scale({scale:.6f})')
    outline_strokes: list = []
    track_strokes: list = []
    for s in c.strokes:
        if not s.outline or s.pen_size is not None:
            track_strokes.append(s)
        else:
            outline_strokes.append(s)
    parts = [f'<g transform="{transform}">']
    if outline_strokes:
        parts.append(f'<g fill="{color}">' +
                     "".join(f'<path d="{_outline_path_d(s)}"/>'
                             for s in outline_strokes) + "</g>")
    if track_strokes:
        parts.append(f'<g fill="none" stroke="{color}" stroke-linecap="round" '
                     'stroke-linejoin="round">')
        for s in track_strokes:
            w = s.pen_size if s.pen_size is not None else 40.0
            parts.append(
                f'<polyline stroke-width="{w}" '
                f'points="{_track_points_str(s)}"/>'
            )
        parts.append("</g>")
    parts.append("</g>")
    return "".join(parts)


def render_wordart_svg(
    placed: list,
    *,
    page_width_mm: float,
    page_height_mm: float,
    shape: Optional[Shape] = None,
    show_shape_outline: bool = True,
    background: str = "white",
) -> str:
    """Compose a single-page SVG from placed chars (+ optional shape outline)."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {page_width_mm} {page_height_mm}" '
        f'width="{page_width_mm}mm" height="{page_height_mm}mm">'
    ]
    parts.append(f'<rect x="0" y="0" width="{page_width_mm}" '
                 f'height="{page_height_mm}" fill="{background}"/>')
    if show_shape_outline and shape is not None:
        d = shape.svg_path_d()
        if d:
            parts.append(f'<path d="{d}" fill="none" stroke="#bbb" '
                         f'stroke-width="0.3" stroke-dasharray="2 2"/>')
    parts.append('<g class="chars">')
    for (c, x, y, size, rot) in placed:
        parts.append(_place_char_svg(c, x, y, size, rot))
    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------


def wordart_compose(
    shape: Shape,
    char_loader: CharLoader,
    *,
    layout: Layout,
    char_size_mm: float,
    orientation: Orientation = "bottom_to_center",
    text: str = "",
    texts_per_edge: Optional[list[str]] = None,
    page_width_mm: float,
    page_height_mm: float,
    show_shape_outline: bool = True,
) -> tuple[str, dict]:
    """
    High-level: given a shape + text + layout, return (svg_string, info_dict).

    `info_dict` includes capacity metrics and any missing characters.
    """
    info = capacity(layout, shape, char_size_mm)
    if layout == "ring":
        placed, missing = compute_ring(text, shape, char_size_mm, orientation,
                                       char_loader)
    elif layout == "fill":
        placed, missing = compute_fill(text, shape, char_size_mm, char_loader,
                                       orient=orientation)
    elif layout == "linear":
        if not isinstance(shape, Polygon):
            raise ValueError("linear layout requires a polygon shape")
        placed, missing = compute_linear(
            texts_per_edge or [text], shape, char_size_mm, orientation,
            char_loader,
        )
    else:
        raise ValueError(f"unknown layout: {layout}")

    info["placed_count"] = len(placed)
    info["missing_count"] = len(missing)
    info["missing_chars"] = "".join(missing)

    svg = render_wordart_svg(
        placed,
        page_width_mm=page_width_mm,
        page_height_mm=page_height_mm,
        shape=shape,
        show_shape_outline=show_shape_outline,
    )
    return svg, info


__all__ = [
    "Orientation", "Layout",
    "wordart_compose", "render_wordart_svg",
    "compute_ring", "compute_fill", "compute_linear",
    "compute_three_band", "three_band_capacity",
    "compute_linear_groups", "compute_linear_ordered",
    "ring_positions", "fill_positions", "edge_positions",
    "capacity",
]
