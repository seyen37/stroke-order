"""Tests for the MMH adapter.

These tests require ``data/mmh_cache/graphics.txt`` to exist (either seeded
or downloaded). They are skipped if the file is missing so that a fresh
checkout's test run doesn't need the 30 MB download.
"""
from pathlib import Path

import pytest

from stroke_order.ir import EM_SIZE
from stroke_order.sources.mmh import MMHSource

# Check up-front whether MMH data is available
_MMH_CACHE = Path(__file__).resolve().parents[1] / "data" / "mmh_cache" / "graphics.txt"
_NO_MMH = not _MMH_CACHE.is_file()


pytestmark = pytest.mark.skipif(
    _NO_MMH,
    reason="MMH graphics.txt not cached (run once with --allow-network)"
)


@pytest.fixture(scope="module")
def mmh() -> MMHSource:
    return MMHSource(allow_network=False)


def test_char_count(mmh):
    assert mmh.char_count() > 9000


def test_load_yong(mmh):
    c = mmh.get_character("永")
    assert c.char == "永"
    assert c.stroke_count == 5
    assert c.data_source == "mmh"
    # coords should be inside the canonical em
    bb = c.bbox
    assert 0 <= bb.x_min and bb.x_max <= EM_SIZE
    assert 0 <= bb.y_min and bb.y_max <= EM_SIZE


def test_load_yi(mmh):
    c = mmh.get_character("一")
    assert c.stroke_count == 1
    # 一 should sit horizontally near mid-height
    s = c.strokes[0]
    assert len(s.raw_track) >= 2


def test_has_character(mmh):
    assert mmh.has_character("永")
    # U+E000 is Private Use Area — guaranteed never in any Chinese font dataset
    assert not mmh.has_character("\ue000")


def test_simplified_only_char(mmh):
    """们 is simplified-only; should be in MMH but not in g0v."""
    c = mmh.get_character("们")
    assert c.stroke_count == 5


def test_parse_cubic_bezier_path(mmh):
    """MMH uses C (cubic Bezier) commands extensively; verify they parse."""
    c = mmh.get_character("永")
    for stroke in c.strokes:
        types = {cmd.get("type") for cmd in stroke.outline}
        # most MMH strokes include at least one C or Q
        if any(t in types for t in ("C", "Q")):
            return
    pytest.fail("expected at least one stroke with C or Q command in 永")
