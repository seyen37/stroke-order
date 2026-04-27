"""
CNS11643 全字庫 font-outline fallback source (Phase 5al).

Extends character coverage from g0v/MMH's ~9k chars to ~95k by extracting
glyph outlines straight from the Taiwan government's CNS 全字庫 TTF
fonts. Output is **outline geometry only** — not stroke-by-stroke
centerlines like g0v/MMH. For the writing-robot use case that means:

- SVG preview: looks correct (real font glyph).
- G-code: three modes, chosen at render time:
  1. ``skip``     — don't emit strokes; treat as "known char, skip writing"
  2. ``trace``    — sample outline to polyline and trace the contour
  3. ``skeleton`` — run Zhang-Suen thinning on a rasterised glyph to
     obtain a rough centreline (see :mod:`stroke_order.cns_skeleton`).

The source is **disabled** when the font files aren't present — callers
get a ``CharacterNotFound`` for every character rather than an
ImportError. To enable, drop the 全字庫 TTFs into::

    ~/.stroke-order/cns-fonts/

or point ``STROKE_ORDER_CNS_FONT_DIR`` at another directory.

Font plane routing
------------------
Unicode plane selects which TTF to consult:

- Plane 0 (BMP, 0x0000–0xFFFF)                 → TW-{Style}-98_1.ttf
- Plane 2 (CJK Extension B/C/D/E/F/G/I)         → TW-{Style}-Ext-B-98_1.ttf
- Plane 15 (Supplementary PUA-A)                → TW-{Style}-Plus-98_1.ttf

``Style`` defaults to Kai (楷) — the closest thing to the MOE kaishu
in g0v. Sung (宋) is also supported if its files are present; call
``CNSFontSource(style="sung")`` to get Mingti-style glyphs.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..ir import EM_SIZE, Character, Point, Stroke
from .g0v import CharacterNotFound


_ENV_DIR = "STROKE_ORDER_CNS_FONT_DIR"
_DEFAULT_DIR = Path.home() / ".stroke-order" / "cns-fonts"


def default_cns_font_dir() -> Path:
    env = os.environ.get(_ENV_DIR)
    return Path(env).expanduser() if env else _DEFAULT_DIR


#: TTF filename templates by Unicode plane. {style} = "Kai" or "Sung".
_FONT_PER_PLANE = {
    0:  "TW-{style}-98_1.ttf",        # BMP
    2:  "TW-{style}-Ext-B-98_1.ttf",  # CJK Ext B/C/D/E/F/G/I
    15: "TW-{style}-Plus-98_1.ttf",   # PUA-A
}


class CNSFontSource:
    """Extract glyph outlines from the Taiwan 全字庫 TTF fonts.

    Each character returned has **exactly one :class:`Stroke`** whose
    ``outline`` contains the entire glyph's path commands (possibly
    multiple contours separated by M commands). ``raw_track`` is empty;
    downstream G-code writers check for that and treat it as a CNS-font
    char to be handled per user choice (skip / trace / skeleton).
    """

    def __init__(
        self,
        font_dir: Optional[Path] = None,
        style: str = "kai",
    ) -> None:
        self.font_dir = Path(font_dir) if font_dir else default_cns_font_dir()
        if style not in ("kai", "sung"):
            raise ValueError(f"style must be 'kai' or 'sung', got {style!r}")
        self.style = style
        self._style_name = "Kai" if style == "kai" else "Sung"
        # Lazily-loaded {filename: TTFont}
        self._fonts: dict[str, object] = {}
        # Character-level memoisation
        self._cache: dict[str, Character] = {}

    def __repr__(self) -> str:
        return (f"CNSFontSource(dir={self.font_dir!s}, "
                f"style={self.style!r}, loaded_fonts={len(self._fonts)})")

    # ---------- diagnostics -----------------------------------------------

    def available_planes(self) -> list[int]:
        """Return the Unicode planes for which a TTF is present."""
        return [
            plane for plane, tmpl in _FONT_PER_PLANE.items()
            if (self.font_dir / tmpl.format(style=self._style_name)).exists()
        ]

    def is_ready(self) -> bool:
        """True iff at least one TTF is present in the font dir."""
        return bool(self.available_planes())

    # ---------- core read -------------------------------------------------

    def _font_for_plane(self, plane: int):
        """Return a loaded TTFont for ``plane`` or None if the file is absent."""
        tmpl = _FONT_PER_PLANE.get(plane)
        if tmpl is None:
            return None
        filename = tmpl.format(style=self._style_name)
        if filename in self._fonts:
            return self._fonts[filename]
        path = self.font_dir / filename
        if not path.exists():
            return None
        try:
            from fontTools.ttLib import TTFont
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "fontTools is required for CNSFontSource; "
                "install with `pip install fonttools`"
            ) from e
        font = TTFont(str(path), lazy=True)
        self._fonts[filename] = font
        return font

    def get_character(self, char: str) -> Character:
        if char in self._cache:
            return self._cache[char]
        cp = ord(char)
        plane = cp >> 16
        font = self._font_for_plane(plane)
        if font is None:
            raise CharacterNotFound(
                f"no CNS font for U+{cp:04X} ({char!r}) — "
                f"plane {plane} TTF absent from {self.font_dir}"
            )
        cmap = font.getBestCmap()
        gname = cmap.get(cp)
        if gname is None:
            raise CharacterNotFound(
                f"CNS font missing glyph for U+{cp:04X} ({char!r})"
            )
        # Draw glyph via a command-capturing pen.
        pen = _OutlineCmdPen(font.getGlyphSet())
        font.getGlyphSet()[gname].draw(pen)
        if not pen.commands:
            raise CharacterNotFound(
                f"CNS font has glyph but no drawable outline for U+{cp:04X}"
            )
        # Normalise coords into the canonical 2048 em frame.
        units_per_em = font["head"].unitsPerEm
        ascender = font["hhea"].ascender
        scale = EM_SIZE / units_per_em
        cmds = [
            _transform_cmd(cmd, scale=scale, ascender=ascender)
            for cmd in pen.commands
        ]
        # Phase 5am: tag Sung-style chars with a distinct data_source so
        # downstream code (mingti style filter, server bypass) can tell
        # "real Sung outline" apart from "Kai outline awaiting filter".
        # Kai keeps the bare "cns_font" tag for back-compat with 5al tests.
        ds = "cns_font_sung" if self.style == "sung" else "cns_font"
        c = Character(
            char=char,
            unicode_hex=f"{cp:04x}",
            strokes=[Stroke(
                index=0,
                raw_track=[],       # empty: no centreline yet
                outline=cmds,
                kind_code=9,
                kind_name="其他",
                has_hook=False,
            )],
            data_source=ds,
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
# Helpers
# ---------------------------------------------------------------------------


class _OutlineCmdPen:
    """fontTools SegmentPen that collects move/line/curve events.

    Implements the duck-typed Pen protocol (moveTo / lineTo / qCurveTo /
    curveTo / closePath / endPath). Commands are captured in FONT coords
    (Y-up); the caller converts them into our Y-down canonical frame.

    Tracks the current pen position explicitly so we can decompose
    multi-control-point ``qCurveTo`` into individual Q segments without
    assuming the previous command was an M/L.
    """
    def __init__(self, glyph_set):
        self.glyph_set = glyph_set
        self.commands: list[dict] = []
        self._current: tuple[float, float] = (0.0, 0.0)
        self._start: Optional[tuple[float, float]] = None

    def moveTo(self, pt):
        self.commands.append({"type": "M", "x": pt[0], "y": pt[1]})
        self._current = (pt[0], pt[1])
        self._start = (pt[0], pt[1])

    def lineTo(self, pt):
        self.commands.append({"type": "L", "x": pt[0], "y": pt[1]})
        self._current = (pt[0], pt[1])

    def qCurveTo(self, *points):
        # fontTools quadratic Bezier: a sequence of control points (all
        # off-curve) plus a final on-curve endpoint. Consecutive off-curve
        # pairs imply an on-curve midpoint. Also supports TrueType-style
        # "last point may be None" for all-off closed curves.
        if not points:
            return
        if points[-1] is None:
            # All off-curve: curve wraps back to start. Treat it as if
            # last point equals the first control (rarely encountered).
            points = points[:-1] + (points[0],)
        # Decompose into single-control Q segments.
        for i in range(len(points) - 1):
            ctrl = points[i]
            if i < len(points) - 2:
                nxt = points[i + 1]
                end = ((ctrl[0] + nxt[0]) / 2, (ctrl[1] + nxt[1]) / 2)
            else:
                end = points[-1]
            self.commands.append({
                "type": "Q",
                "begin": {"x": ctrl[0], "y": ctrl[1]},
                "end":   {"x": end[0],  "y": end[1]},
            })
            self._current = end

    def curveTo(self, *points):
        # Cubic Bezier: triplets of (ctrl1, ctrl2, endpoint).
        if len(points) % 3 != 0:
            return
        for i in range(0, len(points), 3):
            c1, c2, ep = points[i], points[i + 1], points[i + 2]
            self.commands.append({
                "type": "C",
                "begin": {"x": c1[0], "y": c1[1]},
                "mid":   {"x": c2[0], "y": c2[1]},
                "end":   {"x": ep[0], "y": ep[1]},
            })
            self._current = (ep[0], ep[1])

    def closePath(self):
        # Our downstream SVG renderer auto-closes at each M; no command needed.
        pass

    def endPath(self):
        pass


def _transform_cmd(cmd: dict, *, scale: float, ascender: float) -> dict:
    """Map one outline command from font (Y-up) to canonical (Y-down) coords.

    ``y_out = (ascender - y_font) * scale``  (flip + scale uniformly).
    """
    def _pt(px, py):
        return {"x": px * scale, "y": (ascender - py) * scale}

    t = cmd["type"]
    if t in ("M", "L"):
        return {"type": t, **_pt(cmd["x"], cmd["y"])}
    if t == "Q":
        return {
            "type": "Q",
            "begin": _pt(cmd["begin"]["x"], cmd["begin"]["y"]),
            "end":   _pt(cmd["end"]["x"],   cmd["end"]["y"]),
        }
    if t == "C":
        return {
            "type": "C",
            "begin": _pt(cmd["begin"]["x"], cmd["begin"]["y"]),
            "mid":   _pt(cmd["mid"]["x"],   cmd["mid"]["y"]),
            "end":   _pt(cmd["end"]["x"],   cmd["end"]["y"]),
        }
    return cmd


# ---------------------------------------------------------------------------
# Phase 5al: CNS-mode adapter — choose how a CNS-font character renders
# ---------------------------------------------------------------------------


def apply_cns_outline_mode(
    c: Character,
    mode: str = "skip",
    *,
    prefer_g0v: bool = True,           # Phase 5aq Path 1 (default ON)
    junction_aware: bool = False,      # Phase 5aq Path 2 (experimental, opt-in)
) -> Character:
    """Convert a CNS-font character (outline-only) into one of three modes:

    - ``"skip"`` (default) — leave outline-only. SVG renders the outline
      filled; G-code skips because ``raw_track`` is empty.
    - ``"trace"`` — sample the outline into a polyline and store as
      ``raw_track``. G-code will write the contour. Slow but visually
      complete.
    - ``"skeleton"`` — produce centreline polylines suitable for
      writing-robot G-code. Phase 5aq adds two cooperating paths:

        * **Path 1** (``prefer_g0v=True``, default ON): if g0v has the
          character, swap in its canonical N-stroke layout — perfect
          alignment, but the visual switches from CNS outline to g0v
          kaishu. Covers ~6063 traditional chars.
        * **Path 2** (``junction_aware=True``, default OFF, experimental):
          run the Zhang-Suen + junction-aware splitter from
          ``cns_skeleton`` instead of the legacy endpoint walker.
          Per Phase 5aq investigation the splitter still over-segments
          on most CJK glyphs (Zhang-Suen produces too many false
          junctions for the heuristic to recover); kept opt-in so it
          can be exercised by future R&D without affecting prod paths.

      Defaults give the best behaviour today: Path 1 catches g0v chars
      perfectly, everything else falls through to the legacy 5al walker.

    No-op when ``c.data_source`` does not match a known outline-font
    source — covers CNS Kai (``"cns_font"``) / Sung (``"cns_font_sung"``)
    plus the MoE outline fonts added in 5av/5aw (``"moe_song"``,
    ``"moe_kaishu"``). All of them start out with one big outline-only
    Stroke, which the same skeleton conversion handles uniformly.
    Always returns a deep copy when modifying.
    """
    ds = c.data_source or ""
    is_outline_font = (
        ds.startswith("cns_font")
        or ds in ("moe_song", "moe_kaishu")
    )
    if not is_outline_font or mode == "skip":
        return c
    if mode not in ("trace", "skeleton"):
        raise ValueError(
            f"unknown cns mode {mode!r}; "
            "expected skip / trace / skeleton"
        )
    # Each CNS character has exactly one Stroke holding the full outline.
    src = c.strokes[0] if c.strokes else None
    if src is None or not src.outline:
        return c

    # Phase 5aq Path 1 — try g0v first for skeleton mode. trace stays
    # raw because trace's value is "show me the actual font outline".
    if mode == "skeleton" and prefer_g0v:
        aligned = _g0v_aligned(c)
        if aligned is not None:
            return aligned

    from copy import deepcopy
    new_c = deepcopy(c)

    if mode == "trace":
        tracks = _outline_to_polylines(src.outline)
    else:  # skeleton
        # Phase 5aq Path 2 — junction-aware splitting (default) or the
        # legacy 5al endpoint walker.
        if junction_aware:
            from ..cns_skeleton import outline_to_skeleton_tracks_v2
            tracks = outline_to_skeleton_tracks_v2(src.outline)
        else:
            from ..cns_skeleton import outline_to_skeleton_tracks
            tracks = outline_to_skeleton_tracks(src.outline)

    # Replace the single big outline stroke with one Stroke per polyline,
    # so G-code emits separate pen-down/up cycles per traced contour.
    new_strokes: list[Stroke] = []
    for idx, track in enumerate(tracks):
        if len(track) < 2:
            continue
        new_strokes.append(Stroke(
            index=idx,
            raw_track=[Point(float(x), float(y)) for x, y in track],
            outline=[],   # we've consumed the outline into tracks
            kind_code=9,
            kind_name="其他",
            has_hook=False,
        ))
    if new_strokes:
        new_c.strokes = new_strokes
    return new_c


def _g0v_aligned(cns_c: Character) -> Optional[Character]:
    """Phase 5aq Path 1: try to swap a CNS character for its g0v equivalent.

    Returns a new Character whose strokes come from g0v (with proper
    raw_tracks, kind_codes, smoothing) but whose ``data_source`` is
    tagged ``cns_font_..._g0v_aligned`` so callers can tell it took the
    canonical fast-path. Returns ``None`` when g0v doesn't have the
    character — the caller then falls back to Path 2.

    Both g0v and CNS fonts use the canonical 2048 Y-down em frame, so
    the strokes are visually compatible without any bbox transform.
    """
    from .g0v import G0VSource, CharacterNotFound as _NotFound
    from ..classifier import classify_character
    from ..smoothing import smooth_character
    try:
        g0v_c = G0VSource().get_character(cns_c.char)
    except _NotFound:
        return None
    classify_character(g0v_c)
    smooth_character(g0v_c)
    # Tag the data_source so downstream knows the swap happened. Keep
    # the CNS prefix so existing ``startswith("cns_font")`` bypass and
    # CNS-mode tests continue to work.
    g0v_c.data_source = (cns_c.data_source or "cns_font") + "_g0v_aligned"
    return g0v_c


def _outline_to_polylines(outline_cmds: list[dict],
                          samples_per_curve: int = 8
                          ) -> list[list[tuple[float, float]]]:
    """Sample a multi-contour outline into a list of polylines (one per M)."""
    out: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for cmd in outline_cmds:
        t = cmd["type"]
        if t == "M":
            if len(cur) >= 2:
                out.append(cur)
            cur = [(cmd["x"], cmd["y"])]
        elif t == "L":
            cur.append((cmd["x"], cmd["y"]))
        elif t == "Q":
            if not cur:
                continue
            p0 = cur[-1]
            p1 = (cmd["begin"]["x"], cmd["begin"]["y"])
            p2 = (cmd["end"]["x"],   cmd["end"]["y"])
            for i in range(1, samples_per_curve + 1):
                tt = i / samples_per_curve
                u = 1.0 - tt
                cur.append((u * u * p0[0] + 2 * u * tt * p1[0] + tt * tt * p2[0],
                            u * u * p0[1] + 2 * u * tt * p1[1] + tt * tt * p2[1]))
        elif t == "C":
            if not cur:
                continue
            p0 = cur[-1]
            p1 = (cmd["begin"]["x"], cmd["begin"]["y"])
            p2 = (cmd["mid"]["x"],   cmd["mid"]["y"])
            p3 = (cmd["end"]["x"],   cmd["end"]["y"])
            for i in range(1, samples_per_curve + 1):
                tt = i / samples_per_curve
                u = 1.0 - tt
                cur.append((
                    u**3 * p0[0] + 3 * u**2 * tt * p1[0]
                    + 3 * u * tt**2 * p2[0] + tt**3 * p3[0],
                    u**3 * p0[1] + 3 * u**2 * tt * p1[1]
                    + 3 * u * tt**2 * p2[1] + tt**3 * p3[1],
                ))
    if len(cur) >= 2:
        out.append(cur)
    return out


# ---------------------------------------------------------------------------
# Phase 5am: lazy singletons so the server can re-use one TTFont per process
# ---------------------------------------------------------------------------


_KAI_SINGLETON: Optional[CNSFontSource] = None
_SUNG_SINGLETON: Optional[CNSFontSource] = None


def get_cns_kai_source() -> CNSFontSource:
    """Process-wide lazy Kai source. Always returns the same instance."""
    global _KAI_SINGLETON
    if _KAI_SINGLETON is None:
        _KAI_SINGLETON = CNSFontSource(style="kai")
    return _KAI_SINGLETON


def get_cns_sung_source() -> CNSFontSource:
    """Process-wide lazy Sung source. Mirrors :func:`get_cns_kai_source`.

    Used by the Phase-5am ``_upgrade_to_sung`` hook in ``web.server`` so
    every request shares one ``TTFont`` per plane, rather than spinning
    up fresh font handles per character.
    """
    global _SUNG_SINGLETON
    if _SUNG_SINGLETON is None:
        _SUNG_SINGLETON = CNSFontSource(style="sung")
    return _SUNG_SINGLETON


def reset_cns_singletons() -> None:
    """Drop cached singletons. Used by tests that monkeypatch the font dir."""
    global _KAI_SINGLETON, _SUNG_SINGLETON
    _KAI_SINGLETON = None
    _SUNG_SINGLETON = None


__all__ = [
    "CNSFontSource",
    "default_cns_font_dir",
    "apply_cns_outline_mode",
    "get_cns_kai_source",
    "get_cns_sung_source",
    "reset_cns_singletons",
]
