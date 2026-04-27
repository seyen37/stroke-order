"""
詞雲 (WordCloud) mode — sister module to :mod:`wordart`.

Unlike wordart's ring / fill / linear (which place characters uniformly
around or inside a shape), wordcloud places **tokens** (words/phrases)
with **varying sizes**:

* **7 levels** — weights are mapped linearly between ``min_size_mm`` and
  ``max_size_mm``.
* **weight modes**:

  - ``manual``    — explicit ``:weight`` suffix per token (``春:7|夏:3``)
  - ``frequency`` — derive weights from char-occurrence frequency
  - ``random``    — random 1-7 per token

* **collision avoidance** — Archimedean spiral search from the shape's
  centroid with AABB overlap test against already-placed tokens.
  If a token cannot fit, it is shrunk one level at a time; if still no
  fit, it is dropped and reported.

Sub-layouts
-----------

Beyond the default greedy wordcloud, wordcloud mode also exposes
three structured variants:

* **concentric** — N concentric rings (Circle / Ellipse / regular Polygon),
  each ring carrying its own text.
* **gradient_v** — size varies linearly from top to bottom (or reverse).
* **split_lr**   — left and right halves of the shape carry independent texts.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

from ..ir import Character
from ..shapes import Circle, Ellipse, Polygon, Shape
from .wordart import MIN_CHAR_SIZE_MM, _cycle_chars, _fit_char_size_binary


WeightMode = Literal["manual", "frequency", "random"]
GradientDir = Literal["down", "up"]
GradientHDir = Literal["right", "left"]    # Phase 5an: gradient_h direction
RadialDir   = Literal["convex", "concave"] # Phase 5an: radial size gradient

CharLoader = Callable[[str], Optional["Character"]]

N_LEVELS = 7


# ---------------------------------------------------------------------------
# Token parsing & sizing
# ---------------------------------------------------------------------------


@dataclass
class Token:
    """One word / phrase to place as a single horizontal row of glyphs."""
    text: str
    weight: int = 4         # 1 (smallest) .. 7 (largest)
    size_mm: float = 0.0    # filled in later

    @property
    def char_list(self) -> list[str]:
        return [c for c in self.text if not c.isspace()]


def parse_tokens(tokens_str: str, weight_mode: WeightMode = "manual") -> list[Token]:
    """Parse ``春:7|夏:5|秋:3|冬:1`` style input into Token list.

    - Tokens without explicit ``:weight`` get weight 4 (manual / frequency)
      or a random 1..7 (random mode).
    - ``frequency`` mode recomputes weights from char-occurrence counts.
    """
    tokens: list[Token] = []
    for entry in tokens_str.split("|"):
        entry = entry.strip()
        if not entry:
            continue
        # Try trailing :N (N = 1..7)
        weight: Optional[int] = None
        text = entry
        if ":" in entry:
            head, _, tail = entry.rpartition(":")
            try:
                w = int(tail.strip())
                if 1 <= w <= N_LEVELS:
                    weight = w
                    text = head.strip()
            except ValueError:
                pass
        if weight is None:
            weight = 4
        if text:
            tokens.append(Token(text=text, weight=weight))

    if weight_mode == "random":
        for t in tokens:
            t.weight = random.randint(1, N_LEVELS)
    elif weight_mode == "frequency" and tokens:
        # Count char occurrences across all tokens
        freq: Counter = Counter()
        for t in tokens:
            for ch in t.char_list:
                freq[ch] += 1
        if freq:
            max_f = max(freq.values())
            min_f = min(freq.values())
            for t in tokens:
                if not t.char_list:
                    continue
                # token weight = normalized MAX char freq among its chars
                tf = max(freq[ch] for ch in t.char_list)
                if max_f == min_f:
                    norm = 1.0
                else:
                    norm = (tf - min_f) / (max_f - min_f)
                # map [0, 1] → [1, N_LEVELS]
                t.weight = max(1, min(N_LEVELS, round(1 + norm * (N_LEVELS - 1))))
    # manual — leave weights as parsed

    return tokens


def level_to_size(level: int, min_size_mm: float, max_size_mm: float) -> float:
    """Linearly map 1..7 level to ``[min_size_mm, max_size_mm]``."""
    level = max(1, min(N_LEVELS, level))
    if N_LEVELS == 1:
        return max_size_mm
    t = (level - 1) / (N_LEVELS - 1)
    return min_size_mm + (max_size_mm - min_size_mm) * t


def _token_bbox(size_mm: float, n_chars: int,
                padding_mm: float) -> tuple[float, float]:
    """Horizontal row bbox: (width, height)."""
    if n_chars <= 0:
        return (0.0, 0.0)
    return (n_chars * size_mm + 2 * padding_mm,
            size_mm + 2 * padding_mm)


# ---------------------------------------------------------------------------
# Collision / placement helpers
# ---------------------------------------------------------------------------


def _bbox_overlaps(a: tuple[float, float, float, float],
                   b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _bbox_in_shape(bb: tuple[float, float, float, float], shape: Shape) -> bool:
    """All 4 corners + 4 edge midpoints inside shape → bbox considered inside."""
    x1, y1, x2, y2 = bb
    xm = (x1 + x2) / 2
    ym = (y1 + y2) / 2
    test_pts = [
        (x1, y1), (x2, y1), (x1, y2), (x2, y2),
        (xm, y1), (xm, y2), (x1, ym), (x2, ym),
    ]
    return all(shape.contains(px, py) for px, py in test_pts)


def _spiral_positions(cx: float, cy: float, step: float,
                      max_radius: float, max_steps: int = 5000):
    """Yield points on an Archimedean spiral growing outward from (cx, cy)."""
    yield cx, cy  # try centroid first
    a = step / (2 * math.pi)
    theta = step / a  # start one full "step" out
    count = 0
    while count < max_steps:
        r = a * theta
        if r > max_radius:
            return
        yield cx + r * math.cos(theta), cy + r * math.sin(theta)
        theta += step / max(r, step)
        count += 1


def try_place_token(
    size_mm: float, n_chars: int, shape: Shape,
    placed_bboxes: list[tuple[float, float, float, float]],
    padding_mm: float = 1.0,
    max_attempts: int = 2000,
) -> Optional[tuple[float, float]]:
    """Return (center_x, center_y) of a non-colliding placement, or None."""
    w, h = _token_bbox(size_mm, n_chars, padding_mm)
    if w <= 0 or h <= 0:
        return None
    xmin, ymin, xmax, ymax = shape.bbox()
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2
    # Search radius — enough to cover the whole shape
    max_r = math.hypot(xmax - xmin, ymax - ymin)
    step = max(size_mm * 0.35, 1.0)

    attempts = 0
    for px, py in _spiral_positions(cx, cy, step, max_r):
        attempts += 1
        if attempts > max_attempts:
            break
        bb = (px - w / 2, py - h / 2, px + w / 2, py + h / 2)
        if not _bbox_in_shape(bb, shape):
            continue
        if any(_bbox_overlaps(bb, q) for q in placed_bboxes):
            continue
        return (px, py)
    return None


# ---------------------------------------------------------------------------
# WordCloud core
# ---------------------------------------------------------------------------


def compute_wordcloud(
    tokens: list[Token],
    shape: Shape,
    *,
    char_loader: CharLoader,
    min_size_mm: float,
    max_size_mm: float,
    padding_mm: float = 1.0,
    shrink_on_fail: bool = True,
) -> tuple[list, list[str], list[str]]:
    """Place tokens in the shape. Returns ``(placed, missing, dropped)``.

    - ``placed``  — list of ``(Character, x, y, size_mm, rotation_deg)``.
    - ``missing`` — chars not available in the source data.
    - ``dropped`` — tokens that could not fit at any level.

    Placement order: largest weight first.
    If a token fails to fit and ``shrink_on_fail`` is true, the token's
    level is decremented by 1 and retried, down to level 1.
    """
    # Assign sizes
    for t in tokens:
        t.size_mm = level_to_size(t.weight, min_size_mm, max_size_mm)
    # Largest first
    tokens_sorted = sorted(tokens, key=lambda t: -t.weight)

    placed: list = []
    missing: list[str] = []
    dropped: list[str] = []
    placed_bboxes: list[tuple[float, float, float, float]] = []

    for token in tokens_sorted:
        chars: list[Character] = []
        for ch in token.char_list:
            c = char_loader(ch)
            if c is None:
                missing.append(ch)
            else:
                chars.append(c)
        if not chars:
            continue

        # First try at current level, then shrink
        placed_at: Optional[tuple[float, float]] = None
        try_level = token.weight
        while try_level >= 1:
            size = level_to_size(try_level, min_size_mm, max_size_mm)
            pos = try_place_token(size, len(chars), shape, placed_bboxes,
                                  padding_mm=padding_mm)
            if pos is not None:
                token.weight = try_level
                token.size_mm = size
                placed_at = pos
                break
            if not shrink_on_fail:
                break
            try_level -= 1

        if placed_at is None:
            dropped.append(token.text)
            continue

        px, py = placed_at
        sz = token.size_mm
        w, h = _token_bbox(sz, len(chars), padding_mm)
        placed_bboxes.append((px - w / 2, py - h / 2, px + w / 2, py + h / 2))
        # Distribute chars along row, centred on (px, py)
        for i, c in enumerate(chars):
            cx = px - (len(chars) - 1) * sz / 2 + i * sz
            placed.append((c, cx, py, sz, 0.0))

    return placed, missing, dropped


# ---------------------------------------------------------------------------
# Sub-layout: concentric rings
# ---------------------------------------------------------------------------


def compute_concentric(
    texts_per_ring: list[str],
    shape: Shape,
    char_size_mm: float,
    orient,
    char_loader: CharLoader,
    ring_spacing_factor: float = 1.3,
    *,
    auto_cycle: bool = True,  # ring always cycles anyway — kept for signature parity
) -> tuple[list, list[str]]:
    """Build multiple concentric rings (outermost = first text)."""
    # Local import to avoid circular
    from .wordart import compute_ring

    placed: list = []
    missing: list[str] = []

    xmin, ymin, xmax, ymax = shape.bbox()
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2
    step = char_size_mm * ring_spacing_factor

    n_rings = len(texts_per_ring)

    if isinstance(shape, Circle):
        for i in range(n_rings):
            r_i = shape.radius_mm - i * step
            if r_i < char_size_mm * 1.5:
                break
            text = texts_per_ring[i]
            if not text:
                continue
            ring_shape = Circle(cx, cy, r_i)
            p, m = compute_ring(text, ring_shape, char_size_mm, orient,
                                char_loader)
            placed.extend(p)
            missing.extend(m)
    elif isinstance(shape, Ellipse):
        for i in range(n_rings):
            rx_i = shape.rx_mm - i * step
            ry_i = shape.ry_mm - i * step
            if rx_i < char_size_mm * 1.5 or ry_i < char_size_mm * 1.5:
                break
            text = texts_per_ring[i]
            if not text:
                continue
            ring_shape = Ellipse(cx, cy, rx_i, ry_i)
            p, m = compute_ring(text, ring_shape, char_size_mm, orient,
                                char_loader)
            placed.extend(p)
            missing.extend(m)
    elif isinstance(shape, Polygon):
        # Infer "radius" from centroid-to-vertex distance (works for regular polys)
        n = len(shape.vertices)
        r_avg = sum(math.hypot(v[0] - cx, v[1] - cy) for v in shape.vertices) / n
        for i in range(n_rings):
            r_i = r_avg - i * step
            if r_i < char_size_mm * 2.0:
                break
            text = texts_per_ring[i]
            if not text:
                continue
            ring_shape = Polygon.regular(cx, cy, r_i, n)
            p, m = compute_ring(text, ring_shape, char_size_mm, orient,
                                char_loader)
            placed.extend(p)
            missing.extend(m)

    return placed, missing


# ---------------------------------------------------------------------------
# Sub-layout: vertical gradient (size varies with y)
# ---------------------------------------------------------------------------


def compute_gradient_v(
    text: str,
    shape: Shape,
    char_loader: CharLoader,
    *,
    min_size_mm: float,
    max_size_mm: float,
    direction: GradientDir = "down",
    auto_cycle: bool = False,
) -> tuple[list, list[str]]:
    """Fill shape row by row; character size varies vertically.

    - ``direction='down'`` — big at top, small at bottom (default)
    - ``direction='up'``   — small at top, big at bottom
    - ``auto_cycle``       — repeat text to fill all rows if text runs out
    """
    placed: list = []
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

    xmin, ymin, xmax, ymax = shape.bbox()
    total_h = ymax - ymin
    if total_h <= 0:
        return placed, missing

    def _place(chars_source: list[Character]) -> None:
        idx = 0
        y = ymin + (max_size_mm if direction == "down" else min_size_mm) / 2
        while idx < len(chars_source) and y < ymax:
            ratio = (y - ymin) / total_h
            ratio = max(0.0, min(1.0, ratio))
            if direction == "down":
                size = max_size_mm - (max_size_mm - min_size_mm) * ratio
            else:
                size = min_size_mm + (max_size_mm - min_size_mm) * ratio
            if size <= 0:
                break
            for left, right in shape.scanline(y):
                left_in = left + size / 2
                right_in = right - size / 2
                if right_in <= left_in:
                    continue
                usable = right_in - left_in
                cells = int(usable / size) + 1
                row_span = (cells - 1) * size
                x0 = (left_in + right_in - row_span) / 2
                for k in range(cells):
                    if idx >= len(chars_source):
                        break
                    x = x0 + k * size
                    if (shape.contains(x - size / 3, y - size / 3)
                            and shape.contains(x + size / 3, y - size / 3)
                            and shape.contains(x - size / 3, y + size / 3)
                            and shape.contains(x + size / 3, y + size / 3)):
                        placed.append((chars_source[idx], x, y, size, 0.0))
                        idx += 1
                if idx >= len(chars_source):
                    break
            y += size * 1.1

    if auto_cycle:
        # Cycle chars to a generous upper bound (area / min_size²); the _place
        # loop stops naturally when rows run out.
        area_est = int((xmax - xmin) * (ymax - ymin) / (min_size_mm ** 2))
        chars_target = _cycle_chars(chars, max(area_est, len(chars)))
        _place(chars_target)
    else:
        _place(chars)

    return placed, missing


# ---------------------------------------------------------------------------
# Sub-layout: split left / right
# ---------------------------------------------------------------------------


def compute_split_lr(
    text_left: str, text_right: str,
    shape: Shape,
    char_size_mm: float,
    char_loader: CharLoader,
    *,
    auto_cycle: bool = False,
    auto_fit: bool = False,
    min_char_size_mm: float = MIN_CHAR_SIZE_MM,
) -> tuple[list, list[str]]:
    """Place ``text_left`` in left half, ``text_right`` in right half."""
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

    left_chars = _load(text_left)
    right_chars = _load(text_right)
    if not left_chars and not right_chars:
        return placed, missing

    xmin, ymin, xmax, ymax = shape.bbox()
    midx = (xmin + xmax) / 2

    def _split_slots(s: float) -> tuple[list, list]:
        lefts: list = []
        rights: list = []
        y = ymin + s / 2
        while y + s / 2 <= ymax:
            for left, right in shape.scanline(y):
                left_in = left + s / 2
                right_in = right - s / 2
                if right_in <= left_in:
                    continue
                usable = right_in - left_in
                cells = int(usable / s) + 1
                row_span = (cells - 1) * s
                x0 = (left_in + right_in - row_span) / 2
                for k in range(cells):
                    x = x0 + k * s
                    if not (shape.contains(x - s / 3, y - s / 3)
                            and shape.contains(x + s / 3, y + s / 3)):
                        continue
                    if x < midx:
                        lefts.append((x, y))
                    else:
                        rights.append((x, y))
            y += s
        return lefts, rights

    size = char_size_mm
    if auto_fit:
        def both_halves_fit(s: float) -> bool:
            ls, rs = _split_slots(s)
            if left_chars and len(ls) < len(left_chars):
                return False
            if right_chars and len(rs) < len(right_chars):
                return False
            return True
        size = _fit_char_size_binary(
            both_halves_fit, requested=char_size_mm, min_size=min_char_size_mm,
        )

    left_slots, right_slots = _split_slots(size)

    lc = left_chars
    rc = right_chars
    if auto_cycle:
        if lc and len(lc) < len(left_slots):
            lc = _cycle_chars(lc, len(left_slots))
        if rc and len(rc) < len(right_slots):
            rc = _cycle_chars(rc, len(right_slots))

    for (x, y), c in zip(left_slots, lc):
        placed.append((c, x, y, size, 0.0))
    for (x, y), c in zip(right_slots, rc):
        placed.append((c, x, y, size, 0.0))
    return placed, missing


# ---------------------------------------------------------------------------
# Phase 5an — Sub-layout: horizontal size gradient
# ---------------------------------------------------------------------------


def compute_gradient_h(
    text: str,
    shape: Shape,
    char_loader: CharLoader,
    *,
    min_size_mm: float,
    max_size_mm: float,
    direction: GradientHDir = "right",
    auto_cycle: bool = False,
) -> tuple[list, list[str]]:
    """Fill shape column-by-column with a horizontal size gradient.

    - ``direction='right'`` — big at left, small at right
    - ``direction='left'``  — small at left, big at right
    - ``auto_cycle``        — cycle ``text`` to keep filling columns once exhausted

    Mirror of :func:`compute_gradient_v` along the vertical axis. Each
    column's character size is interpolated linearly from
    ``max_size_mm`` to ``min_size_mm`` along the chosen direction.
    """
    placed: list = []
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

    xmin, ymin, xmax, ymax = shape.bbox()
    total_w = xmax - xmin
    if total_w <= 0:
        return placed, missing

    def _place(chars_source: list[Character]) -> None:
        idx = 0
        # Start half a char in so the first column doesn't fall on the edge.
        x = xmin + (max_size_mm if direction == "right" else min_size_mm) / 2
        while idx < len(chars_source) and x < xmax:
            ratio = (x - xmin) / total_w
            ratio = max(0.0, min(1.0, ratio))
            if direction == "right":
                size = max_size_mm - (max_size_mm - min_size_mm) * ratio
            else:
                size = min_size_mm + (max_size_mm - min_size_mm) * ratio
            if size <= 0:
                break
            # Walk the column top-to-bottom in steps of ``size`` and check
            # containment cell-by-cell. Unlike scanline (which is row-major),
            # we use a vertical sweep at this fixed ``x``.
            y = ymin + size / 2
            placed_in_column: list[tuple[float, float, float]] = []
            while y + size / 2 <= ymax and idx < len(chars_source):
                # Test the four interior corners — same containment rule as
                # gradient_v, just rotated 90°.
                if (shape.contains(x - size / 3, y - size / 3)
                        and shape.contains(x + size / 3, y - size / 3)
                        and shape.contains(x - size / 3, y + size / 3)
                        and shape.contains(x + size / 3, y + size / 3)):
                    placed_in_column.append((x, y, size))
                y += size * 1.05
            for cx, cy, csz in placed_in_column:
                if idx >= len(chars_source):
                    break
                placed.append((chars_source[idx], cx, cy, csz, 0.0))
                idx += 1
            x += size * 1.1

    if auto_cycle:
        # Cycle to a generous upper bound; the loop stops when columns end.
        area_est = int((xmax - xmin) * (ymax - ymin) / (min_size_mm ** 2))
        chars_target = _cycle_chars(chars, max(area_est, len(chars)))
        _place(chars_target)
    else:
        _place(chars)

    return placed, missing


# ---------------------------------------------------------------------------
# Phase 5an — Sub-layout: wave (chars along sine curves)
# ---------------------------------------------------------------------------


def compute_wave(
    text: str,
    shape: Shape,
    char_size_mm: float,
    char_loader: CharLoader,
    *,
    amplitude_mm: Optional[float] = None,
    wavelength_mm: Optional[float] = None,
    wave_lines: int = 3,
    tangent_rotation: bool = True,
    auto_cycle: bool = False,
) -> tuple[list, list[str]]:
    """Place characters along ``wave_lines`` parallel sine curves.

    For each baseline ``y_i = ymin + (i + 0.5) * (ymax - ymin) / wave_lines``
    the curve ``y(x) = y_i + A * sin(2π * x / λ)`` is sampled by arc length
    at intervals of ``char_size_mm``. Each sample point receives one
    character; points falling outside the shape are skipped.

    - ``amplitude_mm``  — peak height of the wave (defaults to ``0.8 *
      char_size_mm`` so adjacent waves don't collide).
    - ``wavelength_mm`` — distance between two crests (defaults to
      ``8 * char_size_mm`` — gives ~1 crest per 8 chars).
    - ``wave_lines``    — number of parallel waves (vertical stripes).
    - ``tangent_rotation`` — when True, each char rotates so its baseline
      is tangent to the curve. When False, all chars are upright.
    - ``auto_cycle`` — repeat ``text`` to fill all sample slots; otherwise
      stop when the input is exhausted.

    Returns ``(placed, missing)`` where ``placed = [(char, x, y, size,
    rotation_degrees), ...]``.
    """
    placed: list = []
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

    A = amplitude_mm if amplitude_mm is not None else char_size_mm * 0.8
    L = wavelength_mm if wavelength_mm is not None else char_size_mm * 8.0
    if A < 0 or L <= 0:
        return placed, missing
    if wave_lines < 1:
        return placed, missing

    xmin, ymin, xmax, ymax = shape.bbox()
    band_h = (ymax - ymin) / wave_lines

    # Pre-compute which (x, y, rot) slot positions exist on each baseline.
    # We sample x at fine resolution (char_size_mm / 4) and walk the
    # accumulated arc length, dropping a slot every char_size_mm.
    fine_step = max(char_size_mm / 4.0, 0.5)
    slots: list[tuple[float, float, float]] = []
    for i in range(wave_lines):
        baseline_y = ymin + (i + 0.5) * band_h
        # Pre-step samples for this baseline.
        prev_x, prev_y = xmin, baseline_y + A * math.sin(0.0)
        accum = 0.0
        # First slot at the leftmost edge of the curve.
        slots_for_line: list[tuple[float, float, float]] = []
        if shape.contains(prev_x, prev_y):
            slope = (2 * math.pi * A / L) * math.cos(0.0)
            rot = math.degrees(math.atan(slope)) if tangent_rotation else 0.0
            slots_for_line.append((prev_x, prev_y, rot))
        x = xmin + fine_step
        while x <= xmax:
            phase = 2 * math.pi * (x - xmin) / L
            y = baseline_y + A * math.sin(phase)
            seg = math.hypot(x - prev_x, y - prev_y)
            accum += seg
            if accum >= char_size_mm:
                accum = 0.0
                if shape.contains(x, y):
                    slope = (2 * math.pi * A / L) * math.cos(phase)
                    rot = math.degrees(math.atan(slope)) if tangent_rotation else 0.0
                    slots_for_line.append((x, y, rot))
            prev_x, prev_y = x, y
            x += fine_step
        slots.extend(slots_for_line)

    if not slots:
        return placed, missing

    # Cycle / truncate chars to slot count.
    if auto_cycle and len(chars) < len(slots):
        chars = _cycle_chars(chars, len(slots))

    for i, (x, y, rot) in enumerate(slots):
        if i >= len(chars):
            break
        placed.append((chars[i], x, y, char_size_mm, rot))
    return placed, missing


# ---------------------------------------------------------------------------
# Phase 5an — Sub-layout: radial size gradient (concave / convex)
# ---------------------------------------------------------------------------


def compute_radial_gradient(
    text: str,
    shape: Shape,
    char_loader: CharLoader,
    *,
    min_size_mm: float,
    max_size_mm: float,
    direction: RadialDir = "convex",
    auto_cycle: bool = False,
) -> tuple[list, list[str]]:
    """Fill shape with characters whose size depends on distance from centre.

    - ``direction='convex'``  — big in centre, small at edges (凸)
    - ``direction='concave'`` — small in centre, big at edges (凹)
    - ``auto_cycle``          — repeat text once exhausted

    Algorithm: lay out a coarse grid at ``min_size_mm`` granularity, then
    for each grid point compute the per-cell ``size`` from its radial
    distance to the shape's centroid (normalised against the largest
    centre-to-edge distance). Cells that fail the four-corner containment
    test at their computed size are skipped. Cells overlapping
    already-placed neighbours are also skipped (greedy).
    """
    placed: list = []
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
    if max_size_mm <= 0 or min_size_mm <= 0 or max_size_mm < min_size_mm:
        return placed, missing

    xmin, ymin, xmax, ymax = shape.bbox()
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    # Largest centre-to-corner distance bounds the normalisation.
    r_max = max(math.hypot(xmin - cx, ymin - cy),
                math.hypot(xmax - cx, ymin - cy),
                math.hypot(xmin - cx, ymax - cy),
                math.hypot(xmax - cx, ymax - cy)) or 1.0

    # Grid stepping uses ``min_size_mm`` so the densest packing has room.
    step = max(min_size_mm * 0.9, 1.0)

    # Pre-compute candidate slots with their per-cell sizes.
    candidates: list[tuple[float, float, float]] = []
    y = ymin + min_size_mm / 2
    while y < ymax:
        x = xmin + min_size_mm / 2
        while x < xmax:
            d = math.hypot(x - cx, y - cy)
            ratio = max(0.0, min(1.0, d / r_max))
            if direction == "convex":
                size = max_size_mm - (max_size_mm - min_size_mm) * ratio
            else:  # concave
                size = min_size_mm + (max_size_mm - min_size_mm) * ratio
            # Only keep slots whose four interior corners are inside.
            if (shape.contains(x - size / 3, y - size / 3)
                    and shape.contains(x + size / 3, y - size / 3)
                    and shape.contains(x - size / 3, y + size / 3)
                    and shape.contains(x + size / 3, y + size / 3)):
                candidates.append((x, y, size))
            x += step
        y += step

    if not candidates:
        return placed, missing

    # Sort by descending size — bigger characters claim space first so
    # smaller ones can fit in the gaps without overlap.
    candidates.sort(key=lambda t: -t[2])

    chars_iter = chars
    if auto_cycle:
        chars_iter = _cycle_chars(chars, len(candidates))

    # Greedy AABB collision check against already-placed cells.
    occupied: list[tuple[float, float, float, float]] = []
    char_idx = 0
    for x, y, size in candidates:
        if char_idx >= len(chars_iter):
            break
        bb = (x - size / 2, y - size / 2, x + size / 2, y + size / 2)
        clash = False
        for ob in occupied:
            if not (bb[2] <= ob[0] or bb[0] >= ob[2]
                    or bb[3] <= ob[1] or bb[1] >= ob[3]):
                clash = True
                break
        if clash:
            continue
        placed.append((chars_iter[char_idx], x, y, size, 0.0))
        occupied.append(bb)
        char_idx += 1

    return placed, missing


# ---------------------------------------------------------------------------
# Capacity helpers
# ---------------------------------------------------------------------------


def wordcloud_capacity(
    shape: Shape, min_size_mm: float, max_size_mm: float,
    padding_mm: float = 1.0,
) -> dict:
    """Rough estimate of how many tokens fit if all were level 1 (min size)."""
    xmin, ymin, xmax, ymax = shape.bbox()
    # Estimate by area / (avg_token_area) — very rough.
    # Assume each token = ~2 chars long on average.
    sq = lambda s: s * s
    avg_area = (min_size_mm + max_size_mm) / 2
    approx_tokens = int(((xmax - xmin) * (ymax - ymin)) / (2 * sq(avg_area)))
    return {
        "layout": "wordcloud",
        "approx_max_tokens": max(0, approx_tokens),
        "min_size_mm": min_size_mm,
        "max_size_mm": max_size_mm,
    }


__all__ = [
    "Token", "WeightMode", "GradientDir", "GradientHDir", "RadialDir",
    "N_LEVELS",
    "parse_tokens", "level_to_size",
    "compute_wordcloud", "compute_concentric",
    "compute_gradient_v", "compute_split_lr",
    # Phase 5an
    "compute_gradient_h", "compute_wave", "compute_radial_gradient",
    "try_place_token", "wordcloud_capacity",
]
