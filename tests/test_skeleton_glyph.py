"""R1a 骨架長肉字模引擎守門測試（承 §66 鎖不變式不鎖寫法）。

不變式：輪廓非空且閉合可用、密度補償單調、even-odd 有洞環、
popup 降級階梯（字型缺→骨架字模 200+degraded；骨架也缺→維持 503）。

shapely 為選用相依（web extras）——缺席時需 shapely 的測試 skip
（同 needs_hei 慣例）；降級階梯測試以 monkeypatch 模擬、不依賴實際缺席。
"""
import math

import pytest

from stroke_order.sources.skeleton_glyph import (
    SkeletonGlyphUnavailable, _effective_width, glyph_polylines, is_available,
)

needs_shapely = pytest.mark.skipif(
    not is_available(),
    reason="shapely（GEOS）缺——pip install shapely 或安裝 web extras",
)


@needs_shapely
def test_glyph_polylines_basic_nonempty_closed():
    """永/春/歡 皆須產出輪廓；每環 ≥3 點、座標有限。"""
    for ch in ["永", "春", "歡"]:
        contours = glyph_polylines(ch)
        assert contours, f"{ch} 輪廓不可為空"
        for ring in contours:
            assert len(ring) >= 3
            assert all(math.isfinite(x) and math.isfinite(y)
                       for x, y in ring), f"{ch} 座標須有限"


def test_density_compensation_monotonic():
    """筆畫越多、有效字重越細（spike 定版不變式）——不需 shapely。"""
    w = 180.0
    w5, w9, w22 = (_effective_width(w, n) for n in (5, 9, 22))
    assert w22 < w9 < w5 < w
    # spike 實證錨點：歡（22 筆）約 101（±2 容差，防公式被無聲改掉）
    assert abs(w22 - 101) <= 2


@needs_shapely
def test_evenodd_holes_present():
    """春「日」部、歡「口」部須有洞環（even-odd 相容的關鍵）。"""
    from shapely.geometry import Point, Polygon
    for ch in ["春", "歡"]:
        contours = glyph_polylines(ch)
        polys = [Polygon(r) for r in contours]
        nested = sum(
            1 for i, a in enumerate(polys) for j, b in enumerate(polys)
            if i != j and b.contains(Point(a.exterior.coords[0]))
        )
        assert nested >= 1, f"{ch} 應至少有一個洞環（巢狀輪廓）"


@needs_shapely
def test_param_validation():
    with pytest.raises(ValueError):
        glyph_polylines("永", weight=0)
    with pytest.raises(ValueError):
        glyph_polylines("永", width_ratio=-1)
    with pytest.raises(ValueError):
        glyph_polylines("永", cap="butt")


@needs_shapely
def test_popup_degrades_to_skeleton_when_font_missing(monkeypatch, tmp_path):
    """降級階梯第 2 階：字型缺席 → 200＋degraded＋glyph_source=skeleton。"""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from stroke_order.sources.noto_hei import reset_hei_singleton
    from stroke_order.web.server import create_app

    monkeypatch.setenv("STROKE_ORDER_HEI_FONT_FILE",
                       str(tmp_path / "no-such-font.otf"))
    reset_hei_singleton()
    try:
        c = TestClient(create_app())
        r = c.post("/api/popup/svg", json={"upper": "永"})
        assert r.status_code == 200
        d = r.json()
        assert d["degraded"] is True
        assert d["glyph_source"] == "skeleton"
        assert d["components"] == 1, "骨架字模同樣要過連筋（剪下不散）"
        assert d["svg"].startswith("<svg")
    finally:
        reset_hei_singleton()


def test_popup_503_when_both_unavailable(monkeypatch, tmp_path):
    """降級階梯第 3 階：字型缺＋骨架字模也不可用 → 維持 503＋安裝指引。"""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import stroke_order.sources.skeleton_glyph as sg
    from stroke_order.sources.noto_hei import reset_hei_singleton
    from stroke_order.web.server import create_app

    def _raise(*a, **k):
        raise SkeletonGlyphUnavailable("simulated: shapely missing")

    monkeypatch.setenv("STROKE_ORDER_HEI_FONT_FILE",
                       str(tmp_path / "no-such-font.otf"))
    monkeypatch.setattr(sg, "glyph_polylines", _raise)
    reset_hei_singleton()
    try:
        c = TestClient(create_app())
        r = c.post("/api/popup/svg", json={"upper": "永"})
        assert r.status_code == 503
        assert "思源黑體" in r.json()["detail"]
    finally:
        reset_hei_singleton()
