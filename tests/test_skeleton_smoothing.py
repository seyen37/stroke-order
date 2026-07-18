"""5ed 骨架平滑：Chaikin corner-cutting on Zhang-Suen skeleton tracks.

Zhang-Suen thinning yields staircase-jagged pixel polylines (篆書/隸書/宋體/
CNS 描紅骨架). ``chaikin_smooth`` rounds the staircase; endpoints stay put
and ``iters=0`` is a pass-through, so existing behaviour is opt-out.
"""
from __future__ import annotations

import math

from stroke_order.cns_skeleton import (
    chaikin_smooth, outline_to_skeleton_tracks,
)


def _max_turn_deg(pts) -> float:
    """Sharpest interior turn (degrees) along a polyline."""
    m = 0.0
    for i in range(1, len(pts) - 1):
        ax, ay = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
        bx, by = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        na, nb = math.hypot(ax, ay), math.hypot(bx, by)
        if na < 1e-9 or nb < 1e-9:
            continue
        c = max(-1.0, min(1.0, (ax * bx + ay * by) / (na * nb)))
        m = max(m, math.degrees(math.acos(c)))
    return m


_STAIR = [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2),
          (3, 2), (3, 3), (4, 3), (4, 4)]


def test_chaikin_preserves_endpoints():
    sm = chaikin_smooth(_STAIR, 2)
    assert sm[0] == (0.0, 0.0)
    assert sm[-1] == (4.0, 4.0)


def test_chaikin_rounds_sharpest_corner_progressively():
    # a 90° staircase should soften as iterations rise (total winding is
    # conserved but spread over more, gentler corners).
    assert _max_turn_deg(_STAIR) == 90.0
    t1 = _max_turn_deg(chaikin_smooth(_STAIR, 1))
    t2 = _max_turn_deg(chaikin_smooth(_STAIR, 2))
    assert t1 < 60.0
    assert t2 < 35.0
    assert t2 < t1


def test_chaikin_adds_points():
    assert len(chaikin_smooth(_STAIR, 2)) > len(_STAIR)


def test_chaikin_zero_or_negative_iters_is_passthrough():
    assert chaikin_smooth(_STAIR, 0) == _STAIR
    assert chaikin_smooth(_STAIR, -1) == _STAIR


def test_chaikin_short_or_empty_path_noop():
    assert chaikin_smooth([(0, 0), (1, 1)], 3) == [(0, 0), (1, 1)]
    assert chaikin_smooth([], 2) == []


def _L_outline():
    # thin L-shaped bar → skeleton has a corner + thinning staircase
    return [
        {"type": "M", "x": 300, "y": 200},
        {"type": "L", "x": 400, "y": 200},
        {"type": "L", "x": 400, "y": 1700},
        {"type": "L", "x": 1800, "y": 1700},
        {"type": "L", "x": 1800, "y": 1800},
        {"type": "L", "x": 300, "y": 1800},
        {"type": "L", "x": 300, "y": 200},
    ]


def test_outline_skeleton_smoothing_is_opt_out_and_smoother():
    raw = outline_to_skeleton_tracks(_L_outline(), chaikin_iters=0)
    sm = outline_to_skeleton_tracks(_L_outline(), chaikin_iters=2)
    assert raw and sm
    assert len(raw) == len(sm)                       # stroke count unchanged
    assert sum(len(t) for t in sm) > sum(len(t) for t in raw)  # denser
    # never sharper than the raw staircase
    assert (max(_max_turn_deg(t) for t in sm)
            <= max(_max_turn_deg(t) for t in raw) + 1e-6)


def test_outline_skeleton_default_applies_smoothing():
    # default chaikin_iters (2) must differ from the raw jagged path
    default = outline_to_skeleton_tracks(_L_outline())
    raw = outline_to_skeleton_tracks(_L_outline(), chaikin_iters=0)
    assert sum(len(t) for t in default) > sum(len(t) for t in raw)
