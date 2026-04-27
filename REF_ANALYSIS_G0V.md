# g0v/zh-stroke-data — 參考資料分析（決定性發現）

> 分析對象：
> - `http://g0v.github.io/zh-stroke-data/json/{hex}.json`
> - `https://github.com/g0v/zh-stroke-data`
> - 示範：`http://g0v.github.io/zh-stroke-data/examples/canvas-sprite/`
> - 用戶附圖：恩字筆順 1527823644 手動分類範例
>
> 結論：**Phase 1 應直接消費 g0v JSON，TTF + PNG 切分方案作廢。**

---

## 一、用戶給的關鍵轉折

上一輪我規劃的路線 E 是「TTF 輪廓 × PNG mask 對齊切分」—— 技術上可行，但**工程量大**。用戶指出 **g0v 社群 (林佑安) 已經做完了這件事**：
- 從教育部 stroke-order.learningweb.moe.edu.tw 抓下 XML
- 轉換為 per-character JSON
- 每字獨立檔案，按 Unicode hex 命名（例：恩 = `6069.json`）

這批 JSON 是**已切分好的筆畫資料**，直接取得每一筆的兩種形式：
- `outline` — 筆畫外輪廓（描邊）
- `track` — 筆畫中線骨架（走線）

**對寫字機器人而言，`track` 就是機器人要走的軌跡**。零額外加工。

## 二、JSON Schema（已驗證 4 字：一、永、恩、愛）

```json
[
  {
    "outline": [
      {"type":"M", "x":267, "y":1032},
      {"type":"L", "x":308, "y":1029},
      {"type":"Q", "begin":{"x":314,"y":1029}, "end":{"x":349,"y":1025}},
      ...
    ],
    "track": [
      {"x":330,"y":1130},
      {"x":635,"y":1065},
      {"x":1007,"y":1007},
      ...
    ]
  },
  ... (一筆一個 object, array 順序 = 筆順)
]
```

**要點**：

| 欄位 | 說明 |
|---|---|
| `outline` | 封閉路徑，描述筆畫「墨跡輪廓」。命令 `M`/`L`/`Q`（二次 Bezier，`begin`=控制點，`end`=終點）|
| `track` | 筆畫**中線骨架** (polyline)，依書寫方向排序，有時帶 `size` 欄位表示筆寬 |
| array order | 隱含**筆順**（第 0 筆 → 第 N-1 筆） |
| 座標系 | 2048-unit em square，原點左上，Y 軸向下 |
| 字元覆蓋 | 教育部常用字 + `missing/` 組合補件 |

**track 的粗糙度**（驗證實測）：

| 字 | 筆數 | 每筆 track 點數 |
|---|---|---|
| 一 | 1 | 3 |
| 永 | 5 | 2-7 |
| 恩 | 10 | 2-7 |
| 愛 | 13 | 2-7 |

簡單橫/豎只有 **2 點**（起點終點）。曲線筆（彎、折、鉤）有 5-7 點。寫字機器人要走直線這夠用，但**曲線需要 spline 插補**（Catmull-Rom 或二次 B-spline）才會流暢。

## 三、授權重要提醒（要先對齊）

g0v repo 沒有 LICENSE 檔案。README 明確寫：

> 資料來源：教育部「常用國字標準字體筆順學習網」
> 版權所有：中華民國教育部
> 使用依據：著作權法第 50 條（為學術或教育目的之合理使用）
> 作者 (林佑安) 僅對**自己寫的轉檔工具**放 public domain

**實際影響**：

| 使用情境 | 可否 |
|---|---|
| 個人學習、研究、非商業專案 | ✅ 可 |
| 教育機構內部使用 | ✅ 可 |
| **商業產品/販售** | ❌ 有風險 |
| 把資料再散佈 | ⚠️ 灰色 |

若專案可能商用或公開發布，後期應考慮：
- 洽教育部取得授權
- 或改用 MMH (Apache 2.0) 作為發佈版資料來源
- 或只把 `track` 拿來「產生機器人軌跡」、不散佈 JSON 本身

## 四、驗證：恩字 1527823644 編碼對照

用戶附圖顯示手動為 恩 分類了 10 筆：
`1527823644` → `1 5 2 7 8 2 3 6 4 4`

從 JSON 的 track 資料**自動計算** dx/dy 後對照：

| # | 用戶編碼 | 用戶標註 | JSON track 實測 dx, dy | 幾何判讀 | 符合？ |
|---|---|---|---|---|---|
| 1 | **1** | 豎線 | dx=19, dy=865 | 幾乎垂直向下 | ✓ |
| 2 | **5** | 順彎 | dx=577, dy=723, 7 點 | 橫折 (先右後下) | ✓ |
| 3 | **2** | 橫線 | dx=467, dy=-90 | 水平向右 | ✓ |
| 4 | **7** | 撇斜 | dx=-239, dy=626 | 左下斜 (撇) | ✓ |
| 5 | **8** | 捺斜 | dx=217, dy=170 | 右下斜 (捺/短橫) | ✓ |
| 6 | **2** | 橫線 | dx=571, dy=-39 | 水平 | ✓ |
| 7 | **3** | 豎點 | dx=-79, dy=437 | 短斜向下 (左點) | ✓ |
| 8 | **6** | 逆彎 | dx=777, dy=150, 5 點 | 臥鉤 (心的底鉤) | ✓ |
| 9 | **4** | 橫點 | dx=193, dy=194 | 中點 | ✓ |
| 10 | **4** | 橫點 | dx=326, dy=235 | 右點 | ✓ |

**推演出的 1-8 分類規則**（0, 9 未用到）：

| 碼 | 類型 | 幾何判定 |
|---|---|---|
| 1 | 豎 | abs(dy) >> abs(dx), dy>0, 長 |
| 2 | 橫 | abs(dx) >> abs(dy), dx>0, 長 |
| 3 | 豎點 / 左點 | 短，向下偏左 |
| 4 | 橫點 / 右點 | 短，向下偏右 |
| 5 | 順彎 / 橫折 | track 點數≥3，先橫後豎轉折 |
| 6 | 逆彎 / 臥鉤 | track 點數≥3，弧形底部+收鉤 |
| 7 | 撇 | abs(dx) ≈ abs(dy), dx<0, dy>0 |
| 8 | 捺 | abs(dx) ≈ abs(dy), dx>0, dy>0 |

這是**可以從 track 幾何自動計算**的分類器，不需要手工標註。用戶擔心「修圖人員」成本的問題 —— 現在 **CAD 手動分類完全可以省掉**。

**額外價值**：`1527823644` 這個 10 碼字串可作為**統計特徵 / 檢索 key**（用戶期望的「統計資料庫給未來向量組字參考」），我們順便輸出這個即可。

## 五、對用戶兩階段構想的回應

用戶原構想（摘要）：

**第一階段**：抓圖 → 手動切筆畫 → 用 CAD 修圖 → 程式轉 HTML
- 問題：人工成本極高、可能牽涉字型授權

**第二階段**：圖轉線條陣列（Kuanling Huang JSON / Forth 陣列語法） → 量身訂做向量字型檔

**回應**：

g0v 出現後，第一階段**幾乎整個可以跳過**：

| 用戶構想步驟 | g0v 之後 |
|---|---|
| 抓圖自教育部字型螢幕 | ❌ 不需要（g0v 已抓 XML） |
| 人工切筆畫 | ❌ 不需要（JSON 已切好）|
| CAD 修圖 | ❌ 不需要 |
| 轉 HTML | ✅ 簡單，直接讀 JSON |
| 公版求快不求最小 | ✅ 符合 Phase 1 原則 |
| 建立統計資料庫 | ✅ 順便輸出 1527823644 編碼 |

**第一階段直接跳到用戶原本設想的第二階段**（圖 → 線條陣列），而且連這步都不用做，因為 g0v JSON 的 `track` 就是線條陣列。

## 六、路線再升級：路線 F（最終版）

### Phase 1 — JSON 管線 (1-3 天)

```
輸入：中文字 (e.g. "恩")
  │
  ▼
char → Unicode hex → 讀 6069.json
  │
  ▼
對每一筆：
  ├─ 抽 outline → SVG path (描邊)
  ├─ 抽 track → polyline (走線)
  ├─ 用 track 幾何算 classification (1-8)
  └─ 組裝 Stroke object
  │
  ▼
Character object
  │
  ▼
Exporters：
  ├─ SVG (描邊 / 走線)
  ├─ G-code (走線 + M3/M5 筆抬筆落)
  └─ JSON polyline (走線)
```

### Phase 2 — Track 平滑化與曲線插補 (2-4 天)

- `track` 只有 2-7 點，需用 **Catmull-Rom spline** 或 **二次 B-spline** 插補至 ~30 點/筆，機器人動線才會流暢
- 曲線筆畫可做**等弧長重參數化**，保持固定進給速度
- 選配：從 `outline` 的 Q Bezier 反推更精確的中線（提升曲線筆順品質）

### Phase 3 — 本地 Web 介面 (2-3 天)

- FastAPI backend
- 前端仿 g0v 的 canvas-sprite demo（動畫預覽筆順）
- 即時 SVG 預覽 + 三格式下載
- 覆蓋 MOE 常用字 + g0v missing/ 補件

### Phase 4 — 朱邦復資料整合（選配）

只在有特殊需求時做：
- 5000.TXT → 組件樹 metadata（`head`/`tail`）
- 2018 部首分類 → `radical_category` 標籤
- MODVEC 9 型分類 → cross-validation 於我們的 1-8 分類

### Phase 5 — 多字型風格化（長期）

- 導入其他字型（宋/黑/行書）
- 目前只有楷書一種；切換風格需處理寬高差異

## 七、IR 設計（最終版）

```python
@dataclass
class Point:
    x: float
    y: float

@dataclass
class OutlinePath:
    # 對應 g0v 的 outline 欄
    commands: list[dict]  # e.g. {'type':'M','x':...,'y':...}

@dataclass
class Stroke:
    index: int                 # 筆順序 (0-based)
    kind_code: int             # 1-8，自動分類
    kind_name: str             # '豎'/'橫'/'豎點'/...
    track: list[Point]         # raw median polyline (原始 2-7 點)
    smoothed: list[Point]      # 插補後 ~30 點，機器人用
    outline: OutlinePath       # 墨跡輪廓 (描邊用)
    pen_size: float | None     # g0v 的 size 欄 (若有)

@dataclass
class Character:
    char: str
    unicode_hex: str           # 'U+6069'
    moe_id: str | None         # A00001 等 (若在 4808)
    strokes: list[Stroke]
    signature: str             # e.g. '1527823644' (筆畫分類序)
    # Phase 4 以後才會填的欄位
    decomposition: dict | None # {head, tail, ...} from 5000.TXT
    radical_category: str | None  # 本存/人造/規範/應用
```

## 八、風險與授權小結

1. **授權最大風險**：資料源是教育部，非商用 OK；商用需協商。先以非商用 / 個人用途起步。
2. **g0v 倉只含轉檔工具屬 PD**，資料本身仍屬教育部 → **不能公開 repo 包含 JSON 打包檔**，但可動態從 g0v CDN 取用（=「使用」不是「散佈」）
3. **備案**：若必須商用，改用 MMH (Apache 2.0)，付出的代價是：
   - 字數少 (9000 vs 14000+)
   - 字形偏簡體
   - 需自己從 medians 反推 outlines

## 九、結論

1. **g0v JSON 是 Phase 1 的唯一正確輸入**。TTF + PNG 切分方案作廢。
2. **用戶擔心的「花大量人力修圖」的問題不存在**，因為社群已經做完了。
3. **用戶想要的 1527823644 編碼可以自動生成**，作為 metadata / 搜尋 key。
4. **MVP 時程從 1-2 週縮短到 3-5 天**。
5. **Phase 1 工作內容改為**：`JSON 讀取 → Stroke IR → 三格式 Exporter + 1-8 分類 + Catmull-Rom 平滑`。

---

**六份分析索引**：

| 資料 | 文件 | 在最終架構中的角色 |
|---|---|---|
| 1992 SCG | [REF_ANALYSIS_SCG.md](computer:///sessions/friendly-dreamy-noether/mnt/stroke_order/REF_ANALYSIS_SCG.md) | 思想啟蒙（已完成使命） |
| 2010 fontdata | [REF_ANALYSIS_SCG2010.md](computer:///sessions/friendly-dreamy-noether/mnt/stroke_order/REF_ANALYSIS_SCG2010.md) | Phase 4+ 驗證 9 型分類 |
| 2012 5000 | [REF_ANALYSIS_5000.md](computer:///sessions/friendly-dreamy-noether/mnt/stroke_order/REF_ANALYSIS_5000.md) | Phase 4 組件樹 metadata |
| 2018 講座 | [REF_ANALYSIS_2018.md](computer:///sessions/friendly-dreamy-noether/mnt/stroke_order/REF_ANALYSIS_2018.md) | Phase 4 部首分類 metadata |
| 2025 MOE | [REF_ANALYSIS_MOE.md](computer:///sessions/friendly-dreamy-noether/mnt/stroke_order/REF_ANALYSIS_MOE.md) | 官方基準 + 4808 常用字表 + 17 規則驗證 |
| **g0v JSON** | **本文** | **Phase 1 主輸入** |

**Phase 1 MVP 範圍定稿，等你說「開始動工」。**
