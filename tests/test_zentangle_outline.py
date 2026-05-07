"""
Phase 6z-1A — zentangle outline extraction tests.

Tests the public API of ``stroke_order.exporters.zentangle``:

* :func:`extract_outline_polylines` — char → contour polylines
* :func:`list_sources` — UI dropdown helper

Font-independent tests (input validation + dispatch) always run.
Font-dependent tests are gated by ``needs_kaishu`` markers; they skip
gracefully when ``edukai-5.1_*.ttf`` is not present (typical for sandbox
+ CI without the asset). On developer machines with the font, they
verify real outlines for "心" and "日".
"""
from __future__ import annotations

from pathlib import Path

import pytest

from stroke_order.exporters import zentangle
from stroke_order.sources.g0v import CharacterNotFound
from stroke_order.sources.moe_kaishu import reset_kaishu_singleton


_TEST_KAISHU_FONT = "/tmp/moe-kaishu/edukai-5.1_20251208.ttf"


def _kaishu_available() -> bool:
    return Path(_TEST_KAISHU_FONT).exists()


needs_kaishu = pytest.mark.skipif(
    not _kaishu_available(),
    reason="MoE Kaishu absent; copy edukai-5.1*.ttf to /tmp/moe-kaishu/",
)


@pytest.fixture
def kaishu_env(monkeypatch):
    """Point the kaishu source at the test font and reset its singleton."""
    if _kaishu_available():
        monkeypatch.setenv(
            "STROKE_ORDER_KAISHU_FONT_FILE", _TEST_KAISHU_FONT
        )
    reset_kaishu_singleton()


# ---------------------------------------------------------------------------
# Input validation (font-independent)
# ---------------------------------------------------------------------------


def test_extract_rejects_empty_string():
    with pytest.raises(ValueError, match="single character"):
        zentangle.extract_outline_polylines("")


def test_extract_rejects_multi_char():
    with pytest.raises(ValueError, match="single character"):
        zentangle.extract_outline_polylines("心心")


def test_extract_rejects_non_string():
    with pytest.raises(ValueError, match="single character"):
        zentangle.extract_outline_polylines(123)  # type: ignore[arg-type]


def test_extract_rejects_unknown_source():
    with pytest.raises(ValueError, match="unknown source"):
        zentangle.extract_outline_polylines("心", source="not-a-source")


def test_extract_unknown_source_message_lists_valid_keys():
    """The error message should expose valid sources for caller debugging."""
    with pytest.raises(ValueError) as ei:
        zentangle.extract_outline_polylines("心", source="bogus")
    msg = str(ei.value)
    for key in ("moe_kaishu", "cns_kai", "moe_song", "moe_lishu", "chongxi_seal"):
        assert key in msg, f"valid source {key!r} should appear in error: {msg}"


# ---------------------------------------------------------------------------
# list_sources / registry (font-independent — sandbox has no fonts so all
# entries report ready=False, but the structure must hold).
# ---------------------------------------------------------------------------


def test_list_sources_returns_five_entries():
    sources = zentangle.list_sources()
    assert len(sources) == 5
    keys = [s["key"] for s in sources]
    assert keys == [
        "moe_kaishu",
        "cns_kai",
        "moe_song",
        "moe_lishu",
        "chongxi_seal",
    ], "ordered registry powers the UI dropdown order"


def test_list_sources_each_entry_has_required_fields():
    for entry in zentangle.list_sources():
        assert set(entry.keys()) == {"key", "label", "ready"}
        assert isinstance(entry["key"], str)
        assert isinstance(entry["label"], str)
        assert isinstance(entry["ready"], bool)


def test_list_sources_kaishu_label_is_chinese():
    """User-facing label must be the Chinese script name, not the snake_case key."""
    sources = {s["key"]: s["label"] for s in zentangle.list_sources()}
    assert sources["moe_kaishu"] == "教育部楷書"
    assert sources["cns_kai"] == "CNS 楷書"
    assert sources["moe_song"] == "教育部宋體"
    assert sources["moe_lishu"] == "教育部隸書"
    assert sources["chongxi_seal"] == "崇喜篆書"


def test_default_source_is_moe_kaishu():
    """Q1 user decision (Phase 6z-1): MVP default = 教育部楷書."""
    assert zentangle.DEFAULT_SOURCE == "moe_kaishu"


def test_default_samples_per_curve_matches_cns_font_pipeline():
    """Stay aligned with the 5al CNS font pipeline default for visual consistency."""
    assert zentangle.DEFAULT_SAMPLES_PER_CURVE == 8


# ---------------------------------------------------------------------------
# Outline extraction with real fonts (kaishu)
# ---------------------------------------------------------------------------


@needs_kaishu
def test_extract_xin_returns_at_least_one_contour(kaishu_env):
    """「心」 — simple character, expect at least one closed polyline contour."""
    contours = zentangle.extract_outline_polylines("心")
    assert len(contours) >= 1, "「心」 should yield ≥1 contour"
    for poly in contours:
        assert len(poly) >= 3, "each contour must have ≥3 points"
        for pt in poly:
            assert isinstance(pt, tuple)
            assert len(pt) == 2
            assert all(isinstance(c, (int, float)) for c in pt)


@needs_kaishu
def test_extract_ri_has_inner_and_outer_contours(kaishu_env):
    """「日」 — expect ≥2 contours (outer rectangle + at least one inner cavity)."""
    contours = zentangle.extract_outline_polylines("日")
    assert len(contours) >= 2, (
        "「日」 should yield ≥2 contours (outer + at least one inner)"
    )


@needs_kaishu
def test_extract_returns_em_scaled_y_down_coords(kaishu_env):
    """Coords should be in the canonical EM frame (Y-down, ~ EM_SIZE = 2048 across glyph)."""
    from stroke_order.ir import EM_SIZE

    contours = zentangle.extract_outline_polylines("心")
    all_x = [pt[0] for poly in contours for pt in poly]
    all_y = [pt[1] for poly in contours for pt in poly]
    assert all_x and all_y
    # Generous bounds: glyph occupies a meaningful fraction of the EM box.
    # (Don't tighten further — different glyphs have different bbox sizes.)
    assert max(all_x) - min(all_x) > EM_SIZE * 0.1, (
        "glyph width should be > 10% of EM"
    )
    assert max(all_y) - min(all_y) > EM_SIZE * 0.1, (
        "glyph height should be > 10% of EM"
    )


@needs_kaishu
def test_extract_higher_samples_yields_more_points(kaishu_env):
    """samples_per_curve scales polyline density (Bezier sampling)."""
    contours_low = zentangle.extract_outline_polylines("心", samples_per_curve=2)
    contours_high = zentangle.extract_outline_polylines("心", samples_per_curve=16)
    points_low = sum(len(p) for p in contours_low)
    points_high = sum(len(p) for p in contours_high)
    assert points_high > points_low, (
        "higher samples_per_curve should produce more polyline points"
    )


@needs_kaishu
def test_extract_unknown_glyph_raises_character_not_found(kaishu_env):
    """A character outside the font's coverage should raise CharacterNotFound."""
    # Private-use codepoint U+E000 is unlikely to exist in any normal font.
    with pytest.raises(CharacterNotFound):
        zentangle.extract_outline_polylines("")


@needs_kaishu
def test_extract_default_and_explicit_source_match(kaishu_env):
    """Calling with the default source argument == omitting it."""
    a = zentangle.extract_outline_polylines("心")
    b = zentangle.extract_outline_polylines("心", source="moe_kaishu")
    assert a == b
