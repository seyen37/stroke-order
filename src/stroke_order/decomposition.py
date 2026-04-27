"""
Character decomposition database — parse 朱邦復's 5000 會意字 dataset into
a Python dictionary keyed by character.

The source file (``data/5000_wuqian.txt``) contains two sections:

1. Prelude (~509 entries): 242 象形 + 38 指事 + 267 會意, with fullwidth
   spaces as column separators and single-letter role markers (Ａ=體用
   shorthand).

2. Appendix ("七、附錄"): ~3,756 會意字 entries in a slightly different
   format, TAB-separated with explicit 體/用 role labels.

Both share the same logical schema:

    【字】 類別-最早字形  首[字首]角色-定義  尾[字尾]角色-定義  概念

We merge both sections into one flat lookup. Characters without explicit
decomposition (象形 / 指事) have empty head/tail but carry the earliest
form and concept.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional

from .variants import variants_of

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class Decomposition:
    """Structured 會意 decomposition of a single character."""

    char: str
    category: str = ""             # 象形 / 指事 / 會意 / 衍文 / 異體
    earliest_form: str = ""        # 甲骨 / 金文 / 小篆 / 隸書 / 楷書 / 衍文
    head_root: Optional[str] = None
    head_role: Optional[str] = None       # '體' or '用'
    head_def: str = ""
    tail_root: Optional[str] = None
    tail_role: Optional[str] = None
    tail_def: str = ""
    concept: str = ""

    @property
    def is_atom(self) -> bool:
        """True if this is an atomic pictograph / ideograph (no sub-parts)."""
        return self.head_root is None and self.tail_root is None

    def summary(self) -> str:
        if self.is_atom:
            return (f"{self.char} [{self.category or '?'}/{self.earliest_form or '?'}] "
                    f"{self.concept}")
        parts = []
        if self.head_root:
            role = f"({self.head_role})" if self.head_role else ""
            parts.append(f"首[{self.head_root}]{role}")
        if self.tail_root:
            role = f"({self.tail_role})" if self.tail_role else ""
            parts.append(f"尾[{self.tail_root}]{role}")
        head_tail = " + ".join(parts)
        return (f"{self.char} = {head_tail}  "
                f"[{self.category}/{self.earliest_form}] {self.concept}")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

# Category labels we recognize at the start of a field
_CATEGORY_WORDS = ("象形", "指事", "會意", "衍文", "異體")

# Role shorthand: Ａ/Ｂ (fullwidth) = 體, ａ/ｂ (fullwidth) = 用
_ROLE_MAP = {
    "Ａ": "體", "Ｂ": "體", "A": "體", "B": "體",
    "ａ": "用", "ｂ": "用", "a": "用", "b": "用",
    "體": "體", "用": "用",
}

# Match placeholder references like &~ANWG;
_PLACEHOLDER_RE = re.compile(r"&~[A-Z0-9]+;")

# Hyphen-like chars (halfwidth, fullwidth, dash variants).
# Order matters inside a regex char class: the ``-`` must be first or last
# so it's not interpreted as a range.
_HYPHENS = "－─—-"


def _strip_placeholders(s: str) -> str:
    """BMP references keep their tag for reference but we strip for output."""
    return _PLACEHOLDER_RE.sub("", s).strip()


def _parse_head_tail(field: str) -> tuple[Optional[str], Optional[str], str]:
    """
    Parse a 首/尾 field like:
      '首［日］Ａ太陽。'            (prelude)
      '首［水］體－液體。'           (appendix)
      '首［爪］ａ手足的指甲。'       (prelude, 用)
    Return (root_char(s), role, definition).
    """
    if not field:
        return None, None, ""

    # strip leading 首/尾 label
    s = field.lstrip("首尾").strip()

    # expect [X]; tolerate halfwidth brackets too
    m = re.match(r"[［\[]([^］\]]*)[］\]](.*)", s)
    if not m:
        return None, None, s.strip()

    root_raw = m.group(1).strip()
    after = m.group(2).strip()

    root = root_raw or None
    if root and _PLACEHOLDER_RE.search(root):
        # keep placeholder tag, caller can decide
        root = _strip_placeholders(root) or root_raw

    # role detection: first char is role indicator
    role: Optional[str] = None
    definition = after
    if after:
        first = after[0]
        if first in _ROLE_MAP:
            role = _ROLE_MAP[first]
            definition = after[1:].lstrip(_HYPHENS + " 　")
        # appendix uses "體－..." so first char is 體/用, second is hyphen
    definition = definition.rstrip("。 　")
    return root, role, definition


def _parse_category_form(field: str) -> tuple[str, str]:
    """Parse '象形－甲骨' / '＠－金文' / '會意－小篆文' → (category, earliest_form)."""
    if not field:
        return "", ""
    # normalize ＠/＃ to 會意/指事 for human-readable category
    cat_map = {"＠": "會意", "＃": "指事"}
    # split by any hyphen variant
    parts = re.split(f"[{_HYPHENS}]", field, maxsplit=1)
    if len(parts) == 2:
        cat, form = parts[0].strip(), parts[1].strip()
    else:
        cat, form = field.strip(), ""
    cat = cat_map.get(cat, cat)
    return cat, form


def _parse_line(line: str) -> Optional[Decomposition]:
    """Parse one entry line. Returns None if the line isn't an entry."""
    line = line.rstrip("\n")
    if not line or not line.startswith("【"):
        return None
    close = line.find("】")
    if close < 0:
        return None

    char_raw = line[1:close].strip()
    # BMP placeholder characters: keep as their tag (no real char)
    if _PLACEHOLDER_RE.fullmatch(char_raw):
        char = char_raw  # e.g., "&~ANWG;"
    elif len(char_raw) == 1:
        char = char_raw
    else:
        # composite chars or partial data; skip
        return None

    rest = line[close + 1:]
    # split on either (a) any run of tabs OR (b) 2+ spaces (half/fullwidth).
    # Prelude format uses multiple fullwidth spaces; appendix format uses
    # tabs (sometimes a single tab between category and concept).
    fields = [f.strip() for f in re.split(r"(?:\t+|[ 　]{2,})", rest) if f.strip()]
    if not fields:
        return None

    head_field = tail_field = category_field = concept = None
    for f in fields:
        if f.startswith("首"):
            head_field = f
        elif f.startswith("尾"):
            tail_field = f
        elif (
            f.startswith(("＠", "＃")) or
            any(f.startswith(w) for w in _CATEGORY_WORDS)
        ):
            # this is the category-form field
            if category_field is None:
                category_field = f
            elif concept is None:
                concept = f
        else:
            if concept is None:
                concept = f

    hr, hrole, hdef = _parse_head_tail(head_field) if head_field else (None, None, "")
    tr, trole, tdef = _parse_head_tail(tail_field) if tail_field else (None, None, "")
    cat, form = _parse_category_form(category_field or "")

    return Decomposition(
        char=char,
        category=cat,
        earliest_form=form,
        head_root=hr, head_role=hrole, head_def=hdef,
        tail_root=tr, tail_role=trole, tail_def=tdef,
        concept=(concept or "").rstrip("。 　"),
    )


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


class DecompositionDB:
    """Lazy-loaded lookup: char → Decomposition."""

    def __init__(self, path: Optional[Path] = None) -> None:
        if path is None:
            path = (Path(__file__).resolve().parents[2]
                    / "data" / "5000_wuqian.txt")
        self.path = Path(path)
        self._map: Optional[dict[str, Decomposition]] = None

    def _ensure(self) -> dict[str, Decomposition]:
        if self._map is not None:
            return self._map
        if not self.path.is_file():
            self._map = {}
            return self._map
        m: dict[str, Decomposition] = {}
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                entry = _parse_line(line)
                if entry is None:
                    continue
                # prefer the first occurrence (prelude tends to have richer
                # descriptions than appendix duplicates)
                if entry.char not in m:
                    m[entry.char] = entry
        self._map = m
        return m

    def get(self, char: str, *, try_variants: bool = True) -> Optional[Decomposition]:
        """
        Look up a character. If not found and ``try_variants`` is True,
        also try the traditional/simplified counterpart (e.g. 溫 ↔ 温).

        When a match is found via variant fallback, the returned
        Decomposition has its ``char`` field rewritten to the QUERIED char
        so downstream consumers see a consistent identifier.
        """
        m = self._ensure()
        hit = m.get(char)
        if hit is not None:
            return hit
        if not try_variants:
            return None
        for alt in variants_of(char):
            hit = m.get(alt)
            if hit is not None:
                # Preserve the user's queried char in the returned object;
                # this way the JSON / UI shows "溫" even though data is from "温"
                return replace(hit, char=char)
        return None

    def __contains__(self, char: str) -> bool:
        if char in self._ensure():
            return True
        return any(v in self._ensure() for v in variants_of(char))

    def __len__(self) -> int:
        return len(self._ensure())


_DEFAULT_DB: Optional[DecompositionDB] = None


def default_db() -> DecompositionDB:
    """Process-wide singleton (lazy init on first call)."""
    global _DEFAULT_DB
    if _DEFAULT_DB is None:
        _DEFAULT_DB = DecompositionDB()
    return _DEFAULT_DB


__all__ = [
    "Decomposition",
    "DecompositionDB",
    "default_db",
]
