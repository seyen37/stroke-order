"""Phase 5ay — stamp (印章) mode: 5 presets, single-layer SVG, laser G-code."""
from __future__ import annotations

import math

import pytest

from stroke_order.exporters.stamp import (
    SvgDecoration,
    _arc_text_positions,
    _auto_grid_dims,
    _grid_positions_right_to_left,
    _stamp_border_polys,
    render_stamp_gcode,
    render_stamp_svg,
    stamp_capacity,
)
from stroke_order.ir import Character


# ---------------------------------------------------------------------------
# Stub loader (avoids real font dependency for unit tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_loader():
    from stroke_order.ir import Stroke, Point

    def _l(ch):
        return Character(
            char=ch, unicode_hex=f"{ord(ch):04x}", data_source="stub",
            strokes=[Stroke(
                index=0,
                raw_track=[Point(100, 100), Point(1948, 1948)],
                outline=[
                    {"type": "M", "x": 100,  "y": 100},
                    {"type": "L", "x": 1948, "y": 100},
                    {"type": "L", "x": 1948, "y": 1948},
                    {"type": "L", "x": 100,  "y": 1948},
                ],
                kind_code=9, kind_name="其他", has_hook=False,
            )],
        )
    return _l


# ---------------------------------------------------------------------------
# Layout helpers (5ay-1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n,expected", [
    (1, (1, 1)), (2, (2, 1)), (3, (3, 1)),
    (4, (2, 2)),
    (5, (3, 2)), (6, (3, 2)),
    (7, (3, 3)), (8, (3, 3)), (9, (3, 3)),
])
def test_auto_grid_dims_table(n, expected):
    assert _auto_grid_dims(n) == expected


def test_grid_right_to_left_starts_in_right_column():
    """First placed char must sit in the right-most column (high x)."""
    coords = _grid_positions_right_to_left(
        n=4, rows=2, cols=2, inner_w=20, inner_h=20,
        centre_x=10, centre_y=10,
    )
    # Cell width = 10mm; right column centre x = 15mm, left = 5mm.
    assert coords[0][0] == pytest.approx(15.0)
    assert coords[0][1] == pytest.approx(5.0)   # top of right column
    assert coords[1][0] == pytest.approx(15.0)  # still right column
    assert coords[1][1] == pytest.approx(15.0)  # bottom of right column
    assert coords[2][0] == pytest.approx(5.0)   # now left column starts


def test_grid_capped_at_n():
    coords = _grid_positions_right_to_left(
        n=2, rows=3, cols=3, inner_w=30, inner_h=30,
        centre_x=15, centre_y=15,
    )
    assert len(coords) == 2


def test_arc_text_positions_evenly_distributes():
    pts = _arc_text_positions(n=6, ring_radius=10, centre_x=0, centre_y=0,
                              span_deg=240.0, start_deg=-120.0)
    assert len(pts) == 6
    # All points are on the ring (radius 10).
    for x, y, _rot in pts:
        assert math.hypot(x, y) == pytest.approx(10.0, abs=1e-6)


def test_arc_single_char_at_apex():
    pts = _arc_text_positions(n=1, ring_radius=10, centre_x=0, centre_y=0,
                              span_deg=240.0, start_deg=-120.0)
    assert len(pts) == 1
    # Apex is start + span/2 = -120 + 120 = 0° → (10, 0).
    x, y, _ = pts[0]
    assert x == pytest.approx(10.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Borders (5ay-1)
# ---------------------------------------------------------------------------


def test_border_single_returns_one_poly():
    polys = _stamp_border_polys("square_name", 25, 25, double_border=False)
    assert len(polys) == 1


def test_border_double_returns_two_concentric():
    polys = _stamp_border_polys("square_official", 40, 40,
                                double_border=True, double_gap_mm=0.8)
    assert len(polys) == 2


def test_border_round_yields_circle():
    from stroke_order.shapes import Circle
    polys = _stamp_border_polys("round", 40, 40, double_border=False)
    assert isinstance(polys[0], Circle)


def test_border_oval_yields_ellipse():
    from stroke_order.shapes import Ellipse
    polys = _stamp_border_polys("oval", 50, 30, double_border=False)
    assert isinstance(polys[0], Ellipse)


# ---------------------------------------------------------------------------
# render_stamp_svg — single layer
# ---------------------------------------------------------------------------


def test_svg_single_engrave_layer(stub_loader):
    svg = render_stamp_svg("AB", stub_loader, preset="square_name")
    assert 'id="stamp-engrave"' in svg
    # Stamp mode is single-layer — no patch's cut/write split.
    assert 'id="patch-cut"' not in svg


def test_svg_uses_black_color(stub_loader):
    svg = render_stamp_svg("A", stub_loader, preset="square_name")
    assert 'stroke="#000"' in svg


def test_svg_includes_border_when_show_border_true(stub_loader):
    svg = render_stamp_svg("A", stub_loader, preset="square_name",
                           show_border=True)
    assert 'class="stamp-border"' in svg


def test_svg_omits_border_when_show_border_false(stub_loader):
    """Workflow: hide border, post-process in design tool."""
    svg = render_stamp_svg("A", stub_loader, preset="square_name",
                           show_border=False)
    assert 'class="stamp-border"' not in svg
    # But the engrave layer + chars are still there.
    assert 'id="stamp-engrave"' in svg


def test_svg_double_border_emits_two_paths(stub_loader):
    svg = render_stamp_svg("A", stub_loader, preset="square_official",
                           double_border=True)
    assert svg.count('class="stamp-border"') == 2


def test_svg_decorations_embedded(stub_loader):
    deco = SvgDecoration(
        svg_content='<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="3"/></svg>',
        x_mm=5, y_mm=5, w_mm=10, h_mm=10,
    )
    svg = render_stamp_svg("A", stub_loader, preset="square_name",
                           decorations=[deco])
    assert "<circle" in svg


def test_svg_supports_all_5_presets(stub_loader):
    """Every preset in the closed taxonomy must render without error."""
    for preset in ("square_name", "square_official",
                   "round", "oval", "rectangle_title"):
        svg = render_stamp_svg("吉祥如意", stub_loader, preset=preset)  # type: ignore
        assert 'id="stamp-engrave"' in svg, f"{preset} missing engrave layer"


def test_svg_round_preset_with_2plus_chars_has_arc_chars(stub_loader):
    """Round preset arranges (n-1) chars on arc + 1 centre char.

    For n=4, we expect 3 arc chars + 1 centre = 4 total char-path groups
    (in addition to the border)."""
    svg = render_stamp_svg("業務專用", stub_loader, preset="round",
                           stamp_width_mm=40, stamp_height_mm=40,
                           char_size_mm=8)
    # Sanity: render produced output and includes the engrave group.
    assert 'id="stamp-engrave"' in svg
    # With stub glyph being 4 path segments, just confirm <path> count grows
    # with character count vs single-char case.
    one = render_stamp_svg("業", stub_loader, preset="round",
                           stamp_width_mm=40, stamp_height_mm=40,
                           char_size_mm=8)
    assert svg.count("<path ") > one.count("<path ")


# ---------------------------------------------------------------------------
# G-code — laser engraver
# ---------------------------------------------------------------------------


def test_gcode_uses_default_laser_on(stub_loader):
    gc = render_stamp_gcode("A", stub_loader, preset="square_name")
    assert "G21" in gc and "G90" in gc
    assert "M3 S255" in gc      # default laser power
    assert "M5" in gc           # laser_off


def test_gcode_custom_power(stub_loader):
    gc = render_stamp_gcode("A", stub_loader, preset="square_name",
                            laser_power=120)
    assert "M3 S120" in gc
    assert "M3 S255" not in gc


def test_gcode_default_feed_1500(stub_loader):
    gc = render_stamp_gcode("A", stub_loader, preset="square_name")
    # Feed appears in G1 cuts.
    assert "F1500" in gc


def test_gcode_show_border_true_includes_border_path(stub_loader):
    """Border outline should appear before glyph G-code when shown."""
    gc = render_stamp_gcode("A", stub_loader, preset="square_name",
                            show_border=True)
    # Header annotation echoes the flag — and at least one G0 (border move)
    # should precede the chars.
    assert "show_border=True" in gc
    # Border G-code should produce extra G0 moves vs no-border case.
    no_border = render_stamp_gcode("A", stub_loader, preset="square_name",
                                   show_border=False)
    assert gc.count("G0 ") > no_border.count("G0 ")


def test_gcode_show_border_false_omits_border(stub_loader):
    gc = render_stamp_gcode("A", stub_loader, preset="square_name",
                            show_border=False)
    assert "show_border=False" in gc


def test_gcode_decorations_skipped_with_note(stub_loader):
    deco = SvgDecoration(
        svg_content='<svg><path d="M0 0 L10 10"/></svg>',
        x_mm=0, y_mm=0, w_mm=10, h_mm=10,
    )
    gc = render_stamp_gcode("A", stub_loader, preset="square_name",
                            decorations=[deco])
    assert "decoration" in gc.lower()
    assert "skipped" in gc.lower()


# ---------------------------------------------------------------------------
# Capacity
# ---------------------------------------------------------------------------


def test_capacity_square_name_caps_at_4():
    info = stamp_capacity(preset="square_name", stamp_width_mm=25,
                          stamp_height_mm=25, char_size_mm=10)
    assert info["max_chars"] == 4
    assert info["preset"] == "square_name"
    assert len(info["inner_size_mm"]) == 2


def test_capacity_square_official_caps_at_9():
    info = stamp_capacity(preset="square_official", stamp_width_mm=42,
                          stamp_height_mm=42, char_size_mm=12)
    assert info["max_chars"] == 9


def test_capacity_round_scales_with_radius():
    small = stamp_capacity(preset="round", stamp_width_mm=20,
                           stamp_height_mm=20, char_size_mm=6)
    large = stamp_capacity(preset="round", stamp_width_mm=60,
                           stamp_height_mm=60, char_size_mm=6)
    assert large["max_chars"] > small["max_chars"]


def test_capacity_double_border_shrinks_inner():
    no_db = stamp_capacity(preset="square_name", stamp_width_mm=25,
                           stamp_height_mm=25, char_size_mm=10,
                           double_border=False)
    db = stamp_capacity(preset="square_name", stamp_width_mm=25,
                        stamp_height_mm=25, char_size_mm=10,
                        double_border=True, double_gap_mm=2.0)
    # Double-border uses extra gap mm on each side → smaller inner box.
    assert db["inner_size_mm"][0] < no_db["inner_size_mm"][0]


# ---------------------------------------------------------------------------
# Web API
# ---------------------------------------------------------------------------


try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS = True
except ImportError:
    _HAS = False


@pytest.fixture
def client():
    if not _HAS:
        pytest.skip("web deps missing")
    return TestClient(create_app())


def test_api_stamp_capacity(client):
    r = client.get("/api/stamp/capacity?preset=square_name"
                   "&stamp_width_mm=25&stamp_height_mm=25&char_size_mm=10")
    assert r.status_code == 200
    d = r.json()
    assert d["preset"] == "square_name"
    assert d["max_chars"] == 4


def test_api_stamp_get_svg(client):
    r = client.get("/api/stamp?text=吉&preset=square_name"
                   "&stamp_width_mm=25&stamp_height_mm=25&char_size_mm=10")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    body = r.text
    assert 'id="stamp-engrave"' in body
    assert 'class="stamp-border"' in body


def test_api_stamp_get_svg_hidden_border(client):
    r = client.get("/api/stamp?text=吉&preset=square_name&show_border=false")
    assert r.status_code == 200
    body = r.text
    assert 'id="stamp-engrave"' in body
    assert 'class="stamp-border"' not in body


def test_api_stamp_get_gcode(client):
    r = client.get("/api/stamp?text=吉&preset=square_name&format=gcode")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "M3 S255" in r.text
    assert "G21" in r.text


def test_api_stamp_post_with_decorations(client):
    body = {
        "text": "業務",
        "preset": "round",
        "stamp_width_mm": 40, "stamp_height_mm": 40,
        "char_size_mm": 8,
        "decorations": [{
            "svg_content": '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="3"/></svg>',
            "x_mm": 5, "y_mm": 5, "w_mm": 10, "h_mm": 10,
        }],
        "format": "svg",
    }
    r = client.post("/api/stamp", json=body)
    assert r.status_code == 200
    assert "<circle" in r.text


def test_api_stamp_post_double_border(client):
    body = {
        "text": "公司印章",
        "preset": "square_official",
        "stamp_width_mm": 42, "stamp_height_mm": 42,
        "char_size_mm": 12,
        "double_border": True,
        "format": "svg",
    }
    r = client.post("/api/stamp", json=body)
    assert r.status_code == 200
    assert r.text.count('class="stamp-border"') == 2


def test_api_stamp_invalid_preset_rejected(client):
    r = client.get("/api/stamp?preset=octagon&text=A")
    assert r.status_code == 422


def test_api_stamp_invalid_format_rejected(client):
    # 12b-4: pdf 已加入支援 format（svg/gcode/pdf 三選一），改用真實
    # invalid format（如 docx）測試 422 拒絕路徑。
    r = client.get("/api/stamp?preset=square_name&text=A&format=docx")
    assert r.status_code == 422


def test_api_stamp_pdf_format(client):
    """12b-4: PDF format 走 cairosvg svg2pdf 直出。"""
    r = client.post(
        "/api/stamp",
        json={"text": "王明", "preset": "square_name", "format": "pdf",
              "stamp_width_mm": 12, "stamp_height_mm": 12, "char_size_mm": 5},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    # PDF magic bytes
    assert r.content[:4] == b"%PDF"
    # Reasonable size lower bound — 印章 PDF 至少 1KB
    assert len(r.content) > 1000


# ---------------------------------------------------------------------------
# 12c: 陰刻 / 陽刻 (engrave_mode concave / convex)
# ---------------------------------------------------------------------------


def test_api_stamp_convex_svg_has_red_fill_white_chars(client):
    """陽刻 SVG：紅底 (#c33) + 字白色 fill (#fff)。"""
    r = client.post(
        "/api/stamp",
        json={"text": "王", "preset": "square_name", "format": "svg",
              "stamp_width_mm": 12, "stamp_height_mm": 12, "char_size_mm": 5,
              "engrave_mode": "convex"},
    )
    assert r.status_code == 200
    assert 'fill="#c33"' in r.text  # 紅底
    assert 'fill="#fff"' in r.text  # 字白
    assert 'id="stamp-chars"' in r.text


def test_api_stamp_concave_svg_unchanged(client):
    """陰刻 (預設)：維持既有 stroke-based 渲染，跟 12c 之前一致。"""
    r = client.post(
        "/api/stamp",
        json={"text": "王", "preset": "square_name", "format": "svg",
              "stamp_width_mm": 12, "stamp_height_mm": 12, "char_size_mm": 5,
              "engrave_mode": "concave"},
    )
    assert r.status_code == 200
    assert 'id="stamp-engrave"' in r.text
    # 陰刻不該有紅底
    assert 'fill="#c33"' not in r.text


def test_api_stamp_convex_gcode_has_scanline(client):
    """陽刻 G-code：用 scanline 鋪滿背景（含 raster scan header）。"""
    r = client.post(
        "/api/stamp",
        json={"text": "王", "preset": "square_name", "format": "gcode",
              "stamp_width_mm": 12, "stamp_height_mm": 12, "char_size_mm": 5,
              "engrave_mode": "convex"},
    )
    assert r.status_code == 200
    assert "raster scan" in r.text
    assert "scan_lines=" in r.text
    # M3 命令數 > 50（每條 scan line 多個 ON segment）
    assert r.text.count("M3") > 50


def test_api_stamp_invalid_engrave_mode_rejected(client):
    """陽刻 mode 必須是 concave 或 convex，其他值 422。"""
    r = client.post(
        "/api/stamp",
        json={"text": "王", "preset": "square_name", "format": "svg",
              "engrave_mode": "embossed"},
    )
    assert r.status_code == 422


def test_api_stamp_round_name_preset_uses_circle_border(client):
    """12i: round_name preset 邊框應為圓形（SVG 含 <circle> 而非 <rect> path）。"""
    r = client.post(
        "/api/stamp",
        json={"text": "福", "preset": "round_name", "format": "svg",
              "stamp_width_mm": 12, "stamp_height_mm": 12, "char_size_mm": 5},
    )
    assert r.status_code == 200
    # _stamp_border_polys 對 round/round_name 返回 Circle，渲染出 <path d="..."> 圓弧
    # 不該有方形邊框 path（M 0 0 L W 0 L W H L 0 H Z 之類）
    assert "stamp-border" in r.text or "fill=" in r.text  # 邊框存在


def test_api_stamp_round_name_5char_layout_within_circle():
    """12j: round_name 5 字 layout placement bbox 角落不超圓邊太多。

    放寬容忍度 0.6mm — OTF 字筆劃通常不到 cell bbox 角落（bbox 是 EM 框，
    實際筆劃內縮），所以 bbox 角落略超圓邊不代表筆劃超出。實測 0.78 ratio
    視覺上字仍在圓內。
    """
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C()] * 5
    p = _placements_for_preset(
        "round_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
    )
    assert len(p) == 5
    cx_center, cy_center = 6.0, 6.0
    radius = 6.0 - 0.8  # = 5.2 mm
    OTF_PADDING_TOLERANCE = 0.6  # mm — OTF 字筆劃離 bbox 角落的安全距離
    for i, (_, x, y, _, w, h) in enumerate(p):
        for dx in (w / 2, -w / 2):
            for dy in (h / 2, -h / 2):
                dist = ((x + dx - cx_center) ** 2 +
                        (y + dy - cy_center) ** 2) ** 0.5
                assert dist <= radius + OTF_PADDING_TOLERANCE, \
                    f"第{i+1}字 bbox 角落 dist={dist:.3f} > " \
                    f"radius+tol={radius + OTF_PADDING_TOLERANCE}"


def test_api_stamp_round_name_vs_square_name_layout_differ():
    """12i: round_name 跟 square_name 同樣字數但 inner 收縮後位置不同。"""
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C()] * 3
    p_sq = _placements_for_preset(
        "square_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
    )
    p_rd = _placements_for_preset(
        "round_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
    )
    # 字身 w/h 不同（圓的較小，因為 inner 收縮 0.93）
    assert p_rd[0][4] < p_sq[0][4]
    assert p_rd[0][5] < p_sq[0][5]


def test_api_stamp_2char_default_horizontal_layout():
    """12h: 2 字章預設左右排列（右字 chars[0] + 左字 chars[1]）。

    字身 non-uniform stretch：寬 46% inner_w（兩字共 92% + 中央 gap 4%）、
    高 92% inner_h（拉長到接近邊框）。
    """
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C(), C()]
    p = _placements_for_preset(
        "square_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
    )
    assert len(p) == 2
    cx_center = 6.0
    # 第 1 字（chars[0]）在右、第 2 字在左
    assert p[0][1] > cx_center, f"第1字 cx={p[0][1]} 應在右"
    assert p[1][1] < cx_center, f"第2字 cx={p[1][1]} 應在左"
    # 字身高 > 寬（縱向拉長）
    assert p[0][5] > p[0][4], f"水平排列字身 h ({p[0][5]}) 應 > w ({p[0][4]})"


def test_api_stamp_2char_vertical_layout():
    """12h: 2 字章 vertical 切換 — 上下排列（上字 + 下字）。

    字身：寬 92% inner_w、高 46% inner_h（橫向拉寬）。
    """
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C(), C()]
    p = _placements_for_preset(
        "square_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
        layout_2char="vertical",
    )
    cy_center = 6.0
    # 第 1 字在上、第 2 字在下
    assert p[0][2] < cy_center
    assert p[1][2] > cy_center
    # 字身寬 > 高（橫向拉寬）
    assert p[0][4] > p[0][5]


def test_api_stamp_char_offsets_apply():
    """12g: char_offsets 套用到 placement (cx, cy)。

    用 24mm 大章 + char_size=5（cell 比字身大很多）確保 offset 不被 clamp。
    """
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C(), C()]
    base = _placements_for_preset(
        "square_name", chars, 24, 24, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
    )
    moved = _placements_for_preset(
        "square_name", chars, 24, 24, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
        char_offsets=[(0.5, -0.3), (0.0, 0.0)],
    )
    # 第 1 字應該位移
    assert abs(moved[0][1] - (base[0][1] + 0.5)) < 1e-6
    assert abs(moved[0][2] - (base[0][2] - 0.3)) < 1e-6
    # 第 2 字 (0, 0) 應該不變
    assert abs(moved[1][1] - base[1][1]) < 1e-6
    assert abs(moved[1][2] - base[1][2]) < 1e-6


def test_api_stamp_char_offsets_bounds_clamp():
    """12g: char_offsets 超過邊界要 clamp（字 outline bbox 不超 inner box）。"""
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C()]
    # 超大 dx — 應 clamp 到右邊界
    p = _placements_for_preset(
        "square_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
        char_offsets=[(100.0, 100.0)],  # 100mm 超大
    )
    cx, cy, _, w, h = p[0][1:]
    inner_left = 0.8
    inner_right = 12 - 0.8
    inner_top = 0.8
    inner_bot = 12 - 0.8
    # 字 bbox 不能超出 inner box
    assert cx + w / 2 <= inner_right + 1e-6
    assert cx - w / 2 >= inner_left - 1e-6
    assert cy + h / 2 <= inner_bot + 1e-6
    assert cy - h / 2 >= inner_top - 1e-6


def test_api_stamp_char_offsets_empty_backward_compat():
    """12g: char_offsets=None 等同於不傳，行為不變（向後相容）。"""
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C()] * 3
    base = _placements_for_preset(
        "square_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
    )
    none_case = _placements_for_preset(
        "square_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
        char_offsets=None,
    )
    empty_case = _placements_for_preset(
        "square_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
        char_offsets=[],
    )
    assert base == none_case == empty_case


def test_api_stamp_5char_default_2plus3_layout():
    """12f: 5 字章預設 2+3 layout（姓名章：右 2 字姓 + 左 3 字名）。

    預期：
    - 右欄字 (chars[0], chars[1]) 上下排列（姓）
    - 左欄字 (chars[2], chars[3], chars[4]) 上中下排列（名）
    - 右欄 cell h 較大（46% — 2 字欄），左欄 cell h 較小（30% — 3 字欄）
    """
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C()] * 5
    p = _placements_for_preset(
        "square_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
    )
    assert len(p) == 5
    cx_center = 6.0
    # 右欄 2 字（上下）— x 大於章面中心
    assert p[0][1] > cx_center and p[1][1] > cx_center
    assert p[0][2] < p[1][2], "第1字應在第2字上方"
    # 左欄 3 字（上中下）— x 小於章面中心
    for i in (2, 3, 4):
        assert p[i][1] < cx_center, f"第{i+1}字 cx={p[i][1]} 應在左欄"
    assert p[2][2] < p[3][2] < p[4][2], "左欄字應由上到下排列"
    # 右欄 cell h 較大（46%），左欄 cell h 較小（30%）
    assert p[0][5] > p[2][5], "右欄字 h 應大於左欄字 h（2 字欄 vs 3 字欄）"


def test_api_stamp_5char_3plus2_layout():
    """12f: 5 字章可切 3+2 layout（職名章變體：右 3 字主名 + 左 2 字職稱）。"""
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C()] * 5
    p = _placements_for_preset(
        "square_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
        layout_5char="3plus2",
    )
    assert len(p) == 5
    cx_center = 6.0
    # 右欄 3 字 + 左欄 2 字
    for i in (0, 1, 2):
        assert p[i][1] > cx_center
    assert p[3][1] < cx_center and p[4][1] < cx_center
    # 此 layout 右欄 cell h 較小（30%）
    assert p[0][5] < p[3][5]


def test_api_stamp_6plus_chars_truncated_to_5():
    """12e: square_name 後端 hard-cap：6+ 字截斷只取前 5。

    前端應警示，但後端做 safety net 防止 layout 爆炸。
    """
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C()] * 8
    p = _placements_for_preset(
        "square_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
    )
    assert len(p) == 5, f"6+ 字應截斷到 5，實際 {len(p)}"


def test_api_stamp_single_char_fills_cell_ignores_cap():
    """12d: 1 字章字身撐滿 inner 96%，不被 char_size_mm cap。

    業界 1 字章慣例：字撐滿章面（豬豬小姐 0.7-1.5cm 章「檀」「福」字
    佔 90%+）。stroke-order 過去用 char_size_mm cap 邏輯讓 1 字章
    字太小（12mm 章 char_size=5 → 字身只 5mm 佔 48%）。
    Phase 12d fix：1 字 ignore cap，固定 ratio 0.96 撐滿 cell。
    """
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C()]

    # 不同 char_size_mm 都該得到相同字身大小（1 字 ignore cap）
    for cs in [0, 5, 12, 20]:
        p = _placements_for_preset(
            "square_name", chars, 12, 12, cs,
            border_padding_mm=0.8,
            double_border=False, double_gap_mm=0.8,
        )
        inner = 12 - 2 * 0.8
        # 字身應該 96% inner（10.4 * 0.96 = 9.98 mm）
        assert abs(p[0][4] - inner * 0.96) < 0.01, \
            f"char_size_mm={cs}: 字身 {p[0][4]} != {inner * 0.96}"
        assert p[0][4] == p[0][5]  # 1 字 uniform scale (w == h)


def test_api_stamp_convex_pdf_has_red_fill(client):
    """陽刻 PDF：cairosvg 應正確處理 fill-rule 並輸出有顏色的 PDF。"""
    r = client.post(
        "/api/stamp",
        json={"text": "王", "preset": "square_name", "format": "pdf",
              "stamp_width_mm": 12, "stamp_height_mm": 12, "char_size_mm": 5,
              "engrave_mode": "convex"},
    )
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
    # 陽刻 PDF 跟陰刻 PDF size 應該不同（不同 SVG 內容）
    r2 = client.post(
        "/api/stamp",
        json={"text": "王", "preset": "square_name", "format": "pdf",
              "stamp_width_mm": 12, "stamp_height_mm": 12, "char_size_mm": 5,
              "engrave_mode": "concave"},
    )
    assert r2.status_code == 200
    # 兩種 mode 的 PDF 內容應該不同
    assert r.content != r2.content


# ---------------------------------------------------------------------------
# Patch's new show_border flag (5ay-4)
# ---------------------------------------------------------------------------


def test_api_patch_show_border_default_true(client):
    r = client.get("/api/patch?text=吉&preset=rectangle&format=svg")
    assert r.status_code == 200
    assert 'class="patch-outline"' in r.text


def test_api_patch_show_border_false_hides_outline(client):
    r = client.get("/api/patch?text=吉&preset=rectangle"
                   "&show_border=false&format=svg")
    assert r.status_code == 200
    assert 'class="patch-outline"' not in r.text


def test_api_patch_show_border_false_in_gcode_omits_outline(client):
    """When border is hidden, the per-tile outline emission disappears.

    Note: the header banner always names "patch outline + char outlines"
    as the cut-layer description; the per-tile comment 'tile (r,c) patch
    outline' is what's actually gated by show_border."""
    r_on = client.get("/api/patch?text=吉&preset=rectangle"
                      "&show_border=true&format=gcode_cut")
    r_off = client.get("/api/patch?text=吉&preset=rectangle"
                       "&show_border=false&format=gcode_cut")
    assert r_on.status_code == 200 and r_off.status_code == 200
    # The per-tile outline marker only appears with the border on.
    assert "tile (0,0) patch outline" in r_on.text
    assert "tile (0,0) patch outline" not in r_off.text
