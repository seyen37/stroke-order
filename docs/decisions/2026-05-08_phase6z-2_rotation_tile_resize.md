# Phase 6z-2 — 紙磚旋轉 + Tile size canvas resize

**日期**：2026-05-08
**版本**：0.14.124 → **0.14.125**
**範圍**：Phase 6z 第二個 sub-phase — 旋轉 pure helper + canvas 動態 resize + 8 preset 旋轉按鈕 + slider 微調 + L1/L2 reset/prev 動作 + ACTIONS 真實 handler 取代 stub。
**前置**：6z-1.2 commit `f74c128`（inline 控件取代 modal、bump 0.14.124）+ user 全 ★ Approve QODA。
**對應 commit**：本 commit。

---

## 1. QODA 紀錄（user Approve all defaults）

| Q | 議題 | 決定 |
|---|---|---|
| 1 | 旋轉 UI | **A** 8 preset 按鈕 + slider 微調 |
| 2 | L1 / L2 wire 時機 | **A** 6z-2c 真接 wire（不留 stub） |
| 3 | Tile size 改變 | **A** Canvas width/height attribute 真實 resize |
| 4 | 旋轉中心 | **A** Canvas 中心（紙磚中心）|
| 5 | 旋轉 state persist | **B** No — per-session view state |

---

## 2. 變更清單

### 2.1 `outline.mjs` (+60 lines)

**新增** `rotateContours(contours, degrees, center)` pure helper：
- Apply 2D rotation matrix to all polyline points
- Y-down convention (positive degrees = visually CW on screen, matches「轉動紙磚」 直覺)
- Pivot 是參數 (Q4 = canvas center caller-controlled)
- Throws on non-finite degrees / malformed center
- Skips malformed points (NaN / 非 array) but keeps polyline

### 2.2 `tests/test_zentangle_outline.mjs` (+10 cases)

`rotateContours` 測：
- 0° identity
- 90° about origin: (1,0) → (0,1) (Y-down CW)
- 180° flip about origin
- 360° round-trip (within tolerance)
- 47° about non-origin pivot keeps pivot fixed
- -90° is inverse of +90°
- empty / null input → []
- non-finite degrees → RangeError
- malformed center → RangeError
- NaN points filtered, valid kept

### 2.3 `zentangle.js` (~+150 lines net)

**新增 constants**：
```js
const TILE_SIZES = {
  bijou: 360,         // ~5cm
  standard: 600,      // 9cm baseline
  apprentice: 900,    // ~13.5cm (viewport-friendly cap)
};
const TILE_MARGIN_RATIO = 0.10;
```

**新增 helpers**：
- `currentTileSize()` / `currentTileMargin()` — derive from `_config.tileSize`
- `resizeCanvasToConfig()` — set canvas.width/height + re-acquire ctx
- `applyRotation(deg, {skipHistory})` — normalise to (-180, 180], push history, redraw
- `angleReset()` / `anglePrev()` / `rotationDelta(d)` — action handlers
- `wireRotationControls()` — wire 8 preset buttons + slider + reset/prev + register ACTIONS handlers

**重構** `drawTileBackground()`：用 `currentTileSize/Margin` 取代 hardcoded `TILE_SIZE/TILE_MARGIN`。

**重構** `renderOutline()` 末段：
```js
const ts = currentTileSize();
const tm = currentTileMargin();
const mappedRaw = mapContourToTile(contours, bbox, ts, tm);
const mapped = _rotationDegrees !== 0
  ? rotateContours(mappedRaw, _rotationDegrees, [ts/2, ts/2])
  : mappedRaw;
drawOutline(mapped);
```

**升級** `dispatchAction()`：
- 從純 status-bar stub → registry-aware
- `_actionHandlers[action]` 有註冊 → call handler；否則 fallback stub
- Phase 6z-2c register: angle-reset / angle-prev / tile-rotate-delta
- 後續 6z-3+ 可漸進加 handler，無 runtime crash 風險

**Per-session 旋轉 state**（Q5=B）：
- `_rotationDegrees` 0 init，**不寫 localStorage**
- `_rotationHistory[]` bounded 16，L2 用
- Reload → 重置 0°（符合「轉動紙磚配合手部」 per-session 直覺）

**tile_size radio handler 升級**（從 6z-1.2 「視覺差異待 6z-2」 → 6z-2 真實 resize）：
```js
.addEventListener("change", (e) => {
  commitConfigChange({ tileSize: e.target.value });
  resizeCanvasToConfig();
  drawTileBackground();
  renderOutline().catch(...);
  setStatus(`紙磚尺寸 → ${TILE_LABELS[e.target.value]}`);
});
```

### 2.4 `index.html` (+30 lines)

新加旋轉 row（在 mode/tile radio row 下方、config display 上方）：
- 8 preset 按鈕 (`.zt-rot-preset[data-deg]`) 0/45/90/135/180/-135/-90/-45
- `<input type="range" min="-180" max="180" step="1" value="0">` slider
- Display span 顯示當前角度 (monospace, 0°)
- 立即回正 button (= L1/Q)
- 上次角度 button (= L2/Shift+Q)

### 2.5 Boot 流程升級

`boot()` 新加：
- `resizeCanvasToConfig()` ← 解決 reload bijou/apprentice 時 canvas 沿用 HTML 預設 600 的 bug
- `drawTileBackground()` 在 renderOutline 之前先畫一次（如 outline fetch 失敗，至少 user 看到正確尺寸的空磚）

---

## 3. 鍵盤 + 滑鼠 真實 wired

從 6z-1E ACTIONS table 對應：

| Key (per v0.3 §3.1) | ACTION | 6z-2 handler |
|---|---|---|
| Q | ANGLE_RESET | `angleReset` (rotation = 0°) |
| Shift+Q | ANGLE_PREV | `anglePrev` (history pop) |
| Ctrl+滑鼠 wheel | TILE_ROTATE_DELTA | `rotationDelta(±5)` |

PSA：滑鼠 Ctrl+wheel 已從 6z-1E 起就 dispatch TILE_ROTATE_DELTA action，但當時是 stub；現在 registry 找到 handler 就真旋轉了。

---

## 4. 測試

| 層級 | tool | passed | skipped |
|---|---|---|---|
| Outline pure (含 rotateContours) | Node `node:test` | 25 | 0 |
| Backend zentangle | pytest | 18 | 8 (font) |
| HTML smoke (旋轉 UI + JS hooks) | TestClient | 13/13 | — |

**Manual E2E (待 user 機器)**：
1. 切到「禪繞字模式」 → 看到「心」字框 + 8 個旋轉 preset 按鈕 + slider + 立即回正 / 上次角度
2. 點「45°」 → 字框旋轉 45° clockwise
3. 拖 slider 到 -30° → 字框立即跟動
4. 點「立即回正」 → 字框轉回 0°
5. 點「上次角度」 → 回到 -30°
6. 點「Bijou」 → canvas 縮到 360px、字框重 render 在小磚上
7. 點「學徒磚」 → canvas 放到 900px
8. 反覆切換 tile + 旋轉 → 視覺正確
9. 鍵盤 Q → 立即回正；Shift+Q → 上次角度
10. Ctrl+滑鼠滾輪 → 旋轉±5°（每 tick）
11. Reload page → 旋轉重置 0°（per-session，Q5=B）；tile 套上次 config

---

## 5. P7-COMPLETION

- **任務**：紙磚旋轉 + tile size canvas resize
- **方案**：`rotateContours` 純函數 (Y-down 標準 2D 矩陣) + `_rotationDegrees` per-session state + `_actionHandlers` registry-aware dispatcher 升級 + canvas attribute 真實 resize
- **改動**：4 files (3 mod + 1 new doc) + 1 modified test，~+250 / -10 lines
- **影響分析**：
  - `outline.mjs` 新加 export 不影響既有 `computeBbox/mapContourToTile/contoursAreClosed`
  - `dispatchAction` 升級為 registry-aware → 既有 6z-1E stub 行為保留 (fallback 路徑)
  - `_actionHandlers` 是 Object.create(null) — 後續 phase 漸進加 handler 安全
  - `_rotationDegrees / _rotationHistory` 是 module-level state，不污染 localStorage
  - 33 既有測試全 pass、HTML smoke 13/13 → no regression
- **三問自審**：
  - 方案正確：是。Pure rotation 與 mapping 解耦；canvas resize 解 6z-1.2 留下的「視覺差異待 6z-2」承諾
  - 影響全面：是。grep `TILE_SIZE` / `TILE_MARGIN` 確認所有 hardcoded 都改用 helper；boot 路徑加 resize 解 reload bug
  - 回歸風險：低。Pure helper Node test 100% cover；canvas state 改動局限於 zentangle 模式
- **剩餘風險**：
  1. **Slider drag 性能** — 每 input 觸發 renderOutline (含 fetch)；fetch 已 cache 同 char/source，但若 source 切換+slider 同時動可能 race。建議 6z-3 加 fetch 結果 cache + abortController；目前 6z-2 不擋
  2. **Slider 與 8 preset 的 history 互動** — slider drag 累積很多 history entry，「上次角度」 可能跳到剛才的中間值；ROTATION_HISTORY_MAX=16 限制了無限增長但 UX 上仍可能不直覺。6z-2 接受此 trade-off
  3. **學徒磚 900px 在 viewport <= 900 上會超出**；CSS `max-width:100%` 已設、視覺會自動縮小但點擊精度損失。6z+1 mobile/tablet phase 處理
  4. **Y-down vs Y-up 旋轉方向直覺** — 「轉動紙磚」直覺是「順時針=右手往右推」，Y-down 數學上正度數 = 順時針，已 align；但 user 若以「Y-up 數學課本」直覺，正度數會是逆時針。Doc 註解已說明
  5. **ACTIONS handler registry 全域 mutable** — `_actionHandlers["..."] = ...` 多次 boot 會疊（boot 是 idempotent ✓ via `_booted`，所以單頁不會疊）。SPA 多頁切換不影響因為 zentangle 模式的 boot 只跑一次

---

## 6. 對 6z-3+ 的影響

### 6z-3 ICSO + tangle 庫
- ACTIONS handlers 已建立 registry pattern → 6z-3 register: `cycle-base-shape` (□), `cycle-tangle` (△), `confirm` (✕), `cancel` (○), `repeat-3` (R1), `repeat-fill` (R2)
- Mode radio 的 fill-phase 視覺差異 (純禪繞 / 空心 / 背景) 在 6z-3 spec 階段定義
- Stroke storage schema (per v0.3 §4.2) 加進 mandala-style 的 state object

### 6z-4 input 完整 wiring
- 6z-2c 已預埋 `_actionHandlers` registry → 6z-4 不需重做架構，只 register handlers
- 鍵盤滑鼠 listener 路徑不動（dispatchAction 已升級）

### 6z-5 Pseudo-3D
- Rotation pipeline 已建立 `mappedRaw → rotated → drawn`，pseudo-3D 也插入這個 pipeline (在 rotation 之前 apply pseudo_3d transform)
- 切階段 6z-5a (depth_dir 4 dir) → 6z-5b (curve 軸 1) → 6z-5c (評估砍軸) 仍按 v0.3 design

---

## 7. 配對 reference

- 6z-1.2 commit：`f74c128`（inline 控件取代 modal）
- 6z-1.1 commit：`ca83132`（DEFAULT_CONFIG）
- v0.3 design doc：[`2026-05-06_phase6z_zentangle_design_v0.3.md`](2026-05-06_phase6z_zentangle_design_v0.3.md) §6 6z-2a/b 拆細
- ACTIONS table 與鍵盤/滑鼠/gamepad mapping：v0.3 §2.1 + §3.1
- Memory `feedback_pure_helper_for_node_test`（rotation logic 抽 .mjs 對應此 pattern）
- Memory `feedback_visual_render_verify`（待 user 機器 PNG verify）
