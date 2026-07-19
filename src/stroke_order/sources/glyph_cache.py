"""5ey-E：字型源字形快取的共用 LRU 上限。

三個外框字型源（崇羲篆體、CNS、教育部隸書）各有一份
``self._cache: dict[str, Character]``——原本無上限。單次頁面的唯一字
數不大，但長會期跨模式累積（抄經＋週期表＋字帖…）可達數千字，
每個外框 Character 數十至數百 KB，在 Render 免費層 512MB 下是
記憶體棘輪的一環。統一上限：超過即淘汰最久未用（LRU）。

上限取 1024：涵蓋「整頁心經（117 唯一字）＋週期表（~120）＋常用
教學字集」數個工作集仍綽綽有餘，重載成本只在真正冷門字出現。
"""
from __future__ import annotations

from collections import OrderedDict

#: 每個字型源的字形快取上限（entries）。
GLYPH_CACHE_MAX = 1024


def lru_put(cache: OrderedDict, key, value, max_entries: int = GLYPH_CACHE_MAX):
    """寫入並維持 LRU 上限（呼叫端 hit 時自行 ``move_to_end``）。"""
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > max_entries:
        cache.popitem(last=False)
