"""
Phase 5cd — 組件家族反查（component → 含它的字）與部首教學路線。

VISION.md 組件化路線缺的那座橋：既有 ``decompose`` 是「字 → 組件」
的正向分解，這裡補上反向索引——給一個組件（典型是康熙部首），列出
cover-set 裡所有含它的字，並把 214 部首按「家族大小」排成教學序。

設計要點：

1. **部首變體映射**：IDS 分解的葉子用的是變體形（海 → 氵 而非 水）。
   ``RADICAL_VARIANTS`` 收錄傳統楷書常見偏旁變體，查「水」的家族時
   同時比對 {水, 氵, 氺}。只收無歧義的字形變體，不做語意部首歸屬
   （組件教學關心的是「形」的覆蓋，不是字典學歸部）。
2. **排序＝複雜度代理**：家族字按（IDS 葉數, 字碼）升冪。真實筆畫數
   需要載入整個字集的字形資料（每字一次 I/O，5000 字不可行），葉數
   是「結構簡→繁」的無 I/O 代理，教學直覺一致（江 → 海 → 灣）。
3. **per-coverset 快取**：葉集合表對整個 cover-set 建一次
   （``functools.lru_cache``），之後任何組件查家族都是集合交集。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from .coverset import load_coverset
from .decompose import decompose, get_leaf_components
from .ids import default_ids_map

# ---------------------------------------------------------------------------
# 部首 → 傳統楷書偏旁變體（形變體，非語意歸部）
# ---------------------------------------------------------------------------

RADICAL_VARIANTS: dict[str, tuple[str, ...]] = {
    "人": ("亻",),
    "刀": ("刂",),
    "心": ("忄", "⺗"),
    "手": ("扌",),
    "攴": ("攵",),
    "水": ("氵", "氺"),
    "火": ("灬",),
    "爪": ("爫",),
    "犬": ("犭",),
    "玉": ("⺩",),
    "示": ("礻",),
    "糸": ("糹",),
    "网": ("罒", "⺲"),
    "老": ("耂",),
    "肉": ("⺼",),
    "艸": ("艹", "⺿"),
    "衣": ("衤",),
    "言": ("訁",),
    "辵": ("辶", "⻍", "⻌"),
    "邑": ("⻏",),
    "金": ("釒",),
    "阜": ("⻖",),
    "食": ("飠",),
    "竹": ("⺮",),
    "襾": ("覀",),
}


def component_targets(component: str,
                      include_variants: bool = True) -> frozenset[str]:
    """查詢時要比對的形集合：組件本身 ＋（可選）它的偏旁變體。"""
    if not include_variants:
        return frozenset((component,))
    return frozenset((component, *RADICAL_VARIANTS.get(component, ())))


# ---------------------------------------------------------------------------
# 葉集合表（per cover-set，一次建表之後全部查詢走交集）
# ---------------------------------------------------------------------------


@lru_cache(maxsize=8)
def _leaf_table(coverset_name: str) -> dict[str, frozenset[str]]:
    """cover-set 內每個字的葉組件集合（含字本身，讓「查木得木」成立）。"""
    cs = load_coverset(coverset_name)
    ids_map = default_ids_map()
    table: dict[str, frozenset[str]] = {}
    for ch in cs.chars:
        leaves = get_leaf_components(ch, ids_map)
        table[ch] = frozenset(leaves) | {ch}
    return table


def _complexity_key(ch: str, ids_map: dict[str, str]) -> tuple[int, int]:
    """排序鍵：（IDS 葉數, 字碼）——結構簡→繁的無 I/O 代理。"""
    return (len(decompose(ch, ids_map)), ord(ch))


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def component_family(
    component: str,
    coverset_name: str,
    *,
    include_variants: bool = True,
    limit: Optional[int] = None,
) -> dict:
    """cover-set 裡所有含 ``component``（或其變體）的字，簡→繁排序。

    回傳 dict：component / coverset / targets（實際比對的形集合）/
    family_size（未截斷總數）/ chars（截斷後清單）。
    """
    targets = component_targets(component, include_variants)
    table = _leaf_table(coverset_name)
    ids_map = default_ids_map()
    fam = [ch for ch, leaves in table.items() if targets & leaves]
    # 部首本字（與其變體）永遠領頭——教學順序「先寫部首、再寫家族」。
    # （部首本字常有筆形級 IDS 分解，純葉數排序會把它推到中段。）
    fam.sort(key=lambda ch: ((0 if ch in targets else 1),
                             *_complexity_key(ch, ids_map)))
    total = len(fam)
    if limit is not None:
        fam = fam[:limit]
    return {
        "component": component,
        "coverset": coverset_name,
        "targets": sorted(targets),
        "family_size": total,
        "chars": fam,
    }


def radical_route(
    radicals: str,
    coverset_name: str,
    *,
    band_of: Optional[dict[str, int]] = None,
    min_family: int = 1,
    preview: int = 5,
) -> list[dict]:
    """把一串部首排成教學路線：家族大的先教（覆蓋槓桿最高）。

    ``radicals``：部首字串（呼叫端傳 kangxi ALL_RADICALS——components
    層不 import exporters，維持分層方向）。``band_of``：部首 → 筆畫數
    （可選，來自 RADICAL_BANDS）。家族小於 ``min_family`` 的部首剔除
    （該 cover-set 用不到的部首不進教學序）。

    排序：家族大小降冪 → 部首筆畫升冪 → 字碼。
    """
    entries = []
    for r in radicals:
        fam = component_family(r, coverset_name)
        if fam["family_size"] < min_family:
            continue
        entries.append({
            "radical": r,
            "strokes": (band_of or {}).get(r),
            "family_size": fam["family_size"],
            "preview": fam["chars"][:preview],
        })
    entries.sort(key=lambda e: (-e["family_size"],
                                e["strokes"] if e["strokes"] else 99,
                                ord(e["radical"])))
    return entries


__all__ = [
    "RADICAL_VARIANTS",
    "component_targets",
    "component_family",
    "radical_route",
]
