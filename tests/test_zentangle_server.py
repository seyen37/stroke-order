"""
Phase 6z-1B — zentangle outline server endpoint tests.

Covers:
* ``GET /api/zentangle/sources`` (font-independent — always runs)
* ``GET /api/zentangle/outline?char=&source=&samples_per_curve=``
  - 400 on bad input (font-independent — always runs)
  - 503 on missing font (font-independent — sandbox has no fonts)
  - 200 with contours when font present (gated by ``needs_kaishu``)
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.sources.moe_kaishu import reset_kaishu_singleton
from stroke_order.web.server import create_app


_TEST_KAISHU_FONT = "/tmp/moe-kaishu/edukai-5.1_20251208.ttf"


def _kaishu_available() -> bool:
    return Path(_TEST_KAISHU_FONT).exists()


needs_kaishu = pytest.mark.skipif(
    not _kaishu_available(),
    reason="MoE Kaishu absent; copy edukai-5.1*.ttf to /tmp/moe-kaishu/",
)


@pytest.fixture
def kaishu_env(monkeypatch):
    if _kaishu_available():
        monkeypatch.setenv(
            "STROKE_ORDER_KAISHU_FONT_FILE", _TEST_KAISHU_FONT
        )
    reset_kaishu_singleton()


@pytest.fixture
def client(kaishu_env):
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# /api/zentangle/sources — font-independent
# ---------------------------------------------------------------------------


def test_sources_endpoint_returns_five_keys(client):
    r = client.get("/api/zentangle/sources")
    assert r.status_code == 200
    data = r.json()
    assert "sources" in data
    keys = [s["key"] for s in data["sources"]]
    assert keys == [
        "moe_kaishu",
        "cns_kai",
        "moe_song",
        "moe_lishu",
        "chongxi_seal",
    ]


def test_sources_endpoint_each_entry_has_fields(client):
    r = client.get("/api/zentangle/sources")
    data = r.json()
    for entry in data["sources"]:
        assert {"key", "label", "ready"} <= set(entry.keys())


# ---------------------------------------------------------------------------
# /api/zentangle/outline — input validation (font-independent)
# ---------------------------------------------------------------------------


def test_outline_endpoint_rejects_missing_char(client):
    r = client.get("/api/zentangle/outline")
    # FastAPI reports missing required Query as 422
    assert r.status_code == 422


def test_outline_endpoint_rejects_empty_char(client):
    r = client.get("/api/zentangle/outline?char=")
    # Query min_length=1 → 422
    assert r.status_code == 422


def test_outline_endpoint_rejects_multi_char(client):
    r = client.get("/api/zentangle/outline?char=" + "心心")
    # max_length=1 → 422
    assert r.status_code == 422


def test_outline_endpoint_rejects_unknown_source(client):
    r = client.get("/api/zentangle/outline?char=" + "心" + "&source=bogus")
    assert r.status_code == 400
    assert "unknown source" in r.json()["detail"].lower()


def test_outline_endpoint_rejects_out_of_range_samples(client):
    # samples_per_curve must be 1..64
    r = client.get(
        "/api/zentangle/outline?char=" + "心" + "&samples_per_curve=0"
    )
    assert r.status_code == 422
    r = client.get(
        "/api/zentangle/outline?char=" + "心" + "&samples_per_curve=999"
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /api/zentangle/outline — font-dependent (real outline returned)
# ---------------------------------------------------------------------------


@needs_kaishu
def test_outline_endpoint_returns_contours_for_xin(client):
    r = client.get("/api/zentangle/outline?char=" + "心")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["char"] == "心"
    assert data["source"] == "moe_kaishu"
    assert data["samples_per_curve"] == 8
    assert data["em_size"] > 0
    contours = data["contours"]
    assert len(contours) >= 1
    for poly in contours:
        assert len(poly) >= 3
        for pt in poly:
            assert isinstance(pt, list)
            assert len(pt) == 2


@needs_kaishu
def test_outline_endpoint_explicit_samples_per_curve_respected(client):
    r_low = client.get(
        "/api/zentangle/outline?char=" + "心" + "&samples_per_curve=2"
    )
    r_high = client.get(
        "/api/zentangle/outline?char=" + "心" + "&samples_per_curve=16"
    )
    assert r_low.status_code == 200
    assert r_high.status_code == 200
    pts_low = sum(len(p) for p in r_low.json()["contours"])
    pts_high = sum(len(p) for p in r_high.json()["contours"])
    assert pts_high > pts_low


# ---------------------------------------------------------------------------
# /api/zentangle/outline — graceful degradation when font missing
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    _kaishu_available(),
    reason="font available — this test simulates the missing-font path",
)
def test_outline_endpoint_503_when_font_missing(client):
    """Sandbox/CI without the font → 503 (not 500), so frontend can
    degrade gracefully rather than treat as permanent error."""
    r = client.get("/api/zentangle/outline?char=" + "心")
    # 404 (no glyph) and 503 (font file absent) are both acceptable
    # graceful-degradation outcomes; the contract is "no 500 / 200".
    assert r.status_code in (404, 503), r.text
