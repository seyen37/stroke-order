"""
Make Me a Hanzi source adapter.

MMH (https://github.com/skishore/makemeahanzi) stores ~9000 simplified and
traditional characters derived from the Arphic PL KaitiM GB / UKai fonts.
Unlike g0v, it's **LGPL-licensed** and therefore safe for commercial use.

Data format
-----------

A single ``graphics.txt`` file, ~30 MB, with one JSON object per line::

    {"character": "永",
     "strokes": ["M 237 518 Q 240 513 ... Z", ...],
     "medians": [[[224, 532], [305, 531]], ...]}

- ``strokes[i]`` is an SVG path ``d`` string for the outline (墨跡).
- ``medians[i]`` is a sparse polyline of the centerline (骨架).
- Coordinate system: 1024×1024 em, **Y-axis points UP** (font convention).

We normalize to our canonical 2048 Y-down frame by ``y' = 2048 - y·2, x' = x·2``.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.request
from pathlib import Path
from typing import Optional

from ..ir import Character, Point, Stroke, OutlineCommand
from .g0v import CharacterNotFound  # reuse exception type

log = logging.getLogger(__name__)

#: URL for Make Me a Hanzi's graphics.txt (~30 MB).
MMH_GRAPHICS_URL = (
    "https://raw.githubusercontent.com/skishore/makemeahanzi/master/graphics.txt"
)

#: MMH's source em width (x-axis scale basis). We scale 2× to reach 2048.
MMH_EM_WIDTH = 1024

#: Arphic fonts (MMH's source) use Y-up coordinates with baseline at y=0 and
#: ascender near y=900. We place baseline at canonical y=1800 so descender
#: (y_mmh ≈ -124) lands near y=2048 (bottom of em) and ascender (y_mmh ≈ 900)
#: lands near y=0 (top of em).
MMH_ASCENDER = 900

#: Scale factor applied to both axes when converting MMH → canonical.
_SCALE = 2.0


def _to_canonical(x: float, y: float) -> tuple[float, float]:
    """MMH (Arphic font coords, Y-up, baseline=0, ascender≈900) → canonical
    2048-em Y-down."""
    return x * _SCALE, (MMH_ASCENDER - y) * _SCALE


# ---------------------------------------------------------------------------
# SVG path "d" string → list of our outline command dicts
# ---------------------------------------------------------------------------

# Tokenise on whitespace AND between digit/letter boundaries (handles "M123,45"
# as well as "M 123 45"). Commas and whitespace are delimiters.
_PATH_TOKEN = re.compile(r"([MLQCTSZmlqctsz])|(-?\d+(?:\.\d+)?)")


def _parse_svg_path(d: str) -> list[OutlineCommand]:
    """
    Parse an SVG path ``d`` string into our list-of-dicts outline format.

    Supports absolute commands ``M`` (moveto), ``L`` (lineto), ``Q``
    (quadratic bezier: control + endpoint), ``C`` (cubic bezier: c1 + c2
    + endpoint), and ``Z`` (close path — implicit, ignored downstream).

    MMH uses M/L/Q/C/Z only. We don't attempt to handle relative (lowercase)
    commands because MMH paths are absolute.
    """
    tokens = [m.group(0) for m in _PATH_TOKEN.finditer(d)]
    out: list[OutlineCommand] = []
    i = 0
    current_cmd: Optional[str] = None
    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            cmd = tok.upper()
            if cmd == "Z":
                # close path — emit nothing; our outline is implicitly closed
                current_cmd = None
            else:
                current_cmd = cmd
            i += 1
            continue
        if current_cmd is None:
            # stray number (shouldn't happen in well-formed MMH); skip
            i += 1
            continue
        # read numeric arguments for the current command
        cmd = current_cmd
        if cmd in ("M", "L"):
            x = float(tokens[i]); y = float(tokens[i + 1])
            nx, ny = _to_canonical(x, y)
            out.append({"type": cmd, "x": nx, "y": ny})
            i += 2
        elif cmd == "Q":
            bx = float(tokens[i]);     by = float(tokens[i + 1])
            ex = float(tokens[i + 2]); ey = float(tokens[i + 3])
            b = _to_canonical(bx, by)
            e = _to_canonical(ex, ey)
            out.append({
                "type": "Q",
                "begin": {"x": b[0], "y": b[1]},
                "end":   {"x": e[0], "y": e[1]},
            })
            i += 4
        elif cmd == "C":
            # cubic bezier: 2 control points + endpoint = 6 numbers.
            # Emitted in g0v's naming convention (begin/mid/end) so all
            # sources share a single outline schema.
            c1x = float(tokens[i]);     c1y = float(tokens[i + 1])
            c2x = float(tokens[i + 2]); c2y = float(tokens[i + 3])
            ex  = float(tokens[i + 4]); ey  = float(tokens[i + 5])
            c1 = _to_canonical(c1x, c1y)
            c2 = _to_canonical(c2x, c2y)
            e  = _to_canonical(ex, ey)
            out.append({
                "type":  "C",
                "begin": {"x": c1[0], "y": c1[1]},
                "mid":   {"x": c2[0], "y": c2[1]},
                "end":   {"x": e[0],  "y": e[1]},
            })
            i += 6
        else:
            log.warning("unsupported SVG command %r in MMH path", cmd)
            i += 1
    return out


# ---------------------------------------------------------------------------
# Source class
# ---------------------------------------------------------------------------


class MMHSource:
    """
    Adapter for Make Me a Hanzi's graphics.txt.

    On first use, downloads the 30 MB graphics file into ``cache_dir`` and
    builds an in-memory ``char -> line`` index (lazily loaded entries). A
    single instance can be reused across many lookups for amortized O(1)
    access.

    Parameters
    ----------
    cache_dir
        Where graphics.txt is stored. Default: project ``data/mmh_cache/``.
    allow_network
        If False, raise CharacterNotFound when graphics.txt is missing
        instead of downloading.
    """

    def __init__(
        self,
        cache_dir: Optional[str | Path] = None,
        allow_network: bool = True,
    ) -> None:
        if cache_dir is None:
            cache_dir = Path(__file__).resolve().parents[3] / "data" / "mmh_cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.allow_network = allow_network
        self._graphics_path = self.cache_dir / "graphics.txt"
        self._index: Optional[dict[str, str]] = None  # char → raw JSON line

    # ---------- public API -----------------------------------------------

    def get_character(self, char: str) -> Character:
        if len(char) != 1:
            raise ValueError(f"expected a single character, got {char!r}")
        index = self._ensure_index()
        line = index.get(char)
        if line is None:
            raise CharacterNotFound(
                f"U+{ord(char):04X} not in Make Me a Hanzi dataset"
            )
        raw = json.loads(line)
        return self._parse(raw)

    def has_character(self, char: str) -> bool:
        """Cheap membership check (triggers download if not cached)."""
        return char in self._ensure_index()

    def char_count(self) -> int:
        return len(self._ensure_index())

    # ---------- internals ------------------------------------------------

    def _ensure_graphics(self) -> None:
        if self._graphics_path.is_file():
            return
        if not self.allow_network:
            raise CharacterNotFound(
                "MMH graphics.txt not cached and network disabled"
            )
        log.info("downloading MMH graphics.txt (~30 MB) to %s…",
                 self._graphics_path)
        with urllib.request.urlopen(MMH_GRAPHICS_URL, timeout=60) as resp:
            data = resp.read()
        self._graphics_path.write_bytes(data)
        log.info("downloaded %d bytes", len(data))

    def _ensure_index(self) -> dict[str, str]:
        if self._index is not None:
            return self._index
        self._ensure_graphics()
        index: dict[str, str] = {}
        with self._graphics_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                # fast path: character is in the first 30 chars as "character":"X"
                # parse minimally to extract it
                try:
                    obj = json.loads(line)
                    ch = obj["character"]
                    index[ch] = line
                except Exception:
                    continue
        self._index = index
        log.info("indexed %d characters from MMH graphics.txt", len(index))
        return index

    def _parse(self, raw: dict) -> Character:
        char = raw["character"]
        strokes_raw = raw.get("strokes", [])
        medians_raw = raw.get("medians", [])

        if len(strokes_raw) != len(medians_raw):
            log.warning(
                "MMH %s: strokes count %d != medians count %d",
                char, len(strokes_raw), len(medians_raw)
            )

        strokes: list[Stroke] = []
        n = max(len(strokes_raw), len(medians_raw))
        for i in range(n):
            outline_d = strokes_raw[i] if i < len(strokes_raw) else ""
            median_pts = medians_raw[i] if i < len(medians_raw) else []
            outline = _parse_svg_path(outline_d) if outline_d else []
            track = []
            for p in median_pts:
                nx, ny = _to_canonical(float(p[0]), float(p[1]))
                track.append(Point(nx, ny))
            strokes.append(Stroke(
                index=i,
                raw_track=track,
                outline=outline,
            ))

        return Character(
            char=char,
            unicode_hex=f"{ord(char):x}",
            strokes=strokes,
            data_source="mmh",
        )


__all__ = ["MMHSource", "MMH_GRAPHICS_URL", "MMH_EM_SIZE"]
