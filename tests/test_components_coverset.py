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


# ---------------------------------------------------------------------------
# wuqian_5000 cover-set (6b-11)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cs_wuqian() -> CoverSet:
    return load_coverset("wuqian_5000")


def test_list_coversets_includes_wuqian():
    metas = list_coversets()
    names = [m["name"] for m in metas]
    assert "wuqian_5000" in names


def test_wuqian_size_in_expected_range(cs_wuqian):
    """Should be ~3,700-3,800 after CJK filter from raw ~3,719 entries."""
    assert 3500 <= cs_wuqian.size <= 4000


def test_wuqian_metadata(cs_wuqian):
    assert "5000" in cs_wuqian.title or "漢字基因" in cs_wuqian.title
    assert "朱邦復" in cs_wuqian.source or "字易" in cs_wuqian.source


def test_wuqian_known_chars_present(cs_wuqian):
    """Spot-check well-known chars that 朱邦復's 5000 set should include.

    Note: 朱邦復's curation is selective — even seemingly-canonical 會意
    chars like 林 (⿰木木) and 想 (心+相) are NOT in the set. Stick to
    pure 象形 chars empirically verified to be in the source file.
    """
    chars_set = set(cs_wuqian.chars)
    for c in "明日月人木火山水":
        assert c in chars_set, f"{c} should be in 漢字基因 5000"


def test_wuqian_distinct_components_larger_than_808(cs_wuqian, cs808):
    """wuqian_5000 has more chars than 808 → should yield more components.

    Sanity: the larger curated set should provide more decomposition
    breadth than the 808 high-frequency set.
    """
    ids_map = default_ids_map()
    comps_808 = collect_components(cs808.chars, ids_map)
    comps_wuqian = collect_components(cs_wuqian.chars, ids_map)
    assert len(comps_wuqian) > len(comps_808), (
        f"wuqian ({len(comps_wuqian)}) should have more components "
        f"than 808 ({len(comps_808)})"
    )


# ---------------------------------------------------------------------------
# educational_4808 cover-set (6b-11 — 教育部常用國字標準字體表)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cs_edu() -> CoverSet:
    return load_coverset("educational_4808")


def test_list_coversets_includes_edu_4808():
    metas = list_coversets()
    names = [m["name"] for m in metas]
    assert "educational_4808" in names


def test_edu_4808_exact_size(cs_edu):
    """MOE 標準表 is exactly 4,808 chars (this is in the title)."""
    assert cs_edu.size == 4808


def test_edu_4808_metadata(cs_edu):
    assert "教育部" in cs_edu.title or "MOE" in cs_edu.title.upper()
    assert "4808" in cs_edu.title or "4,808" in cs_edu.source


def test_edu_4808_known_chars(cs_edu):
    """High-frequency chars must be in the MOE standard set."""
    chars_set = set(cs_edu.chars)
    for c in "明林日月人木火想山水永":
        assert c in chars_set, f"{c} should be in 教育部 4808"


def test_edu_4808_distinct_components_more_than_808(cs_edu, cs808):
    """4808 chars > 808 chars → more distinct components."""
    ids_map = default_ids_map()
    comps_808 = collect_components(cs808.chars, ids_map)
    comps_edu = collect_components(cs_edu.chars, ids_map)
    assert len(comps_edu) > len(comps_808)
