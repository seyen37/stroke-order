# 2026-05-01 — 印章模組業界規範對齊（Phase 12b）

<!-- retrofit 2026-05-02：原檔名 2026-05-03_stamp_industry_alignment.md，內部日期 5-03。git commit 5-01 17:53 (+0800)，align commit date 後重命名。 -->

> User 上傳 8 張業界範例圖驅動，整理出印章規格的 8 級制 / 字數對應排列 / 字體 / 印面類型四個維度。對照 stroke-order 現況決定 Phase 12b/c/d/e 路線；本次完成 12b（8 級尺寸 quick-pick + 警示 + PDF 下載 + 兩輪 bug fix）。

## 業界規範彙總

8 張範例圖（豬豬小姐 / 吉祥刻印 / 無上印鋪 / 傳家手工 / 好福印 / 隆興印章 + 兩張字體範例）共識整理：

### A. 印面尺寸 — 8 級制（方/圓共用）

| 規格 | 邊長/直徑 | 業界主流字數 | 主要用途 |
|---|---|---|---|
| 公分 | 1.0 cm | 1-2 字 | 小型私章 |
| **4 分** | **1.2 cm** | 1-3 字 | **個人姓名章（最常見）** |
| 5 分 | 1.5 cm | 2-4 字 | 個人姓名章 |
| 6 分 | 1.8 cm | 2-4 字 | 負責人章 / 中型 |
| 7 分 | 2.1 cm | 2-5 字 | 大姓名章 |
| **8 分** | **2.4 cm** | 4-9 字 | **公司章（標準）** |
| 9 分 | 2.7 cm | 4-9 字 | 公司章 |
| **1 寸** | **3.0 cm** | 4-9 字 | **公司章（最大）** |

### B. 字體（業界 6 種）

正楷 / 隸書 / 仿宋 / 毛楷 / 毛行 / 篆字。

stroke-order 目前 5 種（楷 / 宋體 / 隸 / 粗楷濾鏡 / 篆書），缺毛楷與毛行 → Phase 12e backlog。

### C. 排列規則

- **1 字**：粗體置中
- **2 字**：上下 或 左右
- **3 字**：1+2 layout（右大姓拉長 + 左 2 字堆疊）
- **4 字**：2×2
- **5-9 字**：右行為主直書多列

### D. 兩個 stroke-order 缺的維度

- **陽刻**（朱文，字凸出）vs **陰刻**（白文，字凹下）—— 業界都常見，stroke-order 只有陰刻 → Phase 12c
- **小尺寸警示**：「< 1.5cm + 多筆劃字」會相連，業界明文提示

## 對照與路線

| Phase | 範圍 | 狀態 |
|---|---|---|
| **12b** | 8 級 quick-pick + 警示 + PDF + 字數推薦 + 2 輪 bug fix | **本次完成** |
| 12c | 陽刻支援（SVG + G-code + PDF + UI） | 下一步 |
| 12d | 1 字 preset 驗證 / 微調 | 12c 之後 |
| 12e | 毛楷 / 毛行字體；5 字非均勻佈局 | 長期 backlog |

User 確認目標使用者是「自己用雷射雕刻機 + 多人預先編輯協作」，因此尺寸應**嚴格對齊業界 8 級制**（不是隨意尺寸）。

## 七個 12b 設計決策

### 決策 1：8 級尺寸用 dropdown 而非 chip

**選項**：
| 選項 | 描述 |
|---|---|
| A | dropdown select（單行緊湊） ✅ |
| B | chip 8 個按鈕（視覺直觀但占空間） |
| C | 下拉 + chip 並列（冗餘） |

**選 A**：印章面板已經很多 row，dropdown 最節省空間 + 業界尺寸不需要視覺輔助記憶（4 分 / 8 分 / 1 寸 是用戶熟悉名詞）。

### 決策 2：手動改 w/h 自動切「自訂尺寸」（雙向 sync）

**為什麼**：
- 防止 UI 顯示不一致（quick-pick 顯示 4 分但 w/h 是 13）
- 如果 user 從別處改回 8 級值（例如把 13 改成 12），quick-pick 自動跳到對應 option

**陷阱避免**：方/圓共用同一個 quick-pick → 圓章的「直徑」也走 w/h（圓章只用 w 但 stamp.py 設計成 w==h）。

### 決策 3：char_size_mm 從 force size 改成 cap

**Bug 起因**：11g 改 bbox-based scale 後，char_size_mm 直接撐滿，4 字 cell 4mm + char_size 5/10mm 就嚴重重疊。

**選項**：
| 選項 | 描述 | 缺點 |
|---|---|---|
| A | 完全忽略 char_size_mm，cell-based 自動撐滿 | user 失去字大小控制 |
| B | char_size_mm 當 cap：`min(cell, char_size_mm)` ✅ | 語意改變需 UI 同步 |
| C | warn 但允許超出 | UX 不友善 |

**選 B**：保留 user control（想字小一點），但加上「不超出 cell」安全網。UI label 改「字大小上限」+ tooltip 說明語意。

### 決策 4：char_size_mm = 0 = 完全撐滿 cell

允許 `char_size_mm = 0`（min 從 2 改 0），這時 cap 邏輯回退到「直接用 cell_size」。**語意一致性**：0 = 「不限制」 = 「字撐滿」。

### 決策 5：border_padding_mm 預設 2.0 → 0.8

**根據**：業界小章（4-7 分）inset 約 0.5-1.0 mm；過去 2.0 是公司章（8 分以上）規格。

**為什麼不做 dynamic ratio**（如 padding = width × 0.05）：
- 簡單性：固定 default 比 dynamic 容易理解
- user 可以手動微調（input 還在）
- 大章（24mm 以上）影響輕微（inner 從 20 → 22.4 只 +12%）

**陷阱避免**：影響 7 處 default 同步（server.py × 3 + stamp.py × 4 + index.html × 1），用 sed 批次改，grep 驗證沒漏。

### 決策 6：cell 內留 8% padding（CELL_FILL_RATIO = 0.92）

**為什麼 0.92 而不是 0.85 或 0.95**：
- 0.95 太貼，視覺上仍然像碰邊
- 0.85 太空，4 字章面積使用率不夠
- 0.92 = 留 8% 約是業界印章字距（中央 4mm 字身配 0.16mm 左右間距），視覺最自然

**為什麼只在 square_name n=1/2/4，不在 3 字 1+2 layout**：
- 3 字 1+2 layout 已經有 `inner_h * 0.92` 比例
- 重複套會讓 3 字字身更小，回退視覺空間

### 決策 7：PDF 用 cairosvg svg2pdf 直出（不走 sutra 路線）

| 路線 | 用於 | 原因 |
|---|---|---|
| `cairosvg.svg2pdf()` | **印章** ✅ | 單頁、向量、雷射雕刻機需保留向量資訊 |
| `cairosvg.svg2png()` + Pillow 合併 | 抄經（sutra） | 多頁、要 dpi 控制、PNG flatten 解透明背景 |

**好處**：
- 檔案小（5 KB）
- 雷射雕刻機 / 印刷廠軟體可解出原向量
- 列印任何尺寸都清晰

## 兩輪 bug fix 教訓

### 11g 改動暴露 inner_w 計算舊 bug

11g 改 bbox-based scale 之前，char_size_mm 污染 inner_w 的 bug 因為 EM-based scale 字身有自然 padding 而不顯眼。11g 之後 bbox 撐滿，bug 立刻可見。

**抽象原則候選**：「**底層改動會暴露上層舊 bug**」。重要 base infra 改動後（特別是 scale / coordinate 之類的），要主動 audit 整條 pipeline 而不只看「直接相關範圍」。

### 一個變數散布在 7 處 default

`border_padding_mm = 2.0` 散布在 7 處：3 個 server endpoint + 4 個 stamp.py 函數 default + 1 個 HTML input value。本次同步改是手動 sed + grep 驗證，但任何一處遺漏就會造成 default 不一致。

**抽象原則候選**：「**Single source of truth for defaults**」。candidates：
- Python：`stamp.py` 頂端 `DEFAULTS = {...}` 然後 import
- Pydantic Field 跟 `Query()` 都從 module-level constant 讀

本次沒重構是 effort/value 不對等（grep 找得齊、改動完成），但 debt 列入 backlog，下次有類似改動時順手做。

## 教訓沉澱建議

兩條原則建議寫進 personal-playbook。等 §8.8 之後的下次 sync 時加。

### 候選 §8.9：底層改動 → 整條 pipeline audit

**規則**：scale / coordinate / EM / bbox 等基礎座標系統的改動，視為高風險改動。不只看「直接相關功能是否正確」，還要 audit：
- 所有用同類座標的 caller
- 所有 default 值合理性
- 所有 cap / floor / clamp 是否仍合理
- UX 上「user 看到的數字」是否還對應預期意義

**反例**：11g 改 bbox-scale，只看了 stamp 預覽是否撐滿，沒 audit 「char_size_mm + 1/2/4 字情境」「inner_w 計算 max() 副作用」「border_padding 預設值在新 scale 下是否合理」三個衍生問題。

### 候選 §8.10：Default 值 single source of truth

**規則**：超過一處出現的 default 值（`x = N`）在 codebase 內，要改 named constant 並 import。grep 看到 3 處以上的 magic number 即觸發重構。

**驗證**：對既有 codebase 跑 `grep -rE "= [0-9]" src/` 找出 magic number top 10，挑出散布超過 3 處的列入 backlog。

## 後續 — Phase 12c 陽刻支援高層 spec

### 概念

| 模式 | 視覺 | SVG | G-code |
|---|---|---|---|
| **陰刻**（現況） | 字凹下、白底紅字描邊 | 字 outline 用 stroke | 雷射沿字筆劃路徑 |
| **陽刻**（新增） | 字凸出、紅底白字 | 字 outline 用 fill + 邊框內倒填色（even-odd） | 雷射光柵掃描鋪滿背景，字保留不雕 |

### 工程拆解

| 子任務 | 影響 | 風險 |
|---|---|---|
| 12c-1 後端 `engrave_mode` 參數 | stamp.py + patch.py（抄經印章區） | 低 |
| 12c-2 SVG 陽刻渲染（fill + even-odd） | exporters/svg.py 加 mode 支援 | 低-中 |
| 12c-3 G-code 陽刻路徑（hatching / raster fill） | exporters/gcode.py 新增 fill 演算法 | **最大** |
| 12c-4 UI radio「陰刻 / 陽刻」 + 預覽顏色 | index.html 印章面板 | 低 |
| 12c-5 PDF 抄經印章區同步支援 | sutra exporters 印章 hook | 低 |

### 12c-3 G-code 陽刻路徑要先 prototype

最大風險 + 最大不確定性：「印章邊框內 - 字 outline = 鋪滿區域」的光柵掃描路徑生成。

可能演算法：
1. **Scanline filling**：水平掃描線，每條線跟字 outline 求交，產生 segments，雷射沿這些 segments 走（傳統 plotter rasterization）
2. **Boustrophedon path planning**：之字形掃描，每行反向，減少空跑時間
3. **Concentric infill**：從邊框往內等距內縮，類似 3D printing infill

需要動工前 prototype 驗證可行性 → 寫進 12c-3 的 task spec。

## 相關 commits

- `b24c7ce` feat(stamp): 8 級尺寸 quick-pick + 警示 + PDF 下載
- `9e427fa` feat(stamp): 8 級尺寸 quick-pick + 小尺寸警示 + 字數推薦尺寸
- `4c29ee0` fix(stamp): 4 字字重疊 + char_size_mm 污染 inner 兩 bug
- `ddc8acc` fix(stamp): 字到外框留白過大 + 4 字 cell 互碰邊

## 版本

pyproject.toml: 0.14.2 → 0.14.5（連 3 個 patch bump）
Render deploy: 6 次自動 redeploy 全綠

待補：v0.14.5 annotated git tag。
