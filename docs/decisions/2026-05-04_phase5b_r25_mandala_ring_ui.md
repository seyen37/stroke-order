# Phase 5b r25：Mandala 模式裝飾層 UI 改用「環」結構

**日期**：2026-05-04
**版本**：0.14.103 → 0.14.104
**範圍**：前端 UI（index.html）+ 後端 r_mm 支援（mandala.py，r24 結尾已備好）
**測試**：`tests/test_mandala.py` +4 → 112 passed

---

## 1. 背景

r24 之前的裝飾層 UI 結構：

- 一個 flat list（`#md-extras-list`），每個 row 是一層 layer
- 半徑用 `r_ratio`（0.05–1.0，相對 r_total = size_mm/2）
- 「+ 增加裝飾層」單一按鈕，最多 10 層

問題：

- `r_ratio` 對使用者是抽象量。實際 mandala 設計常以「離中心 N mm」為單位思考（特別是寫字機軌跡，物理單位即直接量），但 UI 強迫換算。
- 沒有空間維度的視覺分組。10 層全部攤平在一起很難視覺辨識誰跟誰共享一個徑向區帶。

## 2. 決策

改用「環」（ring）為組織單位：

- **環 = 同心 10mm 環區**：第 N 環涵蓋 (N×10) – ((N+1)×10) mm
- **最多 11 環**（idx 0–10），第 0 環一律存在
- **每環內可放最多 10 層裝飾層**
- **層全域編號**：`ringIdx × 10 + localIdx (1-based)`
  - 0 環第 1 層 → 「第 1 層」；0 環第 10 層 → 「第 10 層」
  - 1 環第 1 層 → 「第 11 層」；2 環第 1 層 → 「第 21 層」…
- **半徑單位用 mm**（`r_mm`，整數，0–200）
  - 新加層的預設值 = 該環的內邊（ringIdx × 10 mm）
  - 但 user 仍可手動設成任意值（環的標題只是視覺分組，不限制 r_mm 範圍）

## 3. 實作

### 後端（已在 r24 末段預先支援）

`render_extra_layer_svg` 加 `r_mm` 優先 path：

```python
r_mm_val = layer.get("r_mm")
if r_mm_val is not None:
    r_band = max(float(r_mm_val), 0.1)
else:
    r_ratio = float(layer.get("r_ratio", 0.5))
    r_band = max(r_total * r_ratio, 0.1)
```

向後相容：未帶 `r_mm` 的 preset / API 仍跑 r_ratio 邏輯。

### 前端（r25 主體）

DOM 結構從 flat list 改為兩層樹：

```
#md-rings-container
└── .md-ring-section[data-ring=0]
    ├── .md-ring-header
    │   ├── 「第 0 環 (0 - 10 mm)」label
    │   ├── 「+ 增加裝飾層」 button
    │   └── 「× 刪除環」 button (僅 ring > 0)
    └── .md-ring-layers
        └── .md-layer-row × N
            └── span.md-layer-idx, checkbox.md-layer-visible,
                select.md-layer-style, input.md-layer-n,
                input.md-layer-r-mm, input.md-layer-len,
                input.md-layer-width, button.md-layer-delete
```

新的 6 個 JS 函數：

| 函數 | 職責 |
|---|---|
| `_mandalaCurrentRTotalMm()` | 從 `#md-size` 推 r_total = size/2，給 r_ratio↔r_mm 轉換用 |
| `mandalaUpdateExtrasCount()` | badge 顯示 `(N 環 / M 層)`，並控 `+ 增加環` 是否 disabled |
| `mandalaRenumber()` | 全域 renumber：每 ring 內 `ringIdx*10 + localIdx` |
| `mandalaAddLayerToRing(section, cfg)` | 加 layer row 到指定 ring |
| `mandalaAddRing(ringIdx, layerCfgs)` | 加 ring section（傳 `null` 自動分配下一 idx）+ 內部 layers |
| `mandalaBuildExtraLayersJson()` | 輸出 r_mm 為主，附 r_ratio 給 helper 推 pointing |

**preset apply 改造**：依每 layer 的 `r_mm`（或 `r_ratio × r_total`）算出 ringIdx，分組到對應 ring 一次建立。

```js
const r_mm = layer.r_mm ?? (layer.r_ratio || 0.5) * r_total_est;
const ringIdx = Math.max(0, Math.min(MD_RING_MAX-1, Math.floor(r_mm / 10)));
ringMap[ringIdx] ??= [];
ringMap[ringIdx].push({...layer, r_mm});
// 確保 ring 0 一定存在
if (!ringMap[0]) ringMap[0] = [];
```

**初始化**：頁面載入時一律有 ring 0 + 1 個 default layer（style=lotus_petal, r_mm=0）。

## 4. 棄用 / 移除

| 移除項 | 取代 |
|---|---|
| `mandalaAddLayerRow(cfg)` | 拆成 `mandalaAddRing` + `mandalaAddLayerToRing` |
| `_mandalaRenumberRows` | `mandalaRenumber`（多一層 ring loop） |
| `#md-extras-list` element | `#md-rings-container` |
| `#md-extras-add` button | `#md-add-ring` + per-ring `.md-add-layer-to-ring` |
| `.md-layer-r` input (r_ratio) | `.md-layer-r-mm` input (mm) |
| `MD_LAYER_MAX = 10` | `MD_RING_MAX × MD_LAYERS_PER_RING = 11 × 10 = 110`（理論上限） |

## 5. 驗證

- **單元**：`tests/test_mandala.py` +4 cases（112 pass）
  - `test_extra_layer_r_mm_overrides_r_ratio` — r_mm 蓋 r_ratio
  - `test_extra_layer_r_ratio_fallback_when_no_r_mm` — r_ratio fallback 路徑保留
  - `test_extra_layer_r_mm_zero_uses_minimum_radius` — r_mm=0 不爆
  - `test_extra_layer_r_mm_supports_far_outside_r_total` — r_mm > r_total（如 ring 10 = 100-110mm）仍渲染
- **API 端到端**：FastAPI testclient 帶 4-ring `extra_layers_json`，回 200 SVG，dot 數正確
- **視覺**：cairosvg 出 PNG 4 ring 同時渲染（r_mm = 5/25/55/95），各 ring 在預期半徑出現
- **JS syntax**：node --check 通過
- **向後相容**：sample 3 個舊 preset（lotus_throne / dharma_wheel / kuji_in，全 r_ratio）渲染正常

## 6. 教訓 / 未來

- **物理單位 > 比例**：寫字機軌跡是 mm 單位，UI 跟著 mm 走比 r_ratio 直觀。但保留 r_ratio 作為 layer schema 的 fallback path 以保 preset 向後相容（也讓 helper 可推 pointing）。
- **環為「視覺分組容器」非「物理約束」**：使用者可在 0 環裡放 r_mm=80 的 layer，UI 不阻止。環只是 organizational hint + 預設值來源。這比強約束簡單，且不會誤刪使用者意圖。
- **層編號跨環需保留 gap**：每環封頂 10 層保證全域 numbering 不撞（ring 0: 1-10, ring 1: 11-20, ...）。如果未來要超出，需重新設計 numbering scheme。

## 7. 涉及檔案

```
src/stroke_order/web/static/index.html  (UI 重寫 + JS 6 函數替換)
src/stroke_order/exporters/mandala.py   (r_mm fallback path，r24 末段已就位)
tests/test_mandala.py                    (+4 r25 tests)
pyproject.toml                           (0.14.103 → 0.14.104)
```
