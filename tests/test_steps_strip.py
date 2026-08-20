"""
X1 — 筆順分解圖（靜態逐筆累積條）。

田野證據（word_worksheet_tool 評估）：老師從筆順字典網站抓「第 N 格畫到
第 N 筆」的分解圖貼 Word，動機是省筆順字型的錢。本功能用 g0v 教育部標準
楷書筆順原生排版同樣的圖——授權乾淨、不抓任何外站。

本檔鎖四條核心不變式（皆為評估建議書預繳的風險註記，§97）：

  · **灰階可辨**——已寫淡灰、當前濃黑，灰階單調遞增；gif 的紅色
    highlight（#c33 灰階後比 #333 淡）不得出現。讀寫障礙教室幾乎必然
    黑白影印。
  · **自動換列**——格數＝筆畫數（1–30+），頁寬由 cols 決定、與單字筆畫
    數解耦（§96.1）。
  · **序號不用 <text>**——走 noto_hei 字形路徑（§5bv）；字型缺席序號
    整個省略、不補符號（§87）。
  · **墨跡在畫布內**——含最後一列（§96.2/.3 的教訓）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.exporters.steps import (
    STEP_CURR_COLOR,
    STEP_DONE_COLOR,
    render_steps_svg,
)
from stroke_order.web.char_pipeline import _load, build_digit_glyphs
from stroke_order.web.server import create_app

_ROOT = Path(__file__).resolve().parent.parent
_INDEX = _ROOT / "src" / "stroke_order" / "web" / "static" / "index.html"
_GRID_JS = (_ROOT / "src" / "stroke_order" / "web" / "static" / "modes"
            / "grid.js")


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def _chars(text):
    return [_load(c, "auto", "animation")[0] for c in text]


def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


# ---------------------------------------------------------------------------
# 結構：格數＝筆畫數、逐格累積
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["永", "春天"])
def test_x1_one_cell_per_stroke(text):
    chars = _chars(text)
    svg = render_steps_svg(chars)
    assert svg.count('class="step-strip"') == len(chars)
    for ch in chars:
        m = re.search(
            rf'data-char="{ch.char}" data-steps="(\d+)"', svg)
        assert m and int(m.group(1)) == len(ch.strokes)
    assert svg.count('class="step-cell"') == sum(
        len(c.strokes) for c in chars)


def test_x1_cells_accumulate():
    """第 k 格恰有 k 筆：k-1 筆淡灰群＋1 筆濃黑群。"""
    (ch,) = _chars("永")
    svg = render_steps_svg([ch])
    cells = re.findall(r'<g class="step-cell" data-step="(\d+)"[^>]*>(.*?)'
                       r'</g><g class="step-cell"|'
                       r'<g class="step-cell" data-step="(\d+)"[^>]*>(.*)',
                       svg, re.S)
    # 逐格檢查：done 群的 path 數 == step-1
    for k in range(1, len(ch.strokes) + 1):
        cell = svg.split(f'data-step="{k}"')[1].split('class="step-cell"')[0]
        curr = cell.split('class="curr"')[1]
        assert '<path' in curr or '<polyline' in curr
        if k == 1:
            assert 'class="done"' not in cell
        else:
            done = cell.split('class="done"')[1].split('class="curr"')[0]
            assert done.count("<path") + done.count("<polyline") >= k - 1


# ---------------------------------------------------------------------------
# 灰階可辨（黑白影印鐵則）
# ---------------------------------------------------------------------------


def test_x1_current_stroke_darker_than_done_in_grayscale():
    """當前筆的灰階亮度必須明顯低於已寫筆——鎖現象不鎖色值（§66）。"""
    assert _lum(STEP_CURR_COLOR) < _lum(STEP_DONE_COLOR) - 60


def test_x1_gif_red_highlight_is_absent():
    """gif 的 #c33 灰階後比已寫的 #333 還淡——分解圖不得沿用。"""
    svg = render_steps_svg(_chars("永"))
    assert "#c33" not in svg and "#cc3333" not in svg


# ---------------------------------------------------------------------------
# 自動換列（§96.1：頁寬與單字筆畫數解耦）
# ---------------------------------------------------------------------------


def test_x1_wraps_when_strokes_exceed_cols():
    (ch,) = _chars("歡")   # 22 畫
    n = len(ch.strokes)
    assert n > 8
    narrow = render_steps_svg([ch], cols=8)
    wide = render_steps_svg([ch], cols=20)
    w = lambda s: float(re.search(   # noqa: E731
        r'viewBox="0 0 (\S+) (\S+)"', s).group(1))
    h = lambda s: float(re.search(   # noqa: E731
        r'viewBox="0 0 (\S+) (\S+)"', s).group(2))
    # 頁寬只由 cols 決定
    assert w(narrow) < w(wide)
    # 22 畫：8 欄 → 3 列、20 欄 → 2 列；高度比應接近 3:2（列高相同）
    assert h(narrow) > h(wide) * 1.3


def test_x1_all_cells_inside_canvas():
    """每一格（含換列後最後一列）都在 viewBox 內——§96.2/.3 的鎖。"""
    svg = render_steps_svg(_chars("歡永"), cols=8)
    vb_w, vb_h = (float(x) for x in re.search(
        r'viewBox="0 0 (\S+) (\S+)"', svg).groups())
    strips = re.findall(r'class="step-strip"[^>]*transform="translate\(0,'
                        r'(\d+)\)"', svg)
    cells = re.findall(r'class="step-cell"[^>]*transform="translate\((\d+),'
                       r'(\d+)\)"', svg)
    from stroke_order.ir import EM_SIZE
    strip_ys = [int(y) for y in strips]
    assert cells
    for cx, cy in ((int(a), int(b)) for a, b in cells):
        assert cx + EM_SIZE <= vb_w + 1
    # 最深的格子＋一格高不得超出畫布
    max_bottom = max(sy + int(b) + EM_SIZE for sy in strip_ys
                     for a, b in cells)
    # cells 的 cy 是 strip 內座標——取每條 strip 的最大 cy 逐條驗
    for sy, strip_svg in zip(strip_ys, re.split(
            r'class="step-strip"', svg)[1:]):
        cys = [int(b) for _a, b in re.findall(
            r'class="step-cell"[^>]*translate\((\d+),(\d+)\)', strip_svg)]
        if cys:
            assert sy + max(cys) + EM_SIZE <= vb_h + 1
    del max_bottom


# ---------------------------------------------------------------------------
# 序號：字形路徑、可省略、不補符號
# ---------------------------------------------------------------------------


def test_x1_no_text_element_anywhere():
    """§5bv：<text> 在 Render 的 PDF 上會變空框。"""
    svg = render_steps_svg(_chars("春"), digit_glyphs=build_digit_glyphs())
    assert "<text" not in svg and "font-family" not in svg


def test_x1_numbers_rendered_from_glyphs_with_white_pad():
    glyphs = build_digit_glyphs()
    if not glyphs:
        pytest.skip("noto_hei 未安裝")
    svg = render_steps_svg(_chars("永"), digit_glyphs=glyphs)
    assert svg.count('class="step-num"') == 5
    assert 'data-n="5"' in svg
    # 白底護墊：黑白影印下序號壓字仍可讀
    num = svg.split('class="step-num"')[1].split("</g>")[0]
    assert 'fill="white"' in num


def test_x1_numbers_omitted_without_placeholder_when_font_missing():
    """§87：字型缺席序號整個省略——不畫問號、不畫方框。"""
    svg = render_steps_svg(_chars("永"), digit_glyphs=None)
    assert 'class="step-num"' not in svg
    assert "?" not in svg and "□" not in svg
    svg2 = render_steps_svg(_chars("永"), digit_glyphs={})
    assert 'class="step-num"' not in svg2


def test_x1_two_digit_numbers_have_both_digits():
    """第一版的錯：全形步進讓「10」看起來像只印了「0」。鎖兩位數都在。"""
    glyphs = build_digit_glyphs()
    if not glyphs:
        pytest.skip("noto_hei 未安裝")
    (ch,) = _chars("歡")
    svg = render_steps_svg([ch], digit_glyphs=glyphs)
    num10 = svg.split('data-n="10"')[1].split('class="step-cell"')[0]
    # 兩個數字字形群（translate…scale 各一）
    assert num10.count("scale(") == 2, "兩位數序號少了一位"


# ---------------------------------------------------------------------------
# 端點
# ---------------------------------------------------------------------------


def test_x1_endpoint_svg(client):
    r = client.get("/api/steps", params={"chars": "春天"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.text.count('class="step-strip"') == 2


def test_x1_endpoint_pdf_and_png(client):
    p = client.get("/api/steps", params={"chars": "春", "format": "pdf"})
    assert p.status_code == 200 and p.content[:5] == b"%PDF-"
    assert "X-Pdf-Dpi-Used" in p.headers
    g = client.get("/api/steps", params={"chars": "春", "format": "png"})
    assert g.status_code == 200 and g.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("params", [
    {"chars": ""},
    {"chars": "春", "format": "tiff"},
    {"chars": "春", "cols": 2},
    {"chars": "春", "format": "pdf", "margin_mm": 80},
])
def test_x1_endpoint_rejects_bad_input(client, params):
    r = client.get("/api/steps", params=params)
    assert r.status_code == 422, (params, r.status_code)


def test_x1_endpoint_guide_param_matters(client):
    a = client.get("/api/steps", params={"chars": "春", "guide": "mi"}).text
    b = client.get("/api/steps", params={"chars": "春", "guide": "none"}).text
    assert a != b


def test_x1_numbers_param_off(client):
    r = client.get("/api/steps", params={"chars": "春", "numbers": "false"})
    assert 'class="step-num"' not in r.text


# ---------------------------------------------------------------------------
# parity：UI ≡ JS ≡ API
# ---------------------------------------------------------------------------


def test_x1_ui_buttons_match_js():
    page = _INDEX.read_text("utf-8")
    js = _GRID_JS.read_text("utf-8")
    for el_id in ("grid-steps-svg", "grid-steps-pdf"):
        assert f'id="{el_id}"' in page, f"index.html 缺 {el_id}"
        assert f'getElementById("{el_id}")' in js, f"grid.js 沒接 {el_id}"
    assert "/api/steps" in js
