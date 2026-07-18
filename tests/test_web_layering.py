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
