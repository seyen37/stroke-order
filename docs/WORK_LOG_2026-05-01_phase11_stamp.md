# Work Log — 2026-05-01 — Phase 11 stamp module
> （retrofit 2026-05-02：原檔名 `WORK_LOG_2026-05-01.md`，加 topic 後綴維持與同日其他兩份 work log 一致命名。）

> Phase 11：印章模組精修（字型授權 gate 收尾 + 3 字傳統 1+2 layout + outline 字型對齊修正 + 篆書邊緣平滑度）

**版本**：0.14.0 → 0.14.1
**Commits**：9 個（c973cc0 sync 之後一路到 020cb96）
**修改檔**：`web/static/index.html`、`exporters/stamp.py`、`exporters/patch.py`、`web/server.py`、`pyproject.toml`

---

## 一、本日重點

Phase 11 是把字型授權 gate（Phase 9-10 完成）後續的 UX 收斂、印章模組的多項對齊問題、與篆書字型本身的渲染品質一次處理掉。共 8 個子任務（11a → 11h），全部 commit 完畢，無 backlog 殘餘。

關鍵 lesson：**多次 debug 都是先用 curl 直接看 backend 真實 SVG 輸出才找到 root cause**——這個經驗已沉澱進 PROJECT_PLAYBOOK §8.8（見決策日誌）。

---

## 二、子任務清單（按 commit 順序）

### 11a — 字型授權 gate 收尾（commit `9b5addd`）

3-in-1 改動：
- 7 處 select option text 簡化（移除 5/8 套說明文，改為單行「楷書（原版，預設）」「宋體」「隸書」「粗楷（純濾鏡）」「篆書（崇羲）」）
- 加 `fontStyleAuthGate` helper：使用者切到非授權字型時自動觸發 confirm dialog
- tintPreviewFill bug fix：印章外框切換不切換的問題（父 group `stroke="none"` 把子 border 也抹掉）
- 印章字數提示 1-4 → 2-5（CC BY-ND 字型最常見章長）

### 11b — 印章預覽空白 bug round 1（commit `cd64287`）

用戶回報「切到隸書/篆書印章預覽空白」。

第一輪修法：tintPreviewFill 父 group 不再設 `stroke="none"`，改用 per-element stroke check。**只解了一半**——border 出現了，但骨架線還是不見。

### 11c — 印章預覽空白 bug round 2（commit `84ac8f0`）

直接 curl `/stamp` endpoint 看實際 SVG，發現 backend 根本沒回 outline path——只回 skeleton polylines。

Root cause：`web/server.py` stamp_post 路徑的 `_upgrade_to_seal/_upgrade_to_lishu` 沒帶 `*_outline_mode="skip"` 參數，預設走 skeleton 模式，把 outline 拿掉了。

修法：loader 補 `seal_outline_mode="skip"` + `lishu_outline_mode="skip"`，1 行 fix。**這條才是真 root cause**。

→ 教訓寫進 §8.8。

### 11d — 3 字自動補「印」字（commit `439e7d8`）

用戶建議：3 字姓名章可選擇自動補「印」字湊成 2×2 排版，比例會比較協調。

加 checkbox + 字 input + `stampBuildBody` 補邏輯。預設關閉，用戶 opt-in。

### 11e — 3 字傳統 1+2 layout（commit `a60dc4a`）

用戶反饋上一輪改動仍是 3 字垂直排成單欄（不傳統）。提供台灣傳統印章圖例：第一個字（姓）置右、上下拉長；第二、三字縮小排在左側。

工程改動：
- `_placements_for_preset` 的 placement 結構從 4-tuple `(c, x, y, rot)` → 5-tuple → **6-tuple `(c, x, y, rot, w_mm, h_mm)`**——支援非均勻 size
- 新 helper `_char_cut_paths_stretched(c, cx, cy, w, h, rot)`：分離 `scale_x` / `scale_y`
- 3-char 分支邏輯：右側 surname `width=0.5×inner_w, height=0.92×inner_h`（拉高），左側兩字各 `min(inner_h×0.46, inner_w×0.50)`

curl 驗證 backend 確實回 1+2 結構後，提示用戶 hard reload (Ctrl+Shift+R) 清瀏覽器快取。

### 11f — 隸書偏下 + 字放大 + 外框加粗（commit `06258d4`）

用戶試用後三個微調：
1. **隸書偏下**：outline 字型（TTF/OTF）的 typographic baseline 在 ascender 附近（~1554/2048），不是 EM 中心。原本 EM-center 對齊讓隸書/宋體/篆書的字心偏下。
2. **字放大**：cell 利用率不足
3. **外框加粗**：default `stroke_width` 0.3 → 0.6 mm

修法：
- 新 helper `_char_outline_bbox_full_em(c)` / `_char_outline_bbox_em(c)`——回傳 outline path 的真實 bbox
- placement 換用 bbox-center 而不是 EM-center
- stroke_width default 0.3 → 0.6

### 11g — bbox-based scale（commit `690442d`）

11f 之後字還是沒撐滿 cell。Root cause：原本 EM-based scale (`size_mm / 2048`) 假設整個 EM 都是字身，但實際 outline bbox 通常只占 EM 的 ~70-80%。

改用 **bbox-based scale**：
```python
scale_x = w_mm / bbox_w_em
scale_y = h_mm / bbox_h_em
```

字 outline bbox 撐滿整個 cell。視覺上明顯填滿。

### 11h — 篆書邊緣平滑度（commit `020cb96`）

用戶：「看起來還可以，但是篆體字，字體邊緣不平滑，請問可再平滑些嗎？」

curl 取實際 SVG 分析「王」字 outline path 命令分布：
- **142 段 `L` (直線)**
- **181 段 `Q` (二次 Bezier)**
- **0 段 `C` (三次 Bezier)**

→ 結論：**崇羲篆體 OTF 字型作者用大量短直線近似平滑曲線**，這是字型設計選擇（OTF 內部資料層問題），bbox-based scale 放大後直線片段間的鋸齒就明顯，不是 stroke-order 渲染 bug。

最低風險修法：SVG `<svg>` + `<g>` 都加 `shape-rendering="geometricPrecision"`，告訴瀏覽器以精度優先 over 速度，使用最高品質 anti-aliasing。

→ patch.py 也同步加，描紅頁也受惠。
→ bump 0.14.0 → 0.14.1
→ 教訓寫進 §8.8

---

## 三、回歸測試

| Suite | 結果 |
|---|---|
| `tests/test_stamp.py` | 46 passed |
| `tests/test_patch.py` | 24 passed |

11h 提交後僅跑 stamp + patch suite（影響範圍局部），未跑全套。**TODO**：明日 morning audit 補跑全套確認 nothing else regressed。

---

## 四、Render deploy 狀態

每個 commit push origin/main 後 Render 自動重 deploy（~2-3 min）。本日 9 次 deploy 全綠。

最終生產版本：v0.14.1
URL: https://stroke-order.onrender.com/

---

## 五、Backlog（無）

Phase 11 全部 8 個子任務 (11a-11h) 完成，無遺留待辦。

---

## 六、給未來自己的話

1. **debug 流程**：UI 看到的「不對」不要直接改前端。先 curl backend endpoint，看真實輸出再判斷哪一層出問題（11b → 11c 範例：第一輪改前端只解一半，第二輪 curl 才找到真 root cause 在 backend loader）。已寫進 §8.8。

2. **outline-only 字型的座標系統**：TTF / OTF 的 typographic baseline 不在 EM 中心，bbox 中心也不等於字身中心。混用 stroke-bearing fonts (KanjiVG/G0V) 與 outline-only fonts (CNS / 隸書 / 宋體 / 篆書) 時，rendering pipeline 必須有 per-source 的座標處理。

3. **OTF 字型品質的天花板**：篆書邊緣鋸齒 root cause 在字型作者的設計選擇（用直線近似曲線），不是渲染端能完全解決的問題。`shape-rendering="geometricPrecision"` 是天花板下的 best effort。如果未來想根治，要換 TrueType 篆體字型或自訂 spline interpolator——但成本對應的價值 ratio 不高，先不做。
