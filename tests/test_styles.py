"""
Phase 5aj — stroke-filter styles (假宋體 / 假隸書 / 粗楷).

Tests cover:

1. Pure-function contract — ``apply_style`` never mutates its input
   and returns a new Character with observable per-style properties.
2. Per-style geometry checks — Bold's pen_size, Mingti's
   horizontal/vertical pen_size contrast, Lishu's vertical compression.
3. Web API integration — five multi-character endpoints accept a
   ``style`` query param and produce measurably different SVG output.
"""
from __future__ import annotations

import pytest

from stroke_order.classifier import classify_character
from stroke_order.smoothing import smooth_character
from stroke_order.sources.g0v import G0VSource
from stroke_order.styles import STYLES, apply_style, list_styles


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def char_yong(source):
    """The classic '永' character — has all eight stroke kinds between
    its 5 strokes, so it's a good testbed for kind-sensitive filters."""
    c = source.get_character("永")
    classify_character(c)
    smooth_character(c)
    return c


# ---------------------------------------------------------------------------
# Registry / identity
# ---------------------------------------------------------------------------


def test_registry_has_five_styles():
    # Phase 5at adds 'seal_script' (崇羲篆體 swap, identity filter).
    assert set(STYLES) == {"kaishu", "mingti", "lishu", "bold", "seal_script"}


def test_list_styles_descriptions():
    names = {n for n, _ in list_styles()}
    assert names == {"kaishu", "mingti", "lishu", "bold", "seal_script"}
    # Every style has a non-empty human description
    for _, desc in list_styles():
        assert desc and isinstance(desc, str)


def test_kaishu_is_identity(char_yong):
    assert apply_style(char_yong, "kaishu") is char_yong


def test_unknown_style_raises(char_yong):
    with pytest.raises(ValueError):
        apply_style(char_yong, "nope")


# ---------------------------------------------------------------------------
# Purity
# ---------------------------------------------------------------------------


def _snapshot(c):
    return [
        (s.kind_code, len(s.raw_track),
         len(s.smoothed_track or []), s.pen_size)
        for s in c.strokes
    ]


@pytest.mark.parametrize("style", ["mingti", "lishu", "bold"])
def test_style_does_not_mutate_input(char_yong, style):
    before = _snapshot(char_yong)
    _ = apply_style(char_yong, style)
    after = _snapshot(char_yong)
    assert before == after


# ---------------------------------------------------------------------------
# Bold
# ---------------------------------------------------------------------------


def test_bold_sets_pen_size_on_every_stroke(char_yong):
    bolded = apply_style(char_yong, "bold")
    for s in bolded.strokes:
        assert s.pen_size is not None
        assert s.pen_size > 0


def test_bold_pen_sizes_larger_than_kaishu(char_yong):
    """Bold's pen_size should be noticeably larger than the renderer's
    default track width (18.0 baseline in _char_svg)."""
    bolded = apply_style(char_yong, "bold")
    for s in bolded.strokes:
        assert s.pen_size > 30.0


# ---------------------------------------------------------------------------
# Mingti
# ---------------------------------------------------------------------------


def test_mingti_horizontals_thinner_than_verticals(char_yong):
    """The defining Mingti contrast: vertical strokes are thicker,
    horizontals are thinner."""
    import stroke_order.styles._helpers as H
    m = apply_style(char_yong, "mingti")
    h_widths = [s.pen_size for s in m.strokes if H.is_horizontal(s.kind_code)]
    v_widths = [s.pen_size for s in m.strokes if H.is_vertical(s.kind_code)]
    if h_widths and v_widths:
        assert max(h_widths) < min(v_widths)


def test_mingti_adds_serif_points(char_yong):
    """Every Mingti stroke should gain end-serif points in its
    smoothed_track (extra points beyond the base track length)."""
    m = apply_style(char_yong, "mingti")
    for orig, styled in zip(char_yong.strokes, m.strokes):
        orig_len = len(orig.smoothed_track or orig.raw_track)
        styled_len = len(styled.smoothed_track or styled.raw_track)
        # Should grow by exactly 2 points (serif tick + return to end)
        assert styled_len == orig_len + 2


# ---------------------------------------------------------------------------
# Lishu
# ---------------------------------------------------------------------------


def test_lishu_adds_波磔_on_horizontals(char_yong):
    """Horizontal strokes should gain ≥2 flare points; non-horizontal
    strokes' track length is unchanged by this pass."""
    import stroke_order.styles._helpers as H
    lishu = apply_style(char_yong, "lishu")
    for orig, styled in zip(char_yong.strokes, lishu.strokes):
        orig_len = len(orig.smoothed_track or orig.raw_track)
        styled_len = len(styled.smoothed_track or styled.raw_track)
        if H.is_horizontal(orig.kind_code):
            assert styled_len == orig_len + 2   # mid + flare
        else:
            assert styled_len == orig_len


def test_lishu_compresses_vertical_extent(char_yong):
    """The whole character's Y-extent after Lishu should be roughly
    COMPRESS_Y × original. Check via stroke bboxes (approximate test
    since smoothed_track drives the shape)."""
    def _yrange(c):
        ys = []
        for s in c.strokes:
            track = s.smoothed_track or s.raw_track
            ys.extend(p.y for p in track)
        return max(ys) - min(ys)
    before = _yrange(char_yong)
    after = _yrange(apply_style(char_yong, "lishu"))
    # LishuStyle.COMPRESS_Y = 0.82. Lishu also extends some horizontal
    # strokes with flares, which can slightly widen the y-range; allow
    # tolerance but confirm it's clearly compressed relative to original.
    assert after < before, f"expected vertical compression; got {after}/{before}"
    assert after < before * 0.97   # at least ~3% compression


# ---------------------------------------------------------------------------
# Edge cases: punctuation (kind_code=9) should not crash any filter
# ---------------------------------------------------------------------------


def test_styles_work_on_punctuation():
    """Hand-authored punctuation has kind_code=9; Mingti/Lishu specific
    tricks no-op on kind 9 but Bold still applies — nothing should crash."""
    from stroke_order.sources import PunctuationSource
    src = PunctuationSource()
    c = src.get_character("，")
    for style in ("bold", "mingti", "lishu"):
        out = apply_style(c, style)
        assert out.strokes


# ---------------------------------------------------------------------------
# Web API
# ---------------------------------------------------------------------------


try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS = True
except ImportError:
    _HAS = False


@pytest.fixture(scope="module")
def client():
    if not _HAS:
        pytest.skip("web deps missing")
    return TestClient(create_app())


@pytest.mark.parametrize(
    "endpoint,extra_params",
    [
        ("notebook",   "text=永&preset=large&cell_style=trace"),
        ("letter",     "text=永&preset=A5&cell_style=trace"),
        ("manuscript", "text=永&preset=300&cell_style=trace"),
        ("grid",       "chars=永&cell_style=trace"),
    ],
)
def test_api_style_default_kaishu_matches_omitted(client, endpoint, extra_params):
    """Back-compat: omitting ``style`` equals passing ``style=kaishu``."""
    r1 = client.get(f"/api/{endpoint}?{extra_params}")
    r2 = client.get(f"/api/{endpoint}?{extra_params}&style=kaishu")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.content == r2.content


@pytest.mark.parametrize(
    "endpoint,extra_params",
    [
        ("notebook",   "text=永&preset=large&cell_style=trace"),
        ("letter",     "text=永&preset=A5&cell_style=trace"),
        ("manuscript", "text=永&preset=300&cell_style=trace"),
    ],
)
@pytest.mark.parametrize("style", ["mingti", "lishu", "bold"])
def test_api_style_changes_svg(client, endpoint, extra_params, style):
    """A non-kaishu style must produce a different SVG than kaishu."""
    r_ka = client.get(f"/api/{endpoint}?{extra_params}")
    r_st = client.get(f"/api/{endpoint}?{extra_params}&style={style}")
    assert r_ka.status_code == 200 and r_st.status_code == 200
    assert r_ka.text != r_st.text, f"{endpoint} style={style} identical to kaishu"


def test_api_wordart_style_parameter(client):
    """Wordart also accepts style — different styles change output."""
    base = "/api/wordart?shape=circle&layout=ring&text=永&shape_size_mm=120"
    r_ka = client.get(base)
    r_bold = client.get(base + "&style=bold")
    assert r_ka.status_code == 200 and r_bold.status_code == 200
    assert r_ka.text != r_bold.text


def test_api_rejects_unknown_style(client):
    r = client.get("/api/notebook?text=永&preset=large&style=bogus")
    assert r.status_code == 422
