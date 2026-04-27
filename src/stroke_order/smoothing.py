"""
Spline smoothing for stroke tracks.

g0v tracks are sparse — typically 2 points for straight strokes, up to 7
for curved ones. For a writing robot to produce a smooth motion, we need
to densify these tracks using spline interpolation.

Default algorithm: Catmull-Rom spline with a tension parameter. This has
several useful properties:

- Passes EXACTLY through every input point (C1 continuous)
- Requires no external control points
- Tension parameter τ ∈ [0, 1] controls "tightness" (0.5 ≈ uniform CR)
- Degrades gracefully for 2-point tracks (straight-line interpolation)

For 2-point tracks, Catmull-Rom has nothing to curve through, so we just
sample the line segment evenly.
"""
from __future__ import annotations

from typing import Optional

from .ir import Character, Point, Stroke


DEFAULT_SAMPLES_PER_STROKE = 30
DEFAULT_TENSION = 0.5  # standard uniform Catmull-Rom


def _cr_segment(
    p0: Point, p1: Point, p2: Point, p3: Point,
    n_samples: int,
    tension: float = DEFAULT_TENSION,
) -> list[Point]:
    """
    Catmull-Rom interpolation over the P1→P2 segment, with P0 and P3 as
    the 'shoulder' control points. Returns `n_samples` points STARTING at
    P1 (exactly), ending just BEFORE P2 (so concatenated segments don't
    duplicate shared endpoints).

    Tension τ (Kochanek–Bartels style) scales the tangent magnitudes:
    τ=1 → standard uniform Catmull-Rom (loose, natural curves)
    τ=0.5 → tighter curves (our default)
    τ=0 → zero tangents; curves flatten toward straight lines
    """
    s = tension  # simpler name inside hot loop
    out: list[Point] = []
    for i in range(n_samples):
        t = i / n_samples
        t2 = t * t
        t3 = t2 * t
        # Cubic Hermite basis with Catmull-Rom tangents:
        #   m1 = s * (P2 - P0)     (tangent at P1)
        #   m2 = s * (P3 - P1)     (tangent at P2)
        #   q(t) = h00(t)*P1 + h10(t)*m1 + h01(t)*P2 + h11(t)*m2
        # where h00,h10,h01,h11 are standard Hermite basis polynomials.
        # This guarantees q(0)=P1, q(1)=P2 for any tension s.
        h00 = 2 * t3 - 3 * t2 + 1
        h10 = t3 - 2 * t2 + t
        h01 = -2 * t3 + 3 * t2
        h11 = t3 - t2
        m1x = s * (p2.x - p0.x)
        m1y = s * (p2.y - p0.y)
        m2x = s * (p3.x - p1.x)
        m2y = s * (p3.y - p1.y)
        x = h00 * p1.x + h10 * m1x + h01 * p2.x + h11 * m2x
        y = h00 * p1.y + h10 * m1y + h01 * p2.y + h11 * m2y
        out.append(Point(x, y))
    return out


def smooth_track(
    track: list[Point],
    samples_per_stroke: int = DEFAULT_SAMPLES_PER_STROKE,
    tension: float = DEFAULT_TENSION,
) -> list[Point]:
    """
    Catmull-Rom densification of a sparse polyline.

    Parameters
    ----------
    track
        Input points (must have ≥ 2).
    samples_per_stroke
        Approximate total output point count. Distributes evenly across
        the N-1 segments.
    tension
        τ ∈ [0, 1]. 0 → equivalent to straight-line interpolation; 0.5 →
        standard uniform Catmull-Rom; 1 → tighter curves.

    Returns
    -------
    List of points. Starts exactly at track[0], ends exactly at track[-1].
    """
    if len(track) < 2:
        raise ValueError("smooth_track needs at least 2 points")
    if samples_per_stroke < len(track):
        # Can't have fewer output points than input points
        samples_per_stroke = len(track)

    # Special case: 2 points — straight line, nothing to spline
    if len(track) == 2:
        p0, p1 = track
        out = []
        for i in range(samples_per_stroke):
            t = i / (samples_per_stroke - 1)
            out.append(Point(p0.x + (p1.x - p0.x) * t, p0.y + (p1.y - p0.y) * t))
        return out

    # ≥ 3 points: proper Catmull-Rom
    # Distribute samples across segments proportional to segment length.
    segments = [(track[i], track[i + 1]) for i in range(len(track) - 1)]
    lengths = [((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5 for a, b in segments]
    total_length = sum(lengths) or 1.0
    # reserve at least 2 samples per segment; distribute rest by length
    per_seg = [max(2, int(samples_per_stroke * L / total_length)) for L in lengths]

    out: list[Point] = []
    for i, (a, b) in enumerate(segments):
        # Construct CR shoulder control points by reflecting endpoints
        # when at boundaries (keeps endpoints pinned).
        p0 = track[i - 1] if i - 1 >= 0 else Point(
            2 * a.x - b.x, 2 * a.y - b.y
        )
        p3 = track[i + 2] if i + 2 < len(track) else Point(
            2 * b.x - a.x, 2 * b.y - a.y
        )
        out.extend(_cr_segment(p0, a, b, p3, per_seg[i], tension))

    # Append the exact final endpoint
    out.append(track[-1])
    return out


def smooth_stroke(
    stroke: Stroke,
    samples_per_stroke: int = DEFAULT_SAMPLES_PER_STROKE,
    tension: float = DEFAULT_TENSION,
) -> Stroke:
    """Populate `stroke.smoothed_track` in place. Returns the same stroke."""
    stroke.smoothed_track = smooth_track(
        stroke.raw_track, samples_per_stroke, tension
    )
    return stroke


def smooth_character(
    char: Character,
    samples_per_stroke: int = DEFAULT_SAMPLES_PER_STROKE,
    tension: float = DEFAULT_TENSION,
) -> Character:
    """Smooth every stroke in the character. Mutates and returns `char`."""
    for s in char.strokes:
        smooth_stroke(s, samples_per_stroke, tension)
    return char


__all__ = [
    "smooth_track",
    "smooth_stroke",
    "smooth_character",
    "DEFAULT_SAMPLES_PER_STROKE",
    "DEFAULT_TENSION",
]
