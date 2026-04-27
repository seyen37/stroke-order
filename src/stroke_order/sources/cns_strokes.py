"""
CNS11643 canonical stroke sequence (Phase 5ap).

Parses the 全字庫 ``CNS_strokes_sequence.txt`` into a lookup that returns
the **canonical writing order** for any covered character — a list of
single-digit stroke type codes:

==== ==== ============================
code 名   description
==== ==== ============================
1    橫   horizontal stroke
2    豎   vertical stroke
3    撇   left-falling diagonal
4    點   dot
5    折   bend / hook (any non-trivial curve)
==== ==== ============================

These five classes are the **CNS simplified taxonomy**, distinct from
the project's internal 1-8 classifier (which adds 鉤 / 提 / 捺). Use
this when you need the *count* and *type sequence* for a glyph as
specified by the Taiwan government's reference data, e.g. to validate
the output of skeletonisation against the canonical N-stroke layout.

File format (verified by inspection)
------------------------------------

``CNS_strokes_sequence.txt`` — one line per CNS code::

    1-4243   5
    1-4427   55
    1-4663   45534

Tab-separated; second column is a digit string of length = N strokes.

Reverse lookup
--------------
Unicode codepoint → CNS code routes through :class:`CNSComponents`,
which already knows how to find the four ``CNS2UNICODE_*.txt`` files
under multiple plausible roots (Properties/, sibling MapingTables/,
``STROKE_ORDER_CNS_MAPPING_DIR``).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .cns_components import CNSComponents, default_cns_properties_dir


#: Canonical stroke type names by code, exposed for diagnostics / UI.
STROKE_NAMES: dict[int, str] = {
    1: "橫", 2: "豎", 3: "撇", 4: "點", 5: "折",
}


class CNSStrokes:
    """Lazy-loaded canonical stroke-sequence lookup.

    Mirrors :class:`CNSComponents`: silent ``is_ready() is False`` when
    the source file is missing; :meth:`canonical_strokes` returns ``[]``
    so callers can fall back gracefully.
    """

    def __init__(self, properties_dir: Optional[Path] = None) -> None:
        self.dir = (Path(properties_dir) if properties_dir
                    else default_cns_properties_dir())
        self._loaded = False
        self._sequences: dict[str, list[int]] = {}   # cns_code → [codes]
        # Re-use components' Unicode↔CNS map (it already searches sensible
        # locations for ``CNS2UNICODE_*.txt``).
        self._components = CNSComponents(self.dir)

    def is_ready(self) -> bool:
        return (self.dir / "CNS_strokes_sequence.txt").exists()

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        path = self.dir / "CNS_strokes_sequence.txt"
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            cns_code, seq_str = parts[0].strip(), parts[1].strip()
            if not cns_code or not seq_str:
                continue
            try:
                seq = [int(ch) for ch in seq_str
                       if ch.isdigit() and 1 <= int(ch) <= 5]
            except ValueError:
                continue
            if seq:
                self._sequences[cns_code] = seq

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def canonical_strokes(self, char: str) -> list[int]:
        """Return ``[1,3,4,...]`` writing-order codes; ``[]`` if not covered.

        The list length is the canonical N-stroke count.
        """
        if len(char) != 1:
            return []
        self._load()
        cns = self._components.cns_code_for(char)
        if cns is None:
            return []
        return self._sequences.get(cns, [])

    def canonical_count(self, char: str) -> int:
        """Number of strokes per CNS data; 0 if uncovered."""
        return len(self.canonical_strokes(char))

    def canonical_names(self, char: str) -> list[str]:
        """Pretty names (橫/豎/撇/點/折) for ``char``'s strokes."""
        return [STROKE_NAMES.get(c, "?") for c in self.canonical_strokes(char)]


__all__ = ["CNSStrokes", "STROKE_NAMES"]
