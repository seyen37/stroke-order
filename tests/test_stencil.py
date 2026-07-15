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


def _cut_gaps(orig: np.ndarray, carved: np.ndarray,
              bridge_px: int = 4) -> list[tuple[int, int]]:
    """回傳每道截口的 (高, 寬) bbox；截口＝原為墨、鑿橋後變白之處。"""
    cut = orig & ~carved
    lab, n = _label(cut)
    gaps: list[tuple[int, int]] = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if len(ys) < bridge_px:               # 去斑（AA 級碎點）
            continue
        gaps.append((int(ys.max() - ys.min() + 1),
                     int(xs.max() - xs.min() + 1)))
    return gaps


def test_5dm_stencil_cuts_at_corners_not_midspan():
    """5dm（方正大黑連筋切法）：軸向對齊截口、直筆中段不截斷、轉角穿近牆。

    5dm 改動：橋接逃逸限純軸向（上/下/左/右），只穿「近牆」——截口為
    乾淨軸向矩形（像被內縮的筆畫端），取代 5dl 的 ±70° 斜向扇形。
    直筆中段完整仍是鐵則。
    """
    orig = _ring_mask()       # 環帶＝rows/cols 10..89、孔 30..69
    m = orig.copy()
    carve_stencil_bridges(m, bridge_px=4, bridge_count=4)
    assert _n_holes(m) == 0                     # 孔仍被接回外部
    # 上下橫筆與左右豎筆的「中段」完整無截斷（核心可讀性鐵則）
    assert m[10:30, 48:53].all(), "上橫中段被截斷"
    assert m[70:90, 48:53].all(), "下橫中段被截斷"
    assert m[48:53, 10:30].all(), "左豎中段被截斷"
    assert m[48:53, 70:90].all(), "右豎中段被截斷"
    # 5dm：每道截口皆軸向對齊（bbox 至少一邊 ≤ 橋寬＋容差＝薄矩形）。
    gaps = _cut_gaps(orig, m, bridge_px=4)
    assert len(gaps) >= 2, f"大孔應 ≥ 2 截口，實得 {len(gaps)}"
    for gh, gw in gaps:
        assert min(gh, gw) <= 7, f"截口非軸向（bbox {gh}x{gw}）"


def test_5dm_stencil_minimal_bridges_small_vs_large():
    """5dm：小孔 1 橋、大孔 2 橋（自動最少橋數、對邊近牆各一、可讀性優先）。"""
    # 大孔（環，孔 span 40 ≥ 30）→ 恰 2 道軸向截口（近牆修正後不再併橋）。
    orig = _ring_mask()
    big = orig.copy()
    carve_stencil_bridges(big, bridge_px=4, bridge_count=4)
    gaps_big = _cut_gaps(orig, big, bridge_px=4)
    assert len(gaps_big) == 2, f"大孔應恰 2 截口，實得 {len(gaps_big)}"
    # 小孔（span < 30）→ 1 橋。
    small0 = np.zeros((60, 60), bool)
    small0[15:45, 15:45] = True                 # 30×30 方塊
    small0[22:38, 22:38] = False                # 16×16 孔（span 16 < 30）
    small = small0.copy()
    carve_stencil_bridges(small, bridge_px=4, bridge_count=4)
    assert _n_holes(small) == 0                 # 小孔接回
    assert len(_cut_gaps(small0, small, bridge_px=4)) == 1, "小孔應恰 1 橋"


def test_5dl_cutout_frame_spokes_two_ties():
    """5dl：含框時字件以最近框邊垂直輻條接框，1~2 筋、連通、不交叉。"""
    m = _ring_mask()
    add_frame(m, frame_px=5)
    added = connect_cutout_components(m, bridge_px=4)
    _lab, n = _label(m)
    assert n == 1                               # 連成單件
    assert added == 2                           # 環（單件）補 2 輻條
    # 兩輻條落在環與框之間的間隙帶、且為兩道分離的筋（非交叉）
    gap = np.ones_like(m)
    gap[10:90, 10:90] = False
    gap[:5, :] = gap[-5:, :] = False
    gap[:, :5] = gap[:, -5:] = False
    _labs, k = _label(m & gap)
    assert k == 2, f"間隙帶應恰兩道分離連筋，實得 {k}"


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
