"""Shared geometry helpers for style transforms."""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Optional

from ..ir import Character, EM_SIZE, Point, Stroke


def deepcopy_character(c: Character) -> Character:
    """Return a deep-copied Character so style filters stay pure."""
    return deepcopy(c)


def stroke_track(s: Stroke) -> list[Point]:
    """Return the preferred rendered track for a stroke (smoothed if set)."""
    return list(s.smoothed_track) if s.smoothed_track else list(s.raw_track)


def set_track(s: Stroke, pts: list[Point]) -> None:
    """Overwrite the stroke's preferred track. Also clears outline because
    the outline is no longer in sync with the track."""
    s.smoothed_track = pts
    # raw_track stays as-is; outline is now invalid for the new shape so we
    # drop it to prevent the renderer from drawing stale outline geometry.
    s.outline = []


def tangent_at_end(pts: list[Point], at_start: bool = False) -> tuple[float, float]:
    """Return the unit tangent (dx, dy) at one end of the track.

    ``at_start=False`` → tangent from second-to-last to last point (points
    AWAY from the stroke body). ``at_start=True`` → tangent from second
    point to first, also pointing AWAY from the body.
    """
    if len(pts) < 2:
        return (1.0, 0.0)
    if at_start:
        a, b = pts[1], pts[0]
    else:
        a, b = pts[-2], pts[-1]
    dx, dy = b.x - a.x, b.y - a.y
    mag = math.hypot(dx, dy) or 1.0
    return (dx / mag, dy / mag)


def perpendicular(d: tuple[float, float], rotate_ccw: bool = True) -> tuple[float, float]:
    """Rotate a 2D direction 90°. In SVG y-down coords, CCW is (-dy, dx)."""
    dx, dy = d
    return (-dy, dx) if rotate_ccw else (dy, -dx)


def add_end_serif(s: Stroke, length: float = 60.0,
                  kind: str = "perpendicular") -> None:
    """Append a short perpendicular "serif tick" at the stroke's end.

    The track gains two extra points: one offset perpendicular to the
    stroke direction, then back to the original endpoint — a visible
    little hook on the endpoint when rendered as a polyline.

    ``kind``:
        - "perpendicular"  — straight tick across the stroke direction
        - "flare_up"       — a small hook angled back (for 波磔-lite)
    """
    pts = stroke_track(s)
    if len(pts) < 2:
        return
    end = pts[-1]
    tx, ty = tangent_at_end(pts)
    # Serif direction: perpendicular to the tangent (CCW rotation).
    px, py = perpendicular((tx, ty), rotate_ccw=True)
    if kind == "flare_up":
        # blend perpendicular + slight forward motion to suggest a flare
        fx = px * 0.85 + tx * 0.3
        fy = py * 0.85 + ty * 0.3
        mag = math.hypot(fx, fy) or 1.0
        px, py = fx / mag, fy / mag
    serif_pt = Point(end.x + px * length, end.y + py * length)
    pts.append(serif_pt)
    pts.append(end)   # return to baseline so the next render step keeps origin
    set_track(s, pts)


def add_lishu_flare(s: Stroke, length: float = 120.0) -> None:
    """Add a 波磔-style upward flare at the END of a horizontal stroke.

    The flare is a longer, forward-and-upward extension — visually more
    prominent than a simple serif. Used for Lishu (隸書) filter.
    """
    pts = stroke_track(s)
    if len(pts) < 2:
        return
    end = pts[-1]
    tx, ty = tangent_at_end(pts)
    # Flare direction: mostly perpendicular upward (negative y in SVG),
    # with a small forward component to give the wave feel.
    # For a horizontal rightward stroke (tx>0, ty≈0), perpendicular CCW
    # = (0, 1) which is DOWN in SVG. We want UP (-y), so rotate CW.
    px, py = perpendicular((tx, ty), rotate_ccw=False)
    # Mix perpendicular with forward motion (70/30 split).
    fx = px * 0.7 + tx * 0.6
    fy = py * 0.7 + ty * 0.6
    mag = math.hypot(fx, fy) or 1.0
    fx, fy = fx / mag, fy / mag
    mid_pt = Point(end.x + fx * length * 0.5, end.y + fy * length * 0.5)
    flare_pt = Point(end.x + fx * length, end.y + fy * length)
    # Smooth tri-point flare — no need to return to end; the flare IS the
    # stroke's new terminal.
    pts.append(mid_pt)
    pts.append(flare_pt)
    set_track(s, pts)


def compress_vertical(s: Stroke, factor: float, pivot_y: float) -> None:
    """Scale a stroke's Y coords toward ``pivot_y`` by ``factor``.

    ``factor < 1`` compresses (makes character shorter), preserving x.
    Modifies both raw_track and smoothed_track so the stroke keeps a
    consistent shape regardless of which the renderer reads. Also
    scales the outline's coordinate fields when they exist.
    """
    def _scale_y(y: float) -> float:
        return pivot_y + (y - pivot_y) * factor

    s.raw_track = [Point(p.x, _scale_y(p.y)) for p in s.raw_track]
    if s.smoothed_track:
        s.smoothed_track = [Point(p.x, _scale_y(p.y)) for p in s.smoothed_track]
    # Scale outline command coordinates too.
    new_outline = []
    for cmd in s.outline:
        new_cmd = dict(cmd)
        if "y" in new_cmd:
            new_cmd["y"] = _scale_y(new_cmd["y"])
        for sub in ("begin", "mid", "end"):
            if sub in new_cmd:
                p = dict(new_cmd[sub])
                p["y"] = _scale_y(p["y"])
                new_cmd[sub] = p
        new_outline.append(new_cmd)
    s.outline = new_outline


def is_horizontal(kind_code: int) -> bool:
    """True for 橫 (2) and 橫點 (4) — strokes that run mostly left-to-right."""
    return kind_code in (2, 4)


def is_vertical(kind_code: int) -> bool:
    """True for 豎 (1) and 豎點 (3)."""
    return kind_code in (1, 3)
