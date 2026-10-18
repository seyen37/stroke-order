"""
v0.14.296（Blueprint v1.2 方案 C）——計數器跨重啟累計＋暫時性磁碟誠實標示。

Render 免費層閒置 15 分鐘休眠、醒來磁碟全空：D2 的計數器每次醒來歸零，
個人化線 gate（手寫字型下載數 >0）因此無從判定。本檔鎖住：

1. 沒設 Gist＝零網路呼叫、行為與先前相同（回歸鎖）。
2. 開機讀回是「加進來」不是覆蓋；重啟後累計不重複算。
3. **未讀回成功不推送**——不拿較小計數覆蓋遠端歷史。
4. 合併仍守缺字 key 上限。
5. /api/metrics 與分享庫頁的誠實標示。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.web import metrics
from stroke_order.web.server import create_app

_ROOT = Path(__file__).resolve().parent.parent


class FakeGist:
    """記憶體版 Gist：GET 回 files、PATCH 寫 files。"""

    def __init__(self, content: dict | None = None, fail_get: bool = False):
        self.content = content
        self.fail_get = fail_get
        self.calls: list[str] = []

    def __call__(self, method, gist_id, token, payload=None):
        self.calls.append(method)
        assert gist_id == "gid" and token == "tok"
        if method == "GET":
            if self.fail_get:
                raise ConnectionError("network down")
            files = {}
            if self.content is not None:
                files[metrics.GIST_FILENAME] = {
                    "content": json.dumps(self.content, ensure_ascii=False)}
            return {"files": files}
        if method == "PATCH":
            c = payload["files"][metrics.GIST_FILENAME]["content"]
            self.content = json.loads(c)
            return {}
        raise AssertionError(method)


@pytest.fixture
def menv(tmp_path, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_METRICS_DIR", str(tmp_path))
    for k in ("STROKE_ORDER_METRICS_GIST_ID", "STROKE_ORDER_METRICS_GIST_TOKEN",
              "STROKE_ORDER_EPHEMERAL_STORAGE"):
        monkeypatch.delenv(k, raising=False)
    metrics.reset_for_tests()
    yield monkeypatch
    metrics.reset_for_tests()


@pytest.fixture
def gist_on(menv):
    menv.setenv("STROKE_ORDER_METRICS_GIST_ID", "gid")
    menv.setenv("STROKE_ORDER_METRICS_GIST_TOKEN", "tok")
    return menv


def _install(monkeypatch, fake):
    monkeypatch.setattr(metrics, "_gist_api", fake)
    return fake


# ---------------------------------------------------------------------------
# 1. 沒設 Gist＝零網路
# ---------------------------------------------------------------------------

def test_no_gist_means_zero_network(menv):
    def boom(*a, **k):
        raise AssertionError("不得呼叫網路")
    menv.setattr(metrics, "_gist_api", boom)
    metrics.record_mode("grid")
    metrics.snapshot()
    assert metrics.restore_from_gist() is False
    assert metrics.push_now() is False
    assert metrics.persistence_mode() == "local"


def test_only_one_of_two_env_vars_is_off(menv):
    menv.setenv("STROKE_ORDER_METRICS_GIST_ID", "gid")
    assert metrics.persistence_mode() == "local"


# ---------------------------------------------------------------------------
# 2. 讀回＝合併；重啟累計不重複
# ---------------------------------------------------------------------------

def test_restore_merges_not_overwrites(gist_on):
    fake = _install(gist_on, FakeGist({
        "since": "2026-10-01T00:00:00+00:00", "mode": {"grid": 5, "handfont": 1},
        "missing_char": {"𪚥": 2}, "missing_char_overflow": 0}))
    metrics.PUSH_INTERVAL  # noqa: B018
    gist_on.setattr(metrics, "PUSH_INTERVAL", 1e9)
    metrics.record_mode("grid")          # 讀回前進來的請求
    assert metrics.persistence_mode() == "gist-pending"
    assert metrics.restore_from_gist() is True
    s = metrics.snapshot()
    assert s["mode"] == {"grid": 6, "handfont": 1}
    assert s["missing_char"] == {"𪚥": 2}
    assert s["since"] == "2026-10-01T00:00:00+00:00", "since 取較早者"
    assert metrics.persistence_mode() == "gist"
    assert metrics.restore_from_gist() is True    # 冪等
    assert metrics.snapshot()["mode"]["grid"] == 6, "重複讀回不得重複加"
    assert fake.calls.count("GET") == 1


def test_restart_accumulates_without_double_count(gist_on):
    """模擬休眠→醒來：本機檔還在（本機開發情境）也不得與 Gist 重複算。"""
    fake = _install(gist_on, FakeGist(None))      # Gist 尚無檔案
    gist_on.setattr(metrics, "PUSH_INTERVAL", 1e9)
    for _ in range(3):
        metrics.record_mode("handfont")
    assert metrics.push_now() is True
    assert fake.content["mode"] == {"handfont": 3}

    metrics.reset_for_tests()                     # 重啟（本機檔仍在 tmp）
    metrics.record_mode("handfont")
    assert metrics.restore_from_gist() is True
    assert metrics.snapshot()["mode"] == {"handfont": 4}
    assert metrics.push_now() is True
    assert fake.content["mode"] == {"handfont": 4}


# ---------------------------------------------------------------------------
# 3. 未讀回不推送
# ---------------------------------------------------------------------------

def test_no_push_when_restore_fails(gist_on):
    fake = _install(gist_on, FakeGist({"since": "2026-10-01T00:00:00+00:00",
                                       "mode": {"grid": 99}, "missing_char": {}},
                                      fail_get=True))
    gist_on.setattr(metrics, "PUSH_INTERVAL", 1e9)
    metrics.record_mode("grid")
    assert metrics.push_now() is False
    assert "PATCH" not in fake.calls, "讀回失敗時不得覆蓋遠端"
    assert fake.content["mode"] == {"grid": 99}
    assert metrics.persistence_mode() == "gist-pending"
    # 網路恢復後：推送前自動重試讀回，遠端歷史保住
    fake.fail_get = False
    assert metrics.push_now() is True
    assert fake.content["mode"] == {"grid": 100}


def test_background_push_is_throttled_and_off_request_path(gist_on):
    fake = _install(gist_on, FakeGist(None))
    metrics.record_mode("grid")          # 第一次 flush → 背景推送
    t = metrics._push_thread
    assert t is not None
    t.join(timeout=5)
    assert fake.calls.count("PATCH") == 1
    for _ in range(5):                   # 節流期內不再推
        metrics.record_mode("grid")
    metrics.snapshot()
    if metrics._push_thread is not None:
        metrics._push_thread.join(timeout=5)
    assert fake.calls.count("PATCH") == 1


def test_push_failure_is_not_fatal(gist_on):
    def flaky(method, *a, **k):
        if method == "GET":
            return {"files": {}}
        raise ConnectionError("down")
    gist_on.setattr(metrics, "_gist_api", flaky)
    gist_on.setattr(metrics, "PUSH_INTERVAL", 1e9)
    metrics.record_mode("grid")
    assert metrics.push_now() is False
    assert metrics.snapshot()["mode"]["grid"] == 1


# ---------------------------------------------------------------------------
# 4. 合併守缺字上限
# ---------------------------------------------------------------------------

def test_merge_respects_missing_char_cap(gist_on):
    remote_mc = {chr(0x4E00 + i): 1 for i in range(metrics.MISSING_CHAR_CAP)}
    _install(gist_on, FakeGist({"since": "2026-10-01T00:00:00+00:00",
                                "mode": {}, "missing_char": remote_mc,
                                "missing_char_overflow": 3}))
    gist_on.setattr(metrics, "PUSH_INTERVAL", 1e9)
    metrics.record_missing_char("龘")             # 本機先有一個新 key
    assert metrics.restore_from_gist() is True
    s = metrics.snapshot()
    assert len(s["missing_char"]) == metrics.MISSING_CHAR_CAP
    assert s["missing_char"]["龘"] == 1
    # 1 個遠端 key 擠不進來 → 計入溢位；遠端原有溢位 3 也加上
    assert s["missing_char_overflow"] == 3 + 1


def test_malformed_remote_content_is_harmless(gist_on):
    def bad(method, *a, **k):
        return {"files": {metrics.GIST_FILENAME: {"content": "not json"}}}
    gist_on.setattr(metrics, "_gist_api", bad)
    gist_on.setattr(metrics, "PUSH_INTERVAL", 1e9)
    assert metrics.restore_from_gist() is False
    metrics.record_mode("grid")
    assert metrics.snapshot()["mode"]["grid"] == 1


# ---------------------------------------------------------------------------
# 5. 誠實標示
# ---------------------------------------------------------------------------

def test_metrics_endpoint_reports_persistence(menv):
    c = TestClient(create_app())
    assert c.get("/api/metrics").json()["persistence"] == "local"
    menv.setenv("STROKE_ORDER_EPHEMERAL_STORAGE", "true")
    assert c.get("/api/metrics").json()["persistence"] == "ephemeral"


def test_gallery_banner_only_when_ephemeral(menv):
    c = TestClient(create_app())
    r = c.get("/gallery")
    assert r.status_code == 200
    assert "gl-ephemeral-notice" not in r.text
    menv.setenv("STROKE_ORDER_EPHEMERAL_STORAGE", "true")
    r2 = c.get("/gallery")
    assert r2.status_code == 200
    assert 'id="gl-ephemeral-notice"' in r2.text
    assert "可能消失" in r2.text
    assert "<!--EPHEMERAL_NOTICE-->" not in r2.text
    assert r2.headers["ETag"] != r.headers["ETag"]


def test_banner_css_uses_existing_warn_tokens():
    css = (_ROOT / "src/stroke_order/web/static/gallery/gallery.css").read_text("utf-8")
    i = css.index(".gl-banner-warn")
    block = css[i:css.index("}", i)]
    assert "var(--gl-warn-bg)" in block and "var(--gl-warn-fg)" in block


def test_render_yaml_declares_storage_env():
    import yaml
    d = yaml.safe_load((_ROOT / "render.yaml").read_text("utf-8"))
    env = {e["key"]: e for e in d["services"][0]["envVars"]}
    assert env["STROKE_ORDER_EPHEMERAL_STORAGE"]["value"] == "true"
    for k in ("STROKE_ORDER_METRICS_GIST_ID", "STROKE_ORDER_METRICS_GIST_TOKEN"):
        assert env[k].get("sync") is False, f"{k} 是秘密，不得寫死在 repo"
