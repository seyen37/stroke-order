"""立體字卡片（pop-up 鏤空字）守門測試。

鎖住不變式：連筋後整卡單一連通（剪下不散）、單/雙層結構、對稱可折合、
折線分層、Web 端點契約。

缺思源黑體字型時，需字型的測試 skip（同既有 noto_hei 測試；字型由
scripts/render_fetch_fonts.sh 於部署時抓）。
"""
import numpy as np
import pytest

from stroke_order.sources.noto_hei import default_hei_font_path
from stroke_order.exporters.popup import (
    generate_popup, build_popup, PopupParams, _label, _label_runs,
)

needs_hei = pytest.mark.skipif(
    not default_hei_font_path().exists(),
    reason="思源黑體 (Noto Sans TC) 缺；執行 scripts/render_fetch_fonts.sh "
           "或設 STROKE_ORDER_HEI_FONT_FILE",
)


@needs_hei
def test_single_tier_single_connected():
    card, folds, meta = build_popup("福")
    assert meta["tiers"] == 1
    assert meta["ncomp"] == 1, "單層整卡必須單一連通（剪下不散）"


@needs_hei
def test_two_tier_single_connected():
    card, folds, meta = build_popup("新年", "快樂")
    assert meta["tiers"] == 2
    assert meta["ncomp"] == 1, "雙層整卡必須單一連通"


@needs_hei
def test_spine_at_card_center_symmetric():
    """中線谷折穿卡片正中；單層時字頂到中線＝字底到中線（對稱好折合）。"""
    card, folds, meta = build_popup("春")
    spine = [f for f in folds if f[0] == "spine"]
    assert len(spine) == 1
    _, y_spine, _, _ = spine[0]
    assert y_spine == meta["CH"] // 2, "中線必須在卡片正中"
    mtn = [f for f in folds if f[0] == "mountain"][0]        # 字頂↔roof
    valseg = [f for f in folds if f[0] == "valley_seg"][0]   # 字底↔底座
    top_d = abs(mtn[1] - y_spine)
    bot_d = abs(valseg[1] - y_spine)
    assert abs(top_d - bot_d) <= 2, "字頂/字底對中線需對稱（|a-d|=|b-c|）"


@needs_hei
def test_fold_layers_present():
    card, folds, meta = build_popup("新年", "快樂")
    kinds = {f[0] for f in folds}
    assert "spine" in kinds and "mountain" in kinds
    assert "valley" in kinds and "valley_seg" in kinds


@needs_hei
def test_svg_has_layers_and_dims():
    r = generate_popup("新年", "快樂")
    assert r.svg.startswith("<svg")
    assert 'stroke="#149046"' in r.svg   # 中線綠
    assert 'stroke="#c62828"' in r.svg   # 山折紅
    assert 'stroke="#1565c0"' in r.svg   # 谷折藍
    assert r.width_mm == pytest.approx(210, abs=1)
    assert r.components == 1


def test_label_helpers_count():
    """連通標記（scipy 與純 numpy run-based 後備皆須正確）——不需字型。"""
    m = np.zeros((30, 30), bool)
    m[1:3, 1:3] = True
    m[6:8, 6:8] = True
    m[6:8, 20:24] = True
    _, n = _label(m)
    assert n == 3
    _, n2 = _label_runs(m)   # 後備獨立驗證
    assert n2 == 3


def test_web_endpoints_fontfree():
    """不需字型的端點契約：頁面 200、空字/超長 422。"""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    c = TestClient(create_app())
    assert c.get("/popup").status_code == 200
    assert c.post("/api/popup/svg", json={"upper": ""}).status_code == 422
    assert c.post("/api/popup/svg",
                  json={"upper": "一二三四五六七八九十十一十二十三"}).status_code == 422


@needs_hei
def test_web_endpoints_generate():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    c = TestClient(create_app())
    r = c.post("/api/popup/svg", json={"upper": "新年", "lower": "快樂"})
    assert r.status_code == 200
    d = r.json()
    assert d["components"] == 1 and d["tiers"] == 2
    assert d["svg"].startswith("<svg")
    r1 = c.post("/api/popup/svg", json={"upper": "福"})
    assert r1.status_code == 200 and r1.json()["tiers"] == 1
