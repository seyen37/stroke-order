"""
Blueprint Phase 0 三件套的守門：D2 需求儀器化＋W0 老師說明頁。
（D3 測試分層由本檔的 marker 註冊測試鎖住。）

D2 的設計約束（隱私）在這裡鎖死：**只數次數，不記人**——snapshot 裡
不得出現 IP/UA/cookie/時間序列欄位。§99 的儀器化精神：缺字計數是 R2
翻案的感測器，模式計數是路線圖 gate 的溫度計。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.web import metrics
from stroke_order.web.server import create_app

_ROOT = Path(__file__).resolve().parent.parent
_GUIDE = _ROOT / "src" / "stroke_order" / "web" / "static" / "guide.html"


@pytest.fixture
def metrics_env(tmp_path, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_METRICS_DIR", str(tmp_path))
    metrics.reset_for_tests()
    yield tmp_path
    metrics.reset_for_tests()


@pytest.fixture
def client(metrics_env):
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# D2 核心：計數器
# ---------------------------------------------------------------------------


def test_d2_record_and_snapshot(metrics_env):
    metrics.record_mode("grid")
    metrics.record_mode("grid")
    metrics.record_mode("steps")
    metrics.record_missing_char("𪚥")
    s = metrics.snapshot()
    assert s["mode"] == {"grid": 2, "steps": 1}
    assert s["missing_char"] == {"𪚥": 1}
    assert "since" in s


def test_d2_persists_and_reloads(metrics_env):
    metrics.record_mode("grid")
    s1 = metrics.snapshot()               # 強制 flush
    metrics.reset_for_tests()             # 模擬重啟（同一目錄）
    metrics.record_mode("grid")
    s2 = metrics.snapshot()
    assert s2["mode"]["grid"] == 2
    assert s2["since"] == s1["since"], "since＝檔案視窗起點，重載不重置"


def test_d2_missing_char_cap_overflows_honestly(metrics_env):
    for i in range(metrics.MISSING_CHAR_CAP):
        metrics.record_missing_char(chr(0x4E00 + i))
    metrics.record_missing_char("龘")     # 超過上限的新 key
    s = metrics.snapshot()
    assert len(s["missing_char"]) == metrics.MISSING_CHAR_CAP
    assert "龘" not in s["missing_char"]
    assert s["missing_char_overflow"] == 1
    # 既有 key 不受上限影響
    metrics.record_missing_char(chr(0x4E00))
    assert metrics.snapshot()["missing_char"][chr(0x4E00)] == 2


def test_d2_no_pii_fields_ever(metrics_env, client):
    """隱私設計約束：快照裡不得出現任何請求脈絡欄位。"""
    client.get("/api/grid", params={"chars": "春"})
    s = client.get("/api/metrics").json()
    assert set(s.keys()) == {"since", "mode", "missing_char",
                             "missing_char_overflow"}
    dump = json.dumps(s)
    for banned in ("ip", "user_agent", "cookie", "session", "referer"):
        assert banned not in dump.lower()


def test_d2_thread_safety_smoke(metrics_env):
    def hammer():
        for _ in range(200):
            metrics.record_mode("grid")
    ts = [threading.Thread(target=hammer) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert metrics.snapshot()["mode"]["grid"] == 1600


def test_d2_unwritable_dir_does_not_break_requests(monkeypatch, tmp_path):
    """寫不進磁碟只是失去持久化——計數活在記憶體、主流程不受影響。"""
    blocked = tmp_path / "f"
    blocked.write_text("not a dir")
    monkeypatch.setenv("STROKE_ORDER_METRICS_DIR", str(blocked / "x"))
    metrics.reset_for_tests()
    metrics.record_mode("grid")           # 不得拋例外
    assert metrics.snapshot()["mode"]["grid"] == 1
    metrics.reset_for_tests()


# ---------------------------------------------------------------------------
# D2 掛點：middleware 與缺字
# ---------------------------------------------------------------------------


def test_d2_mode_counted_via_middleware(client):
    client.get("/api/grid", params={"chars": "春"})
    client.get("/api/grid", params={"chars": "天"})
    client.get("/teach")
    s = client.get("/api/metrics").json()
    assert s["mode"]["grid"] == 2
    assert s["mode"]["teach_page"] == 1


def test_d2_unlisted_paths_not_counted(client):
    client.get("/api/health")
    client.get("/api/coverset/list")
    s = client.get("/api/metrics").json()
    assert "health" not in json.dumps(s["mode"])


def test_d2_missing_char_recorded_on_404(client):
    r = client.get("/api/character/𪚥", params={"source": "g0v"})
    assert r.status_code == 404
    s = client.get("/api/metrics").json()
    assert s["missing_char"].get("𪚥", 0) >= 1


def test_d2_metrics_endpoint_in_snapshot():
    from tests.test_route_snapshot import ROUTE_SNAPSHOT
    assert ("GET", "/api/metrics") in ROUTE_SNAPSHOT
    assert ("GET", "/guide") in ROUTE_SNAPSHOT


# ---------------------------------------------------------------------------
# D3：marker 註冊與分層存在
# ---------------------------------------------------------------------------


def test_d3_slow_marker_registered_and_used():
    py = (_ROOT / "pyproject.toml").read_text("utf-8")
    assert "slow:" in py, "pyproject 未註冊 slow marker"
    marked = [f for f in ("test_page_pdf", "test_sutra", "test_render_cache",
                          "test_chiron_round_vf", "test_popup")
              if "pytestmark = pytest.mark.slow"
              in (_ROOT / "tests" / f"{f}.py").read_text("utf-8")]
    assert len(marked) == 5, f"慢檔標記缺漏：{marked}"


# ---------------------------------------------------------------------------
# W0：老師說明頁
# ---------------------------------------------------------------------------


def test_w0_guide_page_serves(client):
    r = client.get("/guide")
    assert r.status_code == 200
    assert "給老師" in r.text and "字帖" in r.text and "/teach" in r.text


def test_w0_guide_is_self_contained_and_honest():
    page = _GUIDE.read_text("utf-8")
    # 自包含：無外連資源
    assert "http://" not in page and "https://" not in page
    # 誠實措辭：不拿年級當賣點（W4 原則），出處照實
    stripped = page.replace("不代表年級難度", "")
    assert "年級" not in stripped
    assert "教育部" in page and "禁止改作" in page
    # 誠實缺字語（§87）
    assert "查無此字" in page
