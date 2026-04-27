"""Phase 5ay — stamp (印章) mode: 5 presets, single-layer SVG, laser G-code."""
from __future__ import annotations

import math

import pytest

from stroke_order.exporters.stamp import (
    SvgDecoration,
    _arc_text_positions,
    _auto_grid_dims,
    _grid_positions_right_to_left,
    _stamp_border_polys,
    render_stamp_gcode,
    render_stamp_svg,
    stamp_capacity,
)
from stroke_order.ir import Character


# ---------------------------------------------------------------------------
# Stub loader (avoids real font dependency for unit tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_loader():
    from stroke_order.ir import Stroke, Point

    def _l(ch):
        return Character(
            char=ch, unicode_hex=f"{ord(ch):04x}", data_source="stub",
            strokes=[Stroke(
                index=0,
                raw_track=[Point(100, 100), Point(1948, 1948)],
                outline=[
                    {"type": "M", "x": 100,  "y": 100},
                    {"type": "L", "x": 1948, "y": 100},
                    {"type": "L", "x": 1948, "y": 1948},
                    {"type": "L", "x": 100,  "y": 1948},
                ],
                kind_code=9, kind_name="其他", has_hook=False,
            )],
        )
    return _l


# ---------------------------------------------------------------------------
# Layout helpers (5ay-1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n,expected", [
    (1, (1, 1)), (2, (2, 1)), (3, (3, 1)),
    (4, (2, 2)),
    (5, (3, 2)), (6, (3, 2)),
    (7, (3, 3)), (8, (3, 3)), (9, (3, 3)),
])
def test_auto_grid_dims_table(n, expected):
    assert _auto_grid_dims(n) == expected


def test_grid_right_to_left_starts_in_right_column():
    """First placed char must sit in the right-most column (high x)."""
    coords = _grid_positions_right_to_left(
        n=4, rows=2, cols=2, inner_w=20, inner_h=20,
        centre_x=10, centre_y=10,
    )
    # Cell width = 10mm; right column centre x = 15mm, left = 5mm.
    assert coords[0][0] == pytest.approx(15.0)
    assert coords[0][1] == pytest.approx(5.0)   # top of right column
    assert coords[1][0] == pytest.approx(15.0)  # still right column
    assert coords[1][1] == pytest.approx(15.0)  # bottom of right column
    assert coords[2][0] == pytest.approx(5.0)   # now left column starts


def test_grid_capped_at_n():
    coords = _grid_positions_right_to_left(
        n=2, rows=3, cols=3, inner_w=30, inner_h=30,
        centre_x=15, centre_y=15,
    )
    assert len(coords) == 2


def test_arc_text_positions_evenly_distributes():
    pts = _arc_text_positions(n=6, ring_radius=10, centre_x=0, centre_y=0,
                              span_deg=240.0, start_deg=-120.0)
    assert len(pts) == 6
    # All points are on the ring (radius 10).
    for x, y, _rot in pts:
        assert math.hypot(x, y) == pytest.approx(10.0, abs=1e-6)


def test_arc_single_char_at_apex():
    pts = _arc_text_positions(n=1, ring_radius=10, centre_x=0, centre_y=0,
                              span_deg=240.0, start_deg=-120.0)
    assert len(pts) == 1
    # Apex is start + span/2 = -120 + 120 = 0° → (10, 0).
    x, y, _ = pts[0]
    assert x == pytest.approx(10.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Borders (5ay-1)
# ---------------------------------------------------------------------------


def test_border_single_returns_one_poly():
    polys = _stamp_border_polys("square_name", 25, 25, double_border=False)
    assert len(polys) == 1


def test_border_double_returns_two_concentric():
    polys = _stamp_border_polys("square_official", 40, 40,
                                double_border=True, double_gap_mm=0.8)
    assert len(polys) == 2


def test_border_round_yields_circle():
    from stroke_order.shapes import Circle
    polys = _stamp_border_polys("round", 40, 40, double_border=False)
    assert isinstance(polys[0], Circle)


def test_border_oval_yields_ellipse():
    from stroke_order.shapes import Ellipse
    polys = _stamp_border_polys("oval", 50, 30, double_border=False)
    assert isinstance(polys[0], Ellipse)


# ---------------------------------------------------------------------------
# render_stamp_svg — single layer
# ---------------------------------------------------------------------------


def test_svg_single_engrave_layer(stub_loader):
    svg = render_stamp_svg("AB", stub_loader, preset="square_name")
    assert 'id="stamp-engrave"' in svg
    # Stamp mode is single-layer — no patch's cut/write split.
    assert 'id="patch-cut"' not in svg


def test_svg_uses_black_color(stub_loader):
    svg = render_stamp_svg("A", stub_loader, preset="square_name")
    assert 'stroke="#000"' in svg


def test_svg_includes_border_when_show_border_true(stub_loader):
    svg = render_stamp_svg("A", stub_loader, preset="square_name",
                           show_border=True)
    assert 'class="stamp-border"' in svg


def test_svg_omits_border_when_show_border_false(stub_loader):
    """Workflow: hide border, post-process in design tool."""
    svg = render_stamp_svg("A", stub_loader, preset="square_name",
                           show_border=False)
    assert 'class="stamp-border"' not in svg
    # But the engrave layer + chars are still there.
    assert 'id="stamp-engrave"' in svg


def test_svg_double_border_emits_two_paths(stub_loader):
    svg = render_stamp_svg("A", stub_loader, preset="square_official",
                           double_border=True)
    assert svg.count('class="stamp-border"') == 2


def test_svg_decorations_embedded(stub_loader):
    deco = SvgDecoration(
        svg_content='<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="3"/></svg>',
        x_mm=5, y_mm=5, w_mm=10, h_mm=10,
    )
    svg = render_stamp_svg("A", stub_loader, preset="square_name",
                           decorations=[deco])
    assert "<circle" in svg


def test_svg_supports_all_5_presets(stub_loader):
    """Every preset in the closed taxonomy must render without error."""
    for preset in ("square_name", "square_official",
                   "round", "oval", "rectangle_title"):
        svg = render_stamp_svg("吉祥如意", stub_loader, preset=preset)  # type: ignore
        assert 'id="stamp-engrave"' in svg, f"{preset} missing engrave layer"


def test_svg_round_preset_with_2plus_chars_has_arc_chars(stub_loader):
    """Round preset arranges (n-1) chars on arc + 1 centre char.

    For n=4, we expect 3 arc chars + 1 centre = 4 total char-path groups
    (in addition to the border)."""
    svg = render_stamp_svg("業務專用", stub_loader, preset="round",
                           stamp_width_mm=40, stamp_height_mm=40,
                           char_size_mm=8)
    # Sanity: render produced output and includes the engrave group.
    assert 'id="stamp-engrave"' in svg
    # With stub glyph being 4 path segments, just confirm <path> count grows
    # with character count vs single-char case.
    one = render_stamp_svg("業", stub_loader, preset="round",
                           stamp_width_mm=40, stamp_height_mm=40,
                           char_size_mm=8)
    assert svg.count("<path ") > one.count("<path ")


# ---------------------------------------------------------------------------
# G-code — laser engraver
# ---------------------------------------------------------------------------


def test_gcode_uses_default_laser_on(stub_loader):
    gc = render_stamp_gcode("A", stub_loader, preset="square_name")
    assert "G21" in gc and "G90" in gc
    assert "M3 S255" in gc      # default laser power
    assert "M5" in gc           # laser_off


def test_gcode_custom_power(stub_loader):
    gc = render_stamp_gcode("A", stub_loader, preset="square_name",
                            laser_power=120)
    assert "M3 S120" in gc
    assert "M3 S255" not in gc


def test_gcode_default_feed_1500(stub_loader):
    gc = render_stamp_gcode("A", stub_loader, preset="square_name")
    # Feed appears in G1 cuts.
    assert "F1500" in gc


def test_gcode_show_border_true_includes_border_path(stub_loader):
    """Border outline should appear before glyph G-code when shown."""
    gc = render_stamp_gcode("A", stub_loader, preset="square_name",
                            show_border=True)
    # Header annotation echoes the flag — and at least one G0 (border move)
    # should precede the chars.
    assert "show_border=True" in gc
    # Border G-code should produce extra G0 moves vs no-border case.
    no_border = render_stamp_gcode("A", stub_loader, preset="square_name",
                                   show_border=False)
    assert gc.count("G0 ") > no_border.count("G0 ")


def test_gcode_show_border_false_omits_border(stub_loader):
    gc = render_stamp_gcode("A", stub_loader, preset="square_name",
                            show_border=False)
    assert "show_border=False" in gc


def test_gcode_decorations_skipped_with_note(stub_loader):
    deco = SvgDecoration(
        svg_content='<svg><path d="M0 0 L10 10"/></svg>',
        x_mm=0, y_mm=0, w_mm=10, h_mm=10,
    )
    gc = render_stamp_gcode("A", stub_loader, preset="square_name",
                            decorations=[deco])
    assert "decoration" in gc.lower()
    assert "skipped" in gc.lower()


# ---------------------------------------------------------------------------
# Capacity
# ---------------------------------------------------------------------------


def test_capacity_square_name_caps_at_4():
    info = stamp_capacity(preset="square_name", stamp_width_mm=25,
                          stamp_height_mm=25, char_size_mm=10)
    assert info["max_chars"] == 4
    assert info["preset"] == "square_name"
    assert len(info["inner_size_mm"]) == 2


def test_capacity_square_official_caps_at_9():
    info = stamp_capacity(preset="square_official", stamp_width_mm=42,
                          stamp_height_mm=42, char_size_mm=12)
    assert info["max_chars"] == 9


def test_capacity_round_scales_with_radius():
    small = stamp_capacity(preset="round", stamp_width_mm=20,
                           stamp_height_mm=20, char_size_mm=6)
    large = stamp_capacity(preset="round", stamp_width_mm=60,
                           stamp_height_mm=60, char_size_mm=6)
    assert large["max_chars"] > small["max_chars"]


def test_capacity_double_border_shrinks_inner():
    no_db = stamp_capacity(preset="square_name", stamp_width_mm=25,
                           stamp_height_mm=25, char_size_mm=10,
                           double_border=False)
    db = stamp_capacity(preset="square_name", stamp_width_mm=25,
                        stamp_height_mm=25, char_size_mm=10,
                        double_border=True, double_gap_mm=2.0)
    # Double-border uses extra gap mm on each side → smaller inner box.
    assert db["inner_size_mm"][0] < no_db["inner_size_mm"][0]


# ---------------------------------------------------------------------------
# Web API
# ---------------------------------------------------------------------------


try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS = True
except ImportError:
    _HAS = False


@pytest.fixture
def client():
    if not _HAS:
        pytest.skip("web deps missing")
    return TestClient(create_app())


def test_api_stamp_capacity(client):
    r = client.get("/api/stamp/capacity?preset=square_name"
                   "&stamp_width_mm=25&stamp_height_mm=25&char_size_mm=10")
    assert r.status_code == 200
    d = r.json()
    assert d["preset"] == "square_name"
    assert d["max_chars"] == 4


def test_api_stamp_get_svg(client):
    r = client.get("/api/stamp?text=吉&preset=square_name"
                   "&stamp_width_mm=25&stamp_height_mm=25&char_size_mm=10")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    body = r.text
    assert 'id="stamp-engrave"' in body
    assert 'class="stamp-border"' in body


def test_api_stamp_get_svg_hidden_border(client):
    r = client.get("/api/stamp?text=吉&preset=square_name&show_border=false")
    assert r.status_code == 200
    body = r.text
    assert 'id="stamp-engrave"' in body
    assert 'class="stamp-border"' not in body


def test_api_stamp_get_gcode(client):
    r = client.get("/api/stamp?text=吉&preset=square_name&format=gcode")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "M3 S255" in r.text
    assert "G21" in r.text


def test_api_stamp_post_with_decorations(client):
    body = {
        "text": "業務",
        "preset": "round",
        "stamp_width_mm": 40, "stamp_height_mm": 40,
        "char_size_mm": 8,
        "decorations": [{
            "svg_content": '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="3"/></svg>',
            "x_mm": 5, "y_mm": 5, "w_mm": 10, "h_mm": 10,
        }],
        "format": "svg",
    }
    r = client.post("/api/stamp", json=body)
    assert r.status_code == 200
    assert "<circle" in r.text


def test_api_stamp_post_double_border(client):
    body = {
        "text": "公司印章",
        "preset": "square_official",
        "stamp_width_mm": 42, "stamp_height_mm": 42,
        "char_size_mm": 12,
        "double_border": True,
        "format": "svg",
    }
    r = client.post("/api/stamp", json=body)
    assert r.status_code == 200
    assert r.text.count('class="stamp-border"') == 2


def test_api_stamp_invalid_preset_rejected(client):
    r = client.get("/api/stamp?preset=octagon&text=A")
    assert r.status_code == 422


def test_api_stamp_invalid_format_rejected(client):
    r = client.get("/api/stamp?preset=square_name&text=A&format=pdf")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Patch's new show_border flag (5ay-4)
# ---------------------------------------------------------------------------


def test_api_patch_show_border_default_true(client):
    r = client.get("/api/patch?text=吉&preset=rectangle&format=svg")
    assert r.status_code == 200
    assert 'class="patch-outline"' in r.text


def test_api_patch_show_border_false_hides_outline(client):
    r = client.get("/api/patch?text=吉&preset=rectangle"
                   "&show_border=false&format=svg")
    assert r.status_code == 200
    assert 'class="patch-outline"' not in r.text


def test_api_patch_show_border_false_in_gcode_omits_outline(client):
    """When border is hidden, the per-tile outline emission disappears.

    Note: the header banner always names "patch outline + char outlines"
    as the cut-layer description; the per-tile comment 'tile (r,c) patch
    outline' is what's actually gated by show_border."""
    r_on = client.get("/api/patch?text=吉&preset=rectangle"
                      "&show_border=true&format=gcode_cut")
    r_off = client.get("/api/patch?text=吉&preset=rectangle"
                       "&show_border=false&format=gcode_cut")
    assert r_on.status_code == 200 and r_off.status_code == 200
    # The per-tile outline marker only appears with the border on.
    assert "tile (0,0) patch outline" in r_on.text
    assert "tile (0,0) patch outline" not in r_off.text
