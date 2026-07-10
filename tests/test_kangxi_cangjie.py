"""Phase 5bo: 康熙 214 部首 + 倉頡字根 exporter/API tests."""
from __future__ import annotations

import pytest

from stroke_order.exporters.kangxi_radicals import (
    RADICAL_BANDS, ALL_RADICALS, RADICALS, render_kangxi_radicals_page,
)
from stroke_order.exporters.cangjie_roots import (
    CANGJIE_GROUPS, CANGJIE_TEXT, render_cangjie_roots_page,
)


# ---------------------------------------------------------------------------
# 康熙部首資料
# ---------------------------------------------------------------------------


def test_214_radicals_unique():
    assert len(ALL_RADICALS) == 214
    assert len(set(ALL_RADICALS)) == 214
    assert len(RADICALS) == 214


def test_band_structure():
    assert len(RADICAL_BANDS) == 17           # 1畫 → 17畫
    assert [n for n, _c in RADICAL_BANDS] == list(range(1, 18))
    counts = {n: len(c) for n, c in RADICAL_BANDS}
    assert counts[1] == 6 and counts[4] == 34 and counts[17] == 1


def test_radical_spot_checks_moe_forms():
    assert RADICALS[0] == ("一", 1, 1, True)
    assert RADICALS[-1] == ("龠", 214, 17, True)
    assert "青" in ALL_RADICALS and "靑" not in ALL_RADICALS   # MOE 字形
    assert "戶" in ALL_RADICALS                                # 臺灣標準
    idx = {ch: i for ch, i, _n, _b in RADICALS}
    assert idx["心"] == 61                                     # 4畫第一個
    assert idx["金"] == 167                                    # 8畫第一個


def test_kangxi_render_smoke():
    svg = render_kangxi_radicals_page(char_loader=lambda ch: None)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    for gid in ("kr-bg", "kr-grid", "kr-hints"):
        assert f'id="{gid}"' in svg
    assert ">1</text>" in svg and ">214</text>" in svg


# ---------------------------------------------------------------------------
# 倉頡字根資料
# ---------------------------------------------------------------------------


def test_cangjie_25_roots_keys_aligned():
    assert len(CANGJIE_TEXT) == 25
    assert len(set(CANGJIE_TEXT)) == 25
    all_keys = "".join(k for _l, k, _r in CANGJIE_GROUPS)
    assert len(all_keys) == 25
    assert sorted(all_keys) == sorted("ABCDEFGHIJKLMNOPQRSTUVWXY")  # 無 Z
    for _l, keys, rads in CANGJIE_GROUPS:
        assert len(keys) == len(rads)


def test_cangjie_key_mapping_spot_checks():
    mapping = {}
    for _l, keys, rads in CANGJIE_GROUPS:
        mapping.update(zip(keys, rads))
    assert mapping["A"] == "日" and mapping["G"] == "土"
    assert mapping["H"] == "竹" and mapping["N"] == "弓"
    assert mapping["O"] == "人" and mapping["R"] == "口"
    assert mapping["S"] == "尸" and mapping["Y"] == "卜"
    assert mapping["X"] == "難"


def test_cangjie_render_smoke():
    svg = render_cangjie_roots_page(char_loader=lambda ch: None)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    for gid in ("cj-bg", "cj-grid", "cj-hints"):
        assert f'id="{gid}"' in svg
    for key in ("A", "N", "X", "Y"):
        assert f">{key}</text>" in svg


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


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


def test_api_table_page_renders_for_kangxi(client, fast_null_loader):
    r = client.get("/api/sutra?preset=kangxi_radicals&page_type=table")
    assert r.status_code == 200
    assert 'id="kr-grid"' in r.text


def test_api_table_page_renders_for_cangjie(client, fast_null_loader):
    r = client.get("/api/sutra?preset=cangjie_roots&page_type=table")
    assert r.status_code == 200
    assert 'id="cj-grid"' in r.text


def test_api_table_page_error_mentions_new_presets(client):
    r = client.get("/api/sutra?preset=heart_sutra&page_type=table")
    assert r.status_code == 422
    assert "kangxi_radicals" in r.json()["detail"]
    assert "cangjie_roots" in r.json()["detail"]
