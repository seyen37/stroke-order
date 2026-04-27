"""
Sutra preset metadata + external-file loader (Phase 5az / 5bb).

Layout
------
::

    ~/.stroke-order/sutras/
    ├── builtin/                         ← canonical 4 presets (Phase 5az)
    │   ├── heart_sutra.txt
    │   ├── diamond_sutra.txt
    │   ├── great_compassion.txt
    │   └── manjushri_mantra.txt
    └── user/                            ← user-uploaded presets (Phase 5bb)
        ├── <key>.txt                    plain UTF-8 text
        └── <key>.json                   metadata (title, category, repeat...)

Each user file has an optional sibling ``.json`` with these fields::

    {
      "title": "道德經",
      "subtitle": "手抄本",
      "category": "taoist",
      "source": "老子",
      "description": "...",
      "language": "zh-TW",
      "is_mantra_repeat": false,
      "repeat_count": 1,
      "tags": ["philosophy"]
    }

Missing ``.json`` is fine — defaults are derived from the filename.

Categories
----------
Six fixed categories — UI groups presets by these:

- ``buddhist``     佛教
- ``taoist``       道家
- ``confucian``    儒家
- ``classical``    文學經典
- ``christian``    基督宗教
- ``user_custom``  自訂

Builtins always carry a fixed category (the 4 we ship are ``buddhist``).
User presets default to ``user_custom`` but can be reassigned via the JSON.

Legacy fallback
---------------
For backwards compatibility with Phase 5az v0.11.31, files placed
**directly** in ``~/.stroke-order/sutras/`` (no subdirectory) are still
recognised for the four canonical builtin keys. New installs should use
``builtin/``.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal, Optional


_ENV_DIR = "STROKE_ORDER_SUTRA_DIR"
_DEFAULT_DIR = Path.home() / ".stroke-order" / "sutras"

Category = Literal[
    "buddhist", "taoist", "confucian", "classical",
    "christian", "inspirational", "user_custom",
]

#: Display labels for each category — surfaced by the API for UI grouping.
CATEGORY_LABELS: dict[str, str] = {
    "buddhist":      "佛教",
    "taoist":        "道家",
    "confucian":     "儒家",
    "classical":     "文學經典",
    "christian":     "基督宗教",
    "inspirational": "勵志家訓",
    "user_custom":   "自訂",
}
CATEGORY_ORDER: list[str] = [
    "buddhist", "taoist", "confucian", "classical",
    "christian", "inspirational", "user_custom",
]


def default_sutra_dir() -> Path:
    env = os.environ.get(_ENV_DIR)
    return Path(env).expanduser() if env else _DEFAULT_DIR


def builtin_dir() -> Path:
    return default_sutra_dir() / "builtin"


def user_dir() -> Path:
    return default_sutra_dir() / "user"


@dataclass(frozen=True)
class ClosingPageSpec:
    """5bg: 結語頁設定（取代既有「迴向頁」概念，通用於 7 個分類）.

    None 在 SutraInfo.closing 表示「使用該分類的預設模板」(see CLOSING_TEMPLATES).
    """
    title: str = ""              # 結語頁大標（譬如「迴向文」「跋」「自勉」）
    verse: str = ""              # 主文（淡灰描紅）
    blank1_label: str = ""       # 填空 1 提示（譬如「弟子」「在主裡」）
    blank2_label: str = ""       # 填空 2 提示（譬如「迴向」「願主恩臨」）


@dataclass(frozen=True)
class SutraInfo:
    key: str
    title: str
    subtitle: str
    filename: str
    category: str
    source: str                      # 5bd: now used as "版本" (edition/source)
    description: str
    expected_chars: int = 0          # 0 = no expectation (user-uploaded)
    language: str = "zh-TW"
    is_mantra_repeat: bool = False
    repeat_count: int = 1
    is_builtin: bool = True
    tags: tuple[str, ...] = ()       # frozen-friendly tuple, not list
    # ---- Phase 5bd: scholarly metadata --------------------------------
    author: str = ""                 # 撰者
    editor: str = ""                 # 編者（如朱熹編四書）
    notes: str = ""                  # 校記 / 編輯筆記（多行自由文字）
    source_url: str = ""             # 出處網址（CBETA / ctext / wikisource…）
    # ---- Phase 5bg: per-sutra closing override ------------------------
    closing: Optional[ClosingPageSpec] = None  # None → category template


# ---------------------------------------------------------------------------
# Phase 5bg: 7 套結語頁預設模板（每分類一套）
# ---------------------------------------------------------------------------

CLOSING_TEMPLATES: dict[str, ClosingPageSpec] = {
    "buddhist": ClosingPageSpec(
        title="迴向文",
        verse="願以此功德，莊嚴佛淨土，上報四重恩，下濟三途苦",
        blank1_label="弟子",
        blank2_label="迴向",
    ),
    "taoist": ClosingPageSpec(
        title="祈願",
        verse="以此清靜心，願法界蒼生同登道岸",
        blank1_label="信士",
        blank2_label="願力歸於",
    ),
    "confucian": ClosingPageSpec(
        title="誌銘",
        verse="敬書此篇，以資修身齊家",
        blank1_label="後學",
        blank2_label="謹誌",
    ),
    "classical": ClosingPageSpec(
        title="跋",
        verse="敬筆抄錄，以彰先賢之文",
        blank1_label="抄錄者",
        blank2_label="敬識",
    ),
    "christian": ClosingPageSpec(
        title="榮耀歸主",
        verse="凡我所作，皆為主名；願主恩典常與我同在",
        blank1_label="在主裡",
        blank2_label="願主恩臨",
    ),
    "inspirational": ClosingPageSpec(
        title="自勉",
        verse="願以此銘記於心，常自警惕",
        blank1_label="抄錄者",
        blank2_label="勉之",
    ),
    "user_custom": ClosingPageSpec(
        title="結語",
        verse="",
        blank1_label="",
        blank2_label="",
    ),
}


def get_closing(key: str) -> ClosingPageSpec:
    """Return the effective closing-page spec for ``key``.

    Resolution order:
    1. ``info.closing`` if explicitly set (per-sutra override)
    2. ``CLOSING_TEMPLATES[info.category]`` (category default)
    3. Empty spec
    """
    info = get_sutra_info(key)
    if info is None:
        return ClosingPageSpec()
    if info.closing is not None:
        return info.closing
    return CLOSING_TEMPLATES.get(info.category, ClosingPageSpec())


def _closing_from_dict(d: Optional[dict]) -> Optional[ClosingPageSpec]:
    """Parse a closing dict from JSON metadata. ``None`` if missing/invalid."""
    if not d or not isinstance(d, dict):
        return None
    return ClosingPageSpec(
        title=str(d.get("title", "")),
        verse=str(d.get("verse", "")),
        blank1_label=str(d.get("blank1_label", "")),
        blank2_label=str(d.get("blank2_label", "")),
    )


def _closing_to_dict(c: Optional[ClosingPageSpec]) -> Optional[dict]:
    if c is None:
        return None
    return {
        "title": c.title,
        "verse": c.verse,
        "blank1_label": c.blank1_label,
        "blank2_label": c.blank2_label,
    }


# ---------------------------------------------------------------------------
# Builtin registry — the four canonical Phase-5az presets
# ---------------------------------------------------------------------------


BUILTIN_SUTRAS: dict[str, SutraInfo] = {
    "heart_sutra": SutraInfo(
        key="heart_sutra",
        title="般若波羅蜜多心經",
        subtitle="手抄本",
        filename="heart_sutra.txt",
        category="buddhist",
        author="玄奘 譯（唐）",
        editor="",
        source="大正藏 T0251 通行本",
        source_url="https://cbetaonline.dila.edu.tw/zh/T0251",
        description="佛教最短的經典之一，濃縮般若智慧精華。"
                    "適合初學者入門。",
        expected_chars=260,
    ),
    "heart_sutra_kumarajiva": SutraInfo(
        key="heart_sutra_kumarajiva",
        title="摩訶般若波羅蜜大明咒經",
        subtitle="手抄本（鳩摩羅什譯）",
        filename="heart_sutra_kumarajiva.txt",
        category="buddhist",
        author="鳩摩羅什 譯（姚秦）",
        editor="",
        source="大正藏 T0250 鳩摩羅什譯本",
        source_url="https://cbetaonline.dila.edu.tw/zh/T0250",
        description="《心經》最早譯本之一，與玄奘譯版並行流通；"
                    "用語多保留原始譯經風格，可與玄奘版對照閱讀。",
        expected_chars=290,
    ),
    "diamond_sutra": SutraInfo(
        key="diamond_sutra",
        title="金剛般若波羅蜜經",
        subtitle="手抄本",
        filename="diamond_sutra.txt",
        category="buddhist",
        author="鳩摩羅什 譯（姚秦）",
        editor="",
        source="大正藏 T0235 鳩摩羅什譯本",
        source_url="https://cbetaonline.dila.edu.tw/zh/T0235",
        description="大乘佛教般若部重要經典，"
                    "闡述「應無所住而生其心」。適合進階修行者。",
        expected_chars=5175,
    ),
    "great_compassion": SutraInfo(
        key="great_compassion",
        title="大悲咒",
        subtitle="手抄本",
        filename="great_compassion.txt",
        category="buddhist",
        author="伽梵達摩 譯（唐）",
        editor="",
        source="千手千眼觀世音菩薩廣大圓滿無礙大悲心陀羅尼經",
        source_url="https://cbetaonline.dila.edu.tw/zh/T1060",
        description="觀世音菩薩根本咒，"
                    "千手千眼觀世音菩薩廣大圓滿無礙大悲心陀羅尼。",
        expected_chars=415,
    ),
    "manjushri_mantra": SutraInfo(
        key="manjushri_mantra",
        title="文殊菩薩心咒",
        subtitle="手抄本（重複 108 遍）",
        filename="manjushri_mantra.txt",
        category="buddhist",
        author="文殊菩薩根本心咒",
        editor="",
        source="藏傳/漢傳通行版",
        source_url="",
        description="持誦可增長智慧、開啟辯才。"
                    "本手抄本逐行重複抄寫共 108 遍。",
        expected_chars=7,
        is_mantra_repeat=True,
        repeat_count=108,
    ),

    # --- 佛教（Phase 5bg 補加 3 部） -----------------------------------
    "amitabha_sutra": SutraInfo(
        key="amitabha_sutra",
        title="佛說阿彌陀經",
        subtitle="手抄本",
        filename="amitabha_sutra.txt",
        category="buddhist",
        author="鳩摩羅什 譯（姚秦）",
        editor="",
        source="大正藏 T0366 鳩摩羅什譯本",
        source_url="https://cbetaonline.dila.edu.tw/zh/T0366",
        description="淨土三經之一，描述西方極樂世界依正莊嚴，"
                    "勸人持名念佛求生淨土。",
        expected_chars=1858,
    ),
    "lotus_pumen": SutraInfo(
        key="lotus_pumen",
        title="妙法蓮華經・觀世音菩薩普門品",
        subtitle="手抄本（法華經第 25 品）",
        filename="lotus_pumen.txt",
        category="buddhist",
        author="鳩摩羅什 譯（姚秦）",
        editor="",
        source="大正藏 T0262 法華經第 25 品",
        source_url="https://cbetaonline.dila.edu.tw/zh/T0262",
        description="觀世音菩薩普門示現之經，"
                    "民間最廣泛流通的觀音經典，常單行流通稱「觀音經」。",
        expected_chars=3680,
    ),
    "pu_guang_ming": SutraInfo(
        key="pu_guang_ming",
        title="大乘離文字普光明藏經",
        subtitle="手抄本",
        filename="pu_guang_ming.txt",
        category="buddhist",
        author="地婆訶羅 譯（唐）",
        editor="",
        source="大正藏 T0830",
        source_url="https://cbetaonline.dila.edu.tw/zh/T0830",
        description="闡述「大乘離文字普光明藏」法門的般若類經典，"
                    "篇幅適中，適合誦持思惟。",
        expected_chars=1500,
    ),

    # --- 道家 (Phase 5bc) ----------------------------------------------
    "tao_te_ching": SutraInfo(
        key="tao_te_ching",
        title="道德經",
        subtitle="手抄本",
        filename="tao_te_ching.txt",
        category="taoist",
        author="老子（春秋）",
        editor="",
        source="王弼注本（傳世通行本）",
        source_url="https://ctext.org/dao-de-jing/zh",
        description="道家根本經典，分上下兩篇 81 章，"
                    "闡述「道」與「德」的形上學與處世智慧。",
        expected_chars=5400,
    ),
    "qing_jing_jing": SutraInfo(
        key="qing_jing_jing",
        title="太上老君說常清靜經",
        subtitle="手抄本",
        filename="qing_jing_jing.txt",
        category="taoist",
        author="託名太上老君",
        editor="",
        source="正統道藏本",
        source_url="https://zh.wikisource.org/zh-hant/太上老君說常清靜經",
        description="道教全真派早晚必誦的短篇經典，"
                    "教人收心遣慾、回歸清靜本性。",
        expected_chars=391,
    ),
    "gan_ying_pian": SutraInfo(
        key="gan_ying_pian",
        title="太上感應篇",
        subtitle="手抄本",
        filename="gan_ying_pian.txt",
        category="taoist",
        author="託名太上",
        editor="",
        source="正統道藏本",
        source_url="https://zh.wikisource.org/zh-hant/太上感應篇",
        description="勸善經典，闡述「禍福無門，惟人自召」的因果觀，"
                    "歷代廣為流傳。",
        expected_chars=1200,
    ),
    "yin_fu_jing": SutraInfo(
        key="yin_fu_jing",
        title="黃帝陰符經",
        subtitle="手抄本",
        filename="yin_fu_jing.txt",
        category="taoist",
        author="託名黃帝",
        editor="",
        source="正統道藏本",
        source_url="https://zh.wikisource.org/zh-hant/陰符經",
        description="道家簡短而富哲理的經典，"
                    "論天人關係與修身治國之道。",
        expected_chars=447,
    ),

    # --- 儒家 / 蒙學 (Phase 5bc) ---------------------------------------
    "san_zi_jing": SutraInfo(
        key="san_zi_jing",
        title="三字經",
        subtitle="手抄本",
        filename="san_zi_jing.txt",
        category="confucian",
        author="王應麟（宋）",
        editor="",
        source="通行本",
        source_url="https://zh.wikisource.org/zh-hant/三字經",
        description="中華蒙學經典，三字一句、隔句押韻，"
                    "涵蓋歷史、倫理、勸學等主題。",
        expected_chars=1140,
    ),
    "qian_zi_wen": SutraInfo(
        key="qian_zi_wen",
        title="千字文",
        subtitle="手抄本",
        filename="qian_zi_wen.txt",
        category="confucian",
        author="周興嗣（南朝梁）",
        editor="",
        source="通行本",
        source_url="https://zh.wikisource.org/zh-hant/千字文",
        description="用一千個不重複漢字寫成的四言韻文，"
                    "歷代習字必讀。",
        expected_chars=1000,
    ),
    "di_zi_gui": SutraInfo(
        key="di_zi_gui",
        title="弟子規",
        subtitle="手抄本",
        filename="di_zi_gui.txt",
        category="confucian",
        author="李毓秀（清）",
        editor="賈存仁（清）",
        source="通行本",
        source_url="https://zh.wikisource.org/zh-hant/弟子規",
        description="蒙學經典，依《論語・學而》「弟子入則孝」"
                    "為綱，列舉日常行為規範。",
        expected_chars=1080,
    ),
    "da_xue": SutraInfo(
        key="da_xue",
        title="大學",
        subtitle="手抄本",
        filename="da_xue.txt",
        category="confucian",
        author="曾子（傳）",
        editor="朱熹（南宋）",
        source="《禮記》篇章 / 朱熹列為四書之首",
        source_url="https://ctext.org/liji/da-xue/zh",
        description="四書之一，提出格物、致知、誠意、正心、"
                    "修身、齊家、治國、平天下八條目。",
        expected_chars=1753,
    ),
    "zhong_yong": SutraInfo(
        key="zhong_yong",
        title="中庸",
        subtitle="手抄本",
        filename="zhong_yong.txt",
        category="confucian",
        author="子思（傳）",
        editor="朱熹（南宋）",
        source="《禮記》篇章",
        source_url="https://ctext.org/liji/zhong-yong/zh",
        description="四書之一，闡述「中和」之道與「誠」的哲學，"
                    "為儒家心性修養經典。",
        expected_chars=3568,
    ),
    "lun_yu_xue_er": SutraInfo(
        key="lun_yu_xue_er",
        title="論語・學而篇",
        subtitle="手抄本（單篇）",
        filename="lun_yu_xue_er.txt",
        category="confucian",
        author="孔子弟子記述",
        editor="",
        source="《論語》第一篇",
        source_url="https://ctext.org/analects/xue-er/zh",
        description="《論語》第一篇，"
                    "「學而時習之」名句出處，共 16 章。",
        expected_chars=497,
    ),
    "xiao_jing": SutraInfo(
        key="xiao_jing",
        title="孝經",
        subtitle="手抄本",
        filename="xiao_jing.txt",
        category="confucian",
        author="孔子弟子記述（傳）",
        editor="",
        source="今文孝經 18 章本",
        source_url="https://ctext.org/xiao-jing/zh",
        description="專論孝道，分 18 章，"
                    "為歷代蒙學與科舉必讀。",
        expected_chars=1799,
    ),

    # --- 文學經典 (Phase 5bf) ------------------------------------------
    "man_jiang_hong": SutraInfo(
        key="man_jiang_hong",
        title="滿江紅・怒髮衝冠",
        subtitle="手抄本",
        filename="man_jiang_hong.txt",
        category="classical",
        author="岳飛（南宋）",
        editor="",
        source="《全宋詞》收錄",
        source_url="https://zh.wikisource.org/zh-hant/滿江紅_(岳飛)",
        description="豪放派代表詞，闕表愛國情懷，"
                    "「精忠報國」精神象徵。",
        expected_chars=95,
    ),
    "chibi_fu": SutraInfo(
        key="chibi_fu",
        title="前赤壁賦",
        subtitle="手抄本",
        filename="chibi_fu.txt",
        category="classical",
        author="蘇軾（北宋）",
        editor="",
        source="《東坡七集》",
        source_url="https://zh.wikisource.org/zh-hant/前赤壁賦",
        description="蘇軾貶謫黃州時所作，宋代散文巔峰之作，"
                    "闡述「自其變者觀之...自其不變者觀之」的人生哲學。",
        expected_chars=537,
    ),
    "chibi_fu_2": SutraInfo(
        key="chibi_fu_2",
        title="後赤壁賦",
        subtitle="手抄本",
        filename="chibi_fu_2.txt",
        category="classical",
        author="蘇軾（北宋）",
        editor="",
        source="《東坡七集》",
        source_url="https://zh.wikisource.org/zh-hant/後赤壁賦",
        description="《前赤壁賦》姊妹篇，遊覽赤壁山中，"
                    "與道士夢境之記述。",
        expected_chars=357,
    ),
    "shi_shuo": SutraInfo(
        key="shi_shuo",
        title="師說",
        subtitle="手抄本",
        filename="shi_shuo.txt",
        category="classical",
        author="韓愈（唐）",
        editor="",
        source="《昌黎先生集》",
        source_url="https://zh.wikisource.org/zh-hant/師說",
        description="論述老師重要性的散文，唐代古文運動代表作，"
                    "「道之所存，師之所存」名句出處。",
        expected_chars=460,
    ),
    "yueyang_lou_ji": SutraInfo(
        key="yueyang_lou_ji",
        title="岳陽樓記",
        subtitle="手抄本",
        filename="yueyang_lou_ji.txt",
        category="classical",
        author="范仲淹（北宋）",
        editor="",
        source="《范文正公集》",
        source_url="https://zh.wikisource.org/zh-hant/岳陽樓記",
        description="千古名篇，"
                    "「先天下之憂而憂，後天下之樂而樂」名句出處。",
        expected_chars=360,
    ),
    "taohua_yuan_ji": SutraInfo(
        key="taohua_yuan_ji",
        title="桃花源記",
        subtitle="手抄本",
        filename="taohua_yuan_ji.txt",
        category="classical",
        author="陶淵明（東晉）",
        editor="",
        source="《陶淵明集》",
        source_url="https://zh.wikisource.org/zh-hant/桃花源記",
        description="描繪世外桃源理想國度，"
                    "中華文化「桃花源」典故出處。",
        expected_chars=320,
    ),
    "chu_shi_biao": SutraInfo(
        key="chu_shi_biao",
        title="出師表",
        subtitle="手抄本",
        filename="chu_shi_biao.txt",
        category="classical",
        author="諸葛亮（蜀漢）",
        editor="",
        source="《三國志・諸葛亮傳》",
        source_url="https://zh.wikisource.org/zh-hant/出師表",
        description="諸葛亮北伐前上疏後主劉禪的奏章，"
                    "「鞠躬盡瘁，死而後已」精神代表作。",
        expected_chars=740,
    ),
    "lan_ting_xu": SutraInfo(
        key="lan_ting_xu",
        title="蘭亭集序",
        subtitle="手抄本",
        filename="lan_ting_xu.txt",
        category="classical",
        author="王羲之（東晉）",
        editor="",
        source="原跡為書聖代表作",
        source_url="https://zh.wikisource.org/zh-hant/蘭亭集序",
        description="王羲之書法名作，描寫蘭亭雅集，"
                    "「天下第一行書」。",
        expected_chars=324,
    ),
    "teng_wang_ge_xu": SutraInfo(
        key="teng_wang_ge_xu",
        title="滕王閣序",
        subtitle="手抄本",
        filename="teng_wang_ge_xu.txt",
        category="classical",
        author="王勃（唐）",
        editor="",
        source="《王子安集》",
        source_url="https://zh.wikisource.org/zh-hant/滕王閣序",
        description="駢文絕唱，"
                    "「落霞與孤鶩齊飛，秋水共長天一色」千古名句。",
        expected_chars=770,
    ),
    "nian_nu_jiao_chibi": SutraInfo(
        key="nian_nu_jiao_chibi",
        title="念奴嬌・赤壁懷古",
        subtitle="手抄本",
        filename="nian_nu_jiao_chibi.txt",
        category="classical",
        author="蘇軾（北宋）",
        editor="",
        source="《東坡樂府》",
        source_url="https://zh.wikisource.org/zh-hant/念奴嬌・赤壁懷古",
        description="豪放詞代表作，憑弔赤壁古戰場，懷古抒情。",
        expected_chars=100,
    ),
    "chang_hen_ge": SutraInfo(
        key="chang_hen_ge",
        title="長恨歌",
        subtitle="手抄本",
        filename="chang_hen_ge.txt",
        category="classical",
        author="白居易（唐）",
        editor="",
        source="《白氏長慶集》",
        source_url="https://zh.wikisource.org/zh-hant/長恨歌",
        description="描寫唐玄宗與楊貴妃愛情悲劇的長篇敘事詩。",
        expected_chars=840,
    ),
    "pi_pa_xing": SutraInfo(
        key="pi_pa_xing",
        title="琵琶行",
        subtitle="手抄本",
        filename="pi_pa_xing.txt",
        category="classical",
        author="白居易（唐）",
        editor="",
        source="《白氏長慶集》",
        source_url="https://zh.wikisource.org/zh-hant/琵琶行",
        description="敘事長詩，以琵琶女遭遇抒發詩人遭貶謫之情，"
                    "「同是天涯淪落人」名句出處。",
        expected_chars=622,
    ),
    "lou_shi_ming": SutraInfo(
        key="lou_shi_ming",
        title="陋室銘",
        subtitle="手抄本",
        filename="lou_shi_ming.txt",
        category="classical",
        author="劉禹錫（唐）",
        editor="",
        source="《劉夢得文集》",
        source_url="https://zh.wikisource.org/zh-hant/陋室銘",
        description="超短篇銘文（81 字），表達安貧樂道情懷，"
                    "「斯是陋室，惟吾德馨」名句出處。",
        expected_chars=81,
    ),
    "ai_lian_shuo": SutraInfo(
        key="ai_lian_shuo",
        title="愛蓮說",
        subtitle="手抄本",
        filename="ai_lian_shuo.txt",
        category="classical",
        author="周敦頤（北宋）",
        editor="",
        source="《周元公集》",
        source_url="https://zh.wikisource.org/zh-hant/愛蓮說",
        description="以蓮花象徵君子品德，"
                    "「出淤泥而不染」名句出處。",
        expected_chars=119,
    ),

    # --- 基督宗教 (Phase 5bf) ------------------------------------------
    "lord_prayer": SutraInfo(
        key="lord_prayer",
        title="主禱文",
        subtitle="手抄本",
        filename="lord_prayer.txt",
        category="christian",
        author="耶穌教導",
        editor="",
        source="新約聖經・馬太福音 6:9-13",
        source_url="https://zh.wikipedia.org/wiki/主禱文",
        description="基督宗教最重要的禱文，由耶穌親自教導門徒。"
                    "天主教稱「天主經」。",
        expected_chars=70,
    ),
    "hail_mary": SutraInfo(
        key="hail_mary",
        title="聖母經",
        subtitle="手抄本",
        filename="hail_mary.txt",
        category="christian",
        author="天主教傳統禱詞",
        editor="",
        source="路加福音 1:28, 1:42 加教會傳統補充",
        source_url="https://zh.wikipedia.org/wiki/聖母經",
        description="天主教重要禱文（萬福瑪利亞），"
                    "玫瑰經主要組成部分。",
        expected_chars=55,
    ),
    "apostles_creed": SutraInfo(
        key="apostles_creed",
        title="使徒信經",
        subtitle="手抄本",
        filename="apostles_creed.txt",
        category="christian",
        author="早期基督教會",
        editor="",
        source="2 世紀羅馬教會發展定型",
        source_url="https://zh.wikipedia.org/wiki/使徒信經",
        description="基督宗教最古老的信仰宣告之一，"
                    "包含對聖父、聖子、聖靈的信仰陳述。",
        expected_chars=110,
    ),
    "nicene_creed": SutraInfo(
        key="nicene_creed",
        title="尼西亞信經",
        subtitle="手抄本",
        filename="nicene_creed.txt",
        category="christian",
        author="第一次尼西亞公會議",
        editor="",
        source="公元 325 年尼西亞會議制定，"
               "381 年君士坦丁堡會議補充",
        source_url="https://zh.wikipedia.org/wiki/尼西亞信經",
        description="基督教三大信經之一，"
                    "最廣泛被各教派接受的信仰宣告。",
        expected_chars=200,
    ),
    "psalm_23": SutraInfo(
        key="psalm_23",
        title="詩篇 23 篇",
        subtitle="手抄本（耶和華是我的牧者）",
        filename="psalm_23.txt",
        category="christian",
        author="大衛王（傳）",
        editor="",
        source="舊約聖經・詩篇 23",
        source_url="https://zh.wikisource.org/zh-hant/聖經（和合本）/詩篇/第23篇",
        description="最廣為人知的詩篇，"
                    "「耶和華是我的牧者，我必不至缺乏」名句出處。",
        expected_chars=110,
    ),
    "francis_peace_prayer": SutraInfo(
        key="francis_peace_prayer",
        title="聖方濟和平禱文",
        subtitle="手抄本",
        filename="francis_peace_prayer.txt",
        category="christian",
        author="託名亞西西的聖方濟",
        editor="",
        source="20 世紀初出現的禱文",
        source_url="https://zh.wikipedia.org/wiki/和平祈禱文",
        description="「使我作袮和平之子」開頭的著名禱文，"
                    "雖託名聖方濟但實為近代作品。",
        expected_chars=110,
    ),
    "beatitudes": SutraInfo(
        key="beatitudes",
        title="登山寶訓・八福",
        subtitle="手抄本",
        filename="beatitudes.txt",
        category="christian",
        author="耶穌教導",
        editor="",
        source="新約聖經・馬太福音 5:3-12",
        source_url="https://zh.wikipedia.org/wiki/八福",
        description="耶穌登山寶訓開篇，宣告八種「有福之人」。",
        expected_chars=120,
    ),
    "love_chapter": SutraInfo(
        key="love_chapter",
        title="愛的真諦",
        subtitle="手抄本（哥林多前書 13 章）",
        filename="love_chapter.txt",
        category="christian",
        author="使徒保羅",
        editor="",
        source="新約聖經・哥林多前書 13 章",
        source_url="https://zh.wikisource.org/zh-hant/聖經（和合本）/哥林多前書/第13章",
        description="保羅論愛的著名章節，"
                    "「愛是恆久忍耐又有恩慈」基督徒婚禮常用。",
        expected_chars=250,
    ),

    # --- 勵志家訓 (Phase 5bf) ------------------------------------------
    "macarthur_prayer": SutraInfo(
        key="macarthur_prayer",
        title="麥克阿瑟為子祈禱文",
        subtitle="手抄本",
        filename="macarthur_prayer.txt",
        category="inspirational",
        author="麥克阿瑟（Douglas MacArthur，1880-1964）",
        editor="",
        source="原文 1942 年寫於菲律賓巴丹半島",
        source_url="https://zh.wikipedia.org/wiki/道格拉斯·麥克阿瑟",
        description="美國二戰將領麥克阿瑟為子寫的祈禱文，"
                    "中譯本廣為流傳，常被選入勵志教材。",
        expected_chars=350,
    ),
    "jiezi_shu": SutraInfo(
        key="jiezi_shu",
        title="誡子書",
        subtitle="手抄本",
        filename="jiezi_shu.txt",
        category="inspirational",
        author="諸葛亮（蜀漢）",
        editor="",
        source="《諸葛亮集》",
        source_url="https://zh.wikisource.org/zh-hant/誡子書",
        description="諸葛亮寫給兒子諸葛瞻的家書，"
                    "「靜以修身，儉以養德」"
                    "「非淡泊無以明志，非寧靜無以致遠」名句出處。",
        expected_chars=86,
    ),
    "zhu_zi_jia_xun": SutraInfo(
        key="zhu_zi_jia_xun",
        title="朱子治家格言",
        subtitle="手抄本",
        filename="zhu_zi_jia_xun.txt",
        category="inspirational",
        author="朱柏廬（明末清初，1627-1698）",
        editor="",
        source="《朱柏廬治家格言》",
        source_url="https://zh.wikisource.org/zh-hant/朱子家訓",
        description="清代蒙學經典，"
                    "「黎明即起，灑掃庭除」"
                    "「一粥一飯當思來處不易」名句出處。",
        expected_chars=506,
    ),
    "yan_shi_jia_xun_xulun": SutraInfo(
        key="yan_shi_jia_xun_xulun",
        title="顏氏家訓・序致",
        subtitle="手抄本（節錄首篇）",
        filename="yan_shi_jia_xun_xulun.txt",
        category="inspirational",
        author="顏之推（北齊，531-595）",
        editor="",
        source="《顏氏家訓》第一篇",
        source_url="https://ctext.org/yan-shi-jia-xun/xu-zhi/zh",
        description="現存最早的家訓專著首篇，"
                    "顏之推闡述寫作此書動機。"
                    "全書共 20 篇，此為節錄首篇。",
        expected_chars=400,
    ),
    "lin_ze_xu_shi_wu_yi": SutraInfo(
        key="lin_ze_xu_shi_wu_yi",
        title="林則徐十無益格言",
        subtitle="手抄本",
        filename="lin_ze_xu_shi_wu_yi.txt",
        category="inspirational",
        author="林則徐（清，1785-1850）",
        editor="",
        source="林則徐 1839 年自題於家中",
        source_url="https://zh.wikipedia.org/wiki/林則徐",
        description="林則徐人生十無益格言，"
                    "「存心不善，風水無益」開頭，警示世人修身。",
        expected_chars=80,
    ),
}

# Back-compat alias for callers that imported ``SUTRAS`` directly.
SUTRAS = BUILTIN_SUTRAS


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------


_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9_一-鿿\-]")


def sanitize_key(name: str, max_len: int = 50) -> str:
    """Return a filesystem-safe key derived from ``name``.

    Removes characters outside ``[A-Za-z0-9_\\u4e00-\\u9fff-]``, trims to
    ``max_len``. Empty result becomes ``"untitled"``.
    """
    name = (name or "").strip()
    cleaned = _SAFE_KEY_RE.sub("_", name)[:max_len].strip("_")
    return cleaned or "untitled"


def _strip_text(raw: str) -> str:
    """Remove all whitespace (incl. newlines) but keep punctuation."""
    return "".join(ch for ch in raw if not ch.isspace())


def _resolve_builtin_path(info: SutraInfo) -> Optional[Path]:
    """Locate a builtin's text file, supporting the legacy flat layout.

    Search order:
    1. ``<sutras>/builtin/<filename>``  (preferred)
    2. ``<sutras>/<filename>``          (legacy flat — pre-5bb)
    """
    nested = builtin_dir() / info.filename
    if nested.exists():
        return nested
    flat = default_sutra_dir() / info.filename
    if flat.exists():
        return flat
    return None


def _resolve_user_path(key: str) -> Optional[Path]:
    p = user_dir() / f"{key}.txt"
    return p if p.exists() else None


def _user_meta_path(key: str) -> Path:
    return user_dir() / f"{key}.json"


def _builtin_meta_path(key: str) -> Path:
    """5be: per-builtin metadata override. Sibling to the .txt file."""
    info = BUILTIN_SUTRAS.get(key)
    stem = info.filename.removesuffix(".txt") if info else key
    return builtin_dir() / f"{stem}.json"


# Structural fields that are locked even for builtins (changing them would
# break key→file mapping or the loader's classification logic).
_BUILTIN_LOCKED_FIELDS: tuple[str, ...] = (
    "key", "filename", "is_builtin",
    "category", "is_mantra_repeat", "repeat_count",
)


def _read_builtin_override(key: str) -> dict:
    """Read the per-builtin metadata override JSON; missing/invalid → {}."""
    p = _builtin_meta_path(key)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _apply_builtin_override(info: SutraInfo) -> SutraInfo:
    """Return a new SutraInfo with override JSON merged on top of hard-coded
    defaults. Locked fields are always taken from the hard-coded default."""
    if not info.is_builtin:
        return info
    override = _read_builtin_override(info.key)
    if not override:
        return info
    # Build replacement dict from current info, then layer non-locked
    # override fields on top.
    from dataclasses import replace
    safe: dict = {}
    for fld in (
        "title", "subtitle", "source", "description", "language",
        "tags", "author", "editor", "notes", "source_url",
    ):
        if fld in override:
            val = override[fld]
            if fld == "tags":
                val = tuple(str(t) for t in (val or []))
            else:
                val = str(val) if val is not None else ""
            safe[fld] = val
    # 5bg: closing override (dict → ClosingPageSpec, or null → keep default)
    if "closing" in override:
        c = _closing_from_dict(override["closing"])
        # null in JSON means "remove the override and fall back to template"
        safe["closing"] = c
    if not safe:
        return info
    return replace(info, **safe)


# ---------------------------------------------------------------------------
# Loader API — works for builtins and user-uploaded keys uniformly
# ---------------------------------------------------------------------------


def is_loaded(key: str) -> bool:
    info = get_sutra_info(key)
    if info is None:
        return False
    if info.is_builtin:
        path = _resolve_builtin_path(info)
    else:
        path = _resolve_user_path(key)
    return bool(path and path.stat().st_size > 0)


def load_text(key: str) -> Optional[str]:
    """Return cleaned + (optionally) repeated text for ``key``."""
    info = get_sutra_info(key)
    if info is None:
        return None
    if info.is_builtin:
        path = _resolve_builtin_path(info)
    else:
        path = _resolve_user_path(key)
    if path is None or not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    text = _strip_text(raw)
    if not text:
        return None
    if info.is_mantra_repeat and info.repeat_count > 1:
        text = text * info.repeat_count
    return unicodedata.normalize("NFC", text)


def actual_char_count(key: str) -> int:
    text = load_text(key)
    return len(text) if text else 0


# ---------------------------------------------------------------------------
# User-defined preset enumeration + metadata IO
# ---------------------------------------------------------------------------


def list_user_keys() -> list[str]:
    """Return the keys (filenames sans .txt) of user-uploaded sutras."""
    d = user_dir()
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.txt"))


def _read_user_meta(key: str) -> dict:
    """Best-effort metadata read; missing/invalid → empty dict."""
    p = _user_meta_path(key)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _user_info_from_disk(key: str) -> Optional[SutraInfo]:
    """Build a SutraInfo for a user file, applying its sibling JSON."""
    if _resolve_user_path(key) is None:
        return None
    meta = _read_user_meta(key)
    title = meta.get("title") or key
    cat = meta.get("category", "user_custom")
    if cat not in CATEGORY_ORDER:
        cat = "user_custom"
    tags_field = meta.get("tags") or []
    if not isinstance(tags_field, (list, tuple)):
        tags_field = []
    return SutraInfo(
        key=key,
        title=str(title),
        subtitle=str(meta.get("subtitle", "手抄本")),
        filename=f"{key}.txt",
        category=cat,
        source=str(meta.get("source", "")),
        description=str(meta.get("description", "")),
        expected_chars=int(meta.get("expected_chars", 0) or 0),
        language=str(meta.get("language", "zh-TW")),
        is_mantra_repeat=bool(meta.get("is_mantra_repeat", False)),
        repeat_count=int(meta.get("repeat_count", 1) or 1),
        is_builtin=False,
        tags=tuple(str(t) for t in tags_field),
        # 5bd: scholarly metadata
        author=str(meta.get("author", "")),
        editor=str(meta.get("editor", "")),
        notes=str(meta.get("notes", "")),
        source_url=str(meta.get("source_url", "")),
        # 5bg: closing override
        closing=_closing_from_dict(meta.get("closing")),
    )


def get_sutra_info(key: str) -> Optional[SutraInfo]:
    """Return SutraInfo for any preset key (builtin or user).

    For builtins, hard-coded defaults are merged with optional
    ``builtin/{key}.json`` override (5be).
    """
    if key in BUILTIN_SUTRAS:
        return _apply_builtin_override(BUILTIN_SUTRAS[key])
    return _user_info_from_disk(key)


def all_sutra_infos() -> list[SutraInfo]:
    """Return [builtin..., user...] in stable order."""
    out: list[SutraInfo] = [
        _apply_builtin_override(info) for info in BUILTIN_SUTRAS.values()
    ]
    for k in list_user_keys():
        info = _user_info_from_disk(k)
        if info is not None:
            out.append(info)
    return out


# ---------------------------------------------------------------------------
# Builtin write API (5be) — write override + raw text
# ---------------------------------------------------------------------------


def update_builtin_meta(key: str, updates: dict) -> bool:
    """Persist metadata override for a builtin preset.

    Locked fields (see ``_BUILTIN_LOCKED_FIELDS``) are silently dropped.
    Returns True iff the key is a known builtin.
    """
    info = BUILTIN_SUTRAS.get(key)
    if info is None:
        return False
    builtin_dir().mkdir(parents=True, exist_ok=True)
    existing = _read_builtin_override(key)
    safe_updates = {
        k: v for k, v in updates.items()
        if k not in _BUILTIN_LOCKED_FIELDS
    }
    merged = {**existing, **safe_updates}
    _builtin_meta_path(key).write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return True


def write_builtin_text(key: str, text: str) -> bool:
    """Overwrite ``builtin/<filename>`` with new content. Returns True iff
    the key is a known builtin."""
    info = BUILTIN_SUTRAS.get(key)
    if info is None:
        return False
    text = (text or "").strip()
    if not text:
        return False
    builtin_dir().mkdir(parents=True, exist_ok=True)
    (builtin_dir() / info.filename).write_text(text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Snapshot helpers — used by the API
# ---------------------------------------------------------------------------


def _info_to_dict(info: SutraInfo) -> dict:
    """Serialisable snapshot of a SutraInfo + load status."""
    ready = is_loaded(info.key)
    if info.is_builtin:
        path = _resolve_builtin_path(info)
        # Fall back to the canonical builtin path even if file missing,
        # so the UI can show users where to put it.
        full = str(path) if path else str(builtin_dir() / info.filename)
    else:
        full = str(user_dir() / info.filename)
    # 5bg: include resolved closing (override > category template > empty)
    effective_closing = (
        info.closing if info.closing is not None
        else CLOSING_TEMPLATES.get(info.category, ClosingPageSpec())
    )
    return {
        "key": info.key,
        "title": info.title,
        "subtitle": info.subtitle,
        "filename": info.filename,
        "category": info.category,
        "category_label": CATEGORY_LABELS.get(info.category, info.category),
        "source": info.source,
        "description": info.description,
        "expected_chars": info.expected_chars,
        "language": info.language,
        "is_mantra_repeat": info.is_mantra_repeat,
        "repeat_count": info.repeat_count,
        "is_builtin": info.is_builtin,
        "tags": list(info.tags),
        # 5bd: scholarly metadata
        "author": info.author,
        "editor": info.editor,
        "notes": info.notes,
        "source_url": info.source_url,
        # 5bg: closing — both raw override and effective (resolved) values
        "closing_override": _closing_to_dict(info.closing),
        "closing_effective": _closing_to_dict(effective_closing),
        "ready": ready,
        "actual_chars": actual_char_count(info.key) if ready else 0,
        "full_path": full,
    }


def available_presets() -> list[dict]:
    """Flat snapshot of all presets (builtin + user). UI uses this when
    grouping isn't needed."""
    return [_info_to_dict(info) for info in all_sutra_infos()]


def grouped_presets() -> list[dict]:
    """Snapshot grouped by category — drives the UI optgroup display."""
    flat = available_presets()
    by_cat: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
    for p in flat:
        by_cat.setdefault(p["category"], []).append(p)
    out: list[dict] = []
    for cat in CATEGORY_ORDER:
        out.append({
            "key": cat,
            "label": CATEGORY_LABELS[cat],
            "presets": by_cat.get(cat, []),
        })
    return out


# ---------------------------------------------------------------------------
# User-upload write API
# ---------------------------------------------------------------------------


_DEFAULT_USER_META = {
    "title": "",
    "subtitle": "手抄本",
    "category": "user_custom",
    "source": "",
    "description": "",
    "language": "zh-TW",
    "is_mantra_repeat": False,
    "repeat_count": 1,
    "tags": [],
    # 5bd: scholarly metadata
    "author": "",
    "editor": "",
    "notes": "",
    "source_url": "",
    # 5bg: closing (None means "use category template")
    "closing": None,
}


def _next_unique_key(stem: str) -> str:
    """If <stem>.txt exists, return stem_2 / stem_3 / ... until free."""
    if not (user_dir() / f"{stem}.txt").exists():
        return stem
    i = 2
    while (user_dir() / f"{stem}_{i}.txt").exists():
        i += 1
    return f"{stem}_{i}"


def save_user_preset(
    *,
    desired_key: str,
    text: str,
    title: str = "",
    subtitle: str = "手抄本",
    category: str = "user_custom",
    source: str = "",
    description: str = "",
    language: str = "zh-TW",
    is_mantra_repeat: bool = False,
    repeat_count: int = 1,
    tags: Optional[Iterable[str]] = None,
    # 5bd: scholarly metadata
    author: str = "",
    editor: str = "",
    notes: str = "",
    source_url: str = "",
    # 5bg: closing override (None → use category template)
    closing: Optional[dict] = None,
) -> str:
    """Persist a new user preset; returns the actual key used (may differ
    from ``desired_key`` if a collision was avoided).

    Raises ``ValueError`` if ``text`` is empty or ``category`` is unknown.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("text is empty")
    if category not in CATEGORY_ORDER:
        raise ValueError(f"unknown category: {category!r}")
    user_dir().mkdir(parents=True, exist_ok=True)
    base = sanitize_key(desired_key) or sanitize_key(title) or "untitled"
    key = _next_unique_key(base)
    (user_dir() / f"{key}.txt").write_text(text, encoding="utf-8")
    meta = dict(_DEFAULT_USER_META)
    meta.update({
        "title": title or key,
        "subtitle": subtitle,
        "category": category,
        "source": source,
        "description": description,
        "language": language,
        "is_mantra_repeat": bool(is_mantra_repeat),
        "repeat_count": int(repeat_count),
        "tags": list(tags or []),
        "author": author,
        "editor": editor,
        "notes": notes,
        "source_url": source_url,
        # 5bg: closing override (dict or None)
        "closing": closing if isinstance(closing, dict) else None,
    })
    (user_dir() / f"{key}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return key


def update_user_meta(key: str, updates: dict) -> bool:
    """Patch metadata for an existing user preset (text not touched).
    Returns True if applied, False if the preset doesn't exist."""
    if _resolve_user_path(key) is None:
        return False
    meta = _read_user_meta(key)
    if not meta:
        meta = dict(_DEFAULT_USER_META)
    # Only allow known fields through; ignore the rest silently.
    for field_name in (
        "title", "subtitle", "category", "source", "description",
        "language", "is_mantra_repeat", "repeat_count", "tags",
        # 5bd: scholarly metadata
        "author", "editor", "notes", "source_url",
        # 5bg: closing override
        "closing",
    ):
        if field_name in updates:
            meta[field_name] = updates[field_name]
    if meta.get("category") not in CATEGORY_ORDER:
        meta["category"] = "user_custom"
    (user_dir() / f"{key}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return True


def delete_user_preset(key: str) -> bool:
    """Delete a user preset (txt + json). Returns True if anything removed."""
    txt_p = user_dir() / f"{key}.txt"
    json_p = user_dir() / f"{key}.json"
    removed = False
    for p in (txt_p, json_p):
        if p.exists():
            p.unlink()
            removed = True
    return removed


def read_user_text(key: str) -> Optional[str]:
    """Raw user-file content (no whitespace stripping, no repeat) — for
    edit UIs that want to surface the file as the user uploaded it."""
    p = _resolve_user_path(key)
    if p is None:
        return None
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Char-stream helper
# ---------------------------------------------------------------------------


def text_to_chars(text: str) -> list[str]:
    return [c for c in text]


__all__ = [
    "Category", "CATEGORY_LABELS", "CATEGORY_ORDER",
    "SutraInfo", "BUILTIN_SUTRAS", "SUTRAS",
    "default_sutra_dir", "builtin_dir", "user_dir",
    "is_loaded", "load_text", "actual_char_count",
    "available_presets", "grouped_presets",
    "list_user_keys", "get_sutra_info",
    "save_user_preset", "update_user_meta", "delete_user_preset",
    "read_user_text", "sanitize_key", "text_to_chars",
    # 5be
    "update_builtin_meta", "write_builtin_text",
    # 5bg
    "ClosingPageSpec", "CLOSING_TEMPLATES", "get_closing",
]
