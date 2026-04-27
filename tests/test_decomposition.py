"""Tests for the 5000.TXT decomposition DB parser."""
import pytest

from stroke_order.decomposition import (
    Decomposition,
    DecompositionDB,
    _parse_line,
    default_db,
)


@pytest.fixture(scope="module")
def db() -> DecompositionDB:
    return default_db()


def test_db_size(db):
    assert len(db) > 3000  # expect ~3,700+


def test_ming_compound(db):
    """明 = 日 + 月."""
    d = db.get("明")
    assert d is not None
    assert d.char == "明"
    assert d.category == "會意"
    assert d.head_root == "日"
    assert d.head_role == "體"
    assert d.tail_root == "月"
    assert d.tail_role == "體"
    assert "明顯" in d.concept
    assert not d.is_atom


def test_ai_compound(db):
    """愛 = 受 + 心."""
    d = db.get("愛")
    assert d is not None
    assert d.head_root == "受"
    assert d.tail_root == "心"


def test_pictograph_atom(db):
    """永 is a 象形 atom (no head/tail)."""
    d = db.get("永")
    assert d is not None
    assert d.is_atom
    assert d.category.startswith("象形")
    assert d.head_root is None
    assert d.tail_root is None


def test_missing_char_returns_none(db):
    """A char NOT in 5000.TXT should return None, not raise."""
    # 恩 is genuinely missing from this draft dataset
    assert db.get("恩") is None
    # Private Use Area — never in any dataset
    assert db.get("\ue000") is None


def test_parse_prelude_format():
    """Prelude uses fullwidth spaces + Ａ/Ｂ/ａ/ｂ role markers."""
    line = "【明】　＠－甲骨　　　首［日］Ａ太陽。　　　　　　　尾［月］Ｂ月亮。　　　　　　有光之日月，可見可知，明顯。"
    d = _parse_line(line)
    assert d is not None
    assert d.char == "明"
    assert d.category == "會意"
    assert d.head_root == "日"
    assert d.head_role == "體"
    assert d.tail_root == "月"
    assert d.tail_role == "體"


def test_parse_appendix_format():
    """Appendix uses tabs + 體/用 explicit role labels."""
    line = "【唱】\t首［口］體－説話的通道。\t尾［昌］用－旺盛。\t\t會意－小篆\t口發出旺盛之聲。"
    d = _parse_line(line)
    assert d is not None
    assert d.char == "唱"
    assert d.head_root == "口"
    assert d.tail_root == "昌"
    assert d.tail_role == "用"
    assert d.category == "會意"


def test_parse_non_entry_returns_none():
    for non_entry in ["", "\n", "some prose text", "六、利用程式攝製動畫"]:
        assert _parse_line(non_entry) is None


def test_decomposition_summary_atom():
    d = Decomposition(char="日", category="象形", earliest_form="甲骨",
                      concept="太陽")
    assert d.is_atom
    s = d.summary()
    assert "日" in s and "太陽" in s
    assert "象形" in s


def test_decomposition_summary_compound():
    d = Decomposition(
        char="明", category="會意", earliest_form="甲骨",
        head_root="日", head_role="體", head_def="太陽",
        tail_root="月", tail_role="體", tail_def="月亮",
        concept="明顯",
    )
    assert not d.is_atom
    s = d.summary()
    assert "首[日]" in s and "尾[月]" in s
