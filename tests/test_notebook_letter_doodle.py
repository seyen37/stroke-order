"""Integration tests for notebook / letter / doodle exporters."""
import io

import pytest

try:
    from PIL import Image, ImageDraw
    import cairosvg  # noqa
    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False

from stroke_order.classifier import classify_character
from stroke_order.exporters.letter import flow_letter, render_letter_page_svg
from stroke_order.exporters.multi_page import (
    render_pages_as_single_or_zip, render_pages_as_zip,
)
from stroke_order.exporters.notebook import (
    build_notebook_layout, flow_notebook, render_notebook_page_svg,
)
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


# ----- notebook -------------------------------------------------------------


def test_notebook_small_preset(loader):
    pages = flow_notebook("春眠不覺曉", loader, preset="small")
    assert len(pages) >= 1
    svg = render_notebook_page_svg(pages[0])
    assert "<svg" in svg and "</svg>" in svg


def test_notebook_paginates_on_overflow(loader):
    # Long text on small paper should span pages
    long = "一" * 200
    pages = flow_notebook(long, loader, preset="small")
    assert len(pages) >= 2


def test_notebook_doodle_zone_skipped(loader):
    layout = build_notebook_layout(
        preset="small", doodle_zone=True, doodle_zone_size_mm=40
    )
    assert len(layout.reserve_zones) == 1
    z = layout.reserve_zones[0]
    # zone sits in bottom-right
    assert z.x_mm > layout.size.width_mm / 2
    assert z.y_mm > layout.size.height_mm / 2


# ----- letter ---------------------------------------------------------------


def test_letter_single_page(loader):
    pages = flow_letter("春眠不覺曉", loader, preset="A5",
                        title_space_mm=10, signature_space_mm=10)
    assert len(pages) == 1
    svg = render_letter_page_svg(
        pages[0], title_text="致 朋友", signature_text="2026 春")
    assert "致 朋友" in svg
    assert "2026 春" in svg


# ----- multi-page zip -------------------------------------------------------


def test_multipage_zip_contains_all_pages(loader):
    pages = flow_notebook("一" * 100, loader, preset="small")
    body, mime, ext = render_pages_as_single_or_zip(
        pages, render_notebook_page_svg, filename_prefix="test"
    )
    if len(pages) > 1:
        assert mime == "application/zip" and ext == "zip"
        # unpack and verify
        import zipfile
        zf = zipfile.ZipFile(io.BytesIO(body))
        names = zf.namelist()
        assert len(names) == len(pages)
        for i in range(1, len(pages) + 1):
            assert any(f"test-{i:02d}.svg" in n for n in names)
    else:
        assert mime == "image/svg+xml" and ext == "svg"


# ----- doodle ---------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DEPS, reason="Pillow + cairosvg required")
def test_doodle_from_circle_image():
    from stroke_order.exporters.doodle import render_doodle_svg
    img = Image.new("RGB", (200, 200), "white")
    ImageDraw.Draw(img).ellipse([30, 30, 170, 170], outline="black", width=4)
    svg = render_doodle_svg(img, canvas_width_mm=100)
    assert "<svg" in svg
    # should have some line elements
    assert svg.count("<line") + svg.count("<circle") > 5


@pytest.mark.skipif(not _HAS_DEPS, reason="Pillow required")
def test_doodle_with_annotations():
    from stroke_order.exporters.doodle import render_doodle_svg
    from stroke_order.layouts import Annotation
    img = Image.new("RGB", (100, 100), "white")
    ImageDraw.Draw(img).line([10, 10, 90, 90], fill="black", width=3)
    svg = render_doodle_svg(
        img, canvas_width_mm=80,
        annotations=[Annotation("HELLO", 5, 5, 4.0)],
    )
    assert "HELLO" in svg
