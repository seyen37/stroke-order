"""Phase 5b r29b: gallery bookmark + sort by likes tests。"""

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
    def _make(user_id: int = None, title: str = "test",
              created_at: str = "2026-05-04T00:00:00+00:00") -> int:
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
                 100, nonce, created_at),
            )
            return int(cur.lastrowid)
    return _make


# ============================================================ DB schema

def test_bookmarks_table_exists(gallery_env):
    from stroke_order.gallery.db import db_connection
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "ORDER BY name",
        ).fetchall()
    names = {r["name"] for r in rows}
    assert "bookmarks" in names


def test_bookmarks_unique_user_upload(gallery_env, make_user, make_upload):
    """同 user × upload 重複 INSERT 應撞 UNIQUE constraint。"""
    import sqlite3
    from stroke_order.gallery.db import db_connection
    user_id = make_user()
    upload_id = make_upload(user_id=user_id)
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO bookmarks (user_id, upload_id, created_at) "
            "VALUES (?, ?, ?)",
            (user_id, upload_id, "2026-05-04T00:00:00Z"),
        )
    with pytest.raises(sqlite3.IntegrityError):
        with db_connection() as conn:
            conn.execute(
                "INSERT INTO bookmarks (user_id, upload_id, created_at) "
                "VALUES (?, ?, ?)",
                (user_id, upload_id, "2026-05-04T00:00:01Z"),
            )


# ============================================================ toggle_bookmark

def test_toggle_bookmark_creates_then_unbookmarks(
    gallery_env, make_user, make_upload,
):
    from stroke_order.gallery import service
    user_id = make_user()
    upload_id = make_upload(user_id=user_id)
    r = service.toggle_bookmark(user_id=user_id, upload_id=upload_id)
    assert r["bookmarked"] is True
    r = service.toggle_bookmark(user_id=user_id, upload_id=upload_id)
    assert r["bookmarked"] is False


def test_toggle_bookmark_nonexistent_upload(gallery_env, make_user):
    from stroke_order.gallery import service
    user_id = make_user()
    with pytest.raises(service.NotFound):
        service.toggle_bookmark(user_id=user_id, upload_id=99999)


def test_is_bookmarked_by(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    u2 = make_user("u2@t")
    upload_id = make_upload(user_id=u1)
    service.toggle_bookmark(user_id=u1, upload_id=upload_id)
    assert service.is_bookmarked_by(upload_id=upload_id, user_id=u1) is True
    assert service.is_bookmarked_by(upload_id=upload_id, user_id=u2) is False


# ============================================================ list_uploads sort + bookmarked

def test_list_sort_by_likes(gallery_env, make_user, make_upload):
    """sort=likes 按 like_count desc 排，newest 為 tiebreak。"""
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    u2 = make_user("u2@t")
    # 3 uploads at different times
    upload_a = make_upload(user_id=u1, title="A",
                           created_at="2026-05-04T00:00:00Z")
    upload_b = make_upload(user_id=u1, title="B",
                           created_at="2026-05-04T00:01:00Z")
    upload_c = make_upload(user_id=u1, title="C",
                           created_at="2026-05-04T00:02:00Z")
    # likes: A=2, B=0, C=1
    service.toggle_like(user_id=u1, upload_id=upload_a)
    service.toggle_like(user_id=u2, upload_id=upload_a)
    service.toggle_like(user_id=u1, upload_id=upload_c)

    listed = service.list_uploads(sort="likes")
    titles = [it["title"] for it in listed["items"]]
    # 預期: A (2 likes), C (1 like), B (0 likes)
    assert titles == ["A", "C", "B"]


def test_list_sort_default_newest(gallery_env, make_user, make_upload):
    """default sort = newest first（保 r28 行為）。"""
    from stroke_order.gallery import service
    u1 = make_user()
    upload_a = make_upload(user_id=u1, title="A",
                           created_at="2026-05-04T00:00:00Z")
    upload_b = make_upload(user_id=u1, title="B",
                           created_at="2026-05-04T00:01:00Z")
    listed = service.list_uploads()
    titles = [it["title"] for it in listed["items"]]
    assert titles == ["B", "A"]  # B newer


def test_list_sort_invalid_rejected(gallery_env):
    from stroke_order.gallery import service
    with pytest.raises(service.InvalidUpload, match="sort"):
        service.list_uploads(sort="bogus")


def test_list_bookmarked_by_filter(gallery_env, make_user, make_upload):
    """bookmarked_by filter 只列該 user 已 bookmark 的 upload。"""
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    u2 = make_user("u2@t")
    a = make_upload(user_id=u1, title="A")
    b = make_upload(user_id=u1, title="B")
    c = make_upload(user_id=u1, title="C")
    # u1 bookmarks A and C; u2 bookmarks B only
    service.toggle_bookmark(user_id=u1, upload_id=a)
    service.toggle_bookmark(user_id=u1, upload_id=c)
    service.toggle_bookmark(user_id=u2, upload_id=b)

    # u1 view
    listed = service.list_uploads(bookmarked_by=u1)
    titles = sorted(it["title"] for it in listed["items"])
    assert titles == ["A", "C"]

    # u2 view
    listed = service.list_uploads(bookmarked_by=u2)
    titles = sorted(it["title"] for it in listed["items"])
    assert titles == ["B"]


def test_list_bookmarked_by_me_column(gallery_env, make_user, make_upload):
    """list_uploads 帶 viewer_user_id 時，每個 item 含 bookmarked_by_me。"""
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    u2 = make_user("u2@t")
    upload_id = make_upload(user_id=u1)
    service.toggle_bookmark(user_id=u1, upload_id=upload_id)

    # u1 viewer → bookmarked_by_me=True
    listed = service.list_uploads(viewer_user_id=u1)
    assert listed["items"][0]["bookmarked_by_me"] is True
    # u2 viewer → False
    listed = service.list_uploads(viewer_user_id=u2)
    assert listed["items"][0]["bookmarked_by_me"] is False
    # anon → False
    listed = service.list_uploads()
    assert listed["items"][0]["bookmarked_by_me"] is False


def test_list_combo_sort_and_bookmarked(gallery_env, make_user, make_upload):
    """sort=likes + bookmarked_by filter combo 兩個同時生效。"""
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    u2 = make_user("u2@t")
    a = make_upload(user_id=u1, title="A",
                    created_at="2026-05-04T00:00Z")
    b = make_upload(user_id=u1, title="B",
                    created_at="2026-05-04T00:01Z")
    c = make_upload(user_id=u1, title="C",
                    created_at="2026-05-04T00:02Z")
    # u1 bookmarks A and C
    service.toggle_bookmark(user_id=u1, upload_id=a)
    service.toggle_bookmark(user_id=u1, upload_id=c)
    # likes: A=2, C=1
    service.toggle_like(user_id=u1, upload_id=a)
    service.toggle_like(user_id=u2, upload_id=a)
    service.toggle_like(user_id=u1, upload_id=c)

    listed = service.list_uploads(bookmarked_by=u1, sort="likes")
    titles = [it["title"] for it in listed["items"]]
    # 只 A, C（B 沒 bookmark）；按 likes 排 → A, C
    assert titles == ["A", "C"]


# ============================================================ FK cascade

def test_delete_upload_cascades_bookmarks(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    from stroke_order.gallery.db import db_connection
    u1 = make_user("u1@t")
    upload_id = make_upload(user_id=u1)
    service.toggle_bookmark(user_id=u1, upload_id=upload_id)
    with db_connection() as conn:
        n = conn.execute(
            "SELECT count(*) AS n FROM bookmarks WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()["n"]
        assert n == 1
    service.delete_upload(upload_id=upload_id, user_id=u1)
    with db_connection() as conn:
        n = conn.execute(
            "SELECT count(*) AS n FROM bookmarks WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()["n"]
    assert n == 0


# ============================================================ API integration

def test_api_bookmark_endpoint_requires_login(gallery_env, make_upload):
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    upload_id = make_upload()
    client = TestClient(create_app())
    r = client.post(f"/api/gallery/uploads/{upload_id}/bookmark")
    assert r.status_code == 401


def test_api_bookmark_endpoint_logged_in(
    gallery_env, make_user, make_upload,
):
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    from stroke_order.gallery import auth as auth_mod
    user_id = make_user()
    upload_id = make_upload(user_id=user_id)
    session = auth_mod.create_session(user_id=user_id)
    client = TestClient(create_app())
    client.cookies.set("psd_session", session)
    r = client.post(f"/api/gallery/uploads/{upload_id}/bookmark")
    assert r.status_code == 200
    assert r.json()["bookmarked"] is True
    # 第二次 → unbookmark
    r = client.post(f"/api/gallery/uploads/{upload_id}/bookmark")
    assert r.json()["bookmarked"] is False


def test_api_list_bookmarked_filter_requires_login(gallery_env):
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    client = TestClient(create_app())
    r = client.get("/api/gallery/uploads?bookmarked=true")
    assert r.status_code == 401


def test_api_list_sort_likes(gallery_env, make_user, make_upload):
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    from stroke_order.gallery import service
    u1 = make_user("u1@t")
    a = make_upload(user_id=u1, title="A",
                    created_at="2026-05-04T00:00Z")
    b = make_upload(user_id=u1, title="B",
                    created_at="2026-05-04T00:01Z")
    service.toggle_like(user_id=u1, upload_id=b)

    client = TestClient(create_app())
    r = client.get("/api/gallery/uploads?sort=likes")
    assert r.status_code == 200
    titles = [it["title"] for it in r.json()["items"]]
    assert titles == ["B", "A"]  # B 1 like, A 0


def test_api_get_upload_includes_bookmarked_by_me(
    gallery_env, make_user, make_upload,
):
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    from stroke_order.gallery import auth as auth_mod, service
    u1 = make_user()
    upload_id = make_upload(user_id=u1)
    service.toggle_bookmark(user_id=u1, upload_id=upload_id)

    session = auth_mod.create_session(user_id=u1)
    client = TestClient(create_app())
    client.cookies.set("psd_session", session)
    r = client.get(f"/api/gallery/uploads/{upload_id}")
    assert r.status_code == 200
    upload = r.json()["upload"]
    assert upload["bookmarked_by_me"] is True
