"""
Command-line entry point for the stroke-order package.

Examples
--------
    stroke-order convert 永 --format svg --out yong.svg
    stroke-order convert 永恩 --format gcode --out yongen.gcode --char-size 30
    stroke-order convert 日 --format json --out ri.json
    stroke-order convert 永 --format svg --mode both --show-numbers --rainbow
    stroke-order info 永          # print diagnostics
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from .classifier import classify_character
from .decomposition import default_db as default_decomp_db
from .exporters.gcode import GCodeOptions, save_gcode
from .exporters.json_polyline import save_json
from .exporters.svg import save_svg
from .hook_policy import apply_hook_policy
from .radicals import lookup as radical_lookup
from .smoothing import smooth_character
from .sources import CharacterNotFound, Source, make_source
from .validation import apply_known_bug_fix, validate_character


def _load_character(src: Source, char: str, apply_fix: bool,
                    hook_policy: str = "animation"):
    """Load + validate + repair + classify + hook-policy + smooth +
    decomposition lookup."""
    c = src.get_character(char)
    report = validate_character(c)
    if apply_fix and report.fixable:
        c, did_fix = apply_known_bug_fix(c)
        if did_fix:
            print(f"  [fix] {char}: {report.fix_description}", file=sys.stderr)
    for w in report.warnings:
        print(f"  [warn] {char}: {w}", file=sys.stderr)
    classify_character(c)
    apply_hook_policy(c, hook_policy)
    smooth_character(c)
    # Attach decomposition info if available (朱邦復 5000.TXT DB)
    decomp = default_decomp_db().get(char)
    if decomp is not None:
        c.decomposition = decomp
    # Attach radical classification (朱邦復 2018 部首分類)
    radical = radical_lookup(char)
    if radical is not None:
        c.radical_category = f"{radical.category}/{radical.subcategory}"
    return c


def cmd_convert(args: argparse.Namespace) -> int:
    src = make_source(args.source)
    chars = []
    for ch in args.chars:
        try:
            chars.append(_load_character(
                src, ch,
                apply_fix=not args.no_auto_fix,
                hook_policy=args.hook_policy,
            ))
        except CharacterNotFound as e:
            print(f"[error] {ch}: {e}", file=sys.stderr)
            return 2

    fmt = args.format
    out = args.out

    if fmt == "svg":
        if len(chars) != 1:
            print("[error] svg format currently supports one char at a time; "
                  "use gcode or json for multi-char input.",
                  file=sys.stderr)
            return 1
        save_svg(
            chars[0],
            out,
            mode=args.mode,
            show_numbers=args.show_numbers,
            rainbow=args.rainbow,
        )
    elif fmt == "gif":
        if len(chars) != 1:
            print("[error] gif format supports one char at a time",
                  file=sys.stderr)
            return 1
        try:
            from .exporters.gif import save_gif
        except ImportError as e:
            print(f"[error] GIF export needs cairosvg+Pillow: {e}",
                  file=sys.stderr)
            return 1
        save_gif(
            chars[0], out,
            frame_duration_ms=args.gif_duration,
            show_numbers=args.show_numbers,
        )
    elif fmt == "odp":
        try:
            from .exporters.odp import save_odp
        except ImportError as e:
            print(f"[error] ODP export needs cairosvg: {e}", file=sys.stderr)
            return 1
        save_odp(chars, out)
    elif fmt == "gcode":
        opts = GCodeOptions(
            char_size_mm=args.char_size,
            feed_rate=args.feed_rate,
            char_spacing_mm=args.char_spacing,
        )
        save_gcode(chars, out, opts=opts)
    elif fmt == "json":
        save_json(chars if len(chars) > 1 else chars[0], out)
    else:
        print(f"[error] unknown format: {fmt}", file=sys.stderr)
        return 1

    print(f"[ok] wrote {out} ({fmt}, {len(chars)} char"
          f"{'s' if len(chars)>1 else ''})", file=sys.stderr)
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    src = make_source(args.source)
    for ch in args.chars:
        try:
            c = src.get_character(ch)
        except CharacterNotFound as e:
            print(f"{ch}: NOT FOUND ({e})")
            continue
        report = validate_character(c)
        classify_character(c)
        print(f"{ch}  U+{c.unicode_hex.upper()}  "
              f"{c.stroke_count} strokes  signature={c.signature}  "
              f"source={c.data_source}")
        print(f"  validation: {report.summary()}")
        for w in report.warnings:
            print(f"    warn: {w}")
        for e in report.errors:
            print(f"    err:  {e}")
        print(f"  bbox: {c.bbox}  overflow={c.has_overflow}")
        # Decomposition info from 5000.TXT database
        decomp = default_decomp_db().get(ch)
        if decomp is not None:
            c.decomposition = decomp
            print(f"  decomp: {decomp.summary()}")
        # Radical classification (朱邦復 2018 四大類)
        radical = radical_lookup(ch)
        if radical is not None:
            c.radical_category = f"{radical.category}/{radical.subcategory}"
            print(f"  radical: {radical.category}/{radical.subcategory}")
        for s in c.strokes:
            print(f"    #{s.index+1}: kind={s.kind_code}({s.kind_name}) "
                  f"pts={len(s.raw_track)} hook={s.has_hook}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stroke-order",
        description="Convert Chinese characters to vector stroke data "
                    "(SVG / G-code / JSON polyline).",
    )
    p.add_argument("--offline", action="store_true",
                   help="Never fetch from network; use cache only.")
    p.add_argument("--source",
                   choices=["g0v", "mmh", "kanjivg", "auto", "tw", "cn", "jp"],
                   default="auto",
                   help="Data source: g0v=教育部繁體 / mmh=Make Me a Hanzi "
                        "(LGPL, 9574 字) / kanjivg=日本漢字 (CC-BY-SA) / "
                        "auto=g0v→mmh / tw=g0v→mmh / cn=mmh→g0v / "
                        "jp=kanjivg→mmh [default: auto]")
    sub = p.add_subparsers(dest="command", required=True)

    # convert
    c = sub.add_parser("convert", help="Convert character(s) to an output file.")
    c.add_argument("chars", help="One or more characters (e.g. '永' or '永恩日').")
    c.add_argument("--format", "-f",
                   choices=["svg", "gcode", "json", "gif", "odp"],
                   required=True)
    c.add_argument("--out", "-o", required=True, help="Output path.")
    c.add_argument("--no-auto-fix", action="store_true",
                   help="Do NOT apply known-bug repairs (gsyan888 list).")
    c.add_argument("--hook-policy", choices=["animation", "static"],
                   default="animation",
                   help="animation=保留動畫筆順的鉤 (預設) / static=去除鉤 "
                        "符合教育部靜態 PNG 字形")
    # SVG options
    c.add_argument("--mode", choices=["outline", "track", "both"],
                   default="outline",
                   help="(svg) outline=墨跡, track=骨架, both=疊加 [default: outline]")
    c.add_argument("--show-numbers", action="store_true",
                   help="(svg) overlay stroke-order numbers 1,2,3,...")
    c.add_argument("--rainbow", action="store_true",
                   help="(svg) use distinct color per stroke (debug)")
    # G-code options
    c.add_argument("--char-size", type=float, default=20.0,
                   help="(gcode) char width in mm [default: 20]")
    c.add_argument("--char-spacing", type=float, default=5.0,
                   help="(gcode) horizontal gap between chars in mm [default: 5]")
    c.add_argument("--feed-rate", type=int, default=3000,
                   help="(gcode) feed rate mm/min [default: 3000]")
    c.add_argument("--gif-duration", type=int, default=500,
                   help="(gif) ms per frame [default: 500 = 2 fps]")
    c.set_defaults(func=cmd_convert)

    # info
    i = sub.add_parser("info", help="Print diagnostics for character(s).")
    i.add_argument("chars")
    i.set_defaults(func=cmd_info)

    # grid (字帖 batch mode)
    g = sub.add_parser("grid", help="Multi-char 字帖 worksheet SVG.")
    g.add_argument("chars",
                   help="Characters to put on the worksheet (e.g. '你好世界').")
    g.add_argument("--out", "-o", required=True, help="Output SVG path.")
    g.add_argument("--cols", type=int, default=4,
                   help="Columns per row [default: 4]")
    g.add_argument("--guide",
                   choices=["tian", "mi", "hui", "plain", "none"],
                   default="tian",
                   help="Grid style: tian=田字格 mi=米字格 hui=回宮格 "
                        "plain=方格 none=無 [default: tian]")
    g.add_argument("--cell-style",
                   choices=["outline", "trace", "filled", "ghost", "blank"],
                   default="outline",
                   help="outline=墨跡 trace=軌跡 filled=墨+軌跡 "
                        "ghost=淡底(臨摹用) blank=空格 [default: outline]")
    g.add_argument("--cell-size", type=int, default=120,
                   help="Cell size in px [default: 120]")
    g.add_argument("--repeat", type=int, default=1,
                   help="Copies of each char in primary style [default: 1]")
    g.add_argument("--ghost-copies", type=int, default=0,
                   help="Faint ghost copies per char (for tracing) [default: 0]")
    g.add_argument("--blank-copies", type=int, default=0,
                   help="Empty cells per char (freehand practice) [default: 0]")
    g.set_defaults(func=cmd_grid)

    # serve (Web UI)
    s = sub.add_parser("serve", help="Start the local Web UI.")
    s.add_argument("--host", default="127.0.0.1",
                   help="Bind address [default: 127.0.0.1]")
    s.add_argument("--port", type=int, default=8000,
                   help="Port [default: 8000]")
    s.add_argument("--reload", action="store_true",
                   help="Auto-reload on code changes (dev)")
    s.set_defaults(func=cmd_serve)

    return p


def cmd_grid(args: argparse.Namespace) -> int:
    """字帖 batch mode — multi-char worksheet."""
    from .exporters.grid import save_grid_svg
    src = make_source(args.source)
    chars = []
    for ch in args.chars:
        try:
            chars.append(_load_character(
                src, ch, apply_fix=True, hook_policy="animation"))
        except CharacterNotFound as e:
            print(f"[warn] {ch}: {e} — skipping", file=sys.stderr)
    if not chars:
        print("[error] no characters loaded", file=sys.stderr)
        return 2
    save_grid_svg(
        chars, args.out,
        cols=args.cols,
        guide=args.guide,
        cell_style=args.cell_style,
        cell_size_px=args.cell_size,
        repeat_per_char=args.repeat,
        ghost_copies=args.ghost_copies,
        blank_copies=args.blank_copies,
    )
    print(f"[ok] wrote {args.out} "
          f"({len(chars)} chars × "
          f"{args.repeat + args.ghost_copies + args.blank_copies} cells = "
          f"{len(chars) * (args.repeat + args.ghost_copies + args.blank_copies)} cells)",
          file=sys.stderr)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        from .web.server import run as web_run
    except ImportError as e:
        print(f"[error] Web UI requires fastapi + uvicorn: {e}",
              file=sys.stderr)
        print("        pip install fastapi 'uvicorn[standard]'",
              file=sys.stderr)
        return 1
    print(f"[ok] starting stroke-order web UI on http://{args.host}:{args.port}/",
          file=sys.stderr)
    web_run(host=args.host, port=args.port, reload=args.reload)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # treat "chars" as iterable of single chars (only present on convert/info)
    if hasattr(args, "chars"):
        args.chars = list(args.chars)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
