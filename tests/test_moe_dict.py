"""T2 教育部辭典資料源守門測試。

鎖住：bundle 存在且可查、原文逐字保留（ND 授權不得改作）、端點契約
（found/attribution/授權標示）、教學頁自動帶入且保留可編輯、缺字誠實回報。
"""
import gzip
import json

import pytest

from stroke_order.sources import moe_dict


def test_bundle_present_and_loaded():
    """bundle 隨 repo 散布——存在、可載、涵蓋常用字。"""
    assert moe_dict.is_ready(), f"缺 bundle：{moe_dict.bundle_path()}"
    assert moe_dict.entry_count() > 5000


def test_lookup_shape_and_content():
    d = moe_dict.lookup("園")
    assert d is not None
    assert d["zhuyin"] == "ㄩㄢˊ"
    assert d["radical"] == "囗"          # 教育部權威部首
    assert d["stroke_count"] == 13
    assert "種植花木" in d["definition"]
    assert "[例]" in d["definition"], "例句標記須原樣保留"
    assert len(d["words"]) >= 4
    w = d["words"][0]
    assert w["word"].startswith("園") and w["zhuyin"] and w["definition"]


def test_lookup_rejects_non_single_char():
    assert moe_dict.lookup("") is None
    assert moe_dict.lookup("園藝") is None
    assert moe_dict.lookup("〇〇") is None


def test_definitions_are_verbatim_no_placeholder_artifacts():
    """ND 授權：內容不得改作——抽驗釋義無 xlsx 假影、未被截斷標記污染。"""
    with gzip.open(moe_dict.bundle_path(), "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 300:
                break
            d = json.loads(line)
            for text in [d.get("df", "")] + [w.get("df", "") for w in d.get("w", [])]:
                assert "_x000D_" not in text, "CR 假影須還原為換行"
                assert "…（略）" not in text and "..." not in text[-4:], \
                    "釋義不得截斷／摘要"


def test_missing_char_returns_none():
    assert moe_dict.lookup("\U0002F81A") is None   # 罕用相容字，辭典無


def test_endpoint_contract():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    c = TestClient(create_app())

    r = c.get("/api/dict/園")
    assert r.status_code == 200
    d = r.json()
    assert d["found"] is True
    assert d["zhuyin"] == "ㄩㄢˊ" and d["radical"] == "囗"
    assert d["words"] and d["license"].startswith("創用CC")
    assert "教育部" in d["attribution"], "出處標示（ND 姓名標示義務）"
    assert "language.moe.gov.tw" in d["source_url"]

    r2 = c.get("/api/dict/\U0002F81A")
    assert r2.status_code == 200 and r2.json()["found"] is False
    assert c.get("/api/dict/園藝").status_code == 422


def test_teach_page_wires_dict_but_keeps_editable():
    """教學頁：自動帶入＋仍可編輯（§87 不裝懂／可升級）＋出處標示。"""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from stroke_order.web.server import create_app
    t = TestClient(create_app()).get("/teach").text
    assert "api/dict" in t
    assert "（教育部，可修改）" in t          # 帶入但不鎖死
    assert "attribution" in t                  # 出處標示帶進頁面與下載檔
    assert 'id="meaning"' in t and 'id="vocab"' in t   # 仍是可編輯欄位
