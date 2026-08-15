"""T1 識字教學頁守門測試。

鎖住：頁面契約（200＋自包含＋設計 token＋導覽）、/api/radical-info 端點
契約（部首歸類單一事實源的薄包裝）、下載單檔的執行期 TTS 標記。
"""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from stroke_order.web.server import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_teach_page_contract(client):
    r = client.get("/teach")
    assert r.status_code == 200
    t = r.text
    # 自包含：無相對 .js import（§67 快取鍵不涉入）
    assert "<script src=" not in t
    # 核心功能標記：瀏覽器 TTS、下載、筆順動畫、部件、可填欄位
    assert "speechSynthesis" in t
    assert "SpeechSynthesisUtterance" in t
    assert "下載教學單檔" in t
    assert "api/character" in t and "api/components" in t
    assert "api/radical-info" in t
    assert 'id="meaning"' in t and 'id="vocab"' in t
    # 誠實標注：注音無逐字資料（老師自填）、發音為本機合成
    assert "請自填" in t or "老師填寫" in t


def test_radical_info_endpoint(client):
    r = client.get("/api/radical-info/木")
    assert r.status_code == 200
    d = r.json()
    assert d["is_radical"] is True
    assert d["category"] == "本存" and d["subcategory"] == "植物"
    r2 = client.get("/api/radical-info/園")   # 非部首字 → 誠實 false
    assert r2.status_code == 200
    assert r2.json()["is_radical"] is False
    assert client.get("/api/radical-info/ab").status_code == 422


def test_index_has_teach_entry(client):
    page = client.get("/").text
    # 錨定書寫練習「群組 div」（data-g="write" 另見於 CSS 選擇器與分頁鈕），
    # 取到 make 群之前——確保入口在書寫練習群內。
    write_group = page.split('class="mode-group show" data-g="write"')[1] \
                      .split('data-g="make"')[0]
    assert 'href="/teach"' in write_group
    assert "識字教學" in write_group


def test_teach_supports_compound_char(client):
    """園：components 有 IDS＋leaves、meta 有筆畫數——教學頁的資料鏈可用。"""
    comp = client.get("/api/components/園").json()
    assert comp["ids"] and comp["leaves_distinct"]
    meta = client.get("/api/meta/園").json()
    assert meta["stroke_count"] == 13
