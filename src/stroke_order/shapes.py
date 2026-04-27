"""
Geometric shape primitives for wordart (文字雲) mode.

Each shape provides:
- ``point_at(t)`` where t ∈ [0, 1] returns a point on the boundary
- ``tangent_at(t)`` returns the angle (degrees, SVG convention) of the
  tangent at that point (used to orient characters)
- ``contains(x, y)`` — point-in-shape test (for fill scanline)
- ``perimeter()`` — total boundary length in mm
- ``bbox()`` — axis-aligned bounding box
- ``edges()`` — for polygons only: list of (start, end, length)
- ``scanline(y)`` — returns list of (x_left, x_right) horizontal intervals
  inside the shape at row y (for fill mode)

All coordinates are **mm**. SVG angles increase clockwise from the +X axis.

Our SVG convention
------------------

0° = 3 o'clock, 90° = 6 o'clock, 180° = 9 o'clock, 270° = 12 o'clock.
These match CSS/SVG ``rotate(angle)`` semantics directly.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol


class Shape(Protocol):
    def point_at(self, t: float) -> tuple[float, float]: ...
    def tangent_at(self, t: float) -> float: ...  # SVG-convention degrees
    def contains(self, x: float, y: float) -> bool: ...
    def perimeter(self) -> float: ...
    def bbox(self) -> tuple[float, float, float, float]: ...  # (xmin,ymin,xmax,ymax)
    def scanline(self, y: float) -> list[tuple[float, float]]: ...
    def svg_path_d(self) -> str: ...


# ---------------------------------------------------------------------------
# Circle
# ---------------------------------------------------------------------------


@dataclass
class Circle:
    cx_mm: float
    cy_mm: float
    radius_mm: float

    def point_at(self, t: float) -> tuple[float, float]:
        """t=0 at 12 o'clock, increasing clockwise."""
        theta = (270 + 360 * t) % 360  # SVG angle of the point
        rad = math.radians(theta)
        return (self.cx_mm + self.radius_mm * math.cos(rad),
                self.cy_mm + self.radius_mm * math.sin(rad))

    def tangent_at(self, t: float) -> float:
        """Angle (deg) of outward-radial direction from center.

        Characters with 'bottom toward center' orientation rotate by this
        angle + 90° to align their 'up' with the outward radial."""
        theta = (270 + 360 * t) % 360
        return theta  # outward radial is along this direction

    def contains(self, x: float, y: float) -> bool:
        dx, dy = x - self.cx_mm, y - self.cy_mm
        return dx * dx + dy * dy <= self.radius_mm * self.radius_mm

    def perimeter(self) -> float:
        return 2 * math.pi * self.radius_mm

    def bbox(self) -> tuple[float, float, float, float]:
        r = self.radius_mm
        return (self.cx_mm - r, self.cy_mm - r,
                self.cx_mm + r, self.cy_mm + r)

    def scanline(self, y: float) -> list[tuple[float, float]]:
        dy = y - self.cy_mm
        if abs(dy) > self.radius_mm:
            return []
        half = math.sqrt(self.radius_mm * self.radius_mm - dy * dy)
        return [(self.cx_mm - half, self.cx_mm + half)]

    def svg_path_d(self) -> str:
        cx, cy, r = self.cx_mm, self.cy_mm, self.radius_mm
        # Two arc sweeps to close a circle as a path
        return (f"M {cx - r} {cy} "
                f"A {r} {r} 0 1 0 {cx + r} {cy} "
                f"A {r} {r} 0 1 0 {cx - r} {cy} Z")


# ---------------------------------------------------------------------------
# Ellipse
# ---------------------------------------------------------------------------


@dataclass
class Ellipse:
    cx_mm: float
    cy_mm: float
    rx_mm: float
    ry_mm: float

    def point_at(self, t: float) -> tuple[float, float]:
        theta = (270 + 360 * t) % 360
        rad = math.radians(theta)
        return (self.cx_mm + self.rx_mm * math.cos(rad),
                self.cy_mm + self.ry_mm * math.sin(rad))

    def tangent_at(self, t: float) -> float:
        """Outward-normal angle (not exactly radial for ellipse, but close
        enough for typography — characters face roughly away from center)."""
        # Parametric angle
        theta_deg = (270 + 360 * t) % 360
        theta = math.radians(theta_deg)
        # Gradient of implicit ellipse at (rx·cos, ry·sin) is (cos/rx, sin/ry)
        # in ellipse-normalised space; in real coords the outward normal is
        # (cos θ / rx, sin θ / ry) renormalised.
        nx = math.cos(theta) / self.rx_mm
        ny = math.sin(theta) / self.ry_mm
        mag = math.hypot(nx, ny) or 1.0
        nx /= mag; ny /= mag
        return math.degrees(math.atan2(ny, nx)) % 360

    def contains(self, x: float, y: float) -> bool:
        dx = (x - self.cx_mm) / self.rx_mm
        dy = (y - self.cy_mm) / self.ry_mm
        return dx * dx + dy * dy <= 1.0

    def perimeter(self) -> float:
        # Ramanujan's approximation
        a, b = self.rx_mm, self.ry_mm
        h = ((a - b) / (a + b)) ** 2 if (a + b) else 0
        return math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))

    def bbox(self) -> tuple[float, float, float, float]:
        return (self.cx_mm - self.rx_mm, self.cy_mm - self.ry_mm,
                self.cx_mm + self.rx_mm, self.cy_mm + self.ry_mm)

    def scanline(self, y: float) -> list[tuple[float, float]]:
        dy = y - self.cy_mm
        if abs(dy) > self.ry_mm:
            return []
        half = self.rx_mm * math.sqrt(max(0.0, 1 - (dy / self.ry_mm) ** 2))
        return [(self.cx_mm - half, self.cx_mm + half)]

    def svg_path_d(self) -> str:
        cx, cy, rx, ry = self.cx_mm, self.cy_mm, self.rx_mm, self.ry_mm
        return (f"M {cx - rx} {cy} "
                f"A {rx} {ry} 0 1 0 {cx + rx} {cy} "
                f"A {rx} {ry} 0 1 0 {cx - rx} {cy} Z")


# ---------------------------------------------------------------------------
# Regular polygon
# ---------------------------------------------------------------------------


@dataclass
class Polygon:
    """Convex polygon defined by a list of (x, y) vertices in order.

    For regular polygons use the :meth:`regular` factory.
    """
    vertices: list[tuple[float, float]]

    @classmethod
    def regular(cls, cx_mm: float, cy_mm: float, radius_mm: float,
                sides: int, rotation_deg: float = 270.0) -> "Polygon":
        """Inscribed regular polygon. rotation_deg=270 places vertex at 12 o'clock."""
        if sides < 3:
            raise ValueError(f"polygon needs >=3 sides, got {sides}")
        verts: list[tuple[float, float]] = []
        for i in range(sides):
            theta = math.radians(rotation_deg + 360 * i / sides)
            verts.append((cx_mm + radius_mm * math.cos(theta),
                          cy_mm + radius_mm * math.sin(theta)))
        return cls(verts)

    # ---------- Phase 5ah: new geometric-figure factories ----------------

    @classmethod
    def star(cls, cx_mm: float, cy_mm: float, radius_mm: float,
             points: int = 5, inner_ratio: float = 0.382,
             rotation_deg: float = 270.0) -> "Polygon":
        """N-pointed star. 2N vertices alternating outer and inner radius.

        ``inner_ratio`` = inner_radius / outer_radius. Default 0.382 ≈ the
        "golden-ratio" style five-point star; drop to ~0.5 for a chunkier
        look.
        """
        if points < 3:
            raise ValueError(f"star needs >=3 points, got {points}")
        inner_ratio = max(0.05, min(0.95, float(inner_ratio)))
        inner_r = radius_mm * inner_ratio
        n = 2 * points
        verts: list[tuple[float, float]] = []
        for i in range(n):
            r = radius_mm if i % 2 == 0 else inner_r
            theta = math.radians(rotation_deg + 360 * i / n)
            verts.append((cx_mm + r * math.cos(theta),
                          cy_mm + r * math.sin(theta)))
        return cls(verts)

    @classmethod
    def heart(cls, cx_mm: float, cy_mm: float, size_mm: float,
              segments: int = 72) -> "Polygon":
        """Classic parametric heart scaled into a ``size_mm`` bounding box.

        The parametric equations are:

            x(t) = 16 · sin³(t)
            y(t) = 13·cos(t) − 5·cos(2t) − 2·cos(3t) − cos(4t)

        sampled at ``segments`` points around the full curve. We negate y
        so the cleft sits on TOP (normal SVG y-down orientation).
        """
        if segments < 12:
            raise ValueError(f"heart needs >=12 segments, got {segments}")
        raw: list[tuple[float, float]] = []
        for i in range(segments):
            t = 2 * math.pi * i / segments
            x = 16 * math.sin(t) ** 3
            y = -(13 * math.cos(t) - 5 * math.cos(2 * t)
                  - 2 * math.cos(3 * t) - math.cos(4 * t))
            raw.append((x, y))
        # Scale + centre to fit size_mm × size_mm bbox
        xs = [p[0] for p in raw]
        ys = [p[1] for p in raw]
        raw_w = max(xs) - min(xs) or 1e-6
        raw_h = max(ys) - min(ys) or 1e-6
        scale = size_mm / max(raw_w, raw_h)
        mid_x = (max(xs) + min(xs)) / 2
        mid_y = (max(ys) + min(ys)) / 2
        verts = [(cx_mm + (x - mid_x) * scale,
                  cy_mm + (y - mid_y) * scale) for x, y in raw]
        return cls(verts)

    @classmethod
    def rounded_rect(cls, cx_mm: float, cy_mm: float,
                     width_mm: float, height_mm: float,
                     corner_radius_mm: float | None = None,
                     corner_segments: int = 8) -> "Polygon":
        """Rectangle with quarter-circle rounded corners, approximated by
        ``4 × (corner_segments + 1)`` vertices.

        If ``corner_radius_mm`` is None, defaults to 20% of min(width,height).
        """
        if width_mm <= 0 or height_mm <= 0:
            raise ValueError("rounded_rect needs positive width/height")
        if corner_segments < 2:
            raise ValueError("corner_segments must be >= 2")
        if corner_radius_mm is None:
            corner_radius_mm = min(width_mm, height_mm) * 0.2
        r = max(0.0, min(float(corner_radius_mm),
                         width_mm / 2.0, height_mm / 2.0))
        hw, hh = width_mm / 2, height_mm / 2
        # Corner centres + sweep ranges (SVG angles, y-down)
        # Walk CLOCKWISE: top-right → bottom-right → bottom-left → top-left.
        corners = [
            (cx_mm + hw - r, cy_mm - hh + r, 270.0, 360.0),  # TR: 270→360 (arc upward-right)
            (cx_mm + hw - r, cy_mm + hh - r,   0.0,  90.0),  # BR: 0→90
            (cx_mm - hw + r, cy_mm + hh - r,  90.0, 180.0),  # BL
            (cx_mm - hw + r, cy_mm - hh + r, 180.0, 270.0),  # TL
        ]
        verts: list[tuple[float, float]] = []
        for ccx, ccy, a0, a1 in corners:
            for i in range(corner_segments + 1):
                t = i / corner_segments
                theta = math.radians(a0 + (a1 - a0) * t)
                verts.append((ccx + r * math.cos(theta),
                              ccy + r * math.sin(theta)))
        return cls(verts)

    @classmethod
    def trapezoid(cls, cx_mm: float, cy_mm: float,
                  width_mm: float, height_mm: float,
                  top_ratio: float = 0.6) -> "Polygon":
        """Isoceles trapezoid with horizontal top/bottom sides.

        ``top_ratio`` = top_width / bottom_width. Default 0.6 = narrower
        top (the typical trapezoid look). ``top_ratio > 1`` inverts it
        (narrower bottom, wider top).
        """
        if width_mm <= 0 or height_mm <= 0:
            raise ValueError("trapezoid needs positive width/height")
        top_ratio = max(0.1, float(top_ratio))
        hw = width_mm / 2.0
        hh = height_mm / 2.0
        top_half = hw * top_ratio
        # CW starting top-left (matches rounded_rect orientation)
        verts = [
            (cx_mm - top_half, cy_mm - hh),   # top-left
            (cx_mm + top_half, cy_mm - hh),   # top-right
            (cx_mm + hw,       cy_mm + hh),   # bottom-right
            (cx_mm - hw,       cy_mm + hh),   # bottom-left
        ]
        return cls(verts)

    @classmethod
    def cone(cls, cx_mm: float, cy_mm: float,
             width_mm: float, height_mm: float,
             taper: float = 0.5,
             invert: bool = False) -> "Polygon":
        """Phase 5as: vertically-symmetric tapering shape (funnel-like).

        Distinct from ``trapezoid`` (which inherits the asymmetry knob
        ``top_ratio``) — ``cone`` is always **isoceles** about the
        vertical centreline, with both top and bottom flat.

        - ``taper`` ∈ (0.05, 1.0) — narrow_width / wide_width.
            ``1.0`` ≈ rectangle, ``0.05`` ≈ a sliver.
        - ``invert`` — when False (default) the wide side is at the
            **top** (resembles a 漏斗/funnel; chars cluster top-heavy);
            when True, wide side is at the **bottom** (looks like a
            classic ice-cream cone outline).

        Why a separate factory rather than a trapezoid alias: this is
        easier to reason about for end users (one knob, one orientation
        flag) and saves them remembering that ``top_ratio < 1`` means
        the trapezoid is wider at the bottom.
        """
        if width_mm <= 0 or height_mm <= 0:
            raise ValueError("cone needs positive width/height")
        taper = max(0.05, min(1.0, float(taper)))
        hw = width_mm / 2.0
        hh = height_mm / 2.0
        narrow_half = hw * taper
        if invert:
            top_half, bot_half = narrow_half, hw
        else:
            top_half, bot_half = hw, narrow_half
        verts = [
            (cx_mm - top_half, cy_mm - hh),   # top-left
            (cx_mm + top_half, cy_mm - hh),   # top-right
            (cx_mm + bot_half, cy_mm + hh),   # bottom-right
            (cx_mm - bot_half, cy_mm + hh),   # bottom-left
        ]
        return cls(verts)

    @classmethod
    def capsule(cls, cx_mm: float, cy_mm: float,
                width_mm: float, height_mm: float,
                orientation: str = "horizontal",
                arc_segments: int = 16) -> "Polygon":
        """Phase 5as: pill / lozenge / 膠囊 shape.

        Two **full** semicircles joined by two parallel straight sides.
        Distinct from ``rounded`` rect (whose corners are quarter
        circles with a configurable radius) — capsule's short axis is
        ALWAYS a full half-circle.

        - ``orientation``:
            ``"horizontal"`` — long axis runs left-to-right; semicircles
            cap the short (vertical) edges.
            ``"vertical"``   — long axis runs top-to-bottom; semicircles
            cap top and bottom.
        - ``arc_segments`` — points per semicircle (default 16 → 32
            total + 2 line segments). Higher = smoother but heavier
            polygons.
        """
        if width_mm <= 0 or height_mm <= 0:
            raise ValueError("capsule needs positive width/height")
        if arc_segments < 4:
            raise ValueError("arc_segments must be >= 4 for a smooth arc")
        if orientation not in ("horizontal", "vertical"):
            raise ValueError(
                f"orientation must be 'horizontal' or 'vertical', "
                f"got {orientation!r}"
            )
        hw = width_mm / 2.0
        hh = height_mm / 2.0
        verts: list[tuple[float, float]] = []
        if orientation == "horizontal":
            # Radius of end-caps = half the short side.
            r = min(hh, hw)
            cy_top = cy_mm
            # Left cap: semicircle from top (90°) to bottom (270°), CW.
            cx_left = cx_mm - hw + r
            cx_right = cx_mm + hw - r
            # Right cap: from top of right cap (90°) sweep clockwise (90→-90)
            for i in range(arc_segments + 1):
                t = i / arc_segments
                # Angle from +90° down to -90° (right cap, going clockwise
                # in screen-y coords means y grows from top to bottom).
                theta = math.radians(-90.0 + 180.0 * t)
                verts.append((cx_right + r * math.cos(theta),
                              cy_top  + r * math.sin(theta)))
            # Left cap: from bottom (90°) sweep clockwise to top (270°)
            for i in range(arc_segments + 1):
                t = i / arc_segments
                theta = math.radians(90.0 + 180.0 * t)
                verts.append((cx_left + r * math.cos(theta),
                              cy_top + r * math.sin(theta)))
        else:  # vertical
            r = min(hw, hh)
            cx_mid = cx_mm
            cy_top = cy_mm - hh + r
            cy_bot = cy_mm + hh - r
            # Top cap: from right (0°) sweep CW up over to left (180°)
            for i in range(arc_segments + 1):
                t = i / arc_segments
                theta = math.radians(180.0 + 180.0 * t)
                verts.append((cx_mid + r * math.cos(theta),
                              cy_top + r * math.sin(theta)))
            # Bottom cap: left (180°) → right (360°)
            for i in range(arc_segments + 1):
                t = i / arc_segments
                theta = math.radians(0.0 + 180.0 * t)
                verts.append((cx_mid + r * math.cos(theta),
                              cy_bot + r * math.sin(theta)))
        return cls(verts)

    @classmethod
    def arch_strip(cls, cx_mm: float, cy_mm: float,
                   width_mm: float, height_mm: float,
                   curvature: float = 0.5,
                   position: str = "top",
                   arc_segments: int = 24) -> "Polygon":
        """Phase 5ax: curved horizontal strip — arched name patches.

        The classic 警局○○小組 / 急救援 patch: a wide stripe whose
        top and bottom edges are concentric circular arcs sharing a
        common centre below (``position="top"``) or above
        (``position="bottom"``) the strip.

        Geometry:
        - ``curvature`` ∈ (0, 1] — how strongly the arcs bow.
            Smaller = flatter; 0.5 ≈ typical police-arm arch;
            1.0 = nearly a half-disc.
        - ``position="top"``: arch curves UP (text reads bottom-to-top
            of arc). Imagine top of a shoulder patch.
        - ``position="bottom"``: arch curves DOWN (text under shield).
        - ``arc_segments`` — points per arc; 24 = smooth; lower = faster.

        Coordinates: returns a closed polygon traced clockwise from
        the inner-arc start vertex.
        """
        if width_mm <= 0 or height_mm <= 0:
            raise ValueError("arch_strip needs positive width/height")
        curvature = max(0.05, min(1.0, float(curvature)))
        if position not in ("top", "bottom"):
            raise ValueError(
                f"position must be 'top' or 'bottom', got {position!r}"
            )

        # Geometry derivation. The inner arc has chord ``width_mm``;
        # ``curvature`` sets sagitta s = curvature × (height_mm/2).
        hw = width_mm / 2.0
        hh = height_mm / 2.0
        sagitta_inner = curvature * hh
        # Radius from chord + sagitta: r = (chord^2 / 8s) + s/2
        if sagitta_inner < 0.5:
            sagitta_inner = 0.5
        r_inner = (hw * hw) / (2 * sagitta_inner) + sagitta_inner / 2
        r_outer = r_inner + height_mm

        # Centre of curvature: directly above (position="bottom" → arc
        # bows DOWN means centre is above) or below the strip centre.
        if position == "top":
            # Strip arches UP. Inner arc top is at cy - hh + sagitta_inner;
            # the centre lies BELOW the strip.
            centre_y = cy_mm + (r_inner - sagitta_inner)
            inner_top_y = centre_y - r_inner   # y where inner arc peaks
            # Sweep angle covering the chord.
            half_angle = math.asin(hw / r_inner)
            verts: list[tuple[float, float]] = []
            # Outer arc, left → right (top of strip when bowing up).
            for i in range(arc_segments + 1):
                t = i / arc_segments
                theta = math.pi * 1.5 - half_angle + 2 * half_angle * t
                # math angle (ccw); we want screen-y down → negate sin
                verts.append((cx_mm + r_outer * math.cos(theta),
                              centre_y + r_outer * math.sin(theta)))
            # Inner arc, right → left.
            for i in range(arc_segments + 1):
                t = i / arc_segments
                theta = math.pi * 1.5 + half_angle - 2 * half_angle * t
                verts.append((cx_mm + r_inner * math.cos(theta),
                              centre_y + r_inner * math.sin(theta)))
        else:  # position == "bottom" — arch curves DOWN
            centre_y = cy_mm - (r_inner - sagitta_inner)
            half_angle = math.asin(hw / r_inner)
            verts = []
            # Inner arc, left → right (top of strip when bowing down).
            for i in range(arc_segments + 1):
                t = i / arc_segments
                theta = math.pi * 0.5 + half_angle - 2 * half_angle * t
                verts.append((cx_mm + r_inner * math.cos(theta),
                              centre_y + r_inner * math.sin(theta)))
            # Outer arc, right → left.
            for i in range(arc_segments + 1):
                t = i / arc_segments
                theta = math.pi * 0.5 - half_angle + 2 * half_angle * t
                verts.append((cx_mm + r_outer * math.cos(theta),
                              centre_y + r_outer * math.sin(theta)))
        # Re-centre on (cx_mm, cy_mm): the geometry above places the
        # chord midpoint at cy_mm, but the strip extends asymmetrically
        # (peak on one side, chord on the other). Shift Y so the bbox
        # centre sits at cy_mm — what users intuitively expect.
        ys = [v[1] for v in verts]
        bbox_cy = (min(ys) + max(ys)) / 2.0
        shift = cy_mm - bbox_cy
        if abs(shift) > 1e-6:
            verts = [(x, y + shift) for x, y in verts]
        return cls(verts)

    @classmethod
    def banner(cls, cx_mm: float, cy_mm: float,
               width_mm: float, height_mm: float,
               notch_side: str = "right",
               notch_depth: float = 0.25) -> "Polygon":
        """Phase 5ax: flag/key-tag shape — rectangle with one notched end.

        ``notch_side``:
        - ``"right"`` → V-cut on the right edge (typical "REMOVE BEFORE
          FLIGHT" key-tag look)
        - ``"left"``  → V-cut on the left edge

        ``notch_depth`` ∈ (0.05, 0.45) — how deep the V cuts in,
        relative to the strip width. 0.25 ≈ classic look.
        """
        if width_mm <= 0 or height_mm <= 0:
            raise ValueError("banner needs positive width/height")
        if notch_side not in ("right", "left"):
            raise ValueError(
                f"notch_side must be 'right' or 'left', got {notch_side!r}"
            )
        notch_depth = max(0.05, min(0.45, float(notch_depth)))
        hw = width_mm / 2.0
        hh = height_mm / 2.0
        notch_x = notch_depth * width_mm

        if notch_side == "right":
            # CW from top-left
            verts = [
                (cx_mm - hw, cy_mm - hh),                 # top-left
                (cx_mm + hw, cy_mm - hh),                 # top-right outer
                (cx_mm + hw - notch_x, cy_mm),            # notch tip (centre)
                (cx_mm + hw, cy_mm + hh),                 # bottom-right outer
                (cx_mm - hw, cy_mm + hh),                 # bottom-left
            ]
        else:  # notch_side == "left"
            verts = [
                (cx_mm - hw, cy_mm - hh),                 # top-left outer
                (cx_mm + hw, cy_mm - hh),                 # top-right
                (cx_mm + hw, cy_mm + hh),                 # bottom-right
                (cx_mm - hw, cy_mm + hh),                 # bottom-left outer
                (cx_mm - hw + notch_x, cy_mm),            # notch tip
            ]
        return cls(verts)

    # ---------- boundary parameterisation -----------------------------

    def edges(self) -> list[tuple[tuple[float, float], tuple[float, float], float]]:
        n = len(self.vertices)
        out = []
        for i in range(n):
            a = self.vertices[i]
            b = self.vertices[(i + 1) % n]
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            out.append((a, b, L))
        return out

    def perimeter(self) -> float:
        return sum(L for _, _, L in self.edges())

    def _edge_at_t(self, t: float):
        """Return (edge_index, local_t, edge_start, edge_end) for t∈[0,1]."""
        edges = self.edges()
        total = sum(L for _, _, L in edges)
        target = (t % 1.0) * total
        acc = 0.0
        for i, (a, b, L) in enumerate(edges):
            if target <= acc + L or i == len(edges) - 1:
                local = (target - acc) / L if L else 0
                return i, max(0.0, min(1.0, local)), a, b
            acc += L
        a, b, _ = edges[-1]
        return len(edges) - 1, 1.0, a, b

    def point_at(self, t: float) -> tuple[float, float]:
        _, local, a, b = self._edge_at_t(t)
        return (a[0] + (b[0] - a[0]) * local, a[1] + (b[1] - a[1]) * local)

    def tangent_at(self, t: float) -> float:
        """Angle (deg) of the OUTWARD normal at this boundary point.

        For text on the outside of a convex polygon, we want the normal
        pointing away from the centroid — that's "up" for characters.
        """
        _, _, a, b = self._edge_at_t(t)
        # Edge tangent direction:
        dx, dy = b[0] - a[0], b[1] - a[1]
        # Outward normal (for a CCW polygon, rotate tangent +90°; for CW
        # polygon, rotate -90°). We compute centroid-relative check:
        edge_mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        cx = sum(v[0] for v in self.vertices) / len(self.vertices)
        cy = sum(v[1] for v in self.vertices) / len(self.vertices)
        # Normal rotated one way
        nx, ny = -dy, dx   # 90° CCW in math coords (= 90° CW in SVG y-down)
        # Is this pointing away from centroid?
        if (edge_mid[0] + nx - cx) ** 2 + (edge_mid[1] + ny - cy) ** 2 < \
           (edge_mid[0] - cx) ** 2 + (edge_mid[1] - cy) ** 2:
            # nope, flip
            nx, ny = -nx, -ny
        return math.degrees(math.atan2(ny, nx)) % 360

    # ---------- containment & scanline --------------------------------

    def contains(self, x: float, y: float) -> bool:
        """Ray-casting: count intersections with horizontal ray → inside = odd."""
        inside = False
        verts = self.vertices
        n = len(verts)
        j = n - 1
        for i in range(n):
            xi, yi = verts[i]
            xj, yj = verts[j]
            if ((yi > y) != (yj > y)):
                x_int = (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
                if x < x_int:
                    inside = not inside
            j = i
        return inside

    def scanline(self, y: float) -> list[tuple[float, float]]:
        """Horizontal intersections with all edges at height y; return
        paired (left, right) intervals."""
        xs: list[float] = []
        verts = self.vertices
        n = len(verts)
        for i in range(n):
            a = verts[i]
            b = verts[(i + 1) % n]
            y1, y2 = a[1], b[1]
            if y1 == y2:
                continue
            if (y1 <= y < y2) or (y2 <= y < y1):
                t = (y - y1) / (y2 - y1)
                xs.append(a[0] + t * (b[0] - a[0]))
        xs.sort()
        spans: list[tuple[float, float]] = []
        for i in range(0, len(xs) - 1, 2):
            spans.append((xs[i], xs[i + 1]))
        return spans

    def bbox(self) -> tuple[float, float, float, float]:
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        return (min(xs), min(ys), max(xs), max(ys))

    def svg_path_d(self) -> str:
        if not self.vertices:
            return ""
        parts = [f"M {self.vertices[0][0]} {self.vertices[0][1]}"]
        for x, y in self.vertices[1:]:
            parts.append(f"L {x} {y}")
        parts.append("Z")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Arc (Phase 5ah) — open partial circle, usable with the ring layout for
# "text on arc" effects. Not a closed region, so contains() / scanline()
# deliberately return empty; fill / three_band / concentric layouts cannot
# operate on an Arc.
# ---------------------------------------------------------------------------


@dataclass
class Arc:
    cx_mm: float
    cy_mm: float
    radius_mm: float
    start_deg: float = 180.0   # SVG angle: 0=3 o'clock, 90=6, 180=9, 270=12
    extent_deg: float = 180.0  # arc sweep in degrees (clockwise from start)

    @property
    def _end_deg(self) -> float:
        return self.start_deg + self.extent_deg

    def point_at(self, t: float) -> tuple[float, float]:
        theta_deg = self.start_deg + self.extent_deg * max(0.0, min(1.0, t))
        rad = math.radians(theta_deg)
        return (self.cx_mm + self.radius_mm * math.cos(rad),
                self.cy_mm + self.radius_mm * math.sin(rad))

    def tangent_at(self, t: float) -> float:
        """Outward-radial direction (same convention as Circle)."""
        return (self.start_deg + self.extent_deg * t) % 360

    def contains(self, x: float, y: float) -> bool:
        # Arc is an open path, not a filled region.
        return False

    def perimeter(self) -> float:
        return math.radians(abs(self.extent_deg)) * self.radius_mm

    def bbox(self) -> tuple[float, float, float, float]:
        # Sample ~48 points around the arc to estimate the bbox.
        xs: list[float] = []
        ys: list[float] = []
        for i in range(49):
            p = self.point_at(i / 48)
            xs.append(p[0]); ys.append(p[1])
        return (min(xs), min(ys), max(xs), max(ys))

    def scanline(self, y: float) -> list[tuple[float, float]]:
        # Not a filled region.
        return []

    def svg_path_d(self) -> str:
        sx, sy = self.point_at(0)
        ex, ey = self.point_at(1)
        large_arc_flag = 1 if abs(self.extent_deg) > 180 else 0
        sweep_flag = 1 if self.extent_deg > 0 else 0   # 1 = clockwise in SVG
        r = self.radius_mm
        return (f"M {sx} {sy} "
                f"A {r} {r} 0 {large_arc_flag} {sweep_flag} {ex} {ey}")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_shape(
    kind: str,
    cx_mm: float, cy_mm: float,
    size_mm: float,
    *,
    sides: int = 6,
    aspect: float = 1.0,
    # Phase 5ah: shape-specific knobs. All have sensible defaults.
    star_inner_ratio: float = 0.382,
    trapezoid_top_ratio: float = 0.6,
    rounded_corner_ratio: float = 0.2,
    arc_start_deg: float = 180.0,
    arc_extent_deg: float = 180.0,
    # Phase 5as
    cone_taper: float = 0.5,
    cone_invert: bool = False,
    capsule_orientation: str = "horizontal",
    # Phase 5ax
    arch_curvature: float = 0.5,
    banner_notch_depth: float = 0.25,
) -> Shape:
    """
    Convenience factory.

    Closed shapes (support all layouts: ring / fill / concentric / …):
    - 'circle'   : ``size_mm`` = diameter
    - 'ellipse'  : ``size_mm`` = horizontal diameter; vertical = size_mm × aspect
    - 'polygon'  : ``size_mm`` = diameter of bounding circle; ``sides`` = N
    - 'triangle', 'square', 'pentagon', 'hexagon', 'octagon' : shorthand polygons
    - 'star'     : ``size_mm`` = outer-vertex diameter; ``sides`` = points;
                   ``star_inner_ratio`` tunes the "chunkiness"
    - 'heart'    : ``size_mm`` = bbox side length
    - 'rounded'  : rounded rectangle; ``size_mm`` × (size_mm × aspect);
                   corner radius = min(w, h) × ``rounded_corner_ratio``
    - 'trapezoid': ``size_mm`` × (size_mm × aspect); ``trapezoid_top_ratio``
                   tunes the top width relative to the bottom

    Open paths (only the ``ring`` / ``linear`` path-following layouts):
    - 'arc'      : partial circle with ``arc_start_deg`` + ``arc_extent_deg``
    """
    shorthand = {"triangle": 3, "square": 4, "pentagon": 5,
                 "hexagon": 6, "heptagon": 7, "octagon": 8,
                 "nonagon": 9, "decagon": 10}
    if kind == "circle":
        return Circle(cx_mm, cy_mm, size_mm / 2)
    if kind == "ellipse":
        return Ellipse(cx_mm, cy_mm, size_mm / 2, (size_mm * aspect) / 2)
    if kind == "polygon":
        return Polygon.regular(cx_mm, cy_mm, size_mm / 2, sides)
    if kind in shorthand:
        return Polygon.regular(cx_mm, cy_mm, size_mm / 2, shorthand[kind])
    if kind == "star":
        return Polygon.star(
            cx_mm, cy_mm, size_mm / 2,
            points=max(3, sides),
            inner_ratio=star_inner_ratio,
        )
    if kind == "heart":
        return Polygon.heart(cx_mm, cy_mm, size_mm)
    if kind == "rounded":
        width = size_mm
        height = size_mm * aspect
        return Polygon.rounded_rect(
            cx_mm, cy_mm, width, height,
            corner_radius_mm=min(width, height) * rounded_corner_ratio,
        )
    if kind == "trapezoid":
        width = size_mm
        height = size_mm * aspect
        return Polygon.trapezoid(
            cx_mm, cy_mm, width, height,
            top_ratio=trapezoid_top_ratio,
        )
    if kind == "arc":
        return Arc(cx_mm, cy_mm, size_mm / 2,
                   start_deg=arc_start_deg,
                   extent_deg=arc_extent_deg)
    # Phase 5as
    if kind == "cone":
        width = size_mm
        height = size_mm * aspect
        return Polygon.cone(
            cx_mm, cy_mm, width, height,
            taper=cone_taper, invert=cone_invert,
        )
    if kind == "capsule":
        width = size_mm
        height = size_mm * aspect
        return Polygon.capsule(
            cx_mm, cy_mm, width, height,
            orientation=capsule_orientation,
        )
    # Phase 5ax: patch-mode shapes
    if kind == "arch_top":
        return Polygon.arch_strip(
            cx_mm, cy_mm, size_mm, size_mm * aspect,
            curvature=arch_curvature, position="top",
        )
    if kind == "arch_bottom":
        return Polygon.arch_strip(
            cx_mm, cy_mm, size_mm, size_mm * aspect,
            curvature=arch_curvature, position="bottom",
        )
    if kind == "banner_right":
        return Polygon.banner(
            cx_mm, cy_mm, size_mm, size_mm * aspect,
            notch_side="right", notch_depth=banner_notch_depth,
        )
    if kind == "banner_left":
        return Polygon.banner(
            cx_mm, cy_mm, size_mm, size_mm * aspect,
            notch_side="left", notch_depth=banner_notch_depth,
        )
    raise ValueError(f"unknown shape kind: {kind!r}")


__all__ = [
    "Shape", "Circle", "Ellipse", "Polygon", "Arc", "make_shape",
]
