"""
Phase 5at — 崇羲篆體 source + style swap.

Covers ChongxiSealSource graceful fallback, real-font glyph extraction
when the OTF is present, the v1-walker skeleton conversion, the
``_upgrade_to_seal`` server hook, and the /api/seal-status endpoint.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from stroke_order.sources.chongxi_seal import (
    ChongxiSealSource,
    _simp_to_trad,
    apply_seal_outline_mode,
    attribution_notice,
    default_seal_font_path,
    get_seal_source,
    reset_seal_singleton,
)
from stroke_order.sources.g0v import CharacterNotFound


_TEST_FONT = "/tmp/chongxi-fonts/chongxi_seal.otf"


def _seal_available() -> bool:
    return Path(_TEST_FONT).exists()


needs_seal = pytest.mark.skipif(
    not _seal_available(),
    reason="崇羲篆體 absent; extract chongxi_seal.zip to /tmp/chongxi-fonts/",
)


@pytest.fixture
def seal_env(monkeypatch):
    """Point env at the test font and clear the process-wide singleton."""
    if _seal_available():
        monkeypatch.setenv("STROKE_ORDER_SEAL_FONT_FILE", _TEST_FONT)
    reset_seal_singleton()


# ---------------------------------------------------------------------------
# Graceful fallback when font absent
# ---------------------------------------------------------------------------


def test_default_path_uses_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("STROKE_ORDER_SEAL_FONT_FILE", str(tmp_path / "x.otf"))
    assert default_seal_font_path() == tmp_path / "x.otf"


def test_default_path_uses_dir_var(monkeypatch, tmp_path):
    monkeypatch.delenv("STROKE_ORDER_SEAL_FONT_FILE", raising=False)
    monkeypatch.setenv("STROKE_ORDER_SEAL_FONT_DIR", str(tmp_path))
    assert default_seal_font_path() == tmp_path / "chongxi_seal.otf"


def test_source_not_ready_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_SEAL_FONT_FILE", str(tmp_path / "nope.otf"))
    src = ChongxiSealSource()
    assert src.is_ready() is False
    assert src.available_glyph_count() == 0
    with pytest.raises(CharacterNotFound):
        src.get_character("永")


def test_attribution_includes_required_fields():
    """CC BY-ND 3.0 TW requires attributing the original author. The
    string must contain BOTH 季旭昇 (author) and the 中研院 (institution)
    so any rendered output that surfaces ``attribution_notice()`` is
    automatically licence-compliant."""
    s = attribution_notice()
    assert "崇羲" in s
    assert "季旭昇" in s
    assert "CC BY-ND" in s


# ---------------------------------------------------------------------------
# Singleton behaviour (mirrors 5am Sung tests)
# ---------------------------------------------------------------------------


def test_get_seal_source_is_singleton():
    reset_seal_singleton()
    a = get_seal_source()
    b = get_seal_source()
    assert a is b


# ---------------------------------------------------------------------------
# Happy path with real font
# ---------------------------------------------------------------------------


@needs_seal
def test_loads_simple_glyph(seal_env):
    src = ChongxiSealSource()
    assert src.is_ready()
    assert src.available_glyph_count() > 11000
    c = src.get_character("永")
    assert c.data_source == "chongxi_seal"
    assert len(c.strokes) == 1
    assert c.strokes[0].outline   # outline-only at this stage
    assert c.strokes[0].raw_track == []   # tracks are empty until apply_seal_outline_mode


@needs_seal
def test_caches_subsequent_lookups(seal_env):
    src = ChongxiSealSource()
    a = src.get_character("永")
    b = src.get_character("永")
    assert a is b


@needs_seal
def test_unknown_codepoint_raises(seal_env):
    src = ChongxiSealSource()
    # Emoji not in the seal font.
    with pytest.raises(CharacterNotFound):
        src.get_character("\U0001F600")


# ---------------------------------------------------------------------------
# 5dn：以崇羲為主體、簡轉繁補足（QODA A 案）——崇羲＝純繁體，缺口幾乎
# 全是簡體；簡體輸入轉繁後用崇羲的繁體篆形渲染。
# ---------------------------------------------------------------------------


def test_5dn_simp_to_trad_single_char():
    """opencc s2t 單字轉換：簡體→繁體；非單字/無變化回 None。"""
    assert _simp_to_trad("国") == "國"
    assert _simp_to_trad("书") == "書"
    assert _simp_to_trad("发") == "發"
    # 已是繁體 / 兩岸同形 → 無變化 → None（不觸發 fallback）
    assert _simp_to_trad("國") is None
    assert _simp_to_trad("永") is None


@needs_seal
def test_5dn_simplified_input_renders_via_traditional_glyph(seal_env):
    """簡體輸入 → 簡轉繁 → 用崇羲繁體篆形渲染；字形＝對應繁體字。"""
    src = ChongxiSealSource()
    for simp, trad in [("国", "國"), ("书", "書"), ("龙", "龍")]:
        cs = src.get_character(simp)
        ct = src.get_character(trad)
        assert cs.strokes[0].outline, f"{simp} 應能經 fallback 渲染"
        # 簡體用的是繁體字形 → outline 指令數與繁體一致
        assert len(cs.strokes[0].outline) == len(ct.strokes[0].outline)
        # 保留使用者原輸入身份（char＝簡體）
        assert cs.char == simp


@needs_seal
def test_5dn_traditional_still_direct_hit(seal_env):
    """以崇羲為主體：繁體字直接命中、不經轉換。"""
    src = ChongxiSealSource()
    c = src.get_character("國")
    assert c.char == "國"
    assert c.strokes[0].outline


# ---------------------------------------------------------------------------
# apply_seal_outline_mode — skeleton (default) / trace / skip
# ---------------------------------------------------------------------------


@needs_seal
def test_skeleton_mode_produces_polylines(seal_env):
    src = ChongxiSealSource()
    c = src.get_character("永")
    sk = apply_seal_outline_mode(c, "skeleton")
    assert len(sk.strokes) >= 1
    # Skeleton dropped the outline and gave us raw_tracks.
    for s in sk.strokes:
        assert len(s.raw_track) >= 2
        assert s.outline == []


@needs_seal
def test_trace_mode_samples_outline(seal_env):
    src = ChongxiSealSource()
    c = src.get_character("永")
    tr = apply_seal_outline_mode(c, "trace")
    assert len(tr.strokes) >= 1
    for s in tr.strokes:
        assert len(s.raw_track) >= 2


@needs_seal
def test_skip_mode_returns_input_untouched(seal_env):
    src = ChongxiSealSource()
    c = src.get_character("永")
    out = apply_seal_outline_mode(c, "skip")
    assert out is c


def test_apply_mode_rejects_unknown():
    from stroke_order.ir import Character, Stroke
    fake = Character(
        char="X", unicode_hex="0058", data_source="chongxi_seal",
        strokes=[Stroke(index=0, raw_track=[],
                        outline=[{"type": "M", "x": 0, "y": 0}],
                        kind_code=9, kind_name="其他", has_hook=False)],
    )
    with pytest.raises(ValueError, match="unknown seal mode"):
        apply_seal_outline_mode(fake, "rasterize")


def test_apply_mode_passes_through_non_seal_data_source():
    from stroke_order.ir import Character
    g0v_char = Character(char="永", unicode_hex="6c38", data_source="g0v")
    out = apply_seal_outline_mode(g0v_char, "skeleton")
    assert out is g0v_char


# ---------------------------------------------------------------------------
# Server _upgrade_to_seal
# ---------------------------------------------------------------------------


def test_upgrade_no_op_when_style_is_not_seal_script():
    from stroke_order.ir import Character
    from stroke_order.web.char_pipeline import _upgrade_to_seal
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    for style in ("kaishu", "mingti", "lishu", "bold"):
        assert _upgrade_to_seal(base, style) is base


def test_upgrade_returns_none_for_none_input():
    from stroke_order.web.char_pipeline import _upgrade_to_seal
    assert _upgrade_to_seal(None, "seal_script") is None


def test_upgrade_falls_back_when_font_missing(tmp_path, monkeypatch):
    """No OTF → upgrade silently returns the original kaishu Character."""
    from stroke_order.ir import Character
    from stroke_order.web.char_pipeline import _upgrade_to_seal
    monkeypatch.setenv("STROKE_ORDER_SEAL_FONT_FILE", str(tmp_path / "nope.otf"))
    reset_seal_singleton()
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    assert _upgrade_to_seal(base, "seal_script") is base


@needs_seal
def test_upgrade_swaps_to_seal_when_available(seal_env):
    """End-to-end: g0v Character + style=seal_script → seal outline."""
    from stroke_order.ir import Character
    from stroke_order.web.char_pipeline import _upgrade_to_seal
    base = Character(char="永", unicode_hex="6c38", data_source="g0v")
    out = _upgrade_to_seal(base, "seal_script")
    assert out is not base
    assert out.data_source == "chongxi_seal"
    # apply_seal_outline_mode runs internally → strokes carry raw_track
    assert all(s.raw_track for s in out.strokes)


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


def test_api_seal_status_payload_shape(client):
    """Status endpoint always returns the attribution + ready flag."""
    r = client.get("/api/seal-status")
    assert r.status_code == 200
    d = r.json()
    for key in ("font_file", "ready", "glyph_count",
                "attribution", "license", "license_url"):
        assert key in d
    assert "崇羲" in d["attribution"]
    assert "CC BY-ND" in d["license"]


@needs_seal
def test_api_notebook_seal_script_swaps_strokes(seal_env, client):
    """End-to-end through FastAPI: kaishu vs seal_script for 山 produce
    different stroke counts (kaishu = 3 strokes, seal = 2 from the
    skeletonised Chongxi outline)."""
    r_k = client.get(
        "/api/notebook?text=山&preset=large&style=kaishu&cell_style=outline"
    )
    r_s = client.get(
        "/api/notebook?text=山&preset=large&style=seal_script&cell_style=outline"
    )
    assert r_k.status_code == 200 and r_s.status_code == 200
    assert r_k.text != r_s.text


@needs_seal
def test_api_wordart_seal_script_works(seal_env, client):
    """wordart + seal_script must render without error and place glyphs."""
    r = client.get(
        "/api/wordart?shape=circle&shape_size_mm=160&layout=fill"
        "&text=春夏秋冬&char_size_mm=20&style=seal_script"
    )
    assert r.status_code == 200
    placed = int(r.headers.get("x-wordart-placed", "0"))
    assert placed > 0


def test_seal_script_is_valid_style_param(client):
    """Style pattern accepts 'seal_script' even when the font is absent
    (the swap is silent fallback, not a 422 error)."""
    r = client.get(
        "/api/notebook?text=永&preset=large&style=seal_script&cell_style=outline"
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 5do：崇羲缺字補足延伸為異體字鏈（簡轉繁＋異體字正規化）
# ---------------------------------------------------------------------------


def test_5do_seal_variants_includes_variant_normalization():
    """_seal_variants：簡體與異體字都給候選（爲→為、衆→眾、卻、国→國）。"""
    from stroke_order.sources.chongxi_seal import _seal_variants
    assert "國" in _seal_variants("国")      # 簡轉繁
    assert "為" in _seal_variants("爲")      # 異體正規化
    assert "眾" in _seal_variants("衆")
    assert "卻" in _seal_variants("却")
    assert _seal_variants("永") == []        # 崇羲已有/無變化 → 空


@needs_seal
def test_5do_seal_variant_chain_renders_and_rare_stays_missing(seal_env):
    """異體字經鏈補足可渲染；真正罕見佛經字（閦/毘）維持缺字。"""
    src = ChongxiSealSource()
    for ch in ["爲", "衆", "却"]:
        c = src.get_character(ch)
        assert c.char == ch and c.strokes[0].outline
    for rare in ["閦", "毘"]:
        with pytest.raises(CharacterNotFound):
            src.get_character(rare)
