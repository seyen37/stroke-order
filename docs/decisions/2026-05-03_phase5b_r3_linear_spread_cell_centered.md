# 2026-05-03 — Phase 5b r3 文字雲：linear + spread 改為 cell-centered（首尾各留半 gap）

> 多邊形 linear 模式 + spread 對齊 + 字數 < slots 時，原本「endpoints-included」分布會在邊內跳 slot 造成不均勻 gap，且字貼到邊端 → 多邊形角落兩字相黏。改成 cell-centered 分布。

**版號**：0.14.81 → 0.14.82
**Phase**：5b r3

---

## User intent

User 在 5 邊 polygon 每邊填「日月金木水火土」7 字、auto_cycle=OFF、align=spread 設定下發現：

- 邊內字距不均（中間有跳 slot 出現大 gap）
- 邊與邊交接處（多邊形角落）兩字相黏

要求：

1. 「請檢視實際情況，調整文字與文字之間的間距」 — 修字距均勻性
2. 「在文字的首與尾，各自增加一半『文字與文字之間的間距』」 — 邊首/邊尾各留半 gap

---

## 問題分析

`compute_linear` 走流程：

1. `edge_positions(a, b, char_size)` 算出 N slots，slot i 在邊長分數 `(i + 0.5) / N`，相鄰 slot 距離 = char_size
2. 字數 ≥ slots → 從 slot 0 依序填，截斷
3. 字數 < slots + auto_cycle 關 → 走 `_pick_slot_indices(n_chars, n_slots, "spread")` 從 N 個 slot 中挑 n_chars 個 index

`_pick_slot_indices(spread)` 的算式 `step = (n_slots - 1) / (n_chars - 1)`、`indices = [round(i * step)]`：保證頭尾 (slot 0, slot N-1) 一定中。但中間 indices 是離散 round 出來的，會出現跳 slot 造成不均勻 gap。例如 7 chars in 8 slots → indices = [0, 1, 2, 4, 5, 6, 7]（slot 3 被跳），第 3 跟第 4 字之間的 gap 加倍。

而且首尾 char 在 slot 0 / slot N-1，距邊端只有 char_size/2，跨 corner 跟下一邊首字之間僅 char_size 距離 → 視覺上「相黏」（用戶反映的接合）。

## 關鍵決策

### 1. 改變 spread 語意，不重用 _pick_slot_indices

選 cell-centered 重新分布：char j 位於邊長分數 `(j + 0.5) / n_chars`，間距均勻 = `edge_length / n_chars`，邊首/邊尾 padding = `edge_length / (2 × n_chars)`。

理由：

- 「字距均勻」是基本 visual contract，比「endpoints 對齊」更符合直覺。
- 邊首尾各 `gap/2` padding 自然解決多邊形角落相黏問題（不需要額外做 corner 偵測或 inset）。
- 跟 `edge_positions` 的 `(i + 0.5) / N` 邏輯一致（slot grid 也是 cell-centered），口徑統一。

### 2. 只改 compute_linear 的 spread 分支，不動 _pick_slot_indices

`_pick_slot_indices` 還被 `compute_three_band`（中線）跟 `compute_linear_groups` 用。User 只反映 linear 模式的問題，沒提 three_band / groups。改 helper 全域語意風險擴散，所以：

- 在 `compute_linear` 的 `else: chars < slots` 分支多 case 一個 `if align == "spread":` → call 新 helper `_spread_positions_on_edge(a, b, n_chars)`，直接算位置（繞過 slot grid）
- 其他 align（center/left/right）維持走 `_pick_slot_indices` + slot grid

附帶好處：`_pick_slot_indices(spread)` 跟 `_spread_positions_on_edge` 各自單一職責，不混語意。

### 3. Outward angle 沿用 corner-flip 後的 slots[0] 角度

新 helper 不重算 outward angle（一邊上每個位置 normal 相同），直接拿已經過 `if d_test < d_here: flip` 修正的 `slots[0][2]`。避免重複實作 corner-flip 邏輯。

---

## 實作

| 檔案 | 修改 |
|------|------|
| `exporters/wordart.py` | 新增 `_spread_positions_on_edge(a, b, n_chars)` helper（cell-centered 分布、不需 slot grid） |
| `exporters/wordart.py` `compute_linear` | else 分支多 case `if align == "spread":` 走新 helper；其他 align 維持原 `_pick_slot_indices` 路徑 |
| `tests/test_align.py` | `test_linear_align_spread_endpoints` 改名為 `test_linear_align_spread_cell_centered`，斷言改成距離 ≈ 0.5 × edge_length（cell-centered）+ 首字距邊起點 > char_size_mm 的 sanity check |

後端 wire（`web/server.py` `/api/wordart`）不動。

---

## 驗證

- pytest test_align + test_wordart + test_wordcloud + test_stamp → **271 passed in 5.01s**
- 視覺驗證：5 邊 polygon × 7 chars/edge × auto_cycle=OFF × spread → 每邊 7 字均勻分布、邊角落清楚有半 gap padding，跟 user screenshot 對比 ✓

---

## Lessons / 適用 future round

1. **「均勻分布」比「endpoints 對齊」更符合 user 直覺**：本來 spread = 「分得開」隱含 endpoints-included 設計（B1 phase 5h commit 寫死的），但實際 user 心智是「字距均勻」。當設計 contract 跟視覺直覺有 gap 時，視覺直覺贏。

2. **_pick_slot_indices 是 slot-picker 而非 position-computer**：把離散 slot 集合上挑 index 跟在連續邊上算位置混在同個 helper 裡是早期實作的便利，但語意不同。r3 拆出 `_spread_positions_on_edge` 是正確的職責切分；以後再有「邊上連續分布」需求都該走這條 path。

3. **Polygon 角落相黏的根因是「字貼邊端」**：解法不是 corner inset 偵測，而是 cell-centered 分布天然帶半 cell padding。「對稱 padding」是 invariant，不該靠 ad-hoc 條件檢測。
