"""
Letter paper mode — handwritten correspondence layout.

Differs from notebook mode mainly in presentation:

- Ruled horizontal lines only (no column grid) — like traditional writing paper
- Optional decorative border frame
- Reserved header space for title (e.g. 敬啟者 above content)
- Reserved footer space for signature (e.g. 敬上 below content)
- Typically A4 or A5 paper; smaller character size than practice notebook
"""
from __future__ import annotations

from typing import Iterable, Literal, Optional

from ..layouts import (
    Annotation, Page, PageLayout, PageSize, ReserveZone,
    SignatureBlock, TitleBlock, WritingDirection, flow_text,
)
from .page import CellStyle, render_page_svg, _xml_escape

LetterPreset = Literal["A4", "A5", "Letter"]


_PRESETS: dict[str, dict] = {
    # signature_space defaults are roomy enough for signature + date line
    "A4":     {"margin_x": 25.0, "margin_y": 28.0, "line_height": 10.0,
               "default_title_space": 14.0, "default_signature_space": 24.0},
    "A5":     {"margin_x": 18.0, "margin_y": 20.0, "line_height": 9.0,
               "default_title_space": 11.0, "default_signature_space": 20.0},
    # US Letter (8.5" × 11" = 215.9 × 279.4 mm) — slightly wider & shorter
    # than A4. Margins match common American business-letter convention
    # (1" = 25.4mm); line_height slightly larger for comfortable writing.
    "Letter": {"margin_x": 25.4, "margin_y": 25.4, "line_height": 10.0,
               "default_title_space": 14.0, "default_signature_space": 24.0},
}


def build_letter_layout(
    preset: LetterPreset = "A4",
    *,
    line_height_mm: Optional[float] = None,
    margin_mm: Optional[float] = None,
    title_space_mm: float = 0.0,
    signature_space_mm: float = 0.0,
    direction: WritingDirection = "horizontal",
    first_line_offset_mm: Optional[float] = None,
    lines_per_page: Optional[int] = None,
) -> PageLayout:
    """Build a PageLayout for a letter page.

    ``title_space_mm`` reserves the top N mm of the content area for the
    recipient address / 敬啟者 phrase (visually blank, text flows below).
    ``signature_space_mm`` does the same at the bottom.

    ``margin_mm`` (optional) overrides the preset default for all four
    margins; if omitted, the preset's asymmetric default margins are used.

    ``first_line_offset_mm`` (Phase 5aa): distance from the reference edge
    to the ending edge of the first row/column — same semantics as notebook
    mode. See ``flow_text`` docstring for the full rules. If omitted, the
    layout starts at the content top (橫) or content right (直) as usual.

    ``lines_per_page`` (Phase 5ab, precedence over ``line_height_mm``):
    fit exactly N rows (橫書) / columns (直書) of body text per page. The
    derived cell size uses the BODY content area — i.e. excludes both the
    title band (``title_space_mm``) and signature band (``signature_space_mm``)
    for 橫書, matching the user-visible "rows you can actually write in".
    Cell is also capped at ``min(content_w, content_h)`` so square cells
    never overflow the page.
    """
    if preset not in _PRESETS:
        raise ValueError(f"unknown preset {preset!r}")
    p = _PRESETS[preset]
    page = PageSize.named(preset)
    if margin_mm is not None:
        mx = my = margin_mm
    else:
        mx, my = p["margin_x"], p["margin_y"]

    # Effective content dimensions for cell-size derivation. Horizontal body
    # area is squeezed by the title+signature bands; vertical body keeps the
    # full height (bands only shorten the column, not its count).
    content_w = max(1.0, page.width_mm - 2 * mx)
    content_h_full = max(1.0, page.height_mm - 2 * my)
    content_h_body = max(
        1.0,
        page.height_mm - 2 * my - title_space_mm - signature_space_mm,
    )
    max_cell = min(content_w, content_h_full)   # square-fit cap

    # Derive line_height: lines_per_page wins; then explicit line_height_mm;
    # then preset default. All capped at max_cell.
    if lines_per_page is not None and lines_per_page > 0:
        if direction == "vertical":
            derived = content_w / lines_per_page
        else:
            derived = content_h_body / lines_per_page
        lh = min(derived, max_cell)
    elif line_height_mm is not None:
        lh = min(line_height_mm, max_cell)
    else:
        lh = min(p["line_height"], max_cell)

    return PageLayout(
        size=page,
        margin_top_mm=my + title_space_mm,
        margin_bottom_mm=my + signature_space_mm,
        margin_left_mm=mx, margin_right_mm=mx,
        line_height_mm=lh, char_width_mm=lh,
        grid_style="ruled",
        direction=direction,
        first_line_offset_mm=first_line_offset_mm,
    )


def flow_letter(
    text: str,
    char_loader,
    *,
    preset: LetterPreset = "A4",
    line_height_mm: Optional[float] = None,
    margin_mm: Optional[float] = None,
    title_space_mm: float = 0.0,
    signature_space_mm: float = 0.0,
    annotations: Optional[Iterable[Annotation]] = None,
    # Letter-specific placement (new in Phase 5b+)
    title_text: str = "",
    title_size_mm: Optional[float] = None,
    signature_text: str = "",
    signature_size_mm: Optional[float] = None,
    date_text: str = "",
    date_size_mm: Optional[float] = None,
    signature_lines_after_body: int = 1,
    signature_align: str = "right",
    direction: WritingDirection = "horizontal",
    first_line_offset_mm: Optional[float] = None,
    lines_per_page: Optional[int] = None,
) -> list[Page]:
    """
    Lay out a letter.

    Body text is flowed normally. If ``title_text`` is provided, it's
    placed in page 1's top margin. If ``signature_text`` (or ``date_text``)
    is provided, the signature block is placed **relative to where the
    body ended** — 1 row below the last body char by default (configurable
    via ``signature_lines_after_body``). If the signature block would
    exceed the bottom margin, it's pushed to a new page (cross-page
    behaviour that users expect for handwritten letters).

    Signature alignment defaults to right; date appears one line below
    the signature at 75% the signature size unless ``date_size_mm`` is
    given.
    """
    layout = build_letter_layout(
        preset=preset,
        line_height_mm=line_height_mm,
        margin_mm=margin_mm,
        title_space_mm=title_space_mm,
        signature_space_mm=signature_space_mm,
        direction=direction,
        first_line_offset_mm=first_line_offset_mm,
        lines_per_page=lines_per_page,
    )
    pages = flow_text(text, layout, char_loader, direction=direction,
                      first_line_offset_mm=first_line_offset_mm)
    if annotations and pages:
        pages[0].annotations = list(annotations)

    # ---- Title block (page 1 only) ----
    # A1 rule: title stays horizontal at top, regardless of body direction
    if title_text and pages:
        t_size = title_size_mm if title_size_mm is not None else layout.line_height_mm
        pages[0].title_block = TitleBlock(
            text=title_text,
            size_mm=t_size,
            y_mm=max(t_size, layout.margin_top_mm - 2),
            align="left",
        )

    # ---- Signature block placement ----
    # Horizontal letter: signature/date N rows below the body end, right-aligned
    # Vertical letter: signature placed on the LEFT side of the page as a
    #   final column; date below the signature. (A1: traditional 落款)
    if signature_text or date_text:
        s_size = (signature_size_mm if signature_size_mm is not None
                  else layout.line_height_mm)
        d_size = (date_size_mm if date_size_mm is not None else s_size * 0.75)

        last_page = pages[-1]

        if direction == "vertical":
            # Phase 5z: signature 靠下 — bottom-aligned to content_bottom,
            # in the same column as body end (or next leftward column if
            # body reaches too far down). Bottom edge of the signature
            # block sits at content_bottom regardless of which column.
            col_step = layout.char_width_mm + layout.line_spacing_mm
            # Estimated total height of signature + date (stacked chars)
            step_sig = s_size * 1.1
            step_d = d_size * 1.1
            n_sig = sum(1 for ch in signature_text if not ch.isspace())
            n_d   = sum(1 for ch in date_text if not ch.isspace())
            total_h = n_sig * step_sig + (2 + n_d * step_d if n_d else 0)
            # sig_y = baseline y of first signature char.
            # We want the LAST char's bottom to reach content_bottom.
            # First char sits at sig_y; last at sig_y + (n_sig-1)*step_sig
            # (and date below that). So sig_y = content_bottom - total_h + s_size.
            sig_y = layout.content_bottom - total_h + s_size

            # Column choice: start from last body column (leftmost x); if
            # body already occupies the required bottom space there, slide
            # one column further left.
            if last_page.chars:
                min_x = min(p.x_mm for p in last_page.chars)
                same_col_chars = [p for p in last_page.chars
                                   if abs(p.x_mm - min_x) < 0.5]
                last_body_bottom = max(
                    p.y_mm + p.height_mm for p in same_col_chars)
                gap_after_body = (max(0, signature_lines_after_body)
                                   * layout.line_height_mm)
                # Top of signature block (≈ sig_y - s_size)
                sig_top = sig_y - s_size
                if sig_top < last_body_bottom + gap_after_body:
                    # Collides with body — shift column left
                    sig_x = min_x - col_step
                    if sig_x < layout.content_x:
                        new_page = Page(page_num=len(pages) + 1, layout=layout)
                        pages.append(new_page)
                        last_page = new_page
                        sig_x = layout.content_right - layout.char_width_mm
                else:
                    sig_x = min_x
            else:
                sig_x = layout.content_right - layout.char_width_mm

            # Final clamp: signature must fit inside content area vertically
            if sig_y - s_size < layout.content_y:
                sig_y = layout.content_y + s_size   # stick to top (very tall sig)

            last_page.signature_block = SignatureBlock(
                signature_text=signature_text,
                date_text=date_text,
                signature_size_mm=s_size,
                date_size_mm=d_size,
                y_mm=sig_y,
                align=f"vertical:{sig_x:.3f}",
            )
        else:
            date_space = (d_size + 2) if date_text else 0
            needed_below = s_size + date_space
            if last_page.chars:
                last = last_page.chars[-1]
                body_end_y = last.y_mm + last.height_mm
            else:
                body_end_y = layout.content_y
            gap = max(0, signature_lines_after_body) * layout.row_step
            sig_y = body_end_y + gap
            bottom_needed = sig_y + needed_below
            if bottom_needed > layout.content_bottom:
                new_page = Page(page_num=len(pages) + 1, layout=layout)
                pages.append(new_page)
                sig_y = layout.content_y + layout.row_step
                last_page = new_page
            last_page.signature_block = SignatureBlock(
                signature_text=signature_text,
                date_text=date_text,
                signature_size_mm=s_size,
                date_size_mm=d_size,
                y_mm=sig_y,
                align=signature_align,
            )
    return pages


def _decorative_border_svg(page: Page) -> str:
    """Thin decorative inner/outer borders."""
    W = page.layout.size.width_mm
    H = page.layout.size.height_mm
    outer_inset = 4.0
    inner_inset = 6.0
    return (
        f'<g class="border" fill="none" stroke="#888" stroke-width="0.4">'
        f'<rect x="{outer_inset}" y="{outer_inset}" '
        f'width="{W - outer_inset * 2}" height="{H - outer_inset * 2}"/>'
        f'<rect x="{inner_inset}" y="{inner_inset}" '
        f'width="{W - inner_inset * 2}" height="{H - inner_inset * 2}" '
        'stroke-width="0.15"/>'
        f'</g>'
    )


def _text_anchor_for(align: str) -> str:
    return {"right": "end", "center": "middle", "left": "start"}.get(align, "start")


def _render_signature_block_svg(sb, layout: PageLayout) -> list[str]:
    """Render the flow-aware signature block. Returns list of SVG fragments.

    Horizontal mode: single-line text with chosen anchor.
    Vertical mode  : signature rendered as a column of chars top→bottom
                     (one char per <text>), then date column below.
                     Encoded via ``align='vertical:<x>'``.
    """
    out: list[str] = []

    # Vertical signature (直書 letter): align field carries the X of the column
    if isinstance(sb.align, str) and sb.align.startswith("vertical:"):
        try:
            x_col = float(sb.align.split(":", 1)[1])
        except ValueError:
            x_col = layout.content_x
        # Place each char of signature as its own <text>, top-to-bottom.
        y = sb.y_mm
        step_sig = sb.signature_size_mm * 1.1
        for ch in sb.signature_text:
            if ch.isspace():
                y += step_sig
                continue
            out.append(
                f'<text x="{x_col + sb.signature_size_mm / 2:.2f}" '
                f'y="{y:.2f}" text-anchor="middle" '
                f'font-size="{sb.signature_size_mm:.2f}" fill="#333" '
                f'font-family="sans-serif">{_xml_escape(ch)}</text>'
            )
            y += step_sig
        # Date below the signature column (same column)
        if sb.date_text:
            y += 2  # small gap
            step_d = sb.date_size_mm * 1.1
            for ch in sb.date_text:
                if ch.isspace():
                    y += step_d
                    continue
                out.append(
                    f'<text x="{x_col + sb.signature_size_mm / 2:.2f}" '
                    f'y="{y:.2f}" text-anchor="middle" '
                    f'font-size="{sb.date_size_mm:.2f}" fill="#666" '
                    f'font-family="sans-serif">{_xml_escape(ch)}</text>'
                )
                y += step_d
        return out

    # Horizontal path (unchanged)
    if sb.align == "right":
        x = layout.content_right
    elif sb.align == "center":
        x = (layout.content_x + layout.content_right) / 2
    else:
        x = layout.content_x
    anchor = _text_anchor_for(sb.align)
    if sb.signature_text:
        out.append(
            f'<text x="{x:.2f}" y="{sb.y_mm:.2f}" '
            f'text-anchor="{anchor}" '
            f'font-size="{sb.signature_size_mm:.2f}" fill="#333" '
            f'font-family="sans-serif">'
            f'{_xml_escape(sb.signature_text)}</text>'
        )
    if sb.date_text:
        date_y = sb.y_mm + sb.date_size_mm + 2
        out.append(
            f'<text x="{x:.2f}" y="{date_y:.2f}" '
            f'text-anchor="{anchor}" '
            f'font-size="{sb.date_size_mm:.2f}" fill="#666" '
            f'font-family="sans-serif">'
            f'{_xml_escape(sb.date_text)}</text>'
        )
    return out


def _render_title_block_svg(tb, layout: PageLayout) -> list[str]:
    x = layout.content_x
    if tb.align == "right":
        x = layout.content_right
    elif tb.align == "center":
        x = (layout.content_x + layout.content_right) / 2
    anchor = _text_anchor_for(tb.align)
    return [
        f'<text x="{x:.2f}" y="{tb.y_mm:.2f}" '
        f'text-anchor="{anchor}" '
        f'font-size="{tb.size_mm:.2f}" fill="#333" '
        f'font-family="sans-serif">'
        f'{_xml_escape(tb.text)}</text>'
    ]


def render_letter_page_svg(
    page: Page,
    *,
    cell_style: CellStyle = "outline",
    decorative_border: bool = True,
    show_page_number: bool = True,
    show_grid: bool = True,
    # Legacy absolute-position params (used only when page.title_block /
    # page.signature_block are NOT set by flow_letter). Kept for API
    # compatibility / ad-hoc rendering.
    title_text: str = "",
    signature_text: str = "",
    date_text: str = "",
    title_size_mm: Optional[float] = None,
    signature_size_mm: Optional[float] = None,
    date_size_mm: Optional[float] = None,
) -> str:
    """
    Render one letter page.

    Prefers ``page.title_block`` / ``page.signature_block`` (set by
    ``flow_letter``) over the legacy positional parameters. The flow-aware
    blocks know WHERE to render (page-local Y based on body end); the
    legacy path places them at fixed page locations as a fallback.

    ``show_grid`` (Phase 5af): when False, the ruled horizontal/vertical
    writing lines are omitted so only the title, body text, signature,
    and (optionally) the decorative border remain — a "clean text" view.
    """
    base = render_page_svg(
        page,
        cell_style=cell_style,
        draw_border=False,
        show_page_number=show_page_number,
        show_zones=False,
        show_grid=show_grid,
    )
    layout = page.layout
    extras: list[str] = []
    if decorative_border:
        extras.append(_decorative_border_svg(page))

    # --- Title: prefer flow-aware block ---
    if page.title_block is not None:
        extras.extend(_render_title_block_svg(page.title_block, layout))
    elif title_text:
        t_size = title_size_mm if title_size_mm is not None else layout.line_height_mm
        extras.extend(_render_title_block_svg(
            TitleBlock(text=title_text, size_mm=t_size,
                       y_mm=max(t_size, layout.margin_top_mm - 2),
                       align="left"),
            layout,
        ))

    # --- Signature: prefer flow-aware block ---
    if page.signature_block is not None:
        extras.extend(_render_signature_block_svg(page.signature_block, layout))
    elif signature_text or date_text:
        s_size = (signature_size_mm if signature_size_mm is not None
                  else layout.line_height_mm)
        d_size = (date_size_mm if date_size_mm is not None else s_size * 0.75)
        # Legacy bottom-right absolute placement
        H = layout.size.height_mm
        y = H - 12 - ((d_size + 2) if date_text else 0)
        extras.extend(_render_signature_block_svg(
            SignatureBlock(
                signature_text=signature_text, date_text=date_text,
                signature_size_mm=s_size, date_size_mm=d_size,
                y_mm=y, align="right",
            ),
            layout,
        ))

    if not extras:
        return base
    return base.replace("</svg>", "\n".join(extras) + "\n</svg>")


def render_letter_gcode(
    pages: list[Page],
    *,
    cell_style: CellStyle = "outline",
    feed_rate: int = 3000,
    travel_rate: int = 6000,
    pen_up_cmd: str = "M5",
    pen_down_cmd: str = "M3 S90",
    pen_dwell_sec: float = 0.15,
    flip_y: bool = False,
) -> str:
    """Emit G-code for letter pages.

    Delegates to ``render_notebook_gcode`` (same Page IR, same stroke→G-code
    conversion), then swaps the file header banner so the output identifies
    itself as a letter job.

    Only body character strokes are written — title and signature blocks
    are decorative text (rendered via SVG ``<text>``), not stroke data, so
    a stroke-based robot cannot reproduce them. This matches how notebook
    mode skips non-stroke content.
    """
    from .notebook import render_notebook_gcode

    code = render_notebook_gcode(
        pages,
        cell_style=cell_style,
        feed_rate=feed_rate,
        travel_rate=travel_rate,
        pen_up_cmd=pen_up_cmd,
        pen_down_cmd=pen_down_cmd,
        pen_dwell_sec=pen_dwell_sec,
        flip_y=flip_y,
    )
    return code.replace(
        "; --- stroke-order 筆記 G-code ---",
        "; --- stroke-order 信紙 G-code ---\n"
        "; (title/signature blocks are decorative text; only body strokes emitted)",
        1,
    )


def render_letter_json(
    pages: list[Page],
    *,
    cell_style: CellStyle = "outline",
    indent: int = 2,
) -> str:
    """Render letter pages as structured JSON.

    Wraps ``render_notebook_json`` and extends it with letter-specific data:

    - Top-level key renamed ``"notebook"`` → ``"letter"``.
    - Each page entry carries an optional ``title_block`` and/or
      ``signature_block`` sub-object (only when set on the Page).

    The base ``pages[].chars`` / ``pages[].zones`` fields remain identical
    so downstream consumers that work with notebook JSON keep working.
    """
    import json as _json
    from .notebook import render_notebook_json

    base = _json.loads(
        render_notebook_json(pages, cell_style=cell_style, indent=indent)
    )
    # Swap top-level key for clarity (readers grep for the mode name).
    base["letter"] = base.pop("notebook")

    # Annotate per-page with optional title/signature metadata.
    for page_obj, page_out in zip(pages, base["pages"]):
        tb = page_obj.title_block
        if tb is not None:
            page_out["title_block"] = {
                "text": tb.text,
                "size_mm": round(tb.size_mm, 3),
                "y_mm": round(tb.y_mm, 3),
                "align": tb.align,
            }
        sb = page_obj.signature_block
        if sb is not None:
            page_out["signature_block"] = {
                "signature_text": sb.signature_text,
                "date_text": sb.date_text,
                "signature_size_mm": round(sb.signature_size_mm, 3),
                "date_size_mm": round(sb.date_size_mm, 3),
                "y_mm": round(sb.y_mm, 3),
                "align": sb.align,
            }

    return _json.dumps(base, ensure_ascii=False, indent=indent)


__all__ = [
    "build_letter_layout",
    "flow_letter",
    "render_letter_page_svg",
    "render_letter_gcode",
    "render_letter_json",
    "LetterPreset",
]
