"""預抓 g0v 筆順資料進單一 bundle（data/g0v_bundle.json.gz）。

W1-D（架構健檢 2026-07-18）：讓常用字零網路命中，消除線上冷路徑。

⚠ 必須在「網路可達 g0v.github.io」的機器上跑（本機 PowerShell 即可）；
雲端沙箱／Render 資料中心出站會被擋（同 docs.opencv.org 教訓，PRINCIPLES §9）。

用法（專案根目錄）：

    python scripts/prefetch_g0v.py              # 預設常用 2000 字
    python scripts/prefetch_g0v.py --limit 5000 # 擴大字集
    python scripts/prefetch_g0v.py --chars 龍鳳 # 追加指定字

字集來源：data/5000_wuqian.txt 依「出現順序」取唯一 CJK 字（近似頻序），
另合併 data/g0v_cache/*.json 既有字與既有 bundle（可續跑、增量）。
輸出為 deterministic gzip（mtime=0、sort_keys）——重跑同字集位元組相同，
不會汙染 git diff。
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BUNDLE = DATA / "g0v_bundle.json.gz"
CACHE_DIR = DATA / "g0v_cache"
WUQIAN = DATA / "5000_wuqian.txt"
BASE_URL = "http://g0v.github.io/zh-stroke-data/json/"
UA = "stroke-order-prefetch/1.0 (+https://github.com/seyen37)"


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF


def common_chars(limit: int) -> list[str]:
    """從 5000_wuqian.txt 依出現順序取前 limit 個唯一 CJK 字。"""
    seen: dict[str, None] = {}
    text = WUQIAN.read_text(encoding="utf-8-sig")
    for ch in text:
        if _is_cjk(ch) and ch not in seen:
            seen[ch] = None
            if len(seen) >= limit:
                break
    return list(seen)


def load_existing() -> dict[str, list]:
    bundle: dict[str, list] = {}
    if BUNDLE.is_file():
        with gzip.open(BUNDLE, "rt", encoding="utf-8") as f:
            bundle.update(json.load(f))
    for p in sorted(CACHE_DIR.glob("*.json")):
        if p.stem not in bundle:
            try:
                bundle[p.stem] = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                print(f"  跳過壞檔 {p.name}", file=sys.stderr)
    return bundle


def fetch(hex_code: str) -> list | None:
    """抓單字；404 回 None，其他錯誤重試一次後放棄（回 None）。"""
    url = f"{BASE_URL}{hex_code}.json"
    for attempt in (1, 2):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == 2:
                print(f"  HTTP {e.code} @ {hex_code}，放棄", file=sys.stderr)
                return None
            time.sleep(1.0)
        except (urllib.error.URLError, OSError) as e:
            if attempt == 2:
                print(f"  網路錯誤 @ {hex_code}: {e}，放棄", file=sys.stderr)
                return None
            time.sleep(1.0)
    return None


def write_bundle(bundle: dict[str, list]) -> None:
    raw = json.dumps(
        bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    buf = io.BytesIO()
    # mtime=0 → deterministic 輸出，重跑同內容位元組相同
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(raw)
    BUNDLE.write_bytes(buf.getvalue())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=2000, help="常用字數上限（預設 2000）")
    ap.add_argument("--chars", default="", help="額外指定字（直接連寫）")
    ap.add_argument("--sleep", type=float, default=0.05, help="每字間隔秒數")
    args = ap.parse_args()

    wanted = common_chars(args.limit) + [c for c in args.chars if _is_cjk(c)]
    bundle = load_existing()
    todo = [c for c in wanted if f"{ord(c):x}" not in bundle]
    print(f"字集 {len(wanted)}、已有 {len(bundle)}、待抓 {len(todo)}")

    misses: list[str] = []
    fetched = 0
    try:
        for i, ch in enumerate(todo, 1):
            hex_code = f"{ord(ch):x}"
            data = fetch(hex_code)
            if data is None:
                misses.append(ch)
            else:
                bundle[hex_code] = data
                fetched += 1
            if i % 100 == 0:
                print(f"  {i}/{len(todo)}（成功 {fetched}、缺 {len(misses)}）")
                write_bundle(bundle)  # 每百字落盤一次，中斷可續跑
            time.sleep(args.sleep)
    except KeyboardInterrupt:
        print("中斷——已抓部分照樣寫入，可重跑續抓")

    write_bundle(bundle)
    size_mb = BUNDLE.stat().st_size / 1e6
    print(f"完成：bundle {len(bundle)} 字、{size_mb:.1f}MB → {BUNDLE}")
    if misses:
        print(f"g0v 無資料 {len(misses)} 字：{''.join(misses[:50])}"
              + ("…" if len(misses) > 50 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
