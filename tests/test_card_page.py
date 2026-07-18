"""5et 手寫卡片模式：頁面路由與靜態資產契約。"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.web.server import create_app, STATIC_DIR


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_card_page_serves(client):
    r = client.get("/card")
    assert r.status_code == 200
    assert "手寫卡片" in r.text
    assert "/static/card/main.js" in r.text


def test_card_static_modules_exist():
    base = Path(STATIC_DIR) / "card"
    for name in ("main.js", "geometry.js", "model.js", "render.js", "glyphs.js"):
        assert (base / name).is_file(), f"static/card/{name} 缺檔"


def test_index_links_card(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'href="/card"' in r.text


def test_card_reference_style_endpoint_available(client):
    """R2 內建風格 provider 依賴的端點（5d-7 既有）仍供貨。"""
    r = client.get("/api/handwriting/reference/永", params={"style": "kaishu"})
    assert r.status_code == 200
    data = r.json()
    assert data["em_size"] == 2048
    assert isinstance(data["strokes"], list)


def test_card_pdf_endpoint(client):
    """R4：SVG→PDF 轉檔（cairosvg）＋安全拒收契約。"""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="96mm" height="58mm"'
        ' viewBox="0 0 96 58"><rect width="96" height="58" fill="#fff"/>'
        '<path d="M10 10L80 40" stroke="#000" stroke-width="1"/></svg>'
    )
    r = client.post("/api/card/pdf", json={"svg": svg, "filename": "測試卡"})
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")
    assert r.headers["content-type"] == "application/pdf"


def test_card_pdf_rejects_external_refs(client):
    """SSRF 面：href/url()/script/image 一律 422。"""
    bad = [
        '<svg xmlns="x"><image href="http://evil/x.png"/></svg>',
        '<svg xmlns="x"><script>1</script></svg>',
        '<svg xmlns="x"><rect style="fill:url(#g)"/></svg>',
        '<svg xmlns="x"><use xlink:href="#a"/></svg>',
        "not svg at all",
    ]
    for svg in bad:
        r = client.post("/api/card/pdf", json={"svg": svg})
        assert r.status_code == 422, svg


def test_card_pdf_size_limit(client):
    r = client.post("/api/card/pdf", json={"svg": "<svg" + "x" * 2_100_000})
    assert r.status_code == 413
