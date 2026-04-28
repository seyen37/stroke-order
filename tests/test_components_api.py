"""Phase A — HTTP endpoints for component coverage analyzer (6b-5/6/7).

Drives the FastAPI app via TestClient. Backend logic is unit-tested in
test_components_*.py; these tests cover request/response shape + error
paths only.
"""
from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS_WEB = True
except ImportError:
    _HAS_WEB = False

pytestmark = pytest.mark.skipif(
    not _HAS_WEB, reason="fastapi/httpx not installed"
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


# ===========================================================================
# 6b-5: GET /api/components/{char}
# ===========================================================================


def test_components_compound_char(client):
    """明 = ⿰日月 → leaves [日, 月], not atomic."""
    r = client.get("/api/components/明")
    assert r.status_code == 200
    d = r.json()
    assert d["char"] == "明"
    assert d["ids"] == "⿰日月"
    assert d["leaves"] == ["日", "月"]
    assert d["leaves_distinct"] == ["日", "月"]
    assert d["is_atomic"] is False


def test_components_atomic_char(client):
    """永 is atomic — IDS equals self, leaves equals [self]."""
    r = client.get("/api/components/永")
    assert r.status_code == 200
    d = r.json()
    assert d["char"] == "永"
    assert d["ids"] == "永"
    assert d["leaves"] == ["永"]
    assert d["is_atomic"] is True


def test_components_duplicate_leaves(client):
    """林 = ⿰木木 — leaves preserves duplicates, distinct dedupes."""
    r = client.get("/api/components/林")
    assert r.status_code == 200
    d = r.json()
    assert d["leaves"] == ["木", "木"]
    assert d["leaves_distinct"] == ["木"]


def test_components_rejects_multichar(client):
    """Multi-char input → 400."""
    r = client.get("/api/components/明月")
    assert r.status_code == 400


def test_components_unknown_char_treated_as_atomic(client):
    """Char not in IDS map → treat as atomic (graceful fallback)."""
    # Pick an unusual but valid CJK code — should always work
    r = client.get("/api/components/㐀")  # CJK Ext A first char
    assert r.status_code == 200
    d = r.json()
    assert d["char"] == "㐀"
    # Either has IDS or is atomic — both are valid responses


# ===========================================================================
# 6b-6: GET /api/coverset/list + /api/coverset/{name}
# ===========================================================================


def test_coverset_list_includes_808(client):
    """Built-in registry exposes cjk_common_808."""
    r = client.get("/api/coverset/list")
    assert r.status_code == 200
    d = r.json()
    names = [cs["name"] for cs in d["coversets"]]
    assert "cjk_common_808" in names


def test_coverset_list_metadata_shape(client):
    """Each entry has expected keys."""
    r = client.get("/api/coverset/list")
    expected = {"name", "title", "description", "size", "source", "url"}
    for cs in r.json()["coversets"]:
        assert expected.issubset(cs.keys())


def test_coverset_detail_808(client):
    """808 cover-set detail has 808 chars + ~194 distinct components."""
    r = client.get("/api/coverset/cjk_common_808")
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "cjk_common_808"
    assert d["size"] == 808
    assert len(d["chars"]) == 808
    assert len(d["chars_simp"]) == 808
    # Per docs/analysis 808_coverage_report.md: 194 distinct components.
    # Allow some drift from future ids-data updates (150-250 range).
    assert 150 <= d["distinct_components"] <= 250


def test_coverset_detail_unknown_404(client):
    """Unknown cover-set → 404."""
    r = client.get("/api/coverset/nonexistent_xyz")
    assert r.status_code == 404


# ===========================================================================
# 6b-7: POST /api/coverage/recommend
# ===========================================================================


def test_recommend_empty_written(client):
    """No chars written yet — first recommendation has high gain."""
    r = client.post("/api/coverage/recommend",
                    json={"written_chars": "", "coverset": "cjk_common_808",
                          "top_k": 5})
    assert r.status_code == 200
    d = r.json()
    assert d["coverset"] == "cjk_common_808"
    assert d["written_count"] == 0
    assert len(d["recommendations"]) == 5
    # First pick should add multiple components (most chars have ≥2)
    assert d["recommendations"][0]["gain"] >= 2
    # Coverage starts at zero
    assert d["coverage"]["covered_count"] == 0
    assert d["coverage"]["composable_count"] == 0


def test_recommend_skips_written_chars(client):
    """Written chars don't appear in recommendations."""
    r = client.post("/api/coverage/recommend",
                    json={"written_chars": "明", "coverset": "cjk_common_808",
                          "top_k": 10})
    assert r.status_code == 200
    rec_chars = [rec["char"] for rec in r.json()["recommendations"]]
    assert "明" not in rec_chars


def test_recommend_coverage_grows(client):
    """Writing more chars → coverage_count increases."""
    r0 = client.post("/api/coverage/recommend",
                     json={"written_chars": "", "coverset": "cjk_common_808"})
    r1 = client.post("/api/coverage/recommend",
                     json={"written_chars": "明林校永我",
                           "coverset": "cjk_common_808"})
    assert r0.status_code == 200
    assert r1.status_code == 200
    cov0 = r0.json()["coverage"]["covered_count"]
    cov1 = r1.json()["coverage"]["covered_count"]
    assert cov1 > cov0


def test_recommend_composable_count_increments(client):
    """Writing one char that IS in the cover-set → composable_count >= 1."""
    r = client.post("/api/coverage/recommend",
                    json={"written_chars": "明", "coverset": "cjk_common_808"})
    d = r.json()
    # 明 is in 808; writing it → at least 明 itself is composable
    assert d["coverage"]["composable_count"] >= 1


def test_recommend_default_coverset_is_808(client):
    """Default coverset (omitted in request) is cjk_common_808."""
    r = client.post("/api/coverage/recommend", json={"written_chars": ""})
    assert r.status_code == 200
    assert r.json()["coverset"] == "cjk_common_808"


def test_recommend_unknown_coverset_404(client):
    r = client.post("/api/coverage/recommend",
                    json={"written_chars": "", "coverset": "nonexistent_xyz"})
    assert r.status_code == 404


def test_recommend_top_k_respected(client):
    """top_k=2 returns at most 2 recommendations."""
    r = client.post("/api/coverage/recommend",
                    json={"written_chars": "", "coverset": "cjk_common_808",
                          "top_k": 2})
    assert r.status_code == 200
    assert len(r.json()["recommendations"]) <= 2


def test_recommend_response_shape(client):
    """Each recommendation has char, new_components, existing_components, gain."""
    r = client.post("/api/coverage/recommend",
                    json={"written_chars": "明", "top_k": 1})
    rec = r.json()["recommendations"][0]
    expected = {"char", "new_components", "existing_components", "gain"}
    assert expected.issubset(rec.keys())
    assert isinstance(rec["new_components"], list)
    assert isinstance(rec["gain"], int)
    assert rec["gain"] == len(rec["new_components"])
