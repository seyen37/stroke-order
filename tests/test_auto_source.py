"""Tests for AutoSource and the make_source factory."""
import pytest

from stroke_order.sources import (
    AutoSource,
    CharacterNotFound,
    G0VSource,
    MMHSource,
    make_source,
)


def test_make_source_variants():
    assert isinstance(make_source("g0v"), G0VSource)
    assert isinstance(make_source("mmh"), MMHSource)
    assert isinstance(make_source("auto"), AutoSource)
    # case-insensitive
    assert isinstance(make_source("AUTO"), AutoSource)


def test_make_source_invalid():
    with pytest.raises(ValueError, match="unknown source"):
        make_source("bogus")


class _Boom:
    """Stub source that always raises CharacterNotFound."""
    def get_character(self, char):
        raise CharacterNotFound(f"stub-missing: {char}")


class _Ok:
    """Stub that returns a marker Character."""
    def get_character(self, char):
        from stroke_order.ir import Character
        return Character(char=char, unicode_hex=f"{ord(char):x}",
                         data_source="stub_ok")


def test_autosource_primary_wins():
    src = AutoSource(primary=_Ok(), secondary=_Boom())
    c = src.get_character("X")
    assert c.data_source == "stub_ok"


def test_autosource_falls_back_on_not_found():
    src = AutoSource(primary=_Boom(), secondary=_Ok())
    c = src.get_character("Y")
    assert c.data_source == "stub_ok"


def test_autosource_propagates_when_both_fail():
    """When every source layer raises, the chain re-raises CharacterNotFound.

    Uses an emoji the punctuation table doesn't list and the CNS Kai TTF
    doesn't carry, so the chain genuinely exhausts itself even when the
    user has CNS fonts installed in their dev env.
    """
    src = AutoSource(primary=_Boom(), secondary=_Boom())
    with pytest.raises(CharacterNotFound):
        src.get_character("\U0001F600")  # 😀 — not in any source


# ---------------------------------------------------------------------------
# 5dq：make_source 記憶化（同名字源重用）——修效能 502 根因
# ---------------------------------------------------------------------------


def test_5dq_make_source_caches_by_name():
    """同名字源回同一 instance（重用 per-instance 快取）；不同名不同物件。"""
    from stroke_order.sources import make_source, reset_source_cache
    reset_source_cache()
    a1 = make_source("auto")
    a2 = make_source("auto")
    assert a1 is a2, "同名字源應重用（否則 mmh/moe_kaishu 快取每次重建）"
    assert make_source("g0v") is not a1
    # 大小寫正規化：AUTO == auto
    assert make_source("AUTO") is a1


def test_5dq_reset_source_cache_clears():
    from stroke_order.sources import make_source, reset_source_cache
    a1 = make_source("auto")
    reset_source_cache()
    a2 = make_source("auto")
    assert a1 is not a2, "reset 後應重建"


def test_5dq_make_source_unknown_not_cached():
    """未知名稱拋 ValueError、不進快取。"""
    from stroke_order.sources import make_source, reset_source_cache
    reset_source_cache()
    with pytest.raises(ValueError):
        make_source("bogus")
    with pytest.raises(ValueError):   # 二次仍拋（未毒化快取）
        make_source("bogus")
