"""
W2 — 字帖頁尾生字資訊區。

字帖評估建議書盤出的三個缺口之一：同好的產生器在每張字帖底下附生字的
部首／筆畫／注音與釋義，學生不必再翻字典。我們手上早有教育部《國語辭典
簡編本》的離線 bundle（T2），缺的只是「放到紙上」這一段。

本檔鎖四條核心不變式：

  · **§88 的線**——釋義是 CC BY-ND：**節錄整條義項可以、動任何一條的字
    不可以**。所以呈現的釋義必須是 ``definition`` 原文的**連續子字串**，
    放不下就整條不放，絕不出現刪節號。
  · **零回歸**——``info_footer`` 預設關，關著時輸出與 W2 之前**逐位元組**
    相同。
  · **不用 ``<text>``**——§5bv：cairosvg 吃伺服器字型堆疊，Render 的
    ``apt.txt`` 沒有 CJK 字型，``<text>`` 會變空框。W1 之後 PDF 是字帖的
    主要出口，這個坑不能再踩。
  · **不裁切**——註記字形（noto_hei）是基線相對的，墨跡會超出 em 框下緣
    0.33 em。畫布高度必須容得下實際墨跡，否則最後一列會被削掉。
"""
from __future__ import annotations

import random
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.exporters.grid import (
    INFO_LONG_NOTICE,
    INFO_MAX_CHARS,
    INFO_SEP,
    _info_footer_svg,
    _info_metrics,
    _ink_band,
    _wrap,
    compose_info_line,
    render_grid_svg,
)
from stroke_order.ir import EM_SIZE
from stroke_order.sources import moe_dict
from stroke_order.web.char_pipeline import _load, build_info_rows
from stroke_order.web.server import create_app

_ROOT = Path(__file__).resolve().parent.parent
_INDEX = _ROOT / "src" / "stroke_order" / "web" / "static" / "index.html"
_GRID_JS = _ROOT / "src" / "stroke_order" / "web" / "static" / "modes" / "grid.js"

_ELLIPSES = ("…", "...", "⋯", "（略）", "(略)", "以下略")

needs_dict = pytest.mark.skipif(
    not moe_dict.is_ready(), reason="教育部辭典 bundle 未建置")


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def _chars(text: str):
    return [_load(c, "auto", "animation")[0] for c in text]


# ---------------------------------------------------------------------------
# §88：釋義必須是原文的連續子字串
# ---------------------------------------------------------------------------


@needs_dict
def test_w2_first_sense_is_a_contiguous_substring_of_the_original():
    """抽驗 300 條：第一義項逐字出現在原文裡（只切不改）。

    這是 ND 授權的機械化檢查——只要有人在切分裡加了「去掉序號」「補標
    點」「壓縮空白」，這條就會紅。
    """
    rng = random.Random(20260820)
    pool = sorted(moe_dict._load().keys())      # noqa: SLF001
    checked = 0
    for ch in rng.sample(pool, 300):
        entry = moe_dict.lookup(ch)
        sense = moe_dict.first_sense(ch)
        if sense is None:
            continue
        assert sense["text"] in entry["definition"], ch
        checked += 1
    assert checked >= 250, f"抽到的樣本太多沒有釋義（只驗到 {checked} 條）"


@needs_dict
def test_w2_split_senses_covers_all_three_separator_shapes():
    """實測 bundle 有三種分隔樣態，缺一不可：無換行／單 \\n／\\n\\n。

    第一版只切 ``\\n\\n``，2,935 條「單 \\n 分隔」的字第一義項會取到整條
    釋義——這條測試就是那次修正的鎖。
    """
    shapes = {"none": 0, "single": 0, "double": 0}
    for ch in moe_dict._load():                 # noqa: SLF001
        d = (moe_dict.lookup(ch) or {}).get("definition") or ""
        if "\n\n" in d:
            shapes["double"] += 1
        elif "\n" in d:
            shapes["single"] += 1
        elif d:
            shapes["none"] += 1
    assert all(v > 100 for v in shapes.values()), shapes
    # 單 \n 的字：切完必須真的變多條（否則就是分隔符抓錯）
    multi = [ch for ch in moe_dict._load()      # noqa: SLF001
             if "\n" in ((moe_dict.lookup(ch) or {}).get("definition") or "")
             and "\n\n" not in ((moe_dict.lookup(ch) or {}).get("definition") or "")]
    assert multi
    sample = multi[0]
    assert (moe_dict.first_sense(sample)["total"] > 1), sample


@pytest.mark.parametrize("definition", [
    "一年四季中的第一季。",
    "X" * INFO_MAX_CHARS,
    "X" * (INFO_MAX_CHARS + 1),
    "X" * 227,
])
def test_w2_definition_is_whole_or_nothing(definition):
    """釋義要嘛整條原文、要嘛換成告示語——中間沒有「截一半」這個選項。"""
    line = compose_info_line({"char": "春", "meta": "日部", "definition": definition})
    if len(definition) <= INFO_MAX_CHARS:
        assert definition in line
    else:
        assert INFO_LONG_NOTICE in line
        assert definition[:10] not in line, "出現了原文的前綴＝被截斷了"


@pytest.mark.parametrize("definition", ["X" * 227, "一年四季中的第一季。"])
def test_w2_never_emits_an_ellipsis(definition):
    """刪節號＝「這裡本來還有字」，那正是 ND 不准的改作痕跡。"""
    line = compose_info_line({"char": "春", "definition": definition})
    for bad in _ELLIPSES:
        assert bad not in line, (bad, line)


def test_w2_wrap_loses_no_characters():
    """換行只是排版，不得少字——少字就變成截斷了。"""
    text = "".join(chr(0x4E00 + i) for i in range(137))
    for cap in (1, 7, 40, 200):
        assert "".join(_wrap(text, cap)) == text
        assert all(len(ln) <= cap for ln in _wrap(text, cap))


# ---------------------------------------------------------------------------
# 零回歸：預設關，關著時逐位元組相同
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cols", [1, 3, 5])
@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
@pytest.mark.parametrize("zy", [None, {"春": "ㄔㄨㄣ"}])
def test_w2_zero_regression_when_footer_off(cols, direction, zy):
    chars = _chars("春天")
    kw = dict(cols=cols, direction=direction, zhuyin_map=zy)
    base = render_grid_svg(chars, **kw)
    # 傳了資料但沒開 → 不得有任何影響
    assert render_grid_svg(
        chars, info_footer=False,
        info_rows=[{"char": "春", "meta": "日部", "definition": "x"}],
        **kw) == base
    # 開了但沒資料 → 一樣不得有任何影響
    assert render_grid_svg(chars, info_footer=True, info_rows=None, **kw) == base
    assert render_grid_svg(chars, info_footer=True, info_rows=[], **kw) == base


def test_w2_api_defaults_to_off(client):
    a = client.get("/api/grid", params={"chars": "春天", "cols": 3})
    b = client.get("/api/grid",
                   params={"chars": "春天", "cols": 3, "info_footer": "false"})
    assert a.status_code == b.status_code == 200
    assert a.text == b.text


@needs_dict
def test_w2_footer_off_does_not_touch_the_dictionary(client, monkeypatch):
    """關著時連查都不查——預設路徑不付任何代價（同 R1b 雙軌）。"""
    import stroke_order.web.char_pipeline as cp

    def boom(*a, **k):
        raise AssertionError("info_footer 關著卻查了字典")

    monkeypatch.setattr(cp, "build_info_rows", boom)
    assert client.get("/api/grid",
                      params={"chars": "春天"}).status_code == 200


# ---------------------------------------------------------------------------
# 版面
# ---------------------------------------------------------------------------


@needs_dict
def test_w2_one_row_per_looked_up_char(client):
    svg = client.get("/api/grid", params={
        "chars": "春天日月", "cols": 3, "info_footer": "true"}).text
    assert svg.count('class="info-row"') == 4
    assert 'data-info-rows="4"' in svg
    for ch in "春天日月":
        assert f'<g class="info-row" data-char="{ch}">' in svg


@needs_dict
def test_w2_chars_missing_from_the_dictionary_are_simply_not_listed():
    """查無此字＝不列，不猜、不填佔位符（§87）。"""
    rows, _g = build_info_rows(["春", "A", "天"])
    assert [r["char"] for r in rows] == ["春", "天"]


def test_w2_missing_glyphs_leave_a_gap_not_a_placeholder():
    """字形缺席就留白——不得偷偷換成別的符號。"""
    frag, height = _info_footer_svg(
        [{"char": "春", "meta": "日部", "definition": "一年四季中的第一季。"}],
        {}, 4096.0)
    assert height > 0
    assert "<path" not in frag and "<polyline" not in frag
    assert "?" not in frag and "□" not in frag and "tofu" not in frag


def test_w2_footer_never_uses_a_text_element():
    """§5bv：<text> 在 Render 上會變空框（apt.txt 無 CJK 字型）。"""
    rows, glyphs = build_info_rows(["春"]) if moe_dict.is_ready() else (
        [{"char": "春", "meta": "日部", "definition": "測試"}], {})
    frag, _h = _info_footer_svg(rows, glyphs, 4096.0)
    assert "<text" not in frag and "font-family" not in frag


@needs_dict
@pytest.mark.parametrize("text,cols", [("春", 1), ("春天", 3), ("春天日月水火", 4)])
def test_w2_footer_ink_fits_inside_the_canvas(text, cols):
    """最後一列不得被畫布下緣削掉。

    註記字形是基線相對的（noto_hei 墨跡 y∈[573,2728]／EM 2048，下緣超出
    em 框 0.33 em）。第一版把「框高＝字級」當墨跡高，PNG 上最後一列被切
    掉半個字——這條算出實際墨跡下緣並和 viewBox 比對。
    """
    rows, glyphs = build_info_rows(list(text))
    svg = render_grid_svg(_chars(text), cols=cols, info_footer=True,
                          info_rows=rows, info_glyphs=glyphs)
    vb_w, vb_h = (float(x) for x in
                  re.search(r'viewBox="0 0 (\S+) (\S+)"', svg).groups())
    grid_h = float(re.search(r'<g transform="translate\(0,(\d+)\)">'
                             r'<g class="info-footer"', svg).group(1))
    text_em, _line_h, _cap = _info_metrics(vb_w)
    _ink_top, ink_bot = _ink_band(glyphs)
    # 每個註記字的 translate y（_info_text_paths 產生的 g）
    yvals = [float(m) for m in
             re.findall(r'translate\([\d.]+,(-?[\d.]+)\) scale', svg)]
    assert yvals, "footer 沒有畫出任何字"
    bottom = grid_h + max(yvals) + ink_bot * (text_em / EM_SIZE)
    assert bottom <= vb_h + 1.0, (bottom, vb_h)


@needs_dict
def test_w2_footer_adds_height_and_keeps_width(client):
    off = client.get("/api/grid", params={"chars": "春天", "cols": 3}).text
    on = client.get("/api/grid", params={
        "chars": "春天", "cols": 3, "info_footer": "true"}).text
    w0, h0 = re.search(r'viewBox="0 0 (\S+) (\S+)"', off).groups()
    w1, h1 = re.search(r'viewBox="0 0 (\S+) (\S+)"', on).groups()
    assert float(w0) == float(w1), "頁尾不得改變寬度"
    assert float(h1) > float(h0), "頁尾沒有把畫布加高"
    # px 尺寸要跟著 EM 一起長，比例不得走鐘
    px = lambda s: [int(x) for x in re.search(          # noqa: E731
        r'width="(\d+)" height="(\d+)"', s).groups()]
    (pw0, ph0), (pw1, ph1) = px(off), px(on)
    assert pw0 == pw1
    assert ph1 / ph0 == pytest.approx(float(h1) / float(h0), rel=0.01)


def test_w2_line_capacity_scales_with_the_sheet_not_the_cell():
    """字帖整張會等比貼進 A4，所以字級要看**版面寬**，不能只綁格高。

    只綁格高的話，兩個生字的窄字帖放大到 A4 後註記會變半個標題大——第一
    版就是這樣，一列只排得下 11 個字。
    """
    caps = [_info_metrics(n * EM_SIZE)[2] for n in (1, 2, 5, 10, 20)]
    assert all(c >= 40 for c in caps), caps
    # 寬字帖不會無限縮小字級（有下限＝格高的 0.18）
    assert _info_metrics(100 * EM_SIZE)[0] == pytest.approx(EM_SIZE * 0.18)


# ---------------------------------------------------------------------------
# 端到端
# ---------------------------------------------------------------------------


@needs_dict
def test_w2_pdf_end_to_end_contains_the_footer(client):
    """PDF 是字帖的主要出口（W1）——頁尾必須真的印得出來。"""
    off = client.get("/api/grid", params={
        "chars": "春天", "cols": 3, "format": "pdf"})
    on = client.get("/api/grid", params={
        "chars": "春天", "cols": 3, "format": "pdf", "info_footer": "true"})
    assert off.status_code == on.status_code == 200
    assert on.content[:5] == b"%PDF-"
    # 同一張紙、同樣的格子，多了註記 → 內容一定變多
    assert len(on.content) > len(off.content)


@needs_dict
def test_w2_svg_output_has_no_ellipsis_anywhere(client):
    svg = client.get("/api/grid", params={
        "chars": "春天日月", "cols": 3, "info_footer": "true"}).text
    for bad in _ELLIPSES:
        assert bad not in svg, bad


@needs_dict
def test_w2_gcode_and_json_ignore_the_footer(client):
    """註記是給人看的文字，寫字機器人不該去寫它。"""
    for fmt in ("gcode", "json"):
        a = client.get("/api/grid", params={
            "chars": "春天", "format": fmt}).text
        b = client.get("/api/grid", params={
            "chars": "春天", "format": fmt, "info_footer": "true"}).text
        assert a == b, fmt


# ---------------------------------------------------------------------------
# parity：UI 勾選 ≡ API 參數
# ---------------------------------------------------------------------------


def test_w2_ui_checkbox_id_matches_the_one_grid_js_reads():
    page = _INDEX.read_text("utf-8")
    js = _GRID_JS.read_text("utf-8")
    assert 'id="grid-info-footer"' in page, "index.html 沒有頁尾勾選框"
    assert 'getElementById("grid-info-footer")' in js, "grid.js 沒有讀勾選框"
    assert 'p.set("info_footer"' in js, "grid.js 沒有送 info_footer 參數"


def test_w2_api_exposes_info_footer_on_grid_only(client):
    """只有 /api/grid 有這個參數——別的模式沒實作就不該出現在 schema。"""
    spec = client.get("/openapi.json").json()
    names = {p["name"] for p in
             spec["paths"]["/api/grid"]["get"].get("parameters", [])}
    assert "info_footer" in names
    for path in ("/api/notebook", "/api/letter"):
        if path in spec["paths"]:
            other = {p["name"] for p in
                     spec["paths"][path]["get"].get("parameters", [])}
            assert "info_footer" not in other, path


def test_w2_separator_is_a_single_source_of_truth():
    """分隔符只有 exporters/grid.py 一份——伺服器層不得自己拼。"""
    cp = (_ROOT / "src" / "stroke_order" / "web"
          / "char_pipeline.py").read_text("utf-8")
    assert INFO_SEP not in cp, "char_pipeline 出現分隔符字面值"
