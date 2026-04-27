"""
Phase 5ai — punctuation source (方案 A) + SVG text fallback (方案 B).

Covers:

- ``PunctuationSource`` returns valid Character IR for ~25 marks.
- It plugs in as a final fallback in ``AutoSource`` / ``RegionAutoSource``
  so ``make_source("auto").get_character("，")`` just works.
- ``_load`` in server.py bypasses the Han-char pipeline for punctuation
  so validate/classify/smooth never touch the hand-authored strokes.
- ``flow_text`` populates ``Page.text_glyphs`` for chars still missing
  after all source fallbacks — used by ``render_page_svg`` as SVG
  ``<text>`` fallback.
- G-code export skips text fallback (not stroke data).
- JSON export emits a ``text_fallback`` entry per page so downstream
  knows which cells the robot won't reach.
"""
from __future__ import annotations

import json as _json

import pytest

from stroke_order.ir import Character, Point, Stroke
from stroke_order.sources import (
    AutoSource, CharacterNotFound, make_source,
    PunctuationSource, supported_punctuation,
)


# ---------------------------------------------------------------------------
# PunctuationSource directly
# ---------------------------------------------------------------------------


def test_supported_set_covers_common_cjk_marks():
    s = set(supported_punctuation())
    for mark in ["。", "，", "、", "：", "；", "！", "？",
                 "「", "」", "『", "』", "（", "）", "《", "》",
                 "〈", "〉", "—", "…", "·"]:
        assert mark in s, f"missing {mark!r}"


def test_supported_set_covers_common_ascii_marks():
    s = set(supported_punctuation())
    for mark in [".", ",", "!", "?", ":", ";", "(", ")", "-", '"', "'"]:
        assert mark in s, f"missing ASCII {mark!r}"


def test_punctuation_source_returns_valid_character():
    src = PunctuationSource()
    c = src.get_character("，")
    assert isinstance(c, Character)
    assert c.char == "，"
    assert c.unicode_hex == "ff0c"
    assert c.data_source == "punctuation"
    assert c.strokes
    # Strokes have ≥2 points and are pre-classified as "其他" (9)
    for st in c.strokes:
        assert len(st.raw_track) >= 2
        assert st.kind_code == 9
        for p in st.raw_track:
            assert isinstance(p, Point)
            assert 0 <= p.x <= 2048
            assert 0 <= p.y <= 2048


def test_punctuation_source_raises_on_unknown():
    src = PunctuationSource()
    with pytest.raises(CharacterNotFound):
        src.get_character("永")   # not punctuation


def test_autosource_falls_back_to_punctuation():
    """Default AutoSource should find punctuation even when primary/secondary
    (real g0v/mmh) don't have it."""
    # Use stub sources so test doesn't need g0v fixtures installed
    class _Boom:
        def get_character(self, c):
            raise CharacterNotFound(f"stub: {c}")
    src = AutoSource(primary=_Boom(), secondary=_Boom())
    c = src.get_character("，")
    assert c.data_source == "punctuation"


def test_make_source_auto_resolves_punctuation():
    """End-to-end: the public factory's default picks punctuation."""
    src = make_source("auto")
    c = src.get_character("。")
    assert c.data_source == "punctuation"


def test_region_source_also_has_punctuation_fallback():
    for region in ("tw", "cn", "jp"):
        src = make_source(region)
        c = src.get_character("，")
        assert c.data_source == "punctuation", f"region {region} missed ，"


# ---------------------------------------------------------------------------
# flow_text: TextGlyph fallback for chars with no stroke data anywhere
# ---------------------------------------------------------------------------


def test_flow_text_populates_text_glyphs_on_missing_char():
    """Characters the loader returns None for get a TextGlyph entry so the
    SVG preview can still show them (even though G-code can't)."""
    from stroke_order.layouts import (
        PageLayout, PageSize, TextGlyph, flow_text,
    )

    def empty_loader(_ch):
        return None   # nothing resolves

    layout = PageLayout(
        size=PageSize(100, 100),
        margin_top_mm=10, margin_bottom_mm=10,
        margin_left_mm=10, margin_right_mm=10,
        line_height_mm=10, char_width_mm=10,
    )
    pages = flow_text("AB", layout, empty_loader)
    assert len(pages) == 1
    page = pages[0]
    assert page.missing == ["A", "B"]    # diagnostics preserved
    assert len(page.text_glyphs) == 2    # fallback glyphs
    assert all(isinstance(tg, TextGlyph) for tg in page.text_glyphs)
    assert page.text_glyphs[0].char == "A"
    assert page.text_glyphs[1].char == "B"


# ---------------------------------------------------------------------------
# End-to-end via the Web API: punctuation strokes + SVG text fallback
# ---------------------------------------------------------------------------


try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS = True
except ImportError:
    _HAS = False


@pytest.fixture(scope="module")
def client():
    if not _HAS:
        pytest.skip("web deps missing")
    return TestClient(create_app())


def test_api_character_endpoint_serves_punctuation(client):
    r = client.get("/api/character/，")
    assert r.status_code == 200
    data = r.json()
    assert "strokes" in data
    assert len(data["strokes"]) >= 1


def test_api_notebook_renders_punctuation_as_strokes(client):
    """Notebook SVG for text containing 「，」 should include real geometry
    from the punctuation source — and crucially NOT fall through to the
    text-glyph fallback group.

    After Phase 5aj ``_char_svg`` renders empty-outline strokes (like
    punctuation) as ``<polyline>`` so they're visible in all cell modes,
    so we compare total drawable element count (path + polyline).
    """
    r = client.get("/api/notebook?text=一，一&preset=large&cell_style=outline")
    r_no_comma = client.get("/api/notebook?text=一一&preset=large&cell_style=outline")
    assert r.status_code == 200 and r_no_comma.status_code == 200
    # 「，」 adds drawable elements AND must not land in the text-fallback group
    assert 'class="text-fallback"' not in r.text
    total_with = r.text.count('<path') + r.text.count('<polyline')
    total_without = r_no_comma.text.count('<path') + r_no_comma.text.count('<polyline')
    assert total_with > total_without


def test_api_notebook_text_fallback_for_unknown_character(client):
    """A char not in g0v/mmh/punctuation (e.g. emoji) should render as
    an SVG <text> element, not silently disappear."""
    # U+1F600 is unlikely to be in any character source.
    r = client.get("/api/notebook?text=一%F0%9F%98%80&preset=large&cell_style=outline")
    assert r.status_code == 200
    assert 'class="text-fallback"' in r.text
    # The emoji character should appear literally inside the <text> node
    assert "😀" in r.text


def test_api_notebook_json_lists_text_fallback_entries(client):
    """JSON output includes ``text_fallback`` entries for SVG-only chars."""
    r = client.get("/api/notebook?text=一%F0%9F%98%80&preset=large&format=json")
    assert r.status_code == 200
    data = _json.loads(r.text)
    any_fallback = any("text_fallback" in p and p["text_fallback"]
                       for p in data["pages"])
    assert any_fallback, "expected at least one page to list text_fallback"


def test_api_notebook_gcode_skips_text_fallback(client):
    """G-code export only looks at page.chars — text fallback chars must
    NOT produce pen-down commands."""
    r = client.get("/api/notebook?text=一%F0%9F%98%80&preset=large"
                   "&cell_style=outline&format=gcode")
    assert r.status_code == 200
    gc = r.text
    # Count M3 S90 (pen-down). With just '一' there should be ≤ few.
    # The emoji must not add any new pen-downs vs '一' alone.
    r_alone = client.get("/api/notebook?text=一&preset=large"
                         "&cell_style=outline&format=gcode")
    assert gc.count("M3 S90") == r_alone.text.count("M3 S90")


def test_api_notebook_punctuation_actually_writes_in_gcode(client):
    """G-code export for punctuation should produce pen-down commands
    (stroke data from PunctuationSource)."""
    r_plain = client.get("/api/notebook?text=一&preset=large"
                         "&cell_style=outline&format=gcode")
    r_punct = client.get("/api/notebook?text=一，&preset=large"
                         "&cell_style=outline&format=gcode")
    assert r_plain.status_code == 200 and r_punct.status_code == 200
    # Adding ， should produce MORE pen-down commands — the comma has strokes
    assert r_punct.text.count("M3 S90") > r_plain.text.count("M3 S90")
