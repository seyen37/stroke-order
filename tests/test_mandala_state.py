"""Phase 5b r27: .mandala.md 檔案 schema 驗證測試。

實際 export/import 邏輯在前端 JS（純客戶端、不上傳伺服器）。
這支 test 用 PyYAML 驗證：
- Fixture file 的結構符合 schema spec
- 必要欄位齊全、類型正確
- Migration table 命名一致

未來 r28 server-side gallery 會用到這個 schema parser，
所以保留 Python 端可解析能力很重要。
"""

import pathlib
import re

import pytest
import yaml

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "sample.mandala.md"
EXPECTED_SCHEMA = "stroke-order-mandala-v1"


def _split_frontmatter(text: str) -> tuple[str, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    assert m, "fixture missing frontmatter"
    return m.group(1), m.group(2)


@pytest.fixture
def fixture_md() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def fixture_state(fixture_md: str) -> dict:
    fm, _ = _split_frontmatter(fixture_md)
    return yaml.safe_load(fm)


def test_fixture_file_exists(fixture_md):
    assert "---" in fixture_md
    assert "schema: stroke-order-mandala-v1" in fixture_md


def test_frontmatter_valid_yaml(fixture_state):
    assert isinstance(fixture_state, dict)
    assert fixture_state["schema"] == EXPECTED_SCHEMA


def test_top_level_sections_present(fixture_state):
    """schema spec 要求的 top-level keys 全部存在。"""
    required = {"schema", "exported_at", "generator", "metadata",
                "canvas", "center", "ring", "mandala", "extra_layers", "style"}
    actual = set(fixture_state.keys())
    missing = required - actual
    assert not missing, f"missing top-level: {missing}"


def test_metadata_required_fields(fixture_state):
    m = fixture_state["metadata"]
    for key in ("id", "title", "title_pinyin", "design_note",
                "author", "created_at", "modified_at"):
        assert key in m, f"metadata missing: {key}"
    # title 跟 title_pinyin 應該都是字串（即使空）
    assert isinstance(m["title"], str)
    assert isinstance(m["title_pinyin"], str)
    # title_pinyin 應該只含 [a-z0-9-]
    if m["title_pinyin"]:
        assert re.match(r"^[a-z0-9-]+$", m["title_pinyin"]), \
            f"bad slug: {m['title_pinyin']}"


def test_canvas_section(fixture_state):
    c = fixture_state["canvas"]
    assert isinstance(c["size_mm"], (int, float))
    assert isinstance(c["page_width_mm"], (int, float))
    assert isinstance(c["page_height_mm"], (int, float))


def test_center_section_char_type(fixture_state):
    ce = fixture_state["center"]
    assert ce["type"] in ("char", "icon", "empty")
    assert "text" in ce
    assert "line_color" in ce
    assert re.match(r"^#[0-9a-fA-F]{6}$", ce["line_color"])


def test_ring_section_complete(fixture_state):
    r = fixture_state["ring"]
    for key in ("text", "size_mm", "spacing", "orientation",
                "auto_shrink", "shrink_safety_margin",
                "protect_chars", "protect_radius_factor", "line_color"):
        assert key in r, f"ring missing: {key}"
    assert r["orientation"] in (
        "bottom_to_center", "top_to_center", "upright", "tangent")


def test_mandala_section_complete(fixture_state):
    md = fixture_state["mandala"]
    assert md["style"] in (
        "interlocking_arcs", "lotus_petal", "radial_rays")
    assert md["composition_scheme"] in (
        "vesica", "inscribed", "freeform")
    assert md["n_fold"] is None or isinstance(md["n_fold"], int)
    assert isinstance(md["show"], bool)
    assert re.match(r"^#[0-9a-fA-F]{6}$", md["line_color"])


def test_extra_layers_structure(fixture_state):
    layers = fixture_state["extra_layers"]
    assert isinstance(layers, list)
    for layer in layers:
        # 必要欄位
        for key in ("ring", "style", "n_fold", "r_mm", "color", "visible"):
            assert key in layer, f"layer missing: {key}"
        assert isinstance(layer["ring"], int)
        assert layer["ring"] >= 0
        assert layer["ring"] <= 10  # MD_RING_MAX - 1
        assert isinstance(layer["n_fold"], int)
        assert isinstance(layer["r_mm"], (int, float))
        assert layer["r_mm"] >= 0
        assert re.match(r"^#[0-9a-fA-F]{6}$", layer["color"])
        assert isinstance(layer["visible"], bool)


def test_pinyin_slug_format(fixture_state):
    """拼音 slug 應該是 lowercase + hyphen-separated 形式。"""
    slug = fixture_state["metadata"]["title_pinyin"]
    if slug:
        assert slug == slug.lower(), "slug must be lowercase"
        assert " " not in slug, "slug must not have spaces"
        assert not slug.startswith("-")
        assert not slug.endswith("-")
        assert "--" not in slug


def test_inline_pinyin_comment_present(fixture_md):
    """fixture 應該有 inline comment `# 拼音: ...` 註解，方便人讀。"""
    assert re.search(r"#\s*拼音[:：]\s*\S+", fixture_md), \
        "fixture should have inline pinyin comment next to title"


def test_body_section_present(fixture_md):
    """body 應有 ## 視覺概觀 + ## 設計意圖 兩 section。"""
    _, body = _split_frontmatter(fixture_md)
    assert "## 視覺概觀" in body
    assert "## 設計意圖" in body


def test_round_trip_preserves_structure(fixture_state):
    """state → yaml.dump → yaml.load 後結構等價。"""
    dumped = yaml.dump(fixture_state, allow_unicode=True, sort_keys=False)
    reloaded = yaml.safe_load(dumped)
    assert reloaded == fixture_state


def test_schema_known_in_migration_table(fixture_state):
    """fixture schema 必須在已知 migration table 中（v1 是當前唯一）。"""
    known = {"stroke-order-mandala-v1"}
    assert fixture_state["schema"] in known, \
        f"unknown schema: {fixture_state['schema']}"
