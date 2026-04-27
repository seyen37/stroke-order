"""
教育部標準宋體 (MoE Standard Sung) source — Phase 5av.

Loads glyph outlines from the Republic of China Ministry of Education's
official 標準宋體 font, Unicode version 4.4 (24,033 chars across BMP +
Plane 2 / CJK Ext-B). Used to **upgrade** the Phase-5am ``style="mingti"``
swap target — MoE Sung is more authoritative for Taiwan than CNS Sung
for common chars, so we try it first and only fall back to CNS Sung
(or the 5aj filter) when MoE doesn't cover the requested character.

License (must be cited)
-----------------------
**CC BY-ND 3.0 TW** — same terms as 5at (Chongxi Seal) and 5au (MoE
Lishu): attribute "中華民國教育部"; redistribute (incl. commercial)
permitted; no derivatives of the *font file* itself. Glyph extraction
for downstream rendering is normal use, not a derivative work.

Coordinate frame
----------------
``unitsPerEm = 2048`` — identical to project EM_SIZE, so
``_transform_cmd`` only does the Y-flip.
"""
from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Optional

from ..ir import EM_SIZE, Character, Point, Stroke
from .cns_font import _OutlineCmdPen, _transform_cmd
from .g0v import CharacterNotFound


_ENV_FILE = "STROKE_ORDER_SONG_FONT_FILE"
_ENV_DIR = "STROKE_ORDER_SONG_FONT_DIR"
_DEFAULT_FILE = (
    Path.home() / ".stroke-order" / "song-fonts" / "edusong_Unicode.ttf"
)


def default_song_font_path() -> Path:
    f = os.environ.get(_ENV_FILE)
    if f:
        return Path(f).expanduser()
    d = os.environ.get(_ENV_DIR)
    if d:
        return Path(d).expanduser() / "edusong_Unicode.ttf"
    return _DEFAULT_FILE


_ATTRIBUTION = (
    "教育部標準宋體 UN (Version 4.4) by 中華民國教育部, CC BY-ND 3.0 TW. "
    "https://language.moe.gov.tw/result.aspx?classify_sn=23"
)


def attribution_notice() -> str:
    return _ATTRIBUTION


class MoeSongSource:
    """MoE Standard Sung outline loader.

    ``data_source = "moe_song"`` so the 5aj :class:`MingtiStyle` filter
    knows to short-circuit (the real font already IS Sung — the
    horizontal-thin / vertical-thick / faux-serif filter would fight
    the glyph designer's intent).
    """

    def __init__(self, font_path: Optional[Path] = None) -> None:
        self.font_path = (
            Path(font_path) if font_path else default_song_font_path()
        )
        self._font: object = None
        self._cache: dict[str, Character] = {}

    def __repr__(self) -> str:
        return (f"MoeSongSource(file={self.font_path!s}, "
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
                "fontTools is required for MoeSongSource; "
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
                f"教育部標準宋體 not installed; checked {self.font_path}"
            )
        cp = ord(char)
        cmap = font.getBestCmap()
        gname = cmap.get(cp)
        if gname is None:
            raise CharacterNotFound(
                f"教育部標準宋體 has no glyph for U+{cp:04X} ({char!r})"
            )
        pen = _OutlineCmdPen(font.getGlyphSet())
        font.getGlyphSet()[gname].draw(pen)
        if not pen.commands:
            raise CharacterNotFound(
                f"教育部標準宋體 glyph for U+{cp:04X} has no drawable outline"
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
            data_source="moe_song",
        )
        self._cache[char] = c
        return c

    def has(self, char: str) -> bool:
        try:
            self.get_character(char)
            return True
        except CharacterNotFound:
            return False


def apply_song_outline_mode(c: Character, mode: str = "skeleton") -> Character:
    """Convert MoE-Song outline → centerline polylines (v1 walker)."""
    if c.data_source != "moe_song" or mode == "skip":
        return c
    if mode not in ("trace", "skeleton"):
        raise ValueError(
            f"unknown song mode {mode!r}; expected skip / trace / skeleton"
        )
    src = c.strokes[0] if c.strokes else None
    if src is None or not src.outline:
        return c

    new_c = deepcopy(c)
    if mode == "trace":
        from .cns_font import _outline_to_polylines
        tracks = _outline_to_polylines(src.outline)
    else:
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


_SINGLETON: Optional[MoeSongSource] = None


def get_song_source() -> MoeSongSource:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = MoeSongSource()
    return _SINGLETON


def reset_song_singleton() -> None:
    global _SINGLETON
    _SINGLETON = None


__all__ = [
    "MoeSongSource",
    "apply_song_outline_mode",
    "default_song_font_path",
    "attribution_notice",
    "get_song_source",
    "reset_song_singleton",
]
