"""
S1 — 昭源環方 / Chiron GoRound TC (圓體) 字源＋第七種字模筆形風格。

昭源環方是把昭源黑體（思源黑體香港版的現代筆形改造）程式化圓角而成的
仿圓體：骨架仍是黑體，粗細均勻、無收筆尖鋒，因此和 5dm 的 noto_hei
同屬「可當字模底」那一類。本檔驗證字源本身（註冊、出處、輪廓抽取）
與 S1 的價值主張（圓體字模幾何有效：每個封閉 counter 都連回板）。

字型相依測試以 needs_round 守門（沙箱 ~/.stroke-order/round-fonts/ 或
STROKE_ORDER_ROUND_FONT_FILE），比照 test_noto_hei 的守門作法。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from stroke_order.sources.chiron_round import (
    ChironRoundSource,
    attribution_notice,
    default_round_font_path,
    get_round_source,
    reset_round_singleton,
)
from stroke_order.sources.g0v import CharacterNotFound


def _round_available() -> bool:
    return default_round_font_path().exists()


needs_round = pytest.mark.skipif(
    not _round_available(),
    reason="昭源環方 (Chiron GoRound TC) absent; run "
           "scripts/render_fetch_fonts.sh or set STROKE_ORDER_ROUND_FONT_FILE",
)


# ---------------------------------------------------------------------------
# Font-independent: registry + metadata
# ---------------------------------------------------------------------------


def test_round_registered_in_zentangle_registry():
    from stroke_order.exporters import zentangle as zt
    assert "chiron_round" in zt.SOURCE_REGISTRY
    assert zt.SOURCE_REGISTRY["chiron_round"] is get_round_source


def test_round_label_is_chinese():
    from stroke_order.exporters import zentangle as zt
    labels = {s["key"]: s["label"] for s in zt.list_sources()}
    assert labels["chiron_round"] == "昭源環方"


def test_round_attribution_names_ofl():
    """OFL 須標明；上游未宣告 Reserved Font Name，故不得謊稱有。"""
    a = attribution_notice()
    assert "OFL" in a or "Open Font License" in a
    assert "Chiron GoRound" in a


def test_round_source_singleton():
    reset_round_singleton()
    assert get_round_source() is get_round_source()


def test_round_env_override(monkeypatch, tmp_path):
    """部署靠 STROKE_ORDER_ROUND_FONT_FILE 指路（render.yaml）——不得失效。"""
    target = tmp_path / "custom.otf"
    monkeypatch.setenv("STROKE_ORDER_ROUND_FONT_FILE", str(target))
    assert default_round_font_path() == target
    monkeypatch.delenv("STROKE_ORDER_ROUND_FONT_FILE")
    monkeypatch.setenv("STROKE_ORDER_ROUND_FONT_DIR", str(tmp_path))
    assert default_round_font_path().parent == tmp_path
    assert default_round_font_path().name.endswith(".otf")


def test_round_missing_font_raises_character_not_found(tmp_path):
    """字型缺席時拋 CharacterNotFound（非 IOError）——降級階梯靠它接。"""
    src = ChironRoundSource(font_path=tmp_path / "nope.otf")
    assert src.is_ready() is False
    with pytest.raises(CharacterNotFound):
        src.get_character("明")


# ---------------------------------------------------------------------------
# 接線守門（§86 教訓：新字源不能只加模組，要沿既有路徑全數接上）
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent


def test_s1_stencil_dropdown_offers_round():
    """index.html 的 sc-source 下拉必須真的列出這個字源，否則使用者選不到。"""
    page = (_ROOT / "src" / "stroke_order" / "web" / "static"
            / "index.html").read_text("utf-8")
    block = page.split('<select id="sc-source">')[1].split("</select>")[0]
    assert 'value="chiron_round"' in block
    assert "昭源環方" in block


def test_s1_stencil_dropdown_matches_registry():
    """下拉選項集合 ≡ SOURCE_REGISTRY 鍵集合——單一事實源（§76）。

    先前只加模組沒加下拉／只加下拉沒登註冊表都會靜默漂移，故鎖死。
    """
    import re

    from stroke_order.exporters import zentangle as zt
    page = (_ROOT / "src" / "stroke_order" / "web" / "static"
            / "index.html").read_text("utf-8")
    block = page.split('<select id="sc-source">')[1].split("</select>")[0]
    in_page = set(re.findall(r'<option value="([\w-]+)"', block))
    assert in_page == set(zt.SOURCE_REGISTRY), (
        f"下拉與註冊表漂移：只在頁面 {in_page - set(zt.SOURCE_REGISTRY)}；"
        f"只在註冊表 {set(zt.SOURCE_REGISTRY) - in_page}"
    )


def test_s1_deploy_wiring_agrees_on_one_path():
    """部署三處（fetch 腳本落點／render.yaml env／模組預設檔名）須同名。"""
    sh = (_ROOT / "scripts" / "render_fetch_fonts.sh").read_text("utf-8")
    ry = (_ROOT / "render.yaml").read_text("utf-8")
    fname = default_round_font_path().name  # 無 env 時＝模組內建檔名
    assert f"round-fonts/{fname}" in sh, "fetch 腳本未抓此字型或落點不符"
    assert f"round-fonts/{fname}" in ry, "render.yaml env 路徑與腳本落點不符"
    assert "STROKE_ORDER_ROUND_FONT_FILE" in ry
    # 上游 repo 直取（同 Noto 作法），不依賴本專案 fonts-v1 release
    assert "chiron-fonts/chiron-go-round-tc" in sh


def test_s1_license_travels_with_the_font():
    """OFL 資產須在 LICENSE B 段與 licenses/README 對照表都有登錄。"""
    lic = (_ROOT / "LICENSE").read_text("utf-8")
    idx = (_ROOT / "licenses" / "README.md").read_text("utf-8")
    for text in (lic, idx):
        assert "昭源環方" in text
        assert "chiron-go-round-tc" in text
    assert (_ROOT / "licenses" / "SIL-OFL-1.1.txt").exists()


# ---------------------------------------------------------------------------
# Font-dependent: outline extraction + 字模拓撲有效性
# ---------------------------------------------------------------------------


@needs_round
def test_round_extracts_contours():
    src = ChironRoundSource()
    c = src.get_character("明")
    assert c.data_source == "chiron_round"
    assert c.strokes and c.strokes[0].outline


@needs_round
def test_round_unknown_glyph_raises():
    with pytest.raises(CharacterNotFound):
        ChironRoundSource().get_character("")  # PUA — absent


@needs_round
@pytest.mark.parametrize("ch", ["田", "圖", "國", "回", "圓"])
def test_s1_round_stencil_all_counters_bridged(ch):
    """S1 鐵則（沿用 5dm 判準）：圓體字模每個封閉 counter 都連回板。

    收 700B 而非 400R 的理由就在這條——兩者在 50 mm 都過，但 400R 筆寬
    比基準細約 35%，小尺寸時餘裕不足。見 ADR
    docs/decisions/2026-08-20_s1_chiron_round.md。
    """
    from stroke_order.exporters import zentangle as zt
    from stroke_order.exporters import stencil as st
    from stroke_order.ir import EM_SIZE

    polys = zt.extract_outline_polylines(ch, source="chiron_round")
    ppm = st.PX_PER_MM
    ch_px = max(8, int(round(50 * ppm)))
    mg = max(2, int(round(max(5.0, 50 * 0.2) * ppm)))
    mask = np.zeros((2 * mg + ch_px, 2 * mg + ch_px), dtype=bool)
    st._fill_polys(
        mask,
        [[(float(x), float(y)) for x, y in p] for p in polys],
        ox=mg, oy=mg, scale=ch_px / EM_SIZE,
    )
    st.carve_stencil_bridges(mask, max(2, int(round(2.0 * ppm))), 4)
    lab, n = st._label(~mask & ~st._outside(mask))
    remaining = sum(1 for i in range(1, n + 1) if (lab == i).sum() > 30)
    assert remaining == 0, f"{ch}：仍有 {remaining} 個 counter 未連回板"


@needs_round
def test_s1_round_stroke_width_in_stencil_class():
    """圓體要能當字模底，筆寬須落在黑體級距（非楷書級的細）。

    5dm 實測：楷書中位 ≈6px、黑體 ≈20-24px（該次量法）。本測以同一
    量法比對「昭源環方 700B 不比思源黑體細太多」——留 25% 容差。
    """
    from scipy import ndimage

    from stroke_order.exporters import zentangle as zt
    from stroke_order.exporters import stencil as st
    from stroke_order.ir import EM_SIZE

    def median_width(source: str) -> float:
        polys = zt.extract_outline_polylines("國", source=source)
        ppm = st.PX_PER_MM
        ch_px = max(8, int(round(50 * ppm)))
        mg = max(2, int(round(10.0 * ppm)))
        mask = np.zeros((2 * mg + ch_px, 2 * mg + ch_px), dtype=bool)
        st._fill_polys(
            mask,
            [[(float(x), float(y)) for x, y in p] for p in polys],
            ox=mg, oy=mg, scale=ch_px / EM_SIZE,
        )
        edt = ndimage.distance_transform_edt(mask)
        pos = edt[edt > 0]
        ridge = edt[edt > np.percentile(pos, 80)]
        return float(np.median(ridge) * 2)

    from stroke_order.sources.noto_hei import default_hei_font_path
    if not default_hei_font_path().exists():
        pytest.skip("比較基準思源黑體未安裝")

    w_round = median_width("chiron_round")
    w_hei = median_width("noto_hei")
    assert w_round >= w_hei * 0.75, (
        f"昭源環方筆寬 {w_round:.1f}px 遠細於思源黑體 {w_hei:.1f}px——"
        "字重選錯了（400R？應為 700B）"
    )
