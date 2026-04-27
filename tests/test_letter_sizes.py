"""Tests for letter-mode title/signature/date size tuning."""
import re

import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.letter import flow_letter, render_letter_page_svg
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


def _font_sizes_in(svg: str) -> list[float]:
    return sorted(float(x) for x in re.findall(r'font-size="([\d.]+)"', svg))


def test_title_size_defaults_to_char_size(loader):
    pages = flow_letter(
        "春眠不覺曉", loader, preset="A5",
        line_height_mm=9, signature_space_mm=15,
    )
    svg = render_letter_page_svg(
        pages[0], title_text="敬啟者", signature_text="敬上"
    )
    # Title and signature should use char_size (9mm) since no override
    sizes = _font_sizes_in(svg)
    # 9 appears twice (title + sig), date not included, footer is 3
    assert 9.0 in sizes


def test_title_size_override(loader):
    pages = flow_letter("春", loader, preset="A5", line_height_mm=9)
    svg = render_letter_page_svg(
        pages[0], title_text="敬啟者",
        title_size_mm=15, signature_text="敬上", signature_size_mm=7,
    )
    sizes = _font_sizes_in(svg)
    assert 15.0 in sizes
    assert 7.0 in sizes


def test_date_line_rendered(loader):
    pages = flow_letter("春", loader, preset="A5",
                        line_height_mm=9, signature_space_mm=25)
    svg = render_letter_page_svg(
        pages[0],
        signature_text="學生 敬上",
        date_text="2026 年 春",
    )
    assert "2026 年 春" in svg
    # date defaults to 0.75 × signature (9 × 0.75 = 6.75)
    sizes = _font_sizes_in(svg)
    assert 6.75 in sizes


def test_date_size_override(loader):
    pages = flow_letter("春", loader, preset="A5", line_height_mm=10)
    svg = render_letter_page_svg(
        pages[0], signature_text="敬上", signature_size_mm=8,
        date_text="2026", date_size_mm=4,
    )
    sizes = _font_sizes_in(svg)
    assert 4.0 in sizes
    assert 8.0 in sizes


def test_date_without_signature(loader):
    pages = flow_letter("春", loader, preset="A5", line_height_mm=9)
    svg = render_letter_page_svg(pages[0], date_text="2026")
    # date still appears
    assert "2026" in svg


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


def test_api_letter_with_date(client):
    r = client.get(
        "/api/letter?text=春眠不覺曉&preset=A5"
        "&title_text=敬啟者&signature_text=敬上&date_text=2026年春"
        "&title_size_mm=8&signature_size_mm=6&date_size_mm=4"
    )
    assert r.status_code == 200
    svg = r.text
    assert "敬啟者" in svg
    assert "2026年春" in svg
    sizes = _font_sizes_in(svg)
    assert 8.0 in sizes
    assert 6.0 in sizes
    assert 4.0 in sizes


def test_api_letter_autosize_defaults(client):
    """Omitting size params → sizes track line_height_mm."""
    r = client.get(
        "/api/letter?text=春&preset=A5&line_height_mm=12"
        "&title_text=X&signature_text=Y&date_text=Z"
    )
    assert r.status_code == 200
    sizes = _font_sizes_in(r.text)
    assert 12.0 in sizes  # title and signature
    assert 9.0 in sizes   # date = 12 × 0.75
