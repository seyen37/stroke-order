"""5fz: 郵件通道三模式（dev mode／Brevo HTTP API／SMTP fallback）。

背景：Render 免費層封鎖所有對外 SMTP 埠（25/465/587）——傳統 SMTP 在
production 連不出去（Errno 101）。Brevo 走 HTTPS 443，是免費層唯一
可行通道。測試全程 monkeypatch、不打網路。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from stroke_order.gallery import smtp as mail


def _run(coro):
    # asyncio.run：每次全新 event loop——避免與其他 async 測試共用
    # loop 造成整批跑時 loop closed / no current loop。
    return asyncio.run(coro)


# ------------------------------------------------- from 解析

@pytest.mark.parametrize("raw,expect", [
    ("stroke-order <a@b.c>", ("stroke-order", "a@b.c")),
    ("a@b.c", ("a@b.c", "a@b.c")),
    ("  Name Here <x@y.z>  ", ("Name Here", "x@y.z")),
])
def test_parse_from_addr(raw, expect):
    assert mail._parse_from_addr(raw) == expect


# ------------------------------------------------- 模式優先序

def test_dev_mode_short_circuits(monkeypatch, capsys):
    monkeypatch.setenv("STROKE_ORDER_AUTH_DEV_MODE", "true")
    monkeypatch.setenv("STROKE_ORDER_BREVO_API_KEY", "should-not-be-used")
    called = []
    monkeypatch.setattr(mail, "_sync_send_brevo",
                        lambda *a, **k: called.append("brevo"))
    _run(mail.send_magic_link_email("u@example.com", "http://x/y"))
    assert not called                       # dev mode 優先、不打 API
    out = capsys.readouterr().out
    assert "http://x/y" in out and "u@example.com" in out


def test_brevo_priority_over_smtp(monkeypatch):
    monkeypatch.delenv("STROKE_ORDER_AUTH_DEV_MODE", raising=False)
    monkeypatch.setenv("STROKE_ORDER_BREVO_API_KEY", "key-123")
    monkeypatch.setenv("STROKE_ORDER_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("STROKE_ORDER_SMTP_USER", "u")
    calls = []
    monkeypatch.setattr(
        mail, "_sync_send_brevo",
        lambda to, subject, body, settings: calls.append(
            (to, subject, body)))
    monkeypatch.setattr(
        mail, "_sync_send",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("SMTP 不該被呼叫")))
    _run(mail.send_magic_link_email("u@example.com", "http://x/magic"))
    assert len(calls) == 1
    to, subject, body = calls[0]
    assert to == "u@example.com"
    assert "登入連結" in subject
    assert "http://x/magic" in body


def test_no_channel_raises_helpful_error(monkeypatch):
    monkeypatch.delenv("STROKE_ORDER_AUTH_DEV_MODE", raising=False)
    monkeypatch.delenv("STROKE_ORDER_BREVO_API_KEY", raising=False)
    monkeypatch.delenv("STROKE_ORDER_SMTP_HOST", raising=False)
    monkeypatch.delenv("STROKE_ORDER_SMTP_USER", raising=False)
    with pytest.raises(RuntimeError, match="BREVO"):
        _run(mail.send_magic_link_email("u@example.com", "http://x"))


# ------------------------------------------------- Brevo payload／錯誤

class _FakeResp:
    status = 201
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_brevo_payload_shape(monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_BREVO_API_KEY", "key-abc")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v
                               for k, v in req.header_items()}
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    mail._sync_send_brevo(
        "student@school.tw", "[stroke-order] 公眾分享庫登入連結",
        "請點以下連結：\nhttp://x/magic\n",
        {"from_addr": "stroke-order <seyen37@gmail.com>"})
    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"
    assert captured["headers"]["api-key"] == "key-abc"
    body = captured["body"]
    assert body["sender"] == {"name": "stroke-order",
                              "email": "seyen37@gmail.com"}
    assert body["to"] == [{"email": "student@school.tw"}]
    assert "http://x/magic" in body["textContent"]


def test_brevo_http_error_becomes_runtime_error(monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_BREVO_API_KEY", "bad-key")
    import io
    import urllib.error
    import urllib.request

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {},
            io.BytesIO(b'{"message":"Key not found"}'))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="401"):
        mail._sync_send_brevo("u@example.com", "s", "b",
                              {"from_addr": "a@b.c"})


def test_brevo_network_error_becomes_runtime_error(monkeypatch):
    monkeypatch.setenv("STROKE_ORDER_BREVO_API_KEY", "key")
    import urllib.request

    def fake_urlopen(req, timeout=None):
        raise OSError(101, "Network is unreachable")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="連線失敗"):
        mail._sync_send_brevo("u@example.com", "s", "b",
                              {"from_addr": "a@b.c"})
