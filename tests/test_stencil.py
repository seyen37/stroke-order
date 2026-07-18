"""Phase 5dc: 鏤空字／噴漆字模——橋接幾何、拓撲不變量與 API 契約。

合成 mask 先行（§8.5：合成形狀先於真字），字型相依的 API 測試
以 needs_kaishu 守門（沿用 test_zentangle_outline 慣例）。
"""
from pathlib import Path

import numpy as np
import pytest

from stroke_order.exporters.stencil import (
    CUTTING_STYLES,
    DEFAULT_CUTTING_STYLE,
    CuttingStyle,
    _hole_corners,
    _label,
    _outside,
    add_frame,
    carve_stencil_bridges,
    connect_cutout_components,
    get_cutting_style,
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


# ---------------------------------------------------------------------------
# 5do：垂直置中（依墨邊界）＋噴漆字輪廓軸向去微段（平順化）
# ---------------------------------------------------------------------------


def test_5do_stencil_outline_smoothed_no_staircase():
    """5do：細化光柵（8px/mm）＋較大 RDP 容差 → 軸向邊平順、無階梯微段。

    黑體般的軸向方塊字模，輪廓頂點應精簡（無 1px 階梯鋸齒殘留）。
    """
    # 合成方塊字（軸向邊），墨佔 em 中段
    box = [[[(400.0, 400.0), (1600.0, 400.0), (1600.0, 1600.0),
             (400.0, 1600.0)]]]
    loops, _w, _h, _st = stencil_geometry(
        box, kind="stencil", char_height_mm=50, bridge_width_mm=2.0)
    # 一個實心方塊（無孔）→ 單一矩形環，平順化後頂點極少（≈4，容 AA 餘裕）
    main = max(loops, key=len)
    assert len(main) <= 8, f"軸向方塊輪廓應平順精簡，實得 {len(main)} 頂點"


def test_5do_stencil_centers_ink_vertically():
    """依墨實際 y-範圍垂直置中：即使字形偏在 em 框下半，也上下等距。"""
    # 合成字形：墨只佔 em 的下半（y 1100..1900）——舊法會沉底貼框。
    char_polys = [[[(500.0, 1100.0), (1500.0, 1100.0),
                    (1500.0, 1900.0), (500.0, 1900.0)]]]
    loops, w, h, st = stencil_geometry(
        char_polys, kind="stencil", char_height_mm=50, bridge_width_mm=2.0)
    ys = [y for lp in loops for _x, y in lp]
    top_gap = min(ys)
    bot_gap = h - max(ys)
    assert abs(top_gap - bot_gap) <= 0.6, (
        f"墨應垂直置中：上緣 {top_gap:.2f}mm vs 下緣 {bot_gap:.2f}mm")


# ---------------------------------------------------------------------------
# 5ef：切割風格 registry 重構——純 seam、行為逐位元保存（承 5dm §4/§5）
# ---------------------------------------------------------------------------


def test_5ef_registry_contract():
    """registry 契約：physical 存在、connect_depth=full、預設＝physical。"""
    assert DEFAULT_CUTTING_STYLE == "physical"
    assert "physical" in CUTTING_STYLES
    phys = CUTTING_STYLES["physical"]
    assert isinstance(phys, CuttingStyle)
    assert phys.key == "physical"
    assert phys.connect_depth == "full"
    assert phys.label                      # 有顯示名（供 UI/header）
    # get_cutting_style：已知回傳同物件、未知拋 KeyError
    assert get_cutting_style("physical") is phys
    with pytest.raises(KeyError):
        get_cutting_style("no_such_style")


def test_5ef_default_style_is_physical_byte_identical():
    """行為保存鐵證：不傳 style（預設）與明示 style='physical' 產出**逐位元
    相同**的 loops＋stats（stencil 與 cutout 兩路徑都驗）。"""
    ring = _ring_polys()
    for kind, kwargs in (("stencil", {}),
                         ("cutout", {"frame": True, "frame_width_mm": 3})):
        d_loops, d_w, d_h, d_st = stencil_geometry(
            [ring], kind=kind, char_height_mm=40, bridge_width_mm=2, **kwargs)
        p_loops, p_w, p_h, p_st = stencil_geometry(
            [ring], kind=kind, style="physical",
            char_height_mm=40, bridge_width_mm=2, **kwargs)
        assert d_loops == p_loops, f"{kind}: 預設與 physical loops 不一致"
        assert (d_w, d_h) == (p_w, p_h)
        assert d_st == p_st
        assert d_st["style"] == "physical"      # stats 記錄所用風格


def test_5ef_unknown_connect_depth_raises(monkeypatch):
    """seam 守衛：connect_depth 非已實作值的風格 → NotImplementedError（證明
    dispatch 真的讀 connect_depth、非死參數；full/envelope 皆已實作，故用一個
    尚未實作的假 depth）。"""
    fake = CuttingStyle(key="depth_fake", label="假深度",
                        connect_depth="not_a_real_depth")  # type: ignore[arg-type]
    monkeypatch.setitem(CUTTING_STYLES, "depth_fake", fake)
    with pytest.raises(NotImplementedError):
        stencil_geometry([_ring_polys()], kind="stencil",
                         style="depth_fake", char_height_mm=40)


def test_5ef_api_rejects_bad_style(client):
    """API 契約：未知切割風格 → 422（在字型載入前擋下，無需字型）。"""
    assert client.get(
        "/api/stencil?chars=明&style=bogus").status_code == 422
    # 合法 physical 不因 style 被擋（缺字型會走到 400/需字型，但非 422 風格錯）
    r = client.get("/api/stencil?chars=明&style=physical")
    assert r.status_code != 422


@needs_kaishu
def test_5ef_api_style_header(client, monkeypatch):
    """有字型時，回應帶 X-Stencil-Style 標頭＝所用風格。"""
    monkeypatch.setenv("STROKE_ORDER_KAISHU_FONT_FILE", _TEST_KAISHU_FONT)
    from stroke_order.sources.moe_kaishu import reset_kaishu_singleton
    reset_kaishu_singleton()
    r = client.get("/api/stencil?chars=明&kind=stencil&style=physical")
    assert r.status_code == 200
    assert r.headers["x-stencil-style"] == "physical"


# ---------------------------------------------------------------------------
# 5eg：envelope（方正簡潔）第二切割風格——只斷外框、深層 counter 留島
# ---------------------------------------------------------------------------


def _nested_ring_mask(n: int = 120):
    """回狀雙環：外環(ink)＋內環(ink)；中間環白孔(depth1)＋中心白孔(depth2)。"""
    m = np.zeros((n, n), dtype=bool)
    m[10:n - 10, 10:n - 10] = True
    m[25:n - 25, 25:n - 25] = False          # 外方塊挖空 → 外環
    m[40:n - 40, 40:n - 40] = True           # 內方塊
    m[52:n - 52, 52:n - 52] = False          # 內方塊挖空 → 內環
    return m


def _nested_ring_polys(em: float = 2048.0):
    """回：四同心方框（even-odd → 外環＋內環兩圈墨、中間環＋中心兩白孔）。"""
    def sq(f):
        return [(f, f), (em - f, f), (em - f, em - f), (f, em - f)]
    return [sq(em * 0.08), sq(em * 0.20), sq(em * 0.34), sq(em * 0.44)]


def test_5eg_hole_depth_nested():
    """孔巢狀深度：回狀外環 depth1、中心 depth2；單環＝depth1。"""
    from stroke_order.exporters.stencil import _hole_depths
    m = _nested_ring_mask()
    lab, n = _label(~m & ~_outside(m))
    assert n == 2
    assert sorted(_hole_depths(m, lab, n).values()) == [1, 2]
    # 單環（口）只有一個 depth1 孔
    s = _ring_mask()
    labs, ns = _label(~s & ~_outside(s))
    assert ns == 1
    assert list(_hole_depths(s, labs, ns).values()) == [1]


def test_5eg_envelope_leaves_deep_island():
    """envelope（max_depth=1）只鑿最外圈、深層孔留島；full 全鑿殘腔 0。"""
    m = _nested_ring_mask()
    full = m.copy()
    b_full = carve_stencil_bridges(full, 6, max_depth=None)
    env = m.copy()
    b_env = carve_stencil_bridges(env, 6, max_depth=1)
    assert (b_full, _n_holes(full)) == (2, 0)     # 全連派：2 橋、殘腔 0
    assert (b_env, _n_holes(env)) == (1, 1)       # 外框派：1 橋、中心留 1 島


def test_5eg_envelope_equals_full_on_single_ring():
    """單環字（口/日）envelope 與 full 無異——都只有 depth1 孔、都鑿。"""
    s = _ring_mask()
    full = s.copy()
    env = s.copy()
    assert carve_stencil_bridges(full, 6, max_depth=None) == 1
    assert carve_stencil_bridges(env, 6, max_depth=1) == 1
    assert _n_holes(full) == _n_holes(env) == 0


def test_5eg_registry_has_envelope():
    assert "envelope" in CUTTING_STYLES
    env = CUTTING_STYLES["envelope"]
    assert env.connect_depth == "envelope"
    assert env.label == "方正簡潔"


def test_5eg_geometry_style_dispatch():
    """stencil_geometry：巢狀字 physical 鑿全部孔、envelope 只鑿外圈。"""
    nested = _nested_ring_polys()
    _l, _w, _h, phys = stencil_geometry(
        [nested], kind="stencil", style="physical",
        char_height_mm=50, bridge_width_mm=2)
    _l2, _w2, _h2, env = stencil_geometry(
        [nested], kind="stencil", style="envelope",
        char_height_mm=50, bridge_width_mm=2)
    assert phys["holes_bridged"] == 2 and phys["style"] == "physical"
    assert env["holes_bridged"] == 1 and env["style"] == "envelope"


def test_5eg_cutout_ignores_envelope():
    """cutout 恆全連（envelope 的深層留島會讓字件掉光）——兩風格結果相同。"""
    ring = _ring_polys()
    _l, _w, _h, phys = stencil_geometry(
        [ring, ring], kind="cutout", style="physical",
        char_height_mm=40, frame=True, frame_width_mm=3)
    _l2, _w2, _h2, env = stencil_geometry(
        [ring, ring], kind="cutout", style="envelope",
        char_height_mm=40, frame=True, frame_width_mm=3)
    assert phys["bridges_added"] == env["bridges_added"]
    assert phys["components_before"] == env["components_before"]


def test_5eg_api_accepts_envelope(client):
    """API：style=envelope 合法（非 422）；未知風格仍 422。"""
    assert client.get(
        "/api/stencil?chars=明&style=envelope").status_code != 422
    assert client.get(
        "/api/stencil?chars=明&style=nope").status_code == 422
