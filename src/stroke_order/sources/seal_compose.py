"""5fa：篆體缺字的部件合成（rule-based 推測，誠實標示）。

崇羲篆體收錄《說文》＋教育部常用字——「罣」「耨」與元素週期表的
現代造字常缺。但這些字結構規律（罣＝网＋圭、耨＝耒＋辱、鋰＝金＋里），
且**小篆組字傳統本來就用完整部件形**（不是楷書的縮略偏旁）——把
部件篆形縮放平移進結構槽位，可合成可辨識的近似篆字。

三個資料來源，依序：

1. ``ELEMENT_DECOMP``：元素週期表特化表（現代造字不在會意 DB）。
2. 朱邦復《五千字》會意拆解 DB（3,719 字，head/tail 部件——
   本專案既有 :mod:`stroke_order.decomposition`）。DB 給的是語意
   序（字首/字尾）而非空間方位，方位由 ``_HEAD_POSITION`` 推測：
   字首是典型左偏旁（金木水火…）→ ⿰；典型上偏旁（网艹雨…）→ ⿱；
   气 → ⿹ 包圍。**推不出方位就誠實放棄**（維持退楷書），不出爛字。
3. 部件本身缺篆時，交回 ``get_character``（含簡繁/異體 fallback、
   以及巢狀合成——``_composing`` 集合防循環）。

誠實標示：合成字 ``validation_notes`` 帶 ``seal-synth:⿰金里`` 記號，
渲染層據此在 cellmap 標 ``data-seal-synth``、預覽狀態列顯示統計。
``data_source`` 維持 ``"chongxi_seal"``——骨架/描邊轉換管線
（apply_seal_outline_mode）依它分流，合成字要走同一條。
"""
from __future__ import annotations

from typing import Callable, Optional

from ..ir import Character, Stroke

EM = 2048

# ---------------------------------------------------------------------------
# 結構槽位（EM 2048 座標；(dx, dy, sx, sy)：x' = dx + sx·x）
# ---------------------------------------------------------------------------
# 小篆偏旁習慣：左右各佔約半、留窄縫；上下同理；气 是三筆包覆右上，
# 聲旁縮入左下。數值是視覺調參的第一版，之後可依實機回饋微調。
_SLOTS: dict[str, tuple[tuple[float, float, float, float],
                        tuple[float, float, float, float]]] = {
    "⿰": ((40.0, 0.0, 0.46, 1.0), (1064.0, 0.0, 0.46, 1.0)),
    "⿱": ((0.0, 40.0, 1.0, 0.46), (0.0, 1064.0, 1.0, 0.46)),
    "⿹": ((0.0, 0.0, 1.0, 1.0), (150.0, 800.0, 0.55, 0.55)),
}

# ---------------------------------------------------------------------------
# 字首方位推測表（朱邦復 DB 的 head root → 空間結構）
# ---------------------------------------------------------------------------
# 保守曲線：只收「幾乎總是」該方位的部首；含糊的一律不收（寧缺勿錯，
# 推不出來就退楷書）。root 用完整部件形（DB 與篆書皆然：网 而非 罒）。
_HEAD_LEFT = set(
    "金木水火土石言糸耒禾米虫魚馬鳥革足女子弓貝車舟角酉骨食"
    "犬牛王玉目手日月山阜島綜")
_HEAD_TOP = set("网艹草竹雨宀穴亠癶爪")
_HEAD_SURROUND = set("气")


def _infer_operator(head: str) -> Optional[str]:
    if head in _HEAD_SURROUND:
        return "⿹"
    if head in _HEAD_TOP:
        return "⿱"
    if head in _HEAD_LEFT:
        return "⿰"
    return None


# ---------------------------------------------------------------------------
# 元素週期表特化拆解（Taiwan 命名；現代造字不在會意 DB）
# ---------------------------------------------------------------------------
# (op, 部首件, 聲旁件)。只收高把握項；沒把握的元素不收＝維持退楷書。
# 聲旁件缺篆時 get_character 會走簡繁/異體 fallback（如 尔→爾）。
ELEMENT_DECOMP: dict[str, tuple[str, str, str]] = {
    # 气 部（⿹ 包圍）
    "氫": ("⿹", "气", "巠"), "氦": ("⿹", "气", "亥"),
    "氮": ("⿹", "气", "炎"), "氧": ("⿹", "气", "羊"),
    "氟": ("⿹", "气", "弗"), "氖": ("⿹", "气", "乃"),
    "氯": ("⿹", "气", "彔"), "氬": ("⿹", "气", "亞"),
    "氪": ("⿹", "气", "克"), "氙": ("⿹", "气", "山"),
    "氡": ("⿹", "气", "冬"),
    # 金 部（⿰）
    "鋰": ("⿰", "金", "里"), "鈹": ("⿰", "金", "皮"),
    "鈉": ("⿰", "金", "內"), "鎂": ("⿰", "金", "美"),
    "鋁": ("⿰", "金", "呂"), "鉀": ("⿰", "金", "甲"),
    "鈣": ("⿰", "金", "丐"), "鈧": ("⿰", "金", "亢"),
    "鈦": ("⿰", "金", "太"), "釩": ("⿰", "金", "凡"),
    "鉻": ("⿰", "金", "各"), "錳": ("⿰", "金", "孟"),
    "鈷": ("⿰", "金", "古"), "鎳": ("⿰", "金", "臬"),
    "鋅": ("⿰", "金", "辛"), "鎵": ("⿰", "金", "家"),
    "鍺": ("⿰", "金", "者"), "銣": ("⿰", "金", "如"),
    "鍶": ("⿰", "金", "思"), "釔": ("⿰", "金", "乙"),
    "鋯": ("⿰", "金", "告"), "鈮": ("⿰", "金", "尼"),
    "鉬": ("⿰", "金", "目"), "鎝": ("⿰", "金", "荅"),
    "釕": ("⿰", "金", "了"), "銠": ("⿰", "金", "老"),
    "鈀": ("⿰", "金", "巴"), "鎘": ("⿰", "金", "鬲"),
    "銦": ("⿰", "金", "因"), "銻": ("⿰", "金", "弟"),
    "銫": ("⿰", "金", "色"), "鋇": ("⿰", "金", "貝"),
    "鑭": ("⿰", "金", "闌"), "鈰": ("⿰", "金", "市"),
    "鐠": ("⿰", "金", "普"), "釹": ("⿰", "金", "女"),
    "鉕": ("⿰", "金", "叵"), "釤": ("⿰", "金", "彡"),
    "銪": ("⿰", "金", "有"), "鏑": ("⿰", "金", "啇"),
    "鈥": ("⿰", "金", "火"), "鉺": ("⿰", "金", "耳"),
    "銩": ("⿰", "金", "丟"), "鐿": ("⿰", "金", "意"),
    "鎦": ("⿰", "金", "留"), "鉿": ("⿰", "金", "合"),
    "鉭": ("⿰", "金", "旦"), "鎢": ("⿰", "金", "烏"),
    "錸": ("⿰", "金", "來"), "鋨": ("⿰", "金", "我"),
    "銥": ("⿰", "金", "衣"), "鉑": ("⿰", "金", "白"),
    "鉈": ("⿰", "金", "它"), "鉍": ("⿰", "金", "必"),
    "釙": ("⿰", "金", "卜"), "鍅": ("⿰", "金", "法"),
    "鐳": ("⿰", "金", "雷"), "錒": ("⿰", "金", "阿"),
    "釷": ("⿰", "金", "土"), "鏷": ("⿰", "金", "菐"),
    "鈾": ("⿰", "金", "由"), "錼": ("⿰", "金", "奈"),
    "鈽": ("⿰", "金", "布"), "鋂": ("⿰", "金", "每"),
    "鋦": ("⿰", "金", "局"), "鉳": ("⿰", "金", "北"),
    "鉲": ("⿰", "金", "卡"), "鑀": ("⿰", "金", "愛"),
    "鐨": ("⿰", "金", "費"), "鍆": ("⿰", "金", "門"),
    "鍩": ("⿰", "金", "若"), "鐒": ("⿰", "金", "勞"),
    "鑪": ("⿰", "金", "盧"), "鐽": ("⿰", "金", "達"),
    "錀": ("⿰", "金", "侖"), "鎶": ("⿰", "金", "哥"),
    "鉨": ("⿰", "金", "尔"), "鏌": ("⿰", "金", "莫"),
    "鉝": ("⿰", "金", "立"), "鈇": ("⿰", "金", "夫"),
    # 石 部（⿰）
    "硼": ("⿰", "石", "朋"), "碳": ("⿰", "石", "炭"),
    "矽": ("⿰", "石", "夕"), "磷": ("⿰", "石", "粦"),
    "砷": ("⿰", "石", "申"), "硒": ("⿰", "石", "西"),
    "碲": ("⿰", "石", "帝"), "碘": ("⿰", "石", "典"),
    "砈": ("⿰", "石", "厄"),
    # 水 部
    "溴": ("⿰", "水", "臭"), "汞": ("⿱", "工", "水"),
}


def is_seal_synth(c: Optional[Character]) -> bool:
    """渲染層探測：這個（已載入的）字是不是部件合成篆字。"""
    return c is not None and any(
        n.startswith("seal-synth:") for n in c.validation_notes)


# ---------------------------------------------------------------------------
# 幾何：outline 命令仿射（canonical EM 座標，Y 已朝下——純縮放平移）
# ---------------------------------------------------------------------------

def _affine_pt(p: dict, dx: float, dy: float, sx: float, sy: float) -> dict:
    return {"x": dx + sx * p["x"], "y": dy + sy * p["y"]}


def _affine_cmd(cmd: dict, dx: float, dy: float,
                sx: float, sy: float) -> dict:
    t = cmd.get("type", "")
    if t in ("M", "L"):
        return {"type": t,
                "x": dx + sx * cmd["x"], "y": dy + sy * cmd["y"]}
    if t == "Q":
        return {"type": "Q",
                "begin": _affine_pt(cmd["begin"], dx, dy, sx, sy),
                "end": _affine_pt(cmd["end"], dx, dy, sx, sy)}
    if t == "C":
        return {"type": "C",
                "begin": _affine_pt(cmd["begin"], dx, dy, sx, sy),
                "mid": _affine_pt(cmd["mid"], dx, dy, sx, sy),
                "end": _affine_pt(cmd["end"], dx, dy, sx, sy)}
    return dict(cmd)


def _part_outline(c: Character) -> list:
    out: list = []
    for s in c.strokes:
        out.extend(s.outline or [])
    return out


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def resolve_decomp(char: str, decomp_db) -> Optional[tuple[str, str, str]]:
    """回 (op, part1, part2)；查無或方位推不出 → None（誠實放棄）。"""
    hit = ELEMENT_DECOMP.get(char)
    if hit:
        return hit
    d = decomp_db.get(char)
    if d is None or not d.head_root or not d.tail_root:
        return None
    head = d.head_root.strip()
    tail = d.tail_root.strip()
    if len(head) != 1 or len(tail) != 1:
        return None
    op = _infer_operator(head)
    if op is None:
        return None
    return (op, head, tail)


def compose_seal_character(
    char: str,
    get_part: Callable[[str], Character],
    decomp_db,
) -> Optional[Character]:
    """部件合成一個近似篆字；不可合成回 None。

    ``get_part`` 由 ChongxiSealSource 提供（含簡繁/異體 fallback 與
    巢狀合成）；取件失敗應丟 CharacterNotFound。
    """
    plan = resolve_decomp(char, decomp_db)
    if plan is None:
        return None
    op, p1, p2 = plan
    from .g0v import CharacterNotFound
    try:
        c1 = get_part(p1)
        c2 = get_part(p2)
    except CharacterNotFound:
        return None
    slot1, slot2 = _SLOTS[op]
    outline: list = []
    for c, (dx, dy, sx, sy) in ((c1, slot1), (c2, slot2)):
        outline.extend(
            _affine_cmd(cmd, dx, dy, sx, sy) for cmd in _part_outline(c))
    if not outline:
        return None
    return Character(
        char=char,
        unicode_hex=f"{ord(char):04x}",
        strokes=[Stroke(
            index=0, raw_track=[], outline=outline,
            kind_code=0, kind_name="其他", has_hook=False,
        )],
        data_source="chongxi_seal",        # 骨架/描邊管線依此分流——必須維持
        validation_notes=[f"seal-synth:{op}{p1}{p2}"],
    )
