"""Phase 5l — grid bounding-box fix + lines_per_page tests."""
import re

import pytest

from stroke_order.exporters.notebook import build_notebook_layout, flow_notebook
from stroke_order.exporters.page import _grid_svg, render_page_svg
from stroke_order.layouts import Page, PageLayout, PageSize


def _minimal_page(line_height=12.0, char_width=None, width=148.0, height=210.0,
                  margin=12.0, grid_style="square"):
    cw = char_width if char_width is not None else line_height
    layout = PageLayout(
        size=PageSize(width, height),
        margin_top_mm=margin, margin_bottom_mm=margin,
        margin_left_mm=margin, margin_right_mm=margin,
        line_height_mm=line_height, char_width_mm=cw,
        grid_style=grid_style,
    )
    return Page(page_num=1, layout=layout)


# ============================================================================
# Grid clipping — the core 5l bug
# ============================================================================


def test_square_grid_extends_to_content_edges_with_partial_row():
    """Phase 5o: grid spans full content area, including a shrunk last row/col
    when leftover space exists (vs. 5l behavior of stopping at last-full-cell)."""
    # A5: 148x210, margin=12, content=124x186, line_height=12
    # Leftover row: 186 - 15*12 = 186 - 180 = 6mm
    page = _minimal_page(line_height=12.0, width=148, height=210, margin=12)
    svg = _grid_svg("square", page)
    lines = re.findall(
        r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"/>',
        svg)
    # Vertical lines have x1==x2; they should extend to content_bottom=198
    vert = [(x1, y1, x2, y2) for x1, y1, x2, y2 in lines if x1 == x2]
    assert len(vert) > 0
    for (_, _, _, y2) in vert:
        assert float(y2) <= 198.01  # within content_bottom
    # Horizontal lines should span to content_right=136
    horiz = [(x1, y1, x2, y2) for x1, y1, x2, y2 in lines if y1 == y2]
    assert len(horiz) > 0
    for (_, _, x2, _) in horiz:
        assert float(x2) <= 136.01  # within content_right


def test_square_grid_has_partial_last_row():
    """With 186mm content and 12mm row, leftover = 6mm → a partial row drawn."""
    page = _minimal_page(line_height=12.0, width=148, height=210, margin=12)
    svg = _grid_svg("square", page)
    # Horizontal lines — should include a line at y = content_bottom (198)
    assert 'y1="198' in svg or 'y2="198' in svg


def test_dotted_grid_includes_partial_extent():
    """Dotted intersections include the partial last row/column."""
    page = _minimal_page(line_height=10.0, width=105, height=148, margin=8)
    # content = 89×132: n_cols = 8 full (leftover 9mm → partial col), n_rows = 13 full (leftover 2mm).
    # cols: 9 + 1 partial = 10 columns of intersections. rows: 13 + 1 partial = 14 rows.
    # Actually row leftover = 132 - 130 = 2mm (≤ 0.5 threshold? > 0.5 → include).
    # vlines: 9 major + 1 partial = 10 columns. hlines: 14 major + 1 partial = 15.
    # Total circles: 10 × 15 = 150.
    svg = _grid_svg("dotted", page)
    n_dots = svg.count("<circle")
    assert 140 <= n_dots <= 160  # allows minor edge cases


def test_ruled_grid_spans_to_content_right():
    """5o: ruled lines span to content_right (not clipped to last full cell)."""
    page = _minimal_page(line_height=12.0, width=148, height=210, margin=12)
    svg = _grid_svg("ruled", page)
    lines = re.findall(r'x2="([\d.]+)"', svg)
    # ruled lines go up to content_right = 136
    max_x2 = max(float(x) for x in lines)
    assert abs(max_x2 - 136.0) < 0.5


def test_none_grid_returns_empty():
    page = _minimal_page(grid_style="none")
    assert _grid_svg("none", page) == ""


# ============================================================================
# Default preset changed to "large"
# ============================================================================


def test_build_notebook_layout_default_is_large():
    layout = build_notebook_layout()
    # large preset → A4 = 210 × 297
    assert layout.size.width_mm == 210.0
    assert layout.size.height_mm == 297.0


# ============================================================================
# lines_per_page (B1: wins over line_height_mm)
# ============================================================================


def test_lines_per_page_derives_line_height():
    # A4 with margin=15 → content_h = 267
    # lines_per_page=10 → line_height = 26.7
    layout = build_notebook_layout(
        preset="large", margin_mm=15, lines_per_page=10,
    )
    assert abs(layout.line_height_mm - 26.7) < 0.01
    assert abs(layout.char_width_mm - 26.7) < 0.01  # square cells


def test_lines_per_page_overrides_line_height_mm():
    """B1: When both provided, lines_per_page wins."""
    layout = build_notebook_layout(
        preset="large", margin_mm=15,
        line_height_mm=8.0, lines_per_page=20,
    )
    # content_h = 267; 267/20 = 13.35 (not 8.0)
    assert abs(layout.line_height_mm - 13.35) < 0.01


def test_lines_per_page_none_uses_line_height_mm():
    layout = build_notebook_layout(
        preset="large", margin_mm=15, line_height_mm=10.0,
    )
    assert layout.line_height_mm == 10.0


def test_flow_notebook_respects_lines_per_page(source):
    from stroke_order.classifier import classify_character
    from stroke_order.smoothing import smooth_character
    def loader(ch):
        try:
            c = source.get_character(ch)
            classify_character(c); smooth_character(c)
            return c
        except Exception:
            return None
    pages = flow_notebook(
        "日永一日永", loader, preset="large", lines_per_page=15,
    )
    # With 15 lines on A4 (267/15=17.8mm cell), chars should use that cell size
    assert len(pages[0].chars) > 0
    first = pages[0].chars[0]
    assert abs(first.height_mm - 17.8) < 0.1


# ============================================================================
# Web API
# ============================================================================


try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS = True
except ImportError:
    _HAS = False


@pytest.fixture(scope="module")
def client():
    if not _HAS:
        pytest.skip("web deps missing")
    return TestClient(create_app())


def test_api_notebook_default_preset_is_large(client):
    r = client.get("/api/notebook/capacity?text=a")
    assert r.status_code == 200
    d = r.json()
    # A4 = 210 × 297
    assert d["page_size_mm"] == [210.0, 297.0]


def test_api_notebook_accepts_lines_per_page(client):
    r = client.get("/api/notebook?text=永一&lines_per_page=20")
    assert r.status_code == 200
    # Check capacity/rows count reflects 20 rows
    r2 = client.get("/api/notebook/capacity?text=永一&lines_per_page=20")
    d = r2.json()
    # lines_per_page=20 in horizontal → 20 rows
    assert d["lines_per_page"] == 20


def test_api_lines_per_page_precedence_over_line_height(client):
    """Both lines_per_page and line_height_mm provided → lines wins (B1)."""
    r = client.get(
        "/api/notebook/capacity?text=永&line_height_mm=8&lines_per_page=10"
    )
    assert r.status_code == 200
    d = r.json()
    assert d["lines_per_page"] == 10


# ============================================================================
# Phase 5m — lines_per_page boundary fix (prevents page overflow)
# ============================================================================


def test_lines_per_page_1_horizontal_caps_at_content_width():
    """Horizontal lines=1 on A4 should cap cell at content_width (180), not
    blow up to content_height (267) which overflows the page horizontally."""
    layout = build_notebook_layout(
        preset="large", margin_mm=15, lines_per_page=1, direction="horizontal",
    )
    # A4 content = 180×267 → cap at 180 (not 267)
    assert layout.line_height_mm == 180.0
    assert layout.char_width_mm == 180.0


def test_lines_per_page_1_vertical_caps_at_content_width():
    """Vertical lines=1 on A4: uses content_width/1=180, no cap needed."""
    layout = build_notebook_layout(
        preset="large", margin_mm=15, lines_per_page=1, direction="vertical",
    )
    assert layout.line_height_mm == 180.0


def test_lines_per_page_vertical_uses_content_width():
    """Vertical lines_per_page=10 on A4 → 180/10 = 18mm cell (not 267/10)."""
    layout = build_notebook_layout(
        preset="large", margin_mm=15, lines_per_page=10, direction="vertical",
    )
    assert abs(layout.line_height_mm - 18.0) < 0.01


def test_lines_per_page_horizontal_uses_content_height():
    """Horizontal lines_per_page=10 on A4 → 267/10 = 26.7mm cell."""
    layout = build_notebook_layout(
        preset="large", margin_mm=15, lines_per_page=10,
        direction="horizontal",
    )
    assert abs(layout.line_height_mm - 26.7) < 0.01


def test_cell_never_exceeds_content_box():
    """Any cell size must be ≤ min(content_w, content_h) regardless of input."""
    for lines in (1, 2, 3, 5, 10, 50):
        for d in ("horizontal", "vertical"):
            layout = build_notebook_layout(
                preset="large", margin_mm=15,
                lines_per_page=lines, direction=d,  # type: ignore
            )
            content_w = layout.size.width_mm - 2 * layout.margin_left_mm
            content_h = layout.size.height_mm - 2 * layout.margin_top_mm
            assert layout.line_height_mm <= min(content_w, content_h) + 0.01, \
                f"lines={lines} dir={d} overflowed"


def test_api_lines_per_page_1_no_overflow(client):
    """API with lines_per_page=1 should produce cells that fit the page."""
    r = client.get("/api/notebook/capacity?text=永&lines_per_page=1")
    assert r.status_code == 200
    d = r.json()
    # cell_size should not exceed min(content_w, content_h)
    content_w = d["page_size_mm"][0] - d["margin_mm"]["left"] - d["margin_mm"]["right"]
    content_h = d["page_size_mm"][1] - d["margin_mm"]["top"] - d["margin_mm"]["bottom"]
    assert d["line_height_mm"] <= min(content_w, content_h) + 0.01


def test_api_lines_per_page_1_vertical_no_overflow(client):
    r = client.get("/api/notebook/capacity?text=永&lines_per_page=1&direction=vertical")
    assert r.status_code == 200
    d = r.json()
    content_w = d["page_size_mm"][0] - d["margin_mm"]["left"] - d["margin_mm"]["right"]
    content_h = d["page_size_mm"][1] - d["margin_mm"]["top"] - d["margin_mm"]["bottom"]
    assert d["line_height_mm"] <= min(content_w, content_h) + 0.01


# ============================================================================
# Phase 5n — first_line_offset_mm
# ============================================================================


def test_first_line_offset_horizontal_shifts_first_row(source):
    """Horizontal: first_line_offset_mm = first row's bottom y."""
    from stroke_order.classifier import classify_character
    from stroke_order.smoothing import smooth_character
    def loader(ch):
        try:
            c = source.get_character(ch); classify_character(c); smooth_character(c)
            return c
        except Exception:
            return None
    # Default: A4 margin=15, line_height=15 → first row at y=15 (top=15, bottom=30)
    pages = flow_notebook("永一日", loader, preset="large",
                         line_height_mm=15, margin_mm=15)
    default_first_y = pages[0].chars[0].y_mm
    assert abs(default_first_y - 15) < 0.01

    # With first_line_offset_mm = 60 → first row bottom at y=60 → top at y=45
    pages = flow_notebook("永一日", loader, preset="large",
                         line_height_mm=15, margin_mm=15,
                         first_line_offset_mm=60)
    shifted_first_y = pages[0].chars[0].y_mm
    assert abs(shifted_first_y - 45) < 0.01  # 60 - 15 = 45


def test_first_line_offset_vertical_shifts_first_column(source):
    """Vertical: first_line_offset_mm = first column's LEFT edge distance from right."""
    from stroke_order.classifier import classify_character
    from stroke_order.smoothing import smooth_character
    def loader(ch):
        try:
            c = source.get_character(ch); classify_character(c); smooth_character(c)
            return c
        except Exception:
            return None
    # Default A4 margin=15, char_width=15. Default cursor_x = (210-15) - 15 = 180.
    pages = flow_notebook("永一日", loader, preset="large",
                         line_height_mm=15, margin_mm=15, direction="vertical")
    default_first_x = pages[0].chars[0].x_mm
    assert abs(default_first_x - 180) < 0.01

    # With first_line_offset_mm = 100 → first column left at x = 210 - 100 = 110
    pages = flow_notebook("永一日", loader, preset="large",
                         line_height_mm=15, margin_mm=15, direction="vertical",
                         first_line_offset_mm=100)
    shifted_first_x = pages[0].chars[0].x_mm
    assert abs(shifted_first_x - 110) < 0.01


def test_first_line_offset_clamped_to_default_not_margin(source):
    """Phase 5p: min = margin + line_height (= auto default), not just margin.
    Values below default clamp to default (first row at natural position)."""
    from stroke_order.classifier import classify_character
    from stroke_order.smoothing import smooth_character
    def loader(ch):
        try:
            c = source.get_character(ch); classify_character(c); smooth_character(c)
            return c
        except Exception:
            return None
    # A4 margin=15, line_height=15 → auto default = 30.
    # offset=5 (below default) should clamp to 30 → cursor_y = 30-15 = 15 = margin.
    pages = flow_notebook("永", loader, preset="large",
                         line_height_mm=15, margin_mm=15,
                         first_line_offset_mm=5)
    first_y = pages[0].chars[0].y_mm
    # first row TOP at margin_top = 15 (= content_y)
    assert abs(first_y - 15) < 0.01


def test_api_first_line_offset_accepted(client):
    r = client.get("/api/notebook?text=永&first_line_offset_mm=40")
    assert r.status_code == 200


def test_api_first_line_offset_horizontal_effect(client):
    """Different offsets should produce different SVGs."""
    r1 = c1 = client.get("/api/notebook?text=" + "永一日" * 4 +
                         "&preset=large&line_height_mm=15&margin_mm=15")
    r2 = client.get("/api/notebook?text=" + "永一日" * 4 +
                    "&preset=large&line_height_mm=15&margin_mm=15"
                    "&first_line_offset_mm=60")
    assert r1.content != r2.content


# ============================================================================
# Phase 5o — grid follows first_line_offset & 直書 ruled = vertical lines
# ============================================================================


def test_grid_follows_first_line_offset_horizontal():
    """With offset=60 on A4 (margin=15, line_height=15), grid top should be
    at y = offset - line_height = 45 (not margin_top=15)."""
    layout = PageLayout(
        size=PageSize(210, 297),
        margin_top_mm=15, margin_bottom_mm=15,
        margin_left_mm=15, margin_right_mm=15,
        line_height_mm=15, char_width_mm=15,
        grid_style="square",
        direction="horizontal",
        first_line_offset_mm=60,
    )
    page = Page(page_num=1, layout=layout)
    svg = _grid_svg("square", page)
    # Extract all y-coordinates of horizontal lines (y1==y2)
    hlines = re.findall(
        r'<line x1="[\d.]+" y1="([\d.]+)" x2="[\d.]+" y2="[\d.]+"/>', svg)
    ys = [float(y) for y in hlines]
    # Top of grid (first horizontal line) should be at y=45
    assert min(ys) >= 44.99
    assert min(ys) <= 45.01


def test_grid_has_shrunken_last_row_when_offset_pushed():
    """When offset shifts grid, leftover bottom space becomes a shrunken row."""
    layout = PageLayout(
        size=PageSize(210, 297),
        margin_top_mm=15, margin_bottom_mm=15,
        margin_left_mm=15, margin_right_mm=15,
        line_height_mm=15, char_width_mm=15,
        grid_style="square",
        direction="horizontal",
        first_line_offset_mm=60,
    )
    page = Page(page_num=1, layout=layout)
    svg = _grid_svg("square", page)
    # Last horizontal line should be at content_bottom = 282 (not stopping early)
    hlines = re.findall(
        r'<line x1="[\d.]+" y1="([\d.]+)" x2="[\d.]+" y2="[\d.]+"/>', svg)
    ys = [float(y) for y in hlines]
    assert max(ys) >= 281.99  # within content_bottom range


def test_vertical_ruled_draws_vertical_lines():
    """直書 + ruled: draws vertical column separators (not horizontal)."""
    layout = PageLayout(
        size=PageSize(210, 297),
        margin_top_mm=15, margin_bottom_mm=15,
        margin_left_mm=15, margin_right_mm=15,
        line_height_mm=15, char_width_mm=15,
        grid_style="ruled",
        direction="vertical",
    )
    page = Page(page_num=1, layout=layout)
    svg = _grid_svg("ruled", page)
    # Extract line elements — vertical lines have x1 == x2
    lines = re.findall(
        r'<line x1="([\d.]+)" y1="[\d.]+" x2="([\d.]+)" y2="[\d.]+"/>', svg)
    # All ruled lines in vertical mode should be vertical (x1 == x2)
    for (x1, x2) in lines:
        assert abs(float(x1) - float(x2)) < 0.01


# ---- Phase 5p: capacity returns default_first_line_offset_mm ----


def test_capacity_returns_default_first_line_offset_horizontal(client):
    """API capacity response should expose the auto default for first-line offset."""
    r = client.get("/api/notebook/capacity?text=a&preset=large"
                   "&line_height_mm=15&margin_mm=15&direction=horizontal")
    assert r.status_code == 200
    d = r.json()
    # horizontal: default = margin_top + line_height = 15 + 15 = 30
    assert abs(d["default_first_line_offset_mm"] - 30.0) < 0.01


def test_capacity_returns_default_first_line_offset_vertical(client):
    """Vertical: default = margin_right + char_width."""
    r = client.get("/api/notebook/capacity?text=a&preset=large"
                   "&line_height_mm=15&margin_mm=15&direction=vertical")
    assert r.status_code == 200
    d = r.json()
    # vertical: default = margin_right + char_width = 15 + 15 = 30
    assert abs(d["default_first_line_offset_mm"] - 30.0) < 0.01


def test_capacity_default_tracks_lines_per_page(client):
    """When lines_per_page changes cell size, the default also changes."""
    r = client.get("/api/notebook/capacity?text=a&preset=large"
                   "&margin_mm=15&lines_per_page=20")
    d = r.json()
    # line_height = content_h / 20 = 267/20 = 13.35 → default = 15 + 13.35 = 28.35
    assert abs(d["default_first_line_offset_mm"] - 28.35) < 0.1


def test_vertical_first_line_offset_respects_min_char_width(source):
    """Phase 5p: vertical offset < default should clamp so first col's RIGHT
    edge stays at or inside content_right (never past page edge)."""
    from stroke_order.classifier import classify_character
    from stroke_order.smoothing import smooth_character
    def loader(ch):
        try:
            c = source.get_character(ch); classify_character(c); smooth_character(c)
            return c
        except Exception:
            return None
    # A4 margin=15, char_width=15 → default = 30.
    # offset=5 → clamp to 30 → cursor_x = 210 - 30 = 180.
    pages = flow_notebook("永", loader, preset="large",
                         line_height_mm=15, margin_mm=15,
                         direction="vertical",
                         first_line_offset_mm=5)
    first_x = pages[0].chars[0].x_mm
    # first col LEFT at x=180, right edge at 195 (= content_right) — perfect
    assert abs(first_x - 180) < 0.01


# ---- Phase 5q: Letter preset ----


def test_notebook_letter_preset_is_us_letter_size():
    """Notebook 'letter' preset should produce 215.9 × 279.4 mm page."""
    layout = build_notebook_layout(preset="letter")
    assert abs(layout.size.width_mm - 215.9) < 0.01
    assert abs(layout.size.height_mm - 279.4) < 0.01


def test_notebook_letter_preset_uses_16mm_margin():
    """US letter default margin ≈ 16mm (common for notebook paper)."""
    layout = build_notebook_layout(preset="letter")
    assert abs(layout.margin_left_mm - 16.0) < 0.01
    assert abs(layout.margin_top_mm - 16.0) < 0.01


def test_letter_mode_Letter_preset_is_us_letter_size():
    """Letter mode 'Letter' preset should produce 215.9 × 279.4 mm page."""
    from stroke_order.exporters.letter import build_letter_layout
    layout = build_letter_layout(preset="Letter")
    assert abs(layout.size.width_mm - 215.9) < 0.01
    assert abs(layout.size.height_mm - 279.4) < 0.01


def test_letter_mode_Letter_preset_uses_1inch_margin():
    """US letter classic 1 inch (25.4mm) margin."""
    from stroke_order.exporters.letter import build_letter_layout
    layout = build_letter_layout(preset="Letter")
    assert abs(layout.margin_left_mm - 25.4) < 0.01
    assert abs(layout.margin_top_mm - 25.4) < 0.01


def test_api_notebook_accepts_letter_preset(client):
    r = client.get("/api/notebook?text=永&preset=letter")
    assert r.status_code == 200


def test_api_letter_accepts_Letter_preset(client):
    r = client.get("/api/letter?text=永&preset=Letter")
    assert r.status_code == 200


def test_api_notebook_capacity_letter_preset(client):
    r = client.get("/api/notebook/capacity?text=a&preset=letter")
    assert r.status_code == 200
    d = r.json()
    assert d["page_size_mm"] == [215.9, 279.4]


def test_api_letter_capacity_Letter_preset(client):
    r = client.get("/api/letter/capacity?text=a&preset=Letter")
    assert r.status_code == 200
    d = r.json()
    assert d["page_size_mm"] == [215.9, 279.4]


# ---- Phase 5r: interactive doodle zone (custom x/y/w/h) ----


def test_doodle_zone_default_is_bottom_right(source):
    """Without x/y/w/h override, zone goes to bottom-right (legacy behavior)."""
    from stroke_order.classifier import classify_character
    from stroke_order.smoothing import smooth_character
    def loader(ch):
        try:
            c = source.get_character(ch); classify_character(c); smooth_character(c)
            return c
        except Exception:
            return None
    pages = flow_notebook(
        "永", loader, preset="large",
        doodle_zone=True, doodle_zone_size_mm=50,
    )
    zones = pages[0].layout.reserve_zones
    assert len(zones) == 1
    # A4 = 210 × 297, margin = 15. Zone at (210-15-50, 297-15-50) = (145, 232)
    assert abs(zones[0].x_mm - 145) < 0.5
    assert abs(zones[0].y_mm - 232) < 0.5
    assert abs(zones[0].width_mm - 50) < 0.01


def test_doodle_zone_custom_position(source):
    """Custom x/y/w/h places zone at exact coords (not bottom-right)."""
    from stroke_order.classifier import classify_character
    from stroke_order.smoothing import smooth_character
    def loader(ch):
        try:
            c = source.get_character(ch); classify_character(c); smooth_character(c)
            return c
        except Exception:
            return None
    pages = flow_notebook(
        "永", loader, preset="large",
        doodle_zone=True,
        doodle_zone_x_mm=30, doodle_zone_y_mm=40,
        doodle_zone_width_mm=60, doodle_zone_height_mm=80,
    )
    zones = pages[0].layout.reserve_zones
    assert len(zones) == 1
    assert abs(zones[0].x_mm - 30) < 0.01
    assert abs(zones[0].y_mm - 40) < 0.01
    assert abs(zones[0].width_mm - 60) < 0.01
    assert abs(zones[0].height_mm - 80) < 0.01


def test_doodle_zone_clamped_to_content_area(source):
    """Zone positions outside content area get clamped."""
    from stroke_order.classifier import classify_character
    from stroke_order.smoothing import smooth_character
    def loader(ch):
        try:
            c = source.get_character(ch); classify_character(c); smooth_character(c)
            return c
        except Exception:
            return None
    # Zone at x=-10 (outside) → should clamp to margin_left = 15
    pages = flow_notebook(
        "永", loader, preset="large",
        doodle_zone=True,
        doodle_zone_x_mm=-10, doodle_zone_y_mm=-10,
        doodle_zone_width_mm=60, doodle_zone_height_mm=60,
    )
    zones = pages[0].layout.reserve_zones
    assert zones[0].x_mm >= 14.99  # clamped to margin_left
    assert zones[0].y_mm >= 14.99


def test_text_avoids_custom_doodle_zone(source):
    """Text should flow around zone wherever it's placed (not just bottom-right)."""
    from stroke_order.classifier import classify_character
    from stroke_order.smoothing import smooth_character
    def loader(ch):
        try:
            c = source.get_character(ch); classify_character(c); smooth_character(c)
            return c
        except Exception:
            return None
    # Zone covering top-left 80×80mm area
    pages = flow_notebook(
        "永一日" * 20, loader, preset="large",
        doodle_zone=True,
        doodle_zone_x_mm=15, doodle_zone_y_mm=15,
        doodle_zone_width_mm=80, doodle_zone_height_mm=80,
    )
    # No character should be inside the zone
    z = pages[0].layout.reserve_zones[0]
    for ch in pages[0].chars:
        # Char cell's top-left at (ch.x_mm, ch.y_mm) with size line_height × char_width
        # It shouldn't overlap the zone
        in_zone = (ch.x_mm >= z.x_mm and ch.x_mm < z.x_mm + z.width_mm
                   and ch.y_mm >= z.y_mm and ch.y_mm < z.y_mm + z.height_mm)
        assert not in_zone, \
            f"char {ch.char.char} at ({ch.x_mm},{ch.y_mm}) overlaps zone"


def test_api_doodle_zone_accepts_xywh(client):
    r = client.get(
        "/api/notebook?text=" + "永一" * 50 + "&preset=large"
        "&doodle_zone=true&doodle_zone_x_mm=50&doodle_zone_y_mm=80"
        "&doodle_zone_width_mm=90&doodle_zone_height_mm=70"
    )
    assert r.status_code == 200


def test_api_doodle_zone_capacity_accepts_xywh(client):
    r = client.get(
        "/api/notebook/capacity?text=永&preset=large"
        "&doodle_zone=true&doodle_zone_x_mm=50&doodle_zone_y_mm=80"
        "&doodle_zone_width_mm=90&doodle_zone_height_mm=70"
    )
    assert r.status_code == 200


# ---- Phase 5s: multi-zone + svg_content ----


def test_api_get_zones_json_multi_zone(client):
    """GET with zones_json creates multiple zones."""
    import urllib.parse, json
    zones = [{"x": 30, "y": 30, "w": 40, "h": 40},
             {"x": 130, "y": 100, "w": 60, "h": 50}]
    url = ("/api/notebook?text=" + "永一" * 30 + "&preset=large"
           "&zones_json=" + urllib.parse.quote(json.dumps(zones)))
    r = client.get(url)
    assert r.status_code == 200


def test_api_post_notebook_with_svg_content(client):
    """POST route accepts zones with svg_content and embeds it cleanly
    (Phase 5w: outline + label are no longer emitted)."""
    body = {
        "text": "永一日永一",
        "preset": "large",
        "zones": [
            {"x": 30, "y": 30, "w": 60, "h": 60, "label": "Zone A"},
            {"x": 120, "y": 120, "w": 50, "h": 50,
             "svg_content": '<circle cx="50" cy="50" r="40" fill="red"/>',
             "content_viewbox": [0, 0, 100, 100]},
        ],
    }
    r = client.post("/api/notebook", json=body)
    assert r.status_code == 200
    svg = r.text
    # Embedded circle should render
    assert "<circle" in svg
    # Zone-content group marker
    assert "zone-content" in svg
    # Phase 5w: no outline rect or label text from zones
    assert "Zone A" not in svg
    # no dashed outline
    assert "stroke-dasharray=\"2 2\"" not in svg


def test_flow_notebook_multi_zone_text_avoids_all(source):
    """Text must avoid ALL zones when multiple are defined."""
    from stroke_order.classifier import classify_character
    from stroke_order.smoothing import smooth_character
    def loader(ch):
        try:
            c = source.get_character(ch); classify_character(c); smooth_character(c)
            return c
        except Exception:
            return None
    zones_spec = [
        {"x": 15, "y": 15, "w": 80, "h": 40},
        {"x": 120, "y": 100, "w": 70, "h": 70},
    ]
    pages = flow_notebook(
        "永一日" * 50, loader, preset="large",
        zones=zones_spec,
    )
    # No character should overlap either zone
    for ch in pages[0].chars:
        for z in pages[0].layout.reserve_zones:
            in_zone = (ch.x_mm >= z.x_mm
                       and ch.x_mm < z.x_mm + z.width_mm
                       and ch.y_mm >= z.y_mm
                       and ch.y_mm < z.y_mm + z.height_mm)
            assert not in_zone, \
                f"char at ({ch.x_mm},{ch.y_mm}) overlaps zone {z.label}"


# ---- Phase 5v: notebook format=svg|gcode|json ----


def test_api_notebook_format_svg(client):
    r = client.get("/api/notebook?text=永一&preset=large&format=svg")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]


def test_api_notebook_format_gcode(client):
    r = client.get("/api/notebook?text=永一&preset=large"
                   "&cell_style=outline&format=gcode")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "G21" in r.text and "G90" in r.text


def test_api_notebook_format_gcode_ghost_has_no_strokes(client):
    """cell_style=ghost → G-code comment-only, no actual strokes."""
    r = client.get("/api/notebook?text=永&preset=large"
                   "&cell_style=ghost&format=gcode")
    assert r.status_code == 200
    # no pen-down command means no strokes emitted
    assert "M3 S90" not in r.text


def test_api_notebook_format_json(client):
    import json
    r = client.get("/api/notebook?text=永一&preset=large&format=json")
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"]
    d = json.loads(r.text)
    assert "notebook" in d and "pages" in d
    assert d["notebook"]["pages"] >= 1
    # chars have strokes with mm coordinates
    first_char = d["pages"][0]["chars"][0]
    assert "strokes" in first_char
    assert "x_mm" in first_char


def test_api_notebook_format_rejects_invalid(client):
    r = client.get("/api/notebook?text=永&format=pdf")
    assert r.status_code == 422


def test_api_notebook_post_format_json(client):
    import json
    body = {"text": "永一", "preset": "large", "format": "json",
            "zones": [], "cell_style": "ghost"}
    r = client.post("/api/notebook", json=body)
    assert r.status_code == 200
    d = json.loads(r.text)
    assert "notebook" in d


def test_reserve_zone_svg_content_embedded_fit_within(source):
    """Zone with svg_content should render inside the zone bbox."""
    from stroke_order.classifier import classify_character
    from stroke_order.smoothing import smooth_character
    from stroke_order.exporters.notebook import render_notebook_page_svg
    def loader(ch):
        try:
            c = source.get_character(ch); classify_character(c); smooth_character(c)
            return c
        except Exception:
            return None
    zones_spec = [{
        "x": 30, "y": 30, "w": 60, "h": 60,
        "svg_content": '<circle cx="50" cy="50" r="40" fill="blue"/>',
        "content_viewbox": [0, 0, 100, 100],
    }]
    pages = flow_notebook("永", loader, preset="large", zones=zones_spec)
    svg = render_notebook_page_svg(pages[0])
    # Output SVG should embed the circle
    assert "<circle" in svg
    # Should have the zone-content group
    assert "zone-content" in svg


def test_horizontal_ruled_stays_horizontal():
    """Sanity: horizontal direction still draws horizontal ruled lines."""
    layout = PageLayout(
        size=PageSize(210, 297),
        margin_top_mm=15, margin_bottom_mm=15,
        margin_left_mm=15, margin_right_mm=15,
        line_height_mm=15, char_width_mm=15,
        grid_style="ruled",
        direction="horizontal",
    )
    page = Page(page_num=1, layout=layout)
    svg = _grid_svg("ruled", page)
    lines = re.findall(
        r'<line x1="[\d.]+" y1="([\d.]+)" x2="[\d.]+" y2="([\d.]+)"/>', svg)
    for (y1, y2) in lines:
        assert abs(float(y1) - float(y2)) < 0.01
