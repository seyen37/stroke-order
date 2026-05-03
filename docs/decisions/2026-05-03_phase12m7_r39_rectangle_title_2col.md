# 2026-05-03 — Phase 12m-7 r39 職名章 (rectangle_title) 2-column 結構化重寫

> 把 `rectangle_title` preset 從「split chars by half top/bot」legacy layout 換成「左欄職稱 + 右欄姓名」2-column 結構化欄位，搭配 4 個獨立 input fields 跟 1/2 行 toggle checkbox。

**版號**：0.14.77 → 0.14.78
**Round**：r39
**檔案**：4 改 1 新（pyproject.toml / stamp.py / server.py / static/index.html / docs/decisions/...）

---

## User intent / 規格

- 印章類型 職名章 預設自訂尺寸 **28 × 8 mm**（mid-task user 從 28×18 改 28×8）
- 外框內 → 分 2 欄
  - **左欄寬 12 mm**：職稱 → 可勾選 1 行或 2 行
  - **右欄寬 14 mm**：姓名 → 永遠 1 行
- 文字 auto-fit（自動放大縮小填滿欄位，分散排列）
- 文字方向 **橫書**，從左到右

---

## 關鍵決策

### 1. 結構化欄位 vs 單一 text + separator

選 4 個獨立 fields（`rect_left_line1` / `rect_left_line2` / `rect_right` / `rect_left_2rows`）而不是 single text + separator。

理由：跟 oval / tax_invoice 已經建立的 pattern 一致（structured-input-over-separator memory rule）；user 心智模型「左欄職稱 / 右欄姓名 / 1 或 2 行」mapping 1:1 到 UI fields，不必教 escape syntax；後續加欄位（例如左欄 3 行）也容易擴充。

### 2. Backward-compat fallback

新 layout 透過 `_has_rect_structured` flag 判斷有沒有 structured fields。沒有 → fallback 至原 legacy「half top / bot row」layout。

理由：legacy unit tests（test_stamp.py 162 個）都用 `text="..."` 無 structured fields call rectangle_title preset；如果直接 hard-cut，會破老測試 + 老 caller。Fallback 路徑保留歷史行為。

```python
_has_rect_structured = preset == "rectangle_title" and (
    (rect_left_line1_chars and len(rect_left_line1_chars) > 0)
    or (rect_left_line2_chars and len(rect_left_line2_chars) > 0)
    or (rect_right_chars and len(rect_right_chars) > 0)
)
if n == 0 and not _has_oval_structured and not _has_rect_structured:
    return []
```

### 3. side_pad 算法：max((W - LEFT - RIGHT) / 2, inset)

side_pad 不固定，取「平均剩餘寬度」跟 `inset`（border_padding）大值。

理由：28×8 預設搭配 `border_padding_mm=0.8`、LEFT=12、RIGHT=14 → side_pad = max(1, 0.8) = 1mm，左右對稱。若 user 把 width 改成 25mm（< 12+14=26）→ side_pad = max(-0.5, 0.8) = 0.8，左右各 0.8mm 但 columns 會擠到 25-1.6=23.4mm，自動 cap by char_size_mm 不會炸。

### 4. Auto-fit 公式：min(cell_w * 0.95, col_h * 0.85, char_size_mm)

每欄 cell_w = col_w / n_chars。字大小三 cap：水平 95% 填滿、垂直 85%（多留上下 padding）、user-設 char_size_mm 上限。

選 0.95 / 0.85 fill ratio：

- 水平 cell 之間不黏（5% 間距）但夠飽滿。
- 垂直 0.85 預留 stamp 上下 border + 視覺 breathing room。
- char_size_mm cap 防止「stamp 很大 + 字很少」時字撐到誇張比例。

### 5. Default 28 × 8 mm

理由：業界職名章常見尺寸（圓刻店「20×9」「26×10」「28×10」），8mm 高搭配 0.8mm border 留約 6.4mm 字身高度，雙行各 ~2.7mm 仍可辨識。User 提的 28×18 比例太高（H/W = 0.64），實作時 user 立即修正到 28×8（H/W = 0.29），更符合長條職名章視覺。

---

## 實作 footprint

| 檔案 | 修改 |
|------|------|
| `stamp.py` `_placements_for_preset` | +4 keyword args; 新 2-column branch 在 `elif preset == "rectangle_title":` 內，搭配 `_has_rect_struct` toggle 跟 legacy fallback；`n == 0` early-return 加 `not _has_rect_structured` guard |
| `stamp.py` `render_stamp_svg` / `render_stamp_gcode` | +4 string/bool kwargs，`_load_chars()` plumb 進 placements call |
| `server.py` `StampPostRequest` | +4 Pydantic fields |
| `static/index.html` defaults | `rectangle_title: [28, 8, 6, false]` |
| `static/index.html` rect-fields HTML block | 4 inputs + checkbox + 標題 row + 第 2 行條件顯示 row |
| `static/index.html` `stampUpdateOvalFieldsUI` | 加 `isRect` show/hide rect-fields + hide 單一 text 欄 |
| `static/index.html` `stampInit` | wire `st-rect-left-2rows` change listener → toggle `st-rect-left-line2-row` |
| `static/index.html` `stampBuildBody` | +4 fields 進 request body |

---

## 驗證

- `pytest tests/test_stamp.py` → 162 passed in 3.0s（legacy fallback 路徑保護有效）
- 視覺驗證：
  - 1-row 左欄（經理 + 王大同）：5 char boxes 排正確 ✓
  - 2-row 左欄（經理 / 特助 + 王大同）：左 2×2、右 1×3 ✓
  - 4-char 左欄（業務副理 + 王大同）：左 4 字 cell 縮小自動 fit ✓

---

## Lessons / 適用 future round

1. **新增 structured-fields preset 必查 early-return guard**：`_placements_for_preset` 開頭 `if n == 0 and not _has_oval_structured: return []` 是 12m-1 加的，當時只考慮 oval/tax_invoice。新加 rect 結構欄位時忘了同步擴張這條件 → 第一次 render 出空 SVG 才發現。Pattern：每加一個 「text 為空但 structured fields 提供」的 preset 都要回頭檢查這個 guard。

2. **Visual rendering 驗證每 round**：unit tests 162 個全 pass 但第一次 render 完全空白 — 單測抓不到「字根本沒被加進 placements」這種 layout-level bug。memory rule `feedback_visual_render_verify` 再次驗證有效。

3. **Mid-task spec change 要立刻調整**：user 從 28×18 改 28×8 是中途修改，沒做白工因為當時還沒 render 視覺。如果已經 render PNG + 寫 unit tests，這種改動成本會高出許多 — small spec change 早講比晚講好。

---

## r39b 補丁：欄位寬度依 1 行 / 2 行自動切換

**版號**：0.14.78 → 0.14.79

User 看完 r39 視覺後反映：1 行職稱情境下，左欄 12mm 浪費空間（職稱通常 2-4 字，cell 拉太大反而稀疏），姓名（右欄）需要更多空間。改成：

| 模式 | LEFT_W | RIGHT_W | 邏輯 |
|------|--------|---------|------|
| 1 行職稱 | 10 mm | 16 mm | 職稱字少給右欄姓名多空間 |
| 2 行職稱 | 12 mm | 14 mm | 雙行職稱字較密、需多一點寬度 |

實作只動 1 處（stamp.py rectangle_title branch 內的 LEFT_W / RIGHT_W 常數變條件），加 1 處 UI hint 文字。

驗證：
- 1-row case: 左欄 cell_w=5、ch_sz=4.75；右欄 cell_w=5.33、ch_sz=5.07（右側字明顯比左側大）✓
- 2-row case: 維持 r39 行為（左 2.72×4 / 右 4.43×3）✓
- pytest test_stamp 162 passed ✓

**Lesson**：「動態欄寬隨內容密度調整」是業界職名章常見視覺策略——固定值好實作但忽略「字數越少 cell 越該縮」的視覺平衡。第一輪用固定值是合理 starting point，等 user 看到實效再 tune；不要為了「pre-emptive 動態化」一開始就加 case 邏輯，rectangle_title 的字數區間有限（2-4 / 5-7），切換 toggle 帶 1 個維度就夠。
