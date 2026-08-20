"""
W4 — 分級選字：照教育部國小常用字頻表的名次帶入字帖生字。

字帖評估建議書的最後一個缺口。設計是**零新端點**：前端 fetch 既有
``/api/coverset/moe_elementary_5021``，切片即選字——這整個功能站在一條
資料契約上：

    **chars 順序 ≡ frequency_rank 順序（rank 1..N 連續無跳號）**
    → 第 N 名就是 chars[N-1]

本檔的第一組測試就是把這條契約鎖死：JSON 改排序、rank 出現跳號、端點
改變輸出順序，任何一個動了這裡就紅——否則前端會**默默帶錯字**（老師
不會發現，字帖照樣印得出來）。

第二組是誠實標示鎖（評估建議書的風險註記）：frequency_rank 是字頻代理，
**不等於年級**——UI 與 JS 不得出現「年級」字樣。

純切片邏輯（夾限、截尾）在 ``grid_freq_core.mjs``，由
``tests/test_grid_freq_core.mjs`` 用 node 直測。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stroke_order.web.server import create_app

_ROOT = Path(__file__).resolve().parent.parent
_STATIC = _ROOT / "src" / "stroke_order" / "web" / "static"
_INDEX = _STATIC / "index.html"
_FREQ_JS = _STATIC / "modes" / "grid_freq.js"
_FREQ_CORE = _STATIC / "modes" / "grid_freq_core.mjs"
_COVERSET_JSON = (_ROOT / "src" / "stroke_order" / "components"
                  / "coversets" / "moe_elementary_5021.json")


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


@pytest.fixture(scope="module")
def raw_entries():
    return json.loads(_COVERSET_JSON.read_text("utf-8"))["entries"]


# ---------------------------------------------------------------------------
# 資料契約：chars 順序 ≡ frequency_rank 順序
# ---------------------------------------------------------------------------


def test_w4_frequency_rank_is_sequential_with_no_gaps(raw_entries):
    """rank 必須是 1..N 連續——跳號或重排都會讓「第 N 名 = chars[N-1]」失效。"""
    ranks = [e["frequency_rank"] for e in raw_entries]
    assert ranks == list(range(1, len(raw_entries) + 1))


def test_w4_endpoint_chars_follow_rank_order(client, raw_entries):
    """端點回的 chars 逐字等同 JSON 的 trad 序——切片語意的另一半。"""
    r = client.get("/api/coverset/moe_elementary_5021")
    assert r.status_code == 200
    chars = r.json()["chars"]
    assert len(chars) == len(raw_entries)
    assert chars == [e["trad"] for e in raw_entries]


def test_w4_a_known_slice_matches_by_hand(client):
    """已知答案自驗（§93）：第 101–110 名實查為「些最寫又因前從法明行」。

    這條在上面兩條之外再釘一根樁：哪天有人「無害地」重排 JSON 又同步改了
    rank 欄位，順序契約測試全綠，但選出來的字已經不是字頻表的字了。
    """
    chars = client.get("/api/coverset/moe_elementary_5021").json()["chars"]
    assert "".join(chars[100:110]) == "些最寫又因前從法明行"


def test_w4_pick_upper_bound_matches_grid_chars_limit(client):
    """MAX_PICK ≡ /api/grid 的 chars 上限 ≡ 輸入框 maxlength（三處 parity）。

    帶入超過 /api/grid 收的長度，多出來的字會被 422 拒收——三個數字必須
    是同一個。
    """
    m = re.search(r"MAX_PICK\s*=\s*(\d+)", _FREQ_CORE.read_text("utf-8"))
    assert m, "grid_freq_core.mjs 缺 MAX_PICK"
    max_pick = int(m.group(1))

    spec = client.get("/openapi.json").json()
    chars_param = next(
        p for p in spec["paths"]["/api/grid"]["get"]["parameters"]
        if p["name"] == "chars")
    assert chars_param["schema"]["maxLength"] == max_pick

    page = _INDEX.read_text("utf-8")
    m2 = re.search(r'id="grid-chars"[^>]*maxlength="(\d+)"', page)
    assert m2 and int(m2.group(1)) == max_pick


# ---------------------------------------------------------------------------
# 誠實標示：字頻不是年級
# ---------------------------------------------------------------------------


def test_w4_no_grade_level_claim_anywhere():
    """不得拿「年級」當分級依據——名次是字頻代理，不是課綱。

    允許的唯一形態是否定句「不代表年級難度」；除此之外整個 index.html
    與兩個 W4 模組出現「年級」就紅（守門連註解都掃——§95：紅了改措辭，
    不放寬守門）。
    """
    for path in (_FREQ_JS, _FREQ_CORE, _INDEX):
        stripped = path.read_text("utf-8").replace("不代表年級難度", "")
        assert "年級" not in stripped, path.name


def test_w4_hint_names_the_actual_source():
    """標示要指名真正的出處（字頻表），不是模糊的「常用字」。"""
    assert "字頻" in _INDEX.read_text("utf-8").split(
        'id="grid-freq-from"')[0].rsplit("<!--", 1)[-1] or \
        "字頻" in _FREQ_CORE.read_text("utf-8")


# ---------------------------------------------------------------------------
# parity：UI 元件 ≡ JS 讀取 ≡ 模組註冊
# ---------------------------------------------------------------------------


def test_w4_ui_ids_match_what_the_js_reads():
    page = _INDEX.read_text("utf-8")
    js = _FREQ_JS.read_text("utf-8")
    for el_id in ("grid-freq-from", "grid-freq-count",
                  "grid-freq-fill", "grid-freq-hint"):
        assert f'id="{el_id}"' in page, f"index.html 缺 {el_id}"
        assert f'getElementById("{el_id}")' in js, f"grid_freq.js 沒讀 {el_id}"
    assert 'getElementById("grid-chars")' in js, "帶入目標應是 grid-chars"


def test_w4_module_registered_with_version_query():
    """§11.4／版本快取鍵：script 註冊與模組間 import 都要帶 ?v=__V__。"""
    page = _INDEX.read_text("utf-8")
    assert '/static/modes/grid_freq.js?v=__V__' in page
    js = _FREQ_JS.read_text("utf-8")
    for imp in re.findall(r'from\s+"(\./[^"]+)"', js):
        assert imp.endswith("?v=__V__"), f"import 缺版本鍵：{imp}"


def test_w4_no_new_endpoint_and_no_hardcoded_total():
    """設計不變式：零新端點（fetch 既有 coverset）、不硬寫字表總數。"""
    js = _FREQ_JS.read_text("utf-8")
    assert "/api/coverset/moe_elementary_5021" in js
    assert "charpick" not in js
    # 5018 是資料的事實，不是程式的常數——上限要從 fetch 回來的長度設
    for text in (js, _FREQ_CORE.read_text("utf-8"),
                 _INDEX.read_text("utf-8")):
        assert "5018" not in text
