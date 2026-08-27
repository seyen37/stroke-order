"""
R1b — 昭源環方可變字重軸（字重滑桿）。

雙軌設計是本輪的核心：``weight=None`` 走靜態 700B（行為與記憶體足跡與
R1b 之前完全相同）、給 weight 才開可變字體（RSS +75 MB）。前兩項測試就是
這條不變式的鎖——沒有它，「雙軌」只是註解裡的宣稱。

另鎖 :func:`resolve_overlaps`：可變字體保留重疊輪廓（重疊消除無法沿 wght
軸內插），拿 even-odd 直接畫會打出假洞（實測「明」洞 4→10、墨面積 −6.2%）。

字型相依測試以 needs_vf / needs_static 守門，比照 test_chiron_round。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

# D3：本檔以光柵化/PDF 為主——整檔標 slow（開發可 -m 'not slow' 跳過）
pytestmark = pytest.mark.slow

from stroke_order.exporters import zentangle as zt
from stroke_order.sources.chiron_round import (
    ChironRoundSource,
    STATIC_WEIGHT,
    WEIGHT_MAX,
    WEIGHT_MIN,
    default_round_font_path,
    default_round_vf_path,
    resolve_overlaps,
)
from stroke_order.sources.g0v import CharacterNotFound

_ROOT = Path(__file__).resolve().parent.parent

needs_vf = pytest.mark.skipif(
    not default_round_vf_path().exists(),
    reason="昭源環方可變字體缺；執行 scripts/render_fetch_fonts.sh "
           "或設 STROKE_ORDER_ROUND_VF_FILE",
)
needs_static = pytest.mark.skipif(
    not default_round_font_path().exists(),
    reason="昭源環方靜態字型缺；執行 scripts/render_fetch_fonts.sh",
)


# ---------------------------------------------------------------------------
# 雙軌不變式——本輪的核心承諾，缺這兩條「雙軌」就只是註解
# ---------------------------------------------------------------------------


@needs_static
def test_r1b_no_weight_output_is_bit_identical_to_before():
    """不給 weight → 逐點等同靜態路徑（零回歸鐵證）。

    R1b 之前 ``extract_outline_polylines`` 只有這一條路；新增 weight 參數
    不得讓既有呼叫的輸出漂一個小數位。
    """
    src = ChironRoundSource()
    direct = src.get_character("國").strokes[0].outline
    via_pipeline = zt.extract_outline_polylines("國", source="chiron_round")
    from stroke_order.sources.cns_font import _outline_to_polylines
    assert via_pipeline == _outline_to_polylines(direct, samples_per_curve=8)


@needs_static
def test_r1b_no_weight_never_opens_the_variable_font(tmp_path):
    """不給 weight 時 VF 檔完全不被開啟——這就是「預設不付 RSS」的實作點。

    把 VF 路徑指到不存在的檔：靜態路徑仍須完全正常。若哪天有人把 VF 提到
    ``__init__`` 或 ``_load_font`` 裡預先載入，這條會紅。
    """
    src = ChironRoundSource(vf_path=tmp_path / "not-there.otf")
    polys = zt.extract_outline_polylines("國", source="chiron_round")
    assert polys and src.get_character("國").strokes[0].outline
    assert src._vf is None, "不給 weight 卻載入了可變字體"


@needs_vf
def test_r1b_weight_path_loads_vf_lazily():
    """反向：真的給 weight 才載入 VF。"""
    src = ChironRoundSource()
    assert src._vf is None
    src.get_character("國", weight=500)
    assert src._vf is not None


# ---------------------------------------------------------------------------
# 參數驗證（字型無關）
# ---------------------------------------------------------------------------


def test_r1b_clamp_constants_are_sane():
    assert WEIGHT_MIN < STATIC_WEIGHT <= WEIGHT_MAX
    assert (WEIGHT_MIN, WEIGHT_MAX) == (300, 800)


def test_r1b_only_chiron_declares_weight_support():
    supported = {k for k in zt.SOURCE_REGISTRY if zt.source_supports_weight(k)}
    assert supported == {"chiron_round"}


def test_r1b_weight_on_unsupported_source_raises():
    with pytest.raises(ValueError, match="no weight axis"):
        zt.extract_outline_polylines("國", source="noto_hei", weight=500)


@needs_vf
@pytest.mark.parametrize("bad", [WEIGHT_MIN - 1, WEIGHT_MAX + 1, 0, 1000])
def test_r1b_weight_out_of_range_raises(bad):
    with pytest.raises(ValueError, match="weight must be within"):
        ChironRoundSource().get_character("國", weight=bad)


def test_r1b_missing_vf_raises_character_not_found(tmp_path):
    """VF 缺檔＋給 weight → CharacterNotFound（非 IOError/500）。"""
    src = ChironRoundSource(vf_path=tmp_path / "nope.otf")
    assert src.vf_ready() is False
    with pytest.raises(CharacterNotFound):
        src.get_character("國", weight=500)


# ---------------------------------------------------------------------------
# resolve_overlaps——可變字體重疊輪廓補正
# ---------------------------------------------------------------------------


def test_resolve_overlaps_merges_two_overlapping_squares():
    """兩個同向重疊方框 → 併成一個輪廓（even-odd 下原本會打出假洞）。"""
    a = [(0, 0), (100, 0), (100, 100), (0, 100)]
    b = [(50, 50), (150, 50), (150, 150), (50, 150)]
    out = resolve_overlaps([a, b])
    assert len(out) == 1, f"重疊未被吸收：{len(out)} 個輪廓"


def test_resolve_overlaps_keeps_a_real_hole():
    """外環＋反向內環＝真的洞，不得被填掉。"""
    outer = [(0, 0), (200, 0), (200, 200), (0, 200)]
    hole = [(50, 50), (50, 150), (150, 150), (150, 50)]   # 反向
    out = resolve_overlaps([outer, hole])
    assert len(out) == 2, "真的洞被填掉了"


def test_resolve_overlaps_keeps_ink_nested_inside_a_hole():
    """巢狀（「田」型）：洞裡的墨不得被連帶扣掉。

    這條擋的是「外環聯集 − 洞環聯集」那種批次集合代數——實測會讓「田」
    墨面積少 33%、洞 4→1。
    """
    outer = [(0, 0), (300, 0), (300, 300), (0, 300)]
    hole = [(50, 50), (50, 250), (250, 250), (250, 50)]        # 反向
    inner = [(100, 100), (200, 100), (200, 200), (100, 200)]   # 洞裡的墨
    out = resolve_overlaps([outer, hole, inner])
    assert len(out) == 3, f"洞內的墨被扣掉了：{len(out)} 個輪廓"


def test_resolve_overlaps_degrades_without_shapely(monkeypatch):
    """shapely 缺席 → 原樣回傳，不假裝成功（§8 誠實降級）。"""
    import builtins
    real_import = builtins.__import__

    def fake(name, *a, **k):
        if name.startswith("shapely"):
            raise ImportError("no shapely")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    src = [[(0, 0), (10, 0), (10, 10)]]
    assert resolve_overlaps(src) == src


# ---------------------------------------------------------------------------
# 字型相依：字重軸的實際幾何
# ---------------------------------------------------------------------------


def _judge(polys):
    """回 (筆寬 px, 墨連通件數, 洞數, 鑿橋後殘腔數) @50 mm 字框。"""
    from scipy import ndimage

    from stroke_order.exporters import stencil as st
    from stroke_order.ir import EM_SIZE

    ppm = st.PX_PER_MM
    ch_px = max(8, int(round(50 * ppm)))
    mg = max(2, int(round(10.0 * ppm)))
    mask = np.zeros((2 * mg + ch_px, 2 * mg + ch_px), dtype=bool)
    st._fill_polys(mask, [[(float(x), float(y)) for x, y in p] for p in polys],
                   ox=mg, oy=mg, scale=ch_px / EM_SIZE)
    edt = ndimage.distance_transform_edt(mask)
    pos = edt[edt > 0]
    width = float(np.median(edt[edt > np.percentile(pos, 80)]) * 2)
    lab, n = ndimage.label(mask)
    ink = sum(1 for i in range(1, n + 1) if (lab == i).sum() > 200)
    lb, m = ndimage.label(~mask)
    outside = set(lb[0, :]) | set(lb[-1, :]) | set(lb[:, 0]) | set(lb[:, -1])
    holes = sum(1 for i in range(1, m + 1)
                if i not in outside and (lb == i).sum() > 200)
    st.carve_stencil_bridges(mask, max(2, int(round(2.0 * ppm))), 4)
    l2, n2 = st._label(~mask & ~st._outside(mask))
    rem = sum(1 for i in range(1, n2 + 1) if (l2 == i).sum() > 30)
    return width, ink, holes, rem


@needs_vf
@pytest.mark.parametrize("weight", [300, 400, 500, 600, 700, 800])
def test_r1b_every_weight_is_a_valid_stencil(weight):
    """夾限內任一字重都須是物理有效字模（殘腔 0）——滑桿不得產生廢品。"""
    polys = zt.extract_outline_polylines(
        "國", source="chiron_round", weight=weight)
    _, _, _, remaining = _judge(polys)
    assert remaining == 0, f"wght={weight}：仍有 {remaining} 個 counter 未連回板"


@needs_vf
@pytest.mark.parametrize("ch,holes", [("國", 2), ("歡", 5), ("明", 4)])
def test_r1b_counters_never_fill_in_across_the_range(ch, holes):
    """字碗（洞）在整個夾限內數量不變——加粗不得把字碗填死。"""
    seen = {w: _judge(zt.extract_outline_polylines(
        ch, source="chiron_round", weight=w))[2]
        for w in (300, 500, 800)}
    assert set(seen.values()) == {holes}, f"{ch} 洞數隨字重漂移：{seen}"


@needs_vf
def test_r1b_stroke_width_increases_monotonically():
    widths = [
        _judge(zt.extract_outline_polylines(
            "國", source="chiron_round", weight=w))[0]
        for w in (300, 400, 500, 600, 700, 800)
    ]
    assert widths == sorted(widths), f"字重與筆寬不單調：{widths}"
    assert widths[-1] > widths[0] * 2, (
        f"字重軸範圍太窄，滑桿沒有意義：{widths[0]:.1f} → {widths[-1]:.1f} px")


@needs_vf
@needs_static
@pytest.mark.parametrize("ch", ["國", "明", "永", "歡", "圓", "回"])
def test_r1b_vf_at_static_weight_matches_the_static_file(ch):
    """VF@700 的墨面積須貼齊靜態 700B（±2%）——補正正確性的實證錨點。

    補正前實測差 4–12%（重疊處被 even-odd 挖成假洞）。這裡不比對拓撲件數，
    因為靜態檔做過 overlap removal、兩者在「剛好相切」處會差一個像素
    （實測「快」墨件 3 vs 2、「囊」洞 7 vs 6，但面積差都 <0.5%）。
    """
    from stroke_order.exporters import stencil as st
    from stroke_order.ir import EM_SIZE

    def ink_px(polys):
        px = 1200
        mg = px // 8
        m = np.zeros((2 * mg + px, 2 * mg + px), dtype=bool)
        st._fill_polys(m, [[(float(x), float(y)) for x, y in p]
                           for p in polys], ox=mg, oy=mg, scale=px / EM_SIZE)
        return int(m.sum())

    static = ink_px(zt.extract_outline_polylines(ch, source="chiron_round"))
    vf = ink_px(zt.extract_outline_polylines(
        ch, source="chiron_round", weight=STATIC_WEIGHT))
    assert abs(vf - static) / static < 0.02, (
        f"{ch}：VF@{STATIC_WEIGHT} 墨面積偏離靜態檔 "
        f"{(vf - static) / static * 100:+.1f}%（重疊輪廓補正失效？）")


# ---------------------------------------------------------------------------
# 接線守門（承 S1 的 parity 鎖精神）
# ---------------------------------------------------------------------------


def test_r1b_dropdown_weight_flag_matches_registry():
    """下拉帶 data-weight 的選項集合 ≡ 宣告 supports_weight 的字源集合。

    前端靠 data-weight 決定要不要顯示滑桿；若它與伺服器端漂移，使用者會
    看到一個送出去必定 422 的滑桿（或該有卻沒有）。
    """
    import re
    page = (_ROOT / "src" / "stroke_order" / "web" / "static"
            / "index.html").read_text("utf-8")
    block = page.split('<select id="sc-source">')[1].split("</select>")[0]
    flagged = set(re.findall(r'<option value="([\w-]+)" data-weight=', block))
    assert flagged == {k for k in zt.SOURCE_REGISTRY
                       if zt.source_supports_weight(k)}


def test_r1b_slider_range_matches_backend_clamp():
    """UI 滑桿的 min/max ≡ 後端夾限——不得各寫一份數字。"""
    import re
    page = (_ROOT / "src" / "stroke_order" / "web" / "static"
            / "index.html").read_text("utf-8")
    m = re.search(r'<input id="sc-weight"[^>]*>', page)
    assert m, "找不到字重滑桿"
    tag = m.group(0)
    assert f'min="{WEIGHT_MIN}"' in tag and f'max="{WEIGHT_MAX}"' in tag, tag
    assert f'value="{STATIC_WEIGHT}"' in tag, "滑桿預設值應等於靜態檔字重"


def test_r1b_deploy_wiring_agrees_on_one_path():
    sh = (_ROOT / "scripts" / "render_fetch_fonts.sh").read_text("utf-8")
    ry = (_ROOT / "render.yaml").read_text("utf-8")
    fname = default_round_vf_path().name
    assert f"round-fonts/{fname}" in sh
    assert f"round-fonts/{fname}" in ry
    assert "STROKE_ORDER_ROUND_VF_FILE" in ry
    idx = (_ROOT / "licenses" / "README.md").read_text("utf-8")
    assert fname in idx, "可變字體未登錄 licenses/README.md 對照表"
