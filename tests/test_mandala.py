"""Phase 5b r4 — 曼陀羅模式 (mandala) 基本測試。"""

import math

import pytest

from stroke_order.exporters.mandala import (
    MANDALA_PRESETS,
    clouds_band_svg,
    compute_layout_geometry,
    compute_mandala_placements,
    compute_r_ring_from_spacing,
    crosses_band_svg,
    dots_band_svg,
    eyes_band_svg,
    get_mandala_preset,
    hearts_band_svg,
    interlocking_arcs_band_svg,
    lattice_band_svg,
    leaves_band_svg,
    list_mandala_presets,
    lotus_petal_band_svg,
    max_safe_char_size_ring,
    radial_rays_band_svg,
    render_extra_layer_svg,
    render_mandala_svg,
    spiral_band_svg,
    squares_band_svg,
    stars_band_svg,
    teardrops_band_svg,
    triangles_band_svg,
    wave_band_svg,
    zigzag_band_svg,
)
from stroke_order.ir import Character, Point, Stroke


@pytest.fixture
def stub_loader():
    def _l(ch):
        return Character(
            char=ch, unicode_hex=f"{ord(ch):04x}", data_source="stub",
            strokes=[Stroke(
                index=0,
                raw_track=[Point(100, 100), Point(1948, 1948)],
                outline=[
                    {"type": "M", "x": 200,  "y": 200},
                    {"type": "L", "x": 1848, "y": 200},
                    {"type": "L", "x": 1848, "y": 1848},
                    {"type": "L", "x": 200,  "y": 1848},
                ],
                kind_code=9, kind_name="其他", has_hook=False,
            )],
        )
    return _l


# ---------------------------------------------------------------------------
# interlocking_arcs_band_svg — geometry
# ---------------------------------------------------------------------------


def test_interlocking_arcs_emits_n_circles():
    """N=9 → 9 個 <circle> elements."""
    svg = interlocking_arcs_band_svg(0, 0, 50, 9)
    assert svg.count("<circle") == 9


def test_interlocking_arcs_petal_radius_overlap():
    """overlap_ratio > 1 → 相鄰圓 overlap (花瓣半徑 > 半弦長)。"""
    cx, cy, r_band, n = 0.0, 0.0, 50.0, 9
    half_chord = r_band * math.sin(math.pi / n)
    svg = interlocking_arcs_band_svg(
        cx, cy, r_band, n, overlap_ratio=1.25)
    # First circle: extract r=...
    import re
    rs = re.findall(r'<circle[^>]*r="([\d.]+)"', svg)
    assert rs, "no <circle> emitted"
    petal_r = float(rs[0])
    # overlap_ratio=1.25 → petal_r > half_chord (i.e. overlap)
    assert petal_r > half_chord, (
        f"expected overlap (petal_r > {half_chord:.2f}), got {petal_r:.2f}")
    assert abs(petal_r - half_chord * 1.25) < 0.01


def test_interlocking_arcs_first_at_12_oclock():
    """rotation_offset_deg=-90 → 第一圓位於 12 o'clock (cy 上方)。"""
    cx, cy, r_band, n = 0.0, 0.0, 50.0, 4
    svg = interlocking_arcs_band_svg(
        cx, cy, r_band, n, rotation_offset_deg=-90.0)
    import re
    coords = re.findall(r'<circle cx="([\-\d.]+)" cy="([\-\d.]+)"', svg)
    assert coords, "no <circle> emitted"
    x0, y0 = float(coords[0][0]), float(coords[0][1])
    assert abs(x0 - cx) < 0.01, f"first circle should be at cx, got x={x0}"
    # SVG y-axis: 12 o'clock = y < cy (smaller y)
    assert y0 < cy - 1.0, f"first circle should be above center, got y={y0}"


def test_interlocking_arcs_zero_n_returns_empty():
    assert interlocking_arcs_band_svg(0, 0, 50, 1) == ""
    assert interlocking_arcs_band_svg(0, 0, 0, 9) == ""


# ---------------------------------------------------------------------------
# compute_mandala_placements
# ---------------------------------------------------------------------------


def test_placements_center_plus_ring(stub_loader):
    center = stub_loader("咒")
    ring = [stub_loader(c) for c in "臨兵鬥者皆陣列在前"]
    placed = compute_mandala_placements(
        center, ring, cx=100, cy=100, r_total=70,
        char_size_center_mm=24, char_size_ring_mm=10,
        r_ring_ratio=0.45,
    )
    # 1 center + 9 ring chars
    assert len(placed) == 10
    # Center at (cx, cy)
    c_center = placed[0]
    assert c_center[1] == 100 and c_center[2] == 100
    assert c_center[3] == 24  # size
    # Ring chars all at r ≈ 70 * 0.45 = 31.5
    for p in placed[1:]:
        dx, dy = p[1] - 100, p[2] - 100
        r = math.hypot(dx, dy)
        assert abs(r - 31.5) < 0.5, f"ring char at r={r:.2f}, expected 31.5"
        assert p[3] == 10  # ring char size


def test_placements_center_only(stub_loader):
    """ring_chars=[] → 只有 center；對應 user 的 case A (中心字 + mandala)."""
    center = stub_loader("咒")
    placed = compute_mandala_placements(
        center, [], cx=100, cy=100, r_total=70,
        char_size_center_mm=24, char_size_ring_mm=10,
    )
    assert len(placed) == 1


def test_placements_no_center_only_ring(stub_loader):
    """center=None → 只有 ring；對應 case C 變體 (顯示 ring 不顯示 center icon)."""
    ring = [stub_loader(c) for c in "臨兵鬥者"]
    placed = compute_mandala_placements(
        None, ring, cx=100, cy=100, r_total=70,
        char_size_center_mm=24, char_size_ring_mm=10,
    )
    assert len(placed) == 4


# ---------------------------------------------------------------------------
# render_mandala_svg — full pipeline
# ---------------------------------------------------------------------------


def test_render_default_case_b(stub_loader):
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        size_mm=140, page_width_mm=210, page_height_mm=210,
    )
    assert info["placed_count"] == 10
    assert info["missing_count"] == 0
    assert info["n_fold"] == 9
    assert info["has_center_char"] is True
    assert "<svg" in svg and "</svg>" in svg
    # mandala band 有 9 個 circles (5b r5: halos 也是 circles，要分開算)
    mandala_block_start = svg.index('class="mandala"')
    mandala_block_end = svg.index('</g>', mandala_block_start)
    mandala_block = svg[mandala_block_start:mandala_block_end]
    assert mandala_block.count("<circle") == 9


def test_render_show_chars_off(stub_loader):
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        show_chars=False,
    )
    assert 'class="chars"' not in svg
    assert 'class="char-halos"' not in svg  # 字關時 halo 也省
    assert info["placed_count"] == 0
    # mandala band 9 圓還在
    mandala_block_start = svg.index('class="mandala"')
    mandala_block_end = svg.index('</g>', mandala_block_start)
    assert svg[mandala_block_start:mandala_block_end].count("<circle") == 9


def test_render_show_mandala_off(stub_loader):
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        show_mandala=False,
    )
    # No mandala circles; chars still placed (10 = center + 9 ring)
    assert svg.count('<circle') == 0
    assert info["placed_count"] == 10


def test_render_n_fold_override(stub_loader):
    """n_fold 可獨立於字環字數設定（例如字環 9 字、mandala 12-fold）."""
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        n_fold=12,
    )
    assert info["n_fold"] == 12
    assert info["ring_chars_count"] == 9
    # mandala band 12 圓
    mandala_block_start = svg.index('class="mandala"')
    mandala_block_end = svg.index('</g>', mandala_block_start)
    assert svg[mandala_block_start:mandala_block_end].count("<circle") == 12


def test_render_protect_halos_emitted_by_default(stub_loader):
    """Phase 5b r5: protect_chars 預設 ON → 有 char-halos group + N+1 個白圓
    （center + ring N 個）插在 mandala 跟 chars 中間。"""
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        protect_chars=True, protect_radius_factor=0.55,
    )
    assert 'class="char-halos"' in svg
    # halo 區塊裡 fill="white" 圓
    halo_block_start = svg.index('class="char-halos"')
    halo_block_end = svg.index('</g>', halo_block_start)
    halo_block = svg[halo_block_start:halo_block_end]
    assert halo_block.count('fill="white"') == 10  # 1 center + 9 ring
    # halo 在 mandala 之後、chars 之前（z-order）
    mandala_pos = svg.index('class="mandala"')
    halo_pos = svg.index('class="char-halos"')
    chars_pos = svg.index('class="chars"')
    assert mandala_pos < halo_pos < chars_pos


def test_render_protect_halos_off(stub_loader):
    """protect_chars=False → 無 halo group。"""
    svg, _ = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        protect_chars=False,
    )
    assert 'class="char-halos"' not in svg


def test_render_halo_skipped_when_no_mandala(stub_loader):
    """show_mandala=False → 沒有 mandala 線需要擋，halo 也省略不畫。"""
    svg, _ = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        show_mandala=False, protect_chars=True,
    )
    # halo 只在 mandala 開時才需要
    assert 'class="char-halos"' not in svg


def test_render_halo_radius_scales_with_factor(stub_loader):
    """halo 半徑 = char_size × radius_factor。"""
    import re
    svg_small, _ = render_mandala_svg(
        "咒", "臨兵鬥者", stub_loader,
        char_size_ring_mm=10, protect_radius_factor=0.5,
    )
    svg_large, _ = render_mandala_svg(
        "咒", "臨兵鬥者", stub_loader,
        char_size_ring_mm=10, protect_radius_factor=0.7,
    )
    # 從 halo 區塊抓第一個非 center halo（ring char halo, size=10mm）
    def first_ring_halo_r(svg):
        block = svg[svg.index('class="char-halos"'):svg.index('</g>', svg.index('class="char-halos"'))]
        rs = [float(m) for m in re.findall(r'<circle[^>]*r="([\d.]+)"', block)]
        # 第 0 個是 center (size=24, r=24*factor)；後面是 ring chars (size=10)
        return rs[1]
    r_small = first_ring_halo_r(svg_small)
    r_large = first_ring_halo_r(svg_large)
    assert abs(r_small - 5.0) < 0.01    # 10 × 0.5
    assert abs(r_large - 7.0) < 0.01    # 10 × 0.7


def test_lotus_petal_emits_n_paths():
    """Phase 5b r6: lotus_petal_band_svg → N 個 <path> elements."""
    svg = lotus_petal_band_svg(0, 0, 50, 9)
    assert svg.count("<path") == 9
    # Each path should be quadratic bezier (M ... Q ... Q ... Z)
    assert svg.count("Q ") >= 18  # 2 Q per petal × 9 petals


def test_lotus_petal_zero_n_returns_empty():
    assert lotus_petal_band_svg(0, 0, 50, 1) == ""
    assert lotus_petal_band_svg(0, 0, 0, 9) == ""


def test_lotus_petal_radial_extent_scales_with_length_ratio():
    """length_ratio 越大 → r_outer 越遠。"""
    import re
    cx, cy, r_band, n = 0.0, 0.0, 50.0, 9
    svg_short = lotus_petal_band_svg(
        cx, cy, r_band, n, length_ratio=0.5)
    svg_long = lotus_petal_band_svg(
        cx, cy, r_band, n, length_ratio=2.0)
    # 抓第 1 個 path 的 tip point (M base Q control TIP Q control2 base Z)
    # 用 regex 抓 d 屬性的座標序列
    def tip_dist(svg):
        d = re.search(r'd="M [\d.\-]+,[\d.\-]+ Q [\d.\-]+,[\d.\-]+ ([\d.\-]+),([\d.\-]+) Q', svg).groups()
        tx, ty = float(d[0]), float(d[1])
        return math.hypot(tx - cx, ty - cy)
    assert tip_dist(svg_long) > tip_dist(svg_short)


def test_render_mandala_style_lotus(stub_loader):
    """mandala_style='lotus_petal' → mandala 區塊有 <path>，無 <circle>。"""
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        mandala_style="lotus_petal",
    )
    mandala_block_start = svg.index('class="mandala"')
    mandala_block_end = svg.index('</g>', mandala_block_start)
    block = svg[mandala_block_start:mandala_block_end]
    assert block.count("<path") == 9
    assert block.count("<circle") == 0


def test_radial_rays_emits_n_lines():
    """Phase 5b r7: radial_rays_band_svg → N 個 <line> elements."""
    svg = radial_rays_band_svg(0, 0, 50, 9)
    assert svg.count("<line") == 9


def test_radial_rays_zero_n_returns_empty():
    assert radial_rays_band_svg(0, 0, 50, 1) == ""
    assert radial_rays_band_svg(0, 0, 0, 9) == ""


def test_radial_rays_first_at_12_oclock():
    """rotation_offset_deg=-90 → 第 1 條光線 endpoints 都在 cy 上方 (y < cy)。"""
    import re
    cx, cy, r_band, n = 0.0, 0.0, 50.0, 4
    svg = radial_rays_band_svg(cx, cy, r_band, n, rotation_offset_deg=-90.0)
    m = re.search(
        r'<line x1="([\-\d.]+)" y1="([\-\d.]+)" x2="([\-\d.]+)" y2="([\-\d.]+)"',
        svg)
    assert m
    x1, y1, x2, y2 = (float(g) for g in m.groups())
    assert abs(x1 - cx) < 0.01 and abs(x2 - cx) < 0.01  # vertical line
    assert y1 < cy - 1.0 and y2 < cy - 1.0              # both above center


def test_render_mandala_style_radial_rays(stub_loader):
    """mandala_style='radial_rays' → mandala 區塊有 <line>，無 circle/path。"""
    svg, _ = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        mandala_style="radial_rays",
    )
    mandala_block_start = svg.index('class="mandala"')
    mandala_block_end = svg.index('</g>', mandala_block_start)
    block = svg[mandala_block_start:mandala_block_end]
    assert block.count("<line") == 9
    assert block.count("<circle") == 0
    assert block.count("<path") == 0


def test_render_mandala_style_arcs_default(stub_loader):
    """default mandala_style='interlocking_arcs' → mandala 區塊全 <circle>，無 <path>。"""
    svg, _ = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
    )
    mandala_block_start = svg.index('class="mandala"')
    mandala_block_end = svg.index('</g>', mandala_block_start)
    block = svg[mandala_block_start:mandala_block_end]
    assert block.count("<circle") == 9
    assert block.count("<path") == 0


def test_compute_r_ring_from_spacing_default():
    """Phase 5b r8: 字距 = 2 字身, center 24mm + ring 10mm。
    r_ring = 2 × 10 + (24 + 10) / 2 = 20 + 17 = 37mm."""
    r = compute_r_ring_from_spacing(24, 10, 2.0)
    assert abs(r - 37.0) < 0.01


def test_compute_r_ring_from_spacing_minimum():
    """字距 = 1 (最緊湊)：r_ring = 10 + 17 = 27mm。"""
    r = compute_r_ring_from_spacing(24, 10, 1.0)
    assert abs(r - 27.0) < 0.01


def test_compute_layout_geometry_freeform():
    r_band, off = compute_layout_geometry(
        "freeform", r_ring=37, r_total=70, r_band_ratio=0.78, n=9)
    assert abs(r_band - 70 * 0.78) < 0.01
    assert off == 0.0


def test_compute_layout_geometry_vesica():
    """vesica: r_band = r_ring / cos(π/N), offset = π/N → degrees 180/N。"""
    r_band, off = compute_layout_geometry(
        "vesica", r_ring=37, r_total=70, r_band_ratio=0.78, n=9)
    assert abs(r_band - 37 / math.cos(math.pi / 9)) < 0.01
    assert abs(off - 20.0) < 0.01  # 180/9 = 20


def test_compute_layout_geometry_inscribed():
    """inscribed: r_band = r_ring (圓心 = 字位置), offset = 0。"""
    r_band, off = compute_layout_geometry(
        "inscribed", r_ring=37, r_total=70, r_band_ratio=0.78, n=9)
    assert abs(r_band - 37) < 0.01
    assert off == 0.0


def test_render_scheme_inscribed_arcs(stub_loader):
    """inscribed + arcs：圓心在字位置（=字環半徑 r_ring），半徑 = char_size × pad。"""
    import re
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        composition_scheme="inscribed",
        char_size_ring_mm=10, inscribed_padding_factor=0.7,
    )
    assert info["composition_scheme"] == "inscribed"
    assert abs(info["r_ring_mm"] - 37.0) < 0.1
    assert abs(info["r_band_mm"] - 37.0) < 0.1  # inscribed: r_band = r_ring
    # mandala 圓半徑 = 10 × 0.7 = 7
    block = svg[svg.index('class="mandala"'):svg.index('</g>', svg.index('class="mandala"'))]
    rs = [float(m) for m in re.findall(r'<circle[^>]*r="([\d.]+)"', block)]
    assert all(abs(r - 7.0) < 0.01 for r in rs), f"all circles should be r=7, got {rs}"


def test_render_scheme_vesica_arcs(stub_loader):
    """vesica + arcs：r_band = r_ring / cos(π/N)，offset 角度 = π/N。"""
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        composition_scheme="vesica",
    )
    assert info["composition_scheme"] == "vesica"
    expected_r_band = 37.0 / math.cos(math.pi / 9)
    assert abs(info["r_band_mm"] - expected_r_band) < 0.1


def test_render_scheme_freeform_backward_compat(stub_loader):
    """freeform: 維持 r4-r7 行為（r_ring = r_total × r_ring_ratio）。"""
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        composition_scheme="freeform",
        size_mm=140, r_ring_ratio=0.45, r_band_ratio=0.78,
    )
    assert info["composition_scheme"] == "freeform"
    assert abs(info["r_ring_mm"] - 31.5) < 0.1   # 70 × 0.45
    assert abs(info["r_band_mm"] - 54.6) < 0.1   # 70 × 0.78


def test_render_char_spacing_scales_r_ring(stub_loader):
    """字距增大 → r_ring 增大、r_band 跟著外推。"""
    _, info_2 = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        composition_scheme="vesica", char_spacing=2.0,
    )
    _, info_3 = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        composition_scheme="vesica", char_spacing=3.0,
    )
    assert info_3["r_ring_mm"] > info_2["r_ring_mm"]
    assert info_3["r_band_mm"] > info_2["r_band_mm"]


def test_max_safe_char_arcs_vesica_shrinks():
    """Phase 5b r9: arcs+vesica overlap=1.25 → clearance = r_ring·tan(π/N)·0.25。
    char_size 10 應 shrink 到 ≈ 5.7（2 × 0.85 × 3.37）。"""
    safe = max_safe_char_size_ring(
        "vesica", "interlocking_arcs",
        r_ring=37, r_band=39.37, n=9, char_size_ring_mm=10.0,
        overlap_ratio=1.25, margin=0.85,
    )
    expected = 2.0 * 0.85 * 37.0 * math.tan(math.pi / 9) * 0.25
    assert abs(safe - expected) < 0.01


def test_max_safe_char_arcs_vesica_no_shrink_when_small():
    """char_size 已經夠小 → 不放大。"""
    safe = max_safe_char_size_ring(
        "vesica", "interlocking_arcs",
        r_ring=37, r_band=39.37, n=9, char_size_ring_mm=3.0,
        overlap_ratio=1.25, margin=0.85,
    )
    assert safe == 3.0


def test_max_safe_char_lotus_inscribed_shrinks():
    """lotus+inscribed → 字 bbox 角落不超出瓣。"""
    safe = max_safe_char_size_ring(
        "inscribed", "lotus_petal",
        r_ring=37, r_band=37, n=9, char_size_ring_mm=10.0,
        lotus_length_ratio=1.25, lotus_width_ratio=0.6, margin=0.85,
    )
    assert safe < 10.0
    assert safe > 5.0  # 不應 shrink 過頭


def test_max_safe_char_arcs_inscribed_no_shrink():
    """arcs+inscribed: 圓半徑由 char_size 決定，不需 shrink。"""
    safe = max_safe_char_size_ring(
        "inscribed", "interlocking_arcs",
        r_ring=37, r_band=37, n=9, char_size_ring_mm=10.0,
    )
    assert safe == 10.0


def test_render_auto_shrink_reports_in_info(stub_loader):
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        composition_scheme="vesica", mandala_style="interlocking_arcs",
        char_size_ring_mm=10.0, auto_shrink_chars=True,
    )
    assert info["char_size_ring_original_mm"] == 10.0
    assert info["char_size_ring_effective_mm"] < 10.0
    assert info["char_shrunk"] is True


def test_render_auto_shrink_off_keeps_size(stub_loader):
    _, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        composition_scheme="vesica", mandala_style="interlocking_arcs",
        char_size_ring_mm=10.0, auto_shrink_chars=False,
    )
    assert info["char_size_ring_effective_mm"] == 10.0
    assert info["char_shrunk"] is False


def test_extra_layer_arcs_dispatch():
    """Phase 5b r10: layer dict with style=interlocking_arcs → emits <circle>."""
    svg = render_extra_layer_svg(100, 100, 70, {
        "style": "interlocking_arcs", "n_fold": 18, "r_ratio": 0.95,
        "overlap_ratio": 1.4,
    })
    assert svg.count("<circle") == 18


def test_extra_layer_lotus_dispatch():
    svg = render_extra_layer_svg(100, 100, 70, {
        "style": "lotus_petal", "n_fold": 12, "r_ratio": 0.95,
        "lotus_length_ratio": 0.4, "lotus_width_ratio": 0.5,
    })
    assert svg.count("<path") == 12


def test_extra_layer_rays_dispatch():
    svg = render_extra_layer_svg(100, 100, 70, {
        "style": "radial_rays", "n_fold": 36, "r_ratio": 0.30,
        "rays_length_ratio": 0.8,
    })
    assert svg.count("<line") == 36


def test_extra_layer_default_n_fallback():
    """layer dict 沒指定 n_fold → 用 default_n。"""
    svg = render_extra_layer_svg(100, 100, 70, {
        "style": "interlocking_arcs",
    }, default_n=7)
    assert svg.count("<circle") == 7


def test_render_with_two_extra_layers(stub_loader):
    """主 mandala + 外層 + 內層 → 3 個 mandala 層級 element。"""
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        composition_scheme="vesica",
        extra_layers=[
            {"style": "lotus_petal", "n_fold": 18, "r_ratio": 0.95,
             "lotus_length_ratio": 0.4, "lotus_width_ratio": 0.5},
            {"style": "radial_rays", "n_fold": 36, "r_ratio": 0.30,
             "rays_length_ratio": 0.8},
        ],
    )
    assert info["extra_layers_count"] == 2
    # main mandala block 還在
    assert 'class="mandala"' in svg
    # extra layers wrapper
    assert 'class="extra-layers"' in svg
    # 外層 lotus 18 paths
    assert svg.count('<path d="M ') >= 18  # 主 lotus 不會走 path（默認 arcs），所以 path 來自外層
    # 內層 rays 36 lines
    assert svg.count("<line") == 36


def test_render_extra_layers_skip_invalid(stub_loader):
    """壞 layer (非 dict / 缺 keys) 應該跳過不炸。"""
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        extra_layers=[
            "not a dict",
            42,
            None,
            {"style": "interlocking_arcs", "n_fold": 18, "r_ratio": 0.95},
        ],
    )
    # extra_layers_count counts ALL passed (good or bad)
    assert info["extra_layers_count"] == 4
    # 但只有 1 個有效 layer 渲染出來
    assert 'data-idx="3"' in svg


def test_render_no_extra_layers_default(stub_loader):
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
    )
    assert info["extra_layers_count"] == 0
    assert 'class="extra-layers"' not in svg


def test_dots_band_emits_n_filled_circles():
    """Phase 5b r11: dots → N 個 fill 實心圓 (non-stroke)。"""
    svg = dots_band_svg(0, 0, 50, 36, dot_radius_mm=1.5)
    assert svg.count("<circle") == 36
    assert svg.count('fill="#222"') == 36
    assert svg.count("stroke=\"none\"") == 36


def test_triangles_band_emits_n_polygons():
    svg = triangles_band_svg(0, 0, 50, 12, pointing="outward")
    assert svg.count("<polygon") == 12
    # polygon 有 3 個座標點 → 2 個空格
    import re
    first_pts = re.search(r'<polygon points="([^"]+)"', svg).group(1)
    assert len(first_pts.split(" ")) == 3


def test_triangles_pointing_inward_vs_outward():
    """outward: apex 半徑更大；inward: apex 半徑更小。"""
    import re
    out = triangles_band_svg(0, 0, 50, 6, length_ratio=1.0, pointing="outward")
    inn = triangles_band_svg(0, 0, 50, 6, length_ratio=1.0, pointing="inward")
    # 抓第一個 polygon 第一個點（apex）的 x,y
    def first_apex_dist(svg):
        pts = re.search(r'<polygon points="([^"]+)"', svg).group(1)
        ax, ay = map(float, pts.split(" ")[0].split(","))
        return (ax * ax + ay * ay) ** 0.5
    assert first_apex_dist(out) > first_apex_dist(inn)


def test_wave_band_emits_polyline():
    svg = wave_band_svg(0, 0, 50, 12, amplitude_ratio=0.05)
    assert svg.count("<polyline") == 1
    # 12 wave × 24 samples + 1 = 289 點 (預設 samples_per_wave=24)
    import re
    pts = re.search(r'<polyline points="([^"]+)"', svg).group(1)
    n_points = len(pts.strip().split(" "))
    assert n_points >= 12 * 4  # 至少有合理樣本數


def test_zigzag_band_alternates_peak_valley():
    """齒高 alternation: 偶數 idx 在 r+h、奇數 idx 在 r-h。"""
    import re
    svg = zigzag_band_svg(0, 0, 50, 6, tooth_height_ratio=0.1)
    # 12 vertices + 1 closing = 13 points
    pts = re.search(r'<polyline points="([^"]+)"', svg).group(1).split(" ")
    assert len(pts) == 13
    # 第 0 個 vertex 應在 12 o'clock + r+h = 半徑 55
    p0x, p0y = map(float, pts[0].split(","))
    r0 = (p0x * p0x + p0y * p0y) ** 0.5
    assert abs(r0 - 55.0) < 0.5  # peak r = 50 + 5
    # 第 1 個 vertex 在 valley
    p1x, p1y = map(float, pts[1].split(","))
    r1 = (p1x * p1x + p1y * p1y) ** 0.5
    assert abs(r1 - 45.0) < 0.5  # valley r = 50 - 5


def test_extra_layer_dots_dispatch():
    svg = render_extra_layer_svg(100, 100, 70, {
        "style": "dots", "n_fold": 24, "r_ratio": 0.95, "dot_radius_mm": 0.8,
    })
    assert svg.count("<circle") == 24
    assert "stroke=\"none\"" in svg


def test_extra_layer_triangles_dispatch():
    svg = render_extra_layer_svg(100, 100, 70, {
        "style": "triangles", "n_fold": 8, "r_ratio": 0.95,
        "length_ratio": 0.5, "width_ratio": 0.5, "pointing": "outward",
    })
    assert svg.count("<polygon") == 8


def test_extra_layer_wave_dispatch():
    svg = render_extra_layer_svg(100, 100, 70, {
        "style": "wave", "n_fold": 18, "r_ratio": 0.95, "amplitude_ratio": 0.04,
    })
    assert "<polyline" in svg


def test_extra_layer_zigzag_dispatch():
    svg = render_extra_layer_svg(100, 100, 70, {
        "style": "zigzag", "n_fold": 36, "r_ratio": 0.95,
        "tooth_height_ratio": 0.04,
    })
    assert "<polyline" in svg


def test_preset_registry_has_kuji_in():
    """Phase 5b r12: kuji_in (九字真言) 是預設首個 preset。"""
    assert "kuji_in" in MANDALA_PRESETS
    p = get_mandala_preset("kuji_in")
    assert p is not None
    assert p["name"] == "九字真言"
    assert p["config"]["composition_scheme"] == "vesica"


def test_preset_unknown_returns_none():
    assert get_mandala_preset("not_a_real_preset") is None


def test_list_mandala_presets_keys_complete():
    presets = list_mandala_presets()
    keys = [p["key"] for p in presets]
    assert "kuji_in" in keys
    assert "lotus_throne" in keys
    assert "dharma_wheel" in keys
    assert "flame_seal" in keys
    assert "minimal" in keys
    # 所有 entry 都有 name + description + config
    for p in presets:
        assert all(k in p for k in ("key", "name", "description", "config"))


def test_each_preset_renders_without_error(stub_loader):
    """每個 preset 用 stub loader 都能 render 成功（config 合法性測試）。"""
    presets = list_mandala_presets()
    for p in presets:
        cfg = p["config"]
        kwargs = {
            "size_mm": 140, "page_width_mm": 210, "page_height_mm": 210,
            "mandala_style": cfg.get("mandala_style", "interlocking_arcs"),
            "composition_scheme": cfg.get("composition_scheme", "vesica"),
            "char_spacing": cfg.get("char_spacing", 2.0),
            "auto_shrink_chars": cfg.get("auto_shrink_chars", True),
            "extra_layers": cfg.get("extra_layers", []),
        }
        for opt in ("overlap_ratio", "lotus_length_ratio", "lotus_width_ratio",
                    "rays_length_ratio", "inscribed_padding_factor"):
            if opt in cfg:
                kwargs[opt] = cfg[opt]
        # Test 用 stub loader 即可（preset 不依賴特定字符）
        svg, info = render_mandala_svg(
            cfg.get("center_text", "咒"),
            cfg.get("ring_text", "臨兵鬥者皆陣列在前"),
            stub_loader, **kwargs,
        )
        assert "<svg" in svg
        assert info["composition_scheme"] == cfg.get("composition_scheme", "vesica")
        assert info["extra_layers_count"] == len(cfg.get("extra_layers", []))


def test_preset_api_endpoint_returns_list():
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    c = TestClient(create_app())
    r = c.get("/api/mandala/presets")
    assert r.status_code == 200
    data = r.json()
    assert "presets" in data
    keys = [p["key"] for p in data["presets"]]
    assert "kuji_in" in keys


def test_spiral_band_emits_n_polylines():
    """Phase 5b r13: N=9 → 9 條 <polyline>（每 arm 1 條）。"""
    svg = spiral_band_svg(0, 0, 50, 9)
    assert svg.count("<polyline") == 9


def test_spiral_band_zero_n_returns_empty():
    assert spiral_band_svg(0, 0, 50, 0) == ""
    assert spiral_band_svg(0, 0, 0, 9) == ""


def test_spiral_cw_vs_ccw_produce_different_endpoints():
    """spin_turns=1.0 跟 direction 切換 → 終點 phi 對稱反轉。"""
    import re
    cw_svg = spiral_band_svg(
        0, 0, 50, 1, length_ratio=1.0, spin_turns=1.0,
        direction="cw", samples_per_arm=4, rotation_offset_deg=0.0)
    ccw_svg = spiral_band_svg(
        0, 0, 50, 1, length_ratio=1.0, spin_turns=1.0,
        direction="ccw", samples_per_arm=4, rotation_offset_deg=0.0)
    # 抓最後 1 點（spiral 終點）— polyline 點清單最後一個
    def last_point(svg):
        pts = re.search(r'<polyline points="([^"]+)"', svg).group(1).split(" ")
        return tuple(float(c) for c in pts[-1].split(","))
    cw_last = last_point(cw_svg)
    ccw_last = last_point(ccw_svg)
    # cw / ccw spin 完整 1 圈，終點應該回到起點附近（兩者非常接近）
    # 但中間軌跡不同，所以中段點不同。我們檢查 cw vs ccw 第 1 個中段點 y 符號相反
    def mid_y(svg):
        pts = re.search(r'<polyline points="([^"]+)"', svg).group(1).split(" ")
        # 第 1 個點（k=1, 1/4 完成度）
        return float(pts[1].split(",")[1])
    assert (mid_y(cw_svg) - 0) * (mid_y(ccw_svg) - 0) < 0  # y 符號相反


def test_spiral_zero_spin_degenerates_to_radial():
    """spin_turns=0 → 直線（degenerate）。每 polyline 點都在同 angle。"""
    import re
    svg = spiral_band_svg(
        0, 0, 50, 1, length_ratio=1.0, spin_turns=0.0,
        samples_per_arm=8, rotation_offset_deg=-90.0)  # 12 o'clock
    pts_str = re.search(r'<polyline points="([^"]+)"', svg).group(1).split(" ")
    # 全部點 x ≈ 0 (12 o'clock 軸)
    for p in pts_str:
        x = float(p.split(",")[0])
        assert abs(x) < 0.01


def test_extra_layer_spiral_dispatch():
    svg = render_extra_layer_svg(100, 100, 70, {
        "style": "spiral", "n_fold": 9, "r_ratio": 0.78,
        "length_ratio": 1.25, "spin_turns": 0.5, "direction": "cw",
    })
    assert svg.count("<polyline") == 9


def test_render_with_many_extra_layers(stub_loader):
    """Phase 5b r14 regression: dynamic UI 可加任意層 — 測 5 層極端 case。"""
    layers = [
        {"style": "interlocking_arcs", "n_fold": 24, "r_ratio": 1.0,
         "overlap_ratio": 1.4},
        {"style": "spiral", "n_fold": 9, "r_ratio": 0.85,
         "length_ratio": 0.4, "spin_turns": 0.5, "direction": "cw"},
        {"style": "lotus_petal", "n_fold": 18, "r_ratio": 0.65,
         "lotus_length_ratio": 0.3, "lotus_width_ratio": 0.4},
        {"style": "triangles", "n_fold": 12, "r_ratio": 0.40,
         "length_ratio": 0.3, "width_ratio": 0.5, "pointing": "inward"},
        {"style": "dots", "n_fold": 8, "r_ratio": 0.18,
         "dot_radius_mm": 1.5},
    ]
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        composition_scheme="vesica",
        extra_layers=layers,
    )
    assert info["extra_layers_count"] == 5
    # 5 個 extra-layer wrapper
    assert svg.count('class="extra-layer"') == 5
    # 各 layer 對應 SVG element
    extras_block_start = svg.index('class="extra-layers"')
    extras_block_end = svg.index('</g></g>',
                                  extras_block_start)  # 收尾 (extra-layers + 最後一個 extra-layer)
    block = svg[extras_block_start:]
    assert block.count('data-style="interlocking_arcs"') >= 1
    assert block.count('data-style="spiral"') >= 1
    assert block.count('data-style="lotus_petal"') >= 1
    assert block.count('data-style="triangles"') >= 1
    assert block.count('data-style="dots"') >= 1


def test_center_type_char_default_backward_compat(stub_loader):
    """Phase 5b r15: 預設 center_type='char' → 跟 r4-r14 行為一致。"""
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
    )
    assert info["center_type"] == "char"
    assert info["has_center_char"] is True
    assert info["has_center_icon"] is False
    assert 'class="center-icon"' not in svg


def test_center_type_icon_emits_center_icon_block(stub_loader):
    """Case C: center_type='icon' → SVG 含 center-icon block，無中心字。"""
    svg, info = render_mandala_svg(
        "咒",  # 雖然有 center_text 但被 icon 覆蓋
        "臨兵鬥者皆陣列在前", stub_loader,
        center_type="icon",
        center_icon_style="lotus_petal",
        center_icon_n=8,
        center_icon_size_mm=14,
    )
    assert info["center_type"] == "icon"
    assert info["has_center_char"] is False  # 不載入字
    assert info["has_center_icon"] is True
    assert 'class="center-icon"' in svg
    # icon 用 lotus → 8 個 path
    icon_block_start = svg.index('class="center-icon"')
    icon_block_end = svg.index('</g>', icon_block_start)
    block = svg[icon_block_start:icon_block_end]
    assert block.count("<path") == 8


def test_center_type_empty_no_center(stub_loader):
    """center_type='empty' → 無中心字也無 icon。"""
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        center_type="empty",
    )
    assert info["center_type"] == "empty"
    assert info["has_center_char"] is False
    assert info["has_center_icon"] is False
    assert 'class="center-icon"' not in svg


def test_case_a_char_no_ring_renders_main_mandala(stub_loader):
    """Case A: 字中心 + 無字環 → mandala 仍 render（default N=8 fallback）。"""
    svg, info = render_mandala_svg(
        "咒", "", stub_loader,
        center_type="char",
    )
    # ring chars = 0
    assert info["ring_chars_count"] == 0
    # 但 N 應該 fallback 到 8（避免 vesica n=2 退化）
    assert info["n_fold"] == 8
    # main mandala band 仍渲染
    assert 'class="mandala"' in svg


def test_center_icon_style_dispatch(stub_loader):
    """center_icon_style 切換 → 對應 primitive 渲染。"""
    for style, marker in [
        ("interlocking_arcs", "<circle"),
        ("radial_rays", "<line"),
        ("dots", "<circle"),
        ("triangles", "<polygon"),
    ]:
        svg, _ = render_mandala_svg(
            "", "臨兵鬥者皆陣列在前", stub_loader,
            center_type="icon",
            center_icon_style=style,
            center_icon_n=8,
            center_icon_size_mm=10,
        )
        # icon block 應該有對應 primitive marker
        icon_start = svg.index('class="center-icon"')
        icon_end = svg.index('</g>', icon_start)
        assert marker in svg[icon_start:icon_end], f"{style}: missing {marker}"


def test_squares_band_emits_n_polygons():
    """Phase 5b r16: squares → N 個 polygon (4 點/方形)。"""
    svg = squares_band_svg(0, 0, 50, 12)
    assert svg.count("<polygon") == 12
    # 每 polygon 4 個點 → 3 個空格分隔
    import re
    pts = re.search(r'<polygon points="([^"]+)"', svg).group(1).split(" ")
    assert len(pts) == 4


def test_squares_radial_vs_diamond():
    """radial 跟 diamond alignment 產生不同 polygon 角點分布。"""
    import re
    rad = squares_band_svg(0, 0, 50, 4, length_ratio=1.0,
                            rotation_alignment="radial")
    dia = squares_band_svg(0, 0, 50, 4, length_ratio=1.0,
                            rotation_alignment="diamond")
    # 兩個結果不同（角點座標應該不一樣）
    assert rad != dia


def test_hearts_band_emits_n_paths_with_cubic():
    """hearts → N 個 path，內含 cubic bezier (C 命令)。"""
    svg = hearts_band_svg(0, 0, 50, 8)
    assert svg.count("<path") == 8
    assert "C " in svg  # cubic bezier 標記


def test_hearts_pointing_inward_vs_outward_rotation_differs():
    """outward 跟 inward 的 SVG transform rotate 角度應該差 180°。"""
    out = hearts_band_svg(0, 0, 50, 4, pointing="outward")
    inn = hearts_band_svg(0, 0, 50, 4, pointing="inward")
    assert out != inn


def test_teardrops_band_emits_n_paths():
    svg = teardrops_band_svg(0, 0, 50, 12)
    assert svg.count("<path") == 12
    assert "C " in svg


def test_leaves_band_with_vein_includes_extra_line():
    """with_vein=True → path 含 base→tip 直線 (M ... L ...)。"""
    svg = leaves_band_svg(0, 0, 50, 6, with_vein=True)
    # path d 含 "L " 表示直線（vein）
    assert " L " in svg


def test_leaves_band_without_vein():
    svg = leaves_band_svg(0, 0, 50, 6, with_vein=False)
    # 不含 L 命令（純 quadratic bezier 葉形）
    assert " L " not in svg


def test_extra_layer_dispatches_4_new_primitives():
    """5b r16: 新 4 primitive 都能透過 dispatcher render。"""
    for style, marker, count in [
        ("squares", "<polygon", 9),
        ("hearts", "<path", 9),
        ("teardrops", "<path", 9),
        ("leaves", "<path", 9),
    ]:
        svg = render_extra_layer_svg(100, 100, 70, {
            "style": style, "n_fold": 9, "r_ratio": 0.95,
        })
        assert svg.count(marker) >= count, f"{style}: expect ≥{count} {marker}"


def test_clouds_band_emits_3n_circles():
    """Phase 5b r17: 每 cloud = 3 個 overlapping circles → 9 cloud × 3 = 27 圓。"""
    svg = clouds_band_svg(0, 0, 50, 9)
    assert svg.count("<circle") == 27


def test_clouds_band_zero_n_returns_empty():
    assert clouds_band_svg(0, 0, 50, 0) == ""
    assert clouds_band_svg(0, 0, 0, 9) == ""


def test_clouds_pointing_outward_vs_inward():
    """outward 跟 inward 中央 lobe 位置應該不同（outward 朝外，inward 朝內）。"""
    out_svg = clouds_band_svg(0, 0, 50, 4, pointing="outward",
                               rotation_offset_deg=-90.0)
    in_svg = clouds_band_svg(0, 0, 50, 4, pointing="inward",
                              rotation_offset_deg=-90.0)
    assert out_svg != in_svg


def test_extra_layer_clouds_dispatch():
    svg = render_extra_layer_svg(100, 100, 70, {
        "style": "clouds", "n_fold": 8, "r_ratio": 0.95,
        "length_ratio": 1.0, "lobe_radius_ratio": 0.45,
    })
    assert svg.count("<circle") == 24  # 8 cloud × 3 lobe


def test_auspicious_clouds_preset_exists():
    """5b r17: 祥雲 preset 加入。"""
    p = get_mandala_preset("auspicious_clouds")
    assert p is not None
    assert p["name"] == "祥雲"
    # 包 cloud extras
    cloud_layers = [l for l in p["config"]["extra_layers"]
                    if l["style"] == "clouds"]
    assert len(cloud_layers) == 2  # 內外各 1 cloud layer


def test_render_include_background_default_white_rect(stub_loader):
    """Phase 5b r18: include_background=True (default) → SVG 含白底 rect。"""
    svg, _ = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
    )
    assert 'fill="white"' in svg


def test_render_include_background_false_no_rect(stub_loader):
    """include_background=False → 透明背景，無白底 rect。"""
    svg, _ = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        include_background=False,
    )
    # 第一個 SVG element 不應該是白底 rect
    # 找 SVG 開頭幾百字符檢查
    head = svg[:500]
    assert '<rect x="0" y="0"' not in head or 'fill="white"' not in head


def test_api_format_png_returns_png_bytes():
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    c = TestClient(create_app())
    r = c.get("/api/mandala", params={
        "center_text": "咒", "ring_text": "臨兵鬥者皆陣列在前",
        "format": "png", "png_size_px": 512,
    })
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    # PNG magic bytes: 89 50 4E 47 0D 0A 1A 0A
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_api_format_png_transparent_returns_rgba():
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    c = TestClient(create_app())
    r = c.get("/api/mandala", params={
        "center_text": "咒", "ring_text": "臨兵鬥者皆陣列在前",
        "format": "png_transparent", "png_size_px": 256,
    })
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_api_format_pdf_returns_pdf_bytes():
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    c = TestClient(create_app())
    r = c.get("/api/mandala", params={
        "center_text": "咒", "ring_text": "臨兵鬥者皆陣列在前",
        "format": "pdf",
    })
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    # PDF magic: %PDF
    assert r.content[:4] == b"%PDF"


def test_api_format_invalid_returns_422():
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    c = TestClient(create_app())
    r = c.get("/api/mandala", params={
        "center_text": "咒", "ring_text": "臨",
        "format": "bmp",  # 不支援
    })
    assert r.status_code == 422  # FastAPI regex validation


def test_gcode_basic_structure(stub_loader):
    """Phase 5b r19: G-code 輸出有正確 header + G0/G1 序列。"""
    from stroke_order.exporters.mandala import render_mandala_gcode
    svg, _ = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        size_mm=140, page_width_mm=210, page_height_mm=210,
    )
    gcode = render_mandala_gcode(svg)
    assert "G21" in gcode  # mm units
    assert "G90" in gcode  # absolute
    assert "G0" in gcode   # travel moves
    assert "G1" in gcode   # cutting moves
    assert "F1000" in gcode  # feed rate
    assert gcode.startswith("; Mandala G-code")


def test_gcode_polyline_count_matches_primitives(stub_loader):
    """G-code 內 polyline 數量 = 主 mandala 9 圓 + extras。"""
    from stroke_order.exporters.mandala import render_mandala_gcode
    svg, _ = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        extra_layers=[
            {"style": "lotus_petal", "n_fold": 18, "r_ratio": 0.95},
            {"style": "dots", "n_fold": 24, "r_ratio": 0.30,
             "dot_radius_mm": 1.0},
        ],
    )
    gcode = render_mandala_gcode(svg)
    import re
    m = re.search(r"polylines: (\d+)", gcode)
    n_polylines = int(m.group(1)) if m else 0
    # 9 主 vesica + 18 lotus + 24 dots = 51
    assert n_polylines == 51


def test_gcode_skip_chars_and_halos(stub_loader):
    """字 outlines 跟 halos 不應出現在 G-code。"""
    from stroke_order.exporters.mandala import render_mandala_gcode
    svg, _ = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        protect_chars=True,  # halo on
    )
    gcode = render_mandala_gcode(svg)
    # 主 mandala = 9 圓 (vesica)，no chars / no halos
    import re
    m = re.search(r"polylines: (\d+)", gcode)
    n_polylines = int(m.group(1)) if m else 0
    assert n_polylines == 9  # 只有主 mandala 圓，沒 halo (10) 也沒 chars


def test_gcode_y_flip_adds_to_page_height(stub_loader):
    """flip_y=True：G-code Y = page_h - SVG y。flip + no-flip 相加 = page_h。"""
    from stroke_order.exporters.mandala import render_mandala_gcode
    svg, _ = render_mandala_svg(
        "咒", "臨兵鬥者", stub_loader,
        size_mm=100, page_width_mm=200, page_height_mm=200,
    )
    g_flip = render_mandala_gcode(svg, flip_y=True)
    g_noflip = render_mandala_gcode(svg, flip_y=False)
    import re
    def first_y(text):
        m = re.search(r"G0 X[\-\d.]+ Y([\-\d.]+) ; travel", text)
        return float(m.group(1)) if m else None
    y_flip = first_y(g_flip)
    y_noflip = first_y(g_noflip)
    assert y_flip is not None and y_noflip is not None
    assert abs((y_flip + y_noflip) - 200.0) < 0.1


def test_path_d_to_polylines_quadratic_bezier_sampling():
    """Quadratic bezier 採樣 N 點。"""
    from stroke_order.exporters.mandala import _path_d_to_polylines
    d = "M 0,0 Q 5,10 10,0 Z"
    polys = _path_d_to_polylines(d, samples_per_curve=8)
    assert len(polys) == 1
    pts = polys[0]
    # 起點 (0,0) + 8 sample + close
    assert len(pts) >= 9
    # 起點 == 終點（Z 閉合）
    assert pts[0] == pts[-1]


def test_path_d_to_polylines_cubic_bezier_sampling():
    """Cubic bezier 採樣。"""
    from stroke_order.exporters.mandala import _path_d_to_polylines
    d = "M 0,0 C 0,10 10,10 10,0 Z"
    polys = _path_d_to_polylines(d, samples_per_curve=8)
    assert len(polys) == 1
    pts = polys[0]
    assert len(pts) >= 9


def test_api_format_gcode_returns_text():
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    c = TestClient(create_app())
    r = c.get("/api/mandala", params={
        "center_text": "咒", "ring_text": "臨兵鬥者皆陣列在前",
        "format": "gcode",
    })
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert r.text.startswith("; Mandala G-code")


def test_ten_virtues_preset_exists():
    """Phase 5b r20: 十字真言 preset (no center text, 10 美德字環)。"""
    p = get_mandala_preset("ten_virtues")
    assert p is not None
    assert p["name"] == "十字真言"
    cfg = p["config"]
    assert cfg["center_type"] == "icon"  # 無中心字 → 用 icon 取代
    assert cfg["center_text"] == ""
    assert cfg["ring_text"] == "真誠信實愛和恕禮善同"
    assert len(cfg["ring_text"]) == 10  # 10 字
    assert cfg["center_icon_n"] == 10   # icon N 對齊 ring N


def test_ten_virtues_renders_with_no_center_char(stub_loader):
    """十字真言 render → 中心 icon (no char) + 10 ring chars + extras。"""
    p = get_mandala_preset("ten_virtues")
    cfg = p["config"]
    svg, info = render_mandala_svg(
        cfg["center_text"], cfg["ring_text"], stub_loader,
        composition_scheme=cfg["composition_scheme"],
        char_spacing=cfg["char_spacing"],
        center_type=cfg["center_type"],
        center_icon_style=cfg["center_icon_style"],
        center_icon_n=cfg["center_icon_n"],
        center_icon_size_mm=cfg["center_icon_size_mm"],
        extra_layers=cfg["extra_layers"],
    )
    assert info["center_type"] == "icon"
    assert info["has_center_char"] is False  # 無中心字
    assert info["has_center_icon"] is True
    assert info["ring_chars_count"] == 10
    assert info["n_fold"] == 10
    assert 'class="center-icon"' in svg


def test_extra_layer_visible_false_skipped():
    """Phase 5b r21: layer dict 'visible': False → render_extra_layer_svg 回空。"""
    svg = render_extra_layer_svg(100, 100, 70, {
        "style": "interlocking_arcs", "n_fold": 9, "r_ratio": 0.95,
        "visible": False,
    })
    assert svg == ""


def test_extra_layer_visible_true_renders():
    """visible=True (預設) → 正常渲染。"""
    svg_default = render_extra_layer_svg(100, 100, 70, {
        "style": "interlocking_arcs", "n_fold": 9, "r_ratio": 0.95,
    })
    svg_explicit = render_extra_layer_svg(100, 100, 70, {
        "style": "interlocking_arcs", "n_fold": 9, "r_ratio": 0.95,
        "visible": True,
    })
    assert svg_default == svg_explicit
    assert svg_default.count("<circle") == 9


def test_render_with_mixed_visibility_layers(stub_loader):
    """部分 layers visible=False → 只渲染 visible=True 的層。"""
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", stub_loader,
        extra_layers=[
            {"style": "lotus_petal", "n_fold": 18, "r_ratio": 0.95},
            {"style": "dots", "n_fold": 24, "r_ratio": 0.30,
             "visible": False},  # 此層隱藏
            {"style": "radial_rays", "n_fold": 36, "r_ratio": 0.20},
        ],
    )
    # extra_layers_count 仍是 3（含隱藏的，metadata 用）
    assert info["extra_layers_count"] == 3
    # 但 SVG 內 extra-layer wrapper 只有 2 個（visible=False 那層被 skip）
    assert svg.count('class="extra-layer"') == 2
    # Style verification
    assert 'data-style="lotus_petal"' in svg
    assert 'data-style="dots"' not in svg     # 被隱藏
    assert 'data-style="radial_rays"' in svg


def test_crosses_band_emits_2n_lines():
    """Phase 5b r23: N 個十字 = 2N 條 line（每 cross 1 徑向 + 1 切向 line）。"""
    svg = crosses_band_svg(0, 0, 50, 12)
    assert svg.count("<line") == 24


def test_stars_band_emits_n_polygons_with_2k_points():
    """N=9 個星，每星 5-pointed → 10 vertex polygon。"""
    svg = stars_band_svg(0, 0, 50, 9, star_points=5)
    assert svg.count("<polygon") == 9
    import re
    pts_str = re.search(r'<polygon points="([^"]+)"', svg).group(1)
    assert len(pts_str.split()) == 10  # 2 × 5 points


def test_stars_band_6_points_yields_12_vertices():
    svg = stars_band_svg(0, 0, 50, 8, star_points=6)
    assert svg.count("<polygon") == 8
    import re
    pts_str = re.search(r'<polygon points="([^"]+)"', svg).group(1)
    assert len(pts_str.split()) == 12  # 2 × 6


def test_eyes_band_emits_path_plus_pupil():
    """每 eye = 1 path (上下 arc) + 1 circle (pupil)。"""
    svg = eyes_band_svg(0, 0, 50, 8)
    assert svg.count("<path") == 8
    # Eye 內 pupil 是實心 circle (fill 黑) 跟 mandala band circle 區別
    assert svg.count("<circle") == 8


def test_lattice_band_emits_n_paths_with_4_M():
    """每 lattice cell = 1 path (square + 2 對角線, 共 3 個 M / 起始)。"""
    svg = lattice_band_svg(0, 0, 50, 12)
    assert svg.count("<path") == 12
    # Each path 含 3 個 M（square 起點 + 2 條對角線起點）
    import re
    first_d = re.search(r'<path d="([^"]+)"', svg).group(1)
    assert first_d.count("M ") == 3


def test_extra_layer_dispatches_4_new_primitives():
    """5b r23: 4 新 primitive 全部 dispatch 成功。"""
    for style, marker, expected_count in [
        ("crosses", "<line", 18),       # 9 cross × 2 lines
        ("stars", "<polygon", 9),        # 9 star polygons
        ("eyes", "<path", 9),            # 9 eye paths (each has 2 arcs)
        ("lattice", "<path", 9),         # 9 lattice cells
    ]:
        svg = render_extra_layer_svg(100, 100, 70, {
            "style": style, "n_fold": 9, "r_ratio": 0.95,
        })
        assert svg.count(marker) >= expected_count, (
            f"{style}: expect ≥{expected_count} {marker}, got {svg.count(marker)}")


def test_render_missing_chars_reported(stub_loader):
    """Loader 回 None 的字記入 missing list."""
    def loader_mostly_none(ch):
        return None if ch in "兵者" else stub_loader(ch)
    svg, info = render_mandala_svg(
        "咒", "臨兵鬥者皆陣列在前", loader_mostly_none,
    )
    assert info["missing_count"] == 2
    assert "兵" in info["missing_chars"] and "者" in info["missing_chars"]
    assert info["ring_chars_count"] == 7  # 9 - 2 missing


# Phase 5b r25: r_mm absolute radius support — overrides r_ratio when present
def test_extra_layer_r_mm_overrides_r_ratio():
    """layer.r_mm 設定時應蓋過 r_ratio，輸出 dots 應位於 r_mm 圓周上。"""
    layer = {
        "style": "dots",
        "n_fold": 4,
        "r_mm": 25.0,           # 絕對 25mm
        "r_ratio": 0.99,        # 應被忽略（若用 r_ratio × r_total = 49.5mm）
        "dot_radius_mm": 1.0,
    }
    cx, cy, r_total = 50.0, 50.0, 50.0  # r_total=50, 4-fold → dots at 0/90/180/270 deg
    svg = render_extra_layer_svg(cx, cy, r_total, layer)
    # 4 dots → 4 個 <circle .../>
    assert svg.count("<circle") == 4
    # 第一顆 dot 應在 (cx + 25, cy) = (75, 50)，而非 (cx + 49.5, cy) = (99.5, 50)
    # 用簡易 regex 抓 cx 屬性
    import re
    cx_vals = sorted(float(m) for m in re.findall(r'cx="([\d.\-]+)"', svg))
    # 4 個 dot 在四方位：(25, 50), (50, 25), (50, 75), (75, 50) → sorted cx = 25,50,50,75
    assert cx_vals == [25.0, 50.0, 50.0, 75.0]


def test_extra_layer_r_ratio_fallback_when_no_r_mm():
    """layer 只給 r_ratio（無 r_mm）時應 fall back 到 r_ratio × r_total。"""
    layer = {
        "style": "dots",
        "n_fold": 4,
        "r_ratio": 0.5,
        "dot_radius_mm": 1.0,
    }
    cx, cy, r_total = 50.0, 50.0, 60.0  # 0.5 × 60 = 30mm
    svg = render_extra_layer_svg(cx, cy, r_total, layer)
    import re
    cx_vals = sorted(float(m) for m in re.findall(r'cx="([\d.\-]+)"', svg))
    # 4 dots 在 (cx ± 30, cy ± 30) → sorted cx = 20,50,50,80
    assert cx_vals == [20.0, 50.0, 50.0, 80.0]


def test_extra_layer_r_mm_zero_uses_minimum_radius():
    """r_mm=0 應 clamp 成 0.1（避免奇異）— layer 仍會渲染（不爆）。"""
    layer = {
        "style": "dots",
        "n_fold": 6,
        "r_mm": 0.0,
        "dot_radius_mm": 0.5,
    }
    svg = render_extra_layer_svg(50.0, 50.0, 70.0, layer)
    # 6 個 dots 全部聚在中心附近（半徑 0.1mm 圓周）— 不應 crash 或回空
    assert svg.count("<circle") == 6


def test_extra_layer_r_mm_supports_far_outside_r_total():
    """r_mm > r_total 時仍渲染（ring 10 = 100-110mm，超過小尺寸 r_total）— 不被 clamp。"""
    layer = {
        "style": "dots",
        "n_fold": 4,
        "r_mm": 105.0,
        "dot_radius_mm": 1.0,
    }
    cx, cy, r_total = 50.0, 50.0, 50.0  # r_total=50 但 r_mm=105 仍渲染
    svg = render_extra_layer_svg(cx, cy, r_total, layer)
    import re
    cx_vals = sorted(float(m) for m in re.findall(r'cx="([\d.\-]+)"', svg))
    # dots 在 (50 ± 105, 50 ± 105) → sorted = [-55, 50, 50, 155]
    assert cx_vals == [-55.0, 50.0, 50.0, 155.0]


# Phase 5b r26: 線條顏色（fill/stroke）+ G-code 按色分組

def test_layer_color_default_black():
    """layer 不給 color 時，default 黑色 (#000000)。"""
    layer = {"style": "interlocking_arcs", "n_fold": 6}
    svg = render_extra_layer_svg(50.0, 50.0, 50.0, layer)
    # 預期 stroke="#000000" 出現
    assert 'stroke="#000000"' in svg
    # 不應出現舊的 #222 default
    assert 'stroke="#222"' not in svg


def test_layer_color_custom_applied():
    """layer 帶 color → 出現在 stroke/fill 屬性。"""
    layer = {"style": "lotus_petal", "n_fold": 8, "color": "#c0392b"}
    svg = render_extra_layer_svg(50.0, 50.0, 50.0, layer)
    assert 'stroke="#c0392b"' in svg


def test_layer_color_dots_uses_fill():
    """dots primitive 用 fill_color 而非 stroke（內充實心圓）。"""
    layer = {"style": "dots", "n_fold": 4, "color": "#2980b9", "dot_radius_mm": 1.0}
    svg = render_extra_layer_svg(50.0, 50.0, 50.0, layer)
    assert 'fill="#2980b9"' in svg


def test_mandala_line_color_param(stub_loader):
    """mandala_line_color 套到主 mandala primitives stroke。"""
    svg, _ = render_mandala_svg(
        "中", "字環", stub_loader,
        mandala_line_color="#27ae60",
    )
    # 主 mandala primitives 應有綠色 stroke
    assert 'stroke="#27ae60"' in svg


def test_char_line_color_param(stub_loader):
    """char_line_color 套到中心字 + 字環的 stroke / fill。"""
    svg, _ = render_mandala_svg(
        "中", "字環", stub_loader,
        char_line_color="#e91e63",
    )
    # 字 SVG 用 fill / stroke 都用 char color
    assert ('fill="#e91e63"' in svg) or ('stroke="#e91e63"' in svg)


def test_gcode_groups_by_color(stub_loader):
    """G-code 按 color 分組：3 種顏色 → 3 個 COLOR comment 標籤。"""
    from stroke_order.exporters.mandala import render_mandala_gcode
    extra = [
        {"style": "dots", "n_fold": 4, "r_mm": 10.0, "color": "#c0392b",
         "dot_radius_mm": 1.0},
        {"style": "dots", "n_fold": 4, "r_mm": 25.0, "color": "#27ae60",
         "dot_radius_mm": 1.0},
        {"style": "dots", "n_fold": 4, "r_mm": 40.0, "color": "#2980b9",
         "dot_radius_mm": 1.0},
    ]
    svg, _ = render_mandala_svg(
        "", "", stub_loader,
        page_width_mm=200, page_height_mm=200, size_mm=180,
        extra_layers=extra, show_mandala=False, center_type="empty",
    )
    gcode = render_mandala_gcode(svg)
    # 3 個 color comment header
    assert gcode.count("; ===== COLOR:") == 3
    assert "#c0392b" in gcode
    assert "#27ae60" in gcode
    assert "#2980b9" in gcode


def test_gcode_same_color_stays_grouped(stub_loader):
    """同色 layer 不被分散，G-code 中只出現該色一個 group。"""
    from stroke_order.exporters.mandala import render_mandala_gcode
    extra = [
        {"style": "dots", "n_fold": 4, "r_mm": 10.0, "color": "#c0392b",
         "dot_radius_mm": 1.0},
        {"style": "dots", "n_fold": 4, "r_mm": 25.0, "color": "#27ae60",
         "dot_radius_mm": 1.0},
        {"style": "dots", "n_fold": 4, "r_mm": 40.0, "color": "#c0392b",
         "dot_radius_mm": 1.0},  # 又回紅色
    ]
    svg, _ = render_mandala_svg(
        "", "", stub_loader,
        page_width_mm=200, page_height_mm=200, size_mm=180,
        extra_layers=extra, show_mandala=False, center_type="empty",
    )
    gcode = render_mandala_gcode(svg)
    # 紅色 #c0392b 應該只出現一次 COLOR header（兩 layer 合併）
    red_headers = gcode.count("; ===== COLOR: #c0392b")
    assert red_headers == 1, f"expected 1 red group, got {red_headers}\n{gcode[:500]}"
    # 共 2 個 color group（紅 + 綠）
    assert gcode.count("; ===== COLOR:") == 2


def test_gcode_default_color_when_unspecified(stub_loader):
    """未指定 color 時 G-code 用 default #000000（黑），不報錯。"""
    from stroke_order.exporters.mandala import render_mandala_gcode
    extra = [
        {"style": "dots", "n_fold": 4, "r_mm": 20.0, "dot_radius_mm": 1.0},
    ]
    svg, _ = render_mandala_svg(
        "", "", stub_loader,
        page_width_mm=200, page_height_mm=200, size_mm=180,
        extra_layers=extra, show_mandala=False, center_type="empty",
    )
    gcode = render_mandala_gcode(svg)
    assert "; ===== COLOR: #000000" in gcode
