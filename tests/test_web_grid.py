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
