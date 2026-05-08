# Phase 6z-5a — Pseudo-3D depth_dir 4 方向 (curve_mode → 6z-5b)

**日期**：2026-05-08
**版本**：0.14.130 → **0.14.131**
**範圍**：v0.3 design §4 Pseudo-3D 變形機制 MVP — 4 方向 perspective (depth_dir) only，curve_mode 4 軸延後 6z-5b。Per-unit local transform，sticky state 後續新 unit 自動繼承。
**前置**：6z-3.5 commit `bfbc4fd`（user-place + repeat）+ user 全 ★ Approve QODA。
**對應 commit**：本 commit。

---

## 1. QODA 紀錄（user 全 ★ Approve）

| Q | 議題 | 決定 |
|---|---|---|
| 1 | Apply pseudo_3d 到哪個 unit | **A** Last placed (auto-apply) |
| 2 | 新放置 unit 繼承 perspective state | **A** Sticky (set 一次, 後續 inherit) |
| 3 | depth_degree 控制 | **A** Slider (連續 0~1, step 0.05) |

對應 v0.3 senior review note #2（6z-5 切 a/b/c）：
- **6z-5a (本)**: `depth_dir` 4 方向 only
- **6z-5b (next)**: `curve_mode` 軸 1 (中高邊低) + visual verify
- **6z-5c**: 評估 `curve_mode` 軸 2-4 是否需要 (依 5b 視覺豐富度決定)

---

## 2. 數學設計

Per-unit local transform — 對 unit center (ucx, ucy) 做 perspective，**非全 tile 透視**。每個 placed unit 有自己的 pseudo_3d state、互相獨立。

### 2.1 4 方向公式

對點 (x, y) 相對 unit center (ucx, ucy)，dx = x - ucx, dy = y - ucy:

| dir | 視覺效果 | 公式 |
|---|---|---|
| forward (前 ↑) | foreshortening (元素往畫面深處，大→小) | k = 1 - d × 0.5; (x, y) = (ucx + dx×k, ucy + dy×k) |
| backward (後 ↓) | 元素擴張 (大→更大, sides 厚) | k = 1 + d × 0.5; 同上 |
| left (左 ←) | 右側看起來厚 (左 tilt 透視) | x' = x + dy × d × 0.4; y' = y |
| right (右 →) | 左側看起來厚 (右 tilt) | x' = x - dy × d × 0.4; y' = y |

係數選擇：SCALE_COEF = 0.5 (forward/backward 最大 ±50% scale)、SHEAR_COEF = 0.4 (left/right 最大 40% horizontal shear / unit 高度)。對 degree=1 視覺差異明顯但不過度誇張。

### 2.2 ORB / DOT 半徑 scaling

對 ORB / DOT spec，center (cx, cy) 變換後，**半徑 r 同步 scale** (forward/backward only):

- forward: r × (1 - d × 0.5)
- backward: r × (1 + d × 0.5)
- left/right: r 不變 (shear preserves area)

對應 v0.3 §4「element 往畫面深處延伸 (大→小)」 直覺：不只 center 移動，整個 orb 要視覺縮小。

### 2.3 Identity 邏輯

`depth_dir === null || depth_degree === 0` → return 原始 spec 不變動 (early-return)。重要：

- `_placedUnits[i].pseudo_3d` 是 `null` 時 不套變形
- Slider 拖到 0 時 unit 變回 axis-aligned (degree=0 即 identity)
- 既有 (6z-3.5) units 在 6z-5a 啟用後不變 (預設 pseudo_3d=null)

---

## 3. 變更清單

### 3.1 NEW `static/zentangle/pseudo3d.mjs` (~140 lines)

純 module，依賴 tangle.mjs 的 SPEC_* 常數：

- `applyPseudo3DToPoint(x, y, ucx, ucy, depth_dir, depth_degree)` — 單點 transform
- `pseudo3DRadiusScale(depth_dir, depth_degree)` — ORB/DOT r scale 因子
- `applyPseudo3DToSpec(spec, ucx, ucy, depth_dir, depth_degree)` — 對任意 spec 變形
- `applyPseudo3DToSpecs(specs, ucx, ucy, depth_dir, depth_degree)` — 陣列 convenience
- `VALID_DEPTH_DIRS = ["forward", "backward", "left", "right"]` (UI dropdown order stable)
- `isValidDepthDir(dir)` — null + 4 valid 才回 true

### 3.2 NEW `tests/test_zentangle_pseudo3d.mjs` (+21 cases)

- `applyPseudo3DToPoint`: null/0 → identity；4 方向各算一例；center point 任 dir 都不變；forward+backward symmetry
- `pseudo3DRadiusScale`: identity / left+right preserve 1
- `applyPseudo3DToSpec`: ORB/DOT scale r、LINE 兩端點都轉、null/0 returns same ref
- `applyPseudo3DToSpecs`: array convenience + empty/null guard
- `isValidDepthDir` + `VALID_DEPTH_DIRS` 順序穩定

### 3.3 `zentangle.js` (~+115 lines)

- import `applyPseudo3DToSpecs`, `isValidDepthDir`, `VALID_DEPTH_DIRS` from pseudo3d.mjs
- 新 module state:
  - `_stickyDepthDir = null` (none/forward/backward/left/right)
  - `_stickyDepthDegree = 0.5` (0..1 default 0.5)
  - `KEY_DIR_TO_PSEUDO3D = {up: "forward", down: "backward", left: "left", right: "right"}` mapping table
- `placeUnitAtClick`: 新單元 inherit `_stickyDepthDir/Degree` 進其 pseudo_3d field
- `drawTangleLayer`: 對每 unit 套 `applyPseudo3DToSpecs` (only when `unit.pseudo_3d.depth_dir` 非 null)
- 新 helpers:
  - `setPerspectiveDir(dir)` — set sticky + apply to last unit + refresh button highlight + redraw
  - `setPerspectiveDegree(degree)` — set sticky + sync last unit's degree + redraw + slider display
  - `clearPerspective()` — `setPerspectiveDir(null)`
  - `refreshPerspectiveButtonHighlight()` — active 紅底白字
  - `wirePseudo3DControls()` — 4 button + slider input + clear button + register `pseudo3d-dir` ACTION handler

### 3.4 `index.html` (+24 lines)

透視 row (在旋轉 row 後、config-display 前)：

- 4 .zt-p3d-btn (data-dir = forward/backward/left/right) + 中文 label「前↑/後↓/左←/右→」
- input range slider (0~1, step 0.05, default 0.5) — id `zentangle-p3d-slider`
- 數值顯示 span - id `zentangle-p3d-display`
- 「無透視」 button - id `zentangle-p3d-clear`
- 提示「↑↓←→ 鍵 ＝ 4 方向；套到最後 unit + sticky inherit 後續新 unit」

### 3.5 Bump

`pyproject.toml` 0.14.130 → **0.14.131**

### 3.6 Decision log

本檔。**§3.14 SOP dogfood**: Python list-of-strings + `\n.join` + `newline='\n'` + 三件套 verify。

---

## 4. 鍵盤 ACTION 整合（registry-aware dispatcher 升級的 payoff）

6z-1E `wireInputScaffolding` 已把 ↑↓←→ 鍵 dispatch 到 `ACTIONS.PSEUDO3D_DIR` action with arg `"up"/"down"/"left"/"right"`。

6z-5a `wirePseudo3DControls` register handler:

```js
_actionHandlers["pseudo3d-dir"] = (keyDir) => {
  const dir = KEY_DIR_TO_PSEUDO3D[keyDir];  // "up" → "forward" 等
  if (!dir) return;
  setPerspectiveDir(dir);
};
```

Mapping table 在 dispatch boundary 處理 — input 層保持 agnostic of perspective semantics、6z-5a domain 自己 translate。對應 6z-2c 的 ACTIONS dispatcher 升級設計（漸進加 handler 不需重做 routing）。

---

## 5. 測試

| 層級 | tool | passed |
|---|---|---|
| outline.mjs Node | `node:test` | 25/25 |
| tangle.mjs Node | `node:test` | 25/25 |
| **pseudo3d.mjs Node** | `node:test` | **21/21 NEW** |
| Backend pytest | pytest | 18 / 8 skip (font) |
| Smoke (TestClient): 透視 UI + JS hooks | TestClient | 15/15 |

**Manual E2E（待 user 視覺驗）**：

1. 切到禪繞字模式 + 點 Crescent Moon → 「先點 canvas 放第一個」
2. 點字內任處 → 1 個 crescent (axis-aligned, 預設 sticky=null)
3. 點「前 ↑」 button → last crescent 變 foreshortening (中心拉小)、button 紅底高亮
4. 點 canvas 第二位置 → 新 crescent 自動套 forward perspective (sticky inherit)
5. 拖 slider 到 1.0 → 看到 last unit 的 forward 強度加大
6. 拖 slider 到 0 → last unit 視覺變回 axis-aligned (degree=0 即 identity)
7. 點「後 ↓」 → forward 高亮關、backward 高亮開、last unit 變擴張
8. 點「左 ←」 → unit shear 視覺
9. 點「無透視」 → 所有 sticky 清掉、last unit 變 axis-aligned
10. 鍵盤 ↑ → 同點 button「前」 (KEY_DIR_TO_PSEUDO3D 翻譯)
11. 旋轉 45° → perspective unit 跟 tile 整體一起轉 (ctx transform 之上 + per-unit local 變形 之下，兩層合)
12. Reload → sticky 重置 null, _placedUnits 清空 (per-session policy)

---

## 6. P7-COMPLETION

- **任務**：Pseudo-3D depth_dir 4 方向 MVP，per-unit local transform，sticky state
- **方案**：
  - pseudo3d.mjs 純 module + Node test
  - drawTangleLayer 套 transform 在 buildUnit 之後、renderTangleSpecs 之前
  - sticky state 後續 placed unit 自動 inherit
  - ACTIONS dispatcher 接 ↑↓←→ 鍵 (KEY_DIR_TO_PSEUDO3D mapping)
- **改動**：5 files (3 mod + 2 new) + 1 new doc, ~+330 / -8 lines
- **影響分析**：
  - pseudo3d.mjs 純 export, 對 tangle.mjs 是 read-only dependency (import SPEC_* 常數)
  - drawTangleLayer 只多一個 `if (unit.pseudo_3d?.depth_dir)` 分支, 不影響 axis-aligned units
  - placeUnitAtClick 只加 pseudo_3d field initialization (null when sticky null)
  - 既有 50 + 21 (新) = 71 Node tests 全 pass、18 pytest + 15 smoke 全 pass → no regression
- **三問自審**：
  - 方案正確：是。Pure module + sticky state pattern 對齊既有 stroke-order pattern (rotation pattern + tangle dispatch + placed units)
  - 影響全面：是。grep `pseudo_3d` 在 zentangle.js 唯一 mutator (placeUnit + setPerspective*) + 唯一 reader (drawTangleLayer)；無 dangling
  - 回歸風險：低。新 dimension 預設 null=identity；不啟動就完全不影響 6z-3.5 單元行為
- **剩餘風險**：
  1. **旋轉時 perspective 視覺正確性待 user verify** — 旋轉 45° + forward 0.5 應該看到 unit 整體跟 tile 轉 + unit 自身 foreshortening (兩層 transform compose)
  2. **Slider 拖動時 last unit 即時 update 但非 last 的 unit 不動** — 是 design (sticky 只動 last)；如 user 期待全部跟動 → 6z-5a.X 補 「apply to all」 toggle
  3. **No selection mechanism** — Q1=A 只動 last unit，user 想改中間某 unit 的 perspective 做不到；6z-5a.X / 6z-9 draft 系統補 selection
  4. **Curve_mode 4 軸延後 6z-5b** — design doc 兼容 (schema 已預留 curve_mode/curve_degree field、pseudo3d.mjs 加 helper 即可)

---

## 7. 對 6z-5b/c + 後續的影響

### 6z-5b curve_mode 軸 1 (中高邊低)
- pseudo3d.mjs 加 `applyCurveModeToPoint(...)` + `CURVE_MODES = ["high-mid", ...]`
- Compose pipeline: pseudo_3d depth → curve_mode → render
- UI 加 4 button (中高邊低 / 邊高中低 / 左高右低 / 右高左低) + 同 slider 重複用

### 6z-5c curve_mode 軸 3-4 砍評估
- Senior review note #2 預埋條件：5b 視覺夠豐富 → 砍軸 3-4
- 直接拿 5b ship 後 user E2E 反饋判斷

### 6z-6 切割 mode + string layer
- pseudo_3d 不影響 string drawing — string 是 region divider, perspective 只對 tangle units
- 但 string 內可能也想套 pseudo_3d → 評估時看

### 6z-9 draft 系統
- `_placedUnits` 進 snapshot (含 pseudo_3d field)
- 30 步 bounded undo + auto-save 5 min localStorage
- pseudo_3d state 自動 serialise (純 dict 結構)

### 6z-10 gallery + .zentangle.md export
- pseudo_3d field 會 serialise 進 .zentangle.md frontmatter (per v0.3 §4.2 schema)
- 對應 mandala kind dispatch pattern (r28)

---

## 8. 經驗萃取（candidate）

> **Per-unit local transform > global transform — 對 creative tool 的元素級控制，per-unit local state + render-time apply 比 global state + pre-bake 彈性高**
>
> 6z-2 ctx transform 是「**整 tile 變換**」 (rotation/pan)，6z-5a pseudo_3d 是「**每 unit 變換**」。兩者抽象不同：
> - 整 tile = ctx.save/translate/rotate/restore (ctx-level)
> - 每 unit = unit.pseudo_3d 進 schema, render time 套 pure helper (data-level)
> - 兩者 compose: tile transform → unit transform → 最終 render
>
> 對應 v0.3 §4 「Pseudo-3D 是 stroke-level 變形、tile rotation 是 viewport-level」 區分。

候選 memory；若 6z-5b/6/9 出現相同 pattern 就升格進 PRINCIPLES.md。

---

## 9. 配對 reference

- 6z-3.5 commit：`bfbc4fd` (user-place 提供 pseudo-3D 的 target stroke)
- 6z-2.1 commit：`e05f705` (ctx transform 整 tile 旋轉，本 phase 的「**外層**」)
- v0.3 design doc §4 Pseudo-3D 變形機制：[`2026-05-06_phase6z_zentangle_design_v0.3.md`](2026-05-06_phase6z_zentangle_design_v0.3.md)
- v0.3 design doc §4.2 schema (pseudo_3d field 預設值 + degree)
- Senior review note #2: 6z-5 切 a/b/c 對應策略
- Memory `feedback_pure_helper_for_node_test` (pseudo3d.mjs 對應)
- Stroke-order PRINCIPLES.md §6.11 (Canvas 整體 transform)
