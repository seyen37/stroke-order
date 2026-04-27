"""Tests for shape primitives."""
import math

import pytest

from stroke_order.shapes import Circle, Ellipse, Polygon, make_shape


# ----- Circle ---------------------------------------------------------------


def test_circle_perimeter():
    c = Circle(0, 0, 10)
    assert abs(c.perimeter() - 2 * math.pi * 10) < 1e-6


def test_circle_contains():
    c = Circle(100, 100, 50)
    assert c.contains(100, 100)
    assert c.contains(140, 100)
    assert not c.contains(200, 100)


def test_circle_point_at_top():
    c = Circle(100, 100, 50)
    x, y = c.point_at(0)
    # top = (cx, cy-r)
    assert abs(x - 100) < 1e-6
    assert abs(y - 50) < 1e-6


def test_circle_point_at_right():
    c = Circle(100, 100, 50)
    x, y = c.point_at(0.25)
    assert abs(x - 150) < 1e-6
    assert abs(y - 100) < 1e-6


def test_circle_scanline():
    c = Circle(100, 100, 50)
    # at center, full diameter
    spans = c.scanline(100)
    assert len(spans) == 1
    l, r = spans[0]
    assert abs((r - l) - 100) < 1e-6
    # well outside → no spans
    assert c.scanline(200) == []


# ----- Ellipse --------------------------------------------------------------


def test_ellipse_contains():
    e = Ellipse(100, 100, 50, 30)
    assert e.contains(100, 100)
    assert e.contains(145, 100)
    assert not e.contains(145, 125)  # outside the shorter axis


def test_ellipse_bbox():
    e = Ellipse(100, 100, 50, 30)
    assert e.bbox() == (50, 70, 150, 130)


# ----- Polygon --------------------------------------------------------------


def test_polygon_regular_hexagon_edge_count():
    p = Polygon.regular(0, 0, 50, 6)
    assert len(p.edges()) == 6


def test_polygon_regular_equal_edge_lengths():
    p = Polygon.regular(0, 0, 50, 6)
    lens = [L for _, _, L in p.edges()]
    assert max(lens) - min(lens) < 1e-6


def test_polygon_contains_center():
    p = Polygon.regular(100, 100, 50, 6)
    assert p.contains(100, 100)


def test_polygon_doesnt_contain_far_point():
    p = Polygon.regular(100, 100, 50, 6)
    assert not p.contains(300, 300)


def test_polygon_min_sides():
    with pytest.raises(ValueError):
        Polygon.regular(0, 0, 50, 2)


def test_polygon_point_at_cycles():
    p = Polygon.regular(0, 0, 50, 4)  # square
    x0, y0 = p.point_at(0.0)
    x1, y1 = p.point_at(1.0)
    assert abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6


def test_polygon_scanline_produces_spans():
    p = Polygon.regular(100, 100, 50, 6)
    spans = p.scanline(100)
    assert len(spans) == 1
    l, r = spans[0]
    assert r > l


# ----- Factory --------------------------------------------------------------


@pytest.mark.parametrize("kind,expected_type", [
    ("circle", Circle),
    ("ellipse", Ellipse),
    ("triangle", Polygon),
    ("hexagon", Polygon),
    ("octagon", Polygon),
])
def test_make_shape_kinds(kind, expected_type):
    s = make_shape(kind, 0, 0, 100)
    assert isinstance(s, expected_type)


def test_make_shape_polygon_with_sides():
    s = make_shape("polygon", 0, 0, 100, sides=7)
    assert isinstance(s, Polygon)
    assert len(s.vertices) == 7


def test_make_shape_unknown_raises():
    with pytest.raises(ValueError):
        make_shape("zigzag", 0, 0, 100)  # type: ignore


# ----- Phase 5as: cone + capsule ------------------------------------------


def test_cone_default_is_isoceles_trapezoid():
    """Default cone (taper=0.5, invert=False) has wide top, narrow bottom,
    and is symmetric about x=cx."""
    p = Polygon.cone(100, 100, 80, 80)
    assert len(p.vertices) == 4
    # Top corners equidistant from cx
    tl, tr, br, bl = p.vertices
    assert abs((100 - tl[0]) - (tr[0] - 100)) < 1e-6
    assert abs((100 - bl[0]) - (br[0] - 100)) < 1e-6
    # Top wider than bottom (default invert=False)
    top_w = tr[0] - tl[0]
    bot_w = br[0] - bl[0]
    assert top_w > bot_w
    # Bottom width = top × taper
    assert abs(bot_w - top_w * 0.5) < 1e-6


def test_cone_invert_swaps_top_and_bottom():
    p = Polygon.cone(100, 100, 80, 80, taper=0.3, invert=True)
    tl, tr, br, bl = p.vertices
    top_w = tr[0] - tl[0]
    bot_w = br[0] - bl[0]
    # Inverted: bottom wider than top
    assert bot_w > top_w


def test_cone_taper_clamped_to_safe_range():
    """taper outside (0.05, 1.0) should clamp, not crash."""
    p_low = Polygon.cone(0, 0, 80, 80, taper=-1)
    p_hi = Polygon.cone(0, 0, 80, 80, taper=99)
    assert len(p_low.vertices) == 4
    assert len(p_hi.vertices) == 4


def test_cone_rejects_bad_dimensions():
    with pytest.raises(ValueError):
        Polygon.cone(0, 0, 0, 80)


def test_capsule_horizontal_default_orientation():
    p = Polygon.capsule(100, 100, 200, 80)
    # 16 segments * 2 caps + 1 closing vertex per cap = 34
    assert len(p.vertices) == 34
    bb = p.bbox()
    # Horizontal: bbox width > height.
    assert bb[2] - bb[0] > bb[3] - bb[1]


def test_capsule_vertical_orientation():
    p = Polygon.capsule(100, 100, 80, 200, orientation="vertical")
    bb = p.bbox()
    # Vertical: bbox height > width.
    assert bb[3] - bb[1] > bb[2] - bb[0]


def test_capsule_centre_inside_corners_outside():
    """Smoke test capsule containment is sane."""
    p = Polygon.capsule(100, 100, 200, 60)
    assert p.contains(100, 100)
    # Far corner of bounding box is outside (capsule bulges only mid-way).
    bb = p.bbox()
    assert not p.contains(bb[0] - 5, bb[1] - 5)


def test_capsule_rejects_bad_orientation():
    with pytest.raises(ValueError, match="orientation"):
        Polygon.capsule(0, 0, 100, 50, orientation="diagonal")  # type: ignore


def test_capsule_rejects_too_few_arc_segments():
    with pytest.raises(ValueError):
        Polygon.capsule(0, 0, 100, 50, arc_segments=2)


def test_make_shape_cone_passes_taper():
    """make_shape forwards cone_taper / cone_invert correctly."""
    s = make_shape("cone", 0, 0, 100, aspect=1.5,
                   cone_taper=0.2, cone_invert=True)
    assert isinstance(s, Polygon)
    # Width (size_mm) and height (size_mm * aspect) match params.
    bb = s.bbox()
    assert bb[3] - bb[1] == pytest.approx(150)   # height = 100 * 1.5


def test_make_shape_capsule_orientation():
    s_h = make_shape("capsule", 0, 0, 200, aspect=0.4,
                     capsule_orientation="horizontal")
    s_v = make_shape("capsule", 0, 0, 80, aspect=2.5,
                     capsule_orientation="vertical")
    assert isinstance(s_h, Polygon) and isinstance(s_v, Polygon)
    assert s_h.bbox()[2] - s_h.bbox()[0] > s_h.bbox()[3] - s_h.bbox()[1]
    assert s_v.bbox()[3] - s_v.bbox()[1] > s_v.bbox()[2] - s_v.bbox()[0]
