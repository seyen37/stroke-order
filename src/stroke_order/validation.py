"""
Data validation & known-bug repair layer.

Runs after a source adapter loads a Character, BEFORE classification and
smoothing. Two responsibilities:

1. **Detect** suspicious data — stroke count mismatch vs expected, coord
   overflow outside the em square, duplicated strokes, etc.
2. **Fix** characters with *known* bugs (gsyan888's inventory of MOE
   duplicate-stroke issues). The fix is a simple deterministic recipe per
   character; we deliberately keep this as a hand-maintained table rather
   than attempt heuristic auto-repair.

References
----------
- REF_ANALYSIS_G0V.md (gsyan888 bug verification section)
- https://gsyan888.blogspot.com/2024/05/moe-stroke-bugs.html
- https://gsyan888.blogspot.com/2022/12/moe-stroke-track-bugs.html
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .ir import EM_SIZE, Character


# ---------------------------------------------------------------------------
# Known bug inventory — keyed by lowercase Unicode hex
# ---------------------------------------------------------------------------
#
# Each entry maps to a ``repair`` callable that takes a Character and
# returns a new list of strokes. We never mutate the input; caller
# decides whether to commit.

BugRepair = Callable[[Character], list]


def _drop_trailing(n: int) -> BugRepair:
    """Strategy: drop the last N strokes (the duplicated tail)."""
    def repair(c: Character):
        return list(c.strokes[:-n])
    return repair


def _take_first(n: int) -> BugRepair:
    """Strategy: keep only the first N strokes."""
    def repair(c: Character):
        return list(c.strokes[:n])
    return repair


#: Known buggy characters. Every entry has:
#:   hex_codepoint → (expected_count, repair_strategy, issue_summary)
KNOWN_BUGS: dict[str, tuple[int, BugRepair, str]] = {
    # From gsyan888 2024/05 + 2022/12 reports, verified against g0v JSON.
    "61c2": (16, _take_first(16),
             "懂: 32 筆資料 vs 應有 16 筆（整字重複）"),
    "69bb": (14, _drop_trailing(1),
             "榻: 15 筆 vs 應有 14 筆（末筆重複）"),
    "779e": (16, _drop_trailing(1),
             "瞞: 17 筆 vs 應有 16 筆（末筆重複）"),
    "6170": (15, _take_first(15),
             "慰: 18 筆 vs 應有 15 筆（心部前三筆重複）"),
    "5bd3": (12, _take_first(12),
             "寓: 13 筆 vs 應有 12 筆（第 6 筆重複）"),
    "88fd": (14, _take_first(14),
             "製: 15 筆 vs 應有 14 筆（第 13 筆重複）"),
    "554a": (10, _take_first(10),
             "啊: 11 筆 vs 應有 10 筆"),
    # 叫 has correct count but coordinate ordering issue; we cannot auto-fix,
    # only flag. Listed in FLAGGED_COORDINATE_BUGS below.
}


#: Characters where count is correct but coordinates are malformed.
#: We can only warn; repair requires swapping to another source (e.g. MMH).
FLAGGED_COORDINATE_BUGS: dict[str, str] = {
    "53eb": "叫: 第 4 筆座標錯置（順序問題，筆數正確）",
    # add more as discovered
}


# ---------------------------------------------------------------------------
# Validation result object
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixable: bool = False        # True if a known-bug repair is available
    fix_description: str = ""    # human-readable description of the fix

    def add_error(self, msg: str) -> None:
        self.is_valid = False
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def summary(self) -> str:
        parts = []
        if self.is_valid:
            parts.append("VALID")
        else:
            parts.append(f"INVALID ({len(self.errors)} errors)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warnings")
        if self.fixable:
            parts.append("auto-fixable")
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_stroke_count(char: Character) -> ValidationResult:
    """Check against KNOWN_BUGS expected-count table."""
    r = ValidationResult()
    hex_code = char.unicode_hex.lower()
    if hex_code in KNOWN_BUGS:
        expected, _, issue = KNOWN_BUGS[hex_code]
        if char.stroke_count != expected:
            r.add_error(
                f"stroke count mismatch: got {char.stroke_count}, "
                f"expected {expected} — known bug: {issue}"
            )
            r.fixable = True
            r.fix_description = issue
    if hex_code in FLAGGED_COORDINATE_BUGS:
        r.add_warning(
            f"known coordinate issue (unfixable without alt source): "
            f"{FLAGGED_COORDINATE_BUGS[hex_code]}"
        )
    return r


def validate_overflow(char: Character) -> ValidationResult:
    """Detect coordinates outside the [0, EM_SIZE] em square."""
    r = ValidationResult()
    bb = char.bbox
    if bb.x_min < 0 or bb.y_min < 0 or bb.x_max > EM_SIZE or bb.y_max > EM_SIZE:
        r.add_warning(
            f"bbox overflows em square: {bb} "
            f"(x_min={bb.x_min}, y_min={bb.y_min}, "
            f"x_max={bb.x_max}, y_max={bb.y_max}); "
            f"consider --auto-scale or enlarging render viewBox"
        )
    return r


def validate_character(char: Character) -> ValidationResult:
    """Run all validators; merge results."""
    merged = ValidationResult()
    for fn in (validate_stroke_count, validate_overflow):
        r = fn(char)
        if not r.is_valid:
            merged.is_valid = False
        merged.errors.extend(r.errors)
        merged.warnings.extend(r.warnings)
        if r.fixable and not merged.fixable:
            merged.fixable = True
            merged.fix_description = r.fix_description
    return merged


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------


def apply_known_bug_fix(char: Character) -> tuple[Character, bool]:
    """
    If `char` matches a known-bug pattern, apply the repair and return
    (fixed_char, True). Otherwise return (char, False). Always returns a
    NEW Character object when a fix is applied.
    """
    hex_code = char.unicode_hex.lower()
    if hex_code not in KNOWN_BUGS:
        return char, False

    expected, repair, issue = KNOWN_BUGS[hex_code]
    if char.stroke_count == expected:
        return char, False  # already correct (e.g. fixed upstream)

    new_strokes = repair(char)
    # re-index so the stroke.index field reflects new order
    for i, s in enumerate(new_strokes):
        s.index = i

    from dataclasses import replace
    fixed = replace(char, strokes=new_strokes,
                    validation_notes=char.validation_notes + [f"auto-fix: {issue}"])
    return fixed, True


__all__ = [
    "KNOWN_BUGS",
    "FLAGGED_COORDINATE_BUGS",
    "ValidationResult",
    "validate_stroke_count",
    "validate_overflow",
    "validate_character",
    "apply_known_bug_fix",
]
