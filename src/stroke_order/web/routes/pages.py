"""頁面殼（/、/card、/handwriting、/sutra-editor）＋card PDF＋vendor 同源代理＋health。

W3-R1（架構健檢 Wave 3）：自 server.py create_app() 機械搬遷，行為零變。
共用 helpers 暫由 ``..server`` 匯入（R2 收斂到專屬模組）。
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from fastapi import HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi import APIRouter
from ..responses import _content_disposition, _safe_filename_part
from ..versioning import STATIC_DIR, _versioned_page

_CARD_PDF_DENY = re.compile(
    r"(xlink:href|href\s*=|url\s*\(|<\s*(script|image|foreignObject|iframe|use|embed|object))",
    re.IGNORECASE,
)


class CardPdfRequest(BaseModel):
    svg: str
    filename: str = "card"


class PopupSvgRequest(BaseModel):
    upper: str
    lower: str = ""
    char_h_mm: float = 44.0
    roof_mm: float = 30.0
    tread_mm: float = 30.0
    cell_w_mm: float = 46.0
    card_w_mm: float = 210.0
    card_h_mm: float = 340.0


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


# 立體字卡片（pop-up 鏤空字）：獨立頁＋SVG 產生端點
@router.get("/popup", include_in_schema=False)
def popup_page():
    page = STATIC_DIR / "popup.html"
    if not page.is_file():
        return PlainTextResponse(
            "Pop-up page missing — static/popup.html not bundled.",
            status_code=404,
        )
    return _versioned_page(page)


@router.post("/api/popup/svg")
def popup_svg(req: PopupSvgRequest):
    upper = (req.upper or "").strip()
    if not upper:
        raise HTTPException(422, detail="上排文字不可為空")
    if len(upper) > 12 or len(req.lower or "") > 12:
        raise HTTPException(422, detail="每排文字最多 12 字")
    try:
        from ...exporters.popup import generate_popup, PopupParams
    except Exception as e:  # pragma: no cover
        raise HTTPException(503, detail=f"popup 模組不可用：{e}") from e
    P = PopupParams(
        card_w_mm=float(req.card_w_mm), card_h_mm=float(req.card_h_mm),
        char_h_mm=float(req.char_h_mm), roof_mm=float(req.roof_mm),
        tread_mm=float(req.tread_mm), cell_w_mm=float(req.cell_w_mm),
    )
    try:
        r = generate_popup(upper, (req.lower or "").strip(), P)
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from e
    except Exception as e:  # pragma: no cover
        from ...sources.g0v import CharacterNotFound
        if isinstance(e, CharacterNotFound):
            # R1a 後只剩「字型缺＋骨架字模也不可用（shapely 缺/缺字）」才到這
            raise HTTPException(
                503, detail="思源黑體字型未安裝（鏤空字需要）——"
                            "請執行 scripts/render_fetch_fonts.sh 或設 "
                            "STROKE_ORDER_HEI_FONT_FILE。",
            ) from e
        raise HTTPException(500, detail=f"產生失敗：{e}") from e
    # R1a 降級誠實標注（getattr 防禦：測試 monkeypatch 的替身可無此欄）
    glyph_source = getattr(r, "glyph_source", "noto_hei")
    # 5ft：SVG 內嵌 <popup-config> metadata（比照 mandala 的
    # <mandala-config>）——公眾分享庫以此驗證/分類立體字上傳
    import json as _json
    import re as _re
    _cfg = _json.dumps({
        "schema": "stroke-order-popup-v1",
        "upper": upper, "lower": (req.lower or "").strip(),
        "card_w_mm": float(req.card_w_mm), "card_h_mm": float(req.card_h_mm),
        "char_h_mm": float(req.char_h_mm), "roof_mm": float(req.roof_mm),
        "tread_mm": float(req.tread_mm), "cell_w_mm": float(req.cell_w_mm),
        "components": r.components, "bridges": r.bridges, "tiers": r.tiers,
    }, ensure_ascii=False)
    svg_out = _re.sub(
        r"(<svg\b[^>]*>)",
        lambda m: (m.group(1)
                   + "<metadata><popup-config><![CDATA["
                   + _cfg + "]]></popup-config></metadata>"),
        r.svg, count=1,
    )
    return {
        "svg": svg_out, "width_mm": r.width_mm, "height_mm": r.height_mm,
        "components": r.components, "bridges": r.bridges, "tiers": r.tiers,
        "glyph_source": glyph_source,
        "degraded": glyph_source != "noto_hei",
    }


# ---- Phase 5cj/5ck: OpenCV.js 同源代抓 --------------------------------
#
# 5cj：校網防火牆擋外部 CDN → 本伺服器代抓＋落地快取（同源永不被擋）。
# 5ck：使用者實測仍卡「產生中…」，兩個根因一起修：
#   ① 原端點 async def ＋ 同步 requests.get —— 下載 11MB 期間整個
#      event loop 被凍住，全站無回應（最壞 120s×2 來源）。
#   ② 惰性下載 —— Render 免費 tier 每次部署/喚醒後快取皆空，第一個
#      使用者要全程陪等。
# 修法：抓檔邏輯抽到模組層同步函式（threadpool 與背景執行緒共用）、
# 啟動時背景預熱、串流下載＋原子換檔、/vendor/status 可觀察性。

# 5cl：Render 實測 docs.opencv.org 對資料中心出站回 403（bot 防護；
# 4.x 還會轉跳 4.13.0 再 403）。改以 npm 鏡像為主源——
# @techstark/opencv-js 的 dist/opencv.js 是官方原檔（其 README
# 明載），bits 相同、CDN 對 hotlink/資料中心友善。
# docs.opencv.org 降末位備援並補瀏覽器 UA（其 403 疑似 UA 過濾）。
#
# 5da：家用機實測破案——4.9.0-release.3 的 WASM runtime init 在
# 新版 Chrome（149 實測）永久懸掛：importScripts 數百 ms 完成、
# cv Promise 永不 resolve；微型 WASM 模組同機秒過＝非 WASM 封鎖。
# 4.11.0-release.1 同機同管道 759ms 完整就緒（cv.Mat ready）。
# 回頭看，先前判定的「受管理電腦環境層懸掛」極可能一直就是這個
# 版本不相容。pin 升 4.11，且把版本寫進快取檔名——升級自動失效
# 舊快取（Render 燒入檔與本機 ~/.stroke-order/vendor 都適用）。
_OPENCV_VERSION = "4.11.0-release.1"
_OPENCV_CACHE_FNAME = "opencv-4.11.0.js"
# 5da：docs.opencv.org 退出清單——實測只掛 4.9.0/4.13.0（4.11.0
# 回 404），且它對資料中心 403（5cl）、4.9.0 又會懸掛；同源＋
# 兩個 npm CDN 已足（§8.2：實測不存在的 URL 不入 pin 清單）。
_OPENCV_SOURCES = (
    f"https://cdn.jsdelivr.net/npm/@techstark/opencv-js@{_OPENCV_VERSION}"
    "/dist/opencv.js",
    f"https://unpkg.com/@techstark/opencv-js@{_OPENCV_VERSION}"
    "/dist/opencv.js",
)
_OPENCV_FETCH_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
}
_OPENCV_MIN_BYTES = 1_000_000

# 5cn：opentype.js（MIT）——「自訂字型」瀏覽器端解析 TTF/OTF 用。
# 同一套同源代抓管線（校網/防火牆免疫、零執行期外網依賴給前端）。
_OPENTYPE_SOURCES = (
    "https://cdn.jsdelivr.net/npm/opentype.js@1.3.4/dist/opentype.min.js",
    "https://unpkg.com/opentype.js@1.3.4/dist/opentype.min.js",
)
_OPENTYPE_MIN_BYTES = 100_000
_vendor_fetch_lock = threading.Lock()
_opencv_prewarm_started = False


def _vendor_cache_path(fname: str) -> Path:
    vendor_dir = Path(os.environ.get(
        "STROKE_ORDER_VENDOR_DIR",
        str(Path.home() / ".stroke-order" / "vendor")))
    return vendor_dir / fname


def _opencv_cache_path() -> Path:
    # 5da：檔名帶版本——pin 升級自動失效舊快取
    return _vendor_cache_path(_OPENCV_CACHE_FNAME)


def _ensure_vendor_cached(fname: str, sources: tuple[str, ...],
                          min_bytes: int, timeout: float = 90.0) -> Path:
    """確保 vendor 檔已落地快取；缺檔時同步代抓（可重入）。

    - 快取命中：不進鎖直接回（熱路徑零開銷）。
    - 缺檔：單一執行緒下載（鎖防預熱與端點重複抓），串流寫入
      .part 暫存檔、驗尺寸後原子 replace——絕不 serve 半檔。
    """
    cache = _vendor_cache_path(fname)
    if cache.is_file() and cache.stat().st_size >= min_bytes:
        return cache
    import requests as _rq
    with _vendor_fetch_lock:
        if cache.is_file() and cache.stat().st_size >= min_bytes:
            return cache                    # 等鎖期間別人已抓完
        cache.parent.mkdir(parents=True, exist_ok=True)
        last_err: Optional[Exception] = None
        for url in sources:
            try:
                with _rq.get(url, timeout=(10, timeout), stream=True,
                             headers=_OPENCV_FETCH_HEADERS) as r:
                    r.raise_for_status()
                    tmp = cache.with_name(fname + ".part")
                    size = 0
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            f.write(chunk)
                            size += len(chunk)
                    if size < min_bytes:
                        raise ValueError(f"{fname} 過小：{size}B")
                    tmp.replace(cache)
                    return cache
            except Exception as e:          # noqa: BLE001 — 逐源重試
                last_err = e
        raise RuntimeError(f"{fname} 代抓失敗：{last_err}")


def _ensure_opencv_cached(timeout: float = 90.0) -> Path:
    return _ensure_vendor_cached(
        _OPENCV_CACHE_FNAME, _OPENCV_SOURCES, _OPENCV_MIN_BYTES, timeout)


def _ensure_opentype_cached(timeout: float = 90.0) -> Path:
    return _ensure_vendor_cached(
        "opentype.min.js", _OPENTYPE_SOURCES, _OPENTYPE_MIN_BYTES, timeout)


def _prewarm_opencv_cache() -> None:
    """5ck：啟動時背景預熱（daemon thread；失敗不影響服務，
    端點屆時會在 threadpool 內補抓）。每個行程只啟動一次。
    5cn：一併預熱 opentype.min.js。"""
    global _opencv_prewarm_started
    if _opencv_prewarm_started or os.environ.get("STROKE_ORDER_NO_PREFETCH"):
        return
    _opencv_prewarm_started = True

    def _job() -> None:
        for fn in (_ensure_opencv_cached, _ensure_opentype_cached):
            try:
                fn()
            except Exception:               # noqa: BLE001 — 預熱盡力而為
                pass

    threading.Thread(target=_job, name="vendor-prewarm", daemon=True).start()


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
