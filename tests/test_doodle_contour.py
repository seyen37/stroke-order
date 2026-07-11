"""Phase 5ch — 塗鴉伺服器引擎 contour 輪廓向量化。

背景：使用者實測回報——同一張照片在 VectorLine 得到輪廓向量，
本專案（伺服器引擎）卻是掃描線圖。5ch 把取樣方式重設計為
Otsu 二值化 → 邊界追蹤 → RDP 閉合路徑，預設 contour、
scanline 降為選項。
"""
from __future__ import annotations

import io
import re

import numpy as np
import pytest
from PIL import Image, ImageDraw

from stroke_order.exporters.doodle import (
    _loop_area,
    _otsu_threshold,
    _simplify_loop,
    _trace_boundary_loops,
    render_doodle_svg,
)

try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS_WEB = True
except ImportError:
    _HAS_WEB = False


# ---------------------------------------------------------------------------
# 純函式單元
# ---------------------------------------------------------------------------


def test_square_traces_single_loop_rdp_4_corners():
    m = np.zeros((40, 40), bool)
    m[10:30, 8:32] = True
    loops = _trace_boundary_loops(m)
    assert len(loops) == 1
    assert abs(_loop_area(loops[0]) - 480) < 1e-9   # 24×20
    assert len(_simplify_loop(loops[0], 1.0)) == 4


def test_ring_traces_outer_and_hole():
    """甜甜圈 → 外框＋孔洞兩個獨立閉環。"""
    m = np.zeros((60, 60), bool)
    yy, xx = np.mgrid[0:60, 0:60]
    r = np.hypot(xx - 30, yy - 30)
    m[(r >= 10) & (r <= 20)] = True
    loops = _trace_boundary_loops(m)
    assert len(loops) == 2
    # 閉環 RDP 退化基線防護：簡化後仍是多邊形而非塌縮
    assert all(len(_simplify_loop(lp, 1.0)) >= 8 for lp in loops)


def test_otsu_threshold_bimodal():
    g = np.concatenate([np.full(500, 40, np.uint8),
                        np.full(500, 210, np.uint8)]).reshape(20, 50)
    assert 40 <= _otsu_threshold(g) < 210


def _shapes_img() -> Image.Image:
    img = Image.new("RGB", (300, 200), "white")
    d = ImageDraw.Draw(img)
    d.ellipse([30, 30, 130, 130], fill="black")
    d.rectangle([180, 60, 260, 160], outline="black", width=8)
    return img


def test_render_contour_default_emits_closed_paths():
    svg = render_doodle_svg(_shapes_img(), canvas_width_mm=150)
    paths = re.findall(r'<path d="M[^"]+Z"/>', svg)
    assert len(paths) == 3        # 圓 1 ＋ 方框外緣/內緣 2
    assert "<line " not in svg    # 不再是掃描線


def test_render_scanline_style_preserved():
    svg = render_doodle_svg(_shapes_img(), canvas_width_mm=150,
                            style="scanline")
    assert svg.count("<line ") > 20


def test_contour_and_scanline_share_mm_header():
    a = render_doodle_svg(_shapes_img(), canvas_width_mm=150)
    b = render_doodle_svg(_shapes_img(), canvas_width_mm=150,
                          style="scanline")
    assert a.split(">")[0] == b.split(">")[0]   # 5bt mm 契約不動


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

pytestmark_api = pytest.mark.skipif(
    not _HAS_WEB, reason="fastapi/httpx not installed")


@pytest.fixture(scope="module")
def client():
    if not _HAS_WEB:
        pytest.skip("fastapi/httpx not installed")
    return TestClient(create_app())


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    _shapes_img().save(buf, format="PNG")
    return buf.getvalue()


def test_api_doodle_default_is_contour(client):
    r = client.post("/api/doodle",
                    files={"image": ("t.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    assert '<path d="M' in r.text
    assert "<line " not in r.text


def test_api_doodle_scanline_opt_in(client):
    r = client.post("/api/doodle",
                    files={"image": ("t.png", _png_bytes(), "image/png")},
                    data={"vector_style": "scanline"})
    assert r.status_code == 200
    assert "<line " in r.text


def test_api_doodle_rejects_bad_style(client):
    r = client.post("/api/doodle",
                    files={"image": ("t.png", _png_bytes(), "image/png")},
                    data={"vector_style": "sketchy"})
    assert r.status_code == 422


def test_5ci_responsiveness_fixes(client):
    """5ci：使用者複驗回報「OpenCV 無回應／解析度差」的三項修復。"""
    html = client.get("/").text
    # ① 解析度：UI 預設 200 → 500（contour 在 200px 上描是糊的）
    assert 'id="dd-max-side" type="number" value="500"' in html
    # ② 巨量 SVG 不再 innerHTML 直塞（renderer frozen 40s 實測）——
    #    預覽改 <img src=blob> 光柵顯示
    assert "塗鴉預覽" in html
    assert 'im.src = url' in html
    js = client.get("/static/doodle_engine.js").text
    # ③ 可觀察性：載入講清楚要等多久＋各階段進度
    assert "10~60 秒" in js
    assert "解碼與縮圖…" in js
    assert "二值化與輪廓抽取…" in js
    assert "條路徑）…" in js
    # ④ 大照片快徑：無裁切時跳過全解析度灰階
    assert "needCrop" in js


def test_5cj_vendor_proxy_and_same_origin_first(client, tmp_path,
                                                monkeypatch):
    """5cj：校網擋外部 CDN → OpenCV.js 改同源代抓。

    端點測試不打真網路：預先植入假快取檔（>1MB 門檻）驗證服務
    與快取標頭；引擎清單驗證同源位址排首位。
    """
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    fake = b"/* fake opencv.js */" + b"x" * 1_100_000
    (vendor / "opencv.js").write_bytes(fake)
    monkeypatch.setenv("STROKE_ORDER_VENDOR_DIR", str(vendor))
    r = client.get("/vendor/opencv.js")
    assert r.status_code == 200
    assert r.content == fake
    assert "max-age" in r.headers.get("cache-control", "")

    js = client.get("/static/doodle_engine.js").text
    urls_block = js.split("OPENCV_CDN_URLS = [")[1].split("]")[0]
    lines = [l.strip() for l in urls_block.splitlines() if '"' in l]
    assert lines[0].startswith('"/vendor/opencv.js"')   # 同源優先
    assert any("docs.opencv.org" in l for l in lines)   # CDN 備援仍在


def test_index_has_style_select_and_cdn_fix(client):
    html = client.get("/").text
    assert 'id="dd-server-style"' in html
    assert 'value="contour"' in html
    js = client.get("/static/doodle_engine.js").text
    # 5ch：4.10.0 死連結修正 → 4.9.0 pin ＋ 4.x 備援清單
    assert "OPENCV_CDN_URLS" in js
    assert "https://docs.opencv.org/4.9.0/opencv.js" in js
    assert "https://docs.opencv.org/4.x/opencv.js" in js
    # 死連結不再被引用（註解提及版號 OK，URL 不行）
    assert "https://docs.opencv.org/4.10.0/opencv.js" not in js
