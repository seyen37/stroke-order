"""
Build 朱邦復 漢字基因 5000 會意字 cover-set dataset.

Input: data/5000_wuqian.txt (already in repo — see decomposition.py parser).
Output: src/stroke_order/components/coversets/wuqian_5000.json

Source: 朱邦復《字易》、《漢字基因講座》— 2012 年初稿 (香港文化傳信公司 + 中國
        動漫集團之中娛文化公司協議公開)。

Why this cover-set:
  Provides a structurally-curated character set of ~3,700-3,800 CJK chars,
  selected for 會意 (compound-meaning) decomposability. Compared to the
  TCS 808 set (high-frequency cross-CJK), this is a deeper Chinese-only set
  with explicit head/tail decomposition baked in — useful for users who want
  to write a more comprehensive Chinese personal font.

Note: this is NOT the 教育部 4808 standard set. Naming kept honest.
"""
from __future__ import annotations

import json
from pathlib import Path

import opencc


def _is_cjk(c: str) -> bool:
    """True for CJK Unified Ideographs + CJK Ext A.

    Excludes Bopomofo, entity-encoded glyphs (`&~...;`), Latin, etc.
    """
    if len(c) != 1:
        return False
    code = ord(c)
    return 0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF


def main():
    from stroke_order.decomposition import default_db

    db = default_db()
    # DecompositionDB lazy-loads — call get() once to trigger parse.
    db.get("明")
    raw_chars = sorted(db._map.keys())
    chars_trad = [c for c in raw_chars if _is_cjk(c)]
    print(f"Raw entries in DB: {len(raw_chars)}")
    print(f"After CJK filter:  {len(chars_trad)}")
    print(f"Excluded examples: {[c for c in raw_chars if not _is_cjk(c)][:10]}")

    # Generate simp counterparts via OpenCC (TW → CN)
    t2s = opencc.OpenCC("t2s")
    chars_simp = [t2s.convert(c) for c in chars_trad]

    mismatches = sum(1 for s, t in zip(chars_simp, chars_trad) if s != t)
    print(f"Simp/trad differ: {mismatches} ({100*mismatches/len(chars_trad):.1f}%)")

    entries = []
    for i, (s, t) in enumerate(zip(chars_simp, chars_trad)):
        entries.append({
            "index": i + 1,
            "simp": s,
            "trad": t,
            "same": s == t,
        })

    out = {
        "title": "朱邦復 漢字基因 5000 會意字",
        "english_title": "Chu Bang-Fu's Hanzi Genome 5000 Ideographic Compounds",
        "source": "朱邦復《字易》、《漢字基因講座》(2012 初稿)",
        "url": "https://www.cbflabs.com/",
        "description":
            "結構化 curation 的 5000 字集（實際 ~3,800 字），"
            "強調會意分解的可能性。vs TCS 808 共用高頻集合，"
            "這份是更深入的中文個人字庫候選集。",
        "char_count": len(entries),
        "trad_simp_mismatch_count": mismatches,
        "entries": entries,
    }

    out_path = Path("src/stroke_order/components/coversets/wuqian_5000.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\nWrote {out_path}: {len(entries)} chars")


if __name__ == "__main__":
    main()
