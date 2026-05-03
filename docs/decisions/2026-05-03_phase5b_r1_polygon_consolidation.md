# 2026-05-03 — Phase 5b r1 文字雲：規則多邊形整併進「多邊形 (自訂 N 邊)」

> 文字雲模式外框形狀 dropdown 中的「規則多邊形」optgroup（三角形、四角形、五角形⋯⋯十角形 8 個 options）功能跟「多邊形 (自訂 N 邊)」重複，整併成單一 polygon entry，搭配 +/− 按鈕跟邊數 counter。

**版號**：0.14.79 → 0.14.80
**Phase**：5b r1（文字雲互動 polish）

---

## User intent

- 「規則多邊形」optgroup 與「多邊形 (自訂 N 邊)」功能重複 → 整併成「多邊形 (自訂 N 邊)」
- 預設為 3 邊（三角形）
- 在邊 3 input **下一行** 用「+」按鈕提示可增加為 N 邊

---

## 關鍵決策

### 1. UI 整併策略：dropdown 移除規則多邊形 + N 用按鈕控制

選 (a) UI 完全移除「規則多邊形」optgroup，只保留 polygon entry，N 用按鈕控制 — 而不是 (b) 保留 optgroup 給「快速選 1 個常用 N」。

理由：

- 8 個 dropdown options 跟 1 個 polygon + N input 表達能力相同，重複增加認知負擔。
- N 從 3 → 20 連續可調，dropdown 蓋不到 11+ 邊，polygon 模式才完整。
- User 訴求明確「整併」，不是「並列」。

### 2. N counter UI：hidden input + visible label + 雙按鈕

選 hidden input + visible counter label + 「+/−」按鈕，**不**讓 user 直接編輯數字。

理由：

- User 明確要求「+」按鈕為 affordance，沒提數字直接編輯需求。
- 邊數從 3 慢慢加到 N 是常見操作模式（user 心智：「好像不夠，再加一邊」），按鈕直觀；數字編輯用於跨大幅度跳（3 → 15 直接打），但 polygon 連續加邊本來就是漸進操作。
- 簡化 UX：不用處理 typed-out-of-range value 的 clamp on blur edge case。
- 真要直接打數字 → 之後加 input field 再說，不要 pre-emptive。

### 3. 「+」按鈕位置：邊 3 input 之下（user 明確要求）

放在 `<div id="wa-edge-inputs">` 之**後**（user 看到的「邊 3」input 下一行），而不是在邊 inputs 之上做 counter row。

理由：

- User 字面要求 「在邊 3 的下一行，用「+」提示可增加為 N 邊」。
- 心智模型上：「我看完邊 3 的內容，發現需要更多邊」→ 順下流是按 +。如果 + 在邊 inputs 之上，user 看到 + 時還沒進入邊 input 的 mental flow，affordance 失效。
- 第一輪實作放在上方（counter+input+按鈕 row），user 反映後第二輪改到下方。**Lesson**：UX 細節差別只能靠 user 點明，不要憑「常識」。

### 4. 後端不動，前端純 UI 整併

`make_shape("polygon", sides=N)` 後端早就支援 sides=3-20。`_SHAPE_KINDS` regex 也接受 `polygon`。所以前端整併純 UI，後端零改動。

**Lesson**：UI 整併 task 先看後端能力，往往發現後端已 generic、UI 是冗餘的捷徑（dropdown 8 options 是早期沒想到 polygon 自訂 N 的遺產）。

### 5. 舊 `triangle / square / ... / decagon` value backward compat

`POLYGON_SIDES` mapping 保留在 JS（`waIsPolygon`、`waCurrentSides` 都還會 fallback 查它），對應後端的 shorthand `_SHAPE_KINDS` 入口。

理由：

- 萬一有人 bookmark 帶 `?shape=triangle` 進來、或 persisted state 從舊版 cookie 還原，UI 不會炸（waCurrentSides 仍回 3）。
- 程式碼 footprint 極小（10 個 const entries），維護成本可忽略。

---

## 實作 footprint

| 檔案 | 修改 |
|------|------|
| `static/index.html` `<select id="wa-shape">` | 移除「規則多邊形」optgroup（8 options）；`polygon` 改為 selected default |
| `static/index.html` `wa-edges-row` | 加 `wa-sides-count` visible label、`wa-sides-n` hidden input；邊 inputs 下方加「+/−」buttons row |
| `static/index.html` JS `waIsPolygon` / `waCurrentSides` | 接受 `shape="polygon"`；polygon mode 從 `wa-sides-n` 讀，否則 fallback 至 POLYGON_SIDES mapping |
| `static/index.html` JS `waSyncSidesCounter` 新增 | 同步 hidden input → visible label；按 N 上下界 disable +/− 按鈕 |
| `static/index.html` JS `waBumpSides` 新增 | +/− 按鈕 handler，clamp [3,20]，bump 後 rebuild edges + capacity |
| `static/index.html` JS `waUpdatePanels` 結尾 | 多 call `waSyncSidesCounter()` 確保 panel 顯示時 counter 正確 |

後端：**零改動**（`make_shape("polygon", sides=N)` 已支援）。

---

## 驗證

- `pytest test_stamp + test_wordart + test_wordcloud` → 247 passed in 4.34s
- 後端 API smoke：`/api/wordart/capacity?shape=polygon&sides=N&layout=linear` for N ∈ {3,4,5,7,10,20} 全 200，per-edge capacity scale 正常（N=3:[12,12,12]、N=20:[2×20]）
- 視覺 PNG 驗證：N=3（三角形）/ N=5 / N=7（七角形）linear 渲染都正確，每邊文字依 edge 排列 ✓

---

## Lessons / 適用 future round

1. **UI 整併前先看後端**：dropdown 8 options vs `polygon + sides=N` 是同義表達，後端早 generic。「整併」task 多半找得到這種冗餘 dropdown 是早期 UI 給的捷徑、後來被 generic 入口取代但 dropdown 沒清。

2. **User 字面要求 「下一行」 ≠ 「上一行」**：第一版實作放 counter row 在 edge inputs 上方（理性合理 — counter 在前），user 不買帳。改放下方就 OK。**位置 affordance 在 mental flow 順向位置才有效；憑「常識」放上方是 designer 邏輯，不是 user 邏輯。**

3. **Backward compat 用最小成本維持**：`POLYGON_SIDES` mapping 留在 JS 沒成本（10 行 const），萬一舊 query string 進來不會炸。「砍乾淨」跟「留尾巴」之間，對外部入口（query string、URL）一律留。
