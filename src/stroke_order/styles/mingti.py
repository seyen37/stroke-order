"""Mingti-like style — horizontal thin, vertical thick, small end-serifs.

This is a "feel" filter, not a real 宋體 typeface. The effect is best
seen with ``cell_style=trace`` or ``filled`` which renders stroke width
from the per-stroke ``pen_size``. With ``cell_style=outline`` (the
default g0v outline-fill) the Mingti contrast only shows on strokes
whose outline is empty (punctuation / added serif ticks).
"""
from __future__ import annotations

from ..ir import Character
from . import _helpers as H
from ._helpers import deepcopy_character as _deepcopy_character


class MingtiStyle:
    name = "mingti"
    description = "假宋體（橫細豎粗 + 末端襯線）"

    #: Pen-size base when a stroke has none. Matches _char_svg defaults.
    _BASE = 18.0

    #: Per-kind scale factors — tuned to give a noticeable Mingti-like
    #: horizontal/vertical contrast without making anything disappear.
    SCALE_HORIZONTAL = 0.55   # 橫 / 橫點 — thinner
    SCALE_VERTICAL = 2.2      # 豎 / 豎點 — much thicker
    SCALE_OTHER = 1.2         # 撇 / 捺 / 彎 — slight emphasis

    #: Length (em units) of the little end-tick that imitates a serif.
    SERIF_LENGTH = 55.0

    def apply(self, c: Character) -> Character:
        # Phase 5am + 5av: a real Sung outline came in via
        # _upgrade_to_sung. Skip the assumed-Kai filter so we don't add
        # fake serifs to glyphs that already are Mingti.
        ds = c.data_source or ""
        if ds.startswith("cns_font_sung") or ds == "moe_song":
            return c
        new_c = _deepcopy_character(c)
        for s in new_c.strokes:
            base = s.pen_size if s.pen_size is not None else self._BASE
            if H.is_horizontal(s.kind_code):
                s.pen_size = base * self.SCALE_HORIZONTAL
                # Add a small perpendicular tick at the stroke end.
                H.add_end_serif(s, length=self.SERIF_LENGTH,
                                kind="perpendicular")
            elif H.is_vertical(s.kind_code):
                s.pen_size = base * self.SCALE_VERTICAL
                H.add_end_serif(s, length=self.SERIF_LENGTH,
                                kind="perpendicular")
            else:
                s.pen_size = base * self.SCALE_OTHER
                # Other strokes (撇/捺/彎/鉤) get a subtler tick so
                # they match the Mingti geometric feel.
                H.add_end_serif(s, length=self.SERIF_LENGTH * 0.6,
                                kind="perpendicular")
        return new_c
