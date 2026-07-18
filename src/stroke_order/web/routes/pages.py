"""頁面殼（/、/card、/handwriting、/sutra-editor）＋card PDF＋vendor 同源代理＋health。

W3-R1（架構健檢 Wave 3）：自 server.py create_app() 機械搬遷，行為零變。
共用 helpers 暫由 ``..server`` 匯入（R2 收斂到專屬模組）。
"""
from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi import APIRouter
from ..server import (
    CardPdfRequest,
    STATIC_DIR,
    _CARD_PDF_DENY,
    _OPENCV_MIN_BYTES,
    _OPENTYPE_MIN_BYTES,
    _content_disposition,
    _ensure_opencv_cached,
    _ensure_opentype_cached,
    _opencv_cache_path,
    _prewarm_opencv_cache,
    _safe_filename_part,
    _vendor_cache_path,
    _versioned_page,
)

router = APIRouter()

# ------ root index ---------------------------------------------------

@router.get("/", include_in_schema=False)
def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        return PlainTextResponse(
            "Web UI not bundled. See source at /api/character/{char}",
            status_code=200,
        )
    return _versioned_page(index_path)

# 5bd: dedicated full-screen sutra editor (subpage)
@router.get("/sutra-editor", include_in_schema=False)
def sutra_editor_page():
    page = STATIC_DIR / "sutra-editor.html"
    if not page.is_file():
        return PlainTextResponse(
            "Editor page missing — static/sutra-editor.html not bundled.",
            status_code=404,
        )
    return _versioned_page(page)

# 5d-1: dedicated handwriting practice page (PSD — Personal Stroke
# Database). Independent web app; collects stroke trajectories with
# timestamps + pressure + tilt for driving handwriting robots,
# especially valuable for fonts that lack real stroke-order data
# (隸書 / 篆書 / 草書 / 行書).
@router.get("/handwriting", include_in_schema=False)
def handwriting_page():
    page = STATIC_DIR / "handwriting.html"
    if not page.is_file():
        return PlainTextResponse(
            "Handwriting practice page missing — "
            "static/handwriting.html not bundled.",
            status_code=404,
        )
    return _versioned_page(page)

# 5et: 手寫卡片編輯器（獨立頁，ES modules——照 handwriting/ 慣例）
@router.get("/card", include_in_schema=False)
def card_page():
    page = STATIC_DIR / "card.html"
    if not page.is_file():
        return PlainTextResponse(
            "Card editor page missing — static/card.html not bundled.",
            status_code=404,
        )
    return _versioned_page(page)

# 5et-R4：卡片印刷 PDF——前端組好含出血/裁切標記的 SVG，此端點只做
# SVG→PDF 轉檔（cairosvg，與抄經 PDF 同管線）。安全：拒收任何外部
# 參照/腳本模式（防 SSRF/XXE 面）；正常前端產物不含這些字樣。
@router.post("/api/card/pdf")
def card_pdf(req: CardPdfRequest):
    svg = req.svg.strip()
    if len(svg) > 2_000_000:
        raise HTTPException(413, detail="SVG 過大（>2MB）")
    if not svg.startswith("<svg"):
        raise HTTPException(422, detail="不是 SVG 內容")
    m = _CARD_PDF_DENY.search(svg)
    if m:
        raise HTTPException(
            422,
            detail=f"SVG 含不允許的外部參照/腳本模式（{m.group(0)!r}）",
        )
    try:
        import cairosvg
    except ImportError as e:
        raise HTTPException(503, detail=f"cairosvg 不可用：{e}") from e
    try:
        pdf_bytes = cairosvg.svg2pdf(bytestring=svg.encode("utf-8"))
    except Exception as e:
        raise HTTPException(422, detail=f"SVG 轉 PDF 失敗：{e}") from e
    safe = _safe_filename_part(req.filename) or "card"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": _content_disposition(safe, "pdf"),
        },
    )


async def _startup_prewarm_opencv():    # pragma: no cover — 真啟動才跑
    """5ck：真伺服器啟動（uvicorn）即背景預抓 opencv.js。

    TestClient 不進 context manager 不觸發 startup——測試零干擾。
    直接掛 router.on_startup（@router.on_event 已 deprecated，
    每次 create_app 都會吐警告——測試噪音）。
    """
    _prewarm_opencv_cache()

router.on_startup.append(_startup_prewarm_opencv)

@router.get("/vendor/opencv.js")
def vendor_opencv():
    """Phase 5cj/5ck：OpenCV.js 同源代理＋落地快取。

    5cj：校園/企業防火牆擋外部網域（docs.opencv.org 被靜默
    丟包時瀏覽器連 onerror 都等不到）→ 本伺服器代抓，同源
    載入永不被擋。
    5ck：改「同步 def」——FastAPI 自動丟 threadpool，缺檔補抓
    時不再凍住 event loop（原 async def＋同步 requests 會讓
    全站無回應）。啟動預熱後此處通常直接命中快取。
    """
    try:
        cache = _ensure_opencv_cached()
    except Exception as e:              # noqa: BLE001
        raise HTTPException(
            502, detail=f"伺服器代抓 opencv.js 失敗：{e}")
    return FileResponse(
        cache, media_type="text/javascript",
        headers={"Cache-Control": "public, max-age=604800"})

@router.get("/vendor/opentype.min.js")
def vendor_opentype():
    """5cn：opentype.js（MIT）同源代理——自訂字型前端解析用。"""
    try:
        cache = _ensure_opentype_cached()
    except Exception as e:              # noqa: BLE001
        raise HTTPException(
            502, detail=f"伺服器代抓 opentype.min.js 失敗：{e}")
    return FileResponse(
        cache, media_type="text/javascript",
        headers={"Cache-Control": "public, max-age=604800"})

@router.get("/vendor/status")
def vendor_status():
    """5ck：快取可觀察性（PRINCIPLES §8.1）——預熱狀態一眼可查。"""
    cache = _opencv_cache_path()
    size = cache.stat().st_size if cache.is_file() else 0
    ot = _vendor_cache_path("opentype.min.js")
    ot_size = ot.stat().st_size if ot.is_file() else 0
    return {"opencv_cached": size >= _OPENCV_MIN_BYTES, "size": size,
            "opentype_cached": ot_size >= _OPENTYPE_MIN_BYTES,
            "opentype_size": ot_size}


# ------ health ------------------------------------------------------

@router.get("/api/health")
def health():
    return {"ok": True, "version": "0.3.0"}
