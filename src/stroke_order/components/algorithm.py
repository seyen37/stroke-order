"""
Greedy set-cover recommendation: which character should the user write next?

Problem: given a target character set (e.g. the 808 cover-set) and the user's
already-written characters, pick the next character from the remaining
candidates that adds the most NEW components to the user's coverage.

This is the classic NP-hard Set Cover problem; the greedy algorithm achieves
ln(n)+1 approximation factor and works well in practice for our scale
(hundreds of chars, hundreds of components).

Reference: VISION.md §四 (覆蓋率數學) — the cover-set "dynamic task assignment"
described as "每次選 information gain 最大的字推薦".
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .decompose import decompose


@dataclass(frozen=True)
class Recommendation:
    """One recommended next-character with its information gain.

    Attributes:
        char: The recommended character.
        new_components: Components this char would add to user's coverage
            (i.e. not already covered).
        existing_components: Components this char shares with what user
            already wrote (no new info, but reinforces existing).
        gain: ``len(new_components)`` — primary ranking metric.
    """

    char: str
    new_components: frozenset[str]
    existing_components: frozenset[str]

    @property
    def gain(self) -> int:
        return len(self.new_components)


def _component_set_for(char: str, ids_map: dict[str, str]) -> frozenset[str]:
    """Return distinct leaf components of ``char`` as a frozenset."""
    return frozenset(decompose(char, ids_map))


def coverage_status(
    written_chars: Iterable[str],
    target_chars: Iterable[str],
    ids_map: dict[str, str],
) -> dict:
    """Compute current coverage stats for the user's written characters.

    Returns:
        Dict with::
            covered_components:    distinct components user has written
            target_components:     distinct components in target set
            covered_count:         len(covered_components)
            target_count:          len(target_components)
            coverage_ratio:        covered_count / target_count (0..1)
            unwritten_chars:       target chars user hasn't written yet
            composable_count:      # of target chars whose components are
                                    fully covered (incl. already-written)
            composable_ratio:      composable_count / len(target_chars)
    """
    target_chars_list = list(target_chars)
    written_set = set(written_chars)

    covered: set[str] = set()
    for c in written_set:
        covered.update(decompose(c, ids_map))

    target_components: set[str] = set()
    target_per_char: dict[str, frozenset[str]] = {}
    for c in target_chars_list:
        comps = _component_set_for(c, ids_map)
        target_per_char[c] = comps
        target_components.update(comps)

    composable_count = sum(
        1 for c in target_chars_list
        if target_per_char[c].issubset(covered)
    )

    return {
        "covered_components": covered,
        "target_components": target_components,
        "covered_count": len(covered & target_components),
        "target_count": len(target_components),
        "coverage_ratio": (
            len(covered & target_components) / len(target_components)
            if target_components else 0.0
        ),
        "unwritten_chars": [c for c in target_chars_list if c not in written_set],
        "composable_count": composable_count,
        "composable_ratio": (
            composable_count / len(target_chars_list) if target_chars_list else 0.0
        ),
    }


def recommend_next(
    written_chars: Iterable[str],
    target_chars: Iterable[str],
    ids_map: dict[str, str],
    top_k: int = 5,
) -> list[Recommendation]:
    """Greedy: rank unwritten target chars by # of new components contributed.

    Tie-break order:
      1. More new components (primary)
      2. Fewer total components (preferring simpler chars when gain ties — they
         are easier to write and may be more frequent)
      3. Original order in target_chars (stable)

    Args:
        written_chars: Characters user has already written.
        target_chars: Cover-set candidate characters.
        ids_map: IDS map (from ``default_ids_map()``).
        top_k: How many recommendations to return.

    Returns:
        Up to ``top_k`` ``Recommendation`` objects, sorted best first.
        Empty if all target_chars already written or zero gain.
    """
    written_set = set(written_chars)
    covered: set[str] = set()
    for c in written_set:
        covered.update(decompose(c, ids_map))

    candidates = []
    for idx, char in enumerate(target_chars):
        if char in written_set:
            continue
        comps = _component_set_for(char, ids_map)
        new = comps - covered
        if not new:
            continue  # zero gain — skip
        existing = comps & covered
        candidates.append((
            -len(new),       # primary: more new = better (negative for ascending sort)
            len(comps),      # tie: fewer total = simpler char wins
            idx,             # stable: original order
            Recommendation(
                char=char,
                new_components=frozenset(new),
                existing_components=frozenset(existing),
            ),
        ))

    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    return [c[3] for c in candidates[:top_k]]


def greedy_full_cover(
    target_chars: Iterable[str],
    ids_map: dict[str, str],
    seed_chars: Iterable[str] = (),
) -> list[str]:
    """Run greedy set-cover all the way: select chars one at a time until
    no remaining char adds new components.

    Useful for "compute the minimum cover sequence offline".

    Args:
        target_chars: Pool of candidate characters.
        ids_map: IDS map.
        seed_chars: Already-included characters (skip in selection).

    Returns:
        Ordered list of selected characters. Length ≤ len(target_chars).
        The selection covers the maximum possible component set.
    """
    target_list = list(target_chars)
    selected: list[str] = []
    written = set(seed_chars)
    while True:
        recs = recommend_next(written, target_list, ids_map, top_k=1)
        if not recs:
            break
        next_char = recs[0].char
        selected.append(next_char)
        written.add(next_char)
    return selected
