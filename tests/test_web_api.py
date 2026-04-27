"""Integration tests for the FastAPI Web UI."""
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
def client():
    return TestClient(create_app())


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert b"stroke-order" in r.content


def test_character_endpoint(client):
    r = client.get("/api/character/永")
    assert r.status_code == 200
    d = r.json()
    assert "strokes" in d and "medians" in d
    assert len(d["strokes"]) == 5
    assert len(d["medians"]) == 5


def test_meta_endpoint(client):
    r = client.get("/api/meta/永")
    assert r.status_code == 200
    d = r.json()
    assert d["character"] == "永"
    assert d["stroke_count"] == 5
    assert "validation" in d
    assert d["validation"]["is_valid"] is True


def test_export_svg(client):
    r = client.get("/api/export/永?format=svg")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]
    assert b"<svg" in r.content
    assert "filename*=UTF-8''" in r.headers.get("content-disposition", "")


def test_export_gcode_custom_params(client):
    r = client.get("/api/export/永?format=gcode&char_size=40&feed_rate=2000")
    assert r.status_code == 200
    # char_size 40 should produce coords up to around 40-50mm
    body = r.content.decode("utf-8")
    assert "F2000" in body  # feed rate respected
    assert "M3" in body and "M5" in body  # pen up/down


def test_export_json(client):
    r = client.get("/api/export/永?format=json")
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"]


def test_bad_char_length(client):
    r = client.get("/api/character/兩字")
    assert r.status_code == 400


def test_invalid_format(client):
    r = client.get("/api/export/永?format=doc")
    assert r.status_code == 422  # FastAPI pattern validation


def test_invalid_source(client):
    r = client.get("/api/character/永?source=bogus")
    assert r.status_code == 400


def test_hook_policy_changes_output(client):
    """日's stroke 2 should have different median lengths under each policy."""
    r_anim = client.get("/api/character/日?hook_policy=animation").json()
    r_stat = client.get("/api/character/日?hook_policy=static").json()
    # stroke 2 (index 1) — the 橫折鉤
    assert len(r_anim["medians"][1]) != len(r_stat["medians"][1])
