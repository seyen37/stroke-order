#!/usr/bin/env python3
"""Build-time 下載 vendor JS（opencv.js / opentype.min.js）— Phase 5cq。

Render buildCommand 用法（照 render_fetch_fonts.sh 的慣例）::

    STROKE_ORDER_VENDOR_DIR=/opt/render/project/src/.vendor \
        python scripts/fetch_vendor.py

要點
----
- 寫進 **git checkout 路徑**（/opt/render/project/src/…），不是
  $HOME——Render build 使用者的 home 是 ephemeral，不會存活到
  runtime 容器。runtime 以同一個 STROKE_ORDER_VENDOR_DIR 環境
  變數讀同一路徑（見 render.yaml envVars）。
- 燒入部署後，伺服器執行期**零外網依賴**：啟動預熱直接命中
  快取、/vendor 端點直接出檔。
- 單檔失敗只警告、**不中斷 build**——runtime 端點保有 5ck 的
  惰性補抓，網站照常運作。
- 抓檔邏輯直接復用 server 的 _ensure_vendor_cached（同一組
  來源清單、尺寸門檻、鎖與原子換檔），單一事實來源。
"""
from __future__ import annotations

import os
import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dest = os.environ.get("STROKE_ORDER_VENDOR_DIR")
    if argv:
        dest = argv[0]
        os.environ["STROKE_ORDER_VENDOR_DIR"] = dest
    if not dest:
        print("usage: STROKE_ORDER_VENDOR_DIR=<dir> "
              "python scripts/fetch_vendor.py  (或以第一個參數指定目錄)")
        return 2

    # import 放在 dest 確立之後——_ensure_vendor_cached 讀環境變數
    from stroke_order.web.routes.pages import (
        _OPENCV_CACHE_FNAME,
        _OPENCV_MIN_BYTES,
        _OPENCV_SOURCES,
        _OPENTYPE_MIN_BYTES,
        _OPENTYPE_SOURCES,
        _ensure_vendor_cached,
    )

    # 5da：opencv 快取檔名帶版本（單一事實源在 web/routes/pages.py）——
    # pin 升級時 build 自動抓新檔，舊檔閒置無妨
    for fname, sources, min_bytes in (
        (_OPENCV_CACHE_FNAME, _OPENCV_SOURCES, _OPENCV_MIN_BYTES),
        ("opentype.min.js", _OPENTYPE_SOURCES, _OPENTYPE_MIN_BYTES),
    ):
        try:
            p = _ensure_vendor_cached(fname, sources, min_bytes)
            print(f"[fetch_vendor] OK  {fname}: "
                  f"{p.stat().st_size:,} bytes -> {p}")
        except Exception as e:              # noqa: BLE001 — 不中斷 build
            print(f"[fetch_vendor] WARN {fname} 下載失敗：{e} "
                  "（runtime /vendor 端點會惰性補抓，build 照常）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
