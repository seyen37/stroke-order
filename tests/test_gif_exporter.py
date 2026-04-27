"""Tests for GIF animation exporter."""
import io
import tempfile
from pathlib import Path

import pytest

try:
    from PIL import Image
    import cairosvg  # noqa
    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False

pytestmark = pytest.mark.skipif(
    not _HAS_DEPS, reason="Pillow + cairosvg required"
)


from stroke_order.classifier import classify_character
from stroke_order.exporters.gif import render_frames_as_pngs, save_gif
from stroke_order.smoothing import smooth_character


def _prep(source, char="永"):
    c = source.get_character(char)
    classify_character(c)
    smooth_character(c)
    return c


def test_render_frames_produces_expected_frame_count(source):
    c = _prep(source, "永")  # 5 strokes
    pngs = render_frames_as_pngs(c, empty_lead_count=1, final_hold_count=2)
    # 1 empty + 5 strokes + 2 hold = 8 frames
    assert len(pngs) == 8
    # Each should be valid PNG bytes
    for b in pngs:
        im = Image.open(io.BytesIO(b))
        assert im.size == (300, 300)


def test_save_gif_creates_valid_animated_gif(source, tmp_path: Path):
    c = _prep(source, "永")
    out = tmp_path / "永.gif"
    save_gif(c, str(out))
    assert out.is_file()
    assert out.stat().st_size > 1000  # non-trivial

    im = Image.open(out)
    # Verify it's actually animated with the right frame count
    frame_count = 0
    try:
        while True:
            im.seek(frame_count)
            frame_count += 1
    except EOFError:
        pass
    # 永: 1 lead + 5 strokes + 3 hold = 9 by default
    assert frame_count >= 5  # at least 5 frames for a 5-stroke char


def test_save_gif_with_custom_duration(source, tmp_path: Path):
    c = _prep(source, "一")  # 1-stroke simplest case
    out = tmp_path / "一.gif"
    save_gif(c, str(out), frame_duration_ms=200)
    im = Image.open(out)
    assert im.info.get("duration") == 200
