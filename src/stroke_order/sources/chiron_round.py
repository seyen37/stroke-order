"""
昭源環方 / Chiron GoRound TC (圓體) source — S1。

第七種字模筆形風格：**圓體**。昭源環方是以昭源黑體（思源黑體香港版
的現代筆形改造）為底、用程式把筆畫端點與轉角圓角化而成的仿圓體，
筆形骨架仍是設計過的黑體——**粗細均勻、無收筆尖鋒**，因此和 5dm
的 `noto_hei` 同屬「適合當字模底」的那一類，只是端點是圓的。

為什麼收 Bold (700B) 而不是 Regular (400R)
------------------------------------------
實測（50 mm 字框、2 mm 連筋；數據與方法見
``docs/decisions/2026-08-20_s1_chiron_round.md``）：

===================  ==================  =========
字型                 筆寬中位 (px@50mm)  殘腔
===================  ==================  =========
Noto Sans TC Bold    42–47               0（基準）
昭源環方 400R        26–32               0
昭源環方 700B        40–54               0
===================  ==================  =========

兩個字重在 50 mm 都過「殘腔 0」，但筆寬會隨輸出尺寸等比縮小——
400R 比現行基準細約 35%，做小尺寸字模時餘裕明顯不足。**選有餘裕
的那個**（§ 不做暫時性補丁）。

圓角並沒有因此變少：圓角的**絕對半徑**兩者幾乎一致（400R
R/(W/2)=1.087 × 半筆寬 69 EM ≈ 75 EM；700B 0.615 × 112 EM ≈ 69 EM）
——比值差只是分母（筆寬）不同造成的，同一套圓角化程序。所以
700B 看起來一樣圓，只是筆畫粗。

License (must be cited)
-----------------------
**SIL Open Font License 1.1** — 與思源黑體同一套授權：可商用、可打包、
可改作；整套字型不得單獨販售，散布時 OFL 通知須同行。上游未宣告
Reserved Font Name。
Copyright 2024-2026 Tamcy；Copyright 2014-2025 Adobe；
Copyright 2016 The Nunito Sans Project Authors（內嵌西文）。
https://github.com/chiron-fonts/chiron-go-round-tc

字型取得
--------
上游 repo 的 ``STATIC_OTF/`` 目錄**直接進版控**，因此
`scripts/render_fetch_fonts.sh` 走 raw.githubusercontent 直取（同
Noto 的作法），**不必**先上傳到本專案的 ``fonts-v1`` release。

Coordinate frame
----------------
``unitsPerEm = 1000``（CFF/OTF），與 `noto_hei` 同路徑：
``scale = EM_SIZE / 1000`` 加 Y 翻轉，走 ``_transform_cmd``。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..ir import EM_SIZE, Character, Stroke
from .cns_font import _OutlineCmdPen, _transform_cmd
from .g0v import CharacterNotFound

_ENV_FILE = "STROKE_ORDER_ROUND_FONT_FILE"
_ENV_DIR = "STROKE_ORDER_ROUND_FONT_DIR"
_FONT_FILENAME = "ChironGoRoundTC-700B.otf"
_DEFAULT_FILE = (
    Path.home() / ".stroke-order" / "round-fonts" / _FONT_FILENAME
)


def default_round_font_path() -> Path:
    f = os.environ.get(_ENV_FILE)
    if f:
        return Path(f).expanduser()
    d = os.environ.get(_ENV_DIR)
    if d:
        return Path(d).expanduser() / _FONT_FILENAME
    return _DEFAULT_FILE


_ATTRIBUTION = (
    "昭源環方 Chiron GoRound TC — Copyright 2024-2026 Tamcy, "
    "Copyright 2014-2025 Adobe, Copyright 2016 The Nunito Sans Project "
    "Authors. SIL Open Font License 1.1. "
    "https://github.com/chiron-fonts/chiron-go-round-tc"
)


def attribution_notice() -> str:
    return _ATTRIBUTION


class ChironRoundSource:
    """昭源環方 (圓體) outline loader — 圓端點的字模底。"""

    def __init__(self, font_path: Optional[Path] = None) -> None:
        self.font_path = (
            Path(font_path) if font_path else default_round_font_path()
        )
        self._font: object = None
        self._cache: dict[str, Character] = {}

    def __repr__(self) -> str:
        return (f"ChironRoundSource(file={self.font_path!s}, "
                f"loaded={self._font is not None}, "
                f"cached={len(self._cache)})")

    def is_ready(self) -> bool:
        return self.font_path.exists()

    def _load_font(self):
        if self._font is not None:
            return self._font
        if not self.font_path.exists():
            return None
        try:
            from fontTools.ttLib import TTFont
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "fontTools is required for ChironRoundSource; "
                "install with `pip install fonttools`"
            ) from e
        self._font = TTFont(str(self.font_path), lazy=True)
        return self._font

    def available_glyph_count(self) -> int:
        font = self._load_font()
        if font is None:
            return 0
        return len(font.getBestCmap())

    def get_character(self, char: str) -> Character:
        if char in self._cache:
            return self._cache[char]
        font = self._load_font()
        if font is None:
            raise CharacterNotFound(
                f"昭源環方 (Chiron GoRound TC) not installed; "
                f"checked {self.font_path}"
            )
        cp = ord(char)
        cmap = font.getBestCmap()
        gname = cmap.get(cp)
        if gname is None:
            raise CharacterNotFound(
                f"昭源環方 has no glyph for U+{cp:04X} ({char!r})"
            )
        pen = _OutlineCmdPen(font.getGlyphSet())
        font.getGlyphSet()[gname].draw(pen)
        if not pen.commands:
            raise CharacterNotFound(
                f"昭源環方 glyph for U+{cp:04X} has no drawable outline"
            )
        units = font["head"].unitsPerEm
        ascender = font["hhea"].ascender
        scale = EM_SIZE / units
        cmds = [
            _transform_cmd(cmd, scale=scale, ascender=ascender)
            for cmd in pen.commands
        ]
        c = Character(
            char=char,
            unicode_hex=f"{cp:04x}",
            strokes=[Stroke(
                index=0,
                raw_track=[],
                outline=cmds,
                kind_code=9,
                kind_name="其他",
                has_hook=False,
            )],
            data_source="chiron_round",
        )
        self._cache[char] = c
        return c

    def has(self, char: str) -> bool:
        try:
            self.get_character(char)
            return True
        except CharacterNotFound:
            return False


_SINGLETON: Optional[ChironRoundSource] = None


def get_round_source() -> ChironRoundSource:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = ChironRoundSource()
    return _SINGLETON


def reset_round_singleton() -> None:
    global _SINGLETON
    _SINGLETON = None
    from ..cache_bus import bump  # 5eu：跨層快取失效訊號
    bump()


__all__ = [
    "ChironRoundSource",
    "default_round_font_path",
    "attribution_notice",
    "get_round_source",
    "reset_round_singleton",
]
