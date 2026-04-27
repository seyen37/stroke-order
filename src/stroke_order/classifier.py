"""
Stroke geometric classifier — maps a track polyline to a kind_code ∈ {1..8}.

Classification scheme (1-8), from user's 恩 = 1527823644 reference:

    1 = 豎     (vertical long stroke)
    2 = 橫     (horizontal long stroke)
    3 = 豎點   (short, slanting down-left; 左點)
    4 = 橫點   (short, slanting down-right; 右點 / 短捺)
    5 = 順彎   (clockwise turn: horizontal-then-vertical fold, 橫折)
    6 = 逆彎   (counter-clockwise hook: 臥鉤)
    7 = 撇     (long left-falling diagonal)
    8 = 捺     (long right-falling diagonal)

Inputs are the RAW TRACK POINTS from g0v (sparse 2-7 points per stroke).
This is a best-effort classifier — some characters have ambiguous strokes
whose label depends on structural context (not geometry); those may not
exactly match human-labeled signatures. See classify_character() docstring.
"""
from __future__ import annotations

import math

from .ir import Character, Point, STROKE_KIND_NAMES, Stroke

# Tuning constants (in canonical 2048 em-square units)
SHORT_LENGTH_THRESHOLD = 350.0   # < this → short stroke (candidate for dots)
AXIS_RATIO_THRESHOLD = 0.35      # |perpendicular| / |along| < this → axis-aligned
TURN_ANGLE_THRESHOLD = 45.0      # degrees of direction change to count as a "turn"
HOOK_REVERSE_THRESHOLD = 100.0   # degrees reversed from overall direction → hook


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def _vec(a: Point, b: Point) -> tuple[float, float]:
    return b.x - a.x, b.y - a.y


def _length(v: tuple[float, float]) -> float:
    return math.hypot(v[0], v[1])


def _angle_deg(v: tuple[float, float]) -> float:
    """Angle from +X axis in degrees, Y-down convention (so 90° = pointing down)."""
    return math.degrees(math.atan2(v[1], v[0]))


def _signed_angle_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """
    Signed angle from a to b in degrees, in range (-180, 180].
    Positive = counter-clockwise in math convention (which is clockwise on
    screen since Y is flipped), negative = the opposite.
    """
    if _length(a) == 0 or _length(b) == 0:
        return 0.0
    # normalize
    a_ang = math.atan2(a[1], a[0])
    b_ang = math.atan2(b[1], b[0])
    d = math.degrees(b_ang - a_ang)
    while d > 180:
        d -= 360
    while d <= -180:
        d += 360
    return d


# ---------------------------------------------------------------------------
# hook detection
# ---------------------------------------------------------------------------


def detect_hook(track: list[Point]) -> bool:
    """
    A stroke has a 'hook' (鉤) when the last segment reverses direction relative
    to the overall stroke direction by more than HOOK_REVERSE_THRESHOLD degrees.

    This catches 橫折鉤 endings (like 日's 2nd stroke that curls back up-left)
    but not plain 橫折 (which just turns 90°).
    """
    if len(track) < 3:
        return False

    overall = _vec(track[0], track[-1])
    last_seg = _vec(track[-2], track[-1])
    if _length(overall) < 1e-6 or _length(last_seg) < 1e-6:
        return False

    angle = abs(_signed_angle_between(overall, last_seg))
    return angle > HOOK_REVERSE_THRESHOLD


# ---------------------------------------------------------------------------
# turn detection (for 5/6 curved/folded strokes)
# ---------------------------------------------------------------------------


def _max_turn_angle(track: list[Point],
                    exclude_last: bool = False) -> tuple[float, float]:
    """
    Return (max_abs_turn_deg, max_signed_turn_deg) across the track.
    Used to distinguish 順彎 (single clean turn) from 逆彎 (hook endings).

    If ``exclude_last`` is True, skip the final junction — this isolates
    interior folds from terminal hook reversals, which is how we tell
    橫折鉤 (5; has a fold earlier AND a hook at end) from 臥鉤 (6; smooth
    curve + hook only at end).
    """
    if len(track) < 3:
        return 0.0, 0.0

    max_abs = 0.0
    max_signed = 0.0
    last_junction = len(track) - 3  # index of second-to-last iter in loop below
    for i in range(len(track) - 2):
        if exclude_last and i == last_junction:
            continue
        v1 = _vec(track[i], track[i + 1])
        v2 = _vec(track[i + 1], track[i + 2])
        if _length(v1) < 1e-6 or _length(v2) < 1e-6:
            continue
        signed = _signed_angle_between(v1, v2)
        if abs(signed) > max_abs:
            max_abs = abs(signed)
            max_signed = signed
    return max_abs, max_signed


# ---------------------------------------------------------------------------
# main classifier
# ---------------------------------------------------------------------------


def classify_stroke(stroke: Stroke) -> int:
    """Return a kind_code in {1..8} for this stroke, based on its raw track."""
    track = stroke.raw_track
    if len(track) < 2:
        return 0  # degenerate

    start, end = track[0], track[-1]
    dx, dy = end.x - start.x, end.y - start.y
    length = math.hypot(dx, dy)

    max_turn_abs, _ = _max_turn_angle(track)
    interior_max_turn, _ = _max_turn_angle(track, exclude_last=True)
    has_hook = detect_hook(track)

    # ---- CURVED / FOLDED strokes first (need >= 3 track points) -----------
    if len(track) >= 3 and max_turn_abs > TURN_ANGLE_THRESHOLD:
        # Distinguishing 5 (順彎/橫折) from 6 (逆彎/臥鉤):
        #   Key insight: both can end with a hook (the last junction's
        #   reversal), so `max_turn_abs` alone is not enough. We look at
        #   INTERIOR turns (i.e., max-turn excluding the final junction):
        #     - 5 (橫折) has an INTERIOR fold >= 60° — a real corner in
        #       the body of the stroke (e.g. 日's 2nd stroke: right-then-
        #       sharp-down then maybe a small hook).
        #     - 6 (臥鉤) has NO sharp interior turn; the curve sweeps
        #       gradually and only reverses at the very end (心's bottom,
        #       戈's diagonal-hook).
        if interior_max_turn >= 60.0:
            return 5
        if has_hook:
            return 6
        # fallback: gentle curve with no hook and no interior fold
        # → treat as a gentle fold (5)
        return 5

    # ---- STRAIGHT strokes: short vs long dispatch -------------------------
    if length < SHORT_LENGTH_THRESHOLD:
        # 短筆畫 → 點類
        # 豎點 (3): slants down-left or roughly straight-down but short
        # 橫點 (4): slants down-right or roughly horizontal but short
        if dx < 0:
            return 3  # down-left short → 左點 / 豎點 family
        # dx >= 0 (right or straight-down)
        # If dominant direction is vertical-down (small dx), still treat as
        # horizontal dot in the 橫點/短捺 family.
        return 4

    # ---- LONG strokes → direction-based ----------------------------------
    abs_dx, abs_dy = abs(dx), abs(dy)

    # 豎 (1): vertical-ish, dy > 0 (going down)
    if abs_dx < AXIS_RATIO_THRESHOLD * abs_dy:
        return 1

    # 橫 (2): horizontal-ish
    if abs_dy < AXIS_RATIO_THRESHOLD * abs_dx:
        return 2

    # 撇 (7): diagonal, going down-left
    if dx < 0 and dy > 0:
        return 7

    # 捺 (8): diagonal, going down-right
    if dx > 0 and dy > 0:
        return 8

    # Rare: going upward (dy < 0) — treat as 提/挑 which in our scheme maps
    # back to 2 (approximate horizontal rising stroke)
    return 2


def classify_character(char: Character) -> Character:
    """
    Fill in kind_code, kind_name, and has_hook for every stroke in `char`.
    Mutates and returns the same Character object.

    Caveats
    -------
    This is PURELY GEOMETRIC. Two strokes with identical track geometry but
    different structural meanings (e.g., 恩's stroke 5 being a 捺 vs strokes
    9/10 being dots within 心) will get the same code. The character's
    signature is a useful fingerprint but will not always match a human's
    labeling when multiple valid interpretations exist.
    """
    for s in char.strokes:
        s.kind_code = classify_stroke(s)
        s.kind_name = STROKE_KIND_NAMES.get(s.kind_code, "未分類")
        s.has_hook = detect_hook(s.raw_track)
    return char


__all__ = [
    "classify_stroke",
    "classify_character",
    "detect_hook",
    "SHORT_LENGTH_THRESHOLD",
    "AXIS_RATIO_THRESHOLD",
    "TURN_ANGLE_THRESHOLD",
    "HOOK_REVERSE_THRESHOLD",
]
