"""Web API tests for Phase 5a new endpoints."""
import io

import pytest

try:
    from fastapi.testclient import TestClient
    from PIL import Image, ImageDraw
    from stroke_order.web.server import create_app
    _HAS = True
except ImportError:
    _HAS = False

pytestmark = pytest.mark.skipif(not _HAS, reason="web deps missing")


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_notebook_short_text_single_page(client):
    r = client.get("/api/notebook?text=春眠不覺曉&preset=small")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]
    assert r.headers.get("x-stroke-order-pages") == "1"


def test_notebook_long_text_returns_zip(client):
    long_text = "一日月水火土" * 30
    r = client.get(f"/api/notebook?text={long_text}&preset=small")
    assert r.status_code == 200
    # Should be ZIP or multi-page
    pages = int(r.headers.get("x-stroke-order-pages", "1"))
    if pages > 1:
        assert "application/zip" in r.headers["content-type"]


def test_notebook_single_page_query(client):
    r = client.get(
        "/api/notebook?text=" + ("一" * 200) + "&preset=small&page=1"
    )
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]


def test_notebook_page_out_of_range(client):
    r = client.get("/api/notebook?text=一&preset=small&page=99")
    assert r.status_code == 404


def test_notebook_all_grid_styles(client):
    for g in ("square", "ruled", "dotted", "none"):
        r = client.get(f"/api/notebook?text=一&preset=small&grid_style={g}")
        assert r.status_code == 200


def test_letter_basic(client):
    r = client.get(
        "/api/letter?text=敬啟者&preset=A5&title_text=致老友"
    )
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]


def test_letter_multi_page(client):
    text = "春" * 300
    r = client.get(f"/api/letter?text={text}&preset=A5")
    assert r.status_code == 200
    pages = int(r.headers.get("x-stroke-order-pages", "1"))
    assert pages >= 1


def test_doodle_accepts_image(client):
    img = Image.new("RGB", (200, 200), "white")
    ImageDraw.Draw(img).ellipse([30, 30, 170, 170], outline="black", width=4)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    r = client.post(
        "/api/doodle",
        files={"image": ("test.png", buf, "image/png")},
    )
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]


def test_doodle_invalid_image(client):
    r = client.post(
        "/api/doodle",
        files={"image": ("bogus.txt", b"not an image", "text/plain")},
    )
    assert r.status_code == 400


def test_doodle_with_annotations_json(client):
    img = Image.new("RGB", (100, 100), "white")
    ImageDraw.Draw(img).rectangle([20, 20, 80, 80], outline="black", width=3)
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    import json
    anns = [{"text": "ANNOTATE", "x_mm": 10, "y_mm": 10, "size_mm": 4}]
    r = client.post(
        "/api/doodle",
        data={"annotations_json": json.dumps(anns)},
        files={"image": ("test.png", buf, "image/png")},
    )
    assert r.status_code == 200
    assert "ANNOTATE" in r.text


def test_index_has_all_5_modes(client):
    r = client.get("/")
    assert r.status_code == 200
    for m in ("單字模式", "字帖模式", "筆記模式", "信紙模式", "塗鴉模式"):
        assert m in r.text, f"missing mode: {m}"
    for mid in ("notebook-view", "letter-view", "doodle-view"):
        assert mid in r.text
