"""
Notebook mode — multi-page handwriting practice layout.

Text flows left-to-right, wraps at the right margin, auto-paginates. A
configurable doodle reserve zone (default: none) lets you leave blank
space on each page. Annotations can be overlaid at arbitrary mm positions.

Typical settings
----------------

- ``small``  = A6 (105×148 mm), line height 10 mm
- ``medium`` = A5 (148×210 mm), line height 12 mm
- ``large``  = A4 (210×297 mm), line height 15 mm
"""
from __future__ import annotations

from typing import Iterable, Literal, Optional

from ..layouts import (
    Annotation, GridStyle, Page, PageLayout, PageSize, ReserveZone,
    WritingDirection, flow_text,
)
from .page import CellStyle, render_page_svg

# re-export for __all__ consumers
_CellStyle_ = CellStyle  # noqa

NotebookPreset = Literal["small", "medium", "large", "letter"]


_PRESETS: dict[str, dict] = {
    "small":  {"page": "A6",     "line_height": 10.0, "margin": 8.0},
    "medium": {"page": "A5",     "line_height": 12.0, "margin": 12.0},
    "large":  {"page": "A4",     "line_height": 15.0, "margin": 15.0},
    # US Letter (8.5" × 11" ≈ 215.9 × 279.4 mm) — similar to A4 but slightly
    # wider/shorter. Uses a ~16mm margin which matches common US letter paper.
    "letter": {"page": "Letter", "line_height": 15.0, "margin": 16.0},
}


def build_notebook_layout(
    preset: NotebookPreset = "large",
    *,
    grid_style: GridStyle = "square",
    line_height_mm: Optional[float] = None,
    margin_mm: Optional[float] = None,
    doodle_zone: bool = False,
    doodle_zone_size_mm: float = 40.0,
    doodle_zone_x_mm: Optional[float] = None,
    doodle_zone_y_mm: Optional[float] = None,
    doodle_zone_width_mm: Optional[float] = None,
    doodle_zone_height_mm: Optional[float] = None,
    lines_per_page: Optional[int] = None,
    direction: WritingDirection = "horizontal",
    first_line_offset_mm: Optional[float] = None,
    zones: Optional[list[dict]] = None,
) -> PageLayout:
    """Build a PageLayout for one of the preset notebook sizes.

    ``lines_per_page`` (B1 precedence): overrides ``line_height_mm``. The
    source dimension depends on ``direction``:

    - ``horizontal`` (橫書): N *rows* per page → ``content_height / N``
    - ``vertical``   (直書): N *columns* per page → ``content_width / N``

    The derived cell is also **capped at the smaller content dimension** so
    square cells never overflow the page. This handles edge cases like
    ``lines_per_page=1`` where the derived cell would otherwise be taller
    than the page is wide (Phase 5m fix).
    """
    if preset not in _PRESETS:
        raise ValueError(f"unknown preset {preset!r}")
    p = _PRESETS[preset]
    page = PageSize.named(p["page"])
    mg = margin_mm if margin_mm is not None else p["margin"]

    content_w = max(1.0, page.width_mm - 2 * mg)
    content_h = max(1.0, page.height_mm - 2 * mg)
    max_cell = min(content_w, content_h)   # square-fit cap

    # Derive line_height: lines_per_page wins if set (B1)
    if lines_per_page is not None and lines_per_page > 0:
        if direction == "vertical":
            derived = content_w / lines_per_page
        else:
            derived = content_h / lines_per_page
        lh = min(derived, max_cell)
    elif line_height_mm is not None:
        lh = min(line_height_mm, max_cell)
    else:
        lh = min(p["line_height"], max_cell)

    zone_objs: list[ReserveZone] = []
    # Helper to clamp + build ReserveZone
    content_x_min = mg
    content_y_min = mg
    content_x_max = page.width_mm - mg
    content_y_max = page.height_mm - mg

    def _clamp_zone(zx, zy, zw, zh):
        zx = max(content_x_min, min(zx, content_x_max - zw))
        zy = max(content_y_min, min(zy, content_y_max - zh))
        zw = min(zw, content_x_max - zx)
        zh = min(zh, content_y_max - zy)
        return zx, zy, zw, zh

    if zones:
        # Phase 5s: explicit zones list (can carry svg_content)
        for i, z in enumerate(zones):
            zx = float(z.get("x", content_x_max - 40))
            zy = float(z.get("y", content_y_max - 40))
            zw = float(z.get("w", 40.0))
            zh = float(z.get("h", 40.0))
            zx, zy, zw, zh = _clamp_zone(zx, zy, zw, zh)
            svg_content = z.get("svg_content")
            vb = z.get("content_viewbox")
            if vb is not None and not isinstance(vb, tuple):
                vb = tuple(vb)
            label = z.get("label") or f"塗鴉區{i+1}"
            zone_objs.append(ReserveZone(
                x_mm=zx, y_mm=zy, width_mm=zw, height_mm=zh,
                label=label, svg_content=svg_content, content_viewbox=vb,
                stretch=bool(z.get("stretch", False)),
            ))
    elif doodle_zone:
        # Legacy single-zone path (Phase 5a/5r)
        zw = (doodle_zone_width_mm if doodle_zone_width_mm is not None
              else doodle_zone_size_mm)
        zh = (doodle_zone_height_mm if doodle_zone_height_mm is not None
              else doodle_zone_size_mm)
        zx = (doodle_zone_x_mm if doodle_zone_x_mm is not None
              else page.width_mm - mg - zw)
        zy = (doodle_zone_y_mm if doodle_zone_y_mm is not None
              else page.height_mm - mg - zh)
        zx, zy, zw, zh = _clamp_zone(zx, zy, zw, zh)
        zone_objs.append(ReserveZone(zx, zy, zw, zh, label="塗鴉區"))

    # The local var `zones` collides with the function arg — alias for return:
    zones_for_layout = zone_objs

    return PageLayout(
        size=page,
        margin_top_mm=mg, margin_bottom_mm=mg,
        margin_left_mm=mg, margin_right_mm=mg,
        line_height_mm=lh, char_width_mm=lh,
        grid_style=grid_style,
        reserve_zones=zones_for_layout,
        direction=direction,
        first_line_offset_mm=first_line_offset_mm,
    )


def flow_notebook(
    text: str,
    char_loader,
    *,
    preset: NotebookPreset = "large",
    grid_style: GridStyle = "square",
    line_height_mm: Optional[float] = None,
    margin_mm: Optional[float] = None,
    doodle_zone: bool = False,
    doodle_zone_size_mm: float = 40.0,
    doodle_zone_x_mm: Optional[float] = None,
    doodle_zone_y_mm: Optional[float] = None,
    doodle_zone_width_mm: Optional[float] = None,
    doodle_zone_height_mm: Optional[float] = None,
    annotations: Optional[Iterable[Annotation]] = None,
    direction: WritingDirection = "horizontal",
    lines_per_page: Optional[int] = None,
    first_line_offset_mm: Optional[float] = None,
    zones: Optional[list[dict]] = None,
) -> list[Page]:
    """
    Lay text into notebook pages with the chosen preset. Returns list[Page].
    Caller renders each page with ``render_notebook_page_svg``.

    ``direction``      — ``horizontal`` (default, 橫書) or ``vertical`` (直書).
    ``lines_per_page`` — if given, overrides ``line_height_mm`` so exactly
                          that many rows (橫書) or columns (直書) fit per page.
    """
    layout = build_notebook_layout(
        preset=preset,
        grid_style=grid_style,
        line_height_mm=line_height_mm,
        margin_mm=margin_mm,
        doodle_zone=doodle_zone,
        doodle_zone_size_mm=doodle_zone_size_mm,
        doodle_zone_x_mm=doodle_zone_x_mm,
        doodle_zone_y_mm=doodle_zone_y_mm,
        doodle_zone_width_mm=doodle_zone_width_mm,
        doodle_zone_height_mm=doodle_zone_height_mm,
        lines_per_page=lines_per_page,
        direction=direction,
        first_line_offset_mm=first_line_offset_mm,
        zones=zones,
    )
    pages = flow_text(text, layout, char_loader, direction=direction,
                      first_line_offset_mm=first_line_offset_mm)
    if annotations and pages:
        pages[0].annotations = list(annotations)
    return pages


def render_notebook_page_svg(
    page: Page,
    *,
    cell_style: CellStyle = "ghost",
    draw_border: bool = True,
    show_page_number: bool = True,
) -> str:
    """
    Render one notebook page as SVG.

    Defaults to ``cell_style='ghost'`` (faint grey character for tracing
    practice) — this is the most common notebook use case: the student
    traces over the printed character.
    """
    return render_page_svg(
        page,
        cell_style=cell_style,
        draw_border=draw_border,
        show_page_number=show_page_number,
    )


# ---------------------------------------------------------------------------
# Phase 5v: G-code + JSON exporters for notebook pages
# ---------------------------------------------------------------------------


# Styles that actually get written by the robot (not for human tracing practice)
_WRITABLE_STYLES = {"outline", "trace", "filled"}


def render_notebook_gcode(
    pages: list[Page],
    *,
    cell_style: CellStyle = "ghost",
    feed_rate: int = 3000,
    travel_rate: int = 6000,
    pen_up_cmd: str = "M5",
    pen_down_cmd: str = "M3 S90",
    pen_dwell_sec: float = 0.15,
    flip_y: bool = False,     # page Y is already mm, so default don't flip
) -> str:
    """Emit G-code for notebook pages.

    - Only emits characters when ``cell_style`` is ``outline`` / ``trace`` /
      ``filled`` (i.e. the robot should physically write them). ``ghost`` and
      ``blank`` are for human tracing / freehand practice and skipped.
    - Pages are emitted sequentially with comment markers.
    - Reserve zones (塗鴉區) are emitted as comment markers only — the
      robot doesn't draw them, but the G-code file notes where they are.
    """
    from io import StringIO
    from ..ir import EM_SIZE

    buf = StringIO()
    buf.write("; --- stroke-order 筆記 G-code ---\n")
    buf.write(f"; pages: {len(pages)}  cell_style: {cell_style}  feed: {feed_rate}\n")
    buf.write("G21 ; mm\n")
    buf.write("G90 ; absolute\n")
    buf.write(f"{pen_up_cmd} ; pen up (start)\n")
    if pen_dwell_sec > 0:
        buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")

    # Only emit strokes if the cell_style is a writable one
    write_chars = cell_style in _WRITABLE_STYLES

    for page in pages:
        buf.write(f"\n; ==== page {page.page_num} / {len(pages)} ====\n")
        for z in page.layout.reserve_zones:
            buf.write(f"; zone '{z.label}' x={z.x_mm} y={z.y_mm} "
                      f"w={z.width_mm} h={z.height_mm}\n")

        if not write_chars:
            buf.write(f"; (cell_style={cell_style} — no strokes emitted)\n")
            continue

        for pc in page.chars:
            if not pc.char.strokes:
                continue
            scale_x = pc.width_mm / EM_SIZE
            scale_y = pc.height_mm / EM_SIZE
            buf.write(f"\n; -- char {pc.char.char} at ({pc.x_mm:.2f},"
                      f"{pc.y_mm:.2f}) --\n")
            for s in pc.char.strokes:
                pts = s.track
                if not pts:
                    continue

                def _xy(p):
                    x_mm = pc.x_mm + p.x * scale_x
                    y_ir = (EM_SIZE - p.y) if flip_y else p.y
                    y_mm = pc.y_mm + y_ir * scale_y
                    return x_mm, y_mm

                x, y = _xy(pts[0])
                buf.write(f"G0 X{x:.3f} Y{y:.3f} F{travel_rate}\n")
                buf.write(f"{pen_down_cmd}\n")
                if pen_dwell_sec > 0:
                    buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")
                for p in pts[1:]:
                    x, y = _xy(p)
                    buf.write(f"G1 X{x:.3f} Y{y:.3f} F{feed_rate}\n")
                if pen_dwell_sec > 0:
                    buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")
                buf.write(f"{pen_up_cmd}\n")

    buf.write(f"\n; --- epilogue ---\n")
    buf.write(f"{pen_up_cmd}\n")
    buf.write("; done\n")
    return buf.getvalue()


def render_notebook_json(
    pages: list[Page],
    *,
    cell_style: CellStyle = "ghost",
    indent: int = 2,
) -> str:
    """Render notebook pages as structured JSON (pages + chars + zones).

    Output shape::

        {
          "notebook": {
            "pages": 3,
            "page_size_mm": [210, 297],
            "direction": "horizontal",
            "line_height_mm": 15,
            "cell_style": "ghost"
          },
          "pages": [
            {
              "page_num": 1,
              "chars": [
                {"char": "永", "unicode": "U+6C38",
                 "x_mm": 15, "y_mm": 15, "width_mm": 15, "height_mm": 15,
                 "strokes": [[[x_mm,y_mm], ...], ...]}
              ],
              "zones": [
                {"label": "塗鴉區", "x_mm": 15, "y_mm": 15,
                 "width_mm": 50, "height_mm": 50,
                 "svg_content": "..." or null}
              ]
            }
          ]
        }
    """
    import json
    from ..ir import EM_SIZE

    if not pages:
        return json.dumps({"notebook": {"pages": 0}, "pages": []},
                          ensure_ascii=False, indent=indent)

    layout = pages[0].layout
    out_pages = []
    for page in pages:
        chars_out = []
        for pc in page.chars:
            scale_x = pc.width_mm / EM_SIZE
            scale_y = pc.height_mm / EM_SIZE
            strokes = []
            for s in pc.char.strokes:
                track = [[round(pc.x_mm + p.x * scale_x, 3),
                          round(pc.y_mm + p.y * scale_y, 3)]
                         for p in s.track]
                strokes.append({
                    "index": s.index,
                    "kind_name": s.kind_name,
                    "has_hook": s.has_hook,
                    "track_mm": track,
                })
            chars_out.append({
                "char": pc.char.char,
                "unicode": f"U+{pc.char.unicode_hex.upper()}",
                "x_mm": round(pc.x_mm, 3),
                "y_mm": round(pc.y_mm, 3),
                "width_mm": round(pc.width_mm, 3),
                "height_mm": round(pc.height_mm, 3),
                "strokes": strokes,
            })
        zones_out = []
        for z in page.layout.reserve_zones:
            zones_out.append({
                "label": z.label,
                "x_mm": round(z.x_mm, 3),
                "y_mm": round(z.y_mm, 3),
                "width_mm": round(z.width_mm, 3),
                "height_mm": round(z.height_mm, 3),
                "svg_content": z.svg_content,
                "content_viewbox": (list(z.content_viewbox)
                                    if z.content_viewbox else None),
            })
        # Phase 5ai: chars without stroke data are captured as text-fallback
        # entries so downstream consumers (and the robot-driver UI) know
        # which cells won't be written by a stroke-based machine.
        text_fallback = [
            {
                "char": tg.char,
                "x_mm": round(tg.x_mm, 3),
                "y_mm": round(tg.y_mm, 3),
                "width_mm": round(tg.width_mm, 3),
                "height_mm": round(tg.height_mm, 3),
            }
            for tg in getattr(page, "text_glyphs", [])
        ]
        page_out: dict = {
            "page_num": page.page_num,
            "chars": chars_out,
            "zones": zones_out,
        }
        if text_fallback:
            page_out["text_fallback"] = text_fallback
        out_pages.append(page_out)

    payload = {
        "notebook": {
            "pages": len(pages),
            "page_size_mm": [layout.size.width_mm, layout.size.height_mm],
            "direction": layout.direction,
            "line_height_mm": layout.line_height_mm,
            "char_width_mm": layout.char_width_mm,
            "cell_style": cell_style,
            "grid_style": layout.grid_style,
        },
        "pages": out_pages,
    }
    return json.dumps(payload, ensure_ascii=False, indent=indent)


__all__ = [
    "build_notebook_layout",
    "flow_notebook",
    "render_notebook_page_svg",
    "render_notebook_gcode",
    "render_notebook_json",
    "NotebookPreset",
]
