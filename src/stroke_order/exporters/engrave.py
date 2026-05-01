"""Phase 12c-3: 陽刻光柵掃描演算法（convex engraving raster scan）.

陰刻（concave，現況）vs 陽刻（convex，本 module）：
- **陰刻**：字凹下，雷射沿字筆劃路徑走，背景留白。stroke-only，G-code
  路徑就是字 outline 本身。
- **陽刻**：字凸出，雷射光柵掃描鋪滿背景，字筆劃內部不雕。需要 raster
  化算法把「印章邊框內 - 字 outline」轉成水平掃描線清單。

演算法：scanline filling + even-odd rule + boustrophedon
   1. 每隔 line_pitch 一條水平線 y = const
   2. 對每條線，求所有字 outline polygon 的交點
   3. 套 even-odd rule：交點之間奇數段在「字內」，偶數段在「字外」
   4. 雷射 ON 區段 = 字外（背景） = [border_left, x1] ∪ [x2, x3] ∪ ...
   5. Boustrophedon 之字形：奇數行 L→R、偶數行 R→L 減少空跑時間

效能（驗證自 prototype）：
- 4 分章 1 字: 6 ms compute, 800 行 G-code, 38 秒雷射
- 1 寸大公司章 4 字: 84 ms compute, 5K 行 G-code, 4.5 分鐘雷射

prototype: scripts/prototype_engrave_convex.py
"""
from __future__ import annotations


def scanline_intersections(
    polygons: list[list[tuple[float, float]]],
    y: float,
) -> list[float]:
    """求水平線 y 跟所有 polygon 邊的交點 x 座標清單.

    用半開區間 (y0 <= y < y1) 避免頂點 double-count（degenerate cases
    可能 1px 鋸齒，但 0.1mm line_pitch 下肉眼看不出）。
    """
    xs = []
    for poly in polygons:
        for i in range(len(poly) - 1):
            x0, y0 = poly[i]
            x1, y1 = poly[i + 1]
            # 跳過水平邊
            if y0 == y1:
                continue
            # 排序使 y0 < y1
            if y0 > y1:
                x0, y0, x1, y1 = x1, y1, x0, y0
            # 半開區間判斷
            if y0 <= y < y1:
                t = (y - y0) / (y1 - y0)
                x = x0 + t * (x1 - x0)
                xs.append(x)
    xs.sort()
    return xs


def scanline_engrave_gcode(
    polygons: list[list[tuple[float, float]]],
    *,
    border_left: float, border_right: float,
    border_top: float, border_bottom: float,
    line_pitch: float = 0.1,
    feed: float = 1500.0,
    laser_power: int = 255,
    laser_on: str = "M3",
    laser_off: str = "M5",
    boustrophedon: bool = True,
) -> tuple[list[str], dict]:
    """生成陽刻光柵掃描 G-code.

    Args:
        polygons: 字 outline polygons (mm space, 已經 closed 首尾相同)
        border_left/right/top/bottom: 邊框矩形（雷射只在框內掃描）
        line_pitch: 掃描線間距 (mm)，越小越細緻
        feed: 雷射切割速度 (mm/min)
        laser_power: S 值 (0-1000，依雷射機規格)
        boustrophedon: 之字形掃描（奇偶行反向）

    Returns:
        (gcode_lines, stats) — gcode_lines 是字串清單（不含換行），
        stats 含 scan_lines / on_segments / total_cut_mm / estimated_min。
    """
    lines = [
        "; --- engrave: convex (陽刻 / 朱文) raster scan ---",
        f"; Stamp area: ({border_left:.2f}, {border_top:.2f}) - "
        f"({border_right:.2f}, {border_bottom:.2f}) mm",
        f"; Line pitch: {line_pitch} mm   Feed: {feed} mm/min",
        "G21 ; mm units",
        "G90 ; absolute positioning",
        f"{laser_off} ; laser off (initial)",
    ]

    n_lines = 0
    n_segments = 0
    total_cut_mm = 0.0
    direction_l_to_r = True

    y = border_top
    while y <= border_bottom:
        xs = scanline_intersections(polygons, y)
        # Even-odd rule：在 [border_left, border_right] 內，
        # boundary 序列分區 ON/OFF 交替（從外圍 ON 開始）
        in_range = [x for x in xs if border_left < x < border_right]
        boundary = [border_left] + in_range + [border_right]
        # 區段索引偶數 (0, 2, 4...) = ON（背景），奇數 = OFF（字內）
        on_segments = []
        for i in range(len(boundary) - 1):
            if i % 2 == 0:  # ON
                seg_l, seg_r = boundary[i], boundary[i + 1]
                if seg_r > seg_l:  # 跳過零長度（可能來自浮點誤差）
                    on_segments.append((seg_l, seg_r))

        if not on_segments:
            y += line_pitch
            continue

        # Boustrophedon: 奇偶行反向減少空跑
        if boustrophedon and not direction_l_to_r:
            on_segments = [(b, a) for (a, b) in reversed(on_segments)]

        for x_start, x_end in on_segments:
            lines.append(f"G0 X{x_start:.3f} Y{y:.3f}")
            lines.append(f"{laser_on} S{laser_power}")
            lines.append(f"G1 X{x_end:.3f} F{feed:.0f}")
            lines.append(laser_off)
            n_segments += 1
            total_cut_mm += abs(x_end - x_start)
        n_lines += 1
        if boustrophedon:
            direction_l_to_r = not direction_l_to_r
        y += line_pitch

    lines.append(f"{laser_off} ; final laser off")

    stats = {
        "scan_lines": n_lines,
        "on_segments": n_segments,
        "gcode_lines": len(lines),
        "total_cut_mm": total_cut_mm,
        "estimated_min": total_cut_mm / feed if feed > 0 else 0.0,
    }
    return lines, stats


def char_outlines_to_polygons(
    char,
    *,
    samples_per_curve: int = 8,
) -> list[list[tuple[float, float]]]:
    """把 Character 的所有 stroke outline 轉成 polygon list (in EM space).

    跟 patch._outline_to_polyline 同核心，但回傳所有 strokes 一次處理。
    Stroke outline 命令型態（M/L/Q/C）已經 sampled 成多邊形。
    """
    from .patch import _outline_to_polyline  # 重用，避免複製演算法
    polygons = []
    for stroke in char.strokes:
        if not stroke.outline:
            continue
        pts = _outline_to_polyline(stroke, samples_per_curve=samples_per_curve)
        if pts and len(pts) >= 3:
            # 確保 polygon 封閉（首尾相同點，scanline algorithm 假設封閉）
            if pts[0] != pts[-1]:
                pts.append(pts[0])
            polygons.append(pts)
    return polygons


def transform_polygons_em_to_mm(
    polygons: list[list[tuple[float, float]]],
    *,
    cx_mm: float, cy_mm: float,
    w_mm: float, h_mm: float,
    rotation_deg: float = 0.0,
) -> list[list[tuple[float, float]]]:
    """把 EM-space polygons 轉到 mm-space.

    跟 patch._char_cut_paths_stretched 同樣 bbox-based scale + center alignment
    （11g + 11f）。w_mm / h_mm 可不同（非均勻拉長 like 3 字 1+2 layout 右大姓）。
    """
    import math
    if not polygons:
        return []

    # 求所有 polygons 合 bbox
    all_pts = [p for poly in polygons for p in poly]
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    bbox_w = max(max_x - min_x, 1.0)  # 防 div by zero
    bbox_h = max(max_y - min_y, 1.0)
    bbox_cx = (min_x + max_x) / 2
    bbox_cy = (min_y + max_y) / 2

    scale_x = w_mm / bbox_w
    scale_y = h_mm / bbox_h

    cos_r = math.cos(math.radians(rotation_deg))
    sin_r = math.sin(math.radians(rotation_deg))

    out = []
    for poly in polygons:
        mm_poly = []
        for (px, py) in poly:
            # bbox-center alignment
            x = (px - bbox_cx) * scale_x
            y = (py - bbox_cy) * scale_y
            # rotate
            rx = x * cos_r - y * sin_r
            ry = x * sin_r + y * cos_r
            # translate
            mm_poly.append((rx + cx_mm, ry + cy_mm))
        out.append(mm_poly)
    return out
