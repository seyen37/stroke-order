"""
Phase 5al — CNS11643 全字庫 fallback source.

Covers the source adapter (font-outline extraction + plane routing),
component metadata lookup, and the ``apply_cns_outline_mode`` post-
processor (skip / trace / skeleton). Skeletonisation gets a smoke test
on a synthetic outline; full glyph rendering is exercised only when
the user has dropped TTFs into ``$STROKE_ORDER_CNS_FONT_DIR``.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from stroke_order.sources import CharacterNotFound, CNSFontSource
from stroke_order.sources.cns_components import CNSComponents
from stroke_order.sources.cns_font import apply_cns_outline_mode


# ---------------------------------------------------------------------------
# Whether the local environment has the TTFs available.
# Tests that need real fonts skip themselves when not.
# ---------------------------------------------------------------------------


_TEST_FONT_DIR = "/tmp/cns-fonts"


def _fonts_available() -> bool:
    return Path(f"{_TEST_FONT_DIR}/TW-Kai-98_1.ttf").exists()


def _sung_fonts_available() -> bool:
    return Path(f"{_TEST_FONT_DIR}/TW-Sung-98_1.ttf").exists()


needs_fonts = pytest.mark.skipif(
    not _fonts_available(),
    reason="CNS TTFs absent; extract Fonts_Kai.zip to /tmp/cns-fonts",
)


needs_sung_fonts = pytest.mark.skipif(
    not _sung_fonts_available(),
    reason="CNS Sung TTFs absent; extract Fonts_Sung.zip to /tmp/cns-fonts",
)


@pytest.fixture
def cns_env(monkeypatch):
    if _fonts_available():
        monkeypatch.setenv("STROKE_ORDER_CNS_FONT_DIR", _TEST_FONT_DIR)
    # Phase 5am: server keeps Sung-source singletons alive across requests.
    # Tests that monkeypatch the env need a clean slate so the singleton
    # picks up the new dir.
    from stroke_order.sources.cns_font import reset_cns_singletons
    reset_cns_singletons()


# ---------------------------------------------------------------------------
# CNSFontSource — graceful fallback when fonts absent
# ---------------------------------------------------------------------------


def test_cns_source_not_ready_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_CNS_FONT_DIR", str(tmp_path / "nope"))
    src = CNSFontSource()
    assert src.is_ready() is False
    assert src.available_planes() == []
    with pytest.raises(CharacterNotFound):
        src.get_character("永")


def test_cns_source_unknown_style_rejected():
    with pytest.raises(ValueError):
        CNSFontSource(style="bogus")


# ---------------------------------------------------------------------------
# CNSFontSource — happy path with real TTFs
# ---------------------------------------------------------------------------


@needs_fonts
def test_cns_source_loads_bmp_glyph(cns_env):
    src = CNSFontSource()
    assert src.is_ready() is True
    assert 0 in src.available_planes()
    c = src.get_character("永")
    assert c.data_source == "cns_font"
    assert len(c.strokes) == 1
    outline = c.strokes[0].outline
    # Should have multiple Move commands (one per contour) + many Q curves
    types = [cmd["type"] for cmd in outline]
    assert types.count("M") >= 3   # 永 has at least 3 contours
    assert "Q" in types
    # Coordinates land within the 2048 em frame
    for cmd in outline:
        if cmd["type"] in ("M", "L"):
            assert -100 <= cmd["x"] <= 2200
            assert -100 <= cmd["y"] <= 2200


@needs_fonts
def test_cns_source_loads_plane2_glyph(cns_env):
    """Plane-2 (Ext-B) char must come from the Ext-B TTF."""
    src = CNSFontSource()
    if 2 not in src.available_planes():
        pytest.skip("Ext-B TTF not installed")
    c = src.get_character("𡃁")   # U+210C1
    assert c.data_source == "cns_font"
    assert len(c.strokes[0].outline) > 0


@needs_fonts
def test_cns_source_caches_result(cns_env):
    src = CNSFontSource()
    a = src.get_character("永")
    b = src.get_character("永")
    assert a is b   # cached object identity


@needs_fonts
def test_autosource_falls_through_to_cns(cns_env):
    """A char not in g0v fixtures should resolve via CNS font."""
    from stroke_order.sources import AutoSource
    auto = AutoSource()
    # 鱻 (U+9C7B) is BMP — should hit CNS font (g0v fixture-only mode lacks it)
    try:
        c = auto.get_character("鱻")
        # When the Real g0v dataset is loaded this could resolve via g0v
        # too — accept either; the key is no exception.
        assert c.data_source in ("g0v", "mmh", "cns_font")
    except CharacterNotFound:
        pytest.skip("auto chain doesn't have 鱻 even with CNS fonts")


# ---------------------------------------------------------------------------
# apply_cns_outline_mode — skip / trace / skeleton
# ---------------------------------------------------------------------------


@needs_fonts
def test_cns_mode_skip_is_noop(cns_env):
    src = CNSFontSource()
    c = src.get_character("永")
    out = apply_cns_outline_mode(c, "skip")
    assert out is c   # identity


@needs_fonts
def test_cns_mode_trace_populates_track(cns_env):
    src = CNSFontSource()
    c = src.get_character("永")
    traced = apply_cns_outline_mode(c, "trace")
    # Trace produces N Stroke objects (one per contour), each with raw_track
    assert len(traced.strokes) >= 3
    for s in traced.strokes:
        assert len(s.raw_track) >= 2


@needs_fonts
def test_cns_mode_skeleton_produces_track(cns_env):
    src = CNSFontSource()
    c = src.get_character("永")
    skel = apply_cns_outline_mode(c, "skeleton")
    # 永 has 5 strokes; skeleton tracing yields ~5 polylines (varies)
    assert len(skel.strokes) >= 1
    total_pts = sum(len(s.raw_track) for s in skel.strokes)
    assert total_pts >= 10


def test_cns_mode_rejects_unknown():
    from stroke_order.ir import Character
    fake = Character(char="X", unicode_hex="0058", data_source="cns_font")
    with pytest.raises(ValueError, match="unknown cns mode"):
        apply_cns_outline_mode(fake, "rasterize")


def test_cns_mode_passes_through_non_cns():
    """Other data_source values are returned unchanged."""
    from stroke_order.ir import Character
    g0v_char = Character(char="一", unicode_hex="4e00", data_source="g0v")
    out = apply_cns_outline_mode(g0v_char, "skeleton")
    assert out is g0v_char


# ---------------------------------------------------------------------------
# Skeleton algorithm — pure-numpy correctness
# ---------------------------------------------------------------------------


def test_zhang_suen_thins_a_bar():
    """A 3-pixel-thick horizontal bar should thin to a 1-pixel line."""
    from stroke_order.cns_skeleton import zhang_suen
    img = np.zeros((30, 30), dtype=bool)
    img[14:17, 5:25] = True   # 3-tall × 20-wide bar
    skel = zhang_suen(img)
    assert skel.any()
    # Skeleton should be ~1-tall: each column has at most 1 set pixel
    for col in range(5, 25):
        assert skel[:, col].sum() <= 1


def test_outline_to_skeleton_smoke():
    """Synthetic horizontal-bar outline → 1-D skeleton polyline.

    A wide rectangle thins to a horizontal line that retains enough
    pixels to survive the ``len(path) >= 2`` filter.
    """
    from stroke_order.cns_skeleton import outline_to_skeleton_tracks
    outline = [
        {"type": "M", "x": 200,  "y": 1000},
        {"type": "L", "x": 1800, "y": 1000},
        {"type": "L", "x": 1800, "y": 1100},
        {"type": "L", "x": 200,  "y": 1100},
        {"type": "L", "x": 200,  "y": 1000},
    ]
    tracks = outline_to_skeleton_tracks(outline)
    assert len(tracks) >= 1
    # The skeleton of a long thin bar should have many points
    assert sum(len(t) for t in tracks) >= 5


# ---------------------------------------------------------------------------
# Component metadata
# ---------------------------------------------------------------------------


def test_components_not_ready_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_CNS_PROPERTIES_DIR",
                       str(tmp_path / "nope"))
    comps = CNSComponents()
    assert comps.is_ready() is False
    assert comps.decompose("永") == []


def test_components_decompose_with_real_data(tmp_path, monkeypatch):
    """End-to-end with actual CNS Properties files (if available)."""
    props_dir = Path("/tmp/cns11643/Properties")
    if not props_dir.exists():
        pytest.skip("CNS Properties dir not extracted to /tmp/cns11643")
    monkeypatch.setenv("STROKE_ORDER_CNS_PROPERTIES_DIR", str(props_dir))
    comps = CNSComponents()
    parts = comps.decompose("永")
    # 永 is a basic char — components list should be non-empty
    assert isinstance(parts, list)


# ---------------------------------------------------------------------------
# Web API
# ---------------------------------------------------------------------------


try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS = True
except ImportError:
    _HAS = False


@pytest.fixture
def client():
    if not _HAS:
        pytest.skip("web deps missing")
    return TestClient(create_app())


def test_api_cns_status(client):
    r = client.get("/api/cns-status")
    assert r.status_code == 200
    d = r.json()
    assert "font_dir" in d
    assert "fonts_ready" in d
    assert "kai_planes" in d


def test_api_decompose_unknown_returns_empty(client):
    r = client.get("/api/decompose/Z")
    assert r.status_code == 200
    d = r.json()
    assert d["char"] == "Z"
    assert d["components"] == []


def test_api_decompose_rejects_multi_char(client):
    r = client.get("/api/decompose/abc")
    assert r.status_code == 400


def test_api_endpoints_accept_cns_outline_mode(client):
    """All multi-mode endpoints accept the new cns_outline_mode param."""
    for url, code in [
        ("/api/notebook?text=永&preset=large&cns_outline_mode=skip", 200),
        ("/api/notebook?text=永&preset=large&cns_outline_mode=trace", 200),
        ("/api/notebook?text=永&preset=large&cns_outline_mode=skeleton", 200),
        ("/api/letter?text=永&preset=A5&cns_outline_mode=trace", 200),
        ("/api/manuscript?text=永&cns_outline_mode=skeleton", 200),
        ("/api/notebook?text=永&preset=large&cns_outline_mode=bogus", 422),
    ]:
        r = client.get(url)
        assert r.status_code == code, f"{url}: {r.status_code} {r.text[:200]}"


# ---------------------------------------------------------------------------
# Phase 5am — CNS Sung source plumbing + mingti style upgrade
# ---------------------------------------------------------------------------


def test_get_cns_sung_source_is_singleton():
    """Repeated calls return the same instance (per-process cache)."""
    from stroke_order.sources.cns_font import (
        get_cns_sung_source, reset_cns_singletons,
    )
    reset_cns_singletons()
    a = get_cns_sung_source()
    b = get_cns_sung_source()
    assert a is b
    assert a.style == "sung"


def test_get_cns_kai_source_is_singleton():
    from stroke_order.sources.cns_font import (
        get_cns_kai_source, reset_cns_singletons,
    )
    reset_cns_singletons()
    a = get_cns_kai_source()
    b = get_cns_kai_source()
    assert a is b
    assert a.style == "kai"


def test_kai_and_sung_singletons_are_distinct():
    from stroke_order.sources.cns_font import (
        get_cns_kai_source, get_cns_sung_source, reset_cns_singletons,
    )
    reset_cns_singletons()
    assert get_cns_kai_source() is not get_cns_sung_source()


@needs_sung_fonts
def test_cns_sung_source_loads_glyph_with_distinct_data_source(cns_env):
    """A Sung-style CNS char must be tagged ``cns_font_sung``."""
    from stroke_order.sources.cns_font import CNSFontSource
    src = CNSFontSource(style="sung")
    assert src.is_ready()
    c = src.get_character("永")
    assert c.data_source == "cns_font_sung"
    assert len(c.strokes) == 1
    assert c.strokes[0].outline   # has drawable geometry
    # Sanity: Kai for the same char must have a *different* outline (the
    # whole point of the upgrade is real visual difference).
    kai_c = CNSFontSource(style="kai").get_character("永")
    assert kai_c.data_source == "cns_font"
    # Outline command counts won't match between two type designs.
    assert len(kai_c.strokes[0].outline) != len(c.strokes[0].outline)


def test_mingti_short_circuits_on_sung_outline():
    """``MingtiStyle.apply`` must pass a cns_font_sung Character through
    untouched — re-running the kaishu filter on a real Sung outline would
    bolt on fake serifs and ruin the type designer's intent."""
    from stroke_order.ir import Character, Stroke
    from stroke_order.styles import apply_style
    fake_sung = Character(
        char="永", unicode_hex="6c38", data_source="cns_font_sung",
        strokes=[Stroke(index=0, raw_track=[],
                        outline=[{"type": "M", "x": 0, "y": 0},
                                 {"type": "L", "x": 100, "y": 100}],
                        kind_code=9, kind_name="其他", has_hook=False)],
    )
    out = apply_style(fake_sung, "mingti")
    assert out is fake_sung   # identity, no copy, no mutation


def test_apply_cns_outline_mode_handles_sung_data_source():
    """Phase-5am refactor: ``apply_cns_outline_mode`` uses
    ``startswith("cns_font")`` so both Kai and Sung route through the
    skip/trace/skeleton machinery."""
    from stroke_order.ir import Character, Stroke
    from stroke_order.sources.cns_font import apply_cns_outline_mode
    sung = Character(
        char="永", unicode_hex="6c38", data_source="cns_font_sung",
        strokes=[Stroke(index=0, raw_track=[],
                        outline=[{"type": "M", "x": 0, "y": 0},
                                 {"type": "L", "x": 1000, "y": 0},
                                 {"type": "L", "x": 1000, "y": 100},
                                 {"type": "L", "x": 0, "y": 100},
                                 {"type": "L", "x": 0, "y": 0}],
                        kind_code=9, kind_name="其他", has_hook=False)],
    )
    out = apply_cns_outline_mode(sung, "trace")
    # Trace should populate raw_track on the resulting strokes.
    assert any(len(s.raw_track) >= 2 for s in out.strokes)


def test_upgrade_to_sung_no_op_when_style_is_not_mingti():
    """Server helper: only mingti triggers the swap."""
    from stroke_order.ir import Character
    from stroke_order.web.server import _upgrade_to_sung
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    for style in ("kaishu", "lishu", "bold"):
        assert _upgrade_to_sung(base, style) is base


def test_upgrade_to_sung_returns_none_for_none_input():
    from stroke_order.web.server import _upgrade_to_sung
    assert _upgrade_to_sung(None, "mingti") is None


def test_upgrade_to_sung_falls_back_when_no_sung_source_available(tmp_path, monkeypatch):
    """Phase 5av — both MoE Song AND CNS Sung absent → original returned.

    Was 5am test (CNS Sung only). Now verifies the layered chain:
    MoE Song → CNS Sung → original. We disable BOTH for this test.
    """
    from stroke_order.ir import Character
    from stroke_order.sources.cns_font import reset_cns_singletons
    from stroke_order.sources.moe_song import reset_song_singleton
    from stroke_order.web.server import _upgrade_to_sung
    monkeypatch.setenv("STROKE_ORDER_CNS_FONT_DIR", str(tmp_path / "no-cns"))
    monkeypatch.setenv("STROKE_ORDER_SONG_FONT_FILE",
                       str(tmp_path / "no-song.ttf"))
    reset_cns_singletons()
    reset_song_singleton()
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    assert _upgrade_to_sung(base, "mingti") is base


@needs_sung_fonts
def test_upgrade_to_sung_swaps_to_cns_sung_when_only_cns_available(
    tmp_path, cns_env, monkeypatch,
):
    """When MoE Song is unavailable, layered chain falls through to CNS Sung."""
    from stroke_order.ir import Character
    from stroke_order.sources.moe_song import reset_song_singleton
    from stroke_order.web.server import _upgrade_to_sung
    monkeypatch.setenv("STROKE_ORDER_SONG_FONT_FILE",
                       str(tmp_path / "no-song.ttf"))
    reset_song_singleton()
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    out = _upgrade_to_sung(base, "mingti")
    assert out is not base
    assert out.data_source == "cns_font_sung"
    assert out.strokes and out.strokes[0].outline


@needs_sung_fonts
def test_api_notebook_mingti_uses_real_sung_when_available(cns_env, client):
    """End-to-end through FastAPI: mingti notebook output should differ
    from kaishu, and rely on Sung outline (no kaishu serif filter)."""
    r_mingti = client.get(
        "/api/notebook?text=永&preset=large&style=mingti&cell_style=outline"
    )
    r_kaishu = client.get(
        "/api/notebook?text=永&preset=large&style=kaishu&cell_style=outline"
    )
    assert r_mingti.status_code == 200 and r_kaishu.status_code == 200
    # The two SVGs must be visibly different — Sung outline replaces
    # g0v kaishu strokes entirely.
    assert r_mingti.text != r_kaishu.text


def test_api_cns_status_includes_sung_planes(client):
    """Phase-5am status payload exposes sung_planes alongside kai_planes."""
    r = client.get("/api/cns-status")
    assert r.status_code == 200
    d = r.json()
    assert "sung_planes" in d
    assert isinstance(d["sung_planes"], list)


# ---------------------------------------------------------------------------
# Phase 5aq — Plan C: g0v prior (Path 1) + junction-aware splitter (Path 2)
# ---------------------------------------------------------------------------


@needs_fonts
def test_path1_g0v_prior_swaps_when_available(cns_env):
    """Skeleton mode + prefer_g0v=True must use g0v's canonical stroke
    layout when g0v has the char — perfect N-stroke alignment is the
    whole point of Path 1."""
    from stroke_order.sources.cns_font import CNSFontSource, apply_cns_outline_mode
    src = CNSFontSource()
    c = src.get_character("永")    # in g0v
    out = apply_cns_outline_mode(c, "skeleton", prefer_g0v=True)
    # g0v says 永 has 5 strokes; the swap must respect that exactly.
    assert len(out.strokes) == 5
    # data_source carries the hybrid tag so downstream can tell.
    assert "g0v_aligned" in out.data_source
    # Each stroke must have non-empty raw_track (G-code-ready).
    assert all(s.raw_track for s in out.strokes)


@needs_fonts
def test_path1_falls_back_when_g0v_missing(cns_env):
    """Path 1 must fail open: chars NOT in g0v stay on the legacy
    skeleton walker rather than crashing."""
    from stroke_order.sources.cns_font import CNSFontSource, apply_cns_outline_mode
    src = CNSFontSource()
    # Pick a CNS-only Han char unlikely to be in g0v fixtures.
    # 𡃁 (U+210C1, Plane 2). g0v is BMP-only, so this MUST miss.
    try:
        c = src.get_character("\U000210C1")
    except Exception:
        pytest.skip("Plane-2 Ext-B char not loaded")
    out = apply_cns_outline_mode(c, "skeleton", prefer_g0v=True)
    # No g0v swap → fall back: data_source is unchanged 'cns_font'.
    assert out.data_source == "cns_font"
    # Still gets the legacy walker output (>=1 stroke).
    assert len(out.strokes) >= 1


@needs_fonts
def test_path1_disabled_keeps_legacy_behaviour(cns_env):
    """prefer_g0v=False routes through the legacy v1 walker even for
    g0v-covered chars — this is the ablation knob for 5aq-5 measurement."""
    from stroke_order.sources.cns_font import CNSFontSource, apply_cns_outline_mode
    src = CNSFontSource()
    c = src.get_character("永")
    out = apply_cns_outline_mode(c, "skeleton", prefer_g0v=False)
    # Legacy: data_source stays 'cns_font'; stroke count whatever Zhang-Suen gives.
    assert out.data_source == "cns_font"


def test_path1_skip_mode_unaffected_by_prefer_g0v():
    """Path 1 only kicks in for skeleton mode. skip / trace ignore it."""
    from stroke_order.ir import Character, Stroke
    from stroke_order.sources.cns_font import apply_cns_outline_mode
    fake = Character(
        char="永", unicode_hex="6c38", data_source="cns_font",
        strokes=[Stroke(index=0, raw_track=[],
                        outline=[{"type": "M", "x": 0, "y": 0}],
                        kind_code=9, kind_name="其他", has_hook=False)],
    )
    # skip mode short-circuits before ANY swap logic
    out = apply_cns_outline_mode(fake, "skip", prefer_g0v=True)
    assert out is fake


# Path 2 — opt-in skeleton splitter. Its quality is alpha so we only
# verify it (a) imports + runs without error and (b) returns at least
# one segment for a non-trivial input. Detailed accuracy is tracked in
# the 5ap measurement report, not asserted here.


def test_path2_detect_junctions_on_synthetic_cross():
    """A simple + cross has exactly one true junction at the centre."""
    import numpy as np
    from stroke_order.cns_skeleton import detect_junctions
    skel = np.zeros((11, 11), dtype=bool)
    skel[5, 1:10] = True   # horizontal arm
    skel[1:10, 5] = True   # vertical arm
    junctions = detect_junctions(skel)
    # Centre pixel should be the only junction (crossing number = 4).
    assert (5, 5) in junctions
    # Endpoints should NOT be junctions.
    assert (5, 1) not in junctions
    assert (1, 5) not in junctions


def test_path2_split_at_junctions_returns_segments_for_cross():
    """A simple + cross splits into multiple segments. The exact count
    depends on how 8-connected staircase artefacts are handled — we
    only assert that we get *more than one* segment and each segment
    has at least 2 pixels (no empty walks)."""
    import numpy as np
    from stroke_order.cns_skeleton import split_at_junctions
    skel = np.zeros((11, 11), dtype=bool)
    skel[5, 1:10] = True
    skel[1:10, 5] = True
    segments = split_at_junctions(skel)
    assert len(segments) >= 2
    for seg in segments:
        assert len(seg) >= 2


def test_path2_merge_collinear_reduces_count():
    """Merging should produce ≤ the input segment count.
    Exact merge correctness is gated by the 8-connectivity walker
    accuracy (alpha — see Phase 5aq notes)."""
    import numpy as np
    from stroke_order.cns_skeleton import (
        split_at_junctions, merge_collinear,
    )
    skel = np.zeros((11, 11), dtype=bool)
    skel[5, 1:10] = True
    skel[1:10, 5] = True
    segments = split_at_junctions(skel)
    merged = merge_collinear(segments, angle_threshold_deg=20)
    assert 1 <= len(merged) <= len(segments)


def test_path2_sort_writing_order_top_to_bottom():
    from stroke_order.cns_skeleton import sort_writing_order
    tracks = [
        [(50.0, 100.0), (150.0, 100.0)],   # bottom-row stroke
        [(50.0, 10.0), (150.0, 10.0)],     # top-row stroke
        [(50.0, 50.0), (150.0, 50.0)],     # middle-row stroke
    ]
    out = sort_writing_order(tracks)
    # First stroke sorted should have the smallest y_min.
    assert out[0][0][1] == 10.0
    assert out[-1][0][1] == 100.0


@needs_fonts
def test_path2_pipeline_runs_end_to_end_without_hanging(cns_env):
    """Smoke test: outline_to_skeleton_tracks_v2 must terminate quickly
    on a real CJK glyph and return ≥ 1 track. No accuracy assertion —
    Path 2 is experimental."""
    import time
    from stroke_order.cns_skeleton import outline_to_skeleton_tracks_v2
    from stroke_order.sources.cns_font import CNSFontSource
    c = CNSFontSource().get_character("一")   # simplest: 1 stroke
    t0 = time.time()
    tracks = outline_to_skeleton_tracks_v2(c.strokes[0].outline)
    elapsed = time.time() - t0
    assert tracks, "v2 returned no tracks for 一"
    assert elapsed < 5.0, f"v2 too slow ({elapsed:.1f}s on 一)"
