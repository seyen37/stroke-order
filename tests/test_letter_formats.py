"""
Phase 5ac — 信紙模式 3 種輸出格式 (SVG / G-code / JSON).

Mirrors notebook's format tests (test_notebook_grid_fix.py):

- ``render_letter_gcode`` delegates to notebook's G-code engine, swaps the
  header banner to "信紙", and still emits body-char strokes only.
- ``render_letter_json`` wraps notebook's JSON, renames top key to
  "letter", and appends per-page ``title_block`` / ``signature_block``
  when set by flow_letter.
- ``/api/letter?format=gcode|json`` returns the correct Content-Type,
  honours ``download=true`` (Content-Disposition), and gives the same
  cell-style semantics as notebook (ghost → no strokes).
"""
from __future__ import annotations

import json

import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.letter import (
    flow_letter, render_letter_gcode, render_letter_json,
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
# render_letter_gcode
# ---------------------------------------------------------------------------


def test_gcode_header_identifies_as_letter(loader):
    pages = flow_letter("永一", loader, preset="A5", margin_mm=15,
                        line_height_mm=10)
    gc = render_letter_gcode(pages, cell_style="outline")
    assert "stroke-order 信紙 G-code" in gc
    assert "stroke-order 筆記 G-code" not in gc


def test_gcode_with_writable_style_emits_strokes(loader):
    """cell_style=outline (writable) → at least one pen-down command."""
    pages = flow_letter("永", loader, preset="A5", margin_mm=15,
                        line_height_mm=10)
    gc = render_letter_gcode(pages, cell_style="outline")
    # M3 S90 is the default pen-down command
    assert "M3 S90" in gc


def test_gcode_with_ghost_style_has_no_strokes(loader):
    """cell_style=ghost is tracing-only → header + skip marker, no pen-down."""
    pages = flow_letter("永", loader, preset="A5", margin_mm=15,
                        line_height_mm=10)
    gc = render_letter_gcode(pages, cell_style="ghost")
    assert "M3 S90" not in gc
    assert "no strokes emitted" in gc or "(cell_style=ghost" in gc


# ---------------------------------------------------------------------------
# render_letter_json
# ---------------------------------------------------------------------------


def test_json_top_level_key_is_letter(loader):
    pages = flow_letter("永一", loader, preset="A5", margin_mm=15,
                        line_height_mm=10)
    data = json.loads(render_letter_json(pages, cell_style="outline"))
    assert "letter" in data
    assert "notebook" not in data
    # Preserves the metadata shape from notebook JSON
    assert "pages" in data["letter"]
    assert "page_size_mm" in data["letter"]
    assert "direction" in data["letter"]


def test_json_includes_title_and_signature_blocks(loader):
    pages = flow_letter(
        "永一", loader, preset="A5", margin_mm=15, line_height_mm=10,
        title_text="致恩師",
        signature_text="學生 敬上",
        date_text="2026 春",
    )
    data = json.loads(render_letter_json(pages, cell_style="outline"))
    p0 = data["pages"][0]
    assert "title_block" in p0
    assert p0["title_block"]["text"] == "致恩師"
    last = data["pages"][-1]
    assert "signature_block" in last
    assert last["signature_block"]["signature_text"] == "學生 敬上"
    assert last["signature_block"]["date_text"] == "2026 春"


def test_json_without_title_or_signature_omits_those_keys(loader):
    """Pages without title/signature shouldn't carry noisy null fields."""
    pages = flow_letter("永一", loader, preset="A5", margin_mm=15,
                        line_height_mm=10)
    data = json.loads(render_letter_json(pages, cell_style="outline"))
    for p in data["pages"]:
        assert "title_block" not in p
        assert "signature_block" not in p


def test_json_preserves_chars_data(loader):
    """Body chars (+ stroke track) should survive the wrapper."""
    pages = flow_letter("永", loader, preset="A5", margin_mm=15,
                        line_height_mm=10)
    data = json.loads(render_letter_json(pages, cell_style="outline"))
    chars = data["pages"][0]["chars"]
    assert len(chars) == 1
    assert chars[0]["char"] == "永"
    assert "strokes" in chars[0]
    assert len(chars[0]["strokes"]) > 0


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


def test_api_letter_format_gcode(client):
    r = client.get("/api/letter?text=永一&preset=A5"
                   "&cell_style=outline&format=gcode")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    assert "stroke-order 信紙 G-code" in body
    # Writable style → pen-down present
    assert "M3 S90" in body


def test_api_letter_format_json(client):
    r = client.get("/api/letter?text=永一&preset=A5&format=json"
                   "&title_text=致恩師&signature_text=敬上")
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"]
    data = r.json()
    assert "letter" in data
    # Title appears on page 1; signature on last page
    assert data["pages"][0].get("title_block", {}).get("text") == "致恩師"
    assert data["pages"][-1].get("signature_block", {}).get(
        "signature_text") == "敬上"


def test_api_letter_format_json_default_no_blocks(client):
    """No title/signature text → JSON shouldn't have those keys."""
    r = client.get("/api/letter?text=永&preset=A5&format=json")
    data = r.json()
    for p in data["pages"]:
        assert "title_block" not in p
        assert "signature_block" not in p


def test_api_letter_format_download_sets_content_disposition(client):
    r = client.get("/api/letter?text=永&preset=A5"
                   "&format=gcode&download=true")
    assert r.status_code == 200
    cd = r.headers.get("content-disposition", "")
    assert "letter" in cd and ".gcode" in cd

    r2 = client.get("/api/letter?text=永&preset=A5"
                    "&format=json&download=true")
    cd2 = r2.headers.get("content-disposition", "")
    assert "letter" in cd2 and ".json" in cd2


def test_api_letter_format_default_is_svg(client):
    """Back-compat: no format param → SVG (image/svg+xml or zip for multi-page)."""
    r = client.get("/api/letter?text=永&preset=A5")
    assert r.status_code == 200
    ct = r.headers["content-type"]
    assert "image/svg+xml" in ct or "application/zip" in ct


def test_api_letter_format_rejects_unknown_value(client):
    r = client.get("/api/letter?text=永&preset=A5&format=pdf")
    # FastAPI/Pydantic returns 422 for regex-pattern violation
    assert r.status_code == 422
