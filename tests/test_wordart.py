"""Tests for wordart exporter + API."""
import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.wordart import (
    capacity, compute_fill, compute_linear, compute_ring,
    edge_positions, fill_positions, ring_positions, wordart_compose,
)
from stroke_order.shapes import Circle, Polygon, make_shape
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


# ----- Ring layout ----------------------------------------------------------


def test_ring_positions_fills_perimeter():
    c = Circle(100, 100, 50)
    pos = ring_positions(c, char_size_mm=10)
    # perimeter ≈ 314 mm, should fit ~31 slots
    assert len(pos) >= 20


def test_ring_positions_scales_with_char_size():
    c = Circle(100, 100, 50)
    big = ring_positions(c, char_size_mm=30)
    small = ring_positions(c, char_size_mm=5)
    assert len(small) > len(big)


def test_compute_ring_places_text(loader):
    c = Circle(100, 100, 50)
    placed, missing = compute_ring(
        "一" * 30, c, char_size_mm=10,
        orient="bottom_to_center", char_loader=loader,
    )
    assert len(placed) > 0
    assert missing == []
    # each placement is 5-tuple
    for p in placed:
        char, x, y, size, rot = p
        assert size == 10
        assert 0 <= rot <= 360


def test_compute_ring_cycles_short_text(loader):
    c = Circle(100, 100, 50)
    placed, _ = compute_ring("一", c, char_size_mm=10,
                             orient="upright", char_loader=loader)
    # only "一" available, so all slots cycle through it
    assert len(placed) > 3
    assert all(p[0].char == "一" for p in placed)


# ----- Fill layout ----------------------------------------------------------


def test_fill_positions_nonempty_for_big_circle():
    c = Circle(100, 100, 50)
    slots = fill_positions(c, char_size_mm=10)
    assert len(slots) > 10


def test_fill_positions_empty_for_tiny_circle():
    c = Circle(100, 100, 2)  # smaller than char
    slots = fill_positions(c, char_size_mm=10)
    assert slots == []


def test_compute_fill_places_some(loader):
    c = Circle(100, 100, 40)
    placed, _ = compute_fill("一" * 50, c, 10, loader)
    assert len(placed) > 0
    assert all(rot == 0 for _, _, _, _, rot in placed)


# ----- Linear layout (polygon) ---------------------------------------------


def test_edge_positions_divides_edge_length():
    pos = edge_positions((0, 0), (40, 0), char_size_mm=10)
    assert len(pos) == 4


def test_compute_linear_uses_per_edge_texts(loader):
    p = make_shape("hexagon", 100, 100, 150)
    # Use only chars known to be in test fixtures
    texts = ["一", "永", "日", "一", "永", "日"]
    placed, missing = compute_linear(
        texts, p, char_size_mm=8, orient="bottom_to_center",
        char_loader=loader,
    )
    # 6 edges, 1 char each → 6 placements
    assert len(placed) >= 5


# ----- Capacity helper -----------------------------------------------------


def test_capacity_ring():
    c = Circle(0, 0, 50)
    info = capacity("ring", c, 10)
    assert "min_chars_for_full_ring" in info
    assert info["min_chars_for_full_ring"] > 0


def test_capacity_linear_per_edge_lengths():
    p = make_shape("hexagon", 0, 0, 100)
    info = capacity("linear", p, 10)
    assert "min_chars_per_edge" in info
    assert len(info["min_chars_per_edge"]) == 6


# ----- High-level compose ---------------------------------------------------


def test_wordart_compose_returns_svg(loader):
    s = make_shape("circle", 100, 100, 120)
    svg, info = wordart_compose(
        s, loader, layout="ring", char_size_mm=10,
        orientation="bottom_to_center",
        text="一永日月" * 10,
        page_width_mm=200, page_height_mm=200,
    )
    assert "<svg" in svg and "</svg>" in svg
    assert info["placed_count"] > 0


# ----- Web API -------------------------------------------------------------

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


def test_api_wordart_capacity(client):
    r = client.get("/api/wordart/capacity?shape=circle&shape_size_mm=140&char_size_mm=10&layout=ring")
    assert r.status_code == 200
    d = r.json()
    assert d["min_chars_for_full_ring"] > 0


def test_api_wordart_render_ring(client):
    r = client.get("/api/wordart?shape=circle&shape_size_mm=140&char_size_mm=10"
                   "&layout=ring&text=" + "一" * 40)
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]
    assert int(r.headers.get("x-wordart-placed", "0")) > 0


def test_api_wordart_linear_per_edge(client):
    r = client.get("/api/wordart?shape=hexagon&shape_size_mm=150&char_size_mm=8"
                   "&layout=linear&texts_per_edge=一|永|日|月|一|日")
    assert r.status_code == 200
    assert int(r.headers.get("x-wordart-placed", "0")) >= 6


def test_api_wordart_clamps_oversize_shape(client):
    """Shape larger than page should be clamped, not reject."""
    r = client.get("/api/wordart/capacity?shape=circle&shape_size_mm=390"
                   "&char_size_mm=10&layout=ring&page_width_mm=210&page_height_mm=297")
    assert r.status_code == 200
    d = r.json()
    assert d["clamped"] is True
    assert d["shape_size_mm"] <= 300


def test_api_wordart_invalid_shape(client):
    r = client.get("/api/wordart?shape=zigzag")
    assert r.status_code == 422
