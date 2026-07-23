"""5fy: 文字黑名單詞庫＋首次上傳 24h 審閱期（防護三部曲之二）。

黑名單掛 ``_safe_unicode_str`` 單一入口——title/comment/display_name/
bio/檢舉 detail 全蓋；審閱期＝首件起 24h 內上傳暫不公開、查詢入口
懶釋放（免 cron）、本人可見自己的隱藏件。
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.exporters.envelope import embed_export_envelope


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


def _svg_bytes(tag: str) -> bytes:
    return embed_export_envelope(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9">'
        f'<desc>{tag}</desc><rect width="9" height="9"/></svg>',
        mode="grid", app_version="0.0.1").encode("utf-8")


def _upload(user_id: int, title: str = "普通標題", comment: str = "",
            tag: str = "") -> dict:
    from stroke_order.gallery import service
    return service.create_upload(
        user_id=user_id, content_bytes=_svg_bytes(tag or title),
        filename="g.svg", title=title, comment=comment, kind="grid")


def _backdate_first_upload(user_id: int, hours: float) -> None:
    """把該 user 全部上傳的 created_at 往前撥（模擬時間流逝）。"""
    from stroke_order.gallery.db import db_connection
    ts = (datetime.now(timezone.utc)
          - timedelta(hours=hours)).isoformat()
    with db_connection() as conn:
        conn.execute(
            "UPDATE uploads SET created_at = ? WHERE user_id = ?",
            (ts, user_id))


# ================================================= 黑名單：正規化比對

@pytest.mark.parametrize("text", [
    "幹你娘",             # 直球
    "幹 你 娘",           # 夾空白
    "幹.你.娘",           # 夾標點
    "幹－你－娘",         # 全形符號
    "ＦＵＣＫ",           # 全形英文（NFKC 折疊）
    "FuCk you",           # 大小寫
    "前綴幹你娘後綴",     # 子字串
])
def test_blocklist_hits_with_evasion(gallery_env, text):
    from stroke_order.gallery.service import _blocked_words_hit
    assert _blocked_words_hit(text) is True


@pytest.mark.parametrize("text", [
    "我的隸書練字", "永字八法練習", "心經抄經分享",
    "楷書 vs 隸書比較", "第一次雷雕作品",
])
def test_blocklist_passes_normal_text(gallery_env, text):
    from stroke_order.gallery.service import _blocked_words_hit
    assert _blocked_words_hit(text) is False


def test_blocklist_file_parses(gallery_env):
    from stroke_order.gallery.service import _load_blocked_words
    words = _load_blocked_words()
    assert len(words) >= 20            # 基礎詞庫存在
    assert all(w == w.casefold() for w in words)


# ================================================= 黑名單：全欄位覆蓋

def test_blocklist_rejects_title(gallery_env, make_user):
    from stroke_order.gallery import service
    uid = make_user()
    with pytest.raises(service.InvalidUpload, match="不當字詞") as ei:
        _upload(uid, title="幹你娘標題")
    assert "幹你娘" not in str(ei.value)    # 不回顯命中詞


def test_blocklist_rejects_comment(gallery_env, make_user):
    from stroke_order.gallery import service
    uid = make_user()
    with pytest.raises(service.InvalidUpload, match="不當字詞"):
        _upload(uid, comment="去 你 媽 的")


def test_blocklist_rejects_profile_fields(gallery_env, make_user):
    from stroke_order.gallery import service
    uid = make_user()
    with pytest.raises(service.InvalidUpload, match="不當字詞"):
        service.update_profile(user_id=uid, display_name="婊子",
                               bio=None)
    with pytest.raises(service.InvalidUpload, match="不當字詞"):
        service.update_profile(user_id=uid, display_name=None,
                               bio="加賴詳談喔")


def test_blocklist_rejects_report_detail(gallery_env, make_user):
    from stroke_order.gallery import service
    author = make_user("author@example.com")
    rec = _upload(author)
    with pytest.raises(service.InvalidUpload, match="不當字詞"):
        service.create_report(upload_id=rec["id"], reason="other",
                              detail="fuck this",
                              reporter_ip="1.2.3.4")


# ================================================= 首次上傳 24h 審閱期

def test_first_upload_hidden_with_reason(gallery_env, make_user):
    from stroke_order.gallery import service
    uid = make_user()
    rec = _upload(uid, title="我的第一件")
    assert rec["hidden"] == 1 or rec["hidden"] is True
    assert rec["hide_reason"] == service.HIDE_REASON_FIRST24


def test_uploads_within_window_also_held(gallery_env, make_user):
    from stroke_order.gallery import service
    uid = make_user()
    _upload(uid, title="第一件", tag="a")
    rec2 = _upload(uid, title="第二件", tag="b")
    assert rec2["hide_reason"] == service.HIDE_REASON_FIRST24


def test_review_period_visibility(gallery_env, make_user):
    """公眾看不到；本人看得到（帶隱藏標示）；他人看不到。"""
    from stroke_order.gallery import service
    author = make_user("author@example.com")
    other = make_user("other@example.com")
    _upload(author, title="審閱中作品")
    assert service.list_uploads(page=1, size=10)["total"] == 0
    mine = service.list_uploads(page=1, size=10,
                                viewer_user_id=author)
    assert mine["total"] == 1
    assert mine["items"][0]["hidden"]
    assert service.list_uploads(page=1, size=10,
                                viewer_user_id=other)["total"] == 0


def test_review_period_auto_release_after_24h(gallery_env, make_user):
    """時間過 24h → 查詢入口懶釋放自動公開（免 cron）。"""
    from stroke_order.gallery import service
    uid = make_user()
    rec = _upload(uid, title="到期自動公開", tag="x")
    _upload(uid, title="窗內第二件", tag="y")
    _backdate_first_upload(uid, hours=25)
    out = service.list_uploads(page=1, size=10)
    assert out["total"] == 2                     # 兩件都釋放
    up = service.get_upload(rec["id"])
    assert not up["hidden"] and up["hide_reason"] is None


def test_review_period_not_released_before_24h(gallery_env, make_user):
    from stroke_order.gallery import service
    uid = make_user()
    _upload(uid, title="剛滿 23 小時", tag="x")
    _backdate_first_upload(uid, hours=23)
    assert service.list_uploads(page=1, size=10)["total"] == 0


def test_established_user_uploads_public_immediately(gallery_env,
                                                     make_user):
    """老帳號（首件已滿 24h）之後的上傳即時公開。"""
    from stroke_order.gallery import service
    uid = make_user()
    _upload(uid, title="舊作", tag="old")
    _backdate_first_upload(uid, hours=30)
    rec = _upload(uid, title="新作即時公開", tag="new")
    assert not rec["hidden"] and rec["hide_reason"] is None
    assert service.list_uploads(page=1, size=10)["total"] == 2


def test_manual_review_takes_precedence(gallery_env, make_user):
    """5fx 人工審閱（管理員勾選）優先於 24h 審閱期——不會自動釋放。"""
    from stroke_order.gallery import service
    uid = make_user()
    service.admin_set_user_moderation(user_id=uid, status="review")
    rec = _upload(uid, title="人工審閱件")
    assert rec["hide_reason"] == service.HIDE_REASON_PENDING
    _backdate_first_upload(uid, hours=30)
    up = service.get_upload(rec["id"])
    assert up["hidden"]                          # 懶釋放不碰人工審閱件


def test_release_does_not_touch_other_hide_reasons(gallery_env,
                                                   make_user):
    from stroke_order.gallery import service
    uid = make_user()
    rec = _upload(uid, title="被下架的", tag="x")
    service.admin_set_upload_hidden(upload_id=rec["id"], hidden=True)
    _backdate_first_upload(uid, hours=30)
    service.list_uploads(page=1, size=10)        # 觸發懶釋放
    assert service.get_upload(rec["id"])["hidden"]


# ================================================= API＋前端契約

def test_api_upload_reports_review_period(gallery_env):
    from stroke_order.web.server import create_app
    app = create_app()
    c = TestClient(app)
    r0 = c.post("/api/gallery/auth/request-login",
                json={"email": "new@example.com"})
    assert r0.status_code == 200
    from stroke_order.gallery.auth import make_login_token
    c.get(f"/api/gallery/auth/consume?"
          f"token={make_login_token('new@example.com')}",
          follow_redirects=False)
    r = c.post("/api/gallery/uploads",
               files={"file": ("a.svg", _svg_bytes("api"),
                               "image/svg+xml")},
               data={"title": "API 首次上傳", "kind": "grid"})
    assert r.status_code == 200, r.text
    up = r.json()["upload"]
    assert up["hidden"] and up["hide_reason"] == "first-upload-review"


def test_frontend_review_period_contract(gallery_env):
    from stroke_order.web.server import create_app
    c = TestClient(create_app())
    gl = c.get("/gallery").text
    assert "24 小時審閱期" in gl
    up = c.get("/static/gallery/uploader.js").text
    assert "first-upload-review" in up and "24 小時審閱期" in up
    gjs = c.get("/static/gallery/gallery.js").text
    assert "_hiddenLabel" in gjs
    assert "審閱期中" in gjs
