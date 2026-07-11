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
    # browser 為預設引擎；server 為備援選項
    assert 'value="browser" selected' in html
    assert 'value="server"' in html


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
    # CDN 惰性載入且版本 pin 死（可重現性）
    assert "https://docs.opencv.org/4.10.0/opencv.js" in body


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
