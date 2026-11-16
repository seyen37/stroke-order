"""v0.14.304：AGENTS.md（給 AI 代理的入口）同步鎖。

AGENTS.md 只指路；指的路若不存在（檔案改名、搬家），代理就會被帶錯。
本測試抓出所有反引號內、看起來像 repo 路徑的字串，逐一確認存在。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "AGENTS.md"

# 樣板路徑（含 YYYY 等占位）與指令不算
_SKIP = re.compile(r"YYYY|\*|\s|^python|^node|^/static|^/api|\?v=")


def _paths():
    text = AGENTS.read_text(encoding="utf-8")
    out = []
    for tok in re.findall(r"`([^`]+)`", text):
        if _SKIP.search(tok):
            continue
        if "/" in tok or tok.endswith((".md", ".py", ".bat", ".toml")):
            out.append(tok.rstrip("/"))
    return out


def test_agents_md_exists_and_points_to_design():
    text = AGENTS.read_text(encoding="utf-8")
    for must in ("DESIGN.md", "docs/PRINCIPLES.md", "收工檢查.bat",
                 "不 commit、不 push", "只讀"):
        assert must in text, must


def test_agents_md_paths_exist():
    paths = _paths()
    assert len(paths) >= 8, f"抓到的路徑太少（格式被改壞？）：{paths}"
    missing = [p for p in paths if not (ROOT / p).exists()]
    assert not missing, f"AGENTS.md 指向不存在的路徑：{missing}"
