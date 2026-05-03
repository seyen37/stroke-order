# Phase 5b r26：Mandala 線條顏色 + G-code 色彩分組 + ring 0 警示

**日期**：2026-05-04
**版本**：0.14.104 → 0.14.105
**範圍**：3 大功能合併
- 裝飾層 ring 0 警示提示
- 線條顏色（11 色 preset + custom，per-layer / 主 mandala / 字布局）
- G-code 按色分組輸出（comment 標籤）

**測試**：`tests/test_mandala.py` +8 → 120 passed（全 web suite 142 passed）

---

## 1. 動機

User 反饋三件事：

1. ring 0（0–10 mm 同心區）半徑非常小，裝飾層幾乎重疊在中心點，預設 0 環 + 1 層 default 容易誤導 user。
2. 寫字機需要不同顏色的線條 — 預設黑色，要支援曼陀羅常用色 + 自訂色，每層可獨立著色。
3. 寫字機只有單支筆，G-code 若色彩交錯輸出會強迫頻繁換筆。希望同色線條打成 batch。

## 2. 三大決策

### 2.1 ring 0 警示（功能）

Conditional banner — 只在「ring 0 是唯一存在的 ring」時顯示：

```
⚠️ 0 環半徑非常小（0–10 mm），裝飾層幾乎重疊在中心點，
難以辨識且容易跟中心字撞。建議先按「＋ 增加環」、在較外層（≥ 20 mm）加裝飾層。
```

`mandalaUpdateExtrasCount` 偵測 ring 數 == 1 且 `data-ring="0"` 即顯示，否則隱藏。

> Why conditional rather than永久：r25 預設啟動就有 ring 0 + 1 層；如果 user 已加 ring 1+ 那他懂結構了，不需要 banner 干擾。

### 2.2 線條顏色（核心）

**11 色 palette**（曼陀羅常用）：黑 `#000000`、紅 `#c0392b`、橘 `#e67e22`、金 `#d4af37`、黃 `#f1c40f`、綠 `#27ae60`、青 `#16a085`、藍 `#2980b9`、紫 `#8e44ad`、粉 `#e91e63`、棕 `#8b4513`。預設黑色。

**Backend layer 結構新增 `color` 欄位**：

```js
{ "style":"dots", "n_fold":12, "r_mm":15.0, "color":"#c0392b", ... }
```

`render_extra_layer_svg` 從 `layer.color` 取（default `"#000000"`），dispatch 給每個 primitive 函數的 `stroke_color`/`fill_color` 參數。17 個 primitive 早就有這些參數（之前 hardcoded `"#222"`），dispatcher 傳值即可。

**全域 2 個新 render_mandala_svg 參數**：

- `mandala_line_color` — 主 mandala primitive（interlocking_arcs / lotus_petal / radial_rays）
- `char_line_color` — 中心字 + 字環的字筆畫 stroke + outline fill

`_place_char_svg` 從 wordart.py 加 `color: str = "#222"` 參數，內部 `<g fill="..." stroke="...">` 用變數。Default `"#222"` 維持其他 wordart 模式向後相容。

**API 接收**：

- `/api/mandala?mandala_line_color=#000000&char_line_color=#000000` — 6-digit hex 正則驗證
- `extra_layers_json` 內 layer 加 `color` field

**前端 UI 共用 helper `_mandalaWireColorControl(selectEl, pickerEl, initHex)`**：

每處顏色控制 = `<select>`（11 色 preset + 「自訂…」option）+ `<input type="color">`。雙向 sync：
- select 變 → picker.value 跟著變；select=「自訂…」 → 觸發 `picker.click()` 開 native picker
- picker 手動變 → 找 hex match preset，否則 select 切到 「自訂…」(空 value)

控制 3 處：主 mandala (`md-mandala-color`)、字布局 (`md-char-color`)、每 layer row (`.md-layer-color`)。

### 2.3 G-code 按色分組（核心）

**問題**：寫字機是單筆機械，pen 換色要人工。如果 polyline 順序是 [紅, 綠, 紅, 藍, 綠]，user 要換筆 5 次。

**解決**：`render_mandala_gcode` 改造成 color-aware：

1. SVG walk 時記錄當前 stroke / fill（從 element / 父 `<g>` 繼承）
2. 每 polyline 用 helper `_resolve_color(elem, parent_stroke, parent_fill)`：stroke 不為 none 用 stroke，否則 fill，否則 default `#000000`
3. 收集為 `tagged_polylines: list[(color, points)]`，order-stable
4. **首次出現順序決定 group 順序**（dict iteration order 在 Py3.7+ 保證）
5. 每 color group 前 emit comment：
   ```
   ; ===== COLOR: #c0392b =====
   ; polylines in this color: 18
   ; --- pause / change pen to #c0392b ---
   ```

通用 `;` 註解格式不綁定具體機器（M6 / M0 / 自訂指令 user 看 comment 自行對應），保持最大相容性。

> 為何 stable order 重要：user 會期望 ring 由內到外執行（接近他在 UI 看到的順序）。dict 保持插入順序，第一次見到的 color 拿到最前面 group，後續同色塞回該 group → 視覺上跟 layer 列表順序一致。

## 3. 棄用 / 變更

| Before | After |
|---|---|
| primitive `stroke_color="#222"` default | 仍保留（內部 default），但 `render_extra_layer_svg` 預設改傳 `#000000` |
| `_place_char_svg(c,x,y,size,rot)` | `_place_char_svg(c,x,y,size,rot, color="#222")` 加 optional 參數，向後相容 |
| `render_mandala_svg(...)` | 多 2 個 kwargs：`mandala_line_color="#000000"`, `char_line_color="#222"` |
| G-code: flat polyline 序列 | 按 color group，每 group 前 comment header |
| Layer schema | 新增 optional `color: str = "#000000"` |

## 4. 驗證

| 驗證項 | 結果 |
|---|---|
| `tests/test_mandala.py` | **120 passed** (112 prior + 8 r26 新增) |
| `tests/test_web_api.py` + `tests/test_web_phase5.py` | 142 passed (含 mandala 全部) |
| API E2E `/api/mandala?format=svg&extra_layers_json=...` | 200，layer 色出現在 SVG |
| API E2E `/api/mandala?format=gcode` | 200，2 個 COLOR group header |
| 壞 color 值（如 `"red"`） | 422 reject（regex 拒絕非 hex） |
| 視覺 PNG 渲染 | 紅/綠/金 3 ring 各色正確，無 cross-talk |
| JS syntax (`node --check`) | OK |

## 5. 教訓 / 未來

- **Color hex 是 single source of truth**：preset select 跟 picker 雙向 sync 都圍繞 picker.value（hex 字串）。preset select 純粹是 UX 加速器，不存自身狀態。
- **`color: optional` + `default="#000000"`**：layer schema 加新欄位時用 optional，舊 preset / 舊 frontend payload 不會壞。所有測試證明：preset 沒指定 color → 後端 fallback 黑色，gcode 只有 1 個 group 沒問題。
- **G-code comment 比 M6 通用**：M6 T<n> 是 CNC 標準，但寫字機常用自訂 M-code（M0 暫停、M5 自訂等）或無 M-code 純人工換筆。Comment 是萬用語法，user 看到 `; ===== COLOR: #xxx =====` 自然知道該換筆，且不會干擾任何 G-code interpreter。
- **stable insertion-ordered dict**：Python 3.7+ dict 插入順序保證對 user 體驗很關鍵 — 紅綠藍三 ring 從內到外，G-code 也是紅→綠→藍順序。如果改用 sorted-by-hex 會變成 #27ae60 → #2980b9 → #c0392b，跟 user 的 layer 順序不一致。
- **r25 ring 警示寫死「ring 0 唯一」條件夠精準**：避免「永遠顯示」的雜訊，又精準涵蓋 user 痛點（剛打開 mandala 模式時）。

## 6. 涉及檔案

```
src/stroke_order/exporters/mandala.py    (color 串到 17 primitives，render_mandala_svg
                                          加 mandala/char_line_color，gcode 按色分組)
src/stroke_order/exporters/wordart.py    (_place_char_svg 加 color 參數)
src/stroke_order/web/server.py            (API 加 mandala/char_line_color regex 驗證)
src/stroke_order/web/static/index.html    (3 處 color 雙控制 + ring 0 警示 banner)
tests/test_mandala.py                     (+8 r26 tests)
pyproject.toml                            (0.14.104 → 0.14.105)
```
