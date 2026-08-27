"""5eu（架構健檢 W2）：重渲染回應快取＋ETag＋失效契約。"""
from __future__ import annotations

import gzip
import json

import pytest

# D3：本檔以光柵化/PDF 為主——整檔標 slow（開發可 -m 'not slow' 跳過）
pytestmark = pytest.mark.slow
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


# ---------------------------------------------------------------------------
# 5ex：預覽 GET 化（A1）＋渲染併發閘門（B）
# ---------------------------------------------------------------------------


def test_5ex_sutra_get_glyph_chars_three_states(client):
    """GET /api/sutra 支援 glyph_chars 三態（與 POST 同語意）＋可快取。"""
    base = {"preset": "heart_sutra", "page_type": "body", "page_index": 0,
            "emit_cellmap": "true", "show_original_glyph": "true"}
    # ""＝零載入純版面：cellmap 有、字形層無
    blank = client.get("/api/sutra", params={**base, "glyph_chars": ""})
    assert blank.status_code == 200
    assert 'id="sutra-cellmap"' in blank.text
    assert 'id="sutra-trace"' not in blank.text
    # 子集＝遠小於完整版
    full = client.get("/api/sutra", params=base)
    assert full.status_code == 200
    import re
    m = re.search(r'data-char="([^"]+)"', blank.text)
    sub = client.get("/api/sutra",
                     params={**base, "glyph_chars": m.group(1)})
    assert sub.status_code == 200
    assert len(sub.content) < len(full.content) / 2
    # 可快取：同參數第二發命中（POST 自 5bz 起是快取盲區——A1 主目的）
    again = client.get("/api/sutra", params={**base, "glyph_chars": ""})
    assert again.headers["x-render-cache"] == "hit"
    assert again.content == blank.content


def test_5ex_render_gate_caps_concurrency(monkeypatch):
    """閘門：同時渲染 ≤ RENDER_GATE_MAX；排隊不拒絕（全部 200）。

    注意測試法：TestClient 每請求各開事件迴圈，跨迴圈搶同一顆
    asyncio.Semaphore 會死鎖（正式環境 uvicorn 單迴圈無此事）——
    改用 ASGITransport 在單一迴圈上 gather 真併發。
    """
    import asyncio

    import httpx

    monkeypatch.setattr(srv, "RENDER_GATE_MAX", 1)
    app = create_app()

    async def main():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
                transport=transport, base_url="http://t") as c:
            rs = await asyncio.gather(
                *[c.get("/api/grid", params={"chars": ch})
                  for ch in "永和安心"])
            return [r.status_code for r in rs]

    results = asyncio.run(main())
    assert results == [200, 200, 200, 200]
    assert app.state.render_gate_stat["peak"] == 1
    assert app.state.render_gate_stat["active"] == 0


def test_5ex_gate_default_and_cache_hit_bypasses_gate(client):
    """預設上限 2；快取命中不過閘門（peak 不因 hit 增加）。"""
    assert srv.RENDER_GATE_MAX == 2
    app = client.app
    r1 = client.get("/api/grid", params={"chars": "心"})
    peak_after_miss = app.state.render_gate_stat["peak"]
    r2 = client.get("/api/grid", params={"chars": "心"})
    assert r2.headers["x-render-cache"] == "hit"
    assert app.state.render_gate_stat["peak"] == peak_after_miss


def test_5ex_opencc_init_publish_order_race(monkeypatch):
    """5ex 修：_ensure_opencc 併發冷初始化不得讓他緒看到半成品。

    注入慢速 OpenCC（s2t 建構刻意 sleep）重現原 race：舊版 guard
    （_opencc_t2s）先發布，他緒在空窗呼叫 to_traditional 會炸
    'NoneType' object is not callable。修後 guard 最後發布，全綠。
    """
    import sys
    import threading
    import time
    import types

    import stroke_order.variants as V

    monkeypatch.setattr(V, "_opencc_t2s", None)
    monkeypatch.setattr(V, "_opencc_s2t", None)

    class SlowCC:
        def __init__(self, mode):
            if mode == "s2t":
                time.sleep(0.05)      # 拉開兩顆建構的空窗
            self._mode = mode

        def convert(self, ch):
            return ch

    fake = types.ModuleType("opencc")
    fake.OpenCC = SlowCC
    monkeypatch.setitem(sys.modules, "opencc", fake)

    errors = []

    def worker():
        try:
            for _ in range(20):
                V.to_traditional("测")
                V.to_simplified("測")
        except Exception as e:      # 舊版：TypeError NoneType not callable
            errors.append(e)

    ts = [threading.Thread(target=worker) for _ in range(6)]
    for th in ts:
        th.start()
    for th in ts:
        th.join()
    assert errors == [], errors


def test_5ex_capacity_probe_exempt_from_gate():
    """容量預檢（打字即發、輕量）不過閘門——peak 不因 capacity 增加。"""
    app = create_app()
    c = TestClient(app)
    r = c.get("/api/letter/capacity", params={"text": "測試"})
    assert r.status_code == 200
    assert app.state.render_gate_stat["peak"] == 0   # 從未進閘門
    r2 = c.get("/api/grid", params={"chars": "測"})
    assert r2.status_code == 200
    assert app.state.render_gate_stat["peak"] == 1   # 一般渲染有進


# ---------------------------------------------------------------------------
# 5ey：表格頁分段載入（D）＋記憶體衛生（E）
# ---------------------------------------------------------------------------


def test_5ey_table_page_glyph_chars_three_states(client):
    """單字格表格頁（週期表）吃 glyph_chars 三態——與 body 同語意。"""
    base = {"preset": "periodic_table", "page_type": "table",
            "emit_cellmap": "true", "show_original_glyph": "true"}
    blank = client.get("/api/sutra", params={**base, "glyph_chars": ""})
    assert blank.status_code == 200
    assert 'id="sutra-cellmap"' in blank.text     # 版面/格線/cellmap 齊全
    full = client.get("/api/sutra", params=base)
    assert full.status_code == 200
    import re
    m = re.search(r'data-char="([^"]+)"', blank.text)
    sub = client.get("/api/sutra", params={**base, "glyph_chars": m.group(1)})
    assert sub.status_code == 200
    assert len(sub.content) < len(full.content)   # 子集 < 完整


def test_5ey_selfdrawn_table_blank_still_200(client):
    """自繪多字表格（乘法表）帶 glyph_chars=""：伺服器不炸（前端偵測
    無 cellmap 後回退一次性完整渲染，不會用到這個空殼）。"""
    r = client.get("/api/sutra", params={
        "preset": "multiplication_table", "page_type": "table",
        "glyph_chars": ""})
    assert r.status_code == 200


def test_5ey_glyph_cache_lru_cap():
    """字型源字形快取 LRU：超上限淘汰最舊、hit 沿用記號。"""
    from collections import OrderedDict

    from stroke_order.sources.glyph_cache import GLYPH_CACHE_MAX, lru_put
    assert GLYPH_CACHE_MAX == 384   # 5fb：實測 63KB/字 → 384≈24MB/源
    c = OrderedDict()
    for i in range(5):
        lru_put(c, i, str(i), max_entries=3)
    assert list(c) == [2, 3, 4]                   # 0,1 淘汰
    c.move_to_end(2)                              # hit 沿用
    lru_put(c, 9, "9", max_entries=3)
    assert list(c) == [4, 2, 9]                   # 3 被淘汰、2 因 hit 保留
    # 三個外框字型源都掛上 LRU
    import inspect

    from stroke_order.sources import chongxi_seal, cns_font, moe_lishu
    for mod in (chongxi_seal, cns_font, moe_lishu):
        src = inspect.getsource(mod)
        assert "lru_put(self._cache" in src, mod.__name__
        assert "move_to_end(char)" in src, mod.__name__


def test_5ey_release_memory_hook_in_gate():
    """渲染閘門 active 歸零時 gc+malloc_trim（RSS 棘輪對策）標記。"""
    import inspect

    from stroke_order.web import server as srv_mod
    src = inspect.getsource(srv_mod)
    assert "malloc_trim" in src
    assert "gc.collect()" in src
    assert '_release_memory()' in src


# ---------------------------------------------------------------------------
# 5ff：表格頁補 5bz 參考字形層（空白格真根因）
# ---------------------------------------------------------------------------


def test_5ff_table_emits_reference_layer(tmp_path, monkeypatch):
    """5ff：篆/隸骨架層設計上 0.03 近隱形（5ca），預覽可見度由
    sutra-glyph-reference 淡色原字層扛——表格 wrapper 先前沒轉發
    show_original_glyph（§26 單一未轉發旗標同款）＝週期表×篆書
    整頁看起來空白。鎖：旗開→參考層存在且有內容；旗關→不吐
    （plotter 下載語意不變）；glyph_chars 過濾同樣約束參考層。"""
    from pathlib import Path
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
        "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/mingliu.ttc",
    ]
    src = next((f for f in candidates if Path(f).exists()), None)
    if src is None:
        pytest.skip("無系統 CJK 字型可裁子集")
    from fontTools import subset as ft_subset
    from fontTools.ttLib import TTFont
    font = TTFont(src, fontNumber=0, lazy=True)
    ss = ft_subset.Subsetter()
    ss.populate(text="金里")
    ss.subset(font)
    out = tmp_path / "seal_5ff.otf"
    font.save(str(out))
    monkeypatch.setenv("STROKE_ORDER_SEAL_FONT_FILE", str(out))
    import stroke_order.sources.chongxi_seal as cs
    cs.reset_seal_singleton()
    try:
        c = TestClient(create_app())
        base = {"preset": "periodic_table", "page_type": "table",
                "style": "seal_script", "emit_cellmap": "true",
                "show_original_glyph": "true", "glyph_chars": "鋰"}
        t = c.get("/api/sutra", params=base).text
        assert 'id="sutra-glyph-reference"' in t
        ref = t.split('id="sutra-glyph-reference"')[1].split("</g>")[0]
        assert len(ref) > 50                       # 參考層有墨
        t2 = c.get("/api/sutra",
                   params={**base, "show_original_glyph": "false"}).text
        assert "sutra-glyph-reference" not in t2   # 下載語意不變
        t3 = c.get("/api/sutra", params={**base, "glyph_chars": ""}).text
        if "sutra-glyph-reference" in t3:          # 空集合＝零參考字
            assert len(t3.split('id="sutra-glyph-reference"')[1]
                       .split("</g>")[0]) < 50
    finally:
        cs.reset_seal_singleton()


def test_5fg_traced_run_three_states():
    """5fg：自繪表格共用描紅片段的三態語意——①外框字填色照舊
    ②骨架字＋參考 loader → 參考層 0.55＋骨架 0.03 ③骨架字無參考
    → 骨架可見 0.55（誠實降級：空白比瑕疵更糟）。"""
    from stroke_order.exporters.sutra import traced_run
    from stroke_order.ir import Character, Stroke, Point

    def _mk(outline_cmds, track_pts):
        return Character(
            char="測", unicode_hex="6e2c",
            strokes=[Stroke(index=0, raw_track=track_pts,
                            outline=outline_cmds,
                            kind_code=0, kind_name="其他",
                            has_hook=False)],
            data_source="test")

    track = [Point(x=100, y=100), Point(x=1900, y=1900)]
    outlined = _mk([{"type": "M", "x": 100, "y": 100},
                    {"type": "L", "x": 1900, "y": 100},
                    {"type": "L", "x": 1900, "y": 1900},
                    {"type": "Z"}], track)
    skeleton_only = _mk([], track)

    # ① 外框字 → 填色群組（stroke=none 維持）
    s1 = traced_run("測", 100, 100, 10, lambda ch: outlined, fill="#ccc")
    assert 'fill="#ccc" stroke="none"' in s1 and "polyline" not in s1

    # ② 骨架字＋參考 → 參考層 0.55 有墨；骨架 0.03 近隱形
    s2 = traced_run("測", 100, 100, 10, lambda ch: skeleton_only,
                    fill="#ccc",
                    outline_glyph_loader=lambda ch: outlined)
    assert 'opacity="0.55"' in s2          # 參考層
    assert 'opacity="0.030"' in s2         # 骨架維持近隱形
    assert "<path" in s2 and "polyline" in s2

    # ③ 骨架字、無參考 → 骨架「可見」stroke（絕不再 stroke="none" 包骨架）
    s3 = traced_run("測", 100, 100, 10, lambda ch: skeleton_only,
                    fill="#ccc")
    assert 'stroke="#ccc"' in s3 and 'opacity="0.55"' in s3
    assert "polyline" in s3
    # 隱形三要件皆不得出現在骨架群組：stroke=none 包 polyline
    import re
    for g in re.findall(r"<g[^>]*>", s3):
        if "stroke=\"none\"" in g:
            raise AssertionError("skeleton wrapped in stroke=none again")
