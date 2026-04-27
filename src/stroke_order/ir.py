"""
Intermediate Representation (IR) for Chinese character stroke data.

The IR is **source-agnostic**: g0v JSON, Make Me a Hanzi, and any future
data source all flow through these dataclasses. Internal coordinate
system is fixed to 2048×2048 em square (following MOE / g0v convention),
Y-axis pointing down. Source adapters must normalize into this frame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, TYPE_CHECKING


# ---------------------------------------------------------------------------
# Canonical coordinate frame
# ---------------------------------------------------------------------------

#: Internal em-square dimension. g0v uses 2048, MMH uses 1024 (adapters scale).
EM_SIZE: int = 2048


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Point:
    """A 2-D coordinate in the canonical frame (0..EM_SIZE, Y-down)."""
    x: float
    y: float

    def __iter__(self):  # lets tuple(p) work, nice for numpy
        yield self.x
        yield self.y


@dataclass(frozen=True, slots=True)
class BBox:
    """Axis-aligned bounding box."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def overflows_em(self) -> bool:
        """True if any coordinate is outside the [0, EM_SIZE] em square."""
        return (
            self.x_min < 0 or self.y_min < 0
            or self.x_max > EM_SIZE or self.y_max > EM_SIZE
        )

    @classmethod
    def from_points(cls, points: list[Point]) -> "BBox":
        if not points:
            raise ValueError("cannot compute bbox of empty point list")
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        return cls(min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------------------
# Stroke classification
# ---------------------------------------------------------------------------

# 1-8 classification scheme derived from 恩字 1527823644 reference (see
# REF_ANALYSIS_G0V.md §四). 0 and 9 reserved for future use.
STROKE_KIND_NAMES: dict[int, str] = {
    0: "未分類",
    1: "豎",
    2: "橫",
    3: "豎點",
    4: "橫點",
    5: "順彎",  # 橫折 / clockwise turn
    6: "逆彎",  # 臥鉤 / counter-clockwise hook
    7: "撇",
    8: "捺",
    9: "其他",
}

KindCode = int  # ∈ {0..9}


# ---------------------------------------------------------------------------
# Stroke outline command (from g0v outline field)
# ---------------------------------------------------------------------------


OutlineCommand = dict[str, Any]  # keeps raw g0v outline structure for now
# Shape examples:
#   {"type": "M", "x": 267, "y": 1032}
#   {"type": "L", "x": 308, "y": 1029}
#   {"type": "Q", "begin": {"x":314, "y":1029}, "end": {"x":349, "y":1025}}


# ---------------------------------------------------------------------------
# Core IR objects
# ---------------------------------------------------------------------------


@dataclass
class Stroke:
    """One stroke of a character, with both outline and track representations."""

    index: int                         # 0-based position in stroke order
    raw_track: list[Point]             # original track points (sparse, 2-7 pts)
    outline: list[OutlineCommand]      # raw outline path commands (from source)

    # populated by classifier.py
    kind_code: KindCode = 0
    kind_name: str = "未分類"
    has_hook: bool = False

    # populated by smoothing.py (optional; empty means "use raw_track")
    smoothed_track: list[Point] = field(default_factory=list)

    # optional: some g0v strokes include a "size" field (pen width)
    pen_size: Optional[float] = None

    @property
    def bbox(self) -> BBox:
        points: list[Point] = list(self.raw_track)
        # also include outline extrema for accurate overshoot detection
        for cmd in self.outline:
            if "x" in cmd and "y" in cmd:
                points.append(Point(cmd["x"], cmd["y"]))
            for sub in ("begin", "mid", "end"):
                if sub in cmd:
                    points.append(Point(cmd[sub]["x"], cmd[sub]["y"]))
        return BBox.from_points(points)

    @property
    def track(self) -> list[Point]:
        """Preferred track: smoothed if available, else raw."""
        return self.smoothed_track if self.smoothed_track else self.raw_track


@dataclass
class Character:
    """A Chinese character with its complete stroke data."""

    char: str                          # the character itself, e.g. "永"
    unicode_hex: str                   # e.g. "6c38" (lowercase, no prefix)
    strokes: list[Stroke] = field(default_factory=list)

    # metadata (optional; filled by respective layers)
    moe_id: Optional[str] = None             # e.g. "A00001"
    decomposition: Optional[Any] = None      # Decomposition instance (Phase 3)
    radical_category: Optional[str] = None   # 本存/人造/規範/應用 (Phase 4)
    data_source: str = "unknown"             # e.g. "g0v", "mmh"
    validation_notes: list[str] = field(default_factory=list)

    @property
    def stroke_count(self) -> int:
        return len(self.strokes)

    @property
    def signature(self) -> str:
        """10-character signature per user's example: 恩 → '1527823644'.

        Each digit is the kind_code (0-9) of each stroke in order.
        If stroke count > 10, produces longer string; if < 10, shorter.
        """
        return "".join(str(s.kind_code) for s in self.strokes)

    @property
    def bbox(self) -> BBox:
        """Union of all stroke bboxes."""
        if not self.strokes:
            return BBox(0, 0, 0, 0)
        boxes = [s.bbox for s in self.strokes]
        return BBox(
            min(b.x_min for b in boxes),
            min(b.y_min for b in boxes),
            max(b.x_max for b in boxes),
            max(b.y_max for b in boxes),
        )

    @property
    def has_overflow(self) -> bool:
        return self.bbox.overflows_em

    def summary(self) -> str:
        """Compact debug representation."""
        return (
            f"<Character {self.char!r} U+{self.unicode_hex.upper()} "
            f"{self.stroke_count} strokes sig={self.signature!r} "
            f"source={self.data_source}>"
        )


__all__ = [
    "EM_SIZE",
    "Point",
    "BBox",
    "STROKE_KIND_NAMES",
    "KindCode",
    "OutlineCommand",
    "Stroke",
    "Character",
]
