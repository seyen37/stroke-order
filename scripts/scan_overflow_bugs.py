#!/usr/bin/env python3
"""
Batch-scan g0v JSON for characters that:

  1. Overflow the 2048 em-square (coordinates outside [0, 2048])
  2. Have stroke count mismatching a declared expected value

Input  : either a directory of cached JSONs, or a list of characters on stdin
Output : CSV report with one row per problematic character, written to
         ``docs/overflow_scan_report.csv`` (or ``--out`` path)

Usage
-----

    # scan all chars currently cached in data/g0v_cache/
    python scripts/scan_overflow_bugs.py

    # scan a specific chars list (one per line from stdin)
    python scripts/scan_overflow_bugs.py --chars-file chars.txt

    # increase the overflow tolerance in em units (default 0)
    python scripts/scan_overflow_bugs.py --tolerance 100
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Add src/ to sys.path so we can run this script without pip install
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT / "src"))

from stroke_order.ir import EM_SIZE  # noqa: E402
from stroke_order.sources.g0v import CharacterNotFound, G0VSource  # noqa: E402
from stroke_order.validation import KNOWN_BUGS, validate_character  # noqa: E402


def iter_chars_from_cache(cache_dir: Path):
    """Yield (char, hex_code) for every .json in cache."""
    for p in sorted(cache_dir.glob("*.json")):
        hex_code = p.stem
        try:
            ch = chr(int(hex_code, 16))
        except ValueError:
            continue
        yield ch, hex_code


def iter_chars_from_file(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for ch in line:
            yield ch, f"{ord(ch):x}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache-dir", type=Path,
                   default=ROOT / "data" / "g0v_cache")
    p.add_argument("--chars-file", type=Path,
                   help="File with characters to scan (instead of cache).")
    p.add_argument("--out", type=Path,
                   default=ROOT / "docs" / "overflow_scan_report.csv")
    p.add_argument("--tolerance", type=float, default=0.0,
                   help="em-units of overflow to tolerate (default 0).")
    p.add_argument("--allow-network", action="store_true",
                   help="Fetch missing JSONs from g0v (slower).")
    args = p.parse_args()

    src = G0VSource(cache_dir=args.cache_dir, allow_network=args.allow_network)

    if args.chars_file:
        iterator = list(iter_chars_from_file(args.chars_file))
    else:
        iterator = list(iter_chars_from_cache(args.cache_dir))

    print(f"Scanning {len(iterator)} characters…", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[list] = []
    overflow_count = 0
    count_mismatch = 0
    missing_count = 0
    ok_count = 0

    for ch, hex_code in iterator:
        try:
            c = src.get_character(ch)
        except CharacterNotFound:
            missing_count += 1
            rows.append([ch, hex_code.upper(), "missing", 0, "", "", "", ""])
            continue
        except Exception as e:  # noqa: BLE001
            rows.append([ch, hex_code.upper(), "error", 0, "", "", "", str(e)])
            continue

        bb = c.bbox
        ox = max(0, -bb.x_min, bb.x_max - EM_SIZE)
        oy = max(0, -bb.y_min, bb.y_max - EM_SIZE)
        has_overflow = ox > args.tolerance or oy > args.tolerance

        expected = KNOWN_BUGS.get(hex_code, (None,))[0]
        stroke_ct = c.stroke_count
        has_count_mismatch = expected is not None and stroke_ct != expected

        issues: list[str] = []
        if has_overflow:
            issues.append(f"overflow(Δx={ox:.0f},Δy={oy:.0f})")
            overflow_count += 1
        if has_count_mismatch:
            issues.append(f"count_mismatch(got {stroke_ct}, expected {expected})")
            count_mismatch += 1

        if issues:
            rows.append([
                ch, hex_code.upper(), "issue", stroke_ct,
                f"{bb.x_min:.0f}", f"{bb.y_min:.0f}",
                f"{bb.x_max:.0f}", f"{bb.y_max:.0f}",
                "; ".join(issues),
            ])
        else:
            ok_count += 1

    # Write CSV report (only rows with issues)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["char", "unicode_hex", "status", "stroke_count",
                    "x_min", "y_min", "x_max", "y_max", "issues"])
        for row in rows:
            w.writerow(row)

    print(f"\n=== Scan summary ===", file=sys.stderr)
    print(f"  Total scanned:   {len(iterator)}", file=sys.stderr)
    print(f"  OK:              {ok_count}", file=sys.stderr)
    print(f"  Overflow:        {overflow_count}", file=sys.stderr)
    print(f"  Count mismatch:  {count_mismatch}", file=sys.stderr)
    print(f"  Missing:         {missing_count}", file=sys.stderr)
    print(f"\nReport: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
