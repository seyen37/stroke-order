# Phase 6z 禪繞字 Design Spike — 決策紀錄

**日期**：2026-05-06
**狀態**：**進行中（design doc 待寫）**
**範圍**：禪繞字 (Zentangle Embedded Hanzi) 模式 — 漢字 outline + 內部禪繞畫填充 + 紙磚旋轉 + 重複疊加 + 草稿系統

> ⚠️ 這份是 **Decision spike** — 完整 design doc 尚未寫完。等下次工作日 user 確認動工才整合所有決定到 `2026-05-06_phase6z_zentangle_design.md`。

---

## Phase 6z 起源

Phase 5b 完整 ship gallery 社群平台後（375 tests / 0.14.121），user 提出新 mode：「禪繞字」。

> 「主要是，用戶可以選擇一個中文字，預設為「心」，系統呈現的是文字的邊框，而不是中心軌跡，以這個文字邊框為核心，開始繪製纏繞畫文字 ... 採用『紙磚』的形式，繪畫時可以轉動紙磚的角度來配合手的順手程度 ... 也希望未來可以擷取禪繞畫的圖片，生成設定檔」

範圍評估：**目前單一 phase 最大 scope**，比 r29-r29k 加總更大。

---

## 為什麼這份是 spike，不是 final design doc

1. **8+ 條架構軸全未決狀態** — 直接 implement 高機率重做
2. **User 願景豐富但細節需釐清** — 21 批資料逐步收斂後才能 commit final spec
3. **「不寫 design doc 就動 code」 是 anti-pattern** — 對應 §5.7「何時不該立即實作」的「不確認需求清楚」+ 「不確認技術可行」雙判準
4. **Senior 該等 alignment 才動工** — user OK plan 後才花時間寫 design doc，不是空想動工

---

## 累積 15 大決策方向（逐一 QODA）

### 1. Phase shape — 用什麼 phase 形式？

**Q**：MVP 該全 vision / vertical slice / spike / design doc / 純禪繞先 / 砍 scope？

**O**：6 個選項（A 全 vision / B vertical slice / C spike / D design doc / E 純禪繞先 / F 砍 scope）

**D ★ D — Design doc 先寫**，理由：

- 8 條軸全部未決狀態下動工 = 高機率重做
- 紙磚旋轉是核心差異化，spec 未明就 implement 注定改架構
- 檔案格式是長期承諾，先想清楚比 migration 便宜

**A**：✅ user 同意

---

### 2. MVP modes — 哪幾種繪畫模式

**Q**：純禪繞 / 空心填充 / 背景鑲嵌 / Monogram / 3D — 哪些 MVP？

**O**：4-5 種模式 ranked by 複雜度

**D ★** MVP 3 模式：
- **A. 純禪繞**（char=null，整磚自由畫）✅
- **B. 空心填充型**（char=漢字，fill_mode='inside'）✅
- **C. 背景鑲嵌型**（char=漢字，fill_mode='outside'）— **從 phase 6z+1 提前進 MVP**

理由：第 12 + 20 批 user 資料兩次出現「負空間浮現式」，證明非邊緣 case；HTML5 canvas reverse clip 工程量小（~10 行）；「字框是 container，tangle 才是核心」哲學上 outside mode 等價於 inside。

字母裝飾型 (Monogram) + 3D defer 到 phase 6z+ 進階。

**A**：✅ user 確認

---

### 3. MVP tangle 庫數量

**Q**：MVP 內建多少個 tangles？

**O**：3 / 5 / 6 / 全 7+

**D ★ 6 個**：

| Tangle | ICSO 主元素 | Role | Category |
|---|---|---|---|
| Crescent Moon | C | focal | geometric |
| Hollibaugh | I | structural | geometric |
| Tipple | O | filler | geometric |
| Mooka | S compound | dynamic | organic |
| Printemps | S simple | dynamic | organic |
| **Florz** | I + O | (背景結構) | geometric |

理由：6 個 tangles 涵蓋 ICSO + 兩 category + 4 role，且第 10/17/18 批多次出現 Florz 在實戰範例（穩定三角構圖 / Z 暗線實戰），證明常用必入。

---

### 4. 紙磚旋轉模式

**Q**：自由角度 / preset 按鈕 / hybrid？

**O**：A1 hybrid / A2 純自由 / A3 純 preset

**D ★ A1 Hybrid**：8 preset 按鈕 (0/45/90/135/180/225/270/315°) + 拖拉自由旋轉 + 一鍵還原

對應 schema：`tile.rotation: float (degrees)` 配合 UI rotate gesture / button group。

**A**：✅ user 確認

---

### 5. ICSO 疊加座標系統（核心 mechanism）

**Q**：Stroke 該存 tile-local coords 還是 world coords？

**O**：B1 tile-local（render 時還原） / B2 world coords

**D ★ B1 tile-local**：是禪繞數位版**核心架構**。User 在旋轉後 tile 自然下筆，stroke 落在 tile 自己座標系，「stroke 跟著 tile 旋轉」正是「轉動紙張配合手部」要實現的事。

```yaml
tile:
  rotation: 45
strokes:
  - {points: [...]}    # tile-local，跟 tile 一起旋轉
```

**A**：✅ user 確認

---

### 6. 填充密度控制

**Q**：density 怎讓 user 控制？

**O**：C1 三選一按鈕 / C2 一條 density slider / C3 兩條 slider (size × spacing)

**D ★ C2** 一條 density slider (low/medium/high)。Density 是 perceptual axis，user 直覺；size 跟 spacing 同現象兩面，不需拆兩 slider。

```yaml
fill_strategy:
  density: 'low' | 'medium' | 'high'
```

**A**：✅ user 確認

---

### 7. UI 引導模式

**Q**：分層 wizard / 純自由 / hybrid？

**O**：A 純自由 / B 強制 wizard / C hybrid + contextual hint

**D ★ C** 自由為主 + 角落 contextual hint 文字（不彈窗、不打斷） + toolbar 視覺順序體現分層流程：

```
左→右 toolbar: 鉛筆暗線 → 黑描邊 → tangle 元素 → 填黑 → 紙磚旋轉
```

第一次開磚帶 1 行小提示「先用鉛筆畫暗線分割」+ ✕ 關閉。

**「大元素切空白 → 小元素遞迴填」** 核心機制：MVP user 純手動，phase 6z+1 加 auto-detect empty region。

**A**：✅ user 確認

---

### 8. 元素尺寸設計

**Q**：尺寸 UI 怎設計？智慧 disable 過大按鈕？

**O**：A 連續 slider only / B 預設按鈕 only / C 5 預設按鈕 + 微調 slider

**D ★ C**：

```
Size: ⚪ XS (14) · ⚪ S (24) · ⚪ M (40) ★ · ⚪ L (60) · ⚪ XL (90)
微調 slider: 10-120px
```

**Hard disable 過大按鈕**：MVP **不做**（呼應禪繞「沒有錯誤」精神，user 想試就試）。phase 6z+1 加「建議尺寸高亮」（dim 過大但仍可選）。

**A**：✅ user 確認

---

### 9. 9 cell 重複疊加 panel ⭐ 核心 UX

**Q**：怎用按鈕減負 user 重複手繪 ICSO 元素？

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
   ▶ 間距 (mm): [▼1▲] 快選 1 · 2 · 3 · 5 · 8
   [✓ 確認] [✗ 取消] [🔁 填滿空白]
```

**「填滿空白」 簡化版**：raycast 從 base stroke 沿選定方向到「邊界」距離 D，自動 count = floor(D/spacing)。撞到 outline / 紙磚邊 / 既有 stroke → preview 截斷 + 顯示「已填滿」綠 badge。

**Schema**：每個 repeat 寫成獨立 stroke 帶 `parent_id` + `repeat_meta`：

```yaml
strokes:
  - id: "stroke_001"
    type: line
    points: [...]
  - id: "stroke_002"
    parent_id: "stroke_001"
    repeat_meta: {direction: 'E', index: 1, spacing: 2}
    type: line
    points: [...]
```

→ file size 略大但 render 簡單 + import 直觀。

**A**：✅ user 確認

---

### 10. 紙磚尺寸單位

**Q**：cm / inch / 內部 mm？

**D ★** 內部 mm（base unit），display layer 換算 cm/inch。MVP 預設 cm（台灣慣用）+ inch toggle。

```
快選: ⚪ Bijou (5cm) · ⚪ 標準 (9cm) ★ · ⚪ 學徒磚 (11.4cm) · ⚪ 自訂 ___
```

**A**：✅ user 確認

---

### 11. 草稿 vs 定稿哲學調和 ⭐

**Q**：禪繞「沒有錯誤」 vs user 要 undo + snapshot — 怎調和？

**D ★** 兩 phase 模型：

| 階段 | 行為 | 哲學 |
|---|---|---|
| **草稿 (draft)** | 全功能 undo + snapshot | 工程實用主義 |
| **定稿 (final)** | 上傳 gallery 後 immutable | 禪繞精神 |

對應寫作 (草稿 vs 定稿) / 攝影 (RAW vs 沖洗成相片)。

**Schema**：`draft_meta: {is_draft: bool}` 標記。Published 後 immutable，不可後製改動。

**A**：✅ user 確認

---

### 12. Undo 深度

**Q**：1 步 / bounded multi-step / unlimited？

**D ★ A2 Bounded 30 步**。30 步覆蓋 99% 「最近畫錯」需求；紙磚 size 限制下總 stroke 100-300，30 步足夠 cover 一個 mistake region。

**對應快捷**：`Ctrl+Z` undo / `Ctrl+Shift+Z` redo。**只畫筆動作入 history**（旋轉紙磚 / size 變更不算）。

**A**：✅ user 確認

---

### 13. Snapshot 數量 + 結構

**Q**：還原點該幾個？

**D ★ 8 slots = 3 auto + 5 manual**：

| Slot | 類型 | 觸發 |
|---|---|---|
| 1-3 | Auto rolling FIFO | 每 5 分鐘 / 每 20 strokes 自動 |
| 4-8 | Manual named | User 主動「儲存還原點」 |

**儲存**：IndexedDB（不是 localStorage — quota 太小）。8 slot × ~100KB ≈ ~800KB，IndexedDB quota 50MB+ 寬鬆。

**UI**：左側 panel，auto / manual 兩區塊清楚分。

**A**：✅ user 確認

---

### 14. Snapshot 命名 + 衝突處理

**Q**：命名 convention？重名怎處理？

**D ★** 內部 UUID + user-visible label：

```yaml
{
  id: "uuid-abc123",      # 內部 unique 不可改
  mode: "zentangle",
  title: "心",              # user 設定
  label: "練習 #1",         # snapshot 標題（manual 才有）
  type: "auto" | "manual",
  created_at: "...",
  thumbnail_data_url: "...",
  state: "<frontmatter + strokes 完整 MD>"
}
```

**重名處理**：
- 內部 UUID 永不撞
- User-visible label 重複 → prompt「覆蓋 / 改名 / 取消」
- Auto 用「自動 HH:MM」時間戳，不撞

**A**：✅ user 確認

---

### 15. 本機下載檔名 + 覆蓋衝突

**Q**：User download 到本機 PC，怎避免下次下載覆蓋？

**D ★** Timestamp suffix 永不覆蓋：

```
<title>_<YYYY-MM-DD>_<HHMM>.<mode>.md

範例:
  心_2026-05-06_1234.zentangle.md
  心經_2026-05-06_1500.mandala.md
  論語_2026-05-06_1830.psd.json
```

**File-System Access API** 支援 Save As dialog → user 可改名。Fallback `<a download>` 預設 timestamp suffix。

**A**：✅ user 確認

---

### 16. Cross-mode reuse 策略

**Q**：snapshot system 該包進 phase 6z（zentangle）還是另開 phase 7？

**O**：
- E1 全包進 phase 6z
- E2 phase 6z 最薄 + phase 7 完整 cross-mode
- E3 phase 6z 不做

**D ★ E2 — 拆兩 phase 漸進**：

**Phase 6z 包含（最薄 draft）**：
- Undo/redo bounded 30 步
- 單一 auto snapshot slot（localStorage）
- 「儲存到本地檔」（D2 timestamp suffix download）
- **不做** multi-snapshot UI / IndexedDB

**Phase 7（snapshot 完整版）**：
- IndexedDB 8-slot system
- Cross-mode `snapshot.mjs` 抽 module
- Mandala / PSD 模式套用
- 全套 manual + auto UI

→ Phase 6z user **可以 rest/resume**（單 slot），但**沒有多版本**。phase 7 升級多版本 + 跨 mode。**Scope 控制原則**。

**A**：✅ user 確認

---

## 統一 Schema（截至目前）

```yaml
---
title: "心 - 我的禪繞字"
author: "user.display_name"
mode: 'pure' | 'embedded'
chars: ["心"] | []                       # array 預留多字延伸
fill_mode: 'inside' | 'outside'           # MVP 兩個都做
tile:
  shape: 'square'                          # MVP only
  size_mm: 90                              # internal mm
  display_unit: 'cm'                        # UI 偏好
  rotation: 0                              # 當前角度（deg）
fill_strategy:
  density: 'low' | 'medium' | 'high'
strokes:
  # String 暗線
  - {type: line, layer: guide, points: [...]}
  
  # 基底元素 + 重複疊加（展開為個別 stroke）
  - id: "stroke_001"
    type: line | curve | s_shape | orb | dot
    layer: final
    points: [...]
    size: 40
    rotation: 45                            # tile-local angle
  - id: "stroke_002"
    parent_id: "stroke_001"
    repeat_meta: {direction: 'E', index: 1, spacing: 2}
    type: line
    layer: final
    points: [...]
  
  # Tangle 填充
  - {type: fill, layer: final, region: [...]}

shadows: []                                 # MVP 始終空（schema 預留）

draft_meta:
  schema_version: 1
  is_draft: true | false                    # true=草稿 / false=published
  undo_depth: 30
  history: [...]                            # bounded undo array

created_at: ...
updated_at: ...
---
```

---

## 21 批資料的核心啟示

| 批 | 啟示 |
|---|---|
| 1-2 | 紙磚 size 多種 → MVP square only，schema 預留 shape |
| 3 | 黑白 vs 彩色 → MVP 黑白 |
| 4-5, 14-16 | ICSO 5 元素 + tangle library hierarchy（基礎 vs 組合）|
| 6 | 學習 3 階段 → MVP UX flow |
| 7-9, 18 | tangle 步驟分解 → tangle 庫帶 step tutorial（V1.5）|
| 10, 17 | 構圖 + tangle role → 4 role 標籤（structural/focal/dynamic/filler） |
| 11-12, 20 | Embedded Letters 是官方技法 → product 定位 |
| 13 | 設計哲學 8 步儀式 → MVP UX 規範（無 notification / muted palette / 60fps）|
| 18 | String 2B pencil + 4 templates |
| 19 | 陰影 3 技法 → 整批 defer post-MVP |
| 21 | 重複疊加 9 cell panel → product positioning 升級為「**重複疊加減負工具**」|

---

## Sub-phase 拆解（preliminary，design doc 寫完才 final）

| Sub-phase | 範圍 | 估時 |
|---|---|---|
| 6z-0 | Design doc 寫 | 2-3h |
| 6z-1 | Outline 抽取 spike + 純禪繞 mode（無 char） | 4-5h |
| 6z-2 | 紙磚 + 旋轉系統 + tile-local coords | 3-4h |
| 6z-3 | ICSO 工具 + 5-6 個 tangles + size selector | 5-6h |
| 6z-4 | 9 cell 重複疊加 panel | 3-4h |
| 6z-5 | Embedded mode（漢字 outline + fill_mode inside/outside）| 4-5h |
| 6z-6 | Draft 系統（undo + 單 slot snapshot + download）| 3-4h |
| 6z-7 | Gallery 整合（kind=zentangle + thumbnail） | 2-3h |
| 6z-8 | Tests + decision logs + bump | 3-4h |

**Phase 6z 總估**：~30-40 hours，分 8-9 個 sub-phases。**比 r29-r29k 系列加總略大**。

**Phase 7（snapshot 跨 mode）**：~15-20 hours 獨立 phase。

---

## Risk Register（preliminary）

| # | Risk | Mitigation |
|---|---|---|
| R1 | 字框 outline 抽取技術未驗證 | 6z-1 spike 先驗證 freetype + Pillow path 抽取 |
| R2 | 紙磚旋轉 + tile-local coords 算錯 | 6z-2 完成後 manual E2E 驗證旋轉一致性 |
| R3 | 9 cell 「填滿空白」 raycast 邏輯複雜 | 從手動 fixed count 開始，「填滿」按鈕作為加碼 |
| R4 | Tangle library 內容深度不足 | 6 個 tangles 帶詳細 step tutorial 比 12 個淺 OK |
| R5 | Phase 6z scope creep | 嚴守 sub-phase 邊界，每 sub-phase 結束 commit + bump |
| R6 | 草稿系統 schema 跟 published 不對齊 | `draft_meta.is_draft` 必填欄位 + 兩 phase 明確 boundary |

---

## 哲學定位（design doc 主軸）

**Phase 6z 是「禪繞重複疊加減負工具」**，不是「禪繞數位畫板」。

差別：

| Aspect | 數位畫板 | 重複疊加減負工具 ★ |
|---|---|---|
| 核心價值 | 提供畫筆 | **減少 user 重複勞動** |
| 主要 UI | toolbar of brushes | **9 cell 疊加 panel** |
| User 期待 | 「我畫得像不像」 | 「我享受重複的節奏」 |
| 競品比較 | Krita / Procreate | （無直接競品 — 禪繞特化）|
| Product moat | 畫筆精緻度 | **重複機制 + 紙磚旋轉 + ICSO 結構** |

→ design doc 該明確 product thesis，避免被 user / 自己誤導往「畫板」方向擴 scope。

---

## 下次回來該做的事

1. **動工寫 phase 6z design doc**（~600-800 行 markdown）
   - 整合 21 批資料 + 16 決策 + 統一 schema + sub-phase 拆解 + risk register
   - 文件位置：`docs/decisions/2026-05-06_phase6z_zentangle_design.md`
2. **確認 design doc OK** 才進 sub-phase 6z-1 implementation
3. **每 sub-phase 結束** commit + bump version + 各自 sub-phase decision log

**Approval gate**：design doc 寫完 user OK 後才動 code。**不該因為「我已經想了一天」就 commit 動 implementation**（§5.7 「何時不該立即實作」）。

---

## Cross-link 參考

- 工作日誌：`docs/journal/2026-05-06_session_log.md`
- 共通性原則更新：`docs/PRINCIPLES.md`（新加 §6 章節 — 設計流程原則）
- Personal-playbook morning audit：`docs/decisions/2026-05-06_r29-r29k_principles.md`（在 personal-playbook repo）
