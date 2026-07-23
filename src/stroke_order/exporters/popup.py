"""立體鏤空字卡片（pop-up standing hollow text）幾何產生器。

機構（經實體驗證）：箱型 pop-up。前立面＝鏤空文字（字即實體、周圍透空），
文字頂＝摺線接頂面 roof、文字底＝摺線接底座、中線谷折穿字中對稱好折合。
雙層＝兩箱疊成階梯，中線穿中間 tread 正中、上下兩排等高對稱（|a-d|=|b-c|）。

- 鏤空字用 noto_hei（思源黑體），多輪廓 even-odd。
- 連筋：每散件連到 roof（經字頂）或底座（經字底）；浮件補最短縱橋；
  整卡剪裁後單一連通（元件數=1）才保證剪下不散。
- 輸出向量 SVG：CUT（黑實）／MOUNTAIN（紅虛山折）／VALLEY（藍虛谷折）／
  SPINE（綠中線谷折）分層，供列印剪折與雷切。

座標：mm。卡片 A4（210×297 可調），對折成 A5。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..sources.noto_hei import get_hei_source
from ..sources.cns_font import _outline_to_polylines
from .engrave import scanline_intersections
from .stencil import _thick_line
from .doodle import _trace_boundary_loops, _simplify_loop

PX_PER_MM = 8
_RDP_EPS = 2.0


def _label_runs(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """4-連通元件標記（run-based union-find，純 numpy）。

    以每列的「連續 True 段（run）」為單位做 union-find，而非逐像素 BFS——
    段數遠少於像素數，故大 mask（A4×8px/mm）亦秒級。回傳 (labels, count)，
    labels 為 1..count 的密集標籤（0＝背景）。
    """
    h, w = mask.shape
    labels = np.zeros((h, w), np.int32)
    parent = [0]

    def find(a):
        r = a
        while parent[r] != r:
            r = parent[r]
        while parent[a] != r:
            parent[a], a = r, parent[a]
        return r

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    prev = []          # 前一列 runs: (x0, x1, label)
    nextlab = 1
    for y in range(h):
        row = mask[y]
        d = np.diff(row.view(np.int8))
        starts = (np.where(d == 1)[0] + 1).tolist()
        ends = (np.where(d == -1)[0] + 1).tolist()
        if row[0]:
            starts.insert(0, 0)
        if row[-1]:
            ends.append(w)
        cur = []
        j0 = 0
        for x0, x1 in zip(starts, ends):
            lbl = 0
            for k in range(j0, len(prev)):
                px0, px1, plbl = prev[k]
                if px1 <= x0:
                    j0 = k + 1
                    continue
                if px0 >= x1:
                    break
                if lbl == 0:
                    lbl = plbl
                else:
                    union(lbl, plbl)
            if lbl == 0:
                lbl = nextlab
                parent.append(nextlab)
                nextlab += 1
            labels[y, x0:x1] = lbl
            cur.append((x0, x1, lbl))
        prev = cur
    if nextlab == 1:
        return labels, 0
    # 攤平等價類 → 密集標籤
    roots = np.array([find(i) for i in range(nextlab)], np.int32)
    uniq, dense = np.unique(roots[1:], return_inverse=True)
    remap = np.zeros(nextlab, np.int32)
    remap[1:] = dense + 1
    nz = labels > 0
    labels[nz] = remap[labels[nz]]
    return labels, int(len(uniq))


def _label(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """4-連通元件標記。優先用 scipy（C 實作最快），無則 run-based numpy。"""
    try:
        from scipy.ndimage import label as _sci
        lab, n = _sci(mask)
        return lab, int(n)
    except Exception:  # pragma: no cover - fallback
        return _label_runs(mask)


@dataclass
class PopupParams:
    card_w_mm: float = 210.0
    card_h_mm: float = 340.0
    char_h_mm: float = 44.0        # 每排字高
    roof_mm: float = 30.0          # 頂面 roof 深度
    tread_mm: float = 30.0         # 雙層中間 tread 深度（＝下排頂面）
    cell_w_mm: float = 46.0        # 每字格寬
    gap_mm: float = 6.0            # 字距
    bridge_mm: float = 1.6         # 連筋寬
    px_per_mm: int = PX_PER_MM


@dataclass
class PopupResult:
    svg: str
    width_mm: float
    height_mm: float
    bridges: int
    components: int
    tiers: int


def _fill_row(card, text, ytop, ybot, P):
    """把一排鏤空字填進 card（先清空該帶再填字墨）。回傳 (Lx, Rx) 前立面左右界(px)。"""
    CW = card.shape[1]
    src = get_hei_source()
    n = len(text)
    cw = int(round(P.cell_w_mm * P.px_per_mm))
    gap = int(round(P.gap_mm * P.px_per_mm))
    x0 = (CW - (n * cw + (n - 1) * gap)) // 2
    Lx, Rx = x0, x0 + n * cw + (n - 1) * gap
    card[ytop:ybot, Lx:Rx] = False
    for i, ch in enumerate(text):
        cont = _outline_to_polylines(
            src.get_character(ch).strokes[0].outline, samples_per_curve=10)
        xs = [p[0] for pl in cont for p in pl]
        ys = [p[1] for pl in cont for p in pl]
        mnx, mxx, mny, mxy = min(xs), max(xs), min(ys), max(ys)
        cx = x0 + cw // 2 + i * (cw + gap)
        sx = (cw - 6 * P.px_per_mm) / (mxx - mnx)
        sy = (ybot - ytop) / (mxy - mny)
        closed = [[(cx + (px - (mnx + mxx) / 2) * sx, ytop + (py - mny) * sy)
                   for px, py in pl] for pl in cont]
        y0 = int(min(p[1] for pl in closed for p in pl))
        y1 = int(max(p[1] for pl in closed for p in pl))
        for py in range(max(0, y0), min(card.shape[0], y1) + 1):
            ix = scanline_intersections([pl + [pl[0]] for pl in closed], py)
            for k in range(0, len(ix) - 1, 2):
                a, b = int(round(ix[k])), int(round(ix[k + 1]))
                if b >= a:
                    card[py, max(0, a):min(CW, b + 1)] = True
    return Lx, Rx


def _connect(card, bridge_px):
    """連筋：浮件補最短縱橋到主體（卡身）。回傳補橋數。

    批次法：每輪只標記一次，把當輪**所有**非主體件各補一道縱橋到主體，
    再重標確認。把標記次數從 O(浮件數) 降到 O(輪數≈2-3)——scipy 路徑更快、
    numpy 後備也可行。
    """
    half = max(1, bridge_px // 2)
    added = 0
    for _ in range(6):
        lab, n = _label(card)
        if n <= 1:
            break
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        main = int(sizes.argmax())
        progressed = False
        for c in range(1, n + 1):
            if c == main or sizes[c] == 0:
                continue
            ys, xs = np.where(lab == c)
            for anc in ("t", "b"):
                if anc == "t":
                    x = int(xs[np.argmin(ys)]); y0 = int(ys.min())
                    col = lab[:y0, x]; hit = np.where(col == main)[0]
                else:
                    x = int(xs[np.argmax(ys)]); y0 = int(ys.max())
                    col = lab[y0 + 1:, x]; hit = np.where(col == main)[0]
                if len(hit):
                    y1 = int(hit.max()) if anc == "t" else y0 + 1 + int(hit.min())
                    _thick_line(card, (y0, x), (y1, x), half)
                    added += 1
                    progressed = True
                    break
        if not progressed:
            break
    return added


def build_popup(upper: str, lower: str = "", params: Optional[PopupParams] = None):
    """組裝整卡 mask＋折線幾何。lower 為空＝單層；否則雙層。

    回傳 (card_mask, folds, meta)。folds: list of (kind, y_mm, x0_mm, x1_mm)
    kind ∈ {"valley","mountain","spine"}；SPINE 為中線（全卡寬）。
    """
    P = params or PopupParams()
    pm = P.px_per_mm
    CW = int(round(P.card_w_mm * pm))
    CH = int(round(P.card_h_mm * pm))
    C = CH // 2
    h = int(round(P.char_h_mm * pm))
    D = int(round(P.roof_mm * pm))
    card = np.ones((CH, CW), bool)
    folds = []  # (kind, y_px, x0_px, x1_px)
    two = bool(lower.strip())

    if not two:
        # 單層：文字跨中線 [C-h/2, C+h/2]
        yTop, yBot = C - h // 2, C + h // 2
        yRoofTop = yTop - D
        L, R = _fill_row(card, upper, yTop, yBot, P)
        card[yRoofTop + 1:yBot, L - 1:L + 1] = False
        card[yRoofTop + 1:yBot, R - 1:R + 1] = False
        folds.append(("valley", yRoofTop, L, R))   # roof↔背板
        folds.append(("mountain", yTop, L, R))     # 字頂↔roof
        folds.append(("valley_seg", yBot, L, R))   # 字底↔底座(分段)
        folds.append(("spine", C, 0, CW))          # 中線穿字中
        side = (yRoofTop, yBot)
        tiers = 1
    else:
        # 雙層：中線穿中間 tread 正中，上下兩排等高對稱
        T = int(round(P.tread_mm * pm))
        yT_top, yT_bot = C - T // 2, C + T // 2
        yUp_bot, yUp_top = yT_top, yT_top - h
        yLo_top, yLo_bot = yT_bot, yT_bot + h
        yRoofTop = yUp_top - D
        Lu, Ru = _fill_row(card, upper, yUp_top, yUp_bot, P)
        Ll, Rl = _fill_row(card, lower, yLo_top, yLo_bot, P)
        L, R = min(Lu, Ll), max(Ru, Rl)
        card[yRoofTop + 1:yLo_bot, L - 1:L + 1] = False
        card[yRoofTop + 1:yLo_bot, R - 1:R + 1] = False
        folds.append(("valley", yRoofTop, L, R))    # roof↔背板
        folds.append(("mountain", yUp_top, L, R))   # 上排頂↔roof
        folds.append(("valley", yUp_bot, L, R))     # 上排底↔tread
        folds.append(("spine", C, 0, CW))           # 中線穿tread正中
        folds.append(("mountain", yLo_top, L, R))   # tread↔下排頂
        folds.append(("valley_seg", yLo_bot, L, R)) # 下排底↔底座(分段)
        side = (yRoofTop, yLo_bot)
        tiers = 2

    bridges = _connect(card, int(round(P.bridge_mm * pm)))
    _, ncomp = _label(card)
    meta = dict(CW=CW, CH=CH, C=C, L=L, R=R, side=side,
                bridges=bridges, ncomp=int(ncomp), tiers=tiers, pm=pm)
    return card, folds, meta


def _seg_runs(row, min_px):
    xs = np.where(row)[0]
    if not len(xs):
        return []
    a = p = xs[0]
    runs = []
    for x in xs[1:]:
        if x - p > 2:
            runs.append((a, p)); a = x
        p = x
    runs.append((a, p))
    return [(int(ra), int(rb)) for ra, rb in runs if rb - ra >= min_px]


def popup_to_svg(card, folds, meta) -> str:
    """整卡 mask＋折線 → 向量 SVG（CUT/MOUNTAIN/VALLEY/SPINE 分層）。"""
    pm = meta["pm"]
    CW, CH = meta["CW"], meta["CH"]
    Wmm, Hmm = CW / pm, CH / pm
    L, R = meta["L"], meta["R"]
    y0s, y1s = meta["side"]
    # 前立面材料(字帶+roof/tread)描邊 → 切割閉環
    loops_px = _trace_boundary_loops(card)
    cut_paths = []
    for lp in loops_px:
        s = _simplify_loop(lp, eps=_RDP_EPS)
        if len(s) >= 3:
            cut_paths.append("M " + " L ".join(
                f"{x/pm:.2f},{y/pm:.2f}" for x, y in s) + " Z")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{Wmm:.1f}mm" '
        f'height="{Hmm:.1f}mm" viewBox="0 0 {Wmm:.2f} {Hmm:.2f}">',
        f'<rect width="{Wmm:.2f}" height="{Hmm:.2f}" fill="#fff"/>',
    ]
    # CUT 層（黑實）
    parts.append('<g stroke="#000" stroke-width="0.3" fill="none">')
    for d in cut_paths:
        parts.append(f'<path d="{d}"/>')
    # 前立面左右切割
    parts.append(f'<line x1="{L/pm:.2f}" y1="{y0s/pm:.2f}" x2="{L/pm:.2f}" y2="{y1s/pm:.2f}"/>')
    parts.append(f'<line x1="{R/pm:.2f}" y1="{y0s/pm:.2f}" x2="{R/pm:.2f}" y2="{y1s/pm:.2f}"/>')
    parts.append('</g>')

    def fold_line(y, x0, x1, color, dash):
        return (f'<line x1="{x0/pm:.2f}" y1="{y/pm:.2f}" x2="{x1/pm:.2f}" '
                f'y2="{y/pm:.2f}" stroke="{color}" stroke-width="0.4" '
                f'stroke-dasharray="{dash}"/>')

    for kind, y, x0, x1 in folds:
        if kind == "mountain":
            parts.append(fold_line(y, x0, x1, "#c62828", "3 2"))
        elif kind == "valley":
            parts.append(fold_line(y, x0, x1, "#1565c0", "4 2"))
        elif kind == "spine":
            parts.append(fold_line(y, x0, x1, "#149046", "6 2"))
        elif kind == "valley_seg":
            for ra, rb in _seg_runs(card[y - 2, :], int(2 * pm)):
                parts.append(fold_line(y, ra, rb, "#1565c0", "3 2"))
    parts.append('</svg>')
    return "\n".join(parts)


def generate_popup(upper: str, lower: str = "",
                   params: Optional[PopupParams] = None) -> PopupResult:
    if not upper.strip():
        raise ValueError("上排文字不可為空")
    card, folds, meta = build_popup(upper, lower, params)
    svg = popup_to_svg(card, folds, meta)
    return PopupResult(svg=svg, width_mm=meta["CW"] / meta["pm"],
                       height_mm=meta["CH"] / meta["pm"], bridges=meta["bridges"],
                       components=meta["ncomp"], tiers=meta["tiers"])


__all__ = ["PopupParams", "PopupResult", "generate_popup", "build_popup",
           "popup_to_svg"]
