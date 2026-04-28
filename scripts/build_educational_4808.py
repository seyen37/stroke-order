"""
Build 教育部常用國字標準字體表 (4,808 字) cover-set dataset.

CANONICAL SOURCE: official PDF published by 教育部國語推行委員會
(民國71年9月1日, 1982-09-01).
File metadata Author: moejsmpc (教育部 國語會).

Earlier prototypes used a third-party Gist; we found that the Gist
contained 1 char with a PRC variant codepoint (U+5F5D 彝) instead of the
Taiwan standard (U+5F5E 彞). This script parses the official PDF directly
to ensure Taiwan-variant integrity. See decision log
2026-04-28_phase_a_complete.md.

Output: src/stroke_order/components/coversets/educational_4808.json

Each entry includes the official 教育部字號 (e.g. A00001 ~ A04808),
which makes per-char traceability back to government records possible.

Usage:
    # First, extract the PDF text via pdftotext (poppler-utils):
    pdftotext -layout 17694982751288.pdf /tmp/moe_full.txt
    python3 scripts/build_educational_4808.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import opencc


def main():
    src = Path("/tmp/moe_full.txt")
    if not src.exists():
        print("ERROR: /tmp/moe_full.txt not found. Extract from PDF:")
        print("  pdftotext -layout PATH/TO/MOE_4808.pdf /tmp/moe_full.txt")
        sys.exit(1)

    text = src.read_text(encoding="utf-8")

    # Each entry line:  "00001 A00001   4e00      一"
    line_re = re.compile(
        r"\s*(?P<idx>\d{5})\s+(?P<moe_id>[A-Z]\d{5})\s+"
        r"(?P<hex>[0-9a-f]{4,5})\s+(?P<char>\S)"
    )
    entries_raw = []
    for line in text.splitlines():
        m = line_re.match(line)
        if not m:
            continue
        d = m.groupdict()
        entries_raw.append({
            "idx": int(d["idx"]),
            "moe_id": d["moe_id"],
            "hex": d["hex"].lower(),
            "char": d["char"],
        })

    print(f"Parsed {len(entries_raw)} entries from official PDF")
    if len(entries_raw) != 4808:
        print(f"WARNING: expected 4808 entries, got {len(entries_raw)}")

    # Sanity: entries should be in 流水序 1..4808
    for i, e in enumerate(entries_raw, 1):
        if e["idx"] != i:
            print(f"WARNING: entry #{i} has idx={e['idx']}")
            break

    # Cross-check Unicode hex matches actual char (defensive: log only,
    # don't fail). Known case: A02149 汨 — PDF metadata hex 6c69 vs
    # rendered char U+6C68. Source of truth = actual char (what user writes).
    hex_mismatches = [
        e for e in entries_raw if int(e["hex"], 16) != ord(e["char"])
    ]
    if hex_mismatches:
        print(f"NOTE: {len(hex_mismatches)} hex/char mismatch in PDF metadata"
              f" (trusted char as source of truth)")
        for m in hex_mismatches:
            print(f"  {m['moe_id']}: char={m['char']!r} (U+{ord(m['char']):04X})"
                  f" vs PDF metadata U+{m['hex'].upper()}")

    chars_trad = [e["char"] for e in entries_raw]

    # simp counterparts via OpenCC (TW → CN)
    t2s = opencc.OpenCC("t2s")
    chars_simp = [t2s.convert(c) for c in chars_trad]
    simp_diff = sum(1 for s, t in zip(chars_simp, chars_trad) if s != t)
    print(f"simp/trad differ: {simp_diff} ({100*simp_diff/len(chars_trad):.1f}%)")

    # Build entries with MOE id metadata. Unicode codepoint derived from
    # actual char (not PDF metadata, which has 1 known error in A02149).
    entries = []
    for raw, simp, trad in zip(entries_raw, chars_simp, chars_trad):
        entries.append({
            "index": raw["idx"],
            "moe_id": raw["moe_id"],          # 教育部字號 A00001 ~ A04808
            "unicode": f"U+{ord(trad):04X}",  # derived from char, not PDF
            "simp": simp,
            "trad": trad,
            "same": simp == trad,
        })

    out = {
        "title": "教育部常用國字標準字體表 4808",
        "english_title": "MOE-Taiwan Standard Common Chinese Characters (4,808)",
        "source":
            "中華民國教育部國語推行委員會《常用國字標準字體表》"
            "（民國71年9月1日公告，1982-09-01）",
        "url": "https://language.moe.gov.tw/material/info?m=9fe3ff5a-5a8c-4817-9e60-6337dd55a509",
        "description":
            "台灣教育部官方公告之常用國字標準字體表，共 4,808 字，"
            "每字附原始公告之教育部字號 (A00001 ~ A04808)。"
            "原始來源直接解析官方 PDF（Author: moejsmpc），"
            "確保台灣標準字體變體完整性 (T-variant integrity)。",
        "char_count": len(entries),
        "trad_simp_mismatch_count": simp_diff,
        "entries": entries,
    }

    out_path = Path(
        "src/stroke_order/components/coversets/educational_4808.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {out_path}: {len(entries)} chars")
    print(f"Includes 教育部字號 metadata for full traceability.")


if __name__ == "__main__":
    main()
