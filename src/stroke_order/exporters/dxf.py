"""
Phase 5bq: minimal DXF R12 (AC1009) ASCII writer — zero dependencies.

Emits layered POLYLINE entities for laser software (LightBurn,
Beam Studio) and CAD. Modelled on the VectorLine convention
(REF_ANALYSIS_VECTORLINE.md): CUT layer red, ENGRAVE black — plus a
WRITE layer (blue) carrying centreline pen tracks for plotters.

Design notes
------------
- R12 chosen deliberately: the most widely-parsed DXF dialect; classic
  POLYLINE/VERTEX/SEQEND (LWPOLYLINE is R13+ and less universally read).
- Our geometry lives in SVG-like mm space (Y pointing DOWN); DXF is
  Y-up, so ``flip_y=True`` (default) negates Y — shapes import
  upright and unmirrored. Absolute translation is irrelevant to laser
  software (they re-origin on import).
- Only what we need: no BLOCKS, no dimensions, no text entities.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DxfPolyline:
    """One polyline in mm space (SVG-like, Y down)."""
    points: list = field(default_factory=list)   # [(x_mm, y_mm), ...]
    closed: bool = False


#: AutoCAD colour indices per conventional layer name.
LAYER_COLORS = {
    "CUT": 1,       # red
    "ENGRAVE": 7,   # black/white
    "WRITE": 5,     # blue
}


def _g(code: int, value) -> str:
    """One DXF group: code line + value line."""
    return f"{code}\n{value}\n"


def layers_to_dxf(
    layers: list,          # [(layer_name, [DxfPolyline, ...]), ...]
    *,
    flip_y: bool = True,
) -> str:
    """Serialise named polyline layers into a DXF R12 ASCII document.

    ``layers`` preserves order; layer colours come from
    :data:`LAYER_COLORS` (fallback: 7). Empty layers are still declared
    in the LAYER table (harmless, keeps importers' layer lists stable)
    but emit no entities.
    """
    out: list[str] = []

    # --- HEADER ----------------------------------------------------------
    out.append(_g(0, "SECTION") + _g(2, "HEADER"))
    out.append(_g(9, "$ACADVER") + _g(1, "AC1009"))
    out.append(_g(0, "ENDSEC"))

    # --- TABLES: layer table ----------------------------------------------
    out.append(_g(0, "SECTION") + _g(2, "TABLES"))
    out.append(_g(0, "TABLE") + _g(2, "LAYER") + _g(70, len(layers)))
    for name, _polys in layers:
        color = LAYER_COLORS.get(name, 7)
        out.append(
            _g(0, "LAYER") + _g(2, name) + _g(70, 0)
            + _g(62, color) + _g(6, "CONTINUOUS")
        )
    out.append(_g(0, "ENDTAB") + _g(0, "ENDSEC"))

    # --- ENTITIES ----------------------------------------------------------
    out.append(_g(0, "SECTION") + _g(2, "ENTITIES"))
    sy = -1.0 if flip_y else 1.0
    for name, polys in layers:
        for poly in polys:
            pts = poly.points
            if len(pts) < 2:
                continue
            out.append(
                _g(0, "POLYLINE") + _g(8, name)
                + _g(66, 1)                       # vertices follow
                + _g(70, 1 if poly.closed else 0)
            )
            for x, y in pts:
                out.append(
                    _g(0, "VERTEX") + _g(8, name)
                    + _g(10, f"{x:.3f}") + _g(20, f"{sy * y:.3f}")
                    + _g(30, "0.0")
                )
            out.append(_g(0, "SEQEND") + _g(8, name))
    out.append(_g(0, "ENDSEC"))
    out.append(_g(0, "EOF"))
    return "".join(out)


__all__ = ["DxfPolyline", "LAYER_COLORS", "layers_to_dxf"]
