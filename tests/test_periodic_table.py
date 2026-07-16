"""Phase 5bo / 5ds: 元素週期表 exporter + API tests.

5ds redesign: the page is now a 米字格抄經 layout — every occupied cell
is a 米字格 with the element's Chinese name as a 描紅 trace glyph, and
nothing else (no atomic numbers, Latin symbols, category tint, legend,
or group/period labels). 鑭 (57) / 錒 (89) sit in the main block at
group 3; 鑭系 (58-71) / 錒系 (90-103) are the pull-out rows.
"""
from __future__ import annotations

import pytest

from stroke_order.exporters.periodic_table import (
    ELEMENTS, CATEGORY_COLORS, CATEGORY_LABELS_ZH,
    render_periodic_table_page,
)


# ---------------------------------------------------------------------------
# Layout data sanity
# ---------------------------------------------------------------------------


def test_118_elements_no_cell_overlap():
    cells = [e["cell"] for e in ELEMENTS]
    assert len(cells) == 118
    assert len(set(cells)) == 118


def test_cell_ranges_match_standard_layout():
    for e in ELEMENTS:
        row, col = e["cell"]
        assert 1 <= row <= 9
        assert 1 <= col <= 18
        if row in (8, 9):                      # 鑭系/錒系 pull-out rows
            assert 3 <= col <= 16
    # spot checks against the 5ds layout
    by_z = {e["z"]: e for e in ELEMENTS}
    assert by_z[1]["cell"] == (1, 1)           # H  — group 1, period 1
    assert by_z[2]["cell"] == (1, 18)          # He — group 18, period 1
    assert by_z[26]["cell"] == (4, 8)          # Fe
    assert by_z[57]["cell"] == (6, 3)          # 鑭 La → main block, group 3
    assert by_z[58]["cell"] == (8, 3)          # 鈰 Ce → pull-out row starts
    assert by_z[71]["cell"] == (8, 16)         # 鎦 Lu → pull-out row ends
    assert by_z[89]["cell"] == (7, 3)          # 錒 Ac → main block, group 3
    assert by_z[90]["cell"] == (9, 3)          # 釷 Th → actinide pull-out
    assert by_z[103]["cell"] == (9, 16)        # 鐒 Lr → actinide pull-out ends
    assert by_z[104]["cell"] == (7, 4)         # Rf resumes period 7
    assert by_z[118]["cell"] == (7, 18)        # Og


def test_group1_reads_top_to_bottom_in_leftmost_column():
    """User spec: leftmost column top→bottom = 氫 鋰 鈉 鉀 銣 銫 鍅."""
    by_z = {e["z"]: e for e in ELEMENTS}
    col1 = [(by_z[z]["cell"], by_z[z]["zh"])
            for z in (1, 3, 11, 19, 37, 55, 87)]
    for period, ((row, col), zh) in enumerate(col1, start=1):
        assert col == 1
        assert row == period
    assert "".join(zh for _, zh in col1) == "氫鋰鈉鉀銣銫鍅"


def test_group3_has_lanthanum_and_actinium_in_main_block():
    """5ds: 鑭/錒 live in group 3 (col 3) at periods 6/7, not the
    pull-out rows."""
    cols_p6 = {e["cell"][1] for e in ELEMENTS if e["cell"][0] == 6}
    cols_p7 = {e["cell"][1] for e in ELEMENTS if e["cell"][0] == 7}
    assert 3 in cols_p6                         # 鑭 La
    assert 3 in cols_p7                         # 錒 Ac
    by_z = {e["z"]: e for e in ELEMENTS}
    assert by_z[57]["zh"] == "鑭"
    assert by_z[89]["zh"] == "錒"


def test_every_element_categorised_with_color_and_label():
    # category data retained for reference even though the render draws
    # no tint/legend anymore.
    for e in ELEMENTS:
        assert e["category"] in CATEGORY_COLORS
        assert e["category"] in CATEGORY_LABELS_ZH


def test_taiwan_names_spot_check():
    by_z = {e["z"]: e for e in ELEMENTS}
    assert by_z[43]["zh"] == "鎝"    # Tc 臺灣譯名
    assert by_z[85]["zh"] == "砈"    # At
    assert by_z[87]["zh"] == "鍅"    # Fr
    assert by_z[71]["zh"] == "鎦"    # Lu


# ---------------------------------------------------------------------------
# Renderer — 米字格 style, characters only
# ---------------------------------------------------------------------------


def test_render_with_null_loader_still_valid_svg():
    svg = render_periodic_table_page(char_loader=lambda ch: None)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    # new structural groups
    assert 'id="pt-grid"' in svg
    assert 'id="pt-title"' in svg
    assert 'id="pt-trace"' in svg
    # 米字格 cells drawn even without glyphs (border stroke present)
    assert 'stroke="#888888"' in svg          # GRID_LINE_COLOR
    # removed chrome: no category bg, no legend, no in-table series markers
    assert 'id="pt-bg"' not in svg
    assert 'id="pt-legend"' not in svg
    assert "57-71" not in svg and "89-103" not in svg


def test_render_draws_no_atomic_numbers_or_latin_symbols():
    svg = render_periodic_table_page(char_loader=lambda ch: None)
    # Latin element symbols must not appear as <text> anymore
    for sym in ("H", "Og", "Fe", "Au"):
        assert f">{sym}</text>" not in svg


def test_show_grid_false_omits_mizige_lines():
    with_grid = render_periodic_table_page(char_loader=lambda ch: None)
    no_grid = render_periodic_table_page(
        char_loader=lambda ch: None, show_grid=False)
    grid_block = with_grid.split('id="pt-grid"')[1].split("</g>")[0]
    empty_block = no_grid.split('id="pt-grid"')[1].split("</g>")[0]
    assert "<rect" in grid_block               # 米字格 borders present
    assert "<rect" not in empty_block          # omitted when show_grid=False


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from stroke_order.web.server import app
    return TestClient(app)


@pytest.fixture()
def fast_null_loader(monkeypatch):
    """Stub the per-char loading pipeline so API-routing tests don't pay
    the full 118-glyph render cost (covered by exporter-level tests +
    visual verification). Cells render as empty 米字格; layout still full."""
    import stroke_order.web.server as srv

    def _null_load(char, source, hook_policy, auto_fix=True):
        from fastapi import HTTPException
        raise HTTPException(404, detail="stubbed")

    monkeypatch.setattr(srv, "_load", _null_load)


def test_api_table_page_renders_for_periodic_table(client, fast_null_loader):
    r = client.get("/api/sutra?preset=periodic_table&page_type=table")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg")
    assert 'id="pt-grid"' in r.text
    assert 'id="pt-trace"' in r.text


def test_api_table_page_rejected_for_other_presets(client):
    r = client.get("/api/sutra?preset=heart_sutra&page_type=table")
    assert r.status_code == 422
    assert "periodic_table" in r.json()["detail"]


def test_api_table_page_post_route(client, fast_null_loader):
    r = client.post("/api/sutra", json={
        "preset": "periodic_table", "page_type": "table",
    })
    assert r.status_code == 200
    assert 'id="pt-grid"' in r.text
