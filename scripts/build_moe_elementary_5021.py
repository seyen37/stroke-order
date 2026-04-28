"""
Build 教育部國小學童常用字頻 5021 cover-set dataset.

CANONICAL SOURCE: 教育部「國小學童常用字詞調查報告書」(民國91年3月二版,
2002), 字頻總表 5,021 字, ranked by actual usage frequency from elementary
school student writing samples.

The companion DBF file (SHREST1.DBF) had 48 PUA-encoded 異體字 that needed
cross-reference to recover. This .txt source provides clean Unicode for all
5,021 entries, including 4 CJK Ext A + 2 CJK Ext B+ chars (the modern
Unicode equivalents of the original Big5-ETEN PUA codepoints).

Note: source contains 3 editorial duplicates (成、躍、咕) — likely from
manual transcription. Deduped at first occurrence (highest rank wins),
giving 5,018 unique chars. Cover-set name keeps "5021" for traceability
to the official publication number.

Output: src/stroke_order/components/coversets/moe_elementary_5021.json

Each entry: rank (1-5018), trad, simp, frequency_rank (= rank).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import opencc


def _is_cjk(c: str) -> bool:
    if len(c) != 1:
        return False
    code = ord(c)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0x20000 <= code <= 0x3FFFF
    )


def main():
    src = Path("/sessions/friendly-dreamy-noether/mnt/uploads/"
               "教育部字庫5021字.txt")
    if not src.exists():
        print(f"ERROR: {src} not found")
        sys.exit(1)

    text = src.read_text(encoding="utf-8-sig")  # strips BOM automatically

    chars_in_order = []
    for c in text:
        if _is_cjk(c):
            chars_in_order.append(c)

    print(f"Total CJK chars (with dups): {len(chars_in_order)}")

    # Dedupe preserving first occurrence (highest frequency rank wins)
    seen = set()
    chars_unique = []
    duplicates = []
    for c in chars_in_order:
        if c in seen:
            duplicates.append(c)
        else:
            seen.add(c)
            chars_unique.append(c)

    print(f"Unique chars: {len(chars_unique)}")
    print(f"Duplicates removed: {duplicates}")

    # Generate simp counterparts
    t2s = opencc.OpenCC("t2s")
    chars_simp = [t2s.convert(c) for c in chars_unique]
    simp_diff = sum(1 for s, t in zip(chars_simp, chars_unique) if s != t)
    print(f"simp/trad differ: {simp_diff} ({100*simp_diff/len(chars_unique):.1f}%)")

    entries = []
    for i, (s, t) in enumerate(zip(chars_simp, chars_unique)):
        entries.append({
            "index":           i + 1,
            "frequency_rank":  i + 1,         # rank in original publication
            "trad":            t,
            "simp":            s,
            "same":            s == t,
            "unicode":         f"U+{ord(t):04X}",
        })

    out = {
        "title": "教育部國小常用字頻表 5021",
        "english_title":
            "MOE-Taiwan Elementary School Common Character Frequency (5,021)",
        "source":
            "中華民國教育部《國小學童常用字詞調查報告書》"
            "（民國91年3月二版，2002年），字頻總表",
        "url":
            "https://language.moe.gov.tw/001/Upload/files/SITE_CONTENT/"
            "M0001/PRIMARY/shrest2-1.htm?open",
        "description":
            "台灣教育部 2002 年國小學童作文取樣統計之字頻總表，"
            "依實際使用頻率高低排序，rank 1（的）為最高頻字。"
            "vs 4808 標準字表的差異：4808 是 standards-based curation, "
            "5021 是 actual-usage frequency。原始公告 5,021 字含 3 個編輯"
            "重複（成、躍、咕），dedupe 後 5,018 unique chars。"
            "rank 即 frequency order（高頻字優先）。",
        "char_count":               len(entries),
        "original_published_count": 5021,
        "duplicates_in_source":     [str(c) for c in duplicates],
        "trad_simp_mismatch_count": simp_diff,
        "entries": entries,
    }

    out_path = Path(
        "src/stroke_order/components/coversets/moe_elementary_5021.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {out_path}: {len(entries)} chars")


if __name__ == "__main__":
    main()
