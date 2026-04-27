import pytest

from stroke_order.sources.g0v import CharacterNotFound, G0VSource


def test_load_yong(source: G0VSource):
    c = source.get_character("永")
    assert c.char == "永"
    assert c.unicode_hex == "6c38"
    assert c.stroke_count == 5
    assert c.data_source == "g0v"
    for s in c.strokes:
        assert len(s.raw_track) >= 2
        assert len(s.outline) > 0


def test_load_yi(source: G0VSource):
    c = source.get_character("一")
    assert c.unicode_hex == "4e00"
    assert c.stroke_count == 1


def test_load_en(source: G0VSource):
    c = source.get_character("恩")
    assert c.stroke_count == 10
    # first stroke: 豎 of 因, should have ≥ 2 pts going down
    s0 = c.strokes[0]
    dy = s0.raw_track[-1].y - s0.raw_track[0].y
    assert dy > 500  # going down substantially


def test_not_found_cache_only(source: G0VSource):
    # 鱻 (U+9C7B) is very unlikely to be cached in fixtures
    with pytest.raises(CharacterNotFound):
        source.get_character("鱻")


def test_invalid_input_length(source: G0VSource):
    with pytest.raises(ValueError):
        source.get_character("兩字")
