"""Phase 5bo: 二十四節氣 exporter + API tests."""
from __future__ import annotations

import pytest

from stroke_order.exporters.solar_terms import (
    SOLAR_TERMS, SOLAR_TERMS_TEXT, render_solar_terms_page,
)


def test_24_terms_48_chars():
    assert len(SOLAR_TERMS) == 24
    assert all(len(t) == 2 for t, _d in SOLAR_TERMS)
    assert len(SOLAR_TERMS_TEXT) == 48
    assert len(set(t for t, _d in SOLAR_TERMS)) == 24


def test_term_order_and_dates_spot_check():
    terms = [t for t, _d in SOLAR_TERMS]
    dates = dict(SOLAR_TERMS)
    assert terms[0] == "立春" and terms[-1] == "大寒"
    assert terms[3] == "春分" and terms[9] == "夏至"
    assert terms[15] == "秋分" and terms[21] == "冬至"
    # 季節斷點：每 6 個一季，立X 開頭
    assert terms[6] == "立夏" and terms[12] == "立秋" and terms[18] == "立冬"
    assert dates["春分"] == "3/21" and dates["冬至"] == "12/22"


def test_render_with_null_loader_still_valid_svg():
    svg = render_solar_terms_page(char_loader=lambda ch: None)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    for gid in ("st-bg", "st-grid", "st-hints"):
        assert f'id="{gid}"' in svg
    assert ">2/4</text>" in svg
    assert ">12/22</text>" in svg


def test_render_loader_memoised():
    calls: list[str] = []

    def loader(ch):
        calls.append(ch)
        return None

    render_solar_terms_page(char_loader=loader, title="")
    assert len(calls) == len(set(calls))


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from stroke_order.web.server import app
    return TestClient(app)


@pytest.fixture()
def fast_null_loader(monkeypatch):
    import stroke_order.web.server as srv

    def _null_load(char, source, hook_policy, auto_fix=True):
        from fastapi import HTTPException
        raise HTTPException(404, detail="stubbed")

    monkeypatch.setattr(srv, "_load", _null_load)


def test_api_table_page_renders_for_solar_terms(client, fast_null_loader):
    r = client.get("/api/sutra?preset=solar_terms&page_type=table")
    assert r.status_code == 200
    assert 'id="st-grid"' in r.text


def test_api_table_page_error_mentions_solar_terms(client):
    r = client.get("/api/sutra?preset=heart_sutra&page_type=table")
    assert r.status_code == 422
    assert "solar_terms" in r.json()["detail"]
