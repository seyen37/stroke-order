"""
Phase 5ak — user dictionary (rare / coined / new characters).

Covers:

- ``UserDictSource`` save / load / list / delete with the
  ``STROKE_ORDER_USER_DICT_DIR`` env var pointing at a tmp dir.
- AutoSource / RegionAutoSource priority — user-dict wins over g0v.
- ``handwriting_to_strokes`` and ``svg_to_strokes`` normalization helpers.
- ``/api/user-dict`` CRUD endpoints with all three input formats.
- ``_load`` bypass for ``data_source == "user"``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from stroke_order.ir import Character
from stroke_order.sources import (
    AutoSource, CharacterNotFound, UserDictSource,
    default_user_dict_dir,
)
from stroke_order.sources.user_dict import (
    handwriting_to_strokes, svg_to_strokes,
)


# ---------------------------------------------------------------------------
# Tmp-dir fixture so we never touch real ~/.stroke-order/
# ---------------------------------------------------------------------------


@pytest.fixture
def user_dict_dir(tmp_path, monkeypatch):
    d = tmp_path / "user-dict"
    monkeypatch.setenv("STROKE_ORDER_USER_DICT_DIR", str(d))
    return d


# ---------------------------------------------------------------------------
# UserDictSource — basics
# ---------------------------------------------------------------------------


def test_default_dir_uses_env_var(user_dict_dir):
    assert default_user_dict_dir() == user_dict_dir


def test_save_creates_json_file(user_dict_dir):
    src = UserDictSource()
    path = src.save_character("鱻", strokes=[
        {"track": [[100, 100], [200, 100], [200, 200]]},
        {"track": [[100, 200], [200, 200]]},
    ])
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["char"] == "鱻"
    assert payload["unicode_hex"] == "9c7b"
    assert payload["data_source"] == "user"
    assert len(payload["strokes"]) == 2


def test_save_then_get_round_trips(user_dict_dir):
    src = UserDictSource()
    src.save_character("鱻", strokes=[
        {"track": [[100, 100], [200, 200]], "kind_code": 7},
    ])
    c = src.get_character("鱻")
    assert isinstance(c, Character)
    assert c.char == "鱻"
    assert c.data_source == "user"
    assert len(c.strokes) == 1
    assert c.strokes[0].kind_code == 7


def test_get_unknown_char_raises(user_dict_dir):
    src = UserDictSource()
    with pytest.raises(CharacterNotFound):
        src.get_character("未")


def test_list_chars_sorted_by_codepoint(user_dict_dir):
    src = UserDictSource()
    src.save_character("乙", strokes=[{"track": [[0, 0], [100, 100]]}])
    src.save_character("一", strokes=[{"track": [[0, 0], [100, 100]]}])
    src.save_character("甲", strokes=[{"track": [[0, 0], [100, 100]]}])
    chars = src.list_chars()
    # codepoints: 一=4E00, 乙=4E59, 甲=7532
    assert chars == ["一", "乙", "甲"]


def test_delete_removes_file(user_dict_dir):
    src = UserDictSource()
    src.save_character("鱻", strokes=[{"track": [[0, 0], [10, 10]]}])
    assert src.has("鱻") is True
    assert src.delete_character("鱻") is True
    assert src.has("鱻") is False
    assert src.delete_character("鱻") is False   # second delete = no-op


def test_save_validates_minimum_points(user_dict_dir):
    src = UserDictSource()
    with pytest.raises(ValueError, match="must have"):
        src.save_character("X", strokes=[{"track": [[0, 0]]}])


def test_save_rejects_multi_char(user_dict_dir):
    src = UserDictSource()
    with pytest.raises(ValueError):
        src.save_character("AB", strokes=[{"track": [[0, 0], [1, 1]]}])


def test_invalidate_after_save(user_dict_dir):
    """Caller should see updated data after save_character on a re-get."""
    src = UserDictSource()
    src.save_character("鱻", strokes=[{"track": [[0, 0], [10, 10]]}])
    c1 = src.get_character("鱻")
    assert len(c1.strokes) == 1
    src.save_character("鱻", strokes=[
        {"track": [[0, 0], [10, 10]]},
        {"track": [[20, 0], [30, 10]]},
    ])
    c2 = src.get_character("鱻")
    assert len(c2.strokes) == 2


# ---------------------------------------------------------------------------
# Source-chain priority — user dict overrides built-ins
# ---------------------------------------------------------------------------


def test_autosource_user_dict_overrides_primary(user_dict_dir):
    """A char added to user-dict should be returned BEFORE g0v even
    if g0v has the same char."""
    src = UserDictSource()
    src.save_character("一", strokes=[
        {"track": [[100, 100], [1900, 100]], "kind_code": 9}
    ])
    auto = AutoSource()
    c = auto.get_character("一")
    assert c.data_source == "user"


def test_autosource_falls_through_to_g0v(user_dict_dir, source):
    """Char NOT in user-dict but in g0v → returned from g0v."""
    auto = AutoSource(primary=source)   # use fixtures-only g0v
    c = auto.get_character("一")
    assert c.data_source != "user"


def test_region_source_also_honours_user_dict(user_dict_dir):
    """Region source's user_dict layer should override built-ins."""
    src = UserDictSource()
    src.save_character("永", strokes=[
        {"track": [[0, 0], [2048, 2048]]}
    ])
    from stroke_order.sources import RegionAutoSource
    for region in ("tw", "cn", "jp"):
        c = RegionAutoSource(region).get_character("永")
        assert c.data_source == "user", f"region {region} missed user override"


# ---------------------------------------------------------------------------
# Helpers: handwriting + SVG → strokes
# ---------------------------------------------------------------------------


def test_handwriting_normalizes_to_em_frame():
    raw = [[[0, 0], [100, 0], [100, 100]]]
    out = handwriting_to_strokes(
        raw, canvas_width=200, canvas_height=200,
    )
    assert len(out) == 1
    track = out[0]["track"]
    assert len(track) == 3
    # canvas 200×200 → uniform scale 2048/200 = 10.24, then centred (no offset
    # since canvas already square). All coords ≤ 2048.
    for x, y in track:
        assert 0 <= x <= 2048
        assert 0 <= y <= 2048
    # First point at (0,0) on canvas → (0, 0) em (with centre offsets = 0)
    assert track[0] == [0.0, 0.0]


def test_handwriting_skips_taps():
    raw = [
        [[10, 10]],                   # single tap — drop
        [[0, 0], [100, 100]],         # real stroke — keep
    ]
    out = handwriting_to_strokes(raw, canvas_width=200, canvas_height=200)
    assert len(out) == 1


def test_handwriting_rejects_empty_canvas():
    with pytest.raises(ValueError):
        handwriting_to_strokes([], canvas_width=200, canvas_height=200)


def test_svg_to_strokes_polyline():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg">
      <polyline points="10,10 90,10 90,90"/>
    </svg>'''
    out = svg_to_strokes(svg)
    assert len(out) == 1
    assert len(out[0]["track"]) == 3


def test_svg_to_strokes_multiple_paths():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg">
      <line x1="0" y1="0" x2="100" y2="0"/>
      <line x1="0" y1="50" x2="100" y2="50"/>
      <polyline points="0,100 100,100"/>
    </svg>'''
    out = svg_to_strokes(svg)
    assert len(out) == 3


def test_svg_to_strokes_rejects_empty_svg():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    with pytest.raises(ValueError):
        svg_to_strokes(svg)


def test_svg_to_strokes_rejects_invalid_xml():
    with pytest.raises(ValueError):
        svg_to_strokes("not valid xml")


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
def client(user_dict_dir):
    """Per-test client so each test sees a clean dict dir."""
    if not _HAS:
        pytest.skip("web deps missing")
    return TestClient(create_app())


def test_api_user_dict_empty_initially(client):
    r = client.get("/api/user-dict")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 0
    assert d["chars"] == []


def test_api_user_dict_post_json(client):
    r = client.post("/api/user-dict", json={
        "char": "鱻",
        "format": "json",
        "strokes": [{"track": [[100, 100], [200, 200], [300, 300]]}],
    })
    assert r.status_code == 200
    d = r.json()
    assert d["char"] == "鱻"
    assert d["stroke_count"] == 1
    # Verify it appears in list
    r2 = client.get("/api/user-dict")
    assert r2.json()["count"] == 1
    assert r2.json()["chars"][0]["char"] == "鱻"


def test_api_user_dict_post_svg(client):
    svg = '<svg xmlns="http://www.w3.org/2000/svg">' \
          '<polyline points="0,0 100,100"/></svg>'
    r = client.post("/api/user-dict", json={
        "char": "甲",
        "format": "svg",
        "svg_content": svg,
    })
    assert r.status_code == 200, r.text
    assert r.json()["stroke_count"] == 1


def test_api_user_dict_post_handwriting(client):
    r = client.post("/api/user-dict", json={
        "char": "乙",
        "format": "handwriting",
        "handwriting": {
            "strokes": [[[10, 10], [50, 50], [90, 90]]],
            "canvas_width": 200,
            "canvas_height": 200,
        },
    })
    assert r.status_code == 200, r.text
    assert r.json()["stroke_count"] == 1


def test_api_user_dict_get_one(client):
    client.post("/api/user-dict", json={
        "char": "鱻",
        "format": "json",
        "strokes": [{"track": [[1, 1], [2, 2]]}],
    })
    r = client.get("/api/user-dict/鱻")
    assert r.status_code == 200
    d = r.json()
    assert d["char"] == "鱻"
    assert d["data_source"] == "user"
    assert len(d["strokes"]) == 1


def test_api_user_dict_get_404(client):
    r = client.get("/api/user-dict/未")
    assert r.status_code == 404


def test_api_user_dict_delete(client):
    client.post("/api/user-dict", json={
        "char": "鱻",
        "format": "json",
        "strokes": [{"track": [[1, 1], [2, 2]]}],
    })
    r = client.delete("/api/user-dict/鱻")
    assert r.status_code == 200
    r2 = client.get("/api/user-dict/鱻")
    assert r2.status_code == 404


def test_api_user_dict_post_rejects_bad_format(client):
    r = client.post("/api/user-dict", json={
        "char": "X", "format": "exe", "strokes": [{"track": [[0, 0], [1, 1]]}],
    })
    assert r.status_code == 400


def test_api_user_dict_override_visible_in_notebook(client):
    """User-dict char shows up when rendered in notebook mode."""
    # Add a custom 一 with very distinct strokes
    client.post("/api/user-dict", json={
        "char": "一",
        "format": "json",
        "strokes": [
            {"track": [[100, 100], [1900, 100]], "kind_code": 2},
            {"track": [[100, 1900], [1900, 1900]], "kind_code": 2},
        ],
    })
    # The notebook renders 一 → user-dict version (2 strokes), not g0v's (1 stroke)
    r = client.get("/api/notebook?text=一&preset=large&cell_style=trace&format=json")
    assert r.status_code == 200
    data = r.json()
    one_char = data["pages"][0]["chars"][0]
    assert len(one_char["strokes"]) == 2   # user-dict has 2 strokes


def test_api_user_dict_writes_to_env_dir(client, user_dict_dir):
    """Posted file lands under STROKE_ORDER_USER_DICT_DIR, not real home."""
    client.post("/api/user-dict", json={
        "char": "鱻",
        "format": "json",
        "strokes": [{"track": [[1, 1], [2, 2]]}],
    })
    assert (user_dict_dir / "9c7b.json").exists()


# ---------------------------------------------------------------------------
# Phase 5ar — bulk export / import (helpers + API endpoints)
# ---------------------------------------------------------------------------


def test_export_zip_bytes_round_trip(user_dict_dir):
    """save → export → import into fresh dir → list_chars matches."""
    src = UserDictSource(dict_dir=user_dict_dir)
    src.save_character("鱻", [{"track": [[100, 200], [400, 200]]}])
    src.save_character("璿", [{"track": [[200, 100], [200, 400]]}])
    zip_bytes = src.export_zip_bytes()
    assert zip_bytes.startswith(b"PK")   # ZIP magic

    fresh_dir = user_dict_dir.parent / "restored"
    src2 = UserDictSource(dict_dir=fresh_dir)
    summary = src2.import_zip_bytes(zip_bytes, policy="skip")
    assert summary == {"added": 2, "skipped": 0, "replaced": 0, "errors": []}
    assert sorted(src2.list_chars()) == sorted(["鱻", "璿"])
    # Round-trip data fidelity: same strokes back out.
    c = src2.get_character("鱻")
    assert c.strokes[0].raw_track[0].x == 100.0


def test_export_empty_dir_yields_valid_empty_zip(user_dict_dir):
    src = UserDictSource(dict_dir=user_dict_dir)
    zip_bytes = src.export_zip_bytes()
    # Valid empty ZIP starts with magic and round-trips through zipfile.
    import io, zipfile
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        assert zf.namelist() == []


def test_import_skip_policy_preserves_existing(user_dict_dir):
    src = UserDictSource(dict_dir=user_dict_dir)
    # Pre-existing 鱻 with one track.
    src.save_character("鱻", [{"track": [[10, 10], [20, 20]]}])
    # Import a backup that has a DIFFERENT 鱻 + a new char.
    other = UserDictSource(dict_dir=user_dict_dir.parent / "other")
    other.save_character("鱻", [{"track": [[999, 999], [1000, 1000]]}])
    other.save_character("璿", [{"track": [[300, 300], [400, 400]]}])
    summary = src.import_zip_bytes(other.export_zip_bytes(), policy="skip")
    assert summary["added"] == 1   # 璿 was new
    assert summary["skipped"] == 1   # 鱻 existed → skipped
    assert summary["replaced"] == 0
    # Existing 鱻 must be UNCHANGED.
    src.invalidate("鱻")
    c = src.get_character("鱻")
    assert c.strokes[0].raw_track[0].x == 10.0


def test_import_replace_policy_overwrites(user_dict_dir):
    src = UserDictSource(dict_dir=user_dict_dir)
    src.save_character("鱻", [{"track": [[10, 10], [20, 20]]}])
    other = UserDictSource(dict_dir=user_dict_dir.parent / "other")
    other.save_character("鱻", [{"track": [[999, 999], [1000, 1000]]}])
    summary = src.import_zip_bytes(other.export_zip_bytes(), policy="replace")
    assert summary["replaced"] == 1
    assert summary["added"] == 0
    src.invalidate("鱻")
    c = src.get_character("鱻")
    assert c.strokes[0].raw_track[0].x == 999.0


def test_import_rejects_unknown_policy(user_dict_dir):
    src = UserDictSource(dict_dir=user_dict_dir)
    with pytest.raises(ValueError, match="unknown policy"):
        src.import_zip_bytes(b"PKfake", policy="merge")


def test_import_rejects_corrupt_zip(user_dict_dir):
    src = UserDictSource(dict_dir=user_dict_dir)
    with pytest.raises(ValueError, match="not a valid ZIP"):
        src.import_zip_bytes(b"not actually a zip")


def test_import_collects_errors_for_bad_entries(user_dict_dir):
    """Non-hex filenames, subdirs, malformed JSON should be reported but
    not abort the whole import."""
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("not_hex.json", '{"strokes":[{"track":[[0,0],[1,1]]}]}')
        zf.writestr("sub/dir.json", '{"strokes":[{"track":[[0,0],[1,1]]}]}')
        zf.writestr("rabbit.txt", "irrelevant")
        zf.writestr("9c7b.json",
                    '{"strokes":[{"track":[[0,0],[10,10]]}]}')   # valid 鱻
    src = UserDictSource(dict_dir=user_dict_dir)
    summary = src.import_zip_bytes(buf.getvalue(), policy="skip")
    assert summary["added"] == 1
    assert len(summary["errors"]) == 3
    reasons = {e["name"] for e in summary["errors"]}
    assert reasons == {"not_hex.json", "sub/dir.json", "rabbit.txt"}


# --- API integration ---


def test_api_export_returns_zip(client):
    client.post("/api/user-dict", json={
        "char": "鱻", "format": "json",
        "strokes": [{"track": [[100, 200], [400, 200]]}],
    })
    r = client.get("/api/user-dict/export")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "stroke-order-user-dict-" in r.headers["content-disposition"]
    assert r.content.startswith(b"PK")


def test_api_export_route_does_not_collide_with_char_route(client):
    """The /export path must not be shadowed by the /{char} GET. This is
    a bug-resistance regression test for the 5ar endpoint ordering."""
    r = client.get("/api/user-dict/export")
    assert r.status_code == 200
    # The single-char route would reject "export" with 400 ("char must be
    # a single character"). If we get 200 + ZIP, the order is correct.
    assert "application/zip" in r.headers["content-type"]


def test_api_import_round_trip(client):
    """POST → export → POST /import → list reflects restored chars."""
    client.post("/api/user-dict", json={
        "char": "鱻", "format": "json",
        "strokes": [{"track": [[100, 200], [400, 200]]}],
    })
    client.post("/api/user-dict", json={
        "char": "璿", "format": "json",
        "strokes": [{"track": [[200, 100], [200, 400]]}],
    })
    zip_bytes = client.get("/api/user-dict/export").content
    # Wipe both, re-import.
    client.delete("/api/user-dict/鱻")
    client.delete("/api/user-dict/璿")
    assert client.get("/api/user-dict").json()["count"] == 0
    r = client.post(
        "/api/user-dict/import",
        files={"file": ("backup.zip", zip_bytes, "application/zip")},
        data={"policy": "skip"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["added"] == 2
    assert client.get("/api/user-dict").json()["count"] == 2


def test_api_import_rejects_bogus_policy(client):
    """Invalid policy → 422 with explanatory detail."""
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("9c7b.json", '{"strokes":[{"track":[[0,0],[1,1]]}]}')
    r = client.post(
        "/api/user-dict/import",
        files={"file": ("backup.zip", buf.getvalue(), "application/zip")},
        data={"policy": "merge"},
    )
    assert r.status_code == 422
    assert "policy" in r.json()["detail"]


def test_api_import_corrupt_zip_returns_400(client):
    r = client.post(
        "/api/user-dict/import",
        files={"file": ("not.zip", b"not actually zip", "application/zip")},
        data={"policy": "skip"},
    )
    assert r.status_code == 400
