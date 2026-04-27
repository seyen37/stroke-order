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
