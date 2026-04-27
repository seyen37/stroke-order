"""Tests for 字帖 grid worksheet exporter (Phase 5j tier-based semantics)."""
import xml.etree.ElementTree as ET

from stroke_order.classifier import classify_character
from stroke_order.exporters.grid import auto_tier_counts, render_grid_svg


def _prep(source, chars: str):
    out = []
    for ch in chars:
        c = source.get_character(ch)
        classify_character(c)
        out.append(c)
    return out


def _cells(svg: str) -> int:
    root = ET.fromstring(svg)
    return len([g for g in root
                if g.tag.endswith("}g") and "transform" in g.attrib])


# ----- auto_tier_counts helper --------------------------------------------


def test_auto_tier_counts_cols_1():
    assert auto_tier_counts(1) == (0, 0)


def test_auto_tier_counts_cols_2():
    assert auto_tier_counts(2) == (1, 0)


def test_auto_tier_counts_cols_3():
    assert auto_tier_counts(3) == (1, 1)


def test_auto_tier_counts_cols_4():
    assert auto_tier_counts(4) == (1, 2)


def test_auto_tier_counts_cols_6():
    assert auto_tier_counts(6) == (1, 4)


# ----- render_grid_svg basic ----------------------------------------------


def test_grid_returns_valid_xml(source):
    chars = _prep(source, "永日")
    svg = render_grid_svg(chars, cols=2, guide="tian")
    root = ET.fromstring(svg)
    assert "svg" in root.tag


def test_grid_cell_count_matches_tier_times_N(source):
    chars = _prep(source, "永")
    # 1 char × cols=3 → 1 primary + 1 ghost + 1 blank = 3 tiers × 1 char = 3 cells
    svg = render_grid_svg(chars, cols=3)
    assert _cells(svg) == 3


def test_grid_supports_all_guide_styles(source):
    chars = _prep(source, "一")
    for guide in ("tian", "mi", "hui", "plain", "none"):
        svg = render_grid_svg(chars, cols=1, guide=guide)
        ET.fromstring(svg)


def test_grid_supports_all_cell_styles(source):
    chars = _prep(source, "一")
    for style in ("outline", "trace", "filled", "ghost", "blank"):
        svg = render_grid_svg(chars, cols=1, cell_style=style)
        ET.fromstring(svg)


# ----- Phase 5j: tier-based layout -----------------------------------------


def test_cols_1_no_practice_cells(source):
    # 4 chars, cols=1 → 1 tier × 4 chars = 4 cells
    chars = _prep(source, "永日一永")
    svg = render_grid_svg(chars, cols=1)
    assert _cells(svg) == 4


def test_cols_2_adds_ghost_tier(source):
    chars = _prep(source, "永日一永")  # N=4
    svg = render_grid_svg(chars, cols=2)
    # 2 tiers × 4 = 8 cells
    assert _cells(svg) == 8


def test_cols_3_adds_ghost_and_blank(source):
    chars = _prep(source, "永日一永")  # N=4
    svg = render_grid_svg(chars, cols=3)
    # 3 tiers × 4 = 12 cells
    assert _cells(svg) == 12


def test_cols_4_extra_blank(source):
    chars = _prep(source, "永日一永")  # N=4
    svg = render_grid_svg(chars, cols=4)
    # 4 tiers × 4 = 16 cells (1 primary + 1 ghost + 2 blank)
    assert _cells(svg) == 16


def test_horizontal_viewbox_is_N_cols_tier_rows(source):
    chars = _prep(source, "永日一")  # N=3
    svg = render_grid_svg(chars, cols=3, direction="horizontal")
    root = ET.fromstring(svg)
    parts = root.get("viewBox").split()
    # horizontal: width = N*EM, height = num_tiers*EM
    assert int(parts[2]) == 3 * 2048  # N chars wide
    assert int(parts[3]) == 3 * 2048  # 3 tiers tall


def test_vertical_viewbox_is_tier_cols_N_rows(source):
    chars = _prep(source, "永日一")  # N=3
    svg = render_grid_svg(chars, cols=3, direction="vertical")
    root = ET.fromstring(svg)
    parts = root.get("viewBox").split()
    # vertical: width = num_tiers*EM, height = N*EM
    assert int(parts[2]) == 3 * 2048  # 3 tiers wide
    assert int(parts[3]) == 3 * 2048  # N chars tall


def test_explicit_ghost_blank_overrides_auto(source):
    chars = _prep(source, "永")
    # cols=3 would auto-give ghost=1, blank=1; explicit override
    svg = render_grid_svg(chars, cols=3, ghost_copies=2, blank_copies=0)
    assert _cells(svg) == 3  # 1 primary + 2 ghost = 3 tiers


def test_empty_chars_returns_valid_svg():
    svg = render_grid_svg([], cols=3)
    root = ET.fromstring(svg)
    assert "svg" in root.tag


# ----- Phase 5k: G-code + JSON exporters -----------------------------------


def test_grid_gcode_only_primary_tier(source):
    from stroke_order.exporters.grid import render_grid_gcode
    chars = _prep(source, "日永")
    # cols=3 → 1 primary + 1 ghost + 1 blank = 3 tiers. G-code only primary → 2 cells.
    gcode = render_grid_gcode(chars, cols=3, cell_size_mm=20.0)
    # Count cell sections
    cell_sections = gcode.count("--- cell")
    assert cell_sections == 2


def test_grid_gcode_contains_prologue_and_epilogue(source):
    from stroke_order.exporters.grid import render_grid_gcode
    chars = _prep(source, "一")
    gcode = render_grid_gcode(chars, cols=1, cell_size_mm=15.0)
    assert "G21" in gcode         # prologue: mm
    assert "G90" in gcode         # absolute
    assert "epilogue" in gcode.lower()
    assert "M5" in gcode          # pen up command


def test_grid_gcode_cell_positioning_horizontal(source):
    from stroke_order.exporters.grid import render_grid_gcode
    chars = _prep(source, "日永")
    gcode = render_grid_gcode(
        chars, cols=1, direction="horizontal",
        cell_size_mm=20.0, origin_x_mm=0, origin_y_mm=0,
    )
    # Two cells at x=0 and x=20 (cell_size_mm)
    assert "--- cell (0,0): 日" in gcode
    assert "--- cell (0,1): 永" in gcode


def test_grid_gcode_cell_positioning_vertical(source):
    from stroke_order.exporters.grid import render_grid_gcode
    chars = _prep(source, "日永")
    gcode = render_grid_gcode(
        chars, cols=1, direction="vertical",
        cell_size_mm=20.0,
    )
    # Vertical with cols=1: num_tiers=1, so 日 row=0 col=0, 永 row=1 col=0
    assert "--- cell (0,0): 日" in gcode
    assert "--- cell (1,0): 永" in gcode


def test_grid_gcode_ghost_blank_skipped(source):
    """Ghost and blank tiers must NOT appear as cell sections."""
    from stroke_order.exporters.grid import render_grid_gcode
    chars = _prep(source, "一永")
    # cols=4 → 1 primary + 1 ghost + 2 blank = 4 tiers × 2 chars = 8 cells total,
    # but only 2 primary cells should be in gcode.
    gcode = render_grid_gcode(chars, cols=4)
    assert gcode.count("--- cell") == 2


def test_grid_json_structure(source):
    from stroke_order.exporters.grid import render_grid_json
    import json
    chars = _prep(source, "日永")
    js = render_grid_json(chars, cols=3, direction="horizontal")
    d = json.loads(js)
    assert "grid" in d and "cells" in d
    assert d["grid"]["N"] == 2
    assert d["grid"]["cols"] == 3
    assert d["grid"]["direction"] == "horizontal"
    assert d["grid"]["tier_counts"] == {"primary": 1, "ghost": 1, "blank": 1}
    assert len(d["cells"]) == 6  # 3 tiers × 2 chars


def test_grid_json_primary_cells_have_strokes(source):
    from stroke_order.exporters.grid import render_grid_json
    import json
    chars = _prep(source, "日")
    js = render_grid_json(chars, cols=3)
    d = json.loads(js)
    primary = [c for c in d["cells"] if c["tier_kind"] == "primary"]
    non_primary = [c for c in d["cells"] if c["tier_kind"] != "primary"]
    assert all("strokes" in c for c in primary)
    assert all("strokes" not in c for c in non_primary)


def test_grid_json_cell_positions_in_mm(source):
    from stroke_order.exporters.grid import render_grid_json
    import json
    chars = _prep(source, "日永一")  # N=3
    js = render_grid_json(chars, cols=2, direction="horizontal", cell_size_mm=20.0)
    d = json.loads(js)
    # primary tier (row=0): 3 cells at x=0, 20, 40
    primary = [c for c in d["cells"] if c["tier_kind"] == "primary"]
    assert sorted(c["x_mm"] for c in primary) == [0.0, 20.0, 40.0]
    # ghost tier (row=1): y=20
    ghost = [c for c in d["cells"] if c["tier_kind"] == "ghost"]
    assert all(c["y_mm"] == 20.0 for c in ghost)


# ----- API format parameter ------------------------------------------------


try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS = True
except ImportError:
    _HAS = False


import pytest


@pytest.fixture(scope="module")
def client():
    if not _HAS:
        pytest.skip("web deps missing")
    return TestClient(create_app())


def test_api_grid_format_svg(client):
    r = client.get("/api/grid?chars=日永&cols=2&format=svg")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]


def test_api_grid_format_gcode(client):
    r = client.get("/api/grid?chars=日永&cols=2&format=gcode")
    assert r.status_code == 200
    assert r.text.startswith("; ---") or "G21" in r.text


def test_api_grid_format_json(client):
    import json
    r = client.get("/api/grid?chars=日永&cols=2&format=json")
    assert r.status_code == 200
    d = json.loads(r.text)
    assert "grid" in d and "cells" in d


def test_api_grid_format_rejects_invalid(client):
    r = client.get("/api/grid?chars=日永&format=pdf")
    assert r.status_code == 422


def test_api_grid_download_headers_for_each_format(client):
    for fmt in ("svg", "gcode", "json"):
        r = client.get(f"/api/grid?chars=日&cols=1&format={fmt}&download=true")
        assert r.status_code == 200
        assert "attachment" in r.headers.get("content-disposition", "")
