"""Tests for /api/grid endpoint (字帖 in Web UI)."""
import pytest

try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS_WEB = True
except ImportError:
    _HAS_WEB = False

pytestmark = pytest.mark.skipif(
    not _HAS_WEB, reason="fastapi/httpx not installed"
)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_grid_basic(client):
    r = client.get("/api/grid?chars=永")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]
    assert b"<svg" in r.content


def test_grid_multi_char(client):
    r = client.get("/api/grid?chars=永日一&cols=3")
    assert r.status_code == 200


def test_grid_download_sets_attachment_header(client):
    r = client.get("/api/grid?chars=永&download=true")
    assert r.status_code == 200
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert "filename*=UTF-8''" in cd


# ----- Phase 5cn：自訂字型（瀏覽器端）--------------------------------------


def test_5cn_grid_cells_carry_data_attributes(client):
    """5cn：每格 <g> 帶 data-char / data-cell-style——前端注入定位用。"""
    r = client.get("/api/grid?chars=永日&cols=3")
    svg = r.text
    # 2 字 × 3 層（主字/ghost/blank）＝ 6 格，各帶 data-char
    assert svg.count('data-char="永"') == 3
    assert svg.count('data-char="日"') == 3
    assert svg.count('data-cell-style="ghost"') == 2
    assert svg.count('data-cell-style="blank"') == 2


def test_5cn_vendor_opentype_proxy(client, tmp_path, monkeypatch):
    """5cn：opentype.min.js 走同源代抓（植假快取，不打真網路）。"""
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    fake = b"/* fake opentype */" + b"y" * 150_000
    (vendor / "opentype.min.js").write_bytes(fake)
    monkeypatch.setenv("STROKE_ORDER_VENDOR_DIR", str(vendor))
    r = client.get("/vendor/opentype.min.js")
    assert r.status_code == 200
    assert r.content == fake
    assert "max-age" in r.headers.get("cache-control", "")
    # status 一併回報 opentype 快取狀態
    st = client.get("/vendor/status").json()
    assert st["opentype_cached"] is True
    assert st["opentype_size"] == len(fake)


def test_5cn_index_userfont_ui_and_injection(client):
    """5cn：字帖模式自訂字型 UI＋前端注入層存在。"""
    html = client.get("/").text
    assert 'value="userfont"' in html
    assert 'id="grid-font-file"' in html
    assert "injectUserFontIntoGrid" in html
    assert "/vendor/opentype.min.js" in html
    assert "XMLSerializer" in html            # 注入後的 SVG 走 blob 下載
    assert "未上傳" in html                   # 隱私/版權說明


def test_5cs_userfont_gcode_pipeline(client):
    """5cs：自訂字型機器軌跡——前端骨架化＋G-code 組裝存在，
    輸出慣例與 render_grid_gcode 對齊、明示非筆順。"""
    html = client.get("/").text
    assert "fontCharTracks" in html            # 光柵化→骨架化→EM 軌跡
    assert "gridUserFontGcode" in html         # G-code 組裝
    assert "zhangSuenThin" in html             # 復用 5cg 三件組
    assert "traceCenterlines" in html
    assert "G21 ; mm" in html                  # 慣例對齊
    assert "M3 S90" in html
    assert "非教育部筆順" in html              # 誠實標注（§8 能力邊界）
    assert "grid_userfont.gcode" in html       # blob 下載檔名


def test_5el_userfont_smooth_ui_wired(client):
    """5el：自訂字型平滑度 UI——gf-smooth 數字輸入在字型 wrap；fontCharTracks
    讀值、納入 cache key、傳給 chaikinSmooth（調平滑不回舊快取）。"""
    html = client.get("/").text
    assert 'id="gf-smooth"' in html                       # 平滑數字輸入
    assert 'getElementById("gf-smooth")' in html          # fontCharTracks 讀值
    # cache key 納入迭代數（否則調值回舊軌跡）
    assert 'gridUserFontName + ":" + ch + ":" + ckIters' in html
    # 迭代數餵給 Chaikin（取代原 hardcode 2）
    assert "eng.chaikinSmooth(eng.rdpSimplify(tr, 1.5), ckIters)" in html


def test_5ct_notebook_letter_userfont_ui(client):
    """5ct：筆記/信紙自訂字型 UI＋共用注入/下載接線存在。"""
    html = client.get("/").text
    # 三個模式的字型選單都有 userfont 選項（grid + nb + lt）
    assert html.count('<option value="userfont">') == 3
    assert "ufPageDownloads" in html                  # 頁面型下載接線
    assert 'ufPageDownloads("nb"' in html
    assert 'ufPageDownloads("lt"' in html
    # 伺服器只認標準 style——userfont 由前端映射為 kaishu
    assert html.count('=== "userfont"') >= 5


def test_5cu_grid_zhuyin_api_and_ui(client):
    """5cu：/api/grid zhuyin_map 參數（前端供給、伺服器零字典）＋
    UI 轉換表/checkbox/格距標記存在。"""
    r = client.get("/api/grid?chars=永&zhuyin_map=永:ㄩㄥˇ")
    assert r.status_code == 200
    assert 'class="zhuyin"' in r.text
    assert 'data-pair-em="3072"' in r.text
    r0 = client.get("/api/grid?chars=永")
    assert 'data-pair-em="2048"' in r0.text           # 不帶參數＝原版面

    html = client.get("/").text
    assert 'id="grid-zhuyin"' in html
    assert "pinyinToZhuyin" in html
    assert "gridZhuyinMap" in html
    assert "ZY_WHOLE" in html and "ZY_FIN" in html
    assert "data-pair-em" in html                     # 5cs gcode 格距修正


def test_grid_various_guide_styles(client):
    for guide in ("tian", "mi", "hui", "plain", "none"):
        r = client.get(f"/api/grid?chars=永&guide={guide}")
        assert r.status_code == 200


def test_grid_various_cell_styles(client):
    for style in ("outline", "trace", "filled", "ghost", "blank"):
        r = client.get(f"/api/grid?chars=永&cell_style={style}")
        assert r.status_code == 200


def test_grid_invalid_guide_pattern(client):
    r = client.get("/api/grid?chars=永&guide=bogus")
    assert r.status_code == 422


def test_grid_missing_char_skipped_not_fatal(client):
    # PUA + real char: PUA is skipped, real char renders
    r = client.get("/api/grid?chars=\ue000永")
    assert r.status_code == 200


def test_grid_all_missing_returns_400(client):
    r = client.get("/api/grid?chars=\ue000\ue001")
    assert r.status_code == 400


def test_index_html_mode_toggle(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "單字模式" in r.text
    assert "字帖模式" in r.text
    assert "grid-view" in r.text
