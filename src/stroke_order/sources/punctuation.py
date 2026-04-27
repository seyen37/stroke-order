"""
Built-in punctuation source (Phase 5ai).

Hand-authored stroke data for ~25 common CJK + ASCII punctuation marks.
Lets text like "你好，世界！" render with actual vector strokes instead
of being dropped as "missing" characters, so the output can feed a
stroke-based writing robot via G-code or JSON as well as SVG preview.

Coordinate system: canonical 2048×2048 em square (same as g0v/mmh),
Y-axis pointing DOWN (SVG convention). Each mark's strokes are laid out
by eye to roughly match the typography of commercial CJK fonts, but
they are intentionally **hand-drawn-looking** rather than typographically
precise — matching the "handwriting robot" aesthetic of this project.

Fallback order
--------------
Registered as the final link in ``AutoSource`` / ``RegionAutoSource``, so
punctuation just works when the user types "，" or "!" without having to
know it's coming from a different source.
"""
from __future__ import annotations

import math

from ..ir import Character, Point, Stroke
from .g0v import CharacterNotFound


# ---------------------------------------------------------------------------
# Helpers for building stroke tracks
# ---------------------------------------------------------------------------


def _circle(cx: float, cy: float, r: float, n: int = 16) -> list[tuple[float, float]]:
    """Sample a small circle as n+1 points (closed loop). Useful for dots
    and the 。full-width period mark."""
    pts: list[tuple[float, float]] = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def _dot(cx: float, cy: float, r: float = 80.0) -> list[tuple[float, float]]:
    """A small closed loop representing a dot — 8 points around a tiny circle."""
    return _circle(cx, cy, r, n=8)


# ---------------------------------------------------------------------------
# Punctuation stroke tables
# ---------------------------------------------------------------------------

# Each value is a list-of-strokes, where each stroke is a list of (x,y) tuples
# in the 2048 em-square. Authored by eye; the shapes are intentionally loose
# so they read as "hand-drawn" when rendered next to actual Han characters.

_FULLWIDTH_STROKES: dict[str, list[list[tuple[float, float]]]] = {
    # 。(U+3002) fullwidth period — small circle in bottom-left quadrant
    "。": [_circle(540, 1560, 230, n=14)],

    # ，(U+FF0C) fullwidth comma — head + tail curving down-left
    "，": [[(460, 1300), (550, 1380), (580, 1500),
            (520, 1680), (380, 1840), (240, 1940)]],

    # 、(U+3001) ideographic caesura — short diagonal stroke
    "、": [[(540, 1320), (420, 1520), (280, 1720), (180, 1860)]],

    # ：(U+FF1A) fullwidth colon — two stacked dots (slightly left of centre)
    "：": [_dot(860, 760, r=100), _dot(860, 1460, r=100)],

    # ；(U+FF1B) fullwidth semicolon — top dot + lower comma tail
    "；": [
        _dot(880, 760, r=100),
        [(940, 1400), (980, 1480), (960, 1600),
         (870, 1760), (740, 1900)],
    ],

    # ！(U+FF01) fullwidth exclamation — vertical stroke + dot
    "！": [
        [(1024, 360), (1024, 1420)],
        _dot(1024, 1700, r=100),
    ],

    # ？(U+FF1F) fullwidth question mark — hook curve + dot
    "？": [
        [(540, 860), (620, 580), (880, 400), (1220, 470),
         (1460, 680), (1460, 920), (1260, 1100),
         (1040, 1240), (1024, 1460)],
        _dot(1024, 1700, r=100),
    ],

    # 「(U+300C) left corner bracket — L shape, upper-left
    "「": [[(1480, 520), (280, 520), (280, 1360)]],
    # 」(U+300D) right corner bracket — mirror, lower-right
    "」": [[(1768, 688), (1768, 1528), (568, 1528)]],

    # 『(U+300E) double left — two concentric L's
    "『": [
        [(1440, 440), (240, 440), (240, 1400)],
        [(1440, 620), (420, 620), (420, 1400)],
    ],
    # 』(U+300F) double right
    "』": [
        [(1808, 648), (1808, 1608), (608, 1608)],
        [(1628, 820), (1628, 1428), (608, 1428)],
    ],

    # （(U+FF08) fullwidth left paren — gentle curve
    "（": [[(1320, 280), (900, 600), (760, 1024),
            (900, 1448), (1320, 1768)]],
    # ）(U+FF09) fullwidth right paren
    "）": [[(728, 280), (1148, 600), (1288, 1024),
            (1148, 1448), (728, 1768)]],

    # 《(U+300A) double left angle
    "《": [
        [(960, 360), (360, 1024), (960, 1688)],
        [(1520, 360), (920, 1024), (1520, 1688)],
    ],
    # 》(U+300B) double right angle
    "》": [
        [(528, 360), (1128, 1024), (528, 1688)],
        [(1088, 360), (1688, 1024), (1088, 1688)],
    ],

    # 〈(U+3008) single left angle
    "〈": [[(1280, 360), (520, 1024), (1280, 1688)]],
    # 〉(U+3009) single right angle
    "〉": [[(768, 360), (1528, 1024), (768, 1688)]],

    # — (U+2014) em dash
    "—": [[(240, 1024), (1808, 1024)]],
    # ─ (U+2500) box-drawings horizontal (common alias for dash)
    "─": [[(160, 1024), (1888, 1024)]],

    # … (U+2026) horizontal ellipsis — three dots
    "…": [_dot(440, 1480, r=100),
          _dot(1024, 1480, r=100),
          _dot(1608, 1480, r=100)],

    # · (U+00B7) middle dot
    "·": [_dot(1024, 1024, r=110)],

    # ～ (U+FF5E) fullwidth tilde — wave
    "～": [[(320, 1024), (640, 880), (960, 1024), (1280, 1168),
            (1600, 1024), (1728, 920)]],
}

# Half-width ASCII punctuation — same visual language but half-wide,
# positioned near centre so they blend in a CJK line of text.
_ASCII_STROKES: dict[str, list[list[tuple[float, float]]]] = {
    ".": [_dot(1024, 1760, r=80)],
    ",": [[(1020, 1540), (1040, 1620), (1000, 1740),
           (900, 1860), (800, 1940)]],
    "!": [
        [(1024, 500), (1024, 1460)],
        _dot(1024, 1700, r=80),
    ],
    "?": [
        [(740, 700), (820, 500), (1020, 420), (1240, 500),
         (1340, 680), (1260, 880), (1100, 1020),
         (1024, 1240), (1024, 1440)],
        _dot(1024, 1700, r=80),
    ],
    ":": [_dot(1024, 900, r=80), _dot(1024, 1400, r=80)],
    ";": [
        _dot(1040, 900, r=80),
        [(1060, 1340), (1080, 1440), (1040, 1560),
         (920, 1720), (820, 1820)],
    ],
    "(": [[(1200, 360), (920, 620), (820, 1024),
           (920, 1428), (1200, 1688)]],
    ")": [[(848, 360), (1128, 620), (1228, 1024),
           (1128, 1428), (848, 1688)]],
    "-": [[(700, 1024), (1348, 1024)]],
    "_": [[(300, 1860), (1748, 1860)]],
    "/": [[(1480, 360), (568, 1688)]],
    '"': [
        [(800, 320), (760, 560)],
        [(1280, 320), (1240, 560)],
    ],
    "'": [[(1024, 320), (980, 560)]],
    "*": [  # 6-point asterisk as three overlapping segments
        [(768, 600), (1280, 1448)],
        [(1280, 600), (768, 1448)],
        [(1024, 528), (1024, 1520)],
    ],
    "#": [
        [(720, 400), (648, 1648)],
        [(1400, 400), (1328, 1648)],
        [(460, 820), (1640, 820)],
        [(408, 1228), (1588, 1228)],
    ],
    "@": [  # Approximate spiral: outer circle + inner loop
        _circle(1024, 1024, 520, n=18),
        [(1160, 1400), (880, 1300), (820, 1024),
         (980, 780), (1240, 820), (1320, 1100),
         (1180, 1420), (860, 1460)],
    ],
    "&": [
        [(860, 580), (1080, 480), (1220, 620), (1140, 800),
         (900, 980), (720, 1200), (800, 1440),
         (1040, 1520), (1280, 1400), (1440, 1240)],
    ],
}

_ALL: dict[str, list[list[tuple[float, float]]]] = {}
_ALL.update(_FULLWIDTH_STROKES)
_ALL.update(_ASCII_STROKES)


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------


class PunctuationSource:
    """Source adapter for the hand-authored punctuation strokes.

    Unlike g0v/mmh/kanjivg, this source keeps everything in-memory and
    requires no cache directory or network. Registered as a final
    fallback so primary sources still take precedence when they do cover
    a character.
    """

    def __init__(self) -> None:  # no-op: table is module-level
        pass

    def __repr__(self) -> str:
        return f"PunctuationSource(count={len(_ALL)})"

    def has(self, char: str) -> bool:
        return char in _ALL

    def get_character(self, char: str) -> Character:
        if char not in _ALL:
            raise CharacterNotFound(
                f"no punctuation stroke for U+{ord(char):04X} ({char!r})"
            )
        raw_strokes = _ALL[char]
        strokes: list[Stroke] = []
        for idx, track in enumerate(raw_strokes):
            pts = [Point(float(x), float(y)) for (x, y) in track]
            strokes.append(Stroke(
                index=idx,
                raw_track=pts,
                outline=[],           # no outline — we only have track data
                # Pre-classify as "其他" so the downstream classifier
                # doesn't have to guess at these exotic shapes.
                kind_code=9,
                kind_name="其他",
                has_hook=False,
            ))
        return Character(
            char=char,
            unicode_hex=f"{ord(char):04x}",
            strokes=strokes,
            data_source="punctuation",
        )


def supported_punctuation() -> list[str]:
    """Return a sorted list of every character this source can render.

    Useful for tests, docs, and the UI's 'available characters' hint.
    """
    return sorted(_ALL.keys())


__all__ = ["PunctuationSource", "supported_punctuation"]
