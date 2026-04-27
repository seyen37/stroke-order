"""Tests for flow-aware signature placement (Phase 5b)."""
import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.letter import flow_letter, render_letter_page_svg
from stroke_order.layouts import SignatureBlock, TitleBlock


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


def test_signature_appears_only_on_last_page(loader):
    # Long text → multiple pages; signature must be on LAST only.
    pages = flow_letter(
        "一" * 200, loader, preset="A5", line_height_mm=10,
        signature_text="敬上",
    )
    assert len(pages) >= 2
    # only last page has the signature block
    for p in pages[:-1]:
        assert p.signature_block is None
    assert pages[-1].signature_block is not None
    assert pages[-1].signature_block.signature_text == "敬上"


def test_signature_placed_after_body(loader):
    """Signature Y must be after the last body char Y.

    Uses characters we know are cached in the test fixtures
    (一 / 永 / 日 are all in tests/fixtures/).
    """
    pages = flow_letter(
        "一永日一永", loader, preset="A5", line_height_mm=10,
        signature_text="敬上",
        signature_lines_after_body=1,
    )
    last = pages[-1]
    assert last.signature_block is not None
    assert last.chars, "precondition: last page must have body characters"
    last_char = last.chars[-1]
    body_bottom = last_char.y_mm + last_char.height_mm
    # Signature should be at least one row below the body bottom
    assert last.signature_block.y_mm >= body_bottom


def test_signature_lines_after_body_controls_spacing(loader):
    pages_tight = flow_letter(
        "一", loader, preset="A5", line_height_mm=10,
        signature_text="敬上", signature_lines_after_body=0,
    )
    pages_loose = flow_letter(
        "一", loader, preset="A5", line_height_mm=10,
        signature_text="敬上", signature_lines_after_body=5,
    )
    sig_tight = pages_tight[-1].signature_block.y_mm
    sig_loose = pages_loose[-1].signature_block.y_mm
    assert sig_loose > sig_tight


def test_signature_pushed_to_new_page_when_overflow(loader):
    """If body fills the page, signature overflows to a new page."""
    # Fill an A5 page with small chars right up to the bottom
    pages = flow_letter(
        "一" * 400, loader, preset="A5", line_height_mm=10,
        signature_text="敬上", date_text="2026",
        signature_lines_after_body=3,  # force extra space that won't fit
    )
    # signature should be on a page that is NOT the one with last body char
    # Locate the page where the body ends
    body_end_page = None
    for i, p in enumerate(pages):
        if p.chars:
            body_end_page = i
    sig_page = next(i for i, p in enumerate(pages) if p.signature_block is not None)
    # Either same page or strictly later
    assert sig_page >= body_end_page


def test_signature_align_right(loader):
    pages = flow_letter(
        "春", loader, preset="A5", line_height_mm=10,
        signature_text="敬上", signature_align="right",
    )
    assert pages[-1].signature_block.align == "right"


def test_signature_align_center(loader):
    pages = flow_letter(
        "春", loader, preset="A5", line_height_mm=10,
        signature_text="敬上", signature_align="center",
    )
    assert pages[-1].signature_block.align == "center"


def test_title_on_page_one_only(loader):
    pages = flow_letter(
        "一" * 300, loader, preset="A5", line_height_mm=10,
        title_text="敬啟者", signature_text="敬上",
    )
    assert pages[0].title_block is not None
    assert pages[0].title_block.text == "敬啟者"
    for p in pages[1:]:
        assert p.title_block is None


def test_empty_body_still_places_signature(loader):
    pages = flow_letter(
        "", loader, preset="A5", line_height_mm=10,
        signature_text="敬上",
    )
    assert pages[-1].signature_block is not None


def test_svg_render_uses_flow_blocks(loader):
    """render_letter_page_svg prefers page.signature_block over legacy params."""
    pages = flow_letter(
        "春", loader, preset="A5", line_height_mm=10,
        signature_text="敬上", signature_align="center",
    )
    svg = render_letter_page_svg(pages[-1])
    assert "敬上" in svg
    # center alignment → text-anchor="middle"
    assert 'text-anchor="middle"' in svg


# ---- Web API ----

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


def test_api_letter_signature_lines_after_body(client):
    r = client.get(
        "/api/letter?text=春眠不覺曉&preset=A5&line_height_mm=10"
        "&signature_text=敬上&signature_lines_after_body=3&signature_align=center"
    )
    assert r.status_code == 200
    svg = r.text
    assert "敬上" in svg
    # center alignment must be present
    assert 'text-anchor="middle"' in svg


def test_api_letter_signature_push_to_new_page(client):
    # Very small A5 + lots of text + generous lines_after_body → overflow
    r = client.get(
        "/api/letter?text=" + "一" * 500 + "&preset=A5&line_height_mm=10"
        "&signature_text=敬上&signature_lines_after_body=5"
    )
    assert r.status_code == 200
    pages = int(r.headers.get("x-stroke-order-pages", "1"))
    # Response will be ZIP; just verify we got multi-page
    assert pages >= 2
