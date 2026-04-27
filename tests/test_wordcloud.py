"""Tests for wordcloud module and Phase 5d wordart extensions."""
import math

import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.wordart import (
    compute_linear_groups, compute_linear_ordered, compute_three_band,
    three_band_capacity,
)
from stroke_order.exporters.wordcloud import (
    N_LEVELS, Token, compute_concentric, compute_gradient_v,
    compute_split_lr, compute_wordcloud, level_to_size,
    parse_tokens, try_place_token, wordcloud_capacity,
    # Phase 5an
    compute_gradient_h, compute_radial_gradient, compute_wave,
)
from stroke_order.shapes import Circle, Ellipse, Polygon, make_shape
from stroke_order.smoothing import smooth_character


# ---- shared loader fixture ------------------------------------------------


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
# parse_tokens
# ============================================================================


def test_parse_tokens_manual_weights():
    ts = parse_tokens("春:7|夏:5|秋:3|冬:1")
    assert [(t.text, t.weight) for t in ts] == \
        [("春", 7), ("夏", 5), ("秋", 3), ("冬", 1)]


def test_parse_tokens_default_weight():
    ts = parse_tokens("春|夏")
    assert all(t.weight == 4 for t in ts)


def test_parse_tokens_clamps_weight_to_range():
    ts = parse_tokens("春:99|夏:0|秋:-3")
    # Out-of-range :weight falls back to default 4 (parse failure)
    assert all(1 <= t.weight <= N_LEVELS for t in ts)


def test_parse_tokens_skips_empty():
    ts = parse_tokens("春:7||夏:3|")
    assert len(ts) == 2


def test_parse_tokens_random_mode_varies():
    import random
    random.seed(42)
    ts = parse_tokens("a|b|c|d|e|f|g|h", weight_mode="random")
    weights = [t.weight for t in ts]
    # At least some variation (not all same)
    assert len(set(weights)) > 1
    assert all(1 <= w <= N_LEVELS for w in weights)


def test_parse_tokens_frequency_mode():
    # 永 appears 3 times, 一 appears 1 time
    ts = parse_tokens("永永永|一", weight_mode="frequency")
    # Token with 永 should have higher weight
    by_text = {t.text: t.weight for t in ts}
    assert by_text["永永永"] > by_text["一"]


def test_parse_tokens_ignores_invalid_weight_suffix():
    ts = parse_tokens("春:abc|夏")
    assert ts[0].text == "春:abc"  # :abc is not a valid int, kept as part of text
    assert ts[0].weight == 4


# ============================================================================
# level_to_size
# ============================================================================


def test_level_to_size_endpoints():
    assert level_to_size(1, 5, 20) == 5.0
    assert level_to_size(7, 5, 20) == 20.0


def test_level_to_size_monotonic():
    sizes = [level_to_size(i, 5, 20) for i in range(1, 8)]
    # Strictly increasing
    for a, b in zip(sizes, sizes[1:]):
        assert b > a


def test_level_to_size_clamps_out_of_range():
    assert level_to_size(0, 5, 20) == level_to_size(1, 5, 20)
    assert level_to_size(99, 5, 20) == level_to_size(7, 5, 20)


# ============================================================================
# try_place_token (collision avoidance)
# ============================================================================


def test_try_place_empty_shape_returns_center():
    shape = Circle(100, 100, 50)
    pos = try_place_token(10, 2, shape, [], padding_mm=1)
    assert pos is not None
    x, y = pos
    # First spiral point is centroid
    assert abs(x - 100) < 0.01 and abs(y - 100) < 0.01


def test_try_place_avoids_collision():
    shape = Circle(100, 100, 50)
    # Place a token at center occupying (95,95)-(105,105)
    occupied = [(95, 95, 105, 105)]
    pos = try_place_token(10, 1, shape, occupied, padding_mm=1)
    assert pos is not None
    x, y = pos
    # Must be outside occupied area
    assert not (95 <= x <= 105 and 95 <= y <= 105)


def test_try_place_returns_none_when_full():
    shape = Circle(0, 0, 5)  # too small for a 20mm token
    pos = try_place_token(20, 3, shape, [], padding_mm=1)
    assert pos is None


# ============================================================================
# compute_wordcloud
# ============================================================================


def test_compute_wordcloud_places_tokens(loader):
    # Use chars available in fixtures
    tokens = parse_tokens("永:7|一:5|日:3")
    shape = Circle(100, 100, 60)
    placed, missing, dropped = compute_wordcloud(
        tokens, shape, char_loader=loader,
        min_size_mm=6, max_size_mm=20,
    )
    assert len(placed) >= 3
    assert missing == []
    assert dropped == []


def test_compute_wordcloud_sizes_by_weight(loader):
    tokens = parse_tokens("永:7|一:1")
    shape = Circle(100, 100, 80)
    placed, _, _ = compute_wordcloud(
        tokens, shape, char_loader=loader,
        min_size_mm=4, max_size_mm=20,
    )
    # First placement (largest = 永) should be biggest
    sizes = sorted({p[3] for p in placed}, reverse=True)
    assert sizes[0] > sizes[-1]


def test_compute_wordcloud_drops_oversized(loader):
    # Tiny shape, large tokens — at least some must be dropped
    tokens = parse_tokens("永:7|一:7|日:7|永:7")
    shape = Circle(100, 100, 12)  # very small
    placed, _, dropped = compute_wordcloud(
        tokens, shape, char_loader=loader,
        min_size_mm=8, max_size_mm=20,
        shrink_on_fail=False,
    )
    assert len(dropped) > 0


def test_compute_wordcloud_missing_chars_reported(loader):
    tokens = parse_tokens("葉:5")  # not in fixtures
    shape = Circle(100, 100, 50)
    placed, missing, dropped = compute_wordcloud(
        tokens, shape, char_loader=loader,
        min_size_mm=5, max_size_mm=15,
    )
    assert "葉" in missing
    # Token with all-missing chars isn't placed or dropped (just filtered)
    assert placed == []


def test_compute_wordcloud_shrinks_before_dropping(loader):
    tokens = parse_tokens("永:7")
    # Shape only fits level 1
    shape = Circle(100, 100, 6)
    placed, _, dropped = compute_wordcloud(
        [Token(text="永", weight=7)], shape, char_loader=loader,
        min_size_mm=4, max_size_mm=30,
        shrink_on_fail=True,
    )
    # Should either fit at shrunken size or be dropped, but not raise
    assert len(placed) + len(dropped) == 1


# ============================================================================
# compute_concentric
# ============================================================================


def test_concentric_circle(loader):
    shape = Circle(100, 100, 60)
    placed, missing = compute_concentric(
        ["永永永永永永永永", "一一一一一一"],
        shape, char_size_mm=8, orient="bottom_to_center",
        char_loader=loader,
    )
    assert len(placed) > 0
    assert missing == []


def test_concentric_polygon(loader):
    shape = make_shape("hexagon", 100, 100, 140)
    placed, _ = compute_concentric(
        ["永" * 20, "一" * 10],
        shape, char_size_mm=8, orient="bottom_to_center",
        char_loader=loader,
    )
    assert len(placed) > 0


def test_concentric_stops_when_too_small(loader):
    shape = Circle(100, 100, 20)
    # 10 rings requested, but shape too small → should stop early
    texts = ["永"] * 10
    placed, _ = compute_concentric(
        texts, shape, char_size_mm=8, orient="upright",
        char_loader=loader,
    )
    # Should not crash; may be empty if shape is too small
    assert isinstance(placed, list)


# ============================================================================
# compute_gradient_v
# ============================================================================


def test_gradient_v_down_bigger_at_top(loader):
    shape = Circle(100, 100, 50)
    placed, _ = compute_gradient_v(
        "永一" * 20, shape, loader,
        min_size_mm=4, max_size_mm=14, direction="down",
    )
    assert len(placed) > 0
    # First row at top should have larger size than last row
    top_y = min(p[2] for p in placed)
    bot_y = max(p[2] for p in placed)
    top_sizes = [p[3] for p in placed if abs(p[2] - top_y) < 0.5]
    bot_sizes = [p[3] for p in placed if abs(p[2] - bot_y) < 0.5]
    assert max(top_sizes) > min(bot_sizes)


def test_gradient_v_up_reverses(loader):
    shape = Circle(100, 100, 50)
    placed, _ = compute_gradient_v(
        "永一" * 20, shape, loader,
        min_size_mm=4, max_size_mm=14, direction="up",
    )
    if len(placed) >= 4:
        top_y = min(p[2] for p in placed)
        bot_y = max(p[2] for p in placed)
        top_sizes = [p[3] for p in placed if abs(p[2] - top_y) < 0.5]
        bot_sizes = [p[3] for p in placed if abs(p[2] - bot_y) < 0.5]
        assert max(bot_sizes) >= min(top_sizes)


# ============================================================================
# compute_split_lr
# ============================================================================


def test_split_lr_separates_texts(loader):
    shape = Circle(100, 100, 50)
    placed, _ = compute_split_lr(
        "永永永", "一一一",
        shape, char_size_mm=10, char_loader=loader,
    )
    assert len(placed) > 0
    midx = 100
    left_chars = [p for p in placed if p[1] < midx]
    right_chars = [p for p in placed if p[1] >= midx]
    # Both halves should have some chars if shape big enough
    assert len(left_chars) > 0
    assert len(right_chars) > 0


# ============================================================================
# three_band
# ============================================================================


def test_three_band_capacity_returns_three_keys():
    shape = Circle(100, 100, 80)
    info = three_band_capacity(shape, char_size_mm=8)
    assert "top" in info and "mid" in info and "bot" in info
    assert info["top"] > 0 and info["mid"] > 0 and info["bot"] > 0


def test_three_band_requires_circle_or_ellipse():
    shape = make_shape("hexagon", 100, 100, 100)
    with pytest.raises(ValueError):
        three_band_capacity(shape, char_size_mm=8)


def test_three_band_places_all_three_segments(loader):
    shape = Circle(100, 100, 70)
    placed, missing = compute_three_band(
        "永" * 6, "一日永", "永日一永",
        shape, char_size_mm=8, char_loader=loader,
    )
    assert len(placed) > 0
    assert missing == []
    # Separate by y: top < cy, mid ≈ cy, bot > cy
    cy = 100
    top_chars = [p for p in placed if p[2] < cy - 5]
    mid_chars = [p for p in placed if abs(p[2] - cy) <= 1]
    bot_chars = [p for p in placed if p[2] > cy + 5]
    assert len(top_chars) > 0
    assert len(mid_chars) > 0
    assert len(bot_chars) > 0


def test_three_band_mid_chars_are_upright(loader):
    shape = Circle(100, 100, 70)
    placed, _ = compute_three_band(
        "", "一永日", "",
        shape, char_size_mm=8, char_loader=loader,
    )
    # All placements should be the middle line: upright (rot=0)
    assert all(p[4] == 0.0 for p in placed)


def test_three_band_with_ellipse(loader):
    shape = Ellipse(100, 100, 80, 40)
    placed, _ = compute_three_band(
        "永永永", "一永", "日日日",
        shape, char_size_mm=6, char_loader=loader,
    )
    assert len(placed) > 0


# Phase 5f — per-segment orient


def test_three_band_rotation_helper_arc():
    from stroke_order.exporters.wordart import _three_band_rotation
    # At top (outward=270°): bottom_to_center gives upright glyph (rot 0)
    assert _three_band_rotation("bottom_to_center", 270) == 0.0
    # top_to_center should give 180° (glyph upside down at top)
    assert _three_band_rotation("top_to_center", 270) == 180.0
    # At arbitrary outward: the two orients always differ by exactly 180°
    for outward in (0, 45, 90, 135, 180, 225, 315):
        b = _three_band_rotation("bottom_to_center", outward)
        t = _three_band_rotation("top_to_center", outward)
        assert abs(((t - b) % 360) - 180.0) < 1e-6


def test_three_band_rotation_helper_mid():
    from stroke_order.exporters.wordart import _three_band_mid_rotation
    assert _three_band_mid_rotation("bottom_to_center") == 0.0
    assert _three_band_mid_rotation("top_to_center") == 180.0


def test_three_band_orient_top_inverts_rotation(loader):
    shape = Circle(100, 100, 70)
    placed_b, _ = compute_three_band(
        "永", "", "",
        shape, char_size_mm=8, char_loader=loader,
        orient_top="bottom_to_center",
    )
    placed_t, _ = compute_three_band(
        "永", "", "",
        shape, char_size_mm=8, char_loader=loader,
        orient_top="top_to_center",
    )
    # Both should place exactly 1 char
    assert len(placed_b) == 1 and len(placed_t) == 1
    rot_b = placed_b[0][4]
    rot_t = placed_t[0][4]
    # Exactly 180° apart
    assert abs(((rot_t - rot_b) % 360) - 180.0) < 1e-6


def test_three_band_orient_mid_upside_down(loader):
    shape = Circle(100, 100, 70)
    placed_up, _ = compute_three_band(
        "", "一永日", "",
        shape, char_size_mm=8, char_loader=loader,
        orient_mid="bottom_to_center",
    )
    placed_inv, _ = compute_three_band(
        "", "一永日", "",
        shape, char_size_mm=8, char_loader=loader,
        orient_mid="top_to_center",
    )
    # All upright chars → rot=0
    assert all(p[4] == 0.0 for p in placed_up)
    # All inverted chars → rot=180
    assert all(p[4] == 180.0 for p in placed_inv)


def test_three_band_orient_bot_independent(loader):
    shape = Circle(100, 100, 70)
    # Bot segment only — compare rotations
    placed_b, _ = compute_three_band(
        "", "", "永",
        shape, char_size_mm=8, char_loader=loader,
        orient_bot="bottom_to_center",
    )
    placed_t, _ = compute_three_band(
        "", "", "永",
        shape, char_size_mm=8, char_loader=loader,
        orient_bot="top_to_center",
    )
    assert len(placed_b) == 1 and len(placed_t) == 1
    assert abs(((placed_t[0][4] - placed_b[0][4]) % 360) - 180.0) < 1e-6


def test_three_band_default_orient_preserves_prior_behavior(loader):
    """Defaults (all bottom_to_center) should match the pre-5f behavior."""
    shape = Circle(100, 100, 70)
    placed, _ = compute_three_band(
        "永", "一", "日",
        shape, char_size_mm=8, char_loader=loader,
    )
    # Default all bottom_to_center:
    # Top arc at 12 o'clock: outward=270° → rot=0 (upright)
    top_char = [p for p in placed if p[2] < 100 - 5][0]
    assert abs(top_char[4]) < 1e-6
    # Mid at cy=100: rot=0
    mid_char = [p for p in placed if abs(p[2] - 100) < 1][0]
    assert mid_char[4] == 0.0
    # Bot arc at 6 o'clock: outward=90° → rot=180 (upside-down)
    bot_char = [p for p in placed if p[2] > 100 + 5][0]
    assert abs(bot_char[4] - 180.0) < 1e-6


def test_api_three_band_per_segment_orient(client):
    # Default request
    r1 = client.get(
        "/api/wordart?shape=circle&shape_size_mm=150&char_size_mm=8"
        "&layout=three_band&text_top=永&text_mid=&text_bot="
    )
    assert r1.status_code == 200
    # Same text with top_to_center
    r2 = client.get(
        "/api/wordart?shape=circle&shape_size_mm=150&char_size_mm=8"
        "&layout=three_band&text_top=永&text_mid=&text_bot="
        "&orient_top=top_to_center"
    )
    assert r2.status_code == 200
    # The SVGs must differ (different rotation)
    assert r1.content != r2.content


def test_api_three_band_rejects_invalid_orient(client):
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=150&char_size_mm=8"
        "&layout=three_band&orient_top=tangent"
    )
    # 'tangent' isn't allowed for three_band segments
    assert r.status_code == 422


# ============================================================================
# compute_linear_groups
# ============================================================================


def test_linear_groups_hex_two_groups(loader):
    shape = make_shape("hexagon", 100, 100, 150)
    placed, missing = compute_linear_groups(
        ["永永永永永永永", "一一一一一一一"],
        [[0, 1, 2], [3, 4, 5]],
        shape, char_size_mm=8,
        orient="bottom_to_center", char_loader=loader,
    )
    assert len(placed) >= 2
    assert missing == []


def test_linear_groups_empty_group_skipped(loader):
    shape = make_shape("hexagon", 100, 100, 150)
    placed, _ = compute_linear_groups(
        ["永永永", "", "一永"],
        [[0, 1], [2], [3, 4, 5]],
        shape, char_size_mm=10,
        orient="upright", char_loader=loader,
    )
    # Middle group with empty text produces no placements
    assert len(placed) > 0


def test_linear_groups_invalid_edge_index_ignored(loader):
    shape = make_shape("hexagon", 100, 100, 150)
    placed, _ = compute_linear_groups(
        ["永一"],
        [[0, 99, 1]],  # 99 should be silently skipped
        shape, char_size_mm=10,
        orient="upright", char_loader=loader,
    )
    assert isinstance(placed, list)


# ============================================================================
# compute_linear_ordered
# ============================================================================


def test_linear_ordered_edge_start_shifts_mapping(loader):
    shape = make_shape("hexagon", 100, 100, 140)
    texts = ["一", "永", "日", "一", "永", "日"]
    # Natural order: edge 0 gets text[0] = 一
    p_natural, _ = compute_linear_ordered(
        texts, shape, 20, "upright", loader,
        edge_start=0, edge_direction="cw",
    )
    # With edge_start=1 cw: edge 0 gets text[last] (wrapping) = 日
    p_shifted, _ = compute_linear_ordered(
        texts, shape, 20, "upright", loader,
        edge_start=1, edge_direction="cw",
    )
    if p_natural and p_shifted:
        # They should place different first chars
        char_nat = p_natural[0][0].char
        char_shift = p_shifted[0][0].char
        # With wrapping, edge 0 in shifted case gets text placed at index 0 of
        # order [1,2,3,4,5,0] — so texts_per_edge[5]=日 goes on edge 0
        # Actually compute_linear_ordered iterates compute_linear which iterates
        # edges 0..n-1; edge 0 gets remapped[0] which is texts[order.index(0)]
        # order[i]=(edge_start+i)%n → order=[1,2,3,4,5,0] → order.index(0)=5
        # → remapped[0] = texts[5] = 日
        assert char_nat == "一"
        assert char_shift == "日"


def test_linear_ordered_direction_ccw(loader):
    shape = make_shape("square", 100, 100, 150)
    texts = ["永", "一", "日", "永"]
    placed_cw, _ = compute_linear_ordered(
        texts, shape, 20, "upright", loader,
        edge_start=0, edge_direction="cw",
    )
    placed_ccw, _ = compute_linear_ordered(
        texts, shape, 20, "upright", loader,
        edge_start=0, edge_direction="ccw",
    )
    # Both should place chars; CW and CCW should produce different char-at-edge mappings
    assert len(placed_cw) > 0
    assert len(placed_ccw) > 0


def test_linear_ordered_wraps_edge_start(loader):
    shape = make_shape("hexagon", 100, 100, 140)
    # edge_start=10 should wrap mod 6 = 4
    placed, _ = compute_linear_ordered(
        ["永", "一", "永", "一", "永", "一"],
        shape, 20, "upright", loader,
        edge_start=10, edge_direction="cw",
    )
    assert isinstance(placed, list)


# ============================================================================
# wordcloud_capacity
# ============================================================================


def test_wordcloud_capacity_scales_with_shape():
    small = Circle(0, 0, 30)
    big = Circle(0, 0, 120)
    s_info = wordcloud_capacity(small, 5, 15)
    b_info = wordcloud_capacity(big, 5, 15)
    assert b_info["approx_max_tokens"] > s_info["approx_max_tokens"]


# ============================================================================
# Web API — Phase 5d endpoints
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


def test_api_three_band_capacity(client):
    r = client.get(
        "/api/wordart/capacity?shape=circle&shape_size_mm=150"
        "&char_size_mm=8&layout=three_band&mid_ratio=0.9"
    )
    assert r.status_code == 200
    d = r.json()
    assert "top" in d and "mid" in d and "bot" in d


def test_api_three_band_capacity_rejects_polygon(client):
    r = client.get(
        "/api/wordart/capacity?shape=hexagon&shape_size_mm=150"
        "&char_size_mm=8&layout=three_band"
    )
    assert r.status_code == 422


def test_api_wordart_three_band_render(client):
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=150&char_size_mm=8"
        "&layout=three_band&text_top=永一日永&text_mid=一永&text_bot=日永一"
    )
    assert r.status_code == 200
    assert int(r.headers.get("x-wordart-placed", "0")) > 0


def test_api_wordart_wordcloud(client):
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=160&layout=wordcloud"
        "&tokens=永:7|一:5|日:3&min_size_mm=6&max_size_mm=20"
    )
    assert r.status_code == 200
    assert int(r.headers.get("x-wordart-placed", "0")) > 0


def test_api_wordart_concentric(client):
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=160&char_size_mm=8"
        "&layout=concentric&texts_per_ring=" + "永" * 20 + "|" + "一" * 15
    )
    assert r.status_code == 200
    assert int(r.headers.get("x-wordart-placed", "0")) > 0


def test_api_wordart_gradient_v(client):
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=160&layout=gradient_v"
        "&text=" + "永一" * 30 + "&min_size_mm=5&max_size_mm=18"
    )
    assert r.status_code == 200
    assert int(r.headers.get("x-wordart-placed", "0")) > 0


def test_api_wordart_split_lr(client):
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=160&char_size_mm=10"
        "&layout=split_lr&text_left=永永永&text_right=一一一"
    )
    assert r.status_code == 200
    assert int(r.headers.get("x-wordart-placed", "0")) > 0


def test_api_wordart_edge_groups(client):
    r = client.get(
        "/api/wordart?shape=hexagon&shape_size_mm=160&char_size_mm=10"
        "&layout=linear&edge_groups=0,1,2|3,4,5"
        "&texts_per_edge=永永永永永永|一一一一一一"
    )
    assert r.status_code == 200
    assert int(r.headers.get("x-wordart-placed", "0")) > 0


def test_api_wordart_edge_start_direction(client):
    r = client.get(
        "/api/wordart?shape=hexagon&shape_size_mm=160&char_size_mm=12"
        "&layout=linear&texts_per_edge=一|永|日|一|永|日"
        "&edge_start=2&edge_direction=ccw"
    )
    assert r.status_code == 200


def test_api_wordart_capacity_wordcloud(client):
    r = client.get(
        "/api/wordart/capacity?shape=circle&shape_size_mm=150"
        "&layout=wordcloud&min_size_mm=5&max_size_mm=20"
    )
    assert r.status_code == 200
    d = r.json()
    assert "approx_max_tokens" in d


# ---------------------------------------------------------------------------
# Phase 5an — gradient_h / wave / radial_convex / radial_concave
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_loader():
    """Cheap loader that returns a minimal Character without g0v lookup.
    Layout tests only inspect (x, y, size, rotation) — not stroke geometry."""
    from stroke_order.ir import Character
    def _l(ch):
        return Character(char=ch, unicode_hex=f"{ord(ch):04x}",
                         data_source="stub")
    return _l


# --- gradient_h ---


def test_gradient_h_right_decreases_size_left_to_right(stub_loader):
    shape = Circle(80, 80, 60)
    placed, missing = compute_gradient_h(
        "一二三四五六七八九十", shape, stub_loader,
        min_size_mm=4, max_size_mm=18, direction="right",
    )
    assert missing == []
    assert len(placed) > 0
    # Sort by x, sizes should be non-increasing (within numerical noise).
    by_x = sorted(placed, key=lambda t: t[1])
    sizes = [t[3] for t in by_x]
    # Allow small jitter from per-column step rounding; assert overall trend.
    assert sizes[0] > sizes[-1]


def test_gradient_h_left_reverses_direction(stub_loader):
    shape = Circle(80, 80, 60)
    placed, _ = compute_gradient_h(
        "一二三四五六七八九十", shape, stub_loader,
        min_size_mm=4, max_size_mm=18, direction="left",
    )
    by_x = sorted(placed, key=lambda t: t[1])
    sizes = [t[3] for t in by_x]
    # Left direction → small at left, big at right
    assert sizes[0] < sizes[-1]


def test_gradient_h_auto_cycle_fills_more(stub_loader):
    shape = Circle(80, 80, 60)
    short_text = "永"
    p_no_cycle, _ = compute_gradient_h(
        short_text, shape, stub_loader, min_size_mm=4, max_size_mm=12,
        auto_cycle=False,
    )
    p_cycle, _ = compute_gradient_h(
        short_text, shape, stub_loader, min_size_mm=4, max_size_mm=12,
        auto_cycle=True,
    )
    assert len(p_cycle) > len(p_no_cycle)


def test_gradient_h_handles_empty_text(stub_loader):
    shape = Circle(80, 80, 60)
    placed, _ = compute_gradient_h("", shape, stub_loader,
                                    min_size_mm=4, max_size_mm=12)
    assert placed == []


# --- wave ---


def test_wave_produces_non_zero_tangent_rotations(stub_loader):
    shape = Circle(100, 100, 80)
    placed, missing = compute_wave(
        "天地玄黃宇宙洪荒日月盈昃辰宿列張", shape,
        char_size_mm=10, char_loader=stub_loader,
        amplitude_mm=12, wavelength_mm=60, wave_lines=2,
        tangent_rotation=True,
    )
    assert missing == []
    assert len(placed) > 0
    rotations = [t[4] for t in placed]
    # Some rotations must be non-zero (curve has non-zero slope somewhere).
    assert any(abs(r) > 0.5 for r in rotations)


def test_wave_tangent_off_keeps_chars_upright(stub_loader):
    shape = Circle(100, 100, 80)
    placed, _ = compute_wave(
        "天地玄黃宇宙洪荒", shape,
        char_size_mm=10, char_loader=stub_loader,
        amplitude_mm=12, wavelength_mm=60, wave_lines=2,
        tangent_rotation=False,
    )
    rotations = [t[4] for t in placed]
    assert all(abs(r) < 1e-6 for r in rotations)


def test_wave_more_lines_yields_more_slots(stub_loader):
    shape = Circle(100, 100, 80)
    p1, _ = compute_wave(
        "永" * 200, shape, char_size_mm=8, char_loader=stub_loader,
        wave_lines=1,
    )
    p3, _ = compute_wave(
        "永" * 200, shape, char_size_mm=8, char_loader=stub_loader,
        wave_lines=3,
    )
    assert len(p3) > len(p1)


def test_wave_zero_amplitude_collapses_to_horizontal_lines(stub_loader):
    """A=0 must still produce slots (sin term zero) and rotation 0."""
    shape = Circle(100, 100, 80)
    placed, _ = compute_wave(
        "永" * 50, shape, char_size_mm=10, char_loader=stub_loader,
        amplitude_mm=0, wavelength_mm=40, wave_lines=2,
    )
    assert len(placed) > 0
    assert all(abs(t[4]) < 1e-6 for t in placed)


def test_wave_rejects_non_positive_wavelength(stub_loader):
    shape = Circle(100, 100, 80)
    placed, _ = compute_wave(
        "永永", shape, char_size_mm=10, char_loader=stub_loader,
        wavelength_mm=0,
    )
    assert placed == []


# --- radial_convex / radial_concave ---


def test_radial_convex_largest_chars_near_centre(stub_loader):
    shape = Circle(100, 100, 80)
    placed, missing = compute_radial_gradient(
        "春夏秋冬東西南北", shape, stub_loader,
        min_size_mm=4, max_size_mm=20, direction="convex",
    )
    assert missing == []
    assert len(placed) > 0
    # Sort by distance from centre; the closest cell must have the
    # largest size in the placed set.
    def dist(t): return math.hypot(t[1] - 100, t[2] - 100)
    by_dist = sorted(placed, key=dist)
    assert by_dist[0][3] >= by_dist[-1][3]


def test_radial_concave_smallest_chars_near_centre(stub_loader):
    shape = Circle(100, 100, 80)
    placed, _ = compute_radial_gradient(
        "春夏秋冬東西南北", shape, stub_loader,
        min_size_mm=4, max_size_mm=20, direction="concave",
    )
    def dist(t): return math.hypot(t[1] - 100, t[2] - 100)
    by_dist = sorted(placed, key=dist)
    # First placed (largest in greedy order) lands away from centre.
    # Smallest in the placed set should be the closest.
    assert by_dist[0][3] <= by_dist[-1][3]


def test_radial_gradient_auto_cycle_fills_more(stub_loader):
    shape = Circle(100, 100, 80)
    p_no, _ = compute_radial_gradient(
        "永", shape, stub_loader,
        min_size_mm=6, max_size_mm=20, direction="convex",
        auto_cycle=False,
    )
    p_yes, _ = compute_radial_gradient(
        "永", shape, stub_loader,
        min_size_mm=6, max_size_mm=20, direction="convex",
        auto_cycle=True,
    )
    assert len(p_yes) > len(p_no)


def test_radial_gradient_rejects_invalid_size_range(stub_loader):
    shape = Circle(100, 100, 80)
    placed, _ = compute_radial_gradient(
        "永", shape, stub_loader, min_size_mm=20, max_size_mm=4,
    )
    assert placed == []


def test_radial_gradient_no_overlap_between_placed_cells(stub_loader):
    """Greedy collision-avoidance: no two placed cells' AABBs overlap."""
    shape = Circle(100, 100, 80)
    placed, _ = compute_radial_gradient(
        "天地玄黃宇宙洪荒日月盈昃辰宿列張寒來暑往秋收冬藏", shape, stub_loader,
        min_size_mm=4, max_size_mm=20, direction="convex",
        auto_cycle=True,
    )
    aabbs = [(t[1] - t[3] / 2, t[2] - t[3] / 2,
              t[1] + t[3] / 2, t[2] + t[3] / 2) for t in placed]
    for i, a in enumerate(aabbs):
        for b in aabbs[i + 1:]:
            assert (a[2] <= b[0] or a[0] >= b[2]
                    or a[3] <= b[1] or a[1] >= b[3]), \
                "two placed cells overlap"
