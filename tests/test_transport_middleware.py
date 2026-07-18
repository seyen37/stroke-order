"""W1-B（架構健檢 2026-07-18）：GZip 壓縮與 /static 快取 header 契約。"""
from __future__ import annotations

import pytest



def test_gzip_on_large_static_json(client):
    r = client.get("/static/zhuyin_tw.json", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


def test_gzip_on_large_api_response(client):
    # grid SVG 遠大於 minimum_size=1024，應被壓縮
    r = client.get(
        "/api/grid", params={"chars": "永"}, headers={"Accept-Encoding": "gzip"}
    )
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


def test_small_response_not_gzipped(client):
    r = client.get("/api/health", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") is None


def test_static_versioned_long_cache(client):
    r = client.get("/static/zhuyin_tw.json?v=test")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "public, max-age=604800"


def test_static_unversioned_short_cache(client):
    r = client.get("/static/zhuyin_tw.json")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "public, max-age=3600"


def test_non_static_untouched(client):
    r = client.get("/api/health")
    assert "max-age" not in (r.headers.get("cache-control") or "")
