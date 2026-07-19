"""5fa：篆體缺字部件合成——引擎邏輯＋整條管線。

字型夾具：從系統 CJK 字型裁一個「只含部件、不含合成目標字」的子集
OTF——完美模擬「崇羲有 金/里/网/圭，沒有 鋰/罣」。無系統字型時
整檔 skip（純邏輯測試不受影響、放最前面）。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from stroke_order.sources.seal_compose import (
    ELEMENT_DECOMP, _affine_cmd, _infer_operator, is_seal_synth,
    resolve_decomp,
)

# ---------------------------------------------------------------------------
# 純邏輯（無需字型）
# ---------------------------------------------------------------------------


def test_element_table_sanity():
    """特化表衛生：單字件、部首件屬 金石气水工、operator 合法。"""
    for ch, (op, p1, p2) in ELEMENT_DECOMP.items():
        assert len(ch) == 1
        assert op in ("⿰", "⿱", "⿹"), ch
        assert len(p1) == 1 and len(p2) == 1, ch
        assert p1 in "金石气水工", (ch, p1)


def test_element_table_covers_periodic_page():
    """特化表 key 都是週期表實際用字（防手滑收錯字）。"""
    from stroke_order.exporters.periodic_table import ELEMENTS
    page_chars = set("".join(el["zh"] for el in ELEMENTS))
    unknown = set(ELEMENT_DECOMP) - page_chars
    assert unknown == set(), unknown


def test_infer_operator_conservative():
    assert _infer_operator("金") == "⿰"
    assert _infer_operator("网") == "⿱"
    assert _infer_operator("气") == "⿹"
    assert _infer_operator("相") is None      # 含糊部件——誠實放棄


def test_resolve_decomp_paths():
    from stroke_order.decomposition import default_db
    db = default_db()
    assert resolve_decomp("鋰", db) == ("⿰", "金", "里")   # 特化表
    assert resolve_decomp("罣", db) == ("⿱", "网", "圭")   # 五千字 DB＋方位推測
    assert resolve_decomp("耨", db) == ("⿰", "耒", "辱")
    assert resolve_decomp("〇", db) is None                 # 查無＝放棄


def test_affine_cmd_math():
    m = _affine_cmd({"type": "M", "x": 100.0, "y": 200.0}, 40, 0, 0.5, 1.0)
    assert m == {"type": "M", "x": 90.0, "y": 200.0}
    q = _affine_cmd({"type": "Q", "begin": {"x": 0, "y": 0},
                     "end": {"x": 2048, "y": 2048}}, 0, 1064, 1.0, 0.46)
    assert q["end"]["y"] == pytest.approx(1064 + 0.46 * 2048)


# ---------------------------------------------------------------------------
# 子集字型夾具＋整條管線
# ---------------------------------------------------------------------------

_FONT_CANDIDATES = [
    os.environ.get("STROKE_ORDER_TEST_CJK_FONT", ""),
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "C:/Windows/Fonts/msjh.ttc",
    "C:/Windows/Fonts/mingliu.ttc",
]
#: 子集只含「部件」——目標字（鋰罣氬耨溴）刻意排除＝模擬崇羲缺字
_PARTS = "金里网圭耒辱气亞水臭工石西太"


@pytest.fixture(scope="module")
def subset_seal_font(tmp_path_factory):
    src = next((f for f in _FONT_CANDIDATES if f and Path(f).exists()), None)
    if src is None:
        pytest.skip("無系統 CJK 字型可裁子集（沙箱/CI 有、環境缺則跳過）")
    from fontTools import subset
    from fontTools.ttLib import TTFont
    font = TTFont(src, fontNumber=0, lazy=True)
    ss = subset.Subsetter()
    ss.populate(text=_PARTS)
    ss.subset(font)
    out = tmp_path_factory.mktemp("sealfont") / "subset_seal.otf"
    font.save(str(out))
    return str(out)


@pytest.fixture()
def seal_source(subset_seal_font, monkeypatch):
    import stroke_order.sources.chongxi_seal as cs
    monkeypatch.setenv("STROKE_ORDER_SEAL_FONT_FILE", subset_seal_font)
    cs.reset_seal_singleton()
    yield cs.get_seal_source()
    cs.reset_seal_singleton()


def test_compose_left_right(seal_source):
    """鋰＝⿰金里：合成成功、帶 synth 標記、左右件各落半邊。"""
    c = seal_source.get_character("鋰")
    assert is_seal_synth(c)
    assert any(n == "seal-synth:⿰金里" for n in c.validation_notes)
    assert c.data_source == "chongxi_seal"     # 骨架管線分流依據——必須維持
    xs = [cmd["x"] for s in c.strokes for cmd in s.outline
          if "x" in cmd]
    assert min(xs) < 1024 < max(xs)            # 兩半皆有墨
    assert 0 <= min(xs) and max(xs) <= 2048    # 界內


def test_compose_top_bottom_from_wuqian_db(seal_source):
    """罣＝⿱网圭（五千字 DB＋方位推測）：上下件各落半邊。"""
    c = seal_source.get_character("罣")
    assert is_seal_synth(c)
    ys = []
    for s in c.strokes:
        for cmd in s.outline:
            if "y" in cmd:
                ys.append(cmd["y"])
            elif "end" in cmd:
                ys.append(cmd["end"]["y"])
    assert min(ys) < 1024 < max(ys)


def test_compose_surround_qi(seal_source):
    """氬＝⿹气亞：气 全幅、亞 縮入。"""
    c = seal_source.get_character("氬")
    assert is_seal_synth(c)


def test_compose_gives_up_honestly(seal_source):
    """部件也缺（〇 無拆解；賾 部件不在子集）→ 維持 CharacterNotFound。"""
    from stroke_order.sources.g0v import CharacterNotFound
    with pytest.raises(CharacterNotFound):
        seal_source.get_character("〇")


def test_real_glyph_not_marked(seal_source):
    """子集裡真有的字（金）不是合成字——不帶標記。"""
    c = seal_source.get_character("金")
    assert not is_seal_synth(c)


def test_cellmap_carries_synth_flag(seal_source, monkeypatch):
    """整條渲染管線：抄經頁 cellmap 對合成字帶 data-seal-synth。"""
    from stroke_order.exporters.sutra import cellmap_rect
    r = cellmap_rect("鋰", 0, 0, 10, 10, 0, loaded=True, synth=True)
    assert 'data-seal-synth="1"' in r
    r2 = cellmap_rect("金", 0, 0, 10, 10, 0, loaded=True)
    assert "data-seal-synth" not in r2


# ---------------------------------------------------------------------------
# 5fb：TTFont 句柄回收（懶解析殘留）＋前端配套標記
# ---------------------------------------------------------------------------


def test_5fb_font_handle_recycled(seal_source, monkeypatch):
    """每 N 個字形丟句柄（cmap/度量自快取——重開不重建）。"""
    import stroke_order.sources.chongxi_seal as cs
    monkeypatch.setattr(cs, "FONT_RECYCLE_AFTER", 3)
    seal_source._glyphs_since_open = 0
    for ch in "金里网圭":                      # 4 個未快取？（fixture 共用
        seal_source._cache.pop(ch, None)       # 快取先清，強制走渲染）
    for ch in "金里网":
        seal_source.get_character(ch)
    assert seal_source._font is None            # 第 3 字後句柄已丟
    cmap_before = seal_source._cmap
    c = seal_source.get_character("圭")         # 重開句柄照常渲染
    assert c.strokes
    assert seal_source._cmap is cmap_before     # cmap 跨句柄重用（不重建）


def test_5fb_all_font_sources_have_recycle():
    import inspect

    from stroke_order.sources import chongxi_seal, cns_font, moe_lishu
    for mod in (chongxi_seal, cns_font, moe_lishu):
        src = inspect.getsource(mod)
        assert "_glyphs_since_open" in src, mod.__name__
        assert "FONT_RECYCLE_AFTER" in src, mod.__name__


def test_5fb_frontend_markers():
    from fastapi.testclient import TestClient

    from stroke_order.web.server import app
    c = TestClient(app)
    sj = c.get("/static/modes/sutra.js").text
    assert "SU_BATCH_SIZE_SKELETON" in sj      # 篆/隸縮批
    assert "suBatchSize" in sj
    assert "重試中" in sj                       # 單批重試一次
    hw = c.get("/static/modes/handwrite.js").text
    assert "REF_SCALE = 1.4" in hw             # 範字 1.4×
