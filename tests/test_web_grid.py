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
