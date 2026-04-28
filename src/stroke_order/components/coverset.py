"""
Cover-set loader.

A "cover-set" is a curated character list designed to maximize coverage of
common-character component space. By writing the cover-set, a user
implicitly produces enough component-level handwriting samples to compose
many more characters not in the set.

Built-in cover-sets:

- ``cjk_common_808`` — 中日韓共同常用 808 漢字 (TCS 2014). Empirically
  covers 96.1% of 3,500 most common chars. See
  ``docs/decisions/2026-04-27_808_analysis.md``.
- ``educational_4808`` — 教育部常用國字標準字體表 (4,808 字). Taiwan's
  official 常用 character standard. Most comprehensive practical target
  for a personal Chinese-traditional font. Source: Gist by @p208p2002.
- ``wuqian_5000`` — 朱邦復 漢字基因 5000 會意字 (~3,716 字 after CJK filter).
  Deeper Chinese-only set with explicit 會意 decomposition baked in.
  See ``data/5000_wuqian.txt`` and ``decomposition.py``.

Future built-ins:

- ``minimum_cover`` — algorithm-generated greedy minimum cover

Custom cover-sets can be loaded via :func:`load_coverset_from_path`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoverSet:
    """A named character set + metadata.

    Attributes:
        name: Stable identifier (e.g. "cjk_common_808").
        title: Human-readable title.
        description: One-line description.
        chars: Tuple of trad-form characters in publication order.
        chars_simp: Tuple of simp-form characters (parallel to ``chars``).
        source: Provenance (e.g. organization, publication).
        url: Optional reference URL.
        metadata: Free-form additional fields.
    """

    name: str
    title: str
    description: str
    chars: tuple[str, ...]
    chars_simp: tuple[str, ...]
    source: str = ""
    url: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.chars)


# ---------------------------------------------------------------------------
# Built-in registry
# ---------------------------------------------------------------------------

_BUILTIN_NAMES: tuple[str, ...] = (
    "cjk_common_808",
    "educational_4808",
    "wuqian_5000",
)


def _builtin_path(name: str) -> Path:
    """Resolve the bundled JSON path for a built-in cover-set."""
    files = resources.files("stroke_order.components") / "coversets" / f"{name}.json"
    return Path(str(files))


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_coverset_from_path(path: Path) -> CoverSet:
    """Load a cover-set from a JSON file.

    Expected JSON schema (matches ``data/cjk_common_808.json``)::

        {
          "title": "...",
          "english_title": "...",       (optional)
          "source": "...",              (optional)
          "url": "...",                 (optional)
          "description": "...",         (optional)
          "entries": [
            {"index": 1, "simp": "一", "trad": "一", "same": true},
            ...
          ]
        }
    """
    data = json.loads(path.read_text(encoding="utf-8"))

    name = path.stem
    title = data.get("title", name)
    description = data.get("description", data.get("english_title", ""))
    source = data.get("source", "")
    url = data.get("url", "")

    entries = data.get("entries", [])
    chars = tuple(e["trad"] for e in entries)
    chars_simp = tuple(e["simp"] for e in entries)

    metadata = {
        k: v for k, v in data.items()
        if k not in {"title", "description", "source", "url", "entries"}
    }

    return CoverSet(
        name=name,
        title=title,
        description=description,
        chars=chars,
        chars_simp=chars_simp,
        source=source,
        url=url,
        metadata=metadata,
    )


def load_coverset(name: str) -> CoverSet:
    """Load a built-in cover-set by name.

    Args:
        name: One of :func:`list_coversets`.

    Raises:
        KeyError: if ``name`` is not a built-in.
        FileNotFoundError: if the bundled file is missing (package install issue).
    """
    if name not in _BUILTIN_NAMES:
        raise KeyError(
            f"Unknown built-in cover-set {name!r}. "
            f"Available: {list(_BUILTIN_NAMES)}"
        )
    return load_coverset_from_path(_builtin_path(name))


def list_coversets() -> list[dict]:
    """List metadata for all built-in cover-sets.

    Returns:
        List of dicts with name, title, size, description, source, url.
        Cheap — does not parse char lists.
    """
    out = []
    for name in _BUILTIN_NAMES:
        cs = load_coverset(name)
        out.append({
            "name": cs.name,
            "title": cs.title,
            "description": cs.description,
            "size": cs.size,
            "source": cs.source,
            "url": cs.url,
        })
    return out
