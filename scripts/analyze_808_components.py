"""
Analyze component coverage of 中日韓共用常用 808 漢字 list.

Uses CHISE/cjkvi-ids decomposition data to:
1. Decompose each of 808 chars into leaf components (recursively)
2. Compute distinct component count & frequency distribution
3. Compute reverse coverage: what % of common 3500 chars can be composed
   from the 808-char component set?
4. Output report to docs/analysis/808_coverage_report.md

Usage:
    # First time, download IDS data:
    curl -sL https://raw.githubusercontent.com/cjkvi/cjkvi-ids/master/ids.txt \\
        -o data/ids.txt
    python3 scripts/analyze_808_components.py
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

# Unicode IDS structure descriptors (U+2FF0-U+2FFB, U+31EF) — written with
# explicit \u escapes to avoid invisible-char corruption.
IDS_DESCRIPTORS = set(chr(c) for c in range(0x2FF0, 0x2FFC)) | {chr(0x31EF)}

# Variation selectors U+FE00-U+FE0F (decoration markers, not structural)
VARIATION_SELECTORS = re.compile(r"[︀-️]")

# Compound markers U+2460-U+2473 (①-⑳) — placeholders for unencoded components
COMPOUND_MARKERS = re.compile(r"[①-⑳]")


def parse_ids_file(path: Path) -> dict:
    """Parse ids.txt → {char: ids_string}.

    File format:
      U+CODEPOINT\\tcharacter\\tIDS_string [\\toptional regional variants]
    Lines starting with # are comments. Skip lines with fewer than 3 fields.
    """
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        char = parts[1]
        ids_str = parts[2]
        # Strip leading region tag like [GTKJV]
        if ids_str.startswith("[") and "]" in ids_str:
            ids_str = ids_str.split("]", 1)[1]
        # Remove trailing region tag like ⿰日月[GTJK]
        if "[" in ids_str and ids_str.endswith("]"):
            ids_str = ids_str[: ids_str.rindex("[")]
        ids_str = VARIATION_SELECTORS.sub("", ids_str)
        out[char] = ids_str
    return out


def decompose(char: str, ids_map: dict, max_depth: int = 10,
              _depth: int = 0, _seen=None) -> list:
    """Recursively decompose char to leaf components.

    A leaf is a character that:
    - Has no IDS entry, OR
    - Its IDS is itself (atomic), OR
    - Reached max_depth, OR
    - Already in the recursion path (cycle prevention).

    Compound markers (①②...) are skipped — they represent unencoded sub-components.
    """
    if _seen is None:
        _seen = set()
    if char in _seen or _depth >= max_depth:
        return [char]
    _seen = _seen | {char}

    ids_str = ids_map.get(char, char)
    # Atomic: ids equals char itself or no IDS info
    if ids_str == char or not ids_str:
        return [char]
    # Strip IDS descriptors and compound markers, get child components
    leaves = []
    for c in ids_str:
        if c in IDS_DESCRIPTORS:
            continue
        if COMPOUND_MARKERS.match(c):
            continue
        # Recurse
        sub_leaves = decompose(c, ids_map, max_depth, _depth + 1, _seen)
        leaves.extend(sub_leaves)
    if not leaves:
        return [char]
    return leaves


def load_808() -> list:
    """Load 808 character dataset via the components package loader."""
    from stroke_order.components import load_coverset
    cs = load_coverset("cjk_common_808")
    return [
        {"index": i + 1, "simp": s, "trad": t, "same": s == t}
        for i, (s, t) in enumerate(zip(cs.chars_simp, cs.chars))
    ]


def load_common_3500() -> list:
    """Load 3500 commonly used chars from project's existing 5000_wuqian.txt
    (top 3500 by some ordering)."""
    path = Path("data/5000_wuqian.txt")
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    chars = []
    seen = set()
    for c in text:
        if "一" <= c <= "鿿" and c not in seen:
            chars.append(c)
            seen.add(c)
            if len(chars) >= 3500:
                break
    return chars


def analyze(use_trad: bool = True):
    """Run full analysis on 808 list (trad version) and produce report."""
    print("Loading IDS data ...")
    ids_path = Path("/tmp/ids_data/ids.txt")
    if not ids_path.exists():
        ids_path = Path("data/ids.txt")
    if not ids_path.exists():
        print("ERROR: ids.txt not found. Download with:")
        print("  curl -sL https://raw.githubusercontent.com/cjkvi/cjkvi-ids/master/ids.txt -o data/ids.txt")
        sys.exit(1)
    ids_map = parse_ids_file(ids_path)
    print(f"  Loaded {len(ids_map)} IDS entries")

    # Quick sanity check
    sample = ids_map.get("明", "MISSING")  # 明
    print(f"  Sanity check: 明 → {sample!r}")
    if sample == "" or sample == "MISSING":
        print("  ERROR: parser broken")
        sys.exit(1)

    print("Loading 808 character set ...")
    entries = load_808()
    chars_808 = [e["trad" if use_trad else "simp"] for e in entries]
    chars_808_set = set(chars_808)
    print(f"  {len(chars_808)} chars (using {'trad' if use_trad else 'simp'} forms)")

    # Decompose each 808 char to leaves
    print("\nDecomposing 808 chars to leaf components ...")
    all_leaves = []
    char_to_leaves = {}
    for c in chars_808:
        leaves = decompose(c, ids_map)
        char_to_leaves[c] = leaves
        all_leaves.extend(leaves)
    leaf_counter = Counter(all_leaves)
    distinct_leaves = set(leaf_counter)

    total_atomic_self = sum(1 for c in chars_808 if char_to_leaves[c] == [c])

    print(f"  Distinct leaf components: {len(distinct_leaves)}")
    print(f"  Total leaf occurrences: {sum(leaf_counter.values())}")
    print(f"  808 chars that are atomic (self-decompose): {total_atomic_self}")

    avg_leaves = sum(len(l) for l in char_to_leaves.values()) / len(chars_808)
    print(f"  Avg leaves per char: {avg_leaves:.2f}")

    # Top 30 most frequent components
    print("\nTop 30 most frequent leaf components:")
    for comp, count in leaf_counter.most_common(30):
        is_self = comp in chars_808_set
        marker = "(in 808)" if is_self else ""
        print(f"  {comp}  x {count:3d}  {marker}")

    # Reverse coverage
    print("\nReverse coverage analysis:")
    common_3500 = load_common_3500()
    coverage_stats = None
    sample_covered = []
    if not common_3500:
        print("  (Skipping: 5000_wuqian.txt not loaded)")
    else:
        fully_covered = []
        partially_covered = []
        not_covered = []
        for c in common_3500:
            if not c:
                continue
            target_leaves = set(decompose(c, ids_map))
            unmatched = target_leaves - distinct_leaves
            if not unmatched:
                fully_covered.append(c)
            elif len(unmatched) < len(target_leaves):
                partially_covered.append((c, list(unmatched)))
            else:
                not_covered.append(c)

        total = len(common_3500)
        print(f"  Common chars analyzed: {total}")
        print(f"  Fully covered by 808 components: {len(fully_covered)} "
              f"({100*len(fully_covered)/total:.1f}%)")
        print(f"  Partially covered: {len(partially_covered)} "
              f"({100*len(partially_covered)/total:.1f}%)")
        print(f"  Not covered: {len(not_covered)} "
              f"({100*len(not_covered)/total:.1f}%)")
        coverage_stats = {
            "common_total": total,
            "fully_covered": len(fully_covered),
            "partially_covered": len(partially_covered),
            "not_covered": len(not_covered),
            "fully_covered_pct": 100 * len(fully_covered) / total,
        }
        non_808_covered = [c for c in fully_covered if c not in chars_808_set]
        sample_covered = non_808_covered[:50]
        print("\n  Sample fully-covered chars (composed from 808 leaves):")
        print("   ", " ".join(sample_covered[:30]))

    # Save JSON report
    report = {
        "use_trad": use_trad,
        "char_count": len(chars_808),
        "atomic_self_count": total_atomic_self,
        "distinct_leaf_components": len(distinct_leaves),
        "total_leaf_occurrences": sum(leaf_counter.values()),
        "avg_leaves_per_char": round(avg_leaves, 2),
        "top_30_components": [
            {"component": c, "count": n, "in_808": c in chars_808_set}
            for c, n in leaf_counter.most_common(30)
        ],
        "coverage_stats": coverage_stats,
        "sample_composed_chars": sample_covered,
    }
    out_path = Path("docs/analysis/808_coverage_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\nJSON report -> {out_path}")

    return report, leaf_counter, char_to_leaves


def write_markdown_report(report: dict):
    cs = report.get("coverage_stats")
    lines = [
        "# 808 漢字表組件覆蓋率分析",
        "",
        "> 自動產出：`scripts/analyze_808_components.py`  ",
        "> 資料源：CHISE/cjkvi-ids（IDS 分解）+ 中日韓共用 808 漢字（TCS 2014）  ",
        f"> 使用字形：{'繁體' if report['use_trad'] else '簡體'}",
        "",
        "## 一、基本統計",
        "",
        f"- **808 字總數**：{report['char_count']}",
        f"- **自身即原子的字**：{report['atomic_self_count']}（無法再分解）",
        f"- **獨特葉組件數**：**{report['distinct_leaf_components']}**",
        f"- **葉組件總出現次數**：{report['total_leaf_occurrences']}",
        f"- **平均每字葉組件數**：{report['avg_leaves_per_char']}",
        "",
    ]

    if cs:
        lines.extend([
            "## 二、反向覆蓋率（核心指標）",
            "",
            "**問題**：寫了 808 字，能組合多少新字？",
            "",
            "**方法**：取常用 3500 字（從 `5000_wuqian.txt` 前 3500 字），對每個字遞迴分解到葉組件，檢查所有葉組件是否都在 808 字的葉組件集合裡。",
            "",
            "### 結果",
            "",
            "| 覆蓋程度 | 字數 | 占比 |",
            "|---|---|---|",
            f"| **完全覆蓋**（所有組件都在 808 裡）| **{cs['fully_covered']}** | **{cs['fully_covered_pct']:.1f}%** |",
            f"| 部分覆蓋 | {cs['partially_covered']} | {100*cs['partially_covered']/cs['common_total']:.1f}% |",
            f"| 未覆蓋 | {cs['not_covered']} | {100*cs['not_covered']/cs['common_total']:.1f}% |",
            f"| **總計** | {cs['common_total']} | 100% |",
            "",
            f"**關鍵發現**：寫 808 字後，理論上能合成常用 3500 字中的 **{cs['fully_covered_pct']:.1f}%**（{cs['fully_covered']} 字），槓桿率 **{(cs['fully_covered']+808)/808:.2f}x**。",
            "",
        ])

        if report.get("sample_composed_chars"):
            lines.extend([
                "### 可組合範例字（不在 808 裡，但能用 808 組件組合）",
                "",
                "```",
                "  ".join(report["sample_composed_chars"][:30]),
                "```",
                "",
            ])

    lines.extend([
        "## 三、Top 30 高頻組件",
        "",
        "出現最多次的葉組件——個人手寫資料品質會直接影響大部分字的合成品質。",
        "",
        "| # | 組件 | 出現次數 | 808 中? |",
        "|---|---|---|---|",
    ])
    for i, item in enumerate(report["top_30_components"], 1):
        in_808 = "✅" if item["in_808"] else "—"
        lines.append(f"| {i} | {item['component']} | {item['count']} | {in_808} |")

    lines.extend([
        "",
        "## 四、對 VISION.md 的啟示",
        "",
        f"VISION.md 預估「3500 常用字 → 600-800 獨特組件」。實證跑出來：",
        "",
        f"- 808 字實際分解出 **{report['distinct_leaf_components']} 個獨特葉組件**",
    ])
    if cs:
        lines.append(
            f"- 此 808 字組件集合能完全覆蓋常用 3500 字中的 "
            f"**{cs['fully_covered_pct']:.1f}%**（{cs['fully_covered']} 字）"
        )
    lines.extend([
        "",
        "對 VISION.md 的修訂建議：",
        "",
        f"1. 「最小覆蓋集」量級從理論預估（600-800）修正為**實證範圍 ~{report['distinct_leaf_components']} 葉組件 / ~808 字**",
    ])
    if cs:
        lines.append(
            f"2. 「寫 600 字覆蓋 3500」修正為「**寫 808 字 ⇒ 可寫 ~{808 + cs['fully_covered']} 字（808 + 額外 {cs['fully_covered']}）**」"
        )
    lines.extend([
        "3. 808 表本身就是個有國際背書、可直接採用的「現成最小覆蓋集」",
        "",
    ])
    out_path = Path("docs/analysis/808_coverage_report.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown report -> {out_path}")


if __name__ == "__main__":
    report, _, _ = analyze(use_trad=True)
    write_markdown_report(report)
