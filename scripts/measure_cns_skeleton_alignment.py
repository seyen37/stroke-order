"""
Phase 5ap-A3a — measurement script.

Compare the CNS canonical N-stroke spec against what
``apply_cns_outline_mode(c, "skeleton")`` currently produces, across a
curated sample spanning complexity tiers. Output: a per-tier alignment
rate and a per-character breakdown so we can decide whether A3b
junction-aware splitting is worth building.

Run:
    STROKE_ORDER_CNS_FONT_DIR=/tmp/cns-fonts \\
    STROKE_ORDER_CNS_PROPERTIES_DIR=/tmp/cns11643 \\
    python scripts/measure_cns_skeleton_alignment.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from stroke_order.sources.cns_font import (
    CNSFontSource, apply_cns_outline_mode,
)
from stroke_order.sources.cns_strokes import CNSStrokes
from stroke_order.sources.g0v import CharacterNotFound


# Curated sample: ~100 characters across 5 complexity tiers.
# Picked from common usage (倉頡口訣, 千字文 opening, common surnames,
# everyday words) so the result is representative of typical user input.
TIERS = {
    "簡單 (1-3 strokes)":
        "一二三十人入大小山子木水火土工又之口日月也七八九了刀力",
    "中等 (4-6 strokes)":
        "永王玉田白用石立目石生甲申先光全共字安宇守因回好",
    "中重 (7-10 strokes)":
        "李吳張陳林東京冷雨青草花長明社姓念音夜時計訊海書",
    "複雜 (11-15 strokes)":
        "國園圓圈得從接著復雜想感新領歲廠廢應辦電試該認",
    "極複雜 (16+ strokes)":
        "學藝鬱繁戀體鏡鸞讚襲議護驗鑽顧醫聲聽",
}


def main() -> None:
    src = CNSFontSource()
    strokes_db = CNSStrokes()

    if not src.is_ready():
        print("ERROR: CNS fonts not installed; set STROKE_ORDER_CNS_FONT_DIR")
        sys.exit(1)
    if not strokes_db.is_ready():
        print("ERROR: CNS Properties not installed; "
              "set STROKE_ORDER_CNS_PROPERTIES_DIR")
        sys.exit(1)

    # Phase 5aq — test 3 modes side-by-side:
    #   v1:        legacy walker only (prefer_g0v=False)
    #   v2 + g0v:  Path 1 g0v prior + legacy fallback (default)
    overall = {"v1": [0, 0], "g0v": [0, 0]}
    tier_results: list[tuple[str, dict, list[tuple]]] = []

    for tier_name, chars in TIERS.items():
        rows = []
        per_tier = {"v1": [0, 0], "g0v": [0, 0]}
        for ch in chars:
            if ch.isspace():
                continue
            canonical = strokes_db.canonical_strokes(ch)
            if not canonical:
                rows.append((ch, "no-canon", "—", "—"))
                continue
            try:
                c = src.get_character(ch)
            except CharacterNotFound:
                rows.append((ch, len(canonical), "no-font", "—"))
                continue
            sk_v1 = apply_cns_outline_mode(c, "skeleton", prefer_g0v=False)
            sk_g0v = apply_cns_outline_mode(c, "skeleton", prefer_g0v=True)
            n_v1, n_g0v = len(sk_v1.strokes), len(sk_g0v.strokes)
            ok_v1 = n_v1 == len(canonical)
            ok_g0v = n_g0v == len(canonical)
            per_tier["v1"][0] += int(ok_v1)
            per_tier["v1"][1] += 1
            per_tier["g0v"][0] += int(ok_g0v)
            per_tier["g0v"][1] += 1
            rows.append((ch, len(canonical), n_v1, n_g0v))
        tier_results.append((tier_name, per_tier, rows))
        for k in overall:
            overall[k][0] += per_tier[k][0]
            overall[k][1] += per_tier[k][1]

    # ---------- Print report ----------
    def _pct(p):
        return f"{p[0]/p[1]*100:5.1f}%" if p[1] else "  n/a"

    print("=" * 78)
    print("Phase 5aq — CNS skeleton alignment: v1 (legacy) vs +Path 1 (g0v prior)")
    print("=" * 78)
    print()
    for tier_name, per_tier, rows in tier_results:
        print(f"{tier_name}:  v1={_pct(per_tier['v1'])}  +Path1={_pct(per_tier['g0v'])}"
              f"  ({per_tier['v1'][1]} chars)")
        for ch, canon, n_v1, n_g0v in rows[:10]:
            mark_v1 = "✓" if n_v1 == canon else "✗"
            mark_g0v = "✓" if n_g0v == canon else "✗"
            print(f"   {ch}  canon={canon:<2}  "
                  f"v1={n_v1!s:<4} {mark_v1}   "
                  f"+g0v={n_g0v!s:<4} {mark_g0v}")
        if len(rows) > 10:
            print(f"   ... ({len(rows) - 10} more)")
        print()

    print("=" * 78)
    print(f"OVERALL  v1:     {_pct(overall['v1'])}  ({overall['v1'][0]}/{overall['v1'][1]})")
    print(f"OVERALL  +Path1: {_pct(overall['g0v'])}  ({overall['g0v'][0]}/{overall['g0v'][1]})")
    delta = overall['g0v'][0]/overall['g0v'][1] - overall['v1'][0]/overall['v1'][1] \
        if overall['v1'][1] else 0
    print(f"IMPROVEMENT: {delta * 100:+.1f} percentage points from Path 1 (g0v prior)")
    print("=" * 78)


if __name__ == "__main__":
    main()
