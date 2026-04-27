# 教育部國字標準字體資料 — 參考資料分析（關鍵轉折）

> 分析對象：
> - `edukai-5.1_20251208.ttf` (15.8 MB，官方標準楷書)
> - `全筆順動畫嵌入碼網址列表.csv` (6,063 字 × 4 欄)
> - `6063png.zip` (6,063 張筆順演進圖，50×725 px)
> - `principle.pdf` (7 頁，17 條官方筆順法則)
> - `4808.pdf` (4,808 常用字表)
> - 官網來源：https://stroke-order.learningweb.moe.edu.tw/
>
> 發現：**這批是國家級標準資料，徹底超越前四批的實用價值**

---

## 一、檔案概覽與授權

| 檔案 | 內容 | 授權 | 對我們的價值 |
|---|---|---|---|
| `edukai-5.1_20251208.ttf` | 教育部標準楷書 v5.1 (2025/12) | CC BY-ND 3.0 Taiwan | ★★★★★ 向量形狀主來源 |
| `全筆順動畫...csv` | 6063 字 Unicode + iframe URL | 公開資料 | ★★★★ 字集索引 |
| `6063png.zip` | 6063 張筆順演進圖 | 公開資料 | ★★★★★ 筆順切分關鍵 |
| `principle.pdf` | 17 條筆順基本法則 | 公開資料 | ★★★ 驗證規則 |
| `4808.pdf` | 1982 公告 4808 個常用字 | 公開資料 | ★★★ Phase 1 目標範圍 |

**關鍵授權注意**：TTF 是 **CC BY-ND 3.0** —— 允許轉散佈、允許商業使用，但**禁止改作（No Derivatives）**。我們的用法是：**以 TTF 為輸入，動態提取某字的向量路徑作為寫字機器人的參考資料**。這屬於「使用」而非「改作發佈字型」，法律上安全。需在產品中**標示「中華民國教育部」為字形授權方**。

## 二、TTF 規格驗證

```
Name            : TW-MOE-Std-Kai / 教育部標準楷書
Version         : 5.1, December 2025
License         : CC BY-ND 3.0 Taiwan
Character count : 14,037 glyphs (cmap 涵蓋率)
unitsPerEm      : 2048
Format          : TrueType (glyf 表)，非 CFF
Tables          : GlyphOrder, head, hhea, maxp, OS/2, hmtx, cmap,
                  prep, cvt, loca, glyf, name, post, gasp, FFTM,
                  GPOS, GSUB, vhea, vmtx
```

**對我們的意義**：
- **glyf 表**意味每字是二次 Bezier 輪廓（而非 CFF 的三次 Bezier）
- **14,037 字**已涵蓋所有常用繁體字 + 大量罕用字
- **vhea/vmtx**代表支援直排
- 2048 UPM 是標準字型規格，座標精度足夠

用 fontTools 解析後可以直接取得**每個字的輪廓線 (contours)**，這是「描邊」的向量資料。

## 三、筆順 PNG 的結構分析 — 關鍵發現

每個 50×725 PNG 是**垂直條狀的漸進筆順圖**。以 `永.png` (5 筆) 實測：

```
偵測到 9 個墨跡區塊：
  frame 1: rows 8-13    (5px高, 16 ink px)   ← 小圖示
  frame 2: rows 53-58   (5px高, 16 ink px)   ← 小圖示
  frame 3: rows 61-87   (26px高, 81 ink px)  ← 累積字形
  frame 4: rows 98-103  (5px高, 16 ink px)   ← 小圖示
  frame 5: rows 106-132 (26px高, 133 ink px) ← 累積字形
  frame 6: rows 143-148 (5px高)              ← 小圖示
  frame 7: rows 151-177 (26px高, 159 ink px) ← 累積字形
  frame 8-9: ...
```

結構推測：
```
[第 1 筆單獨] — [第 1 筆累積圖]
[第 2 筆單獨] — [1+2 累積圖]
[第 3 筆單獨] — [1+2+3 累積圖]
...
```

對我們的關鍵意義是：**可以機械化地把每一筆從 TTF 輪廓裡切出來**：

1. 取 PNG 中「第 N 筆累積」與「第 N−1 筆累積」兩張圖
2. 對兩者做 XOR / diff
3. 差異部分就是**第 N 筆的 pixel mask**
4. 將此 mask 投影到 TTF 輪廓上 → 得到該筆對應的 **Bezier 路徑段**
5. 骨架化 mask → 得到該筆的 **中線 polyline** (給寫字機器人用)

這解決了先前用 MMH 或 MODVEC 都沒完整解決的問題：**如何把字型輪廓按筆順切分**。

## 四、17 條筆順法則（principle.pdf 整理）

這是官方驗證用的規則，可以作為算法單元測試：

| # | 規則 | 範例 |
|---|---|---|
| 1 | 自左至右 | 川、仁、街、湖 |
| 2 | 先上後下 | 三、字、星、意 |
| 3 | 由外而內 | 刀、勻、月、問 |
| 4 | 先橫後豎 | 十、干、士、甘、聿 |
| 5 | 先撇後捺 | 入、交、事 |
| 6 | 豎畫在中而不交，先寫豎 | 上、小、山、水 |
| 7 | 底下與豎相接的橫，最後寫 | 王、里、告、書 |
| 8 | 中橫突出者最後寫 | 女、丹 |
| 9 | 四圍結構：先外圍、再裡面、最後封口橫 | 日、田、回、國 |
| 10 | 點在上或左上先寫；下/內/右上後寫 | 下、為、叉、犬 |
| 11 | 從戈之字：先橫，最後點、撇 | 戍、成 |
| 12 | 撇在上 / 撇+橫折鉤下包：撇先寫 | 千、白、用、凡 |
| 13 | 橫豎相交、左右對稱：先橫豎，後左右 | 來、垂、喪、乘、甬 |
| 14 | 豎折/豎曲鉤等無擋筆，通常後寫 | 區、臣、也、比、包 |
| 15 | 含廴、辶為偏旁：最後寫 | 廷、建、返、迷 |
| 16 | 下托半包：先寫上面，再寫下托 | 凶、函、出 |
| 17 | 左右夾中且對稱：先中間，再左右 | 兜、學、樂、變、贏 |

**實際用途**：筆順排序演算法出錯時，拿這 17 條規則 + 每條 3-5 個範例字做**迴歸測試**。

## 五、4808 常用字表

1982 年教育部公告，欄位：`流水序 / 教育部字號 (A00001...) / Unicode / 常用字`。

這是台灣教育體系的**官方常用字基準**。建議：
- **Phase 1 的 MVP 目標**就鎖定這 4,808 字（覆蓋率 100%）
- 超過部分（4808 → 6063 → 14037）作為 Phase 2 擴張
- `A00001` 編號可作為主鍵之一（供與教科書對接）

## 六、與前四批資料的整合關係

這是**全新的、獨立於朱邦復體系**的資料來源。特性對比：

| 面向 | 朱邦復體系 | MOE 體系 |
|---|---|---|
| 來源 | 1個人 40 年 | 政府單位持續維護 |
| 最新版本 | 2018 講座 | 2025/12（6 週前） |
| 授權 | 非正式釋出 | CC BY-ND 3.0（legally open）|
| 字量 | 18,000 字（bitmap）| 14,037 字（vector）+ 4,808 常用 |
| 結構化 | 5000.TXT 的 head+tail schema | TTF 輪廓 + 筆順 PNG |
| 筆順 | 無（只有形） | 6,063 字完整筆順 |
| 筆畫分類 | 有（MODVEC 9 型）| 無（但 17 條法則隱含）|

**結論**：兩套可以互補！

| 需求 | 最佳來源 |
|---|---|
| 字元集 / 常用字範圍 | **MOE 4808** |
| 向量形狀 | **MOE TTF** |
| 筆順 | **MOE PNG** |
| 筆劃分類標籤 | **朱邦復 MODVEC 9 型** |
| 組件樹 / 字根分解 | **朱邦復 5000.TXT** |
| 部首 metadata | **朱邦復 2018** |
| 17 條規則驗證 | **MOE principle** |

## 七、路線再升級：路線 E（MOE 主導 + 朱邦復輔助）

原本的路線 D 是「完全用朱邦復資料」。MOE 資料加入後，**建議升級到路線 E**。

### 新的 Phase 1-3（約 1-2 週）

**Phase 1**：MOE 基礎管線
1. 解析 4808.pdf → 建立 `char → moe_id + unicode` 索引表
2. 用 fontTools 讀 edukai TTF → 每字可取 contour polygons
3. 對 6063 PNG 做 frame segmentation + 差異計算 → 每字可取「第 N 筆 mask」
4. **關鍵演算法**：TTF contour × PNG mask → 把輪廓切成按筆順的分段
5. 輸出 IR：`Character { strokes: [Stroke { contour, mask, skeleton }] }`

**Phase 2**：三種 Exporter（不變）
- contour → SVG path (描邊)
- skeleton → SVG path / G-code / JSON polyline (走線)

**Phase 3**：本地 Web 介面（不變）
- 輸入中文字 → 查 MOE id → 組合 TTF + 筆順 → 三格式輸出 + SVG 預覽

### Phase 4-5（進階，看需求）

**Phase 4**：整合朱邦復資料作為 metadata / classification
- 5000.TXT → 每字補上 `decomposition: {head, tail}`
- MODVEC 9 筆畫類型 → 每個 stroke 補上 `kind: heng/shu/pie/na/...`
- 2018 部首分類 → 每字根補上 `radical_category: 本存/人造/規範/應用`

**Phase 5**：多字型 + 風格化
- 目前只有楷體 → Phase 5 再導入其他字型（宋/明/黑）
- MODVEC 的 `BBFNTKND` 參數化概念 → 我們做風格切換

### 17 條法則 = 單元測試
每條法則挑 3-5 個範例字，驗證我們的筆順切分結果符合規則。

## 八、立即可驗證的第一步

一旦你說動工，最少的「hello world」就是：

```python
# 1. 讀 TTF
from fontTools.ttLib import TTFont
font = TTFont('edukai-5.1_20251208.ttf')

# 2. 對「永」取輪廓
glyph = font['glyf']['uni6C38']  # 永 = U+6C38

# 3. 讀 永.png 做筆順切分
from PIL import Image
strokes = segment_png('6063png/永.png')  # returns 5 stroke masks

# 4. 將輪廓按筆順順序切成 5 段 + 骨架化
vector_strokes = align_contour_to_masks(glyph, strokes)

# 5. 輸出 SVG
svg = export_svg(vector_strokes)
```

跑通這個 pipeline 就等於完成 MVP。4,808 字可以用 batch script 處理。

## 九、架構圖（最終版）

```
┌────────────────────────────────────────────────────────────────┐
│ INPUT: 中文字元 "永"                                              │
└────────────────────────┬───────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ L3 字元查詢                                                        │
│  └─ MOE 4808 lookup → A00001..A04808 + Unicode                 │
│  └─ [可選] 朱邦復 5000.TXT → head+tail decomposition            │
└────────────────────────┬───────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ L2 向量資料取得                                                    │
│  └─ edukai TTF[char] → contours (輪廓, 二次 Bezier)             │
│  └─ 6063png/{char}.png → stroke masks (按順序)                  │
└────────────────────────┬───────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ L1 筆畫切分與標註                                                  │
│  └─ 對齊 contour × mask → per-stroke segment                   │
│  └─ Skeletonize (zhang-suen) → centerline polyline             │
│  └─ [可選] MODVEC 9 型分類 → kind label                          │
│  └─ 17 rule 驗證                                                 │
└────────────────────────┬───────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ L0 輸出                                                           │
│  ├─ SVG (描邊 or 走線)                                           │
│  ├─ G-code (筆抬/筆落 M5/M3)                                     │
│  └─ JSON polyline [[x,y], ...]                                 │
└────────────────────────────────────────────────────────────────┘
```

## 十、結論

1. **這批 MOE 資料是專案的「官方基石」**，建議作為主資料來源。
2. **朱邦復資料降為輔助角色**，提供分類標籤、組件樹、風格化參數。
3. **路線 E 取代路線 D**。Phase 1 的第一個 commit 應該是：`TTF + PNG 對齊切分器`，而非原先建議的 `5000.TXT 解析器`。
4. **合法性最穩**：MOE 資料公開授權，朱邦復資料屬個人著作但既已在網路流傳多年。產品上線時標示「字形由教育部 CC BY-ND 授權」即可。
5. **Phase 1 涵蓋 4,808 字**，對寫字機器人所有一般場景已足夠。

---

**五份分析總結**：

| 來源 | 年代 | 狀態 |
|---|---|---|
| [1992 scg.zip](computer:///sessions/friendly-dreamy-noether/mnt/stroke_order/REF_ANALYSIS_SCG.md) | 1992 | 架構啟蒙 |
| [2010 fontdata](computer:///sessions/friendly-dreamy-noether/mnt/stroke_order/REF_ANALYSIS_SCG2010.md) | 2010 | L1 筆畫原子 |
| [2012 5000.zip](computer:///sessions/friendly-dreamy-noether/mnt/stroke_order/REF_ANALYSIS_5000.md) | 2012 | 字根組合 DB |
| [2018 講座](computer:///sessions/friendly-dreamy-noether/mnt/stroke_order/REF_ANALYSIS_2018.md) | 2018 | metadata |
| **[2025 MOE](computer:///sessions/friendly-dreamy-noether/mnt/stroke_order/REF_ANALYSIS_MOE.md)** | **2025** | **主資料來源** |

**等你說「開始動工」即啟動路線 E 的 Phase 1。**
