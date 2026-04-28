# Spinoff 衍生專案

> 這份文件記錄所有「**建立在 stroke-order 基礎設施上、但獨立發展的下游產品**」的想法。
>
> Spinoffs ≠ Phases。Phases 是 stroke-order 主 repo 內的功能演進；Spinoffs 是另開新 repo / 另起爐灶的衍生產品，跟 stroke-order 透過資料 / API 介面解耦。
>
> 這份文件本身是 **想法的活倉庫**，不代表會全部執行。每個 idea 都標明「狀態」「觸發條件」「相依性」——當條件成熟時再正式啟動。
>
> 最後更新：2026-04-28

---

## 命名 / 狀態 / 解讀

| 狀態 | 意義 |
|---|---|
| 💭 想法 | 概念階段，沒寫過任何 code，可能不會做 |
| 📐 設計中 | 已有完整架構草圖，等觸發條件 |
| 🚧 動工 | 已開新 repo / 開始實作 |
| ✅ 發布 | 公開可用 |
| 🪦 凍結 | 嘗試後決定不繼續，留紀錄當教訓 |

---

## 1. tinyhanzi — 嵌入式中文字庫

**狀態**：💭 想法（2026-04-28）

### 一句話定位

把 stroke-order 的組件資料壓縮成嵌入式可用的 binary blob，~40 KB 涵蓋 4,808 字，含軌跡資料可直接餵嵌入式寫字機器人。

### 為什麼存在

朱邦復 1976 年為 8 位元微電腦資源限制設計組件化字庫，提出「字根 + 變形規則」哲學，但 runtime 沒有完整落地。

50 年後的 2026 年，ESP32 / Arduino 等嵌入式晶片面對的是相同比例的資源困境：晶片絕對容量增加但中文字型也膨脹，相對占用比例沒變。現有方案不外乎：
- 各專案自己抽 subset（每次重做、零 reuse）
- 內建有限子集字庫（LVGL / u8g2，~1000 字）
- 用 16×16 bitmap 6,000 字（~192 KB，邊緣可接受）

**tinyhanzi 的差異化**：用組件化壓縮做到 ~40 KB / 4,808 字（4-5x 壓縮），並天然帶軌跡資料（pen plotter / 寫字機器人直接可用）。

### 技術架構草圖

四層分明：

```
Layer 1（離線 build pipeline，Python）
  ↓ 讀 stroke-order 的 components 套件
  ↓ 組件 polyline 量化（8-bit coords × N points）
  ↓ 字 → composition entries 表格壓縮
  ↓ 產出 .h / .c blob

Layer 2（嵌入式 C runtime，~3-5 KB code）
  void tinyhanzi_render(uint16_t codepoint, uint8_t* bitmap, int size);
  const tinyhanzi_polyline_t* tinyhanzi_polyline(uint16_t codepoint);

Layer 3（整合 adapter）
  - LVGL: lv_font 介面
  - u8g2: u8g2_DrawHanzi()
  - Adafruit GFX: drawHanzi()

Layer 4（寫字機器人直連，差異化賣點）
  - 直接拿軌跡給 stepper motor
  - LVGL/u8g2 都做不到的事
```

### 數字目標

- **儲存**：~40 KB Flash，涵蓋 4,808 字
- **SRAM 峰值**：~2-3 KB（單字解碼 + 合成）
- **單字解碼速度**：< 5 ms on Arduino Nano（80 MHz ARM Cortex-M0）
- **支援 cover-set**：可選 cjk_common_808 / educational_4808 / wuqian_5000

### 觸發條件（什麼時候動工）

- ✅ stroke-order Phase B 完成（組件級 PSD 切割成熟）
- ✅ 個人實際 ESP32 / Arduino 專案需要中文時（dogfooding）
- ✅ 有人主動詢問「你的字庫能用在我的 ESP32 嗎」（社群需求驗證）
- ✅ 半年到一年後

**目前不動工的理由**：stroke-order 主線還在 Phase A 收尾，組件級資料還沒走過完整生命週期，現在抽出來會 premature optimization。

### 相依性

- **必要**：stroke-order Phase A（已完成 ✅）的 components 套件 + 3 cover-sets
- **強烈建議**：stroke-order Phase B（組件級 PSD 切割）完成 — 才有真實使用者軌跡可選擇性使用
- **license check**：cjkvi-ids（CC BY-SA 3.0）+ KanjiVG（CC BY-SA 3.0）+ TCS 808（公共領域）的衍生組合是否能商業使用 / 嵌入式分發

### 開放問題

- **量化精度 vs 視覺品質**：8-bit coords 對小字夠不夠？需要實際測試
- **位置變形規則的硬編碼成本**：組件在不同位置（左/右/上/下/獨立）視覺差異多大？需要多套變體？
- **字級擴展性**：4,808 → 7,000 → 13,500 字的成本曲線（資料量是線性還是次線性？）
- **跟 LVGL/u8g2 的 license 相容性**：MIT / Apache 嵌入式 lib 可否引用 CC BY-SA 衍生資料

### 跟 stroke-order 的關係

```
stroke-order (web service)              tinyhanzi (embedded)
├── components/  (Layer 1 標註)    →    binary blob 來源
├── 5d PSD     (Layer 2 個人風格)  →    可選的「個人字型 mode」
└── Phase C   (Layer 3 組合引擎)   →    runtime 演算法參考
```

兩個 repo 各自獨立，但 tinyhanzi 透過引用 stroke-order 當資料源。**不重做 cover-set 整理（遵守 PROJECT_PLAYBOOK §六 audit checklist）。**

### 「歷史閉環」這個故事

如果未來真的做了 tinyhanzi，README 開場應該講這段：

> 1976 年，朱邦復為了讓中文字能在記憶體只有幾 KB 的 8 位元微電腦上顯示，提出「組件化字庫」哲學——把字根當基本單位，用變形規則組合出每個字。明珠字庫是這個哲學的部分實作。
>
> 50 年後的今天，ESP32 / Arduino 等嵌入式晶片資源依然受限。LVGL、u8g2 等主流嵌入式 GUI 框架仍然只內建幾百個有限的中文字。tinyhanzi 把朱邦復當年的願景，用 2026 年的工具鏈完成最後一哩路。

這個歷史敘事比任何技術描述都有說服力。

---

## 2. Service Worker offline mode

**狀態**：💭 想法（2026-04-28，技術簡單但價值高）

### 一句話定位

讓 `https://stroke-order.onrender.com/handwriting` 在使用者第一次連線後**完全離線可用**——適合通勤 / 教室 / 不穩網路場景。

### 為什麼存在

當前架構每個字都要 fetch 一次 reference + character data。低階手機 / 慢網路體驗很糟。Service Worker + IndexedDB 解決：第一次連線下載 + cache → 後續零網路。

### 技術範圍（小）

- 註冊 SW，攔截 `/api/character/*` + `/api/handwriting/reference/*` 請求
- Cache-first 策略：有 cache 直接回，沒 cache 才 fetch + 寫入 cache
- SW lifecycle：版本號控制 cache 失效
- 預載常用字（5d 第一次選中的 cover-set 全載）

### 數字目標

- 第一次連線：~5-10 MB 預載（808 字 cover-set）
- 第二次起：零網路、瞬時載入
- cache 大小上限：~50 MB（dirty browser cache 自然 evict）

### 觸發條件

- ✅ 想要離線使用 stroke-order 的時候
- ✅ 看到 Render free tier cold start 太煩，想跳過後端
- ✅ 1-2 週可做完，技術門檻低

**這是當前架構唯一的「短期負債清償」spinoff**——可以排在 Phase B 之前先做。

### 相依性

- 無——當前架構直接套用即可
- 順帶要：HTTP `Cache-Control` headers 加上去

### 開放問題

- SW 跟 5d IndexedDB 的儲存衝突？應該不會，但要驗
- Render 部署環境支援 SW（HTTPS 是 must）— 已 OK
- 預載哪個 cover-set？應該讓使用者選，但 default 該是哪個

---

## 3. 組件 glyph cache 分發（網路端）

**狀態**：💭 想法（2026-04-28）

### 一句話定位

把字 SVG 拆成組件級 SVG，讓跨字 / 跨字體共用組件 glyph，cache hit rate 大幅上升。

### 為什麼存在

現在 char `明` 的 reference glyph 跟 `明亮` 的 reference glyph 是完全獨立資產。但他們的 `日` 組件其實可以共用——浪費 50% 流量。

組件化分發後：
- 200 個獨特組件 glyph，瀏覽器 cache 完
- 每個新字只需要 ~30 bytes 的「composition spec」（IDS + 組件位置）
- 換字體（楷 → 隸）只需要 fetch 新組件 set，不需要每字重抓

### 跟 tinyhanzi 的差異

- **tinyhanzi**：嵌入式 binary blob，offline，C runtime
- **組件 glyph cache**：HTTP SVG 分發，online + cached，JS runtime

兩者共用組件資料庫，但表現方式不同。tinyhanzi 是「**離線最小化**」，組件 cache 是「**線上動態合成**」。

### 觸發條件

- ✅ stroke-order Phase C「組合引擎」啟動（這是它的網路端對偶面）
- ✅ 看到實際流量瓶頸時（目前個人專案沒這壓力）
- ✅ 要做 PWA / 行動友善時

### 相依性

- 必要：stroke-order Phase B + Phase C
- 強烈建議：先做 #2 Service Worker（簡單版本）累積經驗

### 開放問題

- 組件 SVG 的位置變形規則（組件在不同位置 visual 不同）
- 如何 client-side 即時合成 + 跟 hanzi-writer 動畫整合

---

## 4. 罕字 OS 字型相容性警告 UI

**狀態**：💭 想法（2026-04-28）

### 一句話定位

當使用者在 5d 寫一個 bentu_6792 附表內的罕字時，依該字的 OS 字型支援資料，主動警告「你的瀏覽器字型可能渲染不出來」。

### 為什麼存在

bentu_6792 已經帶有 550 個冷僻字的 OS support flags（MS 新細明 / 微軟正黑、Google 思源、Apple 蘋方各自支不支援）。這份 metadata 不利用浪費。具體場景：

- 使用者在 MacBook 寫客語字 𰣻（U+308FB），瀏覽器渲染不出 → 不知道是 bug 還是字型問題
- 系統依使用者 user-agent 判斷 OS，查 metadata，主動顯示「⚠️ 此字 macOS 蘋方不支援，可能顯示為豆腐方塊」

### 技術範圍（極小）

- 用 `navigator.userAgent` 偵測 OS
- 接 `/api/components/{char}` 時順帶查 cover-set 的 entries 是否含 os_support
- UI 加一個 banner / tooltip

### 觸發條件

- 有使用者反映「寫 bentu cover-set 時某字看不到」
- 或主動為 5d UI 加品質提示

### 相依性

- bentu_6792 cover-set ✅ 已完成
- 1-2 天工作量

---

## 5. KAGE outline 整合

**狀態**：💭 想法（2026-04-28，可能性最遠）

### 一句話定位

把 stroke-order 的軌跡資料 + 日本 GlyphWiki / KAGE 的輪廓 (outline) 資料做 cross-reference，互相補強。

### 為什麼存在

KAGE 引擎已經跑 20 年，累積了完整的漢字 outline + 組合系統，但只給 outline 不給軌跡。stroke-order 給軌跡但 outline 較弱。兩者結合：
- 罕用字 outline → KAGE
- 罕用字軌跡 → stroke-order 的組件合成
- 標準字 outline + 軌跡都有 → 雙源 cross-validate

### 觸發條件

- ✅ stroke-order Phase D（神經組合）啟動，需要更多 ground truth 資料
- ✅ 跟日本研究者 / GlyphWiki 社群有合作機會
- ✅ 學術論文需要

### 相依性

- KAGE / GlyphWiki API（需確認外部 dependency 穩定性）
- 跨語系字符集對齊（TW vs JP 漢字差異）

### 開放問題

- KAGE 跟 cjkvi-ids 在 IDS 概念上有 overlap，誰是 source of truth？
- License 相容性（KAGE 是 GPLv3，stroke-order 是 MIT）

---

## Spinoff 觸發決策框架

當你考慮「要不要啟動某個 spinoff」時，問自己：

1. **stroke-order 主線該做的事都做完了嗎？** 沒做完 → 別分心
2. **有實際使用者拉力嗎？** 沒人問 → 自己用得到嗎？dogfooding 也算
3. **資料 / 基礎設施依賴都成熟了嗎？** 缺什麼 → 先把 stroke-order 那邊補完
4. **新 repo 的維護成本承擔得起嗎？** 你已經 4 個 active repo，再加一個 ok 嗎？

這四題全 yes 才動工。否則維持 💭 想法 狀態，等下次重新評估。

---

---

## 6. 待整合資料源 Backlog

當前 stroke-order 在 uploads/ 累積了豐富的 Taiwan-first / 漢字研究資料源，已 audit 但尚未整合進 codebase。下次工作日依優先序挑選實作。

### Group A：字頻 / 字單（cover-set 候選）

| 資料源 | 內容 | 規模 | 估時 | 優先 | 主要挑戰 |
|---|---|---|---|---|---|
| `shrest1.zip → SHREST1.DBF` | 國小學童 字頻總表（民國 91 年/2002）| 5,021 字 + 頻次百分比 + 辭典標記 | 2-3 hr | **高** | 48 個 Big5-ETEN PUA 異體字需 CNS 對照表回推 Unicode |
| `shrest2.zip → shrest2.dbf` | 詞頻總表 | 46,666 詞 / 757,632 次 | 1-2 hr | 中 | 詞層 vs 字層的整合策略（不直接對應 cover-set，但對推薦排序有用）|
| `result.zip` | 整套小學調查報告（shrest1-24 合輯） | 全 study | — | 低 | shrest1/2 是其精華，其餘是統計補表 |

**整合方向**：字頻資料 → 推薦演算法的 secondary tiebreak（同樣 component gain 時優先推薦真實高頻字）+ 第 5 個 cover-set `moe_elementary_5021`。

### Group B：教育部 / 全字庫 字型（reference glyph 來源）

| 資料源 | 內容 | 用途 |
|---|---|---|
| `edukai-5.1_20251208.ttf` | 教育部楷書 5.1（2025 最新） | 5d UI 楷書 reference |
| `edusong-big5.ttf` / `edusong_Unicode.ttf` | 教育部宋體 | 5d UI 宋體 reference |
| `MoeLI(隸書3.0版1080724上網).ttf` | 教育部隸書 3.0 | 改善現有隸書 fallback（取代 chongxi_seal 的隸書借用）|
| `Fonts_Kai.zip` | TW-Kai-98 + Ext-B + Plus（全字庫楷體完整版）| 罕字 reference 補強 |
| `Fonts_Sung.zip` | TW-Sung 同上 | 罕字宋體 |
| `chongxi_seal.otf` ✅ | 崇羲篆體（已用） | 篆書 reference |

**整合方向**：取代 / 補強現有 g0v + MMH fallback chain，特別是 4808 之外的罕字。

### Group C：CNS 全字庫屬性表（rich metadata）

| 資料源 | 內容 | 用途 |
|---|---|---|
| `Properties.zip → CNS_cangjie.txt` | 倉頡碼對照 | 輸入法整合 / spinoff 候選 |
| `Properties.zip → CNS_component.txt` | 字根分解 | 跟 cjkvi-ids 交叉驗證 Phase A 組件資料 |
| `Properties.zip → CNS_phonetic.txt` | 聲符 | 形聲字推論基礎 |
| `Properties.zip → CNS_radical.txt` | 部首 | 跟現有 radicals.py 交叉驗證 |
| `Properties.zip → CNS_stroke.txt` | 筆畫數 | metadata 補強 |
| `Properties.zip → CNS_strokes_sequence.txt` | 筆順 | g0v / 教育部筆順的官方對照 |
| `MapingTables.zip` | Big5 ↔ CNS ↔ Unicode | **解決 Group A 的 48 異體字必備工具** |

**整合方向**：Phase A 的 Layer 1 標註層升級——把 cjkvi-ids 跟 CNS 全字庫 cross-ref，Taiwan-variant integrity 升級到「雙源驗證」。

### Group D：倉頡 / 異體字輸入法系統

| 資料源 | 內容 | 用途 |
|---|---|---|
| `mdfont.zip → USRFONT.15M` | 16x16 bitmap 字檔（PUA 異體字） | tinyhanzi 嵌入式字庫的歷史參考實作 |
| `mdfont.zip → USRFONT.24M` | 24x24 bitmap 字檔 | 同上 |
| `mdfont.zip → XUSRCJ.TBL` | 異體字倉頡碼表 | 解碼 SHREST1 的 48 PUA 異體字身分 |
| `mdfont.zip → diction.tte` | 字典 TTE 檔 | （格式不明，需研究）|

**整合方向**：跟 `tinyhanzi` spinoff 緊密關聯——這 2 個 bitmap 檔正是「**朱邦復明珠字庫的當代實作參考**」。tinyhanzi 啟動時必看。

### Group E：朱邦復遺產 / 漢字基因相關

| 資料源 | 內容 | 歷史價值 |
|---|---|---|
| `hanzijiyin2018.zip` | 朱邦復《漢字基因講座》100+ 篇 .doc 講義 | 哲學文獻，VISION.md 引用基底 |
| `5000.zip` | 5000 字 BMP 圖檔（每個字根 134 byte） | 朱邦復原版字根樣本 |
| `6063png.zip` | 6063 個漢字 PNG 圖檔（含一些 CJK Ext A） | 字形視覺資料庫 |
| `ebkman075.zip` | DOS-era 字典管理員 installer (2002) | 歷史封存（不執行）|
| `fontdata2010-new.zip` | 朱邦復字型 ASM 原始碼（DOS 16x16）| **直接對應 tinyhanzi 設計**——50 年前他怎麼壓縮的範本 |
| `scg.zip` / `scg_yang.zip` | SCG (Stroke Char Generator) ASM 原始碼 | 同上，組件化字型生成的原型 |
| `testfont2010.zip` | DOS 字型測試 .EXE | 歷史測試工具，不執行 |

**整合方向**：tinyhanzi spinoff 的**靈感原型**——朱邦復當年的 ASM 實作直接證明「組件壓縮可以做到 8 位元微電腦記憶體尺度」。研讀後再回頭設計現代版。

---

### 整合優先序建議

依「ROI = 對主線價值 / 工作量」排序：

1. **🔥 Group C MapingTables**（高 ROI）：解 Group A 的 48 異體字 + Phase A Taiwan-variant integrity 雙源驗證——~2-3 hr
2. **Group A SHREST1**（高 ROI，有 Group C 加持後）：第 5 個 cover-set `moe_elementary_5021` ranked by 真實 frequency——~1-2 hr 補完
3. **Group B 字型** （中 ROI）：教育部 ttf 直接整合進 g0v fallback chain——~30 min/font
4. **Group C CNS_strokes_sequence**（中 ROI）：跟現有筆順資料 cross-ref，找出官方最新版本與 g0v 的差異——~2 hr
5. **Group D mdfont**（待 tinyhanzi 啟動才有意義）：留給 tinyhanzi spinoff 參考
6. **Group E 漢字基因** （低 ROI 但高史料價值）：tinyhanzi README 寫故事時引用 + VISION.md §三 補充

---

## 修訂歷史

- 2026-04-28：初版。記錄 4 個 spinoff（tinyhanzi、Service Worker offline、組件 glyph cache、KAGE 整合）。
- 2026-04-28（同日修訂）：加 spinoff #4「罕字 OS 字型相容性警告」（基於 bentu_6792 的 OS support metadata）。
- 2026-04-28（同日深夜修訂）：新增 §六「待整合資料源 Backlog」，catalog 今日累積的 Group A-E 五大類資料源（字頻 DBF、教育部 ttf 字型、CNS 全字庫屬性表、倉頡異體字 bitmap 字檔、朱邦復漢字基因系列）+ 整合優先序建議。
- (未來新 spinoff / 狀態變更在此記錄)
