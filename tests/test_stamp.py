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


def test_api_stamp_5char_default_3plus2_layout():
    """12e: 5 字章預設 3+2 layout（傳統台灣印章右起讀：右 3 字 + 左 2 字）。

    預期：
    - 右欄字 (chars[0], chars[1], chars[2]) 上中下排列
    - 左欄字 (chars[3], chars[4]) 上下排列
    - 右欄 cell h 較小（30%），左欄 cell h 較大（46%）
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
    # 右欄 3 字（上中下）— x 大於章面中心
    for i in (0, 1, 2):
        assert p[i][1] > cx_center, f"第{i+1}字 cx={p[i][1]} 應在右欄"
    assert p[0][2] < p[1][2] < p[2][2], "右欄字應由上到下排列"
    # 左欄 2 字（上下）— x 小於章面中心
    assert p[3][1] < cx_center, f"第4字 cx={p[3][1]} 應在左欄"
    assert p[4][1] < cx_center, f"第5字 cx={p[4][1]} 應在左欄"
    assert p[3][2] < p[4][2], "第4字應在第5字上方"
    # 右欄 cell h 較小（30%），左欄 cell h 較大（46%）
    assert p[0][5] < p[3][5], "右欄字 h 應小於左欄字 h（3 字欄 vs 2 字欄）"


def test_api_stamp_5char_2plus3_layout():
    """12e: 5 字章可切 2+3 layout（日本姓名章 / 特殊變體：右 2 字 + 左 3 字）。"""
    from stroke_order.exporters.stamp import _placements_for_preset

    class C:
        pass
    chars = [C()] * 5
    p = _placements_for_preset(
        "square_name", chars, 12, 12, 5,
        border_padding_mm=0.8,
        double_border=False, double_gap_mm=0.8,
        layout_5char="2plus3",
    )
    assert len(p) == 5
    cx_center = 6.0
    # 右欄 2 字 + 左欄 3 字
    assert p[0][1] > cx_center and p[1][1] > cx_center
    for i in (2, 3, 4):
        assert p[i][1] < cx_center
    # 此 layout 右欄 cell h 較大（46%）
    assert p[0][5] > p[2][5]


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
