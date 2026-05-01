# 2026-05-04 — Phase 12l 公司章 7-16 字 multi-short-col layout

> 把 square_official 從 1-9 字擴充到 1-16 字 + 加可複選短列位置（右行 / 中右 / 中左 / 左行）。從 12k 7/8 字單選 radio 升級為通用 multi-short-col + 集中短/平均短可切。整個 phase 1 commit (fde450d)、64 → 124 個測試、bump 0.14.17。

**版號變化**：0.14.16 → 0.14.17
**對話 / 工作期間**：user 上傳 8/10 字公司章 overlap 截圖 + 要求擴到 16 字 + 多選

---

## 整體脈絡

12k 完成 7/8 字 single-radio short col 後，user 用 16 字測試發現 cap 在 9 字。需求是擴到 16 字（4×4 perfect grid）+ 中間字數（10/11/13/14/15）也要支援 short col。同時把 12k 的 single radio 升級成 multi-checkbox（複選短列）+ 預設改右行短。

關鍵設計問題：

1. UI 在 4-col grid 顯示 3 / 4 個 checkbox？
2. 短列字數分配：每選一個 = 短 1 字（平均短），還是選 1 個 lump 全部 deficit（集中短）？
3. 7/8 字 default 從 12k 的 middle 改 right 是否 break backward compat？

3 個問題都是非顯而易見的 UX 取捨，先 plan 對齊再動工（一致 §8.7 morning audit 精神）。

---

## 決策 1：UI checkbox 數量（3 vs 4）

**觸發**：4-col grid（13-15 字）有 4 個位置可短，但 user 原話只有「右/中/左」3 個位置。

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 4-col 顯 4 個 checkbox（右 / 中右 / 中左 / 左） | 精確、user 可指定到單一欄 | UI 字串新增 |
| B | 3 個 checkbox，「中」涵蓋兩中間欄 | 跟 user 原話對齊 | 4-col 無法精確選單一中欄 |

**選擇**：☑ A

**理由**：

User 想精確控制每個短列位置（從複選需求看出來）。3 個 checkbox 在 4-col 場景會出現「選中 = 中右+中左 同時短」綁死，user 想單獨選一個無法做到。另外 layout name 多 2 個（mid-right / mid-left）對 API 影響可控（pattern validation 加 2 名）。

**後續驗證 / 結果**：✅ user 確認 A，UI 動態 3-col / 4-col 切換實作 OK。

---

## 決策 2：短列字數分配（解讀 X 平均 vs 解讀 Y 集中）

**觸發**：user 原話「選 1 個就讓它少 1，選 2 個就 2 個各少 1」vs「選 1 個 lump 全 deficit」兩種解釋。

**選項**：

| 編號 | 方案 | 14 字選 [right] 結果 | 14 字選 [right, mid-right] 結果 |
|---|---|---|---|
| X 平均短 | 每短列各少 1 字 | 不合法（k=1 < deficit 2）| [4,4,3,3] |
| Y 集中短 | k=1 lump 全 deficit | [4,4,4,2] | [4,4,3,3] |

**選擇**：☑ Y 集中短

**理由**：

User 選 Y。語意清楚：「選 1 個 short col = 該 col 少 (deficit / 1) = 全 deficit；選 k 個 short col = 各少 floor(deficit/k) + extra 給最右」。Y 的好處：

1. **單選始終有效**：14 字選 [right] = [4,4,4,2]（合法），不會出現「選太少不合法」的尷尬
2. **集中短 / 平均短 兩種視覺都做得到**：user 自己決定 k 的數量
3. **演算法簡單**：deficit 分配規則一個公式就清楚（base + extra 給最右）

**後續驗證 / 結果**：✅ 13 個 distribution 測試案例（含 7-16 字所有 deficit pattern）全綠。

---

## 決策 3：7/8 字預設從 middle 改 right

**觸發**：user 要求所有字數 default 改 right，但 12k 7/8 字 default 是 middle。

**選項**：

| 編號 | 方案 | 7 字 default 視覺 | 8 字 default 視覺 |
|---|---|---|---|
| A | 改 right（user 原話） | [3,3,1] (右 col 1 字孤立) | [3,3,2] |
| B | 維持 12k middle 為 7/8 字特例 | [2,3,2] | [3,2,3] |

**選擇**：☑ A 改 right

**理由**：

A 的 7 字 [3,3,1] 視覺上單字孤立，並非業界 majority。但 user 確認過 Y 解讀（「選 1 個就少 deficit 2 個」）。A 的好處是 default 行為一致 across 所有 char counts。User 想要 12k 視覺 [3,2,2] 的話可以勾「右行 + 中行」兩個 → counts = [3,2,2] 可重現。

代價：12k 既有「7 字 default = [2,3,2]」變了，但因 12k 沒有自動化測試 fix 該特定 layout（只測 layout option 傳得動），不算 break。

**後續驗證 / 結果**：✅ 不影響既有 64 tests，新加的 7 字 [right, middle] = [3,2,2] test 跟 [right] = [3,3,1] test 都綠。User 接受。

---

## 沒做的決策（明確擱置）

- **5 cols (17-25 字)**：超過 16 字章面 cell 太擁擠，業界少見。延後到有 user 需求才做。
- **Per-char 字身大小調整**：所有 cells 保持等大，不引入 per-cell size override。char_size_mm 仍是全域 cap。
- **長列 cell 大小區隔**：短列字 / 長列字依 col_count 算 cell_h，自動視覺差。不另外加 ratio 控制。

---

## 學到的規則 / pattern（適用未來）

- **多選 UI 比單選 default-magic 直觀**：user 要彈性時，multi-checkbox 把選擇權給 user，預設選 1 個（最常用），複選自然形成「平均/集中」。比起寫死「7 字 default = X / 8 字 default = Y」邏輯，user 自己選簡單明白。
- **deficit 分配演算法 generalize 比寫死好**：原 12k 寫死「7 字 = [3,2,2]」「8 字 = [3,3,2]」三 if-else 涵蓋 2 char counts。12l 改 `_distribute_official_short(n, cols, max_rows, short_indices)` 公式覆蓋 7-16 所有 char count。**generalize 不一定意味更難寫，反而 case 多時簡化**。
- **list[str] vs str field 向後兼容**：API field type union `list[str] | str` + `_normalize_short_cols(value)` helper 接受兩者，舊 client 傳單字串仍 work。**比起新增 v2 endpoint 簡單**。

---

## 相關檔案

- 工作紀錄：[`docs/WORK_LOG_2026-05-04.md`](../WORK_LOG_2026-05-04.md)
- 程式碼異動：
  - `src/stroke_order/exporters/stamp.py`：+4 helpers (`_square_official_grid_for` / `_short_col_name_to_idx` / `_normalize_short_cols` / `_distribute_official_short`) + square_official 分支重構
  - `src/stroke_order/web/server.py`：StampPostRequest field 升 `list[str] | str`，POST/GET 驗證 + comma-split 支援
  - `src/stroke_order/web/static/index.html`：dynamic 3-col / 4-col checkbox group + JS preset/text change hook
  - `tests/test_stamp.py`：+60 個測試（helpers unit + placement integration）
- Commit：`fde450d`
