"""
CNS11643 component (部件) decomposition (Phase 5al).

Parses the 全字庫 ``CNS_component.txt`` + ``CNS_component_ref.txt`` +
``CNS2UNICODE_*.txt`` files into a single ``decompose(char) → [parts]``
function.

**Important:** 全字庫 部件 data is a **flat list of component characters**,
not an IDS (Ideographic Description Sequence). It tells you "字 X
contains parts {A, B, C}" but NOT how they are spatially arranged.
Useful for diagnostics and learning aids; not enough for compositional
glyph synthesis.

File format (verified by inspection)
------------------------------------

``CNS_component_ref.txt`` — id ↔ char mapping::

    1   1-2B21   31D0   ㇐
    3   1-2B23   31D1   ㇑
    ...

``CNS_component.txt`` — character → component-id list::

    1-227A   20,119,55,126
    1-2728   67
    ...

``CNS2UNICODE_Unicode BMP.txt`` (and Plane 2/3/15) — CNS code ↔ Unicode::

    1-2122   FF0C
    1-4427   738B
    ...
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


_ENV_DIR = "STROKE_ORDER_CNS_PROPERTIES_DIR"
_DEFAULT_DIR = Path.home() / ".stroke-order" / "cns-properties"


def default_cns_properties_dir() -> Path:
    env = os.environ.get(_ENV_DIR)
    return Path(env).expanduser() if env else _DEFAULT_DIR


class CNSComponents:
    """Lazy-loaded component decomposition lookup.

    All files are optional — if any are missing the corresponding lookup
    just returns empty results so the caller can fall back gracefully.
    """

    def __init__(self, properties_dir: Optional[Path] = None) -> None:
        self.dir = Path(properties_dir) if properties_dir else default_cns_properties_dir()
        self._loaded = False
        self._ref: dict[int, str] = {}              # id → char
        self._composition: dict[str, list[int]] = {} # cns_code → [ids]
        self._cns_to_unicode: dict[str, str] = {}    # cns_code → unicode hex
        self._unicode_to_cns: dict[str, str] = {}    # unicode hex → cns_code

    def is_ready(self) -> bool:
        """True iff at least the component file is loadable."""
        return (self.dir / "CNS_component.txt").exists()

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        # Component-id → char (㇐, 一, 口, etc.)
        ref_path = self.dir / "CNS_component_ref.txt"
        if ref_path.exists():
            for line in ref_path.read_text(encoding="utf-8").splitlines():
                parts = line.split("\t")
                if len(parts) >= 4:
                    try:
                        self._ref[int(parts[0])] = parts[3]
                    except (ValueError, IndexError):
                        continue
        # Char-cns-code → component-ids
        comp_path = self.dir / "CNS_component.txt"
        if comp_path.exists():
            for line in comp_path.read_text(encoding="utf-8").splitlines():
                parts = line.split("\t")
                if len(parts) != 2:
                    continue
                cns_code, ids_str = parts
                try:
                    ids = [int(s) for s in ids_str.split(",") if s.strip()]
                except ValueError:
                    continue
                self._composition[cns_code] = ids
        # Unicode-hex ↔ CNS-code, all four planes. The Properties zip
        # doesn't include these — they live in MapingTables.zip → Unicode/.
        # Look in several plausible locations relative to the properties
        # dir so users can keep the standard 全字庫 layout.
        candidate_roots = [
            self.dir,                                     # mapping dropped here
            self.dir / "Unicode",                         # ./Unicode/
            self.dir.parent / "MapingTables" / "Unicode", # sibling MapingTables
            self.dir.parent / "Unicode",                  # parent /Unicode/
        ]
        # Honour an explicit env override for the mapping dir.
        env_map = os.environ.get("STROKE_ORDER_CNS_MAPPING_DIR")
        if env_map:
            candidate_roots.insert(0, Path(env_map).expanduser())
        for fname in (
            "CNS2UNICODE_Unicode BMP.txt",
            "CNS2UNICODE_Unicode 2.txt",
            "CNS2UNICODE_Unicode 3.txt",
            "CNS2UNICODE_Unicode 15.txt",
        ):
            for root in candidate_roots:
                p = root / fname
                if p.exists():
                    self._load_mapping(p)
                    break

    def _load_mapping(self, path: Path) -> None:
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                cns, hex_ = parts[0].strip(), parts[1].strip().lower()
                if cns and hex_:
                    self._cns_to_unicode[cns] = hex_
                    self._unicode_to_cns[hex_] = cns

    def decompose(self, char: str) -> list[str]:
        """Return the list of component characters for ``char``.

        Returns an empty list if the character isn't covered or the
        property files aren't installed. The caller is expected to treat
        this as a diagnostic / learning aid, not a render-quality
        decomposition.
        """
        if len(char) != 1:
            return []
        self._load()
        hex_ = f"{ord(char):04x}"
        cns = self._unicode_to_cns.get(hex_)
        if cns is None:
            return []
        ids = self._composition.get(cns, [])
        return [self._ref.get(i, "?") for i in ids]

    def cns_code_for(self, char: str) -> Optional[str]:
        """Reverse Unicode → CNS lookup. None if not covered."""
        if len(char) != 1:
            return None
        self._load()
        return self._unicode_to_cns.get(f"{ord(char):04x}")


__all__ = ["CNSComponents", "default_cns_properties_dir"]
