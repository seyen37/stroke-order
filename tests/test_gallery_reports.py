"""5fx: 檢舉（匿名＋登入）＋作者治理（moderation）＋管理端。

Service 層走 gallery_env/make_user；API 層走 env/app/_login_client
（比照 test_gallery_api.py）。挑戰題最短停留時間在測試中 monkeypatch
為 0（verify 讀模組屬性，call-time 取值）。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.exporters.envelope import embed_export_envelope


# ------------------------------------------------- fixtures

@pytest.fixture
def gallery_env(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("STROKE_ORDER_GALLERY_DIR", td)
        monkeypatch.setenv("STROKE_ORDER_AUTH_SECRET",
                           "test-secret-32-bytes-aaaaaaaaaaaaa")
        monkeypatch.setenv("STROKE_ORDER_BASE_URL", "http://test.local")
        monkeypatch.setenv("STROKE_ORDER_AUTH_DEV_MODE", "true")
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
def make_upload(gallery_env):
    def _make(user_id: int, title: str = "測試作品") -> int:
        from stroke_order.gallery import service
        svg = embed_export_envelope(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9">'
            f'<desc>{user_id}-{title}</desc>'
            f'<rect width="9" height="9"/></svg>',
            mode="grid", app_version="0.0.1")
        rec = service.create_upload(
            user_id=user_id, content_bytes=svg.encode("utf-8"),
            filename="g.svg", title=title, comment="", kind="grid")
        return int(rec["id"])
    return _make


@pytest.fixture
def fast_challenge(monkeypatch):
    """測試免等 3 秒停留。"""
    from stroke_order.gallery import service
    monkeypatch.setattr(service, "CHALLENGE_MIN_SECONDS", 0)


@pytest.fixture
def app(gallery_env):
    from stroke_order.web.server import create_app
    return create_app()


@pytest.fixture
def api(app):
    return TestClient(app)


def _login_client(app, email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/gallery/auth/request-login", json={"email": email})
    assert r.status_code == 200, r.text
    from stroke_order.gallery.auth import make_login_token
    token = make_login_token(email)
    r2 = c.get(f"/api/gallery/auth/consume?token={token}",
               follow_redirects=False)
    assert r2.status_code == 303, r2.text
    return c


# ================================================= 挑戰題（防機器人）

def test_challenge_roundtrip(gallery_env, fast_challenge):
    from stroke_order.gallery import service
    ch = service.issue_report_challenge()
    assert 2 <= ch["a"] + ch["b"] <= 16
    service.verify_report_challenge(ch["token"], ch["a"] + ch["b"])


def test_challenge_wrong_answer(gallery_env, fast_challenge):
    from stroke_order.gallery import service
    ch = service.issue_report_challenge()
    with pytest.raises(service.InvalidUpload, match="不正確"):
        service.verify_report_challenge(ch["token"], ch["a"] + ch["b"] + 1)


def test_challenge_too_fast_rejected(gallery_env):
    """停留時間守門：發題後立刻送出 → 拒（機器人特徵）。"""
    from stroke_order.gallery import service
    ch = service.issue_report_challenge()
    with pytest.raises(service.InvalidUpload, match="太快"):
        service.verify_report_challenge(ch["token"], ch["a"] + ch["b"])


def test_challenge_expired_and_malformed(gallery_env, fast_challenge):
    from stroke_order.gallery import service
    ch = service.issue_report_challenge()
    ts, nonce, sig = ch["token"].split(".")
    old_token = f"{int(ts) - 9999}.{nonce}.{sig}"
    with pytest.raises(service.InvalidUpload, match="過期"):
        service.verify_report_challenge(old_token, ch["a"] + ch["b"])
    with pytest.raises(service.InvalidUpload, match="格式"):
        service.verify_report_challenge("garbage", 5)
    with pytest.raises(service.InvalidUpload, match="格式"):
        service.verify_report_challenge(ch["token"], "not-int")


def test_ip_hash_stable_and_salted(gallery_env):
    from stroke_order.gallery import service
    h1 = service.hash_report_ip("1.2.3.4")
    assert h1 == service.hash_report_ip("1.2.3.4")
    assert h1 != service.hash_report_ip("1.2.3.5")
    assert "1.2.3.4" not in h1          # 不存明文


# ================================================= create_report

def test_report_logged_in_happy(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    author = make_user("author@example.com")
    reporter = make_user("reporter@example.com")
    uid = make_upload(author)
    out = service.create_report(upload_id=uid, reason="spam",
                                detail="灌版", reporter_user_id=reporter)
    assert out["total_reports"] == 1 and out["auto_hidden"] is False


def test_report_own_upload_rejected(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    author = make_user()
    uid = make_upload(author)
    with pytest.raises(service.InvalidUpload, match="自己"):
        service.create_report(upload_id=uid, reason="spam",
                              reporter_user_id=author)


def test_report_bad_reason(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    uid = make_upload(make_user())
    with pytest.raises(service.InvalidUpload, match="原因"):
        service.create_report(upload_id=uid, reason="nope",
                              reporter_ip="9.9.9.9")


def test_report_dedup_per_user_and_per_ip(gallery_env, make_user,
                                          make_upload):
    from stroke_order.gallery import service
    author = make_user("author@example.com")
    rep = make_user("rep@example.com")
    uid = make_upload(author)
    service.create_report(upload_id=uid, reason="spam",
                          reporter_user_id=rep)
    with pytest.raises(service.DuplicateUpload, match="已檢舉"):
        service.create_report(upload_id=uid, reason="other",
                              reporter_user_id=rep)
    service.create_report(upload_id=uid, reason="spam",
                          reporter_ip="5.6.7.8")
    with pytest.raises(service.DuplicateUpload, match="已檢舉"):
        service.create_report(upload_id=uid, reason="spam",
                              reporter_ip="5.6.7.8")


def test_report_threshold_auto_hides(gallery_env, make_user, make_upload, established_authors):
    """3 個獨立來源（帳號×1＋IP×2）→ 自動隱藏，公開列表消失。"""
    from stroke_order.gallery import service
    author = make_user("author@example.com")
    rep = make_user("rep@example.com")
    uid = make_upload(author)
    service.create_report(upload_id=uid, reason="inappropriate",
                          reporter_user_id=rep)
    service.create_report(upload_id=uid, reason="inappropriate",
                          reporter_ip="1.1.1.1")
    out = service.create_report(upload_id=uid, reason="inappropriate",
                                reporter_ip="2.2.2.2")
    assert out["total_reports"] == 3 and out["auto_hidden"] is True
    up = service.get_upload(uid)
    assert up["hidden"] and up["hide_reason"] == \
        service.HIDE_REASON_REPORTS
    assert service.list_uploads(page=1, size=10)["total"] == 0


def test_report_daily_rate_limit(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    author = make_user("author@example.com")
    ids = [make_upload(author, title=f"作品{i}")
           for i in range(service.DAILY_REPORT_LIMIT + 1)]
    for i in range(service.DAILY_REPORT_LIMIT):
        service.create_report(upload_id=ids[i], reason="spam",
                              reporter_ip="8.8.8.8")
    with pytest.raises(service.RateLimited, match="頻繁"):
        service.create_report(upload_id=ids[-1], reason="spam",
                              reporter_ip="8.8.8.8")


# ================================================= 管理端 service

def test_admin_hide_unhide(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    uid = make_upload(make_user())
    out = service.admin_set_upload_hidden(upload_id=uid, hidden=True)
    assert out["hidden"] and out["hide_reason"] == \
        service.HIDE_REASON_ADMIN
    out2 = service.admin_set_upload_hidden(upload_id=uid, hidden=False)
    assert not out2["hidden"] and out2["hide_reason"] is None


def test_moderation_review_hides_new_uploads(gallery_env, make_user,
                                             make_upload):
    from stroke_order.gallery import service
    author = make_user()
    service.admin_set_user_moderation(user_id=author, status="review")
    uid = make_upload(author, title="審閱期上傳")
    up = service.get_upload(uid)
    assert up["hidden"] and up["hide_reason"] == \
        service.HIDE_REASON_PENDING
    # 管理員放行 = unhide
    service.admin_set_upload_hidden(upload_id=uid, hidden=False)
    assert not service.get_upload(uid)["hidden"]


def test_moderation_blacklist_blocks_and_hides(gallery_env, make_user, established_authors,
                                               make_upload):
    from stroke_order.gallery import service
    author = make_user()
    u1 = make_upload(author, title="既有作品")
    out = service.admin_set_user_moderation(
        user_id=author, status="blacklisted")
    assert out["hidden_count"] == 1
    assert service.get_upload(u1)["hide_reason"] == \
        service.HIDE_REASON_BLACKLIST
    with pytest.raises(service.Forbidden, match="停權"):
        make_upload(author, title="不該上得去")
    # 解除 → 黑名單隱藏的自動恢復
    out2 = service.admin_set_user_moderation(
        user_id=author, status="normal")
    assert out2["restored_count"] == 1
    assert not service.get_upload(u1)["hidden"]


def test_moderation_unblacklist_keeps_other_hidden(gallery_env,
                                                   make_user,
                                                   make_upload):
    """解除黑名單只恢復「因黑名單隱藏」的——管理員下架的不動。"""
    from stroke_order.gallery import service
    author = make_user()
    u1 = make_upload(author, title="被管理員下架")
    service.admin_set_upload_hidden(upload_id=u1, hidden=True)
    service.admin_set_user_moderation(user_id=author,
                                      status="blacklisted")
    service.admin_set_user_moderation(user_id=author, status="normal")
    assert service.get_upload(u1)["hidden"]           # 仍隱藏


def test_list_reports_joins(gallery_env, make_user, make_upload):
    from stroke_order.gallery import service
    author = make_user("author@example.com")
    rep = make_user("rep@example.com")
    uid = make_upload(author, title="被檢舉的")
    service.create_report(upload_id=uid, reason="copyright",
                          detail="疑似盜圖", reporter_user_id=rep)
    service.create_report(upload_id=uid, reason="spam",
                          reporter_ip="3.3.3.3")
    out = service.list_reports(page=1, size=10)
    assert out["total"] == 2
    it = out["items"][0]
    assert it["upload_title"] == "被檢舉的"
    assert it["author_email"] == "author@example.com"
    assert it["author_moderation_status"] == "normal"
    anon = [i for i in out["items"] if i["anonymous"]]
    named = [i for i in out["items"] if not i["anonymous"]]
    assert len(anon) == 1 and len(named) == 1
    assert named[0]["reporter_email"] == "rep@example.com"


# ================================================= API 層

def _seed_upload(app, email="author@example.com", title="API 測試作品"):
    c = _login_client(app, email)
    svg = embed_export_envelope(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9">'
        f'<rect width="9" height="{len(title)}"/></svg>',
        mode="grid", app_version="0.0.1")
    r = c.post("/api/gallery/uploads",
               files={"file": (title + ".svg", svg.encode(), "image/svg+xml")},
               data={"title": title, "kind": "grid"})
    assert r.status_code == 200, r.text
    return r.json()["upload"]["id"]


def test_api_challenge_shape(api, gallery_env):
    r = api.get("/api/gallery/report-challenge")
    assert r.status_code == 200
    data = r.json()
    assert set(data) == {"a", "b", "token"}


def test_api_report_honeypot_rejected(app, gallery_env):
    uid = _seed_upload(app)
    api = TestClient(app)
    r = api.post(f"/api/gallery/uploads/{uid}/report",
                 json={"reason": "spam", "website": "http://bot.example"})
    assert r.status_code == 400


def test_api_report_anonymous_challenge_flow(app, gallery_env,
                                             fast_challenge):
    uid = _seed_upload(app)
    api = TestClient(app)
    # 缺挑戰題 → 拒
    r0 = api.post(f"/api/gallery/uploads/{uid}/report",
                  json={"reason": "spam"})
    assert r0.status_code == 422
    # 正確挑戰題 → 過
    ch = api.get("/api/gallery/report-challenge").json()
    r1 = api.post(f"/api/gallery/uploads/{uid}/report",
                  json={"reason": "spam",
                        "challenge_token": ch["token"],
                        "challenge_answer": ch["a"] + ch["b"]})
    assert r1.status_code == 200, r1.text
    assert r1.json()["total_reports"] == 1


def test_api_report_logged_in_and_duplicate(app, gallery_env):
    uid = _seed_upload(app)
    rep = _login_client(app, "reporter@example.com")
    r1 = rep.post(f"/api/gallery/uploads/{uid}/report",
                  json={"reason": "inappropriate", "detail": "test"})
    assert r1.status_code == 200, r1.text
    r2 = rep.post(f"/api/gallery/uploads/{uid}/report",
                  json={"reason": "spam"})
    assert r2.status_code == 409


def test_api_kind_filter_regression(app, gallery_env):
    """5fx 修 bug：route pattern 曾把 popup/5fw 新分類擋成 422。"""
    api = TestClient(app)
    for kind in ("zentangle", "popup", "grid"):
        r = api.get(f"/api/gallery/uploads?page=1&size=5&kind={kind}")
        assert r.status_code == 200, f"kind={kind} → {r.status_code}"
    assert api.get(
        "/api/gallery/uploads?kind=evil").status_code == 422


def test_api_admin_requires_permission(app, gallery_env):
    uid = _seed_upload(app)
    api = TestClient(app)
    assert api.get("/api/gallery/admin/reports").status_code == 401
    plain = _login_client(app, "pleb@example.com")
    assert plain.get("/api/gallery/admin/reports").status_code == 403
    assert plain.post(f"/api/gallery/admin/uploads/{uid}/hide",
                      json={"hidden": True}).status_code == 403
    assert plain.get(
        "/api/gallery/uploads?include_hidden=true").status_code == 403


def test_api_admin_full_flow(app, gallery_env, monkeypatch):
    monkeypatch.setenv("GALLERY_ADMIN_EMAILS",
                       " Admin@Example.com , x@y.z ")
    uid = _seed_upload(app)
    admin = _login_client(app, "admin@example.com")
    # /me 帶 is_admin
    me = admin.get("/api/gallery/me").json()
    assert me["is_admin"] is True
    # 緊急下架
    r = admin.post(f"/api/gallery/admin/uploads/{uid}/hide",
                   json={"hidden": True})
    assert r.status_code == 200 and r.json()["upload"]["hidden"]
    # 公開列表消失；admin include_hidden 看得到
    assert TestClient(app).get(
        "/api/gallery/uploads").json()["total"] == 0
    got = admin.get(
        "/api/gallery/uploads?include_hidden=true").json()
    assert got["total"] == 1 and got["items"][0]["hidden"]
    # 作者勾黑名單 → 上傳被拒
    author_id = got["items"][0]["user_id"]
    r2 = admin.post(f"/api/gallery/admin/users/{author_id}/moderation",
                    json={"status": "blacklisted"})
    assert r2.status_code == 200
    author = _login_client(app, "author@example.com")
    svg = embed_export_envelope(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9">'
        '<rect width="1" height="1"/></svg>',
        mode="grid", app_version="0.0.1")
    r3 = author.post("/api/gallery/uploads",
                     files={"file": ("b.svg", svg.encode(),
                                     "image/svg+xml")},
                     data={"title": "黑名單上傳", "kind": "grid"})
    assert r3.status_code == 403
    # 檢舉清單
    rep = _login_client(app, "rep2@example.com")
    rep.post(f"/api/gallery/uploads/{uid}/report",
             json={"reason": "other", "detail": "x"})
    reports = admin.get("/api/gallery/admin/reports").json()
    assert reports["total"] == 1
    assert reports["items"][0]["author_moderation_status"] == \
        "blacklisted"


# ================================================= 前端契約

def test_gallery_page_report_and_admin_ui(api, gallery_env):
    gl = api.get("/gallery").text
    for marker in ('id="gl-report-dialog"', 'id="gl-report-website"',
                   'id="gl-report-challenge"', 'id="gl-admin-reports-btn"',
                   'id="gl-include-hidden"', 'id="gl-admin-reports-dialog"'):
        assert marker in gl, f"gallery.html 缺 {marker}"
    gjs = api.get("/static/gallery/gallery.js").text
    for marker in ("report-challenge", "admin-hide", "include_hidden",
                   "_openReportDialog", "mod-blacklist"):
        assert marker in gjs, f"gallery.js 缺 {marker}"
