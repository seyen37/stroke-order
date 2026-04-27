from stroke_order.ir import Point
from stroke_order.smoothing import smooth_track


def test_smooth_2pt_straight_line():
    pts = [Point(0, 0), Point(1000, 1000)]
    out = smooth_track(pts, samples_per_stroke=11)
    assert len(out) == 11
    # first and last should be exact
    assert out[0].x == 0 and out[0].y == 0
    assert out[-1].x == 1000 and out[-1].y == 1000
    # middle should be linear
    mid = out[5]
    assert abs(mid.x - 500) < 1e-6
    assert abs(mid.y - 500) < 1e-6


def test_smooth_preserves_endpoints():
    pts = [
        Point(100, 100),
        Point(500, 200),
        Point(900, 500),
        Point(1200, 1000),
    ]
    out = smooth_track(pts, samples_per_stroke=50)
    # "samples_per_stroke" is approximate — integer rounding per segment may
    # lose a few. We require the output to be in the same ballpark and to
    # have at least one sample per segment.
    assert len(out) >= 45
    # start/end exactly preserved
    assert abs(out[0].x - 100) < 1e-6 and abs(out[0].y - 100) < 1e-6
    assert abs(out[-1].x - 1200) < 1e-6 and abs(out[-1].y - 1000) < 1e-6


def test_smooth_passes_through_control_points():
    """Every original point should appear in the output (CR interpolates)."""
    pts = [Point(0, 0), Point(100, 50), Point(300, 200), Point(400, 100)]
    out = smooth_track(pts, samples_per_stroke=100)

    for original in pts:
        # check output contains a point close to this original
        nearest = min(out, key=lambda p: abs(p.x - original.x) + abs(p.y - original.y))
        assert abs(nearest.x - original.x) < 0.5
        assert abs(nearest.y - original.y) < 0.5
