"""
GIF animation exporter — render progressive stroke-order animation as a
single animated GIF file.

Each frame shows strokes 1..N drawn so far, with stroke N highlighted
(thicker, different colour). Useful for documentation, teaching materials,
and sharing on social media.

Dependencies
------------

Requires ``cairosvg`` (for SVG→PNG rendering per frame) and ``Pillow``
(for GIF assembly). These are installed via::

    pip install stroke-order[gif]
"""
from __future__ import annotations

import io
from typing import Optional

from ..ir import Character, Stroke
from .svg import _outline_path_d, _rainbow_color


def _frame_svg(
    char: Character,
    upto: int,
    *,
    width_px: int = 300,
    height_px: int = 300,
    base_color: str = "#333",
    highlight_color: str = "#c33",
    show_numbers: bool = True,
) -> str:
    """
    Render the N-th frame: strokes 0..upto-1 in base_color, stroke (upto-1)
    highlighted. upto=0 produces an empty character (just the guide grid).
    Returns an SVG string.
    """
    em = 2048
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {em} {em}" '
        f'width="{width_px}" height="{height_px}">'
    ]
    # explicit white background (PNG rendering needs this; style="background:"
    # is not part of SVG spec and many renderers ignore it)
    parts.append(
        f'<rect x="0" y="0" width="{em}" height="{em}" fill="white"/>'
    )
    # light guide grid (田字格)
    half = em // 2
    parts.append(
        f'<g stroke="#eee" stroke-width="2" fill="none">'
        f'<rect x="0" y="0" width="{em}" height="{em}"/>'
        f'<line x1="{half}" y1="0" x2="{half}" y2="{em}"/>'
        f'<line x1="0" y1="{half}" x2="{em}" y2="{half}"/>'
        f'</g>'
    )
    # completed strokes (dimmer)
    parts.append('<g class="completed">')
    for i in range(min(upto, len(char.strokes))):
        s = char.strokes[i]
        col = highlight_color if i == upto - 1 else base_color
        d = _outline_path_d(s)
        parts.append(f'<path d="{d}" fill="{col}"/>')
    parts.append("</g>")
    # stroke number labels
    if show_numbers:
        parts.append('<g fill="#008" font-family="sans-serif" font-weight="bold">')
        for i in range(min(upto, len(char.strokes))):
            s = char.strokes[i]
            if not s.raw_track:
                continue
            p = s.raw_track[0]
            parts.append(
                f'<text x="{p.x - 40}" y="{p.y - 20}" font-size="140">{i+1}</text>'
            )
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def render_frames_as_pngs(
    char: Character,
    *,
    width_px: int = 300,
    height_px: int = 300,
    show_numbers: bool = True,
    final_hold_count: int = 3,
    empty_lead_count: int = 1,
) -> list[bytes]:
    """
    Render the full animation frame sequence as PNG bytes.

    The sequence is: [empty × lead] + [1..N strokes] + [N × hold]
    """
    try:
        import cairosvg
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "GIF export requires cairosvg. Install with: pip install cairosvg"
        ) from e

    frames_svg: list[str] = []
    for _ in range(empty_lead_count):
        frames_svg.append(_frame_svg(
            char, 0, width_px=width_px, height_px=height_px,
            show_numbers=show_numbers,
        ))
    for i in range(1, len(char.strokes) + 1):
        frames_svg.append(_frame_svg(
            char, i, width_px=width_px, height_px=height_px,
            show_numbers=show_numbers,
        ))
    # Hold on the last frame
    final = frames_svg[-1] if frames_svg else _frame_svg(char, 0)
    for _ in range(final_hold_count):
        frames_svg.append(final)

    pngs: list[bytes] = []
    for svg in frames_svg:
        png_bytes = cairosvg.svg2png(
            bytestring=svg.encode("utf-8"),
            output_width=width_px,
            output_height=height_px,
        )
        pngs.append(png_bytes)
    return pngs


def save_gif(
    char: Character,
    path: str,
    *,
    width_px: int = 300,
    height_px: int = 300,
    frame_duration_ms: int = 500,
    show_numbers: bool = True,
) -> None:
    """
    Render and save an animated GIF for ``char`` at ``path``.

    Parameters
    ----------
    frame_duration_ms
        Duration of each frame (default 500 ms = 2 fps).
    """
    try:
        from PIL import Image
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "GIF export requires Pillow. Install with: pip install Pillow"
        ) from e

    pngs = render_frames_as_pngs(
        char, width_px=width_px, height_px=height_px, show_numbers=show_numbers,
    )
    # Flatten alpha channels onto white so GIF palette works, then convert to
    # adaptive palette for GIF encoding.
    images: list[Image.Image] = []
    for b in pngs:
        im = Image.open(io.BytesIO(b))
        if im.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", im.size, "white")
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        images.append(im.convert("P", palette=Image.ADAPTIVE, colors=128))
    if not images:
        raise ValueError("no frames produced")

    images[0].save(
        path,
        save_all=True,
        append_images=images[1:],
        duration=frame_duration_ms,
        loop=0,        # infinite loop
        optimize=True,
        # disposal=2 replaces frame; but since our frames are cumulative
        # full-canvas, disposal=1 (leave as-is) would also work. Use 2 for
        # safety across GIF decoders.
        disposal=2,
    )


__all__ = ["save_gif", "render_frames_as_pngs"]
