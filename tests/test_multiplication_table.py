"""Phase 5bo: 九九乘法表 exporter + API tests."""
from __future__ import annotations

import pytest

from stroke_order.exporters.multiplication_table import (
    MNEMONICS, MNEMONICS_TEXT, mnemonic,
    render_multiplication_table_page,
)


# ---------------------------------------------------------------------------
# 口訣拼寫
# ---------------------------------------------------------------------------


def test_mnemonic_spelling_conventions():
    assert mnemonic(1, 1) == "一一得一"      # p < 10 → 得
    assert mnemonic(3, 3) == "三三得九"
    assert mnemonic(2, 5) == "二五一十"      # p == 10 → 一十
    assert mnemonic(3, 4) == "三四十二"      # 11-19 → 十X
    assert mnemonic(4, 5) == "四五二十"      # 整十 → 無個位
    assert mnemonic(3, 7) == "三七二十一"    # ≥20 → 二十一
    assert mnemonic(9, 9) == "九九八十一"


def test_mnemonic_rejects_bad_order():
    with pytest.raises(ValueError):
        mnemonic(7, 3)
    with pytest.raises(ValueError):
        mnemonic(0, 5)


def test_45_mnemonics_lower_triangle():
    assert len(MNEMONICS) == 45
    assert len({(i, j) for i, j, _m in MNEMONICS}) == 45
    for i, j, _m in MNEMONICS:
        assert 1 <= i <= j <= 9
    assert len(MNEMONICS_TEXT) == 200
    # 只用 11 個相異字
    assert set(MNEMONICS_TEXT) <= set("一二三四五六七八九十得")


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def test_render_with_null_loader_still_valid_svg():
    svg = render_multiplication_table_page(char_loader=lambda ch: None)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    for gid in ("mt-bg", "mt-grid", "mt-hints"):
        assert f'id="{gid}"' in svg
    assert ">1×1=1</text>" in svg
    assert ">9×9=81</text>" in svg
    # 下三角：不存在 7×3（僅 3×7）
    assert ">7×3=21</text>" not in svg
    assert ">3×7=21</text>" in svg


def test_render_loader_memoised():
    calls: list[str] = []

    def loader(ch):
        calls.append(ch)
        return None

    render_multiplication_table_page(char_loader=loader, title="")
    # 45 句只該觸發 11 個相異字各一次
    assert len(calls) == len(set(calls))
    assert set(calls) <= set("一二三四五六七八九十得")


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
    import stroke_order.web.char_pipeline as srv  # W3-R2：載字鏈移居 char_pipeline（patch 目標唯一）

    def _null_load(char, source, hook_policy, auto_fix=True):
        from fastapi import HTTPException
        raise HTTPException(404, detail="stubbed")

    monkeypatch.setattr(srv, "_load", _null_load)


def test_api_table_page_renders_for_multiplication(client, fast_null_loader):
    r = client.get("/api/sutra?preset=multiplication_table&page_type=table")
    assert r.status_code == 200
    assert 'id="mt-grid"' in r.text
    assert ">9×9=81</text>" in r.text


def test_api_table_page_still_rejected_for_other_presets(client):
    r = client.get("/api/sutra?preset=heart_sutra&page_type=table")
    assert r.status_code == 422
    assert "multiplication_table" in r.json()["detail"]
