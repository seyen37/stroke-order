"""Tests for region flag and RegionAutoSource."""
import pytest

from stroke_order.sources import (
    CharacterNotFound,
    G0VSource,
    KanjiVGSource,
    MMHSource,
    RegionAutoSource,
    make_source,
)


def test_make_source_region_codes():
    assert isinstance(make_source("tw"), RegionAutoSource)
    assert isinstance(make_source("cn"), RegionAutoSource)
    assert isinstance(make_source("jp"), RegionAutoSource)


def test_region_tw_prefers_g0v():
    s = RegionAutoSource("tw")
    # first source should be G0VSource
    assert isinstance(s._sources[0], G0VSource)


def test_region_cn_prefers_mmh():
    s = RegionAutoSource("cn")
    assert isinstance(s._sources[0], MMHSource)


def test_region_jp_prefers_kanjivg():
    s = RegionAutoSource("jp")
    assert isinstance(s._sources[0], KanjiVGSource)


def test_invalid_region():
    with pytest.raises(ValueError, match="unknown region"):
        RegionAutoSource("xx")  # type: ignore[arg-type]


def test_make_source_unknown():
    with pytest.raises(ValueError, match="unknown source"):
        make_source("bogus")
