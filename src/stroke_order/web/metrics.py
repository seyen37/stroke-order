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

跨重啟累計（v0.14.296，Blueprint v1.2 方案 C）
-------------------------------------------
Render 免費層閒置 15 分鐘就休眠、醒來磁碟全空——上面的補償實測不夠用
（10-18 讀 /api/metrics：since＝剛被叫醒那一刻、計數全空）。設了
``STROKE_ORDER_METRICS_GIST_ID``＋``STROKE_ORDER_METRICS_GIST_TOKEN`` 時，
總數同步到一個私密 GitHub Gist：

- **開機讀回**（:func:`restore_from_gist`）：遠端總數**加進**記憶體計數
  （合併而非覆蓋——讀回完成前進來的請求不會被吃掉）。此模式下不讀本機
  檔，Gist 是唯一事實源，避免同一份次數算兩次。
- **定期推送**（最多每 :data:`PUSH_INTERVAL` 秒一次，背景執行緒）＋
  **關機推送**（:func:`push_now`，uvicorn shutdown；休眠前會收到）。
- **未讀回不推送**：讀回失敗時推送前先重試讀回，仍失敗就放棄這次——
  寧可少存一輪，也不拿較小的計數覆蓋遠端歷史。

沒設這兩個環境變數＝行為與先前完全相同（零網路呼叫，測試鎖住）。
Gist 只放同一份四鍵快照；其修訂歷史是 ≥10 分鐘粒度的**總數**快照，
仍無任何請求脈絡。

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

__all__ = ["GIST_FILENAME", "MISSING_CHAR_CAP", "PUSH_INTERVAL",
           "persistence_mode", "push_now", "record_missing_char",
           "record_mode", "reset_for_tests", "restore_from_gist", "snapshot"]

_ENV_DIR = "STROKE_ORDER_METRICS_DIR"
MISSING_CHAR_CAP = 500

#: flush 節流（秒）——record 高頻呼叫時最多這個頻率寫檔
_FLUSH_INTERVAL = 5.0

_GIST_ID_ENV = "STROKE_ORDER_METRICS_GIST_ID"
_GIST_TOKEN_ENV = "STROKE_ORDER_METRICS_GIST_TOKEN"
_EPHEMERAL_ENV = "STROKE_ORDER_EPHEMERAL_STORAGE"
GIST_FILENAME = "stroke-order-metrics.json"
_GIST_API = "https://api.github.com/gists/"
_GIST_TIMEOUT = 10.0

#: 推送節流（秒）——GitHub API 額度與 Gist 修訂數都夠用的頻率
PUSH_INTERVAL = 600.0

_TRUE_STRINGS = {"1", "true", "yes", "on", "y", "t"}

_lock = threading.Lock()
_state: dict | None = None      # {"since": iso, "mode": {..}, "missing_char": {..}, "missing_char_overflow": int}
_last_flush = 0.0
_restored = False               # Gist 總數已併入 _state
_last_push = 0.0
_push_thread: threading.Thread | None = None


def _gist_cfg() -> tuple[str, str] | None:
    gid = os.environ.get(_GIST_ID_ENV, "").strip()
    tok = os.environ.get(_GIST_TOKEN_ENV, "").strip()
    return (gid, tok) if gid and tok else None


def _gist_api(method: str, gist_id: str, token: str,
              payload: dict | None = None) -> dict:
    """GitHub Gist REST 呼叫（測試以 monkeypatch 替換）。"""
    import requests
    r = requests.request(
        method, _GIST_API + gist_id, json=payload, timeout=_GIST_TIMEOUT,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    r.raise_for_status()
    return r.json()


def persistence_mode() -> str:
    """計數存在哪裡——給 /api/metrics 誠實標示。

    ``gist``＝已與 Gist 接上、跨重啟累計｜``gist-pending``＝設了 Gist
    但尚未讀回成功（這段期間的計數仍會在下次成功時併入）｜
    ``ephemeral``＝主機宣告磁碟暫時性且無 Gist（休眠即歸零）｜
    ``local``＝本機磁碟。
    """
    if _gist_cfg():
        return "gist" if _restored else "gist-pending"
    if os.environ.get(_EPHEMERAL_ENV, "").strip().lower() in _TRUE_STRINGS:
        return "ephemeral"
    return "local"


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
    if p.is_file() and _gist_cfg() is None:   # Gist 模式：遠端是唯一事實源
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
    _maybe_push_locked()


def _merge_remote_locked(remote: dict) -> None:
    s = _load_locked()
    for k, v in (remote.get("mode") or {}).items():
        if isinstance(v, int) and v > 0:
            s["mode"][k] = s["mode"].get(k, 0) + v
    mc = s["missing_char"]
    for k, v in (remote.get("missing_char") or {}).items():
        if not isinstance(v, int) or v <= 0:
            continue
        if k in mc or len(mc) < MISSING_CHAR_CAP:
            mc[k] = mc.get(k, 0) + v
        else:
            s["missing_char_overflow"] += v
    ov = remote.get("missing_char_overflow", 0)
    if isinstance(ov, int) and ov > 0:
        s["missing_char_overflow"] += ov
    rs = remote.get("since")
    if isinstance(rs, str) and rs < s["since"]:   # ISO-8601 UTC 可字串比較
        s["since"] = rs


def restore_from_gist() -> bool:
    """開機讀回 Gist 總數併入記憶體。成功（含 Gist 尚無檔案）回 True。

    冪等：已讀回就直接 True，不會重複加。網路在鎖外做。
    """
    global _restored
    cfg = _gist_cfg()
    if cfg is None:
        return False
    with _lock:
        if _restored:
            return True
    try:
        data = _gist_api("GET", *cfg)
        f = (data.get("files") or {}).get(GIST_FILENAME)
        remote = json.loads(f["content"]) if f and f.get("content") else {}
        if not isinstance(remote, dict):
            remote = {}
    except Exception as e:              # noqa: BLE001 — 網路/格式皆不致命
        log.warning("metrics gist restore failed: %s", e)
        return False
    with _lock:
        if not _restored:               # 併發的另一條讀回已完成就不再加
            _merge_remote_locked(remote)
            _restored = True
    log.info("metrics gist restored (mode keys=%d)", len(remote.get("mode") or {}))
    return True


def push_now() -> bool:
    """把目前總數寫進 Gist。未讀回成功時先重試讀回，仍失敗就不推。"""
    cfg = _gist_cfg()
    if cfg is None:
        return False
    if not restore_from_gist():
        log.warning("metrics gist push skipped: not restored (no clobber)")
        return False
    with _lock:
        content = json.dumps(_load_locked(), ensure_ascii=False)
    try:
        _gist_api("PATCH", *cfg,
                  payload={"files": {GIST_FILENAME: {"content": content}}})
        return True
    except Exception as e:              # noqa: BLE001
        log.warning("metrics gist push failed: %s", e)
        return False


def _maybe_push_locked() -> None:
    """flush 的尾巴：節流後丟背景執行緒推送（不在請求路徑上做網路）。"""
    global _last_push, _push_thread
    if _gist_cfg() is None:
        return
    if _push_thread is not None and _push_thread.is_alive():
        return
    now = time.monotonic()
    if _last_push and now - _last_push < PUSH_INTERVAL:
        return
    _last_push = now
    _push_thread = threading.Thread(target=push_now, name="metrics-gist-push",
                                    daemon=True)
    _push_thread.start()


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
    global _state, _last_flush, _restored, _last_push, _push_thread
    t = _push_thread
    if t is not None:
        t.join(timeout=5)
    with _lock:
        _state = None
        _last_flush = 0.0
        _restored = False
        _last_push = 0.0
        _push_thread = None
