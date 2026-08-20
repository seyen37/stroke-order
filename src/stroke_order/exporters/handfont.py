"""
R3 — 手寫字型：user_dict 手寫軌跡 → 可安裝的 TrueType 字型檔。

FANGCUN 評估（2026-08-11）標記的「差異化殺手鐧」：使用者親手寫的軌跡
（手寫練習已存 EM 2048 折線）經 R1a 長肉引擎變成輪廓，用 fontTools 組成
字型——「你的手寫變成字型」。字集**只含寫過的字**（sign-off）：字型裡每
一個字形都是本人手寫，沒寫過的字顯示 .notdef，這是字型的正常行為，也是
「純手寫」的誠實保證。

座標與度量
----------
- 專案 EM 2048（Y-down）恰好是 TrueType 的慣用 unitsPerEm——零縮放。
- 基線：手寫框的下緣落在 descender 上（CJK 慣例 12% em）：
  ``y_font = EM - y_down - DESCENT``。
- 全形等寬：advance = 2048（CJK 慣例）。

環向（winding）
---------------
TrueType 是 **nonzero** 填色，外環與洞環必須反向——這正是 R3 在
skeleton_glyph 抽 ``flesh_character`` seam 的原因：攤平的 even-odd 折線
沒有環向資訊，只有 shapely 的 exterior/interiors 給得出來。本模組以
signed area 明確定向（外環順時針、洞環逆時針，y-up 座標系），不信任
上游預設。

著作權
------
手寫字形的著作權屬於**書寫者本人**（FANGCUN 評估即定此原則）——字型的
name table 寫明這一點，本專案只是工具。
"""
from __future__ import annotations

from typing import Optional

from ..ir import EM_SIZE, Character

__all__ = ["HandFontUnavailable", "build_hand_font"]

#: 基線位置：手寫框下緣 = descender（12% em，CJK 慣例）
DESCENT = round(EM_SIZE * 0.12)          # 246
ASCENT = EM_SIZE - DESCENT               # 1802

_FAMILY = "StrokeOrder Handwriting"
_FAMILY_ZH = "我的手寫字"


class HandFontUnavailable(Exception):
    """fontTools／shapely 缺席——手寫字型組裝不可用。"""


def _signed_area(coords) -> float:
    s = 0.0
    n = len(coords)
    for i in range(n):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _draw_ring(pen, coords, *, clockwise: bool) -> None:
    """畫一個閉環（座標已是字型 y-up），依需求定向。"""
    pts = [(round(x), round(y)) for x, y in coords]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return
    # signed area > 0 ＝ 逆時針（y-up）
    if (_signed_area(pts) > 0) == clockwise:
        pts = pts[::-1]
    pen.moveTo(pts[0])
    for pt in pts[1:]:
        pen.lineTo(pt)
    pen.closePath()


def _glyph_from_character(c: Character, *, weight: float, cap: str):
    """一個手寫 Character → TrueType glyph（含正確環向）。"""
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from ..sources.skeleton_glyph import flesh_character

    polys = flesh_character(c, weight=weight, cap=cap)
    pen = TTGlyphPen(None)
    for poly in polys:
        flip = lambda ring: [(x, EM_SIZE - y - DESCENT)   # noqa: E731
                             for x, y in ring.coords]
        _draw_ring(pen, flip(poly.exterior), clockwise=True)
        for hole in poly.interiors:
            _draw_ring(pen, flip(hole), clockwise=False)
    return pen.glyph()


def build_hand_font(
    chars: list[Character],
    *,
    weight: float = 120.0,
    cap: str = "round",
    owner: Optional[str] = None,
) -> bytes:
    """手寫 Character 清單 → TTF bytes。

    ``chars`` 為 user_dict 的手寫字（呼叫端負責只餵手寫的——「純手寫」
    是這顆字型的產品定位）。``owner`` 是書寫者名字（進 name table 的
    著作權標注；預設不具名）。
    """
    try:
        from fontTools.fontBuilder import FontBuilder
        from fontTools.pens.ttGlyphPen import TTGlyphPen
    except Exception as e:  # pragma: no cover — fonttools 是必要相依
        raise HandFontUnavailable(f"fontTools 不可用：{e}") from e

    chars = [c for c in chars if c.strokes]
    if not chars:
        raise ValueError("沒有任何手寫字——先寫幾個字再匯出字型")

    glyph_order = [".notdef"]
    glyphs = {".notdef": TTGlyphPen(None).glyph()}
    cmap: dict[int, str] = {}
    for c in chars:
        name = f"uni{ord(c.char):04X}"
        if name in glyphs:
            continue
        glyphs[name] = _glyph_from_character(c, weight=weight, cap=cap)
        glyph_order.append(name)
        cmap[ord(c.char)] = name

    fb = FontBuilder(EM_SIZE, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    metrics = {}
    glyf = fb.font["glyf"]
    for name in glyph_order:
        g = glyf[name]
        lsb = g.xMin if hasattr(g, "xMin") and g.numberOfContours else 0
        metrics[name] = (EM_SIZE, lsb)     # 全形等寬
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=ASCENT, descent=-DESCENT)
    fb.setupOS2(sTypoAscender=ASCENT, sTypoDescender=-DESCENT,
                usWinAscent=ASCENT, usWinDescent=DESCENT)
    who = (owner or "").strip() or "書寫者"
    fb.setupNameTable({
        "familyName": _FAMILY,
        "styleName": "Regular",
        "fullName": f"{_FAMILY} ({_FAMILY_ZH})",
        "psName": "StrokeOrderHandwriting-Regular",
        "copyright": (f"字形為{who}之手寫創作，著作權歸書寫者本人。"
                      "由 stroke-order 專案工具產生。"),
        "licenseDescription": "字形著作權歸書寫者；本檔供其自由使用。",
    })
    fb.setupPost()

    import io
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()
