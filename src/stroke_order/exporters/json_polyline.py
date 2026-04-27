"""
JSON polyline exporter — the "lowest common denominator" format for custom
writing robots, Arduino-class microcontrollers, or any consumer that
doesn't want to parse SVG or G-code.

Output shape (pretty-printed):

    {
      "character": "永",
      "unicode": "U+6C38",
      "em_size": 2048,
      "stroke_count": 5,
      "signature": "45578",
      "source": "g0v",
      "bbox": [x_min, y_min, x_max, y_max],
      "strokes": [
        {
          "index": 0,
          "kind_code": 4,
          "kind_name": "橫點",
          "has_hook": false,
          "track": [[x, y], [x, y], ...],
          "outline_svg": "M … Z"
        },
        ...
      ]
    }

All coordinates are in the canonical 2048 em-square frame with Y pointing
DOWN. Consumers can apply their own scaling/flip as needed.
"""
from __future__ import annotations

import json
from typing import Any

from ..ir import EM_SIZE, Character, Stroke
from .svg import _outline_path_d


def _stroke_dict(stroke: Stroke, use_smoothed: bool = True) -> dict[str, Any]:
    pts = stroke.track if use_smoothed and stroke.smoothed_track else stroke.raw_track
    return {
        "index": stroke.index,
        "kind_code": stroke.kind_code,
        "kind_name": stroke.kind_name,
        "has_hook": stroke.has_hook,
        "pen_size": stroke.pen_size,
        "track": [[round(p.x, 3), round(p.y, 3)] for p in pts],
        "outline_svg": _outline_path_d(stroke),
    }


def character_to_dict(char: Character, use_smoothed: bool = True) -> dict[str, Any]:
    """Plain Python dict representation of a Character — easy to json.dump()."""
    bb = char.bbox
    out = {
        "character": char.char,
        "unicode": f"U+{char.unicode_hex.upper()}",
        "em_size": EM_SIZE,
        "stroke_count": char.stroke_count,
        "signature": char.signature,
        "source": char.data_source,
        "bbox": [round(bb.x_min, 3), round(bb.y_min, 3),
                 round(bb.x_max, 3), round(bb.y_max, 3)],
        "validation_notes": list(char.validation_notes),
        "strokes": [_stroke_dict(s, use_smoothed) for s in char.strokes],
    }
    # Attach 朱邦復 decomposition info if present (Phase 3)
    if char.decomposition is not None:
        d = char.decomposition
        out["decomposition"] = {
            "category": d.category,
            "earliest_form": d.earliest_form,
            "head_root": d.head_root,
            "head_role": d.head_role,
            "head_def": d.head_def,
            "tail_root": d.tail_root,
            "tail_role": d.tail_role,
            "tail_def": d.tail_def,
            "concept": d.concept,
            "is_atom": d.is_atom,
        }
    # Radical classification (Phase 4 — 朱邦復 2018 四大類)
    if char.radical_category is not None:
        out["radical_category"] = char.radical_category
    return out


def character_to_json(
    char: Character,
    *,
    indent: int | None = 2,
    use_smoothed: bool = True,
) -> str:
    return json.dumps(
        character_to_dict(char, use_smoothed),
        ensure_ascii=False,
        indent=indent,
    )


def characters_to_json(
    chars: list[Character],
    *,
    indent: int | None = 2,
    use_smoothed: bool = True,
) -> str:
    return json.dumps(
        [character_to_dict(c, use_smoothed) for c in chars],
        ensure_ascii=False,
        indent=indent,
    )


def save_json(chars, path: str, *, indent: int | None = 2,
              use_smoothed: bool = True) -> None:
    if isinstance(chars, Character):
        payload = character_to_json(chars, indent=indent, use_smoothed=use_smoothed)
    else:
        payload = characters_to_json(list(chars), indent=indent,
                                     use_smoothed=use_smoothed)
    with open(path, "w", encoding="utf-8") as f:
        f.write(payload)


__all__ = [
    "character_to_dict",
    "character_to_json",
    "characters_to_json",
    "save_json",
]
