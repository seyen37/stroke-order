"""
Phase 5ap — CNS canonical stroke sequence parser.

Covers ``CNSStrokes`` (file parsing + Unicode reverse lookup) and the
``/api/cns-stroke-diagnostics/{char}`` endpoint that compares the
canonical N-stroke spec against the actual skeletonisation output.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from stroke_order.sources.cns_strokes import CNSStrokes, STROKE_NAMES


_PROPS_DIR = Path("/tmp/cns11643")


def _props_available() -> bool:
    return (_PROPS_DIR / "CNS_strokes_sequence.txt").exists()


needs_props = pytest.mark.skipif(
    not _props_available(),
    reason="CNS Properties absent; extract Properties.zip to /tmp/cns11643",
)


# ---------------------------------------------------------------------------
# Graceful fallback when the data file is missing
# ---------------------------------------------------------------------------


def test_not_ready_when_dir_missing(tmp_path):
    s = CNSStrokes(properties_dir=tmp_path / "nope")
    assert s.is_ready() is False
    assert s.canonical_strokes("永") == []
    assert s.canonical_count("永") == 0


def test_canonical_strokes_rejects_multi_char(tmp_path):
    s = CNSStrokes(properties_dir=tmp_path)
    assert s.canonical_strokes("abc") == []
    assert s.canonical_strokes("") == []


def test_stroke_names_table_complete():
    """All 5 codes 1-5 must be named — the spec is fixed."""
    for code in (1, 2, 3, 4, 5):
        assert code in STROKE_NAMES
        assert STROKE_NAMES[code]   # non-empty


# ---------------------------------------------------------------------------
# Real-data correctness (skipped if Properties not extracted)
# ---------------------------------------------------------------------------


@needs_props
def test_canonical_strokes_for_known_chars():
    s = CNSStrokes(properties_dir=_PROPS_DIR)
    # Hand-verified sequences from CNS_strokes_sequence.txt.
    cases = {
        "永": [4, 5, 5, 3, 4],   # 5 strokes
        "一": [1],
        "十": [1, 2],
        "大": [1, 3, 4],
    }
    for ch, expected in cases.items():
        assert s.canonical_strokes(ch) == expected, f"mismatch for {ch}"


@needs_props
def test_canonical_count_matches_length():
    s = CNSStrokes(properties_dir=_PROPS_DIR)
    for ch in "一永書學":
        assert s.canonical_count(ch) == len(s.canonical_strokes(ch))


@needs_props
def test_canonical_names_resolve_to_chinese():
    s = CNSStrokes(properties_dir=_PROPS_DIR)
    names = s.canonical_names("永")
    assert names == ["點", "折", "折", "撇", "點"]


@needs_props
def test_unknown_codepoint_returns_empty():
    s = CNSStrokes(properties_dir=_PROPS_DIR)
    # Emoji / Latin → not in CNS
    assert s.canonical_strokes("\U0001F600") == []
    assert s.canonical_strokes("Z") == []


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
def client():
    if not _HAS:
        pytest.skip("web deps missing")
    return TestClient(create_app())


def test_api_diagnostics_rejects_multi_char(client):
    r = client.get("/api/cns-stroke-diagnostics/abc")
    assert r.status_code == 400


def test_api_diagnostics_unknown_char(client):
    """Emoji has no CNS data — diagnostics returns empty fields, not 404."""
    r = client.get("/api/cns-stroke-diagnostics/\U0001F600")
    assert r.status_code == 200
    d = r.json()
    assert d["canonical_count"] == 0
    assert d["canonical_types"] == []


@needs_props
def test_api_diagnostics_known_char(client):
    """End-to-end: 永 should report canonical=5 (regardless of skel state)."""
    r = client.get("/api/cns-stroke-diagnostics/永")
    assert r.status_code == 200
    d = r.json()
    assert d["canonical_count"] == 5
    assert d["canonical_types"] == [4, 5, 5, 3, 4]
    assert d["canonical_names"] == ["點", "折", "折", "撇", "點"]
    assert "actual_polyline_count" in d
    assert "mismatch" in d
    assert isinstance(d["mismatch"], bool)
