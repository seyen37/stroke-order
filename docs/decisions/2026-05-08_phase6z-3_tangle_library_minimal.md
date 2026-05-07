# Phase 6z-3 — ICSO + 2 tangle minimal MVP + pure mode mask

**日期**：2026-05-08
**版本**：0.14.128 → **0.14.129**
**範圍**：Phase 6z 第三 sub-phase MVP — ICSO 5 spec types + 2 tangle (Crescent Moon / Florz) + inline tangle picker + △/R 鍵 cycle action + pure-mode 用 outline 做 Path2D clip。
**前置**：6z-2.3 commit `5eca676`（pan button 箭頭修正）+ user 全 ★ Approve QODA。
**對應 commit**：本 commit。

---

## 1. QODA 紀錄（all ★ confirmed）

| Q | 議題 | 決定 |
|---|---|---|
| 1 | Tangle picker UI | **B** Inline radio row (對齊 mode/tile pattern) |
| 2 | 初始 tangle 數量 | **B** 2 個 (Crescent Moon + Florz) |
| 3 | Mode 視覺實作 | **B** 只 pure mode (hollow/bg → 6z-3.X) |
| 4 | 套用方式 | **A** 自動 (radio change 即 apply) |

---

## 2. 變更清單

### 2.1 新模組 `static/zentangle/tangle.mjs` (~210 lines)

**Spec types** (純資料格式，可 serialise / Node test)：
- `SPEC_LINE`     {type, x1, y1, x2, y2}
- `SPEC_CURVE`    {type, x1, y1, cx, cy, x2, y2} (quadratic)
- `SPEC_S_SHAPE`  {type, x1, y1, x2, y2} (renderer 自算 control points)
- `SPEC_ORB`      {type, cx, cy, r, startAngle?, endAngle?, fill?}
- `SPEC_DOT`      {type, cx, cy, r}

**Pure generators**：
- `buildCrescentMoon(area, density)` — 半弧 row 配下方 dot
- `buildFlorz(area, density)` — 4 petal 幾何花 + 中心 dot

**Registry**：
- `TANGLES` dict (key → {label, build})
- `listTangles()` 給 UI dropdown / cycle order
- `buildTangle(key, area, density)` dispatch

**Renderer**：
- `renderTangleSpecs(ctx, specs)` — 機械 mapping 5 spec types → ctx 操作

**Density enum**：`low / medium / high` → spacing px (70 / 45 / 28)。6z-3 fixed medium，未來 6z-3.X 加 L3 cycle UI 接 density。

### 2.2 `tests/test_zentangle_tangle.mjs` (+17 cases)

- 5 spec const stable
- buildCrescentMoon 回 array、type 分布、orb geometry 完整、density 影響 count、empty area / null → []
- buildFlorz 4-petal 比例 (orbs == 4 × dots)、density scale、empty area
- listTangles 6z-3 MVP = 2 個、entries 都有 key+label
- buildTangle dispatch + unknown key throw
- TANGLES registry shape
- 邊角情境：tiny area 少於 spacing、rectangular area、offset area 座標仍 ≥ origin

### 2.3 `zentangle.js` (~+90 lines)

**新 imports** from `tangle.mjs`：TANGLES / buildTangle / renderTangleSpecs / listTangles

**新 module state**：
- `_activeTangle = "none"` (per-session)
- `TANGLE_DENSITY = "medium"` (constant for 6z-3)
- `TANGLE_STROKE / FILL / LINE_WIDTH` (style consts)

**新 helpers**：
- `drawTangleLayer(mappedContours)` — build outline Path2D + ctx.clip("evenodd") + render specs
- `setActiveTangle(key)` — validate + sync radio + redraw + status
- `cycleTangle()` — order ['none', ...registered keys] cycle，loop
- `wireTangleControls()` — radio change listener + register `cycle-tangle` ACTION handler

**redrawAll 升級**：在 `drawOutline(mapped)` 後加 `drawTangleLayer(mapped)`，inside `withTileRotation` 內 → tangle 自動 inherit 旋轉 + pan + tile_size resize。

**wireRotationControls 末段**：增 `wireTangleControls()` call。

### 2.4 `index.html` (+10 行)

`<div id="zentangle-view">` 內加 tangle row：
```html
<div class="row">
  <span>Tangle</span>
  <label><input type="radio" name="zentangle-tangle" value="none" checked> 無</label>
  <label><input type="radio" name="zentangle-tangle" value="crescent_moon"> Crescent Moon</label>
  <label><input type="radio" name="zentangle-tangle" value="florz"> Florz</label>
  <span>△ 鍵 / R 鍵 cycle 切換</span>
</div>
```

### 2.5 Bump

`pyproject.toml` 0.14.128 → **0.14.129**

### 2.6 Decision log

`docs/decisions/2026-05-08_phase6z-3_tangle_library_minimal.md`（本檔）

---

## 3. Pure mode visual mask 設計

**Q3=B 決定**：6z-3 只做 pure mode 視覺、hollow/bg fallback 到 pure。Why：

1. Pure mode 是禪繞字 thesis 「字內填充 tangle」 最直觀 instance
2. Hollow (字外圍填) / Bg (整磚填+字反白) 涉及 reverse-mask 邏輯、非 trivial
3. 從 minimal pure 起步 → user 看到 tangle effect → 後續 6z-3.X 漸進加 hollow/bg variant

**實作**：Canvas Path2D + `ctx.clip(path, "evenodd")`：

```js
const clipPath = new Path2D();
for (const poly of mappedContours) {
  clipPath.moveTo(poly[0][0], poly[0][1]);
  for (let i = 1; i < poly.length; i++) clipPath.lineTo(...);
  clipPath.closePath();
}
ctx.save();
ctx.clip(clipPath, "evenodd");
renderTangleSpecs(ctx, specs);
ctx.restore();
```

**關鍵: `evenodd` fill rule**：處理 nested contours 正確（如「日」 的外框 + 內框）。Even-odd 規則：點在偶數個 contour 內 = 透明，奇數個 = 填色。對「日」 = 外框內 (1 contour) 是字、加上內框內 (2 contours) 是 hole。User 直覺對齊。

---

## 4. 測試

| 層級 | tool | passed |
|---|---|---|
| outline.mjs Node | `node:test` | 25/25 |
| **tangle.mjs Node** | `node:test` | **17/17 NEW** |
| Backend pytest | pytest | 18 / 8 skip (font) |
| Smoke (TestClient): tangle UI + JS hooks | TestClient | 10/10 |

**Manual E2E（待 user 視覺驗）**：
1. 切到禪繞字模式 → 看到「心」字框 + tangle row 「無 / Crescent Moon / Florz」
2. 點「Crescent Moon」 → 字內部出現半弧 + 點 grid 圖案 (clip 在 outline 內)
3. 點「Florz」 → 字內部出現 4-petal 花圖案
4. 點「無」 → 圖案消失、保留字框
5. 旋轉 45° → tangle 跟字一起轉 (因在 withTileRotation 內)
6. 切「Bijou」 → tangle 跟字一起縮 (用 cache，不重 fetch)
7. 改字「日」 → 重 fetch outline + tangle 重 render in 雙 contour 內 (evenodd 在內框是 hole)
8. 鍵盤 R → cycle tangle (none → crescent_moon → florz → none → ...)
9. Reload → tangle 重置 "無" (per-session, mirrors _rotationDegrees / _panState policy)

---

## 5. P7-COMPLETION

- **任務**：ICSO 5 spec types + 2 tangle (Crescent Moon / Florz) + inline picker + △/R cycle + pure mode clip mask
- **方案**：tangle.mjs 純 module (spec types + 2 generators + dispatch + renderer) + zentangle.js 加 _activeTangle state + drawTangleLayer (Path2D + clip evenodd) + wireTangleControls
- **改動**：3 files mod + 2 new (tangle.mjs + test) + 1 new doc, ~+340 / -2 lines
- **影響分析**：
  - tangle.mjs 全 export，無 side effect import (純模組)
  - zentangle.js 新加 import — 既有 outline import 不變
  - drawTangleLayer 在 redrawAll 末段、不影響 frame / outline 既有 pipeline
  - tangle render 自動 inherit ctx transform (旋轉 + pan + tile_size 同步) — 因為在 withTileRotation 內
  - 既有 33 + 17 (新) = 50 Node tests 全 pass、18 pytest pass、smoke 10/10 → no regression
- **三問自審**：
  - 方案正確：是。Pure spec types + dispatch dict + Path2D clip 都對齊既有 stroke-order pattern (mandala by-kind dispatch + .mjs pure helper + Node test)
  - 影響全面：是。grep `cycle-tangle` 確認 ACTION dispatcher 接得起來; redrawAll 路徑全經 drawTangleLayer
  - 回歸風險：低。新加層 (tangle) 在既有 frame+outline 之上、預設 "none" → 對既有視覺零影響
- **剩餘風險**：
  1. **Hollow / bg mode 視覺 fallback 到 pure** — user 可能期待切 mode 看到差異，但 6z-3 沒做。Status 提示已 noted in 6z-1.2 commit message；6z-3.X 補
  2. **Density 固定 medium** — 沒 UI 調 density，6z-3.X 加 L3 cycle 後接 density radio
  3. **Tangle 圖案是 minimal 簡化版** — 真正 Crescent Moon / Florz 在禪繞傳統有更複雜 step；6z-3 只示範 ICSO 組合 + dispatch + clip 架構，視覺豐富度由 user 反饋驅動 6z-3.X 細化
  4. **Tile rotation > 0 時 area 計算仍用 axis-aligned bbox** — Tangle area 是 tile-local px (margin inset) 後再經 ctx transform；旋轉後 visual 看起來 tangle 「跟著轉」 是對的，但 area 邊界本身是 axis-aligned bbox，旋轉後不是 viewable axis-aligned；對 clip 行為無影響（clip 是用 outline path 不是 bbox）
  5. **Pan-state 跟 tangle 互動** — Pan 時 tangle 已被 ctx.translate 影響、跟字一起 shift，符合「紙磚整體 pan」 直覺
  6. **「日」 之類 nested contour 的 evenodd clip 視覺正確性 待 user verify** — 預期內框是 hole、tangle 不該填內框；如果視覺上錯就是 evenodd vs nonzero 規則 + contour 順序問題

---

## 6. 對 6z-3.X 的影響

**6z-3.1 (predicted)**：可能 user 反饋「想看 hollow / bg 視覺差異」 — 加 mode-aware drawTangleLayer dispatch (clip inside vs outside vs whole tile + outline reverse)

**6z-3.2 (predicted)**：density 控制 UI (radio + L3 ACTION 接到既有 dispatch)

**6z-3.3+**：補另外 4 個 tangle (Hollibaugh / Tipple / Mooka / Static)

**6z-4 (full input wiring)**：`cycle-tangle` ACTION 已 register，6z-4 只需把 △ button (gamepad) 接到同 dispatcher，鍵盤 R 已 work

**6z-5 (Pseudo-3D)**：透視變形可加 layer 在 tangle 之前/之後，不影響本 phase 架構

---

## 7. 配對 reference

- 6z-2.3 commit：`5eca676`（pan button 箭頭修正）
- 6z-2.2 commit：`0c34a83`（pan buttons）
- v0.3 design doc §3 軸 3 「6 個 tangle 庫」 (6z-3 MVP 只做 2)
- v0.3 design doc §4「Pseudo-3D 變形」 — 6z-5 將疊加在 tangle 之上
- Memory `feedback_pure_helper_for_node_test`（tangle.mjs 對應此 pattern）
- Memory `feedback_by_kind_dispatch_dict`（TANGLES registry 對應 mandala kind dispatch pattern）
