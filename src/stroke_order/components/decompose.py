"""
Recursive decomposition of Chinese characters to leaf components.

A "leaf component" is the smallest reusable building block in a character's
IDS-derived structure tree. Examples::

    decompose("明", ids_map)   → ["日", "月"]
    decompose("林", ids_map)   → ["木", "木"]
    decompose("校", ids_map)   → ["木", "交"]
    decompose("永", ids_map)   → ["永"]      # atomic
    decompose("樹", ids_map)   → ["木", "壴", "寸"]   # 樹 = ⿰木⿱壴寸

Rules:
- IDS structure descriptors (⿰⿱⿴ ...) are skipped — they're spatial relations,
  not components.
- Compound markers (①-⑳) are kept as opaque atoms — these represent
  unencoded sub-components that cjkvi-ids couldn't reference by Unicode.
- Cycle prevention: if a char's IDS tree references back to itself, treat
  the recursion point as atomic.
- Depth limit: recursion stops at ``max_depth`` to bound runtime.
"""
from __future__ import annotations

from collections.abc import Iterable

from .ids import COMPOUND_MARKERS, IDS_DESCRIPTORS

DEFAULT_MAX_DEPTH = 10


def decompose(
    char: str,
    ids_map: dict[str, str],
    max_depth: int = DEFAULT_MAX_DEPTH,
    _depth: int = 0,
    _seen: frozenset[str] | None = None,
) -> list[str]:
    """Recursively decompose ``char`` to leaf components.

    Args:
        char: Single character to decompose.
        ids_map: {char: ids_string} from :func:`parse_ids_file`.
        max_depth: Hard cap on recursion depth (default 10).
        _depth, _seen: Internal recursion bookkeeping; do not pass.

    Returns:
        List of leaf components in their natural left-to-right / top-to-bottom
        traversal order. Duplicates preserved (e.g. 林 → ["木", "木"]).
    """
    if _seen is None:
        _seen = frozenset()
    if char in _seen or _depth >= max_depth:
        return [char]
    _seen = _seen | {char}

    ids_str = ids_map.get(char, char)
    # Atomic: ids equals char or no entry
    if not ids_str or ids_str == char:
        return [char]

    leaves: list[str] = []
    for c in ids_str:
        if c in IDS_DESCRIPTORS:
            continue
        if COMPOUND_MARKERS.match(c):
            # Keep compound marker as opaque atom (placeholder for unencoded
            # sub-component) so coverage analysis remains consistent.
            leaves.append(c)
            continue
        sub = decompose(c, ids_map, max_depth, _depth + 1, _seen)
        leaves.extend(sub)

    if not leaves:
        return [char]
    return leaves


def get_leaf_components(char: str, ids_map: dict[str, str]) -> set[str]:
    """Distinct leaf components of ``char`` (set, not list)."""
    return set(decompose(char, ids_map))


def collect_components(
    chars: Iterable[str], ids_map: dict[str, str]
) -> set[str]:
    """Union of leaf components across multiple characters.

    Useful for "what components does this user's written-set cover?".
    """
    out: set[str] = set()
    for c in chars:
        out.update(decompose(c, ids_map))
    return out


def is_atomic(char: str, ids_map: dict[str, str]) -> bool:
    """True iff ``char`` decomposes to itself only (no IDS structure)."""
    return decompose(char, ids_map) == [char]


def covers(
    target: str, available_components: set[str], ids_map: dict[str, str]
) -> bool:
    """Can ``target`` be fully composed from ``available_components``?"""
    target_leaves = set(decompose(target, ids_map))
    return target_leaves.issubset(available_components)
