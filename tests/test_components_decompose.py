"""Tests for stroke_order.components.decompose — recursive leaf extraction."""
from __future__ import annotations

import pytest

from stroke_order.components import (
    collect_components,
    covers,
    decompose,
    default_ids_map,
    get_leaf_components,
    is_atomic,
)


@pytest.fixture(scope="module")
def ids_map():
    return default_ids_map()


# ---------------------------------------------------------------------------
# Atomic chars
# ---------------------------------------------------------------------------


def test_atomic_decomposes_to_self(ids_map):
    """Atomic chars (no IDS structure) decompose to a singleton list."""
    for c in "永一木日月":
        assert decompose(c, ids_map) == [c]
        assert is_atomic(c, ids_map)


def test_atomic_get_leaf_components_singleton(ids_map):
    assert get_leaf_components("永", ids_map) == {"永"}


# ---------------------------------------------------------------------------
# Two-component compounds (left-right, top-bottom)
# ---------------------------------------------------------------------------


def test_ming_decomposes_sun_moon(ids_map):
    """明 = ⿰日月  → 日, 月  (both atomic)."""
    leaves = decompose("明", ids_map)
    assert leaves == ["日", "月"]


def test_lin_decomposes_to_two_woods(ids_map):
    """林 = ⿰木木  → preserves duplicate."""
    leaves = decompose("林", ids_map)
    assert leaves == ["木", "木"]
    assert get_leaf_components("林", ids_map) == {"木"}


def test_xiao_decomposes_to_wood_jiao(ids_map):
    """校 = ⿰木交."""
    leaves = decompose("校", ids_map)
    # 交 itself may further decompose; check 木 is present and 交 OR its
    # leaves are present
    assert "木" in leaves
    assert len(leaves) >= 2


def test_zhang_decomposes_li_zao(ids_map):
    """章 = ⿱立早."""
    leaves = decompose("章", ids_map)
    # 立 may be atomic or further decompose; 早 = ⿱日十
    leaves_set = set(leaves)
    # The structure should at minimum surface 日 and 十
    assert "日" in leaves_set or "立" in leaves_set


# ---------------------------------------------------------------------------
# Cycle prevention & depth limits
# ---------------------------------------------------------------------------


def test_cycle_safe_decomposition():
    """Synthetic cyclic IDS map shouldn't infinite-loop."""
    # A → ⿰AB, B → atomic
    ids = {"A": "⿰AB", "B": "B"}
    result = decompose("A", ids)
    # First A is the recursion entry; second A in IDS is a self-reference
    # that should hit the _seen guard and become atomic.
    assert "A" in result
    assert "B" in result


def test_max_depth_limits_recursion():
    """Deeply nested IDS chains terminate at max_depth."""
    # Linear chain: A → B → C → D → E → atom
    ids = {"A": "⿰B一", "B": "⿰C二", "C": "⿰D三", "D": "⿰E四", "E": "E"}
    leaves = decompose("A", ids, max_depth=2)
    # max_depth=2: decompose A (depth 0) → B,一; decompose B (depth 1) → C,二;
    # decompose C (depth 2) hits limit → returns [C]
    assert "C" in leaves


# ---------------------------------------------------------------------------
# collect_components / covers helpers
# ---------------------------------------------------------------------------


def test_collect_components_union(ids_map):
    """Union across multiple chars."""
    s = collect_components(["明", "林", "校"], ids_map)
    # 明: 日 月; 林: 木; 校: 木 交...
    assert "日" in s
    assert "月" in s
    assert "木" in s


def test_covers_true_when_subset(ids_map):
    """A char is 'covered' when all its leaves are available."""
    # Available = leaves of 明, 林, 校
    available = collect_components(["明", "林", "校"], ids_map)
    # 明 is trivially covered by its own leaves
    assert covers("明", available, ids_map)
    assert covers("林", available, ids_map)


def test_covers_false_when_missing(ids_map):
    """Char with components not in available set → not covered."""
    available = {"日"}  # only 日
    assert not covers("月", available, ids_map)
    assert covers("日", available, ids_map)


# ---------------------------------------------------------------------------
# 808 set sanity (smoke test using bundled cover-set will live in coverset
# test file once 6b-3 lands; this keeps decompose-only scope clean)
# ---------------------------------------------------------------------------


def test_808_known_chars_decompose_correctly(ids_map):
    """Spot-check chars from the 808 list have expected decompositions."""
    # 想 = ⿱相心 → 相 = ⿰木目 → so 想 leaves include 木, 目, 心
    leaves = set(decompose("想", ids_map))
    assert "心" in leaves
    # 樹 = ⿰木⿱壴寸 → leaves include 木, 寸 (壴 may decompose further)
    leaves = set(decompose("樹", ids_map))
    assert "木" in leaves
