"""5ft: gallery 接立體字（popup）upload — schema + service + API tests。

比照 test_gallery_mandala.py 的 fixture 慣例；popup SVG 以合成內容
測（不依賴思源黑體字型——沙箱/CI 未裝也能驗）。
"""

from __future__ import annotations

import io
import json
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


def _popup_svg_bytes(upper="新年", lower="快樂") -> bytes:
    cfg = json.dumps({
        "schema": "stroke-order-popup-v1",
        "upper": upper, "lower": lower,
        "card_w_mm": 148.0, "card_h_mm": 105.0,
        "char_h_mm": 30.0, "roof_mm": 12.0,
        "tread_mm": 12.0, "cell_w_mm": 34.0,
        "components": 5, "bridges": 3, "tiers": 2,
    }, ensure_ascii=False)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f"<metadata><popup-config><![CDATA[{cfg}]]></popup-config></metadata>"
        "<rect x='1' y='1' width='98' height='98'/></svg>"
    ).encode("utf-8")


# ------------------------------------------------- validator

def test_parse_popup_happy_path(gallery_env):
    from stroke_order.gallery.service import parse_and_validate_popup
    state, ext = parse_and_validate_popup(_popup_svg_bytes())
    assert ext == "svg"
    assert state["upper"] == "新年"
    assert state["tiers"] == 2


def test_parse_popup_rejects_no_metadata(gallery_env):
    from stroke_order.gallery.service import (
        InvalidUpload, parse_and_validate_popup)
    with pytest.raises(InvalidUpload, match="popup-config"):
        parse_and_validate_popup(b"<svg xmlns='x'><rect/></svg>")


def test_parse_popup_rejects_non_svg(gallery_env):
    from stroke_order.gallery.service import (
        InvalidUpload, parse_and_validate_popup)
    with pytest.raises(InvalidUpload, match="SVG"):
        parse_and_validate_popup(b'{"schema": "stroke-order-popup-v1"}')


def test_parse_popup_rejects_wrong_schema(gallery_env):
    from stroke_order.gallery.service import (
        InvalidUpload, parse_and_validate_popup)
    bad = _popup_svg_bytes().replace(b"popup-v1", b"popup-v9")
    with pytest.raises(InvalidUpload, match="schema"):
        parse_and_validate_popup(bad)


def test_summarise_popup(gallery_env):
    from stroke_order.gallery.service import summarise_popup
    s = summarise_popup({"upper": "新年", "lower": "快樂",
                         "card_w_mm": 148.0, "card_h_mm": 105.0, "tiers": 2})
    assert s["upper_text"] == "新年"
    assert s["char_count"] == 4
    assert s["tiers"] == 2


# ------------------------------------------------- service create/list

def test_create_upload_popup_kind(gallery_env, make_user):
    from stroke_order.gallery import service
    uid = make_user()
    rec = service.create_upload(
        user_id=uid, content_bytes=_popup_svg_bytes(),
        filename="popup.svg", title="賀年立體字", comment="",
        kind="popup",
    )
    assert rec["kind"] == "popup"
    assert rec["summary"]["upper_text"] == "新年"
    assert str(rec["file_path"]).endswith(".svg")


def test_list_filter_kind_popup(gallery_env, make_user, established_authors):
    from stroke_order.gallery import service
    uid = make_user()
    service.create_upload(
        user_id=uid, content_bytes=_popup_svg_bytes("福", ""),
        filename="p.svg", title="立體福", comment="", kind="popup")
    out = service.list_uploads(page=1, size=10, kind="popup")
    assert out["total"] == 1
    assert out["items"][0]["kind"] == "popup"
    out2 = service.list_uploads(page=1, size=10, kind="psd")
    assert out2["total"] == 0


# ------------------------------------------------- API 端到端（含嵌入）

def test_popup_svg_endpoint_embeds_metadata(client, monkeypatch):
    """/api/popup/svg 產出的 SVG 內嵌 <popup-config>（5ft）——
    monkeypatch generate_popup，不依賴思源黑體。"""
    import stroke_order.exporters.popup as popup_mod

    class _R:
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>'
        width_mm, height_mm = 148.0, 105.0
        components, bridges, tiers = 4, 2, 1

    monkeypatch.setattr(popup_mod, "generate_popup", lambda *a, **k: _R())
    r = client.post("/api/popup/svg", json={
        "upper": "測試", "lower": "",
        "card_w_mm": 148, "card_h_mm": 105, "char_h_mm": 30,
        "roof_mm": 12, "tread_mm": 12, "cell_w_mm": 34,
    })
    assert r.status_code == 200, r.text
    svg = r.json()["svg"]
    assert "<popup-config>" in svg
    assert "stroke-order-popup-v1" in svg
    # metadata 在 <svg> 開標籤之後（非 xml 宣告前）
    assert svg.index("<svg") < svg.index("<popup-config>")
    # round-trip：這份 SVG 直接能過 gallery validator
    from stroke_order.gallery.service import parse_and_validate_popup
    state, ext = parse_and_validate_popup(svg.encode("utf-8"))
    assert state["upper"] == "測試" and ext == "svg"
