"""
Multi-page packaging helpers.

If a notebook/letter layout produces N > 1 pages, we ship them as a ZIP
archive containing ``page-01.svg``, ``page-02.svg``, … This is simpler
than chunking into a single multi-page SVG (which has poor viewer support)
and maps cleanly to "print the whole thing" vs "grab just page 3".

A single-page layout is served directly as one SVG file.
"""
from __future__ import annotations

import io
import zipfile
from typing import Callable

from ..layouts import Page
from .envelope import embed_export_envelope


SvgRenderer = Callable[[Page], str]


def _wrap_with_envelope(
    renderer: SvgRenderer,
    envelope_mode: str | None,
    app_version: str | None,
    envelope_params: dict | None,
) -> SvgRenderer:
    """5fv：``envelope_mode`` 給定時，逐頁 SVG 內嵌統一出口信封。"""
    if envelope_mode is None:
        return renderer

    def _rendered(p: Page) -> str:
        return embed_export_envelope(
            renderer(p), mode=envelope_mode,
            app_version=app_version, params=envelope_params,
        )
    return _rendered


def render_pages_as_zip(
    pages: list[Page],
    renderer: SvgRenderer,
    *,
    filename_prefix: str = "page",
    envelope_mode: str | None = None,
    app_version: str | None = None,
    envelope_params: dict | None = None,
) -> bytes:
    """
    Render every page using ``renderer`` and pack into an in-memory ZIP.
    Returns the ZIP bytes.
    """
    renderer = _wrap_with_envelope(
        renderer, envelope_mode, app_version, envelope_params)
    buf = io.BytesIO()
    width = max(2, len(str(len(pages))))
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, p in enumerate(pages, start=1):
            svg = renderer(p)
            z.writestr(
                f"{filename_prefix}-{i:0{width}d}.svg",
                svg.encode("utf-8"),
            )
    return buf.getvalue()


def render_pages_as_single_or_zip(
    pages: list[Page],
    renderer: SvgRenderer,
    *,
    filename_prefix: str = "page",
    envelope_mode: str | None = None,
    app_version: str | None = None,
    envelope_params: dict | None = None,
) -> tuple[bytes, str, str]:
    """
    Convenience: if N == 1, return SVG bytes + ``image/svg+xml`` MIME.
    If N > 1, return ZIP bytes + ``application/zip``.

    Returns (body_bytes, media_type, file_extension).

    5fv：``envelope_mode`` 給定時，單頁與 zip 內每頁的 SVG 都內嵌
    統一出口信封（守門測試要求呼叫點明示）。
    """
    renderer = _wrap_with_envelope(
        renderer, envelope_mode, app_version, envelope_params)
    if len(pages) == 1:
        return (
            renderer(pages[0]).encode("utf-8"),
            "image/svg+xml",
            "svg",
        )
    return (
        render_pages_as_zip(pages, renderer, filename_prefix=filename_prefix),
        "application/zip",
        "zip",
    )


__all__ = ["render_pages_as_zip", "render_pages_as_single_or_zip"]
