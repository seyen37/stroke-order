"""
KanjiVG source adapter (Japanese kanji support).

Fetches per-character SVG files from KanjiVG (github.com/KanjiVG/kanjivg).
Each kanji has an SVG at ``kanji/{5-digit-lowercase-hex}.svg`` where the
path element `d` attributes ARE the stroke centerlines (not outlines!).
This means we get centerlines for free — no skeletonisation needed.

Format notes
------------

- ``viewBox`` is ``0 0 109 109`` (native 109 em, Y-down).
- Each ``<path>`` has a ``kvg:type`` attribute classifying the stroke in
  Japanese notation (㇔=點, ㇏=捺, ㇒=撇, ㇆=橫折鉤, etc.).
- Paths use M/m, L/l, C/c, S/s (relative cubic bezier is the common case).
- Stroke order = document order of path elements.

Coordinate conversion
---------------------

We scale 109 → 2048 uniformly (factor ~18.79). Y-axis already matches our
Y-down convention.

License
-------

KanjiVG is **CC BY-SA 3.0**. When redistributing output derived from it,
include attribution and the same license clause (ShareAlike).
"""
from __future__ import annotations

import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from svgpathtools import parse_path

from ..ir import EM_SIZE, Character, Point, Stroke, OutlineCommand
from .g0v import CharacterNotFound

log = logging.getLogger(__name__)

KVG_BASE_URL = (
    "https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/"
)

KVG_EM_SIZE = 109
_SCALE = EM_SIZE / KVG_EM_SIZE  # ≈ 18.79

SVG_NS = "{http://www.w3.org/2000/svg}"
KVG_NS = "{http://kanjivg.tagaini.net}"

# How many samples to draw along each cubic bezier segment for the track
_BEZIER_SAMPLES_PER_SEG = 8


class KanjiVGSource:
    """Adapter for KanjiVG kanji stroke data."""

    def __init__(
        self,
        cache_dir: Optional[str | Path] = None,
        allow_network: bool = True,
        user_agent: str = "stroke-order/0.3 (+https://github.com/seyen37)",
        timeout: float = 10.0,
    ) -> None:
        if cache_dir is None:
            cache_dir = Path(__file__).resolve().parents[3] / "data" / "kanjivg_cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.allow_network = allow_network
        self.user_agent = user_agent
        self.timeout = timeout

    # ---------- public API ------------------------------------------------

    def get_character(self, char: str) -> Character:
        if len(char) != 1:
            raise ValueError(f"expected a single character, got {char!r}")
        codepoint = ord(char)
        # KanjiVG filenames: 5-digit lowercase hex
        filename = f"{codepoint:05x}.svg"
        svg_text = self._load_svg(filename, codepoint)
        return self._parse_svg(char, codepoint, svg_text)

    # ---------- internals -------------------------------------------------

    def _load_svg(self, filename: str, codepoint: int) -> str:
        path = self.cache_dir / filename
        if path.is_file():
            return path.read_text(encoding="utf-8")
        if not self.allow_network:
            raise CharacterNotFound(
                f"U+{codepoint:04X} not in KanjiVG cache and network disabled"
            )
        url = KVG_BASE_URL + filename
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise CharacterNotFound(
                    f"U+{codepoint:04X} not in KanjiVG dataset (HTTP 404)"
                ) from e
            raise
        except urllib.error.URLError as e:
            raise CharacterNotFound(
                f"network error fetching U+{codepoint:04X}: {e}"
            ) from e
        # persist cache
        try:
            path.write_text(body, encoding="utf-8")
        except OSError as e:
            log.warning("could not write cache %s: %s", path, e)
        return body

    def _parse_svg(self, char: str, codepoint: int, svg_text: str) -> Character:
        root = ET.fromstring(svg_text)
        # KanjiVG structure: top-level group contains nested groups that each
        # contain path elements. We want all <path> elements with an `id`
        # starting with 'kvg:<hex>-s' (the stroke path, not numbers).
        strokes: list[Stroke] = []
        for i, path_elem in enumerate(root.iter(f"{SVG_NS}path")):
            pid = path_elem.get("id", "")
            if not pid or "-s" not in pid:
                # skip if not a stroke path (ignore any non-stroke paths)
                continue
            d = path_elem.get("d", "").strip()
            if not d:
                continue
            track, outline = self._sample_path(d)
            if not track:
                continue
            strokes.append(Stroke(
                index=len(strokes),
                raw_track=track,
                outline=outline,
            ))

        if not strokes:
            raise CharacterNotFound(
                f"U+{codepoint:04X} KanjiVG SVG contained no usable strokes"
            )

        return Character(
            char=char,
            unicode_hex=f"{codepoint:x}",
            strokes=strokes,
            data_source="kanjivg",
        )

    @staticmethod
    def _sample_path(d: str) -> tuple[list[Point], list[OutlineCommand]]:
        """
        KanjiVG paths ARE centerlines, so we sample them as track points.
        For each segment (Line, QuadraticBezier, CubicBezier) we take
        ~_BEZIER_SAMPLES_PER_SEG points along it and emit them into ``track``.

        Outline commands are set to the raw M/L/C equivalents in canonical
        coordinates so the SVG exporter can still render a stroke shape
        (thin line, since KanjiVG has no width info).
        """
        try:
            path = parse_path(d)
        except Exception as e:
            log.warning("could not parse KanjiVG path: %s", e)
            return [], []

        track: list[Point] = []
        outline: list[OutlineCommand] = []
        started = False
        for seg in path:
            # svgpathtools gives us complex numbers; sample `n` points
            # including endpoints
            n = _BEZIER_SAMPLES_PER_SEG
            if not started:
                p = seg.point(0)
                x, y = p.real * _SCALE, p.imag * _SCALE
                track.append(Point(x, y))
                outline.append({"type": "M", "x": x, "y": y})
                started = True
            for k in range(1, n + 1):
                t = k / n
                p = seg.point(t)
                x, y = p.real * _SCALE, p.imag * _SCALE
                track.append(Point(x, y))
            # Add a final L command for the outline's consumer
            end = seg.point(1)
            outline.append({
                "type": "L",
                "x": end.real * _SCALE,
                "y": end.imag * _SCALE,
            })
        return track, outline


__all__ = ["KanjiVGSource", "KVG_BASE_URL", "KVG_EM_SIZE"]
