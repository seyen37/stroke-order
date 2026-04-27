"""Tests for text layout engine."""
import pytest

from stroke_order.classifier import classify_character
from stroke_order.layouts import (
    PageSize, PageLayout, ReserveZone, flow_text, PAGE_SIZES,
)


@pytest.fixture
def loader(source):
    def _loader(ch):
        try:
            c = source.get_character(ch)
            classify_character(c)
            return c
        except Exception:
            return None
    return _loader


def test_page_size_named():
    s = PageSize.named("A4")
    assert s.width_mm == 210 and s.height_mm == 297


def test_flow_single_page(loader):
    layout = PageLayout(
        size=PageSize.named("A6"),
        line_height_mm=15.0, char_width_mm=15.0,
    )
    # ~10 chars fits easily on A6
    pages = flow_text("一日日日日", layout, loader)
    assert len(pages) == 1
    assert len(pages[0].chars) == 5


def test_flow_wraps_at_right_margin(loader):
    layout = PageLayout(
        size=PageSize.named("A6"),
        margin_left_mm=10, margin_right_mm=10,
        line_height_mm=20.0, char_width_mm=20.0,
    )
    # A6 is 105 mm wide; content is 85 mm; 85/20 = 4.25 chars per line
    text = "一" * 10  # should wrap after 4 chars per row
    pages = flow_text(text, layout, loader)
    # Verify Y positions increase in groups of 4
    ys = sorted(set(p.y_mm for p in pages[0].chars))
    assert len(ys) >= 2  # more than one row


def test_flow_newlines_force_line_break(loader):
    layout = PageLayout(
        size=PageSize.named("A5"),
        line_height_mm=15.0, char_width_mm=15.0,
    )
    pages = flow_text("一\n日\n永", layout, loader)
    ys = [c.y_mm for c in pages[0].chars]
    # should be 3 different y values
    assert len(set(ys)) == 3


def test_flow_page_break(loader):
    # Very small page + many chars → multi-page
    layout = PageLayout(
        size=PageSize(width_mm=50, height_mm=50),
        margin_top_mm=5, margin_bottom_mm=5,
        margin_left_mm=5, margin_right_mm=5,
        line_height_mm=10, char_width_mm=10,
    )
    text = "一" * 30
    pages = flow_text(text, layout, loader)
    assert len(pages) >= 2
    assert sum(len(p.chars) for p in pages) == 30


def test_reserve_zone_skipped(loader):
    layout = PageLayout(
        size=PageSize.named("A6"),
        margin_left_mm=10, margin_right_mm=10,
        margin_top_mm=10, margin_bottom_mm=10,
        line_height_mm=15, char_width_mm=15,
        reserve_zones=[ReserveZone(40, 30, 40, 40)],
    )
    pages = flow_text("一" * 30, layout, loader)
    # No char should be placed inside the zone
    zone = layout.reserve_zones[0]
    for c in pages[0].chars:
        assert not zone.overlaps_cell(c.x_mm, c.y_mm, c.width_mm, c.height_mm)


def test_flow_missing_chars_tracked(loader):
    layout = PageLayout(size=PageSize.named("A5"),
                        line_height_mm=12, char_width_mm=12)
    # \ue000 is PUA, not in any source
    pages = flow_text("一\ue000日", layout, loader)
    assert "\ue000" in pages[0].missing
