"""
Phase 5aw — 教育部標準楷書 source + AutoSource Tier-3 integration.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from stroke_order.sources.moe_kaishu import (
    MoeKaishuSource,
    attribution_notice,
    default_kaishu_font_path,
    get_kaishu_source,
    reset_kaishu_singleton,
)
from stroke_order.sources.g0v import CharacterNotFound


_TEST_FONT = "/tmp/moe-kaishu/edukai-5.1_20251208.ttf"


def _kaishu_available() -> bool:
    return Path(_TEST_FONT).exists()


needs_kaishu = pytest.mark.skipif(
    not _kaishu_available(),
    reason="MoE Kaishu absent; copy edukai-5.1*.ttf to /tmp/moe-kaishu/",
)


@pytest.fixture
def kaishu_env(monkeypatch):
    if _kaishu_available():
        monkeypatch.setenv("STROKE_ORDER_KAISHU_FONT_FILE", _TEST_FONT)
    reset_kaishu_singleton()


# ---- Graceful fallback ---------------------------------------------------


def test_default_path_uses_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("STROKE_ORDER_KAISHU_FONT_FILE", str(tmp_path / "x.ttf"))
    assert default_kaishu_font_path() == tmp_path / "x.ttf"


def test_default_path_dir_glob_fallback(monkeypatch, tmp_path):
    """Phase-5aw addition: ``STROKE_ORDER_KAISHU_FONT_DIR`` accepts the
    distribution's date-stamped filename via glob when the canonical
    ``edukai.ttf`` isn't there."""
    monkeypatch.delenv("STROKE_ORDER_KAISHU_FONT_FILE", raising=False)
    monkeypatch.setenv("STROKE_ORDER_KAISHU_FONT_DIR", str(tmp_path))
    # No file at all → default path returns canonical (still missing).
    assert default_kaishu_font_path() == tmp_path / "edukai.ttf"
    # Date-stamped variant is picked up.
    (tmp_path / "edukai-5.1_20251208.ttf").write_bytes(b"")
    assert default_kaishu_font_path().name.startswith("edukai")


def test_source_not_ready_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_KAISHU_FONT_FILE",
                       str(tmp_path / "nope.ttf"))
    src = MoeKaishuSource()
    assert src.is_ready() is False
    assert src.available_glyph_count() == 0
    with pytest.raises(CharacterNotFound):
        src.get_character("永")


def test_attribution_credits_moe_kaishu():
    s = attribution_notice()
    assert "教育部" in s
    assert "楷書" in s
    assert "CC BY-ND" in s


def test_singleton():
    reset_kaishu_singleton()
    assert get_kaishu_source() is get_kaishu_source()


# ---- Real font ------------------------------------------------------------


@needs_kaishu
def test_loads_glyph(kaishu_env):
    src = MoeKaishuSource()
    assert src.is_ready()
    assert src.available_glyph_count() > 13000
    c = src.get_character("永")
    assert c.data_source == "moe_kaishu"
    assert c.strokes[0].outline


@needs_kaishu
def test_apply_cns_outline_mode_handles_moe_kaishu(kaishu_env):
    """Phase 5aw extends apply_cns_outline_mode to recognise moe_kaishu."""
    from stroke_order.sources.cns_font import apply_cns_outline_mode
    src = MoeKaishuSource()
    c = src.get_character("永")
    sk = apply_cns_outline_mode(c, "skeleton")
    assert len(sk.strokes) >= 1
    assert all(len(s.raw_track) >= 2 for s in sk.strokes)


# ---- AutoSource chain ordering ------------------------------------------


def test_autosource_includes_moe_kaishu():
    """AutoSource constructor exposes moe_kaishu attribute (5aw)."""
    from stroke_order.sources import AutoSource
    auto = AutoSource()
    assert isinstance(auto.moe_kaishu, MoeKaishuSource)


def test_autosource_priority_g0v_wins_over_moe_kaishu(kaishu_env):
    """g0v stroke-data sources still win for chars they cover —
    MoE Kaishu only fills in for chars g0v/MMH miss."""
    from stroke_order.sources import AutoSource
    auto = AutoSource()
    c = auto.get_character("永")
    # 永 is in g0v fixtures; MoE Kaishu must NOT pre-empt it.
    assert c.data_source == "g0v"


@needs_kaishu
def test_autosource_falls_through_to_moe_kaishu_when_no_stroke_data(
    kaishu_env, monkeypatch,
):
    """Stub g0v/MMH so AutoSource falls through to MoE Kaishu."""
    from stroke_order.sources import AutoSource
    class _Boom:
        def get_character(self, char):
            raise CharacterNotFound(f"stub: {char}")
    auto = AutoSource(primary=_Boom(), secondary=_Boom())
    c = auto.get_character("永")   # MoE Kaishu has 永
    assert c.data_source == "moe_kaishu"


def test_regionauto_includes_moe_kaishu():
    from stroke_order.sources import RegionAutoSource
    r = RegionAutoSource("tw")
    assert isinstance(r.moe_kaishu, MoeKaishuSource)


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


def test_api_kaishu_status_payload_shape(client):
    r = client.get("/api/kaishu-status")
    assert r.status_code == 200
    d = r.json()
    for key in ("font_file", "ready", "glyph_count",
                "attribution", "license", "license_url"):
        assert key in d
    assert "教育部" in d["attribution"]
    assert "楷書" in d["attribution"]
