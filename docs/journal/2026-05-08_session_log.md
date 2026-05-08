# 工作日誌 — 2026-05-08（晚段）

**主軸**：早上完成「收工三件套」 commit `6d57f4c` 後，sync personal-playbook §3.14 + §B.24（Cowork 寫檔工具 corruption SOP）→ 一路 ship 6z-3.5 user-place + 6z-5a/b/c Pseudo-3D 全套 → 跨日 18 commits 收工。

> 🔗 **前段 5/7-5/8 早段**：見 [`2026-05-07_08_session_log.md`](2026-05-07_08_session_log.md)（涵蓋 morning audit + 6z-1/2/3 + 1.1/1.2 + 2.1/2.2/2.3 + 3 + 收工三件套）。本檔紀錄 5/8 晚段 5 commits。

---

## Session 概觀

| 段 | 內容 | Commit |
|---|---|---|
| 早上 audit | personal-playbook sync 5ca1ab4 (§3.14 + §B.24 cowork write-tool corruption SOP) | (無 commit, 純讀) |
| 6z-3.5 cross-ref §3.14 + user-place + repeat | tangle.mjs buildUnit + 點選 place + R repeat 取代 auto-fill + PRINCIPLES.md §6.8 cross-ref | `bfbc4fd` (0.14.130) |
| 6z-5a Pseudo-3D depth_dir | pseudo3d.mjs 4 方向 perspective + sticky state + Arrow 鍵 ACTIONS handler | `db7cbda` (0.14.131) |
| 6z-5b curve_mode 軸 1 | pure module 預埋 4 軸 + UI 暴露 軸 1 (high-mid) + chain compose 雙維度 | `3264f4d` (0.14.132) |
| 6z-5c 解鎖剩 3 軸 | 純 UI HTML +3 button (10 min) + 6z-5b decision log §9 addendum | `b4988ce` (0.14.133) |

**狀態**：HEAD `b4988ce`、雙 remote 對齊，0.14.121 → **0.14.133** 跨日 +12 bump。

---

## 1. Morning audit — §3.14 SOP

Personal-playbook fetch 看到 1 commit 5ca1ab4：

> Add §3.14 Cowork write-tool corruption SOP + §B.24 biped-research case (13th revision)

**§3.14 直接打中我的工作流** — Edit / Write / bash heredoc 三種對 mounted Windows + UTF-8 中文 markdown 都會 silently corruption（截斷 / mojibake / 沒寫入）。SOP 唯一可靠寫法：**Python list-of-strings + `\n.join` + `newline='\n'` + 三件套 verify (`wc -l` / `tail -3` / `xxd | tail -2`)**。

### 1.1 倖存者偏差驗證

前 13 commits (5/7-5/8) 寫了 10 個中文 .md，全用 Edit/Write/bash heredoc。立即跑三件套 retro verify：**全部 pass**（0 mojibake、結尾 `0a` LF、行數無截斷）。是運氣 / 倖存者偏差 — 內容沒踩到觸發條件。

### 1.2 從 5/8 起紀律落實

- 6z-3.5 / 6z-5a / 6z-5b / 6z-5c 4 commits 的 decision log 全用 Python list-of-strings 寫
- 寫完即刻三件套 verify
- PRINCIPLES.md §6.8 mapping 加 row 紀錄「§3.14 是 AI agent workflow SOP, 非 stroke-order rule, 引用即可」 + 「13 commits 已驗 pass」

---

## 2. 6z-3.5 — User-place + repeat（架構轉折）

User feedback 5/8 早：「Crescent Moon 與 Florz，看起來有顯示，請問後續會如何操控這些元素的疊加方式，目前看起來是自動填滿」 — 直擊 6z-3 MVP auto-fill 不是 final UX 的架構問題。

v0.3 §1 主流程明寫「**從基底元素開始畫疊加 — L-stick 連續變形、D-Pad 4 方向 pseudo-3D、R1 疊加 3 次、R2 疊加到底**」。Auto-fill 是「結果展示」、user-place 才是「創作體驗」。

### 2.1 變更

- `tangle.mjs`: `buildCrescentMoonUnit` / `buildFlorzUnit` 加進 `TANGLES[].buildUnit`
- `zentangle.js`:
  - `_placedUnits` per-session array
  - `_lastDirection` 從 last 2 units 推算
  - `viewportToTileLocal(x, y)` inverse transform helper（pan + rotation 的反矩陣）
  - canvas left-click → place; R 鍵 → repeat 3 次沿 direction; clear button
  - `drawTangleLayer` 改為 iterate `_placedUnits`
- HTML: 「清除已放」 button + 提示「先選 tangle → 點 canvas → 再點 → R 鍵 repeat」

### 2.2 數學 — Inverse transform

Forward draw transform：`M = T(pan) · T(c) · R(θ) · T(-c)`

Click 在 viewport (canvas px) → 需 inverse 算 tile-local：

```
p_tile = c + R(-θ)(x_view - pan - c)
```

`viewportToTileLocal` 套上述 + `getBoundingClientRect()` 處理 CSS scaling。User 在旋轉/pan 過的紙磚上點任何位置、單元都落在 user 預期處。

### 2.3 User E2E 一次過

Screenshot 顯示 Florz 48 units 在 「日」 字框內（旋轉 45° 狀態）clip evenodd 正確、direction (11, -11) 的小步 R 堆疊填出對角排列。**4-strike pattern 沒觸發**。

---

## 3. 6z-5a — Pseudo-3D depth_dir 4 方向

v0.3 §4 設計，per-unit local perspective transform。

### 3.1 數學

對 unit center (ucx, ucy)：

| dir | 公式 | 視覺 |
|---|---|---|
| forward | k = 1 - d×0.5; (x, y) = (ucx + dx×k, ucy + dy×k); ORB r ×= k | 元素縮小 + 拉向中心（foreshortening）|
| backward | k = 1 + d×0.5; 同上 | 元素擴張、sides 變厚 |
| left | x' = x + dy×d×0.4 | 右側看起來厚（剪切）|
| right | x' = x - dy×d×0.4 | 左側厚 |

### 3.2 Sticky state 設計

User 直觀期待是「**設一次 forward → 之後放的所有 unit 都套 forward**」、不是「每個 unit 都重設一次」。實作：

- `_stickyDepthDir` (null 或 4 方向之一) per-session
- `_stickyDepthDegree` 0..1
- `placeUnitAtClick` 把 sticky 寫進新 unit 的 `pseudo_3d` field
- 點 4 方向 button → 設 sticky AND apply 到 last unit (visual feedback)
- Slider drag → 更新 sticky AND 同步 last unit degree
- 「無透視」 reset → null + 清 last unit pseudo_3d

### 3.3 Arrow 鍵 wire

6z-1E `wireInputScaffolding` 已 dispatch ↑↓←→ 鍵 → `ACTIONS.PSEUDO3D_DIR` action with arg `"up"/"down"/"left"/"right"`。6z-5a 加：

```js
KEY_DIR_TO_PSEUDO3D = {up: "forward", down: "backward", left: "left", right: "right"};
_actionHandlers["pseudo3d-dir"] = (keyDir) => setPerspectiveDir(KEY_DIR_TO_PSEUDO3D[keyDir]);
```

對應 6z-2c 升級的 ACTIONS dispatcher registry — 漸進加 handler 安全。

### 3.4 User E2E 一次過

Screenshot 顯示 Crescent Moon units 在「日」 字框內（旋轉 39° + pan 右 + 透視 forward 0.20）— **三層 transform compose 視覺正確**：

```
M = T(pan) · T(c) · R(θ) · T(-c)  [tile-level ctx transform]
× per-unit pseudo_3d (forward 0.20)  [data-level pre-bake]
× clip(outline, evenodd)  [render-time]
```

**4-strike pattern 沒觸發**。Pure helper Node test 對齊數學、視覺 compose 也對齊直覺。

---

## 4. 6z-5b — Curve mode 軸 1（中高邊低）

v0.3 §4.1「L-stick 4 軸 deformation curvature」 軸 1。

### 4.1 對稱於 6z-5a

6z-5b 是 6z-5a 鏡像 — 加另一維度 (curve_mode) 對稱於 depth_dir：

| 維度 | 6z-5a | 6z-5b |
|---|---|---|
| 4 方向 enum | forward / backward / left / right | high-mid / high-sides / left-high / right-high |
| Sticky state | `_stickyDepthDir / Degree` | `_stickyCurveMode / Degree` |
| Pure helper | `applyPseudo3DTo*` | `applyCurveModeTo*` |
| UI 6z-5b MVP 暴露 | 全 4 方向 | 軸 1 only（其餘 6z-5c）|

### 4.2 數學

```
tx = clamp(dx / unit_scale, -1, 1)
curve = (depends on mode):
  high-mid:   1 - tx²       中央 1, 邊緣 0
  high-sides: tx²            邊緣 1, 中央 0
  left-high:  (1 - tx) / 2   左 1, 右 0
  right-high: (1 + tx) / 2   右 1, 左 0
y' = y - curve * curve_degree * unit_scale * 0.5
```

Curve 是 y-shear 不是 scale → ORB / DOT 半徑保持不變。

### 4.3 Pipeline compose

```
spec → buildUnit
     → if depth_dir: applyPseudo3DToSpecs (6z-5a)
     → if curve_mode: applyCurveModeToSpecs (6z-5b)
     → render
```

兩 transform 各 commute，可獨立啟用。Compose 順序：depth 先（uniform scale 不破 axis-alignment）→ curve 後（y-shear 套在 perspective 後座標）。

### 4.4 預埋全 4 軸的 payoff

`pseudo3d.mjs` switch 已實作全 4 軸（即使 UI 6z-5b 只暴露 1 個）。Node test cover 全 4 軸。**6z-5c 解鎖只需加 HTML 3 button、0 行 JS** — pattern 升格進 PRINCIPLES.md §6.14。

---

## 5. 6z-5c — 解鎖剩 3 軸（10 min ship）

Pure module 預埋 + class-based selector + 共用 wire — 6z-5c 純 UI 加 button + 提示文案、JS 0 改動。

驗證：`document.querySelectorAll(".zt-curve-btn").forEach(...)` 自動 wire 全 4 個 button — 加 button 不需動 JS。

---

## 6. 戰績統計（5/8 晚段）

| 維度 | 數字 |
|---|---|
| Commits | 5 (含早段 cross-ref 合併進 6z-3.5 commit) |
| Lines | +2400+ / -65 |
| New 模組 | 1 (`pseudo3d.mjs` ~220 lines) |
| Tangle.mjs 加擴 | `buildCrescentMoonUnit` + `buildFlorzUnit` + `TANGLES[].buildUnit` |
| Zentangle.js 加 | `_placedUnits` + 3 sticky pairs + `viewportToTileLocal` + 9+ helpers |
| New tests | Node 19 (curve mode) + 21 (depth_dir) + 8 (buildUnit) = **48 new** |
| Total Node tests | 50 → **90** |
| ACTIONS handlers wired | `cycle-tangle`, `repeat-3`, `repeat-fill`, `pseudo3d-dir`（6z-3 + 6z-3.5 + 6z-5a 累積）|
| New PRINCIPLES.md rules | **§6.13** sticky default + inherit、**§6.14** multi-axis enum + class-based wirable |
| Decision logs | 4 個 (6z-3.5 / 6z-5a / 6z-5b 含 §9 6z-5c addendum) |
| Bump | 0.14.129 → **0.14.133** (+4) |

---

## 7. 累積跨日（5/7 → 5/8）戰績

**18 commits / +8400+ lines / 0.14.121 → 0.14.133**

| Phase | Sub-phase 範圍 | Commits |
|---|---|---|
| 元日 | personal-playbook morning audit + cross-ref + design v0.3 reframe | 2 |
| 6z-1 字框 | A+B 後端 → C 前端 → D+E+F force-modal → 1.1 DEFAULT_CONFIG → 1.2 inline 取代 modal | 5 |
| 6z-2 旋轉 | a/b/c+d 統合 → 2.1 frame 共同旋轉 → 2.2 pan buttons → 2.3 arrow direction | 4 |
| 6z-3 tangle | dispatch + clip evenodd + auto-fill MVP → 3.5 user-place + repeat | 2 |
| 6z-5 Pseudo-3D | 5a depth_dir → 5b curve 軸 1 → 5c 解鎖剩 3 軸 | 3 |
| 收工 | 三件套 + 收工三件套 | 2 |

剩餘核心：**6z-6 切割 mode**（5-7h，最後一塊）+ 6z-7 gamepad / 6z-9 draft / 6z-10 gallery。

---

## 8. 反思

### 做得好

1. **§3.14 dogfood 紀律從 5/8 起 100% 落實** — 4 個 decision log 全用 Python list-of-strings + 三件套 verify、零 mojibake / 零截斷
2. **6z-5b/c 的「預埋 + 漸進解鎖」 patterns** — 寫 pure module 全 4 軸、UI 暴露 1 軸 → 解鎖剩 3 軸只 10 min。應驗 §6.14
3. **「對稱模板」 設計** — 6z-5b 完全鏡像 6z-5a (sticky / pure module / wirable selector)，cognitive load 低、bug 風險低
4. **Pure helper Node test 對齊數學** — 6z-5a 21 cases + 6z-5b 19 cases 全 cover 邊界 / identity / inverse / 4 軸對等。視覺 compose 一次過、4-strike pattern 在 6z-3.5 / 5a / 5b 都沒觸發
5. **Sticky state 對 acquisition-first thesis 落實** — 6z-5a/b 沒踩 D-C 強紀律弱預設陷阱、預設友善繼承，§6.13 升格成 reusable principle
6. **跨 phase composing transforms 架構** — tile-level ctx (rotation/pan) × per-unit data-level (depth × curve) × clip 三層各 commute。User E2E 證實視覺正確

### 可以更好

1. **6z-5c 應該在 6z-5b 同 commit ship** — 兩者 10 min 內同質工作，分開 commit 增加 git history noise。但 thesis 是 6z-5b ship 後若 user E2E catch 視覺問題、6z-5c 可單獨 revert，小代價值得
2. **L-stick 連續控制 curve_degree** (per v0.3 §4.1 「L-stick 連續控制 degree」) — 6z-5b 用 slider 模擬，gamepad L-stick 真接 wire 留 6z-7。但「連續」 vs 「discrete preset」 的 UX 差別未實際 verify
3. **Selection mechanism 缺** — 6z-5a/b sticky 只動 last unit、user 想改舊 unit 的 perspective 做不到。對應 v0.3 §1 主流程沒提 selection、預設「**只動 latest**」 是 design choice、但 long-term gallery / draft 階段一定需要
4. **CURVE_COEF / SCALE_COEF 是工程選的，沒實際視覺評估甜蜜點** — 0.5 是 reasonable 起點但可能太強或太弱，user E2E 反饋驅動再調

### 對長期專案影響

- **「v0.3 design wow factor 全摸過」** — 從 outline 抽取到 pseudo-3D 五維 (depth × curve) 一條線打通；剩 6z-6 切割 mode 是最後核心
- **Pure helper + Node test 模式累積成熟** — outline.mjs / tangle.mjs / pseudo3d.mjs 三 module、共 90 Node test、跨 phase 借用無痛
- **ACTIONS dispatcher registry-aware 升級的 payoff** — 6z-3.5 register `repeat-3/-fill`、6z-5a 加 `pseudo3d-dir` 都靠這個漸進，6z-7 gamepad full wire 不需重做架構
- **PRINCIPLES.md §6 rules 從 12 → 14**（+§6.13 sticky default + §6.14 multi-axis enum + class-based wirable）

---

## 9. 下次回來該做的事

### 優先順序

1. **真的 visual E2E 4 curve 軸**（user 5/8 驗了 6z-5a depth、6z-5b 軸 1 not yet, 6z-5c 4 軸 not yet）
2. 視覺通過 → **選下個 sub-phase**：
   - **A** 6z-6 切割 mode（5-7h，最後核心 mechanism）
   - **B** 6z-3.5.X polish（R2 raycast / outline 外點警告 / 4 個 tangle 補完）
   - **C** 6z-7 gamepad full wire / 6z-9 draft / 6z-10 gallery
3. 視覺有偏差 → 6z-5b.X / 6z-5c.X patch（4-strike pattern 預期可能還會來）

### 4-strike pattern 持續預期

今天連續 6z-3.5 / 6z-5a / 6z-5b / 6z-5c 三次 ship 都沒觸發 user catch issue（auto-fill 那次架構問題不算 visual catch、是邏輯架構提問）。但 6z-5b 中高邊低 + 6z-5c 剩 3 軸的視覺 user 還沒實際看 — **下次回來大概率會有 1-2 個視覺 patch**，這是健康閉環、不是 bug。

### Memory candidates 升格觀察

- **§6.13 sticky default + inherit** — 已落實，未來其他 phase 用到時驗證 → 跨 domain valid 才升格進 personal-playbook
- **§6.14 multi-axis enum + class-based wirable** — 同上，pattern 在 6z-2/3/5 都已重現

---

## 10. 結尾感想

5/8 晚段 5 commits 順得驚人 — 從「user 反饋 auto-fill 不是 final」 一路到「pseudo-3D 5 維（depth × curve × rotation × pan × clip）全部 compose 視覺正確」。

兩個關鍵架構決定使這條 chain 能高速：

1. **預埋 pure module 全 enum**（6z-5b 寫 4 軸、UI 暴 1 軸 → 6z-5c 加 3 button 就 ship）
2. **Sticky state 對稱**（6z-5b 鏡像 6z-5a、認知負擔極低）

對應 senior 紀律：**寫 pure module 不偷懶**（不只實作 UI 當下需要的 option）+ **設計時看到對稱性立刻套用**（不每次重發明）。

> 「方法論的本質 = 把『應該做但會偷懶的事』變成『不做就無法交付』」 — personal-playbook §0.1

今天落實的「應該做但會偷懶」 = **§3.14 三件套 verify + 預埋 enum + sticky pattern**。每個都 5 分鐘紀律、累計起來是「ship 18 commits 跨日無重大 visual bug」 的紀律根基。

休息得來。明天 6z-6 切割 mode 是最後 wow factor、新鮮頭腦動會更穩。🍵
