"""Phase 5dc: 鏤空字／噴漆字模——橋接幾何、拓撲不變量與 API 契約。

合成 mask 先行（§8.5：合成形狀先於真字），字型相依的 API 測試
以 needs_kaishu 守門（沿用 test_zentangle_outline 慣例）。
"""
from pathlib import Path

import numpy as np
import pytest

from stroke_order.exporters.stencil import (
    _hole_corners,
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
# 5dg：轉角截斷（噴漆字）＋對稱雙連筋（鏤空字）——使用者實測回饋
# ---------------------------------------------------------------------------


def test_5dg_hole_corners_detects_rect_corners():
    """方環孔洞應偵測出 4 個轉角（±容差：RDP 頂點可能貼角重複）。"""
    m = _ring_mask()
    hole = ~m & ~_outside(m)
    corners = _hole_corners(hole)
    assert 4 <= len(corners) <= 6
    # 轉角都落在孔洞 bbox（30..69）的角落附近（離某個角 < 6px）
    cs = [(30, 30), (69, 30), (30, 69), (69, 69)]
    for x, y in corners:
        assert min((x - cx) ** 2 + (y - cy) ** 2
                   for cx, cy in cs) < 36, (x, y)


def test_5dg_stencil_cuts_at_corners_not_midspan():
    """5dg 核心規則：直筆中段不截斷、截斷點在轉折處。"""
    m = _ring_mask()          # 環帶＝rows/cols 10..89、孔 30..69
    carve_stencil_bridges(m, bridge_px=4, bridge_count=4)
    assert _n_holes(m) == 0                     # 孔仍被接回外部
    # 上下橫筆與左右豎筆的「中段」完整無截斷
    assert m[10:30, 48:53].all(), "上橫中段被截斷"
    assert m[70:90, 48:53].all(), "下橫中段被截斷"
    assert m[48:53, 10:30].all(), "左豎中段被截斷"
    assert m[48:53, 70:90].all(), "右豎中段被截斷"
    # 四個轉角帶內各有白色截口（對角出口）
    assert (~m[12:30, 12:30]).any(), "左上轉角無截口"
    assert (~m[12:30, 70:88]).any(), "右上轉角無截口"
    assert (~m[70:88, 12:30]).any(), "左下轉角無截口"
    assert (~m[70:88, 70:88]).any(), "右下轉角無截口"


def test_5dg_cutout_symmetric_second_tie():
    """單字件掛框：第一筋之外補對稱第二筋（單線不穩固回饋）。"""
    m = _ring_mask()
    add_frame(m, frame_px=5)
    added = connect_cutout_components(m, bridge_px=4)
    _lab, n = _label(m)
    assert n == 1
    assert added == 2                           # 第一筋＋對稱第二筋
    # 兩筋落在環與框之間的間隙帶、且方位大致點對稱
    gap = np.ones_like(m)
    gap[10:90, 10:90] = False                   # 環 bbox（含孔）
    gap[:5, :] = gap[-5:, :] = False            # 框帶
    gap[:, :5] = gap[:, -5:] = False
    labs, k = _label(m & gap)
    assert k == 2, f"間隙帶應恰有兩道連筋，實得 {k}"
    c1 = np.argwhere(labs == 1).mean(axis=0) - 49.5
    c2 = np.argwhere(labs == 2).mean(axis=0) - 49.5
    assert float((c1 * c2).sum()) < 0, "兩筋未在點對稱方位"


def test_5dg_cutout_three_bars_each_gets_two_ties():
    """三＋框：每條橫槓恰兩筋（pass1 各一＋對稱各一）＝ 6 筋。"""
    m = _three_bars_mask()
    add_frame(m, frame_px=4)
    added = connect_cutout_components(m, bridge_px=4)
    _lab, n = _label(m)
    assert n == 1
    assert added == 6


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
