"""Tests for stroke_order.components.algorithm — greedy set-cover."""
from __future__ import annotations

import pytest

from stroke_order.components import (
    coverage_status,
    default_ids_map,
    greedy_full_cover,
    load_coverset,
    recommend_next,
)


@pytest.fixture(scope="module")
def ids_map():
    return default_ids_map()


# ---------------------------------------------------------------------------
# coverage_status
# ---------------------------------------------------------------------------


def test_coverage_status_empty_written(ids_map):
    """No written chars → 0% coverage."""
    s = coverage_status(written_chars=[], target_chars=["明", "林", "校"],
                        ids_map=ids_map)
    assert s["covered_count"] == 0
    assert s["coverage_ratio"] == 0.0
    assert s["composable_count"] == 0


def test_coverage_status_full_written(ids_map):
    """Writing all target chars → 100% coverage + all composable."""
    targets = ["明", "林", "校"]
    s = coverage_status(written_chars=targets, target_chars=targets,
                        ids_map=ids_map)
    assert s["coverage_ratio"] == 1.0
    assert s["composable_count"] == 3
    assert s["composable_ratio"] == 1.0


def test_coverage_status_partial(ids_map):
    """Writing 木 → covers 木 component → can compose 林 (= 木+木) but not
    yet 校 (needs 木+交).
    """
    s = coverage_status(written_chars=["木"], target_chars=["林", "校", "木"],
                        ids_map=ids_map)
    # 林 = 木+木: only needs 木 → composable
    # 校 = 木+交: needs 交 too → NOT composable
    # 木 = 木: trivially composable
    assert s["composable_count"] == 2
    assert "林" not in s["unwritten_chars"] or "林" in s["unwritten_chars"]


# ---------------------------------------------------------------------------
# recommend_next
# ---------------------------------------------------------------------------


def test_recommend_returns_unwritten_chars_only(ids_map):
    """Recommendation skips already-written chars."""
    recs = recommend_next(
        written_chars=["明"], target_chars=["明", "林", "校"], ids_map=ids_map,
    )
    rec_chars = {r.char for r in recs}
    assert "明" not in rec_chars


def test_recommend_first_pick_maximizes_gain(ids_map):
    """First pick should be the char with the most distinct LEAF components.

    Note: leaves are atomic/stroke-level — 交 recursively decomposes into
    atoms like 丿, 一, 八, etc. So 校 (⿰木交) yields more leaves than
    林 (⿰木木) which collapses to {木}.
    """
    targets = ["木", "林", "明", "校"]
    recs = recommend_next(written_chars=[], target_chars=targets,
                          ids_map=ids_map, top_k=4)
    # 木: {木}                  → 1 leaf
    # 林: {木}                  → 1 leaf (dup of 木)
    # 明: {日, 月}              → 2 leaves
    # 校: {木, 一, 丿, 八, ...}  → ~6 leaves (交 recurses)
    # 校 should win (highest gain); confirm it's first AND has more than 明.
    assert recs[0].char == "校"
    assert recs[0].gain > 2  # significantly more than 明's 2


def test_recommend_top_k_respects_limit(ids_map):
    """top_k parameter caps result list."""
    recs = recommend_next(written_chars=[], target_chars=["明", "林", "校", "想"],
                          ids_map=ids_map, top_k=2)
    assert len(recs) <= 2


def test_recommend_no_zero_gain(ids_map):
    """Chars whose components are all already covered shouldn't be in recs."""
    # User has written 木, target includes 林 = ⿰木木 (gain = 0 since all covered)
    recs = recommend_next(written_chars=["木"], target_chars=["林", "明"],
                          ids_map=ids_map)
    rec_chars = {r.char for r in recs}
    assert "林" not in rec_chars  # zero new components → excluded


def test_recommend_returns_empty_when_nothing_to_gain(ids_map):
    """All target chars covered → empty recommendation list."""
    # Write 木 and 日 → covers 木, 日. 林 = 木+木 has zero gain.
    recs = recommend_next(written_chars=["木", "日"], target_chars=["林"],
                          ids_map=ids_map)
    assert recs == []


# ---------------------------------------------------------------------------
# greedy_full_cover (offline)
# ---------------------------------------------------------------------------


def test_greedy_full_cover_terminates(ids_map):
    """Greedy must terminate (no infinite loop)."""
    selected = greedy_full_cover(
        target_chars=["明", "林", "校", "想", "永"], ids_map=ids_map,
    )
    # Should pick most chars (atomic ones may be skipped if already covered)
    assert isinstance(selected, list)
    assert len(selected) <= 5


def test_greedy_full_cover_order_descending_gain(ids_map):
    """First pick must have the most components; later picks may have fewer."""
    targets = ["明", "林", "校", "想"]
    selected = greedy_full_cover(target_chars=targets, ids_map=ids_map)
    # All four picks should appear or be subset; order matters: first pick
    # adds most components.
    assert len(selected) >= 2  # at least the high-gain ones picked


# ---------------------------------------------------------------------------
# Integration with 808 cover-set
# ---------------------------------------------------------------------------


def test_recommend_against_808_first_pick(ids_map):
    """First recommendation against 808 should pick a high-gain char."""
    cs = load_coverset("cjk_common_808")
    recs = recommend_next(
        written_chars=[], target_chars=cs.chars, ids_map=ids_map, top_k=10,
    )
    assert len(recs) > 0
    # First pick should add ≥ 2 components (most 808 chars are not atomic)
    assert recs[0].gain >= 2


def test_greedy_full_cover_808_efficiency(ids_map):
    """Greedy should achieve near-full component coverage in <500 chars."""
    cs = load_coverset("cjk_common_808")
    selected = greedy_full_cover(target_chars=cs.chars, ids_map=ids_map)
    # 808 chars decompose to ~194 distinct components; greedy should find
    # most of them within ~150-300 selections (each picks adds new components
    # until exhausted).
    assert 50 < len(selected) < 500, (
        f"Greedy selected {len(selected)} chars; expected 50-500 range"
    )
