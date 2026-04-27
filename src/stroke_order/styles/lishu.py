"""Lishu-like style — horizontal 波磔 flare + vertical squash.

Two distinctive Lishu features are approximated:

1. **波磔** — horizontal strokes end in an upward-forward flare (the
   classic 雁尾 "goose tail"). Implemented by extending the end of
   every horizontal-kind stroke with two extra track points that
   curve upward + slightly forward.
2. **扁方 proportion** — genuine lishu characters are noticeably
   wider than tall. We vertically compress the whole character to
   ~0.82 around its vertical centre. Horizontal extent is preserved.

Works best with ``cell_style=trace`` or ``filled``. For outline-filled
renderings the vertical squash visibly flattens the character; the
波磔 flare is drawn as polyline (track-based) so it's visible in
``outline`` mode too (via the empty-outline fallback in ``_char_svg``
for strokes whose ``outline`` we've reset).
"""
from __future__ import annotations

from ..ir import Character, EM_SIZE
from . import _helpers as H
from ._helpers import deepcopy_character as _deepcopy_character


class LishuStyle:
    name = "lishu"
    description = "假隸書（橫末波磔 + 整字扁方壓縮）"

    #: Length (em units) of the 波磔 flare added to horizontal stroke ends.
    FLARE_LENGTH = 140.0

    #: Vertical compression factor — 0.82 makes characters ≈18 % shorter.
    COMPRESS_Y = 0.82

    #: Slight extra width on horizontals to balance the compressed height.
    HORIZ_PEN_SCALE = 1.5

    def apply(self, c: Character) -> Character:
        # Phase 5au: a real MoE 隸書 outline came in via _upgrade_to_lishu —
        # don't run the assumed-Kai filter on top of it (would compress an
        # already-flat lishu glyph and add 波磔 on top of real lishu strokes).
        if (c.data_source or "").startswith("moe_lishu"):
            return c
        new_c = _deepcopy_character(c)
        pivot_y = EM_SIZE / 2.0

        # Pass 1: add 波磔 on horizontals, scale their pen_size a bit.
        for s in new_c.strokes:
            if H.is_horizontal(s.kind_code):
                H.add_lishu_flare(s, length=self.FLARE_LENGTH)
                base = s.pen_size if s.pen_size is not None else 18.0
                s.pen_size = base * self.HORIZ_PEN_SCALE

        # Pass 2: compress every stroke vertically around the em centre.
        # Do this AFTER the flare so the flare points are compressed too
        # (keeps the flare proportional to the now-shorter character).
        for s in new_c.strokes:
            H.compress_vertical(s, factor=self.COMPRESS_Y, pivot_y=pivot_y)

        return new_c
