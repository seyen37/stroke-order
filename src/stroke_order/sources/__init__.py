"""
Data source adapters.

All adapters implement the :class:`Source` protocol: given a single Chinese
character, return a :class:`stroke_order.ir.Character` with populated
strokes. Adapters normalize coordinates to the canonical 2048 Y-down em.

Available sources
-----------------

- :class:`G0VSource` — g0v/zh-stroke-data (MOE-derived). ~6063 繁體字.
  Educational/research use; commercial use has legal risk.
- :class:`MMHSource` — Make Me a Hanzi (Arphic-derived). ~9574 chars,
  simplified + traditional. LGPL — commercially usable.
- :class:`KanjiVGSource` — KanjiVG (CC BY-SA 3.0). Japanese kanji with
  rich structural metadata (stroke type classifier, radical grouping).
- :class:`AutoSource` — tries g0v first, falls back to MMH on
  CharacterNotFound. Sensible default for 中文 workflows.
- :class:`RegionAutoSource` — like AutoSource but region-aware. E.g.
  ``region='jp'`` tries KanjiVG first, falls back to MMH for Chinese
  chars not in KanjiVG.
"""
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from ..ir import Character
from .cns_font import CNSFontSource, default_cns_font_dir
from .g0v import CharacterNotFound, G0VSource
from .kanjivg import KanjiVGSource
from .mmh import MMHSource
from .moe_kaishu import MoeKaishuSource, default_kaishu_font_path
from .punctuation import PunctuationSource, supported_punctuation
from .user_dict import UserDictSource, default_user_dict_dir

Region = Literal["tw", "cn", "jp", "auto"]


@runtime_checkable
class Source(Protocol):
    """Minimum surface every adapter must implement."""

    def get_character(self, char: str) -> Character: ...


class AutoSource:
    """Cascading source chain with sensible priority order.

    Order: ``user_dict → primary (g0v) → secondary (mmh) →
    moe_kaishu → punctuation → cns_font``.

    - Phase 5ak: ``UserDictSource`` sits at the **top** so user-authored
      glyphs override the built-in MOE / g0v ones.
    - Phase 5ai: ``PunctuationSource`` is hand-tuned for ~40 CJK + ASCII
      marks with real ``raw_track`` data suitable for plotters. It sits
      **before** the CNS font fallback because CNS Kai/Sung TTFs *do*
      contain these glyphs but as outline-only paths — using them would
      lose the G-code track and produce blank output for punctuation.
    - Phase 5aw: ``MoeKaishuSource`` (14k chars) slots between MMH (last
      stroke-data source) and punctuation — better-quality outlines
      for chars g0v/MMH don't carry, but only when the MoE TTF is
      installed; otherwise this layer is silently skipped.
    - Phase 5al / 5am: ``CNSFontSource`` is the **last** fallback (covers
      ~95k Han chars when TTFs are installed). When the font dir is
      empty its ``get_character`` raises ``CharacterNotFound`` for
      everything, so the chain naturally fails through.
    """

    def __init__(
        self,
        primary: Source | None = None,
        secondary: Source | None = None,
        punctuation: Source | None = None,
        user_dict: Source | None = None,
        cns_font: Source | None = None,
        moe_kaishu: Source | None = None,
    ) -> None:
        self.user_dict = user_dict or UserDictSource()
        self.primary = primary or G0VSource()
        self.secondary = secondary or MMHSource()
        self.moe_kaishu = moe_kaishu or MoeKaishuSource()
        self.punctuation = punctuation or PunctuationSource()
        self.cns_font = cns_font or CNSFontSource()

    def get_character(self, char: str) -> Character:
        # User dict first — overrides everything when present.
        try:
            return self.user_dict.get_character(char)
        except CharacterNotFound:
            pass
        try:
            return self.primary.get_character(char)
        except CharacterNotFound:
            pass
        try:
            return self.secondary.get_character(char)
        except CharacterNotFound:
            pass
        # Punctuation BEFORE all outline-only fallbacks — hand-tuned
        # raw_track for marks like ，！？ wins over MoE/CNS outline
        # which would render fine visually but produce empty G-code.
        try:
            return self.punctuation.get_character(char)
        except CharacterNotFound:
            pass
        # Phase 5aw: MoE Kaishu — outline-only fallback with better
        # quality than CNS Kai for the common range.
        try:
            return self.moe_kaishu.get_character(char)
        except CharacterNotFound:
            pass
        # CNS font: last-resort Han-char coverage.
        return self.cns_font.get_character(char)


class RegionAutoSource:
    """
    Region-aware cascading source.

    ``region='tw'``  : g0v → MMH       (台灣標準繁體優先)
    ``region='cn'``  : MMH → g0v       (大陸標準優先)
    ``region='jp'``  : KanjiVG → MMH   (日本漢字優先)
    ``region='auto'``: g0v → MMH → KanjiVG  (全方位 fallback)
    """

    _ORDERS: dict[str, tuple[type, ...]] = {
        "tw":   (G0VSource, MMHSource),
        "cn":   (MMHSource, G0VSource),
        "jp":   (KanjiVGSource, MMHSource),
        "auto": (G0VSource, MMHSource, KanjiVGSource),
    }

    def __init__(self, region: Region = "auto") -> None:
        if region not in self._ORDERS:
            raise ValueError(
                f"unknown region {region!r}; expected tw/cn/jp/auto"
            )
        self.region = region
        # ``_sources`` holds ONLY the region-specific built-in chain. User
        # dict and punctuation are separate "boundary" layers handled by
        # ``get_character`` so test_region.py can keep checking
        # ``_sources[0]`` for the region's primary source.
        self._sources: list[Source] = []
        for cls in self._ORDERS[region]:
            self._sources.append(cls())
        # Phase 5ak: highest-priority override.
        self.user_dict: Source = UserDictSource()
        # Phase 5aw: MoE Kaishu — outline-quality fallback before CNS Kai.
        self.moe_kaishu: Source = MoeKaishuSource()
        # Phase 5al: CNS font Tier-3 (region-independent, between built-ins
        # and punctuation). Lazy-disabled when fonts aren't installed.
        self.cns_font: Source = CNSFontSource()
        # Phase 5ai: bottom fallback.
        self.punctuation: Source = PunctuationSource()

    def get_character(self, char: str) -> Character:
        # User dict first — overrides everything when present.
        try:
            return self.user_dict.get_character(char)
        except CharacterNotFound:
            pass
        last_err: Exception | None = None
        for s in self._sources:
            try:
                return s.get_character(char)
            except CharacterNotFound as e:
                last_err = e
                continue
        # Punctuation BEFORE all outline-only fallbacks (raw_track wins).
        try:
            return self.punctuation.get_character(char)
        except CharacterNotFound as e:
            last_err = e
        # Phase 5aw: MoE Kaishu — outline-quality fallback.
        try:
            return self.moe_kaishu.get_character(char)
        except CharacterNotFound as e:
            last_err = e
        # Phase 5al: CNS font fallback (~95k chars, outline-only).
        try:
            return self.cns_font.get_character(char)
        except CharacterNotFound as e:
            last_err = e
        raise last_err or CharacterNotFound(
            f"no source in region={self.region!r} has U+{ord(char):04X}"
        )


def _build_source(name: str) -> Source:
    name = name.lower()
    if name == "g0v":
        return G0VSource()
    if name == "mmh":
        return MMHSource()
    if name == "kanjivg":
        return KanjiVGSource()
    if name == "auto":
        return AutoSource()  # already includes PunctuationSource
    if name in ("tw", "cn", "jp"):
        return RegionAutoSource(name)  # type: ignore[arg-type]
    raise ValueError(
        f"unknown source {name!r}; "
        f"expected g0v/mmh/kanjivg/auto/tw/cn/jp"
    )


# 5dq：make_source 記憶化——同名字源只建一次、跨呼叫重用。
# 各字源本有 per-instance 快取（mmh._index 解析 9500 行、moe_kaishu 讀
# CFF glyphset、g0v/cns_font TTFont…），但 _load 每次呼叫都 make_source()
# 建全新 AutoSource（含全新子字源），把這些快取全丟掉重建——一頁元素
# 週期表（118 罕見字）光載入就 ~31s（mmh 重解 20s＋moe_kaishu 重讀 9s）
# → Render 逾時 502。改成同名字源 process 內只建一次（等同既有
# get_kaishu_source 等 singleton 的設計意圖），118 字載入 31s→~1s。
_SOURCE_CACHE: dict[str, Source] = {}


def make_source(name: str) -> Source:
    """
    Factory for the CLI's ``--source`` flag（結果快取、同名重用）.

    Accepts:
      - data source names: 'g0v', 'mmh', 'kanjivg' (exact: no fallbacks)
      - 'auto' (g0v → MMH → punctuation fallback)
      - region codes: 'tw', 'cn', 'jp' (region-specific + punctuation fallback)

    Single-source modes deliberately don't include the punctuation
    fallback — explicitly picking one source means "only that source".
    The ``auto`` / region modes chain :class:`PunctuationSource` at the
    end so mixed CJK documents (text + ``，！？「」``) just work.

    同名字源在 process 內只建一次並重用（見 ``_SOURCE_CACHE`` 註解）；
    測試若改字型路徑等環境變數，呼叫 :func:`reset_source_cache` 清快取。
    """
    key = name.lower()
    src = _SOURCE_CACHE.get(key)
    if src is None:
        src = _build_source(key)          # 未知名稱在此拋 ValueError（不快取）
        _SOURCE_CACHE[key] = src
    return src


def reset_source_cache() -> None:
    """清空 make_source 記憶化（測試改字型/環境後呼叫）。"""
    _SOURCE_CACHE.clear()


__all__ = [
    "Source",
    "Region",
    "G0VSource",
    "MMHSource",
    "KanjiVGSource",
    "PunctuationSource",
    "UserDictSource",
    "CNSFontSource",
    "MoeKaishuSource",
    "AutoSource",
    "RegionAutoSource",
    "CharacterNotFound",
    "make_source",
    "reset_source_cache",
    "supported_punctuation",
    "default_user_dict_dir",
    "default_cns_font_dir",
    "default_kaishu_font_path",
]
