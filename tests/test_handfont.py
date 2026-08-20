"""
R3 — 手寫字型：user_dict 手寫軌跡 → 可安裝 TTF。

FANGCUN 評估的「差異化殺手鐧」：字型裡每個字形都是使用者親手寫的
（sign-off：只含寫過的字）。本檔照 §95.1 兩層驗證：

  · **層一（對照參考實作）**：fontTools 回讀——unitsPerEm、cmap、metrics、
    glyph 輪廓存在。
  · **層二（獨立解碼器）**：PIL/FreeType **真的把字型畫出來**——十字有墨、
    口字的字碗（counter）留白。環向錯（nonzero 填色下外環洞環同向）時
    字碗會被填死，只有真渲染抓得到。

其他鎖：著作權標注歸書寫者（name table）／沒寫過的字不在 cmap（純手寫
誠實保證）／weight 參數生效／endpoint 下載頭與 400。
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.exporters.handfont import ASCENT, DESCENT, build_hand_font
from stroke_order.ir import EM_SIZE
from stroke_order.sources.user_dict import UserDictSource

_ROOT = Path(__file__).resolve().parent.parent
_INDEX = _ROOT / "src" / "stroke_order" / "web" / "static" / "index.html"
_UD_JS = (_ROOT / "src" / "stroke_order" / "web" / "static" / "modes"
          / "userdict.js")


@pytest.fixture
def hand_src(tmp_path, monkeypatch):
    """臨時 user_dict：兩個合成手寫字——十（無洞）、口樣方框（有洞）。"""
    monkeypatch.setenv("STROKE_ORDER_USER_DICT_DIR", str(tmp_path))
    src = UserDictSource(tmp_path)
    src.save_character("十", [
        {"track": [[300, 1024], [1748, 1024]]},
        {"track": [[1024, 300], [1024, 1748]]},
    ])
    src.save_character("口", [
        {"track": [[500, 500], [500, 1500]]},
        {"track": [[500, 500], [1500, 500], [1500, 1500]]},
        {"track": [[500, 1500], [1500, 1500]]},
    ])
    return src


@pytest.fixture
def ttf_bytes(hand_src):
    return build_hand_font(
        [hand_src.get_character(c) for c in ("十", "口")], owner="測試")


# ---------------------------------------------------------------------------
# 層一：fontTools 回讀
# ---------------------------------------------------------------------------


def test_r3_font_parses_with_expected_metrics(ttf_bytes):
    from fontTools.ttLib import TTFont
    f = TTFont(io.BytesIO(ttf_bytes))
    assert f["head"].unitsPerEm == EM_SIZE
    assert f["hhea"].ascent == ASCENT and f["hhea"].descent == -DESCENT
    cmap = f.getBestCmap()
    assert cmap == {ord("十"): "uni5341", ord("口"): "uni53E3"}
    # 全形等寬
    for name in ("uni5341", "uni53E3"):
        assert f["hmtx"][name][0] == EM_SIZE
    # 有 .notdef 且非手寫字不在 cmap（純手寫誠實保證）
    assert ".notdef" in f.getGlyphOrder()
    assert ord("春") not in cmap


def test_r3_glyphs_have_contours(ttf_bytes):
    from fontTools.ttLib import TTFont
    f = TTFont(io.BytesIO(ttf_bytes))
    glyf = f["glyf"]
    assert glyf["uni5341"].numberOfContours >= 1
    # 口樣方框 union 後：外環＋洞環 ≥ 2 條輪廓
    assert glyf["uni53E3"].numberOfContours >= 2


def test_r3_copyright_belongs_to_the_writer(ttf_bytes):
    """字形著作權歸書寫者本人——FANGCUN 評估即定此原則，name table 寫明。"""
    from fontTools.ttLib import TTFont
    f = TTFont(io.BytesIO(ttf_bytes))
    name = f["name"]
    cp = name.getDebugName(0) or ""
    assert "書寫者" in cp or "測試" in cp
    assert "測試" in cp, "owner 參數要進著作權標注"


# ---------------------------------------------------------------------------
# 層二：PIL/FreeType 獨立解碼——真的畫出來
# ---------------------------------------------------------------------------


def _render(ttf: bytes, text: str, size: int = 200):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(io.BytesIO(ttf), size)
    img = Image.new("L", (size * (len(text) + 1), size + 80), 255)
    ImageDraw.Draw(img).text((20, 20), text, font=font, fill=0)
    return img


def _ink(img, thresh: int = 128) -> int:
    import numpy as np
    return int((np.asarray(img) < thresh).sum())


def test_r3_freetype_renders_ink(ttf_bytes):
    dark = _ink(_render(ttf_bytes, "十"))
    assert dark > 500, "FreeType 畫不出墨＝字型壞了"


def test_r3_counter_stays_white_nonzero_winding(ttf_bytes):
    """口的字碗必須留白——外環洞環同向（環向錯）時 nonzero 會填死。

    這是層二存在的理由：fontTools 回讀看不出環向錯，只有真渲染看得出。
    """
    from PIL import ImageFont, Image, ImageDraw
    size = 300
    font = ImageFont.truetype(io.BytesIO(ttf_bytes), size)
    img = Image.new("L", (size + 60, size + 100), 255)
    ImageDraw.Draw(img).text((20, 20), "口", font=font, fill=0)
    w, h = img.size
    # 字中心一小塊應為白（字碗）
    centre = [img.getpixel((w // 2 + dx, h // 2 + dy))
              for dx in (-8, 0, 8) for dy in (-8, 0, 8)]
    assert all(px > 200 for px in centre), "字碗被填死＝環向錯"
    # 但整張圖要有墨（框本身）
    assert _ink(img) > 1000


def test_r3_weight_param_changes_ink(hand_src):
    chars = [hand_src.get_character("十")]
    thin = build_hand_font(chars, weight=60)
    thick = build_hand_font(chars, weight=240)
    assert _ink(_render(thick, "十")) > _ink(_render(thin, "十")) * 1.5


# ---------------------------------------------------------------------------
# 邊界
# ---------------------------------------------------------------------------


def test_r3_empty_charset_raises(hand_src):
    with pytest.raises(ValueError):
        build_hand_font([])


# ---------------------------------------------------------------------------
# 端點
# ---------------------------------------------------------------------------


def test_r3_endpoint_downloads_ttf(hand_src):
    from stroke_order.web.server import create_app
    client = TestClient(create_app())
    r = client.get("/api/user-dict/font", params={"owner": "小明"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("font/ttf")
    assert "attachment" in r.headers["content-disposition"]
    assert r.headers["X-Hand-Font-Chars"] == "2"
    from fontTools.ttLib import TTFont
    f = TTFont(io.BytesIO(r.content))
    assert set(f.getBestCmap()) == {ord("十"), ord("口")}


def test_r3_endpoint_400_when_nothing_written(tmp_path, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_USER_DICT_DIR", str(tmp_path))
    from stroke_order.web.server import create_app
    client = TestClient(create_app())
    r = client.get("/api/user-dict/font")
    assert r.status_code == 400
    assert "手寫" in r.json()["detail"]


@pytest.mark.parametrize("params", [
    {"weight": 0}, {"weight": 999}, {"cap": "butt"}, {"owner": "x" * 41},
])
def test_r3_endpoint_rejects_bad_params(hand_src, params):
    from stroke_order.web.server import create_app
    client = TestClient(create_app())
    r = client.get("/api/user-dict/font", params=params)
    assert r.status_code == 422, params


# ---------------------------------------------------------------------------
# parity：UI ≡ JS
# ---------------------------------------------------------------------------


def test_r3_ui_button_matches_js():
    page = _INDEX.read_text("utf-8")
    js = _UD_JS.read_text("utf-8")
    assert 'id="ud-font"' in page
    assert 'getElementById("ud-font")' in js
    assert "/api/user-dict/font" in js
