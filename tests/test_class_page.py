"""
v0.14.302 R3——/class 課堂筆順頁契約。

互動流程由 Playwright 端到端驗過（WORK_LOG／ADR）；本檔鎖住：路由與版本
注入、教師主題、自包含（無外連）、只用本站端點、共用模組（不各寫一份
播放器／字義卡）、出處標示、計數掛點、前後端上限 parity。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.web import metrics
from stroke_order.web.server import create_app

_STATIC = Path(__file__).resolve().parent.parent / "src" / "stroke_order" / "web" / "static"
_PAGE = _STATIC / "class.html"
_CORE = _STATIC / "teacher" / "classcore.mjs"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_METRICS_DIR", str(tmp_path))
    metrics.reset_for_tests()
    yield TestClient(create_app())
    metrics.reset_for_tests()


def test_page_serves_with_version_injected(client):
    r = client.get("/class")
    assert r.status_code == 200
    assert "課堂筆順" in r.text
    assert "__V__" not in r.text
    for mod in ("teacher/theme.css", "teacher/player.mjs",
                "teacher/dictcard.mjs", "teacher/classcore.mjs"):
        assert re.search(re.escape(mod) + r"\?v=\d", r.text), mod


def test_shared_modules_served(client):
    for mod in ("player.mjs", "dictcard.mjs", "classcore.mjs"):
        r = client.get("/static/teacher/" + mod)
        assert r.status_code == 200 and "javascript" in r.headers["content-type"]


def test_self_contained_and_uses_own_endpoints():
    page = _PAGE.read_text("utf-8")
    assert "http://" not in page and "https://" not in page
    assert "/api/character/" in page and "/api/dict/" in page
    core = _CORE.read_text("utf-8")
    assert "/api/grid?" in core and "/api/steps?" in core


def test_reuses_shared_player_not_a_copy():
    """播放器／字義卡只有一份（teacher/*.mjs），頁面不得自寫 glyph 翻轉。"""
    page = _PAGE.read_text("utf-8")
    assert "StrokePlayer" in page and "sensesHtml" in page
    assert "scale(1, -1)" not in page


def test_attribution_and_honest_miss():
    page = _PAGE.read_text("utf-8")
    assert "禁止改作" in page and "教育部" in page and "g0v" in page
    assert "未收此字" in page          # 查無不裝懂
    assert "沒有「" in page             # 詞語查無照實說


def test_download_disabled_until_loaded():
    page = _PAGE.read_text("utf-8")
    i = page.index('id="dl-grid"')
    assert 'aria-disabled="true"' in page[i - 80:i + 120]


def test_max_chars_within_server_limits():
    m = re.search(r"export const MAX_CHARS = (\d+);", _CORE.read_text("utf-8"))
    assert m and 1 <= int(m.group(1)) <= 40      # /api/grid、/api/steps 上限 40


def test_grid_and_steps_urls_are_valid_requests(client):
    """classcore 產生的參數組合伺服器真的接受（svg 版免字型、快）。"""
    r = client.get("/api/grid", params={"chars": "花園花園花園", "guide": "mi",
                                        "cols": 10})
    assert r.status_code == 200
    r = client.get("/api/steps", params={"chars": "園", "guide": "mi",
                                         "cols": 9, "cell_size": 72,
                                         "format": "svg"})
    assert r.status_code == 200 and "svg" in r.headers["content-type"]


def test_metrics_bucket(client):
    client.get("/class")
    assert client.get("/api/metrics").json()["mode"]["class_page"] == 1
