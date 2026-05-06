# Phase 6z 禪繞字 Design Doc — Zentangle Embedded Hanzi Mode

**日期**：2026-05-06
**版本**：design-v0.1（待 user Approval 後動工 6z-1 implementation）
**範圍**：禪繞字模式 — 漢字 outline + 內部禪繞畫填充 + 紙磚旋轉 + ICSO 元素重複疊加 + 草稿系統 + gallery 整合

> 🔗 **上層 thesis**：
> - personal-playbook §0.4「重新框架問題 > 答問題（plan-first 升級）」 — 本 design doc 是該 thesis 的工程實作（先 frame 對問題，再動 code）
> - personal-playbook §0.1「AI 不是能力不夠、是紀律不夠」 — design doc 是「紀律」 instantiation
> - stroke-order PRINCIPLES.md §6.1 大 phase 必先寫 design doc

---

## 0. Executive Summary

**Phase 6z 是「禪繞重複疊加減負工具」**，不是「禪繞數位畫板」。

| Aspect | 數位畫板（非 thesis）| **重複疊加減負工具 (thesis)** ★ |
|---|---|---|
| 核心價值 | 提供畫筆 | 減少 user 重複勞動 |
| 主要 UI | toolbar of brushes | **9 cell 疊加 panel** |
| User 期待 | 「我畫得像不像」 | 「我享受重複的節奏」 |
| Product moat | 畫筆精緻度 | 重複 mechanism + 紙磚旋轉 + ICSO 結構 |

**MVP 主流程**：

```
1. User 開新磚 (預設方磚 9cm + 4 角 dot + 細邊框)
2. 選 mode：純禪繞 (char=null) / 空心填充 (char=漢字, fill_mode='inside')
3. 畫 String 暗線（4 templates 或自由）
4. 旋轉紙磚（hybrid: 8 preset + 拖拉）
5. 用 ICSO 工具畫基底 stroke
6. 自動浮現 9 cell 疊加 panel → 選方向/次數/間距 → 重複疊加
7. 重複 5-6 直到滿意
8. 草稿系統：30 步 undo + 單 slot localStorage auto-save
9. 「發布到 gallery」→ 上傳成 kind='zentangle'，**immutable 不可後製**
```

**MVP 不做（defer 到 phase 6z+ / phase 7）**：
- 多字組合（multi-char）
- Background mode (fill_mode='outside')
- 彩色禪繞
- 陰影 + Tortillion 推色
- Image → config 反向解析
- 多 snapshot UI（單 auto slot 在 6z，多 snapshot 在 phase 7）
- 跨 mode snapshot 共用（phase 7）

**估時**：6z-0 design doc 已寫（本檔）+ 6z-1 ~ 6z-8 sub-phases 約 30-40 hours / 1-2 週工作日。

---

## 1. 動機 + 願景

### 1.1 起源

5/6 user 提出新模式構想（之前 phase 5b r28-r29k gallery 完整 ship 後 / phase 6 follow/feed 棄選後）：

> 「主要是，用戶可以選擇一個中文字，預設為「心」，系統呈現的是文字的邊框，而不是中心軌跡，以這個文字邊框為核心，開始繪製纏繞畫文字 ... 採用『紙磚』的形式，繪畫時可以轉動紙磚的角度來配合手的順手程度 ... 也希望未來可以擷取禪繞畫的圖片，生成設定檔」

### 1.2 21 批 user 資料消化結論

跨 4 大主題收齊 21 批 reference：
- 紙磚 規格 / 尺寸 / 形狀
- ICSO 5 元素 + tangle library + 構圖原則
- 哲學 / 儀式 / 學習階段
- UI mechanism (旋轉 / 疊加 / 草稿)

### 1.3 設計哲學調和（重要）

**禪繞「沒有錯誤」 vs user 「回上一步」 工程實用** — 看似衝突，**「草稿模式」精準調和**：

| 階段 | 行為 | 哲學 |
|---|---|---|
| **Draft** | 全功能 undo / snapshot / 隨時可改 | 工程實用主義 |
| **Final / Published** | Immutable，發布即 frozen | 禪繞精神 |

對應寫作（草稿 vs 定稿）/ 攝影（RAW vs 沖洗）。**Schema 必含 `is_draft: bool` boundary**。

### 1.4 Embedded Hanzi 是有 lineage 的官方技法

第 11 + 20 批 user 資料明確：禪繞畫官方有 Embedded Letters 技法（網路搜「Zentangle Name Art」），中文版自然延伸到「禪繞字 (Embedded Hanzi)」。Phase 6z **不是 user 自創概念**，是 Zentangle 社群既有 sub-genre 的中文化 + 數位化。

---

## 2. 8+1 條架構軸 — 全 QODA 決定

每軸 Q-O-D-A 結構，最後 ★ 推薦：

### 2.1 軸 1：字框 (outline) 資料來源

**Q**：漢字 outline 從哪取？

**O**：
- A. 從 TTF/OTF 字型抽（freetype + Pillow `getmask`）
- B. HanziWriter / make_me_a_hanzi dataset 的 outline path
- C. 自家手繪 outline 庫（每字一個 SVG）

**D ★ A**：freetype 抽 outline 是標準做法。MVP 預設 **思源黑體 Bold**（提供寬敞 tangle 空間 + 大字小字統一）。Schema 存 outline polygon 直接，不依賴 runtime 字型。

**A**：✅ 確認

### 2.2 軸 2：MVP modes

**Q**：哪幾種繪畫模式？

**O**：純禪繞 / 空心填充 / 背景鑲嵌 / Monogram / 3D

**D ★** MVP 3 模式：
- **純禪繞** (char=null，整磚自由畫)
- **空心填充型** (char=漢字, fill_mode='inside')
- **背景鑲嵌型** (char=漢字, fill_mode='outside') — 從 phase 6z+1 提前進 MVP（工程小 + 第 12/20 批 2 次出現）

Monogram + 3D defer 到 phase 6z+ 進階。

**A**：✅ 確認

### 2.3 軸 3：MVP tangle 庫數量

**Q**：MVP 內建幾個 tangles？

**O**：3 / 5 / 6 / 全 7+

**D ★ 6 個**，涵蓋 ICSO 完整 + 4 role：

| Tangle | ICSO | Role | Category |
|---|---|---|---|
| **Crescent Moon** | C | focal | geometric |
| **Hollibaugh** | I | structural | geometric |
| **Tipple** | O | filler | geometric |
| **Mooka** | S compound | dynamic | organic |
| **Printemps** | S simple | dynamic | organic |
| **Florz** | I + O 格紋 | structural | geometric |

每個 tangle 帶 metadata：

```yaml
crescent_moon:
  cn: "新月"
  primitives: [C, O, I]
  category: geometric
  role: focal
  difficulty: easy
  steps:
    - "邊界畫塗黑半圓"
    - "沿邊緣畫 aura 弧線"
    - "重複外擴"
    - "自然交錯"
```

**A**：✅ 確認

### 2.4 軸 4a：紙磚旋轉模式

**Q**：自由角度 / preset / hybrid？

**O**：A1 hybrid / A2 純自由 / A3 純 preset

**D ★ A1 Hybrid**：
- 8 preset 按鈕（0/45/90/135/180/225/270/315°）
- 拖拉自由旋轉
- 一鍵還原

```yaml
tile:
  rotation: 45        # degrees, float
```

**A**：✅ 確認

### 2.5 軸 4b：ICSO 疊加座標系統 ⭐ 核心 mechanism

**Q**：Stroke 存 tile-local 還是 world coords？

**D ★ B1 tile-local coords**：是禪繞數位版核心架構。User 在旋轉後 tile 自然下筆，stroke 落在 tile 自己座標系，「stroke 跟著 tile 旋轉」 = 「轉動紙張配合手部」 的數位實現。

```yaml
tile:
  rotation: 45
strokes:
  - {points: [...]}    # tile-local，跟 tile 一起旋轉
```

**Render**：display = `rotate_world(stroke_points, tile.rotation)`。

**A**：✅ 確認

### 2.6 軸 5：填充密度控制

**Q**：density UI 怎設計？

**D ★ C2 一條 density slider**（low / medium / high）。Density 是 perceptual axis，user 直覺；size 跟 spacing 同現象兩面，不需拆兩 slider。

**A**：✅ 確認

### 2.7 軸 6：UI 引導模式

**Q**：分層 wizard / 純自由 / hybrid？

**D ★ C** 自由為主 + 角落 contextual hint + toolbar 視覺順序體現分層流程：

```
左→右 toolbar:
  ✏️ 暗線 (String) → 🟫 黑描邊 → 🎨 tangle 元素 → ⬛ 填黑 → 🔄 紙磚旋轉
```

第一次開磚帶 1 行小提示 + ✕ 關閉。**不彈窗、不打斷**（呼應第 13 批哲學的 Flow 狀態）。

**「大元素切空白 → 小元素遞迴填」核心機制**：MVP user 純手動，phase 6z+1 加 auto-detect empty region 計算 + size suggest（不 hard disable）。

**A**：✅ 確認

### 2.8 軸 7：元素尺寸設計

**Q**：尺寸 UI + 智慧 disable？

**D ★** 5 預設按鈕 + 微調 slider：

```
Size: ⚪ XS (14) · ⚪ S (24) · ⚪ M (40) ★ · ⚪ L (60) · ⚪ XL (90)
微調 slider: 10-120px
```

**Hard disable 過大按鈕**：MVP **不做**（呼應「沒有錯誤」精神）。phase 6z+1 加「建議尺寸高亮」（dim 過大但仍可選）。

**A**：✅ 確認

### 2.9 軸 8：File format schema

**Q**：file 格式 schema 設計？

**D ★** YAML frontmatter + body（仿 r27 .mandala.md pattern）：

```yaml
---
title: "心 - 我的禪繞字"
author: "user.display_name"
schema_version: 1
mode: 'pure' | 'embedded'
chars: ["心"] | []                 # MVP 單字 array，預留多字延伸
fill_mode: 'inside' | 'outside'    # MVP 兩個都做
tile:
  shape: 'square'                   # MVP only
  size_mm: 90                       # internal mm
  display_unit: 'cm'                 # UI 偏好
  rotation: 0                       # 當前角度（deg）
character:                           # mode='embedded' 時填
  outline: [polygon_points...]      # 字框 polygon
  font: 'NotoSansTC-Bold'           # 抽 outline 用的字型
fill_strategy:
  density: 'medium'                  # low/medium/high
strokes:
  # String 暗線
  - {id: ..., type: line, layer: guide, points: [...]}
  
  # 基底元素 (ICSO)
  - id: "stroke_001"
    type: line | curve | s_shape | orb | dot
    layer: final
    points: [...]
    size: 40
    rotation: 45                    # tile-local angle
  
  # 重複疊加（展開為個別 stroke）
  - id: "stroke_002"
    parent_id: "stroke_001"
    repeat_meta: {direction: 'E', index: 1, spacing: 2}
    type: line
    layer: final
    points: [...]
  
  # Tangle 填充
  - {id: ..., type: fill, layer: final, region: [...]}

shadows: []                          # MVP 始終空，schema 預留
draft_meta:
  is_draft: true                     # true=draft / false=published
created_at: ...
updated_at: ...
---

# Optional human-readable body（仿 r27 mandala body）
[draft 模式可放 user notes]
```

**A**：✅ 確認

### 2.10 軸 9：9 cell 重複疊加 panel ⭐ 核心 UX

**Q**：怎用按鈕減負 user 重複手繪？

**D ★** 完整 UI spec：

```
User 畫基底 stroke → 自動 detect → 浮現 panel：

   ┌───┬───┬───┐
   │ ↖ │ ↑ │ ↗ │   8 方向疊加按鈕
   ├───┼───┼───┤
   │ ← │ ⊙ │ → │   ⊙ = 預覽 toggle / 確認
   ├───┼───┼───┤
   │ ↙ │ ↓ │ ↘ │
   └───┴───┴───┘

Side Controls:
   ▶ 疊加次數: [▼1▲]  快選 1 · 3 · 5 · 8 · 12
   ▶ 間距 (mm):  [▼1▲] 快選 1 · 2 · 3 · 5 · 8
   [✓ 確認] [✗ 取消] [🔁 填滿空白]
```

**「填滿空白」 mechanism**：raycast 從 base stroke 沿選定方向到「邊界」（character outline / 紙磚邊 / 既有 stroke 的最近一條），算 count = floor(D/spacing)，自動套用。撞到任一邊界 → preview 截斷 + 顯示「✓ 已填滿至邊界」綠 badge。

**「次數/間距 預設值」 vs user「待驗證」 spec**：
- MVP 做 **A 預設快選按鈕** (1/3/5/8/12 次, 1/2/3/5/8 mm)
- MVP 做 **B 簡化版「填滿空白」** raycast
- C 智慧 adaptive **defer** 到 phase 6z+1 待真實使用驗證後 iterate

**Schema impact**：每個 repeat 寫成獨立 stroke 帶 `parent_id` + `repeat_meta`（展開存而非 compact），file size 略大但 render 簡單 + import 直觀。

**A**：✅ 確認

### 2.11 軸 10：草稿 vs 定稿 (draft mode)

**Q**：怎調和「沒有錯誤」 vs user 「undo」 衝突？

**D ★** 兩 phase 模型（見 §1.3）。`draft_meta.is_draft` 必填。

**Undo 設計**：
- Bounded **30 步**（畫筆動作 only）
- `Ctrl+Z` undo / `Ctrl+Shift+Z` redo
- 旋轉紙磚 / size 變更**不算 undo step**（避免污染 stack）

**Auto-save**：
- MVP **單 slot localStorage** auto-save
- 每 5 分鐘 / 每 20 strokes 觸發
- 重開 app 自動 prompt「恢復上次草稿？」

**Snapshot system**（phase 7）：
- IndexedDB 8-slot system
- 3 auto rolling FIFO + 5 manual named
- 跨 mode 共享 module（zentangle / mandala / PSD）

**A**：✅ 確認

### 2.12 軸 11：本機下載檔名

**Q**：避免重複下載覆蓋？

**D ★** Timestamp suffix：

```
<title>_<YYYY-MM-DD>_<HHMM>.<mode>.md

範例:
  心_2026-05-06_1234.zentangle.md
```

File-System Access API 支援 Save As dialog → user 可改名。Fallback `<a download>` 預設 timestamp suffix。

**A**：✅ 確認

### 2.13 軸 12：Gallery 整合

**Q**：怎接 r28 dispatch dict？

**D ★** 加 `kind='zentangle'` 第三 kind：

```python
VALIDATORS = {
    KIND_PSD: parse_and_validate_psd,
    KIND_MANDALA: parse_and_validate_mandala,
    KIND_ZENTANGLE: parse_and_validate_zentangle,    # NEW
}
SUMMARIZERS = {
    KIND_PSD: summarise_psd,
    KIND_MANDALA: summarise_mandala,
    KIND_ZENTANGLE: summarise_zentangle,             # NEW
}
```

仿 r28 by-kind dispatch dict pattern（已驗證模式）。Gallery list / search / filter 自動 cover。

**Thumbnail 生成**：cairosvg 轉 PNG（仿 r28b mandala thumbnail）。

**Gallery card 渲染**：summary 含 `char` (預設「心")、`tangle_count`、`stroke_count`、`tile_size_cm`。

**A**：✅ 確認

---

## 3. Sub-phase 拆解

| Sub-phase | 範圍 | 估時 | Risk |
|---|---|---|---|
| **6z-0** | Design doc 寫（本檔） | 完成 ✅ | — |
| **6z-1** | Outline 抽取 spike + 純禪繞 mode（無 char）+ 紙磚 canvas | 4-5h | R1 字框抽取 |
| **6z-2** | 紙磚旋轉 + tile-local coords + 8 preset 按鈕 | 3-4h | R2 旋轉一致性 |
| **6z-3** | ICSO 工具 (5 個) + size selector + 6 個 tangles 庫 | 5-6h | R3 tangle 步驟教學 |
| **6z-4** | 9 cell 重複疊加 panel + 簡化「填滿空白」 raycast | 3-4h | R3 raycast 邏輯 |
| **6z-5** | Embedded mode（漢字 outline + fill_mode inside/outside）| 4-5h | R5 outline polygon |
| **6z-6** | Draft 系統（undo + 單 slot localStorage auto-save + download）| 3-4h | R4 storage |
| **6z-7** | Gallery 整合（kind=zentangle + thumbnail + dispatch dict）| 2-3h | low — pattern 成熟 |
| **6z-8** | Tests + decision logs + bump | 3-4h | low |

**Phase 6z 總估**：~30-40 hours，分 8 sub-phases。

**Phase 7（snapshot 完整版跨 mode）**：~15-20 hours 獨立 phase。

---

## 4. Anti-pattern 清單（apply §8.35 negative constraints）

> 🔗 **應用 personal-playbook §8.35**：每個 skill / 角色定義必含 strict negative constraints。Design doc 也該有「禁止做的事」清單。

### 4.1 工程層 anti-patterns（不要做）

- ❌ **stroke smoothing 算法 / 拉直線工具 / 正圓 snap** — 違反禪繞「手繪自然感才是靈魂」（第 14 批）
- ❌ **強制 wizard 流程** — 違反禪繞自由精神（第 13 批 Flow 狀態）
- ❌ **完成 % progress bar / dopamine 鮮豔配色 / notification 打斷** — 違反 Flow 狀態（第 13 批）
- ❌ **強制 hard clip stroke 在 outline 內** — 違反「越界 OK」（第 18 批）
- ❌ **彈出框打斷 user 思緒** — 包括 confirm dialog / progress modal / save reminder

### 4.2 Schema 層 anti-patterns

- ❌ **stroke 存 world coords** — 違反軸 4b 核心 mechanism
- ❌ **DB 存 outline path 而非 outline polygon** — runtime 字型依賴會讓檔案 portable 性壞
- ❌ **draft 跟 published 混用同一檔案無 boundary** — 違反軸 10 兩 phase 模型
- ❌ **multi-char 強推進 MVP** — 違反「先單字驗證」 user 明示

### 4.3 UX 層 anti-patterns

- ❌ **Hard disable 過大尺寸按鈕**（軸 7） — 該 dim 提示但仍可選
- ❌ **「請填滿這個空白」催促** — 該讓 user 自由決定密度
- ❌ **published 後可後製改動** — 違反軸 10「定稿 immutable」

### 4.4 Implementation 層 anti-patterns（apply §8.31 P7）

- ❌ **失敗 2 次仍重試同方法** — 應改寫 3 個假設逐一驗證（personal-playbook §8.32）
- ❌ **無 P7 completion format 直接 mark 完成** — 應有 strict completion format（§8.31）
- ❌ **跳過 reviewer / 自己 review 自己** — Self-defense bias（§8.33）

---

## 5. P7 Completion Format（apply §8.31）

> 🔗 **應用 personal-playbook §8.31**：每 sub-phase 完成寫 P7 completion format（剩餘風險必填）。

每 sub-phase（6z-1 ~ 6z-8）結束須提交此 format：

```
[P7-COMPLETION] phase 6z-N

任務：<一句話 task summary>
方案：<採用 approach>
改動：<檔案 + 行範圍 list>
影響分析：<grep 結果 + 影響 caller / module>
三問自審：
  - 方案正確：是 / 否（理由）
  - 影響全面：是 / 否（grep 過哪些）
  - 回歸風險：低 / 中 / 高（驗證手段）
剩餘風險：<什麼情境下可能不對 / 待補完處 - 必填>
```

「**剩餘風險」必填**，不寫不算完成。違反此規則的 sub-phase commit 該被 rebase 重做。

---

## 6. Risk Register

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| **R1** | 字框 outline 抽取技術未驗證（freetype + Pillow path 抽取行為）| High | 6z-1 spike 先驗證；不行的話 fallback 用 hard-coded outline 庫 |
| **R2** | 紙磚旋轉 + tile-local coords 算錯 | High | 6z-2 完成後 manual E2E 驗證旋轉 / 不旋轉一致性 |
| **R3** | 9 cell 「填滿空白」 raycast 邏輯複雜 | Medium | 從手動 fixed count 開始（無 raycast）；「填滿」按鈕作為加碼，非必須 |
| **R4** | Tangle library 內容深度不足（user 用 3 次就 boring） | Medium | 6 個 tangles 帶詳細 step tutorial 比 12 個淺更好；user 反饋驅動加 tangle |
| **R5** | Phase 6z scope creep | High | 嚴守 sub-phase 邊界，每 sub-phase 結束 commit + bump（仿 r29 系列節奏） |
| **R6** | Draft 跟 published schema 不對齊 | Medium | `draft_meta.is_draft` 必填欄位 + 兩 phase 明確 boundary（「發布」按鈕觸發） |
| **R7** | Multi-char 提前進 MVP 拖累 ship | Low | 已 defer，schema 預留 `chars: []` array 不影響 MVP |
| **R8** | User 期待跟 thesis 偏離（user 想要「畫板」 不是「減負工具」） | Medium | Onboarding 文案明確 thesis；MVP 9 cell panel 是核心 UX 強化定位 |

---

## 7. 啟用條件 + 進入準則

> 🔗 **應用 §8.5 啟用條件結構性煞車**：明確列 phase 6z 啟動條件。

✅ **已滿足條件**：

1. ✅ Phase 5b r28-r29k gallery 完整 ship（375 tests / 0.14.121）
2. ✅ Personal-playbook §3.13 / §8.22-§8.30 升格完成（41056b0）
3. ✅ User 願景明確（21 批資料）
4. ✅ Schema 設計收斂（軸 1-12 全 Approval）
5. ✅ Anti-pattern 清單列出（§8.35）
6. ✅ P7 completion format 套用（§8.31）

🚦 **未滿足條件（如有）**：無 — 可進 6z-1 implementation。

---

## 8. 跟現有 stroke-order 系統的相容性

| 區塊 | 衝突風險 | Mitigation |
|---|---|---|
| Gallery dispatch dict (r28) | low | 加 KIND_ZENTANGLE 第三 kind，仿 mandala pattern |
| Thumbnail 生成 (r28b) | low | cairosvg 直接複用 |
| User profile / avatar (r29j) | low | 不衝突，獨立功能 |
| Like / bookmark / sort (r29 系列) | low | 不衝突，自動 cover zentangle uploads |
| URL hash route (r29f-g) | low | 不衝突，可選加 `#zentangle=<id>` deep-link |
| Cross-mode snapshot (phase 7) | n/a | 6z 用單 slot localStorage，phase 7 升級 |

---

## 9. Defer 留給後續

| 待做 | Phase |
|---|---|
| Multi-character (`chars: ["心","經"]`) | phase 6z+1 |
| Background mode 已提前 | (in MVP) |
| Monogram (字母裝飾型) | phase 6z+ |
| 3D 立體效果 | phase 6z+ |
| 彩色禪繞（11 色 preset，仿 r26）| phase 6z+1 |
| 陰影 + Tortillion 推色 | phase 6z+2 |
| Aura 工具（自動派生平行 stroke）| phase 6z+1 |
| Tangle library 擴大（7+ 個更多 tangles）| user 反饋驅動 |
| Tangle step tutorial 模式 | phase 6z+1（V1.5）|
| 智慧 size suggest（dim 過大但可選）| phase 6z+1 |
| Image → config 反向解析（CV）| phase 6z+2 / 7+ |
| Cross-mode snapshot system | **phase 7**（獨立）|
| Mobile / tablet responsive | phase 6z+1 |
| `pushState` 取代 hash route | 視 SEO 需求 |

---

## 10. Approval gate

**Design doc v0.1 寫完 ✅**。下一步：

| | 動作 |
|---|---|
| **A ★** | **User Approve design doc → 進 6z-1 implementation** |
| B | User 想修改某條軸 → re-loop QODA |
| C | 暫存 design doc → 收工今天 |

每 sub-phase 結束按 P7 completion format 提交 + commit + bump version + 各自 sub-phase decision log。

---

## 11. Cross-link 參考

- 設計 spike：`docs/decisions/2026-05-06_phase6z_design_spike.md`（前序文件）
- 工作日誌：`docs/journal/2026-05-06_session_log.md`
- 共通性原則：`docs/PRINCIPLES.md` §6 設計流程原則 + §6.8 thesis ↔ rule mapping
- Personal-playbook 治理層：
  - §0.1-0.4 治理哲學（thesis）
  - §8.31 P7 三問自審
  - §8.32 失敗 2 次換方法
  - §8.33 Self-defense bias
  - §8.35 Strict negative constraints
- r28 by-kind dispatch dict pattern：`docs/decisions/2026-05-04_phase5b_r28_gallery_mandala_upload.md`
- r27 .mandala.md schema pattern（仿）：`docs/decisions/2026-05-04_phase5b_r27_mandala_state_export_import.md`

---

## 12. 結尾

Phase 6z 是 stroke-order 至今最大單一 phase（~30-40h）。Design doc 完成代表「**動筆前該想清楚的事都想清楚了**」 — 對應 personal-playbook §0.4 重新框架問題 thesis 的具體實踐。

Implementation 等 user Approval design doc 後正式啟動。每 sub-phase 帶 P7 completion format + anti-pattern 自審 + commit + bump，仿 r29 系列節奏推進。

> 「方法論的本質 = 把『應該做但會偷懶的事』變成『不做就無法交付』」 — personal-playbook §0.1
