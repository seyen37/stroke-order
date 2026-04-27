"""
Traditional ↔ Simplified Chinese character variant conversion.

The 5000.TXT decomposition dataset has a mixed bag — mostly traditional
(朱邦復 is based in Taiwan) but some simplified substitutes (e.g. 温
rather than 溫). When a user queries one form but the dataset only has
the other, this module provides the missing link.

Primary backend is ``opencc-python-reimplemented`` (pure Python, small).
If that's not installed we fall back to a tiny built-in dictionary of
the most common繁↔簡 pairs — enough for the handful of entries that
actually differ between dataset and user input.
"""
from __future__ import annotations

from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Fallback dictionary — ~100 most common 繁↔簡 pairs seen in typical Chinese
# text. Used only when ``opencc`` is unavailable. Based on MOE 常用字 + the
# specific chars we observe in 5000.TXT.
#
# Keys are both directions (trad→simp mapping; reversed lookup covers simp→trad)
# ---------------------------------------------------------------------------

_TRAD_TO_SIMP: dict[str, str] = {
    "溫": "温", "國": "国", "會": "会", "體": "体", "學": "学",
    "們": "们", "個": "个", "為": "为", "這": "这", "來": "来",
    "時": "时", "實": "实", "說": "说", "對": "对", "發": "发",
    "還": "还", "與": "与", "現": "现", "裡": "里", "麼": "么",
    "樣": "样", "開": "开", "聽": "听", "點": "点", "動": "动",
    "長": "长", "從": "从", "讓": "让", "兒": "儿", "給": "给",
    "問": "问", "過": "过", "號": "号", "頭": "头", "門": "门",
    "關": "关", "見": "见", "經": "经", "總": "总", "說": "说",
    "誰": "谁", "話": "话", "陳": "陈", "讀": "读", "識": "识",
    "學": "学", "寫": "写", "覺": "觉", "臉": "脸", "親": "亲",
    "愛": "爱", "壞": "坏", "應": "应", "當": "当", "東": "东",
    "車": "车", "馬": "马", "鳥": "鸟", "魚": "鱼", "龍": "龙",
    "雞": "鸡", "鴨": "鸭", "風": "风", "雲": "云", "電": "电",
    "書": "书", "筆": "笔", "紙": "纸", "畫": "画", "圖": "图",
    "聲": "声", "語": "语", "詞": "词", "數": "数", "藝": "艺",
    "術": "术", "業": "业", "產": "产", "務": "务", "團": "团",
    "財": "财", "貨": "货", "買": "买", "賣": "卖", "負": "负",
    "請": "请", "謝": "谢", "難": "难", "離": "离", "歲": "岁",
    "醫": "医", "藥": "药", "療": "疗", "療": "疗",
}

# Build simp→trad reverse map automatically
_SIMP_TO_TRAD: dict[str, str] = {v: k for k, v in _TRAD_TO_SIMP.items()}


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

_opencc_t2s: Optional[Callable[[str], str]] = None
_opencc_s2t: Optional[Callable[[str], str]] = None


def _ensure_opencc() -> bool:
    """Try to set up OpenCC. Returns True if successful."""
    global _opencc_t2s, _opencc_s2t
    if _opencc_t2s is not None:
        return True
    try:
        from opencc import OpenCC
    except ImportError:
        return False
    try:
        _opencc_t2s = OpenCC("t2s").convert
        _opencc_s2t = OpenCC("s2t").convert
        return True
    except Exception:
        return False


def to_simplified(char: str) -> str:
    """Convert traditional → simplified; returns original if already simplified."""
    if _ensure_opencc():
        return _opencc_t2s(char)  # type: ignore[misc]
    return _TRAD_TO_SIMP.get(char, char)


def to_traditional(char: str) -> str:
    """Convert simplified → traditional; returns original if already traditional."""
    if _ensure_opencc():
        return _opencc_s2t(char)  # type: ignore[misc]
    return _SIMP_TO_TRAD.get(char, char)


def variants_of(char: str) -> list[str]:
    """
    Return the list of alternative forms to try (excluding the original).
    Typically just one: the traditional↔simplified counterpart.
    """
    alts: list[str] = []
    s = to_simplified(char)
    if s != char:
        alts.append(s)
    t = to_traditional(char)
    if t != char and t not in alts:
        alts.append(t)
    return alts


__all__ = [
    "to_simplified",
    "to_traditional",
    "variants_of",
]
