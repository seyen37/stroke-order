"""Phase 5dc: 鏤空字／噴漆字模——橋接幾何、拓撲不變量與 API 契約。

合成 mask 先行（§8.5：合成形狀先於真字），字型相依的 API 測試
以 needs_kaishu 守門（沿用 test_zentangle_outline 慣例）。
"""
from pathlib import Path

import numpy as np
import pytest

from stroke_order.exporters.stencil import (
    _label,
    _outside,
    add_frame,
    carve_stencil_bridges,
    connect_cutout_components,
    render_stencil_dxf,
    render_stencil_gcode,
    render_stencil_svg,
    stencil_geometry,
)

_TEST_KAISHU_FONT = "/tmp/moe-kaishu/edukai-5.1_20251208.ttf"
needs_kaishu = pytest.mark.skipif(
    not Path(_TEST_KAISHU_FONT).exists(),
    reason="MoE Kaishu absent; copy edukai-5.1*.ttf to /tmp/moe-kaishu/",
)


# ---------------------------------------------------------------------------
# 合成形狀：口（方環）與 三（三橫）
# ---------------------------------------------------------------------------


def _ring_mask(n: int = 100, outer: int = 10, inner: int = 30) -> np.ndarray:
    """口字形：方環（黑），中心為封閉白孔。"""
    m = np.zeros((n, n), dtype=bool)
    m[outer:n - outer, outer:n - outer] = True
    m[inner:n - inner, inner:n - inner] = False
    return m


def _three_bars_mask(n: int = 120) -> np.ndarray:
    """三字形：三條互不相連的橫槓。"""
    m = np.zeros((n, n), dtype=bool)
    for y0 in (20, 55, 90):
        m[y0:y0 + 10, 15:n - 15] = True
    return m


def _n_holes(mask: np.ndarray) -> int:
    _lab, n = _label(~mask & ~_outside(mask))
    return n


def test_5dc_ring_has_one_hole():
    assert _n_holes(_ring_mask()) == 1


def test_5dc_stencil_bridges_rescue_island():
    """噴漆模板：鑿橋後孔洞消失（中心島與外部連通＝不會掉）。"""
    m = _ring_mask()
    n = carve_stencil_bridges(m, bridge_px=4, bridge_count=4)
    assert n == 1                       # 橋接了 1 個孔
    assert _n_holes(m) == 0             # 孔已接回外部
    assert m.any()                      # 環本體仍在（沒整個鑿光）


def test_5dc_stencil_two_bridges_variant():
    m = _ring_mask()
    carve_stencil_bridges(m, bridge_px=4, bridge_count=2)
    assert _n_holes(m) == 0


def test_5dc_cutout_connects_components():
    """鏤空字：三條斷開橫槓補連筋後成單一連通件。"""
    m = _three_bars_mask()
    _lab, before = _label(m)
    assert before == 3
    added = connect_cutout_components(m, bridge_px=4)
    _lab, after = _label(m)
    assert after == 1
    assert added >= 2                   # 至少兩道連筋


def test_5dc_cutout_frame_hangs_everything():
    """邊框模式：加框＋連筋後全部掛在同一件上（含框）。"""
    m = _three_bars_mask()
    add_frame(m, frame_px=5)
    connect_cutout_components(m, bridge_px=4)
    _lab, n = _label(m)
    assert n == 1
    assert m[0, :].all() and m[:, 0].all()      # 框帶存在


# ---------------------------------------------------------------------------
# 幾何收集器（合成閉環直接餵，不需字型）
# ---------------------------------------------------------------------------


def _ring_polys(em: float = 2048.0):
    """EM 座標的口字形閉環（外環＋內環，even-odd 成環帶）。"""
    o, i = em * 0.1, em * 0.35
    outer = [(o, o), (em - o, o), (em - o, em - o), (o, em - o)]
    inner = [(i, i), (em - i, i), (em - i, em - i), (i, em - i)]
    return [outer, inner]


def test_5dc_geometry_stencil_end_to_end():
    loops, w_mm, h_mm, stats = stencil_geometry(
        [_ring_polys()], kind="stencil",
        char_height_mm=40, bridge_width_mm=2)
    assert stats["holes_bridged"] == 1
    assert stats["cut_loops"] >= 2      # 橋接後外環＋內側環群
    assert loops and w_mm > 40 and h_mm > 40   # 含板邊
    # 所有座標落在板面內
    for loop in loops:
        for x, y in loop:
            assert -0.01 <= x <= w_mm + 0.01
            assert -0.01 <= y <= h_mm + 0.01


def test_5dc_geometry_cutout_multi_char():
    ring = _ring_polys()
    loops, _w, _h, stats = stencil_geometry(
        [ring, ring], kind="cutout",
        char_height_mm=40, frame=True, frame_width_mm=3)
    assert stats["components_before"] == 2
    assert stats["cut_loops"] >= 1
    assert loops


def test_5dc_svg_mm_contract():
    """全站契約（5bt audit）：mm width/height ＝ viewBox 跨度。"""
    import re
    loops, w_mm, h_mm, _s = stencil_geometry(
        [_ring_polys()], kind="stencil", char_height_mm=30)
    svg = render_stencil_svg(loops, w_mm, h_mm, kind="stencil")
    m = re.search(r'width="([\d.]+)mm" height="([\d.]+)mm" '
                  r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    assert m
    assert float(m.group(1)) == float(m.group(3))
    assert float(m.group(2)) == float(m.group(4))


def test_5dc_dxf_and_gcode_emitters():
    loops, _w, h_mm, _s = stencil_geometry(
        [_ring_polys()], kind="stencil", char_height_mm=30)
    dxf = render_stencil_dxf(loops)
    assert "SECTION" in dxf and "POLYLINE" in dxf and "CUT" in dxf
    gc = render_stencil_gcode(loops, height_mm=h_mm)
    assert "G21" in gc and "G90" in gc and "M5" in gc
    assert gc.count("; --- loop") == len(loops)


# ---------------------------------------------------------------------------
# API（真字型，缺字型時 skip；422/400 分支不需字型）
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


def test_5dc_api_rejects_bad_kind_and_source(client):
    assert client.get("/api/stencil?chars=明&kind=nope").status_code == 422
    assert client.get(
        "/api/stencil?chars=明&source=bogus").status_code == 422


@needs_kaishu
def test_5dc_api_stencil_svg(client, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_KAISHU_FONT_FILE", _TEST_KAISHU_FONT)
    from stroke_order.sources.moe_kaishu import reset_kaishu_singleton
    reset_kaishu_singleton()
    r = client.get("/api/stencil?chars=明&kind=stencil&format=svg")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]
    assert int(r.headers["x-stencil-holes"]) >= 2   # 明＝日+月 至少 2 孔
    assert 'data-stencil-kind="stencil"' in r.text


@needs_kaishu
def test_5dc_api_cutout_dxf(client, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_KAISHU_FONT_FILE", _TEST_KAISHU_FONT)
    from stroke_order.sources.moe_kaishu import reset_kaishu_singleton
    reset_kaishu_singleton()
    r = client.get("/api/stencil?chars=三&kind=cutout&format=dxf")
    assert r.status_code == 200
    assert "POLYLINE" in r.text
    assert int(r.headers["x-stencil-components"]) >= 1
