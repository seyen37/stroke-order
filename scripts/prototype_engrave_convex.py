"""Phase 12c-3 prototype: G-code 陽刻光柵掃描演算法驗證.

陰刻 vs 陽刻：
- 陰刻（現況）：字凹下，雷射沿字筆劃路徑走，背景留白
- 陽刻（新增）：字凸出，雷射光柵掃描鋪滿背景，字筆劃內部不雕

本 prototype 驗證 G-code 陽刻光柵掃描可行性 — 用「王」字當測試案例，
12mm × 12mm 章面，line_pitch 0.1mm。

演算法：scanline filling + even-odd rule
   1. 每隔 line_pitch 一條水平線 y = const
   2. 對每條線，求所有字 outline polygon 的交點
   3. 套 even-odd rule：交點之間奇數段在「字內」，偶數段在「字外」
   4. 雷射 ON 區段 = 字外（背景） = [border_left, x1] ∪ [x2, x3] ∪ ...

跑法：
    python scripts/prototype_engrave_convex.py

輸出：
    /tmp/prototype_engrave_convex.gcode  — 生成的 G-code
    /tmp/prototype_engrave_convex.svg    — 視覺預覽（綠色 = ON 區段）
    stdout                                — 統計與分析

用途：在 main 動 12c-3 之前驗證演算法不會 crash + G-code 規模合理。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# 為了能在 sandbox 直接 python 執行（而不是當 module）
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from stroke_order.exporters.patch import _outline_to_polyline
from stroke_order.web.server import _load


# =====================================================================
# Config
# =====================================================================
TEST_CHAR = "王"          # 簡單字體 outline，演算法驗證足夠
STAMP_W_MM = 12.0         # 4 分章
STAMP_H_MM = 12.0
BORDER_PADDING = 0.8      # 邊框內縮（與 stamp.py 12b-6 一致）
LINE_PITCH = 0.1          # 光柵掃描密度，0.1 mm = 250 dpi-ish
LASER_FEED = 1500         # mm/min
LASER_POWER = 255

EM_SIZE = 2048


# =====================================================================
# Step 1: 載入字 outline
# =====================================================================
def load_char_polygons(char_str: str) -> list[list[tuple[float, float]]]:
    """載入字並把 outline 轉成 polygons (in EM coords)."""
    char, _, _ = _load(char_str, source="auto", hook_policy="animation")
    polygons = []
    for stroke in char.strokes:
        if not stroke.outline:
            continue
        pts = _outline_to_polyline(stroke, samples_per_curve=8)
        if pts and len(pts) >= 3:
            # 確保 polygon 封閉（首尾相同）
            if pts[0] != pts[-1]:
                pts.append(pts[0])
            polygons.append(pts)
    return polygons


def em_to_mm(polygons: list, cx_mm: float, cy_mm: float, fit_mm: float
            ) -> list[list[tuple[float, float]]]:
    """把 EM-space polygons scale + offset 到 mm-space.

    取所有 polygons 的合 bbox，按 fit_mm 等比縮放並置中。
    """
    all_pts = [p for poly in polygons for p in poly]
    if not all_pts:
        return []
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    bbox_w = max_x - min_x
    bbox_h = max_y - min_y
    scale = fit_mm / max(bbox_w, bbox_h)
    bbox_cx = (min_x + max_x) / 2
    bbox_cy = (min_y + max_y) / 2
    out = []
    for poly in polygons:
        mm_poly = [
            ((px - bbox_cx) * scale + cx_mm,
             (py - bbox_cy) * scale + cy_mm)
            for (px, py) in poly
        ]
        out.append(mm_poly)
    return out


# =====================================================================
# Step 2: Scanline intersection
# =====================================================================
def scanline_intersections(
    polygons: list[list[tuple[float, float]]],
    y: float,
) -> list[float]:
    """求水平線 y 跟所有 polygon 邊的交點 x 座標清單.

    用半開區間 (y0 <= y < y1) 避免頂點 double-count。
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


# =====================================================================
# Step 3: G-code 生成
# =====================================================================
def gen_gcode_convex(
    polygons: list[list[tuple[float, float]]],
    *,
    border_left: float, border_right: float,
    border_top: float, border_bottom: float,
    line_pitch: float = LINE_PITCH,
    feed: int = LASER_FEED,
    power: int = LASER_POWER,
) -> tuple[list[str], dict]:
    """生成陽刻光柵掃描 G-code.

    回傳 (gcode_lines, stats)。
    """
    lines = [
        "; Phase 12c-3 prototype: 陽刻光柵掃描",
        f"; Stamp: {border_right - border_left:.1f} x {border_bottom - border_top:.1f} mm",
        f"; Line pitch: {line_pitch} mm  Feed: {feed} mm/min",
        "G21 ; mm units",
        "G90 ; absolute positioning",
        "M5  ; laser off",
        f"G0 F{feed * 5} ; rapid travel feed",
        f"G1 F{feed} ; cut feed",
    ]

    n_lines = 0
    n_segments = 0
    total_cut_mm = 0.0
    boustrophedon = True  # 之字形掃描減少空跑時間
    direction_left_to_right = True

    y = border_top
    while y <= border_bottom:
        xs = scanline_intersections(polygons, y)
        # even-odd: ON segments are between (border_left, x[0]),
        # (x[1], x[2]), ..., (x[-1], border_right)
        # If xs has even count (應該是), 區段對是 ON 跟 OFF 交替
        # 整條線分段：[border_left, x0, x1, ..., x_n-1, border_right]
        boundary = [border_left] + [x for x in xs
                                    if border_left < x < border_right] + [border_right]
        # 如果 xs 全部 < border_left 或 > border_right，整條 ON
        # 區段索引偶數 (0, 2, 4...) = ON（背景），奇數 = OFF（字內）
        on_segments = []
        for i in range(len(boundary) - 1):
            if i % 2 == 0:  # ON
                on_segments.append((boundary[i], boundary[i + 1]))

        if not on_segments:
            y += line_pitch
            continue

        # Boustrophedon: 反向交替
        if boustrophedon and not direction_left_to_right:
            on_segments = [(b, a) for (a, b) in reversed(on_segments)]

        for x_start, x_end in on_segments:
            lines.append(f"G0 X{x_start:.3f} Y{y:.3f}")
            lines.append(f"M3 S{power}")
            lines.append(f"G1 X{x_end:.3f}")
            lines.append("M5")
            n_segments += 1
            total_cut_mm += abs(x_end - x_start)
        n_lines += 1
        if boustrophedon:
            direction_left_to_right = not direction_left_to_right
        y += line_pitch

    lines.append("M5 ; final laser off")
    lines.append("G0 X0 Y0")

    stats = {
        "scan_lines": n_lines,
        "on_segments": n_segments,
        "gcode_lines": len(lines),
        "total_cut_mm": total_cut_mm,
        "estimated_min": total_cut_mm / feed,  # ~time at feed speed
    }
    return lines, stats


# =====================================================================
# Step 4: 視覺化（簡單 SVG，綠色 = 雷射 ON 區段）
# =====================================================================
def gen_preview_svg(
    polygons: list[list[tuple[float, float]]],
    gcode_lines: list[str],
    *,
    border_left: float, border_right: float,
    border_top: float, border_bottom: float,
) -> str:
    """生成預覽 SVG：綠色=雷射 ON、紅色字 outline、黑邊框."""
    w = border_right - border_left + 4
    h = border_bottom - border_top + 4
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -2 {w} {h}" '
        f'width="{w*30}" height="{h*30}">',
        # White background
        f'<rect x="-2" y="-2" width="{w}" height="{h}" fill="#fefefe"/>',
        # Border (rectangle, double-line for stamp look)
        f'<rect x="{border_left}" y="{border_top}" '
        f'width="{border_right-border_left}" height="{border_bottom-border_top}" '
        f'fill="none" stroke="#000" stroke-width="0.15"/>',
    ]
    # ON segments (從 G-code 解析簡化版)
    current_y = None
    laser_on_segments = []
    laser_on = False
    last_pos = (0, 0)
    for ln in gcode_lines:
        if ln.startswith("G0 X"):
            parts = ln.split()
            x = float(parts[1][1:])
            y = float(parts[2][1:]) if len(parts) > 2 and parts[2].startswith("Y") else last_pos[1]
            last_pos = (x, y)
        elif ln.startswith("M3"):
            laser_on = True
        elif ln.startswith("M5"):
            laser_on = False
        elif ln.startswith("G1 X") and laser_on:
            x_end = float(ln.split()[1][1:])
            laser_on_segments.append((last_pos[0], last_pos[1], x_end, last_pos[1]))
            last_pos = (x_end, last_pos[1])

    # 畫 ON segments（淺綠色細線）
    for (x0, y0, x1, y1) in laser_on_segments:
        svg.append(
            f'<line x1="{x0:.3f}" y1="{y0:.3f}" x2="{x1:.3f}" y2="{y1:.3f}" '
            f'stroke="#0a0" stroke-width="0.05" opacity="0.6"/>'
        )

    # 字 outline (紅色細線疊上去)
    for poly in polygons:
        d = "M" + " L".join(f"{px:.3f},{py:.3f}" for (px, py) in poly) + " Z"
        svg.append(f'<path d="{d}" fill="none" stroke="#c33" stroke-width="0.08"/>')

    svg.append("</svg>")
    return "\n".join(svg)


# =====================================================================
# Main
# =====================================================================
def main():
    print(f"=== Phase 12c-3 prototype: 陽刻光柵掃描 ===")
    print(f"Test char: {TEST_CHAR!r}")
    print(f"Stamp: {STAMP_W_MM}x{STAMP_H_MM} mm, padding {BORDER_PADDING} mm")
    print(f"Line pitch: {LINE_PITCH} mm")
    print()

    # Load char
    t0 = time.time()
    em_polygons = load_char_polygons(TEST_CHAR)
    t1 = time.time()
    print(f"Loaded {len(em_polygons)} polygons (EM space) in {(t1-t0)*1000:.1f} ms")
    total_em_pts = sum(len(p) for p in em_polygons)
    print(f"  Total polygon points: {total_em_pts}")

    # Scale to mm space — 字佔內框 (12 - 2*0.8 = 10.4mm 區域 — 跟 stamp.py 一致)
    inner_w = STAMP_W_MM - 2 * BORDER_PADDING
    inner_h = STAMP_H_MM - 2 * BORDER_PADDING
    fit_mm = min(inner_w, inner_h) * 0.92  # 留 8% padding，跟 12b-7 一致
    cx_mm = STAMP_W_MM / 2
    cy_mm = STAMP_H_MM / 2

    mm_polygons = em_to_mm(em_polygons, cx_mm, cy_mm, fit_mm)
    print(f"Scaled to mm: char fits ~{fit_mm:.2f} mm, centered at ({cx_mm}, {cy_mm})")

    # Generate G-code
    border_left = BORDER_PADDING
    border_right = STAMP_W_MM - BORDER_PADDING
    border_top = BORDER_PADDING
    border_bottom = STAMP_H_MM - BORDER_PADDING

    t0 = time.time()
    gcode_lines, stats = gen_gcode_convex(
        mm_polygons,
        border_left=border_left, border_right=border_right,
        border_top=border_top, border_bottom=border_bottom,
    )
    t1 = time.time()
    print(f"\nG-code generated in {(t1-t0)*1000:.1f} ms")
    print(f"  Scan lines: {stats['scan_lines']}")
    print(f"  ON segments: {stats['on_segments']}")
    print(f"  G-code lines: {stats['gcode_lines']}")
    print(f"  Total cut distance: {stats['total_cut_mm']:.1f} mm")
    print(f"  Estimated time @ {LASER_FEED} mm/min: {stats['estimated_min']:.2f} min")

    # Save outputs
    gcode_str = "\n".join(gcode_lines)
    Path("/tmp/prototype_engrave_convex.gcode").write_text(gcode_str)
    print(f"\nG-code saved to /tmp/prototype_engrave_convex.gcode "
          f"({len(gcode_str)} bytes)")

    svg_str = gen_preview_svg(
        mm_polygons, gcode_lines,
        border_left=border_left, border_right=border_right,
        border_top=border_top, border_bottom=border_bottom,
    )
    Path("/tmp/prototype_engrave_convex.svg").write_text(svg_str)
    print(f"SVG preview saved to /tmp/prototype_engrave_convex.svg "
          f"({len(svg_str)} bytes)")

    # Sanity 檢查
    print("\n=== Sanity ===")
    if stats['scan_lines'] > 1000:
        print(f"  WARN: scan lines {stats['scan_lines']} 偏多，line_pitch 可能太細")
    if stats['gcode_lines'] > 100000:
        print(f"  WARN: gcode lines {stats['gcode_lines']} > 100K，雷射機可能無法吃")
    if stats['on_segments'] == 0:
        print(f"  ERROR: 沒有 ON segments — 演算法 bug 或字 outline 失效")
        return 1
    print("  All sanity checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
