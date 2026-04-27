"""
Phase 5ae — 200-字 manuscript preset (20 rows × 10 columns).

Companion to test_manuscript.py (which covers the 300-字 default). Verifies
preset routing, layout derivation, end-to-end flow placement, and that the
SVG/G-code/JSON outputs reflect the 200 preset instead of the default.
"""
from __future__ import annotations

import json as _json
import re

import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.manuscript import (
    MANUSCRIPT_PRESETS,
    build_manuscript_layout, flow_manuscript,
    render_manuscript_gcode, render_manuscript_json,
    render_manuscript_page_svg,
)
from stroke_order.smoothing import smooth_character


@pytest.fixture
def loader(source):
    def _loader(ch):
        try:
            c = source.get_character(ch)
            classify_character(c)
            smooth_character(c)
            return c
        except Exception:
            return None
    return _loader


# ---------------------------------------------------------------------------
# Preset registry sanity
# ---------------------------------------------------------------------------


def test_presets_registry_contains_both_sizes():
    assert "300" in MANUSCRIPT_PRESETS
    assert "200" in MANUSCRIPT_PRESETS
    assert MANUSCRIPT_PRESETS["200"] == {"rows": 20, "cols": 10, "capacity": 200}


def test_build_layout_rejects_unknown_preset():
    with pytest.raises(ValueError):
        build_manuscript_layout(preset="400")


# ---------------------------------------------------------------------------
# Layout arithmetic for 200 preset
# ---------------------------------------------------------------------------


def test_200_layout_has_bigger_cells_than_300():
    """With default margins, 200-字 cells should be ~20% wider and ~25% taller."""
    layout_200 = build_manuscript_layout(preset="200")
    layout_300 = build_manuscript_layout(preset="300")
    # pair_w 200 = 180/10 = 18 vs pair_w 300 = 15 → 200 cells wider
    # zhuyin default = pair_w/3 → zhuyin_200 = 6, char_200 = 12
    assert abs(layout_200.char_width_mm - 12.0) < 0.01
    assert abs(layout_200.line_spacing_mm - 6.0) < 0.01
    assert layout_200.char_width_mm > layout_300.char_width_mm
    # cell_h 200 = 267/20 = 13.35 vs cell_h 300 = 10.68
    assert abs(layout_200.line_height_mm - 13.35) < 0.01
    assert layout_200.line_height_mm > layout_300.line_height_mm


def test_200_layout_inflated_margin_right():
    """margin_right_mm should be user_margin + zhuyin_w (= 15 + 6 = 21)."""
    layout = build_manuscript_layout(preset="200")
    assert abs(layout.margin_right_mm - 21.0) < 0.01


# ---------------------------------------------------------------------------
# Flow placement — char positions match the 200 grid
# ---------------------------------------------------------------------------


def test_200_first_char_at_top_right_char_cell(loader):
    """First char of 200-字 should sit at x = page_w - user_margin_right - pair_w
    = 210 - 15 - 18 = 177; y = margin_top = 15."""
    pages = flow_manuscript("永一日", loader, preset="200")
    pc = pages[0].chars[0]
    assert abs(pc.x_mm - 177.0) < 0.01
    assert abs(pc.y_mm - 15.0) < 0.01
    assert abs(pc.width_mm - 12.0) < 0.01
    assert abs(pc.height_mm - 13.35) < 0.01


def test_200_col_wraps_after_20_chars(loader):
    """Row 20 overflows; char #20 (0-indexed) starts col 1 at y=15."""
    pages = flow_manuscript("永" * 25, loader, preset="200")
    c0 = pages[0].chars[0]
    c20 = pages[0].chars[20]
    # col step = pair_w = 18
    assert abs((c0.x_mm - c20.x_mm) - 18.0) < 0.01
    assert abs(c20.y_mm - 15.0) < 0.01


def test_200_fills_exactly_one_page(loader):
    pages = flow_manuscript("一" * 200, loader, preset="200")
    assert len(pages) == 1
    assert len(pages[0].chars) == 200


def test_201_chars_spill_to_page_2(loader):
    pages = flow_manuscript("一" * 201, loader, preset="200")
    assert len(pages) == 2
    assert len(pages[0].chars) == 200
    assert len(pages[1].chars) == 1


# ---------------------------------------------------------------------------
# SVG grid — 20 × 10 cells
# ---------------------------------------------------------------------------


def test_200_svg_has_20x10_char_plus_zhuyin_boxes(loader):
    pages = flow_manuscript("永", loader, preset="200")
    svg = render_manuscript_page_svg(pages[0])
    m = re.search(
        r'<g class="manuscript-grid"[^>]*>(.*?)</g>',
        svg, re.DOTALL,
    )
    assert m is not None
    grid_body = m.group(1)
    rect_count = len(re.findall(r'<rect\b', grid_body))
    # 20 * 10 = 200 char rects + 200 zhuyin rects
    assert rect_count == 200 + 200


# ---------------------------------------------------------------------------
# G-code / JSON reflect the chosen preset
# ---------------------------------------------------------------------------


def test_200_gcode_header_shows_20x10(loader):
    pages = flow_manuscript("永一", loader, preset="200")
    gc = render_manuscript_gcode(pages)
    assert "20×10=200" in gc


def test_200_json_metadata(loader):
    pages = flow_manuscript("永一", loader, preset="200")
    data = _json.loads(render_manuscript_json(pages))
    meta = data["manuscript"]
    assert meta["rows"] == 20
    assert meta["cols"] == 10
    assert meta["chars_per_page"] == 200


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


def test_api_manuscript_capacity_preset_200(client):
    r = client.get("/api/manuscript/capacity?preset=200")
    assert r.status_code == 200
    d = r.json()
    assert d["preset"] == "200"
    assert d["rows"] == 20
    assert d["cols"] == 10
    assert d["chars_per_page"] == 200
    # Default margins → char_w = 12, zhuyin_w = 6
    assert abs(d["char_width_mm"] - 12.0) < 0.01
    assert abs(d["zhuyin_width_mm"] - 6.0) < 0.01


def test_api_manuscript_capacity_preset_200_pages_estimation(client):
    r = client.get("/api/manuscript/capacity?preset=200&text=" + "一" * 450)
    d = r.json()
    # 450 / 200 = 2.25 → 3 pages
    assert d["pages_estimated"] == 3


def test_api_manuscript_preset_200_returns_svg(client):
    r = client.get("/api/manuscript?text=永一日&preset=200")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]


def test_api_manuscript_preset_switches_capacity_header(client):
    r1 = client.get("/api/manuscript?text=永&preset=300")
    r2 = client.get("/api/manuscript?text=永&preset=200")
    assert r1.headers["x-capacity-per-page"] == "300"
    assert r2.headers["x-capacity-per-page"] == "200"


def test_api_manuscript_preset_bad_value_rejected(client):
    r = client.get("/api/manuscript?text=永&preset=400")
    assert r.status_code == 422


def test_api_manuscript_preset_default_is_300(client):
    """Back-compat: no preset param → 300-字 behaviour (25×12)."""
    r = client.get("/api/manuscript/capacity")
    d = r.json()
    assert d["preset"] == "300"
    assert d["chars_per_page"] == 300


def test_api_manuscript_200_json_format(client):
    r = client.get("/api/manuscript?text=永&preset=200&format=json")
    assert r.status_code == 200
    data = r.json()
    assert data["manuscript"]["rows"] == 20
    assert data["manuscript"]["cols"] == 10


def test_api_manuscript_200_gcode_format(client):
    r = client.get(
        "/api/manuscript?text=永&preset=200&cell_style=outline&format=gcode")
    assert r.status_code == 200
    assert "20×10=200" in r.text
