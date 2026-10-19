"""
v0.14.297 P1——無狀態手寫字型 ``POST /api/handfont``。

筆跡在請求裡、字型在回應裡，伺服器不落地任何東西（P0 已關共用字庫）。
引擎同 R3（tests/test_handfont.py 的兩層驗證在此對 POST 路徑重跑一次）：
  · 層一 fontTools 回讀：cmap 只含送來的字、全形等寬、著作權歸書寫者。
  · 層二 FreeType 真渲染：十有墨、口的字碗留白（環向正確）。
另鎖：與存檔路徑（GET /api/user-dict/font）同筆跡＝同字形、零落地、
上限與輸入驗證、閘門與計數掛點。
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.web import metrics
from stroke_order.web.routes import user_dict as ud
from stroke_order.web.server import RENDER_CACHE_PREFIXES, create_app

SHI = [[[300, 1024], [1748, 1024]], [[1024, 300], [1024, 1748]]]
KOU = [[[500, 500], [500, 1500]],
       [[500, 500], [1500, 500], [1500, 1500]],
       [[500, 1500], [1500, 1500]]]


@pytest.fixture
def env(tmp_path, monkeypatch):
    ud_dir = tmp_path / "ud"
    monkeypatch.setenv("STROKE_ORDER_USER_DICT_DIR", str(ud_dir))
    monkeypatch.setenv("STROKE_ORDER_METRICS_DIR", str(tmp_path / "m"))
    monkeypatch.setenv("STROKE_ORDER_USER_DICT_WRITABLE", "false")  # 公開站設定
    metrics.reset_for_tests()
    yield tmp_path
    metrics.reset_for_tests()


@pytest.fixture
def client(env):
    return TestClient(create_app())


def _post(client, chars, **kw):
    return client.post("/api/handfont", json={"chars": chars, **kw})


def _font(content):
    from fontTools.ttLib import TTFont
    return TTFont(io.BytesIO(content))


# ---------------------------------------------------------------------------
# 層一／層二
# ---------------------------------------------------------------------------

def test_post_returns_installable_font(client):
    r = _post(client, {"十": SHI, "口": KOU}, owner="小明")
    assert r.status_code == 200
    assert r.headers["content-type"] == "font/ttf"
    assert r.headers["x-hand-font-chars"] == "2"
    assert r.headers["cache-control"] == "no-store"
    assert "attachment" in r.headers["content-disposition"]
    f = _font(r.content)
    assert set(f.getBestCmap()) == {ord("十"), ord("口")}, "只含送來的字"
    assert all(f["hmtx"][g][0] == 2048 for g in ("uni5341", "uni53E3"))
    assert "小明" in (f["name"].getDebugName(0) or "")


def test_post_font_renders_and_counter_stays_white(client):
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    r = _post(client, {"口": KOU})
    font = ImageFont.truetype(io.BytesIO(r.content), 300)
    img = Image.new("L", (360, 400), 255)
    ImageDraw.Draw(img).text((20, 20), "口", font=font, fill=0)
    w, h = img.size
    assert all(img.getpixel((w // 2 + dx, h // 2 + dy)) > 200
               for dx in (-8, 0, 8) for dy in (-8, 0, 8)), "字碗被填死＝環向錯"
    assert int((np.asarray(img) < 128).sum()) > 1000


def test_post_equals_saved_dict_path(env, monkeypatch):
    """同一份筆跡：無狀態 POST 與存檔後 GET 產出的字形輪廓完全相同。"""
    monkeypatch.setenv("STROKE_ORDER_USER_DICT_WRITABLE", "true")
    c = TestClient(create_app())
    for ch, strokes in (("十", SHI), ("口", KOU)):
        assert c.post("/api/user-dict", json={
            "char": ch, "strokes": [{"track": t} for t in strokes]}).status_code == 200
    a = _font(c.get("/api/user-dict/font").content)
    b = _font(_post(c, {"十": SHI, "口": KOU}).content)
    for g in ("uni5341", "uni53E3"):
        ga, gb = a["glyf"][g], b["glyf"][g]
        ga.expand(a["glyf"]); gb.expand(b["glyf"])
        assert list(ga.coordinates) == list(gb.coordinates)


# ---------------------------------------------------------------------------
# 零落地
# ---------------------------------------------------------------------------

def test_post_writes_nothing_to_disk(client, env, monkeypatch):
    from stroke_order.sources.user_dict import UserDictSource

    def boom(*a, **k):
        raise AssertionError("POST /api/handfont 不得寫入字庫")
    monkeypatch.setattr(UserDictSource, "save_character", boom)
    m = env / "m"     # 計數器自己的檔案（只有次數、非手寫）不算
    def files():
        return {p for p in env.rglob("*") if p != m and m not in p.parents}
    before = files()
    assert _post(client, {"十": SHI}).status_code == 200
    after = files()
    assert after == before, f"多出檔案：{after - before}"
    assert not (env / "ud").exists()


def test_works_when_shared_dict_is_readonly(client):
    """公開站（WRITABLE=false）照樣能產字型——這正是 P1 存在的理由。"""
    assert client.get("/api/user-dict").json()["writable"] is False
    assert _post(client, {"十": SHI}).status_code == 200


# ---------------------------------------------------------------------------
# 輸入驗證與上限
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("chars,code", [
    ({}, 400),
    ({"十十": SHI}, 422),
    ({" ": SHI}, 422),
    ({"\u0007": SHI}, 422),
    ({"十": [[[0, 0]]]}, 422),                       # 只有單點輕觸
    ({"十": [[[0, 0], [float("1e9"), 0]]]}, 422),     # 座標荒謬
    ({"十": [[[0, 0, 0], [1, 1, 1]]]}, 422),          # 不是 [x, y]
])
def test_invalid_inputs(client, chars, code):
    r = _post(client, chars)
    assert r.status_code == code, r.text
    assert r.json()["detail"]


def test_too_many_chars(client):
    chars = {chr(0x4E00 + i): SHI for i in range(ud.HANDFONT_MAX_CHARS + 1)}
    r = _post(client, chars)
    assert r.status_code == 413 and "最多" in r.json()["detail"]


def test_too_many_strokes(client):
    r = _post(client, {"十": SHI[:1] * (ud.HANDFONT_MAX_STROKES_PER_CHAR + 1)})
    assert r.status_code == 413


def test_too_many_points_per_stroke(client):
    long = [[[i % 2048, 1000] for i in range(ud.HANDFONT_MAX_POINTS_PER_STROKE + 1)]]
    assert _post(client, {"十": long}).status_code == 413


def test_body_size_cap(client):
    r = client.post("/api/handfont", content=b"{}", headers={
        "content-type": "application/json",
        "content-length": str(ud.HANDFONT_MAX_BODY_BYTES + 1)})
    assert r.status_code in (413, 422)


@pytest.mark.parametrize("kw", [{"weight": 0}, {"weight": 401},
                                {"cap": "pointy"}, {"owner": "x" * 41}])
def test_bad_params(client, kw):
    assert _post(client, {"十": SHI}, **kw).status_code == 422


def test_taps_dropped_but_real_strokes_kept(client):
    r = _post(client, {"十": SHI + [[[5, 5]]]})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 掛點：閘門、計數、sync def
# ---------------------------------------------------------------------------

def test_endpoint_is_gated_and_counted(client):
    assert "/api/handfont" in RENDER_CACHE_PREFIXES
    _post(client, {"十": SHI})
    assert client.get("/api/metrics").json()["mode"].get("handfont") == 1


def test_endpoint_is_sync_def():
    """重 CPU 端點必須 sync def（走 threadpool）——async def 會凍 event loop（5ck）。"""
    import inspect
    assert not inspect.iscoroutinefunction(ud.handfont_post)
