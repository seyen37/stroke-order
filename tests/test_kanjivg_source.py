"""Tests for the KanjiVG source adapter."""
import pytest

from stroke_order.ir import EM_SIZE
from stroke_order.sources.kanjivg import KanjiVGSource


@pytest.fixture(scope="module")
def kvg() -> KanjiVGSource:
    # Network required for first use; subsequent use is cached
    return KanjiVGSource()


def test_load_yong(kvg):
    c = kvg.get_character("永")
    assert c.stroke_count == 5
    assert c.data_source == "kanjivg"
    # coords must be within canonical em after 109→2048 scaling
    bb = c.bbox
    assert 0 <= bb.x_min and bb.x_max <= EM_SIZE
    assert 0 <= bb.y_min and bb.y_max <= EM_SIZE


def test_japanese_only_kanji(kvg):
    """働 (U+50CD, hataraku) — Japanese-only, not in traditional dicts."""
    c = kvg.get_character("働")
    assert c.stroke_count >= 10
    assert c.data_source == "kanjivg"


def test_paths_are_centerlines(kvg):
    """KanjiVG paths are centerlines — track should have multiple pts per stroke."""
    c = kvg.get_character("永")
    for s in c.strokes:
        # Each stroke should have >= 2 points (from the parsed path)
        assert len(s.raw_track) >= 2
