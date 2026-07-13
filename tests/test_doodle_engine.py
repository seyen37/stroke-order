"""Phase 5ca — 塗鴉模式前端化（瀏覽器引擎 + 可切換架構）。

doodle_engine.js 的演算法正確性由 scripts/verify_doodle_parity.{cjs,py}
（node × Python 結構比對）把關；此處鎖三件事：

1. 靜態檔可服務、核心 API 符號存在（B 輪 opencv 引擎要掛同一張表）
2. index.html 有引擎切換 UI 與 script 載入
3. /api/doodle 伺服器端點原樣保留（fallback 路徑）
"""
import pytest

try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS_WEB = True
except ImportError:
    _HAS_WEB = False

pytestmark = pytest.mark.skipif(
    not _HAS_WEB, reason="fastapi/httpx not installed"
)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_doodle_engine_js_serves(client):
    r = client.get("/static/doodle_engine.js")
    assert r.status_code == 200
    body = r.text
    # 引擎表：browser / server 兩引擎 + node 匯出（parity 驗證入口）
    assert "DoodleEngines" in body
    assert '"browser"' in body or "browser:" in body
    assert "module.exports" in body


def test_doodle_engine_core_symbols_locked(client):
    """核心純函式是 5cb（opencv 引擎）與 parity 腳本的公開介面。"""
    body = client.get("/static/doodle_engine.js").text
    for sym in ("grayscale", "autocontrast", "findEdges", "rleRows",
                "autoCropBox", "buildDoodleSvg"):
        assert sym in body, f"doodle_engine.js 缺少核心符號 {sym}"


def test_index_has_engine_selector(client):
    html = client.get("/").text
    assert 'id="dd-engine"' in html
    assert '/static/doodle_engine.js' in html
    # 5cp：server 為預設（受管理電腦環境層卡死大型腳本執行）；
    # browser/opencv 仍為選項
    assert 'value="server" selected' in html
    assert 'value="browser"' in html
    assert 'value="opencv"' in html


def test_index_links_vectorline(client):
    """REF_ANALYSIS_VECTORLINE 社群互連項：塗鴉模式導流描線工坊。"""
    html = client.get("/").text
    assert "vector-line.vercel.app" in html


# ---------------------------------------------------------------------------
# Phase 5cb — OpenCV.js 引擎
# ---------------------------------------------------------------------------

def test_5cb_opencv_engine_registered(client):
    body = client.get("/static/doodle_engine.js").text
    assert "opencv:" in body
    assert "loadOpenCV" in body
    assert "renderInOpenCV" in body
    # CDN 惰性載入且版本 pin 死（可重現性）；5ch：4.10.0 實測 404
    # → 4.9.0；5da：4.9.0 WASM init 於新 Chrome 懸掛 → 4.11.0、
    # docs.opencv.org 退出清單（詳細斷言見 test_doodle_contour.py）
    assert "@techstark/opencv-js@4.11.0-release.1" in body


def test_5cb_opencv_pipeline_symbols(client):
    """輪廓管線關鍵步驟鎖定：二值化→去斑→輪廓→簡化。"""
    body = client.get("/static/doodle_engine.js").text
    for sym in ("adaptiveThreshold", "morphologyEx", "findContours",
                "approxPolyDP", "Canny", "contoursToSvg"):
        assert sym in body, f"doodle_engine.js 缺少 opencv 管線符號 {sym}"


def test_5cb_index_has_opencv_option_and_params(client):
    html = client.get("/").text
    assert 'value="opencv"' in html
    assert 'id="dd-cv-params"' in html
    for pid in ("dd-cv-mode", "dd-cv-block", "dd-cv-c", "dd-cv-invert",
                "dd-cv-simplify", "dd-cv-minarea", "dd-cv-maxside"):
        assert f'id="{pid}"' in html, f"index.html 缺少 OpenCV 參數 {pid}"


# ---------------------------------------------------------------------------
# Phase 5cf — Web Worker 卸載
# ---------------------------------------------------------------------------


def test_5cf_worker_shell_serves(client):
    r = client.get("/static/doodle_worker.js")
    assert r.status_code == 200
    body = r.text
    # 5cj：?v= cache-busting（舊快取 JS 會殘留死 CDN 位址）
    assert 'importScripts("/static/doodle_engine.js?v=' in body
    assert "self.onmessage" in body
    # message 協定三態：status／ok:true／ok:false
    assert "status: msg" in body
    assert "ok: true" in body and "ok: false" in body


def test_5cf_engine_has_worker_offload(client):
    body = client.get("/static/doodle_engine.js").text
    assert "renderVia" in body
    assert "workerSupported" in body
    assert '"/static/doodle_worker.js?v=' in body   # 5cj cache-bust
    # loadOpenCV 的 Worker 分支；5cm fetch 看門狗＋5co 執行回
    # importScripts(絕對 URL)——fetch 先驗可達＋暖快取（可逾時），
    # importScripts 走快取執行（10MB eval 實測會 CPU 懸掛）
    assert "_fetchScript(" in body
    assert "importScripts(url)" in body


def test_5cf_index_routes_through_render_via(client):
    html = client.get("/").text
    assert "mod.renderVia(engineVal, file, opts)" in html


# ---------------------------------------------------------------------------
# Phase 5cg — centerline 骨架化
# ---------------------------------------------------------------------------


def test_5cg_engine_has_skeleton_trio(client):
    """三件組純函式（node 功能測試把關演算法正確性；此處鎖符號）。"""
    body = client.get("/static/doodle_engine.js").text
    for sym in ("zhangSuenThin", "traceCenterlines", "rdpSimplify"):
        assert sym in body, f"doodle_engine.js 缺少 {sym}"
    # 對角修剪（假交叉點的關鍵修正）與骨架化進度回報
    assert "對角" in body
    assert "骨架化中" in body


def test_5cg_centerline_mode_wired(client):
    """centerline 走二值化＋去斑後的骨架分支，輸出開放路徑。"""
    body = client.get("/static/doodle_engine.js").text
    assert 'mode === "centerline"' in body


def test_5cg_index_has_centerline_option(client):
    html = client.get("/").text
    assert 'value="centerline"' in html
