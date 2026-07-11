"""Phase 5bo: 注音符號 exporter + API tests."""
from __future__ import annotations

import pytest

from stroke_order.exporters.zhuyin import (
    ZHUYIN_GROUPS, ZHUYIN_TEXT, render_zhuyin_page,
)


def test_37_symbols_three_groups():
    assert len(ZHUYIN_TEXT) == 37
    assert len(set(ZHUYIN_TEXT)) == 37
    labels = [l for l, _p in ZHUYIN_GROUPS]
    assert labels == ["聲母", "介音", "韻母"]
    counts = {l: len(p) for l, p in ZHUYIN_GROUPS}
    assert counts == {"聲母": 21, "介音": 3, "韻母": 13}


def test_standard_keyboard_mapping_spot_checks():
    mapping = {s: k for _l, pairs in ZHUYIN_GROUPS for s, k in pairs}
    assert len(set(mapping.values())) == 37    # 鍵位不重複
    assert mapping["ㄅ"] == "1" and mapping["ㄆ"] == "q"
    assert mapping["ㄇ"] == "a" and mapping["ㄈ"] == "z"
    assert mapping["ㄓ"] == "5" and mapping["ㄙ"] == "n"
    assert mapping["ㄧ"] == "u" and mapping["ㄩ"] == "m"
    assert mapping["ㄚ"] == "8" and mapping["ㄦ"] == "-"
    assert mapping["ㄝ"] == "," and mapping["ㄥ"] == "/"


def test_render_smoke_and_xml_escape():
    svg = render_zhuyin_page(char_loader=lambda ch: None)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    for gid in ("zy-bg", "zy-grid", "zy-hints"):
        assert f'id="{gid}"' in svg
    # 鍵位含 "," "." "/" "-" "" 等 — 不得出現未跳脫的裸字元問題
    assert ">,</text>" in svg and ">/</text>" in svg
    assert ">1</text>" in svg


def test_render_loader_memoised():
    calls: list[str] = []
    render_zhuyin_page(char_loader=lambda ch: calls.append(ch), title="")
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


def test_api_table_page_renders_for_zhuyin(client, fast_null_loader):
    r = client.get("/api/sutra?preset=zhuyin_symbols&page_type=table")
    assert r.status_code == 200
    assert 'id="zy-grid"' in r.text


def test_api_table_page_error_mentions_zhuyin(client):
    r = client.get("/api/sutra?preset=heart_sutra&page_type=table")
    assert r.status_code == 422
    assert "zhuyin_symbols" in r.json()["detail"]
