# Phase 6z-5b — Curve mode 軸 1 (中高邊低) 加 pseudo_3d 第二維度變形

**日期**：2026-05-08
**版本**：0.14.131 → **0.14.132**
**範圍**：v0.3 §4.1 L-stick 4 軸 deformation curvature 的軸 1 (high-mid) 落實。pseudo_3d 從 depth_dir 單維度擴張到「depth + curve」 雙維度可獨立 compose。軸 2-4 在 pure module 預埋、UI 留 6z-5c 視覺評估後解鎖。
**前置**：6z-5a commit `db7cbda`（depth_dir 4 方向）+ user 直接選 A 不細問 QODA → 默認 6z-5b 設計與 6z-5a 對稱。
**對應 commit**：本 commit。

---

## 1. 設計對稱性（與 6z-5a 對齊）

6z-5b 跟 6z-5a 是同一思路的鏡像 — 把單維度 (depth_dir) 變雙維度 (depth + curve)，UI / state / dispatch pattern 全套用既有架構：

| 維度 | 6z-5a (depth_dir) | 6z-5b (curve_mode) |
|---|---|---|
| 4 方向 enum | forward / backward / left / right | high-mid / high-sides / left-high / right-high |
| Sticky state | `_stickyDepthDir` + `_stickyDepthDegree` | `_stickyCurveMode` + `_stickyCurveDegree` |
| Pure helper | `applyPseudo3DToPoint/Spec/Specs` | `applyCurveModeToPoint/Spec/Specs` |
| UI button class | `.zt-p3d-btn[data-dir]` | `.zt-curve-btn[data-curve]` |
| UI slider | `#zentangle-p3d-slider` | `#zentangle-curve-slider` |
| 6z-5b MVP UI 暴露 | 4 方向全 | **only 軸 1「中高 ⌒」** (其餘 3 軸 留 6z-5c) |
| Compose 順序 | spec → depth → render | spec → depth → curve → render |

對稱設計減少認知負擔 + 6z-5c 解鎖剩餘 3 軸只需 1 行 HTML + 0 行 JS（pure module 已支援全 4 軸）。

---

## 2. 數學設計

curve_mode 是 **y-shear-only** 變形 (對 X 軸不變、Y 沿 X 位置 curve)。對 unit center (ucx, ucy) 局部、`unit_scale` 作 normalising factor:

```
tx = clamp(dx / unit_scale, -1, 1)
switch (curve_mode):
  case "high-mid":   curve = 1 - tx²       // 中央 1, 邊緣 0
  case "high-sides": curve = tx²            // 邊緣 1, 中央 0
  case "left-high":  curve = (1 - tx) / 2   // 左 1, 右 0
  case "right-high": curve = (1 + tx) / 2   // 右 1, 左 0
y' = y - curve * curve_degree * unit_scale * 0.5  // Y-down 故 -y 視覺往上
```

CURVE_COEF = 0.5 — 在 degree=1 + tx=0 (中央) → max y-offset = 0.5 × unit_scale。對 unit_scale=45 → 22.5 px lift。

### 2.1 為何 r 不變 (對比 depth_dir)

| Transform | 影響 | r scaling |
|---|---|---|
| depth_dir forward/backward | uniform scale around center | r × scale_factor (forward 縮 / backward 放) |
| depth_dir left/right | x-shear (preserve area) | r 不變 |
| **curve_mode (4 軸)** | y-shear (preserve x extent + area) | r 不變 |

curve 是 shear (剪切) 不是 scale，所以 ORB / DOT 半徑保持不變。

---

## 3. 變更清單

### 3.1 `pseudo3d.mjs` (+~80 lines)

- `VALID_CURVE_MODES = ["high-mid","high-sides","left-high","right-high"]`
- `isValidCurveMode(mode)` validator
- `applyCurveModeToPoint(x, y, ucx, ucy, curve_mode, curve_degree, unit_scale)`
- `applyCurveModeToSpec(spec, ...)` — per spec type (LINE / CURVE / S_SHAPE / ORB / DOT)
- `applyCurveModeToSpecs(specs, ...)` — array convenience
- 內部 switch 已實作 全 4 軸 (邏輯預埋, UI 6z-5b 只暴露「high-mid」)

### 3.2 `tests/test_zentangle_pseudo3d.mjs` (+19 cases, 40 total)

- identity: null mode / 0 degree / 0 unit_scale 全 returns identity
- high-mid: center max lift / edges unchanged / mid-distance proportional
- high-sides: inverse of high-mid (center 不變 / edges max)
- left-high / right-high: 各自端點 max lift
- x is never changed (curve is y-shear only) — 全 4 mode 同驗
- clamps |dx/us| > 1 (defensive against points outside unit_scale)
- ORB transforms center, preserves r
- LINE transforms both endpoints
- null mode returns same ref (no copy)
- isValidCurveMode + VALID_CURVE_MODES 順序穩定

### 3.3 `zentangle.js` (~+105 lines)

- import `applyCurveModeToSpecs`, `isValidCurveMode`, `VALID_CURVE_MODES`
- 新 module state:
  - `_stickyCurveMode = null` (parallel to `_stickyDepthDir`)
  - `_stickyCurveDegree = 0.5`
- `placeUnitAtClick`: pseudo_3d field 擴增 4 fields (depth_dir, depth_degree, curve_mode, curve_degree)；只要任一 sticky 非 null 就建立 pseudo_3d obj
- `drawTangleLayer`: 鏈式 transform — `spec → depth → curve → render` (各 transform 獨立 if guard, null/0 早 return)
- 新 helpers:
  - `setCurveMode(mode)` — 不破壞 depth_dir 設定 (僅 modify curve fields)
  - `setCurveDegree(degree)` — 同步 sticky + last unit
  - `clearCurveMode()` — `setCurveMode(null)`
  - `refreshCurveModeButtonHighlight()` — active 紅底白字
  - `wireCurveModeControls()` — button + slider + clear

### 3.4 `index.html` (+18 lines)

曲度 row（在透視 row 後、config-display 前）：

- 1 button `.zt-curve-btn[data-curve="high-mid"]`「中高 ⌒」
- 強度 slider `#zentangle-curve-slider` (0~1, step 0.05, default 0.5)
- 數值顯示 `#zentangle-curve-display`
- 「無曲度」 reset button
- 提示「6z-5b MVP only 軸 1; 邊高中低 / 左高右低 / 右高左低 留 6z-5c」

### 3.5 Bump

`pyproject.toml` 0.14.131 → **0.14.132**

### 3.6 Decision log

本檔。**§3.14 SOP dogfood** — Python list-of-strings + 三件套 verify。

---

## 4. Pipeline compose verify

Per-unit transform pipeline 從 6z-5a 1 層 → 6z-5b 2 層 chain:

```
// drawTangleLayer 內 per unit:
let specs = buildUnit(...);
if (depth_dir) specs = applyPseudo3DToSpecs(...);    // 6z-5a
if (curve_mode) specs = applyCurveModeToSpecs(...);  // 6z-5b NEW
renderTangleSpecs(ctx, specs);
```

兩個 transform 各自 commute 可獨立啟用 — null/0 短路。

Compose 順序：depth_dir 先（uniform scale around center 是 affine、不破 axis-alignment）→ curve_mode 後（y-shear 套在 perspective 後的座標上）。順序倒過來不會炸但視覺直覺差 — 先「立體」 後「彎曲」 比 先「彎曲」 後「立體」 自然。

---

## 5. 測試

| 層級 | tool | passed |
|---|---|---|
| outline.mjs Node | `node:test` | 25/25 |
| tangle.mjs Node | `node:test` | 25/25 |
| pseudo3d.mjs Node | `node:test` | **40/40 (+19 new curve mode)** |
| Backend pytest | pytest | 18 / 8 skip (font) |
| Smoke (TestClient): 11 hooks | TestClient | 11/11 |

**Manual E2E（待 user 視覺驗）**：

1. 切到禪繞字 + 點 Florz radio + 點字內 → 1 個 axis-aligned florz
2. 點「中高 ⌒」 → last florz 中央 4 petals 拉高、edges 不動 (parabola 拱起)
3. 拖 curve slider 0.5 → 0 → 1 → 視覺強度連續變化
4. 點 canvas 第二位置 → 新 florz 自動套 curve mode (sticky inherit)
5. 點「前 ↑」 (depth_dir) + curve still on → unit 同時 foreshorten + curve (兩 transform compose)
6. 點「無透視」 → depth 清掉、curve 仍 active (獨立)
7. 點「無曲度」 → curve 清掉、depth 仍 active (獨立)
8. 旋轉 45° + curve 0.8 + depth forward 0.4 → 紙磚整體旋轉 + 每 unit foreshorten + curve 三層 compose
9. Reload → curve sticky 重置 null

---

## 6. P7-COMPLETION

- **任務**：curve_mode 軸 1 (high-mid) MVP，per-unit local y-shear, sticky state, depth + curve 雙維度可獨立啟用
- **方案**：
  - pseudo3d.mjs 加 curve helpers (4 軸全實作但 UI 只暴露 1)
  - drawTangleLayer chain depth → curve transforms
  - sticky state mirror 6z-5a pattern
- **改動**：5 files (3 mod + 1 mod test) + 1 new doc, ~+200/-5 lines
- **影響分析**：
  - pseudo3d.mjs 新 export 不破既有 21 cases
  - drawTangleLayer 鏈式 if guard, null/0 早 return — 既有 only-depth units 不影響
  - 6z-5a UI / state / handler 完全不動 — 兩維度互不干涉
  - 既有 25+25+21 = 71 → 25+25+40 = 90 Node tests 全 pass; 18 pytest + 11 smoke 全 pass
- **三問自審**：
  - 方案正確：是。對稱於 6z-5a (sticky / button / slider / dispatcher)；pure module 預埋 4 軸方便 6z-5c 解鎖
  - 影響全面：是。grep `curve_mode` 確認 placeUnit + drawTangleLayer + setCurveMode 三點 mutator/reader 配對
  - 回歸風險：低。新加維度預設 null=identity；不啟動就完全不影響 6z-5a 視覺
- **剩餘風險**：
  1. **視覺正確性待 user verify** — 高-邊低 curve 在 Florz 4 petals 上的 visual effect (北/南 petal 同時拉高、東/西 不動) 預期為 「拱形」，但 user 可能覺得不像「中高邊低」 描述
  2. **CURVE_COEF = 0.5 不一定是甜蜜點** — 跟 SCALE_COEF 一樣是工程選的；若視覺太強 / 太弱、可調
  3. **6z-5c 是否解鎖剩 3 軸？** — 視覺評估後決定；技術成本 = 1 行 HTML 加 3 button + 0 行 JS (邏輯已備)
  4. **L-stick 連續控制 curve_degree** (per v0.3 §4.1 「L-stick 連續控制 degree」) — 6z-5b 用 slider 模擬 (UI 連續 input)，gamepad L-stick 真接 wire 留 6z-7

---

## 7. 對 6z-5c / 6z-6+ 的影響

### 6z-5c 評估剩 3 軸

解鎖代價：

```html
<button class="zt-curve-btn" data-curve="high-sides">邊高 ⌣</button>
<button class="zt-curve-btn" data-curve="left-high">左高 ⟍</button>
<button class="zt-curve-btn" data-curve="right-high">右高 ⟋</button>
```

JS 完全不動 — pseudo3d.mjs `applyCurveModeToPoint` 已支援 4 軸。

評估維度：5b 視覺 wow factor 是否夠 → 夠就鎖、不需多 3 軸；不夠 → 6z-5c 解 3 軸看是否疊加效果更強。

### 6z-6 切割 mode

String drawing (字內 region divider) 會跟 placed units 共存 — pseudo_3d 對 strings 也能套 (string 也是 stroke)，但需要看 UX 是否要 string 跟 unit 分別獨立 perspective state。

### 6z-9 draft 系統

`_placedUnits[i].pseudo_3d` 含 4 fields (depth_dir, depth_degree, curve_mode, curve_degree) — auto-save 5 min localStorage 寫入時 schema 已 ready。

### 6z-10 .zentangle.md export

pseudo_3d block 直接 serialise 進 frontmatter (per v0.3 §4.2 schema)。

---

## 8. 配對 reference

- 6z-5a commit：`db7cbda` (depth_dir; 本 phase 對稱模板)
- v0.3 design §4.1 L-stick 4 軸 deformation curvature
- v0.3 design §4.3 Render pipeline (depth_dir + curve_mode 在同 pseudo_3d block)
- Senior review note #2: 6z-5 切 a/b/c 對應策略
- Memory `feedback_pure_helper_for_node_test`

---

## 9. 6z-5c addendum — 解鎖剩 3 curve 軸 (5/8 同日)

**版本**：0.14.132 → **0.14.133**
**範圍**：純 UI 解鎖，邏輯零改動（pseudo3d.mjs 4 軸已備）。
**對應 commit**：本 commit 同時 ship 6z-5b + 6z-5c（連續，6z-5c 是 6z-5b 的 follow-up），但分為獨立 git commit：6z-5b commit `3264f4d` + 6z-5c (本)。

### 9.1 變更

- `index.html`: 曲度 row 加 3 button
  - 「邊高 ⌣」 (high-sides)
  - 「左高 ⟍」 (left-high)
  - 「右高 ⟋」 (right-high)
- 提示文案改 「6z-5c 全 4 軸啟用；同 unit 任選一軸（換軸=覆蓋上次）」
- `zentangle.js` setCurveMode label dict 移除 `(6z-5c)` suffix

### 9.2 不需 verify

- `applyCurveModeToPoint` switch 已 cover 4 軸 + 對應 Node test 已 pass
- HTML class `.zt-curve-btn[data-curve]` 共用 wirable selector — 加新 button 自動 wired
- Sticky state machine 不需改（`_stickyCurveMode` 已能存任一 valid mode）

### 9.3 視覺差異 (對 Florz 4 petals)

| Mode | 視覺效果 |
|---|---|
| high-mid ⌒ | 中央拉高 (北/南/中心 dot 都拉)，東/西 不動 |
| high-sides ⌣ | U 形 — 東/西 拉高 (邊緣)，中央/北/南 不動 |
| left-high ⟍ | 左側 (西 petal) 拉高，右側 (東 petal) 不動 — 線性 |
| right-high ⟋ | 右側 (東 petal) 拉高，左側 (西 petal) 不動 |

### 9.4 新 sticky semantics

同 unit 切不同軸 = 覆蓋（單一軸 enum）。Sticky inherit 仍 work — 後續 placed unit 用最新 sticky curve mode。

### 9.5 P7-COMPLETION (6z-5c)

- 任務：解鎖剩 3 curve 軸
- 方案：HTML +3 button、JS 移除「(6z-5c)」 標記
- 改動：2 files, +12 / -5 lines + 本 §9 addendum
- 影響分析：純 UI 解鎖，pure module 4 軸已 Node test 100% cover；既有 90 Node + 18 pytest + 11 smoke 全 pass
- 三問：方案正確 ✓ / 影響全面 ✓ / 回歸風險 極低（純 additive UI button）
- 剩餘風險：
  1. 視覺差異待 user verify（4 軸對 Florz 是否如預期）
  2. CURVE_COEF=0.5 對 4 軸統一—若某些軸視覺強度不對等，未來可分軸調 coef
