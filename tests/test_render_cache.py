"""5eu（架構健檢 W2）：重渲染回應快取＋ETag＋失效契約。"""
from __future__ import annotations

import gzip
import json

import pytest
from fastapi.testclient import TestClient

from stroke_order import cache_bus
from stroke_order.web import server as srv
from stroke_order.web.server import create_app


@pytest.fixture()
def client():
    # function-scoped：每測試新 app＝新快取，互不汙染
    return TestClient(create_app())


def test_second_get_hits_cache_with_identical_bytes(client):
    r1 = client.get("/api/grid", params={"chars": "永"})
    r2 = client.get("/api/grid", params={"chars": "永"})
    assert r1.status_code == r2.status_code == 200
    assert r1.headers["x-render-cache"] == "miss"
    assert r2.headers["x-render-cache"] == "hit"
    assert r1.content == r2.content
    assert r2.headers["content-type"] == r1.headers["content-type"]


def test_etag_304_roundtrip(client):
    r1 = client.get("/api/grid", params={"chars": "永"})
    etag = r1.headers["etag"]
    r2 = client.get(
        "/api/grid", params={"chars": "永"}, headers={"If-None-Match": etag}
    )
    assert r2.status_code == 304
    assert r2.headers["etag"] == etag


def test_different_query_is_different_entry(client):
    a = client.get("/api/grid", params={"chars": "永"})
    b = client.get("/api/grid", params={"chars": "日"})
    assert b.headers["x-render-cache"] == "miss"
    assert a.content != b.content


def test_uncached_paths_untouched(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "x-render-cache" not in r.headers


def test_render_post_does_not_invalidate(client):
    """渲染型 POST（如 /api/patch）不是資料異動，不得沖掉快取。"""
    client.get("/api/grid", params={"chars": "永"})
    client.post("/api/patch", json={"text": "永"})
    r = client.get("/api/grid", params={"chars": "永"})
    assert r.headers["x-render-cache"] == "hit"


def test_mutating_endpoint_invalidates(client):
    client.get("/api/grid", params={"chars": "永"})
    before = cache_bus.epoch()
    # user-dict 異動（POST 任一 payload；即使 422 也不該炸——只驗 <400 才 bump）
    r = client.post(
        "/api/user-dict/𰻝",
        json={"format": "svg", "svg": "<svg xmlns='http://www.w3.org/2000/svg'"
              " viewBox='0 0 2048 2048'><path d='M100 100L1900 1900'/></svg>"},
    )
    if r.status_code < 400:
        assert cache_bus.epoch() > before
        r2 = client.get("/api/grid", params={"chars": "永"})
        assert r2.headers["x-render-cache"] == "miss"
    else:
        # 寫入格式不符時不 bump（快取應仍命中）
        assert cache_bus.epoch() == before


def test_cache_bus_bump_invalidates(client):
    """reset_*_singleton 直接呼叫（測試換字型）→ epoch 變 → 舊條目 miss。"""
    client.get("/api/grid", params={"chars": "永"})
    cache_bus.bump()
    r = client.get("/api/grid", params={"chars": "永"})
    assert r.headers["x-render-cache"] == "miss"


def test_oversized_body_not_cached(client, monkeypatch):
    monkeypatch.setattr(srv, "RENDER_CACHE_MAX_ITEM", 10)  # 10 bytes
    client.get("/api/grid", params={"chars": "永"})
    r = client.get("/api/grid", params={"chars": "永"})
    assert r.headers["x-render-cache"] == "miss"  # 塞不進 → 每次 miss


def test_total_budget_evicts_lru(client, monkeypatch):
    monkeypatch.setattr(srv, "RENDER_CACHE_MAX_TOTAL", 8_000)  # 只夠 ~1 條
    client.get("/api/grid", params={"chars": "永"})   # ~5.9KB
    client.get("/api/grid", params={"chars": "日"})   # ~4.5KB → 總量超 → 擠掉「永」
    r = client.get("/api/grid", params={"chars": "永"})
    assert r.headers["x-render-cache"] == "miss"


def test_gzip_still_applies_on_hit(client):
    client.get("/api/grid", params={"chars": "永"})
    r = client.get(
        "/api/grid", params={"chars": "永"},
        headers={"Accept-Encoding": "gzip"},
    )
    assert r.headers["x-render-cache"] == "hit"
    assert r.headers.get("content-encoding") == "gzip"  # 外層 GZip 仍生效
    assert r.text.startswith("<svg") or "<svg" in r.text  # TestClient 自動解壓
