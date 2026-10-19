"""
v0.14.297 P0——公開站關閉共用字庫（user_dict）寫入。

user_dict 是伺服器上「單一」資料夾、位於 AutoSource 第一順位：本機單人
使用時是特性，公開網站上則是「任何訪客寫一個字、所有人的字帖都換成那份
筆跡」。STROKE_ORDER_USER_DICT_WRITABLE=false 時三個寫入端點回 403＋說明；
沒設＝行為零變（既有 user_dict 測試即回歸鎖）。
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from stroke_order.web.routes import user_dict as ud_routes
from stroke_order.web.server import create_app

_ROOT = Path(__file__).resolve().parent.parent
_STATIC = _ROOT / "src" / "stroke_order" / "web" / "static"

_STROKES = [{"track": [[200, 1000], [1800, 1000]]}]


@pytest.fixture
def dict_dir(tmp_path, monkeypatch):
    d = tmp_path / "ud"
    monkeypatch.setenv("STROKE_ORDER_USER_DICT_DIR", str(d))
    monkeypatch.delenv("STROKE_ORDER_USER_DICT_WRITABLE", raising=False)
    from stroke_order.sources import reset_source_cache
    reset_source_cache()
    yield d
    reset_source_cache()


@pytest.fixture
def client(dict_dir):
    return TestClient(create_app())


def _zip_one() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("6c38.json", '{"char": "永", "strokes": [{"track": [[0,0],[100,100]]}]}')
    return buf.getvalue()


def test_default_is_writable(client, dict_dir):
    assert ud_routes.user_dict_writable() is True
    r = client.post("/api/user-dict", json={"char": "永", "strokes": _STROKES})
    assert r.status_code == 200
    assert client.get("/api/user-dict").json()["writable"] is True


@pytest.mark.parametrize("val", ["false", "0", "no", "OFF", " False "])
def test_false_values_close_writes(val, client, dict_dir, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_USER_DICT_WRITABLE", val)
    assert ud_routes.user_dict_writable() is False


def test_readonly_blocks_all_three_writes(client, dict_dir, monkeypatch):
    # 先在可寫狀態放一個字，驗 DELETE 也被擋
    assert client.post("/api/user-dict",
                       json={"char": "永", "strokes": _STROKES}).status_code == 200
    monkeypatch.setenv("STROKE_ORDER_USER_DICT_WRITABLE", "false")

    r1 = client.post("/api/user-dict", json={"char": "日", "strokes": _STROKES})
    r2 = client.post("/api/user-dict/import",
                     files={"file": ("d.zip", _zip_one(), "application/zip")},
                     data={"policy": "replace"})
    r3 = client.delete("/api/user-dict/永")
    for r in (r1, r2, r3):
        assert r.status_code == 403
        assert r.json()["detail"] == ud_routes.USER_DICT_READONLY_DETAIL
    # 狀態完全沒變：日 沒寫入、永 沒被刪
    chars = {c["char"] for c in client.get("/api/user-dict").json()["chars"]}
    assert chars == {"永"}


def test_readonly_reads_still_work(client, dict_dir, monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_USER_DICT_WRITABLE", "false")
    d = client.get("/api/user-dict").json()
    assert d["writable"] is False and d["count"] == 0
    assert client.get("/api/user-dict/export").status_code == 200
    # 字庫空 → 各模式自然落到內建字源（不因唯讀而壞）
    assert client.get("/api/user-dict/永").status_code == 404


def test_detail_is_honest_and_specific():
    msg = ud_routes.USER_DICT_READONLY_DETAIL
    assert "所有訪客共用" in msg and "瀏覽器" in msg


def test_render_yaml_closes_writes_on_public_site():
    d = yaml.safe_load((_ROOT / "render.yaml").read_text("utf-8"))
    env = {e["key"]: e for e in d["services"][0]["envVars"]}
    assert env["STROKE_ORDER_USER_DICT_WRITABLE"]["value"] == "false"


def test_frontends_surface_readonly():
    hw = (_STATIC / "handwriting.html").read_text("utf-8")
    assert "d.writable === false" in hw and "cb.disabled = true" in hw
    ud = (_STATIC / "modes" / "userdict.js").read_text("utf-8")
    assert "d.writable === false" in ud
    # 刪除不再默默吞錯
    i = ud.index("async function udDelete")
    assert "if (!r.ok)" in ud[i:i + 600]
    sw = (_STATIC / "modes" / "handwrite.js").read_text("utf-8")
    i = sw.index("async function swImport")
    assert "e.detail" in sw[i:i + 800]
