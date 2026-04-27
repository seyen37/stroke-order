"""Tests for ODP (OpenDocument Presentation) exporter."""
import zipfile
from pathlib import Path

import pytest

try:
    import cairosvg  # noqa
    _HAS_CAIRO = True
except ImportError:
    _HAS_CAIRO = False

pytestmark = pytest.mark.skipif(
    not _HAS_CAIRO, reason="cairosvg required for ODP"
)

from stroke_order.classifier import classify_character
from stroke_order.exporters.odp import save_odp
from stroke_order.smoothing import smooth_character


def _prep(source, chars: str):
    out = []
    for ch in chars:
        c = source.get_character(ch)
        classify_character(c)
        smooth_character(c)
        out.append(c)
    return out


def test_odp_is_valid_zip(source, tmp_path: Path):
    chars = _prep(source, "永")
    out = tmp_path / "test.odp"
    save_odp(chars, str(out))
    assert out.is_file()

    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        # ODP required files
        assert "mimetype" in names
        assert "content.xml" in names
        assert "styles.xml" in names
        assert "META-INF/manifest.xml" in names
        # per-char images
        assert "Pictures/char0.png" in names
        # mimetype is uncompressed and correct
        info = z.getinfo("mimetype")
        assert info.compress_type == zipfile.ZIP_STORED
        assert z.read("mimetype") == (
            b"application/vnd.oasis.opendocument.presentation"
        )


def test_odp_slide_count_matches_chars(source, tmp_path: Path):
    chars = _prep(source, "永日一")  # 3 slides (all chars present in fixtures)
    out = tmp_path / "triple.odp"
    save_odp(chars, str(out))

    with zipfile.ZipFile(out) as z:
        content = z.read("content.xml").decode("utf-8")
        assert content.count("<draw:page") == 3
        # per-slide image refs
        for i in range(3):
            assert f"Pictures/char{i}.png" in content


def test_odp_content_xml_contains_metadata(source, tmp_path: Path):
    chars = _prep(source, "永")
    out = tmp_path / "meta.odp"
    save_odp(chars, str(out))
    with zipfile.ZipFile(out) as z:
        content = z.read("content.xml").decode("utf-8")
    # Should mention Unicode codepoint and stroke count
    assert "U+6C38" in content
    assert "5" in content  # 5 strokes for 永
