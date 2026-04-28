"""
IDS (Ideographic Description Sequence) loader.

Parses CHISE/cjkvi-ids format text files into a {char: ids_string} map.

Source: https://github.com/cjkvi/cjkvi-ids

File format::

    # Comment lines starting with #
    U+CODEPOINT\\tcharacter\\tIDS_string [\\t IDS_for_region [...]]

Examples::

    U+660E	明	⿰日月
    U+6797	林	⿰木木
    U+6C38	永	永                       # atomic — IDS == self
    U+4E0E	与	⿹②一[GTKV]	⿻②一[J]   # multi-region

For multi-region entries we keep only the first IDS_string. Region tags like
``[GTKV]`` are stripped from the IDS itself.

The bundled ``data/ids.txt`` is a snapshot from cjkvi-ids' master branch.
To refresh::

    curl -sL https://raw.githubusercontent.com/cjkvi/cjkvi-ids/master/ids.txt \\
        -o src/stroke_order/components/data/ids.txt
"""
from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Unicode IDS structure descriptors:
#   U+2FF0..U+2FFB  ⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻
#   U+31EF          ㇯  (graphic-form-based descriptor, less common)
# Built with chr() to avoid invisible-PUA-character corruption that bit us
# in scripts/analyze_808_components.py first iteration.
IDS_DESCRIPTORS: frozenset[str] = frozenset(
    chr(c) for c in range(0x2FF0, 0x2FFC)
) | {chr(0x31EF)}

# Variation selectors (U+FE00–U+FE0F): glyph variant markers, not structural
VARIATION_SELECTORS = re.compile(r"[︀-️]")

# Compound markers (U+2460–U+2473, ①②③…⑳): cjkvi-ids placeholders for
# unencoded sub-components. We treat these as opaque atoms.
COMPOUND_MARKERS = re.compile(r"[①-⑳]")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse_ids_file(path: Path) -> dict[str, str]:
    """Parse a cjkvi-ids ``ids.txt`` file into a {char: ids_string} dict.

    Multi-region IDS entries keep only the first (canonical) form.
    Region tags like ``[GTKV]`` are stripped. Variation selectors are removed.

    Args:
        path: path to ``ids.txt``

    Returns:
        Dict mapping each char to its primary IDS string. Atomic characters
        map to themselves (``ids[char] == char``).

    Raises:
        FileNotFoundError: if ``path`` doesn't exist.
    """
    out: dict[str, str] = {}
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        char = parts[1]
        ids_str = parts[2]
        # Strip leading region tag like [GTKJV] (rare in current data)
        if ids_str.startswith("[") and "]" in ids_str:
            ids_str = ids_str.split("]", 1)[1]
        # Strip trailing region tag like ⿰日月[GTJK]
        if "[" in ids_str and ids_str.endswith("]"):
            ids_str = ids_str[: ids_str.rindex("[")]
        ids_str = VARIATION_SELECTORS.sub("", ids_str)
        out[char] = ids_str
    return out


# ---------------------------------------------------------------------------
# Default loader (uses bundled snapshot)
# ---------------------------------------------------------------------------


def _bundled_ids_path() -> Path:
    """Resolve the bundled ``ids.txt`` path inside the package."""
    # importlib.resources.files() returns a Traversable; for our packaged
    # text file we can convert to a real path via the .files() API.
    files = resources.files("stroke_order.components") / "data" / "ids.txt"
    # Traversable.as_file() gives a context manager — but for a simple
    # bundled file inside a package, str() conversion works.
    return Path(str(files))


@lru_cache(maxsize=1)
def default_ids_map() -> dict[str, str]:
    """Load the bundled cjkvi-ids snapshot.

    Cached on first call — subsequent calls return the same dict in O(1).

    Returns:
        Dict {char: ids_string} for ~88,937 CJK characters.
    """
    return parse_ids_file(_bundled_ids_path())
