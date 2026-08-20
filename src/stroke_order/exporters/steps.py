"""
X1 — 筆順分解圖（靜態逐筆累積條）。

老師從筆順字典網站抓圖貼 Word 的那個「第 N 格畫到第 N 筆」序列，本模組
原生排版：每字一條、格數＝筆畫數、自動換列；資料是 g0v 教育部標準楷書
筆順（隨 repo 離線），不抓任何外站。

視覺設計（sign-off：已寫淡灰＋當前濃黑＋小序號）
------------------------------------------------
**黃金規則：黑白影印後仍須可辨**（讀寫障礙教室幾乎必然黑白影印）。所以

- 已寫筆畫 ``STEP_DONE_COLOR``（淡灰）、當前筆 ``STEP_CURR_COLOR``（濃黑）
  ——灰階單調遞增，影印安全。刻意**不沿用 gif.py 的紅色 highlight**：
  ``#c33`` 轉灰階後比 ``#333`` 淡，影印下當前筆反而變淺。
- 序號走 **noto_hei 字形路徑**而非 ``<text>``（§5bv：cairosvg 吃伺服器
  字型堆疊，缺字型變空框；W1 起 PDF 是主要出口）。字形缺席時序號整個
  省略、不補符號（§87 不裝懂）。

排版承 §96 教訓：格數＝筆畫數（1–30+ 差異大）→ **必須自動換列**，頁寬由
``cols`` 決定、與單字筆畫數解耦。
"""
from __future__ import annotations

import math
from typing import Optional

from ..ir import EM_SIZE, Character
# 重用字帖排版層的既有輪子（同 package）：筆畫渲染、格線
from .grid import _guide_paths, _outline_or_track, GridStyle

__all__ = ["STEP_CURR_COLOR", "STEP_DONE_COLOR", "render_steps_svg"]

#: 已寫（淡灰）／當前（濃黑）。測試鎖「當前必須比已寫深」的灰階不變式，
#: 不鎖確切色值——鎖現象不鎖算式（§66）。
STEP_DONE_COLOR = "#b3b3b3"
STEP_CURR_COLOR = "#111111"

_NUM_COLOR = "#555555"
_NUM_SIZE_EM = int(EM_SIZE * 0.24)
#: 數字步進＝0.55 字級。noto_hei 的阿拉伯數字是比例寬（約半形），套 CJK
#: 的全形步進會排成「1 0」——第一版就是這樣，兩位數看起來像只印了個位。
_NUM_ADVANCE = 0.55
_CELL_GAP_EM = int(EM_SIZE * 0.08)
_STRIP_GAP_EM = int(EM_SIZE * 0.30)

#: noto_hei 墨跡的上下緣（EM 座標；W2 實測 y∈[573,2728]）——白底護墊要
#: 蓋住的就是這條墨帶。量測值取自 grid._ink_band 的同一批字形，這裡以
#: 序號實際用到的 0–9 再算一次、不硬抄。


def _step_number(k: int, glyphs: dict, ink_band: tuple) -> str:
    """右上角序號＋白底護墊。

    護墊的用途：分解圖後段的格子墨很滿，序號無論放哪都可能壓字——白底
    讓它在黑白影印下仍讀得出來（灰階可辨鐵則的一部分）。
    """
    text = str(k)
    scale = _NUM_SIZE_EM / EM_SIZE
    adv = _NUM_SIZE_EM * _NUM_ADVANCE
    w = adv * len(text)
    x0 = EM_SIZE - w - 50
    ink_top, ink_bot = ink_band
    pad = 36
    parts = [
        f'<g class="step-num" data-n="{k}">',
        f'<rect x="{x0 - pad:.0f}" y="{ink_top * scale - pad:.0f}" '
        f'width="{w + 2 * pad:.0f}" '
        f'height="{(ink_bot - ink_top) * scale + 2 * pad:.0f}" '
        f'fill="white"/>',
    ]
    cx = x0
    for ch in text:
        g = glyphs.get(ch)
        if g is not None and g.strokes:
            parts.append(
                f'<g transform="translate({cx:.1f},0) scale({scale:.6f})" '
                f'fill="{_NUM_COLOR}">'
                f'{_outline_or_track(g.strokes, _NUM_COLOR)}</g>')
        cx += adv
    parts.append("</g>")
    return "".join(parts)


def _digit_ink_band(glyphs: dict) -> tuple:
    """序號字形的實際墨跡上下緣——不假設字形填滿 em 框（§96.2）。"""
    lo = hi = None
    for g in glyphs.values():
        for st in getattr(g, "strokes", ()):
            b = st.bbox
            lo = b.y_min if lo is None else min(lo, b.y_min)
            hi = b.y_max if hi is None else max(hi, b.y_max)
    if lo is None or hi is None or hi <= lo:
        return 0.0, float(EM_SIZE)
    return float(lo), float(hi)


def _step_cell(char: Character, upto: int, guide_svg: str,
               digit_glyphs: Optional[dict], ink_band: tuple) -> str:
    """第 ``upto`` 格：筆畫 1..upto-1 淡灰、第 upto 筆濃黑、右上角序號。"""
    strokes = char.strokes
    parts = [guide_svg]
    done = strokes[:upto - 1]
    if done:
        parts.append(f'<g class="done" fill="{STEP_DONE_COLOR}">'
                     f'{_outline_or_track(done, STEP_DONE_COLOR)}</g>')
    parts.append(f'<g class="curr" fill="{STEP_CURR_COLOR}">'
                 f'{_outline_or_track([strokes[upto - 1]], STEP_CURR_COLOR)}'
                 f'</g>')
    if digit_glyphs:
        parts.append(_step_number(upto, digit_glyphs, ink_band))
    return "".join(parts)


def render_steps_svg(
    chars: list[Character],
    *,
    guide: GridStyle = "tian",
    cols: int = 12,
    cell_size_px: int = 96,
    digit_glyphs: Optional[dict] = None,
) -> str:
    """生字列表 → 筆順分解圖整張 SVG。

    每字一條（``<g class="step-strip" data-char data-steps>``），條內每格
    ``<g class="step-cell" data-step="k">``；超過 ``cols`` 自動換列。頁寬
    恆為 ``cols`` 格——與任何單字的筆畫數解耦（§96.1）。
    """
    chars = [c for c in chars if c.strokes]
    if not chars:
        return ('<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 1 1"></svg>')
    cols = max(1, cols)
    pitch = EM_SIZE + _CELL_GAP_EM
    width_em = cols * pitch - _CELL_GAP_EM
    guide_svg = _guide_paths(guide)
    ink_band = _digit_ink_band(digit_glyphs) if digit_glyphs else (0.0, 0.0)

    strips: list[str] = []
    y = 0
    for ch in chars:
        n = len(ch.strokes)
        rows = math.ceil(n / cols)
        esc = (ch.char.replace("&", "&amp;").replace("<", "&lt;")
                      .replace('"', "&quot;"))
        cells = [f'<g class="step-strip" data-char="{esc}" '
                 f'data-steps="{n}" transform="translate(0,{y})">']
        for k in range(1, n + 1):
            cx = ((k - 1) % cols) * pitch
            cy = ((k - 1) // cols) * pitch
            cells.append(
                f'<g class="step-cell" data-step="{k}" '
                f'transform="translate({cx},{cy})">'
                f'{_step_cell(ch, k, guide_svg, digit_glyphs, ink_band)}</g>')
        cells.append("</g>")
        strips.append("".join(cells))
        y += rows * pitch - _CELL_GAP_EM + _STRIP_GAP_EM
    height_em = y - _STRIP_GAP_EM

    scale = cell_size_px / EM_SIZE
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{round(width_em * scale)}" '
        f'height="{round(height_em * scale)}" '
        f'viewBox="0 0 {width_em} {height_em}">',
        f'<rect x="0" y="0" width="{width_em}" height="{height_em}" '
        f'fill="white"/>',
        *strips,
        "</svg>",
    ]
    return "\n".join(out)
