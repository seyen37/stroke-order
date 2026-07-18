"""
思源黑體 / Noto Sans TC (黑體) source — Phase 5dm.

Loads glyph outlines from **Noto Sans TC** (Traditional-Chinese subset of
Noto Sans CJK, a.k.a. 思源黑體), the open 黑體 recommended for
**鏤空字模 (stencil)** output. 黑體 has near-uniform, thick stroke
weight and no serifs/hooks, so the min-stroke-width is far larger and
more even than 楷書 — bridges/連筋 land on thick walls and don't break,
which is exactly what a laser/spray stencil needs.

Why a new source instead of reusing 教育部宋體 (5av)?
------------------------------------------------------
宋體/明體 is *not* 黑體: it has thin horizontals + thick verticals +
faux serifs, so its thinnest strokes are as fragile as 楷書's for
stencil use. 竹米 STENCIL and the 方正大黑 reference both use a uniform
黑體 for this reason. Empirically (5dm sandbox, chars 明圖界): 楷書
median stroke ≈ 6px vs Noto 黑體 ≈ 20–24px, and 楷書 5th-percentile
stroke ≈ 6px (many fragile tapered tips) vs 黑體 ≈ 14–22px.

License (must be cited)
-----------------------
**SIL Open Font License 1.1** — the most permissive of all fonts this
project ships: commercial use, bundling, and *derivatives* are all
permitted (unlike the MoE CC BY-ND fonts). Reserved Font Name: "Noto".
Copyright 2014-2021 Adobe (developed as Source Han Sans / 思源黑體),
released by Google as Noto Sans CJK. https://github.com/notofonts/noto-cjk

Coordinate frame
----------------
``unitsPerEm = 1000`` (CFF/OTF), so ``_transform_cmd`` applies
``scale = EM_SIZE / 1000`` plus the Y-flip — same path as CNS/MoE
sources.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..ir import EM_SIZE, Character, Stroke
from .cns_font import _OutlineCmdPen, _transform_cmd
from .g0v import CharacterNotFound

_ENV_FILE = "STROKE_ORDER_HEI_FONT_FILE"
_ENV_DIR = "STROKE_ORDER_HEI_FONT_DIR"
_DEFAULT_FILE = (
    Path.home() / ".stroke-order" / "hei-fonts" / "NotoSansTC-Bold.otf"
)


def default_hei_font_path() -> Path:
    f = os.environ.get(_ENV_FILE)
    if f:
        return Path(f).expanduser()
    d = os.environ.get(_ENV_DIR)
    if d:
        return Path(d).expanduser() / "NotoSansTC-Bold.otf"
    return _DEFAULT_FILE


_ATTRIBUTION = (
    "Noto Sans TC (思源黑體) by Adobe / Google, SIL Open Font License 1.1. "
    "Reserved Font Name: Noto. https://github.com/notofonts/noto-cjk"
)


def attribution_notice() -> str:
    return _ATTRIBUTION


class NotoHeiSource:
    """Noto Sans TC (黑體) outline loader — the stencil-recommended font."""

    def __init__(self, font_path: Optional[Path] = None) -> None:
        self.font_path = (
            Path(font_path) if font_path else default_hei_font_path()
        )
        self._font: object = None
        self._cache: dict[str, Character] = {}

    def __repr__(self) -> str:
        return (f"NotoHeiSource(file={self.font_path!s}, "
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
                "fontTools is required for NotoHeiSource; "
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
                f"思源黑體 (Noto Sans TC) not installed; checked {self.font_path}"
            )
        cp = ord(char)
        cmap = font.getBestCmap()
        gname = cmap.get(cp)
        if gname is None:
            raise CharacterNotFound(
                f"思源黑體 has no glyph for U+{cp:04X} ({char!r})"
            )
        pen = _OutlineCmdPen(font.getGlyphSet())
        font.getGlyphSet()[gname].draw(pen)
        if not pen.commands:
            raise CharacterNotFound(
                f"思源黑體 glyph for U+{cp:04X} has no drawable outline"
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
            data_source="noto_hei",
        )
        self._cache[char] = c
        return c

    def has(self, char: str) -> bool:
        try:
            self.get_character(char)
            return True
        except CharacterNotFound:
            return False


_SINGLETON: Optional[NotoHeiSource] = None


def get_hei_source() -> NotoHeiSource:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = NotoHeiSource()
    return _SINGLETON


def reset_hei_singleton() -> None:
    global _SINGLETON
    _SINGLETON = None
    from ..cache_bus import bump  # 5eu：跨層快取失效訊號
    bump()


__all__ = [
    "NotoHeiSource",
    "default_hei_font_path",
    "attribution_notice",
    "get_hei_source",
    "reset_hei_singleton",
]
