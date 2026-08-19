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
from ..sources.noto_hei import get_hei_source
from ..sources.chiron_round import get_round_source

# Per Phase 6z v0.3 §5 軸 1 + Q1 user decision: 教育部楷書 (moe_kaishu)
# is the MVP default — most natural handwriting feel for the acquisition
# target ("想要禪繞風格但不想慢慢手繪的人"). Other sources are exposed as
# advanced options via the UI dropdown but not silently defaulted (對位 D-C
# 強紀律弱預設 — UI must surface the choice rather than silently applying).
DEFAULT_SOURCE = "moe_kaishu"
DEFAULT_SAMPLES_PER_CURVE = 8

# Source dispatch — ordered for the UI dropdown.
SOURCE_REGISTRY: dict[str, Callable] = {
    "noto_hei": get_hei_source,
    "chiron_round": get_round_source,
    "moe_kaishu": get_kaishu_source,
    "cns_kai": get_cns_kai_source,
    "moe_song": get_song_source,
    "moe_lishu": get_lishu_source,
    "chongxi_seal": get_seal_source,
}

_LABELS = {
    "noto_hei": "思源黑體",
    "chiron_round": "昭源環方",
    "moe_kaishu": "教育部楷書",
    "cns_kai": "CNS 楷書",
    "moe_song": "教育部宋體",
    "moe_lishu": "教育部隸書",
    "chongxi_seal": "崇喜篆書",
}


def source_supports_weight(source: str) -> bool:
    """該字源吃不吃 ``weight``（R1b 字重軸）——UI/API 的單一事實源。

    由字源物件的 ``supports_weight`` 類別屬性宣告，呼叫端不必 try/except
    TypeError 去猜。目前只有 ``chiron_round``（昭源環方有可變字體）。
    """
    factory = SOURCE_REGISTRY.get(source)
    if factory is None:
        return False
    try:
        return bool(getattr(factory(), "supports_weight", False))
    except Exception:
        return False


def extract_outline_polylines(
    char: str,
    source: str = DEFAULT_SOURCE,
    samples_per_curve: int = DEFAULT_SAMPLES_PER_CURVE,
    weight: int | None = None,
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
    weight
        R1b 字重軸。``None``（預設）＝走字源的靜態字型，行為與記憶體足跡
        與 R1b 之前完全相同。給值則要求該字源有可變字重軸（見
        :func:`source_supports_weight`），沒有就拋 ``ValueError``。

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
    if weight is None:
        character = src.get_character(char)  # raises CharacterNotFound
    else:
        if not getattr(src, "supports_weight", False):
            raise ValueError(
                f"source {source!r} has no weight axis; sources that do: "
                f"{sorted(k for k in SOURCE_REGISTRY if source_supports_weight(k))}"
            )
        character = src.get_character(char, weight=weight)
    if not character.strokes:
        return []
    outline_cmds = list(character.strokes[0].outline or [])
    if not outline_cmds:
        return []
    polys = _outline_to_polylines(
        outline_cmds, samples_per_curve=samples_per_curve
    )
    if weight is not None:
        # 可變字體保留重疊輪廓（重疊消除無法沿字重軸內插），拿 even-odd
        # 直接畫會在重疊處打出假洞。這裡是折線化後的唯一縫，統一補正；
        # 靜態路徑（weight=None）完全不經過，故零回歸。
        resolver = getattr(src, "resolve_overlaps", None)
        if resolver is not None:
            polys = resolver(polys)
    return polys


def list_sources() -> list[dict]:
    """Return ``[{key, label, ready, supports_weight}]`` for each source.

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
                # R1b：UI 靠這欄決定要不要給字重滑桿（不要在前端硬寫
                # 字源名——那就成了第二個事實源）
                "supports_weight": source_supports_weight(key),
            }
        )
    return out


__all__ = [
    "extract_outline_polylines",
    "source_supports_weight",
    "list_sources",
    "SOURCE_REGISTRY",
    "DEFAULT_SOURCE",
    "DEFAULT_SAMPLES_PER_CURVE",
]
