#!/usr/bin/env python3
"""Phase 5cw: 重建台灣讀音表 static/zhuyin_tw.json。

資料源：McBopomofo（openvanilla，MIT License）
  - BPMFBase.txt        字級注音庫（21,786 字，教育部體系）
  - heterophony{1,2,3}  破音字讀音優先序（1 = 最常用＝預設讀音）

衍生檔已入 repo（執行期／部署期零外網，照 5cq vendor 燒入哲學）。
本腳本只在「要更新資料」時手動執行；網路失敗不影響既有檔案。

格式：{"字": "主音|次音|…"}（排序＋逐行，diff 穩定、截斷可偵測）
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/openvanilla/McBopomofo/master/Source/Data/"
FILES = ["BPMFBase.txt", "heterophony1.list", "heterophony2.list",
         "heterophony3.list"]
OUT = (Path(__file__).resolve().parents[1]
       / "src/stroke_order/web/static/zhuyin_tw.json")
VALID = re.compile(r"^[ㄅ-ㄩˊˇˋ˙]+$")
UA = {"User-Agent": "Mozilla/5.0 (stroke-order build script)"}


def _fetch(name: str) -> str:
    req = urllib.request.Request(BASE + name, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def main() -> int:
    try:
        texts = {n: _fetch(n) for n in FILES}
    except Exception as e:  # noqa: BLE001 — graceful：保留既有檔案
        print(f"[build_zhuyin_tw] fetch failed, keeping existing file: {e}")
        return 0 if OUT.exists() else 1

    readings: dict[str, list[str]] = {}
    for ln in texts["BPMFBase.txt"].splitlines():
        parts = ln.split()
        if len(parts) < 2 or len(parts[0]) != 1:
            continue
        ch, zy = parts[0], parts[1]
        readings.setdefault(ch, [])
        if zy not in readings[ch]:
            readings[ch].append(zy)

    hetero: dict[str, str] = {}
    for i in (1, 2, 3):
        for ln in texts[f"heterophony{i}.list"].splitlines():
            p = ln.split()
            if len(p) == 2 and len(p[0]) == 1 and p[0] not in hetero:
                hetero[p[0]] = p[1]

    out: dict[str, str] = {}
    for ch in sorted(readings):
        rs = [r for r in readings[ch] if VALID.match(r)]
        if not rs:
            continue
        h = hetero.get(ch)
        if h and h in rs:
            rs = [h] + [r for r in rs if r != h]
        out[ch] = "|".join(rs)

    OUT.write_text(
        json.dumps(out, ensure_ascii=False, indent=0) + "\n",
        encoding="utf-8", newline="\n")
    print(f"[build_zhuyin_tw] wrote {len(out)} entries -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
