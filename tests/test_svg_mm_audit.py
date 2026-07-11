"""Phase 5bt: SVG mm 尺寸 audit — 物理尺寸契約測試.

鎖住不變量：凡宣告 mm 實體尺寸的 SVG 端點，width/height 數值必須
等於 viewBox 跨度（1 user unit = 1 mm），否則雷切/繪圖軟體匯入時
會整體縮放（歷史案例：印章 viewBox 描邊 pad 未同步 width，25mm
章匯入變 24.4mm）。
"""
from __future__ import annotations

import re

import pytest


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from stroke_order.web.server import app
    return TestClient(app)


def _root(client, url):
    r = client.get(url)
    assert r.status_code == 200, f"{url} → {r.status_code}"
    m = re.search(r"<svg[^>]*>", r.text)
    assert m, f"{url}: no <svg> root"
    return m.group(0)


def _attr(tag, name):
    m = re.search(rf'{name}="([^"]+)"', tag)
    return m.group(1) if m else None


#: 宣告 mm 實體尺寸的端點（機器/列印導向）
MM_ENDPOINTS = [
    ("notebook",    "/api/notebook?text=永&format=svg"),
    ("letter",      "/api/letter?text=永&format=svg"),
    ("manuscript",  "/api/manuscript?text=永&format=svg"),
    ("wordart",     "/api/wordart?text=永字八法&format=svg"),
    ("mandala",     "/api/mandala?center_char=永&ring_text=八法&format=svg"),
    ("patch",       "/api/patch?text=吉&format=svg"),
    ("stamp",       "/api/stamp?text=吉&preset=square_name&format=svg"),
    ("stamp_oval",  "/api/stamp?text=吉&preset=oval&format=svg"),
    ("stamp_saw",   "/api/stamp?text=吉&preset=round&format=svg&oval_sawtooth=true"),
    ("sutra_body",  "/api/sutra?preset=chinese_numerals&page_type=body"),
    ("sutra_table", "/api/sutra?preset=cangjie_roots&page_type=table"),
]


@pytest.mark.parametrize("name,url", MM_ENDPOINTS,
                         ids=[n for n, _u in MM_ENDPOINTS])
def test_mm_width_matches_viewbox_span(client, name, url):
    tag = _root(client, url)
    w, h, vb = _attr(tag, "width"), _attr(tag, "height"), _attr(tag, "viewBox")
    assert w and w.endswith("mm"), f"{name}: width={w!r} 非 mm"
    assert h and h.endswith("mm"), f"{name}: height={h!r} 非 mm"
    assert vb, f"{name}: 缺 viewBox"
    _x0, _y0, vb_w, vb_h = (float(v) for v in vb.split())
    assert abs(float(w[:-2]) - vb_w) < 1e-3, \
        f"{name}: width {w} ≠ viewBox 跨度 {vb_w}（匯入會縮放）"
    assert abs(float(h[:-2]) - vb_h) < 1e-3, \
        f"{name}: height {h} ≠ viewBox 跨度 {vb_h}"


def test_export_default_stays_px(client):
    """Web 預覽相容：未給 size_mm 時維持既有 300px。"""
    tag = _root(client, "/api/export/永?format=svg")
    assert _attr(tag, "width") == "300"
    assert _attr(tag, "viewBox") == "0 0 2048 2048"


def test_export_size_mm_opt_in(client):
    tag = _root(client, "/api/export/永?format=svg&size_mm=20")
    assert _attr(tag, "width") == "20mm"
    assert _attr(tag, "height") == "20mm"
    assert _attr(tag, "viewBox") == "0 0 2048 2048"


def test_export_size_mm_validation(client):
    r = client.get("/api/export/永?format=svg&size_mm=0")
    assert r.status_code == 422
