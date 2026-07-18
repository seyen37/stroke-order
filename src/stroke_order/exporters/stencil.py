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

import math
from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np

from ..ir import EM_SIZE
from .doodle import _simplify_loop, _trace_boundary_loops
from .dxf import DxfPolyline, layers_to_dxf
from .engrave import scanline_intersections

StencilKind = Literal["stencil", "cutout"]

# ---------------------------------------------------------------------------
# 切割風格 registry（5ef，承 5dm STENCIL_CUTTING_STYLES.md §4/§5）
# ---------------------------------------------------------------------------
#
# 5dm 把「切割策略」與「筆形字型」歸納為兩條正交軸（見文件 §7）：筆形由
# `zentangle.SOURCE_REGISTRY`（選字型）免費提供，引擎只需管**切割策略**軸。
# 該軸的定義參數＝`connect_depth`（連筋深度／文件 §4 R5 核心）：
#
#   - ``full``     ＝全連派：每個 counter 都鑿橋連通、殘腔 0（物理有效字模，
#                    可真的噴漆／雷切）。本專案 5dm 引擎的既有唯一策略。
#   - ``envelope`` ＝外框派（方正簡潔美學，5eg 實作）：只斷最外圈包圍
#                    （深度 1 的孔），深層巢狀 counter（回的中心、國/圖的
#                    內件）留成孤島。斷點最少、最像手寫連筋字，但**非物理
#                    完整**（深層料會掉）——適合展示／厚料，UI 有免責提示。
#
# 5ef 為純重構立好 seam；5eg 加入 envelope 第二策略（新演算法＝孔巢狀深度
# 偵測＋深度過濾，見 `_hole_depths`／`carve_stencil_bridges(max_depth=)`）。
# 其餘 §4 參數（bridge_axis、near_wall_only、keep_primary…）目前在 carve
# 函式內恆為 full 值，待需要它們的策略落地時再拉進 style struct（YAGNI）。

CutConnectDepth = Literal["full", "envelope"]

#: connect_depth → carve_stencil_bridges 的 max_depth（None＝全連、1＝只外框）。
_CONNECT_DEPTH_MAX: dict[str, Optional[int]] = {"full": None, "envelope": 1}

#: 保主幹策略（§4 keep_primary，5ei）：
#:   - ``thinnest_wall``  ＝隱含版（現行）：每轉角挑最短穿牆，不管橫豎。
#:   - ``vertical_first`` ＝顯式版（R1）：偏好垂直射線（切橫筆）、保豎筆主幹，
#:     橫豎近等厚時仍保豎；豎筆明顯較薄時 BIAS 有界仍照切（不做荒謬長切）。
CutKeepPrimary = Literal["thinnest_wall", "vertical_first"]


@dataclass(frozen=True)
class CuttingStyle:
    """一種切割風格（切割策略軸的一個 preset）。

    承載真正**改變輸出**的策略參數：``connect_depth``（連筋深度／5eg）與
    ``keep_primary``（保主幹策略／5ei）。``label`` 供 UI/header 顯示。§4
    其餘參數（bridge_axis、near_wall_only…）待有策略需要時再拉進（YAGNI）。
    """

    key: str
    label: str
    connect_depth: CutConnectDepth
    keep_primary: CutKeepPrimary = "thinnest_wall"


#: 切割風格登記處（key → CuttingStyle）。physical＝物理完整（全連派、殘腔
#: 0、最短穿牆）；envelope＝方正簡潔（只外框、深層留島、切橫保豎主幹）。
CUTTING_STYLES: dict[str, CuttingStyle] = {
    "physical": CuttingStyle(
        key="physical", label="物理完整", connect_depth="full",
        keep_primary="thinnest_wall"),
    "envelope": CuttingStyle(
        key="envelope", label="方正簡潔", connect_depth="envelope",
        keep_primary="vertical_first"),
}

#: 預設切割風格（維持既有行為）。
DEFAULT_CUTTING_STYLE = "physical"


def get_cutting_style(key: str) -> CuttingStyle:
    """依 key 取切割風格；未知 key 拋 ``KeyError``（呼叫端轉 422）。"""
    try:
        return CUTTING_STYLES[key]
    except KeyError:
        raise KeyError(
            f"unknown cutting style: {key!r}; "
            f"available: {sorted(CUTTING_STYLES)}") from None

#: 光柵解析度（px/mm）。5do：4→8（0.125mm/px）——黑體軸向邊的階梯步階
#: 減半，配合較大的 RDP 容差（_STENCIL_RDP_EPS）把殘餘微凸/微凹去乾淨，
#: 噴漆字輪廓更平順。50mm 字高＝400px、2mm 橋寬＝16px；純後端、效能充裕。
PX_PER_MM = 8

#: 5do：字模 loop 簡化容差（px）。8px/mm 下 2.0px≈0.25mm——吃掉光柵階梯
#: 的微段（微凸/微凹），但遠小於筆畫/橋（≥16px）與真轉角，故不損字形。
_STENCIL_RDP_EPS = 2.0


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

_DIRS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))     # 上下左右（十字，fallback 用）
_DIRS_2 = ((-1, 0), (1, 0))                       # 上下（fallback 用）

#: 5dm（方正大黑連筋切法）：橋接逃逸限定純軸向四方向（dx, dy）——
#: 右/左/下/上。軸向缺口＝乾淨矩形（像被內縮的橫/豎筆端），取代 5dl 的
#: ±70° 斜向扇形（斜橋在複雜字如「圖」會糊成一團）。
_ESCAPE_AXES = ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0))

#: 5dg 轉角偵測：RDP 簡化後方向變化 ≥ 45° 視為轉角
#: （cos 45° ≈ 0.707；夾角判斷用內積）。
_CORNER_COS = math.cos(math.radians(45.0))
#: 5dg 放射逃逸的長度上限（px）——超過視為「該方向沒有出口」。
_ESCAPE_CAP_PX = 120


def _hole_corners(hole_mask: np.ndarray) -> list[tuple[float, float]]:
    """孔洞邊界的轉角頂點（(x, y) px）。

    5dg：孔洞輪廓 → RDP 簡化 → 方向變化 ≥45° 的頂點＝轉角。
    孔洞邊界的轉角正是筆畫交接處（口的四角＝橫豎筆相交點）；
    直筆中段是直線段、永遠不會成為候選。
    """
    loops = _trace_boundary_loops(hole_mask)
    if not loops:
        return []
    loop = max(loops, key=len)
    simp = _simplify_loop(loop, eps=2.0)
    m = len(simp)
    if m < 3:
        return []
    corners: list[tuple[float, float]] = []
    for i in range(m):
        x0, y0 = simp[i - 1]
        x1, y1 = simp[i]
        x2, y2 = simp[(i + 1) % m]
        v1x, v1y = x1 - x0, y1 - y0
        v2x, v2y = x2 - x1, y2 - y1
        n1 = math.hypot(v1x, v1y)
        n2 = math.hypot(v2x, v2y)
        if n1 < 1e-9 or n2 < 1e-9:
            continue
        cosang = (v1x * v2x + v1y * v2y) / (n1 * n2)
        if cosang <= _CORNER_COS:
            corners.append((float(x1), float(y1)))
    return corners


def _radial_escape(mask: np.ndarray, outside: np.ndarray,
                   start_xy: tuple[float, float],
                   dir_xy: tuple[float, float]) -> Optional[
                       list[tuple[int, int]]]:
    """從孔洞邊界點沿放射方向走到板外；回傳沿途墨像素（(y, x)）。

    走不到外部（出界/超過 _ESCAPE_CAP_PX）回傳 None。路徑長度
    ＝該轉角處的筆畫厚度（越短＝越適合鑿橋）。
    """
    h, w = mask.shape
    x, y = start_xy
    dx, dy = dir_xy
    path: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for _ in range(_ESCAPE_CAP_PX * 4):
        px, py = int(round(x)), int(round(y))
        if not (0 <= px < w and 0 <= py < h):
            return None
        if outside[py, px]:
            return path
        if mask[py, px] and (py, px) not in seen:
            seen.add((py, px))
            path.append((py, px))
            if len(path) > _ESCAPE_CAP_PX:
                return None
        x += dx * 0.5
        y += dy * 0.5
    return None


def _carve_cross_bridges(mask: np.ndarray, outside: np.ndarray,
                         cy: int, cx: int, half: int,
                         bridge_count: int) -> None:
    """5dc 原十字/上下鑿橋（保留為無轉角孔洞的 fallback）。"""
    h, w = mask.shape
    dirs = _DIRS_4 if bridge_count >= 4 else _DIRS_2
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
        for py, px in path:               # 鑿出垂直於行進方向的白色帶
            if dy != 0:
                mask[py, max(0, px - half):min(w, px + half + 1)] = False
            else:
                mask[max(0, py - half):min(h, py + half + 1), px] = False


#: 5dl 孔洞夠大才給第二道橋（px）——小孔一道即固定、可讀性優先。
_TWO_BRIDGE_MIN_PX = 30

#: 5ei keep_primary="vertical_first" 的水平逃逸懲罰倍率。水平射線（切豎筆
#: 主幹）的穿牆長度 ×BIAS 再比較——橫豎近等厚時偏好垂直射線（切橫筆、保豎），
#: 但豎筆若明顯較薄（<1/BIAS）仍照切（有界、不做荒謬長切）。1.6＝橫筆需比
#: 豎筆薄逾 37.5% 才會改切橫（保豎主幹的合理門檻）。
_VERTICAL_FIRST_BIAS = 1.6


def _escape_score(path_len: int, dyf: float, keep_primary: str) -> float:
    """逃逸方向的**選牆分數**（越小越優先）＝穿牆長度，`vertical_first` 時
    對水平射線（``dyf == 0``＝切豎筆主幹）乘上 BIAS 懲罰。thinnest_wall
    回傳原長＝現行行為（逐位元不變）。"""
    if keep_primary == "vertical_first" and dyf == 0.0:
        return path_len * _VERTICAL_FIRST_BIAS
    return float(path_len)


def _count_true_runs(arr: np.ndarray) -> int:
    """1D 布林陣列中 True 連續段（run）數＝上升緣數。"""
    if arr.size == 0:
        return 0
    return int(arr[0]) + int(np.count_nonzero(arr[1:] & ~arr[:-1]))


def _hole_depths(mask: np.ndarray, holes_lab: np.ndarray,
                 n_holes: int) -> dict[int, int]:
    """每個封閉孔的**巢狀深度**＝到板外的最少穿牆數（5eg／envelope 風格用）。

    幾何依據（Jordan 曲線）：一個被 d 層封閉筆畫包住的孔，任一射線到板外
    必**至少**穿越 d 道牆；存在一條「乾淨」方向恰穿 d 道。故對每孔取多個
    樣本像素、往四軸向各射一線、數該線的墨 run（＝穿牆數），**全取最小**
    ＝該孔深度。depth 1＝最外圈孔（穿一道牆即出板）、depth≥2＝深層巢狀。

    純 numpy（軸向射線用列/行切片，無斜向穿角漏數問題）；只在 envelope
    需要時呼叫。
    """
    depths: dict[int, int] = {}
    for hid in range(1, n_holes + 1):
        ys, xs = np.nonzero(holes_lab == hid)
        if len(ys) == 0:
            depths[hid] = 1
            continue
        step = max(1, len(ys) // 9)          # 最多 ~9 個樣本像素
        best: Optional[int] = None
        for idx in range(0, len(ys), step):
            y0, x0 = int(ys[idx]), int(xs[idx])
            rays = (
                mask[y0, x0 + 1:],            # →
                mask[y0, :x0][::-1],          # ←
                mask[y0 + 1:, x0],            # ↓
                mask[:y0, x0][::-1],          # ↑
            )
            for ray in rays:
                wc = _count_true_runs(ray)
                if wc >= 1 and (best is None or wc < best):
                    best = wc
        depths[hid] = best if best is not None else 1
    return depths


def carve_stencil_bridges(mask: np.ndarray, bridge_px: int,
                          bridge_count: int = 4,
                          max_depth: Optional[int] = None,
                          keep_primary: str = "thinnest_wall") -> int:
    """噴漆模板：每個封閉孔洞鑿白橋接回外部。In-place；回傳孔洞數。

    5dl（使用者實測回饋：截斷切筆畫中段、破壞可讀性）——「最短垂直橋＋
    轉角優先＋自動取最少橋數」：
    1. 偵測孔洞邊界轉角（_hole_corners）＝筆畫交接處
    2. 每轉角沿「質心→轉角」放射逃逸到板外，路徑長＝該處穿牆厚度
    3. **逃逸最短優先**（＝最薄的牆、料損最小）＋空間分隔（橋不擠在
       一起），取 1~2 道（小孔 1、大孔 2；bridge_count 為上限）
    4. 無轉角孔洞（圓孔等）退回 5dc 十字射線（降級階梯）

    改動要點（vs 5dg）：橋數自動取最少（1~2，不再一律 bridge_count）、
    改以「最短穿牆」而非「角度最開」選橋——截口落在筆畫最細的交接處、
    直筆中段幾乎不切。

    5eg（envelope 切割風格）：``max_depth`` 為 None＝全連派（每個孔都鑿橋、
    殘腔 0，物理有效字模）；給整數（envelope＝1）＝只鑿**深度 ≤ max_depth**
    的孔（最外圈環），深層巢狀孔（回的中心、國/圖的內件）**留成孤島**——
    方正簡潔美學、斷點最少，但**非物理完整**（深層料會掉）。回傳**實際鑿
    橋的孔數**（full 時＝總孔數；envelope 時＜總孔數）。

    5ei（keep_primary 保主幹）：``thinnest_wall``（現行）純挑最短穿牆；
    ``vertical_first`` 對水平射線（切豎筆主幹）加 BIAS 懲罰，橫豎近等厚時
    偏好垂直射線（切橫筆、保豎主幹＝R1），豎筆明顯較薄仍照切（BIAS 有界）。
    """
    outside = _outside(mask)
    holes_lab, n_holes = _label(~mask & ~outside)
    # envelope：先在**原始 mask**上快照全孔深度（鑿橋會改 mask、影響後續
    # 孔深度判定，故必須先算），再據以跳過深層孔。
    depths = (_hole_depths(mask, holes_lab, n_holes)
              if max_depth is not None else None)
    bridged = 0
    half = max(1, bridge_px // 2)
    h_, w_ = mask.shape
    for hid in range(1, n_holes + 1):
        if depths is not None and depths.get(hid, 1) > max_depth:
            continue                          # envelope：深層孔留島、不鑿
        bridged += 1
        hole = holes_lab == hid
        ys, xs = np.nonzero(hole)
        fcy, fcx = float(ys.mean()), float(xs.mean())
        cy, cx = int(round(fcy)), int(round(fcx))
        if holes_lab[cy, cx] != hid:      # 凹形孔：質心可能落在孔外
            k = int(np.argmin((ys - cy) ** 2 + (xs - cx) ** 2))
            cy, cx = int(ys[k]), int(xs[k])
        # 5dl：自動最少橋數——小孔 1 道、較大孔 2 道，bridge_count 為上限。
        hole_span = max(int(ys.max() - ys.min()), int(xs.max() - xs.min()))
        n_want = 2 if hole_span >= _TWO_BRIDGE_MIN_PX else 1
        n_want = min(n_want, max(1, bridge_count))
        # --- 轉角候選：每轉角在「朝外扇形」內找**最短穿牆**方向 ---
        # （5dl：不只走質心→轉角的放射對角，而是在其 ±70° 扇形內掃描，
        #  取逃逸最短者＝垂直於最薄的牆、料損最小、截口不落直筆中段。）
        cands: list[tuple[int, tuple[int, int], list[tuple[int, int]]]] = []
        for corner_x, corner_y in _hole_corners(hole):
            # 5dm（方正大黑連筋切法）：每轉角只試上/下/左/右四個純軸方向，
            # 取最短穿牆者。最短軸向逃逸＝垂直穿越最薄的牆（橫或豎筆），
            # 缺口為乾淨矩形、像被內縮的筆畫端——保留字形交接處可讀特徵，
            # 取代 5dl 的 ±70° 斜向扇形（斜橋在複雜字會糊成一團）。
            best: Optional[tuple[float, list[tuple[int, int]]]] = None
            for dxf, dyf in _ESCAPE_AXES:
                # 只走「近牆」：往該方向須立即進入墨（牆）內。若第一步落在
                # 孔洞空腔（自由空間），此方向會穿越整個孔、鑿到對側遠牆——
                # 對邊兩轉角於是撞同一面牆併成一橋（大孔只剩單橋、不穩）。
                # 近牆判定＝往內 2px 仍是墨。
                nx = int(round(corner_x + dxf * 2))
                ny = int(round(corner_y + dyf * 2))
                if not (0 <= ny < h_ and 0 <= nx < w_ and mask[ny, nx]):
                    continue
                path = _radial_escape(mask, outside, (corner_x, corner_y),
                                      (dxf, dyf))
                if not path:
                    continue
                # 5ei：以選牆分數（vertical_first 懲罰水平射線＝保豎主幹）而
                # 非原始長度比較；thinnest_wall 時分數＝長度（行為不變）。
                score = _escape_score(len(path), dyf, keep_primary)
                if best is None or score < best[0]:
                    best = (score, path)
            if best:
                cands.append((best[0], (int(round(corner_y)),
                                        int(round(corner_x))), best[1]))
        if not cands:                     # 無轉角/出不去 → 5dc fallback
            _carve_cross_bridges(mask, outside, cy, cx, half, bridge_count)
            continue
        # --- 選橋：最短穿牆優先（最薄的牆）＋空間分隔（橋不擠一起）---
        cands.sort(key=lambda c: c[0])
        sep = max(6.0, hole_span * 0.35)
        chosen: list[tuple[int, tuple[int, int], list[tuple[int, int]]]] = []
        for c in cands:
            if len(chosen) >= n_want:
                break
            cyc, cxc = c[1]
            if all(math.hypot(cyc - o[1][0], cxc - o[1][1]) >= sep
                   for o in chosen):
                chosen.append(c)
        if len(chosen) < n_want:          # 分隔太嚴 → 按長度遞補
            for c in cands:
                if c not in chosen:
                    chosen.append(c)
                if len(chosen) >= n_want:
                    break
        for _len, _pt, path in chosen:    # 方形筆頭沿最短逃逸路徑鑿白
            for py, px in path:
                mask[max(0, py - half):min(h_, py + half + 1),
                     max(0, px - half):min(w_, px + half + 1)] = False
    return bridged


def _ang_diff(a: float, b: float) -> float:
    """兩角最小差（rad，0~π）。"""
    d = abs(a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


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


def _connect_to_frame(mask: np.ndarray, labels: np.ndarray, n: int,
                      frame_ids: set[int], half: int, ties: int) -> int:
    """5dl：含邊框時，每個字元件直接以**最近框邊的垂直輻條**接上外框。

    每件連 1~2 條短輻條、皆指向最近的框邊材料——輻條放射狀、彼此
    不交叉（取代舊的全域最近點對貪婪連接，那會讓字件間的連筋斜跨
    交叉）。``ties >= 2`` 時補第二輻條：取與第一錨點分隔夠遠的字件
    像素、連到它自己最近的框邊。
    """
    added = 0
    frame_mask = np.isin(labels, list(frame_ids))
    fpts = np.argwhere(frame_mask)
    fstep = max(1, len(fpts) // 4000)
    fpool = fpts[::fstep]
    for cid in range(1, n + 1):
        if cid in frame_ids:
            continue
        comp = np.argwhere(labels == cid)
        cstep = max(1, len(comp) // 800)
        cpool = comp[::cstep]
        # 輻條 1：字件→外框全域最近點對（最短連接）。
        d2 = ((cpool[:, None, :] - fpool[None, :, :]) ** 2).sum(-1)
        k = int(d2.argmin())
        i, j = divmod(k, d2.shape[1])
        a1 = tuple(cpool[i])
        _thick_line(mask, a1, tuple(fpool[j]), half)  # type: ignore[arg-type]
        added += 1
        if ties < 2:
            continue
        # 輻條 2：離 a1 夠遠的字件像素中、離框最近者（第二支撐、不擠）。
        span = max(int(comp[:, 0].max() - comp[:, 0].min()),
                   int(comp[:, 1].max() - comp[:, 1].min()))
        sep2 = max(8.0, span * 0.4) ** 2
        da = ((cpool - np.asarray(a1)) ** 2).sum(1)
        far = cpool[da > sep2]
        if len(far) == 0:
            continue
        d2b = ((far[:, None, :] - fpool[None, :, :]) ** 2).sum(-1)
        kk = int(d2b.argmin())
        ii, jj = divmod(kk, d2b.shape[1])
        _thick_line(mask, tuple(far[ii]), tuple(fpool[jj]),  # type: ignore
                    half)
        added += 1
    return added


def connect_cutout_components(mask: np.ndarray, bridge_px: int,
                              max_iter: int = 64, ties: int = 2) -> int:
    """鏤空字：黑元件間補黑橋（連筋），連成單一連通件。In-place；回傳橋數。

    5dl：**含邊框時**改走 ``_connect_to_frame``——每字件以最近框邊的
    垂直輻條接框、放射不交叉（取代舊全域最近點對貪婪，後者字件間斜
    跨會交叉）。**無邊框時**維持舊的全域最近點對貪婪＋5dg 對稱雙筋
    （字件互連、無框可放射）。
    """
    half = max(1, bridge_px // 2)
    labels_f, n_f = _label(mask)
    if n_f <= 1:
        return 0
    # 邊框元件＝貼畫布四邊者。含框 → 輻條連接。
    border = np.zeros_like(mask)
    border[0, :] = border[-1, :] = True
    border[:, 0] = border[:, -1] = True
    frame_ids = {int(v) for v in np.unique(labels_f[border & mask]) if v > 0}
    if frame_ids:
        return _connect_to_frame(mask, labels_f, n_f, frame_ids, half, ties)
    added = 0
    # 5dg：記住「原生元件」名冊（連筋前）＋每件的連筋錨點。
    labels0, n0 = _label(mask)
    anchors: dict[int, list[tuple[int, int]]] = {}
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
        for pt in (best[1], best[2]):     # 錨點記到「原生元件」帳上
            pid = int(labels0[pt])
            if pid > 0:
                anchors.setdefault(pid, []).append(pt)  # type: ignore[arg-type]
    if ties >= 2 and n0 >= 2:
        added += _add_symmetric_ties(mask, labels0, n0, anchors, half)
    return added


def _add_symmetric_ties(mask: np.ndarray, labels0: np.ndarray, n0: int,
                        anchors: dict[int, list[tuple[int, int]]],
                        half: int) -> int:
    """5dg 對稱第二筋：單筋字元件在錨點的點對稱側補一筋到最近外部材料。"""
    added = 0
    border = np.zeros_like(mask)
    border[0, :] = border[-1, :] = True
    border[:, 0] = border[:, -1] = True
    # 外部材料取樣池（整張 mask，含框/既有連筋；查找時再排除自身元件）
    all_pts = np.argwhere(mask)
    step = max(1, len(all_pts) // 4000)
    pool = all_pts[::step]
    pool_ids = labels0[pool[:, 0], pool[:, 1]]
    for pid in range(1, n0 + 1):
        piece = labels0 == pid
        if (piece & border).any():        # 邊框元件不補
            continue
        got = anchors.get(pid, [])
        if len(got) >= 2:                 # 已有兩筋（如三的中橫）
            continue
        p_pts = np.argwhere(piece)
        cy, cx = p_pts.mean(axis=0)
        if got:
            ay, ax = got[0]
        else:                             # 錨點落在橋上等罕見情形：
            ext0 = pool[pool_ids != pid]  # 以最近外部點當擬錨
            if len(ext0) == 0:
                continue
            d2 = ((ext0 - [cy, cx]) ** 2).sum(axis=1)
            ay, ax = ext0[int(d2.argmin())]
        # 點對稱位置 → 元件上最接近該位置的像素
        my, mx = 2 * cy - ay, 2 * cx - ax
        d2p = ((p_pts - [my, mx]) ** 2).sum(axis=1)
        sp = tuple(p_pts[int(d2p.argmin())])
        # 最近外部材料（排除自身元件）
        ext = pool[pool_ids != pid]
        if len(ext) == 0:
            continue
        d2e = ((ext - np.asarray(sp)) ** 2).sum(axis=1)
        tp = tuple(ext[int(d2e.argmin())])
        _thick_line(mask, sp, tp, half)   # type: ignore[arg-type]
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
    style: str = DEFAULT_CUTTING_STYLE,
    envelope_depth: int = 1,
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
    cut_style = get_cutting_style(style)      # 未知風格 → KeyError（呼叫端轉 422）
    ch_px = max(8, int(round(char_height_mm * px_per_mm)))
    sp_px = max(0, int(round(spacing_mm * px_per_mm)))
    if margin_mm is None:
        margin_mm = max(5.0, char_height_mm * 0.2) if (
            kind == "stencil" or frame) else max(3.0, char_height_mm * 0.1)
    mg_px = max(2, int(round(margin_mm * px_per_mm)))
    scale = ch_px / EM_SIZE
    # 5do：依所有字形**實際墨的 y-範圍**垂直置中，而非靠字型 em 框/
    # baseline——思源黑體漢字墨常溢出 em 框下緣（實測 y 705..2574 / 2048），
    # 舊法（oy=mg_px）會讓字沉底貼下框、甚至被裁切。改成把墨的 y 跨距置於
    # 上下等距的 mg_px 邊界內，畫布高隨墨自適應。
    ink_ys = [y for polys in char_polys for p in polys for (_x, y) in p]
    if ink_ys:
        iy0, iy1 = min(ink_ys), max(ink_ys)
    else:
        iy0, iy1 = 0.0, float(EM_SIZE)
    ink_h_px = max(1, int(math.ceil((iy1 - iy0) * scale)))
    h_px = 2 * mg_px + ink_h_px
    oy = int(round(mg_px - iy0 * scale))     # 墨頂落在 mg_px（可為負，_fill 內夾邊）
    w_px = 2 * mg_px + n * ch_px + (n - 1) * sp_px

    mask = np.zeros((h_px, w_px), dtype=bool)
    for i, polys in enumerate(char_polys):
        _fill_polys(mask, polys,
                    ox=mg_px + i * (ch_px + sp_px), oy=oy, scale=scale)

    bold_px = int(round(bold_mm * px_per_mm))
    if bold_px > 0:
        mask = _dilate(mask, bold_px)

    bw_px = max(2, int(round(bridge_width_mm * px_per_mm)))
    stats: dict = {"kind": kind, "style": cut_style.key}
    # 切割策略 dispatch（切割風格 registry 的 seam）。connect_depth → max_depth：
    # full＝None（全連派、殘腔 0）；envelope＝1（只鑿最外圈、深層留島）。
    if cut_style.connect_depth not in _CONNECT_DEPTH_MAX:
        raise NotImplementedError(
            f"cutting style {cut_style.key!r} (connect_depth="
            f"{cut_style.connect_depth!r}) not implemented yet")
    base_depth = _CONNECT_DEPTH_MAX[cut_style.connect_depth]
    # 5ej：envelope 連筋深度可調——深度限制風格（envelope，base 非 None）時
    # 用 envelope_depth 覆蓋預設 1（連到第幾層；越大連越深、留越少島，調到該
    # 字最大深度＝等同全連）；physical（base=None、全連）不受 envelope_depth
    # 影響。預設 envelope_depth=1＝原 envelope 行為（逐位元不變）。
    max_depth = (max(1, int(envelope_depth))
                 if base_depth is not None else None)
    stats["max_depth"] = max_depth if max_depth is not None else 0
    if kind == "stencil":
        stats["holes_bridged"] = carve_stencil_bridges(
            mask, bw_px, bridge_count, max_depth=max_depth,
            keep_primary=cut_style.keep_primary)
    else:
        # cutout（字即本體、連筋掛框）：envelope 的「深層留島」對 cutout 會讓
        # 字件掉光＝壞字，故 cutout 恆走全連（忽略 connect_depth 的深度限制）。
        _labels, before = _label(mask)
        stats["components_before"] = before
        if frame:
            add_frame(mask, max(1, int(round(frame_width_mm * px_per_mm))))
        stats["bridges_added"] = connect_cutout_components(mask, bw_px)

    loops_px = _trace_boundary_loops(mask)
    min_area = (bw_px * bw_px) / 4.0          # 去斑：小於 1/4 橋寬平方
    # 5do：容差隨解析度縮放（維持 ~0.25mm 的實體去微段效果）。
    eps = _STENCIL_RDP_EPS * (px_per_mm / PX_PER_MM)
    loops_mm: list[list[tuple[float, float]]] = []
    for loop in loops_px:
        area = 0.0
        for i in range(len(loop)):
            x1, y1 = loop[i]
            x2, y2 = loop[(i + 1) % len(loop)]
            area += x1 * y2 - x2 * y1
        if abs(area) / 2.0 < min_area:
            continue
        simp = _simplify_loop(loop, eps=eps)
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
