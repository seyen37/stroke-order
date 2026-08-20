"""教育部《國語辭典簡編本》開放資料——單字字義／注音／部首／常用詞查詢（T2）。

資料由 ``scripts/build_moe_dict.py`` 從教育部公眾授權網下載的 xlsx 轉成
``data/moe_dict_bundle.jsonl.gz``（隨 repo 部署、離線可用、零外部服務）。

**授權：創用CC-姓名標示-禁止改作 3.0 臺灣（可商用、不得改作）**。因此本模組
只做「原文取出、原文呈現」——釋義字串逐字回傳，不摘要、不改寫、不截斷；
呼叫端（教學頁）亦須標示出處。詳 ``licenses/README.md``。

載入策略（承 §36 OOM 教訓）：bundle 每行一字，載入時**只留原始 JSON 字串**
不預先解析（6,028 行、解析後物件膨脹遠大於字串），查到哪個字才 loads 哪行；
threading.Lock 防 threadpool 併發首載重複讀檔。缺檔／壞檔靜默降級為空
（查詢一律回 found=False，教學頁退回老師自填——§87 不裝懂）。
"""
from __future__ import annotations

import gzip
import json
import logging
import re
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

__all__ = ["MOE_ATTRIBUTION", "MOE_LICENSE", "MOE_SOURCE_URL",
           "bundle_path", "first_sense", "is_ready", "lookup",
           "entry_count", "split_senses"]

BUNDLE_FILENAME = "moe_dict_bundle.jsonl.gz"

MOE_LICENSE = "創用CC-姓名標示-禁止改作 3.0 臺灣"
MOE_SOURCE_URL = (
    "https://language.moe.gov.tw/001/Upload/Files/site_content/"
    "M0001/respub/index.html"
)
MOE_ATTRIBUTION = (
    f"字義／注音／部首／常用詞取自 教育部《國語辭典簡編本》開放資料，"
    f"授權：{MOE_LICENSE}（原文呈現、未改作）。"
)

_cache: Optional[dict[str, str]] = None
_lock = threading.Lock()


def bundle_path() -> Path:
    """repo-root ``data/`` 下的 bundle（與 g0v_bundle 同慣例）。"""
    return Path(__file__).resolve().parents[3] / "data" / BUNDLE_FILENAME


def is_ready() -> bool:
    return bundle_path().is_file()


def _load() -> dict[str, str]:
    """懶載：dict[字, 該行原始 JSON 字串]——刻意不預先解析。"""
    global _cache
    if _cache is not None:
        return _cache
    with _lock:
        if _cache is not None:
            return _cache
        data: dict[str, str] = {}
        p = bundle_path()
        if p.is_file():
            try:
                with gzip.open(p, "rt", encoding="utf-8") as f:
                    for line in f:
                        line = line.rstrip("\n")
                        if not line:
                            continue
                        # 首欄固定為 {"c": "<字>"，直接取字元、免全行解析
                        i = line.find('"c":')
                        if i < 0:
                            continue
                        j = line.find('"', i + 4)
                        if j < 0 or j + 1 >= len(line):
                            continue
                        data[line[j + 1]] = line
                log.info("moe_dict bundle loaded: %d chars", len(data))
            except (OSError, ValueError) as e:
                log.warning("moe_dict bundle unreadable (%s) — 降級為空", e)
                data = {}
        _cache = data
        return _cache


def entry_count() -> int:
    return len(_load())


def lookup(char: str) -> Optional[dict]:
    """查單字。回傳 dict（zhuyin/radical/stroke_count/definition/words）或 None。

    釋義與例句為教育部原文，逐字保留（ND 授權要求）。
    """
    if not char or len(char) != 1:
        return None
    raw = _load().get(char)
    if raw is None:
        return None
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    return {
        "char": d.get("c", char),
        "zhuyin": d.get("zy") or "",
        "radical": d.get("rad") or "",
        "stroke_count": d.get("sc"),
        "definition": d.get("df") or "",
        "words": [
            {"word": w.get("w", ""), "zhuyin": w.get("zy", ""),
             "definition": w.get("df", "")}
            for w in (d.get("w") or [])
        ],
    }


# ---------------------------------------------------------------------
# W2：義項切分——「節錄」而非「摘要」
# ---------------------------------------------------------------------
#
# §88 把 ND 授權的線畫在這裡：**節錄（選取整個條目）可以，改寫／摘要／
# 截斷任何一條釋義不可以**。字帖格子放不下整條釋義（中位 36 字、90% 到
# 109 字），但**第一個完整義項**放得下（含例句中位 18 字、85.5% ≤32 字）
# ——取一個完整單元是選取，切斷一個單元不是。
#
# 分隔樣態實測（6,028 條，缺一不可）：
#   · 無換行           2,758 條   單一義項
#   · 單 ``\n`` 分隔    2,935 條   編號義項
#   · ``\n\n`` 分隔       335 條   編號義項
# 先前只切 ``\n\n`` 會讓 2,935 條的「第一義項」取到整條——所以這裡用
# ``\n+``。
_SENSE_SPLIT_RE = re.compile(r"\n+")


def split_senses(definition: str) -> list[str]:
    """釋義原文 → 義項清單。**每一項都是原文的連續子字串**（只切不改）。

    刻意**保留原本的「1.」「2.」編號**：拿掉序號是對內容動手，呈現端要
    標第幾義請用 :func:`first_sense` 回的 ``index``／``total``。
    """
    if not definition:
        return []
    return [s for s in (p.strip() for p in _SENSE_SPLIT_RE.split(definition))
            if s]


def first_sense(char: str) -> Optional[dict]:
    """單字 → 第一個**完整**義項。

    Returns
    -------
    ``{"text": 原文義項, "index": 1, "total": 義項總數}``，查無此字或無
    釋義時回 ``None``。

    ``text`` 是 ``lookup()["definition"]`` 的**連續子字串**（前後空白除
    外）——由 ``test_grid_info_footer`` 抽驗 300 條鎖住。呼叫端若因版面
    放不下，**應留白，不得自行截斷**（§88）。
    """
    entry = lookup(char)
    if entry is None:
        return None
    senses = split_senses(entry.get("definition") or "")
    if not senses:
        return None
    return {"text": senses[0], "index": 1, "total": len(senses)}


def reset_cache() -> None:
    """測試用：清掉懶載快取。"""
    global _cache
    with _lock:
        _cache = None
