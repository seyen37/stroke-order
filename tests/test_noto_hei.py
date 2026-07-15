"""
Phase 5dm — 思源黑體 / Noto Sans TC (黑體) source + 鏤空字模推薦字型。

黑體筆畫粗細均勻、無收筆尖鋒，字模橋接/連筋落在厚壁上不易斷——
故設為鏤空字模式的推薦預設。本檔驗證字源本身（註冊、輪廓抽取、
出處）與 5dm 的價值（黑體字模幾何有效：每個封閉counter都連回板）。

字型相依測試以 needs_hei 守門（沙箱 ~/.stroke-order/hei-fonts/ 或
STROKE_ORDER_HEI_FONT_FILE）。
"""
from __future__ import annotations

import numpy as np
import pytest

from stroke_order.sources.noto_hei import (
    NotoHeiSource,
    attribution_notice,
    default_hei_font_path,
    get_hei_source,
    reset_hei_singleton,
)
from stroke_order.sources.g0v import CharacterNotFound


def _hei_available() -> bool:
    return default_hei_font_path().exists()


needs_hei = pytest.mark.skipif(
    not _hei_available(),
    reason="Noto Sans TC (思源黑體) absent; run scripts/render_fetch_fonts.sh "
           "or set STROKE_ORDER_HEI_FONT_FILE",
)


# ---------------------------------------------------------------------------
# Font-independent: registry + metadata
# ---------------------------------------------------------------------------


def test_hei_registered_in_zentangle_registry():
    from stroke_order.exporters import zentangle as zt
    assert "noto_hei" in zt.SOURCE_REGISTRY
    assert zt.SOURCE_REGISTRY["noto_hei"] is get_hei_source


def test_hei_attribution_names_ofl():
    """OFL 是本專案所有字型中最寬鬆者——出處須標明 OFL + Noto。"""
    a = attribution_notice()
    assert "OFL" in a or "Open Font License" in a
    assert "Noto" in a


def test_hei_source_singleton():
    reset_hei_singleton()
    assert get_hei_source() is get_hei_source()


# ---------------------------------------------------------------------------
# Font-dependent: outline extraction + 5dm stencil validity
# ---------------------------------------------------------------------------


@needs_hei
def test_hei_extracts_contours():
    src = NotoHeiSource()
    c = src.get_character("明")
    assert c.data_source == "noto_hei"
    assert c.strokes and c.strokes[0].outline


@needs_hei
def test_hei_unknown_glyph_raises():
    with pytest.raises(CharacterNotFound):
        NotoHeiSource().get_character("")  # PUA — absent


@needs_hei
@pytest.mark.parametrize("ch", ["田", "圖", "國", "回", "圓"])
def test_5dm_hei_stencil_all_counters_bridged(ch):
    """5dm 鐵則：黑體字模每個封閉 counter 都連回板（鑿橋後 0 殘孔）。

    ＝物理有效字模：無孤島掉落。軸向近牆橋接（方正大黑連筋切法）。
    """
    from stroke_order.exporters import zentangle as zt
    from stroke_order.exporters import stencil as st
    from stroke_order.ir import EM_SIZE

    polys = zt.extract_outline_polylines(ch, source="noto_hei")
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
