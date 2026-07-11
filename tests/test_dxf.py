"""Phase 5bq: DXF R12 writer + patch layered-DXF export tests."""
from __future__ import annotations

import pytest

from stroke_order.exporters.dxf import DxfPolyline, LAYER_COLORS, layers_to_dxf
from stroke_order.ir import EM_SIZE, Character, Point, Stroke


# ---------------------------------------------------------------------------
# writer
# ---------------------------------------------------------------------------


def test_document_structure():
    doc = layers_to_dxf([("CUT", [DxfPolyline([(0, 0), (10, 0)])])])
    assert doc.startswith("0\nSECTION\n2\nHEADER\n")
    assert "AC1009" in doc                      # R12
    assert doc.rstrip().endswith("0\nEOF")
    for section in ("HEADER", "TABLES", "ENTITIES"):
        assert f"2\n{section}\n" in doc


def test_layer_table_and_colors():
    doc = layers_to_dxf([
        ("CUT", []), ("ENGRAVE", []), ("WRITE", []),
    ])
    # 三層都宣告（即使無實體），顏色照慣例：紅/黑/藍
    assert doc.count("0\nLAYER\n") == 3
    assert f"62\n{LAYER_COLORS['CUT']}\n" in doc
    assert f"62\n{LAYER_COLORS['WRITE']}\n" in doc
    assert doc.count("0\nPOLYLINE\n") == 0


def test_closed_flag_and_vertex_count():
    doc = layers_to_dxf([("CUT", [
        DxfPolyline([(0, 0), (10, 0), (10, 5)], closed=True),
        DxfPolyline([(1, 1), (2, 2)], closed=False),
    ])])
    assert doc.count("0\nPOLYLINE\n") == 2
    assert doc.count("0\nVERTEX\n") == 5
    assert doc.count("0\nSEQEND\n") == 2
    assert "70\n1\n" in doc     # closed
    assert "70\n0\n" in doc     # open


def test_y_axis_flip():
    doc = layers_to_dxf([("CUT", [DxfPolyline([(3, 7), (4, 8)])])])
    assert "20\n-7.000\n" in doc and "20\n-8.000\n" in doc
    doc2 = layers_to_dxf([("CUT", [DxfPolyline([(3, 7)])])], flip_y=False)
    # 單點 polyline 被略過（<2 點）→ 無 VERTEX
    assert "0\nVERTEX\n" not in doc2


def test_short_polylines_skipped():
    doc = layers_to_dxf([("CUT", [DxfPolyline([(1, 1)]), DxfPolyline([])])])
    assert "0\nPOLYLINE\n" not in doc


# ---------------------------------------------------------------------------
# patch layered export
# ---------------------------------------------------------------------------


def _stub_char(ch: str) -> Character:
    """One diagonal stroke with a square outline — enough geometry for
    both the ENGRAVE (outline) and WRITE (track) layers."""
    q = EM_SIZE // 4
    return Character(
        char=ch, unicode_hex=f"{ord(ch):04x}", data_source="stub",
        strokes=[Stroke(
            index=0,
            raw_track=[Point(q, q), Point(3 * q, 3 * q)],
            outline=[
                {"type": "M", "x": q, "y": q},
                {"type": "L", "x": 3 * q, "y": q},
                {"type": "L", "x": 3 * q, "y": 3 * q},
                {"type": "L", "x": q, "y": 3 * q},
                {"type": "Z"},
            ],
            kind_code=9, kind_name="其他", has_hook=False,
        )],
    )


def test_render_patch_dxf_three_layers():
    from stroke_order.exporters.patch import render_patch_dxf
    doc = render_patch_dxf("永", lambda ch: _stub_char(ch),
                           preset="rectangle")
    for layer in ("CUT", "ENGRAVE", "WRITE"):
        assert f"2\n{layer}\n" in doc
    # 外框（closed）＋字輪廓＋筆跡至少各一條
    assert doc.count("0\nPOLYLINE\n") >= 3
    assert "70\n1\n" in doc


def test_render_patch_dxf_no_border():
    from stroke_order.exporters.patch import render_patch_dxf
    doc = render_patch_dxf("永", lambda ch: _stub_char(ch),
                           preset="rectangle", show_border=False)
    # CUT 層仍宣告但無實體 → POLYLINE 數量比含框版少 1
    doc_b = render_patch_dxf("永", lambda ch: _stub_char(ch),
                             preset="rectangle", show_border=True)
    assert doc_b.count("0\nPOLYLINE\n") == doc.count("0\nPOLYLINE\n") + 1


def test_render_patch_dxf_tiles_multiply_entities():
    from stroke_order.exporters.patch import render_patch_dxf
    one = render_patch_dxf("永", lambda ch: _stub_char(ch))
    four = render_patch_dxf("永", lambda ch: _stub_char(ch),
                            tile_rows=2, tile_cols=2)
    assert four.count("0\nPOLYLINE\n") == 4 * one.count("0\nPOLYLINE\n")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from stroke_order.web.server import app
    return TestClient(app)


def test_api_patch_dxf_format(client):
    r = client.get("/api/patch?text=吉&preset=rectangle&format=dxf")
    assert r.status_code == 200
    assert "dxf" in r.headers.get("content-disposition", "")
    body = r.text
    assert body.startswith("0\nSECTION")
    for layer in ("CUT", "ENGRAVE", "WRITE"):
        assert f"2\n{layer}\n" in body


def test_api_patch_unknown_format_still_422(client):
    r = client.get("/api/patch?text=吉&format=stl")
    assert r.status_code == 422
