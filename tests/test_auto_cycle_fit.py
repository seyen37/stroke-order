"""Phase 5e: auto_cycle + auto_fit tests."""
import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.wordart import (
    MIN_CHAR_SIZE_MM, _cycle_chars, _fit_char_size_binary,
    compute_fill, compute_linear, compute_linear_groups,
    compute_linear_ordered, compute_ring, compute_three_band,
)
from stroke_order.exporters.wordcloud import (
    compute_gradient_v, compute_split_lr,
)
from stroke_order.shapes import Circle, make_shape
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


# ============================================================================
# Helpers
# ============================================================================


def test_cycle_chars_short_input():
    assert _cycle_chars(["a", "b"], 5) == ["a", "b", "a", "b", "a"]


def test_cycle_chars_long_input_truncates():
    assert _cycle_chars(["a", "b", "c", "d", "e"], 3) == ["a", "b", "c"]


def test_cycle_chars_empty():
    assert _cycle_chars([], 5) == []


def test_cycle_chars_zero_target():
    assert _cycle_chars(["a"], 0) == []


def test_fit_binary_already_fits():
    # If requested size works, return it as-is
    size = _fit_char_size_binary(lambda s: s <= 10, requested=10, min_size=1)
    assert size == 10


def test_fit_binary_shrinks_to_fit():
    # Condition: size <= 5 means "fits"
    size = _fit_char_size_binary(lambda s: s <= 5, requested=15, min_size=1, tol=0.01)
    assert 4.9 < size <= 5.0


def test_fit_binary_hits_floor():
    # Condition never satisfied → returns min_size
    size = _fit_char_size_binary(lambda s: False, requested=10, min_size=3)
    assert size == 3


# ============================================================================
# compute_ring: auto_fit only (cycle is inherent)
# ============================================================================


def test_ring_auto_fit_shrinks_for_long_text(loader):
    shape = Circle(100, 100, 40)  # small circle
    long_text = "永一日" * 20   # 60 chars
    # With char_size_mm=15 only ~16 slots fit
    placed, _ = compute_ring(
        long_text, shape, char_size_mm=15, orient="upright",
        char_loader=loader, auto_fit=True,
    )
    # With auto_fit, all 60 chars should fit at a smaller size
    assert len(placed) >= 50
    # All placed chars should be at the SAME size (smaller than 15)
    sizes = {p[3] for p in placed}
    assert len(sizes) == 1
    assert list(sizes)[0] < 15


def test_ring_no_auto_fit_truncates_at_requested_size(loader):
    shape = Circle(100, 100, 40)
    long_text = "永一日" * 20
    placed, _ = compute_ring(
        long_text, shape, char_size_mm=15, orient="upright",
        char_loader=loader, auto_fit=False,
    )
    # Ring cycles at requested size — placements <= slot count at size=15
    sizes = {p[3] for p in placed}
    assert 15.0 in sizes


# ============================================================================
# compute_fill: auto_cycle + auto_fit
# ============================================================================


def test_fill_auto_cycle_fills_all_slots(loader):
    shape = Circle(100, 100, 50)
    placed_cycle, _ = compute_fill(
        "永一", shape, 10, loader, auto_cycle=True,
    )
    placed_nocycle, _ = compute_fill(
        "永一", shape, 10, loader, auto_cycle=False,
    )
    assert len(placed_cycle) > len(placed_nocycle)
    assert len(placed_nocycle) == 2


def test_fill_auto_fit_shrinks(loader):
    shape = Circle(100, 100, 30)
    long_text = "永一日" * 15   # 45 chars
    placed, _ = compute_fill(
        long_text, shape, char_size_mm=12, char_loader=loader,
        auto_fit=True,
    )
    sizes = {round(p[3], 2) for p in placed}
    assert len(sizes) == 1
    assert list(sizes)[0] < 12


def test_fill_auto_fit_hits_floor_and_truncates(loader):
    shape = Circle(100, 100, 8)  # tiny shape
    long_text = "永" * 50
    placed, _ = compute_fill(
        long_text, shape, char_size_mm=15, char_loader=loader,
        auto_fit=True, min_char_size_mm=3.0,
    )
    # Must not crash. Size should be at/near min_char_size_mm (3.0)
    if placed:
        assert list({round(p[3], 2) for p in placed})[0] <= 4.0


# ============================================================================
# compute_linear: auto_cycle per edge + auto_fit global
# ============================================================================


def test_linear_auto_cycle_per_edge(loader):
    shape = make_shape("square", 100, 100, 150)
    texts = ["永", "一", "日", "永"]
    placed_cycle, _ = compute_linear(
        texts, shape, 20, "upright", loader, auto_cycle=True,
    )
    placed_nocycle, _ = compute_linear(
        texts, shape, 20, "upright", loader, auto_cycle=False,
    )
    # cycling should produce strictly more placements
    assert len(placed_cycle) > len(placed_nocycle)


def test_linear_auto_fit_finds_global_size(loader):
    shape = make_shape("square", 100, 100, 150)
    texts = ["永" * 30, "一" * 3, "日" * 3, "永" * 3]
    placed, _ = compute_linear(
        texts, shape, char_size_mm=20, orient="upright", char_loader=loader,
        auto_fit=True,
    )
    # All edges get placements with the same smaller size
    sizes = {round(p[3], 2) for p in placed}
    assert len(sizes) == 1
    assert list(sizes)[0] < 20


# ============================================================================
# compute_three_band: both flags
# ============================================================================


def test_three_band_auto_cycle_independent_segments(loader):
    shape = Circle(100, 100, 80)
    placed_cycle, _ = compute_three_band(
        "永", "一", "日", shape, 10, loader,
        auto_cycle=True,
    )
    placed_nocycle, _ = compute_three_band(
        "永", "一", "日", shape, 10, loader,
        auto_cycle=False,
    )
    assert len(placed_cycle) > len(placed_nocycle)


def test_three_band_auto_fit_shrinks_all_segments(loader):
    shape = Circle(100, 100, 50)
    long = "永" * 30
    placed, _ = compute_three_band(
        long, "一", long, shape, char_size_mm=15, char_loader=loader,
        auto_fit=True,
    )
    sizes = {round(p[3], 2) for p in placed}
    assert len(sizes) == 1
    assert list(sizes)[0] < 15


# ============================================================================
# compute_split_lr: both flags
# ============================================================================


def test_split_lr_auto_cycle(loader):
    shape = Circle(100, 100, 50)
    placed_cycle, _ = compute_split_lr(
        "永", "一", shape, 10, loader, auto_cycle=True,
    )
    placed_nocycle, _ = compute_split_lr(
        "永", "一", shape, 10, loader, auto_cycle=False,
    )
    assert len(placed_cycle) > len(placed_nocycle)


def test_split_lr_auto_fit(loader):
    shape = Circle(100, 100, 40)
    long = "永一" * 15
    placed, _ = compute_split_lr(
        long, long, shape, char_size_mm=15, char_loader=loader,
        auto_fit=True,
    )
    sizes = {round(p[3], 2) for p in placed}
    assert len(sizes) == 1
    assert list(sizes)[0] < 15


# ============================================================================
# compute_gradient_v: auto_cycle only
# ============================================================================


def test_gradient_v_auto_cycle_fills_shape(loader):
    shape = Circle(100, 100, 50)
    placed_cycle, _ = compute_gradient_v(
        "永一", shape, loader, min_size_mm=5, max_size_mm=15,
        auto_cycle=True,
    )
    placed_nocycle, _ = compute_gradient_v(
        "永一", shape, loader, min_size_mm=5, max_size_mm=15,
        auto_cycle=False,
    )
    assert len(placed_cycle) > len(placed_nocycle)


# ============================================================================
# compute_linear_groups: both flags
# ============================================================================


def test_linear_groups_auto_cycle(loader):
    shape = make_shape("hexagon", 100, 100, 150)
    placed_cycle, _ = compute_linear_groups(
        ["永", "一"],
        [[0, 1, 2], [3, 4, 5]],
        shape, 10, "upright", loader,
        auto_cycle=True,
    )
    placed_nocycle, _ = compute_linear_groups(
        ["永", "一"],
        [[0, 1, 2], [3, 4, 5]],
        shape, 10, "upright", loader,
        auto_cycle=False,
    )
    assert len(placed_cycle) > len(placed_nocycle)


def test_linear_ordered_passes_auto_flags(loader):
    shape = make_shape("hexagon", 100, 100, 150)
    placed, _ = compute_linear_ordered(
        ["永"], shape, 10, "upright", loader,
        edge_start=0, edge_direction="cw",
        auto_cycle=True,
    )
    # With 1 char cycled across one edge
    assert len(placed) >= 1


# ============================================================================
# Web API integration tests
# ============================================================================


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


def test_api_auto_cycle_short_text_fills_fill(client):
    r = c = client.get(
        "/api/wordart?shape=circle&shape_size_mm=120&char_size_mm=10"
        "&layout=fill&text=永一&auto_cycle=true"
    )
    assert r.status_code == 200
    placed = int(r.headers["x-wordart-placed"])
    assert placed > 2  # 2-char text cycled


def test_api_auto_cycle_off_short_text(client):
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=120&char_size_mm=10"
        "&layout=fill&text=永一&auto_cycle=false"
    )
    assert r.status_code == 200
    assert int(r.headers["x-wordart-placed"]) == 2


def test_api_auto_fit_shrinks_size(client):
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=80&char_size_mm=15"
        "&layout=ring&text=" + "永一" * 20 + "&auto_fit=true"
    )
    assert r.status_code == 200
    req = float(r.headers["x-wordart-requested-size"])
    actual = float(r.headers["x-wordart-fitted-size"])
    assert req == 15.0
    assert actual < 15.0


def test_api_auto_fit_off_no_shrinking(client):
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=80&char_size_mm=15"
        "&layout=ring&text=" + "永一" * 20 + "&auto_fit=false"
    )
    assert r.status_code == 200
    # Size stays at requested
    assert abs(float(r.headers["x-wordart-fitted-size"]) - 15.0) < 0.5


def test_api_both_flags_together(client):
    # Short text + both flags → should auto-cycle (fit is a no-op when text shorter)
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=120&char_size_mm=10"
        "&layout=fill&text=永一&auto_cycle=true&auto_fit=true"
    )
    assert r.status_code == 200
    assert int(r.headers["x-wordart-placed"]) > 2


def test_api_min_char_size_floor(client):
    # Absurd overflow: min_char_size_mm ensures we don't go below 3mm
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=50&char_size_mm=20"
        "&layout=fill&text=" + "永" * 200 + "&auto_fit=true&min_char_size_mm=5"
    )
    assert r.status_code == 200
    # size shouldn't go below 5mm
    assert float(r.headers["x-wordart-fitted-size"]) >= 4.8
