"""
Phase 5af — show_grid toggle for letter + manuscript modes.

When ``show_grid=False``:

- Letter mode: the ruled writing lines (layout.grid_style == "ruled")
  are suppressed. Decorative border, title/signature blocks, and body
  chars are unaffected.
- Manuscript mode: the 25×12 / 20×10 pair grid is suppressed. Outer
  page border and body chars are unaffected.

Both modes keep the default ``show_grid=True`` for back-compat.
"""
from __future__ import annotations

import re

import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.letter import flow_letter, render_letter_page_svg
from stroke_order.exporters.manuscript import (
    flow_manuscript, render_manuscript_page_svg,
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
# Letter — show_grid True/False
# ---------------------------------------------------------------------------


def _ruled_line_count(svg: str) -> int:
    """Count <line> elements inside the ruled-grid group."""
    m = re.search(
        r'<g class="grid[^"]*"[^>]*>(.*?)</g>', svg, re.DOTALL
    )
    if m is None:
        return 0
    return len(re.findall(r'<line\b', m.group(1)))


def test_letter_show_grid_default_on_includes_ruled_lines(loader):
    pages = flow_letter("永一日", loader, preset="A5")
    svg = render_letter_page_svg(pages[0])
    assert _ruled_line_count(svg) > 0


def test_letter_show_grid_false_strips_ruled_lines(loader):
    pages = flow_letter("永一日", loader, preset="A5")
    svg = render_letter_page_svg(pages[0], show_grid=False)
    # No ruled-grid group at all when show_grid=False
    assert 'class="grid' not in svg
    # …but chars are still there
    assert '<g class="chars">' in svg


def test_letter_show_grid_preserves_decorative_border(loader):
    """Hiding ruled lines should not remove the decorative border frame."""
    pages = flow_letter("永", loader, preset="A5")
    svg_on = render_letter_page_svg(
        pages[0], show_grid=False, decorative_border=True)
    assert 'class="border"' in svg_on


# ---------------------------------------------------------------------------
# Manuscript — show_grid True/False
# ---------------------------------------------------------------------------


def test_manuscript_show_grid_default_on_includes_pair_grid(loader):
    pages = flow_manuscript("永", loader)
    svg = render_manuscript_page_svg(pages[0])
    assert 'class="manuscript-grid"' in svg


def test_manuscript_show_grid_false_strips_pair_grid(loader):
    pages = flow_manuscript("永", loader)
    svg = render_manuscript_page_svg(pages[0], show_grid=False)
    assert 'class="manuscript-grid"' not in svg
    # Characters are still present
    assert '<g class="chars">' in svg


def test_manuscript_show_grid_false_works_with_200_preset(loader):
    pages = flow_manuscript("永一日", loader, preset="200")
    svg = render_manuscript_page_svg(pages[0], show_grid=False)
    assert 'class="manuscript-grid"' not in svg
    assert '<g class="chars">' in svg


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


def test_api_letter_show_grid_false(client):
    r_on = client.get("/api/letter?text=永&preset=A5")
    r_off = client.get("/api/letter?text=永&preset=A5&show_grid=false")
    assert r_on.status_code == 200 and r_off.status_code == 200
    assert 'class="grid' in r_on.text
    assert 'class="grid' not in r_off.text


def test_api_manuscript_show_grid_false(client):
    r_on = client.get("/api/manuscript?text=永")
    r_off = client.get("/api/manuscript?text=永&show_grid=false")
    assert r_on.status_code == 200 and r_off.status_code == 200
    assert 'manuscript-grid' in r_on.text
    assert 'manuscript-grid' not in r_off.text


def test_api_manuscript_show_grid_default_is_on(client):
    """Back-compat: no show_grid param → grid drawn."""
    r = client.get("/api/manuscript?text=永")
    assert 'manuscript-grid' in r.text
