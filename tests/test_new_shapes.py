"""
Phase 5ah — new wordart shapes.

Covers five new shape kinds:

- ``star``       — N-pointed star (2N vertices)
- ``heart``      — parametric heart (closed polygon)
- ``rounded``    — rounded rectangle
- ``trapezoid``  — isoceles trapezoid with tunable top ratio
- ``arc``        — open partial circle (only ring / linear layouts apply)

And the existing ``show_shape_outline`` toggle for the hide-outline
functionality (exercised through the API).
"""
from __future__ import annotations

import math

import pytest

from stroke_order.shapes import Arc, Polygon, make_shape


# ---------------------------------------------------------------------------
# Polygon factories
# ---------------------------------------------------------------------------


def test_star_has_2n_vertices():
    """5-point star → 10 vertices."""
    s = Polygon.star(0, 0, 50, points=5)
    assert len(s.vertices) == 10


def test_star_alternates_outer_and_inner_radius():
    """Distances from centre alternate between outer and inner radius."""
    outer = 50.0
    inner_ratio = 0.4
    s = Polygon.star(100, 100, outer, points=5, inner_ratio=inner_ratio)
    dists = [math.hypot(x - 100, y - 100) for x, y in s.vertices]
    outers = dists[0::2]
    inners = dists[1::2]
    assert all(abs(d - outer) < 0.01 for d in outers)
    assert all(abs(d - outer * inner_ratio) < 0.01 for d in inners)


def test_star_rejects_too_few_points():
    with pytest.raises(ValueError):
        Polygon.star(0, 0, 10, points=2)


def test_heart_fits_inside_bbox():
    """Heart parametric should fit cleanly inside a size×size square
    centred on the given centre point (±1mm float slop)."""
    size = 100.0
    cx, cy = 0.0, 0.0
    h = Polygon.heart(cx, cy, size)
    xmin, ymin, xmax, ymax = h.bbox()
    assert abs((xmax - xmin) - size) < 1.0 or abs((ymax - ymin) - size) < 1.0
    # Neither dimension exceeds size
    assert (xmax - xmin) <= size + 0.1
    assert (ymax - ymin) <= size + 0.1
    # Bbox centre is near (cx, cy)
    assert abs(((xmax + xmin) / 2) - cx) < 1.0
    assert abs(((ymax + ymin) / 2) - cy) < 1.0


def test_rounded_rect_is_convex_approx():
    """Rounded rect should fit inside its width×height bbox and have
    more than 4 vertices (corner-arc segments)."""
    r = Polygon.rounded_rect(50, 50, 80, 40, corner_radius_mm=10, corner_segments=8)
    assert len(r.vertices) == 4 * (8 + 1)   # 36
    xmin, ymin, xmax, ymax = r.bbox()
    assert abs((xmax - xmin) - 80) < 0.01
    assert abs((ymax - ymin) - 40) < 0.01


def test_rounded_rect_default_corner_radius():
    """Corner radius defaults to 20% of min(width, height)."""
    r = Polygon.rounded_rect(0, 0, 100, 40)   # no explicit radius
    # With 40×100, corner r = 40*0.2 = 8; bbox still 100×40
    xmin, ymin, xmax, ymax = r.bbox()
    assert abs((xmax - xmin) - 100) < 0.01
    assert abs((ymax - ymin) - 40) < 0.01


def test_trapezoid_has_four_vertices_and_narrower_top():
    t = Polygon.trapezoid(0, 0, width_mm=100, height_mm=60, top_ratio=0.5)
    assert len(t.vertices) == 4
    top_y = min(v[1] for v in t.vertices)
    top_pts = [v for v in t.vertices if v[1] == top_y]
    bot_pts = [v for v in t.vertices if v[1] != top_y]
    top_w = max(v[0] for v in top_pts) - min(v[0] for v in top_pts)
    bot_w = max(v[0] for v in bot_pts) - min(v[0] for v in bot_pts)
    assert abs(top_w - 50) < 0.01    # 100 * 0.5
    assert abs(bot_w - 100) < 0.01
    assert top_w < bot_w


def test_trapezoid_inverted_top_wider():
    """top_ratio > 1 inverts the trapezoid."""
    t = Polygon.trapezoid(0, 0, 100, 60, top_ratio=1.5)
    top_y = min(v[1] for v in t.vertices)
    top_w = (max(v[0] for v in t.vertices if v[1] == top_y)
             - min(v[0] for v in t.vertices if v[1] == top_y))
    bot_w = (max(v[0] for v in t.vertices if v[1] != top_y)
             - min(v[0] for v in t.vertices if v[1] != top_y))
    assert top_w > bot_w


# ---------------------------------------------------------------------------
# Arc (open partial circle)
# ---------------------------------------------------------------------------


def test_arc_perimeter_scales_with_extent():
    """Half-circle (180°) perimeter = π·r. Quarter (90°) = π·r/2."""
    half = Arc(0, 0, 50, extent_deg=180)
    quarter = Arc(0, 0, 50, extent_deg=90)
    assert abs(half.perimeter() - math.pi * 50) < 0.01
    assert abs(quarter.perimeter() - math.pi * 25) < 0.01


def test_arc_point_at_walks_along_circle():
    """t=0 lands at start_deg; t=1 lands at start_deg + extent_deg."""
    a = Arc(0, 0, 50, start_deg=180, extent_deg=180)   # 9 o'clock → 3 o'clock (through top)
    p0 = a.point_at(0)
    p1 = a.point_at(1)
    # start_deg 180 is (-50, 0) in xy
    assert abs(p0[0] - (-50)) < 0.01 and abs(p0[1]) < 0.01
    # end (180 + 180 = 360 = 0°) is (50, 0)
    assert abs(p1[0] - 50) < 0.01 and abs(p1[1]) < 0.01


def test_arc_is_not_a_filled_region():
    """Contains/scanline return empty for open arcs — they're paths not areas."""
    a = Arc(0, 0, 50)
    assert a.contains(0, 0) is False
    assert a.scanline(0) == []


def test_arc_svg_path_is_open_not_closed():
    """Arc svg_path_d should be ``M ... A ...`` with NO closing Z."""
    a = Arc(0, 0, 50, start_deg=180, extent_deg=180)
    d = a.svg_path_d()
    assert d.startswith("M ")
    assert " A " in d
    assert not d.rstrip().endswith("Z")


# ---------------------------------------------------------------------------
# make_shape factory
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["star", "heart", "rounded", "trapezoid"])
def test_factory_new_shapes_are_polygons(kind):
    s = make_shape(kind, 100, 100, 80, sides=5, aspect=1.0)
    assert isinstance(s, Polygon)
    assert len(s.vertices) >= 4


def test_factory_arc_returns_arc():
    s = make_shape("arc", 0, 0, 100)
    assert isinstance(s, Arc)
    assert s.radius_mm == 50


def test_factory_rejects_unknown_kind():
    with pytest.raises(ValueError):
        make_shape("blob", 0, 0, 50)


# ---------------------------------------------------------------------------
# Web API
# ---------------------------------------------------------------------------


try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS = True
except ImportError:
    _HAS = False


@pytest.fixture(scope="module")
def client():
    if not _HAS:
        pytest.skip("web deps missing")
    return TestClient(create_app())


@pytest.mark.parametrize(
    "kind",
    ["star", "heart", "rounded", "trapezoid", "arc"],
)
def test_api_wordart_accepts_new_shapes(client, kind):
    """For shapes that support ring (all except arc's contains()), the
    ring layout produces a 200 SVG."""
    r = client.get(
        f"/api/wordart?shape={kind}&layout=ring&text=A&"
        "shape_size_mm=100&char_size_mm=10"
    )
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]


def test_api_wordart_capacity_accepts_new_shapes(client):
    """Capacity endpoint should also accept the new kinds without crashing."""
    for kind in ("star", "heart", "rounded", "trapezoid", "arc"):
        r = client.get(f"/api/wordart/capacity?shape={kind}&layout=ring"
                       "&shape_size_mm=100&char_size_mm=10")
        assert r.status_code == 200, (kind, r.text)


def test_api_wordart_rejects_bad_shape(client):
    r = client.get(
        "/api/wordart?shape=blob&layout=ring&text=A"
    )
    assert r.status_code == 422


def test_api_wordart_show_shape_outline_false_strips_border(client):
    """Hide-outline: show_shape_outline=false removes the dashed outline path."""
    # On a star with show_shape_outline=true, the output has a stroke="#bbb"
    # dashed path (the outline). With show_shape_outline=false, it shouldn't.
    base = "/api/wordart?shape=star&layout=ring&text=ABC&shape_size_mm=120"
    r_on = client.get(base + "&show_shape_outline=true")
    r_off = client.get(base + "&show_shape_outline=false")
    assert r_on.status_code == 200 and r_off.status_code == 200
    assert 'stroke-dasharray="2 2"' in r_on.text
    assert 'stroke-dasharray="2 2"' not in r_off.text


def test_api_wordart_star_sides_controls_points(client):
    """sides=7 on a star → 14 vertices in the outline path."""
    base = "/api/wordart?shape=star&layout=ring&text=A&shape_size_mm=120"
    r5 = client.get(base + "&sides=5")
    r7 = client.get(base + "&sides=7")
    # SVG path for the star polygon will differ between 5 and 7 points
    assert r5.text != r7.text


def test_api_wordart_trapezoid_top_ratio_changes_shape(client):
    """trapezoid_top_ratio tuning must reach the shape factory."""
    base = ("/api/wordart?shape=trapezoid&layout=ring&text=A"
            "&shape_size_mm=120&aspect=0.6")
    r1 = client.get(base + "&trapezoid_top_ratio=0.3")
    r2 = client.get(base + "&trapezoid_top_ratio=0.9")
    assert r1.text != r2.text


def test_api_wordart_arc_extent_changes_output(client):
    """arc_extent_deg tuning must reach the Arc factory."""
    base = ("/api/wordart?shape=arc&layout=ring&text=A&shape_size_mm=120")
    r1 = client.get(base + "&arc_extent_deg=90")
    r2 = client.get(base + "&arc_extent_deg=270")
    assert r1.text != r2.text
