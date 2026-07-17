"""Phase 5bo / 5ds / 5du: 元素週期表 exporter + API tests.

5du: the page is now a **standard blank 抄經 sheet** (reuses
``render_sutra_page`` — full 米字格 grid + 日期/抄寫者 header + outer
frame) with the 118 element names placed at their periodic-table cell
positions; blank periodic gaps stay ordinary blank 米字格 cells.
鑭 (57) / 錒 (89) sit in the main block at group 3; 鑭系 (58-71) /
錒系 (90-103) are the pull-out rows below a blank row.
"""
from __future__ import annotations

import pytest

from stroke_order.exporters.periodic_table import (
    ELEMENTS, CATEGORY_COLORS, CATEGORY_LABELS_ZH,
    periodic_table_cells, render_periodic_table_page,
)
from stroke_order.exporters.sutra import get_geometry


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
    by_z = {e["z"]: e for e in ELEMENTS}
    assert by_z[1]["cell"] == (1, 1)           # H
    assert by_z[2]["cell"] == (1, 18)          # He
    assert by_z[26]["cell"] == (4, 8)          # Fe
    assert by_z[57]["cell"] == (6, 3)          # 鑭 La → main block
    assert by_z[58]["cell"] == (8, 3)          # 鈰 Ce → pull-out starts
    assert by_z[71]["cell"] == (8, 16)         # 鎦 Lu
    assert by_z[89]["cell"] == (7, 3)          # 錒 Ac → main block
    assert by_z[90]["cell"] == (9, 3)          # 釷 Th
    assert by_z[103]["cell"] == (9, 16)        # 鐒 Lr
    assert by_z[118]["cell"] == (7, 18)        # Og


def test_every_element_categorised_with_color_and_label():
    for e in ELEMENTS:
        assert e["category"] in CATEGORY_COLORS
        assert e["category"] in CATEGORY_LABELS_ZH


def test_taiwan_names_spot_check():
    by_z = {e["z"]: e for e in ELEMENTS}
    assert by_z[43]["zh"] == "鎝"    # Tc
    assert by_z[85]["zh"] == "砈"    # At
    assert by_z[87]["zh"] == "鍅"    # Fr
    assert by_z[71]["zh"] == "鎦"    # Lu


# ---------------------------------------------------------------------------
# Cell placement on the standard 抄經 grid (row-major / horizontal)
# ---------------------------------------------------------------------------


def test_periodic_table_cells_positions():
    geom = get_geometry("landscape")           # 20 cols × 15 rows
    cols = geom.cols
    cells = periodic_table_cells(geom)
    assert len(cells) == cols * geom.rows
    assert sum(1 for c in cells if c) == 118    # exactly 118 filled
    # 5dv offsets: down 3 rows, right 1 col. 氫 at grid (row 3, col 1).
    assert cells[3 * cols + 1] == "氫"
    assert cells[3 * cols + 18] == "氦"         # group 18, top row
    assert cells[4 * cols + 1] == "鋰"          # period 2, group 1
    assert cells[5 * cols + 1] == "鈉"          # period 3, group 1
    # 鑭 in main block (period 6, group 3) → grid row 8, col 3
    assert cells[8 * cols + 3] == "鑭"
    assert cells[9 * cols + 3] == "錒"          # period 7, group 3
    # blank row between main block (ends grid row 9) and pull-outs
    assert all(cells[10 * cols + c] == "" for c in range(cols))
    assert cells[11 * cols + 3] == "鈰"         # 鑭系 pull-out
    assert cells[12 * cols + 3] == "釷"         # 錒系 pull-out


def test_layout_has_one_blank_column_each_side_and_top_margin():
    geom = get_geometry("landscape")
    cols, rows = geom.cols, geom.rows
    cells = periodic_table_cells(geom)
    # leftmost + rightmost columns fully blank (1 空欄 each side)
    assert all(cells[r * cols + 0] == "" for r in range(rows))
    assert all(cells[r * cols + (cols - 1)] == "" for r in range(rows))
    # top 3 rows blank (上面空 3 格)
    assert all(cells[r * cols + c] == ""
               for r in range(3) for c in range(cols))


def test_group1_reads_top_to_bottom():
    geom = get_geometry("landscape")
    cols = geom.cols
    cells = periodic_table_cells(geom)
    # group 1 sits in grid column 1 (after the 1-col right shift), rows 3-9
    col = "".join(cells[r * cols + 1] for r in range(3, 10))
    assert col == "氫鋰鈉鉀銣銫鍅"


# ---------------------------------------------------------------------------
# Renderer — reuses the real 抄經 body page
# ---------------------------------------------------------------------------


def test_render_is_standard_sutra_sheet():
    svg = render_periodic_table_page(char_loader=lambda ch: None)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    # standard 抄經 chrome: 米字格 helper guides + black outer frame
    assert "stroke-dasharray" in svg               # 米字格 helper lines
    assert 'stroke="#000000"' in svg               # OUTER_FRAME_COLOR
    # none of the old chemistry-card chrome survives
    assert 'id="pt-grid"' not in svg
    assert 'id="pt-bg"' not in svg
    assert 'id="pt-legend"' not in svg
    # no atomic numbers / Latin symbols
    for sym in ("H", "Og", "Fe"):
        assert f">{sym}</text>" not in svg


def test_show_grid_false_drops_mizige_helpers():
    on = render_periodic_table_page(char_loader=lambda ch: None)
    off = render_periodic_table_page(char_loader=lambda ch: None,
                                     show_grid=False)
    assert "stroke-dasharray" in on
    assert "stroke-dasharray" not in off           # helpers gone


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
    """Stub the per-char loader so API-routing tests don't pay the full
    118-glyph render cost. Cells render empty; grid/frame still full."""
    import stroke_order.web.server as srv

    def _null_load(char, source, hook_policy, auto_fix=True):
        from fastapi import HTTPException
        raise HTTPException(404, detail="stubbed")

    monkeypatch.setattr(srv, "_load", _null_load)


def test_api_table_page_renders_for_periodic_table(client, fast_null_loader):
    r = client.get("/api/sutra?preset=periodic_table&page_type=table")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg")
    assert "stroke-dasharray" in r.text           # standard 米字格 sheet
    assert ">Og</text>" not in r.text             # no Latin symbols


def test_api_table_page_rejected_for_other_presets(client):
    r = client.get("/api/sutra?preset=heart_sutra&page_type=table")
    assert r.status_code == 422
    assert "periodic_table" in r.json()["detail"]


def test_api_table_page_post_route(client, fast_null_loader):
    r = client.post("/api/sutra", json={
        "preset": "periodic_table", "page_type": "table",
    })
    assert r.status_code == 200
    assert "stroke-dasharray" in r.text


# ---------------------------------------------------------------------------
# 5dw: 逐字手寫 click-map on the periodic table (extends 5dt from 抄經 body
# pages to the table page). render_periodic_table_page forwards emit_cellmap
# to render_sutra_page; the API table branch capability-detects it.
# ---------------------------------------------------------------------------


def test_cellmap_emitted_only_when_requested():
    off = render_periodic_table_page(char_loader=lambda ch: None)
    on = render_periodic_table_page(char_loader=lambda ch: None,
                                    emit_cellmap=True)
    assert 'id="sutra-cellmap"' not in off      # off by default
    assert 'id="sutra-cellmap"' in on
    # one click rect per element, carrying the element glyph
    assert 'data-char="氫"' in on
    assert 'data-char="鈾"' in on


def test_cellmap_has_exactly_118_element_rects():
    on = render_periodic_table_page(char_loader=lambda ch: None,
                                    emit_cellmap=True)
    cellmap = on.split('id="sutra-cellmap"')[1]
    # blank periodic gaps emit no rect — exactly the 118 element cells do
    assert cellmap.count('data-char="') == 118


def test_api_table_cellmap_flows_through(client, fast_null_loader):
    on = client.get("/api/sutra?preset=periodic_table"
                    "&page_type=table&emit_cellmap=true")
    off = client.get("/api/sutra?preset=periodic_table&page_type=table")
    assert on.status_code == 200 and off.status_code == 200
    assert 'id="sutra-cellmap"' in on.text
    assert 'id="sutra-cellmap"' not in off.text
    assert 'data-char="氫"' in on.text


def test_api_table_cellmap_ignored_by_selfdrawn_table(client, fast_null_loader):
    # multiplication_table is a self-drawn renderer with no emit_cellmap
    # param; requesting it must not raise (capability-detection guard) and
    # simply yields no click-map.
    r = client.get("/api/sutra?preset=multiplication_table"
                   "&page_type=table&emit_cellmap=true")
    assert r.status_code == 200
    assert 'id="sutra-cellmap"' not in r.text
