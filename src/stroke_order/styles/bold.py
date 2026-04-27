"""Bold kaishu — uniformly thicker strokes.

Implementation: scale every stroke's ``pen_size`` by a constant factor
(default 2.4×). The upgraded ``_char_svg`` (Phase 5aj) honours pen_size
in ``trace`` / ``filled`` modes, and also in ``outline`` / ``ghost``
modes for strokes whose outline is empty (e.g. punctuation).

For real outline-filled strokes (g0v / MMH data), a pen-size change
cannot reshape the pre-computed outline path — so in pure ``outline``
mode you'll see only the punctuation / text-fallback get bolded. Users
who want uniform bold everywhere should pair the ``bold`` style with
``cell_style=trace`` or ``filled``.
"""
from __future__ import annotations

from ..ir import Character
from ._helpers import deepcopy_character as _deepcopy_character


class BoldStyle:
    name = "bold"
    description = "粗楷（所有筆畫加粗）"

    #: Multiplier applied to pen_size. When the stroke has no pen_size
    #: (most g0v/MMH strokes), we fall back to a default baseline that
    #: the SVG renderer uses for the relevant cell_style, then scale.
    scale: float = 2.4

    #: Fallback baselines aligned with ``_char_svg``'s defaults.
    _DEFAULT_TRACK = 18.0
    _DEFAULT_FILLED_TRACK = 14.0
    _DEFAULT_EMPTY_OUTLINE = 40.0

    def apply(self, c: Character) -> Character:
        new_c = _deepcopy_character(c)
        for s in new_c.strokes:
            base = (
                s.pen_size
                if s.pen_size is not None
                else (self._DEFAULT_EMPTY_OUTLINE if not s.outline
                      else self._DEFAULT_TRACK)
            )
            s.pen_size = base * self.scale
        return new_c
