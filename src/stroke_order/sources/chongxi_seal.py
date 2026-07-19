"""
崇羲篆體 (Chongxi Seal Script) source — Phase 5at.

Loads glyph outlines from the *Chongxi Small Seal* font by 季旭昇 and
the Institute of Information Science, Academia Sinica. The font ships
~11,600 small-seal-script glyphs covering Shuowen Jiezi (《說文解字》)
plus the Taiwan MoE Common Words list — vastly more than the 6,063
characters g0v has for kaishu.

License (must be cited in every output)
---------------------------------------
**CC BY-ND 3.0 TW or later**:
- ✅ may redistribute (incl. commercial)
- ✅ must attribute "崇羲篆體 / 季旭昇 / 中央研究院資訊科學研究所"
- ⚠ no derivatives of the *font file* (extracting glyph outlines for
  rendering output is normal use, not a derivative work — same legal
  basis as CNS Sung in Phase 5am)

The :func:`attribution_notice` helper returns a ready-made caption that
SVG/G-code/UI layers should embed when the seal source actually
contributed to an output.

Coordinate frame
----------------
Source TTF uses ``unitsPerEm = 1024``; we scale to the project-wide
2048 em frame inside :func:`get_character` so downstream renderers
don't need to know the difference. Y-flip uses the font's hhea
ascender, identical to :class:`CNSFontSource`.

Outline-only — caller must convert
----------------------------------
Like CNSFontSource, output strokes have ``raw_track=[]`` and the full
glyph outline in a single ``Stroke``. Callers that need centerlines
for G-code must run :func:`apply_seal_outline_mode` (or equivalent)
to convert the outline to skeleton tracks. Phase 5at uses the legacy
v1 walker by default — empirically it handles seal script's simple
topology (1-3 strokes per glyph, fat lines, few junctions) much
better than the over-engineered v2 splitter.
"""
from __future__ import annotations

import os
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Optional

from ..ir import EM_SIZE, Character, Point, Stroke
from .cns_font import _OutlineCmdPen, _transform_cmd
from .glyph_cache import GLYPH_CACHE_MAX, lru_put
from .g0v import CharacterNotFound


_ENV_FILE = "STROKE_ORDER_SEAL_FONT_FILE"
_ENV_DIR = "STROKE_ORDER_SEAL_FONT_DIR"
_DEFAULT_FILE = Path.home() / ".stroke-order" / "seal-fonts" / "chongxi_seal.otf"


# ---------------------------------------------------------------------------
# 5dn：以崇羲為主體、簡轉繁補足不足（QODA A 案）
# ---------------------------------------------------------------------------
# 崇羲篆書是台灣繁體篆書、覆蓋繁體近乎完整（教育部常用字 4808 只真缺
# ~8 罕見字），但**不收簡體**（缺口 ~1500 字幾乎全是簡體）。篆書本來
# 就用繁體/古形——「簡體篆書」是現代產物——故簡體輸入轉繁後用崇羲的
# 繁體篆形渲染，語義上反而更正確，且零新字型、無他家字型授權問題。
# 實測 opencc s2t 可救回崇羲 99% 的缺字（1494/1508）。
#
# opencc 為選用依賴：缺套件時 fallback 靜默關閉（退回原本缺字行為），
# 與字型「未安裝即降級」同一容錯策略。
_S2T_SENTINEL = object()
_S2T_CONVERTER = _S2T_SENTINEL  # s2t 單一轉換器（_simp_to_trad 用）

# 5do（抄經/佛經缺字補足）：把 5dn 的「簡轉繁」延伸成**轉換鏈**。
# 崇羲對核心佛經覆蓋已很高（心經缺 2、金剛經缺 4），缺口分三類：
#   ① 簡體字（国→國）——s2t / s2tw 補
#   ② 異體字（爲→為、衆→眾、卻、兌）——s2tw / t2tw（正規化到台灣標準）補
#   ③ 真正罕見佛經字（閦毘鉢憍耨）——**任何轉換都救不回**（就是標準形、
#      崇羲單純沒有）→ 依使用者決策維持缺字並清楚提示，不引入商用字型。
# 鏈依序試 s2t → s2tw → t2tw，取第一個「崇羲有」的單字候選。實測
# 教育部 4808 由缺 ~1508 降到 9。
_SEAL_CONV_CONFIGS = ("s2t", "s2tw", "t2tw")
_SEAL_CONVERTERS = _S2T_SENTINEL  # list[OpenCC] | None；lazy load


def _seal_converters():
    global _SEAL_CONVERTERS
    if _SEAL_CONVERTERS is _S2T_SENTINEL:
        try:
            import opencc  # type: ignore
            _SEAL_CONVERTERS = [
                opencc.OpenCC(cfg) for cfg in _SEAL_CONV_CONFIGS
            ]
        except Exception:            # noqa: BLE001 — 缺套件即降級
            _SEAL_CONVERTERS = None
    return _SEAL_CONVERTERS


def _seal_variants(char: str) -> list[str]:
    """回傳 ``char`` 的候選正規化單字（簡轉繁＋異體字正規化，去重、排序）。

    只收「恰一字且與原字不同」的結果；無 opencc 即回空清單（降級）。
    順序即優先序（s2t→s2tw→t2tw）。
    """
    convs = _seal_converters()
    if not convs:
        return []
    out: list[str] = []
    for c in convs:
        try:
            r = c.convert(char)
        except Exception:            # noqa: BLE001
            continue
        if len(r) == 1 and r != char and r not in out:
            out.append(r)
    return out


def _simp_to_trad(char: str) -> Optional[str]:
    """單一簡體字 → 繁體（opencc s2t）。5dn 保留：narrower helper。

    僅在轉換結果**恰為一個字且與原字不同**時回傳；無 opencc/非單字/
    無變化 → ``None``。
    """
    global _S2T_CONVERTER
    if _S2T_CONVERTER is _S2T_SENTINEL:
        try:
            import opencc  # type: ignore
            _S2T_CONVERTER = opencc.OpenCC("s2t")
        except Exception:            # noqa: BLE001
            _S2T_CONVERTER = None
    if _S2T_CONVERTER is None:
        return None
    try:
        alt = _S2T_CONVERTER.convert(char)
    except Exception:                # noqa: BLE001
        return None
    if len(alt) == 1 and alt != char:
        return alt
    return None


def default_seal_font_path() -> Path:
    """Resolve the OTF path. Order:

    1. ``$STROKE_ORDER_SEAL_FONT_FILE`` (full path to OTF/TTF)
    2. ``$STROKE_ORDER_SEAL_FONT_DIR / chongxi_seal.otf``
    3. ``~/.stroke-order/seal-fonts/chongxi_seal.otf``
    """
    f = os.environ.get(_ENV_FILE)
    if f:
        return Path(f).expanduser()
    d = os.environ.get(_ENV_DIR)
    if d:
        return Path(d).expanduser() / "chongxi_seal.otf"
    return _DEFAULT_FILE


# Mandatory attribution per CC BY-ND 3.0 TW.
_ATTRIBUTION = (
    "崇羲篆體 (Chongxi Small Seal) by 季旭昇 / 中央研究院資訊科學研究所, "
    "CC BY-ND 3.0 TW. https://xiaoxue.iis.sinica.edu.tw/chongxi/"
)


def attribution_notice() -> str:
    """Return the human-readable attribution string for this font.

    Embed this in every output that contains seal-script glyphs.
    Same string is exposed via the ``/api/seal-status`` endpoint so
    UI banners can render it consistently.
    """
    return _ATTRIBUTION


class ChongxiSealSource:
    """Load 崇羲篆體 glyph outlines into the source-chain pipeline.

    Like :class:`CNSFontSource`: cheap to construct (no I/O), one
    ``TTFont`` lazily opened on first ``get_character`` and reused.
    Each character returned has **exactly one Stroke** whose
    ``outline`` is the entire glyph (multi-contour OK), ``raw_track``
    empty, ``data_source = "chongxi_seal"``.
    """

    def __init__(self, font_path: Optional[Path] = None) -> None:
        self.font_path = (
            Path(font_path) if font_path else default_seal_font_path()
        )
        self._font: object = None
        self._cache: "OrderedDict[str, Character]" = OrderedDict()  # 5ey-E：LRU 上限

    def __repr__(self) -> str:
        return (f"ChongxiSealSource(file={self.font_path!s}, "
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
                "fontTools is required for ChongxiSealSource; "
                "install with `pip install fonttools`"
            ) from e
        self._font = TTFont(str(self.font_path), lazy=True)
        return self._font

    def available_glyph_count(self) -> int:
        """How many character codepoints the font covers."""
        font = self._load_font()
        if font is None:
            return 0
        return len(font.getBestCmap())

    def _render_glyph(self, font, glyph_char: str, id_char: str) -> Character:
        """以 ``glyph_char`` 的字形渲染，但 Character.char 記為 ``id_char``。

        （5dn：簡轉繁 fallback 時 glyph_char＝繁體、id_char＝使用者原本
        輸入的簡體，保留輸入身份、用繁體篆形作圖。）缺字形/無輪廓即
        拋 :class:`CharacterNotFound`。
        """
        cp = ord(glyph_char)
        gname = font.getBestCmap().get(cp)
        if gname is None:
            raise CharacterNotFound(
                f"崇羲篆體 has no glyph for U+{cp:04X} ({glyph_char!r})"
            )
        pen = _OutlineCmdPen(font.getGlyphSet())
        font.getGlyphSet()[gname].draw(pen)
        if not pen.commands:
            raise CharacterNotFound(
                f"崇羲篆體 glyph for U+{cp:04X} has no drawable outline"
            )
        units = font["head"].unitsPerEm
        ascender = font["hhea"].ascender
        scale = EM_SIZE / units
        cmds = [
            _transform_cmd(cmd, scale=scale, ascender=ascender)
            for cmd in pen.commands
        ]
        return Character(
            char=id_char,
            unicode_hex=f"{ord(id_char):04x}",
            strokes=[Stroke(
                index=0,
                raw_track=[],
                outline=cmds,
                kind_code=9,
                kind_name="其他",
                has_hook=False,
            )],
            data_source="chongxi_seal",
        )

    def get_character(self, char: str) -> Character:
        cached = self._cache.get(char)
        if cached is not None:
            self._cache.move_to_end(char)   # 5ey-E：LRU 沿用記號
            return cached
        font = self._load_font()
        if font is None:
            raise CharacterNotFound(
                f"崇羲篆體 font not installed; checked {self.font_path}"
            )
        # 以崇羲為主體：原字先試（繁體/崇羲已有的字直接命中）。
        try:
            c = self._render_glyph(font, char, char)
        except CharacterNotFound:
            # 崇羲缺字 → 5do 轉換鏈 fallback（簡轉繁＋異體字正規化）；
            # 依序試候選、第一個崇羲有的字形勝出、保留原輸入身份。
            c = None
            for alt in _seal_variants(char):
                try:
                    c = self._render_glyph(font, alt, char)
                    break
                except CharacterNotFound:
                    continue
            if c is None:
                # 5fa：轉換鏈也救不回 → 部件合成（罣＝网＋圭、鋰＝金＋里
                # ——小篆組字本用完整部件形；合成字帶 seal-synth 標記，
                # 渲染層誠實標示「推測非原典」）。合成也不行才真缺字。
                c = self._try_compose(char)
            if c is None:
                # 真正罕見字（閦毘鉢…）：轉換也救不回 → 維持缺字。
                raise CharacterNotFound(
                    f"崇羲篆體 lacks U+{ord(char):04X} ({char!r}); "
                    f"no simp/variant form available"
                )
        lru_put(self._cache, char, c, GLYPH_CACHE_MAX)  # 5ey-E
        return c

    def _try_compose(self, char: str):
        """5fa：部件合成 fallback。取件走 get_character（含變體鏈與
        巢狀合成）；_composing 集合防循環（罣→网→罣…）。失敗回 None。"""
        composing = getattr(self, "_composing", None)
        if composing is None:
            composing = self._composing = set()
        if char in composing:
            return None
        composing.add(char)
        try:
            from ..decomposition import default_db
            from .seal_compose import compose_seal_character
            return compose_seal_character(char, self.get_character,
                                          default_db())
        except Exception:
            return None            # 合成任何失敗＝維持缺字語意，不炸渲染
        finally:
            composing.discard(char)

    def has(self, char: str) -> bool:
        try:
            self.get_character(char)
            return True
        except CharacterNotFound:
            return False


#: 5eu（架構健檢 W2）：trace/skeleton 抽取是整條篆書渲染鏈的熱點
#: （Zhang-Suen thinning 每字每請求重跑＝篆書整頁 26s 的主因）。字型檔
#: 在行程內固定 → (char, mode) 決定 tracks。只快取**凍結 tuple 的幾何**、
#: Character 仍每次 deepcopy 重建——呼叫端拿到的是新物件，無共享突變風險。
_MODE_TRACKS_CACHE: "OrderedDict[tuple[str, str], tuple]" = OrderedDict()
_MODE_TRACKS_CACHE_MAX = 4096


def _cached_mode_tracks(char: str, mode: str, outline) -> tuple:
    key = (char, mode)
    hit = _MODE_TRACKS_CACHE.get(key)
    if hit is not None:
        _MODE_TRACKS_CACHE.move_to_end(key)
        return hit
    if mode == "trace":
        from .cns_font import _outline_to_polylines
        tracks = _outline_to_polylines(outline)
    else:  # skeleton (default)
        from ..cns_skeleton import outline_to_skeleton_tracks
        tracks = outline_to_skeleton_tracks(outline)
    frozen = tuple(
        tuple((float(x), float(y)) for x, y in t) for t in tracks
    )
    _MODE_TRACKS_CACHE[key] = frozen
    while len(_MODE_TRACKS_CACHE) > _MODE_TRACKS_CACHE_MAX:
        _MODE_TRACKS_CACHE.popitem(last=False)
    return frozen


def apply_seal_outline_mode(c: Character, mode: str = "skeleton") -> Character:
    """Convert a seal-font character to writable centerlines.

    Mirrors :func:`stroke_order.sources.cns_font.apply_cns_outline_mode`
    but uses **the v1 endpoint walker by default**: empirically it
    handles seal-script glyphs (1-3 strokes, fat strokes, few real
    junctions) far better than the v2 junction-aware splitter, which
    over-segments and runs slow / OOMs on dense outlines.

    Modes:
    - ``"skip"`` — leave outline-only (SVG renders filled, G-code skips)
    - ``"trace"`` — sample outline to polyline; G-code traces contour
    - ``"skeleton"`` (default) — Zhang-Suen thinning → walker tracks

    No-op when ``c.data_source != "chongxi_seal"``.
    """
    if c.data_source != "chongxi_seal" or mode == "skip":
        return c
    if mode not in ("trace", "skeleton"):
        raise ValueError(
            f"unknown seal mode {mode!r}; expected skip / trace / skeleton"
        )
    src = c.strokes[0] if c.strokes else None
    if src is None or not src.outline:
        return c

    new_c = deepcopy(c)
    tracks = _cached_mode_tracks(c.char, mode, src.outline)

    new_strokes: list[Stroke] = []
    for idx, track in enumerate(tracks):
        if len(track) < 2:
            continue
        new_strokes.append(Stroke(
            index=idx,
            raw_track=[Point(float(x), float(y)) for x, y in track],
            outline=[],
            kind_code=9,
            kind_name="其他",
            has_hook=False,
        ))
    if new_strokes:
        new_c.strokes = new_strokes
    return new_c


# ---------------------------------------------------------------------------
# Singleton — server.py shares one font handle per process (mirrors 5am).
# ---------------------------------------------------------------------------


_SINGLETON: Optional[ChongxiSealSource] = None


def get_seal_source() -> ChongxiSealSource:
    """Process-wide lazy singleton."""
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = ChongxiSealSource()
    return _SINGLETON


def reset_seal_singleton() -> None:
    """Drop the cached singleton (used by tests that monkeypatch the path)."""
    global _SINGLETON
    _SINGLETON = None
    # 5eu：字型檔可能換了 → 幾何快取一併作廢，並通知跨層快取失效
    _MODE_TRACKS_CACHE.clear()
    from ..cache_bus import bump
    bump()


__all__ = [
    "ChongxiSealSource",
    "apply_seal_outline_mode",
    "default_seal_font_path",
    "attribution_notice",
    "get_seal_source",
    "reset_seal_singleton",
]
