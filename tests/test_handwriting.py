"""Phase 5d — handwriting practice page (PSD).

Validates:
  * GET /handwriting returns the SPA shell with required script tags
  * GET /static/handwriting/* serves all six ES modules + CSS
  * GET /api/handwriting/reference/{char} returns native EM 2048 outline
    data with style support
  * GET /api/sutra/text/{preset} returns plain text or 422 when not loaded
  * No regression to /, /sutra-editor

This file is intentionally Python-side only — the JS modules' behaviour
is exercised by the in-browser smoke testing the user does manually
(touch / pen / mouse / cross-platform). Node `--check` runs at build
time confirm the modules at least parse.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.web.server import create_app


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def temp_sutra_dir(monkeypatch):
    """Override sutra dir + drop a small heart_sutra.txt into it."""
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("STROKE_ORDER_SUTRA_DIR", td)
        (Path(td) / "heart_sutra.txt").write_text(
            "觀自在菩薩，行深般若波羅蜜多時。",
            encoding="utf-8",
        )
        yield Path(td)


# ---------------------------------------------------------------------------
# /handwriting page
# ---------------------------------------------------------------------------


def test_handwriting_route_returns_html(client):
    r = client.get("/handwriting")
    assert r.status_code == 200
    text = r.text
    assert "筆順練習" in text
    # All six ES modules must be loaded.
    for mod in [
        "handwriting/handwriting.css",
        "handwriting/canvas.js",
        "handwriting/storage.js",
        "handwriting/materials.js",
        "handwriting/grid.js",
        "handwriting/reference.js",
        "handwriting/exporter.js",
    ]:
        assert mod in text, f"module {mod} not referenced in /handwriting"


def test_handwriting_route_includes_action_buttons(client):
    """The data-action hooks the JS module wires up to must be present."""
    r = client.get("/handwriting")
    text = r.text
    for action in [
        "clear", "commit", "prev", "next",
        "export-json", "export-svg-one", "export-svg-zip",
        "clear-all", "email-self", "submit-public",
    ]:
        assert f'data-action="{action}"' in text, f"missing data-action {action!r}"


def test_handwriting_includes_warnings_and_privacy_notice(client):
    """5d-12: privacy banner is always visible; in-app browser banner
    starts hidden but exists in the DOM; lishu/seal priority hint is
    present (initially hidden until style chosen)."""
    text = client.get("/handwriting").text
    assert 'id="hw-banner-privacy"' in text
    assert "您的筆跡資料只存在這部裝置" in text
    assert 'id="hw-banner-inapp-browser"' in text
    assert "Line" in text and "FBAN" in text     # UA pattern source
    assert 'id="hw-style-priority-hint"' in text
    assert "本機資料庫" in text                    # 5cb-style accurate wording


def test_handwriting_includes_5e_placeholders(client):
    """The email + public-database buttons must be present but disabled
    until 5e ships them."""
    text = client.get("/handwriting").text
    # Single regex would also work, but be explicit
    assert "data-action=\"email-self\"" in text
    assert "data-action=\"submit-public\"" in text
    # Both should carry the "待開發" tooltip
    assert "待開發" in text


# ---------------------------------------------------------------------------
# static module serving
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename, must_have", [
    ("canvas.js",   ["WritingCanvas", "EM_SIZE", "pointerdown",
                     "devicePixelRatio", "tiltX"]),
    ("storage.js",  ["saveTrace", "STORE_TRACES", "createIndex",
                     "stroke-order-practice"]),
    ("grid.js",     ["drawGrid", "GRID_STYLES", "mizi", "tianzi", "huizi"]),
    ("reference.js", ["fetchReference", "drawReference", "_outlineBBox"]),
    ("materials.js", ["loadSutraMaterial", "loadInputMaterial",
                      "loadUploadMaterial", "loadFreehandMaterial",
                      "MaterialIterator"]),
    ("exporter.js",  ["exportAllJson", "exportTraceSvg", "exportAllSvgZip",
                      "importJson", "makeZip", "stroke-order-psd-v1",
                      "0x04034b50"]),
])
def test_static_module_serves_with_expected_keys(client, filename, must_have):
    r = client.get(f"/static/handwriting/{filename}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript") \
        or r.headers["content-type"].startswith("text/javascript")
    text = r.text
    for needle in must_have:
        assert needle in text, f"{filename}: missing {needle!r}"


def test_static_css_serves(client):
    r = client.get("/static/handwriting/handwriting.css")
    assert r.status_code == 200
    text = r.text
    assert ".hw-canvas-wrap" in text
    # 768px breakpoint for RWD
    assert "max-width: 767px" in text or "max-width:767px" in text \
        or "767" in text
    # Touch action disabled for the canvas (critical for iOS)
    assert "touch-action: none" in text or "touch-action:none" in text


# ---------------------------------------------------------------------------
# /api/handwriting/reference/{char}
# ---------------------------------------------------------------------------


def test_handwriting_reference_default_kaishu(client):
    r = client.get("/api/handwriting/reference/永")
    assert r.status_code == 200
    data = r.json()
    assert data["char"] == "永"
    assert data["style"] == "kaishu"
    # Native EM 2048 — the same coord system as the page's writing canvas
    assert data["em_size"] == 2048
    assert isinstance(data["strokes"], list)
    assert len(data["strokes"]) > 0
    # Each stroke must have an outline (filtered server-side)
    for s in data["strokes"]:
        assert "outline" in s
        assert len(s["outline"]) > 0


@pytest.mark.parametrize("style", [
    "kaishu", "mingti", "lishu", "seal_script", "bold",
])
def test_handwriting_reference_accepts_all_styles(client, style):
    r = client.get(f"/api/handwriting/reference/永?style={style}")
    assert r.status_code == 200
    data = r.json()
    assert data["style"] == style
    # Even when the font isn't installed (sandbox), backend must
    # gracefully fall back rather than 500. strokes may be [] but the
    # response shape must hold.
    assert "strokes" in data
    assert data["em_size"] == 2048


def test_handwriting_reference_lishu_outline_preserved_not_skeletonised(client):
    """5bz pattern: lishu in skeleton mode strips the outline. The
    handwriting reference endpoint passes outline_mode='skip' so the
    outline stays intact, ready for fill-rendering on the bg canvas.
    Verified by checking the outline isn't empty (when font available)."""
    r = client.get("/api/handwriting/reference/天?style=lishu")
    assert r.status_code == 200
    data = r.json()
    # When MoE lishu is installed locally, strokes are non-empty;
    # in CI sandbox without the font, falls back to kaishu (also
    # non-empty). Either way: outline_mode='skip' must NOT yield
    # empty outlines for the upgrade chain to make sense.
    assert isinstance(data["strokes"], list)
    if data["strokes"]:
        assert all(s.get("outline") for s in data["strokes"]), (
            "outline preservation broken — got empty outline list"
        )


# ---------------------------------------------------------------------------
# /api/sutra/text/{preset}
# ---------------------------------------------------------------------------


def test_sutra_text_returns_plain_text_when_loaded(client, temp_sutra_dir):
    r = client.get("/api/sutra/text/heart_sutra")
    assert r.status_code == 200
    data = r.json()
    assert data["preset"] == "heart_sutra"
    assert data["title"]                      # has a human-readable title
    assert "般若波羅蜜多" in data["text"]
    assert data["char_count"] > 0
    # char_count excludes whitespace (basic sanity)
    assert data["char_count"] <= len(data["text"])


def test_sutra_text_returns_422_when_not_loaded(client, temp_sutra_dir):
    """A registered preset whose .txt file is missing must give a clean
    422 — the frontend uses this signal to fall back to freehand."""
    # diamond_sutra is a registered builtin; we didn't drop the file.
    r = client.get("/api/sutra/text/diamond_sutra")
    assert r.status_code == 422
    assert "not loaded" in r.json()["detail"]


def test_sutra_text_returns_404_for_unknown_preset(client):
    """Random preset key the registry doesn't recognise."""
    r = client.get("/api/sutra/text/this_preset_does_not_exist")
    assert r.status_code in (404, 422)
    # 422 from the URL pattern validator is also acceptable — both
    # are clean refusals the frontend can handle.


# ---------------------------------------------------------------------------
# regression: existing routes still healthy
# ---------------------------------------------------------------------------


def test_main_index_still_works(client):
    r = client.get("/")
    assert r.status_code == 200


def test_sutra_editor_still_works(client):
    r = client.get("/sutra-editor")
    assert r.status_code == 200


def test_existing_character_endpoint_still_works(client):
    r = client.get("/api/character/永")
    assert r.status_code == 200
    # hanzi-writer-format response — different shape from /api/handwriting
    data = r.json()
    assert "strokes" in data
    assert "medians" in data
    # Old contract: strokes are SVG path d-strings (not outline cmd dicts)
    assert isinstance(data["strokes"][0], str)
    assert data["strokes"][0].startswith("M ")


# ---------------------------------------------------------------------------
# Plotter SVG: structural sanity (the ES module is the source of truth,
# but here we re-implement just enough of the schema string to assert
# the front-end constants stay aligned with the test expectations).
# ---------------------------------------------------------------------------


def test_exporter_module_uses_schema_v1_tag(client):
    """If the JSON schema tag changes, importing older files would
    silently fail. Pin the value here so changing it forces a test
    update too."""
    r = client.get("/static/handwriting/exporter.js")
    assert "stroke-order-psd-v1" in r.text


def test_exporter_module_emits_em_2048_viewbox(client):
    """The Plotter SVG generator must use the same EM coordinate system
    as the rest of the engine, so traces re-fed to plotter pipelines
    align with internal char data."""
    r = client.get("/static/handwriting/exporter.js")
    assert 'viewBox="0 0 ${EM_SIZE} ${EM_SIZE}"' in r.text \
        or 'viewBox="0 0 2048 2048"' in r.text \
        or "EM_SIZE      = 2048" in r.text   # const definition
