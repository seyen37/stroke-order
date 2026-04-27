"""
Stroke-filter "font styles" (Phase 5aj).

Strictly speaking these are not font generators — they are post-processing
filters that transform a kaishu Character's stroke data to *resemble*
another calligraphic style. Real Mingti / Lishu fonts are hand-drawn per
character by type designers; these filters just re-weight and re-shape
strokes based on their ``kind_code`` (classifier output, 1–8).

Three filters ship in this iteration:

- ``kaishu`` — identity (no-op); the default, produces original strokes.
- ``mingti`` — "假宋體": vertical strokes thickened, horizontal thinned
   (classic Mingti contrast), plus small perpendicular serifs at each
   stroke's endpoint.
- ``lishu``  — "假隸書": horizontal strokes end in a raised 波磔 flare;
   the whole character is vertically compressed to ~0.82 to feel squat.
- ``bold``   — "粗楷": every stroke's ``pen_size`` scaled up; outlines
   are left intact so the filter only shows in trace/filled cell styles
   (and the Phase-5aj empty-outline track fallback).

Design constraints
------------------
- **Pure** — ``apply_style`` never mutates its input; returns a new
  Character with copied strokes.
- **Robust to atypical kind_codes** — a stroke with ``kind_code`` outside
  1–8 (e.g. punctuation uses 9) is left untouched by style-specific
  tricks; bold still affects it.
- **Doesn't break downstream** — modified strokes keep valid ``outline``
  and ``raw_track`` / ``smoothed_track`` so every exporter (SVG, G-code,
  JSON) continues to work.

Not shipped this iteration (planned for later)
----------------------------------------------
- 篆書 (seal script) — needs shape-level re-structuring, not just
  stroke-level warping.
- 行書 (running script) — needs inter-stroke linking (牽絲) which needs
  stroke-order-aware transformations.
- Hand-tremor — random noise perturbation on each track; easy to add
  but cosmetic.
"""
from __future__ import annotations

from typing import Protocol

from ..ir import Character


class StyleTransform(Protocol):
    """A pure function that returns a re-styled copy of ``c``."""
    name: str
    description: str
    def apply(self, c: Character) -> Character: ...


from .bold import BoldStyle
from .kaishu import KaishuStyle
from .lishu import LishuStyle
from .mingti import MingtiStyle
from .seal_script import SealScriptStyle    # Phase 5at


#: Registry of available style names → factory callable.
STYLES: dict[str, type[StyleTransform]] = {
    "kaishu": KaishuStyle,
    "mingti": MingtiStyle,
    "lishu": LishuStyle,
    "bold": BoldStyle,
    # Phase 5at — actual font swap happens server-side; filter is a no-op.
    "seal_script": SealScriptStyle,
}

DEFAULT_STYLE = "kaishu"


def apply_style(c: Character, style_name: str) -> Character:
    """Apply a named stroke-filter style to a character.

    Returns the input unchanged for ``kaishu`` (fast path). For every
    other style, a deep-copied Character is returned — the caller's
    ``c`` is never mutated.

    Raises
    ------
    ValueError
        If ``style_name`` is not registered.
    """
    if style_name == "kaishu" or style_name == DEFAULT_STYLE:
        return c
    if style_name not in STYLES:
        raise ValueError(
            f"unknown style {style_name!r}; "
            f"valid: {sorted(STYLES)}"
        )
    style = STYLES[style_name]()
    return style.apply(c)


def list_styles() -> list[tuple[str, str]]:
    """Return ``[(name, description), ...]`` for UI population."""
    return [(name, cls().description) for name, cls in STYLES.items()]


__all__ = [
    "StyleTransform",
    "STYLES",
    "DEFAULT_STYLE",
    "apply_style",
    "list_styles",
    "KaishuStyle",
    "MingtiStyle",
    "LishuStyle",
    "BoldStyle",
    "SealScriptStyle",
]
