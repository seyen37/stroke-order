"""Tests for 繁↔簡 variant fallback in decomposition lookup."""
from stroke_order.decomposition import default_db
from stroke_order.variants import to_simplified, to_traditional, variants_of


def test_to_simplified_obvious_pair():
    assert to_simplified("溫") == "温"
    assert to_simplified("國") == "国"
    assert to_simplified("愛") == "爱"


def test_to_traditional_obvious_pair():
    assert to_traditional("温") == "溫"
    assert to_traditional("国") == "國"


def test_variants_of_returns_alternates_only():
    v = variants_of("溫")
    assert "温" in v
    assert "溫" not in v  # exclude the original


def test_variants_of_returns_empty_for_invariant():
    # 永 is the same in trad and simp — no variants to suggest
    assert variants_of("永") == []


def test_db_fallback_trad_to_simp():
    """溫 (trad) isn't in 5000.TXT but 温 (simp) is."""
    db = default_db()
    d = db.get("溫")
    assert d is not None
    # Returned obj should carry the QUERIED char (溫), not dataset's (温)
    assert d.char == "溫"
    # But the decomposition info should match 温's
    assert d.head_root == "水"
    assert d.tail_root == "昷"


def test_db_fallback_simp_to_trad():
    """国 (simp) isn't directly in DB; 國 (trad) is → fallback works."""
    db = default_db()
    d = db.get("国")
    assert d is not None
    assert d.char == "国"  # preserved
    assert d.tail_root == "或"


def test_db_no_fallback_when_disabled():
    db = default_db()
    d = db.get("溫", try_variants=False)
    assert d is None  # strict lookup respects the flag


def test_db_contains_uses_variants():
    db = default_db()
    assert "溫" in db
    assert "国" in db


def test_db_genuinely_missing():
    """Some chars aren't in the 5000 draft at all, even via variants."""
    db = default_db()
    # 慰 has no 繁簡 variant AND isn't in DB
    assert db.get("慰") is None
