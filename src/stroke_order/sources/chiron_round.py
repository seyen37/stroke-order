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

可變字重軸（R1b）
------------------
上游另備 CFF2 可變字體 ``VAR_OTF/ChironGoRoundTCVF.otf``（``wght`` 軸
200–900、47,174 字符、21.7 MB）。這是本專案第一個**真字重旋鈕**——字重
由字型設計師逐級調好，不是把輪廓做形態學膨脹的後製濾鏡（那條是
``/api/stencil`` 既有的 ``bold_mm``，語意不同，兩者並存）。

實測（「國」、50 mm 字框、2 mm 連筋，**已套 :func:`resolve_overlaps`**）：

=======  ==================  ==========  ======
wght     筆寬 (px@50 mm)     墨連通件    殘腔
=======  ==================  ==========  ======
200      12.0                5           0
250      16.0                5           0
300      18.0                5           0
500      34.0                5           0
700      42.5                3           0
800      48.0                3           0
850      50.0                2           0
900      52.0                2           0
=======  ==================  ==========  ======

殘腔全程 0（任何字重都是物理有效字模），字碗洞數在 300–800 完全穩定
（國 2、歡 5、明 4——不會被填死）。夾限
``[WEIGHT_MIN, WEIGHT_MAX] = [300, 800]`` 的依據是兩端各有代價：

- **下界 300**：再細就低於 18 px（200 只有 12 px），等比縮到小尺寸字模
  時餘裕不足（同 S1 選 700B 而非 400R 的理由）。
- **上界 800**：850 起「國」的墨連通件掉到 2，比我們已經在出貨的靜態
  700B（3 件）更黏。800 與 700B 同為 3 件，故收在 800。

**雙軌記憶體策略**：VF 首次取字約 217 ms、RSS +75 MB，之後每字約 1 ms。
不給 ``weight`` 時完全不開 VF 檔，走靜態 700B——現有使用者的行為與記憶體
足跡零變動（承 §35–§38 雲端資源天花板教訓）。

Coordinate frame
----------------
``unitsPerEm = 1000``（CFF/OTF），與 `noto_hei` 同路徑：
``scale = EM_SIZE / 1000`` 加 Y 翻轉，走 ``_transform_cmd``。靜態與可變
兩軌 upem 相同，故座標換算共用同一段程式。
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

# ---- R1b 可變字重軸 -------------------------------------------------
_ENV_VF_FILE = "STROKE_ORDER_ROUND_VF_FILE"
_ENV_VF_DIR = "STROKE_ORDER_ROUND_VF_DIR"
_VF_FILENAME = "ChironGoRoundTCVF.otf"
_DEFAULT_VF_FILE = (
    Path.home() / ".stroke-order" / "round-fonts" / _VF_FILENAME
)

#: 字重滑桿可用區間（實測夾定，非上游 fvar 全域 200–900）。
#: 200 在 50 mm 字框只有 12 px 筆寬（小尺寸字模必破）；900 部件開始
#: 黏合（國 墨件 5→2）。300–800 全程殘腔 0。數據見 ADR
#: docs/decisions/2026-08-20_r1b_weight_axis.md。
WEIGHT_MIN = 300
WEIGHT_MAX = 800

#: 靜態檔對應的字重——不給 weight 時走靜態路徑，語意上等同這個值。
STATIC_WEIGHT = 700


def default_round_font_path() -> Path:
    f = os.environ.get(_ENV_FILE)
    if f:
        return Path(f).expanduser()
    d = os.environ.get(_ENV_DIR)
    if d:
        return Path(d).expanduser() / _FONT_FILENAME
    return _DEFAULT_FILE


def default_round_vf_path() -> Path:
    f = os.environ.get(_ENV_VF_FILE)
    if f:
        return Path(f).expanduser()
    d = os.environ.get(_ENV_VF_DIR)
    if d:
        return Path(d).expanduser() / _VF_FILENAME
    return _DEFAULT_VF_FILE


_ATTRIBUTION = (
    "昭源環方 Chiron GoRound TC — Copyright 2024-2026 Tamcy, "
    "Copyright 2014-2025 Adobe, Copyright 2016 The Nunito Sans Project "
    "Authors. SIL Open Font License 1.1. "
    "https://github.com/chiron-fonts/chiron-go-round-tc"
)


def attribution_notice() -> str:
    return _ATTRIBUTION


def resolve_overlaps(
    contours: list[list[tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    """把可變字體的**重疊輪廓**併掉，還原成 even-odd 相容的多輪廓。

    為什麼只有可變字體需要這道
    -----------------------------
    字型的填充規則是 **nonzero**，重疊的同向輪廓會被填成一體。靜態字重
    檔在建置時已做過 overlap removal，所以拿 even-odd 畫也對；但**重疊
    消除的結果無法沿 wght 軸內插**，可變字體因此保留重疊輪廓。直接用
    even-odd 畫會在重疊處打出假洞——實測「明」洞數 4→10、墨面積少 6.2%，
    「永」0→2。

    作法：依帶號面積判外環／洞環（nonzero 的實務近似），
    ``union(外環) - union(洞環)``，再攤平回外環＋洞環折線。與
    ``skeleton_glyph`` 的輸出契約一致（list[list[(x, y)]]、開放點列）。

    shapely 缺席時原樣回傳並不假裝成功——呼叫端寧可拿到已知有瑕疵的
    幾何，也不要靜默吞掉（承 §8 誠實降級）。
    """
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except Exception:                       # pragma: no cover — 選用相依
        return contours

    def _signed_area(c) -> float:
        a = 0.0
        for i in range(len(c)):
            x1, y1 = c[i]
            x2, y2 = c[(i + 1) % len(c)]
            a += x1 * y2 - x2 * y1
        return a / 2.0

    rings = []
    for c in contours:
        if len(c) < 3:
            continue
        p = Polygon(c)
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty and p.area > 0:
            rings.append((_signed_area(c), p))
    if not rings:
        return contours

    # 外環方向不寫死：本專案是 Y-down EM 框，順逆時針的絕對意義與教科書
    # 相反。但「面積最大的環必為外環」在任何座標慣例下都成立——以它的
    # 帶號方向定義外環方向，日後翻座標系也不會壞。
    outer_positive = max(rings, key=lambda r: r[1].area)[0] > 0

    # **逐環套用、依面積遞減**：外環方向→聯集，洞環方向→差集。
    #
    # 兩個都必要，缺一不可：
    #  · 只看方向、批次做「外環聯集 − 洞環聯集」→ 巢狀字爆掉。「田」是
    #    口的洞裡再放十，一次性差集把十整個扣掉（實測面積 −33%、洞 4→1）。
    #  · 只看巢狀深度、不看方向 → 落在別的筆畫內部的重疊筆畫被誤判成洞
    #    而扣掉（實測「歡」面積 −29%、「鬱」−15%）。
    # 依面積遞減可保證父環先於子環處理，十因此在洞被挖掉之後才聯集回去；
    # 同向重疊的筆畫落進聯集、自然被吸收——那正是本函式要解的原始問題。
    rings.sort(key=lambda r: r[1].area, reverse=True)
    shape = None
    for area, poly in rings:
        if (area > 0) == outer_positive:
            shape = poly if shape is None else shape.union(poly)
        elif shape is not None:
            shape = shape.difference(poly)
    if shape is None or shape.is_empty:
        return contours

    out: list[list[tuple[float, float]]] = []
    for poly in getattr(shape, "geoms", [shape]):
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        for ring in (poly.exterior, *poly.interiors):
            coords = list(ring.coords)
            if len(coords) >= 2 and coords[0] == coords[-1]:
                coords = coords[:-1]        # 開放點列（同 _outline_to_polylines）
            if len(coords) >= 3:
                out.append([(float(x), float(y)) for x, y in coords])
    return out or contours


class ChironRoundSource:
    """昭源環方 (圓體) outline loader — 圓端點的字模底。

    雙軌（R1b）：``get_character(ch)`` 走**靜態 700B**（現行行為，位元不變、
    RSS 不變）；``get_character(ch, weight=450)`` 才走**可變字體**。VF 檔在
    第一次收到 weight 前完全不開啟——這是「預設不付 VF 記憶體代價」的實作
    點，並由 ``test_chiron_round_vf`` 鎖住。
    """

    #: 給 zentangle 管線判斷「這個字源吃不吃 weight」（單一事實源，
    #: 呼叫端不必 try/except TypeError 去猜）。
    supports_weight = True

    #: 可變字重路徑的幾何補正（重疊輪廓 → even-odd 相容）。掛在字源上
    #: 而非寫死在管線裡：管線只問「這個字源有沒有要補正的東西」。
    resolve_overlaps = staticmethod(resolve_overlaps)

    def __init__(self, font_path: Optional[Path] = None,
                 vf_path: Optional[Path] = None) -> None:
        self.font_path = (
            Path(font_path) if font_path else default_round_font_path()
        )
        self.vf_path = Path(vf_path) if vf_path else default_round_vf_path()
        self._font: object = None
        self._vf: object = None
        self._cache: dict[tuple[str, Optional[int]], Character] = {}

    def __repr__(self) -> str:
        return (f"ChironRoundSource(file={self.font_path!s}, "
                f"vf={self.vf_path!s}, "
                f"loaded={self._font is not None}, "
                f"vf_loaded={self._vf is not None}, "
                f"cached={len(self._cache)})")

    def is_ready(self) -> bool:
        return self.font_path.exists()

    def vf_ready(self) -> bool:
        """可變字體是否可用（不開檔，只看存在）——供 UI 決定要不要給滑桿。"""
        return self.vf_path.exists()

    @staticmethod
    def _ttfont(path: Path):
        try:
            from fontTools.ttLib import TTFont
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "fontTools is required for ChironRoundSource; "
                "install with `pip install fonttools`"
            ) from e
        return TTFont(str(path), lazy=True)

    def _load_font(self):
        if self._font is not None:
            return self._font
        if not self.font_path.exists():
            return None
        self._font = self._ttfont(self.font_path)
        return self._font

    def _load_vf(self):
        """可變字體懶載——只有真的要調字重時才開檔（RSS 雙軌）。"""
        if self._vf is not None:
            return self._vf
        if not self.vf_path.exists():
            return None
        self._vf = self._ttfont(self.vf_path)
        return self._vf

    def available_glyph_count(self) -> int:
        font = self._load_font()
        if font is None:
            return 0
        return len(font.getBestCmap())

    def get_character(self, char: str, *,
                      weight: Optional[int] = None) -> Character:
        """``weight=None`` → 靜態 700B；給值 → 可變字體該字重。

        weight 須落在 ``[WEIGHT_MIN, WEIGHT_MAX]``（實測夾定，見模組
        docstring）；超出拋 ``ValueError``（呼叫端轉 422）。
        """
        if weight is not None:
            weight = int(weight)
            if not WEIGHT_MIN <= weight <= WEIGHT_MAX:
                raise ValueError(
                    f"weight must be within [{WEIGHT_MIN}, {WEIGHT_MAX}], "
                    f"got {weight}"
                )
        key = (char, weight)
        if key in self._cache:
            return self._cache[key]

        if weight is None:
            font = self._load_font()
            if font is None:
                raise CharacterNotFound(
                    f"昭源環方 (Chiron GoRound TC) not installed; "
                    f"checked {self.font_path}"
                )
            glyph_set = font.getGlyphSet()
        else:
            font = self._load_vf()
            if font is None:
                raise CharacterNotFound(
                    f"昭源環方可變字體 (Chiron GoRound TC VF) not installed; "
                    f"checked {self.vf_path}"
                )
            glyph_set = font.getGlyphSet(location={"wght": float(weight)})

        cp = ord(char)
        gname = font.getBestCmap().get(cp)
        if gname is None:
            raise CharacterNotFound(
                f"昭源環方 has no glyph for U+{cp:04X} ({char!r})"
            )
        pen = _OutlineCmdPen(glyph_set)
        glyph_set[gname].draw(pen)
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
        self._cache[key] = c
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
    "WEIGHT_MAX",
    "WEIGHT_MIN",
    "STATIC_WEIGHT",
    "default_round_font_path",
    "default_round_vf_path",
    "resolve_overlaps",
    "attribution_notice",
    "get_round_source",
    "reset_round_singleton",
]
