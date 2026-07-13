"""Phase 5dc: 鏤空字／噴漆字模（stencil & cutout）exporter.

雷切/噴漆字模的兩個對偶問題（使用者參考資料：竹米 STENCIL、
speedprint 鏤空字教學）：

- **噴漆字（stencil，模板字）**：留「板」、切掉字形。封閉孔洞
  （口/日/回 的中心）是被字形包圍的孤島，切完會掉——解法＝
  **鑿白橋**：在字形筆畫上留幾道不切的材料帶，把孤島接回大板。
- **鏤空字（cutout，字即本體）**：留「字」、切出字形本身。
  筆畫不連通（三＝三塊）會散成一地——解法＝**加黑橋**（連筋）
  把斷開元件連成單一連通件，或加**邊框**把整個字掛上去。

管線（幾何收集器＋多發射器，第四次應用）：
字形閉環（zentangle.extract_outline_polylines，真字型五源）
→ 光柵化（engrave.scanline_intersections 逐列 even-odd 填色）
→ 加粗 dilate（Kerf/噴漆擴散補償）→ 依子模式鑿白橋/加黑橋
→ 向量化（doodle._trace_boundary_loops＋閉環 RDP）
→ SVG（mm 契約）/DXF（R12 CUT 層）/G-code 三發射器。

⚠ 加工免責：橋接為幾何運算，繁體字結構複雜，上機前務必放大
檢查路徑（UI 已註明）。破字時調大橋寬或加粗（竹米經驗法則）。
"""
from __future__ import annotations

from typing import Literal, Optional

import numpy as np

from ..ir import EM_SIZE
from .doodle import _simplify_loop, _trace_boundary_loops
from .dxf import DxfPolyline, layers_to_dxf
from .engrave import scanline_intersections

StencilKind = Literal["stencil", "cutout"]

#: 光柵解析度（px/mm）——0.25mm/px；50mm 字高＝200px，
#: 2mm 橋寬＝8px，精度/效能平衡點。
PX_PER_MM = 4


# ---------------------------------------------------------------------------
# 光柵化與形態學（純 numpy，零新依賴）
# ---------------------------------------------------------------------------


def _closed(poly: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """確保多邊形首尾相接（scanline_intersections 需要顯式閉合邊）。"""
    if poly and poly[0] != poly[-1]:
        return list(poly) + [poly[0]]
    return list(poly)


def _fill_polys(mask: np.ndarray,
                polys: list[list[tuple[float, float]]],
                ox: int, oy: int, scale: float) -> None:
    """EM 座標閉環群 → 以 even-odd 規則填入 mask（True＝字墨）。

    真字型 glyph 的內外環設計上不重疊，even-odd ≈ nonzero
    （zentangle 既有消費者同一假設）。
    """
    closed = [_closed(p) for p in polys if len(p) >= 3]
    if not closed:
        return
    h, w = mask.shape
    ys = [p[1] for poly in closed for p in poly]
    py0 = max(0, int(min(ys) * scale) + oy)
    py1 = min(h - 1, int(max(ys) * scale) + oy + 1)
    for py in range(py0, py1 + 1):
        y_em = (py + 0.5 - oy) / scale
        xs = scanline_intersections(closed, y_em)
        for i in range(0, len(xs) - 1, 2):
            x0 = int(round(xs[i] * scale)) + ox
            x1 = int(round(xs[i + 1] * scale)) + ox
            if x1 >= x0:
                mask[py, max(0, x0):min(w, x1 + 1)] = True


def _shift_or(m: np.ndarray) -> np.ndarray:
    """4-鄰域膨脹一步（無 wrap-around）。"""
    out = m.copy()
    out[1:, :] |= m[:-1, :]
    out[:-1, :] |= m[1:, :]
    out[:, 1:] |= m[:, :-1]
    out[:, :-1] |= m[:, 1:]
    return out


def _dilate(mask: np.ndarray, r_px: int) -> np.ndarray:
    for _ in range(max(0, r_px)):
        mask = _shift_or(mask)
    return mask


def _run_fill_rows(region: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """逐列 run 填色：同一條 allowed 連續段內只要有 region 像素，
    整段填滿。單像素 frontier flood 在大畫布上要數千迭代；
    run 填色（列/行交替）數個 pass 即收斂。"""
    out = region.copy()
    h = region.shape[0]
    for i in range(h):
        r = out[i]
        if not r.any():
            continue
        a = allowed[i]
        runs = np.cumsum(~a)                  # 同一 allowed 段內 id 相同
        ids = runs[r & a]
        if ids.size:
            hit = np.zeros(int(runs[-1]) + 2, dtype=bool)
            hit[ids] = True
            out[i] = a & hit[runs]
    return out


def _flood(seed: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """從 seed 出發、在 allowed 內做 4-連通 flood fill。

    實作＝列向 run 填色與行向 run 填色交替至不動點（每 pass
    整段擴張，收斂快；正確性等價於 4-連通 flood）。"""
    region = seed & allowed
    while True:
        before = int(region.sum())
        region = _run_fill_rows(region, allowed)
        region = _run_fill_rows(region.T, allowed.T).T
        if int(region.sum()) == before:
            return region


def _outside(mask: np.ndarray) -> np.ndarray:
    """與畫布邊界連通的「外部空白」。"""
    free = ~mask
    seed = np.zeros_like(free)
    seed[0, :] = seed[-1, :] = True
    seed[:, 0] = seed[:, -1] = True
    return _flood(seed, free)


def _label(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """4-連通元件標記（元件數少的場景；BFS-flood 逐件）。"""
    labels = np.zeros(mask.shape, dtype=np.int32)
    remaining = mask.copy()
    n = 0
    while remaining.any():
        n += 1
        ys, xs = np.nonzero(remaining)
        seed = np.zeros_like(mask)
        seed[ys[0], xs[0]] = True
        comp = _flood(seed, remaining)
        labels[comp] = n
        remaining &= ~comp
    return labels, n


# ---------------------------------------------------------------------------
# 橋接（兩個對偶演算法）
# ---------------------------------------------------------------------------

_DIRS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))     # 上下左右（十字）
_DIRS_2 = ((-1, 0), (1, 0))                       # 上下


def carve_stencil_bridges(mask: np.ndarray, bridge_px: int,
                          bridge_count: int = 4) -> int:
    """噴漆模板：每個封閉孔洞沿十字方向鑿白橋接回外部。

    In-place 修改 mask；回傳橋接的孔洞數。
    """
    outside = _outside(mask)
    holes_lab, n_holes = _label(~mask & ~outside)
    half = max(1, bridge_px // 2)
    dirs = _DIRS_4 if bridge_count >= 4 else _DIRS_2
    h, w = mask.shape
    for hid in range(1, n_holes + 1):
        ys, xs = np.nonzero(holes_lab == hid)
        cy, cx = int(round(ys.mean())), int(round(xs.mean()))
        if holes_lab[cy, cx] != hid:      # 凹形孔：質心可能落在孔外
            k = int(np.argmin((ys - cy) ** 2 + (xs - cx) ** 2))
            cy, cx = int(ys[k]), int(xs[k])
        for dy, dx in dirs:
            y, x = cy, cx
            path: list[tuple[int, int]] = []
            reached = False
            while 0 <= y < h and 0 <= x < w:
                if outside[y, x]:
                    reached = True
                    break
                path.append((y, x))
                y += dy
                x += dx
            if not reached:
                continue
            for py, px in path:           # 鑿出垂直於行進方向的白色帶
                if dy != 0:
                    mask[py, max(0, px - half):min(w, px + half + 1)] = False
                else:
                    mask[max(0, py - half):min(h, py + half + 1), px] = False
    return n_holes


def _thick_line(mask: np.ndarray, a: tuple[int, int], b: tuple[int, int],
                half: int) -> None:
    """在 mask 上畫黑色粗線（Bresenham＋方形筆頭）。"""
    h, w = mask.shape
    y0, x0 = a
    y1, x1 = b
    n = max(abs(y1 - y0), abs(x1 - x0), 1)
    for i in range(n + 1):
        t = i / n
        y = int(round(y0 + (y1 - y0) * t))
        x = int(round(x0 + (x1 - x0) * t))
        mask[max(0, y - half):min(h, y + half + 1),
             max(0, x - half):min(w, x + half + 1)] = True


def connect_cutout_components(mask: np.ndarray, bridge_px: int,
                              max_iter: int = 64) -> int:
    """鏤空字：黑元件間以最近點對補黑橋（連筋），連成單一連通件。

    In-place；回傳補的橋數。含邊框時（邊框本身是一個元件）自動
    把每個字元件接上邊框——同一份程式碼吃兩種情境。
    """
    half = max(1, bridge_px // 2)
    added = 0
    for _ in range(max_iter):
        labels, n = _label(mask)
        if n <= 1:
            break
        # 取樣各元件像素（上限 ~400/件），找全域最近元件對
        pts: dict[int, np.ndarray] = {}
        for cid in range(1, n + 1):
            p = np.argwhere(labels == cid)
            step = max(1, len(p) // 400)
            pts[cid] = p[::step]
        best: Optional[tuple[float, tuple, tuple]] = None
        for a in range(1, n + 1):
            for b in range(a + 1, n + 1):
                pa, pb = pts[a], pts[b]
                d2 = ((pa[:, None, :] - pb[None, :, :]) ** 2).sum(-1)
                k = int(d2.argmin())
                i, j = divmod(k, d2.shape[1])
                dist = float(d2[i, j])
                if best is None or dist < best[0]:
                    best = (dist, tuple(pa[i]), tuple(pb[j]))
        assert best is not None
        _thick_line(mask, best[1], best[2], half)   # type: ignore[arg-type]
        added += 1
    return added


def add_frame(mask: np.ndarray, frame_px: int) -> None:
    """鏤空字邊框：畫布四周補黑色框帶（加工後把字掛在框上）。"""
    f = max(1, frame_px)
    mask[:f, :] = True
    mask[-f:, :] = True
    mask[:, :f] = True
    mask[:, -f:] = True


# ---------------------------------------------------------------------------
# 幾何收集器（主入口）
# ---------------------------------------------------------------------------


def stencil_geometry(
    char_polys: list[list[list[tuple[float, float]]]],
    *,
    kind: StencilKind = "stencil",
    char_height_mm: float = 50.0,
    bridge_width_mm: float = 2.0,
    bridge_count: int = 4,
    bold_mm: float = 0.0,
    spacing_mm: float = 5.0,
    margin_mm: Optional[float] = None,
    frame: bool = True,
    frame_width_mm: float = 4.0,
    px_per_mm: int = PX_PER_MM,
) -> tuple[list[list[tuple[float, float]]], float, float, dict]:
    """字形閉環群 → 橋接後的切割閉環（mm）＋板面尺寸＋統計。

    Returns ``(loops_mm, width_mm, height_mm, stats)``。loops 為
    閉環頂點序列（首尾不重複；發射器自行閉合）。
    """
    n = len(char_polys)
    if n == 0:
        return [], 0.0, 0.0, {}
    ch_px = max(8, int(round(char_height_mm * px_per_mm)))
    sp_px = max(0, int(round(spacing_mm * px_per_mm)))
    if margin_mm is None:
        margin_mm = max(5.0, char_height_mm * 0.2) if (
            kind == "stencil" or frame) else max(3.0, char_height_mm * 0.1)
    mg_px = max(2, int(round(margin_mm * px_per_mm)))
    w_px = 2 * mg_px + n * ch_px + (n - 1) * sp_px
    h_px = 2 * mg_px + ch_px

    mask = np.zeros((h_px, w_px), dtype=bool)
    scale = ch_px / EM_SIZE
    for i, polys in enumerate(char_polys):
        _fill_polys(mask, polys,
                    ox=mg_px + i * (ch_px + sp_px), oy=mg_px, scale=scale)

    bold_px = int(round(bold_mm * px_per_mm))
    if bold_px > 0:
        mask = _dilate(mask, bold_px)

    bw_px = max(2, int(round(bridge_width_mm * px_per_mm)))
    stats: dict = {"kind": kind}
    if kind == "stencil":
        stats["holes_bridged"] = carve_stencil_bridges(
            mask, bw_px, bridge_count)
    else:
        _labels, before = _label(mask)
        stats["components_before"] = before
        if frame:
            add_frame(mask, max(1, int(round(frame_width_mm * px_per_mm))))
        stats["bridges_added"] = connect_cutout_components(mask, bw_px)

    loops_px = _trace_boundary_loops(mask)
    min_area = (bw_px * bw_px) / 4.0          # 去斑：小於 1/4 橋寬平方
    loops_mm: list[list[tuple[float, float]]] = []
    for loop in loops_px:
        area = 0.0
        for i in range(len(loop)):
            x1, y1 = loop[i]
            x2, y2 = loop[(i + 1) % len(loop)]
            area += x1 * y2 - x2 * y1
        if abs(area) / 2.0 < min_area:
            continue
        simp = _simplify_loop(loop, eps=1.2)
        loops_mm.append([(x / px_per_mm, y / px_per_mm) for x, y in simp])
    stats["cut_loops"] = len(loops_mm)
    return loops_mm, w_px / px_per_mm, h_px / px_per_mm, stats


# ---------------------------------------------------------------------------
# 發射器：SVG（mm 契約）／DXF／G-code
# ---------------------------------------------------------------------------


def render_stencil_svg(loops_mm, width_mm: float, height_mm: float,
                       kind: StencilKind = "stencil") -> str:
    """全站契約：mm width/height ＝ viewBox 跨度（5bt audit）。"""
    d = " ".join(
        "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in loop) + " Z"
        for loop in loops_mm if len(loop) >= 3)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width_mm:.2f}mm" height="{height_mm:.2f}mm" '
        f'viewBox="0 0 {width_mm:.2f} {height_mm:.2f}" '
        f'data-stencil-kind="{kind}">']
    if kind == "stencil":
        # 板留下、字形區域被切掉（露白）
        parts.append(f'<rect x="0" y="0" width="{width_mm:.2f}" '
                     f'height="{height_mm:.2f}" fill="#d9c7a0"/>')
        parts.append(f'<path d="{d}" fill="#ffffff" fill-rule="evenodd" '
                     f'stroke="#c22" stroke-width="0.2"/>')
    else:
        # 字即本體（材料留下的部分）
        parts.append(f'<rect x="0" y="0" width="{width_mm:.2f}" '
                     f'height="{height_mm:.2f}" fill="#ffffff"/>')
        parts.append(f'<path d="{d}" fill="#555555" fill-rule="evenodd" '
                     f'stroke="#c22" stroke-width="0.2"/>')
    parts.append("</svg>")
    return "\n".join(parts)


def render_stencil_dxf(loops_mm) -> str:
    polys = [DxfPolyline(points=list(loop), closed=True)
             for loop in loops_mm if len(loop) >= 3]
    return layers_to_dxf([("CUT", polys)])


def render_stencil_gcode(
    loops_mm,
    *,
    feed_rate: int = 3000,
    travel_rate: int = 6000,
    pen_up_cmd: str = "M5",
    pen_down_cmd: str = "M3 S90",
    pen_dwell_sec: float = 0.15,
    origin_x_mm: float = 10.0,
    origin_y_mm: float = 10.0,
    height_mm: float = 0.0,
    flip_y: bool = True,
) -> str:
    """切割閉環 → G-code（沿用 grid/patch 全慣例）。"""
    from io import StringIO
    buf = StringIO()
    buf.write("; --- stroke-order 鏤空字/噴漆字模 G-code (CUT loops) ---\n")
    buf.write(f"; loops: {len(loops_mm)}\n")
    buf.write("G21 ; mm\nG90 ; absolute\n")
    buf.write(f"{pen_up_cmd} ; pen up (start)\n")
    if pen_dwell_sec > 0:
        buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")
    buf.write(f"G0 X{origin_x_mm:.3f} Y{origin_y_mm:.3f} "
              f"F{travel_rate} ; home\n")

    def _xy(p):
        x, y = p
        yy = (height_mm - y) if flip_y else y
        return origin_x_mm + x, origin_y_mm + yy

    for li, loop in enumerate(loops_mm):
        if len(loop) < 3:
            continue
        buf.write(f"\n; --- loop {li + 1} ---\n")
        x, y = _xy(loop[0])
        buf.write(f"G0 X{x:.3f} Y{y:.3f} F{travel_rate}\n")
        buf.write(f"{pen_down_cmd}\n")
        if pen_dwell_sec > 0:
            buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")
        for p in list(loop[1:]) + [loop[0]]:      # 顯式閉合
            x, y = _xy(p)
            buf.write(f"G1 X{x:.3f} Y{y:.3f} F{feed_rate}\n")
        if pen_dwell_sec > 0:
            buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")
        buf.write(f"{pen_up_cmd}\n")

    buf.write("\n; --- epilogue ---\n")
    buf.write(f"{pen_up_cmd} ; ensure pen up\n")
    buf.write(f"G0 X{origin_x_mm:.3f} Y{origin_y_mm:.3f} "
              f"F{travel_rate} ; return home\n; done\n")
    return buf.getvalue()


__all__ = [
    "StencilKind", "stencil_geometry",
    "carve_stencil_bridges", "connect_cutout_components", "add_frame",
    "render_stencil_svg", "render_stencil_dxf", "render_stencil_gcode",
]
