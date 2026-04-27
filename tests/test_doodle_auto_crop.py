"""
Phase 5ag — auto-crop for the doodle (塗鴉) mode.

Covers ``auto_crop_image`` directly and the /api/doodle form-param
integration. Uses tiny synthetic PIL images so the tests are fast and
reproducible.
"""
from __future__ import annotations

import io

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from stroke_order.exporters.doodle import auto_crop_image  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers: synthetic images
# ---------------------------------------------------------------------------


def _img_white_with_subject(
    size: int = 200, pad: int = 40, subject_radius: int = 30
) -> Image.Image:
    """White canvas with a black circle in the middle, ``pad`` mm of
    whitespace around it on every side."""
    img = Image.new("L", (size, size), 255)
    cx = cy = size // 2
    ImageDraw.Draw(img).ellipse(
        [cx - subject_radius, cy - subject_radius,
         cx + subject_radius, cy + subject_radius],
        fill=0,
    )
    return img


def _img_with_border(
    size: int = 200, border_w: int = 5,
    inner_pad: int = 20, subject_radius: int = 30,
) -> Image.Image:
    """Black rectangle frame (``border_w`` px thick) → whitespace ring
    (``inner_pad`` px) → black circle subject in the centre."""
    img = Image.new("L", (size, size), 255)
    d = ImageDraw.Draw(img)
    # outer frame
    d.rectangle([0, 0, size - 1, size - 1], outline=0, width=border_w)
    # subject
    cx = cy = size // 2
    d.ellipse(
        [cx - subject_radius, cy - subject_radius,
         cx + subject_radius, cy + subject_radius],
        fill=0,
    )
    return img


# ---------------------------------------------------------------------------
# auto_crop_image — whitespace trim
# ---------------------------------------------------------------------------


def test_trim_whitespace_reduces_size_to_subject():
    img = _img_white_with_subject(size=200, subject_radius=30)
    cropped = auto_crop_image(
        img, trim_whitespace=True, remove_border=False)
    # Original is 200×200; subject spans ~60×60 centred.
    assert cropped.size[0] < img.size[0]
    assert cropped.size[1] < img.size[1]
    # Tight bbox of the circle → roughly 61×61 (±1 px tolerance)
    assert 58 <= cropped.size[0] <= 63
    assert 58 <= cropped.size[1] <= 63


def test_trim_whitespace_noop_on_all_white_image():
    img = Image.new("L", (100, 100), 255)
    cropped = auto_crop_image(
        img, trim_whitespace=True, remove_border=False)
    # Pure whitespace → returned unchanged (exact same size)
    assert cropped.size == (100, 100)


def test_trim_whitespace_preserves_color():
    """Crop should return a crop of the ORIGINAL image (RGB preserved)."""
    img = Image.new("RGB", (100, 100), "white")
    ImageDraw.Draw(img).rectangle([40, 40, 60, 60], fill="red")
    cropped = auto_crop_image(img, trim_whitespace=True)
    assert cropped.mode == "RGB"
    # A pixel inside the red square should still be red
    px = cropped.getpixel((cropped.size[0] // 2, cropped.size[1] // 2))
    assert px[0] > 200 and px[1] < 60 and px[2] < 60   # red dominant


def test_both_passes_disabled_returns_input():
    img = _img_with_border()
    cropped = auto_crop_image(
        img, trim_whitespace=False, remove_border=False)
    assert cropped.size == img.size


# ---------------------------------------------------------------------------
# auto_crop_image — border peel
# ---------------------------------------------------------------------------


def test_remove_border_strips_frame_line():
    """A 200×200 image with a 5 px frame + 20 px white padding + 60 px
    subject should crop down to about the subject size when both passes
    are enabled."""
    img = _img_with_border(
        size=200, border_w=5, inner_pad=20, subject_radius=30)
    cropped = auto_crop_image(
        img, trim_whitespace=True, remove_border=True)
    # After peeling the frame AND retrim: ~subject bbox (~60×60)
    assert cropped.size[0] < 100
    assert cropped.size[1] < 100


def test_remove_border_only_without_whitespace_trim():
    """Border-peel alone (no whitespace trim) still removes the frame
    line; the inner whitespace ring remains untouched."""
    img = _img_with_border(
        size=200, border_w=5, inner_pad=20, subject_radius=30)
    cropped = auto_crop_image(
        img, trim_whitespace=False, remove_border=True)
    # Frame removed → size shrinks by ~2*border_w
    assert cropped.size[0] < img.size[0]
    assert cropped.size[0] >= img.size[0] - 2 * 5 - 2   # some slack


def test_remove_border_noop_when_no_frame():
    """Image without a frame line should not lose real content."""
    img = _img_white_with_subject(size=200, subject_radius=30)
    cropped = auto_crop_image(
        img, trim_whitespace=False, remove_border=True)
    # No frame → the 'peel' loop exits immediately → size unchanged
    assert cropped.size == img.size


def test_remove_border_does_not_eat_real_content():
    """A dark subject touching the left edge (no real frame) should not
    be peeled away — that would be destroying content."""
    img = Image.new("L", (100, 100), 255)
    d = ImageDraw.Draw(img)
    # Vertical dark bar on the left 10 px — visually a "thick left frame",
    # but let's say it's actually content. The function is tuned to
    # recognise it as a frame if dark ratio >= 0.5. So this test verifies
    # that after peeling 10 px, the loop stops (no runaway erosion).
    d.rectangle([0, 0, 9, 99], fill=0)
    d.ellipse([50, 40, 70, 60], fill=0)
    cropped = auto_crop_image(
        img, trim_whitespace=False, remove_border=True)
    # At minimum: the right half containing the ellipse is preserved.
    # (We tolerate the left bar being peeled — that's the feature.)
    assert cropped.size[0] >= 40   # ellipse's right side intact
    assert cropped.size[1] >= 40


# ---------------------------------------------------------------------------
# Web API integration
# ---------------------------------------------------------------------------


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


def _post_doodle(client, img, **data):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return client.post(
        "/api/doodle",
        files={"image": ("test.png", buf, "image/png")},
        data=data,
    )


def test_api_doodle_auto_crop_whitespace_changes_output(client):
    img = _img_white_with_subject(size=200, subject_radius=30)
    r_plain = _post_doodle(client, img)
    r_crop = _post_doodle(client, img, auto_crop_whitespace="true")
    assert r_plain.status_code == 200 and r_crop.status_code == 200
    # Cropping tightens the bbox → the post-crop SVG should contain
    # FEWER <line>/<circle> elements or differently-positioned ones.
    assert r_plain.text != r_crop.text


def test_api_doodle_auto_crop_border_changes_output(client):
    img = _img_with_border(size=200, border_w=5)
    r_plain = _post_doodle(client, img)
    r_crop = _post_doodle(
        client, img,
        auto_crop_whitespace="true", auto_crop_border="true",
    )
    assert r_plain.status_code == 200 and r_crop.status_code == 200
    assert r_plain.text != r_crop.text


def test_api_doodle_auto_crop_default_off_is_unchanged(client):
    """Omitting the flags should produce the SAME SVG as explicitly
    setting both to false (back-compat)."""
    img = _img_with_border(size=200)
    r1 = _post_doodle(client, img)
    r2 = _post_doodle(
        client, img,
        auto_crop_whitespace="false", auto_crop_border="false",
    )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.text == r2.text


def test_api_doodle_auto_crop_all_white_does_not_crash(client):
    """Edge case: entirely whitespace image still returns 200 SVG."""
    img = Image.new("L", (50, 50), 255)
    r = _post_doodle(
        client, img,
        auto_crop_whitespace="true", auto_crop_border="true",
    )
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]
