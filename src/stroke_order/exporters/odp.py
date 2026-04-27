"""
OpenDocument Presentation (.odp) exporter — for教師備課.

Produces a .odp file containing one slide per character. Each slide shows
the character's outline-mode SVG embedded as an image. The ODP file is
a standard zip archive with specific XML manifests; we build it by hand
so there's no external dependency beyond Python's stdlib + cairosvg for
the embedded PNG rasterisation.

The resulting file opens natively in:
  - LibreOffice Impress
  - Google Slides (after upload; format preserved)
  - MS PowerPoint (import mode)
  - Canva

Inspiration: gsyan888's svg2odp conversion workflow (2024/05 blog post).
"""
from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from ..ir import Character
from .svg import character_to_svg

# Slide dimensions (cm) — standard 25.4 × 19.05 → 4:3
SLIDE_WIDTH_CM = 25.4
SLIDE_HEIGHT_CM = 19.05

# Where the character image sits on each slide (cm)
IMG_X_CM = 3.0
IMG_Y_CM = 3.5
IMG_W_CM = 12.0
IMG_H_CM = 12.0

# Right column — metadata text
META_X_CM = 16.0
META_Y_CM = 3.5
META_W_CM = 8.0


_MIMETYPE = "application/vnd.oasis.opendocument.presentation"


def _manifest_xml(num_images: int) -> str:
    file_entries = [
        '<manifest:file-entry manifest:full-path="/" '
        'manifest:version="1.2" '
        f'manifest:media-type="{_MIMETYPE}"/>',
        '<manifest:file-entry manifest:full-path="content.xml" '
        'manifest:media-type="text/xml"/>',
        '<manifest:file-entry manifest:full-path="styles.xml" '
        'manifest:media-type="text/xml"/>',
        '<manifest:file-entry manifest:full-path="meta.xml" '
        'manifest:media-type="text/xml"/>',
    ]
    for i in range(num_images):
        file_entries.append(
            f'<manifest:file-entry manifest:full-path="Pictures/char{i}.png" '
            f'manifest:media-type="image/png"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest:manifest '
        'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
        'manifest:version="1.2">\n'
        + "\n".join(file_entries)
        + "\n</manifest:manifest>\n"
    )


def _meta_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-meta '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'office:version="1.2">'
        '<office:meta>'
        '<meta:generator>stroke-order 0.4</meta:generator>'
        '<dc:title>Chinese Character Stroke Order</dc:title>'
        '</office:meta></office:document-meta>\n'
    )


def _styles_xml() -> str:
    """Minimal styles.xml — slide master and page layout."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-styles '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
        'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
        'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
        'office:version="1.2">'
        '<office:automatic-styles>'
        '<style:page-layout style:name="pl1">'
        f'<style:page-layout-properties fo:page-width="{SLIDE_WIDTH_CM}cm" '
        f'fo:page-height="{SLIDE_HEIGHT_CM}cm" '
        'style:print-orientation="landscape"/>'
        '</style:page-layout>'
        '</office:automatic-styles>'
        '<office:master-styles>'
        '<style:master-page style:name="Default" style:page-layout-name="pl1">'
        '</style:master-page>'
        '</office:master-styles>'
        '</office:document-styles>\n'
    )


def _slide_xml(idx: int, char: Character) -> str:
    """Build one <draw:page> element with image + metadata text."""
    # metadata block
    meta_lines: list[str] = [f"{char.char} (U+{char.unicode_hex.upper()})"]
    meta_lines.append(f"{char.stroke_count} 筆  筆順: {char.signature}")
    if char.radical_category:
        meta_lines.append(f"部首: {char.radical_category}")
    if char.decomposition is not None:
        d = char.decomposition
        meta_lines.append(f"類別: {d.category} / {d.earliest_form or '?'}")
        if d.head_root:
            meta_lines.append(f"首: {d.head_root} ({d.head_role or '?'})")
            meta_lines.append(f"    {d.head_def}")
        if d.tail_root:
            meta_lines.append(f"尾: {d.tail_root} ({d.tail_role or '?'})")
            meta_lines.append(f"    {d.tail_def}")
        if d.concept:
            meta_lines.append(f"概念: {d.concept}")
    meta_body = "".join(
        f'<text:p>{_escape(line)}</text:p>' for line in meta_lines
    )

    return (
        f'<draw:page draw:name="Slide{idx+1}" '
        f'draw:master-page-name="Default">'
        # Image frame
        f'<draw:frame draw:name="CharImg{idx}" '
        f'svg:x="{IMG_X_CM}cm" svg:y="{IMG_Y_CM}cm" '
        f'svg:width="{IMG_W_CM}cm" svg:height="{IMG_H_CM}cm">'
        f'<draw:image xlink:href="Pictures/char{idx}.png" '
        f'xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/>'
        f'</draw:frame>'
        # Metadata text frame
        f'<draw:frame draw:name="MetaTxt{idx}" '
        f'svg:x="{META_X_CM}cm" svg:y="{META_Y_CM}cm" '
        f'svg:width="{META_W_CM}cm" svg:height="12cm">'
        f'<draw:text-box>{meta_body}</draw:text-box>'
        f'</draw:frame>'
        f'</draw:page>'
    )


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
              .replace('"', "&quot;"))


def _content_xml(chars: list[Character]) -> str:
    slides = "".join(_slide_xml(i, c) for i, c in enumerate(chars))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
        'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        'office:version="1.2">'
        '<office:body><office:presentation>'
        + slides +
        '</office:presentation></office:body>'
        '</office:document-content>\n'
    )


def _render_char_png(char: Character, size_px: int = 800) -> bytes:
    """Render a character to a PNG using cairosvg."""
    import cairosvg
    svg = character_to_svg(
        char, mode="both", show_numbers=True,
        width_px=size_px, height_px=size_px,
    )
    return cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        output_width=size_px,
        output_height=size_px,
    )


def save_odp(chars: list[Character], path: str, *,
             img_size_px: int = 1200) -> None:
    """
    Write an .odp file with one slide per character.

    Parameters
    ----------
    chars
        List of Character objects (should have classifier/smoothing/decomp
        already applied).
    path
        Output .odp file path.
    img_size_px
        Resolution of the embedded character PNGs.
    """
    try:
        import cairosvg  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "ODP export needs cairosvg. Install with: pip install cairosvg"
        ) from e

    pngs = [_render_char_png(c, img_size_px) for c in chars]

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # ODP requires mimetype be the FIRST entry AND uncompressed
        zf.writestr(
            zipfile.ZipInfo("mimetype"),
            _MIMETYPE,
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr("META-INF/manifest.xml", _manifest_xml(len(chars)))
        zf.writestr("meta.xml", _meta_xml())
        zf.writestr("styles.xml", _styles_xml())
        zf.writestr("content.xml", _content_xml(chars))
        for i, data in enumerate(pngs):
            zf.writestr(f"Pictures/char{i}.png", data)


__all__ = ["save_odp"]
