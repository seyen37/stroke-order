"""
Phase 5av — 教育部標準宋體 source + layered Sung priority.

When MoE Song is installed, ``style="mingti"`` should swap to MoE Song
first, falling back to CNS Sung only for chars MoE doesn't carry.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from stroke_order.sources.moe_song import (
    MoeSongSource,
    apply_song_outline_mode,
    attribution_notice,
    default_song_font_path,
    get_song_source,
    reset_song_singleton,
)
from stroke_order.sources.g0v import CharacterNotFound


_TEST_FONT = "/tmp/moe-song/edusong_Unicode.ttf"


def _song_available() -> bool:
    return Path(_TEST_FONT).exists()


needs_song = pytest.mark.skipif(
    not _song_available(),
    reason="MoE Song absent; copy edusong_Unicode.ttf to /tmp/moe-song/",
)


@pytest.fixture
def song_env(monkeypatch):
    if _song_available():
        monkeypatch.setenv("STROKE_ORDER_SONG_FONT_FILE", _TEST_FONT)
    reset_song_singleton()


# ---- Graceful fallback ---------------------------------------------------


def test_default_path_uses_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("STROKE_ORDER_SONG_FONT_FILE", str(tmp_path / "x.ttf"))
    assert default_song_font_path() == tmp_path / "x.ttf"


def test_source_not_ready_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_SONG_FONT_FILE", str(tmp_path / "nope.ttf"))
    src = MoeSongSource()
    assert src.is_ready() is False
    assert src.available_glyph_count() == 0
    with pytest.raises(CharacterNotFound):
        src.get_character("永")


def test_attribution_credits_moe():
    s = attribution_notice()
    assert "教育部" in s
    assert "宋體" in s
    assert "CC BY-ND" in s


def test_singleton():
    reset_song_singleton()
    assert get_song_source() is get_song_source()


# ---- Real font ------------------------------------------------------------


@needs_song
def test_loads_glyph(song_env):
    src = MoeSongSource()
    assert src.is_ready()
    assert src.available_glyph_count() > 20000
    c = src.get_character("永")
    assert c.data_source == "moe_song"
    assert c.strokes[0].outline


@needs_song
def test_skeleton_mode_produces_polylines(song_env):
    src = MoeSongSource()
    c = src.get_character("永")
    sk = apply_song_outline_mode(c, "skeleton")
    assert len(sk.strokes) >= 1
    assert all(len(s.raw_track) >= 2 for s in sk.strokes)


def test_apply_passes_through_non_song_data_source():
    from stroke_order.ir import Character
    g0v_char = Character(char="永", unicode_hex="6c38", data_source="g0v")
    assert apply_song_outline_mode(g0v_char, "skeleton") is g0v_char


# ---- MingtiStyle short-circuit covers moe_song too -----------------------


def test_mingti_style_short_circuits_on_moe_song_data_source():
    from stroke_order.ir import Character, Stroke
    from stroke_order.styles import apply_style
    fake = Character(
        char="永", unicode_hex="6c38", data_source="moe_song",
        strokes=[Stroke(index=0, raw_track=[],
                        outline=[{"type": "M", "x": 0, "y": 0},
                                 {"type": "L", "x": 100, "y": 100}],
                        kind_code=9, kind_name="其他", has_hook=False)],
    )
    out = apply_style(fake, "mingti")
    assert out is fake


# ---- Layered _upgrade_to_sung: MoE first, CNS Sung fallback --------------


def test_upgrade_no_op_when_style_is_not_mingti():
    from stroke_order.ir import Character
    from stroke_order.web.server import _upgrade_to_sung
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    for style in ("kaishu", "lishu", "bold", "seal_script"):
        assert _upgrade_to_sung(base, style) is base


def test_upgrade_falls_back_when_no_song_or_sung(tmp_path, monkeypatch):
    """Both MoE Song and CNS Sung absent → original kaishu unchanged."""
    from stroke_order.ir import Character
    from stroke_order.sources.cns_font import reset_cns_singletons
    from stroke_order.web.server import _upgrade_to_sung
    monkeypatch.setenv("STROKE_ORDER_SONG_FONT_FILE", str(tmp_path / "nope.ttf"))
    monkeypatch.setenv("STROKE_ORDER_CNS_FONT_DIR", str(tmp_path / "no-cns"))
    reset_song_singleton()
    reset_cns_singletons()
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    assert _upgrade_to_sung(base, "mingti") is base


@needs_song
def test_upgrade_prefers_moe_song_over_cns_sung(song_env):
    """When both fonts loaded, MoE Song wins for chars it covers."""
    from stroke_order.ir import Character
    from stroke_order.web.server import _upgrade_to_sung
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    out = _upgrade_to_sung(base, "mingti")
    assert out is not base
    # MoE Song wins (its data_source is "moe_song").
    assert out.data_source == "moe_song"


# ---- apply_cns_outline_mode now also handles moe_song --------------------


@needs_song
def test_apply_cns_mode_extends_to_moe_song(song_env):
    """Phase 5av: cns_outline_mode=skeleton now also processes moe_song
    so the user-facing knob stays uniform across font sources."""
    from stroke_order.sources.cns_font import apply_cns_outline_mode
    src = MoeSongSource()
    c = src.get_character("永")
    sk = apply_cns_outline_mode(c, "skeleton")
    # Should produce raw_tracks (polylines) just like CNS Sung would.
    assert len(sk.strokes) >= 1
    assert all(len(s.raw_track) >= 2 for s in sk.strokes)


# ---- API -----------------------------------------------------------------


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


def test_api_song_status_payload_shape(client):
    r = client.get("/api/song-status")
    assert r.status_code == 200
    d = r.json()
    for key in ("font_file", "ready", "glyph_count",
                "attribution", "license", "license_url"):
        assert key in d
    assert "教育部" in d["attribution"]
    assert "宋體" in d["attribution"]


@needs_song
def test_api_notebook_mingti_uses_moe_song(song_env, client):
    """End-to-end: kaishu vs mingti differ; mingti is real Sung."""
    r_k = client.get(
        "/api/notebook?text=永&preset=large&style=kaishu&cell_style=outline"
    )
    r_m = client.get(
        "/api/notebook?text=永&preset=large&style=mingti&cell_style=outline"
    )
    assert r_k.status_code == 200 and r_m.status_code == 200
    assert r_k.text != r_m.text
