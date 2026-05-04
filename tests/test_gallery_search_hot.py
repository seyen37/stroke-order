"""Phase 5b r29c: gallery hot ranking + search tests。"""

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
    """Allow custom email + display_name to test search by author."""
    def _make(email: str = "tester@example.com",
              display_name: str = "Tester") -> int:
        from stroke_order.gallery.db import db_connection
        with db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, display_name, created_at) "
                "VALUES (?, ?, ?)",
                (email, display_name, "2026-05-04T00:00:00+00:00"),
            )
            return int(cur.lastrowid)
    return _make


@pytest.fixture
def make_upload(gallery_env, make_user):
    import secrets
    def _make(user_id: int = None, title: str = "test",
              comment: str = "",
              created_at: str = "2026-05-04T00:00:00+00:00") -> int:
        if user_id is None:
            # 每次給獨立 user 避免 UNIQUE email 衝突
            user_id = make_user(f"auto{secrets.token_hex(4)}@t")
        from stroke_order.gallery.db import db_connection
        nonce = secrets.token_hex(8)
        with db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO uploads "
                "(user_id, title, comment, file_path, file_size, "
                " file_hash, kind, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'psd', ?)",
                (user_id, title, comment, f"{user_id}/{nonce}.json",
                 100, nonce, created_at),
            )
            return int(cur.lastrowid)
    return _make


# ============================================================ sort=hot

def test_sort_hot_recent_likes_beats_old_likes(
    gallery_env, make_user, make_upload,
):
    """Hot ranking: 最近 + 受歡迎 > 古老 + 更受歡迎。

    Formula: log10(likes) * 5 + julianday(created)。50 likes 19d ago 應該
    輸給 5 likes 1d ago（recency boost > like log diff）。
    """
    from stroke_order.gallery import service
    u_owner = make_user("owner@t")
    a = make_upload(user_id=u_owner, title="A_old_popular",
                    created_at="2026-04-15T00:00:00Z")  # 19d ago
    b = make_upload(user_id=u_owner, title="B_recent_some",
                    created_at="2026-05-03T00:00:00Z")  # 1d ago
    c = make_upload(user_id=u_owner, title="C_today_zero",
                    created_at="2026-05-04T00:00:00Z")  # today
    # likes: A=50, B=5, C=0
    for i in range(50):
        u = make_user(f"liker_a{i}@t")
        service.toggle_like(user_id=u, upload_id=a)
    for i in range(5):
        u = make_user(f"liker_b{i}@t")
        service.toggle_like(user_id=u, upload_id=b)

    listed = service.list_uploads(sort="hot")
    titles = [it["title"] for it in listed["items"]]
    # 預期：B (5 likes 1d) > C (0 likes today) > A (50 likes 19d)
    # log10(5)*5 = 3.5 day boost；log10(50)*5 = 8.5 day boost
    # B: 3.5 + (J-1) = J + 2.5
    # C: 0 + J = J
    # A: 8.5 + (J-19) = J - 10.5
    # → B > C > A
    assert titles == ["B_recent_some", "C_today_zero", "A_old_popular"]


def test_sort_hot_invalid_rejected(gallery_env):
    from stroke_order.gallery import service
    with pytest.raises(service.InvalidUpload, match="sort"):
        service.list_uploads(sort="bogus")


# ============================================================ search

def test_search_by_title(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    u = make_user()
    make_upload(user_id=u, title="九字真言曼陀羅")
    make_upload(user_id=u, title="蓮花座曼陀羅")
    make_upload(user_id=u, title="抄經練字")

    listed = service.list_uploads(q="曼陀羅")
    titles = sorted(it["title"] for it in listed["items"])
    assert titles == ["九字真言曼陀羅", "蓮花座曼陀羅"]


def test_search_by_comment(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    u = make_user()
    make_upload(user_id=u, title="A", comment="心經抄寫")
    make_upload(user_id=u, title="B", comment="金剛經")
    listed = service.list_uploads(q="心經")
    assert [it["title"] for it in listed["items"]] == ["A"]


def test_search_by_author_display_name(
    gallery_env, make_user, make_upload,
):
    from stroke_order.gallery import service
    u_alice = make_user(email="alice@t", display_name="Alice")
    u_bob = make_user(email="bob@t", display_name="Bob")
    a1 = make_upload(user_id=u_alice, title="A1")
    b1 = make_upload(user_id=u_bob, title="B1")
    listed = service.list_uploads(q="Alice")
    titles = [it["title"] for it in listed["items"]]
    assert titles == ["A1"]


def test_search_no_match(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    make_upload(title="A")
    make_upload(title="B")
    listed = service.list_uploads(q="不存在的字串")
    assert listed["total"] == 0
    assert listed["items"] == []


def test_search_combines_with_filter_and_sort(
    gallery_env, make_user, make_upload,
):
    """q + sort=hot + bookmarked_by 三者組合。"""
    from stroke_order.gallery import service
    u = make_user()
    a = make_upload(user_id=u, title="曼陀羅A",
                    created_at="2026-05-01T00:00:00Z")
    b = make_upload(user_id=u, title="曼陀羅B",
                    created_at="2026-05-04T00:00:00Z")
    c = make_upload(user_id=u, title="抄經 C",
                    created_at="2026-05-04T00:00:00Z")
    service.toggle_bookmark(user_id=u, upload_id=a)
    service.toggle_bookmark(user_id=u, upload_id=b)

    # q=曼陀羅 + bookmarked_by=u + sort=hot
    listed = service.list_uploads(
        q="曼陀羅", bookmarked_by=u, sort="hot",
        viewer_user_id=u,
    )
    titles = [it["title"] for it in listed["items"]]
    # C (抄經) 不含曼陀羅 → 排除
    # A 跟 B 都含曼陀羅且都 bookmarked
    # sort=hot：B (newer) 應贏 A
    assert titles == ["曼陀羅B", "曼陀羅A"]


def test_search_query_too_long_rejected(gallery_env):
    from stroke_order.gallery import service
    long_q = "a" * 200  # > 100 max
    with pytest.raises(service.InvalidUpload, match="過長"):
        service.list_uploads(q=long_q)


def test_search_empty_string_no_filter(
    gallery_env, make_user, make_upload,
):
    """空字串 / 純 whitespace q 視同 None — 不應 filter。"""
    from stroke_order.gallery import service
    make_upload(title="A")
    make_upload(title="B")
    listed_empty = service.list_uploads(q="")
    listed_whitespace = service.list_uploads(q="   ")
    listed_none = service.list_uploads()
    assert listed_empty["total"] == listed_whitespace["total"]
    assert listed_empty["total"] == listed_none["total"] == 2


# ============================================================ API integration

def test_api_sort_hot(gallery_env, make_user, make_upload):
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    from stroke_order.gallery import service
    u = make_user()
    a = make_upload(user_id=u, title="A",
                    created_at="2026-05-01T00:00:00Z")
    b = make_upload(user_id=u, title="B",
                    created_at="2026-05-04T00:00:00Z")
    # B 一個 like
    u2 = make_user("liker@t")
    service.toggle_like(user_id=u2, upload_id=b)
    client = TestClient(create_app())
    r = client.get("/api/gallery/uploads?sort=hot")
    assert r.status_code == 200
    titles = [it["title"] for it in r.json()["items"]]
    # B (1 like, today) > A (0 likes, 3d ago)
    assert titles == ["B", "A"]


def test_api_search_query(gallery_env, make_user, make_upload):
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    u = make_user()
    make_upload(user_id=u, title="蓮花座曼陀羅")
    make_upload(user_id=u, title="抄經練字")
    client = TestClient(create_app())
    r = client.get("/api/gallery/uploads?q=蓮花")
    assert r.status_code == 200
    titles = [it["title"] for it in r.json()["items"]]
    assert titles == ["蓮花座曼陀羅"]


def test_api_search_invalid_too_long(gallery_env):
    """API q max_length=100 應由 FastAPI 阻擋（422）。"""
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    client = TestClient(create_app())
    r = client.get("/api/gallery/uploads?q=" + "a" * 200)
    assert r.status_code == 422
