"""Phase 5b r29j: avatar upload / serve / clear API tests."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def env(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("STROKE_ORDER_GALLERY_DIR", td)
        monkeypatch.setenv(
            "STROKE_ORDER_AUTH_SECRET",
            "test-secret-32-bytes-aaaaaaaaaaaaaaaaa",
        )
        monkeypatch.setenv("STROKE_ORDER_BASE_URL", "http://test.local")
        monkeypatch.setenv("STROKE_ORDER_AUTH_DEV_MODE", "true")
        from stroke_order.gallery.db import reset_schema_cache
        reset_schema_cache()
        yield Path(td)


@pytest.fixture
def app(env):
    from stroke_order.web.server import create_app
    return create_app()


def _login_client(app, email: str) -> TestClient:
    c = TestClient(app)
    r = c.post(
        "/api/gallery/auth/request-login",
        json={"email": email},
    )
    assert r.status_code == 200
    from stroke_order.gallery.auth import make_login_token
    token = make_login_token(email)
    r2 = c.get(
        f"/api/gallery/auth/consume?token={token}",
        follow_redirects=False,
    )
    assert r2.status_code == 303
    return c


def _make_png(size=(100, 100), color=(255, 0, 0)) -> bytes:
    """Build a tiny valid PNG bytes string for tests."""
    from PIL import Image
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg(size=(100, 100), color=(0, 255, 0)) -> bytes:
    from PIL import Image
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


# ============================================================ POST /me/avatar

def test_avatar_upload_requires_login(app):
    """匿名 POST → 401。"""
    c = TestClient(app)
    r = c.post(
        "/api/gallery/me/avatar",
        files={"file": ("a.png", _make_png(), "image/png")},
    )
    assert r.status_code == 401


def test_avatar_upload_png_succeeds_and_returns_avatar_url(app):
    cli = _login_client(app, "alice@example.com")
    r = cli.post(
        "/api/gallery/me/avatar",
        files={"file": ("avatar.png", _make_png(), "image/png")},
    )
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    assert user["avatar_url"] is not None
    assert user["avatar_url"].startswith(
        f"/api/gallery/users/{user['id']}/avatar?v=")
    # avatar_path 不該外洩到 API response
    assert "avatar_path" not in user


def test_avatar_upload_jpeg_also_works(app):
    cli = _login_client(app, "bob@example.com")
    r = cli.post(
        "/api/gallery/me/avatar",
        files={"file": ("a.jpg", _make_jpeg(), "image/jpeg")},
    )
    assert r.status_code == 200, r.text


def test_avatar_upload_wrong_format_rejected(app):
    cli = _login_client(app, "alice@example.com")
    # Plain text 偽裝 image
    r = cli.post(
        "/api/gallery/me/avatar",
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 422
    assert "PNG" in r.json()["detail"] or "JPEG" in r.json()["detail"]


def test_avatar_upload_too_large_rejected(app):
    cli = _login_client(app, "alice@example.com")
    # 製造 > 2MB 的 PNG（big resolution）— 256×256 dummy image 太小，
    # 用 raw 3MB bytes 假裝（content_type 對但 size 爆）
    big = b"x" * (3 * 1024 * 1024)
    r = cli.post(
        "/api/gallery/me/avatar",
        files={"file": ("big.png", big, "image/png")},
    )
    assert r.status_code == 422
    assert "MB" in r.json()["detail"] or "大小" in r.json()["detail"]


def test_avatar_upload_invalid_image_rejected(app):
    """Content-type 對但 file 不是合法 image。"""
    cli = _login_client(app, "alice@example.com")
    r = cli.post(
        "/api/gallery/me/avatar",
        files={"file": ("fake.png", b"NOT_AN_IMAGE", "image/png")},
    )
    assert r.status_code == 422


# ============================================================ GET /users/{id}/avatar

def test_avatar_get_returns_png_after_upload(app):
    cli = _login_client(app, "alice@example.com")
    r = cli.post(
        "/api/gallery/me/avatar",
        files={"file": ("a.png", _make_png(), "image/png")},
    )
    assert r.status_code == 200
    user_id = r.json()["user"]["id"]
    # Public GET (no auth required)
    pub = TestClient(app)
    r2 = pub.get(f"/api/gallery/users/{user_id}/avatar")
    assert r2.status_code == 200
    assert r2.headers["content-type"] == "image/png"
    # Body should be a PNG (magic bytes \x89PNG)
    assert r2.content[:4] == b"\x89PNG"


def test_avatar_get_404_when_no_upload(app):
    """無 avatar 的 user → GET 回 404。"""
    # 建一個 user 但不上傳 avatar
    cli = _login_client(app, "noavatar@example.com")
    me = cli.get("/api/gallery/me").json()
    user_id = me["user"]["id"]
    pub = TestClient(app)
    r = pub.get(f"/api/gallery/users/{user_id}/avatar")
    assert r.status_code == 404


# ============================================================ DELETE /me/avatar

def test_avatar_delete_clears_url(app):
    cli = _login_client(app, "alice@example.com")
    cli.post(
        "/api/gallery/me/avatar",
        files={"file": ("a.png", _make_png(), "image/png")},
    )
    # Now delete
    r = cli.delete("/api/gallery/me/avatar")
    assert r.status_code == 200
    assert r.json()["user"]["avatar_url"] is None


def test_avatar_delete_idempotent(app):
    """已無 avatar 的 user 再 delete → 不爆，回 user dict。"""
    cli = _login_client(app, "alice@example.com")
    r = cli.delete("/api/gallery/me/avatar")
    assert r.status_code == 200
    assert r.json()["user"]["avatar_url"] is None


# ============================================================ /me + /users/{id} 帶 avatar_url

def test_me_response_includes_avatar_url(app):
    cli = _login_client(app, "alice@example.com")
    r = cli.get("/api/gallery/me")
    assert r.status_code == 200
    user = r.json()["user"]
    assert "avatar_url" in user
    assert user["avatar_url"] is None  # 還沒上傳


def test_user_profile_endpoint_includes_avatar_url(app):
    cli = _login_client(app, "alice@example.com")
    r = cli.post(
        "/api/gallery/me/avatar",
        files={"file": ("a.png", _make_png(), "image/png")},
    )
    user_id = r.json()["user"]["id"]
    pub = TestClient(app)
    r2 = pub.get(f"/api/gallery/users/{user_id}")
    assert r2.status_code == 200
    profile = r2.json()
    assert profile["user"]["avatar_url"] is not None


# ============================================================ cache-bust nonce

def test_avatar_url_nonce_changes_on_replace(app):
    """重新上傳 avatar → URL 的 ?v=<nonce> 變動（cache-bust）。"""
    cli = _login_client(app, "alice@example.com")
    r1 = cli.post(
        "/api/gallery/me/avatar",
        files={"file": ("a.png", _make_png(), "image/png")},
    )
    url1 = r1.json()["user"]["avatar_url"]
    r2 = cli.post(
        "/api/gallery/me/avatar",
        files={"file": ("b.png", _make_png(color=(0, 0, 255)), "image/png")},
    )
    url2 = r2.json()["user"]["avatar_url"]
    assert url1 != url2  # nonce 應改變
