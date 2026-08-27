"""
W1 — 字帖四模式的多頁 PDF ／ PNG 輸出。

痛點：grid／notebook／letter／manuscript 原本只出 SVG／G-code／JSON，多頁
還只給 ZIP，老師要列印得先下載再自己拼；而抄經模式（routes/sutra.py）早就
有一條 SVG →(cairosvg) PNG →(Pillow) 多頁 PDF 的管線在生產跑。W1 把它下沉
到 exporters/multi_page.py 讓四個模式共用。

本檔的兩條核心不變式：
  · **零回歸**——format=svg 的輸出與 W1 之前逐位元組相同（四模式各驗）。
  · **配額模型不得低估**——低估會撞 Render 免費層的 OOM；八個實測點全部
    要落在模型之下（見 multi_page 模組註解的量測表）。

PDF 的檢查不引入新相依：``/Type /Page`` 次數與 ``/MediaBox`` 直接從原始
位元組解析（我們自己用 Pillow 產的 PDF，格式穩定）。
"""
from __future__ import annotations

import re

import pytest

# D3：本檔以光柵化/PDF 為主——整檔標 slow（開發可 -m 'not slow' 跳過）
pytestmark = pytest.mark.slow
from fastapi.testclient import TestClient

from stroke_order.exporters.multi_page import (
    DEFAULT_DPI,
    MIN_DPI,
    PAPER_SIZES_MM,
    RasterBudgetExceeded,
    estimate_peak_mb,
    fit_dpi_to_budget,
    fit_svg_to_paper,
)
from stroke_order.web.routes.modes_text import PAGED_FORMATS
from stroke_order.web.server import create_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def _pdf_pages(body: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", body))


def _pdf_mediabox_mm(body: bytes) -> tuple[float, float]:
    m = re.findall(rb"/MediaBox\s*\[([^\]]*)\]", body)
    assert m, "PDF 沒有 MediaBox"
    v = [float(x) for x in m[0].split()]
    return v[2] / 72 * 25.4, v[3] / 72 * 25.4


# ---------------------------------------------------------------------------
# 配額模型——低估是危險方向
# ---------------------------------------------------------------------------

#: 實測峰值 RSS（A4、各自獨立行程量 ru_maxrss）。模型只准高估，不准低估。
MEASURED_PEAKS = [
    (120, 10, 106), (150, 10, 136), (150, 27, 278),
    (200, 10, 214), (200, 20, 362), (200, 27, 465),
    (300, 5, 269), (300, 10, 435),
]


@pytest.mark.parametrize("dpi,pages,real_mb", MEASURED_PEAKS)
def test_w1_budget_model_never_underestimates(dpi, pages, real_mb):
    """模型低估 → 線上 OOM；高估只是 dpi 保守一點。只准往安全側錯。"""
    est = estimate_peak_mb(pages, 210, 297, dpi)
    assert est >= real_mb, (
        f"dpi {dpi} × {pages} 頁：模型 {est:.0f} MB 低於實測 {real_mb} MB"
        "——係數要調高（見 multi_page 模組註解）")


def test_w1_budget_model_is_monotonic():
    """頁數與 dpi 都只會讓峰值變大——模型形狀壞掉時這條先紅。"""
    base = estimate_peak_mb(5, 210, 297, 150)
    assert estimate_peak_mb(6, 210, 297, 150) > base
    assert estimate_peak_mb(5, 210, 297, 200) > base


def test_w1_dpi_clamps_down_as_pages_grow():
    dpis = [fit_dpi_to_budget(n, 210, 297, 300) for n in (1, 10, 20, 40)]
    assert dpis[0] == 300, "單頁不該被下修"
    assert dpis == sorted(dpis, reverse=True), f"下修不單調：{dpis}"
    for n, d in zip((1, 10, 20, 40), dpis):
        assert estimate_peak_mb(n, 210, 297, d) <= 250.0 + 1e-6


def test_w1_dpi_never_exceeds_request():
    """配額寬裕時不得「加碼」到超過使用者要的 dpi。"""
    assert fit_dpi_to_budget(1, 210, 297, 96) == 96


def test_w1_budget_rejects_when_even_min_dpi_overflows():
    with pytest.raises(RasterBudgetExceeded) as ei:
        fit_dpi_to_budget(500, 210, 297, 300)
    msg = str(ei.value)
    assert str(MIN_DPI) in msg
    assert "分批" in msg or "SVG" in msg, f"錯誤訊息要能行動：{msg}"


# ---------------------------------------------------------------------------
# fit_svg_to_paper——grid 專用
# ---------------------------------------------------------------------------


def test_w1_fit_svg_to_paper_wraps_with_mm_and_keeps_inner_viewbox():
    src = ('<svg xmlns="http://www.w3.org/2000/svg" width="360" height="360" '
           'viewBox="0 0 6144 6144"><circle cx="1" cy="1" r="1"/></svg>')
    out = fit_svg_to_paper(src, 210.0, 297.0, 10.0)
    head = re.search(r"<svg[^>]*>", out).group(0)
    assert 'width="210.0mm"' in head and 'height="297.0mm"' in head
    assert 'viewBox="0 0 6144 6144"' in out       # 內層原樣保留
    assert 'preserveAspectRatio="xMidYMid meet"' in out
    assert "<circle" in out
    # 內層擺在留白內
    inner = re.search(r'<svg x="10.0" y="10.0" width="([\d.]+)" '
                      r'height="([\d.]+)"', out)
    assert inner, out[:300]
    assert float(inner.group(1)) == pytest.approx(190.0)
    assert float(inner.group(2)) == pytest.approx(277.0)


def test_w1_fit_svg_to_paper_without_viewbox_returns_input():
    """沒有 viewBox 就沒有可靠的縮放依據——原樣回傳，不假裝成功（§8）。"""
    src = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
    assert fit_svg_to_paper(src, 210, 297, 10) == src


# ---------------------------------------------------------------------------
# 端點：PDF
# ---------------------------------------------------------------------------

_PAGED_CASES = [
    ("notebook", "/api/notebook", {"text": "春" * 300}),
    ("letter", "/api/letter", {"text": "春" * 200}),
    ("manuscript", "/api/manuscript", {"text": "春" * 400}),
]


@pytest.mark.parametrize("name,url,params", _PAGED_CASES)
def test_w1_paged_modes_emit_pdf_at_layout_size(client, name, url, params):
    r = client.get(url, params={**params, "format": "pdf"})
    assert r.status_code == 200, r.text[:300]
    assert r.headers["content-type"] == "application/pdf"
    body = r.content
    assert body[:5] == b"%PDF-"
    pages = int(r.headers["x-stroke-order-pages"])
    assert _pdf_pages(body) == pages, f"{name}：PDF 頁數與 layout 不符"
    w, h = _pdf_mediabox_mm(body)
    assert (w, h) == pytest.approx((210.0, 297.0), abs=0.5), (
        f"{name}：PDF 頁面實體尺寸不是 A4，列印會走鐘")


def test_w1_grid_pdf_fits_the_chosen_paper(client):
    for paper, (pw, ph) in PAPER_SIZES_MM.items():
        r = client.get("/api/grid",
                       params={"chars": "春夏秋冬", "format": "pdf",
                               "paper": paper})
        assert r.status_code == 200, r.text[:200]
        assert r.headers["x-paper"] == paper
        w, h = _pdf_mediabox_mm(r.content)
        assert (w, h) == pytest.approx((pw, ph), abs=0.5), paper
        assert _pdf_pages(r.content) == 1


def test_w1_grid_pdf_ink_stays_inside_the_margin(client):
    """貼合紙張不得裁切——墨跡必須完全落在留白之內。

    用 PNG 量（PDF 內是同一張光柵）：掃出非白像素的 bbox，換算回 mm 後
    與 margin 比。這條擋的是 preserveAspectRatio 寫錯方向（slice 會裁切）。
    """
    np = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    margin = 10.0
    r = client.get("/api/grid",
                   params={"chars": "春夏秋冬", "format": "png",
                           "paper": "a4", "margin_mm": margin, "dpi": 96})
    assert r.status_code == 200, r.text[:200]
    import io
    img = np.array(Image.open(io.BytesIO(r.content)).convert("L"))
    h_px, w_px = img.shape
    ink = np.argwhere(img < 200)
    assert ink.size, "整張都是白的——沒畫到東西"
    top, left = ink.min(axis=0)
    bottom, right = ink.max(axis=0)
    mm_x = 210.0 / w_px
    mm_y = 297.0 / h_px
    assert left * mm_x >= margin - 1.0, "左側超出留白（被裁切？）"
    assert (w_px - right) * mm_x >= margin - 1.0, "右側超出留白"
    assert top * mm_y >= margin - 1.0, "上緣超出留白"
    assert (h_px - bottom) * mm_y >= margin - 1.0, "下緣超出留白"


def test_w1_pdf_reports_requested_and_used_dpi(client):
    r = client.get("/api/notebook",
                   params={"text": "春" * 300, "format": "pdf", "dpi": 200})
    assert r.status_code == 200
    assert r.headers["x-pdf-dpi-requested"] == "200"
    assert int(r.headers["x-pdf-dpi-used"]) <= 200


def test_w1_pdf_clamps_dpi_on_long_documents_and_says_so(client):
    """頁多時自動下修，而且**一定回報**——不無聲降畫質（§86）。"""
    r = client.get("/api/notebook",
                   params={"text": "春" * 3800, "format": "pdf", "dpi": 300})
    assert r.status_code == 200, r.text[:300]
    pages = int(r.headers["x-stroke-order-pages"])
    assert pages >= 10, f"樣本太短，測不到下修（{pages} 頁）"
    used = int(r.headers["x-pdf-dpi-used"])
    assert r.headers["x-pdf-dpi-requested"] == "300"
    assert used < 300, "頁數這麼多卻沒下修——配額沒生效？"
    assert used >= MIN_DPI
    assert estimate_peak_mb(pages, 210, 297, used) <= 250.0 + 1e-6


# ---------------------------------------------------------------------------
# 端點：PNG
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,url,params", _PAGED_CASES)
def test_w1_paged_modes_emit_png(client, name, url, params):
    r = client.get(url, params={**params, "format": "png"})
    assert r.status_code == 200, r.text[:300]
    assert r.headers["content-type"] == "image/png"
    assert r.content[:4] == b"\x89PNG"


def test_w1_png_honours_page_param(client):
    """PNG 一次一頁，沿用既有 ?page=N；不給就出第 1 頁。"""
    p = {"text": "春" * 300, "format": "png"}
    r1 = client.get("/api/notebook", params=p)
    r2 = client.get("/api/notebook", params={**p, "page": 1})
    r3 = client.get("/api/notebook", params={**p, "page": 2})
    assert r1.status_code == r2.status_code == r3.status_code == 200
    assert r1.content == r2.content, "不給 page 應等同 page=1"
    assert r3.content != r1.content, "page=2 應是不同的一頁"


def test_w1_png_out_of_range_page_is_404(client):
    r = client.get("/api/notebook",
                   params={"text": "春", "format": "png", "page": 99})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 零回歸與接線 parity
# ---------------------------------------------------------------------------

_SVG_CASES = _PAGED_CASES + [("grid", "/api/grid", {"chars": "春夏秋冬"})]


@pytest.mark.parametrize("name,url,params", _SVG_CASES)
def test_w1_svg_path_is_untouched(client, name, url, params):
    """W1 只加格式，既有 SVG 路徑一個位元組都不許動。

    同一組參數請求兩次（含/不含顯式 format=svg）須完全相同，且不得帶上
    只屬於光柵路徑的標頭。
    """
    a = client.get(url, params=params)
    b = client.get(url, params={**params, "format": "svg"})
    assert a.status_code == b.status_code == 200
    assert "x-pdf-dpi-used" not in {k.lower() for k in a.headers}
    # 既有分派不變：單頁出 SVG、多頁仍打包成 ZIP（W1 沒有動這條）
    pages = int(a.headers.get("x-stroke-order-pages", "1"))
    if pages > 1:
        assert a.content[:4] == b"PK\x03\x04", f"{name}：多頁應維持 ZIP"
        assert a.headers["content-type"] == "application/zip"
        # ZIP 標頭內嵌建檔時間，兩次請求的**位元組**本來就會差（跨過
        # DOS 時戳的 2 秒粒度時）——比的是解開後的內容，不是容器位元組。
        # （鎖不變式、不鎖實作巧合：§66。）
        import io
        import zipfile

        def entries(raw):
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                return {n: z.read(n) for n in sorted(z.namelist())}

        assert entries(a.content) == entries(b.content), name
    else:
        assert a.content == b.content
        assert a.content.lstrip()[:4] == b"<svg", name


def test_w1_format_pattern_matches_actual_handlers():
    """`format` 值域 ≡ 真的有 handler 的格式集合。

    防「pattern 加了格式但沒寫分支」——那會靜默回傳 SVG，使用者拿到副檔名
    是 pdf 的 SVG 檔。承 S1／R1b 的 parity 鎖形態。
    """
    from stroke_order.web.routes import modes_text as mt
    src = __import__("pathlib").Path(mt.__file__).read_text("utf-8")
    for fmt in PAGED_FORMATS:
        if fmt == "svg":
            continue          # 預設路徑，沒有 == 分支
        assert f'== "{fmt}"' in src or f'("pdf", "png")' in src, (
            f"format={fmt} 在值域裡卻找不到 handler 分支")


@pytest.mark.parametrize("url", ["/api/notebook", "/api/letter",
                                 "/api/manuscript", "/api/grid"])
def test_w1_all_four_modes_accept_the_same_formats(client, url):
    """四個模式的 format 值域一致——不要有人少接一種。"""
    key = "chars" if url.endswith("grid") else "text"
    for fmt in PAGED_FORMATS:
        r = client.get(url, params={key: "春", "format": fmt})
        assert r.status_code == 200, (url, fmt, r.text[:200])


def test_w1_unknown_format_still_rejected(client):
    r = client.get("/api/notebook", params={"text": "春", "format": "tiff"})
    assert r.status_code == 422


def test_w1_default_dpi_is_the_shared_constant(client):
    """端點預設 dpi ≡ exporters 的 DEFAULT_DPI（不要兩處各寫一個數）。"""
    r = client.get("/api/grid", params={"chars": "春", "format": "pdf"})
    assert r.status_code == 200
    assert r.headers["x-pdf-dpi-requested"] == str(DEFAULT_DPI)
