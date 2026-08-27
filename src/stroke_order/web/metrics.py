"""
D2（Blueprint Phase 0）——需求儀器化：匿名使用計數。

§99 的落地：**「等需求證據」不是被動等**。兩個感測器：

1. **模式使用計數**——每個功能面（grid/steps/stencil/…）被呼叫幾次。
   路線圖的 gate（G0/G1）要靠它判「哪個模式真的有人用」。
2. **缺字請求計數**——筆順鏈 404 時記下是哪個字。這是 R2 GlyphWiki
   翻案的感測器（ADR `2026-08-20_r2_glyphwiki_spike.md`）：需求證據
   自己長出來，不用人猜。

隱私（設計約束，測試鎖住）
--------------------------
**只數次數，不記人**：無 IP、無 UA、無 cookie、無時間序列——counter
的 key 只有功能名與字元。這不是分析平台，是路線圖的溫度計。

持久化（誠實標注）
------------------
計數落地到 ``{METRICS_DIR}/counters.json``（預設
``~/.stroke-order/metrics/``，env ``STROKE_ORDER_METRICS_DIR`` 覆蓋）。
**Render free tier 磁碟是暫時的**——重新部署歸零。所以：(a) snapshot
帶 ``since``（本檔案起算時刻），消費端知道視窗多長；(b) 每次 flush 同時
打一行結構化 log（``metrics-flush``），Render 的 log 保留歷史。相對訊號
（哪個模式多、缺字有沒有出現）不受歸零影響——gate 判定用的正是相對訊號。

防濫用：缺字 key 上限 :data:`MISSING_CHAR_CAP`（超過只累計
``missing_char_overflow`` 總數，不再收新 key）——防掃描灌爆檔案。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

__all__ = ["MISSING_CHAR_CAP", "record_missing_char", "record_mode",
           "reset_for_tests", "snapshot"]

_ENV_DIR = "STROKE_ORDER_METRICS_DIR"
MISSING_CHAR_CAP = 500

#: flush 節流（秒）——record 高頻呼叫時最多這個頻率寫檔
_FLUSH_INTERVAL = 5.0

_lock = threading.Lock()
_state: dict | None = None      # {"since": iso, "mode": {..}, "missing_char": {..}, "missing_char_overflow": int}
_last_flush = 0.0


def _dir() -> Path:
    d = os.environ.get(_ENV_DIR)
    return Path(d).expanduser() if d else (
        Path.home() / ".stroke-order" / "metrics")


def _path() -> Path:
    return _dir() / "counters.json"


def _fresh() -> dict:
    return {"since": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": {}, "missing_char": {}, "missing_char_overflow": 0}


def _load_locked() -> dict:
    global _state
    if _state is not None:
        return _state
    p = _path()
    if p.is_file():
        try:
            d = json.loads(p.read_text("utf-8"))
            if isinstance(d, dict) and "mode" in d and "missing_char" in d:
                d.setdefault("missing_char_overflow", 0)
                _state = d
                return _state
        except (OSError, ValueError):
            pass                     # 壞檔 → 重新開始（計數不是帳本）
    _state = _fresh()
    return _state


def _flush_locked(force: bool = False) -> None:
    global _last_flush
    now = time.monotonic()
    if not force and now - _last_flush < _FLUSH_INTERVAL:
        return
    _last_flush = now
    try:
        d = _dir()
        d.mkdir(parents=True, exist_ok=True)
        tmp = _path().with_suffix(".tmp")
        tmp.write_text(json.dumps(_state, ensure_ascii=False), "utf-8")
        tmp.replace(_path())
        # Render 磁碟暫時性的補償：log 留歷史（結構化、可事後彙整）
        log.info("metrics-flush %s", json.dumps(_state, ensure_ascii=False))
    except OSError as e:             # 寫不進去就只活在記憶體——不擋主流程
        log.debug("metrics flush failed: %s", e)


def record_mode(bucket: str) -> None:
    """某功能面被使用一次。``bucket`` 來自 server 的前綴表（有界集合）。"""
    with _lock:
        s = _load_locked()
        s["mode"][bucket] = s["mode"].get(bucket, 0) + 1
        _flush_locked()


def record_missing_char(char: str) -> None:
    """筆順鏈查無此字——R2 翻案感測器。只記字元本身，無任何請求脈絡。"""
    if not char or len(char) != 1:
        return
    with _lock:
        s = _load_locked()
        mc = s["missing_char"]
        if char in mc or len(mc) < MISSING_CHAR_CAP:
            mc[char] = mc.get(char, 0) + 1
        else:
            s["missing_char_overflow"] += 1
        _flush_locked()


def snapshot() -> dict:
    """目前計數（含 since 視窗起點）。呼叫時強制 flush 一次。"""
    with _lock:
        s = _load_locked()
        _flush_locked(force=True)
        return json.loads(json.dumps(s))     # deep copy


def reset_for_tests() -> None:
    """測試用：清記憶體快取（配合 env 指到 tmp dir）。"""
    global _state, _last_flush
    with _lock:
        _state = None
        _last_flush = 0.0
