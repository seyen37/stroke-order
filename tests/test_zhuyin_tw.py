"""Phase 5cw: 台灣讀音表（McBopomofo 衍生檔）資料契約。

static/zhuyin_tw.json＝前端注音欄的權威讀音來源（教育部體系），
格式 {"字": "主音|次音|…"}，主音＝heterophony 排序的預設讀音。
本檔鎖三件事：檔案完整（截斷可偵測）、台灣審定音正確（衝突字
抽查）、值全為合法注音字元。
"""
import json
import re
from pathlib import Path

import pytest

DATA = (Path(__file__).resolve().parents[1]
        / "src" / "stroke_order" / "web" / "static" / "zhuyin_tw.json")
_VALID = re.compile(r"^[ㄅ-ㄩˊˇˋ˙]+(\|[ㄅ-ㄩˊˇˋ˙]+)*$")

try:
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    _HAS = True
except ImportError:
    _HAS = False


@pytest.fixture(scope="module")
def zy():
    return json.loads(DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client():
    if not _HAS:
        pytest.skip("web deps missing")
    return TestClient(create_app())


def test_5cw_asset_complete(zy):
    # 全庫規模——截斷（沙箱掛載事故型）會直接跌破門檻或 JSON 解析失敗
    assert len(zy) > 20000


def test_5cw_taiwan_readings_spot_check(zy):
    # 教育部審定音 vs 大陸音的代表性衝突字（主音＝第一段）——
    # 這正是 5cw 換資料源的理由，鎖死防止來源回退
    expect = {"垃": "ㄌㄜˋ", "圾": "ㄙㄜˋ", "期": "ㄑㄧˊ",
              "危": "ㄨㄟˊ", "究": "ㄐㄧㄡˋ", "崖": "ㄧㄞˊ",
              "質": "ㄓˊ", "識": "ㄕˋ", "永": "ㄩㄥˇ", "日": "ㄖˋ"}
    for ch, want in expect.items():
        assert zy[ch].split("|")[0] == want, ch


def test_5cw_all_values_valid_bopomofo(zy):
    bad = [ch for ch, v in zy.items() if not _VALID.match(v)]
    assert not bad, bad[:10]


def test_5cw_served_same_origin(client, zy):
    # 前端 fetch("/static/zhuyin_tw.json") 的同源契約
    r = client.get("/static/zhuyin_tw.json")
    assert r.status_code == 200
    d = json.loads(r.text)
    assert d["垃"].split("|")[0] == "ㄌㄜˋ"
    assert len(d) == len(zy)
