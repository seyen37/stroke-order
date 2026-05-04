"""曼陀羅模式 (Mandala mode) — Phase 5b r4 first cut.

Layout (Case B): 中心 1 字 + 環繞 N 字 + 外圍半圓交織 (interlocking arcs)
mandala band。N 預設 = 環繞字數（九字真言 → N=9）。

Geometry (size_mm = total mandala diameter, R = size_mm / 2):
    L0 中心字           : (cx, cy), size = char_size_center_mm
    L1 字環 N 字        : 半徑 r_ring = R × r_ring_ratio,
                          字朝向依 orientation 參數（預設「字底朝內」印章風）
    L2 半圓交織 mandala : N 個圓中心位於半徑 r_band = R × r_band_ratio,
                          每圓半徑 r_petal = r_band × sin(π/N) × overlap_ratio
                          overlap_ratio > 1 → 相鄰圓 overlap，rosette 花瓣感

Independent toggles: show_chars / show_mandala — 可分別開關 L0+L1（文字）跟 L2
（裝飾），對應 user 三個 case 的開合需求。
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from ..ir import Character
from .wordart import Orientation, _place_char_svg, _rotation_for

CharLoader = Callable[[str], Optional[Character]]


def interlocking_arcs_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    overlap_ratio: float = 1.25,
    r_petal: Optional[float] = None,
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """半圓交織環：N 個圓繞中心 (cx, cy) 半徑 r_band 等分排列。

    每圓半徑：

    - ``r_petal`` 顯式指定 → 用此值（5b r8 inscribed mode 用：圓 = char bbox 包圍）
    - 否則 ``r_petal = r_band × sin(π/n) × overlap_ratio``：

      - ``overlap_ratio = 1.0`` → 相鄰圓恰相切
      - ``overlap_ratio > 1.0`` → 相鄰圓 overlap 形成 rosette
        （建議 1.2-1.5；> 1.5 後花瓣過深、視覺亂）

    ``rotation_offset_deg = -90`` → 第 0 個圓位於 12 o'clock（畫面正上方）。
    """
    if n < 2 or r_band <= 0:
        return ""
    if r_petal is None:
        r_petal = r_band * math.sin(math.pi / n) * overlap_ratio
    parts: list[str] = []
    for i in range(n):
        theta = math.radians(rotation_offset_deg + 360.0 * i / n)
        x = cx + r_band * math.cos(theta)
        y = cy + r_band * math.sin(theta)
        parts.append(
            f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{r_petal:.3f}" '
            f'fill="none" stroke="{stroke_color}" '
            f'stroke-width="{stroke_width:.3f}"/>'
        )
    return "".join(parts)


def lotus_petal_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 1.25,
    width_ratio: float = 0.6,
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """蓮花瓣 (lotus petal) 環：N 個 teardrop 花瓣繞中心，瓣尖朝外。

    每瓣由兩條 quadratic bezier 構成 teardrop / vesica 形：
    - 內側 base 點：半徑 ``r_inner = r_band - half_len``
    - 外側 tip 點：半徑 ``r_outer = r_band + half_len``
    - half_len = ``r_band × sin(π/n) × length_ratio``
    - 兩條 bezier 的控制點：半徑 r_band，左右 ±half_angle 處
      （half_angle = ``(π/n) × width_ratio``）

    參數調整：

    - ``length_ratio``: 瓣徑向長度（預設 1.25 跟 arcs 同尺度，方便切換比較）
    - ``width_ratio``: 瓣角寬比（1.0 = 整個 sector、0.6 = 較瘦、預設）

    跟 ``interlocking_arcs_band_svg`` 同尺度（r_band, n 一致），切換 style
    時整體大小一致，UI 不需重新調整其他參數。
    """
    if n < 2 or r_band <= 0:
        return ""
    half_len = r_band * math.sin(math.pi / n) * length_ratio
    r_inner = max(r_band - half_len, 0.1)
    r_outer = r_band + half_len
    half_angle = (math.pi / n) * width_ratio
    parts: list[str] = []
    for i in range(n):
        theta = math.radians(rotation_offset_deg + 360.0 * i / n)
        bx = cx + r_inner * math.cos(theta)
        by = cy + r_inner * math.sin(theta)
        tx = cx + r_outer * math.cos(theta)
        ty = cy + r_outer * math.sin(theta)
        lwx = cx + r_band * math.cos(theta - half_angle)
        lwy = cy + r_band * math.sin(theta - half_angle)
        rwx = cx + r_band * math.cos(theta + half_angle)
        rwy = cy + r_band * math.sin(theta + half_angle)
        d = (f"M {bx:.3f},{by:.3f} "
             f"Q {lwx:.3f},{lwy:.3f} {tx:.3f},{ty:.3f} "
             f"Q {rwx:.3f},{rwy:.3f} {bx:.3f},{by:.3f} Z")
        parts.append(
            f'<path d="{d}" fill="none" stroke="{stroke_color}" '
            f'stroke-width="{stroke_width:.3f}"/>'
        )
    return "".join(parts)


def radial_rays_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 1.25,
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """法輪 / 輻射光線 (radial rays) 環：N 條徑向直線。

    每條線從 ``r_inner = r_band - half_len`` 射到 ``r_outer = r_band + half_len``，
    half_len = ``r_band × sin(π/n) × length_ratio``（跟 arcs / lotus 同尺度）。

    視覺：經典法輪輪輻；搭配 ``halo`` 自然把字環跟 mandala 隔開（線在字位置
    被 halo 遮一段，看起來像「光線從字後射出」）。

    跟其他 primitive 切換時整個 mandala 占用半徑範圍不變，user 不需 retune
    `r_band_ratio`。
    """
    if n < 2 or r_band <= 0:
        return ""
    half_len = r_band * math.sin(math.pi / n) * length_ratio
    r_inner = max(r_band - half_len, 0.1)
    r_outer = r_band + half_len
    parts: list[str] = []
    for i in range(n):
        theta = math.radians(rotation_offset_deg + 360.0 * i / n)
        x1 = cx + r_inner * math.cos(theta)
        y1 = cy + r_inner * math.sin(theta)
        x2 = cx + r_outer * math.cos(theta)
        y2 = cy + r_outer * math.sin(theta)
        parts.append(
            f'<line x1="{x1:.3f}" y1="{y1:.3f}" '
            f'x2="{x2:.3f}" y2="{y2:.3f}" '
            f'stroke="{stroke_color}" stroke-width="{stroke_width:.3f}" '
            f'stroke-linecap="round"/>'
        )
    return "".join(parts)


def dots_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    dot_radius_mm: float = 1.0,
    fill_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r11: 圓點 (dots) 環 — N 個小實心圓繞 r_band。

    最簡 primitive。常用於 layer 之間的 spacer ring 或裝飾光點。
    """
    if n < 1 or r_band <= 0 or dot_radius_mm <= 0:
        return ""
    parts: list[str] = []
    for i in range(n):
        theta = math.radians(rotation_offset_deg + 360.0 * i / n)
        x = cx + r_band * math.cos(theta)
        y = cy + r_band * math.sin(theta)
        parts.append(
            f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{dot_radius_mm:.3f}" '
            f'fill="{fill_color}" stroke="none"/>'
        )
    return "".join(parts)


def triangles_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 1.25,
    width_ratio: float = 0.6,
    pointing: str = "outward",
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r11: 三角形 (triangles) 環 — N 個三角形繞 r_band。

    跟 lotus 同尺度公式（length/width ratio）。``pointing="outward"`` =
    尖端向外（佛塔 / 火焰感）；``"inward"`` = 尖端朝中（聚焦感）。

    Apex 在徑向 r_band ± half_len，base 兩端在 r_band ∓ half_len 對應
    ±half_angle 角度位置。SVG `<polygon>` 三點。
    """
    if n < 2 or r_band <= 0:
        return ""
    half_len = r_band * math.sin(math.pi / n) * length_ratio
    half_angle = (math.pi / n) * width_ratio
    if pointing == "inward":
        apex_r = r_band - half_len
        base_r = r_band + half_len
    else:
        apex_r = r_band + half_len
        base_r = r_band - half_len
    parts: list[str] = []
    for i in range(n):
        theta = math.radians(rotation_offset_deg + 360.0 * i / n)
        ax = cx + apex_r * math.cos(theta)
        ay = cy + apex_r * math.sin(theta)
        b1x = cx + base_r * math.cos(theta - half_angle)
        b1y = cy + base_r * math.sin(theta - half_angle)
        b2x = cx + base_r * math.cos(theta + half_angle)
        b2y = cy + base_r * math.sin(theta + half_angle)
        parts.append(
            f'<polygon points="{ax:.3f},{ay:.3f} {b1x:.3f},{b1y:.3f} '
            f'{b2x:.3f},{b2y:.3f}" fill="none" stroke="{stroke_color}" '
            f'stroke-width="{stroke_width:.3f}"/>'
        )
    return "".join(parts)


def wave_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    amplitude_ratio: float = 0.05,
    samples_per_wave: int = 24,
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r11: 波浪 (wave) 環 — 沿 r_band 一圈正弦波。

    N = 一圈內波峰數量。``amplitude_ratio = 振幅 / r_band``，預設 0.05
    （振幅 5% 半徑，溫柔波浪）。

    用 polyline 採樣 N × samples_per_wave + 1 個點，平滑連線（stroke-linejoin
    round）。曲線從 12 o'clock 開始順時針一圈，閉合。
    """
    if n < 1 or r_band <= 0:
        return ""
    amp = r_band * amplitude_ratio
    total_samples = max(n * samples_per_wave, n * 4)
    pts: list[str] = []
    for i in range(total_samples + 1):
        progress = i / total_samples  # 0..1（一整圈）
        theta = math.radians(rotation_offset_deg + 360.0 * progress)
        wave_phase = 2.0 * math.pi * n * progress
        r = r_band + amp * math.sin(wave_phase)
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        pts.append(f"{x:.3f},{y:.3f}")
    return (
        f'<polyline points="{" ".join(pts)}" fill="none" '
        f'stroke="{stroke_color}" stroke-width="{stroke_width:.3f}" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
    )


def zigzag_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    tooth_height_ratio: float = 0.05,
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r11: 鋸齒 (zigzag) 環 — N 個齒狀 peak/valley 沿 r_band。

    比 wave 簡化（直線而非 sine 曲線）。N = 齒數（一圈幾個尖峰）。
    ``tooth_height_ratio = 齒高 / r_band``，預設 0.05。

    2N 個頂點，alternating peak (r_band + height) / valley (r_band − height)，
    閉合 polyline。視覺：「結界感」邊界、保護環。
    """
    if n < 2 or r_band <= 0:
        return ""
    tooth_h = r_band * tooth_height_ratio
    pts: list[str] = []
    # 2N + 1 個點 (起點再次列入閉合)
    for i in range(2 * n + 1):
        theta = math.radians(rotation_offset_deg + 360.0 * i / (2 * n))
        r = r_band + (tooth_h if i % 2 == 0 else -tooth_h)
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        pts.append(f"{x:.3f},{y:.3f}")
    return (
        f'<polyline points="{" ".join(pts)}" fill="none" '
        f'stroke="{stroke_color}" stroke-width="{stroke_width:.3f}" '
        f'stroke-linejoin="round"/>'
    )


def crosses_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 0.8,
    aspect_ratio: float = 1.0,
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r23: 十字架 (crosses) 環 — N 個十字繞 r_band。

    每 cross 中心位於 r_band，1 臂沿徑向、1 臂沿切向。``aspect_ratio = 1.0``
    時兩臂等長（正十字）；< 1 時切向臂縮短。

    視覺：生命交匯 / 平衡 / 精神物質結合（user spec 提的 cross 象徵）。
    """
    if n < 1 or r_band <= 0:
        return ""
    half_radial = r_band * math.sin(math.pi / n) * length_ratio
    half_tangent = half_radial * aspect_ratio
    parts: list[str] = []
    for i in range(n):
        theta = math.radians(rotation_offset_deg + 360.0 * i / n)
        cx_i = cx + r_band * math.cos(theta)
        cy_i = cy + r_band * math.sin(theta)
        rdx, rdy = math.cos(theta), math.sin(theta)
        tdx, tdy = -math.sin(theta), math.cos(theta)
        # Radial arm
        rx1 = cx_i - rdx * half_radial
        ry1 = cy_i - rdy * half_radial
        rx2 = cx_i + rdx * half_radial
        ry2 = cy_i + rdy * half_radial
        # Tangent arm
        tx1 = cx_i - tdx * half_tangent
        ty1 = cy_i - tdy * half_tangent
        tx2 = cx_i + tdx * half_tangent
        ty2 = cy_i + tdy * half_tangent
        parts.append(
            f'<line x1="{rx1:.3f}" y1="{ry1:.3f}" '
            f'x2="{rx2:.3f}" y2="{ry2:.3f}" '
            f'stroke="{stroke_color}" stroke-width="{stroke_width:.3f}" '
            f'stroke-linecap="round"/>'
            f'<line x1="{tx1:.3f}" y1="{ty1:.3f}" '
            f'x2="{tx2:.3f}" y2="{ty2:.3f}" '
            f'stroke="{stroke_color}" stroke-width="{stroke_width:.3f}" '
            f'stroke-linecap="round"/>'
        )
    return "".join(parts)


def stars_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 0.8,
    star_points: int = 5,
    inner_ratio: float = 0.4,
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r23: 星星 (stars) 環 — N 個 star_points 點星。

    每 star 是 2 × star_points 頂點 polygon（外/內 alternating）。inner_ratio
    控制凹進程度（5-pointed 經典 ratio ≈ 0.382）。

    視覺：光明 / 啟蒙 / 指引 / 宇宙能量（user spec 提的 sun/star 象徵）。
    """
    if n < 1 or r_band <= 0 or star_points < 3:
        return ""
    s = r_band * math.sin(math.pi / n) * length_ratio
    inner_r = s * inner_ratio
    # Local frame star polygon: top vertex at local +y direction
    local_pts = []
    for k in range(2 * star_points):
        # k=0 是 top outer vertex (local +y direction, 即 angle = -π/2 in math angle)
        # 用 SVG screen frame: +y 朝下，所以 top 在 -y... 但 transform 會處理
        # Local angle progression: top → 順時針 (在 transform 後對齊外向方向)
        angle = math.pi * k / star_points - math.pi / 2
        r = s if k % 2 == 0 else inner_r
        local_pts.append((r * math.cos(angle), r * math.sin(angle)))
    pts_str = " ".join(f"{x:.3f},{y:.3f}" for x, y in local_pts)
    parts: list[str] = []
    for i in range(n):
        theta_deg = rotation_offset_deg + 360.0 * i / n
        theta = math.radians(theta_deg)
        cx_i = cx + r_band * math.cos(theta)
        cy_i = cy + r_band * math.sin(theta)
        # 旋轉讓 local "top" (k=0 vertex) 朝徑向外
        rot_deg = theta_deg + 90.0
        parts.append(
            f'<g transform="translate({cx_i:.3f},{cy_i:.3f}) '
            f'rotate({rot_deg:.2f})">'
            f'<polygon points="{pts_str}" fill="none" '
            f'stroke="{stroke_color}" '
            f'stroke-width="{stroke_width:.3f}"/></g>'
        )
    return "".join(parts)


def eyes_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 1.0,
    pupil_ratio: float = 0.3,
    height_ratio: float = 0.5,
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r23: 眼睛 (eyes) 環 — N 個眼睛，每眼 = 上下 arc + 中央 pupil。

    Eye 形狀：兩條 quadratic bezier 形成 leaf/almond，中央實心圓 pupil。
    眼睛長軸沿切向（visually 平躺面向圓心方向）。

    視覺：覺知 / 內省 / 自我觀察（user spec 提的 eye 象徵）。
    """
    if n < 1 or r_band <= 0:
        return ""
    s = r_band * math.sin(math.pi / n) * length_ratio
    h = s * height_ratio
    pupil = h * pupil_ratio
    # Local frame: eye 長軸 = local x（左右），高度 = local y（上下）
    # 兩條 quadratic bezier 形成 vesica/almond outline
    eye_d = (
        f"M {-s:.3f},0 Q 0,{-h:.3f} {s:.3f},0 "
        f"M {-s:.3f},0 Q 0,{h:.3f} {s:.3f},0"
    )
    parts: list[str] = []
    for i in range(n):
        theta_deg = rotation_offset_deg + 360.0 * i / n
        theta = math.radians(theta_deg)
        cx_i = cx + r_band * math.cos(theta)
        cy_i = cy + r_band * math.sin(theta)
        # Local +x → tangent 方向（眼睛橫躺）
        rot_deg = theta_deg + 90.0
        parts.append(
            f'<g transform="translate({cx_i:.3f},{cy_i:.3f}) '
            f'rotate({rot_deg:.2f})">'
            f'<path d="{eye_d}" fill="none" stroke="{stroke_color}" '
            f'stroke-width="{stroke_width:.3f}"/>'
            f'<circle cx="0" cy="0" r="{pupil:.3f}" '
            f'fill="{stroke_color}" stroke="none"/></g>'
        )
    return "".join(parts)


def lattice_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 0.9,
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r23: 網格 (lattice) 環 — N 個 cell（方形 + 對角線 X）繞 r_band。

    每 cell = 4-corner polygon（square outline）+ 2 條對角線（X 形十字），
    用單條 SVG `<path>` (M/L commands + Z) 表達。沿徑向對齊（一邊朝中心）。

    視覺：事物連結 / 和諧（user spec 提的 lattice 象徵）。
    """
    if n < 1 or r_band <= 0:
        return ""
    s = r_band * math.sin(math.pi / n) * length_ratio
    parts: list[str] = []
    for i in range(n):
        theta = math.radians(rotation_offset_deg + 360.0 * i / n)
        cx_i = cx + r_band * math.cos(theta)
        cy_i = cy + r_band * math.sin(theta)
        cos_r, sin_r = math.cos(theta), math.sin(theta)

        def world(lx, ly):
            return (cx_i + lx * cos_r - ly * sin_r,
                    cy_i + lx * sin_r + ly * cos_r)

        c1 = world(-s, -s)
        c2 = world(s, -s)
        c3 = world(s, s)
        c4 = world(-s, s)
        d = (
            f"M {c1[0]:.3f},{c1[1]:.3f} L {c2[0]:.3f},{c2[1]:.3f} "
            f"L {c3[0]:.3f},{c3[1]:.3f} L {c4[0]:.3f},{c4[1]:.3f} Z "
            f"M {c1[0]:.3f},{c1[1]:.3f} L {c3[0]:.3f},{c3[1]:.3f} "
            f"M {c2[0]:.3f},{c2[1]:.3f} L {c4[0]:.3f},{c4[1]:.3f}"
        )
        parts.append(
            f'<path d="{d}" fill="none" stroke="{stroke_color}" '
            f'stroke-width="{stroke_width:.3f}"/>'
        )
    return "".join(parts)


def clouds_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 1.0,
    lobe_radius_ratio: float = 0.45,
    pointing: str = "outward",
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r17: 雲朵 (clouds) 環 — N 個雲朵繞 r_band。

    每雲朵 = 3 個 overlapping circles 構成漫畫式 cloud 輪廓：
    - 左 lobe：tangent 方向 -0.7s, 半徑 ~0.45s
    - 中 lobe：徑向方向 ±0.3s, 半徑 ~0.55s（較大、較高）
    - 右 lobe：tangent 方向 +0.7s, 半徑 ~0.45s

    其中 s = ``r_band × sin(π/N) × length_ratio``（半寬，跟其他 primitive 同尺度）。

    ``pointing="outward"`` = 中央 lobe 朝徑向外（雲朵蓬鬆向外）；
    ``"inward"`` = 朝心（雲朵蓬鬆向內）。

    視覺：輕盈夢幻 / 流動（user spec 提的雲紋象徵）。
    """
    if n < 1 or r_band <= 0:
        return ""
    s = r_band * math.sin(math.pi / n) * length_ratio
    sign = 1.0 if pointing == "outward" else -1.0
    # Local frame: +y axis = 徑向方向（已含 pointing sign）
    # 3 個 lobe 的 (local_x = tangent, local_y = radial, radius)
    lobes_local = [
        (-0.7 * s, 0.0, lobe_radius_ratio * s),                          # 左
        (0.0, sign * 0.3 * s, (lobe_radius_ratio + 0.1) * s),           # 中（較大）
        (0.7 * s, 0.0, lobe_radius_ratio * s),                           # 右
    ]
    parts: list[str] = []
    for i in range(n):
        theta = math.radians(rotation_offset_deg + 360.0 * i / n)
        cloud_cx = cx + r_band * math.cos(theta)
        cloud_cy = cy + r_band * math.sin(theta)
        # local +y rotate 到徑向 (theta) 方向 → rotate by (theta − 90°)
        cos_r = math.cos(theta - math.pi / 2)
        sin_r = math.sin(theta - math.pi / 2)
        for lx, ly, lr in lobes_local:
            wx = lx * cos_r - ly * sin_r
            wy = lx * sin_r + ly * cos_r
            x = cloud_cx + wx
            y = cloud_cy + wy
            parts.append(
                f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{lr:.3f}" '
                f'fill="none" stroke="{stroke_color}" '
                f'stroke-width="{stroke_width:.3f}"/>'
            )
    return "".join(parts)


def squares_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 1.0,
    rotation_alignment: str = "radial",
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r16: 方形 (squares) 環 — N 個方形繞 r_band。

    每方形中心在 r_band 半徑上，邊長 = ``2 × r_band × sin(π/N) × length_ratio``
    （length_ratio=1.0 時相鄰方形邊相觸）。

    ``rotation_alignment``:
    - ``"radial"``: 邊軸對齊徑向（方形邊朝中心）— 較規矩
    - ``"diamond"``: 對角線對齊徑向（方形角朝中心）— 像鑽石

    視覺：穩定 / 物質世界平衡（user spec 提的方形象徵）。
    """
    if n < 1 or r_band <= 0:
        return ""
    half_side = r_band * math.sin(math.pi / n) * length_ratio
    parts: list[str] = []
    for i in range(n):
        theta = math.radians(rotation_offset_deg + 360.0 * i / n)
        cx_i = cx + r_band * math.cos(theta)
        cy_i = cy + r_band * math.sin(theta)
        rot_extra = 0.0 if rotation_alignment == "radial" else math.pi / 4
        rot = theta + rot_extra
        cos_r, sin_r = math.cos(rot), math.sin(rot)
        coords = []
        for dx, dy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
            lx, ly = dx * half_side, dy * half_side
            x = cx_i + lx * cos_r - ly * sin_r
            y = cy_i + lx * sin_r + ly * cos_r
            coords.append(f"{x:.3f},{y:.3f}")
        parts.append(
            f'<polygon points="{" ".join(coords)}" '
            f'fill="none" stroke="{stroke_color}" '
            f'stroke-width="{stroke_width:.3f}"/>'
        )
    return "".join(parts)


def hearts_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 1.0,
    pointing: str = "outward",
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r16: 心形 (hearts) 環 — N 個心形繞 r_band。

    每 heart 用 2 條 cubic bezier 構成 (雙 lobe + 底部尖端)。透過 SVG transform
    把 local heart shape 旋轉 + 平移到正確 angle/position，比手算每點 bezier
    乾淨。

    ``pointing="outward"`` = 尖端朝外（徑向 +），``"inward"`` = 朝內（聚焦感）。

    視覺：愛 / 慈悲 / 連結（user spec 提到的 heart 象徵）。
    """
    if n < 1 or r_band <= 0:
        return ""
    s = r_band * math.sin(math.pi / n) * length_ratio
    # Local heart path: 中央在原點，尖端朝 +y（local frame 下方）
    # 兩個 cubic bezier 構成：左 lobe 上下繞、右 lobe 上下繞
    heart_d = (
        f"M 0,{-0.5 * s:.3f} "
        f"C {0.5 * s:.3f},{-1.2 * s:.3f} {1.4 * s:.3f},{-0.5 * s:.3f} 0,{0.8 * s:.3f} "
        f"C {-1.4 * s:.3f},{-0.5 * s:.3f} {-0.5 * s:.3f},{-1.2 * s:.3f} 0,{-0.5 * s:.3f} Z"
    )
    parts: list[str] = []
    for i in range(n):
        theta_deg = rotation_offset_deg + 360.0 * i / n
        theta = math.radians(theta_deg)
        # 中心位於 r_band，但 heart center 是 V 凹處不是幾何中心 — 略微 offset
        # 簡化：放在 r_band 半徑，尖端朝徑向方向
        cx_i = cx + r_band * math.cos(theta)
        cy_i = cy + r_band * math.sin(theta)
        # rotation: local +y axis 應旋轉到徑向外/內方向
        # 標準 SVG rotate(deg) 是 clockwise (數學負方向)
        rot_deg = theta_deg + 90.0 if pointing == "outward" else theta_deg - 90.0
        parts.append(
            f'<g transform="translate({cx_i:.3f},{cy_i:.3f}) rotate({rot_deg:.2f})">'
            f'<path d="{heart_d}" fill="none" stroke="{stroke_color}" '
            f'stroke-width="{stroke_width:.3f}"/></g>'
        )
    return "".join(parts)


def teardrops_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 1.25,
    pointing: str = "outward",
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r16: 淚滴 (teardrops) 環 — N 個水滴形繞 r_band。

    每 teardrop = 圓端 + 尖端，2 條 cubic bezier。跟 lotus_petal (兩端尖) 區別：
    teardrop 一端圓一端尖，更像「下垂的水珠」。

    ``pointing``: 尖端方向（"outward" = 尖朝外、圓朝內；"inward" = 反之）。

    視覺：層與層之間銜接 / 柔性能量（user spec 提的 teardrop 象徵）。
    """
    if n < 1 or r_band <= 0:
        return ""
    half_len = r_band * math.sin(math.pi / n) * length_ratio
    # local teardrop：圓端在 -y, 尖端在 +y，尺寸 ~ 2*half_len
    s = half_len
    teardrop_d = (
        f"M 0,{-s:.3f} "
        f"C {0.85 * s:.3f},{-s:.3f} {0.85 * s:.3f},{0.4 * s:.3f} 0,{s:.3f} "
        f"C {-0.85 * s:.3f},{0.4 * s:.3f} {-0.85 * s:.3f},{-s:.3f} 0,{-s:.3f} Z"
    )
    parts: list[str] = []
    for i in range(n):
        theta_deg = rotation_offset_deg + 360.0 * i / n
        theta = math.radians(theta_deg)
        cx_i = cx + r_band * math.cos(theta)
        cy_i = cy + r_band * math.sin(theta)
        rot_deg = theta_deg + 90.0 if pointing == "outward" else theta_deg - 90.0
        parts.append(
            f'<g transform="translate({cx_i:.3f},{cy_i:.3f}) rotate({rot_deg:.2f})">'
            f'<path d="{teardrop_d}" fill="none" stroke="{stroke_color}" '
            f'stroke-width="{stroke_width:.3f}"/></g>'
        )
    return "".join(parts)


def leaves_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 1.4,
    width_ratio: float = 0.5,
    with_vein: bool = True,
    pointing: str = "outward",
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r16: 葉片 (leaves) 環 — N 片葉子繞 r_band。

    跟 lotus_petal 類似 (兩端尖 + 中央寬)，但加中央徑向葉脈線（with_vein=True 預設）。

    視覺：有機律動 / 生命感（user spec 提的 leaf 象徵）。
    """
    if n < 1 or r_band <= 0:
        return ""
    # 重用 lotus 形狀 (相同 quad bezier)，加可選 vein
    half_len = r_band * math.sin(math.pi / n) * length_ratio
    r_inner = max(r_band - half_len, 0.1)
    r_outer = r_band + half_len
    half_angle = (math.pi / n) * width_ratio
    parts: list[str] = []
    for i in range(n):
        theta = math.radians(rotation_offset_deg + 360.0 * i / n)
        # leaf shape (= lotus body)
        bx = cx + r_inner * math.cos(theta)
        by = cy + r_inner * math.sin(theta)
        tx = cx + r_outer * math.cos(theta)
        ty = cy + r_outer * math.sin(theta)
        lwx = cx + r_band * math.cos(theta - half_angle)
        lwy = cy + r_band * math.sin(theta - half_angle)
        rwx = cx + r_band * math.cos(theta + half_angle)
        rwy = cy + r_band * math.sin(theta + half_angle)
        leaf_d = (
            f"M {bx:.3f},{by:.3f} "
            f"Q {lwx:.3f},{lwy:.3f} {tx:.3f},{ty:.3f} "
            f"Q {rwx:.3f},{rwy:.3f} {bx:.3f},{by:.3f} Z"
        )
        # 葉脈：base 到 tip 的徑向直線
        if with_vein:
            leaf_d += f" M {bx:.3f},{by:.3f} L {tx:.3f},{ty:.3f}"
        # pointing inward → swap 尖端方向（暫不實作，default outward）
        parts.append(
            f'<path d="{leaf_d}" fill="none" stroke="{stroke_color}" '
            f'stroke-width="{stroke_width:.3f}"/>'
        )
    return "".join(parts)


def spiral_band_svg(
    cx: float, cy: float,
    r_band: float,
    n: int,
    *,
    length_ratio: float = 1.25,
    spin_turns: float = 0.5,
    direction: str = "cw",
    samples_per_arm: int = 24,
    stroke_width: float = 0.6,
    stroke_color: str = "#222",
    rotation_offset_deg: float = -90.0,
) -> str:
    """Phase 5b r13: 螺旋 (spiral) 環 — N 個螺旋 arm，N-fold 對稱。

    每 arm 從 ``r_inner = r_band - half_len`` 到 ``r_outer = r_band + half_len``
    （half_len 跟其他 primitive 同尺度公式），徑向方向同時繞中心旋轉
    ``spin_turns`` 圈。

    參數：

    - ``spin_turns``: 每 arm 旋多少圈
        - 0.0 = 直線（degenerate 到 radial rays，但這個 case 用 rays primitive
          更語意正確）
        - 0.5 = 半圈（柔和螺旋，預設）
        - 1.0 = 整圈（明顯螺旋感）
        - > 1.0 = 多重纏繞（複雜，視覺易亂）
    - ``direction``: ``"cw"`` 順時針 / ``"ccw"`` 逆時針
    - ``samples_per_arm``: polyline 採樣數量（預設 24，越多越平滑）

    每 arm 用 1 條 ``<polyline>``。視覺：「成長 / 能量流動 / 演化」象徵，常見
    於漩渦曼陀羅 / 銀河 / DNA 螺旋等隱喻。
    """
    if n < 1 or r_band <= 0:
        return ""
    half_len = r_band * math.sin(math.pi / n) * length_ratio
    r_inner = max(r_band - half_len, 0.1)
    r_outer = r_band + half_len
    sign = -1.0 if direction == "ccw" else 1.0
    spin_rad = sign * spin_turns * 2.0 * math.pi
    s = max(samples_per_arm, 4)
    parts: list[str] = []
    for i in range(n):
        theta0 = math.radians(rotation_offset_deg + 360.0 * i / n)
        pts: list[str] = []
        for k in range(s + 1):
            t = k / s
            r = r_inner + (r_outer - r_inner) * t
            phi = theta0 + spin_rad * t
            x = cx + r * math.cos(phi)
            y = cy + r * math.sin(phi)
            pts.append(f"{x:.3f},{y:.3f}")
        parts.append(
            f'<polyline points="{" ".join(pts)}" fill="none" '
            f'stroke="{stroke_color}" stroke-width="{stroke_width:.3f}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
        )
    return "".join(parts)


def render_extra_layer_svg(
    cx: float, cy: float, r_total: float, layer: dict,
    *, default_n: int = 9,
) -> str:
    """Phase 5b r10: 渲染一個額外裝飾層（純視覺，不跟字環互動）。

    ``layer`` schema (all keys optional, falls back to default):

    - ``style``: "interlocking_arcs" | "lotus_petal" | "radial_rays"
    - ``n_fold``: int (default = ``default_n``)
    - ``r_ratio``: float (× r_total，決定該層半徑)
    - ``overlap_ratio``: float (arcs only)
    - ``lotus_length_ratio`` / ``lotus_width_ratio``: float (lotus only)
    - ``rays_length_ratio``: float (rays only)
    - ``stroke_width``: float (default 0.6)
    - ``rotation_offset_deg``: float (default -90，12 o'clock 起算)

    Layer 是 atomic 一層 primitive，半徑由 r_ratio × r_total 算出，N 跟字環無
    幾何約束（自由）。多層時各自獨立 call 同一個 helper。
    """
    # 5b r21: layer visibility toggle (default True for backward compat)
    if not layer.get("visible", True):
        return ""
    style = layer.get("style", "interlocking_arcs")
    n = max(2, int(layer.get("n_fold", default_n)))
    # 5b r25: r_mm 絕對值優先；否則 fall back 到 r_ratio × r_total
    r_mm_val = layer.get("r_mm")
    if r_mm_val is not None:
        r_band = max(float(r_mm_val), 0.1)
    else:
        r_ratio = float(layer.get("r_ratio", 0.5))
        r_band = max(r_total * r_ratio, 0.1)
    sw = float(layer.get("stroke_width", 0.6))
    rot_deg = float(layer.get("rotation_offset_deg", -90.0))
    # 5b r26: layer.color 統一線條顏色（fill 跟 stroke 共用同一 hex），預設黑色
    color = str(layer.get("color", "#000000"))

    if style == "lotus_petal":
        return lotus_petal_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("lotus_length_ratio", 1.25)),
            width_ratio=float(layer.get("lotus_width_ratio", 0.6)),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "radial_rays":
        return radial_rays_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("rays_length_ratio", 1.25)),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    # 5b r11: 4 個新 primitive
    if style == "dots":
        return dots_band_svg(
            cx, cy, r_band, n,
            dot_radius_mm=float(layer.get("dot_radius_mm", 1.0)),
            fill_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "triangles":
        return triangles_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("length_ratio", 1.25)),
            width_ratio=float(layer.get("width_ratio", 0.6)),
            pointing=str(layer.get("pointing", "outward")),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "wave":
        return wave_band_svg(
            cx, cy, r_band, n,
            amplitude_ratio=float(layer.get("amplitude_ratio", 0.05)),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "zigzag":
        return zigzag_band_svg(
            cx, cy, r_band, n,
            tooth_height_ratio=float(layer.get("tooth_height_ratio", 0.05)),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "spiral":
        return spiral_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("length_ratio", 1.25)),
            spin_turns=float(layer.get("spin_turns", 0.5)),
            direction=str(layer.get("direction", "cw")),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    # 5b r16: 4 個新 primitive
    if style == "squares":
        return squares_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("length_ratio", 1.0)),
            rotation_alignment=str(layer.get("rotation_alignment", "radial")),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "hearts":
        return hearts_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("length_ratio", 1.0)),
            pointing=str(layer.get("pointing", "outward")),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "teardrops":
        return teardrops_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("length_ratio", 1.25)),
            pointing=str(layer.get("pointing", "outward")),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "leaves":
        return leaves_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("length_ratio", 1.4)),
            width_ratio=float(layer.get("width_ratio", 0.5)),
            with_vein=bool(layer.get("with_vein", True)),
            pointing=str(layer.get("pointing", "outward")),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "clouds":
        return clouds_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("length_ratio", 1.0)),
            lobe_radius_ratio=float(layer.get("lobe_radius_ratio", 0.45)),
            pointing=str(layer.get("pointing", "outward")),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    # 5b r23: 4 個新 primitive
    if style == "crosses":
        return crosses_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("length_ratio", 0.8)),
            aspect_ratio=float(layer.get("aspect_ratio", 1.0)),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "stars":
        return stars_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("length_ratio", 0.8)),
            star_points=int(layer.get("star_points", 5)),
            inner_ratio=float(layer.get("inner_ratio", 0.4)),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "eyes":
        return eyes_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("length_ratio", 1.0)),
            pupil_ratio=float(layer.get("pupil_ratio", 0.3)),
            height_ratio=float(layer.get("height_ratio", 0.5)),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    if style == "lattice":
        return lattice_band_svg(
            cx, cy, r_band, n,
            length_ratio=float(layer.get("length_ratio", 0.9)),
            stroke_width=sw,
            stroke_color=color,
            rotation_offset_deg=rot_deg,
        )
    # default "interlocking_arcs"
    return interlocking_arcs_band_svg(
        cx, cy, r_band, n,
        overlap_ratio=float(layer.get("overlap_ratio", 1.25)),
        stroke_width=sw,
        stroke_color=color,
        rotation_offset_deg=rot_deg,
    )


def _char_protection_halos_svg(
    placements: list,
    *,
    radius_factor: float = 0.55,
    halo_color: str = "white",
) -> str:
    """Phase 5b r5: 字保護 halo — 白色實心圓擋在 mandala 線跟字之間，
    避免 mandala 線穿過字 glyph 內的負空間造成「被切」視覺。

    每個 placement 用半徑 ``size_mm × radius_factor`` 白圓 fill，跟字本身
    z-order 之間插一層。``radius_factor`` 預設 0.55：

    - 0.5  → 內切圓 (剛好涵蓋 bbox 中心十字)
    - 0.55 → 緊貼字身（楷書 glyph 罕見填滿 bbox 角落，視覺夠用）
    - 0.7  → 外接圓 (√2/2 ≈ 0.707，完整罩住 bbox)
    - > 0.7 → 過大，mandala band 會被掏空

    Returns concatenated SVG fragment（無 `<g>` wrapper）。
    """
    parts: list[str] = []
    for placement in placements:
        c, x, y, size, rot = placement[:5]
        r = size * radius_factor
        parts.append(
            f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{r:.3f}" '
            f'fill="{halo_color}" stroke="none"/>'
        )
    return "".join(parts)


# ----------------------------------------------------------------------------
# Phase 5b r8: 字佈局原則 — 字必須在 mandala 線條圍出的內部空間中。
#
# 三種 composition_scheme:
#   1. freeform  : 字環 r_ring 跟 mandala r_band 各自獨立（r4-r7 行為，
#                  backward compat。字可能跟 mandala 線交，需 halo 防切）
#   2. vesica    : 字位於相鄰兩 mandala 圓 / 瓣 / 光線「之間」的交集空間。
#                  數學保證：r_band = r_ring / cos(π/N), primitive 角度
#                  offset = π/N (位於字之間)。字位於 vesica piscis 中央。
#   3. inscribed : 每字 1 個圓包住，圓心 = 字位置。圓半徑 = char_size ×
#                  inscribed_padding_factor。只對 arcs primitive 有意義
#                  (lotus/rays 在 inscribed 模式 fallback 到 freeform 公式)。
# ----------------------------------------------------------------------------


def compute_r_ring_from_spacing(
    char_size_center_mm: float,
    char_size_ring_mm: float,
    char_spacing: float,
) -> float:
    """字距 → 字環半徑（5b r8）。

    字距定義：中心字外緣到字環字內緣的距離（單位 = 字身長度）。
    範圍 1 ~ N+1（user 可選），預設 2。

    ``r_ring = char_spacing × char_size_ring + (char_size_center + char_size_ring) / 2``
    """
    return (char_spacing * char_size_ring_mm
            + (char_size_center_mm + char_size_ring_mm) / 2.0)


def max_safe_char_size_ring(
    composition_scheme: str,
    mandala_style: str,
    *,
    r_ring: float,
    r_band: float,
    n: int,
    char_size_ring_mm: float,
    overlap_ratio: float = 1.25,
    lotus_length_ratio: float = 1.25,
    lotus_width_ratio: float = 0.6,
    inscribed_padding_factor: float = 0.7,
    margin: float = 0.85,
) -> float:
    """Phase 5b r9: 計算讓字 bbox 不碰觸 mandala 線條的安全 char_size_ring。

    對每個 (scheme, style) combo 算字到最近線條的 clearance，回傳
    max char_size 使 ``char_size/2 ≤ margin × clearance``（inscribed
    circle protection — 字 bbox 中心十字不超出，glyph 角落極少填到 bbox 角
    所以實際視覺 OK）。

    回傳值 = `min(user_size, geometric_max)`，所以 user 設小於 geometric
    max 時不會放大；只有設太大才 shrink。

    支援的 combo（其餘維持 user 設值）：

    - **arcs + vesica**:
        clearance = ``r_ring × tan(π/N) × (overlap_ratio − 1)``
        max_char = ``2 × margin × clearance``

    - **lotus + inscribed**:
        瓣中心半寬 = ``r_band × sin(half_angle)``，半寬隨徑向 Δr 線性收窄到 0；
        解 ``char_size/2 ≤ margin × half_width(Δr=char_size/2)`` 得：
        max_char = ``2·m·W / (1 + m·W/half_len)``，
        where W = r_band × sin(half_angle)。
    """
    if n < 2 or char_size_ring_mm <= 0:
        return char_size_ring_mm

    if mandala_style == "interlocking_arcs" and composition_scheme == "vesica":
        # vesica: 字位於兩相鄰圓交集中央，距任一圓邊
        # = r_petal - d，其中 d = r_ring × tan(π/N), r_petal = d × overlap_ratio
        clearance = r_ring * math.tan(math.pi / n) * (overlap_ratio - 1.0)
        if clearance <= 0:
            return char_size_ring_mm  # overlap=1.0 相切無 vesica，跳過
        max_char = 2.0 * margin * clearance
        return min(char_size_ring_mm, max_char)

    if mandala_style == "lotus_petal" and composition_scheme == "inscribed":
        half_len = r_band * math.sin(math.pi / n) * lotus_length_ratio
        half_angle = (math.pi / n) * lotus_width_ratio
        if half_len <= 0:
            return char_size_ring_mm
        W = r_band * math.sin(half_angle)
        if W <= 0:
            return char_size_ring_mm
        # 解隱式：char_size ≤ 2·m·W·(1 - char_size/(2·half_len))
        # → char_size · (1 + m·W/half_len) ≤ 2·m·W
        max_char = (2.0 * margin * W) / (1.0 + margin * W / half_len)
        return min(char_size_ring_mm, max_char)

    return char_size_ring_mm


def compute_layout_geometry(
    scheme: str,
    *,
    r_ring: float,
    r_total: float,
    r_band_ratio: float,
    n: int,
) -> tuple[float, float]:
    """Returns (r_band, angle_offset_deg) for mandala primitive layout.

    - freeform   : (r_total × r_band_ratio, 0°)             # backward compat
    - vesica     : (r_ring / cos(π/N),       180°/N)        # primitive 在字之間
    - inscribed  : (r_ring,                  0°)            # primitive 圓心 = 字位置
    """
    if scheme == "vesica":
        if n < 2:
            return (r_ring, 0.0)
        return (r_ring / math.cos(math.pi / n), 180.0 / n)
    if scheme == "inscribed":
        return (r_ring, 0.0)
    # default "freeform"
    return (r_total * r_band_ratio, 0.0)


def compute_mandala_placements(
    center_char: Optional[Character],
    ring_chars: list[Character],
    *,
    cx: float,
    cy: float,
    r_total: float,
    char_size_center_mm: float,
    char_size_ring_mm: float,
    r_ring_ratio: float = 0.45,
    r_ring: Optional[float] = None,
    orient: Orientation = "bottom_to_center",
    rotation_offset_deg: float = -90.0,
) -> list:
    """Compute (char, x, y, size_mm, rot_deg) tuples for center + ring chars.

    ``rotation_offset_deg = -90`` → 第一個 ring char 位於 12 o'clock，後續
    順時針排列（math angle = 0° at 3 o'clock，所以 -90 是 12 o'clock）。

    5b r8: ``r_ring`` 顯式指定（vesica/inscribed scheme 從 char_spacing 推算）
    優先於 ``r_ring_ratio``（freeform scheme 用半徑比）。
    """
    placed: list = []
    if center_char is not None:
        placed.append((center_char, cx, cy, char_size_center_mm, 0.0))
    n = len(ring_chars)
    if n > 0:
        if r_ring is None:
            r_ring = r_total * r_ring_ratio
        for i, ch in enumerate(ring_chars):
            theta_deg = rotation_offset_deg + 360.0 * i / n
            theta = math.radians(theta_deg)
            x = cx + r_ring * math.cos(theta)
            y = cy + r_ring * math.sin(theta)
            # outward normal direction in degrees (radial outward = same angle as theta)
            outward_angle = theta_deg
            rot = _rotation_for(orient, outward_angle)
            placed.append((ch, x, y, char_size_ring_mm, rot))
    return placed


def render_mandala_svg(
    center_text: str,
    ring_text: str,
    char_loader: CharLoader,
    *,
    size_mm: float = 140.0,
    page_width_mm: float = 210.0,
    page_height_mm: float = 297.0,
    n_fold: Optional[int] = None,
    show_chars: bool = True,
    show_mandala: bool = True,
    char_size_center_mm: float = 24.0,
    char_size_ring_mm: float = 10.0,
    r_ring_ratio: float = 0.45,
    r_band_ratio: float = 0.78,
    overlap_ratio: float = 1.25,
    stroke_width: float = 0.6,
    orient: Orientation = "bottom_to_center",
    show_outline: bool = False,
    protect_chars: bool = True,
    protect_radius_factor: float = 0.55,
    mandala_style: str = "interlocking_arcs",
    lotus_length_ratio: float = 1.25,
    lotus_width_ratio: float = 0.6,
    rays_length_ratio: float = 1.25,
    composition_scheme: str = "vesica",
    char_spacing: float = 2.0,
    inscribed_padding_factor: float = 0.7,
    auto_shrink_chars: bool = True,
    shrink_safety_margin: float = 0.85,
    extra_layers: Optional[list] = None,
    center_type: str = "char",
    center_icon_style: str = "lotus_petal",
    center_icon_n: int = 8,
    center_icon_size_mm: float = 12.0,
    include_background: bool = True,
    # 5b r26: 線條顏色（fill+stroke）
    mandala_line_color: str = "#000000",
    char_line_color: str = "#222",
) -> tuple[str, dict]:
    """Compose Case B mandala SVG (center char + ring chars + interlocking
    arcs band).

    ``n_fold`` 為 None → 自動取 ring_text 字數；否則用 user 指定值（mandala
    對稱軸數可獨立於字數）。``show_outline`` = True 時畫出 r_total / r_ring /
    r_band 三個輔助同心圓（debug 用）。

    Returns (svg_string, info_dict).
    """
    cx = page_width_mm / 2.0
    cy = page_height_mm / 2.0
    r_total = size_mm / 2.0

    # 載入中心字（取首字）— Phase 5b r15: center_type="icon"/"empty" 時跳過
    center_char: Optional[Character] = None
    if center_type == "char" and center_text:
        # 取第一個非空白字元
        for ch in center_text:
            if ch.isspace():
                continue
            c = char_loader(ch)
            if c is not None:
                center_char = c
            break

    # 載入字環
    ring_chars: list[Character] = []
    missing: list[str] = []
    for ch in ring_text:
        if ch.isspace():
            continue
        c = char_loader(ch)
        if c is None:
            missing.append(ch)
        else:
            ring_chars.append(c)

    # Mandala N-fold
    if n_fold is not None:
        n = max(2, int(n_fold))
    elif ring_chars:
        n = max(2, len(ring_chars))
    else:
        # 5b r15: Case A (字/icon 中心 + 無字環) → 預設 N=8
        # （N=2 在 vesica scheme 會 cos(π/2)=0 導致 r_band 發散）
        n = 8

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {page_width_mm} {page_height_mm}" '
        f'width="{page_width_mm}mm" height="{page_height_mm}mm">'
    ]
    # 5b r18: include_background=False → 透明 PNG 用（跳過白色 bg rect）
    if include_background:
        parts.append(
            f'<rect x="0" y="0" width="{page_width_mm}" '
            f'height="{page_height_mm}" fill="white"/>'
        )

    # Debug outline: r_total / r_ring / r_band 三同心圓
    if show_outline:
        for r, color in [
            (r_total, "#bbb"),
            (r_total * r_ring_ratio, "#cdd"),
            (r_total * r_band_ratio, "#cdd"),
        ]:
            parts.append(
                f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" '
                f'fill="none" stroke="{color}" stroke-width="0.3" '
                f'stroke-dasharray="2 2"/>'
            )

    # 5b r8: composition_scheme 決定 r_ring 公式跟 mandala primitive 位置
    if composition_scheme in ("vesica", "inscribed"):
        # 從字距推算 r_ring（單位 = char_size_ring_mm）
        r_ring_eff = compute_r_ring_from_spacing(
            char_size_center_mm, char_size_ring_mm, char_spacing)
    else:
        r_ring_eff = r_total * r_ring_ratio  # freeform: r_ring 由半徑比

    # mandala primitive 圓心半徑 + 起始角度 offset
    r_band, scheme_offset_deg = compute_layout_geometry(
        composition_scheme,
        r_ring=r_ring_eff, r_total=r_total,
        r_band_ratio=r_band_ratio, n=n,
    )
    primitive_rotation_deg = -90.0 + scheme_offset_deg

    # 5b r9: 自動縮小字體避免碰觸框線
    # 字距 (r_ring) 已用 user 原本的 char_size_ring 算好，所以 r_ring 不變；
    # 只縮渲染用的字體大小，讓字 bbox 在 mandala 線條圍出空間內。
    char_size_ring_effective = char_size_ring_mm
    if auto_shrink_chars and n >= 2:
        char_size_ring_effective = max_safe_char_size_ring(
            composition_scheme, mandala_style,
            r_ring=r_ring_eff, r_band=r_band, n=n,
            char_size_ring_mm=char_size_ring_mm,
            overlap_ratio=overlap_ratio,
            lotus_length_ratio=lotus_length_ratio,
            lotus_width_ratio=lotus_width_ratio,
            inscribed_padding_factor=inscribed_padding_factor,
            margin=shrink_safety_margin,
        )

    # 預先算 placements（halo 需要這些位置；inscribed mode 圓心也要對齊字位置）
    placed: list = []
    if show_chars:
        placed = compute_mandala_placements(
            center_char, ring_chars,
            cx=cx, cy=cy, r_total=r_total,
            char_size_center_mm=char_size_center_mm,
            char_size_ring_mm=char_size_ring_effective,
            r_ring_ratio=r_ring_ratio,
            r_ring=(r_ring_eff
                    if composition_scheme in ("vesica", "inscribed")
                    else None),
            orient=orient,
            rotation_offset_deg=-90.0,  # 字環從 12 o'clock 開始（不受 scheme offset 影響）
        )

    # L2 mandala band（先畫，會在 halo 跟字之下）
    if show_mandala and n >= 2:
        parts.append(
            f'<g class="mandala" data-style="{mandala_style}" '
            f'data-scheme="{composition_scheme}">'
        )
        if mandala_style == "lotus_petal":
            parts.append(lotus_petal_band_svg(
                cx, cy, r_band, n,
                length_ratio=lotus_length_ratio,
                width_ratio=lotus_width_ratio,
                stroke_width=stroke_width,
                stroke_color=mandala_line_color,
                rotation_offset_deg=primitive_rotation_deg,
            ))
        elif mandala_style == "radial_rays":
            parts.append(radial_rays_band_svg(
                cx, cy, r_band, n,
                length_ratio=rays_length_ratio,
                stroke_width=stroke_width,
                stroke_color=mandala_line_color,
                rotation_offset_deg=primitive_rotation_deg,
            ))
        else:
            # default "interlocking_arcs"
            # 5b r8: inscribed scheme → 圓半徑由 char_size 控制（圓 = 字 bbox 包圍）
            r_petal_override = (
                char_size_ring_mm * inscribed_padding_factor
                if composition_scheme == "inscribed" else None
            )
            parts.append(interlocking_arcs_band_svg(
                cx, cy, r_band, n,
                overlap_ratio=overlap_ratio,
                r_petal=r_petal_override,
                stroke_width=stroke_width,
                stroke_color=mandala_line_color,
                rotation_offset_deg=primitive_rotation_deg,
            ))
        parts.append('</g>')

    # 5b r10: 額外裝飾層（外圈/內圈/任意層數）— 跟主 mandala band 同 z-order
    # 但獨立位置/style/N，不跟字環互動（純視覺裝飾）
    # 5b r21: 跟 show_mandala 解綁 — extras 由 per-layer visible 控制，不受
    # 「隱藏主 mandala 線條」影響。User 可只 hide 主 band 保留 extras。
    if extra_layers:
        parts.append('<g class="extra-layers">')
        for i, layer in enumerate(extra_layers):
            if not isinstance(layer, dict):
                continue
            try:
                inner_svg = render_extra_layer_svg(
                    cx, cy, r_total, layer, default_n=n)
                if inner_svg:
                    style_attr = layer.get("style", "interlocking_arcs")
                    parts.append(
                        f'<g class="extra-layer" data-idx="{i}" '
                        f'data-style="{style_attr}">{inner_svg}</g>'
                    )
            except (TypeError, ValueError, KeyError):
                # 壞 layer 跳過（容錯，user 從 UI 傳的可能格式不對）
                continue
        parts.append('</g>')

    # 5b r15: 中心 icon (Case C) — center_type="icon" 時在中心畫小 mandala
    # 取代字。重用 render_extra_layer_svg dispatcher（任意 primitive style）。
    # 跟 extra layers 同層渲染但語意分離（icon = 中央焦點，extras = 環狀裝飾）。
    if center_type == "icon" and center_icon_size_mm > 0:
        icon_layer = {
            "style": center_icon_style or "lotus_petal",
            "n_fold": max(2, int(center_icon_n)),
            # r_ratio 是 r_total 的分數，icon 用 size_mm 推算
            "r_ratio": (center_icon_size_mm / 2.0) / r_total,
            "stroke_width": stroke_width,
        }
        try:
            icon_svg = render_extra_layer_svg(
                cx, cy, r_total, icon_layer,
                default_n=icon_layer["n_fold"])
            if icon_svg:
                parts.append(
                    f'<g class="center-icon" '
                    f'data-style="{icon_layer["style"]}">{icon_svg}</g>'
                )
        except (TypeError, ValueError, KeyError):
            pass

    # 5b r5: 字保護 halo — 白色實心圓擋在 mandala 線跟字之間，
    # 只在 mandala + chars 都顯示 + protect_chars=True 時才需要。
    # halo 跟 mandala 顏色不同（halo 白、mandala 黑/灰），會擦掉 halo
    # 區域的 mandala 線；字再畫上去就完整不被切。
    if show_mandala and show_chars and protect_chars and placed:
        parts.append('<g class="char-halos">')
        parts.append(_char_protection_halos_svg(
            placed, radius_factor=protect_radius_factor))
        parts.append('</g>')

    # L0 + L1 chars（最上層）
    placed_count = 0
    if show_chars and placed:
        parts.append('<g class="chars">')
        for (c, x, y, size, rot) in placed:
            parts.append(_place_char_svg(c, x, y, size, rot, char_line_color))
        parts.append('</g>')
        placed_count = len(placed)

    parts.append('</svg>')

    info = {
        "placed_count": placed_count,
        "missing_count": len(missing),
        "missing_chars": "".join(missing),
        "n_fold": n,
        "ring_chars_count": len(ring_chars),
        "has_center_char": center_char is not None,
        "composition_scheme": composition_scheme,
        "r_ring_mm": round(r_ring_eff, 2),
        "r_band_mm": round(r_band, 2),
        "char_size_ring_original_mm": round(char_size_ring_mm, 2),
        "char_size_ring_effective_mm": round(char_size_ring_effective, 2),
        "char_shrunk": char_size_ring_effective < char_size_ring_mm - 0.01,
        "extra_layers_count": len(extra_layers) if extra_layers else 0,
        "center_type": center_type,
        "has_center_icon": center_type == "icon",
    }
    return "\n".join(parts), info


# ---------------------------------------------------------------------------
# Phase 5b r12: Preset 主題 — 一鍵套全部設定（mandala_style + scheme +
# char_spacing + style-specific params + extra_layers）
#
# Preset = high-level 風格名稱 + 配套設定，給 user「立即可用」的起點。
# 後端為 single source of truth，前端透過 /api/mandala/presets 拿 metadata，
# dropdown change 時套到 UI inputs。
# ---------------------------------------------------------------------------


# Phase 5b r28c: state schema → render_mandala_svg 映射
# 給 gallery upload thumbnail / 未來 server-side preview / API 統一使用
def render_mandala_from_state(
    state: dict, char_loader: CharLoader,
) -> tuple[str, dict]:
    """Render `.mandala.md` schema state → SVG。

    state 是 stroke-order-mandala-v1 frontmatter 解析後的 dict（schema +
    canvas + center + ring + mandala + extra_layers + style）。本函式把每個
    section 的欄位 map 到 ``render_mandala_svg`` 的 kwargs，回 (svg, info)。

    ``char_loader`` 由 caller 提供（API 層構造、含 style / source / cns_mode
    pipeline）。本層不知道 loader 細節，純 DI。

    Defensive：state 缺 section / 欄位用 default，不爆。
    """
    canvas = state.get("canvas") or {}
    center = state.get("center") or {}
    ring = state.get("ring") or {}
    mandala = state.get("mandala") or {}
    extras = state.get("extra_layers") or []

    # n_fold: state 中可能是 None（自動取字環長度），保 None 給 render_mandala_svg
    n_fold = mandala.get("n_fold")
    if n_fold is not None:
        try:
            n_fold = int(n_fold)
        except (ValueError, TypeError):
            n_fold = None

    return render_mandala_svg(
        center_text=str(center.get("text", "")),
        ring_text=str(ring.get("text", "")),
        char_loader=char_loader,
        size_mm=float(canvas.get("size_mm", 140)),
        page_width_mm=float(canvas.get("page_width_mm", 210)),
        page_height_mm=float(canvas.get("page_height_mm", 297)),
        n_fold=n_fold,
        show_chars=True,
        show_mandala=bool(mandala.get("show", True)),
        char_size_center_mm=float(center.get("size_mm", 24)),
        char_size_ring_mm=float(ring.get("size_mm", 10)),
        r_ring_ratio=float(mandala.get("r_ring_ratio", 0.45)),
        r_band_ratio=float(mandala.get("r_band_ratio", 0.78)),
        overlap_ratio=float(mandala.get("overlap_ratio", 1.25)),
        stroke_width=float(mandala.get("stroke_width", 0.6)),
        orient=str(ring.get("orientation", "bottom_to_center")),
        show_outline=False,
        protect_chars=bool(ring.get("protect_chars", True)),
        protect_radius_factor=float(ring.get("protect_radius_factor", 0.55)),
        mandala_style=str(mandala.get("style", "interlocking_arcs")),
        lotus_length_ratio=float(mandala.get("lotus_length_ratio", 1.25)),
        lotus_width_ratio=float(mandala.get("lotus_width_ratio", 0.6)),
        rays_length_ratio=float(mandala.get("rays_length_ratio", 1.25)),
        composition_scheme=str(mandala.get("composition_scheme", "vesica")),
        char_spacing=float(ring.get("spacing", 2.0)),
        inscribed_padding_factor=float(
            mandala.get("inscribed_padding_factor", 0.7)),
        auto_shrink_chars=bool(ring.get("auto_shrink", True)),
        shrink_safety_margin=float(ring.get("shrink_safety_margin", 0.85)),
        extra_layers=extras,
        center_type=str(center.get("type", "char")),
        center_icon_style=str(center.get("icon_style", "lotus_petal")),
        center_icon_n=int(center.get("icon_n", 8)),
        center_icon_size_mm=float(center.get("icon_size_mm", 12.0)),
        include_background=True,
        mandala_line_color=str(mandala.get("line_color", "#000000")),
        # state 中 center.line_color 跟 ring.line_color 一致時用同一個；
        # 若不同（schema v1 沒明確規定），優先用 ring（字環是視覺主體）
        char_line_color=str(
            ring.get("line_color", center.get("line_color", "#000000"))),
    )


MANDALA_PRESETS: dict[str, dict] = {
    "kuji_in": {
        "name": "九字真言",
        "description": "vesica + 9 字字環，r4 經典配置（默認）",
        "config": {
            "center_text": "咒",
            "ring_text": "臨兵鬥者皆陣列在前",
            "mandala_style": "interlocking_arcs",
            "composition_scheme": "vesica",
            "char_spacing": 2.0,
            "overlap_ratio": 1.25,
            "auto_shrink_chars": True,
            "extra_layers": [],
        },
    },
    "lotus_throne": {
        "name": "蓮花座",
        "description": "蓮花瓣 inscribed 字環 + 外圈點陣 + 中心點光",
        "config": {
            "center_text": "佛",
            "ring_text": "南無阿彌陀佛",
            "mandala_style": "lotus_petal",
            "composition_scheme": "inscribed",
            "char_spacing": 1.5,
            "lotus_length_ratio": 1.4,
            "lotus_width_ratio": 0.7,
            "auto_shrink_chars": True,
            "extra_layers": [
                {"style": "dots", "n_fold": 24, "r_ratio": 0.95,
                 "dot_radius_mm": 1.0},
                {"style": "dots", "n_fold": 6, "r_ratio": 0.18,
                 "dot_radius_mm": 1.5},
            ],
        },
    },
    "dharma_wheel": {
        "name": "法輪",
        "description": "輻射光線主層 + 鋸齒外框 + 內圈三角聚光",
        "config": {
            "center_text": "法",
            "ring_text": "苦集滅道",
            "mandala_style": "radial_rays",
            "composition_scheme": "vesica",
            "char_spacing": 2.5,
            "rays_length_ratio": 1.5,
            "auto_shrink_chars": True,
            "extra_layers": [
                {"style": "zigzag", "n_fold": 32, "r_ratio": 1.0,
                 "tooth_height_ratio": 0.03},
                {"style": "triangles", "n_fold": 8, "r_ratio": 0.30,
                 "length_ratio": 0.5, "width_ratio": 0.5,
                 "pointing": "inward"},
            ],
        },
    },
    "flame_seal": {
        "name": "火焰結界",
        "description": "vesica 主層 + 外三角火焰 + 鋸齒邊界 + 內波紋",
        "config": {
            "center_text": "封",
            "ring_text": "臨兵鬥者皆陣列在前",
            "mandala_style": "interlocking_arcs",
            "composition_scheme": "vesica",
            "char_spacing": 2.5,
            "overlap_ratio": 1.4,
            "auto_shrink_chars": True,
            "extra_layers": [
                {"style": "zigzag", "n_fold": 36, "r_ratio": 1.0,
                 "tooth_height_ratio": 0.04},
                {"style": "triangles", "n_fold": 18, "r_ratio": 0.93,
                 "length_ratio": 0.4, "width_ratio": 0.4,
                 "pointing": "outward"},
                {"style": "wave", "n_fold": 18, "r_ratio": 0.28,
                 "amplitude_ratio": 0.04},
            ],
        },
    },
    "minimal": {
        "name": "素雅",
        "description": "純 vesica + 字環，無額外裝飾。極簡風格。",
        "config": {
            "center_text": "心",
            "ring_text": "色不異空空不異色",
            "mandala_style": "interlocking_arcs",
            "composition_scheme": "vesica",
            "char_spacing": 2.0,
            "overlap_ratio": 1.20,
            "auto_shrink_chars": True,
            "extra_layers": [],
        },
    },
    "spiral_galaxy": {
        "name": "螺旋星雲",
        "description": "vesica 字環 + 外圈順時針螺旋 + 內圈逆時針螺旋（流動感）",
        "config": {
            "center_text": "氣",
            "ring_text": "金木水火土風雷山澤",
            "mandala_style": "interlocking_arcs",
            "composition_scheme": "vesica",
            "char_spacing": 2.5,
            "overlap_ratio": 1.30,
            "auto_shrink_chars": True,
            "extra_layers": [
                {"style": "spiral", "n_fold": 9, "r_ratio": 0.95,
                 "length_ratio": 0.5, "spin_turns": 0.6, "direction": "cw"},
                {"style": "spiral", "n_fold": 9, "r_ratio": 0.28,
                 "length_ratio": 0.6, "spin_turns": 0.7, "direction": "ccw"},
            ],
        },
    },
    "auspicious_clouds": {
        "name": "祥雲",
        "description": "vesica 字環 + 外圈雲朵 + 內圈雲朵（中式雲紋）",
        "config": {
            "center_text": "雲",
            "ring_text": "乾兌離震巽坎艮坤",
            "mandala_style": "interlocking_arcs",
            "composition_scheme": "vesica",
            "char_spacing": 2.5,
            "overlap_ratio": 1.25,
            "auto_shrink_chars": True,
            "extra_layers": [
                {"style": "clouds", "n_fold": 8, "r_ratio": 0.95,
                 "length_ratio": 1.0, "lobe_radius_ratio": 0.45,
                 "pointing": "outward"},
                {"style": "clouds", "n_fold": 8, "r_ratio": 0.28,
                 "length_ratio": 0.8, "lobe_radius_ratio": 0.5,
                 "pointing": "inward"},
            ],
        },
    },
    "ten_virtues": {
        "name": "十字真言",
        "description": "10 美德字環 (真誠信實愛和恕禮善同) + 中央 10 瓣蓮花 icon + 外圈花瓣（無中心字）",
        "config": {
            "center_text": "",
            "ring_text": "真誠信實愛和恕禮善同",
            "mandala_style": "interlocking_arcs",
            "composition_scheme": "vesica",
            "char_spacing": 2.0,
            "overlap_ratio": 1.25,
            "auto_shrink_chars": True,
            "center_type": "icon",
            "center_icon_style": "lotus_petal",
            "center_icon_n": 10,
            "center_icon_size_mm": 14.0,
            "extra_layers": [
                {"style": "lotus_petal", "n_fold": 10, "r_ratio": 0.95,
                 "lotus_length_ratio": 0.4, "lotus_width_ratio": 0.5},
            ],
        },
    },
}


def get_mandala_preset(key: str) -> Optional[dict]:
    """Lookup preset by key. Returns None if unknown."""
    return MANDALA_PRESETS.get(key)


def list_mandala_presets() -> list[dict]:
    """List all presets as ``[{key, name, description, config}, ...]``。

    Order: insertion order of MANDALA_PRESETS（kuji_in 第一，UI dropdown
    順序對齊）。
    """
    return [
        {"key": k, "name": v["name"], "description": v["description"],
         "config": v["config"]}
        for k, v in MANDALA_PRESETS.items()
    ]


# ---------------------------------------------------------------------------
# Phase 5b r19: G-code 輸出（寫字機 / 雷射 / CNC toolpath）
# ---------------------------------------------------------------------------


def _parse_path_d(d: str) -> list[tuple[str, list[float]]]:
    """Parse SVG path d string → list of (cmd, coords)。

    Supports M / L / Q / C / Z（mandala primitives 限這幾種，不含 A 弧線
    指令）。lowercase relative commands 也支援。
    """
    import re as _re
    tokens = _re.findall(
        r'[MLQCZmlqcz]|[\-+]?\d*\.?\d+(?:[eE][\-+]?\d+)?', d)
    segments: list[tuple[str, list[float]]] = []
    i = 0
    n_coords_for = {'M': 2, 'L': 2, 'Q': 4, 'C': 6,
                    'm': 2, 'l': 2, 'q': 4, 'c': 6,
                    'Z': 0, 'z': 0}
    while i < len(tokens):
        tok = tokens[i]
        if tok in n_coords_for:
            n = n_coords_for[tok]
            if n == 0:
                segments.append((tok.upper(), []))
                i += 1
            else:
                if i + n >= len(tokens):
                    break
                coords = [float(tokens[i + 1 + k]) for k in range(n)]
                segments.append((tok, coords))
                i += 1 + n
        else:
            i += 1
    return segments


def _path_d_to_polylines(d: str, samples_per_curve: int = 24
                          ) -> list[list[tuple[float, float]]]:
    """Path d → list of polylines（每 M 開新 sub-path，Z 閉合）。"""
    segments = _parse_path_d(d)
    polylines: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    cx, cy = 0.0, 0.0
    sx, sy = 0.0, 0.0  # subpath 起點（給 Z 用）
    for cmd, args in segments:
        if cmd == 'M':
            if len(current) >= 2:
                polylines.append(current)
            current = [(args[0], args[1])]
            cx, cy, sx, sy = args[0], args[1], args[0], args[1]
        elif cmd == 'L':
            current.append((args[0], args[1]))
            cx, cy = args[0], args[1]
        elif cmd == 'Q':
            qcx, qcy, ex, ey = args
            for k in range(1, samples_per_curve + 1):
                t = k / samples_per_curve
                x = (1 - t) ** 2 * cx + 2 * (1 - t) * t * qcx + t ** 2 * ex
                y = (1 - t) ** 2 * cy + 2 * (1 - t) * t * qcy + t ** 2 * ey
                current.append((x, y))
            cx, cy = ex, ey
        elif cmd == 'C':
            c1x, c1y, c2x, c2y, ex, ey = args
            for k in range(1, samples_per_curve + 1):
                t = k / samples_per_curve
                x = ((1 - t) ** 3 * cx + 3 * (1 - t) ** 2 * t * c1x
                     + 3 * (1 - t) * t ** 2 * c2x + t ** 3 * ex)
                y = ((1 - t) ** 3 * cy + 3 * (1 - t) ** 2 * t * c1y
                     + 3 * (1 - t) * t ** 2 * c2y + t ** 3 * ey)
                current.append((x, y))
            cx, cy = ex, ey
        elif cmd == 'Z':
            if current and current[0] != current[-1]:
                current.append((sx, sy))
            polylines.append(current)
            current = []
            cx, cy = sx, sy
    if len(current) >= 2:
        polylines.append(current)
    return polylines


def _circle_to_polyline(cx: float, cy: float, r: float, samples: int = 64
                         ) -> list[tuple[float, float]]:
    pts = []
    for i in range(samples + 1):
        theta = 2.0 * math.pi * i / samples
        pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    return pts


def _parse_points_str(s: str) -> list[tuple[float, float]]:
    pts = []
    for tok in s.replace(",", " ").split():
        try:
            pts.append(float(tok))
        except ValueError:
            continue
    return [(pts[i], pts[i + 1]) for i in range(0, len(pts) - 1, 2)]


def _parse_transform(tform: str) -> tuple[float, float, float]:
    """Parse 'translate(X,Y) rotate(R)' → (tx, ty, rot_rad)。其他 transform 忽略。"""
    if not tform:
        return (0.0, 0.0, 0.0)
    import re as _re
    tx, ty, rot = 0.0, 0.0, 0.0
    m = _re.search(r'translate\(\s*([\-\d.]+)[,\s]+([\-\d.]+)\s*\)', tform)
    if m:
        tx, ty = float(m.group(1)), float(m.group(2))
    m = _re.search(r'rotate\(\s*([\-\d.]+)\s*\)', tform)
    if m:
        rot = math.radians(float(m.group(1)))
    return (tx, ty, rot)


def _apply_transform(points, tx: float, ty: float, rot: float
                      ) -> list[tuple[float, float]]:
    if tx == 0 and ty == 0 and rot == 0:
        return list(points)
    cos_r, sin_r = math.cos(rot), math.sin(rot)
    return [
        (x * cos_r - y * sin_r + tx, x * sin_r + y * cos_r + ty)
        for x, y in points
    ]


def render_mandala_gcode(
    svg_str: str,
    *,
    feed_rate_mm_per_min: float = 1000.0,
    travel_rate_mm_per_min: float = 3000.0,
    pen_down_z: float = -1.0,
    pen_up_z: float = 2.0,
    flip_y: bool = True,
    curve_samples: int = 24,
) -> str:
    """Convert mandala SVG → G-code (pen-style writing/cutting machine)。

    僅輸出 mandala/extras/center-icon 的 primitive 線條，**不含字 outline**
    （字 path 過於複雜，第一輪先省）。User 用機器執行 G-code 可雕出完整
    mandala 圖案，字位置可後續手寫 / 雷射 / 另套 G-code 處理。

    Y 軸預設翻轉（SVG y 朝下 → 機器 y 朝上）。

    Output: G21 (mm) + G90 (absolute) + per-polyline G0 (move) + G1 (draw)。
    """
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(svg_str)
    except ET.ParseError:
        return "; G-code generation failed: invalid SVG\n"

    # 從 viewBox 拿 page height (Y flip 用)
    viewbox = root.get("viewBox", "")
    vb_parts = viewbox.split()
    page_h = float(vb_parts[3]) if len(vb_parts) == 4 else 297.0

    target_classes = {"mandala", "extra-layers", "extra-layer", "center-icon"}
    skip_classes = {"chars", "char-halos"}
    # 5b r26: 每 polyline 帶 color tag → 後續 group by color，輸出時相同色一氣呵成
    # tagged_polylines: list[(color, [(x,y), ...])]
    tagged_polylines: list[tuple[str, list[tuple[float, float]]]] = []
    DEFAULT_COLOR = "#000000"

    def tag_local(elem):
        return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

    def _normalize_color(c):
        """SVG 顏色 normalize：去空白、轉小寫；'none'/'' → None"""
        if c is None:
            return None
        s = str(c).strip().lower()
        if not s or s == "none":
            return None
        return s

    def _resolve_color(elem, parent_stroke, parent_fill):
        """Pick the effective draw color for this element.

        SVG stroke/fill 從 parent 繼承（own attr 蓋掉 parent）。本函式優先取 stroke；
        若 stroke=none/missing 則 fall back 到 fill；都沒有用 DEFAULT_COLOR。
        """
        own_stroke = _normalize_color(elem.get("stroke"))
        own_fill = _normalize_color(elem.get("fill"))
        eff_stroke = own_stroke if own_stroke is not None \
            else (parent_stroke if parent_stroke != "__not_set__" else None)
        eff_fill = own_fill if own_fill is not None \
            else (parent_fill if parent_fill != "__not_set__" else None)
        # stroke=none 視為 invisible → 用 fill；都無就 default
        if eff_stroke and eff_stroke != "none":
            return eff_stroke
        if eff_fill and eff_fill != "none":
            return eff_fill
        return DEFAULT_COLOR

    def process_element(elem, transform, parent_stroke, parent_fill):
        t = tag_local(elem)
        own_t = _parse_transform(elem.get("transform", ""))
        tform = own_t if own_t != (0.0, 0.0, 0.0) else transform
        color = _resolve_color(elem, parent_stroke, parent_fill)
        if t == "circle":
            cx = float(elem.get("cx", 0))
            cy = float(elem.get("cy", 0))
            r = float(elem.get("r", 0))
            pts = _circle_to_polyline(cx, cy, r, samples=64)
            if tform != (0.0, 0.0, 0.0):
                pts = _apply_transform(pts, *tform)
            tagged_polylines.append((color, pts))
        elif t in ("polygon", "polyline"):
            pts_str = elem.get("points", "")
            pts = _parse_points_str(pts_str)
            if t == "polygon" and pts:
                pts.append(pts[0])
            if tform != (0.0, 0.0, 0.0):
                pts = _apply_transform(pts, *tform)
            tagged_polylines.append((color, pts))
        elif t == "line":
            pts = [(float(elem.get("x1", 0)), float(elem.get("y1", 0))),
                   (float(elem.get("x2", 0)), float(elem.get("y2", 0)))]
            if tform != (0.0, 0.0, 0.0):
                pts = _apply_transform(pts, *tform)
            tagged_polylines.append((color, pts))
        elif t == "path":
            d = elem.get("d", "")
            for sub in _path_d_to_polylines(d, samples_per_curve=curve_samples):
                if tform != (0.0, 0.0, 0.0):
                    sub = _apply_transform(sub, *tform)
                tagged_polylines.append((color, sub))

    def walk(node, in_target: bool,
             parent_transform=(0.0, 0.0, 0.0),
             parent_stroke="__not_set__", parent_fill="__not_set__"):
        cls = node.get("class", "")
        if cls in skip_classes:
            return
        own_t = _parse_transform(node.get("transform", ""))
        cur_t = own_t if own_t != (0.0, 0.0, 0.0) else parent_transform
        # 繼承 stroke/fill：own 蓋 parent，own 缺則沿用 parent
        own_stroke = _normalize_color(node.get("stroke"))
        own_fill = _normalize_color(node.get("fill"))
        cur_stroke = own_stroke if own_stroke is not None else parent_stroke
        cur_fill = own_fill if own_fill is not None else parent_fill
        if cls in target_classes:
            in_target = True
        if in_target:
            for child in node:
                ct = tag_local(child)
                if ct == "g":
                    walk(child, True, cur_t, cur_stroke, cur_fill)
                else:
                    process_element(child, cur_t, cur_stroke, cur_fill)
        else:
            for child in node:
                ct = tag_local(child)
                if ct == "g":
                    walk(child, False, cur_t, cur_stroke, cur_fill)

    walk(root, in_target=False)

    # Y flip
    if flip_y:
        tagged_polylines = [
            (color, [(x, page_h - y) for x, y in p])
            for color, p in tagged_polylines
        ]

    # 5b r26: 按 color 分組，order-stable（首次出現順序決定 group 順序）
    color_order: list[str] = []
    color_groups: dict[str, list[list[tuple[float, float]]]] = {}
    for color, poly in tagged_polylines:
        if color not in color_groups:
            color_groups[color] = []
            color_order.append(color)
        color_groups[color].append(poly)

    total_points = sum(len(p) for _, p in tagged_polylines)

    # G-code 輸出
    out = [
        "; Mandala G-code (Phase 5b r26)",
        f"; polylines: {len(tagged_polylines)}",
        f"; total points: {total_points}",
        f"; color groups: {len(color_order)} ({', '.join(color_order)})",
        "G21 ; mm",
        "G90 ; absolute coordinates",
        f"F{feed_rate_mm_per_min:.0f} ; feed rate (drawing)",
        f"G0 Z{pen_up_z:.2f} ; pen up",
    ]
    for color in color_order:
        polys = color_groups[color]
        out.append(f"; ===== COLOR: {color} =====")
        out.append(f"; polylines in this color: {len(polys)}")
        out.append(f"; --- pause / change pen to {color} ---")
        for poly in polys:
            if len(poly) < 2:
                continue
            x0, y0 = poly[0]
            out.append(f"G0 X{x0:.3f} Y{y0:.3f} ; travel to start")
            out.append(f"G1 Z{pen_down_z:.2f} F{travel_rate_mm_per_min:.0f}")
            out.append(f"F{feed_rate_mm_per_min:.0f}")
            for x, y in poly[1:]:
                out.append(f"G1 X{x:.3f} Y{y:.3f}")
            out.append(f"G0 Z{pen_up_z:.2f} ; pen up")
    out.append("; end")
    return "\n".join(out) + "\n"


__all__ = [
    "interlocking_arcs_band_svg",
    "lotus_petal_band_svg",
    "radial_rays_band_svg",
    "dots_band_svg",
    "triangles_band_svg",
    "wave_band_svg",
    "zigzag_band_svg",
    "spiral_band_svg",
    "squares_band_svg",
    "hearts_band_svg",
    "teardrops_band_svg",
    "leaves_band_svg",
    "clouds_band_svg",
    "crosses_band_svg",
    "stars_band_svg",
    "eyes_band_svg",
    "lattice_band_svg",
    "compute_mandala_placements",
    "compute_layout_geometry",
    "compute_r_ring_from_spacing",
    "max_safe_char_size_ring",
    "render_extra_layer_svg",
    "render_mandala_svg",
    "render_mandala_from_state",
    "MANDALA_PRESETS",
    "get_mandala_preset",
    "list_mandala_presets",
    "render_mandala_gcode",
    "_char_protection_halos_svg",
]
