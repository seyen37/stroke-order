"""
Radical classification (朱邦復 2018 四大類部首).

From《漢字基因講座》第 104 集〈部首分類〉, 朱邦復 divides radicals into
four semantic categories with sub-groups:

1. **本存** (naturally-existing, organic forms)
   - 本體 (natural bodies): 日月金水土气玉石山
   - 植物: 木禾黍麻米麥瓜竹艸
   - 肢體: 目舌身頁肉血羽皮毛爪骨鼻角心手足髟耳尸齒
   - 動物: 魚龜鼠鳥黽鹿隹虍貝豸豕羊虫犬馬牛

2. **人造** (human-made, geometric forms)
   - 食衣: 臼缶豆皿酉衣巾革韋糸
   - 住行: 門龠瓦車舟几广宀冂邑阜
   - 起居: 鼎鼓鬲爻隶斤斗寸
   - 工作: 耒聿网殳矢矛匕弓刀

3. **規範** (abstract concepts)
   - 定義: 歹方齊高面首長工么囗士夊小大里疋
   - 根源: 力光色音彡香火
   - 現象: 谷黃雨青赤白夕鬼風穴疒黑巛

4. **應用** (associative/relational concepts)
   - 訊息: 言采老辛甘爿片玄冫曰文無龍
   - 事理: 彳鬥非辵走行見用比支攴八飛止艮
   - 關係: 生父子女氏干欠隶臣自至入立又

The categorization is a one-to-one lookup (radical char → category +
subcategory). ~136 radicals total, covering the traditional 214-radical
set's core members.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RadicalCategory:
    """Classification of a single radical character."""
    category: str      # 本存 / 人造 / 規範 / 應用
    subcategory: str   # 本體 / 植物 / 肢體 / 動物 / 食衣 / 住行 / ...


# ---------------------------------------------------------------------------
# Master table — radical char → (category, subcategory)
# Sourced verbatim from 朱邦復《漢字基因講座》0104
# ---------------------------------------------------------------------------

_GROUPS: list[tuple[str, str, str]] = [
    # (category, subcategory, radical_chars)
    ("本存", "本體",  "日月金水土气玉石山"),
    ("本存", "植物",  "木禾黍麻米麥瓜竹艸"),
    ("本存", "肢體",  "目舌身頁肉血羽皮毛爪骨鼻角心手足髟耳尸齒"),
    ("本存", "動物",  "魚龜鼠鳥黽鹿隹虍貝豸豕羊虫犬馬牛"),
    ("人造", "食衣",  "臼缶豆皿酉衣巾革韋糸"),
    ("人造", "住行",  "門龠瓦車舟几广宀冂邑阜"),
    ("人造", "起居",  "鼎鼓鬲爻隶斤斗寸"),
    ("人造", "工作",  "耒聿网殳矢矛匕弓刀"),
    ("規範", "定義",  "歹方齊高面首長工么囗士夊小大里疋"),
    ("規範", "根源",  "力光色音彡香火"),
    ("規範", "現象",  "谷黃雨青赤白夕鬼風穴疒黑巛"),
    ("應用", "訊息",  "言采老辛甘爿片玄冫曰文無龍"),
    ("應用", "事理",  "彳鬥非辵走行見用比支攴八飛止艮"),
    ("應用", "關係",  "生父子女氏干欠隶臣自至入立又"),
]


def _build_table() -> dict[str, RadicalCategory]:
    table: dict[str, RadicalCategory] = {}
    for cat, sub, chars in _GROUPS:
        for ch in chars:
            table[ch] = RadicalCategory(category=cat, subcategory=sub)
    return table


_TABLE: dict[str, RadicalCategory] = _build_table()


def lookup(char: str) -> Optional[RadicalCategory]:
    """Return the RadicalCategory for `char`, or None if not classified."""
    return _TABLE.get(char)


def all_radicals() -> list[str]:
    return sorted(_TABLE.keys())


__all__ = ["RadicalCategory", "lookup", "all_radicals"]
