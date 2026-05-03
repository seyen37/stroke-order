"""Phase 5h — `align` parameter tests (spread/center/left/right)."""
import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.wordart import (
    _pick_slot_indices, compute_linear, compute_linear_groups,
    compute_linear_ordered, compute_three_band,
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
# _pick_slot_indices — pure helper
# ============================================================================


def test_pick_spread_endpoints_included():
    """B1: spread must include slot 0 and slot (n-1)."""
    idxs = _pick_slot_indices(4, 10, "spread")
    assert idxs[0] == 0
    assert idxs[-1] == 9
    assert len(idxs) == 4


def test_pick_spread_even_distribution():
    idxs = _pick_slot_indices(5, 13, "spread")
    assert idxs == [0, 3, 6, 9, 12]


def test_pick_center():
    assert _pick_slot_indices(4, 10, "center") == [3, 4, 5, 6]


def test_pick_left():
    assert _pick_slot_indices(4, 10, "left") == [0, 1, 2, 3]


def test_pick_right():
    assert _pick_slot_indices(4, 10, "right") == [6, 7, 8, 9]


def test_pick_single_char_always_centered():
    """C1: single char always placed at center slot regardless of align."""
    for a in ("spread", "center", "left", "right"):
        assert _pick_slot_indices(1, 10, a) == [5]
        assert _pick_slot_indices(1, 7, a) == [3]


def test_pick_n_chars_exceeds_slots():
    # chars >= slots: return all slots, align is a no-op
    assert _pick_slot_indices(10, 10, "spread") == list(range(10))
    assert _pick_slot_indices(15, 10, "right") == list(range(10))


def test_pick_empty_cases():
    assert _pick_slot_indices(0, 10) == []
    assert _pick_slot_indices(5, 0) == []


# ============================================================================
# compute_linear — align per edge
# ============================================================================


def test_linear_align_left_places_chars_near_edge_start(loader):
    """With left align, chars should be at the first slots of each edge."""
    shape = make_shape("square", 100, 100, 150)
    # 1 char per edge — C1 always centers. Use 2 chars to show the difference.
    placed_left, _ = compute_linear(
        ["永一", "永一", "永一", "永一"],
        shape, char_size_mm=10, orient="upright", char_loader=loader,
        auto_cycle=False, align="left",
    )
    placed_right, _ = compute_linear(
        ["永一", "永一", "永一", "永一"],
        shape, char_size_mm=10, orient="upright", char_loader=loader,
        auto_cycle=False, align="right",
    )
    # Same char count both ways, but positions differ
    assert len(placed_left) == len(placed_right)
    # The first char on edge 0 differs between left and right
    # (edge 0 goes from vertex 0 to vertex 1; left vs right picks opposite ends)
    positions_left = [(round(p[1], 1), round(p[2], 1)) for p in placed_left]
    positions_right = [(round(p[1], 1), round(p[2], 1)) for p in placed_right]
    assert positions_left != positions_right


def test_linear_align_spread_cell_centered(loader):
    """Phase 5b r3: linear + spread = cell-centered（首尾各留半 gap），
    取代原本「endpoints-included」分布。

    chars at fractions ``(i + 0.5) / n_chars`` of edge length → 兩字位於 25%
    跟 75%，距離 = 0.5 × edge_length。Square shape (size=200, radius=100) 邊長
    100√2 ≈ 141.4mm → 兩字距離應 ≈ 70.7mm（不再是 endpoints 的 ~141mm）。
    """
    import math as _m
    shape = make_shape("square", 100, 100, 200)
    placed, _ = compute_linear(
        ["永一", "", "", ""],  # only edge 0 has text
        shape, char_size_mm=15, orient="upright", char_loader=loader,
        auto_cycle=False, align="spread",
    )
    assert len(placed) == 2
    # 兩字距離應 ≈ 0.5 × edge_length（cell-centered）
    edge_len = 100 * (2 ** 0.5)   # square inscribed in radius-100 circle
    d = _m.hypot(placed[0][1] - placed[1][1], placed[0][2] - placed[1][2])
    assert abs(d - 0.5 * edge_len) < 2.0, (
        f"expected ≈{0.5 * edge_len:.1f}mm (cell-centered), got {d:.1f}mm")
    # 首字應距邊起點 edge_len * 0.25 → 不貼邊 (距離 > char_size_mm 是 sanity check)
    vert0 = shape.vertices[0]
    d0 = _m.hypot(placed[0][1] - vert0[0], placed[0][2] - vert0[1])
    assert d0 > 15, f"first char too close to edge start: {d0:.1f}mm"


def test_linear_align_center_vs_left_differs(loader):
    """center align clusters chars near edge midpoint (≠ left or right)."""
    shape = make_shape("square", 100, 100, 200)
    placed_center, _ = compute_linear(
        ["永一", "", "", ""],
        shape, char_size_mm=15, orient="upright", char_loader=loader,
        auto_cycle=False, align="center",
    )
    placed_left, _ = compute_linear(
        ["永一", "", "", ""],
        shape, char_size_mm=15, orient="upright", char_loader=loader,
        auto_cycle=False, align="left",
    )
    # Center and left should produce different placements on edge 0
    pos_center = {(round(p[1], 1), round(p[2], 1)) for p in placed_center}
    pos_left = {(round(p[1], 1), round(p[2], 1)) for p in placed_left}
    assert pos_center != pos_left
    # Center chars should be closer to the edge midpoint (avg of vertex0 + vertex1)
    vert0 = shape.vertices[0]
    vert1 = shape.vertices[1]
    midpoint = ((vert0[0] + vert1[0]) / 2, (vert0[1] + vert1[1]) / 2)
    def _avg_dist_to(pts, target):
        return sum(((p[1] - target[0]) ** 2 + (p[2] - target[1]) ** 2) ** 0.5
                   for p in pts) / len(pts)
    assert _avg_dist_to(placed_center, midpoint) < _avg_dist_to(placed_left, midpoint)


def test_linear_align_nop_when_auto_cycle_on(loader):
    """align is a no-op when auto_cycle fills the edge."""
    shape = make_shape("square", 100, 100, 200)
    p_left, _ = compute_linear(
        ["永"], shape, 15, "upright", loader,
        auto_cycle=True, align="left",
    )
    p_right, _ = compute_linear(
        ["永"], shape, 15, "upright", loader,
        auto_cycle=True, align="right",
    )
    # auto_cycle cycles "永" across all slots → same output both ways
    positions_left = {(round(p[1], 1), round(p[2], 1)) for p in p_left}
    positions_right = {(round(p[1], 1), round(p[2], 1)) for p in p_right}
    assert positions_left == positions_right


def test_linear_align_nop_when_text_full(loader):
    """align is a no-op when chars exactly fill slots."""
    shape = make_shape("square", 100, 100, 150)
    # Use enough chars to likely fill each edge
    long_text = "永一" * 20
    p_left, _ = compute_linear(
        [long_text] * 4, shape, 10, "upright", loader,
        auto_cycle=False, align="left",
    )
    p_right, _ = compute_linear(
        [long_text] * 4, shape, 10, "upright", loader,
        auto_cycle=False, align="right",
    )
    # When text fills each edge, both aligns produce the same set of positions
    assert len(p_left) == len(p_right)


# ============================================================================
# compute_three_band — align applies to all 3 segments
# ============================================================================


def test_three_band_align_spread_farther_than_center(loader):
    """Spread places chars at arc endpoints — farther apart than center."""
    shape = Circle(100, 100, 80)
    # Top arc only, 2 chars per align
    p_spread, _ = compute_three_band(
        "永一", "", "",
        shape, char_size_mm=8, char_loader=loader,
        auto_cycle=False, align="spread",
    )
    p_center, _ = compute_three_band(
        "永一", "", "",
        shape, char_size_mm=8, char_loader=loader,
        auto_cycle=False, align="center",
    )
    assert len(p_spread) == 2 and len(p_center) == 2
    def _dist(p0, p1):
        return ((p0[1] - p1[1]) ** 2 + (p0[2] - p1[2]) ** 2) ** 0.5
    d_spread = _dist(p_spread[0], p_spread[1])
    d_center = _dist(p_center[0], p_center[1])
    # Spread (arc endpoints ≈ 9 and 3 o'clock) should be much farther apart
    # than center (adjacent slots near 12 o'clock).
    assert d_spread > d_center * 3


def test_three_band_align_center_matches_pre_5h(loader):
    """center align should reproduce the 5e (centered about 12/6 o'clock) behavior."""
    shape = Circle(100, 100, 80)
    placed, _ = compute_three_band(
        "永一永", "一永", "永一永",
        shape, char_size_mm=8, char_loader=loader,
        auto_cycle=False, align="center",
    )
    # top chars near x=cx (100), y < cy
    top_chars = [p for p in placed if p[2] < 100 - 5]
    assert len(top_chars) >= 3
    avg_x = sum(p[1] for p in top_chars) / len(top_chars)
    assert abs(avg_x - 100) < 20  # clustered near the center column


def test_three_band_align_left_clusters_9_oclock(loader):
    """left align on top arc → chars cluster near 9 o'clock (x < cx)."""
    shape = Circle(100, 100, 80)
    placed, _ = compute_three_band(
        "永一", "", "",
        shape, char_size_mm=8, char_loader=loader,
        auto_cycle=False, align="left",
    )
    # Top arc with "left" → slots near the start (9 o'clock side)
    top_chars = [p for p in placed if p[2] < 100]
    assert len(top_chars) >= 2
    # All top chars should have x well to the left of cx
    for p in top_chars:
        assert p[1] < 100  # all on left side


def test_three_band_align_right_clusters_3_oclock(loader):
    """right align on top arc → chars cluster near 3 o'clock (x > cx)."""
    shape = Circle(100, 100, 80)
    placed, _ = compute_three_band(
        "永一", "", "",
        shape, char_size_mm=8, char_loader=loader,
        auto_cycle=False, align="right",
    )
    top_chars = [p for p in placed if p[2] < 100]
    assert len(top_chars) >= 2
    for p in top_chars:
        assert p[1] > 100  # all on right side


def test_three_band_single_char_always_centered(loader):
    """C1: single char on top arc → center (12 o'clock), regardless of align."""
    shape = Circle(100, 100, 80)
    for align in ("spread", "center", "left", "right"):
        placed, _ = compute_three_band(
            "永", "", "", shape, 8, loader,
            auto_cycle=False, align=align,
        )
        assert len(placed) == 1
        p = placed[0]
        # Single char should be near top (x≈100, y much less than cy=100)
        assert abs(p[1] - 100) < 1  # x near centre
        assert p[2] < 50  # near 12 o'clock


# ============================================================================
# compute_linear_groups + compute_linear_ordered align pass-through
# ============================================================================


def test_linear_groups_align_passed_through(loader):
    shape = make_shape("hexagon", 100, 100, 150)
    # 1 group of 3 edges, 2 chars on that path
    p_left, _ = compute_linear_groups(
        ["永一"], [[0, 1, 2]], shape, 10, "upright", loader,
        auto_cycle=False, align="left",
    )
    p_right, _ = compute_linear_groups(
        ["永一"], [[0, 1, 2]], shape, 10, "upright", loader,
        auto_cycle=False, align="right",
    )
    assert len(p_left) == 2
    assert len(p_right) == 2
    # Positions should differ
    pos_left = {(round(p[1], 1), round(p[2], 1)) for p in p_left}
    pos_right = {(round(p[1], 1), round(p[2], 1)) for p in p_right}
    assert pos_left != pos_right


def test_linear_ordered_align_passed_through(loader):
    shape = make_shape("square", 100, 100, 200)
    # 1 char per edge, but with align=right — C1 overrides to center
    placed, _ = compute_linear_ordered(
        ["永", "一", "永", "一"],
        shape, 15, "upright", loader,
        edge_start=0, edge_direction="cw",
        auto_cycle=False, align="right",
    )
    assert len(placed) == 4


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


def test_api_align_default_is_spread(client):
    r = client.get(
        "/api/wordart?shape=square&shape_size_mm=200&char_size_mm=15"
        "&layout=linear&texts_per_edge=永一%7C永一%7C永一%7C永一"
        "&auto_cycle=false"
    )
    assert r.status_code == 200


def test_api_align_each_value_accepted(client):
    for v in ("spread", "center", "left", "right"):
        r = client.get(
            f"/api/wordart?shape=square&shape_size_mm=200&char_size_mm=15"
            f"&layout=linear&texts_per_edge=永一%7C永一%7C永一%7C永一"
            f"&auto_cycle=false&align={v}"
        )
        assert r.status_code == 200, f"align={v} failed"


def test_api_align_rejects_invalid(client):
    r = client.get(
        "/api/wordart?shape=square&shape_size_mm=200&char_size_mm=15"
        "&layout=linear&texts_per_edge=永一%7C永一%7C永一%7C永一"
        "&auto_cycle=false&align=justified"
    )
    assert r.status_code == 422


def test_api_align_affects_three_band_output(client):
    base_url = (
        "/api/wordart?shape=circle&shape_size_mm=180&char_size_mm=8"
        "&layout=three_band&text_top=永一永一&text_mid=&text_bot="
        "&auto_cycle=false"
    )
    r_spread = client.get(base_url + "&align=spread")
    r_center = client.get(base_url + "&align=center")
    r_left = client.get(base_url + "&align=left")
    r_right = client.get(base_url + "&align=right")
    # Four SVGs must be all distinct
    svgs = {r_spread.content, r_center.content, r_left.content, r_right.content}
    assert len(svgs) == 4
