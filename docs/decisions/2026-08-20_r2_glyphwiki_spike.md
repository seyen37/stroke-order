# ADR — R2 GlyphWiki/KAGE 字源：spike 後緩議（供日後翻案）

- 日期：2026-08-20
- 狀態：**緩議**（spike 完成、實作不啟動；翻案條件與路徑在文末）
- 相關：FANGCUN 評估 `2026-08-11_fancun_evaluation.md`（R2 原案）、§89
  （外部資產先量對本用途覆蓋率再打包；量測留 ADR 供翻案）、§68/§86
  （禁執行期外部相依）、§97（風險寫不成守門＝該先量測）

## 脈絡

R3→B→R2 的最後一項。R2 原案（FANGCUN 評估）：GlyphWiki 的 KAGE 資料當
新字形來源，罕字也能長字模。順序 sign-off 時已載明「第一步是 spike——
資料取得模式 × 對 CNS 的邊際價值，不過就誠實撤案」。

## Spike 量測（2026-08-20，全部可覆驗）

### 1. 內部：缺口在哪

| 資料層 | 覆蓋 | 能做什麼 |
|---|---|---|
| 筆順骨架鏈（user_dict→g0v→MMH→KanjiVG） | ≈9k 字（g0v bundle 1,830 行＋MMH＋KanjiVG） | 機器人書寫、描紅、分解圖 |
| CNS 全字庫字型 | ≈95k 字 | 輪廓：雕刻/字模/顯示（無筆順幾何） |
| CNS 筆順序列檔 | 廣 | 筆**類**序列（1-5 碼），無幾何 |

**R2 的邊際價值＝9k→95k 缺口的「筆順幾何」**：這些字有輪廓可雕、無筆順
可寫。典型場景：學生姓名含罕字、要寫字機器人寫。真實，但窄。

### 2. 外部：取得與授權

- **授權：自由**。Mozilla 收錄的 GlyphWiki 授權原文：「The glyphs
  registered at the GlyphWiki… can be freely used by anyone」「Reuse of
  this data, such as reproduction or modification… is permitted」，商用
  允許、無署名要求。（來源：mozilla-central
  `layout/reftests/fonts/glyphwiki-license.txt`——原文轉錄，非二手轉述）
- **執行期 API：不可行**。glyphwiki.org 的 robots.txt 明確拒絕機器抓取
  （本 spike 兩次抓取被 ROBOTS_DISALLOWED 擋下）；§68/§86 本就禁止執行
  期外部相依。**尊重站方意願：批次取得只能走官方 dump 檔**（站方明文
  提供 `dump_newest_only.txt.gz` 給批次使用）。
- **合規路徑**：dump 篩 CJK 子集打包進 repo（估 10+ MB）或鏡像自家
  GitHub release 建置時抓（同字型七源模式）。

### 3. 轉換成本與品質

- KAGE 格式：筆畫原語（直線/曲線/折）＋部件引用（`99:` 行）需**遞迴
  展開＋仿射變換**——解析器是持續維護的真實成本。
- **KAGE 筆順不保證教育部標準**——上線須誠實標注（同 §87），教學場景
  的價值因此再打折。

## 決策（使用者 sign-off：緩議歸檔）

與 T3 插圖同構：**授權可、技術可行 ≠ 值得付永久成本**。成本＝10+ MB
永久體積＋解析器維護＋非標準筆順的誠實性負擔；需求端至今**零證據**
（無任何使用者回報罕字機器人書寫需求）。緩議，等 W0 回饋。

## 翻案條件與路徑（直接動工用，不必重做 spike）

**條件**：出現真實需求證據——使用者回報「要寫的字不在 9k 筆順鏈內」
（可在 404 回應加計數器蒐集，見下）。

**路徑**（已驗證合規）：
1. 從官方 dump（`Group:dump-README-en` 之管道）篩「CNS 有輪廓、筆順鏈
   沒有」的字集；
2. 打包進 repo（比照 `moe_dict_bundle` 慣例）或鏡像自家 release；
3. `sources/glyphwiki.py` 解析 KAGE（部件遞迴展開），接在筆順鏈
   KanjiVG 之後當最後後備；
4. 回應標注 `data_source="glyphwiki"` ＋「筆順非教育部標準」（§87）；
5. 授權聲明入 `licenses/`（引 Mozilla 收錄之原文）。

**低成本前置（可先做）**：筆順鏈 404 時記一筆「缺字請求」計數——需求
證據自己會長出來，不用猜。

## 本輪未立新原則

spike 的工作法全是既有原則再套用：§89（先量覆蓋率）、§97 反向用法
（風險寫不成守門＝先量測）、§91（授權查原文——這次連查證管道被 robots
擋下也如實記錄，改引 Mozilla 收錄原文）。
