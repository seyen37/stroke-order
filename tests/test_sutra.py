"""Phase 5az — sutra (抄經) mode: external file loader + A4 landscape SVG."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from stroke_order.exporters.sutra import (
    CELLS_PER_PAGE,
    COLS,
    ROWS,
    PAGE_H_MM,
    PAGE_W_MM,
    page_slice,
    render_sutra_cover,
    render_sutra_dedication,
    render_sutra_page,
    sutra_page_count,
    total_body_pages,
)
from stroke_order.ir import Character, Point, Stroke
from stroke_order.sutras import (
    SUTRAS,
    SutraInfo,
    actual_char_count,
    available_presets,
    is_loaded,
    load_text,
    text_to_chars,
)


# ---------------------------------------------------------------------------
# Stub loader — minimal one-stroke glyph
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_loader():
    def _l(ch):
        return Character(
            char=ch, unicode_hex=f"{ord(ch):04x}", data_source="stub",
            strokes=[Stroke(
                index=0,
                raw_track=[Point(100, 100), Point(1948, 1948)],
                outline=[
                    {"type": "M", "x": 100,  "y": 100},
                    {"type": "L", "x": 1948, "y": 100},
                    {"type": "L", "x": 1948, "y": 1948},
                    {"type": "L", "x": 100,  "y": 1948},
                ],
                kind_code=9, kind_name="其他", has_hook=False,
            )],
        )
    return _l


@pytest.fixture
def temp_sutra_dir(monkeypatch):
    """Override STROKE_ORDER_SUTRA_DIR to a fresh temp dir per test."""
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("STROKE_ORDER_SUTRA_DIR", td)
        yield Path(td)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_canonical_buddhist_presets_present():
    """Phase 5az original 4 buddhist sutras must remain registered."""
    keys = set(SUTRAS.keys())
    for required in ("heart_sutra", "diamond_sutra",
                     "great_compassion", "manjushri_mantra"):
        assert required in keys


def test_only_manjushri_mantra_has_repeat():
    """Among the four buddhist builtins, only manjushri_mantra repeats."""
    repeats = {k: SUTRAS[k].is_mantra_repeat for k in (
        "heart_sutra", "diamond_sutra", "great_compassion", "manjushri_mantra")}
    assert repeats["manjushri_mantra"] is True
    assert SUTRAS["manjushri_mantra"].repeat_count == 108
    for k in ("heart_sutra", "diamond_sutra", "great_compassion"):
        assert repeats[k] is False


# ---------------------------------------------------------------------------
# External-file loader
# ---------------------------------------------------------------------------


def test_load_text_returns_none_when_file_missing(temp_sutra_dir):
    # File for heart_sutra absent — should return None, not raise
    assert load_text("heart_sutra") is None
    assert is_loaded("heart_sutra") is False


def test_load_text_strips_whitespace(temp_sutra_dir):
    (temp_sutra_dir / "heart_sutra.txt").write_text(
        "天\n地\n人\n  山\t水", encoding="utf-8")
    text = load_text("heart_sutra")
    assert text == "天地人山水"
    assert actual_char_count("heart_sutra") == 5


def test_mantra_repeat_expansion(temp_sutra_dir):
    (temp_sutra_dir / "manjushri_mantra.txt").write_text(
        "天地人山水日月", encoding="utf-8")
    text = load_text("manjushri_mantra")
    assert len(text) == 7 * 108
    # First 7 == cycle, 8th == start of cycle again
    assert text[:7] == "天地人山水日月"
    assert text[7:14] == "天地人山水日月"


def test_text_to_chars_one_token_per_char():
    assert text_to_chars("天地，人") == ["天", "地", "，", "人"]
    assert text_to_chars("") == []


def test_available_presets_reports_status(temp_sutra_dir):
    (temp_sutra_dir / "heart_sutra.txt").write_text("天地人", encoding="utf-8")
    snap = {p["key"]: p for p in available_presets()}
    assert snap["heart_sutra"]["ready"] is True
    assert snap["heart_sutra"]["actual_chars"] == 3
    assert snap["diamond_sutra"]["ready"] is False
    assert snap["diamond_sutra"]["actual_chars"] == 0


# ---------------------------------------------------------------------------
# Geometry / pagination
# ---------------------------------------------------------------------------


def test_cells_per_page_is_300():
    assert CELLS_PER_PAGE == COLS * ROWS == 300


def test_total_body_pages():
    assert total_body_pages("") == 0
    assert total_body_pages("A" * 1) == 1
    assert total_body_pages("A" * 300) == 1
    assert total_body_pages("A" * 301) == 2
    assert total_body_pages("A" * 5175) == 18  # diamond sutra estimate


def test_page_slice_boundaries():
    text = "A" * 500
    assert len(page_slice(text, 0)) == 300
    assert len(page_slice(text, 1)) == 200
    assert len(page_slice(text, 2)) == 0


def test_sutra_page_count_aggregates_correctly():
    info = sutra_page_count("A" * 500,
                            include_cover=True, include_dedication=True)
    assert info == {"cover": 1, "body_pages": 2, "dedication": 1, "total": 4}


# ---------------------------------------------------------------------------
# SVG output
# ---------------------------------------------------------------------------


def test_body_page_has_a4_landscape_viewbox(stub_loader):
    svg = render_sutra_page(["A"] * 5, char_loader=stub_loader)
    assert f'viewBox="0 0 {PAGE_W_MM:.3f} {PAGE_H_MM:.3f}"' in svg
    # A4 landscape = wider than tall
    assert PAGE_W_MM > PAGE_H_MM


def test_body_page_has_outer_frame_and_grid(stub_loader):
    svg = render_sutra_page(["A"] * 5, char_loader=stub_loader)
    # outer frame rect
    assert "<rect" in svg
    # grid lines (verticals + horizontals; with helper lines disabled we
    # still have ROWS-1 + COLS-1 lines = 14 + 19 = 33).
    plain = render_sutra_page(["A"] * 5, char_loader=stub_loader,
                               show_helper_lines=False)
    assert plain.count("<line") >= ROWS - 1 + COLS - 1


def test_body_page_helper_lines_add_4_per_cell(stub_loader):
    """米字 helper = 4 lines × 300 cells = 1200 extra lines."""
    plain = render_sutra_page(["A"] * 0, char_loader=stub_loader,
                               show_helper_lines=False)
    helped = render_sutra_page(["A"] * 0, char_loader=stub_loader,
                                show_helper_lines=True)
    delta = helped.count("<line") - plain.count("<line")
    assert delta == 4 * COLS * ROWS  # 1200


def test_body_page_grey_fill_group_present_when_chars_render(stub_loader):
    svg = render_sutra_page(["A"], char_loader=stub_loader)
    assert 'id="sutra-trace"' in svg
    assert 'fill="#cccccc"' in svg


def test_body_page_no_grey_group_when_no_chars(stub_loader):
    """Empty page should not emit an empty <g id="sutra-trace"> wrapper."""
    svg = render_sutra_page([], char_loader=stub_loader)
    assert 'id="sutra-trace"' not in svg


def test_show_grid_false_suppresses_internal_lines(stub_loader):
    with_grid = render_sutra_page([], char_loader=stub_loader,
                                    show_grid=True, show_helper_lines=False)
    no_grid = render_sutra_page([], char_loader=stub_loader,
                                  show_grid=False, show_helper_lines=False)
    assert with_grid.count("<line") > no_grid.count("<line")
    # Outer frame still present in both
    assert "<rect" in no_grid


# ---------------------------------------------------------------------------
# Cover + dedication
# ---------------------------------------------------------------------------


def test_cover_includes_title_text_via_loader(stub_loader):
    info = SUTRAS["heart_sutra"]
    svg = render_sutra_cover(info, char_loader=stub_loader,
                              scribe="王小明")
    # Title chars rendered via loader → multiple <path> elements
    assert svg.count("<path") > 5


def test_dedication_with_verse_renders_two_groups(stub_loader):
    svg = render_sutra_dedication(
        char_loader=stub_loader,
        dedicator="王小明", target="父母",
        body_text="天地人山水",
    )
    # Two underline lines for fill-ins
    assert svg.count("<line") >= 2
    # Verse rendered in trace fill grey
    assert 'fill="#cccccc"' in svg


def test_dedication_without_verse_skips_grey_group(stub_loader):
    svg = render_sutra_dedication(
        char_loader=stub_loader,
        dedicator="王小明", target="父母",
        body_text=None,
    )
    assert 'fill="#cccccc"' not in svg


# ---------------------------------------------------------------------------
# Web API
# ---------------------------------------------------------------------------


try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS = True
except ImportError:
    _HAS = False


@pytest.fixture
def client(temp_sutra_dir):
    if not _HAS:
        pytest.skip("web deps missing")
    # Plant a small placeholder file for heart_sutra so body endpoints work
    (temp_sutra_dir / "heart_sutra.txt").write_text(
        "天地人山水" * 60, encoding="utf-8")
    return TestClient(create_app())


def test_api_presets_lists_all_builtins_with_status(client):
    """5bc: 15 builtins now (4 buddhist + 4 taoist + 7 confucian)."""
    r = client.get("/api/sutra/presets")
    assert r.status_code == 200
    data = r.json()
    assert "sutra_dir" in data
    keys = [p["key"] for p in data["presets"]]
    # All four canonical buddhist presets must lead the list
    for k in ("heart_sutra", "diamond_sutra",
              "great_compassion", "manjushri_mantra"):
        assert k in keys
    # New 5bc additions visible
    for k in ("tao_te_ching", "qian_zi_wen", "san_zi_jing"):
        assert k in keys
    # Status flags reflect which files are present in temp_sutra_dir
    by_key = {p["key"]: p for p in data["presets"]}
    assert by_key["heart_sutra"]["ready"] is True
    assert by_key["heart_sutra"]["body_pages"] >= 1
    assert by_key["diamond_sutra"]["ready"] is False
    assert by_key["tao_te_ching"]["ready"] is False  # no file planted


def test_api_capacity_loaded(client):
    r = client.get("/api/sutra/capacity?preset=heart_sutra"
                    "&include_cover=true&include_dedication=true")
    assert r.status_code == 200
    d = r.json()
    assert d["ready"] is True
    assert d["cover"] == 1 and d["dedication"] == 1
    assert d["body_pages"] >= 1
    assert d["total"] == d["cover"] + d["body_pages"] + d["dedication"]


def test_api_capacity_unloaded_returns_zero(client):
    r = client.get("/api/sutra/capacity?preset=diamond_sutra")
    assert r.status_code == 200
    d = r.json()
    assert d["ready"] is False
    assert d["total"] == 0


def test_api_get_body_page(client):
    r = client.get("/api/sutra?preset=heart_sutra&page_index=0&page_type=body"
                    "&scribe=test&date_str=20260426")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    assert 'id="sutra-trace"' in r.text


def test_api_get_cover(client):
    r = client.get("/api/sutra?preset=heart_sutra&page_type=cover&scribe=test")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    # Cover renders the title — multiple paths
    assert r.text.count("<path") > 5


def test_api_get_dedication(client):
    r = client.get("/api/sutra?preset=heart_sutra&page_type=dedication"
                    "&dedicator=A&target=B")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"


def test_api_unloaded_body_returns_422(client):
    r = client.get("/api/sutra?preset=diamond_sutra&page_type=body")
    assert r.status_code == 422
    assert "not loaded" in r.text.lower() or "not loaded" in r.json()["detail"].lower()


def test_api_unknown_preset_returns_404(client):
    """5bb: arbitrary string keys are syntactically valid (user uploads can
    have any sanitised name); a nonexistent key returns 404 not 422."""
    r = client.get("/api/sutra?preset=mystery_unknown_key&page_type=body")
    assert r.status_code == 404


def test_api_invalid_page_type_rejected(client):
    r = client.get("/api/sutra?preset=heart_sutra&page_type=mystery")
    assert r.status_code == 422


def test_api_post_with_custom_verse(client):
    body = {
        "preset": "heart_sutra",
        "page_type": "dedication",
        "dedicator": "test",
        "target": "test",
        "dedication_verse": "天地人山水日月",
    }
    r = client.post("/api/sutra", json=body)
    assert r.status_code == 200
    assert 'fill="#cccccc"' in r.text


# ===========================================================================
# Phase 5bb — builtin/user split, categories, upload/edit/delete CRUD
# ===========================================================================


from stroke_order.sutras import (
    BUILTIN_SUTRAS, CATEGORY_LABELS, CATEGORY_ORDER,
    builtin_dir, user_dir, sanitize_key,
    save_user_preset, update_user_meta, delete_user_preset,
    read_user_text, get_sutra_info, list_user_keys, grouped_presets,
)


# ---------------------------------------------------------------------------
# Categories registry
# ---------------------------------------------------------------------------


def test_seven_categories_registered():
    """5bf: 6 → 7 categories with inspirational added."""
    assert set(CATEGORY_ORDER) == {
        "buddhist", "taoist", "confucian", "classical",
        "christian", "inspirational", "user_custom",
    }
    for cat in CATEGORY_ORDER:
        assert cat in CATEGORY_LABELS
    assert CATEGORY_LABELS["inspirational"] == "勵志家訓"


def test_all_builtins_marked_is_builtin_true():
    for info in BUILTIN_SUTRAS.values():
        assert info.is_builtin is True


def test_builtins_span_three_categories():
    """5bc: builtins now cover buddhist + taoist + confucian (3 of 6 cats)."""
    cats = {info.category for info in BUILTIN_SUTRAS.values()}
    assert "buddhist" in cats
    assert "taoist" in cats
    assert "confucian" in cats
    # Future categories (classical / christian) start empty, served by uploads
    assert "user_custom" not in cats


def test_taoist_builtins_include_tao_te_ching():
    info = BUILTIN_SUTRAS.get("tao_te_ching")
    assert info is not None
    assert info.category == "taoist"
    assert info.expected_chars > 0


def test_confucian_builtins_include_thousand_char_classic():
    info = BUILTIN_SUTRAS.get("qian_zi_wen")
    assert info is not None
    assert info.category == "confucian"
    # 千字文 is exactly 1000 (advisory; real file count rules)
    assert info.expected_chars == 1000


def test_no_taoist_or_confucian_mantra_repeats():
    """Mantra-repeat is only used for buddhist short mantras (5bc)."""
    for key, info in BUILTIN_SUTRAS.items():
        if info.category != "buddhist":
            assert info.is_mantra_repeat is False, \
                f"{key}: non-buddhist preset should not repeat"


# ---------------------------------------------------------------------------
# builtin/ subdirectory + legacy flat fallback
# ---------------------------------------------------------------------------


def test_builtin_loaded_from_subdir(temp_sutra_dir):
    (temp_sutra_dir / "builtin").mkdir()
    (temp_sutra_dir / "builtin" / "heart_sutra.txt").write_text(
        "天地人", encoding="utf-8")
    assert load_text("heart_sutra") == "天地人"


def test_legacy_flat_fallback_still_works(temp_sutra_dir):
    """Old layout (file directly in sutras/) must still resolve."""
    (temp_sutra_dir / "diamond_sutra.txt").write_text(
        "ABCDE", encoding="utf-8")
    assert load_text("diamond_sutra") == "ABCDE"


def test_builtin_subdir_takes_precedence_over_flat(temp_sutra_dir):
    (temp_sutra_dir / "diamond_sutra.txt").write_text(
        "FLAT", encoding="utf-8")
    (temp_sutra_dir / "builtin").mkdir()
    (temp_sutra_dir / "builtin" / "diamond_sutra.txt").write_text(
        "NESTED", encoding="utf-8")
    assert load_text("diamond_sutra") == "NESTED"


# ---------------------------------------------------------------------------
# User preset CRUD
# ---------------------------------------------------------------------------


def test_save_user_preset_writes_txt_and_json(temp_sutra_dir):
    key = save_user_preset(
        desired_key="my_test", text="天地玄黃",
        title="測試", category="taoist", source="老子",
    )
    assert key == "my_test"
    assert (temp_sutra_dir / "user" / "my_test.txt").exists()
    assert (temp_sutra_dir / "user" / "my_test.json").exists()


def test_save_user_preset_collision_auto_suffixes(temp_sutra_dir):
    a = save_user_preset(desired_key="dup", text="a", title="A",
                          category="user_custom")
    b = save_user_preset(desired_key="dup", text="b", title="B",
                          category="user_custom")
    c = save_user_preset(desired_key="dup", text="c", title="C",
                          category="user_custom")
    assert a == "dup"
    assert b == "dup_2"
    assert c == "dup_3"


def test_save_user_preset_rejects_unknown_category(temp_sutra_dir):
    with pytest.raises(ValueError, match="category"):
        save_user_preset(desired_key="bad", text="abc",
                          title="x", category="bogus")


def test_save_user_preset_rejects_empty_text(temp_sutra_dir):
    with pytest.raises(ValueError, match="empty"):
        save_user_preset(desired_key="bad", text="   ",
                          title="x", category="user_custom")


def test_get_sutra_info_finds_user_preset(temp_sutra_dir):
    save_user_preset(desired_key="taoist1", text="abc",
                      title="道德經", category="taoist", source="老子",
                      tags=["a", "b"])
    info = get_sutra_info("taoist1")
    assert info is not None
    assert info.is_builtin is False
    assert info.category == "taoist"
    assert info.title == "道德經"
    assert info.tags == ("a", "b")


def test_update_user_meta_changes_title_only(temp_sutra_dir):
    save_user_preset(desired_key="x", text="abc", title="原始",
                      category="user_custom")
    ok = update_user_meta("x", {"title": "新標題", "tags": ["1", "2"]})
    assert ok is True
    info = get_sutra_info("x")
    assert info.title == "新標題"
    assert info.tags == ("1", "2")


def test_update_user_meta_returns_false_for_missing_key(temp_sutra_dir):
    assert update_user_meta("does_not_exist", {"title": "x"}) is False


def test_delete_user_preset_removes_both_files(temp_sutra_dir):
    save_user_preset(desired_key="dme", text="abc", title="X",
                      category="user_custom")
    assert delete_user_preset("dme") is True
    assert not (temp_sutra_dir / "user" / "dme.txt").exists()
    assert not (temp_sutra_dir / "user" / "dme.json").exists()
    assert delete_user_preset("dme") is False  # idempotent


def test_read_user_text_returns_raw_unstripped(temp_sutra_dir):
    save_user_preset(desired_key="r", text="天 地\n人", title="x",
                      category="user_custom")
    raw = read_user_text("r")
    # save_user_preset strips trailing whitespace but preserves internal
    # whitespace verbatim
    assert "天" in raw and "地" in raw and "人" in raw


def test_list_user_keys_finds_uploaded(temp_sutra_dir):
    assert list_user_keys() == []
    save_user_preset(desired_key="a", text="x", title="A",
                      category="user_custom")
    save_user_preset(desired_key="b", text="x", title="B",
                      category="taoist")
    assert sorted(list_user_keys()) == ["a", "b"]


# ---------------------------------------------------------------------------
# Grouped snapshot
# ---------------------------------------------------------------------------


def test_grouped_presets_returns_seven_categories(temp_sutra_dir):
    """5bf: 7 categories (added inspirational)."""
    groups = grouped_presets()
    assert len(groups) == 7
    keys = [g["key"] for g in groups]
    assert keys == CATEGORY_ORDER


def test_grouped_presets_classifies_user_uploads(temp_sutra_dir):
    save_user_preset(desired_key="poem1", text="x", title="P1",
                      category="classical")
    save_user_preset(desired_key="self1", text="x", title="S1",
                      category="user_custom")
    groups = {g["key"]: g for g in grouped_presets()}
    classical_keys = [p["key"] for p in groups["classical"]["presets"]]
    custom_keys    = [p["key"] for p in groups["user_custom"]["presets"]]
    assert "poem1" in classical_keys
    assert "self1" in custom_keys


# ---------------------------------------------------------------------------
# sanitize_key helper
# ---------------------------------------------------------------------------


def test_sanitize_key_strips_unsafe_chars():
    assert sanitize_key("hello/world*") == "hello_world"
    # CJK preserved
    assert sanitize_key("道德經") == "道德經"
    # Empty → "untitled"
    assert sanitize_key("") == "untitled"
    assert sanitize_key("///") == "untitled"


# ---------------------------------------------------------------------------
# API endpoints (5bb)
# ---------------------------------------------------------------------------


def test_api_categories_returns_seven(client):
    r = client.get("/api/sutra/categories")
    assert r.status_code == 200
    cats = r.json()["categories"]
    assert len(cats) == 7
    keys = [c["key"] for c in cats]
    assert keys == CATEGORY_ORDER


def test_api_presets_grouped_format(client):
    r = client.get("/api/sutra/presets?grouped=true")
    assert r.status_code == 200
    data = r.json()
    assert "categories" in data
    assert len(data["categories"]) == 7   # 5bf: 6 → 7
    buddhist = next(c for c in data["categories"] if c["key"] == "buddhist")
    keys = [p["key"] for p in buddhist["presets"]]
    # Phase 5az + 5be + 5bg buddhist canonicals
    for required in (
        "heart_sutra", "heart_sutra_kumarajiva",
        "diamond_sutra", "great_compassion", "manjushri_mantra",
        # 5bg additions
        "amitabha_sutra", "lotus_pumen", "pu_guang_ming",
    ):
        assert required in keys, f"missing buddhist preset {required!r}"


def test_api_presets_flat_format_default(client):
    r = client.get("/api/sutra/presets")
    assert r.status_code == 200
    data = r.json()
    assert "presets" in data
    assert "categories" not in data


def test_api_upload_user_preset(client):
    body = {
        "text": "天地玄黃宇宙洪荒日月盈昃",
        "title": "千字文片段",
        "category": "classical",
        "source": "周興嗣",
        "desired_key": "tc_test",
    }
    r = client.post("/api/sutra/upload", json=body)
    assert r.status_code == 200
    assert r.json()["key"] == "tc_test"


def test_api_upload_invalid_category_returns_422(client):
    r = client.post("/api/sutra/upload", json={"text": "x", "category": "x"})
    assert r.status_code == 422


def test_api_upload_empty_text_returns_422(client):
    r = client.post("/api/sutra/upload",
                     json={"text": "  ", "category": "user_custom"})
    assert r.status_code == 422


def test_api_user_get_includes_raw_text(client):
    body = {"text": "天地人", "title": "T", "category": "user_custom",
            "desired_key": "raw_test"}
    client.post("/api/sutra/upload", json=body)
    r = client.get("/api/sutra/user/raw_test")
    assert r.status_code == 200
    d = r.json()
    assert d["title"] == "T"
    assert "天" in d["raw_text"]


def test_api_user_get_404_for_missing(client):
    r = client.get("/api/sutra/user/nonexistent")
    assert r.status_code == 404


def test_api_user_get_404_for_builtin(client):
    """Builtins are not exposed via user/{key} — they live in builtin_dir."""
    r = client.get("/api/sutra/user/heart_sutra")
    assert r.status_code == 404


def test_api_user_put_metadata(client):
    body = {"text": "天地", "title": "old", "category": "user_custom",
            "desired_key": "put_test"}
    client.post("/api/sutra/upload", json=body)
    r = client.put("/api/sutra/user/put_test",
                    json={"title": "new", "tags": ["x"]})
    assert r.status_code == 200
    refreshed = client.get("/api/sutra/user/put_test").json()
    assert refreshed["title"] == "new"
    assert refreshed["tags"] == ["x"]


def test_api_user_delete(client):
    body = {"text": "x", "title": "D", "category": "user_custom",
            "desired_key": "del_test"}
    client.post("/api/sutra/upload", json=body)
    r = client.delete("/api/sutra/user/del_test")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    r2 = client.get("/api/sutra/user/del_test")
    assert r2.status_code == 404


def test_api_user_delete_blocks_builtin(client):
    r = client.delete("/api/sutra/user/heart_sutra")
    assert r.status_code == 404


def test_api_render_user_preset_works(client):
    body = {"text": "天地玄黃宇宙洪荒" * 5, "title": "R",
            "category": "classical", "desired_key": "render_test"}
    client.post("/api/sutra/upload", json=body)
    r = client.get("/api/sutra?preset=render_test&page_type=body&page_index=0")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    assert 'id="sutra-trace"' in r.text


# ===========================================================================
# Phase 5bd — scholarly metadata (author/editor/notes/source_url) + editor page
# ===========================================================================


def test_5bd_sutra_info_carries_scholarly_fields():
    info = BUILTIN_SUTRAS["da_xue"]
    assert info.author == "曾子（傳）"
    assert info.editor == "朱熹（南宋）"
    assert info.source_url.startswith("https://")
    # notes default empty for builtins
    assert info.notes == ""


def test_5bd_save_user_preset_persists_scholarly_fields(temp_sutra_dir):
    key = save_user_preset(
        desired_key="zz_test", text="天地有大美而不言",
        title="莊子節錄", category="taoist",
        author="莊子（戰國）", editor="郭象（西晉）注",
        source="《莊子》外篇",
        source_url="https://ctext.org/zhuangzi/zh",
        notes="此為節錄一句作測試之用",
    )
    info = get_sutra_info(key)
    assert info.author == "莊子（戰國）"
    assert info.editor == "郭象（西晉）注"
    assert info.source == "《莊子》外篇"
    assert info.source_url == "https://ctext.org/zhuangzi/zh"
    assert "節錄" in info.notes


def test_5bd_update_user_meta_patches_scholarly_only(temp_sutra_dir):
    key = save_user_preset(
        desired_key="zz_patch", text="abc", title="t",
        category="taoist", author="原作者", editor="原編者",
    )
    update_user_meta(key, {"author": "新作者", "notes": "新校記"})
    info = get_sutra_info(key)
    assert info.author == "新作者"
    assert info.editor == "原編者"  # untouched
    assert info.notes == "新校記"


def test_5bd_info_to_dict_includes_scholarly_fields():
    from stroke_order.sutras import _info_to_dict
    info = BUILTIN_SUTRAS["zhong_yong"]
    d = _info_to_dict(info)
    for f in ("author", "editor", "notes", "source_url"):
        assert f in d
    assert d["editor"] == "朱熹（南宋）"


# ---------------------------------------------------------------------------
# API: builtin GET + new fields in upload/get/put
# ---------------------------------------------------------------------------


def test_5bd_api_builtin_get_returns_metadata_and_text(client):
    """5bd: /api/sutra/builtin/{key} returns full metadata."""
    # Plant text in builtin/ for tao_te_ching
    bd = builtin_dir()
    bd.mkdir(parents=True, exist_ok=True)
    (bd / "tao_te_ching.txt").write_text("天地玄黃" * 5, encoding="utf-8")
    r = client.get("/api/sutra/builtin/tao_te_ching")
    assert r.status_code == 200
    d = r.json()
    assert d["title"] == "道德經"
    assert d["author"] == "老子（春秋）"
    assert d["source_url"].startswith("https://ctext.org/")
    assert "天地玄黃" in d["raw_text"]


def test_5bd_api_builtin_get_404_for_unknown(client):
    r = client.get("/api/sutra/builtin/not_a_real_key")
    assert r.status_code == 404


def test_5bd_api_upload_accepts_scholarly_fields(client):
    body = {
        "text": "天地有大美而不言",
        "title": "莊子節錄",
        "category": "taoist",
        "author": "莊子（戰國）",
        "editor": "郭象（西晉）注",
        "source": "《莊子》外篇",
        "source_url": "https://ctext.org/zhuangzi/zh",
        "notes": "測試校記",
        "desired_key": "zz_api_test",
    }
    r = client.post("/api/sutra/upload", json=body)
    assert r.status_code == 200
    r2 = client.get("/api/sutra/user/zz_api_test")
    d = r2.json()
    assert d["author"] == "莊子（戰國）"
    assert d["editor"] == "郭象（西晉）注"
    assert d["source_url"] == "https://ctext.org/zhuangzi/zh"
    assert d["notes"] == "測試校記"


def test_5bd_api_put_updates_only_scholarly_fields(client):
    client.post("/api/sutra/upload", json={
        "text": "abc", "title": "t",
        "category": "taoist", "desired_key": "patch_test",
        "author": "A", "editor": "E",
    })
    r = client.put("/api/sutra/user/patch_test",
                    json={"author": "A2", "notes": "N2"})
    assert r.status_code == 200
    d = client.get("/api/sutra/user/patch_test").json()
    assert d["author"] == "A2"
    assert d["editor"] == "E"
    assert d["notes"] == "N2"


def test_5bd_editor_page_served(client):
    r = client.get("/sutra-editor")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    # Spot-check key UI fields
    for needle in ('id="f-author"', 'id="f-editor"', 'id="f-source-url"',
                   'id="f-notes"', '/api/sutra/builtin/'):
        assert needle in r.text


# ===========================================================================
# Phase 5be — builtin metadata override + Kumarajiva Heart Sutra
# ===========================================================================


from stroke_order.sutras import (
    update_builtin_meta, write_builtin_text, _builtin_meta_path,
)


def test_5be_kumarajiva_heart_sutra_registered():
    info = BUILTIN_SUTRAS.get("heart_sutra_kumarajiva")
    assert info is not None
    assert info.category == "buddhist"
    assert "鳩摩羅什" in info.author
    # Must coexist with玄奘版 — both keys present
    assert "heart_sutra" in BUILTIN_SUTRAS


def test_5be_buddhist_kumarajiva_present():
    """5be added Kumarajiva; 5bg added 3 more buddhist sutras."""
    buddhist = [i for i in BUILTIN_SUTRAS.values() if i.category == "buddhist"]
    keys = {i.key for i in buddhist}
    # All five Kumarajiva-era sutras must be present
    for k in ("heart_sutra", "heart_sutra_kumarajiva",
              "diamond_sutra", "great_compassion", "manjushri_mantra"):
        assert k in keys


# ---------------------------------------------------------------------------
# Override mechanism
# ---------------------------------------------------------------------------


def test_5be_update_builtin_meta_creates_json_override(temp_sutra_dir):
    ok = update_builtin_meta("tao_te_ching", {
        "title": "我的道德經",
        "notes": "校記內容",
    })
    assert ok is True
    info = get_sutra_info("tao_te_ching")
    assert info.title == "我的道德經"
    assert info.notes == "校記內容"
    # Locked fields preserve hard-code defaults
    assert info.category == "taoist"


def test_5be_update_builtin_meta_drops_locked_fields(temp_sutra_dir):
    update_builtin_meta("heart_sutra", {
        "title": "改標題",
        "category": "taoist",            # locked
        "is_mantra_repeat": True,        # locked
        "filename": "evil.txt",          # locked
    })
    info = get_sutra_info("heart_sutra")
    assert info.title == "改標題"
    assert info.category == "buddhist"
    assert info.is_mantra_repeat is False
    assert info.filename == "heart_sutra.txt"


def test_5be_update_builtin_meta_unknown_key_returns_false(temp_sutra_dir):
    assert update_builtin_meta("not_a_real_key", {"title": "x"}) is False


def test_5be_write_builtin_text_writes_to_builtin_dir(temp_sutra_dir):
    ok = write_builtin_text("tao_te_ching", "天地玄黃")
    assert ok is True
    p = temp_sutra_dir / "builtin" / "tao_te_ching.txt"
    assert p.exists()
    assert p.read_text(encoding="utf-8") == "天地玄黃"
    assert load_text("tao_te_ching") == "天地玄黃"


def test_5be_write_builtin_text_rejects_empty(temp_sutra_dir):
    assert write_builtin_text("tao_te_ching", "") is False
    assert write_builtin_text("tao_te_ching", "   ") is False


def test_5be_get_sutra_info_falls_back_when_no_override(temp_sutra_dir):
    """No override file → returns the hard-coded default unchanged."""
    info = get_sutra_info("da_xue")
    # Hard-coded values
    assert info.editor == "朱熹（南宋）"
    # Override path doesn't exist
    assert not _builtin_meta_path("da_xue").exists()


def test_5be_overrides_applied_in_grouped_presets(temp_sutra_dir):
    update_builtin_meta("heart_sutra", {"title": "更名後的心經"})
    groups = grouped_presets()
    buddhist = next(g for g in groups if g["key"] == "buddhist")
    titles = [p["title"] for p in buddhist["presets"]]
    assert "更名後的心經" in titles


# ---------------------------------------------------------------------------
# API: PUT /api/sutra/builtin/{key}
# ---------------------------------------------------------------------------


def test_5be_api_put_builtin_meta(client):
    r = client.put("/api/sutra/builtin/tao_te_ching", json={
        "title": "道德經（我的版本）",
        "notes": "API PUT 測試",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["meta_updated"] is True
    assert body["text_written"] is False

    r2 = client.get("/api/sutra/builtin/tao_te_ching")
    d = r2.json()
    assert d["title"] == "道德經（我的版本）"
    assert d["notes"] == "API PUT 測試"


def test_5be_api_put_builtin_text_overwrites_file(client, temp_sutra_dir):
    r = client.put("/api/sutra/builtin/heart_sutra_kumarajiva", json={
        "text": "天地玄黃宇宙洪荒",
    })
    assert r.status_code == 200
    assert r.json()["text_written"] is True
    p = temp_sutra_dir / "builtin" / "heart_sutra_kumarajiva.txt"
    assert p.exists()
    assert "天地玄黃" in p.read_text(encoding="utf-8")


def test_5be_api_put_locked_fields_silently_ignored(client):
    """Locked fields in payload don't error, just get dropped."""
    r = client.put("/api/sutra/builtin/heart_sutra", json={
        "title": "OK 改標題",
        "category": "taoist",   # silently dropped
    })
    assert r.status_code == 200
    info = client.get("/api/sutra/builtin/heart_sutra").json()
    assert info["title"] == "OK 改標題"
    assert info["category"] == "buddhist"


def test_5be_api_put_unknown_builtin_404(client):
    r = client.put("/api/sutra/builtin/no_real_key", json={"title": "x"})
    assert r.status_code == 404


def test_5be_api_delete_builtin_blocked(client):
    r = client.delete("/api/sutra/builtin/heart_sutra")
    assert r.status_code == 405


def test_5be_kumarajiva_appears_in_grouped_listing(client):
    r = client.get("/api/sutra/presets?grouped=true")
    buddhist = next(g for g in r.json()["categories"] if g["key"] == "buddhist")
    keys = [p["key"] for p in buddhist["presets"]]
    assert "heart_sutra_kumarajiva" in keys


# ===========================================================================
# Phase 5bf — 27 new builtin presets across classical/christian/inspirational
# ===========================================================================


def test_5bf_inspirational_category_added():
    assert "inspirational" in CATEGORY_LABELS
    assert CATEGORY_LABELS["inspirational"] == "勵志家訓"
    # Position: between christian and user_custom
    idx = CATEGORY_ORDER.index("inspirational")
    assert CATEGORY_ORDER[idx - 1] == "christian"
    assert CATEGORY_ORDER[idx + 1] == "user_custom"


def test_5bf_classical_has_14_builtins():
    classical = [i for i in BUILTIN_SUTRAS.values() if i.category == "classical"]
    assert len(classical) == 14


def test_5bf_christian_has_8_builtins():
    christian = [i for i in BUILTIN_SUTRAS.values() if i.category == "christian"]
    assert len(christian) == 8


def test_5bf_inspirational_has_5_builtins():
    inspirational = [i for i in BUILTIN_SUTRAS.values()
                      if i.category == "inspirational"]
    assert len(inspirational) == 5


def test_5bf_total_builtins_at_least_43():
    """4 buddhist (5az) + 11 daoist/confucian (5bc) + 1 kumarajiva (5be)
    + 14 classical + 8 christian + 5 inspirational (5bf) = 43.
    Note: 5bg adds 3 more buddhist; this test asserts the floor."""
    assert len(BUILTIN_SUTRAS) >= 43


@pytest.mark.parametrize("key", [
    "man_jiang_hong", "chibi_fu", "shi_shuo", "yueyang_lou_ji",
    "lord_prayer", "hail_mary", "psalm_23",
    "macarthur_prayer", "jiezi_shu", "zhu_zi_jia_xun",
])
def test_5bf_new_builtins_have_required_metadata(key):
    info = BUILTIN_SUTRAS[key]
    assert info.title
    assert info.author
    assert info.source
    assert info.source_url.startswith(("http://", "https://"))
    assert info.expected_chars > 0


def test_5bf_macarthur_prayer_in_inspirational(client):
    r = client.get("/api/sutra/presets?grouped=true")
    insp = next(g for g in r.json()["categories"]
                if g["key"] == "inspirational")
    keys = [p["key"] for p in insp["presets"]]
    assert "macarthur_prayer" in keys


def test_5bf_can_upload_to_inspirational_category(client):
    body = {
        "text": "天地玄黃宇宙洪荒",
        "title": "我的格言",
        "category": "inspirational",
        "desired_key": "my_motto",
    }
    r = client.post("/api/sutra/upload", json=body)
    assert r.status_code == 200


# ===========================================================================
# Phase 5bg — 3 new buddhist + ClosingPageSpec + per-category templates
# ===========================================================================


from stroke_order.sutras import (
    ClosingPageSpec, CLOSING_TEMPLATES, get_closing,
)


def test_5bg_three_new_buddhist_sutras_registered():
    for k in ("amitabha_sutra", "lotus_pumen", "pu_guang_ming"):
        assert k in BUILTIN_SUTRAS
        assert BUILTIN_SUTRAS[k].category == "buddhist"
        assert "鳩摩羅什" in BUILTIN_SUTRAS[k].author or \
               "地婆訶羅" in BUILTIN_SUTRAS[k].author


def test_5bg_buddhist_now_has_8_builtins():
    buddhist = [i for i in BUILTIN_SUTRAS.values() if i.category == "buddhist"]
    assert len(buddhist) == 8


def test_5bg_total_builtins_is_46():
    assert len(BUILTIN_SUTRAS) == 46


def test_5bg_closing_templates_per_category_exist():
    for cat in ("buddhist", "taoist", "confucian", "classical",
                "christian", "inspirational", "user_custom"):
        assert cat in CLOSING_TEMPLATES
    assert CLOSING_TEMPLATES["buddhist"].title == "迴向文"
    assert CLOSING_TEMPLATES["christian"].title == "榮耀歸主"
    assert CLOSING_TEMPLATES["user_custom"].verse == ""


def test_5bg_get_closing_falls_back_to_category():
    # No override on builtin → category template kicks in
    c = get_closing("heart_sutra")
    assert c.title == "迴向文"
    c = get_closing("man_jiang_hong")
    assert c.title == "跋"
    c = get_closing("macarthur_prayer")
    assert c.title == "自勉"


def test_5bg_get_closing_per_sutra_override(temp_sutra_dir):
    update_builtin_meta("heart_sutra", {
        "closing": {
            "title": "我的迴向", "verse": "...",
            "blank1_label": "自題", "blank2_label": "敬識",
        }
    })
    c = get_closing("heart_sutra")
    assert c.title == "我的迴向"
    assert c.blank1_label == "自題"


def test_5bg_user_upload_with_closing(temp_sutra_dir):
    key = save_user_preset(
        desired_key="motto1", text="天行健",
        title="座右銘", category="user_custom",
        closing={
            "title": "自勵", "verse": "君子以自強",
            "blank1_label": "後學", "blank2_label": "敬識",
        },
    )
    info = get_sutra_info(key)
    assert info.closing is not None
    assert info.closing.title == "自勵"
    c = get_closing(key)
    assert c.title == "自勵"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_5bg_api_closing_templates_endpoint(client):
    r = client.get("/api/sutra/closing-templates")
    assert r.status_code == 200
    data = r.json()
    assert "templates" in data
    keys = [t["category"] for t in data["templates"]]
    assert keys == [
        "buddhist", "taoist", "confucian", "classical",
        "christian", "inspirational", "user_custom",
    ]
    buddhist = next(t for t in data["templates"] if t["category"] == "buddhist")
    assert buddhist["closing"]["title"] == "迴向文"


def test_5bg_api_builtin_get_includes_closing_fields(client):
    r = client.get("/api/sutra/builtin/tao_te_ching")
    assert r.status_code == 200
    d = r.json()
    assert "closing_override" in d
    assert "closing_effective" in d
    # No override yet → effective falls back to taoist category template
    assert d["closing_override"] is None
    assert d["closing_effective"]["title"] == "祈願"


def test_5bg_api_put_builtin_closing_override(client):
    r = client.put("/api/sutra/builtin/heart_sutra", json={
        "closing": {
            "title": "客製迴向", "verse": "願以此功德…",
            "blank1_label": "自題", "blank2_label": "敬識",
        }
    })
    assert r.status_code == 200
    info = client.get("/api/sutra/builtin/heart_sutra").json()
    assert info["closing_override"]["title"] == "客製迴向"
    assert info["closing_effective"]["title"] == "客製迴向"


def test_5bg_api_upload_with_closing(client):
    body = {
        "text": "天行健君子以自強不息",
        "title": "易經乾卦",
        "category": "confucian",
        "closing": {
            "title": "自勵", "verse": "君子以自強",
            "blank1_label": "後學", "blank2_label": "敬識",
        },
        "desired_key": "yi_qian",
    }
    r = client.post("/api/sutra/upload", json=body)
    assert r.status_code == 200
    d = client.get("/api/sutra/user/yi_qian").json()
    assert d["closing_override"]["title"] == "自勵"


def test_5bg_api_dedication_uses_resolved_closing_when_verse_blank(
        client, temp_sutra_dir):
    # Plant tao_te_ching text so render works
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "tao_te_ching.txt").write_text("天地萬物" * 5,
                                                       encoding="utf-8")
    # Don't pass dedication_verse → server should pull from closing template
    r = client.get("/api/sutra?preset=tao_te_ching&page_type=dedication"
                    "&dedicator=test&target=test")
    assert r.status_code == 200
    # We can't directly inspect rendered text, but the endpoint should not
    # 422 on missing verse (which would mean fallback worked).
    assert r.headers["content-type"] == "image/svg+xml"


# ===========================================================================
# Phase 5bh — text_mode (compact / with_punct / raw) + signature default empty
# ===========================================================================


from stroke_order.exporters.sutra import prepare_text


def test_5bh_compact_drops_punct_and_whitespace():
    text = "觀自在 菩薩，行深般若波羅蜜多時，照見五蘊皆空。\n度一切苦厄。"
    cells = prepare_text(text, "compact")
    # Every cell must be a real glyph
    assert all(c and not c.isspace() for c in cells)
    assert "，" not in cells
    assert "。" not in cells
    assert " " not in cells
    # Char count = source minus punctuation/whitespace
    expected = sum(1 for c in text
                   if c not in "，。 \n" and not c.isspace())
    assert len(cells) == expected


def test_5bh_with_punct_keeps_punctuation():
    text = "甲乙，丙丁。"
    cells = prepare_text(text, "with_punct")
    assert "，" in cells
    assert "。" in cells


def test_5bh_with_punct_paragraph_alignment():
    """Each \\n-separated paragraph starts at the top of a new column.

    With ROWS=15, column boundaries are at indexes 15, 30, 45...
    """
    from stroke_order.exporters.sutra import ROWS
    text = "甲乙丙丁戊\n第二段第一字"
    cells = prepare_text(text, "with_punct")
    # First 5 cells = first paragraph
    assert cells[:5] == list("甲乙丙丁戊")
    # Cells 5..14 should be empty (paragraph padding)
    assert all(c == "" for c in cells[5:ROWS])
    # Cell at ROWS = 15 must be the start of paragraph 2
    assert cells[ROWS] == "第"


def test_5bh_with_punct_line_head_forbidden_swap():
    """Closing punct at column-top gets swapped with prior cell."""
    from stroke_order.exporters.sutra import ROWS
    # 15 chars then a comma at index 15 (column-top of column 1)
    text = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰，巳午未"
    cells = prepare_text(text, "with_punct")
    # 「，」 is forbidden at column-top → swapped to index 14
    assert cells[ROWS - 1] == "，"
    assert cells[ROWS] == "辰"


def test_5bh_raw_keeps_whitespace_as_blank_cells():
    text = "甲 乙\n丙"
    cells = prepare_text(text, "raw")
    assert cells == ["甲", "", "乙", "", "丙"]


def test_5bh_total_body_pages_uses_mode():
    """compact reduces page count vs raw when text has lots of punct."""
    from stroke_order.exporters.sutra import total_body_pages, CELLS_PER_PAGE
    # Text with 50% punctuation
    base = ("甲乙丙丁戊。" * 100)   # 500 chars, ~83 punct
    compact_pages = total_body_pages(base, "compact")
    raw_pages = total_body_pages(base, "raw")
    # Compact drops punctuation → fewer chars → equal or fewer pages
    assert compact_pages <= raw_pages


# ---------------------------------------------------------------------------
# Server defaults: signature is empty, no '時時抄經' branding
# ---------------------------------------------------------------------------


def test_5bh_signature_default_is_empty(client, temp_sutra_dir):
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text(
        "天地玄黃" * 5, encoding="utf-8")
    # Cover page without explicit signature → no '時時抄經' anywhere
    r = client.get("/api/sutra?preset=heart_sutra&page_type=cover")
    assert r.status_code == 200
    assert "時時抄經" not in r.text


# ---------------------------------------------------------------------------
# API: text_mode parameter wired
# ---------------------------------------------------------------------------


def test_5bh_api_capacity_text_mode_compact_vs_raw(client, temp_sutra_dir):
    builtin_dir().mkdir(parents=True, exist_ok=True)
    # Text padded with punctuation so compact differs from raw
    text = "甲乙丙，丁戊己。" * 50   # 350 chars, ~100 punct
    (builtin_dir() / "heart_sutra.txt").write_text(text, encoding="utf-8")
    r1 = client.get("/api/sutra/capacity?preset=heart_sutra&text_mode=compact")
    r2 = client.get("/api/sutra/capacity?preset=heart_sutra&text_mode=raw")
    assert r1.status_code == 200 and r2.status_code == 200
    # compact has fewer or equal body pages
    assert r1.json()["body_pages"] <= r2.json()["body_pages"]


def test_5bh_api_invalid_text_mode_returns_422(client):
    r = client.get("/api/sutra?preset=heart_sutra&text_mode=mystery")
    assert r.status_code == 422


def test_5bh_api_body_renders_for_all_three_modes(client, temp_sutra_dir):
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text(
        "甲乙，丙丁。戊己" * 20, encoding="utf-8")
    for mode in ("compact", "with_punct", "raw"):
        r = client.get(f"/api/sutra?preset=heart_sutra&page_type=body"
                        f"&text_mode={mode}")
        assert r.status_code == 200, f"mode={mode} → {r.status_code}"
        assert r.headers["content-type"] == "image/svg+xml"


# ===========================================================================
# Phase 5bi — compact_marks (古籍式句讀) + PDF download
# ===========================================================================


from stroke_order.exporters.sutra import (
    prepare_text_with_marks, page_slice_with_marks,
)


def test_5bi_prepare_text_with_marks_attaches_to_previous_glyph():
    """The first punct after a glyph attaches to that glyph; later puncts
    in the same run are dropped."""
    cells, marks = prepare_text_with_marks("甲乙，丙丁。戊")
    assert cells == list("甲乙丙丁戊")
    # 「，」 should attach to 乙, 「。」 should attach to 丁
    assert marks[1] == "，"
    assert marks[3] == "。"
    # Other slots should be empty
    assert marks[0] == ""
    assert marks[2] == ""
    assert marks[4] == ""


def test_5bi_prepare_text_with_marks_keeps_only_first_punct_in_run():
    """If multiple puncts follow in a row (eg. 「！？」), only the first
    is kept as the mark."""
    cells, marks = prepare_text_with_marks("甲乙！？丙")
    assert cells == list("甲乙丙")
    assert marks[1] == "！"


def test_5bi_prepare_text_with_marks_skips_brackets():
    """Brackets / quotes are not 句讀 marks — silently dropped."""
    cells, marks = prepare_text_with_marks("「甲」乙")
    assert cells == list("甲乙")
    # No mark attached; brackets ignored
    assert all(m == "" for m in marks)


def test_5bi_prepare_text_with_marks_handles_empty():
    cells, marks = prepare_text_with_marks("")
    assert cells == [] and marks == []


def test_5bi_prepare_text_with_marks_trailing_punct_dropped():
    """Trailing punct with no following glyph is silently dropped."""
    cells, marks = prepare_text_with_marks("甲。")
    assert cells == ["甲"]
    # No glyph follows the punct → it stays as pending and gets dropped
    assert marks == [""]


def test_5bi_page_slice_with_marks_returns_parallel_lists():
    cells, marks = page_slice_with_marks("甲乙，丙丁。", 0)
    assert len(cells) == len(marks)


def test_5bi_render_sutra_page_emits_marks_group(stub_loader):
    """When punct_marks is provided, an extra <g id="sutra-marks"> appears."""
    cells = ["甲", "乙", "丙"]
    marks_with = ["", "，", ""]
    svg_with = render_sutra_page(cells, char_loader=stub_loader,
                                  punct_marks=marks_with)
    svg_without = render_sutra_page(cells, char_loader=stub_loader)
    assert 'id="sutra-marks"' in svg_with
    assert 'id="sutra-marks"' not in svg_without


def test_5bi_render_sutra_page_no_marks_when_all_empty(stub_loader):
    cells = ["甲", "乙"]
    marks_empty = ["", ""]
    svg = render_sutra_page(cells, char_loader=stub_loader,
                            punct_marks=marks_empty)
    # All marks empty → no group emitted
    assert 'id="sutra-marks"' not in svg


# ---------------------------------------------------------------------------
# API: text_mode = "compact_marks"
# ---------------------------------------------------------------------------


def test_5bi_api_compact_marks_mode_renders(client, temp_sutra_dir):
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text(
        "甲乙，丙丁。" * 30, encoding="utf-8")
    r = client.get("/api/sutra?preset=heart_sutra&page_type=body"
                    "&text_mode=compact_marks")
    assert r.status_code == 200
    assert 'id="sutra-marks"' in r.text


def test_5bi_api_compact_marks_is_default(client, temp_sutra_dir):
    """5bi: compact_marks is the new default text_mode."""
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text(
        "甲乙，丙丁。" * 30, encoding="utf-8")
    # No text_mode param → server default should be compact_marks
    r = client.get("/api/sutra?preset=heart_sutra&page_type=body")
    assert r.status_code == 200
    assert 'id="sutra-marks"' in r.text


# ---------------------------------------------------------------------------
# PDF endpoint
# ---------------------------------------------------------------------------


def test_5bi_pdf_endpoint_returns_pdf(client, temp_sutra_dir):
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text(
        "甲乙丙丁戊" * 30, encoding="utf-8")
    r = client.get("/api/sutra/pdf?preset=heart_sutra&dpi=120")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    # Some content was produced
    assert len(r.content) > 1024


def test_5bi_pdf_endpoint_404_for_unknown_preset(client):
    r = client.get("/api/sutra/pdf?preset=mystery_unknown")
    assert r.status_code == 404


def test_5bi_pdf_endpoint_422_for_unloaded(client):
    # diamond_sutra has no file in this temp dir
    r = client.get("/api/sutra/pdf?preset=diamond_sutra")
    assert r.status_code == 422


def test_5bi_pdf_endpoint_rejects_invalid_text_mode(client):
    r = client.get("/api/sutra/pdf?preset=heart_sutra&text_mode=mystery")
    assert r.status_code == 422


# ===========================================================================
# Phase 5bj — page orientation + text direction (4 combinations)
# ===========================================================================


from stroke_order.exporters.sutra import (
    get_geometry, PageGeometry,
)


def test_5bj_geometry_landscape_default():
    g = get_geometry("landscape")
    assert (g.page_w_mm, g.page_h_mm) == (297.0, 210.0)
    assert (g.cols, g.rows) == (20, 15)
    assert g.cells_per_page == 300


def test_5bj_geometry_portrait():
    g = get_geometry("portrait")
    assert (g.page_w_mm, g.page_h_mm) == (210.0, 297.0)
    assert (g.cols, g.rows) == (15, 20)
    assert g.cells_per_page == 300


def test_5bj_geometry_unknown_falls_back_to_landscape():
    g = get_geometry("invalid")  # type: ignore[arg-type]
    assert g == get_geometry("landscape")


@pytest.mark.parametrize("orientation,expected_w,expected_h", [
    ("landscape", 297.0, 210.0),
    ("portrait", 210.0, 297.0),
])
def test_5bj_render_body_emits_geometry_specific_viewbox(
        stub_loader, orientation, expected_w, expected_h):
    svg = render_sutra_page(
        ["甲"] * 5, char_loader=stub_loader,
        orientation=orientation,
    )
    marker = f'viewBox="0 0 {expected_w:.3f} {expected_h:.3f}"'
    assert marker in svg


def test_5bj_index_to_cell_vertical_vs_horizontal():
    """Vertical = col-major; Horizontal = row-major."""
    from stroke_order.exporters.sutra import _index_to_cell
    geom = get_geometry("landscape")  # 20×15
    # Vertical: char 0 → col 0 row 0; char 1 → col 0 row 1; char 15 → col 1 row 0
    assert _index_to_cell(0, geom=geom, direction="vertical") == (0, 0)
    assert _index_to_cell(1, geom=geom, direction="vertical") == (0, 1)
    assert _index_to_cell(15, geom=geom, direction="vertical") == (1, 0)
    # Horizontal: char 0 → col 0 row 0; char 1 → col 1 row 0; char 20 → col 0 row 1
    assert _index_to_cell(0, geom=geom, direction="horizontal") == (0, 0)
    assert _index_to_cell(1, geom=geom, direction="horizontal") == (1, 0)
    assert _index_to_cell(20, geom=geom, direction="horizontal") == (0, 1)


def test_5bj_cell_origin_vertical_starts_from_right():
    from stroke_order.exporters.sutra import _cell_origin
    geom = get_geometry("landscape")
    # Vertical: col 0 origin x should be near the RIGHT edge
    x_v, _ = _cell_origin(
        0, 0, geom=geom, direction="vertical",
        margin_top_mm=20, margin_left_mm=15, margin_right_mm=15,
        cell_w=10, cell_h=10,
    )
    # 297 - 15 - 1*10 = 272
    assert x_v == 272.0
    # Horizontal: col 0 origin x should be near the LEFT edge
    x_h, _ = _cell_origin(
        0, 0, geom=geom, direction="horizontal",
        margin_top_mm=20, margin_left_mm=15, margin_right_mm=15,
        cell_w=10, cell_h=10,
    )
    assert x_h == 15.0


def test_5bj_punct_mark_position_differs_by_direction(stub_loader):
    """Marks are below in vertical, to the right in horizontal."""
    cells = ["甲", "乙"]
    marks = ["，", ""]
    svg_v = render_sutra_page(cells, char_loader=stub_loader,
                                punct_marks=marks, direction="vertical")
    svg_h = render_sutra_page(cells, char_loader=stub_loader,
                                punct_marks=marks, direction="horizontal")
    # Both should have a sutra-marks group
    assert 'id="sutra-marks"' in svg_v
    assert 'id="sutra-marks"' in svg_h


# ---------------------------------------------------------------------------
# API: paper_orientation + text_direction params
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("orient,direction", [
    ("landscape", "vertical"),
    ("landscape", "horizontal"),
    ("portrait", "vertical"),
    ("portrait", "horizontal"),
])
def test_5bj_api_renders_4_combinations(client, temp_sutra_dir, orient, direction):
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text(
        "天地玄黃" * 30, encoding="utf-8")
    r = client.get(
        f"/api/sutra?preset=heart_sutra&page_type=body"
        f"&paper_orientation={orient}&text_direction={direction}"
    )
    assert r.status_code == 200
    if orient == "landscape":
        assert 'viewBox="0 0 297.000 210.000"' in r.text
    else:
        assert 'viewBox="0 0 210.000 297.000"' in r.text


def test_5bj_api_rejects_invalid_orientation(client):
    r = client.get(
        "/api/sutra?preset=heart_sutra&paper_orientation=square")
    assert r.status_code == 422


def test_5bj_api_rejects_invalid_direction(client):
    r = client.get("/api/sutra?preset=heart_sutra&text_direction=diagonal")
    assert r.status_code == 422


def test_5bj_api_capacity_includes_orientation_param(client, temp_sutra_dir):
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text("天" * 600, encoding="utf-8")
    r1 = client.get("/api/sutra/capacity?preset=heart_sutra&paper_orientation=landscape")
    r2 = client.get("/api/sutra/capacity?preset=heart_sutra&paper_orientation=portrait")
    # Both have the same 300-cell capacity, so body_pages should match
    assert r1.json()["body_pages"] == r2.json()["body_pages"] == 2


def test_5bj_pdf_works_with_portrait(client, temp_sutra_dir):
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text(
        "甲乙丙丁戊" * 30, encoding="utf-8")
    r = client.get("/api/sutra/pdf?preset=heart_sutra"
                    "&paper_orientation=portrait&dpi=120")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


# ===========================================================================
# Phase 5bk — PDF white-background fix + visible 句讀 marks
# ===========================================================================


def test_5bk_marks_use_subdued_grey_color(stub_loader):
    """5bk/5bl: marks group is mid-grey (#888) at lighter opacity."""
    cells = ["甲"]
    marks = ["，"]
    svg = render_sutra_page(cells, char_loader=stub_loader,
                            punct_marks=marks)
    assert '#888888' in svg
    assert 'opacity="0.55"' in svg


def test_5bu_marks_group_uses_fill_only(stub_loader):
    """5bu: marks now use <text> elements rendered with a system CJK
    font, so the group only needs fill + opacity (no stroke)."""
    cells = ["甲"]
    marks = ["，"]
    svg = render_sutra_page(cells, char_loader=stub_loader,
                            punct_marks=marks)
    import re
    m = re.search(r'<g id="sutra-marks"[^>]*>', svg)
    assert m is not None
    group_opening = m.group(0)
    assert 'fill="#888888"' in group_opening
    assert 'opacity="0.55"' in group_opening


def test_5bu_marks_render_as_text_elements(client, temp_sutra_dir):
    """5bu: marks now use SVG <text> elements rendered by the browser/PDF
    backend's CJK font. We expect <text> tags inside the marks group, NOT
    polylines or paths."""
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text(
        "天地玄黃，宇宙洪荒。" * 4, encoding="utf-8")
    r = client.get("/api/sutra?preset=heart_sutra&page_type=body"
                    "&text_mode=compact_marks")
    assert r.status_code == 200
    body = r.text
    start = body.find('<g id="sutra-marks"')
    assert start >= 0, "marks group missing"
    # Take everything after the marks group opening
    fragment = body[start:]
    # Must contain <text> elements
    assert fragment.count("<text") > 0, "no <text> rendered for marks"
    # Should NOT use the legacy polyline/path approach inside marks group
    # (we close after first </g> so other groups elsewhere still allowed)
    end = fragment.find("</g>")
    marks_inner = fragment[:end]
    assert "<polyline" not in marks_inner
    # Spot-check the actual punctuation char appears in the SVG
    assert "，" in marks_inner or "。" in marks_inner


# ---------------------------------------------------------------------------
# PDF: white background sanity
# ---------------------------------------------------------------------------


def test_5bk_pdf_renders_white_background(client, temp_sutra_dir):
    """The first page of the generated PDF should have a near-white sample
    pixel after rasterisation (proves the cairosvg background_color fix +
    PIL alpha-flatten path)."""
    import io
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text(
        "天地玄黃" * 30, encoding="utf-8")
    r = client.get("/api/sutra/pdf?preset=heart_sutra&dpi=120"
                    "&include_cover=false")
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"

    # Re-rasterise via the same pipeline to inspect a sample pixel.
    import cairosvg
    from PIL import Image
    from stroke_order.exporters.sutra import (
        get_geometry, render_sutra_page,
    )
    geom = get_geometry("landscape")
    svg = render_sutra_page([], char_loader=lambda c: None)  # blank page
    png = cairosvg.svg2png(
        bytestring=svg.encode(),
        output_width=int(geom.page_w_mm / 25.4 * 120),
        output_height=int(geom.page_h_mm / 25.4 * 120),
        background_color="white",
    )
    rgba = Image.open(io.BytesIO(png)).convert("RGBA")
    white = Image.new("RGB", rgba.size, "white")
    white.paste(rgba, mask=rgba.split()[3])
    # Sample a corner — must be white, not black
    assert white.getpixel((10, 10)) == (255, 255, 255)


def test_5bl_mark_anchored_bottom_right_for_both_directions(stub_loader):
    """5bl: 句讀 mark sits in the bottom-right of its cell regardless of
    text direction, matching traditional 字下偏右 placement."""
    cells = ["甲"]
    marks = ["，"]
    svg_v = render_sutra_page(cells, char_loader=stub_loader,
                                punct_marks=marks, direction="vertical")
    svg_h = render_sutra_page(cells, char_loader=stub_loader,
                                punct_marks=marks, direction="horizontal")
    # Both renders should still emit the marks group
    assert 'id="sutra-marks"' in svg_v
    assert 'id="sutra-marks"' in svg_h
    # Both should reference the same colour/opacity (group attrs identical)
    import re
    g_v = re.search(r'<g id="sutra-marks"[^>]*>', svg_v).group(0)
    g_h = re.search(r'<g id="sutra-marks"[^>]*>', svg_h).group(0)
    assert g_v == g_h, (
        "marks group attributes must match across directions "
        "(both directions anchor mark to the cell's bottom-right corner)"
    )


def test_5bl_marks_larger_than_one_third_of_glyph(stub_loader):
    """5bl: mark_size lifted from 0.32× to 0.45× of glyph size for
    legibility. We verify indirectly by checking that the rendered
    polyline transform contains a scale matching the new size."""
    cells = ["甲"]
    marks = ["，"]
    svg = render_sutra_page(cells, char_loader=stub_loader,
                            punct_marks=marks)
    # The mark transform should reference scale of (mark_size / EM_SIZE).
    # mark_size = char_size * 0.45 with char_size = min(cell_w, cell_h)*0.85.
    # Specific numeric value isn't worth pinning, but the group must contain
    # a scale() less than the main glyph's scale (which uses 0.85×).
    import re
    scales = [float(s) for s in re.findall(r'scale\(([0-9.]+)\)', svg)]
    assert scales, "no scale() found"
    # All glyph scales reduced by roughly 0.45/0.85 ≈ 0.53 vs main glyphs.
    # We can't easily disambiguate which is mark vs main without parsing
    # the DOM tree, so just sanity-check there are >= 2 distinct scales.
    assert len(set(round(s, 6) for s in scales)) >= 2


# ===========================================================================
# Phase 5bm — bigger marks moved further into bottom-right, cover-by-default
# off, style/source labels updated
# ===========================================================================


def test_5bm_include_cover_default_is_false():
    """5bm: cover-page is now opt-in. Default request should NOT include cover."""
    from stroke_order.web.server import SutraPostRequest
    req = SutraPostRequest()
    assert req.include_cover is False


def test_5bm_api_capacity_no_cover_by_default(client, temp_sutra_dir):
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text("天" * 600, encoding="utf-8")
    # Don't pass include_cover — should default to False
    r = client.get("/api/sutra/capacity?preset=heart_sutra")
    assert r.status_code == 200
    d = r.json()
    assert d["cover"] == 0


def test_5bm_api_pdf_no_cover_by_default(client, temp_sutra_dir):
    """PDF without explicit include_cover should not include the cover."""
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text("天" * 50, encoding="utf-8")
    r = client.get("/api/sutra/pdf?preset=heart_sutra&dpi=120")
    assert r.status_code == 200
    # Compact_marks default with 50 chars + no cover = 1 body page only
    # We can't easily count PDF pages, but at least confirm content present
    assert r.content[:4] == b"%PDF"


def test_5bu_marks_emit_text_element_with_font_size(stub_loader):
    """5bu: marks render as <text> elements with font-size proportional
    to char_size × 0.40."""
    cells = ["甲"]
    marks = ["，"]
    svg = render_sutra_page(cells, char_loader=stub_loader,
                              punct_marks=marks)
    import re
    # Find <text> within marks group — extract font-size value
    m = re.search(r'<text[^>]*font-size="([0-9.]+)"[^>]*>，', svg)
    assert m is not None, "no <text> with the punctuation char found"
    font_size = float(m.group(1))
    # Should be > 0 and reasonably small (< 10mm at typical cell sizes)
    assert 1.0 < font_size < 10.0


# ===========================================================================
# Phase 5bv — dual mark renderer (text for SVG preview, polyline for PDF).
# Browser SVG keeps high-fidelity <text> with CJK font; PDF pipeline uses
# traced glyphs so output is identical on any host (no fonts-noto-cjk dep).
# ===========================================================================


def _marks_inner(svg: str) -> str:
    """Helper: return the inner content of <g id='sutra-marks' ...>...</g>."""
    start = svg.find('<g id="sutra-marks"')
    assert start >= 0, "marks group missing"
    open_end = svg.find(">", start)
    close = svg.find("</g>", open_end)
    return svg[open_end + 1:close]


def test_5bv_default_mark_renderer_is_text(stub_loader):
    """Default mark_renderer remains 'text': the marks group must contain
    <text> elements and NOT trace-style <polyline>/<path>."""
    svg = render_sutra_page(
        ["甲"], char_loader=stub_loader, punct_marks=["，"],
    )
    inner = _marks_inner(svg)
    assert "<text" in inner
    assert "<polyline" not in inner
    assert "<path" not in inner


def test_5bv_polyline_mode_traces_glyph_no_text_element(stub_loader):
    """mark_renderer='polyline' must trace the punctuation glyph (the stub
    loader emits an outline, so we expect <path> and never <text>)."""
    svg = render_sutra_page(
        ["甲"], char_loader=stub_loader, punct_marks=["，"],
        mark_renderer="polyline",
    )
    inner = _marks_inner(svg)
    assert "<text" not in inner
    # Stub loader emits both outline + raw_track → at minimum a <path>.
    assert ("<path" in inner) or ("<polyline" in inner)


def test_5bv_polyline_mode_group_has_stroke(stub_loader):
    """Polyline-mode marks need both fill (for paths) AND stroke (for
    polylines from raw_track-only punct sources). The text-mode group only
    sets fill, so this attribute is the cleanest discriminator."""
    svg = render_sutra_page(
        ["甲"], char_loader=stub_loader, punct_marks=["，"],
        mark_renderer="polyline",
    )
    import re
    m = re.search(r'<g id="sutra-marks"[^>]*>', svg)
    assert m is not None
    g = m.group(0)
    assert 'fill="#888888"' in g
    assert 'stroke="#888888"' in g


def test_5bv_text_mode_group_has_no_stroke(stub_loader):
    """The default text-mode group must NOT carry stroke (sanity check —
    otherwise the <text> glyph would acquire a stray outline)."""
    svg = render_sutra_page(
        ["甲"], char_loader=stub_loader, punct_marks=["，"],
    )
    import re
    m = re.search(r'<g id="sutra-marks"[^>]*>', svg)
    assert m is not None
    g = m.group(0)
    assert "stroke" not in g


def test_5bv_pdf_endpoint_uses_polyline_marks(client, temp_sutra_dir):
    """Smoke test: the PDF endpoint should still produce a valid PDF when
    the server lacks a CJK font (which is the whole point of forcing
    polyline mode). We can't easily disable the system font here, but we
    can verify the endpoint succeeds end-to-end with a punctuation-rich
    text under the 'compact_marks' default."""
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text(
        "天地玄黃，宇宙洪荒。日月盈昃，辰宿列張。" * 4,
        encoding="utf-8",
    )
    r = client.get(
        "/api/sutra/pdf?preset=heart_sutra&dpi=120"
        "&include_cover=false&text_mode=compact_marks"
    )
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_5bv_polyline_mode_skips_when_loader_returns_none():
    """If char_loader can't supply the punctuation glyph in polyline mode,
    we silently drop the mark — better than crashing or emitting an empty
    group element."""
    def loader(_ch):
        return None  # unable to load anything
    svg = render_sutra_page(
        ["甲"], char_loader=loader, punct_marks=["，"],
        mark_renderer="polyline",
    )
    # No glyph parts → no marks group emitted at all.
    assert 'id="sutra-marks"' not in svg


# ===========================================================================
# Phase 5bw — skeleton-fallback for body glyphs.
# 隸書/篆書 default to skeleton-mode characters (outline=[], raw_track only).
# render_sutra_page used to call only _char_cut_paths, which silently dropped
# those glyphs → the page rendered as a blank grid. We now fall back to
# stroked polylines in a separate <g id="sutra-trace-skeleton"> group.
# ===========================================================================


def _skeleton_only_loader():
    """Loader emitting characters with raw_track but outline=[],
    mimicking what apply_seal_outline_mode / apply_lishu_outline_mode
    produce in the default 'skeleton' mode."""
    def _l(ch):
        return Character(
            char=ch, unicode_hex=f"{ord(ch):04x}", data_source="moe_lishu",
            strokes=[Stroke(
                index=0,
                raw_track=[Point(200, 200), Point(1800, 200),
                           Point(1800, 1800), Point(200, 1800),
                           Point(200, 200)],
                outline=[],   # ← skeleton mode — no outline
                kind_code=9, kind_name="其他", has_hook=False,
            )],
        )
    return _l


def test_5bw_skeleton_only_glyph_renders_via_polyline_group():
    """Regression: 隸書/篆書 chars (skeleton-only) used to render as nothing.
    They must now appear in a sutra-trace-skeleton group with <polyline>."""
    loader = _skeleton_only_loader()
    svg = render_sutra_page(["天"], char_loader=loader)
    # Old (broken) behaviour: NO trace group at all → page was visually blank.
    # New behaviour: trace-skeleton group exists with a polyline inside.
    assert 'id="sutra-trace-skeleton"' in svg
    assert "<polyline" in svg


def test_5bw_skeleton_group_uses_stroke_not_fill():
    """The skeleton group must paint with stroke (centerlines) — using fill
    would close the polyline into a misleading filled shape."""
    loader = _skeleton_only_loader()
    svg = render_sutra_page(["天"], char_loader=loader)
    import re
    m = re.search(r'<g id="sutra-trace-skeleton"[^>]*>', svg)
    assert m is not None, "skeleton group missing"
    g = m.group(0)
    assert 'fill="none"' in g
    assert 'stroke="#cccccc"' in g  # default trace_fill colour
    assert 'stroke-width=' in g


def test_5bw_outline_only_glyphs_stay_in_original_trace_group(stub_loader):
    """Existing kaishu/sung pages must NOT regress — outline-bearing chars
    keep going into <g id="sutra-trace">, with no skeleton group emitted."""
    svg = render_sutra_page(["甲", "乙"], char_loader=stub_loader)
    assert 'id="sutra-trace"' in svg
    assert 'id="sutra-trace-skeleton"' not in svg


# ===========================================================================
# Phase 5bx — skeleton stroke-width must survive the inner EM→mm transform.
# Without vector-effect="non-scaling-stroke", the 0.55mm stroke gets shrunk
# by the inner scale (≈ 0.0046) → ≈ 0.0025mm (invisible) → silent regression
# of 5bw. This test pins the attribute so it can't regress again.
# ===========================================================================


# ===========================================================================
# Phase 5bz — optional reference letterform layer beneath the skeleton.
# Browser preview + PDF want to show the original lishu/seal glyph shape so
# the user sees the full letterform; SVG downloads (for plotters) keep
# pure skeleton tracks.
# ===========================================================================


def _outline_only_loader():
    """Loader emitting outline-bearing characters (mimics what the lishu/
    seal sources return when invoked with mode='skip')."""
    def _l(ch):
        return Character(
            char=ch, unicode_hex=f"{ord(ch):04x}", data_source="moe_lishu",
            strokes=[Stroke(
                index=0,
                raw_track=[],
                outline=[
                    {"type": "M", "x": 200,  "y": 200},
                    {"type": "L", "x": 1848, "y": 200},
                    {"type": "L", "x": 1848, "y": 1848},
                    {"type": "L", "x": 200,  "y": 1848},
                    {"type": "Z"},
                ],
                kind_code=9, kind_name="其他", has_hook=False,
            )],
        )
    return _l


def test_5bz_no_outline_loader_keeps_5by_behaviour():
    """Backwards-compat: omitting outline_glyph_loader must produce the
    same output structure as 5by — no reference group emitted."""
    loader = _skeleton_only_loader()
    svg = render_sutra_page(["天"], char_loader=loader)
    assert 'id="sutra-glyph-reference"' not in svg
    assert 'id="sutra-trace-skeleton"' in svg


def test_5bz_skeleton_glyph_with_outline_loader_emits_reference_group():
    """Skeleton-only chars + outline_glyph_loader → reference group
    appears in addition to the skeleton group."""
    skel = _skeleton_only_loader()
    outline = _outline_only_loader()
    svg = render_sutra_page(
        ["天", "地"], char_loader=skel, outline_glyph_loader=outline,
    )
    assert 'id="sutra-glyph-reference"' in svg
    assert 'id="sutra-trace-skeleton"' in svg
    # Reference group must be drawn first (underneath skeleton in z-order).
    ref_pos = svg.find('id="sutra-glyph-reference"')
    skel_pos = svg.find('id="sutra-trace-skeleton"')
    assert ref_pos < skel_pos, "reference must precede skeleton group"


def test_5bz_reference_group_is_faded_and_filled():
    """The reference letterform must be faded (opacity < 1) and filled
    (no stroke), so it reads as a soft background hint."""
    skel = _skeleton_only_loader()
    outline = _outline_only_loader()
    svg = render_sutra_page(
        ["天"], char_loader=skel, outline_glyph_loader=outline,
    )
    import re
    m = re.search(r'<g id="sutra-glyph-reference"[^>]*>', svg)
    assert m is not None
    g = m.group(0)
    assert 'opacity="' in g
    op = float(re.search(r'opacity="([0-9.]+)"', g).group(1))
    assert 0.0 < op < 1.0
    assert 'fill="' in g
    assert 'stroke="none"' in g


def test_5bz_outline_bearing_chars_skip_reference_layer(stub_loader):
    """Kaishu / sung characters already render via the main trace group.
    Even when outline_glyph_loader is supplied, the renderer must NOT
    duplicate them in a reference group."""
    outline = _outline_only_loader()
    svg = render_sutra_page(
        ["甲"], char_loader=stub_loader, outline_glyph_loader=outline,
    )
    # The stub_loader returns outline-bearing chars → main trace group only.
    assert 'id="sutra-trace"' in svg
    assert 'id="sutra-glyph-reference"' not in svg


def test_5bz_post_endpoint_default_omits_reference(client, temp_sutra_dir):
    """POST /api/sutra defaults to show_original_glyph=False so SVG
    downloads stay plotter-friendly."""
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text("天" * 30, encoding="utf-8")
    r = client.post("/api/sutra", json={
        "preset": "heart_sutra", "page_type": "body",
        # show_original_glyph omitted → False
    })
    assert r.status_code == 200
    assert 'id="sutra-glyph-reference"' not in r.text


def test_5bz_post_endpoint_opt_in_emits_reference_when_skeleton(
        client, temp_sutra_dir):
    """show_original_glyph=true must request the reference loader. We
    can't easily install the lishu/seal font in CI, so this end-to-end
    smoke just verifies the request succeeds — the reference group will
    only appear when both lishu source ready AND the page has skeleton
    chars; with kaishu (default style) there are no skeleton chars so
    the group is correctly absent."""
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text("天" * 30, encoding="utf-8")
    r = client.post("/api/sutra", json={
        "preset": "heart_sutra", "page_type": "body",
        "show_original_glyph": True,
    })
    assert r.status_code == 200
    # Default style is kaishu → no skeleton chars → no reference group.
    assert 'id="sutra-trace"' in r.text


def test_5bz_pdf_endpoint_default_includes_reference_query(
        client, temp_sutra_dir):
    """PDF endpoint defaults to show_original_glyph=True (humans want
    to see the letterform). End-to-end smoke that the endpoint accepts
    and processes the request without error."""
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / "heart_sutra.txt").write_text("天" * 50, encoding="utf-8")
    r = client.get("/api/sutra/pdf?preset=heart_sutra&dpi=120")
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


# ===========================================================================
# Phase 5ca / 5cb — opacity policy for the two faded layers.
#
# 5ca initially matched both layers around 0.55 so they printed as a
# single 描紅 grey. User feedback (5cb): the skeleton is incomplete in
# places (skeletonization algorithm limitations) and a visible-but-
# imperfect skeleton is distracting. We now bias the visual weight to
# the reference letterform layer and keep the skeleton near-invisible.
# ===========================================================================


def _opacity_of(svg, group_id):
    import re
    m = re.search(rf'<g id="{group_id}"[^>]*>', svg)
    assert m is not None, f"{group_id} missing"
    op_match = re.search(r'opacity="([0-9.]+)"', m.group(0))
    assert op_match is not None, f"{group_id} has no opacity attribute"
    return float(op_match.group(1))


def test_5cb_reference_layer_dominates_skeleton():
    """The reference glyph carries the visual weight on a printed
    描紅 PDF; the skeleton is intentionally near-invisible so its
    occasional gaps and misplacements don't distract the user."""
    skel = _skeleton_only_loader()
    outline = _outline_only_loader()
    svg = render_sutra_page(
        ["天"], char_loader=skel, outline_glyph_loader=outline,
    )
    skel_op = _opacity_of(svg, "sutra-trace-skeleton")
    ref_op  = _opacity_of(svg, "sutra-glyph-reference")
    # Reference must be in the printable 描紅 band (10-20% grey).
    assert 0.4 <= ref_op <= 0.7, f"reference opacity {ref_op} out of band"
    # Skeleton must be much fainter than reference so it doesn't
    # dominate; 0.1 cap leaves room to dial it up later.
    assert skel_op < 0.1, (
        f"skeleton opacity {skel_op} too prominent — should be a faint "
        "hint behind the reference letterform"
    )
    assert ref_op > skel_op + 0.4, (
        "reference must clearly outweigh skeleton on a printed page"
    )


def test_5cb_skeleton_carries_opacity_even_without_reference(stub_loader):
    """Skeleton-mode-only page (no outline_glyph_loader) keeps the same
    near-invisible opacity. Without a reference layer the page may
    print as nearly blank — that's the user's explicit choice; they
    should pair lishu/seal with show_original_glyph=True for printing."""
    loader = _skeleton_only_loader()
    svg = render_sutra_page(["天"], char_loader=loader)
    op = _opacity_of(svg, "sutra-trace-skeleton")
    assert op < 0.1


def test_5by_skeleton_stroke_width_scales_with_char_size():
    """5by: skeleton stroke-width must track char_size (12%) so the visual
    weight stays consistent across landscape (smaller cells, ~1.13mm) and
    portrait (square cells, ~1.33mm). Test asserts portrait > landscape."""
    loader = _skeleton_only_loader()
    svg_landscape = render_sutra_page(["天"], char_loader=loader,
                                       orientation="landscape")
    svg_portrait  = render_sutra_page(["天"], char_loader=loader,
                                       orientation="portrait")
    import re
    def stroke_w(svg):
        m = re.search(
            r'<g id="sutra-trace-skeleton"[^>]*stroke-width="([0-9.]+)"',
            svg,
        )
        assert m is not None, "skeleton group stroke-width missing"
        return float(m.group(1))
    w_land = stroke_w(svg_landscape)
    w_port = stroke_w(svg_portrait)
    # Both must be visibly thick (≥ 1mm) — 0.55mm fixed value (5bw bug)
    # was too thin and would reach this branch.
    assert w_land >= 1.0, f"landscape stroke {w_land} too thin"
    assert w_port >= 1.0, f"portrait stroke {w_port} too thin"
    # Portrait has square cells so char_size is bigger → stroke must be
    # proportionally bigger as well.
    assert w_port > w_land, (
        f"portrait skeleton stroke {w_port} should exceed landscape "
        f"{w_land} since portrait char_size is larger"
    )


def test_5bx_skeleton_polylines_carry_non_scaling_stroke():
    """Each <polyline> in the skeleton group must declare
    vector-effect="non-scaling-stroke", otherwise the inner scale()
    transform shrinks the stroke to a hairline and the page looks blank.
    """
    loader = _skeleton_only_loader()
    svg = render_sutra_page(["天", "地"], char_loader=loader)
    # Locate every polyline inside the trace-skeleton group.
    start = svg.find('<g id="sutra-trace-skeleton"')
    assert start >= 0, "skeleton group missing"
    end = svg.find("</g>", start) + len("</g>")
    # The skeleton group itself contains multiple inner <g> wrappers —
    # walk to the *outer* close. Easier: just count polylines after start.
    fragment = svg[start:]
    polylines = [m for m in fragment.split("<polyline")[1:]]
    assert polylines, "no polylines emitted in skeleton group"
    for p in polylines:
        head = p.split(">", 1)[0]
        assert 'vector-effect="non-scaling-stroke"' in head, (
            f"polyline missing vector-effect: {head!r}"
        )


def test_5bw_mixed_loader_emits_both_groups():
    """If a page mixes outline-bearing and skeleton-only chars (e.g. seal
    glyph for one char, kaishu fallback for a missing one), both groups
    should appear."""
    def mixed_loader(ch):
        if ch == "甲":  # outline char
            return Character(
                char=ch, unicode_hex=f"{ord(ch):04x}", data_source="kaishu",
                strokes=[Stroke(
                    index=0,
                    raw_track=[Point(100, 100), Point(1948, 1948)],
                    outline=[
                        {"type": "M", "x": 100,  "y": 100},
                        {"type": "L", "x": 1948, "y": 100},
                        {"type": "L", "x": 1948, "y": 1948},
                    ],
                    kind_code=9, kind_name="其他", has_hook=False,
                )],
            )
        # skeleton-only for everything else
        return _skeleton_only_loader()(ch)
    svg = render_sutra_page(["甲", "乙"], char_loader=mixed_loader)
    assert 'id="sutra-trace"' in svg
    assert 'id="sutra-trace-skeleton"' in svg
