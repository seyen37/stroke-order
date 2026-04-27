"""
Phase 5ad — 稿紙模式 (manuscript) tests.

Covers the exporter's layout math + vertical char placement + grid rendering,
plus the web API for SVG / G-code / JSON and capacity preflight.

Fixed spec: A4, 25 rows × 12 columns = 300 chars, vertical (right-to-left),
zhuyin cell sits to the RIGHT of each character cell.
"""
from __future__ import annotations

import json as _json
import re

import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.manuscript import (
    MANUSCRIPT_CAPACITY, MANUSCRIPT_COLS, MANUSCRIPT_ROWS,
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
# Layout arithmetic
# ---------------------------------------------------------------------------


def test_layout_fixed_a4_grid_defaults():
    layout = build_manuscript_layout()
    # A4
    assert layout.size.width_mm == 210
    assert layout.size.height_mm == 297
    # direction
    assert layout.direction == "vertical"
    assert layout.grid_style == "none"   # we draw our own
    # content area with default 15mm margins → pair_w = 180/12 = 15
    # default zhuyin fraction = 1/3 → zhuyin_w = 5, char_w = 10
    assert abs(layout.char_width_mm - 10.0) < 0.01
    assert abs(layout.line_spacing_mm - 5.0) < 0.01   # zhuyin_w
    # row height = 267/25 = 10.68
    assert abs(layout.line_height_mm - 10.68) < 0.01
    # margin_right is inflated by zhuyin_w so flow math lands at char band edge
    assert abs(layout.margin_right_mm - (15 + 5)) < 0.01


def test_layout_honours_custom_margins():
    layout = build_manuscript_layout(
        margin_top_mm=20, margin_bottom_mm=10,
        margin_left_mm=18, margin_right_mm=12,
    )
    # content_w = 210 - 18 - 12 = 180 → pair_w = 15 (unchanged)
    assert abs(layout.char_width_mm - 10.0) < 0.01
    # content_h = 297 - 30 = 267 → cell_h = 10.68 (unchanged)
    assert abs(layout.line_height_mm - 10.68) < 0.01


def test_layout_honours_zhuyin_width_override():
    layout = build_manuscript_layout(zhuyin_width_mm=3)
    # pair_w = 15; zhuyin=3 → char=12
    assert abs(layout.char_width_mm - 12.0) < 0.01
    assert abs(layout.line_spacing_mm - 3.0) < 0.01


def test_layout_rejects_impossible_margins():
    with pytest.raises(ValueError):
        build_manuscript_layout(margin_left_mm=150, margin_right_mm=100)


# ---------------------------------------------------------------------------
# Flow placement — chars land in the right cells
# ---------------------------------------------------------------------------


def test_first_char_at_top_right_char_cell(loader):
    """Default margins → first char's top-left at (180, 15)."""
    pages = flow_manuscript("永一日", loader)
    pc = pages[0].chars[0]
    # first char cell: x=180, y=15, w=10, h=10.68
    assert abs(pc.x_mm - 180.0) < 0.01
    assert abs(pc.y_mm - 15.0) < 0.01
    assert abs(pc.width_mm - 10.0) < 0.01
    assert abs(pc.height_mm - 10.68) < 0.01


def test_second_char_below_first_same_column(loader):
    pages = flow_manuscript("永一日", loader)
    c0, c1 = pages[0].chars[0], pages[0].chars[1]
    # same x (same column), y steps by cell_h (no gap between rows)
    assert abs(c1.x_mm - c0.x_mm) < 0.01
    assert abs((c1.y_mm - c0.y_mm) - 10.68) < 0.01


def test_col_wraps_after_25_chars(loader):
    """After 25 chars in col 0, char #26 goes to col 1 (shifted left by pair_w=15)."""
    text = "永" * 30
    pages = flow_manuscript(text, loader)
    c0 = pages[0].chars[0]
    c25 = pages[0].chars[25]
    # col 1 is to the LEFT of col 0 by exactly pair_w = 15
    assert abs((c0.x_mm - c25.x_mm) - 15.0) < 0.01
    # char 25 back at top (y = content_top = 15)
    assert abs(c25.y_mm - 15.0) < 0.01


def test_300_chars_fit_on_one_page(loader):
    text = "一" * 300
    pages = flow_manuscript(text, loader)
    assert len(pages) == 1
    assert len(pages[0].chars) == 300


def test_301_chars_spill_to_page_2(loader):
    text = "一" * 301
    pages = flow_manuscript(text, loader)
    assert len(pages) == 2
    assert len(pages[0].chars) == 300
    assert len(pages[1].chars) == 1
    # Page 2's first char restarts at top-right char cell
    pc = pages[1].chars[0]
    assert abs(pc.x_mm - 180.0) < 0.01
    assert abs(pc.y_mm - 15.0) < 0.01


# ---------------------------------------------------------------------------
# SVG grid rendering
# ---------------------------------------------------------------------------


def test_svg_has_25x12_char_boxes_plus_zhuyin_boxes(loader):
    """Grid should draw 25*12 = 300 char rects + 25*12 = 300 zhuyin rects."""
    pages = flow_manuscript("永", loader)
    svg = render_manuscript_page_svg(pages[0])
    # Count rects inside the manuscript-grid group.
    m = re.search(
        r'<g class="manuscript-grid"[^>]*>(.*?)</g>',
        svg, re.DOTALL,
    )
    assert m is not None, "manuscript-grid group not found"
    grid_body = m.group(1)
    rect_count = len(re.findall(r'<rect\b', grid_body))
    assert rect_count == 300 + 300   # char + zhuyin


def test_svg_grid_beneath_chars(loader):
    """For correct z-order, grid must appear BEFORE <g class="chars">."""
    pages = flow_manuscript("永", loader)
    svg = render_manuscript_page_svg(pages[0])
    grid_idx = svg.find('class="manuscript-grid"')
    chars_idx = svg.find('<g class="chars">')
    assert grid_idx != -1 and chars_idx != -1
    assert grid_idx < chars_idx


# ---------------------------------------------------------------------------
# G-code / JSON wrappers
# ---------------------------------------------------------------------------


def test_gcode_identifies_as_manuscript(loader):
    pages = flow_manuscript("永一", loader)
    gc = render_manuscript_gcode(pages, cell_style="outline")
    assert "stroke-order 稿紙 G-code" in gc
    assert "stroke-order 筆記 G-code" not in gc


def test_json_top_level_key_and_grid_meta(loader):
    pages = flow_manuscript("永一", loader)
    data = _json.loads(render_manuscript_json(pages, cell_style="outline"))
    assert "manuscript" in data
    assert "notebook" not in data
    meta = data["manuscript"]
    assert meta["rows"] == MANUSCRIPT_ROWS
    assert meta["cols"] == MANUSCRIPT_COLS
    assert meta["chars_per_page"] == MANUSCRIPT_CAPACITY


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


def test_api_manuscript_capacity_defaults(client):
    r = client.get("/api/manuscript/capacity?text=" + "一" * 100)
    assert r.status_code == 200
    d = r.json()
    assert d["rows"] == 25
    assert d["cols"] == 12
    assert d["chars_per_page"] == 300
    assert abs(d["char_width_mm"] - 10.0) < 0.01
    assert abs(d["zhuyin_width_mm"] - 5.0) < 0.01
    assert d["total_chars"] == 100
    assert d["pages_estimated"] == 1


def test_api_manuscript_capacity_estimates_pages(client):
    r = client.get("/api/manuscript/capacity?text=" + "一" * 450)
    d = r.json()
    assert d["pages_estimated"] == 2


def test_api_manuscript_capacity_right_margin_excludes_zhuyin(client):
    """API should report USER-VISIBLE right margin, not the inflated one."""
    r = client.get("/api/manuscript/capacity?margin_right_mm=12")
    d = r.json()
    assert abs(d["margin_mm"]["right"] - 12.0) < 0.01


def test_api_manuscript_capacity_rejects_impossible_margins(client):
    r = client.get(
        "/api/manuscript/capacity?margin_left_mm=150&margin_right_mm=100")
    assert r.status_code == 422


def test_api_manuscript_svg_returns_image(client):
    r = client.get("/api/manuscript?text=永一日")
    assert r.status_code == 200
    ct = r.headers["content-type"]
    assert "image/svg+xml" in ct or "application/zip" in ct


def test_api_manuscript_format_gcode(client):
    r = client.get("/api/manuscript?text=永一&cell_style=outline&format=gcode")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "stroke-order 稿紙 G-code" in r.text


def test_api_manuscript_format_json(client):
    r = client.get("/api/manuscript?text=永一&format=json")
    assert r.status_code == 200
    data = r.json()
    assert data["manuscript"]["chars_per_page"] == 300


def test_api_manuscript_format_download_disposition(client):
    r = client.get(
        "/api/manuscript?text=永&format=gcode&download=true")
    cd = r.headers.get("content-disposition", "")
    assert "manuscript" in cd and ".gcode" in cd

    r2 = client.get(
        "/api/manuscript?text=永&format=json&download=true")
    cd2 = r2.headers.get("content-disposition", "")
    assert "manuscript" in cd2 and ".json" in cd2


def test_api_manuscript_tunes_with_margins(client):
    """Different margins → different SVG (confirms params reach the flow)."""
    r1 = client.get("/api/manuscript?text=永")
    r2 = client.get("/api/manuscript?text=永&margin_top_mm=30")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.content != r2.content
