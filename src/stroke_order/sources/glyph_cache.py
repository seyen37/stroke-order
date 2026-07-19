"""5ey-E：字型源字形快取的共用 LRU 上限。

三個外框字型源（崇羲篆體、CNS、教育部隸書）各有一份
``self._cache: dict[str, Character]``——原本無上限。單次頁面的唯一字
數不大，但長會期跨模式累積（抄經＋週期表＋字帖…）可達數千字，
每個外框 Character 數十至數百 KB，在 Render 免費層 512MB 下是
記憶體棘輪的一環。統一上限：超過即淘汰最久未用（LRU）。

上限取 384（5fb 自 1024 調降）：實測單一複雜字形 Character 深層
約 63KB → 384 條 ≈ 24MB/源 上限；仍涵蓋「整頁心經（117 唯一字）＋
週期表（~120）」兩個工作集，重載成本只在真正冷門字出現。

5fb 追加：FONT_RECYCLE_AFTER——fontTools 懶載入的 TTFont 會把解析過
的表格全留在句柄裡（實測 31 字形殘留 58MB＝每字 ~1.9MB），心經整頁
篆書逐批載入到一半就把 512MB 免費層撐爆（使用者實機：進度條一半
502）。對策：每渲染 N 個字形就「丟句柄」（不 close——執行緒仍在用的
舊句柄由 GC 收；cmap 與字型度量由呼叫端自快取，重開極廉）。
"""
from __future__ import annotations

from collections import OrderedDict

#: 每個字型源的字形快取上限（entries）。
GLYPH_CACHE_MAX = 384

#: 每渲染 N 個字形丟一次 TTFont 句柄（懶解析殘留歸還；見模組 docstring）
FONT_RECYCLE_AFTER = 48


def lru_put(cache: OrderedDict, key, value, max_entries: int = GLYPH_CACHE_MAX):
    """寫入並維持 LRU 上限（呼叫端 hit 時自行 ``move_to_end``）。"""
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > max_entries:
        cache.popitem(last=False)
