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


# ---------------------------------------------------------------------------
# 5br: auto-fit char size / spacing — overlap bug fix
# ---------------------------------------------------------------------------


def test_5br_four_big_chars_do_not_overlap():
    """回報場景：80mm 布章塞 4 個 22mm 字，字心距 12mm < 字寬 → 重疊。"""
    from stroke_order.exporters.patch import (
        _layout_text_positions, _build_patch_shape, _ensure_polygon,
        _CHAR_GAP_RATIO,
    )
    poly = _ensure_polygon(_build_patch_shape("rectangle", 80.0, 40.0))
    positions, eff = _layout_text_positions(
        4, "rectangle", "center", 80.0, 40.0, 22.0, poly)
    assert eff < 22.0                        # 自動縮字
    xs = [x for x, _y, _r in positions]
    for a, b in zip(xs, xs[1:]):
        assert b - a >= eff * _CHAR_GAP_RATIO - 1e-6   # 字心距 ≥ 字寬×gap
    # 全部留在布章內（含半字寬）
    assert xs[0] - eff / 2 >= 0 and xs[-1] + eff / 2 <= 80.0
    # 置中
    assert abs((xs[0] + xs[-1]) / 2 - 40.0) < 1e-6


def test_5br_roomy_layout_unchanged():
    """空間充裕時（2 字 18mm/80mm）維持原本的均勻鋪排位置。"""
    from stroke_order.exporters.patch import (
        _layout_text_positions, _build_patch_shape, _ensure_polygon,
    )
    poly = _ensure_polygon(_build_patch_shape("rectangle", 80.0, 40.0))
    positions, eff = _layout_text_positions(
        2, "rectangle", "center", 80.0, 40.0, 18.0, poly)
    assert eff == 18.0                       # 不縮字
    # 舊公式：margin=9, usable=80-18-18=44, x0=18 → 18, 62
    xs = [x for x, _y, _r in positions]
    assert xs == pytest.approx([18.0, 62.0])


def test_5br_single_char_centered_unchanged():
    from stroke_order.exporters.patch import (
        _layout_text_positions, _build_patch_shape, _ensure_polygon,
    )
    poly = _ensure_polygon(_build_patch_shape("rectangle", 80.0, 40.0))
    positions, _eff = _layout_text_positions(
        1, "rectangle", "center", 80.0, 40.0, 22.0, poly)
    assert positions == [(40.0, 20.0, 0.0)]


def test_5br_on_arc_spacing_clamped():
    from stroke_order.exporters.patch import (
        _layout_text_positions, _build_patch_shape, _ensure_polygon,
        _CHAR_GAP_RATIO,
    )
    poly = _ensure_polygon(_build_patch_shape("arch_top", 80.0, 40.0))
    positions, eff = _layout_text_positions(
        5, "arch_top", "on_arc", 80.0, 40.0, 20.0, poly)
    xs = sorted(x for x, _y, _r in positions)
    for a, b in zip(xs, xs[1:]):
        assert b - a >= eff * _CHAR_GAP_RATIO - 1e-6


# ---------------------------------------------------------------------------
# Phase 5cc — 髮絲線修正：scale transform 下的 stroke-width 補償
# ---------------------------------------------------------------------------

import re


def _glyph_group_widths(svg: str) -> list[tuple[float, float]]:
    """抓出所有「帶 scale transform 的字形群組」的 (scale, stroke_width)。"""
    out = []
    for m in re.finditer(
            r'<g transform="[^"]*scale\(([\d.]+)(?:,[\d.]+)?\)"'
            r' stroke-width="([\d.]+)"', svg):
        out.append((float(m.group(1)), float(m.group(2))))
    return out


def test_5cc_glyph_stroke_width_compensates_scale(stub_loader):
    """內層字形群組 stroke-width × scale ≈ 外層 mm 線寬。

    否則有效線寬 = 0.3 × (22/2048) ≈ 0.003mm 髮絲線 —— cairosvg
    光柵化後直接隱形（瀏覽器靠反鋸齒勉強看得到，假象）。"""
    svg = render_patch_svg("福氣", stub_loader, patch_width_mm=80,
                           patch_height_mm=40, char_size_mm=22,
                           cut_width=0.3, write_width=0.5)
    pairs = _glyph_group_widths(svg)
    # cut 2 字 + write 2 字 = 4 個補償群組
    assert len(pairs) == 4
    effective = sorted(round(s * w, 3) for s, w in pairs)
    assert effective[:2] == [0.3, 0.3]      # cut 層有效線寬
    assert effective[2:] == [0.5, 0.5]      # write 層有效線寬


def test_5cc_no_param_output_has_no_inner_width(stub_loader):
    """不傳 stroke_width_mm 時輸出不變 —— 保護 8 個填色型消費者
    （印章／六張表格頁）零回歸。"""
    from stroke_order.exporters.patch import _char_cut_paths
    frag = _char_cut_paths(stub_loader("福"), 10.0, 10.0, 22.0)
    assert "stroke-width" not in frag


def test_5cc_cairosvg_glyph_actually_visible(stub_loader):
    """E2E：cairosvg 光柵化後字形區必須有暗像素（修正前為 0）。"""
    cairosvg = pytest.importorskip("cairosvg")
    import io
    import numpy as np
    from PIL import Image

    svg = render_patch_svg("福", stub_loader, patch_width_mm=80,
                           patch_height_mm=40, char_size_mm=22)
    png = cairosvg.svg2png(bytestring=svg.encode(), dpi=96,
                           background_color="white")
    img = np.array(Image.open(io.BytesIO(png)).convert("L"))
    H, W = img.shape
    inner = img[int(H * 0.2):int(H * 0.8), int(W * 0.2):int(W * 0.8)]
    dark = int((inner < 128).sum())
    assert dark > 50, f"字形區暗像素僅 {dark} —— 髮絲線退化"
