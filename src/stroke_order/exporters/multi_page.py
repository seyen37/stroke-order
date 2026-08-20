"""
Multi-page packaging helpers.

If a notebook/letter layout produces N > 1 pages, we ship them as a ZIP
archive containing ``page-01.svg``, ``page-02.svg``, … This is simpler
than chunking into a single multi-page SVG (which has poor viewer support)
and maps cleanly to "print the whole thing" vs "grab just page 3".

A single-page layout is served directly as one SVG file.

W1：本模組同時是 **PDF／PNG 的打包縫**。字帖四模式原本只出 SVG／ZIP，
老師要列印得先下載 ZIP 再自己拼；抄經模式（``routes/sutra.py``）早就有
一條 SVG →(cairosvg) PNG →(Pillow) 多頁 PDF 的管線在生產跑，W1 把它
下沉到這裡讓四個模式共用。``cairosvg``／``Pillow`` 在函式內延遲 import
（同 sutra 作法）——它們是 web extras，純 SVG／ZIP 路徑不該被拖累。
"""
from __future__ import annotations

import io
import re
import zipfile
from typing import Callable

from ..layouts import Page
from .envelope import embed_export_envelope


SvgRenderer = Callable[[Page], str]

# ---------------------------------------------------------------------
# W1 光柵化配額
# ---------------------------------------------------------------------
#
# 為什麼需要配額：多頁 PDF 的峰值記憶體隨「頁數 × 單頁像素」線性成長，
# 而 Pillow 的 ``append_images`` **不吃 generator**（實測傳 generator 與
# 傳 list 的峰值 RSS 完全相同，466 vs 462 MB），所以沒有串流出頁這條路。
#
# 實測（A4、各自獨立行程量 ``ru_maxrss``）：
#
#   =====  ======  ======  ======
#   dpi    10 頁   20 頁   27 頁
#   =====  ======  ======  ======
#   150    136 MB  --      278 MB
#   200    214 MB  362 MB  465 MB
#   300    435 MB  --      --
#   =====  ======  ======  ======
#
# 模型有三項，缺一不可：
#
#   峰值 MB ≈ _PEAK_BASE_MB                      直譯器與模組常駐
#           + _PEAK_PER_PAGE_MB   × 單頁 MB      cairosvg 的工作緩衝
#           + _PEAK_ACCUM_FACTOR  × 頁數 × 單頁 MB   Pillow 持有的全部頁
#
# 中間那項是第一版漏掉的：cairosvg 光柵化時的暫存隨**單頁像素**走、與
# 頁數無關，所以「低頁數 × 高 dpi」會被低估（300 dpi × 5 頁模型 249 vs
# 實測 269）。補上後八個量測點全部不低估。
#   單頁 MB = 寬px × 高px × 3 / 1e6
#
# Render 免費層 512 MB。照抄 sutra 的 dpi=200 預設，稿紙滿載（8000 字
# ≈ 27 頁）就會 OOM——承 §35–§38 雲端資源天花板的教訓，這裡改成
# **算得出來就下修 dpi、算不出來才拒絕**，而且下修一定回報（§86 降級
# 供應＋誠實標注，不無聲降畫質）。
# 三個係數都取「比擬合值再保守一點」：**低估是危險方向**（撞 OOM），
# 高估只是 dpi 保守一點。擬合值為 (37, 2.52, 1.28)，這裡各加約一成，
# 使八個量測點全部不低估。日後量到新的點就回來調。
_PEAK_BASE_MB = 45.0
_PEAK_PER_PAGE_MB = 3.0
_PEAK_ACCUM_FACTOR = 1.40
DEFAULT_RASTER_BUDGET_MB = 250.0
DEFAULT_DPI = 150          # 線稿字帖夠用；A4 = 1240×1754
MIN_DPI = 96


class RasterBudgetExceeded(Exception):
    """連 :data:`MIN_DPI` 都塞不進配額——呼叫端轉 422 並附建議。"""


def _page_mb(w_mm: float, h_mm: float, dpi: int) -> float:
    """單頁光柵化後的裸像素量（MB，RGB 三通道）。"""
    return (w_mm / 25.4 * dpi) * (h_mm / 25.4 * dpi) * 3 / 1e6


def estimate_peak_mb(pages: int, w_mm: float, h_mm: float, dpi: int) -> float:
    """回傳光柵化 ``pages`` 頁的預估峰值記憶體（MB）。模型見模組註解。"""
    per = _page_mb(w_mm, h_mm, dpi)
    return (_PEAK_BASE_MB + _PEAK_PER_PAGE_MB * per
            + _PEAK_ACCUM_FACTOR * pages * per)


def fit_dpi_to_budget(
    pages: int, w_mm: float, h_mm: float, requested_dpi: int,
    *, budget_mb: float = DEFAULT_RASTER_BUDGET_MB, min_dpi: int = MIN_DPI,
) -> int:
    """求「峰值 ≤ budget」的最高 dpi，上限為 ``requested_dpi``。

    低於 ``min_dpi`` 就拋 :class:`RasterBudgetExceeded`——寧可明說做不到，
    也不要出一張糊到不能用的字帖。
    """
    if estimate_peak_mb(pages, w_mm, h_mm, requested_dpi) <= budget_mb:
        return requested_dpi
    # 峰值對 dpi 是純二次式（三項裡兩項都正比於單頁像素）→ 直接解
    per_dpi2 = ((_PEAK_PER_PAGE_MB + _PEAK_ACCUM_FACTOR * pages)
                * (w_mm / 25.4) * (h_mm / 25.4) * 3 / 1e6)
    room = budget_mb - _PEAK_BASE_MB
    if per_dpi2 <= 0 or room <= 0:
        raise RasterBudgetExceeded(
            f"{pages} 頁 × {w_mm:.0f}×{h_mm:.0f}mm 超出光柵化配額 "
            f"{budget_mb:.0f} MB")
    best = int((room / per_dpi2) ** 0.5)
    if best < min_dpi:
        raise RasterBudgetExceeded(
            f"{pages} 頁 × {w_mm:.0f}×{h_mm:.0f}mm 即使降到 {min_dpi} dpi "
            f"仍超出光柵化配額 {budget_mb:.0f} MB"
            f"（預估 {estimate_peak_mb(pages, w_mm, h_mm, min_dpi):.0f} MB）"
            "——請減少內容分批輸出，或改用 SVG／ZIP。")
    return min(requested_dpi, best)


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


# ---------------------------------------------------------------------
# W1：PDF／PNG
# ---------------------------------------------------------------------


def _rasterise(svg: str, px_w: int, px_h: int):
    """SVG → 白底 RGB ``PIL.Image``。

    5bk 的教訓照搬：SVG 預設透明底，cairosvg 吐 RGBA、未著墨處 alpha=0，
    直接 ``.convert("RGB")`` 在多數 PIL build 上會塌成**黑色**而非白色。
    兩層保險——(1) 叫 cairosvg 自己塗白底、(2) 轉檔前再合成到白布上。
    """
    import cairosvg
    from PIL import Image

    png_bytes = cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        output_width=px_w, output_height=px_h,
        background_color="white",
    )
    rgba = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    white = Image.new("RGB", rgba.size, "white")
    white.paste(rgba, mask=rgba.split()[3])   # alpha 當遮罩
    return white


def _page_size_mm(page: Page) -> tuple[float, float]:
    """頁面實體尺寸——頁面型模式（notebook/letter/manuscript）自帶。"""
    size = page.layout.size
    return float(size.width_mm), float(size.height_mm)


def render_pages_as_pdf(
    pages: list[Page],
    renderer: SvgRenderer,
    *,
    dpi: int = DEFAULT_DPI,
    budget_mb: float = DEFAULT_RASTER_BUDGET_MB,
    min_dpi: int = MIN_DPI,
    envelope_mode: str | None = None,
    app_version: str | None = None,
    envelope_params: dict | None = None,
) -> tuple[bytes, int]:
    """把所有頁面組成單一多頁 PDF。回傳 ``(pdf_bytes, dpi_used)``。

    ``dpi_used`` 可能小於 ``dpi``——配額不夠時自動下修（見模組註解）。
    呼叫端**必須**把它回報給使用者（`X-Pdf-Dpi-Used` 標頭），不要無聲
    降畫質。連 ``min_dpi`` 都塞不下則拋 :class:`RasterBudgetExceeded`。

    PDF 的頁面實體尺寸由 ``page.layout.size`` 決定，所以列印時 1:1 正確。
    """
    if not pages:
        raise ValueError("no pages to render")
    renderer = _wrap_with_envelope(
        renderer, envelope_mode, app_version, envelope_params)

    w_mm, h_mm = _page_size_mm(pages[0])
    dpi_used = fit_dpi_to_budget(
        len(pages), w_mm, h_mm, dpi, budget_mb=budget_mb, min_dpi=min_dpi)

    images = []
    for p in pages:
        pw_mm, ph_mm = _page_size_mm(p)
        px_w = max(1, int(round(pw_mm / 25.4 * dpi_used)))
        px_h = max(1, int(round(ph_mm / 25.4 * dpi_used)))
        images.append(_rasterise(renderer(p), px_w, px_h))

    buf = io.BytesIO()
    images[0].save(
        buf, format="PDF", save_all=True,
        append_images=images[1:],
        resolution=float(dpi_used),
    )
    return buf.getvalue(), dpi_used


def render_page_as_png(
    page: Page,
    renderer: SvgRenderer,
    *,
    dpi: int = DEFAULT_DPI,
    budget_mb: float = DEFAULT_RASTER_BUDGET_MB,
    min_dpi: int = MIN_DPI,
    envelope_mode: str | None = None,
    app_version: str | None = None,
    envelope_params: dict | None = None,
) -> tuple[bytes, int]:
    """單頁 PNG。回傳 ``(png_bytes, dpi_used)``——同 PDF 的配額語意。

    PNG 一次只出一頁（多頁請用 ``?page=N``，或改用 PDF）。
    """
    renderer = _wrap_with_envelope(
        renderer, envelope_mode, app_version, envelope_params)
    w_mm, h_mm = _page_size_mm(page)
    dpi_used = fit_dpi_to_budget(
        1, w_mm, h_mm, dpi, budget_mb=budget_mb, min_dpi=min_dpi)
    px_w = max(1, int(round(w_mm / 25.4 * dpi_used)))
    px_h = max(1, int(round(h_mm / 25.4 * dpi_used)))
    img = _rasterise(renderer(page), px_w, px_h)
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(dpi_used, dpi_used))
    return buf.getvalue(), dpi_used


_SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>", re.I)
_VIEWBOX_RE = re.compile(r'viewBox\s*=\s*"([^"]+)"', re.I)


def fit_svg_to_paper(
    svg: str, paper_w_mm: float, paper_h_mm: float, margin_mm: float,
) -> str:
    """把一張沒有實體尺寸的 SVG（如 grid 的 px 座標）貼進紙張、置中。

    grid 模式是**單張、px 座標、沒有分頁也沒有紙張概念**的自由尺寸字帖，
    和頁面型三模式不同——要出可列印的 PDF 就得先決定紙張。作法是包一層
    帶 mm 的外層 SVG，內層用巢狀 ``<svg preserveAspectRatio="xMidYMid
    meet">`` 讓渲染器自己等比縮放置中，**我們不自己算縮放數學**（少一個
    會算錯的地方）。

    找不到 ``viewBox`` 時原樣回傳——不假裝成功（§8）。
    """
    m = _SVG_OPEN_RE.search(svg)
    if not m:
        return svg
    vb = _VIEWBOX_RE.search(m.group(0))
    if not vb:
        return svg
    inner = svg[m.end():]
    if inner.rstrip().endswith("</svg>"):
        inner = inner.rstrip()[: -len("</svg>")]

    box_w = max(1.0, paper_w_mm - 2 * margin_mm)
    box_h = max(1.0, paper_h_mm - 2 * margin_mm)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {paper_w_mm} {paper_h_mm}" '
        f'width="{paper_w_mm}mm" height="{paper_h_mm}mm">'
        f'<rect x="0" y="0" width="{paper_w_mm}" height="{paper_h_mm}" '
        f'fill="white"/>'
        f'<svg x="{margin_mm}" y="{margin_mm}" '
        f'width="{box_w}" height="{box_h}" '
        f'viewBox="{vb.group(1)}" preserveAspectRatio="xMidYMid meet">'
        f'{inner}</svg></svg>'
    )


#: 紙張尺寸（mm）——grid 的 ``paper`` 參數用。
PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "a4": (210.0, 297.0),
    "a5": (148.0, 210.0),
    "letter": (215.9, 279.4),
}


def render_svg_as_pdf(
    svg: str, w_mm: float, h_mm: float,
    *,
    dpi: int = DEFAULT_DPI,
    budget_mb: float = DEFAULT_RASTER_BUDGET_MB,
    min_dpi: int = MIN_DPI,
) -> tuple[bytes, int]:
    """單張已帶實體尺寸的 SVG → 單頁 PDF（grid 走這條）。"""
    dpi_used = fit_dpi_to_budget(
        1, w_mm, h_mm, dpi, budget_mb=budget_mb, min_dpi=min_dpi)
    px_w = max(1, int(round(w_mm / 25.4 * dpi_used)))
    px_h = max(1, int(round(h_mm / 25.4 * dpi_used)))
    img = _rasterise(svg, px_w, px_h)
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=float(dpi_used))
    return buf.getvalue(), dpi_used


def render_svg_as_png(
    svg: str, w_mm: float, h_mm: float,
    *,
    dpi: int = DEFAULT_DPI,
    budget_mb: float = DEFAULT_RASTER_BUDGET_MB,
    min_dpi: int = MIN_DPI,
) -> tuple[bytes, int]:
    """單張已帶實體尺寸的 SVG → PNG（grid 走這條）。"""
    dpi_used = fit_dpi_to_budget(
        1, w_mm, h_mm, dpi, budget_mb=budget_mb, min_dpi=min_dpi)
    px_w = max(1, int(round(w_mm / 25.4 * dpi_used)))
    px_h = max(1, int(round(h_mm / 25.4 * dpi_used)))
    buf = io.BytesIO()
    _rasterise(svg, px_w, px_h).save(
        buf, format="PNG", dpi=(dpi_used, dpi_used))
    return buf.getvalue(), dpi_used


__all__ = [
    "DEFAULT_DPI",
    "DEFAULT_RASTER_BUDGET_MB",
    "MIN_DPI",
    "PAPER_SIZES_MM",
    "RasterBudgetExceeded",
    "estimate_peak_mb",
    "fit_dpi_to_budget",
    "fit_svg_to_paper",
    "render_page_as_png",
    "render_pages_as_pdf",
    "render_pages_as_single_or_zip",
    "render_pages_as_zip",
    "render_svg_as_pdf",
    "render_svg_as_png",
]
