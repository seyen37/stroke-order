"""
G-code exporter for pen plotters / writing robots.

Defaults target AxiDraw-style machines but every parameter is configurable:

- Unit:              mm (G21)
- Positioning:       absolute (G90)
- Pen up:            ``M5``             (spindle off)
- Pen down:          ``M3 S90``         (spindle on, S = servo angle)
- Rapid move:        ``G0``
- Controlled move:   ``G1``
- Default feed rate: 3000 mm/min

The canonical IR is 2048 em square with Y pointing DOWN. G-code coordinate
systems typically have Y pointing UP, so we flip Y by default. Each stroke
becomes: (pen-up travel) → (pen down) → (controlled polyline) → (pen up).
"""
from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

from ..ir import EM_SIZE, Character, Point


@dataclass
class GCodeOptions:
    """Tunables for G-code emission. Sensible defaults for AxiDraw-like pens."""

    #: Logical character size in the output X dimension (mm).
    char_size_mm: float = 20.0

    #: Origin offset in mm. First character is placed here; subsequent
    #: characters offset by char_size_mm + char_spacing_mm to the right.
    origin_x_mm: float = 10.0
    origin_y_mm: float = 10.0

    #: Horizontal gap between successive characters (mm).
    char_spacing_mm: float = 5.0

    #: Feed rate (mm/min) for controlled G1 moves (pen down).
    feed_rate: int = 3000

    #: Rapid travel rate (mm/min) for pen-up G0 moves. 0 = no explicit F.
    travel_rate: int = 6000

    #: Commands for pen up / down. Override for non-AxiDraw machines.
    pen_up_cmd: str = "M5"
    pen_down_cmd: str = "M3 S90"

    #: Dwell (seconds) after pen down / before pen up to let servo settle.
    pen_dwell_sec: float = 0.15

    #: Flip Y axis (IR is Y-down; most plotters are Y-up).
    flip_y: bool = True

    #: If True, prepend a standard prologue (G21, G90, home, raise pen).
    include_prologue: bool = True

    #: If True, append a standard epilogue (raise pen, return to origin).
    include_epilogue: bool = True

    #: If True, include human-readable comments (;) for each stroke.
    include_comments: bool = True


def _transform_point(p: Point, scale: float, x0: float, y0: float,
                     flip_y: bool) -> tuple[float, float]:
    """Map IR point (0..EM_SIZE) to machine mm coords with origin shift."""
    x_mm = x0 + p.x * scale
    y_ir = (EM_SIZE - p.y) if flip_y else p.y
    y_mm = y0 + y_ir * scale
    return x_mm, y_mm


def _emit_dwell(buf: StringIO, seconds: float) -> None:
    if seconds > 0:
        # P = milliseconds in most firmwares
        buf.write(f"G4 P{int(seconds * 1000)}\n")


def characters_to_gcode(
    chars: list[Character],
    opts: GCodeOptions | None = None,
) -> str:
    """
    Emit G-code for one or more characters laid out left-to-right.
    Returns a single G-code string.
    """
    o = opts or GCodeOptions()
    scale = o.char_size_mm / EM_SIZE  # mm per em-unit
    buf = StringIO()

    if o.include_prologue:
        buf.write("; --- stroke-order G-code ---\n")
        buf.write(f"; characters: {''.join(c.char for c in chars)}\n")
        buf.write(f"; char_size: {o.char_size_mm} mm, feed: {o.feed_rate} mm/min\n")
        buf.write("G21 ; mm\n")
        buf.write("G90 ; absolute\n")
        buf.write(f"{o.pen_up_cmd} ; pen up (start)\n")
        _emit_dwell(buf, o.pen_dwell_sec)
        buf.write(f"G0 X{o.origin_x_mm:.3f} Y{o.origin_y_mm:.3f}"
                  + (f" F{o.travel_rate}" if o.travel_rate else "")
                  + " ; home\n")

    # Per-character offsets
    x_cursor = o.origin_x_mm
    for ci, ch in enumerate(chars):
        if o.include_comments:
            buf.write(f"\n; --- character {ci+1}: {ch.char} "
                      f"(U+{ch.unicode_hex.upper()}, "
                      f"{ch.stroke_count} strokes) ---\n")
        for s in ch.strokes:
            pts = s.track
            if not pts:
                continue
            if o.include_comments:
                buf.write(f"; stroke {s.index + 1}: "
                          f"kind={s.kind_code}({s.kind_name}) "
                          f"hook={s.has_hook}\n")
            # pen-up travel to stroke start
            x, y = _transform_point(pts[0], scale, x_cursor, o.origin_y_mm, o.flip_y)
            buf.write(f"G0 X{x:.3f} Y{y:.3f}"
                      + (f" F{o.travel_rate}" if o.travel_rate else "")
                      + "\n")
            # pen down + dwell
            buf.write(f"{o.pen_down_cmd}\n")
            _emit_dwell(buf, o.pen_dwell_sec)
            # draw rest
            for p in pts[1:]:
                x, y = _transform_point(p, scale, x_cursor, o.origin_y_mm, o.flip_y)
                buf.write(f"G1 X{x:.3f} Y{y:.3f} F{o.feed_rate}\n")
            # pen up
            _emit_dwell(buf, o.pen_dwell_sec)
            buf.write(f"{o.pen_up_cmd}\n")
        # advance cursor for next character
        x_cursor += o.char_size_mm + o.char_spacing_mm

    if o.include_epilogue:
        buf.write("\n; --- epilogue ---\n")
        buf.write(f"{o.pen_up_cmd} ; ensure pen up\n")
        buf.write(f"G0 X{o.origin_x_mm:.3f} Y{o.origin_y_mm:.3f}"
                  + (f" F{o.travel_rate}" if o.travel_rate else "")
                  + " ; return home\n")
        buf.write("; done\n")

    return buf.getvalue()


def character_to_gcode(char: Character, opts: GCodeOptions | None = None) -> str:
    return characters_to_gcode([char], opts)


def save_gcode(chars, path: str, opts: GCodeOptions | None = None) -> None:
    """Write G-code for `chars` (single char or list) to `path`."""
    if isinstance(chars, Character):
        chars = [chars]
    gcode = characters_to_gcode(chars, opts)
    with open(path, "w", encoding="utf-8") as f:
        f.write(gcode)


__all__ = [
    "GCodeOptions",
    "character_to_gcode",
    "characters_to_gcode",
    "save_gcode",
]
