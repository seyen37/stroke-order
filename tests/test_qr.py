"""
W3 — QR code：紙本 → 線上字典的動線。

字帖評估建議書盤出的三個缺口之一。同好的字帖產生器在每字旁附教育百科的
連結與 QR，學生印出來掃碼就能自學——這是那份借鏡裡最好的點子。

**關鍵：不需要教育百科的 API。** 它的 Open API 要註冊 api_key（執行期外部
相依＋密鑰管理，正是 §68／§86 根治掉的東西），但**詞條頁是純網址**，編碼
進 QR 完全離線可產。

本檔的三條核心不變式：
  · **emitter 正確**——我們自己組的 SVG 反解回暗模組集合，須 ≡ segno 的
    matrix。這是在驗我們的 emitter，不是在驗 segno。
  · **網址樣板單一事實源**——前端不得自己拼教育百科網址。
  · **自包含**——下載的教學單內 QR 是 inline SVG，零外連。
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from stroke_order.exporters.qr import (
    MAX_QR_TEXT,
    PEDIA_ENTRY_URL,
    QrUnavailable,
    is_available,
    pedia_url,
    qr_svg,
)
from stroke_order.web.server import create_app

_ROOT = Path(__file__).resolve().parent.parent
_TEACH = _ROOT / "src" / "stroke_order" / "web" / "static" / "teach.html"

needs_segno = pytest.mark.skipif(
    not is_available(),
    reason="segno 未安裝（web extras）",
)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def _dark_modules(svg: str) -> set[tuple[int, int]]:
    """反解我們產出的 SVG → {(row, col)} 暗模組集合。"""
    m = re.search(r'data-qr-modules="(\d+)" data-qr-quiet="(\d+)"', svg)
    assert m, "SVG 缺少 data-qr-* 錨點"
    quiet = int(m.group(2))
    # module_px 由第一個 rect 的 height 推得（所有 rect 同高）
    first = re.search(r'<rect x="\d+" y="\d+" width="\d+" height="(\d+)"/>',
                      svg)
    assert first, "SVG 沒有任何 rect"
    px = int(first.group(1))
    out: set[tuple[int, int]] = set()
    for x, y, w, _h in re.findall(
            r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"/>', svg):
        col = int(x) // px - quiet
        row = int(y) // px - quiet
        for i in range(int(w) // px):
            out.add((row, col + i))
    return out


# ---------------------------------------------------------------------------
# emitter 正確性——這才是我們寫的部分
# ---------------------------------------------------------------------------


@needs_segno
@pytest.mark.parametrize("text", [
    "https://pedia.cloud.edu.tw/Entry/Detail?title=%E6%98%A5",
    "https://example.com/",
    "短",
    "A" * 200,
])
def test_w3_svg_dark_modules_match_segno_matrix(text):
    """自組 SVG 反解回來的暗模組集合，須逐格等同 segno 的 matrix。

    這條直接鎖住 emitter：座標算錯、quiet zone 位移、同列合併 rect 的
    寬度算錯，全都會在這裡紅。
    """
    import segno
    want = {
        (r, c)
        for r, row in enumerate(segno.make(text, error="m").matrix)
        for c, v in enumerate(row) if v
    }
    assert _dark_modules(qr_svg(text)) == want


@needs_segno
def test_w3_svg_geometry_and_quiet_zone():
    svg = qr_svg("https://example.com/", module_px=5, quiet=3)
    head = re.search(r"<svg[^>]*>", svg).group(0)
    n = int(re.search(r'data-qr-modules="(\d+)"', head).group(1))
    side = (n + 2 * 3) * 5
    assert f'width="{side}"' in head and f'height="{side}"' in head
    assert f'viewBox="0 0 {side} {side}"' in head
    # 靜區內不得有任何暗模組
    mods = _dark_modules(svg)
    assert min(r for r, _ in mods) >= 0 and min(c for _, c in mods) >= 0
    assert max(r for r, _ in mods) < n and max(c for _, c in mods) < n


@needs_segno
def test_w3_finder_patterns_present():
    """三個角落的 7×7 定位圖案——沒有它掃描器根本找不到 QR。"""
    svg = qr_svg("https://example.com/")
    mods = _dark_modules(svg)
    n = max(r for r, _ in mods) + 1
    n = int(re.search(r'data-qr-modules="(\d+)"', svg).group(1))
    for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):
        # 外框全暗
        ring = [(r0, c0 + i) for i in range(7)] + \
               [(r0 + 6, c0 + i) for i in range(7)] + \
               [(r0 + i, c0) for i in range(7)] + \
               [(r0 + i, c0 + 6) for i in range(7)]
        assert all(p in mods for p in ring), f"定位圖案 {r0},{c0} 外框不完整"
        # 內部 3×3 全暗、其間的一圈全亮
        assert all((r0 + 2 + i, c0 + 2 + j) in mods
                   for i in range(3) for j in range(3))
        assert (r0 + 1, c0 + 1) not in mods


@needs_segno
def test_w3_rects_are_merged_not_one_per_module():
    """同列連續暗模組要合併——自包含教學單會內嵌它，標記量差很多。"""
    svg = qr_svg("https://pedia.cloud.edu.tw/Entry/Detail?title=%E6%98%A5")
    n_rects = svg.count("<rect")
    n_dark = len(_dark_modules(svg))
    assert n_rects < n_dark * 0.75, (
        f"沒有合併：{n_rects} 個 rect / {n_dark} 個暗模組")


@needs_segno
def test_w3_qr_svg_has_no_external_reference():
    """QR 是純幾何——不得出現任何外連（自包含鐵則的前置條件）。"""
    svg = qr_svg("https://example.com/")
    assert "http" not in svg.replace(
        'xmlns="http://www.w3.org/2000/svg"', ""), svg[:200]


@needs_segno
@pytest.mark.parametrize("bad", ["", "   ", "x" * (MAX_QR_TEXT + 1)])
def test_w3_qr_svg_rejects_bad_text(bad):
    with pytest.raises(ValueError):
        qr_svg(bad)


def test_w3_qr_svg_raises_when_segno_missing(monkeypatch):
    """segno 缺席拋 QrUnavailable——呼叫端才能降級為不印，而非整張失敗。"""
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "segno":
            raise ImportError("no segno")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(QrUnavailable):
        qr_svg("https://example.com/")


# ---------------------------------------------------------------------------
# 網址樣板：單一事實源
# ---------------------------------------------------------------------------


def test_w3_pedia_url_encodes_cjk():
    assert pedia_url("春") == PEDIA_ENTRY_URL.format(q=quote("春", safe=""))
    assert "%E6%98%A5" in pedia_url("春")
    assert "春" not in pedia_url("春"), "未編碼的中文會讓部分掃描器出錯"


def test_w3_pedia_url_rejects_empty():
    for bad in ("", "   "):
        with pytest.raises(ValueError):
            pedia_url(bad)


def test_w3_dict_endpoint_exposes_entry_url(client):
    r = client.get("/api/dict/春")
    assert r.status_code == 200
    assert r.json()["entry_url"] == pedia_url("春")


def test_w3_dict_entry_url_present_even_when_char_not_found(client):
    """查無此字也要給連結——教育百科的涵蓋範圍與我們的 bundle 不同。"""
    r = client.get("/api/dict/兀")
    assert r.status_code == 200
    body = r.json()
    assert body["entry_url"] == pedia_url("兀")


def test_w3_frontend_does_not_hardcode_the_url_template():
    """teach.html 不得自己拼教育百科網址——樣板只有 exporters/qr.py 一份。

    前端硬寫會變成第二個事實源：改樣板時不會有人記得改前端。
    """
    page = _TEACH.read_text("utf-8")
    assert "pedia.cloud" not in page, (
        "teach.html 出現教育百科網址字面值——應改用 /api/dict 的 entry_url")
    assert "entry_url" in page, "teach.html 應消費伺服器給的 entry_url"


def test_w3_teach_download_embeds_qr_inline():
    """自包含鐵則：下載檔內嵌 cur.qrSvg，不是 <img src=/api/qr>。"""
    page = _TEACH.read_text("utf-8")
    doc = page.split("function buildDoc()")[1]
    assert "cur.qrSvg" in doc, "buildDoc 沒有內嵌 QR"
    assert "/api/qr" not in doc, "下載檔不得外連 /api/qr（自包含鐵則）"


# ---------------------------------------------------------------------------
# /api/qr 端點
# ---------------------------------------------------------------------------


@needs_segno
def test_w3_qr_endpoint_returns_svg(client):
    r = client.get("/api/qr", params={"text": pedia_url("春")})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.text.lstrip().startswith("<svg")
    assert _dark_modules(r.text)


@needs_segno
def test_w3_qr_endpoint_honours_module_px(client):
    small = client.get("/api/qr", params={"text": "https://example.com/",
                                          "module_px": 2})
    big = client.get("/api/qr", params={"text": "https://example.com/",
                                        "module_px": 8})
    assert small.status_code == big.status_code == 200
    # 同樣的內容、不同的模組尺寸 → 暗模組集合相同、畫布邊長不同
    assert _dark_modules(small.text) == _dark_modules(big.text)
    side = lambda s: int(re.search(r'width="(\d+)"', s).group(1))  # noqa: E731
    assert side(big.text) == 4 * side(small.text)


@pytest.mark.parametrize("params", [
    {"text": ""},
    {"text": "   "},
    {"text": "x" * (MAX_QR_TEXT + 1)},
    {"text": "ok", "module_px": 0},
    {"text": "ok", "quiet": -1},
])
def test_w3_qr_endpoint_rejects_bad_input(client, params):
    r = client.get("/api/qr", params=params)
    assert r.status_code == 422, (params, r.status_code)


def test_w3_qr_endpoint_503_when_segno_missing(client, monkeypatch):
    """相依缺席回 503（暫時性），不是 500——前端據此降級為只留連結。"""
    import stroke_order.exporters.qr as qr_mod

    def boom(*a, **k):
        raise QrUnavailable("no segno")

    monkeypatch.setattr(qr_mod, "qr_svg", boom)
    r = client.get("/api/qr", params={"text": "https://example.com/"})
    assert r.status_code == 503
    assert "不影響" in r.json()["detail"], "訊息要說明降級後仍可用"


def test_w3_teach_page_still_works_without_qr(client):
    """QR 是加值，不是必要條件——/teach 與 /api/dict 不得因它失敗。"""
    assert client.get("/teach").status_code == 200
    assert client.get("/api/dict/春").status_code == 200
