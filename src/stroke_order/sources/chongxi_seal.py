"""
崇羲篆體 (Chongxi Seal Script) source — Phase 5at.

Loads glyph outlines from the *Chongxi Small Seal* font by 季旭昇 and
the Institute of Information Science, Academia Sinica. The font ships
~11,600 small-seal-script glyphs covering Shuowen Jiezi (《說文解字》)
plus the Taiwan MoE Common Words list — vastly more than the 6,063
characters g0v has for kaishu.

License (must be cited in every output)
---------------------------------------
**CC BY-ND 3.0 TW or later**:
- ✅ may redistribute (incl. commercial)
- ✅ must attribute "崇羲篆體 / 季旭昇 / 中央研究院資訊科學研究所"
- ⚠ no derivatives of the *font file* (extracting glyph outlines for
  rendering output is normal use, not a derivative work — same legal
  basis as CNS Sung in Phase 5am)

The :func:`attribution_notice` helper returns a ready-made caption that
SVG/G-code/UI layers should embed when the seal source actually
contributed to an output.

Coordinate frame
----------------
Source TTF uses ``unitsPerEm = 1024``; we scale to the project-wide
2048 em frame inside :func:`get_character` so downstream renderers
don't need to know the difference. Y-flip uses the font's hhea
ascender, identical to :class:`CNSFontSource`.

Outline-only — caller must convert
----------------------------------
Like CNSFontSource, output strokes have ``raw_track=[]`` and the full
glyph outline in a single ``Stroke``. Callers that need centerlines
for G-code must run :func:`apply_seal_outline_mode` (or equivalent)
to convert the outline to skeleton tracks. Phase 5at uses the legacy
v1 walker by default — empirically it handles seal script's simple
topology (1-3 strokes per glyph, fat lines, few junctions) much
better than the over-engineered v2 splitter.
"""
from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Optional

from ..ir import EM_SIZE, Character, Point, Stroke
from .cns_font import _OutlineCmdPen, _transform_cmd
from .g0v import CharacterNotFound


_ENV_FILE = "STROKE_ORDER_SEAL_FONT_FILE"
_ENV_DIR = "STROKE_ORDER_SEAL_FONT_DIR"
_DEFAULT_FILE = Path.home() / ".stroke-order" / "seal-fonts" / "chongxi_seal.otf"


def default_seal_font_path() -> Path:
    """Resolve the OTF path. Order:

    1. ``$STROKE_ORDER_SEAL_FONT_FILE`` (full path to OTF/TTF)
    2. ``$STROKE_ORDER_SEAL_FONT_DIR / chongxi_seal.otf``
    3. ``~/.stroke-order/seal-fonts/chongxi_seal.otf``
    """
    f = os.environ.get(_ENV_FILE)
    if f:
        return Path(f).expanduser()
    d = os.environ.get(_ENV_DIR)
    if d:
        return Path(d).expanduser() / "chongxi_seal.otf"
    return _DEFAULT_FILE


# Mandatory attribution per CC BY-ND 3.0 TW.
_ATTRIBUTION = (
    "崇羲篆體 (Chongxi Small Seal) by 季旭昇 / 中央研究院資訊科學研究所, "
    "CC BY-ND 3.0 TW. https://xiaoxue.iis.sinica.edu.tw/chongxi/"
)


def attribution_notice() -> str:
    """Return the human-readable attribution string for this font.

    Embed this in every output that contains seal-script glyphs.
    Same string is exposed via the ``/api/seal-status`` endpoint so
    UI banners can render it consistently.
    """
    return _ATTRIBUTION


class ChongxiSealSource:
    """Load 崇羲篆體 glyph outlines into the source-chain pipeline.

    Like :class:`CNSFontSource`: cheap to construct (no I/O), one
    ``TTFont`` lazily opened on first ``get_character`` and reused.
    Each character returned has **exactly one Stroke** whose
    ``outline`` is the entire glyph (multi-contour OK), ``raw_track``
    empty, ``data_source = "chongxi_seal"``.
    """

    def __init__(self, font_path: Optional[Path] = None) -> None:
        self.font_path = (
            Path(font_path) if font_path else default_seal_font_path()
        )
        self._font: object = None
        self._cache: dict[str, Character] = {}

    def __repr__(self) -> str:
        return (f"ChongxiSealSource(file={self.font_path!s}, "
                f"loaded={self._font is not None}, "
                f"cached={len(self._cache)})")

    def is_ready(self) -> bool:
        return self.font_path.exists()

    def _load_font(self):
        if self._font is not None:
            return self._font
        if not self.font_path.exists():
            return None
        try:
            from fontTools.ttLib import TTFont
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "fontTools is required for ChongxiSealSource; "
                "install with `pip install fonttools`"
            ) from e
        self._font = TTFont(str(self.font_path), lazy=True)
        return self._font

    def available_glyph_count(self) -> int:
        """How many character codepoints the font covers."""
        font = self._load_font()
        if font is None:
            return 0
        return len(font.getBestCmap())

    def get_character(self, char: str) -> Character:
        if char in self._cache:
            return self._cache[char]
        font = self._load_font()
        if font is None:
            raise CharacterNotFound(
                f"崇羲篆體 font not installed; checked {self.font_path}"
            )
        cp = ord(char)
        cmap = font.getBestCmap()
        gname = cmap.get(cp)
        if gname is None:
            raise CharacterNotFound(
                f"崇羲篆體 has no glyph for U+{cp:04X} ({char!r})"
            )
        pen = _OutlineCmdPen(font.getGlyphSet())
        font.getGlyphSet()[gname].draw(pen)
        if not pen.commands:
            raise CharacterNotFound(
                f"崇羲篆體 glyph for U+{cp:04X} has no drawable outline"
            )
        units = font["head"].unitsPerEm
        ascender = font["hhea"].ascender
        scale = EM_SIZE / units
        cmds = [
            _transform_cmd(cmd, scale=scale, ascender=ascender)
            for cmd in pen.commands
        ]
        c = Character(
            char=char,
            unicode_hex=f"{cp:04x}",
            strokes=[Stroke(
                index=0,
                raw_track=[],
                outline=cmds,
                kind_code=9,
                kind_name="其他",
                has_hook=False,
            )],
            data_source="chongxi_seal",
        )
        self._cache[char] = c
        return c

    def has(self, char: str) -> bool:
        try:
            self.get_character(char)
            return True
        except CharacterNotFound:
            return False


def apply_seal_outline_mode(c: Character, mode: str = "skeleton") -> Character:
    """Convert a seal-font character to writable centerlines.

    Mirrors :func:`stroke_order.sources.cns_font.apply_cns_outline_mode`
    but uses **the v1 endpoint walker by default**: empirically it
    handles seal-script glyphs (1-3 strokes, fat strokes, few real
    junctions) far better than the v2 junction-aware splitter, which
    over-segments and runs slow / OOMs on dense outlines.

    Modes:
    - ``"skip"`` — leave outline-only (SVG renders filled, G-code skips)
    - ``"trace"`` — sample outline to polyline; G-code traces contour
    - ``"skeleton"`` (default) — Zhang-Suen thinning → walker tracks

    No-op when ``c.data_source != "chongxi_seal"``.
    """
    if c.data_source != "chongxi_seal" or mode == "skip":
        return c
    if mode not in ("trace", "skeleton"):
        raise ValueError(
            f"unknown seal mode {mode!r}; expected skip / trace / skeleton"
        )
    src = c.strokes[0] if c.strokes else None
    if src is None or not src.outline:
        return c

    new_c = deepcopy(c)
    if mode == "trace":
        from .cns_font import _outline_to_polylines
        tracks = _outline_to_polylines(src.outline)
    else:  # skeleton (default)
        from ..cns_skeleton import outline_to_skeleton_tracks
        tracks = outline_to_skeleton_tracks(src.outline)

    new_strokes: list[Stroke] = []
    for idx, track in enumerate(tracks):
        if len(track) < 2:
            continue
        new_strokes.append(Stroke(
            index=idx,
            raw_track=[Point(float(x), float(y)) for x, y in track],
            outline=[],
            kind_code=9,
            kind_name="其他",
            has_hook=False,
        ))
    if new_strokes:
        new_c.strokes = new_strokes
    return new_c


# ---------------------------------------------------------------------------
# Singleton — server.py shares one font handle per process (mirrors 5am).
# ---------------------------------------------------------------------------


_SINGLETON: Optional[ChongxiSealSource] = None


def get_seal_source() -> ChongxiSealSource:
    """Process-wide lazy singleton."""
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = ChongxiSealSource()
    return _SINGLETON


def reset_seal_singleton() -> None:
    """Drop the cached singleton (used by tests that monkeypatch the path)."""
    global _SINGLETON
    _SINGLETON = None


__all__ = [
    "ChongxiSealSource",
    "apply_seal_outline_mode",
    "default_seal_font_path",
    "attribution_notice",
    "get_seal_source",
    "reset_seal_singleton",
]
