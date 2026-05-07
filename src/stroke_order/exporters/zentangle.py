"""
Phase 6z (zentangle 禪繞字) outline extraction — 6z-1.

Wraps the existing TTFont outline pipeline (Phase 5al, ``cns_font._outline_to_polylines``)
with a source-dispatch layer for the zentangle mode.

Public API
----------
* :func:`extract_outline_polylines` — char → list of closed-polyline contours
* :func:`list_sources` — UI dropdown helper

Output format: ``list[list[tuple[float, float]]]`` — each inner list is one
contour (closed polyline) of the character outline. A char like "心" typically
has 1-3 contours; "日" has 2 contours (outer rect + inner rect).

Coordinates are in the canonical Y-down frame, EM-scaled (~ ``ir.EM_SIZE``
units across the glyph). Frontend canvas mapper transforms to tile-local
coords (see ``static/zentangle/outline.mjs``).

Why this lives in ``exporters/``
--------------------------------
Mirrors ``mandala.py`` placement: data sources live in ``sources/``, downstream
*exporters / mode-specific modules* (mandala, sutra, doodle, **zentangle**)
that consume sources live in ``exporters/``. Keeps the import direction
``exporters → sources`` one-way.
"""
from __future__ import annotations

from typing import Callable

from ..sources.cns_font import _outline_to_polylines, get_cns_kai_source
from ..sources.chongxi_seal import get_seal_source
from ..sources.moe_kaishu import get_kaishu_source
from ..sources.moe_lishu import get_lishu_source
from ..sources.moe_song import get_song_source

# Per Phase 6z v0.3 §5 軸 1 + Q1 user decision: 教育部楷書 (moe_kaishu)
# is the MVP default — most natural handwriting feel for the acquisition
# target ("想要禪繞風格但不想慢慢手繪的人"). Other sources are exposed as
# advanced options via the UI dropdown but not silently defaulted (對位 D-C
# 強紀律弱預設 — UI must surface the choice rather than silently applying).
DEFAULT_SOURCE = "moe_kaishu"
DEFAULT_SAMPLES_PER_CURVE = 8

# Source dispatch — ordered for the UI dropdown.
SOURCE_REGISTRY: dict[str, Callable] = {
    "moe_kaishu": get_kaishu_source,
    "cns_kai": get_cns_kai_source,
    "moe_song": get_song_source,
    "moe_lishu": get_lishu_source,
    "chongxi_seal": get_seal_source,
}

_LABELS = {
    "moe_kaishu": "教育部楷書",
    "cns_kai": "CNS 楷書",
    "moe_song": "教育部宋體",
    "moe_lishu": "教育部隸書",
    "chongxi_seal": "崇喜篆書",
}


def extract_outline_polylines(
    char: str,
    source: str = DEFAULT_SOURCE,
    samples_per_curve: int = DEFAULT_SAMPLES_PER_CURVE,
) -> list[list[tuple[float, float]]]:
    """Extract list of closed-polyline contours for ``char`` from ``source``.

    Wraps the per-source ``get_character()`` pipeline (which returns a
    transformed-cmd list via ``_OutlineCmdPen`` + ``_transform_cmd``) and
    samples Bezier curves into linear polylines via
    :func:`cns_font._outline_to_polylines`.

    Parameters
    ----------
    char
        Single CJK character (``len(char) == 1``).
    source
        One of :data:`SOURCE_REGISTRY` keys
        (``moe_kaishu`` / ``cns_kai`` / ``moe_song`` / ``moe_lishu`` /
        ``chongxi_seal``).
    samples_per_curve
        Bezier sampling density. ``8`` is the established balance (see
        ``cns_font._outline_to_polylines``).

    Returns
    -------
    list of polylines; each polyline is a ``list[tuple[float, float]]`` in
    EM-scaled Y-down coordinates. Empty list if the glyph has no drawable
    outline (very rare; treated as not-found by callers).

    Raises
    ------
    ValueError
        ``char`` is not exactly one character, or ``source`` is unknown.
    CharacterNotFound
        Source has no glyph for ``char``.
    RuntimeError
        Source font file is missing on disk (advisable to fall back to
        another source via the registry order rather than aborting).
    """
    if not isinstance(char, str) or len(char) != 1:
        raise ValueError(
            f"char must be a single character (len 1), got {char!r}"
        )
    if source not in SOURCE_REGISTRY:
        raise ValueError(
            f"unknown source {source!r}; "
            f"valid: {sorted(SOURCE_REGISTRY.keys())}"
        )
    src = SOURCE_REGISTRY[source]()
    character = src.get_character(char)  # raises CharacterNotFound
    if not character.strokes:
        return []
    outline_cmds = list(character.strokes[0].outline or [])
    if not outline_cmds:
        return []
    return _outline_to_polylines(
        outline_cmds, samples_per_curve=samples_per_curve
    )


def list_sources() -> list[dict]:
    """Return ``[{key, label, ready}]`` for each registered source.

    UI uses this to populate the source dropdown. ``ready=False`` indicates
    the font file is missing and that source should be visually disabled
    (e.g. greyed out with an installation tooltip).
    """
    out = []
    for key, factory in SOURCE_REGISTRY.items():
        try:
            src = factory()
            ready = bool(getattr(src, "is_ready", lambda: True)())
        except Exception:
            ready = False
        out.append(
            {
                "key": key,
                "label": _LABELS.get(key, key),
                "ready": ready,
            }
        )
    return out


__all__ = [
    "extract_outline_polylines",
    "list_sources",
    "SOURCE_REGISTRY",
    "DEFAULT_SOURCE",
    "DEFAULT_SAMPLES_PER_CURVE",
]
