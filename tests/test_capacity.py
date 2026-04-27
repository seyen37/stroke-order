"""Tests for layout_capacity / estimate_pages / capacity endpoints."""
import pytest

from stroke_order.exporters.notebook import build_notebook_layout
from stroke_order.exporters.letter import build_letter_layout
from stroke_order.layouts import layout_capacity, estimate_pages


def test_capacity_basic_shape():
    layout = build_notebook_layout(
        preset="small", line_height_mm=12, margin_mm=10
    )
    cap = layout_capacity(layout)
    assert cap["cols_per_line"] > 0
    assert cap["lines_per_page"] > 0
    assert cap["chars_per_page"] == cap["cols_per_line"] * cap["lines_per_page"]


def test_capacity_larger_chars_means_fewer_cells():
    small = layout_capacity(build_notebook_layout(
        preset="small", line_height_mm=8, margin_mm=5))
    big = layout_capacity(build_notebook_layout(
        preset="small", line_height_mm=16, margin_mm=5))
    assert small["chars_per_page"] > big["chars_per_page"]


def test_capacity_larger_margin_means_fewer_cells():
    tight = layout_capacity(build_notebook_layout(
        preset="medium", line_height_mm=12, margin_mm=5))
    roomy = layout_capacity(build_notebook_layout(
        preset="medium", line_height_mm=12, margin_mm=25))
    assert tight["chars_per_page"] > roomy["chars_per_page"]


def test_capacity_doodle_zone_reduces_count():
    no_zone = layout_capacity(build_notebook_layout(
        preset="medium", doodle_zone=False))
    with_zone = layout_capacity(build_notebook_layout(
        preset="medium", doodle_zone=True, doodle_zone_size_mm=40))
    assert no_zone["chars_per_page"] > with_zone["chars_per_page"]
    assert with_zone["blocked_cells"] > 0


def test_estimate_pages_empty_text():
    layout = build_notebook_layout(preset="medium")
    assert estimate_pages("", layout) == 1


def test_estimate_pages_single_page():
    layout = build_letter_layout(preset="A4", line_height_mm=10, margin_mm=20)
    assert estimate_pages("一" * 50, layout) == 1


def test_estimate_pages_overflows():
    layout = build_notebook_layout(
        preset="small", line_height_mm=16, margin_mm=5)
    # smaller capacity → same text needs more pages
    pages = estimate_pages("一" * 500, layout)
    assert pages >= 3


def test_letter_capacity():
    layout = build_letter_layout(preset="A5", line_height_mm=12, margin_mm=18)
    cap = layout_capacity(layout)
    # should fit at least 5 rows and 5 cols on A5 with sensible settings
    assert cap["cols_per_line"] >= 5
    assert cap["lines_per_page"] >= 5


# ---- Web API capacity endpoints ----

try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS_WEB = True
except ImportError:
    _HAS_WEB = False


@pytest.fixture(scope="module")
def client():
    if not _HAS_WEB:
        pytest.skip("web deps missing")
    return TestClient(create_app())


def test_api_notebook_capacity(client):
    r = client.get(
        "/api/notebook/capacity?preset=small&line_height_mm=12&margin_mm=10&text=春眠不覺曉"
    )
    assert r.status_code == 200
    d = r.json()
    assert d["total_chars"] == 5
    assert d["pages_estimated"] == 1
    assert d["chars_per_page"] > 0


def test_api_notebook_capacity_multipage(client):
    r = client.get(
        "/api/notebook/capacity?preset=small&line_height_mm=16&text=" + "一" * 300
    )
    d = r.json()
    assert d["total_chars"] == 300
    assert d["pages_estimated"] >= 2


def test_api_letter_capacity(client):
    r = client.get("/api/letter/capacity?preset=A4&line_height_mm=10&margin_mm=20&text=abc")
    assert r.status_code == 200
    d = r.json()
    assert d["chars_per_page"] > 0
    assert d["cols_per_line"] > 0
    assert d["lines_per_page"] > 0


def test_api_notebook_render_has_capacity_header(client):
    r = client.get("/api/notebook?text=一&preset=small")
    assert r.headers.get("x-capacity-per-page") is not None
    assert int(r.headers["x-capacity-per-page"]) > 0


def test_api_notebook_accepts_margin_mm(client):
    # Different margin → different page count
    r1 = client.get("/api/notebook?text=" + "一"*100 + "&preset=small&line_height_mm=12&margin_mm=5")
    r2 = client.get("/api/notebook?text=" + "一"*100 + "&preset=small&line_height_mm=12&margin_mm=25")
    p1 = int(r1.headers.get("x-stroke-order-pages", "1"))
    p2 = int(r2.headers.get("x-stroke-order-pages", "1"))
    assert p2 >= p1  # bigger margin → same or more pages
