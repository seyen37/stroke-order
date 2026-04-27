"""
Phase 5aa — first_line_offset_mm in 信紙 (letter) mode.

Mirrors the notebook-mode tests (test_notebook_grid_fix.py) but targets
the letter exporter + /api/letter endpoints. Behaviour must be identical:

- Auto default = margin + line_height (horizontal: top; vertical: right)
- Minimum allowed value = default (values below clamp to default)
- /api/letter/capacity returns ``default_first_line_offset_mm``
- /api/letter accepts ``first_line_offset_mm`` query param
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
# build_letter_layout threads first_line_offset_mm into PageLayout
# ---------------------------------------------------------------------------


def test_build_letter_layout_passes_first_line_offset():
    layout = build_letter_layout(
        preset="A4", line_height_mm=15, margin_mm=15,
        first_line_offset_mm=42.5,
    )
    assert layout.first_line_offset_mm == 42.5


def test_build_letter_layout_default_is_none():
    layout = build_letter_layout(preset="A4", line_height_mm=15, margin_mm=15)
    assert layout.first_line_offset_mm is None


# ---------------------------------------------------------------------------
# flow_letter honours the offset exactly like flow_notebook
# ---------------------------------------------------------------------------


def test_flow_letter_horizontal_shifts_first_row(loader):
    """A4 margin=15, line_height=15: with offset=60, first row BOTTOM at y=60
    → top at y = 60 - 15 = 45 (vs auto default which would be y=15)."""
    pages = flow_letter("永一日", loader, preset="A4",
                        line_height_mm=15, margin_mm=15)
    default_first_y = pages[0].chars[0].y_mm
    assert abs(default_first_y - 15) < 0.01

    pages = flow_letter("永一日", loader, preset="A4",
                        line_height_mm=15, margin_mm=15,
                        first_line_offset_mm=60)
    shifted_first_y = pages[0].chars[0].y_mm
    assert abs(shifted_first_y - 45) < 0.01   # 60 - 15 = 45


def test_flow_letter_vertical_shifts_first_column(loader):
    """A4 margin=15, char_width=15, vertical: with offset=100, first col LEFT
    at x = 210 - 100 = 110 (vs auto default x=180)."""
    pages = flow_letter("永一日", loader, preset="A4",
                        line_height_mm=15, margin_mm=15,
                        direction="vertical")
    default_first_x = pages[0].chars[0].x_mm
    assert abs(default_first_x - 180) < 0.01   # 210 - 15 - 15 = 180

    pages = flow_letter("永一日", loader, preset="A4",
                        line_height_mm=15, margin_mm=15,
                        direction="vertical",
                        first_line_offset_mm=100)
    shifted_first_x = pages[0].chars[0].x_mm
    assert abs(shifted_first_x - 110) < 0.01   # 210 - 100 = 110


def test_flow_letter_clamps_below_default_horizontal(loader):
    """offset < default (= margin+line_height) clamps to default, so the
    first row never overlaps the top margin."""
    # A4 margin=15, line_height=15 → auto default = 30.
    # offset=5 should clamp to 30 → cursor_y = 30-15 = 15 = content_y.
    pages = flow_letter("永", loader, preset="A4",
                        line_height_mm=15, margin_mm=15,
                        first_line_offset_mm=5)
    first_y = pages[0].chars[0].y_mm
    assert abs(first_y - 15) < 0.01


def test_flow_letter_clamps_below_default_vertical(loader):
    """Vertical offset < default clamps so first col's RIGHT edge stays at
    or inside content_right."""
    pages = flow_letter("永", loader, preset="A4",
                        line_height_mm=15, margin_mm=15,
                        direction="vertical",
                        first_line_offset_mm=5)
    first_x = pages[0].chars[0].x_mm
    # clamp 5 → 30 → cursor_x = 210 - 30 = 180
    assert abs(first_x - 180) < 0.01


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


def test_api_letter_capacity_returns_default_horizontal(client):
    r = client.get("/api/letter/capacity?text=a&preset=A4"
                   "&line_height_mm=15&margin_mm=15&direction=horizontal")
    assert r.status_code == 200
    d = r.json()
    # margin_top=15, line_height=15 → default=30
    assert abs(d["default_first_line_offset_mm"] - 30.0) < 0.01


def test_api_letter_capacity_returns_default_vertical(client):
    r = client.get("/api/letter/capacity?text=a&preset=A4"
                   "&line_height_mm=15&margin_mm=15&direction=vertical")
    assert r.status_code == 200
    d = r.json()
    # margin_right=15, char_width=15 → default=30
    assert abs(d["default_first_line_offset_mm"] - 30.0) < 0.01


def test_api_letter_capacity_default_tracks_title_space(client):
    """title_space_mm is baked into margin_top; capacity default should
    follow so the first row auto-slots below the title band."""
    # A4: margin_y=28 default (no margin_mm override), title_space=14,
    # line_height=10 default → default = 28 + 14 + 10 = 52.
    r = client.get("/api/letter/capacity?text=a&preset=A4"
                   "&title_space_mm=14&direction=horizontal")
    d = r.json()
    assert abs(d["default_first_line_offset_mm"] - 52.0) < 0.5


def test_api_letter_accepts_first_line_offset(client):
    """End-to-end: API call with first_line_offset_mm returns 200."""
    r = client.get("/api/letter?text=永&first_line_offset_mm=60"
                   "&line_height_mm=15&margin_mm=15")
    assert r.status_code == 200


def test_api_letter_first_line_offset_changes_output(client):
    """Different offsets produce different SVGs — proof the param reaches
    the flow engine and actually moves characters."""
    base = ("/api/letter?text=" + "永一日" * 3
            + "&preset=A4&line_height_mm=15&margin_mm=15")
    r1 = client.get(base)
    r2 = client.get(base + "&first_line_offset_mm=80")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.content != r2.content
