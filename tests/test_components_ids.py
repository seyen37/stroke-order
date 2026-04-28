"""Tests for stroke_order.components.ids — IDS parser + bundled loader."""
from __future__ import annotations

import pytest

from stroke_order.components.ids import (
    COMPOUND_MARKERS,
    IDS_DESCRIPTORS,
    VARIATION_SELECTORS,
    default_ids_map,
    parse_ids_file,
)


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------


def test_ids_descriptors_includes_basic_12():
    """Standard 12 IDS descriptors U+2FF0–U+2FFB."""
    for c in "⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻":
        assert c in IDS_DESCRIPTORS, f"{c} ({hex(ord(c))}) missing"


def test_ids_descriptors_no_cjk_chars():
    """Descriptor set must not accidentally contain CJK ideographs."""
    for c in "明月日木一人":
        assert c not in IDS_DESCRIPTORS


def test_variation_selector_regex_strips_only_vs():
    """VARIATION_SELECTORS strips U+FE00–U+FE0F only, leaves CJK alone."""
    cjk = "⿰日月"
    assert VARIATION_SELECTORS.sub("", cjk) == cjk

    # Real variation selector (U+FE0E)
    text_with_vs = "字︎"
    assert VARIATION_SELECTORS.sub("", text_with_vs) == "字"


def test_compound_markers_match_circled_digits():
    """COMPOUND_MARKERS matches ①-⑳ used as unencoded-component placeholders."""
    assert COMPOUND_MARKERS.match("①")
    assert COMPOUND_MARKERS.match("⑳")
    assert not COMPOUND_MARKERS.match("木")


# ---------------------------------------------------------------------------
# Parser correctness
# ---------------------------------------------------------------------------


def test_parse_ids_file_basic(tmp_path):
    """Round-trip: write a small ids.txt, parse, verify."""
    ids_text = (
        "# comment line\n"
        "U+660E\t明\t⿰日月\n"
        "U+6797\t林\t⿰木木\n"
        "U+6C38\t永\t永\n"  # atomic
        "U+4E0E\t与\t⿹②一[GTKV]\t⿻②一[J]\n"  # multi-region: keep first
    )
    p = tmp_path / "test_ids.txt"
    p.write_text(ids_text, encoding="utf-8")

    m = parse_ids_file(p)
    assert m["明"] == "⿰日月"
    assert m["林"] == "⿰木木"
    assert m["永"] == "永"
    # First-region IDS, region tag stripped
    assert m["与"] == "⿹②一"


def test_parse_ids_file_skips_comments_and_short_lines(tmp_path):
    p = tmp_path / "test_ids.txt"
    p.write_text(
        "# header\n"
        "\n"
        "U+TOOSHORT\n"
        "U+6797\t林\t⿰木木\n",
        encoding="utf-8",
    )
    m = parse_ids_file(p)
    assert len(m) == 1
    assert m["林"] == "⿰木木"


# ---------------------------------------------------------------------------
# Bundled snapshot — sanity & content checks
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ids_map() -> dict[str, str]:
    """Load the bundled cjkvi-ids snapshot once per module."""
    return default_ids_map()


def test_default_ids_map_size(ids_map):
    """Bundled snapshot covers a reasonable number of chars."""
    # cjkvi-ids master had ~88,000 entries when bundled. Allow 50k-150k range
    # so future snapshot updates don't break tests.
    assert 50_000 < len(ids_map) < 200_000


def test_default_ids_map_known_decompositions(ids_map):
    """Spot-check well-known decompositions."""
    assert ids_map["明"] == "⿰日月"
    assert ids_map["林"] == "⿰木木"
    assert ids_map["校"] == "⿰木交"
    assert ids_map["章"] == "⿱立早"


def test_default_ids_map_atomic_chars(ids_map):
    """Atomic chars decompose to themselves."""
    for c in "永一木日月":
        assert ids_map.get(c) == c, f"{c} should be atomic, got {ids_map.get(c)!r}"


def test_default_ids_map_caches(ids_map):
    """Calling twice returns the same dict object (lru_cache)."""
    again = default_ids_map()
    assert again is ids_map
