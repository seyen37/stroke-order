"""
教育部隸書 (MoE Lishu) source — Phase 5au.

Loads glyph outlines from the Republic of China Ministry of Education's
official 隸書 (clerical-script) font, version 3.00 (released 2019).
Coverage: 5,593 BMP characters.

License (must be cited in every output)
---------------------------------------
**CC BY-ND 3.0 TW**:
- ✅ may redistribute (incl. commercial)
- ✅ must attribute "中華民國教育部"
- ⚠ no derivatives of the *font file* (extracting glyph outlines for
  rendering output is normal use, not a derivative — same legal basis
  as Chongxi Seal in Phase 5at and CNS Sung in 5am)

Used to upgrade the Phase-5aj ``style="lishu"`` filter (which only
fakes 隸書 by adding 波磔 to kaishu) into a real-outline swap.

Coordinate frame
----------------
Source TTF uses ``unitsPerEm = 2048`` — identical to the project em
frame, so :func:`_transform_cmd` only needs the Y-flip (no scale).
"""
from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Optional

from ..ir import EM_SIZE, Character, Point, Stroke
from .cns_font import _OutlineCmdPen, _transform_cmd
from .g0v import CharacterNotFound


_ENV_FILE = "STROKE_ORDER_LISHU_FONT_FILE"
_ENV_DIR = "STROKE_ORDER_LISHU_FONT_DIR"
_DEFAULT_FILE = Path.home() / ".stroke-order" / "lishu-fonts" / "MoeLI.ttf"


def default_lishu_font_path() -> Path:
    f = os.environ.get(_ENV_FILE)
    if f:
        return Path(f).expanduser()
    d = os.environ.get(_ENV_DIR)
    if d:
        return Path(d).expanduser() / "MoeLI.ttf"
    return _DEFAULT_FILE


_ATTRIBUTION = (
    "教育部隸書字型 (Version 3.00) by 中華民國教育部, CC BY-ND 3.0 TW. "
    "https://language.moe.gov.tw/result.aspx?classify_sn=23"
)


def attribution_notice() -> str:
    """Mandatory CC BY-ND 3.0 TW attribution string."""
    return _ATTRIBUTION


class MoeLishuSource:
    """Load MoE 隸書 outlines into the source-chain pipeline.

    Mirrors :class:`stroke_order.sources.chongxi_seal.ChongxiSealSource`:
    cheap to construct, lazy ``TTFont`` open on first ``get_character``,
    one Stroke per character holding the full glyph outline.
    ``data_source = "moe_lishu"`` so the 5aj :class:`LishuStyle` filter
    knows to short-circuit (the real font already IS lishu — adding
    fake 波磔 on top would double up).
    """

    def __init__(self, font_path: Optional[Path] = None) -> None:
        self.font_path = (
            Path(font_path) if font_path else default_lishu_font_path()
        )
        self._font: object = None
        self._cache: dict[str, Character] = {}

    def __repr__(self) -> str:
        return (f"MoeLishuSource(file={self.font_path!s}, "
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
                "fontTools is required for MoeLishuSource; "
                "install with `pip install fonttools`"
            ) from e
        self._font = TTFont(str(self.font_path), lazy=True)
        return self._font

    def available_glyph_count(self) -> int:
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
                f"教育部隸書 font not installed; checked {self.font_path}"
            )
        cp = ord(char)
        cmap = font.getBestCmap()
        gname = cmap.get(cp)
        if gname is None:
            raise CharacterNotFound(
                f"教育部隸書 has no glyph for U+{cp:04X} ({char!r})"
            )
        pen = _OutlineCmdPen(font.getGlyphSet())
        font.getGlyphSet()[gname].draw(pen)
        if not pen.commands:
            raise CharacterNotFound(
                f"教育部隸書 glyph for U+{cp:04X} has no drawable outline"
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
            data_source="moe_lishu",
        )
        self._cache[char] = c
        return c

    def has(self, char: str) -> bool:
        try:
            self.get_character(char)
            return True
        except CharacterNotFound:
            return False


def apply_lishu_outline_mode(c: Character, mode: str = "skeleton") -> Character:
    """Convert a MoE-lishu character to writable centerlines.

    Defaults to v1 walker skeleton (same engineering judgement as
    :func:`stroke_order.sources.chongxi_seal.apply_seal_outline_mode`):
    隸書 has 5-15 broad strokes per glyph with reasonably clean
    junctions, so the simple endpoint walker works better than 5aq's
    over-engineered junction-aware splitter.
    """
    if c.data_source != "moe_lishu" or mode == "skip":
        return c
    if mode not in ("trace", "skeleton"):
        raise ValueError(
            f"unknown lishu mode {mode!r}; expected skip / trace / skeleton"
        )
    src = c.strokes[0] if c.strokes else None
    if src is None or not src.outline:
        return c

    new_c = deepcopy(c)
    if mode == "trace":
        from .cns_font import _outline_to_polylines
        tracks = _outline_to_polylines(src.outline)
    else:  # skeleton
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
# Singleton
# ---------------------------------------------------------------------------


_SINGLETON: Optional[MoeLishuSource] = None


def get_lishu_source() -> MoeLishuSource:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = MoeLishuSource()
    return _SINGLETON


def reset_lishu_singleton() -> None:
    global _SINGLETON
    _SINGLETON = None


__all__ = [
    "MoeLishuSource",
    "apply_lishu_outline_mode",
    "default_lishu_font_path",
    "attribution_notice",
    "get_lishu_source",
    "reset_lishu_singleton",
]
