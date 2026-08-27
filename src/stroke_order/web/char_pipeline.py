"""字元載入管線（W3-R2／架構健檢 Wave 3）——全站唯一的載字鏈。

單一事實源：所有端點的「載字 → 宋/篆/隸升級 → 風格濾鏡 → CNS outline
模式」都經過本模組；:func:`make_char_loader` 是 9 個原 inline 閉包收斂
後的工廠（差異只在三個參數）。

測試注意：要攔載入行為請 monkeypatch **本模組**的符號（``_load``、
``_get_seal``、``_apply_seal_mode``…）——W3-R1 之前它們住 web.server，
R2 起 server 不再持有這些名稱（拒絕別名雙軌，patch 目標唯一）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from ..classifier import classify_character
from ..decomposition import default_db as default_decomp_db
from ..hook_policy import apply_hook_policy
from ..radicals import lookup as radical_lookup
from ..smoothing import smooth_character
from ..sources import CharacterNotFound, make_source
from ..sources.cns_font import (
    apply_cns_outline_mode as _apply_cns_mode,
    get_cns_sung_source as _get_sung,
)
from ..sources.chongxi_seal import (
    apply_seal_outline_mode as _apply_seal_mode,
    get_seal_source as _get_seal,
)
from ..sources.moe_lishu import (
    apply_lishu_outline_mode as _apply_lishu_mode,
    get_lishu_source as _get_lishu,
)
from ..sources.moe_song import get_song_source as _get_song
from ..styles import STYLES as _STYLES, apply_style as _apply_style
from ..validation import apply_known_bug_fix, validate_character

#: Phase 5al: validator for ``cns_outline_mode`` query param.
_CNS_MODE_PATTERN = "^(skip|trace|skeleton)$"

#: Phase 5aj: validator for the ``style`` query param across all multi-char
#: endpoints. Built from the styles registry so adding a new style in
#: stroke_order.styles automatically expands the pattern.
_STYLE_PATTERN = "^(" + "|".join(sorted(_STYLES)) + ")$"


def _load(char: str, source: str, hook_policy: str, auto_fix: bool = True):
    """Shared character loading pipeline for all endpoints."""
    if len(char) != 1:
        raise HTTPException(400, detail=f"expected a single character, got {char!r}")
    try:
        src = make_source(source)
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e
    try:
        c = src.get_character(char)
    except CharacterNotFound as e:
        # D2：缺字請求計數——R2 GlyphWiki 翻案的感測器（§99 儀器化）。
        # 只記字元本身，無任何請求脈絡。
        from .metrics import record_missing_char
        record_missing_char(char)
        raise HTTPException(404, detail=str(e)) from e
    # Phase 5ai-5av: characters from non-Han / outline-only pipelines
    # (punctuation, user dict, CNS-font fallback in Kai/Sung, MoE Song
    # 5av, MoE Lishu 5au, Chongxi Seal 5at) skip the Han-specific
    # validation / classification / smoothing — those assume MOE-grade
    # kaishu structure and would mis-classify hand-authored or
    # outline-only glyphs.
    ds_skip = c.data_source in (
        "punctuation", "user",
        "moe_song", "moe_lishu", "moe_kaishu", "chongxi_seal",
    )
    if ds_skip or (c.data_source or "").startswith("cns_font"):
        from ..validation import ValidationResult
        return c, ValidationResult(is_valid=True), False
    r = validate_character(c)
    applied_fix = False
    if auto_fix and r.fixable:
        c, applied_fix = apply_known_bug_fix(c)
    classify_character(c)
    apply_hook_policy(c, hook_policy)
    smooth_character(c)
    # Attach 5000.TXT decomposition (Phase 3)
    decomp = default_decomp_db().get(char)
    if decomp is not None:
        c.decomposition = decomp
    # Attach radical classification (Phase 4)
    radical = radical_lookup(char)
    if radical is not None:
        c.radical_category = f"{radical.category}/{radical.subcategory}"
    return c, r, applied_fix


def _upgrade_to_sung(c, style: str):
    """Phase 5am + 5av: layered Sung swap when ``style="mingti"``.

    Resolution order:

    1. **MoE 標準宋體** (``"moe_song"`` data_source, 25k Unicode chars,
       台灣權威) — Phase 5av addition. Try first because it's the
       authoritative Sung for Taiwan and ships with a clean BMP+Plane2
       cmap.
    2. **CNS 全字庫 Sung** (``"cns_font_sung"`` data_source, ~95k chars,
       broader rare-character coverage) — Phase 5am fallback for chars
       MoE doesn't carry.
    3. **No swap** — caller's downstream ``_apply_style`` falls back to
       the existing 5aj fake-Mingti filter.

    Both sources tag ``data_source`` so :class:`MingtiStyle` short-
    circuits and doesn't add fake serifs on top of real Sung outlines.
    """
    if c is None or style != "mingti":
        return c
    # Tier 1 — MoE 標準宋體 (5av).
    song = _get_song()
    if song.is_ready():
        try:
            return song.get_character(c.char)
        except CharacterNotFound:
            pass
    # Tier 2 — CNS Sung fallback for Plane-2/15 rare chars (5am).
    sung = _get_sung()
    if sung.is_ready():
        try:
            return sung.get_character(c.char)
        except CharacterNotFound:
            pass
    return c


def _upgrade_to_seal(c, style: str, *, seal_outline_mode: str = "skeleton"):
    """Phase 5at: swap a kaishu character for its 崇羲篆體 outline.

    Triggered when *all three* hold:

    1. The user requested ``style="seal_script"``.
    2. The seal-font source is ready (OTF installed).
    3. The font actually has a glyph for ``c.char``.

    On any failure the original ``c`` is returned unchanged — caller
    sees kaishu and a console warning rather than an error. Unlike
    :func:`_upgrade_to_sung`, the seal swap is **structural** (篆書 has
    different glyph composition than 楷書), so there is no graceful
    "filter fallback" — only "real seal font, or vanilla kaishu".

    The returned character then runs through the requested
    ``seal_outline_mode`` (default ``"skeleton"`` — v1 walker, which
    handles seal's simple topology well; see
    :mod:`stroke_order.sources.chongxi_seal`).
    """
    if c is None or style != "seal_script":
        return c
    seal = _get_seal()
    if not seal.is_ready():
        return c
    try:
        seal_c = seal.get_character(c.char)
        return _apply_seal_mode(seal_c, seal_outline_mode)
    except CharacterNotFound:
        return c
    except Exception:
        # 5ea: 真崇羲篆體某些 dense/degenerate 字形，其 skeleton/thinning
        # （見 chongxi_seal 警語「runs slow / OOMs on dense outlines」）會
        # 拋非 HTTPException 例外。呼叫端的 loader 只 catch HTTPException →
        # 單一字形失敗整頁 500、篆體全不出現。這裡在根部擋住：任何處理失敗
        # 一律退回楷書基底字（符合本函式「真篆體，或 vanilla 楷書」設計），
        # 讓其餘字形照常出篆體、整頁不 500。
        return c


def _upgrade_to_lishu(c, style: str, *, lishu_outline_mode: str = "skeleton"):
    """Phase 5au: swap a kaishu character for its 教育部隸書 outline.

    Mirrors :func:`_upgrade_to_sung` (the Phase-5am pattern): the user
    asked for ``style="lishu"``, and if MoE 隸書 is installed we hand
    back the real-font character with ``data_source = "moe_lishu"``.
    The 5aj :class:`LishuStyle` filter then short-circuits on that
    tag so it doesn't double-up the 波磔 + vertical squash.

    Falls through silently to kaishu when the font isn't present —
    user sees the existing 5aj fake-lishu filter.
    """
    if c is None or style != "lishu":
        return c
    lishu = _get_lishu()
    if not lishu.is_ready():
        return c
    try:
        lishu_c = lishu.get_character(c.char)
        return _apply_lishu_mode(lishu_c, lishu_outline_mode)
    except CharacterNotFound:
        return c
    except Exception:
        # 5ea: 同 _upgrade_to_seal——隸書亦走 skeleton 抽取（警語同上），
        # 單一字形處理失敗一律退回楷書基底字，絕不讓整頁 500。
        return c


# ---------------------------------------------------------------------------
# 5dp: 抄經預覽 502 修復——per-request char-loader 記憶化
# ---------------------------------------------------------------------------
# render_sutra_page 對**每個字位**都呼叫 char_loader(ch)（一頁 260 位），
# 而 _load 不快取——重複字每次重載，一頁心經（117 唯一字 / 260 位）純
# 載入就數秒~十幾秒，且端點是 async def、重活凍住 event loop（§9/5ck
# 應驗）→ Render 單 worker 逾時回 502。記憶化把「每字只載一次」，同一
# request 內同字回同一（唯讀）Character；PDF 多頁共用 loader 時省更多
# （跨頁重複字只載一次）。輸出與非記憶化逐位元相同（已驗）。
def _memoize_char_loader(fn):
    """Wrap a char-loader so each unique char is resolved at most once."""
    cache: dict = {}

    def cached(ch: str):
        if ch not in cache:
            cache[ch] = fn(ch)
        return cache[ch]

    return cached


# 5bz: outline-preserving loader for sutra preview + PDF
# ---------------------------------------------------------------------------
#
# render_sutra_page accepts an *optional* second char-loader that returns
# the outline-bearing version of skeleton-style chars. We build that loader
# by re-running the same upgrade chain as the main loader, but pass
# ``*_outline_mode="skip"`` to ``_upgrade_to_seal`` / ``_upgrade_to_lishu``
# so the lishu/seal sources hand back their original outline data
# (instead of skeletonising it).
#
# For kaishu/sung this returns the same Character as the main loader, but
# render_sutra_page will not consult outline_glyph_loader for them — the
# `_char_cut_paths` path already renders kaishu — so there's no double-
# render risk. We keep the helper simple.



def make_char_loader(
    source: str,
    hook_policy: str,
    style: str,
    *,
    cns_outline_mode: str = "skip",
    seal_outline_mode: str = "skeleton",
    lishu_outline_mode: str = "skeleton",
    catch_all: bool = False,
    memoize: bool = False,
):
    """W3-R2：載字 loader 工廠——收斂原 9 個逐端點 inline 閉包。

    回傳 ``loader(ch) -> Character | None``：load → 宋/篆/隸升級 →
    風格濾鏡（kaishu 除外）→ CNS outline 模式。載入失敗
    （HTTPException，如 404 缺字）回 None——「缺字跳過」是全部
    多字渲染端點的共同語意。

    參數對應原閉包間僅有的差異：

    - ``cns_outline_mode``：``"skip"``（預設）＝不套 CNS outline。
    - ``seal_outline_mode``／``lishu_outline_mode``：stamp／sutra
      outline 層要 ``"skip"`` 保留原始 outline（skeleton 會轉
      centerline，outline-only 渲染會變空白）。
    - ``catch_all``：mandala 語意——任何例外都回 None（missing chars
      跳過＋auto-shrink 逃生）；預設 False 讓非 HTTP 例外照常炸出。
    - ``memoize``：每字只載一次（sutra 多頁 PDF 省最多；預設關——
      呼叫端可能依賴每次拿到全新 Character 物件）。
    """
    def _loader(ch: str):
        try:
            c, _r, _ = _load(ch, source, hook_policy)
            c = _upgrade_to_sung(c, style)
            c = _upgrade_to_seal(c, style, seal_outline_mode=seal_outline_mode)
            c = _upgrade_to_lishu(
                c, style, lishu_outline_mode=lishu_outline_mode)
            if style != "kaishu":
                c = _apply_style(c, style)
            if cns_outline_mode != "skip":
                c = _apply_cns_mode(c, cns_outline_mode)
            return c
        except HTTPException:
            return None
        except Exception:
            if catch_all:
                return None
            raise

    return _memoize_char_loader(_loader) if memoize else _loader


# 5bz: outline-preserving loader for sutra preview + PDF
# ---------------------------------------------------------------------------
#
# render_sutra_page accepts an *optional* second char-loader that returns
# the outline-bearing version of skeleton-style chars: same upgrade chain,
# but ``*_outline_mode="skip"`` so lishu/seal sources hand back original
# outline data (instead of skeletonising it). For kaishu/sung this returns
# the same Character as the main loader, but render_sutra_page will not
# consult outline_glyph_loader for them.


def _build_sutra_outline_loader(
    *, source: str, style: str, hook_policy: str,
):
    """Return a CharLoader that yields *outline-bearing* Characters.

    Used as render_sutra_page's ``outline_glyph_loader`` when the user
    asks for the original-glyph preview (browser preview + PDF). For
    隸書 / 篆書 this swaps in the real font outline; for everything
    else it falls through to the standard kaishu loader.
    """
    return make_char_loader(
        source, hook_policy, style,
        seal_outline_mode="skip", lishu_outline_mode="skip",
    )


# Phase 5b r28c: 共用 mandala char loader builder
# /api/mandala endpoint 跟 gallery upload thumbnail 都用這個構造 loader，
# 確保 server-side 渲染 mandala 字環時的 source / style / cns_mode pipeline 一致。


def build_mandala_char_loader(
    *, style: str = "kaishu", source: str = "auto",
    hook_policy: str = "animation", cns_outline_mode: str = "skip",
):
    """Return a CharLoader for mandala rendering.

    load → upgrade sung/seal/lishu → apply style filter → apply CNS
    outline mode。所有失敗路徑（HTTPException / 其他例外）回 None —
    對應 mandala 模式的「missing chars 跳過 + auto-shrink 逃」邏輯。
    """
    return make_char_loader(
        source, hook_policy, style,
        cns_outline_mode=cns_outline_mode, catch_all=True,
    )


#: W2：頁尾註記一列最多列幾個造詞。造詞是加值資訊，列太多會擠掉釋義。
INFO_MAX_WORDS = 3


def build_digit_glyphs() -> dict:
    """X1：阿拉伯數字 0–9 的字形表（noto_hei）——分解圖序號用。

    序號走字形路徑而非 ``<text>``（§5bv）；noto_hei 缺席（本機沒放字型檔）
    時回空 dict，呼叫端據此**省略序號**、不補符號（§87 不裝懂）。
    """
    glyphs: dict = {}
    try:
        from ..sources.noto_hei import get_hei_source
        hei = get_hei_source()
    except Exception:
        return {}
    for ch in "0123456789":
        try:
            g = hei.get_character(ch)
        except Exception:
            continue
        if g is not None and g.strokes:
            glyphs[ch] = g
    return glyphs


def build_info_rows(chars: list[str]) -> tuple[list[dict], dict]:
    """W2：生字清單 → ``(info_rows, info_glyphs)``，餵給 ``render_grid_svg``。

    **釋義取自教育部《國語辭典簡編本》原文第一義項**（``moe_dict.
    first_sense``），逐字照抄不改寫、不摘要、不截斷——§88 的線畫在
    「節錄整條義項可以、動任何一條的字不可以」。

    註記文字的字形一律走 **noto_hei（思源黑體）**，因為它涵蓋阿拉伯數字
    與全形分隔符號——那些字帖字源（g0v/kanjivg…只有漢字）沒有的字符；缺
    一個字就是版面上一個看不見的洞，而釋義裡「1.」的編號正好會踩到。
    noto_hei 缺席（本機沒放字型檔）時整個註記區留白——不以任何符號代替
    （§87 不裝懂）。

    回傳的 ``info_rows`` 只含**每個查得到的生字一列**；查無此字者不列。
    """
    from ..exporters.grid import compose_info_line
    from ..sources import moe_dict

    rows: list[dict] = []
    for ch in chars:
        entry = moe_dict.lookup(ch)
        if entry is None:
            continue
        sense = moe_dict.first_sense(ch)
        meta_bits = [f"{entry['radical']}部" if entry.get("radical") else "",
                     f"{entry['stroke_count']}畫"
                     if entry.get("stroke_count") else "",
                     entry.get("zhuyin") or ""]
        words = [w["word"] for w in (entry.get("words") or [])
                 if w.get("word")][:INFO_MAX_WORDS]
        rows.append({
            "char": ch,
            "meta": "・".join(b for b in meta_bits if b),
            "definition": (sense or {}).get("text", ""),
            "words": ("造詞：" + "、".join(words)) if words else "",
        })

    glyphs: dict = {}
    if rows:
        from ..sources.noto_hei import get_hei_source
        try:
            hei = get_hei_source()
        except Exception:          # 字型檔缺席 → 註記區留白
            return rows, {}
        for ch in set("".join(compose_info_line(r) for r in rows)):
            try:
                g = hei.get_character(ch)
            except Exception:
                continue
            if g is not None and g.strokes:
                glyphs[ch] = g
    return rows, glyphs


def _parse_zhuyin_map(zhuyin_map: Optional[str], source: str,
                      hook_policy: str) -> tuple[Optional[dict], dict]:
    """5cz：解析「字:注音,字:注音」映射並載入符號 Character。

    5cu 起的共用邏輯——grid（SVG＋G-code）、notebook、letter 三處
    消費，抽成單一 helper。聲調記號（手作 polyline）與載不到的
    符號靜默跳過。回傳 ``(zmap, zchars)``；``zhuyin_map=None`` 時
    ``zmap=None``（＝功能關閉）。
    """
    zmap: Optional[dict] = None
    zchars: dict = {}
    if zhuyin_map is not None:
        zmap = {}
        for pair in zhuyin_map.split(","):
            if ":" not in pair:
                continue
            k, v = pair.split(":", 1)
            if k:
                zmap[k] = v
        for val in zmap.values():
            for sym in val:
                if sym in zchars or sym in "ˊˇˋ˙ˉ":
                    continue
                try:
                    zc, _r2, _2 = _load(sym, source, hook_policy)
                    zchars[sym] = zc
                except HTTPException:
                    continue
    return zmap, zchars
