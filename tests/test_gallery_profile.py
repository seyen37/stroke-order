"""Phase 5b r29d: gallery user profile + user_id filter tests。"""

from __future__ import annotations

import secrets
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def gallery_env(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("STROKE_ORDER_GALLERY_DIR", td)
        monkeypatch.setenv("STROKE_ORDER_AUTH_SECRET",
                           "test-secret-32-bytes-aaaaaaaaaaaaa")
        monkeypatch.setenv("STROKE_ORDER_BASE_URL", "http://test.local")
        from stroke_order.gallery.db import reset_schema_cache
        reset_schema_cache()
        yield Path(td)


@pytest.fixture
def make_user(gallery_env):
    def _make(email: str = None, display_name: str = "Tester",
              bio: str = None,
              created_at: str = "2026-04-01T00:00:00+00:00") -> int:
        from stroke_order.gallery.db import db_connection
        if email is None:
            email = f"u{secrets.token_hex(4)}@t"
        with db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, display_name, bio, created_at) "
                "VALUES (?, ?, ?, ?)",
                (email, display_name, bio, created_at),
            )
            return int(cur.lastrowid)
    return _make


@pytest.fixture
def make_upload(gallery_env, make_user):
    def _make(user_id: int = None, title: str = "test") -> int:
        if user_id is None:
            user_id = make_user()
        from stroke_order.gallery.db import db_connection
        nonce = secrets.token_hex(8)
        with db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO uploads "
                "(user_id, title, file_path, file_size, file_hash, kind, "
                " created_at) "
                "VALUES (?, ?, ?, ?, ?, 'psd', ?)",
                (user_id, title, f"{user_id}/{nonce}.json",
                 100, nonce, "2026-05-04T00:00:00+00:00"),
            )
            return int(cur.lastrowid)
    return _make


# ============================================================ get_user_profile

def test_profile_returns_user_and_stats(
    gallery_env, make_user, make_upload,
):
    from stroke_order.gallery import service
    u = make_user(
        email="alice@t", display_name="Alice",
        bio="曼陀羅愛好者", created_at="2026-04-01T00:00:00+00:00",
    )
    a1 = make_upload(user_id=u, title="A1")
    a2 = make_upload(user_id=u, title="A2")
    # 5 likes on a1, 2 on a2
    for i in range(5):
        liker = make_user()
        service.toggle_like(user_id=liker, upload_id=a1)
    for i in range(2):
        liker = make_user()
        service.toggle_like(user_id=liker, upload_id=a2)

    p = service.get_user_profile(u)
    assert p["user"]["id"] == u
    assert p["user"]["display_name"] == "Alice"
    assert p["user"]["bio"] == "曼陀羅愛好者"
    assert p["stats"]["total_uploads"] == 2
    assert p["stats"]["total_likes_received"] == 7
    assert p["stats"]["member_since"] == "2026-04-01T00:00:00+00:00"


def test_profile_zero_uploads_zero_likes(gallery_env, make_user):
    """新註冊 user 沒任何 upload → stats 全 0。"""
    from stroke_order.gallery import service
    u = make_user()
    p = service.get_user_profile(u)
    assert p["stats"]["total_uploads"] == 0
    assert p["stats"]["total_likes_received"] == 0


def test_profile_unknown_user_raises_not_found(gallery_env):
    from stroke_order.gallery import service
    with pytest.raises(service.NotFound):
        service.get_user_profile(99999)


# ============================================================ list_uploads user_id filter

def test_list_user_id_filter(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    u_alice = make_user(email="alice@t", display_name="Alice")
    u_bob = make_user(email="bob@t", display_name="Bob")
    make_upload(user_id=u_alice, title="A1")
    make_upload(user_id=u_alice, title="A2")
    make_upload(user_id=u_bob, title="B1")

    listed = service.list_uploads(user_id=u_alice)
    titles = sorted(it["title"] for it in listed["items"])
    assert titles == ["A1", "A2"]
    assert listed["total"] == 2

    listed_bob = service.list_uploads(user_id=u_bob)
    titles_bob = [it["title"] for it in listed_bob["items"]]
    assert titles_bob == ["B1"]


def test_list_user_id_filter_combos_with_others(
    gallery_env, make_user, make_upload,
):
    """user_id filter 跟 sort / search / bookmarked 可組合。"""
    from stroke_order.gallery import service
    u = make_user()
    a = make_upload(user_id=u, title="曼陀羅 A")
    b = make_upload(user_id=u, title="抄經 B")
    c = make_upload(user_id=u, title="曼陀羅 C")
    # likes: A=5, C=10
    for i in range(5):
        service.toggle_like(user_id=make_user(), upload_id=a)
    for i in range(10):
        service.toggle_like(user_id=make_user(), upload_id=c)

    # user_id + q="曼陀羅" + sort=likes
    listed = service.list_uploads(
        user_id=u, q="曼陀羅", sort="likes",
    )
    titles = [it["title"] for it in listed["items"]]
    # 只 A, C（B 不含曼陀羅）；C (10 likes) > A (5 likes)
    assert titles == ["曼陀羅 C", "曼陀羅 A"]


# ============================================================ API integration

def test_api_get_user_profile(gallery_env, make_user, make_upload):
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    from stroke_order.gallery import service
    u = make_user(display_name="Alice", bio="Bio test")
    upload_id = make_upload(user_id=u, title="X")
    liker = make_user()
    service.toggle_like(user_id=liker, upload_id=upload_id)

    client = TestClient(create_app())
    r = client.get(f"/api/gallery/users/{u}")
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["display_name"] == "Alice"
    assert data["user"]["bio"] == "Bio test"
    assert data["stats"]["total_uploads"] == 1
    assert data["stats"]["total_likes_received"] == 1


def test_api_get_user_profile_404(gallery_env):
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    client = TestClient(create_app())
    r = client.get("/api/gallery/users/99999")
    assert r.status_code == 404
