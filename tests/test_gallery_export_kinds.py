"""5fw: gallery 接「模式匯出 SVG」12 分類（統一出口信封收件側）。

供給側（5fv）產的信封在此驗收件：認信封→kind=mode、危險構件拒收、
registry 派遣零 API 改動。fixture 比照 test_gallery_popup.py。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from stroke_order.exporters.envelope import embed_export_envelope


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


_BASE_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 50">'
             "<rect x='1' y='1' width='48' height='48'/></svg>")


def _export_svg_bytes(mode: str, app_version: str = "0.14.272") -> bytes:
    return embed_export_envelope(
        _BASE_SVG, mode=mode, app_version=app_version).encode("utf-8")


# ------------------------------------------------- registry / constants

def test_export_kinds_registered(gallery_env):
    from stroke_order.gallery import service
    assert len(service.EXPORT_MODE_KINDS) == 12
    for k in service.EXPORT_MODE_KINDS:
        assert k in service.ALLOWED_KINDS
        assert k in service.VALIDATORS
        assert k in service.SUMMARIZERS
    # 既有三類不受影響
    for k in ("psd", "mandala", "popup"):
        assert k in service.ALLOWED_KINDS


def test_frontend_kind_lists_match_backend(gallery_env):
    """前端 hash.mjs EXPORT_KINDS 與後端 EXPORT_MODE_KINDS 同表
    （單一事實源各半，靠這鎖同步）。"""
    from stroke_order.gallery import service
    mjs = Path("src/stroke_order/web/static/gallery/hash.mjs").read_text(
        encoding="utf-8")
    for k in service.EXPORT_MODE_KINDS:
        assert f"'{k}'" in mjs, f"hash.mjs 缺 kind {k!r}"


# ------------------------------------------------- validator

def test_validator_happy_path_each_mode(gallery_env):
    from stroke_order.gallery import service
    for mode in service.EXPORT_MODE_KINDS:
        state, ext = service.parse_and_validate_export_svg(
            _export_svg_bytes(mode), expected_mode=mode)
        assert ext == "svg"
        assert state["mode"] == mode


def test_validator_rejects_no_envelope(gallery_env):
    from stroke_order.gallery.service import (
        InvalidUpload, parse_and_validate_export_svg)
    with pytest.raises(InvalidUpload, match="憑據"):
        parse_and_validate_export_svg(
            _BASE_SVG.encode(), expected_mode="grid")


def test_validator_rejects_non_svg(gallery_env):
    from stroke_order.gallery.service import (
        InvalidUpload, parse_and_validate_export_svg)
    with pytest.raises(InvalidUpload, match="SVG"):
        parse_and_validate_export_svg(b'{"mode": "grid"}',
                                      expected_mode="grid")


def test_validator_rejects_mode_mismatch(gallery_env):
    """放錯類不可能：檔案聲明 grid、分類選 stamp → 拒收。"""
    from stroke_order.gallery.service import (
        InvalidUpload, parse_and_validate_export_svg)
    with pytest.raises(InvalidUpload, match="不符"):
        parse_and_validate_export_svg(
            _export_svg_bytes("grid"), expected_mode="stamp")


def test_validator_rejects_wrong_schema(gallery_env):
    from stroke_order.gallery.service import (
        InvalidUpload, parse_and_validate_export_svg)
    bad = _export_svg_bytes("grid").replace(b"export-v1", b"export-v9")
    with pytest.raises(InvalidUpload, match="schema"):
        parse_and_validate_export_svg(bad, expected_mode="grid")


@pytest.mark.parametrize("payload,label", [
    ("<script>alert(1)</script>", "script"),
    ("<foreignObject><body/></foreignObject>", "foreignObject"),
    ('<rect onload="alert(1)"/>', "事件屬性"),
    ('<a href="https://evil.example/x">x</a>', "href"),
    ('<rect style="fill:url(http://evil.example/f)"/>', "url"),
    ('<use x="1"/>', "use"),
    ('<image x="1"/>', "image"),
    ('<style>rect{}</style>', "style"),
])
def test_validator_rejects_dangerous_constructs(gallery_env, payload, label):
    """XSS 縱深防禦：本站匯出器從不產生的構件一律拒收。"""
    from stroke_order.gallery.service import (
        InvalidUpload, parse_and_validate_export_svg)
    svg = _export_svg_bytes("grid").decode("utf-8").replace(
        "<rect x='1' y='1' width='48' height='48'/>", payload)
    with pytest.raises(InvalidUpload, match="不允許"):
        parse_and_validate_export_svg(svg.encode(), expected_mode="grid")


def test_validator_allows_internal_clip_url(gallery_env):
    """布章合法輸出含 clip-path="url(#id)" 內部參照——必須放行。"""
    from stroke_order.gallery.service import parse_and_validate_export_svg
    svg = _export_svg_bytes("patch").decode("utf-8").replace(
        "<rect x='1' y='1' width='48' height='48'/>",
        '<g clip-path="url(#c1)"><rect width="4" height="4"/></g>'
        '<clipPath id="c1"><rect width="9" height="9"/></clipPath>')
    state, ext = parse_and_validate_export_svg(
        svg.encode(), expected_mode="patch")
    assert state["mode"] == "patch"


def test_summarise_export_svg(gallery_env):
    from stroke_order.gallery.service import summarise_export_svg
    s = summarise_export_svg({"mode": "zentangle", "app_version": "1.2.3"})
    assert s == {"mode": "zentangle", "app_version": "1.2.3"}


# ------------------------------------------------- service create/list

def test_create_upload_export_kind(gallery_env, make_user):
    from stroke_order.gallery import service
    uid = make_user()
    rec = service.create_upload(
        user_id=uid, content_bytes=_export_svg_bytes("zentangle"),
        filename="zt.svg", title="禪繞永字", comment="",
        kind="zentangle",
    )
    assert rec["kind"] == "zentangle"
    assert rec["summary"]["mode"] == "zentangle"
    assert rec["summary"]["app_version"] == "0.14.272"
    assert str(rec["file_path"]).endswith(".svg")


def test_create_upload_generates_thumbnail(gallery_env, make_user):
    from stroke_order.gallery import service
    uid = make_user()
    rec = service.create_upload(
        user_id=uid, content_bytes=_export_svg_bytes("grid"),
        filename="g.svg", title="字帖", comment="", kind="grid")
    thumb = service.thumbnail_path_of(rec)
    assert thumb.is_file(), "5fw：匯出 SVG 分類應有伺服器縮圖"


def test_list_filter_by_export_kind(gallery_env, make_user):
    from stroke_order.gallery import service
    uid = make_user()
    service.create_upload(
        user_id=uid, content_bytes=_export_svg_bytes("stamp"),
        filename="s.svg", title="印章", comment="", kind="stamp")
    service.create_upload(
        user_id=uid, content_bytes=_export_svg_bytes("wordart"),
        filename="w.svg", title="文字雲", comment="", kind="wordart")
    out = service.list_uploads(page=1, size=10, kind="stamp")
    assert out["total"] == 1 and out["items"][0]["kind"] == "stamp"
    out_all = service.list_uploads(page=1, size=10)
    assert out_all["total"] == 2


# ------------------------------------------------- round-trip（5fv→5fw）

def test_real_endpoint_svg_uploads_ok(client, gallery_env, make_user):
    """端到端：真實 /api/grid 產物（帶信封）直接過 grid 分類驗證。"""
    from stroke_order.gallery import service
    r = client.get("/api/grid?chars=永&cols=3")
    assert r.status_code == 200
    uid = make_user()
    rec = service.create_upload(
        user_id=uid, content_bytes=r.content,
        filename="grid.svg", title="永字帖", comment="", kind="grid")
    assert rec["kind"] == "grid"


# ------------------------------------------------- 前端 UI 契約

def test_gallery_page_kind_dropdown(client):
    gl = client.get("/gallery").text
    assert 'id="gl-kind"' in gl
    for group in ("書寫練習", "製造切割", "藝術創作", "筆順練習"):
        assert f'label="{group}"' in gl
    for kind in ("single", "grid", "manuscript", "notebook", "letter",
                 "sutra", "doodle", "patch", "stamp", "stencil",
                 "wordart", "zentangle", "mandala", "popup", "psd"):
        assert f'value="{kind}"' in gl
    # 舊 kind tabs 已移除（僅剩 全部/我的收藏 兩個 tab）
    assert 'data-kind="psd"' not in gl.split('id="gl-kind"')[0].split(
        "gl-filter-tabs")[-1]


def test_uploader_detects_export_svg(client):
    up = client.get("/static/gallery/uploader.js").text
    assert "stroke-order-export-v1" in up
    assert "export-svg" in up
    hjs = client.get("/static/gallery/hash.mjs").text
    assert "EXPORT_KINDS" in hjs
    assert "zentangle: '禪繞字'" in hjs
