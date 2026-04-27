"""
Phase 5au — 教育部隸書 source + lishu style upgrade.

Mirror of test_chongxi_seal — when MoE Lishu OTF is installed,
``style="lishu"`` swaps the 5aj filter for real-font outline.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from stroke_order.sources.moe_lishu import (
    MoeLishuSource,
    apply_lishu_outline_mode,
    attribution_notice,
    default_lishu_font_path,
    get_lishu_source,
    reset_lishu_singleton,
)
from stroke_order.sources.g0v import CharacterNotFound


_TEST_FONT = "/tmp/moe-lishu/MoeLI.ttf"


def _lishu_available() -> bool:
    return Path(_TEST_FONT).exists()


needs_lishu = pytest.mark.skipif(
    not _lishu_available(),
    reason="MoE Lishu absent; copy MoeLI.ttf to /tmp/moe-lishu/",
)


@pytest.fixture
def lishu_env(monkeypatch):
    if _lishu_available():
        monkeypatch.setenv("STROKE_ORDER_LISHU_FONT_FILE", _TEST_FONT)
    reset_lishu_singleton()


# ---- Graceful fallback ---------------------------------------------------


def test_default_path_uses_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("STROKE_ORDER_LISHU_FONT_FILE", str(tmp_path / "x.ttf"))
    assert default_lishu_font_path() == tmp_path / "x.ttf"


def test_source_not_ready_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_LISHU_FONT_FILE", str(tmp_path / "nope.ttf"))
    src = MoeLishuSource()
    assert src.is_ready() is False
    assert src.available_glyph_count() == 0
    with pytest.raises(CharacterNotFound):
        src.get_character("永")


def test_attribution_credits_moe():
    """CC BY-ND 3.0 TW — must explicitly attribute the MoE."""
    s = attribution_notice()
    assert "教育部" in s
    assert "CC BY-ND" in s


def test_singleton():
    reset_lishu_singleton()
    assert get_lishu_source() is get_lishu_source()


# ---- Real font ------------------------------------------------------------


@needs_lishu
def test_loads_glyph(lishu_env):
    src = MoeLishuSource()
    assert src.is_ready()
    assert src.available_glyph_count() > 5000
    c = src.get_character("永")
    assert c.data_source == "moe_lishu"
    assert c.strokes[0].outline


@needs_lishu
def test_skeleton_mode_produces_polylines(lishu_env):
    src = MoeLishuSource()
    c = src.get_character("永")
    sk = apply_lishu_outline_mode(c, "skeleton")
    assert len(sk.strokes) >= 1
    assert all(len(s.raw_track) >= 2 for s in sk.strokes)


def test_apply_passes_through_non_lishu_data_source():
    from stroke_order.ir import Character
    g0v_char = Character(char="永", unicode_hex="6c38", data_source="g0v")
    assert apply_lishu_outline_mode(g0v_char, "skeleton") is g0v_char


# ---- LishuStyle short-circuit (5au addition) ----------------------------


def test_lishu_style_short_circuits_on_moe_lishu_data_source():
    """When data_source = moe_lishu, the 5aj fake-lishu filter must be
    a no-op — adding 波磔 + vertical squash on top of real lishu would
    double the effect."""
    from stroke_order.ir import Character, Stroke
    from stroke_order.styles import apply_style
    fake_lishu = Character(
        char="永", unicode_hex="6c38", data_source="moe_lishu",
        strokes=[Stroke(index=0, raw_track=[],
                        outline=[{"type": "M", "x": 0, "y": 0},
                                 {"type": "L", "x": 100, "y": 100}],
                        kind_code=9, kind_name="其他", has_hook=False)],
    )
    out = apply_style(fake_lishu, "lishu")
    assert out is fake_lishu


# ---- Server _upgrade_to_lishu --------------------------------------------


def test_upgrade_no_op_when_style_is_not_lishu():
    from stroke_order.ir import Character
    from stroke_order.web.server import _upgrade_to_lishu
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    for style in ("kaishu", "mingti", "bold", "seal_script"):
        assert _upgrade_to_lishu(base, style) is base


def test_upgrade_falls_back_when_font_missing(tmp_path, monkeypatch):
    from stroke_order.ir import Character
    from stroke_order.web.server import _upgrade_to_lishu
    monkeypatch.setenv("STROKE_ORDER_LISHU_FONT_FILE", str(tmp_path / "nope.ttf"))
    reset_lishu_singleton()
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    assert _upgrade_to_lishu(base, "lishu") is base


@needs_lishu
def test_upgrade_swaps_to_moe_lishu_when_available(lishu_env):
    from stroke_order.ir import Character
    from stroke_order.web.server import _upgrade_to_lishu
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    out = _upgrade_to_lishu(base, "lishu")
    assert out is not base
    assert out.data_source == "moe_lishu"
    assert all(s.raw_track for s in out.strokes)


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


def test_api_lishu_status_payload_shape(client):
    r = client.get("/api/lishu-status")
    assert r.status_code == 200
    d = r.json()
    for key in ("font_file", "ready", "glyph_count",
                "attribution", "license", "license_url"):
        assert key in d
    assert "教育部" in d["attribution"]


@needs_lishu
def test_api_notebook_lishu_swaps_strokes(lishu_env, client):
    """style=lishu vs kaishu produce different SVG when MoE 隸書 loaded."""
    r_k = client.get(
        "/api/notebook?text=永&preset=large&style=kaishu&cell_style=outline"
    )
    r_l = client.get(
        "/api/notebook?text=永&preset=large&style=lishu&cell_style=outline"
    )
    assert r_k.status_code == 200 and r_l.status_code == 200
    assert r_k.text != r_l.text
