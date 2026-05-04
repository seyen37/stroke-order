"""Phase 5b r29: gallery upload like 機制 tests。"""

from __future__ import annotations

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
    """Helper: 建一個測試 user。"""
    def _make(email: str = "tester@example.com") -> int:
        from stroke_order.gallery.db import db_connection
        with db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, display_name, created_at) "
                "VALUES (?, ?, ?)",
                (email, "Tester", "2026-05-04T00:00:00+00:00"),
            )
            return int(cur.lastrowid)
    return _make


@pytest.fixture
def make_upload(gallery_env, make_user):
    """Helper: 建一個假的 PSD upload row（直接 INSERT，bypass validator）。"""
    def _make(user_id: int = None, title: str = "test") -> int:
        if user_id is None:
            user_id = make_user("u@t")
        from stroke_order.gallery.db import db_connection
        import secrets
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


# ============================================================ DB schema

def test_likes_table_exists(gallery_env):
    from stroke_order.gallery.db import db_connection
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "ORDER BY name",
        ).fetchall()
    names = {r["name"] for r in rows}
    assert "likes" in names


def test_likes_table_unique_user_upload(gallery_env, make_user, make_upload):
    """同 user × upload 重複 INSERT 應撞 UNIQUE constraint。"""
    import sqlite3
    from stroke_order.gallery.db import db_connection
    user_id = make_user()
    upload_id = make_upload(user_id=user_id)
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO likes (user_id, upload_id, created_at) "
            "VALUES (?, ?, ?)",
            (user_id, upload_id, "2026-05-04T00:00:00Z"),
        )
    with pytest.raises(sqlite3.IntegrityError):
        with db_connection() as conn:
            conn.execute(
                "INSERT INTO likes (user_id, upload_id, created_at) "
                "VALUES (?, ?, ?)",
                (user_id, upload_id, "2026-05-04T00:00:01Z"),
            )


# ============================================================ toggle_like

def test_toggle_like_creates_row(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    user_id = make_user()
    upload_id = make_upload(user_id=user_id)
    r = service.toggle_like(user_id=user_id, upload_id=upload_id)
    assert r["liked"] is True
    assert r["like_count"] == 1


def test_toggle_like_second_time_unlikes(gallery_env, make_user, make_upload):
    """同 user 第二次 toggle 應該 unlike + count 遞減。"""
    from stroke_order.gallery import service
    user_id = make_user()
    upload_id = make_upload(user_id=user_id)
    service.toggle_like(user_id=user_id, upload_id=upload_id)
    r = service.toggle_like(user_id=user_id, upload_id=upload_id)
    assert r["liked"] is False
    assert r["like_count"] == 0


def test_toggle_like_aggregate_count(gallery_env, make_user, make_upload):
    """多個 user like 同一 upload，count 應 aggregate 正確。"""
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    u2 = make_user("u2@t")
    u3 = make_user("u3@t")
    upload_id = make_upload(user_id=u1)
    service.toggle_like(user_id=u1, upload_id=upload_id)
    service.toggle_like(user_id=u2, upload_id=upload_id)
    r = service.toggle_like(user_id=u3, upload_id=upload_id)
    assert r["liked"] is True
    assert r["like_count"] == 3


def test_toggle_like_self_allowed(gallery_env, make_user, make_upload):
    """User 可以 like 自己的 upload（r29 Q4 ★ B）。"""
    from stroke_order.gallery import service
    user_id = make_user()
    upload_id = make_upload(user_id=user_id)
    r = service.toggle_like(user_id=user_id, upload_id=upload_id)
    assert r["liked"] is True


def test_toggle_like_nonexistent_upload(gallery_env, make_user):
    """Like 不存在的 upload → NotFound。"""
    from stroke_order.gallery import service
    user_id = make_user()
    with pytest.raises(service.NotFound):
        service.toggle_like(user_id=user_id, upload_id=99999)


# ============================================================ get_like_info

def test_get_like_info_anon(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    upload_id = make_upload(user_id=u1)
    service.toggle_like(user_id=u1, upload_id=upload_id)

    info = service.get_like_info(upload_id=upload_id)  # anon
    assert info["like_count"] == 1
    assert info["liked_by_me"] is False


def test_get_like_info_logged_in(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    u2 = make_user("u2@t")
    upload_id = make_upload(user_id=u1)
    service.toggle_like(user_id=u1, upload_id=upload_id)
    info_u1 = service.get_like_info(upload_id=upload_id, user_id=u1)
    info_u2 = service.get_like_info(upload_id=upload_id, user_id=u2)
    assert info_u1["liked_by_me"] is True
    assert info_u2["liked_by_me"] is False
    assert info_u1["like_count"] == info_u2["like_count"] == 1


# ============================================================ list/get include like_count

def test_get_upload_includes_like_count(
    gallery_env, make_user, make_upload,
):
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    u2 = make_user("u2@t")
    upload_id = make_upload(user_id=u1)
    service.toggle_like(user_id=u1, upload_id=upload_id)
    service.toggle_like(user_id=u2, upload_id=upload_id)
    rec = service.get_upload(upload_id)
    assert rec["like_count"] == 2


def test_list_uploads_includes_like_count_and_liked_by_me(
    gallery_env, make_user, make_upload,
):
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    u2 = make_user("u2@t")
    upload_id = make_upload(user_id=u1)
    service.toggle_like(user_id=u1, upload_id=upload_id)

    # u1 viewer → liked_by_me True
    res = service.list_uploads(viewer_user_id=u1)
    assert res["items"][0]["like_count"] == 1
    assert res["items"][0]["liked_by_me"] is True

    # u2 viewer → liked_by_me False
    res = service.list_uploads(viewer_user_id=u2)
    assert res["items"][0]["liked_by_me"] is False

    # anon viewer → liked_by_me False
    res = service.list_uploads()
    assert res["items"][0]["liked_by_me"] is False
    assert res["items"][0]["like_count"] == 1


# ============================================================ FK cascade

def test_delete_upload_cascades_likes(gallery_env, make_user, make_upload):
    """Upload 刪除時，likes 自動 cascade delete。"""
    from stroke_order.gallery.db import db_connection
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    u2 = make_user("u2@t")
    upload_id = make_upload(user_id=u1)
    service.toggle_like(user_id=u1, upload_id=upload_id)
    service.toggle_like(user_id=u2, upload_id=upload_id)
    with db_connection() as conn:
        n = conn.execute(
            "SELECT count(*) AS n FROM likes WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()["n"]
        assert n == 2

    # Delete upload via service
    service.delete_upload(upload_id=upload_id, user_id=u1)
    with db_connection() as conn:
        n = conn.execute(
            "SELECT count(*) AS n FROM likes WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()["n"]
    assert n == 0, "likes should cascade delete with upload"


def test_delete_user_cascades_likes(gallery_env, make_user, make_upload):
    """User 刪除時，該 user 的 likes 自動 cascade delete（DB 直接測）。"""
    from stroke_order.gallery.db import db_connection
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    upload_id = make_upload(user_id=u1)
    service.toggle_like(user_id=u1, upload_id=upload_id)
    with db_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (u1,))
    with db_connection() as conn:
        n = conn.execute(
            "SELECT count(*) AS n FROM likes WHERE user_id = ?",
            (u1,),
        ).fetchone()["n"]
    assert n == 0


# ============================================================ API integration

def test_api_like_endpoint_requires_login(gallery_env, make_upload):
    """POST /api/gallery/uploads/{id}/like 未登入回 401。"""
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    upload_id = make_upload()
    client = TestClient(create_app())
    r = client.post(f"/api/gallery/uploads/{upload_id}/like")
    assert r.status_code == 401


def test_api_like_endpoint_logged_in(gallery_env, make_user, make_upload):
    """POST /api/gallery/uploads/{id}/like 登入後可 toggle。"""
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    from stroke_order.gallery import auth as auth_mod
    user_id = make_user()
    upload_id = make_upload(user_id=user_id)
    session = auth_mod.create_session(user_id=user_id)
    client = TestClient(create_app())
    client.cookies.set("psd_session", session)
    r = client.post(f"/api/gallery/uploads/{upload_id}/like")
    assert r.status_code == 200
    data = r.json()
    assert data["liked"] is True
    assert data["like_count"] == 1
    # 第二次 → unlike
    r = client.post(f"/api/gallery/uploads/{upload_id}/like")
    assert r.status_code == 200
    assert r.json()["liked"] is False


def test_api_get_upload_includes_liked_by_me(
    gallery_env, make_user, make_upload,
):
    """GET /api/gallery/uploads/{id} 登入後 record 含 liked_by_me。"""
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    from stroke_order.gallery import auth as auth_mod, service
    user_id = make_user()
    upload_id = make_upload(user_id=user_id)
    service.toggle_like(user_id=user_id, upload_id=upload_id)

    session = auth_mod.create_session(user_id=user_id)
    client = TestClient(create_app())
    client.cookies.set("psd_session", session)
    r = client.get(f"/api/gallery/uploads/{upload_id}")
    assert r.status_code == 200
    upload = r.json()["upload"]
    assert upload["liked_by_me"] is True
    assert upload["like_count"] == 1

    # Anon viewer
    client2 = TestClient(create_app())
    r = client2.get(f"/api/gallery/uploads/{upload_id}")
    assert r.json()["upload"]["liked_by_me"] is False
