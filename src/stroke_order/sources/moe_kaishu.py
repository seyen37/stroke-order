"""
教育部標準楷書 (MoE Standard Kaishu) source — Phase 5aw.

Loads glyph outlines from the Republic of China Ministry of Education's
official 標準楷書 font, version 5.1 (released 2025; 14,037 chars across
BMP + Plane 2 / CJK Ext-B). Used as a **Tier-3 outline fallback** in
the source chain — slotting in *between* the stroke-data sources
(g0v 6k, MMH 9.5k) and the rare-char CNS Kai catch-all (95k).

Why a separate tier (not a style swap)
--------------------------------------
Unlike :mod:`moe_song` / :mod:`moe_lishu` / :mod:`chongxi_seal` which
upgrade the corresponding ``style="..."`` filter, **kaishu is the
default style** — there's no swap to perform. Instead, MoE Kaishu
provides outline coverage for ~10k chars that g0v/MMH don't carry,
with quality clearly better than CNS Kai for the common range.

License (must be cited)
-----------------------
**CC BY-ND 3.0 TW** — same terms as the other MoE fonts:
attribute "中華民國教育部"; redistribute (incl. commercial) permitted;
no derivatives of the *font file* itself.
"""
from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Optional

from ..ir import EM_SIZE, Character, Point, Stroke
from .cns_font import _OutlineCmdPen, _transform_cmd
from .g0v import CharacterNotFound


_ENV_FILE = "STROKE_ORDER_KAISHU_FONT_FILE"
_ENV_DIR = "STROKE_ORDER_KAISHU_FONT_DIR"
_DEFAULT_FILE = (
    Path.home() / ".stroke-order" / "kaishu-fonts" / "edukai.ttf"
)


def default_kaishu_font_path() -> Path:
    f = os.environ.get(_ENV_FILE)
    if f:
        return Path(f).expanduser()
    d = os.environ.get(_ENV_DIR)
    if d:
        # The MoE distribution filename includes a date stamp; accept any
        # ``edukai*.ttf`` in the dir if the canonical name is absent.
        d_path = Path(d).expanduser()
        canon = d_path / "edukai.ttf"
        if canon.exists():
            return canon
        for f in sorted(d_path.glob("edukai*.ttf")):
            return f
        return canon   # report the canonical path even when absent
    return _DEFAULT_FILE


_ATTRIBUTION = (
    "教育部標準楷書 (Version 5.1) by 中華民國教育部, CC BY-ND 3.0 TW. "
    "https://language.moe.gov.tw/result.aspx?classify_sn=23"
)


def attribution_notice() -> str:
    return _ATTRIBUTION


class MoeKaishuSource:
    """MoE Standard Kaishu outline loader.

    ``data_source = "moe_kaishu"`` — distinct from g0v's ``"g0v"`` and
    CNS Kai's ``"cns_font"`` so :func:`apply_cns_outline_mode` and
    server-side bypasses can recognise it.
    """

    def __init__(self, font_path: Optional[Path] = None) -> None:
        self.font_path = (
            Path(font_path) if font_path else default_kaishu_font_path()
        )
        self._font: object = None
        self._cache: dict[str, Character] = {}

    def __repr__(self) -> str:
        return (f"MoeKaishuSource(file={self.font_path!s}, "
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
                "fontTools is required for MoeKaishuSource; "
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
                f"教育部標準楷書 not installed; checked {self.font_path}"
            )
        cp = ord(char)
        cmap = font.getBestCmap()
        gname = cmap.get(cp)
        if gname is None:
            raise CharacterNotFound(
                f"教育部標準楷書 has no glyph for U+{cp:04X} ({char!r})"
            )
        pen = _OutlineCmdPen(font.getGlyphSet())
        font.getGlyphSet()[gname].draw(pen)
        if not pen.commands:
            raise CharacterNotFound(
                f"教育部標準楷書 glyph for U+{cp:04X} has no drawable outline"
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
            data_source="moe_kaishu",
        )
        self._cache[char] = c
        return c

    def has(self, char: str) -> bool:
        try:
            self.get_character(char)
            return True
        except CharacterNotFound:
            return False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


_SINGLETON: Optional[MoeKaishuSource] = None


def get_kaishu_source() -> MoeKaishuSource:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = MoeKaishuSource()
    return _SINGLETON


def reset_kaishu_singleton() -> None:
    global _SINGLETON
    _SINGLETON = None


__all__ = [
    "MoeKaishuSource",
    "default_kaishu_font_path",
    "attribution_notice",
    "get_kaishu_source",
    "reset_kaishu_singleton",
]
