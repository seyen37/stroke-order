"""
5fv — 統一出口信封（stroke-order-export-v1）。

三層驗證：

1. **單元**：embed / parse round-trip、CDATA 注入防禦、冪等。
2. **守門回歸鎖（§70 掃全類）**：routes 層每個 ``svg_response(`` 呼叫點
   必須明示 ``mode=``；每個 ``render_pages_as_single_or_zip(`` /
   ``render_pages_as_zip(`` 呼叫點必須明示 ``envelope_mode=``。未來新
   模式漏嵌直接紅燈；刻意不嵌的例外進 ``_SCAN_WHITELIST``。
3. **功能**：實打各模式端點，驗回應 SVG（含多頁 zip 逐頁）帶正確
   mode 與 app_version 的信封。

前端對應（禪繞 pathsToSvg）在 ``tests/test_zentangle_exporters.mjs``。
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from stroke_order.exporters.envelope import (
    EXPORT_SCHEMA_TAG,
    build_envelope_json,
    embed_export_envelope,
    parse_export_envelope,
)
from stroke_order.web.versioning import APP_VERSION


_MIN_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect/></svg>'

# 沿用 test_stencil.py 慣例：楷書字模不進版控，缺則 skip 不 fail（§68 姊妹律）
_TEST_KAISHU_FONT = "/tmp/moe-kaishu/edukai-5.1_20251208.ttf"
needs_kaishu = pytest.mark.skipif(
    not Path(_TEST_KAISHU_FONT).exists(),
    reason="MoE Kaishu absent; copy edukai-5.1*.ttf to /tmp/moe-kaishu/",
)


# ===========================================================================
# 1) 單元
# ===========================================================================

def test_embed_and_parse_roundtrip():
    out = embed_export_envelope(
        _MIN_SVG, mode="grid", app_version="1.2.3",
        params={"chars": "永"})
    data = parse_export_envelope(out)
    assert data == {
        "schema": EXPORT_SCHEMA_TAG,
        "mode": "grid",
        "app_version": "1.2.3",
        "params": {"chars": "永"},
    }
    # metadata 緊接 <svg> 開標籤後
    assert out.index("<metadata>") > out.index("<svg")
    assert out.index("<metadata>") < out.index("<rect")


def test_embed_minimal_fields_only():
    out = embed_export_envelope(_MIN_SVG, mode="sutra")
    data = parse_export_envelope(out)
    assert data == {"schema": EXPORT_SCHEMA_TAG, "mode": "sutra"}


def test_embed_idempotent_no_double_envelope():
    once = embed_export_envelope(_MIN_SVG, mode="grid")
    twice = embed_export_envelope(once, mode="letter")
    assert twice == once  # 已含信封 → 原樣返回、不覆寫
    assert twice.count("<stroke-order-export>") == 1
    assert twice.count("</stroke-order-export>") == 1


def test_embed_empty_mode_raises():
    with pytest.raises(ValueError):
        embed_export_envelope(_MIN_SVG, mode="")


def test_embed_without_svg_tag_returns_unchanged():
    assert embed_export_envelope("not svg at all", mode="grid") == \
        "not svg at all"


def test_cdata_injection_escaped():
    # params 內含 ]]> 不得提早關閉 CDATA
    body = build_envelope_json("grid", params={"note": "evil]]>payload"})
    assert "]]>" not in body
    out = embed_export_envelope(
        _MIN_SVG, mode="grid", params={"note": "evil]]>payload"})
    data = parse_export_envelope(out)
    assert data is not None and data["params"]["note"] == "evil]]>payload"


def test_parse_garbage_returns_none():
    assert parse_export_envelope(_MIN_SVG) is None
    bad = (_MIN_SVG.replace(
        "<rect/>",
        "<metadata><stroke-order-export><![CDATA[{broken"
        "]]></stroke-order-export></metadata>"))
    assert parse_export_envelope(bad) is None


def test_deterministic_output():
    a = embed_export_envelope(_MIN_SVG, mode="grid", app_version="1.0.0")
    b = embed_export_envelope(_MIN_SVG, mode="grid", app_version="1.0.0")
    assert a == b  # 信封不含時間戳——同輸入位元相同（dedup 友善）


# ===========================================================================
# 2) 守門回歸鎖：呼叫點掃描（§70——同類病掃全類）
# ===========================================================================

_ROUTES_DIR = (Path(__file__).resolve().parent.parent
               / "src" / "stroke_order" / "web" / "routes")

#: 刻意不帶信封的呼叫點（"檔名:呼叫起始行首 80 字" 描述；目前無）
_SCAN_WHITELIST: set[str] = set()


def _call_sites(source: str, func_name: str):
    """抓出 ``func_name(`` 每個呼叫點的完整參數文字（括號配對）。"""
    sites = []
    needle = func_name + "("
    start = 0
    while True:
        i = source.find(needle, start)
        if i < 0:
            break
        # 跳過 import 行與定義行
        line_start = source.rfind("\n", 0, i) + 1
        line = source[line_start:source.find("\n", i)]
        if line.lstrip().startswith(("from ", "import ", "def ")):
            start = i + len(needle)
            continue
        depth, j = 0, i + len(needle) - 1
        while j < len(source):
            if source[j] == "(":
                depth += 1
            elif source[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        sites.append(source[i:j + 1])
        start = j
    return sites


def test_gate_all_svg_response_calls_declare_mode():
    """routes 層每個 svg_response 呼叫點都要明示 mode=（信封憑據）。"""
    misses = []
    for f in sorted(_ROUTES_DIR.glob("*.py")):
        src = f.read_text(encoding="utf-8")
        for call in _call_sites(src, "svg_response"):
            key = f"{f.name}:{call[:80]}"
            if "mode=" not in call and key not in _SCAN_WHITELIST:
                misses.append(key)
    assert not misses, (
        "svg_response 呼叫點缺 mode=（信封憑據；刻意例外請進 "
        f"_SCAN_WHITELIST）：{misses}")


def test_gate_all_multipage_calls_declare_envelope_mode():
    """routes 層每個多頁打包呼叫點都要明示 envelope_mode=。"""
    misses = []
    for f in sorted(_ROUTES_DIR.glob("*.py")):
        src = f.read_text(encoding="utf-8")
        for fn in ("render_pages_as_single_or_zip", "render_pages_as_zip"):
            for call in _call_sites(src, fn):
                key = f"{f.name}:{call[:80]}"
                if "envelope_mode=" not in call and key not in _SCAN_WHITELIST:
                    misses.append(key)
    assert not misses, (
        "多頁打包呼叫點缺 envelope_mode=（zip 內每頁 SVG 的信封；"
        f"刻意例外請進 _SCAN_WHITELIST）：{misses}")


# ===========================================================================
# 3) 功能：實打端點驗信封（參數沿用各模式既有測試的最小組合）
# ===========================================================================

def _assert_envelope(svg_text: str, mode: str):
    data = parse_export_envelope(svg_text)
    assert data is not None, f"{mode}: 回應 SVG 缺信封"
    assert data["schema"] == EXPORT_SCHEMA_TAG
    assert data["mode"] == mode
    assert data["app_version"] == APP_VERSION
    assert svg_text.count("<stroke-order-export") == 1, "信封恰一份"


@pytest.mark.parametrize("url,mode", [
    ("/api/grid?chars=永&cols=3", "grid"),
    ("/api/manuscript?text=永一日", "manuscript"),
    ("/api/notebook?text=一&preset=small", "notebook"),
    ("/api/letter?text=永&preset=A5", "letter"),
    ("/api/export/永?format=svg", "single"),
    ("/api/wordart?shape=square&shape_size_mm=200&char_size_mm=15",
     "wordart"),
    ("/api/patch?text=吉&preset=rectangle", "patch"),
    ("/api/stamp?text=吉&preset=square_name", "stamp"),
])
def test_endpoint_svg_carries_envelope(client, url, mode):
    r = client.get(url)
    assert r.status_code == 200, f"{url} → {r.status_code}"
    assert r.headers["content-type"].startswith("image/svg+xml")
    _assert_envelope(r.text, mode)


def test_sutra_post_svg_carries_envelope(client):
    r = client.post("/api/sutra", json={
        "preset": "heart_sutra",
        "page_type": "dedication",
        "dedicator": "test",
        "target": "test",
        "dedication_verse": "天地人山水日月",
    })
    assert r.status_code == 200
    _assert_envelope(r.text, "sutra")


@needs_kaishu
def test_stencil_svg_carries_envelope(client):
    r = client.get("/api/stencil?chars=明&kind=stencil&format=svg")
    assert r.status_code == 200
    _assert_envelope(r.text, "stencil")


def test_doodle_svg_carries_envelope(client):
    from PIL import Image
    img = Image.new("L", (60, 60), 255)
    for x in range(15, 45):
        for y in range(15, 45):
            img.putpixel((x, y), 0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r = client.post("/api/doodle",
                    files={"image": ("t.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200
    _assert_envelope(r.text, "doodle")


def test_notebook_multipage_zip_every_page_has_envelope(client):
    r = client.get("/api/notebook?text=" + "一" * 1000 + "&preset=small")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/zip"), \
        "1000 字應超過單頁（此斷言若因容量調整而破，調大字數即可）"
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        names = [n for n in z.namelist() if n.endswith(".svg")]
        assert len(names) >= 2
        for n in names:
            _assert_envelope(z.read(n).decode("utf-8"), "notebook")


def test_single_page_via_multipage_exit_has_envelope(client):
    # N==1 走 render_pages_as_single_or_zip 的單頁分支——同樣要有信封
    r = client.get("/api/manuscript?text=永")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    _assert_envelope(r.text, "manuscript")


def test_envelope_valid_json_inside_response(client):
    r = client.get("/api/grid?chars=永&cols=3")
    raw = r.text.split("<![CDATA[", 1)[1].split("]]>", 1)[0]
    payload = json.loads(raw)
    assert payload["mode"] == "grid"
