"""Phase 5cz: 筆記/信紙注音欄（pair 格寬＋strip 渲染＋API 契約）。"""
import pytest

from stroke_order.classifier import classify_character
from stroke_order.exporters.notebook import (
    flow_notebook, render_notebook_page_svg,
)

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


def _loader(source):
    def load(ch):
        try:
            c = source.get_character(ch)
            classify_character(c)
            return c
        except Exception:
            return None
    return load


def test_5cz_flow_pair_width(source):
    """zhuyin=True → 格寬 1.5×行高（2:1 pair）；關閉＝原格寬零回歸。"""
    pages = flow_notebook("永日", _loader(source), zhuyin=True)
    lay = pages[0].layout
    assert abs(lay.char_width_mm - lay.line_height_mm * 1.5) < 1e-9
    pages0 = flow_notebook("永日", _loader(source))
    lay0 = pages0[0].layout
    assert lay0.char_width_mm == lay0.line_height_mm


def test_5cz_render_strip(source):
    """render 傳 zhuyin_map → 每格右側掛 strip；不傳＝零改動。"""
    pages = flow_notebook("永", _loader(source), zhuyin=True)
    sym = source.get_character("一")
    classify_character(sym)
    svg = render_notebook_page_svg(
        pages[0],
        zhuyin_map={"永": "ㄩㄥˇ"},
        zhuyin_chars={"ㄩ": sym, "ㄥ": sym},
    )
    assert 'class="zhuyin"' in svg
    assert "polyline" in svg                 # ˇ 調號（_zhuyin_layout 繼承）
    svg0 = render_notebook_page_svg(pages[0])
    assert 'class="zhuyin"' not in svg0


def test_5cz_api_notebook_zhuyin(client):
    r = client.get("/api/notebook?text=永日&zhuyin_map=永:ㄩㄥˇ,日:ㄖˋ")
    assert r.status_code == 200
    assert 'class="zhuyin"' in r.text


def test_5cz_api_letter_zhuyin(client):
    r = client.get("/api/letter?text=永日&zhuyin_map=永:ㄩㄥˇ,日:ㄖˋ")
    assert r.status_code == 200
    assert 'class="zhuyin"' in r.text
