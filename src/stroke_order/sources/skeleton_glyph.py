"""骨架長肉字模引擎（R1a）——FANGCUN 評估（docs/analysis）後採納的參數化字模。

zh-stroke-data 骨架（track 折線）→ Chaikin 平滑 → shapely buffer「長肉」→
多輪廓折線。輸出形狀刻意對齊 ``cns_font._outline_to_polylines`` 的回傳
（list[list[(x, y)]]、EM 2048、Y-down、even-odd 相容），讓 popup/stencil 這類
消費端 drop-in、零改演算法。

參數軸（R1a 只走預設值；滑桿參數化排 R1b）：

- ``weight``：筆畫全寬（EM 2048 尺度、密度補償前）。
- ``cap``：``"round"``（圓體感）｜``"square"``（黑體感）。
- ``width_ratio``：字面率——對 EM 中心等比縮放。

密度補償（spike 2026-07-23 實證）：``w_eff = weight * sqrt(k / (k + n))``，
n＝筆畫數。未補償時密筆畫字（歡 22 筆）粗字重糊成黑塊；補償後（180→101）
字碗全開。

相依與降級（承 PRINCIPLES §8/§68）：shapely 為選用相依（pyproject web
extras）；缺席時拋 :class:`SkeletonGlyphUnavailable`，呼叫端維持既有 503
降級語意。骨架資料走 g0v（隨 repo 部署的 bundle 覆蓋常用字、零網路）；
缺字拋 g0v 的 ``CharacterNotFound``（語意不變）。
"""
from __future__ import annotations

import math
import threading
from typing import Optional

from ..ir import EM_SIZE
from .g0v import G0VSource

__all__ = [
    "SkeletonGlyphUnavailable",
    "flesh_character",
    "glyph_polylines",
    "is_available",
]

#: 密度補償常數（spike 定版）：w_eff = weight * sqrt(K_DENSITY/(K_DENSITY+n))
K_DENSITY = 10.0

#: Chaikin 平滑輪數（spike 定版；骨架 track 稀疏 2–7 點，3 輪足以去稜角）
CHAIKIN_ROUNDS = 3

_g0v_singleton: Optional[G0VSource] = None
_g0v_lock = threading.Lock()


class SkeletonGlyphUnavailable(Exception):
    """shapely（GEOS）未安裝——骨架長肉引擎不可用。"""


def is_available() -> bool:
    """shapely 是否可用（供健檢／呼叫端預判，不拋例外）。"""
    try:
        import shapely  # noqa: F401
        return True
    except Exception:
        return False


def _get_g0v() -> G0VSource:
    global _g0v_singleton
    if _g0v_singleton is None:
        with _g0v_lock:
            if _g0v_singleton is None:
                _g0v_singleton = G0VSource()
    return _g0v_singleton


def _effective_width(weight: float, stroke_count: int,
                     k: float = K_DENSITY) -> float:
    """筆畫密度補償：筆畫越多、有效字重越細（守門鎖單調性）。"""
    n = max(1, int(stroke_count))
    return float(weight) * math.sqrt(k / (k + n))


def _chaikin(pts: list[tuple[float, float]],
             rounds: int = CHAIKIN_ROUNDS) -> list[tuple[float, float]]:
    for _ in range(rounds):
        if len(pts) < 3:
            break
        out = [pts[0]]
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            out.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            out.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        out.append(pts[-1])
        pts = out
    return pts


def flesh_character(c, *,
                    weight: float = 120.0,
                    cap: str = "round",
                    width_ratio: float = 1.0):
    """骨架長肉核心：任意 ``Character`` → shapely Polygon 清單。

    R3 抽出的 seam（原先綁死 g0v 來源）：``glyph_polylines`` 與手寫字型
    （R3 的 user_dict → TTF）共用同一顆長肉引擎。回傳保留 shapely 的
    exterior/interiors 結構——字型組裝需要**環向資訊**（TrueType nonzero
    填色），攤平的 even-odd 折線給不了。

    Raises 同 :func:`glyph_polylines`（shapely 缺席／參數不合法），另在
    無可用筆畫時拋 ``CharacterNotFound``。
    """
    try:
        from shapely.geometry import LineString, MultiPolygon
        from shapely.ops import unary_union
    except Exception as e:
        raise SkeletonGlyphUnavailable(
            "shapely（GEOS）未安裝——骨架長肉字模不可用；"
            "pip install shapely 或安裝 web extras。"
        ) from e

    if weight <= 0:
        raise ValueError(f"weight 必須為正：{weight}")
    if width_ratio <= 0:
        raise ValueError(f"width_ratio 必須為正：{width_ratio}")
    if cap not in ("round", "square"):
        raise ValueError(f"cap 僅支援 round/square：{cap!r}")

    w = _effective_width(weight, c.stroke_count)

    parts = []
    for st in c.strokes:
        pts = [(p.x, p.y) for p in st.raw_track]
        if len(pts) < 2:
            continue
        pts = _chaikin(pts)
        parts.append(LineString(pts).buffer(
            w / 2.0, cap_style=cap, join_style="round"))
    if not parts:
        from .g0v import CharacterNotFound
        raise CharacterNotFound(f"{c.char!r} 骨架無可用筆畫 track")
    glyph = unary_union(parts)

    if width_ratio != 1.0:
        from shapely.affinity import scale as _scale
        ctr = EM_SIZE / 2.0
        glyph = _scale(glyph, xfact=width_ratio, yfact=width_ratio,
                       origin=(ctr, ctr))

    return list(glyph.geoms) if isinstance(glyph, MultiPolygon) else [glyph]


def glyph_polylines(char: str, *,
                    weight: float = 120.0,
                    cap: str = "round",
                    width_ratio: float = 1.0,
                    ) -> list[list[tuple[float, float]]]:
    """骨架長肉：回傳某字的字模多輪廓折線（EM 2048、even-odd 相容）。

    輪廓為開放點列（首尾不重複），外環與洞環攤平同列——與
    ``_outline_to_polylines`` 同形，消費端以 even-odd 掃描線填充即正確。

    Raises
    ------
    SkeletonGlyphUnavailable
        shapely 未安裝。
    stroke_order.sources.g0v.CharacterNotFound
        g0v 資料集查無此字。
    ValueError
        參數不合法（weight/width_ratio 非正、cap 未知）。
    """
    c = _get_g0v().get_character(char)   # 缺字 → CharacterNotFound（原語意）
    polys = flesh_character(c, weight=weight, cap=cap,
                            width_ratio=width_ratio)
    contours: list[list[tuple[float, float]]] = []
    for poly in polys:
        for ring in (poly.exterior, *poly.interiors):
            coords = list(ring.coords)
            if len(coords) >= 2 and coords[0] == coords[-1]:
                coords = coords[:-1]           # 開放點列（同 _outline_to_polylines）
            if len(coords) >= 3:
                contours.append([(float(x), float(y)) for x, y in coords])
    return contours
