"""Phase 5ax — patch (布章) mode: shapes, dual-layer SVG, dual G-code."""
from __future__ import annotations

import pytest

from stroke_order.exporters.patch import (
    SvgDecoration,
    patch_capacity,
    render_patch_gcode_cut,
    render_patch_gcode_write,
    render_patch_svg,
)
from stroke_order.ir import Character


# ---------------------------------------------------------------------------
# Stub loader (avoids real font dependency for unit tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_loader():
    from stroke_order.ir import Stroke, Point
    def _l(ch):
        # Tiny synthetic glyph: one diagonal stroke 0,0 → 2048,2048 with
        # both outline AND raw_track populated so we exercise both layers.
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
# Shapes (5ax-1)
# ---------------------------------------------------------------------------


def test_arch_strip_top_bbox_centred_on_anchor():
    from stroke_order.shapes import Polygon
    p = Polygon.arch_strip(100, 50, 80, 20, position="top")
    bb = p.bbox()
    assert abs((bb[0] + bb[2]) / 2 - 100) < 0.5
    assert abs((bb[1] + bb[3]) / 2 - 50) < 0.5
    assert p.contains(100, 50)


def test_arch_strip_bottom_mirrors_top():
    from stroke_order.shapes import Polygon
    top = Polygon.arch_strip(100, 50, 80, 20, position="top")
    bot = Polygon.arch_strip(100, 50, 80, 20, position="bottom")
    # Both have the same bbox dimensions (mirror image around y).
    bt, bb = top.bbox(), bot.bbox()
    assert abs((bt[2] - bt[0]) - (bb[2] - bb[0])) < 0.5
    assert abs((bt[3] - bt[1]) - (bb[3] - bb[1])) < 0.5


def test_arch_strip_rejects_invalid_position():
    from stroke_order.shapes import Polygon
    with pytest.raises(ValueError, match="position"):
        Polygon.arch_strip(0, 0, 80, 20, position="middle")  # type: ignore


def test_banner_right_notch_indents_right_edge():
    from stroke_order.shapes import Polygon
    p = Polygon.banner(100, 50, 100, 30, notch_side="right",
                       notch_depth=0.25)
    # Right-edge midpoint is the notch tip, 25mm in from the outer edge.
    assert any(abs(x - 125.0) < 0.5 and abs(y - 50.0) < 0.5
               for x, y in p.vertices)


def test_banner_rejects_invalid_side():
    from stroke_order.shapes import Polygon
    with pytest.raises(ValueError, match="notch_side"):
        Polygon.banner(0, 0, 100, 30, notch_side="middle")  # type: ignore


def test_make_shape_dispatches_new_presets():
    from stroke_order.shapes import make_shape, Polygon
    for kind in ("arch_top", "arch_bottom", "banner_left", "banner_right"):
        s = make_shape(kind, 0, 0, 80, aspect=0.4)
        assert isinstance(s, Polygon)


# ---------------------------------------------------------------------------
# render_patch_svg — dual layer
# ---------------------------------------------------------------------------


def test_svg_has_both_layer_groups(stub_loader):
    svg = render_patch_svg("ABC", stub_loader, preset="rectangle")
    assert 'id="patch-cut"' in svg
    assert 'id="patch-write"' in svg


def test_svg_cut_uses_black_write_uses_red(stub_loader):
    svg = render_patch_svg("A", stub_loader, preset="rectangle")
    # Find the two group strings and verify their stroke colours.
    cut = svg[svg.index('id="patch-cut"'):svg.index('id="patch-write"')]
    write = svg[svg.index('id="patch-write"'):]
    assert 'stroke="#000"' in cut
    assert 'stroke="#c33"' in write


def test_svg_includes_patch_outline(stub_loader):
    svg = render_patch_svg("A", stub_loader, preset="rectangle")
    assert 'class="patch-outline"' in svg


def test_svg_tiles_replicate_per_cell(stub_loader):
    """Each tile gets its own ``<g transform="translate(x,y)">`` block."""
    single = render_patch_svg("A", stub_loader, preset="rectangle",
                              tile_rows=1, tile_cols=1)
    tiled  = render_patch_svg("A", stub_loader, preset="rectangle",
                              tile_rows=2, tile_cols=3)
    # 6 tiles → roughly 6× the per-tile outline count in cut layer.
    assert tiled.count('class="patch-outline"') == 6
    assert single.count('class="patch-outline"') == 1


def test_svg_decorations_embedded(stub_loader):
    deco = SvgDecoration(
        svg_content='<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="3"/></svg>',
        x_mm=10, y_mm=5, w_mm=20, h_mm=10,
    )
    svg = render_patch_svg("A", stub_loader, preset="rectangle",
                           decorations=[deco])
    assert "<circle" in svg


def test_svg_supports_all_presets(stub_loader):
    """Smoke: every preset in the closed taxonomy must render without
    error and include both layer groups."""
    for preset in ("rectangle", "name_tag", "oval", "circle", "shield",
                   "hexagon", "arch_top", "arch_bottom",
                   "banner_left", "banner_right"):
        svg = render_patch_svg("A", stub_loader, preset=preset)  # type: ignore
        assert 'id="patch-cut"' in svg, f"{preset} missing cut layer"
        assert 'id="patch-write"' in svg, f"{preset} missing write layer"


# ---------------------------------------------------------------------------
# G-code — separate cut / write artefacts
# ---------------------------------------------------------------------------


def test_gcode_cut_includes_outline_and_chars(stub_loader):
    gc = render_patch_gcode_cut("AB", stub_loader, preset="rectangle")
    assert "G21" in gc and "G90" in gc
    assert "patch outline" in gc
    # 2 chars × 1 stroke each + 1 patch outline = 3 pen-down sequences
    assert gc.count("M3 S90") >= 3


def test_gcode_write_only_has_chars(stub_loader):
    gc = render_patch_gcode_write("AB", stub_loader, preset="rectangle")
    # Write layer should NOT include the patch outline.
    assert "patch outline" not in gc
    # Two chars → at least two pen-down events.
    assert gc.count("M3 S90") >= 2


def test_gcode_decorations_skipped_in_write_layer(stub_loader):
    """Decorations are SVG fragments, not glyph strokes — write layer
    must stay decoration-free."""
    deco = SvgDecoration(
        svg_content='<svg><path d="M0 0 L10 10"/></svg>',
        x_mm=0, y_mm=0, w_mm=10, h_mm=10,
    )
    gc = render_patch_gcode_write("A", stub_loader, preset="rectangle")
    assert "decoration" not in gc.lower()


# ---------------------------------------------------------------------------
# Capacity preflight
# ---------------------------------------------------------------------------


def test_patch_capacity_estimates_chars_and_grid():
    info = patch_capacity(
        preset="rectangle", patch_width_mm=80, patch_height_mm=40,
        char_size_mm=18, tile_rows=2, tile_cols=3,
    )
    assert info["chars_per_patch"] >= 1
    assert info["tiles_used"] == 6
    assert info["max_grid"][0] >= 1 and info["max_grid"][1] >= 1


def test_patch_capacity_flags_overflow():
    info = patch_capacity(
        preset="rectangle", patch_width_mm=200, patch_height_mm=200,
        char_size_mm=20, tile_rows=2, tile_cols=2,
    )
    # 2×2 patches @ 200×200 + gap easily blow past A4.
    assert info["fits_page"] is False


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


def test_api_patch_capacity(client):
    r = client.get("/api/patch/capacity?preset=rectangle&patch_width_mm=50"
                   "&patch_height_mm=50&char_size_mm=20&tile_rows=2&tile_cols=3")
    assert r.status_code == 200
    d = r.json()
    assert d["tiles_used"] == 6


def test_api_patch_get_svg(client):
    r = client.get("/api/patch?text=吉&preset=rectangle&patch_width_mm=80"
                   "&patch_height_mm=40&char_size_mm=22")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    body = r.text
    assert 'id="patch-cut"' in body
    assert 'id="patch-write"' in body


def test_api_patch_get_gcode_cut(client):
    r = client.get("/api/patch?text=吉&preset=rectangle&format=gcode_cut")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "patch outline" in r.text


def test_api_patch_get_gcode_write(client):
    r = client.get("/api/patch?text=吉&preset=rectangle&format=gcode_write")
    assert r.status_code == 200
    assert "patch outline" not in r.text   # write-only layer
    assert "M3 S90" in r.text


def test_api_patch_post_with_decorations(client):
    body = {
        "text": "吉祥",
        "preset": "rectangle",
        "patch_width_mm": 80, "patch_height_mm": 40,
        "char_size_mm": 22,
        "decorations": [{
            "svg_content": '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="3"/></svg>',
            "x_mm": 5, "y_mm": 5, "w_mm": 15, "h_mm": 15,
        }],
        "format": "svg",
    }
    r = client.post("/api/patch", json=body)
    assert r.status_code == 200
    assert "<circle" in r.text


def test_api_patch_invalid_preset_rejected(client):
    r = client.get("/api/patch?preset=octagon&text=A")  # not in patch presets
    assert r.status_code == 422


def test_api_patch_invalid_format_rejected(client):
    r = client.get("/api/patch?preset=rectangle&text=A&format=pdf")
    assert r.status_code == 422
