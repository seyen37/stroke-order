"""
Export Character IR as hanzi-writer-compatible JSON.

hanzi-writer (https://hanziwriter.org) expects data in the format that
Make Me a Hanzi provides natively: Arphic font em coordinates (1024 unit,
Y pointing up, baseline at y=0, ascender ≈ y=900). Since our canonical IR
is 2048 em Y-down, we apply a simple affine transform:

    x_hw = x_ours * 0.5
    y_hw = 900 - y_ours * 0.5

Output shape::

    {
      "strokes": [ "M 237 518 Q ... Z", ... ],
      "medians": [ [[x,y], [x,y], ...], ... ]
    }

This is exactly what ``HanziWriter.create(target, char, {charDataLoader})``'s
``onComplete`` expects.
"""
from __future__ import annotations

import json
from typing import Any

from ..ir import Character, Stroke


# Convert canonical (2048 Y-down) coords back to hanzi-writer (1024 Y-up,
# Arphic ascender=900) convention.
def _to_hw(x: float, y: float) -> tuple[float, float]:
    return x * 0.5, 900.0 - y * 0.5


def _stroke_outline_hw(stroke: Stroke) -> str:
    """Rebuild the SVG path ``d`` string in hanzi-writer coord system."""
    parts: list[str] = []
    for cmd in stroke.outline:
        t = cmd.get("type", "")
        if t == "M":
            x, y = _to_hw(cmd["x"], cmd["y"])
            parts.append(f"M {x:.1f} {y:.1f}")
        elif t == "L":
            x, y = _to_hw(cmd["x"], cmd["y"])
            parts.append(f"L {x:.1f} {y:.1f}")
        elif t == "Q":
            bx, by = _to_hw(cmd["begin"]["x"], cmd["begin"]["y"])
            ex, ey = _to_hw(cmd["end"]["x"], cmd["end"]["y"])
            parts.append(f"Q {bx:.1f} {by:.1f} {ex:.1f} {ey:.1f}")
        elif t == "C":
            c1x, c1y = _to_hw(cmd["begin"]["x"], cmd["begin"]["y"])
            c2x, c2y = _to_hw(cmd["mid"]["x"],   cmd["mid"]["y"])
            ex,  ey  = _to_hw(cmd["end"]["x"],   cmd["end"]["y"])
            parts.append(f"C {c1x:.1f} {c1y:.1f} {c2x:.1f} {c2y:.1f} "
                         f"{ex:.1f} {ey:.1f}")
    parts.append("Z")
    return " ".join(parts)


def _stroke_medians_hw(stroke: Stroke) -> list[list[float]]:
    """Convert track to hanzi-writer median polyline [[x,y], [x,y], ...]."""
    # prefer smoothed track for a nicer animation if available
    pts = stroke.track
    return [[round(p[0], 1), round(p[1], 1)]
            for p in (_to_hw(q.x, q.y) for q in pts)]


def character_to_hanzi_writer_dict(char: Character) -> dict[str, Any]:
    return {
        "strokes": [_stroke_outline_hw(s) for s in char.strokes],
        "medians": [_stroke_medians_hw(s) for s in char.strokes],
    }


def character_to_hanzi_writer_json(
    char: Character, *, indent: int | None = None
) -> str:
    return json.dumps(
        character_to_hanzi_writer_dict(char),
        ensure_ascii=False,
        indent=indent,
    )


__all__ = [
    "character_to_hanzi_writer_dict",
    "character_to_hanzi_writer_json",
]
