"""5ev（架構健檢 W2b）：?v= 版本執行期注入契約。

單一事實源＝pyproject 版本（APP_VERSION）；前端檔內一律 ?v=__V__ 佔位符，
_VersionedStaticFiles／_versioned_page 吐出時注入。vendor pin（opencv
4.11.0／opentype 1.3.4）是語意版本、刻意不走佔位符。
"""
from __future__ import annotations

import re

import pytest

from stroke_order.web.versioning import APP_VERSION, STATIC_DIR


def test_app_version_matches_pyproject():
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    with open(root / "pyproject.toml", "rb") as f:
        assert APP_VERSION == tomllib.load(f)["project"]["version"]


def test_injected_js_carries_version(client):
    r = client.get("/static/zentangle/zentangle.js")
    assert r.status_code == 200
    assert f"?v={APP_VERSION}" in r.text
    assert "__V__" not in r.text
    assert "javascript" in r.headers["content-type"]


def test_pages_injected_no_placeholder(client):
    for path in ("/", "/card", "/handwriting", "/gallery"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "__V__" not in r.text, path
    index = client.get("/").text
    assert f"doodle_engine.js?v={APP_VERSION}" in index
    assert f"zentangle/zentangle.js?v={APP_VERSION}" in index
    # 5fo：/gallery 曾走 FileResponse 漏掉注入＋手刻 v0.13.0 卡版
    gallery = client.get("/gallery").text
    assert f"gallery/gallery.css?v={APP_VERSION}" in gallery
    assert f"gallery/gallery.js?v={APP_VERSION}" in gallery
    assert re.search(r'id="gl-version"[^>]*></span>',
                     gallery.replace("\n", ""))  # 標籤空殼，由 JS 填


def test_no_hardcoded_version_labels_on_disk():
    """5fo 回歸鎖：HTML 不得再出現手刻的純文字版本標籤（>vX.Y.Z<）。

    既有的 ?v= 掃描抓不到這種（gallery 卡 v0.13.0 就是這樣漏網的）
    ——版本顯示一律空殼＋JS 讀資產 ?v= 填值（§57）。"""
    offenders = []
    for p in STATIC_DIR.rglob("*.html"):
        text = p.read_text("utf-8", errors="ignore")
        for m in re.finditer(r">v\d+\.\d+[\w.]*<", text):
            offenders.append(f"{p.relative_to(STATIC_DIR)}:{m.group(0)}")
    assert offenders == [], (
        f"發現手刻版本標籤（應改空殼＋JS 讀 ?v= 填值）：{offenders}"
    )


def test_vendor_pins_untouched(client):
    """vendor 語意版本不得被 app 版本蓋掉（升版會重抓 10MB 級大檔）。"""
    engine = client.get("/static/doodle_engine.js").text
    assert "opencv.js?v=4.11.0" in engine
    assert f"opencv.js?v={APP_VERSION}" not in engine


def test_injection_etag_304(client):
    r1 = client.get("/static/doodle_worker.js")
    etag = r1.headers["etag"]
    assert APP_VERSION in etag  # etag 含版本 → 升版自動失效
    r2 = client.get(
        "/static/doodle_worker.js", headers={"If-None-Match": etag}
    )
    assert r2.status_code == 304


def test_non_inject_types_passthrough(client):
    """json／二進位不經注入層，走原生 StaticFiles（Range/304 保留）。"""
    r = client.get("/static/zhuyin_tw.json")
    assert r.status_code == 200
    assert len(r.content) > 100_000


def test_no_stale_hardcoded_versions_on_disk():
    """回歸鎖：app 自有前端檔不得再出現寫死的數字版 ?v=（vendor pin 除外）。"""
    offenders = []
    for p in STATIC_DIR.rglob("*"):
        if p.suffix not in (".js", ".mjs", ".html", ".css") or not p.is_file():
            continue
        text = p.read_text("utf-8", errors="ignore")
        for m in re.finditer(r"\?v=([0-9][0-9.]*)", text):
            if m.group(1) in ("4.11.0", "1.3.4"):  # vendor 語意 pin 白名單
                continue
            offenders.append(f"{p.relative_to(STATIC_DIR)}:{m.group(0)}")
    assert offenders == [], (
        f"發現寫死版本 query（應改 ?v=__V__ 佔位符）：{offenders}"
    )


def test_traversal_falls_back_404(client):
    r = client.get("/static/../pyproject.toml")
    assert r.status_code == 404
