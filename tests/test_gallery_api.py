"""Phase 5g — gallery HTTP endpoints.

Drives the FastAPI app via TestClient. Each test gets a fresh
gallery_dir (SQLite + uploads). Auth flows use dev mode so no SMTP.

Convention: tests that need an authenticated user build a fresh
``TestClient`` per user via ``_login_client(app, email)``. Each
client carries its own cookie jar, so multi-user tests can keep
sessions distinct without juggling per-request cookie kwargs.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# --------------------------------------------------------------- fixtures

@pytest.fixture
def env(monkeypatch):
    """Per-test gallery dir + dev-mode SMTP + DB cache reset."""
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


@pytest.fixture
def client(app):
    """Anonymous client (no session)."""
    return TestClient(app)


def _login_client(app, email: str) -> TestClient:
    """Build a fresh TestClient and authenticate it as ``email``.
    Subsequent requests on the returned client send the session cookie
    automatically."""
    c = TestClient(app)
    # Drive the real request-login flow once so its handler is exercised
    r = c.post(
        "/api/gallery/auth/request-login",
        json={"email": email},
    )
    assert r.status_code == 200, r.text
    # Mint our own token + consume it (deterministic, no stdout capture)
    from stroke_order.gallery.auth import make_login_token
    token = make_login_token(email)
    r2 = c.get(
        f"/api/gallery/auth/consume?token={token}",
        follow_redirects=False,
    )
    assert r2.status_code == 303, r2.text
    assert "psd_session" in c.cookies
    return c


def _psd_payload(traces=None) -> bytes:
    """Build a minimal valid PSD JSON for upload tests."""
    if traces is None:
        traces = [
            {
                "id": "abc",
                "char": "永",
                "label_source": "given",
                "style": "kaishu",
                "tags": ["test"],
                "device": "mouse",
                "ts": "2026-04-26T10:00:00Z",
                "em_size": 2048,
                "canvas_size": [512, 512],
                "strokes": [
                    {
                        "points": [[100, 200, 0, 0.5],
                                   [800, 1000, 320, 0.7]],
                        "duration_ms": 320,
                        "pen_down_at": [100, 200],
                        "pen_up_at": [800, 1000],
                    },
                ],
                "source": {"type": "freehand"},
            },
        ]
    payload = {
        "schema": "stroke-order-psd-v1",
        "exported_at": "2026-04-26T10:00:00Z",
        "trace_count": len(traces),
        "traces": traces,
    }
    return json.dumps(payload).encode("utf-8")


# =========================================================== /gallery page

def test_gallery_page_route_returns_html(client):
    """5g-6 onwards: /gallery serves the SPA shell."""
    r = client.get("/gallery")
    assert r.status_code == 200
    text = r.text
    # All three modal anchors that the JS relies on
    assert "gl-login-dialog" in text
    assert "gl-upload-dialog" in text
    assert "gl-profile-dialog" in text
    # SPA module loads
    assert "gallery/gallery.js" in text
    assert "gallery/gallery.css" in text


def test_gallery_static_modules_serve(client):
    """All three JS modules + CSS reachable."""
    for path, must_have in [
        ("/static/gallery/gallery.css",
         ["--gl-accent", ".gl-card", ".gl-dialog"]),
        ("/static/gallery/gallery.js",
         ["fetchMe", "showLoginDialog", "showUploadDialog"]),
        ("/static/gallery/auth.js",
         ["attachAuthHandlers", "fetchMe"]),
        ("/static/gallery/uploader.js",
         ["attachUploaderHandlers", "stroke-order-psd-v1"]),
    ]:
        r = client.get(path)
        assert r.status_code == 200, f"{path} → {r.status_code}"
        for needle in must_have:
            assert needle in r.text, f"{path}: missing {needle!r}"


# =========================================================== auth

def test_auth_request_login_dev_mode_succeeds(client):
    r = client.post(
        "/api/gallery/auth/request-login",
        json={"email": "alice@example.com"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_auth_request_login_rejects_bad_email(client):
    r = client.post(
        "/api/gallery/auth/request-login",
        json={"email": "not-an-email"},
    )
    assert r.status_code == 422


def test_auth_consume_invalid_token_returns_400(client):
    r = client.get(
        "/api/gallery/auth/consume?token=clearly-bad",
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_auth_consume_sets_session_cookie(app):
    cli = _login_client(app, "alice@example.com")
    r = cli.get("/api/gallery/me")
    assert r.status_code == 200
    body = r.json()
    assert body["logged_in"] is True
    assert body["user"]["email"] == "alice@example.com"


def test_auth_logout_clears_session(app):
    cli = _login_client(app, "alice@example.com")
    r = cli.post("/api/gallery/auth/logout")
    assert r.status_code == 200
    # Same client now logged out (server-side session deleted)
    r2 = cli.get("/api/gallery/me")
    assert r2.json()["logged_in"] is False


def test_me_anonymous_returns_logged_in_false(client):
    r = client.get("/api/gallery/me")
    assert r.status_code == 200
    assert r.json() == {"logged_in": False}


# =========================================================== profile

def test_profile_update_requires_login(client):
    r = client.put("/api/gallery/me", json={"display_name": "X"})
    assert r.status_code == 401


def test_profile_update_persists_display_name_and_bio(app):
    cli = _login_client(app, "alice@example.com")
    r = cli.put(
        "/api/gallery/me",
        json={"display_name": "王小明", "bio": "我喜歡寫字"},
    )
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    assert user["display_name"] == "王小明"
    assert user["bio"] == "我喜歡寫字"


def test_profile_update_too_long_rejected(app):
    cli = _login_client(app, "alice@example.com")
    r = cli.put(
        "/api/gallery/me",
        json={"display_name": "x" * 200},
    )
    assert r.status_code == 422


# =========================================================== uploads

def test_upload_requires_login(client):
    r = client.post(
        "/api/gallery/uploads",
        files={"file": ("psd.json", b"{}", "application/json")},
        data={"title": "x", "comment": ""},
    )
    assert r.status_code == 401


def test_upload_happy_path(app):
    cli = _login_client(app, "alice@example.com")
    payload = _psd_payload()
    r = cli.post(
        "/api/gallery/uploads",
        files={"file": ("my.json", payload, "application/json")},
        data={"title": "我的隸書練字", "comment": "練了一個月"},
    )
    assert r.status_code == 200, r.text
    record = r.json()["upload"]
    assert record["title"] == "我的隸書練字"
    assert record["comment"] == "練了一個月"
    assert record["trace_count"] == 1
    assert record["unique_chars"] == 1
    assert record["styles_used"] == ["kaishu"]
    assert record["uploader_email"] == "alice@example.com"
    assert record["filename"] == "my.json"


def test_upload_rejects_bad_schema(app):
    cli = _login_client(app, "alice@example.com")
    bad = json.dumps({"schema": "wrong", "traces": []}).encode()
    r = cli.post(
        "/api/gallery/uploads",
        files={"file": ("bad.json", bad, "application/json")},
        data={"title": "T", "comment": ""},
    )
    assert r.status_code == 422
    assert "schema" in r.json()["detail"]


def test_upload_rejects_empty_traces(app):
    cli = _login_client(app, "alice@example.com")
    payload = json.dumps({
        "schema": "stroke-order-psd-v1",
        "traces": [],
    }).encode()
    r = cli.post(
        "/api/gallery/uploads",
        files={"file": ("empty.json", payload, "application/json")},
        data={"title": "T", "comment": ""},
    )
    assert r.status_code == 422


def test_upload_rejects_no_title(app):
    cli = _login_client(app, "alice@example.com")
    r = cli.post(
        "/api/gallery/uploads",
        files={"file": ("p.json", _psd_payload(), "application/json")},
        data={"title": "   ", "comment": ""},
    )
    assert r.status_code == 422


def test_upload_dedup_same_user(app):
    """Same user uploading byte-identical content twice → 409."""
    cli = _login_client(app, "alice@example.com")
    payload = _psd_payload()
    r1 = cli.post(
        "/api/gallery/uploads",
        files={"file": ("p.json", payload, "application/json")},
        data={"title": "T", "comment": ""},
    )
    assert r1.status_code == 200
    r2 = cli.post(
        "/api/gallery/uploads",
        files={"file": ("p.json", payload, "application/json")},
        data={"title": "T2", "comment": ""},
    )
    assert r2.status_code == 409
    assert "已上傳過" in r2.json()["detail"]


def test_upload_same_content_different_users_allowed(app):
    """Cross-user duplicate hash is allowed (Phase 5h will tag, not block)."""
    cli_a = _login_client(app, "alice@example.com")
    cli_b = _login_client(app, "bob@example.com")
    payload = _psd_payload()
    ra = cli_a.post(
        "/api/gallery/uploads",
        files={"file": ("p.json", payload, "application/json")},
        data={"title": "Alice's", "comment": ""},
    )
    rb = cli_b.post(
        "/api/gallery/uploads",
        files={"file": ("p.json", payload, "application/json")},
        data={"title": "Bob's", "comment": ""},
    )
    assert ra.status_code == 200, ra.text
    assert rb.status_code == 200, rb.text


# =========================================================== list / get

def test_list_uploads_empty(client):
    r = client.get("/api/gallery/uploads")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1


def test_list_uploads_paginated_newest_first(app, client):
    """Upload 3 records → list returns them newest-first."""
    cli = _login_client(app, "alice@example.com")
    titles = []
    for i in range(3):
        # Vary the trace so each upload has a unique hash
        traces = [{
            "id": f"t{i}",
            "char": "永",
            "label_source": "given",
            "style": "kaishu",
            "tags": [],
            "device": "mouse",
            "ts": f"2026-04-26T10:0{i}:00Z",
            "em_size": 2048,
            "canvas_size": [512, 512],
            "strokes": [{
                "points": [[i * 10, 0, 0, 0.5], [800, 1000, 100, 0.5]],
                "duration_ms": 100,
                "pen_down_at": [i * 10, 0],
                "pen_up_at": [800, 1000],
            }],
            "source": {"type": "freehand"},
        }]
        title = f"Title #{i}"
        titles.append(title)
        r = cli.post(
            "/api/gallery/uploads",
            files={"file": (f"p{i}.json", _psd_payload(traces),
                            "application/json")},
            data={"title": title, "comment": ""},
        )
        assert r.status_code == 200, r.text

    body = client.get("/api/gallery/uploads").json()
    assert body["total"] == 3
    titles_returned = [it["title"] for it in body["items"]]
    assert titles_returned == list(reversed(titles))


# =========================================================== download

def test_download_returns_original_bytes(app, client):
    cli = _login_client(app, "alice@example.com")
    payload = _psd_payload()
    r = cli.post(
        "/api/gallery/uploads",
        files={"file": ("p.json", payload, "application/json")},
        data={"title": "T", "comment": ""},
    )
    upload_id = r.json()["upload"]["id"]
    rd = client.get(f"/api/gallery/uploads/{upload_id}/download")
    assert rd.status_code == 200
    assert rd.content == payload


def test_download_404_for_missing(client):
    r = client.get("/api/gallery/uploads/9999/download")
    assert r.status_code == 404


# =========================================================== delete

def test_delete_only_own(app, client):
    """Alice uploads; Bob can't delete it; anonymous can't either;
    Alice can."""
    cli_a = _login_client(app, "alice@example.com")
    cli_b = _login_client(app, "bob@example.com")
    payload = _psd_payload()
    r = cli_a.post(
        "/api/gallery/uploads",
        files={"file": ("p.json", payload, "application/json")},
        data={"title": "Alice's", "comment": ""},
    )
    upload_id = r.json()["upload"]["id"]

    # Bob → 403
    rb = cli_b.delete(f"/api/gallery/uploads/{upload_id}")
    assert rb.status_code == 403

    # Anonymous → 401
    ra_anon = client.delete(f"/api/gallery/uploads/{upload_id}")
    assert ra_anon.status_code == 401

    # Alice → 200
    ra = cli_a.delete(f"/api/gallery/uploads/{upload_id}")
    assert ra.status_code == 200

    # Confirm deletion
    rg = client.get(f"/api/gallery/uploads/{upload_id}")
    assert rg.status_code == 404


def test_delete_also_removes_disk_file(app, env):
    cli = _login_client(app, "alice@example.com")
    r = cli.post(
        "/api/gallery/uploads",
        files={"file": ("p.json", _psd_payload(), "application/json")},
        data={"title": "T", "comment": ""},
    )
    upload_id = r.json()["upload"]["id"]
    rel_path = r.json()["upload"]["file_path"]
    abs_path = env / "uploads" / rel_path
    assert abs_path.is_file()

    cli.delete(f"/api/gallery/uploads/{upload_id}")
    assert not abs_path.exists()


# =========================================================== regression

def test_gallery_endpoints_dont_break_existing_routes(client):
    """Sanity: pre-existing endpoints keep working with gallery added."""
    for path in ["/", "/sutra-editor", "/handwriting", "/api/health"]:
        r = client.get(path)
        assert r.status_code == 200
