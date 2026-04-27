"""
Phase 5ab — lines_per_page + max_cell cap in 信紙 (letter) mode.

Mirrors notebook-mode's lines_per_page behaviour:

- Horizontal: N = rows of BODY text per page → cell = body_content_h / N.
  Body content height excludes title_space + signature_space bands (the
  rows user can actually write in).
- Vertical: N = columns per page → cell = content_w / N.
- Cell is capped at ``min(content_w, content_h_full)`` so square cells
  never exceed the page (edge case: tiny N like 1).
- lines_per_page takes precedence over explicit line_height_mm.
"""
from __future__ import annotations

import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.letter import build_letter_layout, flow_letter
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
# build_letter_layout derives line_height from lines_per_page
# ---------------------------------------------------------------------------


def test_lines_per_page_horizontal_derives_cell_from_body_height():
    """Horizontal: cell = (page_h - 2*margin - title_space - sig_space) / N.
    A4 (297mm), margin=15, title_space=10, sig_space=10 → body_h = 247.
    N=10 → cell = 24.7 (but clipped at max_cell = min(180, 267) = 180)."""
    layout = build_letter_layout(
        preset="A4", margin_mm=15,
        title_space_mm=10, signature_space_mm=10,
        lines_per_page=10,
    )
    # body_h = 297 - 30 - 10 - 10 = 247 → cell = 24.7
    assert abs(layout.line_height_mm - 24.7) < 0.01
    assert abs(layout.char_width_mm - 24.7) < 0.01


def test_lines_per_page_vertical_derives_cell_from_width():
    """Vertical: cell = content_w / N. A4 margin=15 → content_w=180.
    N=12 → cell = 15."""
    layout = build_letter_layout(
        preset="A4", margin_mm=15, direction="vertical",
        lines_per_page=12,
    )
    assert abs(layout.line_height_mm - 15.0) < 0.01


def test_lines_per_page_beats_line_height_mm():
    """When both are given, lines_per_page wins (same precedence as notebook)."""
    layout = build_letter_layout(
        preset="A4", margin_mm=15,
        line_height_mm=8,            # would be 8 if it won
        lines_per_page=10,           # body_h=267 / 10 = 26.7
    )
    assert abs(layout.line_height_mm - 26.7) < 0.01


def test_line_height_mm_capped_at_max_cell():
    """Oversized explicit line_height should clip to max_cell, not overflow.
    A5 (148×210), margin=15 → content_w=118, content_h=180 → max_cell=118.
    Requesting lh=200 should clip to 118."""
    layout = build_letter_layout(
        preset="A5", margin_mm=15,
        line_height_mm=200,
    )
    assert abs(layout.line_height_mm - 118.0) < 0.01


def test_lines_per_page_extreme_clips_to_max_cell():
    """lines_per_page=1 on A4 w/ margin=15 → body_h = 267 → derived = 267.
    But max_cell = min(180, 267) = 180 → must cap at 180 (not 267)."""
    layout = build_letter_layout(
        preset="A4", margin_mm=15, lines_per_page=1,
    )
    assert layout.line_height_mm <= 180.01
    assert abs(layout.line_height_mm - 180.0) < 0.01


# ---------------------------------------------------------------------------
# flow_letter threads the param
# ---------------------------------------------------------------------------


def test_flow_letter_lines_per_page_positions_chars(loader):
    """A4 margin=15, lines_per_page=10 (no title/sig space) → cell=26.7.
    First char sits at (15, 15)."""
    pages = flow_letter(
        "永一日", loader, preset="A4", margin_mm=15,
        lines_per_page=10,
    )
    pc = pages[0].chars[0]
    assert abs(pc.x_mm - 15) < 0.01
    assert abs(pc.y_mm - 15) < 0.01
    assert abs(pc.width_mm - 26.7) < 0.01
    assert abs(pc.height_mm - 26.7) < 0.01


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


def test_api_letter_capacity_accepts_lines_per_page(client):
    r = client.get("/api/letter/capacity?text=a&preset=A4"
                   "&margin_mm=15&lines_per_page=10")
    assert r.status_code == 200
    d = r.json()
    # body_h = 267 → cell = 26.7; capacity should reflect cell size
    assert abs(d["line_height_mm"] - 26.7) < 0.01


def test_api_letter_capacity_default_first_line_tracks_lines_per_page(client):
    """When lines_per_page changes cell size, default_first_line_offset_mm
    (= margin_top + line_height) should follow."""
    r = client.get("/api/letter/capacity?text=a&preset=A4"
                   "&margin_mm=15&lines_per_page=20")
    d = r.json()
    # cell = 267/20 = 13.35 → default = 15 + 13.35 = 28.35
    assert abs(d["default_first_line_offset_mm"] - 28.35) < 0.1


def test_api_letter_accepts_lines_per_page(client):
    r = client.get("/api/letter?text=永一日&preset=A4"
                   "&margin_mm=15&lines_per_page=10")
    assert r.status_code == 200


def test_api_letter_lines_per_page_changes_output(client):
    """Different lines_per_page → different SVG (proves param reaches flow)."""
    base = "/api/letter?text=" + "永一" * 5 + "&preset=A4&margin_mm=15"
    r1 = client.get(base + "&lines_per_page=10")
    r2 = client.get(base + "&lines_per_page=20")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.content != r2.content
