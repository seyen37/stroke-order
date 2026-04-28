"""Tests for stroke_order.components.coverset — built-in & custom cover-sets."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from stroke_order.components import (
    CoverSet,
    collect_components,
    default_ids_map,
    list_coversets,
    load_coverset,
    load_coverset_from_path,
)


# ---------------------------------------------------------------------------
# Built-in registry
# ---------------------------------------------------------------------------


def test_list_coversets_includes_808():
    """The 808 cover-set must be a built-in."""
    metas = list_coversets()
    names = [m["name"] for m in metas]
    assert "cjk_common_808" in names


def test_list_coversets_metadata_shape():
    """Every metadata entry has expected keys."""
    metas = list_coversets()
    expected_keys = {"name", "title", "description", "size", "source", "url"}
    for m in metas:
        assert expected_keys.issubset(m.keys()), f"missing keys in {m!r}"


def test_load_coverset_unknown_raises():
    with pytest.raises(KeyError):
        load_coverset("nonexistent_set_xyz")


# ---------------------------------------------------------------------------
# 808 cover-set content
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cs808() -> CoverSet:
    return load_coverset("cjk_common_808")


def test_cs808_has_808_chars(cs808):
    assert cs808.size == 808
    assert len(cs808.chars) == 808
    assert len(cs808.chars_simp) == 808


def test_cs808_metadata_present(cs808):
    """Sanity-check provenance fields aren't empty."""
    assert "808" in cs808.title or "八百" in cs808.title
    assert cs808.source  # non-empty


def test_cs808_known_chars_present(cs808):
    """A few well-known chars must be in the 808 list."""
    chars_set = set(cs808.chars)
    for c in "一人木日月明永":
        assert c in chars_set, f"{c} should be in 808 trad list"


def test_cs808_simp_trad_alignment(cs808):
    """Each entry has matching simp/trad position."""
    # 来 / 來 is a known simp/trad pair at index 39 (1-indexed)
    idx = cs808.chars_simp.index("来")
    assert cs808.chars[idx] == "來"


# ---------------------------------------------------------------------------
# Custom cover-set loader (round-trip)
# ---------------------------------------------------------------------------


def test_custom_coverset_round_trip(tmp_path):
    """Loading a hand-rolled JSON file works end-to-end."""
    fake = {
        "title": "Test Set",
        "description": "Tiny test set",
        "source": "unit test",
        "url": "https://example.com",
        "entries": [
            {"index": 1, "simp": "一", "trad": "一", "same": True},
            {"index": 2, "simp": "二", "trad": "二", "same": True},
            {"index": 3, "simp": "来", "trad": "來", "same": False},
        ],
    }
    p = tmp_path / "tiny_set.json"
    p.write_text(json.dumps(fake, ensure_ascii=False), encoding="utf-8")

    cs = load_coverset_from_path(p)
    assert cs.name == "tiny_set"
    assert cs.size == 3
    assert cs.chars == ("一", "二", "來")
    assert cs.chars_simp == ("一", "二", "来")
    assert cs.source == "unit test"


# ---------------------------------------------------------------------------
# Integration: 808 chars decompose to ~194 distinct components (per analysis)
# ---------------------------------------------------------------------------


def test_cs808_distinct_components_in_expected_range(cs808):
    """Sanity: 808 chars should decompose to roughly 150-250 distinct
    leaf components (per docs/analysis/808_coverage_report.md the number
    is 194; allow ±25% for future ids-data drift)."""
    ids_map = default_ids_map()
    components = collect_components(cs808.chars, ids_map)
    assert 150 <= len(components) <= 250, (
        f"Expected ~194 distinct components, got {len(components)}. "
        "If far off, regenerate docs/analysis/808_coverage_report.md "
        "and update VISION.md."
    )
