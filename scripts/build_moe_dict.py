#!/usr/bin/env python3
"""T2：教育部《國語辭典簡編本》開放資料 → 單字索引 bundle。

輸入：教育部公眾授權網下載的 xlsx（45,131 筆詞條、15 欄）
輸出：``data/moe_dict_bundle.jsonl.gz``——每行一個單字，附該字的
      注音／部首／總筆畫／釋義，以及以該字開頭的常用詞（含各詞的
      注音與釋義；釋義內含教育部原文的 ``[例]`` 例句）。

授權（重要）：資料為「創用CC-姓名標示-禁止改作 3.0 臺灣」——**內容不得
改作**。本腳本只做「技術上必要的格式轉換」：
  - xlsx → JSONL（載體轉換）
  - ``_x000D_`` → 換行（還原 xlsx 的 CR 編碼假影，非改寫內容）
  - 選取欄位與筆數上限（節錄，不修改任何一條釋義的文字）
釋義文字**逐字保留**，不摘要、不改寫、不截斷。

用法：
    python scripts/build_moe_dict.py <下載的 xlsx> [-o data/moe_dict_bundle.jsonl.gz]

資料來源：https://language.moe.gov.tw/001/Upload/Files/site_content/M0001/respub/index.html
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import sys
from pathlib import Path

#: 每個字保留的常用詞上限（控制 bundle 體積；純節錄、不改內容）
MAX_WORDS_PER_CHAR = 12

# xlsx 欄位索引（依教育部 2014 版匯出格式）
COL_NAME, COL_RADICAL, COL_STROKES, COL_ZHUYIN, COL_DEF = 0, 2, 3, 6, 13


def _clean(v) -> str:
    """xlsx 值 → 字串；還原 CR 假影。不改寫內容。"""
    if v is None:
        return ""
    return str(v).replace("_x000D_", "\n").strip()


def build(xlsx_path: Path, out_path: Path) -> dict:
    try:
        import openpyxl
    except ImportError:
        sys.exit("需要 openpyxl：pip install openpyxl")

    wb = openpyxl.load_workbook(str(xlsx_path), read_only=True)
    ws = wb.active

    singles: dict[str, dict] = {}
    by_head: dict[str, list] = collections.defaultdict(list)
    total = 0

    for row in ws.iter_rows(min_row=2, values_only=True):
        name = _clean(row[COL_NAME])
        if not name:
            continue
        total += 1
        zhuyin = _clean(row[COL_ZHUYIN])
        definition = _clean(row[COL_DEF])
        if len(name) == 1:
            if name not in singles:          # 多音字取首見（其餘為變體列）
                singles[name] = {
                    "zy": zhuyin,
                    "rad": _clean(row[COL_RADICAL]),
                    "sc": row[COL_STROKES] if isinstance(row[COL_STROKES], int) else None,
                    "df": definition,
                }
        elif definition:
            by_head[name[0]].append({"w": name, "zy": zhuyin, "df": definition})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_words = 0
    with gzip.open(out_path, "wt", encoding="utf-8", compresslevel=9) as f:
        for ch in sorted(singles):
            words = by_head.get(ch, [])[:MAX_WORDS_PER_CHAR]
            n_words += len(words)
            rec = {"c": ch, **singles[ch], "w": words}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return {
        "rows": total,
        "chars": len(singles),
        "words": n_words,
        "bytes": out_path.stat().st_size,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("xlsx", type=Path, help="教育部簡編本 xlsx")
    ap.add_argument("-o", "--out", type=Path,
                    default=Path("data/moe_dict_bundle.jsonl.gz"))
    a = ap.parse_args()
    if not a.xlsx.is_file():
        sys.exit(f"找不到 {a.xlsx}")
    stats = build(a.xlsx, a.out)
    print(f"[build_moe_dict] 詞條 {stats['rows']} → 單字 {stats['chars']}、"
          f"常用詞 {stats['words']}；{a.out}（{stats['bytes'] // 1024} KB）")


if __name__ == "__main__":
    main()
