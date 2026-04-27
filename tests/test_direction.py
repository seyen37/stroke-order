"""Phase 5i — 直書 (vertical writing) tests."""
import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.letter import flow_letter
from stroke_order.exporters.notebook import flow_notebook
from stroke_order.exporters.wordart import compute_fill, fill_positions
from stroke_order.layouts import (
    PageLayout, PageSize, flow_text, layout_capacity, estimate_pages,
)
from stroke_order.shapes import Circle
from stroke_order.smoothing import smooth_character


@pytest.fixture
def loader(source):
    def _loader(ch):
        try:
            c = source.get_character(ch)
            classify_character(c)
            smooth_character(c)
            return c
        except Exception:
            return None
    return _loader


# ============================================================================
# flow_text direction behaviour
# ============================================================================


def _layout(width=100, height=100, margin=10, cell=10):
    return PageLayout(
        size=PageSize(width, height),
        margin_top_mm=margin, margin_bottom_mm=margin,
        margin_left_mm=margin, margin_right_mm=margin,
        line_height_mm=cell, char_width_mm=cell,
    )


def test_horizontal_first_char_at_top_left(loader):
    layout = _layout()
    pages = flow_text("永一日", layout, loader, direction="horizontal")
    assert len(pages) == 1
    first = pages[0].chars[0]
    # Top-left cell ≈ (margin_left, margin_top)
    assert abs(first.x_mm - 10) < 0.01
    assert abs(first.y_mm - 10) < 0.01


def test_vertical_first_char_at_top_right(loader):
    layout = _layout()
    pages = flow_text("永一日", layout, loader, direction="vertical")
    assert len(pages) == 1
    first = pages[0].chars[0]
    # Top-right column: x = content_right - cell
    # content_right = 100 - 10 = 90, cell = 10, so x = 80
    assert abs(first.x_mm - 80) < 0.01
    assert abs(first.y_mm - 10) < 0.01


def test_vertical_chars_flow_down(loader):
    layout = _layout()
    pages = flow_text("永一日", layout, loader, direction="vertical")
    chars = pages[0].chars
    # All chars in same column → x equal
    assert len({round(c.x_mm, 2) for c in chars}) == 1
    # y values strictly increasing
    ys = [c.y_mm for c in chars]
    assert ys == sorted(ys)


def test_vertical_columns_flow_right_to_left(loader):
    layout = _layout(width=50, height=50, margin=5, cell=10)
    # content_area = 40x40 mm = 4 cols × 4 rows. 8 chars spans 2 columns.
    pages = flow_text("永一日永一日永一", layout, loader,
                      direction="vertical")
    chars = pages[0].chars
    # First column at x=35, second column at x=25
    xs = [round(c.x_mm, 0) for c in chars]
    # First 4 chars at rightmost column, next 4 one step left
    assert xs[0] > xs[-1]


def test_vertical_newline_jumps_to_next_column(loader):
    layout = _layout()
    pages = flow_text("永\n一", layout, loader, direction="vertical")
    chars = pages[0].chars
    assert len(chars) == 2
    # Second char should be in a different column (smaller x)
    assert chars[1].x_mm < chars[0].x_mm
    # And at top of its column
    assert abs(chars[1].y_mm - 10) < 0.01


def test_vertical_page_break_when_no_more_columns(loader):
    # Small page: 30x30 mm content area, 10 mm cells → 3 cols × 3 rows = 9 cells
    layout = _layout(width=50, height=50, margin=10, cell=10)
    # 10 chars should overflow onto page 2
    pages = flow_text("永" * 10, layout, loader, direction="vertical")
    assert len(pages) >= 2


def test_horizontal_still_works_as_before(loader):
    """Default (no direction param) = horizontal = previous behavior."""
    layout = _layout()
    pages_default = flow_text("永一日", layout, loader)
    pages_h = flow_text("永一日", layout, loader, direction="horizontal")
    # Same result
    positions_d = [(c.x_mm, c.y_mm) for c in pages_default[0].chars]
    positions_h = [(c.x_mm, c.y_mm) for c in pages_h[0].chars]
    assert positions_d == positions_h


# ============================================================================
# layout_capacity direction awareness
# ============================================================================


def test_layout_capacity_vertical_reports_correctly():
    layout = _layout(width=100, height=100, margin=10, cell=10)
    cap_h = layout_capacity(layout, direction="horizontal")
    cap_v = layout_capacity(layout, direction="vertical")
    # For a symmetric square page, capacities are equal
    assert cap_h["chars_per_page"] == cap_v["chars_per_page"]


def test_estimate_pages_vertical():
    layout = _layout(width=40, height=40, margin=5, cell=10)
    # 3x3 = 9 cells per page; 20 chars → at least 3 pages
    assert estimate_pages("永" * 20, layout, direction="vertical") >= 3
    assert estimate_pages("永" * 20, layout, direction="horizontal") >= 3


# ============================================================================
# Notebook direction
# ============================================================================


def test_notebook_vertical_first_char_top_right(loader):
    pages = flow_notebook(
        "永一日", loader, preset="small", direction="vertical",
    )
    chars = pages[0].chars
    # First char at top-right (large x, small y)
    layout = pages[0].layout
    expected_x = layout.content_right - layout.char_width_mm
    assert abs(chars[0].x_mm - expected_x) < 0.01


def test_notebook_horizontal_matches_default(loader):
    default = flow_notebook("永一", loader, preset="small")
    horiz = flow_notebook("永一", loader, preset="small",
                          direction="horizontal")
    # Default == horizontal
    assert [(c.x_mm, c.y_mm) for c in default[0].chars] == \
           [(c.x_mm, c.y_mm) for c in horiz[0].chars]


# ============================================================================
# Letter direction — signature block placement
# ============================================================================


def test_letter_vertical_signature_on_left(loader):
    pages = flow_letter(
        "永一日", loader, preset="A5",
        signature_text="某某",
        direction="vertical",
    )
    sb = pages[-1].signature_block
    assert sb is not None
    # Vertical letters encode signature x via 'align' field
    assert isinstance(sb.align, str) and sb.align.startswith("vertical:")


def test_letter_horizontal_signature_keeps_align(loader):
    pages = flow_letter(
        "永一日", loader, preset="A5",
        signature_text="某某",
        signature_align="right",
        direction="horizontal",
    )
    sb = pages[-1].signature_block
    assert sb is not None
    assert sb.align == "right"


# ============================================================================
# Wordart fill direction
# ============================================================================


def test_fill_positions_horizontal_vs_vertical():
    shape = Circle(100, 100, 40)
    slots_h = fill_positions(shape, 8, direction="horizontal")
    slots_v = fill_positions(shape, 8, direction="vertical")
    # Different scanning order → counts can differ slightly at shape boundary,
    # but should be within a few cells of each other.
    assert abs(len(slots_h) - len(slots_v)) <= 6
    # Both must have a reasonable number of slots for a 40mm radius circle
    assert len(slots_h) > 20
    assert len(slots_v) > 20


def test_fill_vertical_first_slot_is_rightmost_top(loader):
    shape = Circle(100, 100, 40)
    placed, _ = compute_fill(
        "永一日", shape, 8, loader,
        direction="vertical", auto_cycle=False,
    )
    # First char should be at rightmost column, near top
    first = placed[0]
    # x > cx (right side of circle)
    assert first[1] > 100
    # among ALL placed chars, first's x should be the maximum
    max_x = max(p[1] for p in placed)
    assert first[1] == max_x


# ============================================================================
# Web API — all 4 endpoints accept `direction`
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


def test_api_grid_accepts_direction(client):
    for d in ("horizontal", "vertical"):
        r = client.get(f"/api/grid?chars=永一日&cols=3&direction={d}")
        assert r.status_code == 200, f"direction={d} failed"


def test_api_grid_rejects_invalid_direction(client):
    r = client.get("/api/grid?chars=永&cols=3&direction=sideways")
    assert r.status_code == 422


def test_api_notebook_accepts_direction(client):
    for d in ("horizontal", "vertical"):
        r = client.get(f"/api/notebook?text=永一日&preset=small&direction={d}")
        assert r.status_code == 200


def test_api_letter_accepts_direction(client):
    for d in ("horizontal", "vertical"):
        r = client.get(
            f"/api/letter?text=永一日&preset=A5&signature_text=某"
            f"&direction={d}"
        )
        assert r.status_code == 200


def test_api_wordart_fill_accepts_direction(client):
    for d in ("horizontal", "vertical"):
        r = client.get(
            f"/api/wordart?shape=circle&shape_size_mm=140&layout=fill"
            f"&text=永一日永一日&direction={d}"
        )
        assert r.status_code == 200


def test_api_capacity_endpoints_accept_direction(client):
    for endpoint in ("notebook", "letter"):
        for d in ("horizontal", "vertical"):
            r = client.get(
                f"/api/{endpoint}/capacity?text=永一日&direction={d}"
            )
            assert r.status_code == 200, f"{endpoint} direction={d} failed"


def test_api_direction_produces_different_output(client):
    h = client.get(
        "/api/notebook?text=" + "永一" * 20 + "&preset=small"
        "&direction=horizontal"
    )
    v = client.get(
        "/api/notebook?text=" + "永一" * 20 + "&preset=small"
        "&direction=vertical"
    )
    # Both 200, contents different (different SVG)
    assert h.status_code == 200 and v.status_code == 200
    assert h.content != v.content
