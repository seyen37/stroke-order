"""
v0.14.299 P2——/myfont「寫你的名字→得到字型」頁。

互動流程由 Playwright 端到端驗過（WORK_LOG／ADR 記錄）；本檔鎖住頁面契約：
路由與版本注入、自包含（無外連）、誠實措辭（筆跡不上傳保存、只有寫過的字、
著作權歸書寫者）、只走無狀態端點（不碰共用字庫）、前後端上限 parity、
/guide 入口與舊說法修正、計數掛點。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.web import metrics
from stroke_order.web.routes import user_dict as ud
from stroke_order.web.server import create_app

_ROOT = Path(__file__).resolve().parent.parent
_STATIC = _ROOT / "src" / "stroke_order" / "web" / "static"
_PAGE = _STATIC / "myfont.html"
_CORE = _STATIC / "myfont" / "core.mjs"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_METRICS_DIR", str(tmp_path))
    metrics.reset_for_tests()
    yield TestClient(create_app())
    metrics.reset_for_tests()


def test_page_serves_with_version_injected(client):
    r = client.get("/myfont")
    assert r.status_code == 200
    assert "寫你的名字" in r.text
    assert "__V__" not in r.text, "ES module 匯入鏈要帶版本（§67）"
    assert re.search(r"/static/myfont/core\.mjs\?v=\d", r.text)
    assert re.search(r"/static/handwriting/canvas\.js\?v=\d", r.text)


def test_core_module_served(client):
    r = client.get("/static/myfont/core.mjs")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]


def test_page_is_self_contained():
    page = _PAGE.read_text("utf-8")
    assert "http://" not in page and "https://" not in page


def test_page_uses_only_stateless_endpoint():
    """手寫只走 POST /api/handfont；不得寫入共用字庫（P0 的承諾）。"""
    page = _PAGE.read_text("utf-8")
    assert "'/api/handfont'" in page
    assert "/api/user-dict" not in page
    assert "syncTraceToUserDict" not in page and "saveDual" not in page


def test_page_honesty_statements():
    page = _PAGE.read_text("utf-8")
    assert "伺服器不保存" in page
    assert "只有你寫過的字" in page
    assert "著作權歸書寫者" in page
    assert "換裝置不會跟著走" in page


def test_download_disabled_until_success():
    page = _PAGE.read_text("utf-8")
    i = page.index('id="mf-download"')
    assert 'aria-disabled="true"' in page[i - 80:i + 120]


def test_limits_parity_with_server():
    core = _CORE.read_text("utf-8")
    m = re.search(r"export const MAX_TOTAL_CHARS = (\d+);", core)
    assert m and int(m.group(1)) == ud.HANDFONT_MAX_CHARS
    t = re.search(r"export const THIN_MIN_DIST = (\d+);", core)
    assert t and 0 < int(t.group(1)) <= 16, "精簡門檻要肉眼無差"


def test_guide_links_myfont_and_drops_stale_claim():
    g = (_STATIC / "guide.html").read_text("utf-8")
    assert 'href="/myfont"' in g
    assert "在手寫練習裡寫過的字，可以一鍵打包" not in g, "P0 後公開站已不成立"
    assert "伺服器不保存" in g


def test_page_view_counted(client):
    client.get("/myfont")
    assert client.get("/api/metrics").json()["mode"].get("myfont_page") == 1


def test_canvas_has_load_strokes():
    js = (_STATIC / "handwriting" / "canvas.js").read_text("utf-8")
    assert "loadStrokes(strokes)" in js
