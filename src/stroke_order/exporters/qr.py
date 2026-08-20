"""
QR code 產生（W3）——紙本 → 線上字典的動線。

字帖評估建議書（`docs/analysis/2026-08-20_worksheet_generator_evaluation.md`）
盤出的三個缺口之一：**紙本連不回線上**。同好的字帖產生器在每個字旁附教育
百科的連結與 QR，學生把單子印出來、掃碼就能自學——這是那份借鏡裡最好的
點子，而本專案完全沒有。

為什麼不需要教育百科的 API
--------------------------
教育百科有 Open API（``/api/v2/Detail``），但**要註冊 api_key**——那是執行期
外部相依＋密鑰管理，正是 §68／§86 花兩輪根治掉的東西。而**詞條頁本身是純
網址**（見 :data:`PEDIA_ENTRY_URL`，實測 HTTP 200），編碼進 QR 完全不必連網、
不必金鑰、離線可產。我們只「連過去」，不抓也不轉存它的內容。

為什麼自己組 SVG
----------------
``segno`` 有自己的 SVG writer，但它只吃 bytes buffer，而且我們要控制配色與
模組尺寸以配合教學單版面。它另外暴露 ``q.matrix``（逐列的布林矩陣），所以
直接依矩陣組 ``<rect>``——與本專案「自己組 SVG 字串」的既有風格一致。

相依
----
``segno``：BSD、純 Python、**零執行期相依**（``importlib-metadata`` 只在
Python < 3.10 需要，本專案 ``requires-python >= 3.10``）。放 web extras；
缺席時拋 :class:`QrUnavailable`，呼叫端降級為不印 QR——字帖與教學單照常
產出，不因為少一枚 QR 就整張失敗（§8）。
"""
from __future__ import annotations

from urllib.parse import quote

__all__ = [
    "PEDIA_ENTRY_URL",
    "QrUnavailable",
    "is_available",
    "pedia_url",
    "qr_svg",
]

#: 教育百科詞條頁樣板——**全專案唯一一份**。前端不自己拼（由
#: ``/api/dict/{char}`` 的 ``entry_url`` 供給），由 test_qr 的守門鎖住。
#: 實測 ``?title=春`` 回 HTTP 200。
PEDIA_ENTRY_URL = "https://pedia.cloud.edu.tw/Entry/Detail?title={q}"

#: QR 內容長度上限——教育百科網址遠小於此；純粹擋惡意超長輸入。
MAX_QR_TEXT = 512


class QrUnavailable(Exception):
    """segno 未安裝——QR 不可用。呼叫端應降級為不印，而非整張失敗。"""


def is_available() -> bool:
    """segno 是否可用（不拋例外，供健檢／呼叫端預判）。"""
    try:
        import segno  # noqa: F401
        return True
    except Exception:
        return False


def pedia_url(char: str) -> str:
    """單字 → 教育百科詞條頁網址。"""
    if not isinstance(char, str) or not char.strip():
        raise ValueError("char must be a non-empty string")
    return PEDIA_ENTRY_URL.format(q=quote(char, safe=""))


def qr_svg(
    text: str,
    *,
    module_px: int = 4,
    quiet: int = 2,
    fg: str = "#222222",
    title: str | None = None,
) -> str:
    """``text`` → QR 的獨立 SVG 字串。

    Parameters
    ----------
    module_px
        每個模組（小方格）邊長 px。整體邊長 = (模組數 + 2×quiet) × module_px。
    quiet
        靜區寬度（模組數）。QR 規範建議 4；教學單版面吃緊時 2 仍可掃，
        預設 2 並把它留成參數。
    fg
        暗模組顏色。淺色留給背景——**不畫白底**，讓呼叫端決定（內嵌進
        教學單時背景本來就是白的）。

    Raises
    ------
    QrUnavailable
        segno 未安裝。
    ValueError
        ``text`` 為空或超過 :data:`MAX_QR_TEXT`。
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if len(text) > MAX_QR_TEXT:
        raise ValueError(f"text too long ({len(text)} > {MAX_QR_TEXT})")
    if module_px < 1 or quiet < 0:
        raise ValueError("module_px must be >= 1 and quiet >= 0")
    try:
        import segno
    except ImportError as e:
        raise QrUnavailable(
            "segno is required for QR codes; install with `pip install segno`"
        ) from e

    # error='m'（~15% 糾錯）：紙本列印後可能有墨點/折痕，比預設 'l' 穩，
    # 又不像 'q'/'h' 那樣把模組數推高、在小尺寸上變得難掃。
    q = segno.make(text, error="m")
    matrix = [list(row) for row in q.matrix]
    n = len(matrix)
    side = (n + 2 * quiet) * module_px

    # 同一列連續的暗模組併成一個 <rect>——「田」這種規則圖樣能省下大半
    # 標記量，內嵌進自包含教學單時檔案小很多。
    rects: list[str] = []
    for r, row in enumerate(matrix):
        c = 0
        while c < n:
            if not row[c]:
                c += 1
                continue
            start = c
            while c < n and row[c]:
                c += 1
            x = (quiet + start) * module_px
            y = (quiet + r) * module_px
            w = (c - start) * module_px
            rects.append(f'<rect x="{x}" y="{y}" width="{w}" '
                         f'height="{module_px}"/>')

    title_el = f"<title>{_esc(title)}</title>" if title else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{side}" height="{side}" viewBox="0 0 {side} {side}" '
        f'shape-rendering="crispEdges" role="img" '
        f'data-qr-modules="{n}" data-qr-quiet="{quiet}">'
        f'{title_el}'
        f'<g fill="{fg}">{"".join(rects)}</g>'
        f'</svg>'
    )


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;"))
