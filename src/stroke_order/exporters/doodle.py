"""
Doodle / simple-sketch exporter.

Takes a raster image (PNG/JPG/etc.) and produces a clean SVG line-drawing
in a 簡筆畫 style — usable as a decorative illustration for notebook or
letter pages, or a standalone "doodle" page with user-supplied text
annotations.

Algorithm (intentionally simple, no external CV libraries required):

1. Load + downsample image (max 200 px on longest side) for speed and
   to keep output SVG small.
2. Convert to grayscale.
3. Edge-detect via PIL's ``ImageFilter.FIND_EDGES`` (3×3 Laplacian-ish).
4. Threshold to a binary edge map.
5. Run-length encode each row — consecutive edge pixels become one
   ``<line>``. Short singletons (< 2 px) become small ``<rect>``s so
   they stay visible.
6. Emit all edges as stroked SVG paths against a white background.

The result is a compact, printable line drawing. Not as clean as a proper
potrace vectorisation, but it needs zero non-stdlib dependencies beyond
Pillow and numpy (both already required).
"""
from __future__ import annotations

import io
from typing import Optional

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from ..layouts import Annotation
from .page import _annotations_svg, _xml_escape


# ---------------------------------------------------------------------------
# Auto-crop (Phase 5ag) — trim whitespace and/or peel a rectangular frame
# ---------------------------------------------------------------------------


def _content_bbox(gray: np.ndarray, whitespace_threshold: int) -> Optional[
        tuple[int, int, int, int]]:
    """Bounding box of non-whitespace pixels in ``gray`` (HxW uint8).

    A pixel counts as "content" when its grayscale value is ``<=`` the
    whitespace_threshold (darker than near-white). Returns ``(left, top,
    right, bottom)`` with right/bottom EXCLUSIVE, or ``None`` if the
    whole image is whitespace.
    """
    content = gray <= whitespace_threshold
    if not content.any():
        return None
    rows = content.any(axis=1)
    cols = content.any(axis=0)
    top = int(np.argmax(rows))
    bottom = int(len(rows) - np.argmax(rows[::-1]))
    left = int(np.argmax(cols))
    right = int(len(cols) - np.argmax(cols[::-1]))
    return left, top, right, bottom


def _peel_border(
    gray: np.ndarray,
    *,
    darkness_threshold: int,
    min_ratio: float,
    max_peel_px: int,
) -> tuple[int, int, int, int]:
    """Count how many rows/columns to peel from each side so the remaining
    image no longer has a dark "frame line" along its outermost edge.

    A side is peeled when the fraction of dark pixels (≤ ``darkness_threshold``)
    on its outermost row/column reaches ``min_ratio``. The loop stops when
    no side qualifies OR ``max_peel_px`` has been consumed on any side.
    Returns ``(top, bottom, left, right)`` peel counts in pixels.
    """
    H0, W0 = gray.shape
    top = bottom = left = right = 0
    while True:
        if H0 - top - bottom < 4 or W0 - left - right < 4:
            break
        if (top >= max_peel_px and bottom >= max_peel_px
                and left >= max_peel_px and right >= max_peel_px):
            break
        sub = gray[top:H0 - bottom, left:W0 - right]
        sH, sW = sub.shape
        dark_top = (sub[0] <= darkness_threshold).sum() / sW
        dark_bot = (sub[sH - 1] <= darkness_threshold).sum() / sW
        dark_left = (sub[:, 0] <= darkness_threshold).sum() / sH
        dark_right = (sub[:, sW - 1] <= darkness_threshold).sum() / sH
        peeled_any = False
        if dark_top >= min_ratio and top < max_peel_px:
            top += 1
            peeled_any = True
        if dark_bot >= min_ratio and bottom < max_peel_px:
            bottom += 1
            peeled_any = True
        if dark_left >= min_ratio and left < max_peel_px:
            left += 1
            peeled_any = True
        if dark_right >= min_ratio and right < max_peel_px:
            right += 1
            peeled_any = True
        if not peeled_any:
            break
    return top, bottom, left, right


def auto_crop_image(
    img: Image.Image,
    *,
    trim_whitespace: bool = True,
    remove_border: bool = False,
    whitespace_threshold: int = 240,
    border_darkness_threshold: int = 100,
    border_min_ratio: float = 0.5,
    max_border_px: int = 40,
) -> Image.Image:
    """Return a cropped copy of ``img`` with outer whitespace and/or a
    rectangular frame line removed.

    Two independent passes (either can be disabled):

    - ``trim_whitespace``: find the bounding box of non-whitespace pixels
      (``gray <= whitespace_threshold``) and crop the image to that box.
    - ``remove_border``: iteratively peel rows/columns from the outside
      whose dark-pixel ratio (``gray <= border_darkness_threshold``)
      reaches ``border_min_ratio`` — i.e. a continuous thin frame line.
      After peeling the frame, whitespace inside it (common on scanned
      frames with a white gap) is trimmed too.

    Parameters
    ----------
    whitespace_threshold
        Grayscale value up to which a pixel counts as "content" (rather
        than background whitespace). Default 240 on 0-255 scale.
    border_darkness_threshold
        Grayscale value up to which a pixel counts as "dark" when
        detecting frame lines. Default 100.
    border_min_ratio
        Minimum fraction of dark pixels required on a row/column for it
        to be considered part of a frame and peeled. Default 0.5 catches
        full-width frames while rejecting most text-line rows.
    max_border_px
        Safety cap on per-side peel count (prevents runaway erosion on
        pathological inputs).

    If the input has no detectable content (all whitespace), the image
    is returned unchanged.
    """
    if not (trim_whitespace or remove_border):
        return img

    # Work on a grayscale view so the operations are color-independent,
    # but crop the ORIGINAL image to preserve full color/alpha on output.
    base = img
    gray = np.array(base.convert("L"))

    L, T = 0, 0
    W, H = gray.shape[1], gray.shape[0]
    R, B = W, H

    # ---- Pass 1: whitespace trim ----
    if trim_whitespace:
        bbox = _content_bbox(gray, whitespace_threshold)
        if bbox is None:
            # Pure whitespace image — nothing we can meaningfully crop.
            return img
        L, T, R, B = bbox

    # ---- Pass 2: border peel (operates on the current crop region) ----
    if remove_border and R - L >= 4 and B - T >= 4:
        sub = gray[T:B, L:R]
        pt, pb, pl, pr = _peel_border(
            sub,
            darkness_threshold=border_darkness_threshold,
            min_ratio=border_min_ratio,
            max_peel_px=max_border_px,
        )
        L += pl
        T += pt
        R -= pr
        B -= pb
        # Re-trim whitespace inside the frame (scanned frames often have
        # a white margin between the frame line and the actual subject).
        if (pt or pb or pl or pr) and trim_whitespace and R - L >= 2 and B - T >= 2:
            inner = gray[T:B, L:R]
            bbox2 = _content_bbox(inner, whitespace_threshold)
            if bbox2 is not None:
                ll, tt, rr, bb = bbox2
                L, T = L + ll, T + tt
                R, B = L + (rr - ll), T + (bb - tt)

    # Clamp + guard against degenerate outputs
    L = max(0, min(L, W - 1))
    T = max(0, min(T, H - 1))
    R = max(L + 1, min(R, W))
    B = max(T + 1, min(B, H))
    if (L, T, R, B) == (0, 0, W, H):
        return img   # no-op crop; avoid copy
    return base.crop((L, T, R, B))


# ---------------------------------------------------------------------------
# Image preprocessing
# ---------------------------------------------------------------------------

def _prepare(img: Image.Image, max_side_px: int = 200) -> Image.Image:
    """Downsample + grayscale + normalize, returns PIL Image in 'L' mode."""
    if img.mode not in ("L", "RGB", "RGBA"):
        img = img.convert("RGB")
    # downsample
    w, h = img.size
    scale = max_side_px / max(w, h)
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    # flatten alpha onto white
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.split()[-1])
        img = bg
    gray = img.convert("L")
    # stretch contrast so edges stand out
    gray = ImageOps.autocontrast(gray, cutoff=2)
    return gray


def _edge_binary(img: Image.Image, threshold: int = 50) -> np.ndarray:
    """Run FIND_EDGES and threshold → H×W boolean ndarray."""
    edges = img.filter(ImageFilter.FIND_EDGES)
    arr = np.array(edges, dtype=np.int16)
    return arr > threshold


# ---------------------------------------------------------------------------
# Run-length encoding: binary edges → list of horizontal lines
# ---------------------------------------------------------------------------

def _rle_rows(binary: np.ndarray) -> list[tuple[int, int, int]]:
    """Scan each row for runs of True; return list of (y, x_start, x_end_exclusive)."""
    runs: list[tuple[int, int, int]] = []
    H, W = binary.shape
    for y in range(H):
        row = binary[y]
        # find indices of transitions
        diffs = np.diff(row.astype(np.int8))
        starts = np.where(diffs == 1)[0] + 1
        ends = np.where(diffs == -1)[0] + 1
        if row[0]:
            starts = np.concatenate(([0], starts))
        if row[-1]:
            ends = np.concatenate((ends, [W]))
        for s, e in zip(starts, ends):
            if e > s:
                runs.append((y, int(s), int(e)))
    return runs


# ---------------------------------------------------------------------------
# SVG rendering
# ---------------------------------------------------------------------------

def render_doodle_svg(
    img: Image.Image,
    *,
    canvas_width_mm: float = 150.0,
    canvas_height_mm: Optional[float] = None,
    max_side_px: int = 200,
    threshold: int = 50,
    line_color: str = "#222",
    line_width: float = 0.4,
    background: str = "white",
    annotations: Optional[list[Annotation]] = None,
    margin_mm: float = 10.0,
) -> str:
    """
    Convert an image to a doodle SVG with optional text annotations.

    Parameters
    ----------
    img
        PIL Image (will be downsampled).
    canvas_width_mm, canvas_height_mm
        Target physical size of the output. If height is None, computed
        from image aspect ratio.
    max_side_px
        Max dimension in pixels after downsampling. Lower → simpler doodle.
    threshold
        Edge detection threshold (0-255). Higher → fewer lines.
    line_color, line_width
        SVG stroke appearance.
    background
        Canvas fill color.
    annotations
        Optional list of text annotations in mm coords.
    margin_mm
        Padding around the image inside the canvas.

    Returns
    -------
    Complete standalone SVG string (unit = mm).
    """
    gray = _prepare(img, max_side_px=max_side_px)
    binary = _edge_binary(gray, threshold=threshold)
    H, W = binary.shape

    # Compute canvas size
    aspect = H / W
    inner_w = canvas_width_mm - 2 * margin_mm
    inner_h = inner_w * aspect
    if canvas_height_mm is None:
        canvas_height_mm = inner_h + 2 * margin_mm
    else:
        # if user specified, constrain image proportionally
        available_h = canvas_height_mm - 2 * margin_mm
        if inner_h > available_h:
            inner_h = available_h
            inner_w = inner_h / aspect

    # Scale: image px → mm
    sx = inner_w / W
    sy = inner_h / H

    runs = _rle_rows(binary)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {canvas_width_mm} {canvas_height_mm}" '
        f'width="{canvas_width_mm}mm" height="{canvas_height_mm}mm">'
    ]
    parts.append(
        f'<rect x="0" y="0" width="{canvas_width_mm}" '
        f'height="{canvas_height_mm}" fill="{_xml_escape(background)}"/>'
    )
    # Translate image group to inside the margin
    parts.append(f'<g transform="translate({margin_mm},{margin_mm})" '
                 f'stroke="{_xml_escape(line_color)}" fill="none" '
                 f'stroke-width="{line_width}" stroke-linecap="round">')
    # Emit runs as <line>. Y = (y+0.5)*sy so lines sit mid-row.
    for (y, xs, xe) in runs:
        x1 = xs * sx
        x2 = xe * sx
        ym = (y + 0.5) * sy
        # ensure visible dot for singletons
        if xe - xs == 1:
            parts.append(f'<circle cx="{x1 + sx/2:.2f}" cy="{ym:.2f}" '
                         f'r="{sx*0.4:.2f}" fill="{_xml_escape(line_color)}" '
                         f'stroke="none"/>')
        else:
            parts.append(
                f'<line x1="{x1:.2f}" y1="{ym:.2f}" '
                f'x2="{x2:.2f}" y2="{ym:.2f}"/>'
            )
    parts.append("</g>")
    # annotations
    parts.append(_annotations_svg(annotations or []))
    parts.append("</svg>")
    return "\n".join(parts)


def save_doodle_svg(
    img: Image.Image,
    path: str,
    **kwargs,
) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_doodle_svg(img, **kwargs))


__all__ = ["render_doodle_svg", "save_doodle_svg", "auto_crop_image"]
