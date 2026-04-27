"""
Build 中日韓共用常用 808 漢字 dataset.

Input: 808 simplified characters (from TCS official 2014 publication, list provided manually)
Output: data/cjk_common_808.json with simp + trad + metadata

Source: Trilateral Cooperation Secretariat (TCS), proposed at NATF 2013 (Hokkaido),
        finalized at NATF 2014 (Yangzhou). Booklet published 2016.

Reference: https://www.tcs-asia.org/en/data/publications.php
"""

import json
from pathlib import Path

import opencc

# 808 simplified characters (in publication order, from TCS booklet)
CHARS_808_SIMP = (
    "一七三上下不世中主久乘九事二五井亡交京人仁今他仙代令以仰伏伐休位低住何佛作使来例"
    "依便俗保信修个借假伟停备传伤价亿元兄充兆先光免儿入内全两八公六共兵典册再冬冰冷出"
    "刀分刑列初判别利到则前力功加助勇勉动务胜劳势勤劝化北区十千午半卒协南印危卷厚原去"
    "参又及友反取受口古句可史右各合吉同名向君否吹告味呼命和哀品唱商问善喜丧单严四回因"
    "困固国园圆图团土在地均城执基堂坚报场增士壮寿夏夕外多夜大天太夫央失奉女好如妙妹妻"
    "姊始姓威婚妇子字存孝季孙学宅宇守安完宗官宙定客室害家容宿密富寒察实写寸寺射将尊对"
    "小少就尺尾局居屋展山岛崇川工左巨己已市布希师席常平年幸幼序店度庭广建式弓引弟弱强"
    "形彼往待律後徒得从德心必忍志忘忙忠快念怒思急性怨恨恩悟患悲情惜惠恶想愁意爱感慈庆"
    "忧忆应成我战户所手才打扶承技投抱招拜拾持指授采探接推扬支收改放政故效救败教敢散敬"
    "敌数文料新方施旅族日早明易昔星春昨是时晚昼景晴暑暖暗暮暴曲更书最会月有服望朝期木"
    "未末本朱材村东松林果枝柔校根栽案植业极荣乐树桥权次欲歌欢止正步武岁历归死杀母每比"
    "毛氏民气水永江决河油治泉法波泣注泰洋洗活流浪浮浴海消凉净深混浅清减湖温满渔汉洁火"
    "烈无然烟热灯争父片牛物特犬独玉王现球理甘生产用田由申男界留番画异当病登发白百的皆"
    "皇皮益盛尽目直相省看真眠眼着知短石破硏示祖祝神祭禁福礼秀私秋科移税种谷究空窗立章"
    "童端竞竹笑第笔等答算节米精约红纯纸素细终结绝给统经绿线练续罪羊美义习老考者耕耳圣"
    "闻声听肉育胸能脱臣自至致与兴举旧舌舍舞船良色花若苦英茶草菜华万落叶著艺药虎处虚号"
    "虫血众行街衣表制西要见视亲观角解言计训记访设许试诗话认语诚误说谁课调谈请论诸讲谢"
    "证识议读变让豆丰贝财贫货责贮贵买贺赏贤卖质赤走起足路身车军轻辛农迎近追退送逆通速"
    "造连进遇游运过道达远适选遗部都乡酒医里重野量金针银钱钟铁长门闭开闲间关防降限除阴"
    "陆阳雄集难雨雪云电露青静非面革韩音顶顺须领头题愿风飞食饭饮养馀首香马惊骨体高鱼鲜"
    "鸟鸣麦黄黑点鼻齿"
)

assert len(CHARS_808_SIMP) == 808, f"Expected 808 chars, got {len(CHARS_808_SIMP)}"


def main():
    # Convert simp -> trad using OpenCC s2t (Hong Kong / Taiwan standard)
    s2t = opencc.OpenCC("s2t")
    chars_trad = "".join(s2t.convert(c) for c in CHARS_808_SIMP)

    # Identify mismatches (chars where simp != trad)
    mismatches = []
    for i, (s, t) in enumerate(zip(CHARS_808_SIMP, chars_trad)):
        if s != t:
            mismatches.append({"index": i + 1, "simp": s, "trad": t})

    # Build entries
    entries = []
    for i, (s, t) in enumerate(zip(CHARS_808_SIMP, chars_trad)):
        entries.append({
            "index": i + 1,
            "simp": s,
            "trad": t,
            "same": s == t,
        })

    # Output dataset
    out = {
        "title": "中日韓共同常用 808 漢字表",
        "english_title": "808 Commonly Used Chinese Characters in China, Japan and the ROK",
        "source": "Trilateral Cooperation Secretariat (TCS)",
        "publication_year": 2014,
        "booklet_year": 2016,
        "url": "https://www.tcs-asia.org/en/data/publications.php",
        "char_count": len(entries),
        "trad_simp_mismatch_count": len(mismatches),
        "entries": entries,
    }

    out_path = Path("data/cjk_common_808.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}: {len(entries)} chars, {len(mismatches)} simp/trad mismatches")
    print()
    print(f"First 10 mismatches:")
    for m in mismatches[:10]:
        print(f"  #{m['index']:3d}: {m['simp']} → {m['trad']}")


if __name__ == "__main__":
    main()
