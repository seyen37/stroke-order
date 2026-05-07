# Phase 6z-1 — Outline 抽取 + 紙磚 canvas + Force-modal + Input scaffolding

**日期**：2026-05-07
**版本**：0.14.121 → **0.14.122**
**範圍**：Phase 6z 第一個 sub-phase — outline 抽取 backend + 紙磚 canvas frontend + force-modal main menu + 鍵盤滑鼠 + Web Gamepad API input scaffolding。
**前置**：v0.3 design doc commit `8fc5e8f`（path A reframe）+ user Approve all defaults Q1=C / Q2-Q5=A。
**對應 commits**：`74a4886`（A+B 後端）/ `8de3c89`（C 前端）/ 本 commit（D+E+F bump + 本決策 log）。

---

## 1. 範圍 (Scope)

實作 v0.3 §6 「6z-1」全部 6 個內部子步驟：

| Step | 內容 | 對應 commit |
|---|---|---|
| **A** | `exporters/zentangle.py` outline module + dispatch 5 sources | `74a4886` |
| **B** | FastAPI endpoints `/api/zentangle/outline` + `/api/zentangle/sources` | `74a4886` |
| **C** | index.html mode 12 + 紙磚 canvas + outline render + Node tests | `8de3c89` |
| **D** | Force-modal main menu (char + mode + tile size，無預設值) | 本 commit |
| **E** | 鍵盤 + 滑鼠 + Web Gamepad API listener stubs + action vocab | 本 commit |
| **F** | Bump 0.14.122 + 本決策 log + 全 test pass | 本 commit |

---

## 2. QODA 紀錄 (Pre-implementation, all confirmed by user)

| Q | 議題 | 選項 | User 決定 |
|---|---|---|---|
| 1 | Outline source 預設 | A cns_kai / B moe_song / **C moe_kaishu** / D 沿用 sutra | **C** 教育部楷書 |
| 2 | Canvas 內部解析度 | **A 600×600** / B 800 / C 1024 | **A** |
| 3 | Force-modal 必填 | **A char+mode+tile (3 欄位)** / B +source / C 只 char+mode | **A** |
| 4 | Mode 中文 label | **A 禪繞字** / B 禪繞 / C 動感繪字 | **A** |
| 5 | 6z-1 gallery touch | **A 完全不動** / B 預留 dispatch slot | **A** |

---

## 3. 重大決策 (新加 / 取代 v0.3 內容)

### 3.1 Outline 抽取直接 wrap Phase 5al（**R1 風險消除**）

v0.3 §9 R1「字框 outline 抽取技術未驗證」原列為 **High**。Reconnaissance 發現：

- `fontTools>=4.0` 已是 hard dep
- `src/stroke_order/sources/cns_font.py` 既有 `_OutlineCmdPen` + `_outline_to_polylines`（Phase 5al 寫的）— 完整 TTF/OTF → polyline 流程已 verify 過
- 5 個既有 source（kaishu / cns_kai / song / lishu / seal）都有相同 API（`get_character()` 回 `Character.strokes[0].outline`）

**結論**：6z-1A 純 wrap，不重做 outline pipeline。R1 從 High **降到 Low**。

### 3.2 三輸入正交 ≠ 三輸入等效（v0.3 reframe 落地）

實作上：
- 鍵盤 + 滑鼠 是 **universal core** — wireInputScaffolding() 完整 wire
- Web Gamepad API 是 **progressive enhancement** — 只 `gamepadconnected` event listener，6z-7 才完整 polling loop
- **單一 dispatchAction()** function 是所有 input 走的同一條 routing — 6z-2 ~ 6z-7 swap handlers 不動 routing

對應 v0.3 §6 6z-7 估時 8-10h → 3-4h（10-12h saving）。

### 3.3 Schema versioning + strict-on-mismatch 套到 localStorage

`CONFIG_SCHEMA_VERSION = 1` baked into stored payload。`readConfig()` 遇 unknown schema → return null → 強制 re-prompt force-modal。

對應 stroke-order 既有 memory `feedback_schema_versioning_with_migration` 在前端的 instance（同 D-C 強紀律弱預設精神）。

### 3.4 Force-modal 強紀律機制 (D-C 落實)

3 道防線阻止 dismiss：
1. **無預設值**（modal 開啟時 `_value = ""` + radio 全 unchecked）
2. **ESC keydown handler** preventDefault + stopPropagation
3. **背景 click handler** preventDefault + stopPropagation
4. **Confirm button** disabled until `char.length===1 && mode && tileSize`（live update）

UI 還明寫 disclaimer：「⚠ 此選單刻意「無預設值 + 不可 ESC dismiss」 — 對位 v0.3 senior review note #5」。

### 3.5 切階段 boundary 對齊（senior review note #2 應用）

雖然 6z-1 內部沒做 pseudo-3D，但 6z-1E 的 ACTIONS 表已經為 6z-5 a/b/c 切階段預留了 `PSEUDO3D_DIR` action（D-Pad up/down/left/right），分別對應 4 方向 perspective。6z-5 階段切：
- 5a: 接 ACTIONS.PSEUDO3D_DIR 的 4 方向 (perspective only)
- 5b: 加 curve_mode 軸 1 (中高邊低)
- 5c: 評估砍軸

---

## 4. 變更清單 (Files Changed)

### Phase A+B (`74a4886`)
- ⚠ NEW `src/stroke_order/exporters/zentangle.py` (143 lines)
- 🔧 `src/stroke_order/web/server.py` (+60 lines, 2 endpoints)
- ⚠ NEW `tests/test_zentangle_outline.py` (16 cases)
- ⚠ NEW `tests/test_zentangle_server.py` (10 cases)

### Phase C (`8de3c89`)
- ⚠ NEW `src/stroke_order/web/static/zentangle/outline.mjs` (4.2 KB pure helpers)
- ⚠ NEW `src/stroke_order/web/static/zentangle/zentangle.js` (7.2 KB DOM glue)
- 🔧 `src/stroke_order/web/static/index.html` (+50 lines: radio, view, dispatch, script)
- ⚠ NEW `tests/test_zentangle_outline.mjs` (15 Node cases)

### Phase D + E (本 commit)
- 🔧 `src/stroke_order/web/static/index.html` (+95 lines: force-modal markup + reset button + config display)
- 🔧 `src/stroke_order/web/static/zentangle/zentangle.js` (+220 lines: modal lifecycle + ACTIONS dispatch + key/mouse/gamepad wiring)

### Phase F (本 commit)
- 🔧 `pyproject.toml` 0.14.121 → 0.14.122
- ⚠ NEW `docs/decisions/2026-05-07_phase6z-1_outline_canvas_scaffold.md` (本檔)

---

## 5. 測試 Coverage

| 層級 | tool | passed | skipped | 備註 |
|---|---|---|---|---|
| Backend pytest (zentangle) | pytest | 18 | 8 | 8 skip 因 sandbox 無 moe_kaishu 字體 |
| Backend pytest (regression) | pytest | 138 | 8 | 既有 mandala / cns_font / etc 全 pass |
| Frontend Node (outline.mjs) | node:test | 15 | 0 | 純 logic，無 DOM 依賴 |
| Manual E2E（user 機器） | browser | 待 user 視覺驗 | — | 6z-1F user task |

### 待 user 機器手動 verify（6z-1F user task）

由於 sandbox 無瀏覽器 + 無中文字體，以下 manual E2E 需 user 在自己機器上跑：

1. ⚠ 啟動 server (`uvicorn stroke_order.web.server:app`)
2. ⚠ 開 `localhost:PORT/`
3. ⚠ 切到「禪繞字模式」 — 確認 force-modal 自動彈出
4. ⚠ 試圖 ESC / 背景點擊 → 確認 modal 不關
5. ⚠ 不選任何 → 確認 「確認開磚」 button 灰
6. ⚠ 填字「心」+ 模式「純禪繞」+ 紙磚「標準磚」 → 「確認開磚」 變紅可按
7. ⚠ 按 confirm → modal 關閉 → 紙磚 canvas 顯示 4 角點 + 細邊框 + 「心」字框
8. ⚠ 按「重新設定紙磚」 → modal 重開
9. ⚠ Reload page → 自動套上次 config（不再彈 modal）
10. ⚠ 視覺截圖比對（紙磚比例 + 字框正確 = R1 真正 verified by render output）

⚠ 對位 PRINCIPLES.md memory `feedback_visual_render_verify` — 「Visual rendering 驗證每 round — unit tests 不夠」。**6z-1 真正完成度 gate = visual render PNG 比對 pass**。

---

## 6. P7-COMPLETION (Phase 6z-1 整段)

> 對位 personal-playbook §8.31 strict completion format mandatory。

- **任務**：Phase 6z-1 「outline 抽取 + 紙磚 canvas + force-modal + input scaffolding」
- **方案**：5-source dispatch (default moe_kaishu) + FastAPI 2 endpoints + ESM module 拆 pure/DOM + localStorage schema-versioned config + ACTIONS dispatch table
- **改動**：8 files (5 new / 3 mod)，+1100 lines；4 commits 跨 6z-1A→F
- **影響分析**：
  - grep `mandala` 既有 endpoint：no conflict，純加新 routes
  - grep `<input type="radio" name="mode"`：mode 從 11 → 12，dispatch dict 同步加
  - grep `localStorage`：CONFIG_STORAGE_KEY 加新 key，不衝撞既有 (gallery / handwriting)
  - 既有 138 pytest + 75+ Node tests 全 pass，無 regression
- **三問自審**：
  - **方案正確**：是。複用 5al pipeline、ESM 拆 pure helpers、localStorage schema 版本化都對齊 stroke-order 既有 pattern
  - **影響全面**：是。grep 過 mode dispatch / localStorage / radio markup / static mount，無 collision
  - **回歸風險**：低。新模組 + 新 routes + 新 mode；既有測試全 pass；唯一風險點 = visual render 對 user 字體（待 user 機器 manual verify）
- **剩餘風險**：
  1. **R1 字框 outline 視覺正確性** — sandbox 無字體，render 對「心」/「日」 等 char 的視覺結果尚未 PNG verify。User 機器 E2E §5 step 7-10 是真正 close gate
  2. **iOS Safari Web Gamepad API 行為差異** — sandbox 無 browser 測；R4 實際發生點待 6z-7 跨 browser smoke
  3. **「禪繞」品牌矛盾** disclaimer 已加進 UI，但 acquisition target 對「禪繞」期待 vs 實際數位風格落差仍可能引起 user feedback；6z-12 marketing copy phase 完整處理
  4. **Force-modal disclaimer i18n** — 目前繁中硬寫，無 i18n layer；若擴 ENG 需 v0.4 補 i18n（defer）

---

## 7. 配對 reference

- Phase 6z v0.3 design doc：[`2026-05-06_phase6z_zentangle_design_v0.3.md`](2026-05-06_phase6z_zentangle_design_v0.3.md)
- v0.2 senior review path A：commit `8fc5e8f` 訊息
- PRINCIPLES.md §6.8 thesis ↔ rule mapping：[`../PRINCIPLES.md`](../PRINCIPLES.md)
- Phase 5al CNS font outline (reused base)：`src/stroke_order/sources/cns_font.py:426 _outline_to_polylines`
- Mandala mode pattern (template followed)：`src/stroke_order/exporters/mandala.py` + `web/server.py:1900-2104`
- Personal-playbook 治理層：
  - §0.4 重新框架問題 → 6z-1 reconnaissance + plan-first
  - §0.2 Enforcement-based governance → force-modal 3 道防線
  - §8.31 P7 完成格式 → 本 §6
  - §8.35 Strict negative constraints → v0.3 §7 anti-pattern + force-modal 無預設值

---

## 8. 下一步 (6z-2 預備)

6z-1 ship 後，下一個 sub-phase **6z-2** 範圍：

- 6z-2a: 紙磚 rotation logic + math (pure，~3-4h，可 Node test)
- 6z-2b: rotation input wiring (鍵盤 IJKL + sidebar 鈕 + R-stick 預留，~2-3h)

啟動條件：
- ✅ 6z-1 ship + visual verify pass
- ✅ tile-local coords mechanism 已 baked into outline.mjs `mapContourToTile()` (Phase C)

對位 v0.3 §6 估時：6z-2 共 5-7h（拆 a/b 後估時不變但 boundary 清楚）。

---

## 9. 經驗萃取（candidate for PRINCIPLES.md / personal-playbook）

本 sub-phase 三條值得萃取的 pattern（待 review 是否進 SoT）：

1. **「Multi-input single-dispatcher」 pattern** — N 種 input device → 1 個 ACTIONS table → 1 個 dispatchAction()。將「等效」 reframe 成「正交」(routing 唯一，handler 多元)，是 reframing 問題的 instance（§0.4）。
2. **「Force-modal 3 道防線」 pattern** — ESC block + 背景 click block + button disabled 直到 valid。對位 D-C 強紀律弱預設在 web 環境的具體實作。
3. **「Schema-versioned localStorage with strict-on-mismatch」 pattern** — `{schema: N, ...payload}` baked + read 端 `if (parsed.schema !== EXPECTED) return null`。對應既有 memory `feedback_schema_versioning_with_migration` 但範圍延伸到 frontend storage。

是否升格？6z-2 / 6z-3 跑完後若再次出現相同 pattern → 升格進 PRINCIPLES.md（對應 personal-playbook §137 「2 次以上是 pattern」 等待原則）。
