"""
Hook policy — selectively strip terminal hook reversals from stroke tracks.

Background
----------
MOE's筆順學習網 animation data contains small hook ticks at the end of
strokes like 日's second stroke (橫折鉤), 困 / 國 / 口 second strokes, etc.
These hooks show up in the live animation but are **absent** from the
static 全筆順 PNG reference (as documented on the教育部網站的使用說明 FAQ).
This is an official inconsistency.

For writing robots this matters because:

- ``animation`` (default): keep the hook → robot writes the tick at end,
  matches official animation and most mainstream downstream tools
  (bishun.18dao, zeroegg, hanzi-writer).
- ``static``: strip the hook → robot writes clean 橫折 style, matches
  the static MOE PNG and some traditional typography preferences.

Hook stripping algorithm
------------------------

For each stroke that our classifier flagged ``has_hook=True``, find the
terminal reversal inflection point and trim the track at that inflection.
The inflection is the last track point where the direction reverses
significantly vs the overall direction of the stroke.
"""
from __future__ import annotations

import math
from typing import Literal

from .ir import Character, Point, Stroke

HookPolicy = Literal["animation", "static"]


def _strip_hook(track: list[Point]) -> list[Point]:
    """
    Remove the terminal hook from a track. Returns a new list of points.

    Algorithm: walk backward from the end; drop points whose segment
    direction has been reversed >100° from the overall stroke direction.
    Stop at the first "well-aligned" point.
    """
    if len(track) < 3:
        return list(track)

    overall_dx = track[-1].x - track[0].x
    overall_dy = track[-1].y - track[0].y
    overall_len = math.hypot(overall_dx, overall_dy)
    if overall_len < 1e-6:
        return list(track)

    # walk back from end; find the last point P[i] such that the segment
    # P[i-1]→P[i] is roughly aligned with overall direction
    kept = len(track)
    for i in range(len(track) - 1, 0, -1):
        dx = track[i].x - track[i - 1].x
        dy = track[i].y - track[i - 1].y
        seg_len = math.hypot(dx, dy)
        if seg_len < 1e-6:
            continue
        # dot product (normalized) > cos(100°) ≈ -0.17 means it's still
        # generally in the overall direction. More strict cos(90°)=0.
        cos_angle = (dx * overall_dx + dy * overall_dy) / (seg_len * overall_len)
        if cos_angle > -0.17:
            kept = i + 1
            break

    if kept >= len(track):
        return list(track)
    # trimmed track retains [0..kept-1]; that's the pre-hook portion
    return list(track[:kept])


def apply_hook_policy(char: Character, policy: HookPolicy) -> Character:
    """
    Apply the hook policy in place to every stroke in `char`.

    - ``"animation"``: no-op (default; preserves MOE animation data)
    - ``"static"``: strip terminal hooks on strokes where ``has_hook=True``

    Note: the classifier must have run first for ``has_hook`` to be set.
    Both ``raw_track`` and ``smoothed_track`` (if populated) are trimmed.
    """
    if policy == "animation":
        return char
    if policy != "static":
        raise ValueError(
            f"unknown hook policy {policy!r} (expected animation/static)"
        )

    for s in char.strokes:
        if not s.has_hook:
            continue
        s.raw_track = _strip_hook(s.raw_track)
        if s.smoothed_track:
            s.smoothed_track = _strip_hook(s.smoothed_track)
        s.has_hook = False  # mark as already processed

    return char


__all__ = ["HookPolicy", "apply_hook_policy"]
