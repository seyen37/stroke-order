"""Shared pytest fixtures."""
from pathlib import Path

import pytest

from stroke_order.sources.g0v import G0VSource


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def source() -> G0VSource:
    """Network-disabled G0V source reading from tests/fixtures/."""
    return G0VSource(cache_dir=FIXTURES_DIR, allow_network=False)


@pytest.fixture(scope="module")
def client():
    """共用 TestClient（5ev conftest 上收）：每測試模組一個新 app。

    需要特殊環境（dev-mode env、monkeypatch 字型路徑、function 隔離
    如 render cache 測試）的檔案，照舊在該檔定義同名 fixture 覆蓋即可
    （pytest 最近者優先）。
    """
    from fastapi.testclient import TestClient

    from stroke_order.web.server import create_app

    return TestClient(create_app())


@pytest.fixture(scope="module")
def index_bundle(client):
    """W4-R1：index.html＋modes/*.js 串接（照載入序）。

    拆檔前「前端含 X」的斷言打在 / 回應整包 inline script 上；拆檔後
    JS 住 /static/modes/——凡斷言對象是**行為（JS）**而非**版面
    （markup）**的測試改用本 fixture，語意與拆檔前一致。
    """
    import re

    html = client.get("/").text
    parts = [html]
    for m in re.finditer(r'/static/modes/(\w+)\.js', html):
        r = client.get(f"/static/modes/{m.group(1)}.js")
        assert r.status_code == 200, m.group(0)
        parts.append(r.text)
    return "".join(parts)


@pytest.fixture
def established_authors(monkeypatch):
    """5fy：關閉「首次上傳 24h 審閱期」視窗——讓既有測試以
    『老帳號（首件已滿 24h）』視角驗證公開列表／下載行為。
    審閱期本身的行為由 test_gallery_protection.py 專測。"""
    from stroke_order.gallery import service
    monkeypatch.setattr(service, "_first_upload_window_active",
                        lambda uid: False)
