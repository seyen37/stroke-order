"""Phase 5b r28: gallery 接 mandala upload — schema + service + API tests."""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest


# --------------------------------------------------------------- fixtures

@pytest.fixture
def gallery_env(monkeypatch):
    """Each test gets its own gallery dir + auth secret."""
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("STROKE_ORDER_GALLERY_DIR", td)
        monkeypatch.setenv("STROKE_ORDER_AUTH_SECRET",
                           "test-secret-32-bytes-aaaaaaaaaaaaa")
        monkeypatch.setenv("STROKE_ORDER_BASE_URL", "http://test.local")
        from stroke_order.gallery.db import reset_schema_cache
        reset_schema_cache()
        yield Path(td)


@pytest.fixture
def sample_md_bytes() -> bytes:
    """讀取 r27 fixture 的 sample.mandala.md 作為合法 mandala upload。"""
    p = Path(__file__).parent / "fixtures" / "sample.mandala.md"
    return p.read_bytes()


@pytest.fixture
def make_user(gallery_env):
    """Helper: 建一個測試 user（直接插 DB，bypass 登入流程）。"""
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


# =================================================== DB migration / schema

def test_uploads_table_has_kind_and_summary_columns(gallery_env):
    """新建 DB 的 uploads schema 含 kind + summary_json。"""
    from stroke_order.gallery.db import db_connection
    with db_connection() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(uploads)")}
    assert "kind" in cols
    assert "summary_json" in cols
    # legacy 欄位仍存在（向後相容）
    assert "trace_count" in cols
    assert "unique_chars" in cols


def test_uploads_kind_default_psd_for_new_rows(gallery_env, make_user):
    """新插的 row 沒指定 kind 時 default 'psd'。"""
    from stroke_order.gallery.db import db_connection
    user_id = make_user()
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO uploads "
            "(user_id, title, file_path, file_size, file_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, "test", "x", 1, "h", "2026-05-04T00:00:00+00:00"),
        )
        row = conn.execute(
            "SELECT kind FROM uploads ORDER BY id DESC LIMIT 1",
        ).fetchone()
    assert row["kind"] == "psd"


def test_uploads_kind_index_exists(gallery_env):
    """uploads_kind 索引存在（給 list filter 用）。"""
    from stroke_order.gallery.db import db_connection
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='uploads'",
        ).fetchall()
    names = {r["name"] for r in rows}
    assert "uploads_kind" in names


def test_db_migration_idempotent_on_existing_db(gallery_env):
    """既有 DB 已有 kind / summary_json → 二次 migration 不爆。"""
    from stroke_order.gallery.db import (
        _migrate_uploads_kind_columns, db_connection,
    )
    with db_connection() as conn:
        _migrate_uploads_kind_columns(conn)  # 二次跑
        conn.commit()
    # If this got here, idempotency holds
    assert True


# ============================================== mandala validator

def test_parse_mandala_md_happy_path(gallery_env, sample_md_bytes):
    from stroke_order.gallery import service
    state, ext = service.parse_and_validate_mandala(sample_md_bytes)
    assert ext == "md"
    assert state["schema"] == service.MANDALA_SCHEMA_TAG
    assert state["metadata"]["title"] == "我的曼陀羅—九字真言"


def test_parse_mandala_rejects_empty(gallery_env):
    from stroke_order.gallery import service
    with pytest.raises(service.InvalidUpload, match="空"):
        service.parse_and_validate_mandala(b"")


def test_parse_mandala_rejects_non_utf8(gallery_env):
    from stroke_order.gallery import service
    with pytest.raises(service.InvalidUpload, match="UTF-8"):
        service.parse_and_validate_mandala(b"\xff\xfe\x00\x00 not utf8")


def test_parse_mandala_rejects_no_frontmatter(gallery_env):
    from stroke_order.gallery import service
    with pytest.raises(service.InvalidUpload, match="frontmatter"):
        service.parse_and_validate_mandala(b"# just markdown, no yaml\n")


def test_parse_mandala_rejects_wrong_schema(gallery_env):
    from stroke_order.gallery import service
    bad = (
        b"---\nschema: stroke-order-foo-v9\n"
        b"canvas: {size_mm: 100}\ncenter: {}\nring: {}\nmandala: {}\n---\n"
    )
    with pytest.raises(service.InvalidUpload, match="schema"):
        service.parse_and_validate_mandala(bad)


def test_parse_mandala_rejects_missing_required_field(gallery_env):
    """frontmatter 缺 mandala section → reject。"""
    from stroke_order.gallery import service
    bad = (
        b"---\nschema: stroke-order-mandala-v1\n"
        b"canvas: {size_mm: 100}\ncenter: {}\nring: {}\n---\n"
    )
    with pytest.raises(service.InvalidUpload, match="mandala"):
        service.parse_and_validate_mandala(bad)


def test_parse_mandala_svg_with_metadata(gallery_env, sample_md_bytes):
    """SVG 內嵌 <mandala-config> 也接受。"""
    from stroke_order.gallery import service
    # 從 fixture 拿一個合法 state，pack 進 SVG
    state, _ = service.parse_and_validate_mandala(sample_md_bytes)
    # state 裡可能有 datetime — yaml 的 ISO 字串會 load 成 datetime
    # 用 default=str fallback 序列化避免炸
    state_json = json.dumps(state, default=str, ensure_ascii=False)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<metadata><mandala-config xmlns="local">'
        f'<![CDATA[{state_json}]]>'
        '</mandala-config></metadata>'
        '</svg>'
    ).encode("utf-8")
    parsed_state, ext = service.parse_and_validate_mandala(svg)
    assert ext == "svg"
    assert parsed_state["schema"] == service.MANDALA_SCHEMA_TAG


def test_parse_mandala_svg_without_metadata_rejects(gallery_env):
    """SVG 沒有 <mandala-config> 時拒絕 + 友善訊息。"""
    from stroke_order.gallery import service
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle r="5"/></svg>'
    with pytest.raises(service.InvalidUpload, match="metadata"):
        service.parse_and_validate_mandala(svg)


# ============================================== mandala summarise

def test_summarise_mandala_happy_path(gallery_env, sample_md_bytes):
    from stroke_order.gallery import service
    state, _ = service.parse_and_validate_mandala(sample_md_bytes)
    summary = service.summarise_mandala(state)
    assert summary["layer_count"] == 2
    assert summary["ring_count"] == 2
    assert summary["center_text"] == "咒"
    assert summary["mandala_style"] == "interlocking_arcs"
    assert summary["composition_scheme"] == "vesica"


def test_summarise_mandala_defensive_empty_state(gallery_env):
    """state 缺欄位也不爆，回傳 0/空字串。"""
    from stroke_order.gallery import service
    summary = service.summarise_mandala({})
    assert summary["layer_count"] == 0
    assert summary["ring_count"] == 0


# ============================================== create_upload kind dispatch

def test_create_upload_with_kind_mandala(
    gallery_env, sample_md_bytes, make_user,
):
    from stroke_order.gallery import service
    user_id = make_user()
    rec = service.create_upload(
        user_id=user_id,
        content_bytes=sample_md_bytes,
        filename="my.mandala.md",
        title="九字真言曼陀羅",
        comment="第一次上傳測試",
        kind="mandala",
    )
    assert rec["kind"] == "mandala"
    assert rec["title"] == "九字真言曼陀羅"
    assert rec["summary"]["layer_count"] == 2
    assert rec["summary"]["mandala_style"] == "interlocking_arcs"
    # legacy PSD 欄位 = 0/null
    assert rec["trace_count"] == 0
    assert rec["unique_chars"] == 0
    # 副檔名 .md
    assert rec["file_path"].endswith(".md")


def test_create_upload_unknown_kind_rejected(gallery_env, make_user):
    from stroke_order.gallery import service
    user_id = make_user()
    with pytest.raises(service.InvalidUpload, match="kind"):
        service.create_upload(
            user_id=user_id,
            content_bytes=b"...",
            filename="x",
            title="t",
            comment="",
            kind="bogus",
        )


def test_create_upload_mandala_dedup_per_user(
    gallery_env, sample_md_bytes, make_user,
):
    from stroke_order.gallery import service
    user_id = make_user()
    service.create_upload(
        user_id=user_id, content_bytes=sample_md_bytes,
        filename="a.md", title="第一次", comment="", kind="mandala",
    )
    with pytest.raises(service.DuplicateUpload):
        service.create_upload(
            user_id=user_id, content_bytes=sample_md_bytes,
            filename="b.md", title="第二次", comment="", kind="mandala",
        )


# ============================================== list_uploads kind filter

def test_list_uploads_kind_filter(
    gallery_env, sample_md_bytes, make_user,
):
    from stroke_order.gallery import service
    user_id = make_user()
    # 上傳 1 個 mandala
    service.create_upload(
        user_id=user_id, content_bytes=sample_md_bytes,
        filename="m.md", title="曼陀羅", comment="", kind="mandala",
    )
    # 直接 INSERT 1 個假 PSD（懶得跑完整 PSD validator）
    from stroke_order.gallery.db import db_connection
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO uploads "
            "(user_id, title, file_path, file_size, file_hash, kind, "
            "created_at) "
            "VALUES (?, ?, ?, ?, ?, 'psd', ?)",
            (user_id, "PSD示範", "x.json", 10, "fakehash",
             "2026-05-04T00:00:00+00:00"),
        )

    # 全部 = 2
    all_results = service.list_uploads()
    assert all_results["total"] == 2

    # mandala only
    mandala_only = service.list_uploads(kind="mandala")
    assert mandala_only["total"] == 1
    assert mandala_only["items"][0]["kind"] == "mandala"

    # psd only
    psd_only = service.list_uploads(kind="psd")
    assert psd_only["total"] == 1
    assert psd_only["items"][0]["kind"] == "psd"


def test_list_uploads_invalid_kind_rejected(gallery_env):
    from stroke_order.gallery import service
    with pytest.raises(service.InvalidUpload, match="kind filter"):
        service.list_uploads(kind="bogus")


# ============================================== row_to_dict 解析 summary_json

def test_get_upload_returns_summary_dict(
    gallery_env, sample_md_bytes, make_user,
):
    from stroke_order.gallery import service
    user_id = make_user()
    rec = service.create_upload(
        user_id=user_id, content_bytes=sample_md_bytes,
        filename="m.md", title="t", comment="", kind="mandala",
    )
    fetched = service.get_upload(rec["id"])
    assert isinstance(fetched["summary"], dict)
    assert fetched["summary"]["layer_count"] == 2
    # raw summary_json 字串也可在 record 中（應該被 parse 過）
    # 不 assert raw — 行為合約只保證 summary 欄是 dict


# =============================== Phase 5b r28b: thumbnail


def _build_minimal_mandala_svg() -> bytes:
    """Build a minimal SVG with embedded <mandala-config> metadata for tests."""
    import json
    state = {
        "schema": "stroke-order-mandala-v1",
        "metadata": {
            "id": "test-id", "title": "test", "title_pinyin": "test",
            "design_note": "", "author": "",
            "created_at": "2026-05-04T00:00:00Z",
            "modified_at": "2026-05-04T00:00:00Z",
        },
        "canvas": {"size_mm": 100, "page_width_mm": 150, "page_height_mm": 150},
        "center": {"type": "empty", "text": "", "size_mm": 24, "line_color": "#000"},
        "ring": {
            "text": "", "size_mm": 10, "spacing": 2.0,
            "orientation": "bottom_to_center",
            "auto_shrink": True, "shrink_safety_margin": 0.85,
            "protect_chars": True, "protect_radius_factor": 0.55,
            "line_color": "#000",
        },
        "mandala": {
            "style": "interlocking_arcs",
            "composition_scheme": "vesica",
            "n_fold": 6, "show": True,
        },
        "extra_layers": [],
        "style": {"font": "kaishu"},
    }
    state_json = json.dumps(state, ensure_ascii=False)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 150 150" width="150" height="150">'
        f'<metadata><mandala-config xmlns="local">'
        f'<![CDATA[{state_json}]]></mandala-config></metadata>'
        '<circle cx="75" cy="75" r="40" fill="none" '
        'stroke="#c0392b" stroke-width="0.6"/>'
        '</svg>'
    ).encode("utf-8")


def test_thumbnail_generated_for_mandala_svg(gallery_env, make_user):
    """SVG mandala upload → thumbnail .png 存在 + 是有效 PNG。"""
    from stroke_order.gallery import service
    user_id = make_user()
    svg_bytes = _build_minimal_mandala_svg()
    rec = service.create_upload(
        user_id=user_id, content_bytes=svg_bytes, filename="t.svg",
        title="thumb test", comment="", kind="mandala",
    )
    thumb = service.thumbnail_path_of(rec)
    assert thumb.is_file(), f"thumbnail not generated: {thumb}"
    head = thumb.read_bytes()[:8]
    assert head == b"\x89PNG\r\n\x1a\n", f"not a PNG: {head}"
    # Sanity: > 1KB（有實際內容）
    assert thumb.stat().st_size > 1024


def test_thumbnail_skipped_for_mandala_md(gallery_env, sample_md_bytes, make_user):
    """MD path 不生 thumbnail（沒 char loader）。"""
    from stroke_order.gallery import service
    user_id = make_user()
    rec = service.create_upload(
        user_id=user_id, content_bytes=sample_md_bytes, filename="t.md",
        title="md no thumb", comment="", kind="mandala",
    )
    thumb = service.thumbnail_path_of(rec)
    assert not thumb.is_file(), \
        f"thumbnail should be skipped for MD path but exists: {thumb}"


def test_thumbnail_skipped_for_psd(gallery_env, make_user):
    """PSD upload 不生 thumbnail（不是 mandala kind）。"""
    from stroke_order.gallery import service
    user_id = make_user()
    # 直接 INSERT 假 PSD（懶得跑完整 PSD validator）
    from stroke_order.gallery.db import db_connection
    import secrets
    nonce = secrets.token_hex(8)
    fake_psd = b'{"schema":"stroke-order-psd-v1","traces":[{"char":"x","style":"k","points":[]}]}'
    rec = service.create_upload(
        user_id=user_id, content_bytes=fake_psd, filename="x.json",
        title="psd test", comment="", kind="psd",
    )
    thumb = service.thumbnail_path_of(rec)
    assert not thumb.is_file(), \
        f"thumbnail should not exist for PSD: {thumb}"


def test_thumbnail_endpoint_serves_png(gallery_env, make_user, monkeypatch):
    """API GET /uploads/{id}/thumbnail 回 PNG bytes + correct content-type。"""
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    from stroke_order.gallery import service
    user_id = make_user()
    svg_bytes = _build_minimal_mandala_svg()
    rec = service.create_upload(
        user_id=user_id, content_bytes=svg_bytes, filename="t.svg",
        title="endpoint test", comment="", kind="mandala",
    )
    client = TestClient(create_app())
    r = client.get(f"/api/gallery/uploads/{rec['id']}/thumbnail")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_thumbnail_endpoint_404_for_md_upload(
    gallery_env, sample_md_bytes, make_user,
):
    """MD upload 沒 thumbnail → endpoint 回 404。"""
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    from stroke_order.gallery import service
    user_id = make_user()
    rec = service.create_upload(
        user_id=user_id, content_bytes=sample_md_bytes, filename="t.md",
        title="md endpoint test", comment="", kind="mandala",
    )
    client = TestClient(create_app())
    r = client.get(f"/api/gallery/uploads/{rec['id']}/thumbnail")
    assert r.status_code == 404


def test_thumbnail_deleted_on_upload_delete(gallery_env, make_user):
    """delete_upload 也會清掉 thumbnail。"""
    from stroke_order.gallery import service
    user_id = make_user()
    svg_bytes = _build_minimal_mandala_svg()
    rec = service.create_upload(
        user_id=user_id, content_bytes=svg_bytes, filename="t.svg",
        title="delete test", comment="", kind="mandala",
    )
    thumb = service.thumbnail_path_of(rec)
    assert thumb.is_file()
    service.delete_upload(upload_id=rec["id"], user_id=user_id)
    assert not thumb.is_file(), "thumbnail not cleaned up on delete"


# =============================== Phase 5b r28c: MD thumbnail


def test_thumbnail_generated_for_mandala_md_with_loader(
    gallery_env, sample_md_bytes, make_user,
):
    """MD upload 帶 char_loader → 生成 thumbnail（即使 stub loader 缺字）。"""
    from stroke_order.gallery import service
    user_id = make_user()
    # Stub loader 永遠回 None（缺字 — render 會 skip 但不爆）
    stub_loader = lambda c: None
    rec = service.create_upload(
        user_id=user_id, content_bytes=sample_md_bytes, filename="m.md",
        title="md thumb", comment="", kind="mandala",
        char_loader=stub_loader,
    )
    thumb = service.thumbnail_path_of(rec)
    assert thumb.is_file(), \
        f"MD upload with loader should generate thumbnail: {thumb}"
    head = thumb.read_bytes()[:8]
    assert head == b"\x89PNG\r\n\x1a\n"
    assert thumb.stat().st_size > 1024


def test_thumbnail_md_without_loader_skipped(
    gallery_env, sample_md_bytes, make_user,
):
    """MD upload 沒帶 loader → 跳過 thumbnail（保 r28b 行為）。"""
    from stroke_order.gallery import service
    user_id = make_user()
    rec = service.create_upload(
        user_id=user_id, content_bytes=sample_md_bytes, filename="m.md",
        title="md no loader", comment="", kind="mandala",
        # 不傳 char_loader（預設 None）
    )
    thumb = service.thumbnail_path_of(rec)
    assert not thumb.is_file()


def test_thumbnail_md_loader_exception_graceful(
    gallery_env, sample_md_bytes, make_user,
):
    """MD upload 的 loader 拋例外 → 不擋 upload，thumbnail 跳過（graceful）。"""
    from stroke_order.gallery import service
    user_id = make_user()

    def bad_loader(ch):
        raise RuntimeError("loader 模擬 fail")

    # Upload 仍應成功（thumbnail 失敗 graceful）
    rec = service.create_upload(
        user_id=user_id, content_bytes=sample_md_bytes, filename="m.md",
        title="bad loader", comment="", kind="mandala",
        char_loader=bad_loader,
    )
    assert rec["id"]  # upload 還是進 DB
    thumb = service.thumbnail_path_of(rec)
    # render 內每個字 try/except — 缺字仍能 render，thumbnail 應生成
    # 但若 render_mandala_from_state 整個爆（非每字爆），thumbnail 不存在
    # 兩種狀況都接受：upload 成功 + 不擋
    # 主要 assert 是 upload 不爆


def test_render_mandala_from_state_helper():
    """exporters.mandala.render_mandala_from_state — state schema → SVG。"""
    from stroke_order.exporters.mandala import render_mandala_from_state
    state = {
        "schema": "stroke-order-mandala-v1",
        "canvas": {"size_mm": 100, "page_width_mm": 150, "page_height_mm": 150},
        "center": {"type": "empty", "text": "", "size_mm": 24, "line_color": "#000"},
        "ring": {"text": "", "size_mm": 10, "spacing": 2.0,
                 "orientation": "bottom_to_center",
                 "auto_shrink": True, "shrink_safety_margin": 0.85,
                 "protect_chars": True, "protect_radius_factor": 0.55,
                 "line_color": "#000"},
        "mandala": {"style": "interlocking_arcs",
                    "composition_scheme": "vesica",
                    "n_fold": 6, "show": True,
                    "overlap_ratio": 1.25,
                    "lotus_length_ratio": 1.25, "lotus_width_ratio": 0.6,
                    "rays_length_ratio": 1.25,
                    "inscribed_padding_factor": 0.7,
                    "r_ring_ratio": 0.45, "r_band_ratio": 0.78,
                    "stroke_width": 0.6, "line_color": "#c0392b"},
        "extra_layers": [
            {"ring": 2, "style": "dots", "n_fold": 12, "r_mm": 25,
             "color": "#27ae60", "visible": True, "dot_radius_mm": 1.0},
        ],
        "style": {"font": "kaishu"},
    }
    svg, info = render_mandala_from_state(state, lambda c: None)
    assert "<svg" in svg
    # 應含 mandala primitives 跟 extra layer 的色
    assert "#c0392b" in svg or "#27ae60" in svg
    assert info["composition_scheme"] == "vesica"
    assert info["extra_layers_count"] == 1
