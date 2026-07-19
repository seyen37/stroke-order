"""W3-R2（架構健檢 Wave 3）：web 層分層回歸鎖。

R2 把共用 helpers 自 server.py 移居 char_pipeline／responses／
versioning，routes↔server 循環已解。這裡用靜態掃描鎖住三件事，
防止回潮（PRINCIPLES §35：鐵則掃全體配機器回歸鎖）。
"""
from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "stroke_order" / "web"
ROUTES = WEB / "routes"


def test_routes_never_import_server():
    """routes 不得 import web.server——單向依賴（server → routes）。

    回潮等於重新引入循環 import，還會讓「patch server 別名不影響
    實際呼叫」的沉默失效地雷復活。
    """
    offenders = []
    pat = re.compile(r"from \.\.server import|from \.\. import server|"
                     r"from stroke_order\.web\.server import")
    for f in ROUTES.glob("*.py"):
        if pat.search(f.read_text("utf-8")):
            offenders.append(f.name)
    assert offenders == [], (
        f"routes 檔 import 了 web.server：{offenders}——共用 helpers 應住 "
        "char_pipeline／responses／versioning。"
    )


def test_char_loading_symbols_live_only_in_pipeline():
    """載字鏈符號唯一住址＝char_pipeline（monkeypatch 目標唯一）。

    server 若再持有 _load 等名稱，測試 patch 到別名不會影響實際
    呼叫——沉默失效。
    """
    server_text = (WEB / "server.py").read_text("utf-8")
    for sym in ("def _load(", "def _upgrade_to_sung(",
                "def _upgrade_to_seal(", "def _upgrade_to_lishu(",
                "def make_char_loader("):
        assert sym not in server_text, f"server.py 不得再定義 {sym}"
    pipeline_text = (WEB / "char_pipeline.py").read_text("utf-8")
    for sym in ("def _load(", "def make_char_loader("):
        assert sym in pipeline_text


MODE_SCRIPTS = [
    "core", "stencil", "grid", "notebook", "letter", "manuscript",
    "doodle", "grid_route", "wordart", "mandala", "patch", "stamp",
    "sutra", "userdict", "handwrite", "fonts",
]

#: W4-R2 次批完結：16 檔全數 ES module（跨檔相依＝顯式 import/export 網）。
ES_MODULE_MODES = set(MODE_SCRIPTS)


def test_index_mode_scripts_order_snapshot():
    """W4-R1：index.html 的 modes/*.js 載入序＝拆檔前 inline 區段序。

    傳統 script 靠文件序保證全域定義順序——順序變動＝行為可能變，
    必須先來改這份快照並說明。
    """
    import re

    html = (WEB / "static" / "index.html").read_text("utf-8")
    found = re.findall(r'/static/modes/(\w+)\.js\?v=__V__', html)
    assert found == MODE_SCRIPTS, (
        f"modes script 載入序偏離快照：{found}"
    )
    for name in MODE_SCRIPTS:
        f = WEB / "static" / "modes" / f"{name}.js"
        assert f.is_file() and f.stat().st_size > 100, f"{name}.js 缺失或過小"

    # W4-R2：module 化狀態快照——classic↔module 的翻轉是語意變更
    # （嚴格模式＋自有作用域＋deferred），必須先過「零被依賴＋嚴格
    # 模式掃描」再來改這份集合。
    modules = set(re.findall(
        r'<script type="module" src="/static/modes/(\w+)\.js', html))
    assert modules == ES_MODULE_MODES, (
        f"module 化集合偏離快照：{sorted(modules)}"
    )


def test_index_no_large_inline_script():
    """W4-R1 防回潮：index.html 不得再長出大型 inline <script> 巨石。

    允許小型 glue（≤30 行）；新前端邏輯請進 modes/*.js（傳統 script）
    或照卡片模式開 ES modules。"""
    import re

    html = (WEB / "static" / "index.html").read_text("utf-8")
    for m in re.finditer(r"<script>(.*?)</script>", html, re.S):
        n = len(m.group(1).splitlines())
        assert n <= 30, (
            f"index.html 出現 {n} 行 inline <script>——巨石回潮。"
            "請放進 static/modes/ 或 ES module。"
        )


def test_svg_media_type_written_once():
    """``image/svg+xml`` 字串在 web 層只允許出現在 responses.py。"""
    offenders = []
    for f in list(ROUTES.glob("*.py")) + [WEB / "server.py",
                                          WEB / "char_pipeline.py"]:
        if "image/svg+xml" in f.read_text("utf-8"):
            offenders.append(f.name)
    assert offenders == [], (
        f"svg media_type 散寫於：{offenders}——請改用 responses.svg_response()。"
    )
