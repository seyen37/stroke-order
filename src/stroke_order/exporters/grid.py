"""
字帖 / practice-worksheet generator.

Render a grid of characters with configurable guide lines (田字格, 米字格,
回宮格, 方格). Output is a single SVG document that can be printed directly
or rasterized to PNG/PDF.

Unlike the single-char SVG exporter, each cell uses the FULL em square as
its canvas, so characters display at proper proportions.
"""
from __future__ import annotations

from typing import Literal, Optional

from ..ir import EM_SIZE, Character
from .svg import _outline_path_d, _track_points_str

GridStyle = Literal["tian", "mi", "hui", "plain", "none"]
CellStyle = Literal["filled", "outline", "trace", "ghost", "blank"]


def auto_tier_counts(cols: int) -> tuple[int, int]:
    """Given the user's ``cols`` input, return (ghost_copies, blank_copies)
    defaults for the tier-based worksheet.

    cols=1 → (0, 0)  — primary only
    cols=2 → (1, 0)  — primary + 1 ghost
    cols≥3 → (1, cols-2) — primary + 1 ghost + (cols-2) blanks
    """
    if cols <= 1:
        return (0, 0)
    if cols == 2:
        return (1, 0)
    return (1, cols - 2)


def _guide_paths(style: GridStyle, size: int = EM_SIZE) -> str:
    """
    Return SVG <g> content for the guide lines of one cell.
    Uses light grey dashed lines so they're visible but not obtrusive.
    """
    half = size // 2
    third_l, third_r = size // 3, 2 * size // 3
    # stroke-width in em-units; 12 ≈ 1.2% of em = visible at typical print sizes
    g = ['<g class="guides" stroke="#bbbbbb" stroke-width="12" fill="none" '
         'stroke-dasharray="40 30">']
    # outer border always (except 'none') — solid, slightly darker
    if style != "none":
        g.append(f'<rect x="0" y="0" width="{size}" height="{size}" '
                 f'stroke="#888" stroke-width="14" stroke-dasharray="none"/>')

    if style == "tian":
        # 田字格: cross through centre
        g.append(f'<line x1="{half}" y1="0" x2="{half}" y2="{size}"/>')
        g.append(f'<line x1="0" y1="{half}" x2="{size}" y2="{half}"/>')
    elif style == "mi":
        # 米字格: tian + two diagonals
        g.append(f'<line x1="{half}" y1="0" x2="{half}" y2="{size}"/>')
        g.append(f'<line x1="0" y1="{half}" x2="{size}" y2="{half}"/>')
        g.append(f'<line x1="0" y1="0" x2="{size}" y2="{size}"/>')
        g.append(f'<line x1="{size}" y1="0" x2="{0}" y2="{size}"/>')
    elif style == "hui":
        # 回宮格: outer + inner 1/3 rectangle
        g.append(f'<rect x="{third_l}" y="{third_l}" '
                 f'width="{third_r - third_l}" height="{third_r - third_l}"/>')
    # 'plain' = just the border (already added)
    # 'none' = nothing
    g.append("</g>")
    return "\n    ".join(g)


def _outline_or_track(strokes, color: str) -> str:
    """5ew-R4 修：outline 有值→填色 path；track-only（手寫字/標點）→
    同色 polyline 折線。

    原版對所有筆畫硬呼叫 ``_outline_path_d``——空 outline 產生
    ``d="Z"`` 垃圾 path（瀏覽器 console error），且該筆畫在
    ghost/outline/filled 格式樣完全不顯示（user-dict 手寫字只有
    track）。page.py 5ai 早已用「拆兩群」處理，這裡補齊同語意。"""
    outline = [s for s in strokes if s.outline]
    track = [s for s in strokes if not s.outline]
    parts = "".join(f'<path d="{_outline_path_d(s)}"/>' for s in outline)
    if track:
        parts += (f'<g fill="none" stroke="{color}" stroke-width="40" '
                  'stroke-linecap="round" stroke-linejoin="round">' +
                  "".join(f'<polyline points="{_track_points_str(s)}"/>'
                          for s in track) + "</g>")
    return parts


def _cell_content(char: Character, style: CellStyle) -> str:
    """Render one character into one cell's SVG content (no border/guides)."""
    if style == "blank" or not char.strokes:
        return ""
    if style == "ghost":
        # light grey outline — for tracing practice
        return ('<g class="ghost" fill="#e0e0e0">' +
                _outline_or_track(char.strokes, "#e0e0e0") + "</g>")
    if style == "outline":
        # filled stroke outlines (standard display)
        return ('<g class="outline" fill="#222">' +
                _outline_or_track(char.strokes, "#222") + "</g>")
    if style == "trace":
        # centerline track (thin red line) — what the robot will follow
        return ('<g class="trace" fill="none" stroke="#c22" stroke-width="14" '
                'stroke-linecap="round" stroke-linejoin="round">' +
                "".join(f'<polyline points="{_track_points_str(s)}"/>'
                        for s in char.strokes) + "</g>")
    # 'filled' = outline + trace overlay
    return (
        '<g class="outline" fill="#ccc">' +
        _outline_or_track(char.strokes, "#ccc") +
        "</g>"
        '<g class="trace" fill="none" stroke="#c22" stroke-width="10" '
        'stroke-linecap="round" stroke-linejoin="round">' +
        "".join(f'<polyline points="{_track_points_str(s)}"/>'
                for s in char.strokes) +
        "</g>"
    )


# ---------------------------------------------------------------------------
# Phase 5cu: 注音欄（字格右側 2:1 窄欄，注音符號可描紅）
# ---------------------------------------------------------------------------

#: 注音欄寬（EM 座標）——沿用稿紙模式「字:注音 = 2:1」慣例
ZHUYIN_STRIP_EM: int = EM_SIZE // 2

#: 聲調記號手作 polyline（200×200 box；一聲不標、輕聲為點）。
#: 幾何極簡＝機器可寫；不用 <text>（CJK/符號描邊鐵則）。
_ZY_TONE_TRACKS: dict[str, list[list[tuple[int, int]]]] = {
    "ˊ": [[(40, 160), (160, 40)]],
    "ˇ": [[(30, 50), (100, 160), (170, 50)]],
    "ˋ": [[(40, 40), (160, 160)]],
}
_ZY_TONE_CHARS = "ˊˇˋ˙ˉ"


def _zhuyin_layout(
    sym_str: str, zhuyin_chars: dict[str, Character],
) -> tuple[list[tuple[str, Character, float, float, float]],
           list[list[tuple[float, float]]],
           Optional[tuple[float, float, float]]]:
    """5cy：注音欄幾何收集器（SVG 與 G-code 共用——單一真相源，
    調號位置等修正兩端自動同步）。座標系＝strip 視口
    ``ZHUYIN_STRIP_EM × EM_SIZE``。

    Returns ``(placements, tone_tracks, tone_dot)``:

    - ``placements``: ``[(符號字, Character, x, y, scale)]`` 符號放置
      （符號字獨立攜帶——G-code 註解要標原符號，不能信賴
      Character.char，測試 stand-in 曝露過此坑）
    - ``tone_tracks``: 二三四聲 polyline 點列（已平移到最後一個
      符號的右上角——5cv 課本慣例）
    - ``tone_dot``: 輕聲 ``(cx, cy, r)`` 或 ``None``
    """
    w = ZHUYIN_STRIP_EM
    tone = next((c for c in sym_str if c in _ZY_TONE_CHARS), "")
    syms = [c for c in sym_str if c in zhuyin_chars]
    y0 = float(EM_SIZE)
    sym_h = EM_SIZE / 2.0
    last_top = 120.0
    placements: list[tuple[str, Character, float, float, float]] = []
    if syms:
        sym_h = EM_SIZE / max(len(syms), 2)
        s = min(float(w), sym_h) * 0.92
        y0 = (EM_SIZE - sym_h * len(syms)) / 2
        last_top = y0 + (len(syms) - 1) * sym_h
        scale = s / EM_SIZE
        for i, c in enumerate(syms):
            x = (w - s) / 2
            y = y0 + i * sym_h + (sym_h - s) / 2
            placements.append((c, zhuyin_chars[c], x, y, scale))
    tone_tracks: list[list[tuple[float, float]]] = []
    tone_dot: Optional[tuple[float, float, float]] = None
    if tone == "˙":                          # 輕聲：點，標於注音上方
        tone_dot = (w / 2, max(90.0, y0 - 120), 36.0)
    elif tone in _ZY_TONE_TRACKS:
        # 5cv：二三四聲標於「最後一個符號的右上角」（教育部/課本
        # 慣例；原版在欄底右側，使用者實機驗收指正）
        tx_ = w - 230
        ty_ = max(30.0, last_top + sym_h * 0.05)
        tone_tracks = [[(tx_ + px, ty_ + py) for px, py in track]
                       for track in _ZY_TONE_TRACKS[tone]]
    return placements, tone_tracks, tone_dot


def _zhuyin_strip(sym_str: str, zhuyin_chars: dict[str, Character],
                  style: CellStyle) -> str:
    """Render one 注音欄 strip (viewport ``ZHUYIN_STRIP_EM × EM_SIZE``).

    符號經 ``_cell_content`` 渲染——描紅/淡灰/紅軌跡樣式全數繼承，
    「注音也能練筆順」。``blank`` 層只畫外框（學生自行填寫）。
    幾何一律來自 ``_zhuyin_layout``（5cy 收集器）。
    """
    w = ZHUYIN_STRIP_EM
    parts = ['<g class="zhuyin">',
             f'<rect x="0" y="0" width="{w}" height="{EM_SIZE}" '
             f'fill="none" stroke="#cccccc" stroke-width="8"/>']
    if style != "blank":
        placements, tone_tracks, tone_dot = _zhuyin_layout(
            sym_str, zhuyin_chars)
        for _sym, zc, x, y, scale in placements:
            parts.append(
                f'<g transform="translate({x:.1f},{y:.1f}) '
                f'scale({scale:.6f})">'
                f'{_cell_content(zc, style)}</g>')
        color = "#e0e0e0" if style == "ghost" else (
            "#c22" if style in ("trace", "filled") else "#222")
        if tone_dot:
            cx_, cy_, r_ = tone_dot
            parts.append(f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" '
                         f'r="{r_:.0f}" fill="{color}"/>')
        for track in tone_tracks:
            pts = " ".join(f"{px:g},{py}" for px, py in track)
            parts.append(f'<polyline points="{pts}" fill="none" '
                         f'stroke="{color}" stroke-width="28" '
                         f'stroke-linecap="round" '
                         f'stroke-linejoin="round"/>')
    parts.append("</g>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# W2：頁尾生字資訊區
# ---------------------------------------------------------------------------

#: 註記文字的**字級上限**（EM 座標）。EM_SIZE 是一格字的高度，0.18 約等
#: 於格高的六分之一——A4 上印出來約 9pt，教學單註記的常見大小。
INFO_TEXT_EM: float = EM_SIZE * 0.18

#: 一列註記的**目標字數**。字帖整張會等比縮放貼進 A4（W1 ``fit_svg_to_
#: paper``），所以字級只能相對於**版面寬度**決定，不能只綁 EM_SIZE：兩個
#: 生字的窄字帖放大到 A4 後，格高的六分之一會變成半個標題那麼大。實際
#: 字級取 ``min(INFO_TEXT_EM, 版面寬 / 這個數)``，讓一列的字數不論字帖寬
#: 窄都落在 40 上下。
INFO_TARGET_CHARS: int = 40

#: 行高與上下留白，皆相對於**實際**字級（見 :func:`_info_metrics`）。
INFO_LINE_RATIO: float = 1.75
INFO_PAD_EM: float = EM_SIZE * 0.12

#: 釋義的**長度預算**：超過就整段不放（見 :func:`compose_info_line`）。
#: 這是版面預算，不是授權判準——40 字約等於一列，再長就會把整個頁尾撐成
#: 好幾倍高、喧賓奪主。實測第一義項（含例句）長度分佈：中位 18 字、75%
#: 25 字、85.5% ≤32 字、**90.3% ≤40 字**、最長 227 字。
INFO_MAX_CHARS: int = 40

#: 義項放不下時**整段換成這句**——不是截斷後加刪節號。§88 把線畫在這裡：
#: 節錄（選取整個義項）可以，截斷任何一條釋義不可以。所以放不下就不放，
#: 並告訴使用者去看完整條目，絕不出現「…」「...」「（略）」。
INFO_LONG_NOTICE: str = "釋義較長，見完整條目"

#: 欄位分隔符（全形直線，前後各一空格由版面自然留白代替）。
INFO_SEP: str = "｜"


def _info_text_paths(
    text: str,
    glyphs: dict,
    x: float,
    y: float,
    size_em: float,
    color: str = "#444444",
) -> str:
    """把一串文字畫成**字形路徑**（不是 ``<text>``）。

    為什麼不用 ``<text>``：cairosvg 光柵化時吃的是**伺服器**的字型堆疊，
    乾淨 Linux 主機沒有 CJK 字型就會變成空框——§5bv 已經在抄經的句讀上
    踩過並改走 polyline。W1 之後 PDF 是字帖的主要出口，這個坑不能再踩。
    走自家字形資料則任何部署一致（實測 15 字 7.4 KB、快取後 1 ms）。

    ``glyphs`` 缺的字直接跳過並留出空位——不以任何符號代替（§87 不猜）。
    """
    scale = size_em / EM_SIZE
    parts: list[str] = []
    cx = x
    for ch in text:
        g = glyphs.get(ch)
        if g is not None and g.strokes:
            body = _cell_content(g, "filled")
            parts.append(
                f'<g transform="translate({cx:.1f},{y:.1f}) '
                f'scale({scale:.6f})" fill="{color}">{body}</g>')
        cx += size_em
    return "".join(parts)


def _info_metrics(width_em: float) -> tuple[float, float, int]:
    """版面寬度 → ``(字級, 行高, 一列字數)``。等寬前進，故字數＝寬÷字級。"""
    text_em = min(INFO_TEXT_EM, width_em / INFO_TARGET_CHARS)
    return text_em, text_em * INFO_LINE_RATIO, max(1, int(width_em / text_em))


def _ink_band(glyphs: dict) -> tuple[float, float]:
    """註記字形的實際墨跡上下緣（EM 座標）。

    **不能假設字形填滿 0..EM_SIZE 的框。** 註記走的是 noto_hei，它的字形
    是以基線為準放進 em 框的：實測墨跡落在 y∈[573, 2728]（EM_SIZE=2048）
    ——上方空 0.28 em、下方**超出框 0.33 em**。照「框頂＝y、框高＝字級」
    排版就會把最後一列削掉半個字（第一版的 PNG 正是如此）。所以量出來再
    排，而不是相信框。

    量不到（沒有字形）時回 ``(0, EM_SIZE)``——反正也沒有東西要畫。
    """
    lo = hi = None
    for g in glyphs.values():
        for st in getattr(g, "strokes", ()):  # type: ignore[attr-defined]
            b = st.bbox
            lo = b.y_min if lo is None else min(lo, b.y_min)
            hi = b.y_max if hi is None else max(hi, b.y_max)
    if lo is None or hi is None or hi <= lo:
        return 0.0, float(EM_SIZE)
    return float(lo), float(hi)


def compose_info_line(row: dict) -> str:
    """一筆生字資料 → 一列註記文字。**唯一決定「放不下怎麼辦」的地方。**

    ``row`` 欄位（皆為選填字串）::

        {"char": "春", "meta": "日部・9畫・ㄔㄨㄣ",
         "definition": "教育部原文第一義項", "words": "造詞：春天、春季"}

    釋義**要嘛整條原文、要嘛一個字都不放**：超過 :data:`INFO_MAX_CHARS`
    就整段換成 :data:`INFO_LONG_NOTICE`，絕不截斷（§88 節錄可以、截斷不
    行）。這是**內容長度**的判準，與版面寬窄無關——版面放不下是換行處理
    的事（換行不減字，不涉及授權）。
    """
    char = (row.get("char") or "").strip()
    meta = (row.get("meta") or "").strip()
    definition = (row.get("definition") or "").strip()
    words = (row.get("words") or "").strip()

    if definition and len(definition) > INFO_MAX_CHARS:
        definition = INFO_LONG_NOTICE
    return INFO_SEP.join(p for p in (char, meta, definition, words) if p)


def _wrap(text: str, capacity: int) -> list[str]:
    """等寬硬換行。**不刪字**——所以與 §88 無關（截斷才是改作）。"""
    if not text:
        return []
    return [text[i:i + capacity] for i in range(0, len(text), capacity)]


def _info_footer_svg(
    rows: list[dict],
    glyphs: dict,
    width_em: float,
) -> tuple[str, int]:
    """生字資訊區 → ``(svg 片段, 高度 EM)``。

    每個生字一列：``部首・筆畫・注音 ｜ 第一義項 ｜ 造詞``。義項太長時
    **整段留白並註明**，絕不截斷後當原文（§88：節錄可以、截斷不行）。
    """
    if not rows:
        return "", 0
    text_em, line_h, capacity = _info_metrics(width_em)
    wrapped = [(r, _wrap(compose_info_line(r), capacity)) for r in rows]
    n_lines = sum(len(w) for _r, w in wrapped)
    scale = text_em / EM_SIZE
    ink_top, ink_bot = _ink_band(glyphs)
    ink_h = (ink_bot - ink_top) * scale
    line_h = max(line_h, ink_h)          # 行距不得小於墨跡高，否則相疊
    # 高度＝上下留白＋(n-1) 個行距＋最後一列的**墨跡**高
    height = round(INFO_PAD_EM * 2 + line_h * (n_lines - 1) + ink_h)
    parts = [f'<g class="info-footer" data-info-rows="{len(rows)}">',
             f'<line x1="0" y1="{INFO_PAD_EM:.1f}" x2="{width_em:.1f}" '
             f'y2="{INFO_PAD_EM:.1f}" stroke="#cccccc" stroke-width="6"/>']
    # y 是該列**墨跡**頂端；扣掉字形框內上方的空白才是 translate 的原點
    y = INFO_PAD_EM * 2 - ink_top * scale
    for r, lines in wrapped:
        parts.append(
            f'<g class="info-row" data-char="{_esc_attr(r.get("char", ""))}">')
        for ln in lines:
            parts.append(_info_text_paths(ln, glyphs, 0.0, y, text_em))
            y += line_h
        parts.append("</g>")
    parts.append("</g>")
    return "".join(parts), height


def _esc_attr(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace('"', "&quot;"))


def render_grid_svg(
    chars: list[Character],
    *,
    cols: int = 1,
    guide: GridStyle = "tian",
    cell_style: CellStyle = "outline",
    cell_size_px: int = 120,
    ghost_copies: Optional[int] = None,
    blank_copies: Optional[int] = None,
    direction: Literal["horizontal", "vertical"] = "horizontal",
    repeat_per_char: int = 1,   # kept for back-compat; no longer affects layout
    # 5cu：注音欄——zhuyin_map 由前端算好傳入（伺服器零字典依賴），
    # zhuyin_chars 為符號 Character 表（server 以 char_loader 載入）
    zhuyin_map: Optional[dict[str, str]] = None,
    zhuyin_chars: Optional[dict[str, Character]] = None,
    # W2：頁尾生字資訊區。**opt-in（預設關）**——它會加高整張 SVG，開了就
    # 改變既有字帖的輸出尺寸，故絕不預設開啟（同 W1 對 grid 加紙張的顧慮）。
    # info_rows 由呼叫端備妥（伺服器層查字典），這裡只排版；info_glyphs 是
    # 註記文字要用到的字形表——文字走**自家字形路徑**而非 <text>，因為
    # cairosvg 的 <text> 吃伺服器字型堆疊，缺 CJK 會變空框（§5bv 已踩過，
    # 而 W1 之後 PDF 是主要出口）。
    info_footer: bool = False,
    info_rows: Optional[list[dict]] = None,
    info_glyphs: Optional[dict[str, Character]] = None,
) -> str:
    """
    Render a 字帖-style worksheet SVG with **tier-based** layout (Phase 5j).

    Given ``N`` input characters (= string length), this function builds a
    grid of exactly ``N`` cells per "tier" (row in 橫書, column in 直書)
    and stacks multiple tiers:

    - Tier 1: primary (full characters in ``cell_style``)
    - Tiers 2..1+ghost_copies: ghost (light grey for tracing practice)
    - Tiers 2+ghost..: blank (empty cells for freehand practice)

    ``cols`` sets the **total tier count**. If ``ghost_copies`` or
    ``blank_copies`` are ``None``, they are auto-derived from ``cols``:

    ======  ======  ======
    cols    ghost   blank
    ======  ======  ======
    1       0       0
    2       1       0
    3       1       1
    4       1       2
    N≥3     1       N-2
    ======  ======  ======

    Layout orientation
    ------------------
    - ``horizontal`` (橫書): each tier is a ROW of N cells; tiers stack
      top-to-bottom (row 0 = primary, last row = last blank tier).
    - ``vertical`` (直書): each tier is a COLUMN of N cells; tiers stack
      right-to-left (rightmost column = primary, leftmost = last tier).

    ``repeat_per_char`` is kept in the signature for backward-compatibility
    but no longer affects layout — the new semantic always uses exactly one
    primary tier per worksheet.
    """
    if not chars:
        return ('<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 1 1"></svg>')

    N = len(chars)

    auto_g, auto_b = auto_tier_counts(cols)
    if ghost_copies is None:
        ghost_copies = auto_g
    if blank_copies is None:
        blank_copies = auto_b
    ghost_copies = max(0, ghost_copies)
    blank_copies = max(0, blank_copies)

    # Build tiers (each tier has exactly N cells — one per character)
    tiers: list[list[tuple[Character, CellStyle]]] = []
    tiers.append([(c, cell_style) for c in chars])          # primary
    for _ in range(ghost_copies):
        tiers.append([(c, "ghost") for c in chars])
    for _ in range(blank_copies):
        tiers.append([(c, "blank") for c in chars])
    num_tiers = len(tiers)

    if direction == "vertical":
        grid_cols = num_tiers
        grid_rows = N
    else:
        grid_cols = N
        grid_rows = num_tiers

    # 5cu：注音欄開啟時每格加寬為「字格＋右側窄欄」（2:1）
    zy_on = zhuyin_map is not None
    zhuyin_chars = zhuyin_chars or {}
    pair_w = EM_SIZE + (ZHUYIN_STRIP_EM if zy_on else 0)

    total_w_em = grid_cols * pair_w
    grid_h_em = grid_rows * EM_SIZE

    # W2：先算頁尾（高度要併進畫布），最後才輸出。關閉時 footer_h_em 為 0，
    # 下面每一項尺寸都與 W2 之前逐位元組相同——零回歸由測試鎖住。
    footer_svg = ""
    footer_h_em = 0
    if info_footer and info_rows:
        footer_svg, footer_h_em = _info_footer_svg(
            info_rows, info_glyphs or {}, total_w_em)

    # footer 關閉時保持 int，viewBox 字串才與 W2 之前逐位元組相同
    total_h_em = grid_h_em + footer_h_em if footer_h_em else grid_h_em
    total_w_px = round(grid_cols * cell_size_px * pair_w / EM_SIZE)
    total_h_px = round(total_h_em * cell_size_px / EM_SIZE)

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{total_w_px}" height="{total_h_px}" '
        f'viewBox="0 0 {total_w_em} {total_h_em}" '
        # 5cu：前端（5cs G-code 組裝等）需要知道格距——EM 座標
        f'data-pair-em="{pair_w}">'
    ]
    out.append(f'<rect x="0" y="0" width="{total_w_em}" '
               f'height="{total_h_em}" fill="white"/>')
    guide_svg = _guide_paths(guide)

    for tier_idx, tier in enumerate(tiers):
        for char_idx, (ch, style) in enumerate(tier):
            if direction == "vertical":
                # Rightmost column is tier 0 (primary); stacked leftward
                col = (num_tiers - 1) - tier_idx
                row = char_idx
            else:
                col = char_idx
                row = tier_idx
            tx = col * pair_w
            ty = row * EM_SIZE
            # 5cn：cell 定位標記——「自訂字型」前端注入需要知道每格
            # 是哪個字、哪種格式樣（純屬性、視覺零變化）
            esc = (ch.char.replace("&", "&amp;").replace("<", "&lt;")
                          .replace('"', "&quot;"))
            out.append(f'<g transform="translate({tx},{ty})" '
                       f'data-char="{esc}" data-cell-style="{style}">')
            out.append(f'  {guide_svg}')
            out.append(f'  {_cell_content(ch, style)}')
            out.append("</g>")
            if zy_on:
                sym = zhuyin_map.get(ch.char, "")
                out.append(f'<g transform="translate({tx + EM_SIZE},{ty})">'
                           f'{_zhuyin_strip(sym, zhuyin_chars, style)}</g>')
    if footer_svg:
        out.append(f'<g transform="translate(0,{grid_h_em})">'
                   f'{footer_svg}</g>')
    out.append("</svg>")
    return "\n".join(out)


def save_grid_svg(chars: list[Character], path: str, **kwargs) -> None:
    svg = render_grid_svg(chars, **kwargs)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


# ---------------------------------------------------------------------------
# Cell positioning helper (shared across SVG / G-code / JSON renderers)
# ---------------------------------------------------------------------------


def _grid_cell_positions(
    chars: list[Character],
    cols: int,
    ghost_copies: Optional[int],
    blank_copies: Optional[int],
    direction: Literal["horizontal", "vertical"],
) -> tuple[list[dict], int, int]:
    """Compute per-cell metadata for the grid layout.

    Returns ``(cells, grid_cols, grid_rows)`` where each cell dict has:
    ``{char, char_idx, tier_idx, tier_kind, col, row, cell_style_default}``.

    ``tier_kind`` ∈ {"primary", "ghost", "blank"}.
    """
    N = len(chars)
    if N == 0:
        return [], 1, 1

    auto_g, auto_b = auto_tier_counts(cols)
    g = auto_g if ghost_copies is None else max(0, ghost_copies)
    b = auto_b if blank_copies is None else max(0, blank_copies)
    num_tiers = 1 + g + b

    cells: list[dict] = []
    for tier_idx in range(num_tiers):
        if tier_idx == 0:
            kind = "primary"
        elif tier_idx <= g:
            kind = "ghost"
        else:
            kind = "blank"
        for char_idx in range(N):
            if direction == "vertical":
                col = (num_tiers - 1) - tier_idx  # rightmost = primary
                row = char_idx
            else:
                col = char_idx
                row = tier_idx
            cells.append({
                "char": chars[char_idx],
                "char_idx": char_idx,
                "tier_idx": tier_idx,
                "tier_kind": kind,
                "col": col,
                "row": row,
            })

    if direction == "vertical":
        grid_cols, grid_rows = num_tiers, N
    else:
        grid_cols, grid_rows = N, num_tiers
    return cells, grid_cols, grid_rows


# ---------------------------------------------------------------------------
# G-code renderer — primary tier only (A1 rule)
# ---------------------------------------------------------------------------


def render_grid_gcode(
    chars: list[Character],
    *,
    cols: int = 1,
    ghost_copies: Optional[int] = None,
    blank_copies: Optional[int] = None,
    direction: Literal["horizontal", "vertical"] = "horizontal",
    cell_size_mm: float = 20.0,
    cell_gap_mm: float = 0.0,
    feed_rate: int = 3000,
    travel_rate: int = 6000,
    pen_up_cmd: str = "M5",
    pen_down_cmd: str = "M3 S90",
    pen_dwell_sec: float = 0.15,
    flip_y: bool = True,
    origin_x_mm: float = 10.0,
    origin_y_mm: float = 10.0,
    # 5cy：注音欄進 G-code——與 SVG 同源（zhuyin_map/zhuyin_chars
    # 由 server 解析傳入；幾何走 _zhuyin_layout 收集器）
    zhuyin_map: Optional[dict[str, str]] = None,
    zhuyin_chars: Optional[dict[str, Character]] = None,
) -> str:
    """Emit G-code for the grid's primary tier only.

    Ghost (pre-traced example) and blank (student practice) tiers are skipped
    — the writing robot only needs to write the primary/master cells.

    Cells are emitted in **tier order**: horizontal mode scans the primary
    row left-to-right; vertical mode scans the primary column top-to-bottom.
    This keeps pen motion visually predictable (B1 rule).

    5cy：``zhuyin_map`` 存在時每格加寬為 pair（2:1，同 SVG 版面），
    主字寫完接著寫該格注音符號與調號——「注音也能機器寫」。
    """
    import math
    from io import StringIO
    from ..ir import EM_SIZE

    cells, grid_cols, grid_rows = _grid_cell_positions(
        chars, cols, ghost_copies, blank_copies, direction,
    )
    primary_cells = [c for c in cells if c["tier_kind"] == "primary"]
    # Order: left-to-right for horizontal, top-to-bottom for vertical
    if direction == "vertical":
        primary_cells.sort(key=lambda c: c["row"])
    else:
        primary_cells.sort(key=lambda c: c["col"])

    zy_on = zhuyin_map is not None
    zhuyin_chars = zhuyin_chars or {}
    pair_em = EM_SIZE + (ZHUYIN_STRIP_EM if zy_on else 0)
    # 5cy：X 間距隨 pair 加寬（zy 關閉時 pair_em=EM ＝原間距，零回歸）
    x_pitch = cell_size_mm * pair_em / EM_SIZE + cell_gap_mm
    cell_pitch = cell_size_mm + cell_gap_mm
    scale = cell_size_mm / EM_SIZE

    buf = StringIO()
    buf.write("; --- stroke-order 字帖 G-code (primary tier only) ---\n")
    buf.write(f"; chars: {''.join(c.char for c in chars)}\n")
    buf.write(f"; cell_size={cell_size_mm}mm gap={cell_gap_mm}mm "
              f"direction={direction} feed={feed_rate}\n")
    if zy_on:
        buf.write("; zhuyin: pair layout 2:1 (字格＋右側注音欄)\n")
    buf.write("G21 ; mm\n")
    buf.write("G90 ; absolute\n")
    buf.write(f"{pen_up_cmd} ; pen up (start)\n")
    if pen_dwell_sec > 0:
        buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")
    buf.write(f"G0 X{origin_x_mm:.3f} Y{origin_y_mm:.3f} F{travel_rate} ; home\n")

    for cell in primary_cells:
        ch = cell["char"]
        # Cell origin in the output coordinate system
        # horizontal: column increases → X increases; row increases → Y increases
        # 5cy：X 用 pair 間距（注音關閉時 x_pitch == cell_pitch）
        cell_x = origin_x_mm + cell["col"] * x_pitch
        cell_y = origin_y_mm + cell["row"] * cell_pitch

        buf.write(f"\n; --- cell ({cell['row']},{cell['col']}): "
                  f"{ch.char} (U+{ch.unicode_hex.upper()}) ---\n")

        def _emit_track(pts_em: list[tuple[float, float]]) -> None:
            """一條筆畫（cell 內 EM 座標）→ 抬筆定位/落筆/走筆/抬筆。"""
            def _mm(px: float, py: float) -> tuple[float, float]:
                y_ir = (EM_SIZE - py) if flip_y else py
                return cell_x + px * scale, cell_y + y_ir * scale

            x, y = _mm(*pts_em[0])
            buf.write(f"G0 X{x:.3f} Y{y:.3f} F{travel_rate}\n")
            buf.write(f"{pen_down_cmd}\n")
            if pen_dwell_sec > 0:
                buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")
            for px, py in pts_em[1:]:
                x, y = _mm(px, py)
                buf.write(f"G1 X{x:.3f} Y{y:.3f} F{feed_rate}\n")
            if pen_dwell_sec > 0:
                buf.write(f"G4 P{int(pen_dwell_sec * 1000)}\n")
            buf.write(f"{pen_up_cmd}\n")

        for s in ch.strokes:
            pts = s.track
            if not pts:
                continue
            buf.write(f"; stroke {s.index + 1}: {s.kind_name}\n")
            _emit_track([(p.x, p.y) for p in pts])

        # 5cy：注音欄——主字寫完接著寫本格注音（strip 在字格右側，
        # X 偏移 EM_SIZE；幾何與 SVG 同源 _zhuyin_layout）
        if zy_on:
            sym = zhuyin_map.get(ch.char, "")
            placements, tone_tracks, tone_dot = _zhuyin_layout(
                sym, zhuyin_chars)
            for zsym, zc, zx, zy_, zscale in placements:
                for s in zc.strokes:
                    if not s.track:
                        continue
                    buf.write(f"; zhuyin {zsym} "
                              f"stroke {s.index + 1}: {s.kind_name}\n")
                    _emit_track([
                        (EM_SIZE + zx + p.x * zscale, zy_ + p.y * zscale)
                        for p in s.track])
            for track in tone_tracks:
                buf.write("; zhuyin tone\n")
                _emit_track([(EM_SIZE + px, py) for px, py in track])
            if tone_dot:
                # 輕聲點＝八邊形微圓（r=36 EM ≈ 0.35mm @20mm 格）
                cx_, cy_, r_ = tone_dot
                buf.write("; zhuyin tone dot\n")
                _emit_track([
                    (EM_SIZE + cx_ + r_ * math.cos(i * math.pi / 4),
                     cy_ + r_ * math.sin(i * math.pi / 4))
                    for i in range(9)])

    buf.write("\n; --- epilogue ---\n")
    buf.write(f"{pen_up_cmd} ; ensure pen up\n")
    buf.write(f"G0 X{origin_x_mm:.3f} Y{origin_y_mm:.3f} F{travel_rate} ; return home\n")
    buf.write("; done\n")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# JSON renderer — full grid metadata + all cells (C2 rule)
# ---------------------------------------------------------------------------


def render_grid_json(
    chars: list[Character],
    *,
    cols: int = 1,
    ghost_copies: Optional[int] = None,
    blank_copies: Optional[int] = None,
    direction: Literal["horizontal", "vertical"] = "horizontal",
    cell_size_mm: float = 20.0,
    cell_gap_mm: float = 0.0,
    guide: GridStyle = "tian",
    cell_style: CellStyle = "filled",
    indent: int = 2,
) -> str:
    """Render the grid as structured JSON.

    Output shape::

        {
          "grid": {
            "chars": [...],
            "N": 4,
            "cols": 3,
            "direction": "horizontal",
            "grid_cols": 4, "grid_rows": 3,
            "cell_size_mm": 20.0, "cell_gap_mm": 0.0,
            "guide": "tian",
            "tier_counts": {"primary": 1, "ghost": 1, "blank": 1}
          },
          "cells": [
            {
              "char": "日", "unicode": "U+65E5",
              "tier_idx": 0, "tier_kind": "primary",
              "col": 0, "row": 0,
              "x_mm": 0.0, "y_mm": 0.0,
              "cell_style": "filled",
              "strokes": [ [[x,y], ...], ... ]   # only if primary
            },
            ...
          ]
        }

    Non-primary cells omit ``strokes`` (they're empty for practice anyway).
    """
    import json

    cells, grid_cols_n, grid_rows_n = _grid_cell_positions(
        chars, cols, ghost_copies, blank_copies, direction,
    )
    cell_pitch = cell_size_mm + cell_gap_mm

    auto_g, auto_b = auto_tier_counts(cols)
    g = auto_g if ghost_copies is None else max(0, ghost_copies)
    b = auto_b if blank_copies is None else max(0, blank_copies)

    cells_out = []
    for cell in cells:
        ch = cell["char"]
        style = cell_style if cell["tier_kind"] == "primary" else cell["tier_kind"]
        cell_out: dict = {
            "char": ch.char,
            "unicode": f"U+{ch.unicode_hex.upper()}",
            "tier_idx": cell["tier_idx"],
            "tier_kind": cell["tier_kind"],
            "col": cell["col"],
            "row": cell["row"],
            "x_mm": round(cell["col"] * cell_pitch, 3),
            "y_mm": round(cell["row"] * cell_pitch, 3),
            "cell_style": style,
        }
        if cell["tier_kind"] == "primary":
            # Emit stroke polylines scaled to the cell's mm coord frame
            from ..ir import EM_SIZE
            scale = cell_size_mm / EM_SIZE
            strokes = []
            for s in ch.strokes:
                track = [[round(p.x * scale, 3), round(p.y * scale, 3)]
                         for p in s.track]
                strokes.append({
                    "index": s.index,
                    "kind_name": s.kind_name,
                    "has_hook": s.has_hook,
                    "track_mm": track,
                })
            cell_out["strokes"] = strokes
        cells_out.append(cell_out)

    payload = {
        "grid": {
            "chars": [c.char for c in chars],
            "N": len(chars),
            "cols": cols,
            "direction": direction,
            "grid_cols": grid_cols_n,
            "grid_rows": grid_rows_n,
            "cell_size_mm": cell_size_mm,
            "cell_gap_mm": cell_gap_mm,
            "guide": guide,
            "tier_counts": {"primary": 1, "ghost": g, "blank": b},
        },
        "cells": cells_out,
    }
    return json.dumps(payload, ensure_ascii=False, indent=indent)


__all__ = ["render_grid_svg", "save_grid_svg", "auto_tier_counts",
           "render_grid_gcode", "render_grid_json",
           "GridStyle", "CellStyle",
           # W2 頁尾生字資訊區
           "INFO_LONG_NOTICE", "INFO_MAX_CHARS", "INFO_SEP",
           "compose_info_line"]
