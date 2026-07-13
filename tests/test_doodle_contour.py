"""Phase 5ch — 塗鴉伺服器引擎 contour 輪廓向量化。

背景：使用者實測回報——同一張照片在 VectorLine 得到輪廓向量，
本專案（伺服器引擎）卻是掃描線圖。5ch 把取樣方式重設計為
Otsu 二值化 → 邊界追蹤 → RDP 閉合路徑，預設 contour、
scanline 降為選項。
"""
from __future__ import annotations

import io
import re

import numpy as np
import pytest
from PIL import Image, ImageDraw

from stroke_order.exporters.doodle import (
    _loop_area,
    _otsu_threshold,
    _simplify_loop,
    _trace_boundary_loops,
    render_doodle_svg,
)

try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS_WEB = True
except ImportError:
    _HAS_WEB = False


# ---------------------------------------------------------------------------
# 純函式單元
# ---------------------------------------------------------------------------


def test_square_traces_single_loop_rdp_4_corners():
    m = np.zeros((40, 40), bool)
    m[10:30, 8:32] = True
    loops = _trace_boundary_loops(m)
    assert len(loops) == 1
    assert abs(_loop_area(loops[0]) - 480) < 1e-9   # 24×20
    assert len(_simplify_loop(loops[0], 1.0)) == 4


def test_ring_traces_outer_and_hole():
    """甜甜圈 → 外框＋孔洞兩個獨立閉環。"""
    m = np.zeros((60, 60), bool)
    yy, xx = np.mgrid[0:60, 0:60]
    r = np.hypot(xx - 30, yy - 30)
    m[(r >= 10) & (r <= 20)] = True
    loops = _trace_boundary_loops(m)
    assert len(loops) == 2
    # 閉環 RDP 退化基線防護：簡化後仍是多邊形而非塌縮
    assert all(len(_simplify_loop(lp, 1.0)) >= 8 for lp in loops)


def test_otsu_threshold_bimodal():
    g = np.concatenate([np.full(500, 40, np.uint8),
                        np.full(500, 210, np.uint8)]).reshape(20, 50)
    assert 40 <= _otsu_threshold(g) < 210


def _shapes_img() -> Image.Image:
    img = Image.new("RGB", (300, 200), "white")
    d = ImageDraw.Draw(img)
    d.ellipse([30, 30, 130, 130], fill="black")
    d.rectangle([180, 60, 260, 160], outline="black", width=8)
    return img


def test_render_contour_default_emits_closed_paths():
    svg = render_doodle_svg(_shapes_img(), canvas_width_mm=150)
    paths = re.findall(r'<path d="M[^"]+Z"/>', svg)
    assert len(paths) == 3        # 圓 1 ＋ 方框外緣/內緣 2
    assert "<line " not in svg    # 不再是掃描線


def test_render_scanline_style_preserved():
    svg = render_doodle_svg(_shapes_img(), canvas_width_mm=150,
                            style="scanline")
    assert svg.count("<line ") > 20


def test_contour_and_scanline_share_mm_header():
    a = render_doodle_svg(_shapes_img(), canvas_width_mm=150)
    b = render_doodle_svg(_shapes_img(), canvas_width_mm=150,
                          style="scanline")
    assert a.split(">")[0] == b.split(">")[0]   # 5bt mm 契約不動


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

pytestmark_api = pytest.mark.skipif(
    not _HAS_WEB, reason="fastapi/httpx not installed")


@pytest.fixture(scope="module")
def client():
    if not _HAS_WEB:
        pytest.skip("fastapi/httpx not installed")
    return TestClient(create_app())


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    _shapes_img().save(buf, format="PNG")
    return buf.getvalue()


def test_api_doodle_default_is_contour(client):
    r = client.post("/api/doodle",
                    files={"image": ("t.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    assert '<path d="M' in r.text
    assert "<line " not in r.text


def test_api_doodle_scanline_opt_in(client):
    r = client.post("/api/doodle",
                    files={"image": ("t.png", _png_bytes(), "image/png")},
                    data={"vector_style": "scanline"})
    assert r.status_code == 200
    assert "<line " in r.text


def test_api_doodle_rejects_bad_style(client):
    r = client.post("/api/doodle",
                    files={"image": ("t.png", _png_bytes(), "image/png")},
                    data={"vector_style": "sketchy"})
    assert r.status_code == 422


def test_5ci_responsiveness_fixes(client):
    """5ci：使用者複驗回報「OpenCV 無回應／解析度差」的三項修復。"""
    html = client.get("/").text
    # ① 解析度：UI 預設 200 → 500（contour 在 200px 上描是糊的）
    assert 'id="dd-max-side" type="number" value="500"' in html
    # ② 巨量 SVG 不再 innerHTML 直塞（renderer frozen 40s 實測）——
    #    預覽改 <img src=blob> 光柵顯示
    assert "塗鴉預覽" in html
    assert 'im.src = url' in html
    js = client.get("/static/doodle_engine.js").text
    # ③ 可觀察性：載入講清楚在等什麼＋各階段進度
    #   （5cm 起下載進度以 MB 即時回報，取代「10~60 秒」約略句）
    assert "下載＋編譯 OpenCV.js" in js
    assert "下載 OpenCV.js… " in js          # 5cm：MB 進度
    assert "解碼與縮圖…" in js
    assert "二值化與輪廓抽取…" in js
    assert "條路徑）…" in js
    # ④ 大照片快徑：無裁切時跳過全解析度灰階
    assert "needCrop" in js


def test_5cj_vendor_proxy_and_same_origin_first(client, tmp_path,
                                                monkeypatch):
    """5cj：校網擋外部 CDN → OpenCV.js 改同源代抓。

    端點測試不打真網路：預先植入假快取檔（>1MB 門檻）驗證服務
    與快取標頭；引擎清單驗證同源位址排首位。
    """
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    from stroke_order.web.server import _OPENCV_CACHE_FNAME
    fake = b"/* fake opencv.js */" + b"x" * 1_100_000
    (vendor / _OPENCV_CACHE_FNAME).write_bytes(fake)     # 5da：檔名帶版本
    monkeypatch.setenv("STROKE_ORDER_VENDOR_DIR", str(vendor))
    r = client.get("/vendor/opencv.js")
    assert r.status_code == 200
    assert r.content == fake
    assert "max-age" in r.headers.get("cache-control", "")

    js = client.get("/static/doodle_engine.js").text
    urls_block = js.split("OPENCV_CDN_URLS = [")[1].split("]")[0]
    lines = [l.strip() for l in urls_block.splitlines() if '"' in l]
    # 5cm：同源位址絕對化（_ORIGIN 前綴），仍居首位
    assert '"/vendor/opencv.js"' in lines[0]            # 同源優先
    assert any("cdn.jsdelivr.net" in l for l in lines)  # CDN 備援仍在


def test_5ck_vendor_endpoint_is_sync_def(client):
    """5ck 回歸鎖：/vendor/opencv.js 必須是同步 def。

    async def＋同步 requests 會在下載 11MB 期間凍住整個
    event loop（全站無回應）——FastAPI 對同步 def 自動走
    threadpool，其他請求不受影響。
    """
    import inspect
    from stroke_order.web.server import create_app as _ca
    app = _ca()
    eps = [r.endpoint for r in app.routes
           if getattr(r, "path", "") == "/vendor/opencv.js"]
    assert eps, "vendor 端點不存在"
    assert not inspect.iscoroutinefunction(eps[0])


def test_5ck_startup_prewarm_registered():
    """5ck：startup 掛鉤存在（真啟動時背景預熱 opencv.js）。"""
    from stroke_order.web.server import create_app as _ca
    app = _ca()
    names = [getattr(f, "__name__", "") for f in app.router.on_startup]
    assert any("prewarm" in n for n in names)


def test_5ck_vendor_status_observability(client, tmp_path, monkeypatch):
    """5ck：/vendor/status 回報快取狀態（§8.1 降級可觀察性）。"""
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    monkeypatch.setenv("STROKE_ORDER_VENDOR_DIR", str(vendor))
    r = client.get("/vendor/status")
    assert r.status_code == 200
    body = r.json()
    assert body["opencv_cached"] is False and body["size"] == 0

    from stroke_order.web.server import _OPENCV_CACHE_FNAME
    fake = b"/* fake */" + b"x" * 1_100_000
    (vendor / _OPENCV_CACHE_FNAME).write_bytes(fake)     # 5da：檔名帶版本
    body = client.get("/vendor/status").json()
    assert body["opencv_cached"] is True and body["size"] == len(fake)
    assert "opentype_cached" in body            # 5cn：一併觀察 opentype


def test_5cl_fetch_sources_datacenter_friendly(client):
    """5cl：docs.opencv.org 對資料中心出站回 403（Render 實測）。

    伺服器抓取源以 jsDelivr 鏡像為主（@techstark/opencv-js 的
    dist/opencv.js＝官方原檔）、unpkg 次之、docs 降末位
    備援並補瀏覽器 UA；瀏覽器端備援清單第二位也加 jsDelivr
    （校網常放行 cdn.jsdelivr.net）。
    """
    from stroke_order.web.server import (
        _OPENCV_FETCH_HEADERS,
        _OPENCV_SOURCES,
    )
    assert "cdn.jsdelivr.net" in _OPENCV_SOURCES[0]
    # 5da：4.9.0 的 WASM init 在新 Chrome 懸掛（家用機實錘）→ 4.11
    assert "4.11.0" in _OPENCV_SOURCES[0]               # 版本 pin 不漂移
    # 5da：docs.opencv.org 退出清單（4.11.0 實測 404＋資料中心 403）
    assert all("docs.opencv.org" not in u for u in _OPENCV_SOURCES)
    assert len(_OPENCV_SOURCES) >= 2                    # 仍有備援
    assert "Mozilla/5.0" in _OPENCV_FETCH_HEADERS["User-Agent"]

    js = client.get("/static/doodle_engine.js").text
    urls_block = js.split("OPENCV_CDN_URLS = [")[1].split("];")[0]
    assert "cdn.jsdelivr.net" in urls_block            # 瀏覽器備援


def test_5cm_fetch_eval_watchdog_absolutized(client):
    """5cm：Chrome 實機解剖三修（校網環境「產生中…」永久卡死）。

    ① OPENCV_CDN_URLS 同源位址絕對化（location.origin）——相對
       路徑在 blob/巢狀 worker 的 base URL 下直接 SyntaxError，
       且正式 worker 內相對 importScripts 實測無限懸掛
    ② worker 端載入改 fetch＋間接 eval——importScripts 同步阻塞
       無法逾時，silent-drop 防火牆（校網）下永久懸掛；fetch 有
       chunk 間隔逾時＋MB 下載進度
    ③ 主執行緒 script tag 20s 逾時＋renderVia 90s 進度看門狗
       （terminate → 主執行緒降級 → 伺服器），恢復降級階梯
    """
    js = client.get("/static/doodle_engine.js").text
    assert "var _ORIGIN" in js
    assert '_ORIGIN + "/vendor/opencv.js"' in js        # ① 絕對化
    assert "_fetchScript" in js                          # ② fetch 看門狗
    assert "OPENCV_FETCH_STALL_MS" in js                 # ② chunk 逾時
    # ②' 5co：執行改回 importScripts（快取命中）——10MB 間接 eval
    #    在引擎情境實測 CPU 懸掛，禁止回歸
    assert "importScripts(url)" in js
    assert "(0, eval)(code)" not in js
    assert "OpenCV.js 載入逾時" in js                    # ③ script tag 逾時
    assert "worker 逾時無回應" in js                     # ③ 看門狗
    assert "clearStall" in js


def test_5cp_server_default_and_opencv_failure_memory(client):
    """5cp：受管理電腦環境層會卡死大型腳本執行（同 bytes 於 blob
    worker 正常）——體驗保底三件：預設伺服器引擎、OpenCV 標實驗性、
    session 失敗記憶自動改用伺服器。"""
    html = client.get("/").text
    assert '<option value="server" selected>' in html      # 預設伺服器
    assert "實驗性" in html                                 # opencv 降實驗
    assert 'sessionStorage.getItem("dd-opencv-broken")' in html
    assert 'sessionStorage.setItem("dd-opencv-broken"' in html
    js = client.get("/static/doodle_engine.js").text
    assert "worker 逾時無回應（30s）" in js                 # 看門狗收緊
    # 5cr：opencv 禁止主執行緒 fallback——主執行緒懸掛時 timer 全停
    # （看門狗無效）＝整頁凍死；worker 失敗直接拋給 UI 退伺服器
    assert "opencv 不退主執行緒" in js


def test_5cq_fetch_vendor_build_script(tmp_path, monkeypatch):
    """5cq：build-time 燒入——腳本復用 _ensure_vendor_cached、
    render.yaml 的 buildCommand 與 runtime env 指向同一路徑。
    （植入合法尺寸假檔＝快取命中，不打真網路。）"""
    import importlib.util
    from pathlib import Path as _P
    root = _P(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "fetch_vendor", root / "scripts" / "fetch_vendor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from stroke_order.web.server import _OPENCV_CACHE_FNAME
    vendor = tmp_path / "baked"
    vendor.mkdir()
    (vendor / _OPENCV_CACHE_FNAME).write_bytes(b"x" * 1_100_000)
    (vendor / "opentype.min.js").write_bytes(b"y" * 150_000)
    monkeypatch.setenv("STROKE_ORDER_VENDOR_DIR", str(vendor))
    assert mod.main([]) == 0                 # 快取命中、graceful 回 0

    ry = (root / "render.yaml").read_text("utf-8")
    assert "scripts/fetch_vendor.py" in ry               # build 端
    assert "STROKE_ORDER_VENDOR_DIR" in ry               # runtime 端
    assert "/opt/render/project/src/.vendor" in ry       # 同一路徑


def test_5ck_ensure_cached_hits_cache_without_network(tmp_path, monkeypatch):
    """5ck：快取命中時 _ensure_opencv_cached 不碰網路直接回。"""
    from stroke_order.web.server import (
        _OPENCV_CACHE_FNAME,
        _ensure_opencv_cached,
    )
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    fake = vendor / _OPENCV_CACHE_FNAME                  # 5da：檔名帶版本
    fake.write_bytes(b"y" * 1_200_000)
    monkeypatch.setenv("STROKE_ORDER_VENDOR_DIR", str(vendor))
    # 若走到網路分支會 import requests 打真連線；快取命中應直接回
    assert _ensure_opencv_cached() == fake


def test_index_has_style_select_and_cdn_fix(client):
    html = client.get("/").text
    assert 'id="dd-server-style"' in html
    assert 'value="contour"' in html
    js = client.get("/static/doodle_engine.js").text
    # 5ch：4.10.0 死連結修正 → 4.9.0 pin；5cl：4.x 移除（會轉跳
    # 漂移版本），備援改 jsDelivr 鏡像（見 test_5cl_*）
    assert "OPENCV_CDN_URLS" in js
    # 5da：4.9.0 WASM init 於新 Chrome 懸掛 → 4.11.0；docs.opencv.org
    # 退出清單（4.11.0 實測 404；註解提及版號 OK，URL 不行）
    assert "@techstark/opencv-js@4.11.0-release.1" in js
    assert "https://docs.opencv.org/" not in js
    assert "https://docs.opencv.org/4.x/opencv.js" not in js
