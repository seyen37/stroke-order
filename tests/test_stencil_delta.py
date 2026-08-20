"""
B 案 — 真輪廓 ±δ 字模粗細微調（向量域、雙向、保留起收筆）。

R1 spike 驗證可行、R1b 量出楷書級安全區 ±20 EM 後另案的小輪。與既有
``bold_mm``（事後光柵膨脹濾鏡、只加不減）語意不同、可疊用。

本輪動工時的新量測（誠實訂正）：**±20 不是跨字源的安全保證**——noto_hei
（粗黑體）在 +20 就讓「歡」黏合（3→1 件）、「國」孔 2→5，等於楷書在
+40 才發生的事。夾限保留 ±20（量測涵蓋範圍），字源相依的後果由既有
件數/孔數標頭回報。本檔把這批實測值釘成已知答案樁（§93）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import MultiPolygon, Polygon

from stroke_order.exporters.stencil import (
    DELTA_EM_LIMIT,
    apply_delta_em,
    stencil_geometry,
)
from stroke_order.web.server import create_app

_ROOT = Path(__file__).resolve().parent.parent
_INDEX = _ROOT / "src" / "stroke_order" / "web" / "static" / "index.html"
_SC_JS = (_ROOT / "src" / "stroke_order" / "web" / "static" / "modes"
          / "stencil.js")

try:
    from stroke_order.exporters.zentangle import extract_outline_polylines
    _HEI_OK = bool(extract_outline_polylines("國", source="noto_hei"))
except Exception:
    _HEI_OK = False

needs_hei = pytest.mark.skipif(not _HEI_OK, reason="noto_hei 字型未安裝")


def _shape(polys):
    s = None
    for r in polys:
        p = Polygon(r)
        if not p.is_valid:
            p = p.buffer(0)
        s = p if s is None else s.symmetric_difference(p)
    return s


def _stats(polys):
    s = _shape(polys)
    geoms = list(s.geoms) if isinstance(s, MultiPolygon) else [s]
    return (len(geoms), sum(len(g.interiors) for g in geoms), s.area)


# ---------------------------------------------------------------------------
# 幾何語意（合成圖形——不吃字型）
# ---------------------------------------------------------------------------

#: 口字形：外環＋洞環（even-odd）
_RING = [
    [(500, 500), (1500, 500), (1500, 1500), (500, 1500)],
    [(700, 700), (1300, 700), (1300, 1300), (700, 1300)],
]


def test_b_zero_delta_is_identity():
    assert apply_delta_em(_RING, 0.0) is _RING
    assert apply_delta_em([], 10.0) == []


def test_b_even_odd_hole_survives_buffering():
    """XOR 重建：洞在 ±δ 後仍是洞（不靠環向、不靠巢狀深度）。"""
    for d in (-15.0, 15.0):
        out = apply_delta_em(_RING, d)
        comps, holes, _a = _stats(out)
        assert comps == 1 and holes == 1, (d, comps, holes)


def test_b_area_is_monotonic_in_delta():
    a_thin = _stats(apply_delta_em(_RING, -15))[2]
    a_zero = _stats(_RING)[2]
    a_bold = _stats(apply_delta_em(_RING, 15))[2]
    assert a_thin < a_zero < a_bold


def test_b_thin_wall_vanishes_honestly():
    """牆厚 < 2·|δ| 的部件整個消失——回空、不回垃圾幾何。"""
    thin = [[(0, 0), (2048, 0), (2048, 30), (0, 30)]]   # 30 EM 細條
    assert apply_delta_em(thin, -20.0) == []


def test_b_clamp_is_enforced_at_the_source():
    with pytest.raises(ValueError):
        apply_delta_em(_RING, DELTA_EM_LIMIT + 1)
    with pytest.raises(ValueError):
        apply_delta_em(_RING, -(DELTA_EM_LIMIT + 1))


# ---------------------------------------------------------------------------
# 已知答案樁（§93）：noto_hei 實測值——B 輪動工時量的
# ---------------------------------------------------------------------------


@needs_hei
def test_b_known_answers_noto_hei():
    """明 在 ±20 全程穩定（2 件 4 孔）；歡 在 +20 黏合（3→1）——

    後者釘住「±20 非跨字源安全」這個訂正：哪天有人把夾限當安全保證放寬，
    或粗字源行為默默變了，這裡會紅。
    """
    ming = extract_outline_polylines("明", source="noto_hei")
    for d in (-20, 20):
        comps, holes, _a = _stats(apply_delta_em(ming, d))
        assert (comps, holes) == (2, 4), (d, comps, holes)

    huan = extract_outline_polylines("歡", source="noto_hei")
    assert _stats(huan)[:2] == (3, 5)
    assert _stats(apply_delta_em(huan, 20))[0] == 1   # 黏合——粗字源的實況


# ---------------------------------------------------------------------------
# stencil_geometry 整合
# ---------------------------------------------------------------------------


def test_b_geometry_zero_delta_zero_regression():
    """delta_em=0（預設）→ 輸出與不帶參數逐項相同。"""
    a = stencil_geometry([_RING], char_height_mm=50.0)
    b = stencil_geometry([_RING], char_height_mm=50.0, delta_em=0.0)
    assert a == b


def test_b_geometry_delta_changes_output_and_keeps_slot():
    base = stencil_geometry([_RING], char_height_mm=50.0)
    bold = stencil_geometry([_RING], char_height_mm=50.0, delta_em=15.0)
    assert base[0] != bold[0]
    # 減細到消失：字槽保留（板面尺寸不因此塌掉）
    thin = [[(0, 0), (2048, 0), (2048, 30), (0, 30)]]
    loops, w, h, _s = stencil_geometry([thin, _RING],
                                       char_height_mm=50.0, delta_em=-20.0)
    loops2, w2, h2, _s2 = stencil_geometry([thin, _RING],
                                           char_height_mm=50.0)
    assert w == w2, "空槽也要佔位——版面對位不變"


def test_b_stacks_with_bold_mm():
    """δ（向量域）與 bold_mm（光柵域）語意不同、可疊用不衝突。"""
    both = stencil_geometry([_RING], char_height_mm=50.0,
                            delta_em=10.0, bold_mm=0.5)
    only_d = stencil_geometry([_RING], char_height_mm=50.0, delta_em=10.0)
    assert both[0] != only_d[0]


# ---------------------------------------------------------------------------
# 端點
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


@needs_hei
def test_b_endpoint_accepts_delta(client):
    r0 = client.get("/api/stencil", params={
        "chars": "明", "source": "noto_hei"})
    r1 = client.get("/api/stencil", params={
        "chars": "明", "source": "noto_hei", "delta_em": 15})
    r2 = client.get("/api/stencil", params={
        "chars": "明", "source": "noto_hei", "delta_em": -15})
    assert r0.status_code == r1.status_code == r2.status_code == 200
    assert len({r0.text, r1.text, r2.text}) == 3, "三種 δ 應產生三種輸出"


@needs_hei
def test_b_endpoint_zero_delta_is_byte_identical(client):
    a = client.get("/api/stencil", params={
        "chars": "明", "source": "noto_hei"})
    b = client.get("/api/stencil", params={
        "chars": "明", "source": "noto_hei", "delta_em": 0})
    assert a.text == b.text


def test_b_endpoint_clamps(client):
    for bad in (21, -21, 100):
        r = client.get("/api/stencil", params={
            "chars": "明", "source": "noto_hei", "delta_em": bad})
        assert r.status_code == 422, bad


# ---------------------------------------------------------------------------
# parity：UI ≡ JS ≡ 夾限
# ---------------------------------------------------------------------------


def test_b_ui_input_matches_js_and_limit():
    page = _INDEX.read_text("utf-8")
    js = _SC_JS.read_text("utf-8")
    m = re.search(r'id="sc-delta"[^>]*min="(-?\d+)"[^>]*max="(\d+)"', page)
    assert m, "index.html 缺 sc-delta"
    assert float(m.group(1)) == -DELTA_EM_LIMIT
    assert float(m.group(2)) == DELTA_EM_LIMIT
    assert 'g("sc-delta")' in js and "delta_em" in js
