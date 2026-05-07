# Phase 6z-1 / 6z-2 / 6z-3 跨日 implementation 總覽 (5/7 → 5/8)

**日期**：2026-05-07 → 2026-05-08
**版本累進**：0.14.121 → **0.14.129**
**範圍**：Phase 6z 禪繞字模式 — design v0.3 reframe 落實 + 字框抽取 + 紙磚 canvas + 旋轉/pan + tangle 庫 MVP，跨 12 commits 兩日 ship。
**前置**：phase 6z spike commit `b78ea48`（5/6）+ design v0.1 `0043cfc`（5/6 深夜）+ design v0.2 `fff3014`（5/6 深夜 PS2 版）。

---

## 0. 跨日 commit 索引

| Commit | 範圍 | 主題 |
|---|---|---|
| `5615b65` | docs | PRINCIPLES.md §6.8 cross-ref expansion (5/7 morning audit) |
| `8fc5e8f` | docs | **Design v0.3** — gamepad reframe path A (PS2 → Web Gamepad API) |
| `74a4886` | feat | **6z-1A+B** outline backend + 2 endpoints |
| `8de3c89` | feat | **6z-1C** frontend canvas + outline render |
| `def8f38` | feat | **6z-1D+E+F** force-modal + input scaffolding (0.14.122) |
| `ca83132` | fix | **6z-1.1** DEFAULT_CONFIG fallback (0.14.123) |
| `f74c128` | fix | **6z-1.2** inline 取代 modal (0.14.124) |
| `36327b8` | feat | **6z-2** 旋轉 + tile resize (0.14.125) |
| `e05f705` | fix | **6z-2.1** frame+outline 共同旋轉 (0.14.126) |
| `0c34a83` | feat | **6z-2.2** pan buttons (0.14.127) |
| `5eca676` | fix | **6z-2.3** pan arrow direction (0.14.128) |
| `2fc0d5d` | feat | **6z-3** ICSO + 2 tangle MVP (0.14.129) |

---

## 1. 主要決策（thesis-level）

### 1.1 Design v0.3: PS2 → Web Gamepad API reframe

**v0.2 problem**：PS2 controller 為 hard requirement、三 input method 等效 → acquisition target 大部分沒 PS2 → 14h dev cost 是 dead weight。

**v0.3 path A reframe**：
- 鍵盤+滑鼠 = universal core
- Web Gamepad API auto-detect = progressive enhancement（任何標準 USB/Bluetooth gamepad）
- PS2 layout 圖示保留為通用 mapping 範例

**節省**：6z-7 input 整合從 8-10h → 3-4h（-6h）+ 6z-11 testing matrix 5-6h → 3-4h（-2h）= **-10-12h 總**。

**對應 v0.2 senior review 5 notes**：
- #1 PS2 hardware niche → reframe（本決策）
- #2 Pseudo-3D 4×4 over-engineered → 6z-5 切 a/b/c
- #3 估時樂觀 → R7 警告 1.2-1.5x burn
- #4 「禪繞」 品牌矛盾 → §12 defer 6z-12
- #5 D-C 強紀律弱預設 → 6z-1 force-modal force（後續 reverse for UX domain）

### 1.2 預設策略 domain-specific（思維重新框架）

**過程**：6z-1F → 6z-1.1 → 6z-1.2 三輪修補 force-modal、揭示「**強紀律弱預設 (D-C) 套錯 domain**」。

**Reframe 結論**：
- **Ops** (NIC name / schema)：強紀律弱預設 D-C
- **UX / Acquisition** (zentangle char / mode / tile)：預設要 senior 不要 absent

**Memory saved**：[`feedback_domain_specific_defaults.md`](../../.auto-memory/feedback_domain_specific_defaults.md)
**新加 PRINCIPLES**：[§6.9 預設策略 domain-specific](../PRINCIPLES.md#69-預設策略-domain-specific)

### 1.3 Modal vs Inline — Creative tool config

**過程**：6z-1F force-modal 必填 → 6z-1.1 DEFAULT_CONFIG fallback + 非阻擋 → 6z-1.2 完全 strip + inline radio。

**Reframe 結論**：
- **Modal** = transactional / destructive / irreversible 動作
- **Inline + auto-apply** = creative tool config（持續微調）

**新加 PRINCIPLES**：[§6.10 Modal vs Inline](../PRINCIPLES.md#610-modal-vs-inline)

### 1.4 Canvas ctx transform > primitive pre-rotation

**過程**：6z-2 用 `rotateContours()` pre-rotate outline polylines、frame 卻 axis-aligned → user 反饋「外框連同字一起旋轉才對」 → 6z-2.1 改 ctx transform 包整個 redrawAll。

**Reframe 結論**：
- **群組變換** (整個紙磚旋轉/pan/縮放) → ctx transform
- **個別 primitive 變換** (stroke pseudo-3D 進 schema) → polyline pre-transform + Node test

**Bonus 觀察**：Viewport (pan/zoom/scroll) vs 內容變換 (rotation/pseudo-3D) 是兩個正交 dimension，state 該分開存（如 `_rotationDegrees` vs `_panState`）。

**新加 PRINCIPLES**：[§6.11 Canvas 整體變換用 ctx transform](../PRINCIPLES.md#611-canvas-整體變換用-ctx-transform)

### 1.5 失敗 2 次同類修補 → strip and rebuild

**辨識**：第 2 次同類修補意味 root cause 沒解、第 3 次該 strip。

**今日 instances**：
- **6z-1 force-modal 三輪**（必填 → 非阻擋 → 刪）= 明確 strip signal、第 3 次刪掉 modal
- **6z-2 visual 四輪**（rotation pre-rotate → ctx transform → pan creation → arrow direction）= 不同 root cause、是 visual verify 累積、不是 strip signal

**新加 PRINCIPLES**：[§6.12 失敗 2 次同類修補 → strip](../PRINCIPLES.md#612-失敗-2-次同類修補--strip-and-rebuild)

**對應 personal-playbook §8.32 失敗 2 次換方法** — 工程 instance。

---

## 2. 跨 phase 統計

| 維度 | 數字 |
|---|---|
| 總 commit | 12 |
| 總 lines | +5400+ / -200 |
| 新模組 | 2 (`outline.mjs` 4.2 KB / `tangle.mjs` 8.8 KB) |
| 新 endpoints | 2 (`/api/zentangle/outline` + `/api/zentangle/sources`) |
| 新 mode | 1 (zentangle, mode #12) |
| 新 PRINCIPLES.md rules | 4 (§6.9 / §6.10 / §6.11 / §6.12) |
| 新 memory | 1 (`feedback_domain_specific_defaults`) |
| 新 decision logs | 7 (6z-1 / 6z-1.1 / 6z-1.2 / 6z-2 / 6z-2.1 / 6z-2.2 / 6z-3 + summary 本檔) |
| Tests added | 50 (Node 17+10+15+8 = 50) |
| ACTIONS handlers wired | 4 (angle-reset / angle-prev / tile-rotate-delta / cycle-tangle) |

---

## 3. v0.3 sub-phase 進度更新（vs design doc 估時）

| Sub-phase | 範圍 | 估時 | 實際 ship | 狀態 |
|---|---|---|---|---|
| 6z-0 | Design doc v0.3 | 5-6h | ~3h | ✅ commit `8fc5e8f` |
| 6z-1 | Outline + canvas + force-modal | 5-6h | ~5h（A+B+C+D+E+F）| ✅ + 2 patch (1.1, 1.2) |
| 6z-2a | rotation logic pure | 3-4h | ~1.5h | ✅ in `36327b8` |
| 6z-2b | rotation input wiring | 2-3h | ~1.5h | ✅ in `36327b8` |
| 6z-3 | ICSO + 6 tangles + cycle | 6-8h | ~3h（MVP 2 tangle, 4 個 defer 6z-3.X）| ✅ minimal MVP `2fc0d5d` |

**累計 burn**：~14h ship（v0.3 est 21-27h、實際快約 1.5x，**但** scope 也較窄，6z-3 只做 2/6 tangle、hollow/bg mode 視覺差異 defer、6z-7 整合未動）

**剩餘**：6z-3.X polish + 6z-4 (input wiring full) + 6z-5 (pseudo-3D) + 6z-6 (切割 mode) + 6z-7 (gamepad) + 6z-8 (embedded) + 6z-9 (draft) + 6z-10 (gallery) + 6z-11 (tests / decision logs / final bump) + 6z-12 (marketing copy)。

---

## 4. 5 次 ship → user E2E catch issue → patch 模式

| # | Phase | User 反饋 | Root cause |
|---|---|---|---|
| 1 | 6z-1.1 | 「請預設值先讓開磚」 | D-C 套錯 UX domain |
| 2 | 6z-1.2 | 「為何要跳出視窗」 | Modal 當 settings 入口的錯前提 |
| 3 | 6z-2.1 | 「外框連同字一起旋轉」 | ctx transform vs polyline pre-rotate |
| 4 | 6z-2.2 | 「邊角超出可視區」 | Rotation overflow + pan UX 缺 |
| 5 | 6z-2.3 | 「左右箭頭方向錯」 | CSS writing-mode rotate arrows |

**meta-pattern**：Visual rendering 細節（modal flow / canvas layering / CSS rotation / pan vector）unit tests 抓不到。User PNG verify 是真 close gate（對應 memory `feedback_visual_render_verify`，今天連續 5 次驗證）。

**前 2 次 (1.1 + 1.2)** 跟 modal 同 root cause → 第 2 次是 strip signal、第 3 次落實。
**後 3 次 (2.1 + 2.2 + 2.3)** 是 visual 累積 fix、不同 root cause、是漸進完善而非 strip。

---

## 5. v0.3 design doc vs 實際 ship 差異 (acquisition-first 落實)

| v0.3 design | 實際 ship | 落差說明 |
|---|---|---|
| Force-modal 第一次必填 | DEFAULT_CONFIG fallback + inline radio | thesis re-balance: UX 不該用 D-C |
| Modal 留作進階設定 | Modal 完全刪 | 三輪修補後 strip |
| 紙磚旋轉 polyline pre-rotate | ctx transform 包整段 redrawAll | 群組變換的對的抽象 |
| Pan = 6z-2 沒列 | 加 4 側 pan button (6z-2.2) | user 反饋驅動 |
| Tangle 6 個 MVP | 2 個 (Crescent Moon + Florz) | 「裝對 3 個就夠用」 克制 |
| Mode 全 3 視覺差異 | 只 pure mode 落實 | hollow/bg → 6z-3.X |
| 6z-3 含 user-place + repeat | 只做 auto-fill | 用 thesis 邏輯：MVP 驗 dispatch + clip 架構，user-place 等下次 6z-3.5 再加 |

**落差合理**：design doc 是規劃 anchor、實際 ship 是 user 反饋 + scope 克制的 trade-off。每次落差有明確原因 + decision log 紀錄，不是「**spec drift**」 而是「**spec evolution**」。

---

## 6. 接下來路徑（decision pending）

### Option A — **6z-3.5 user-place + repeat（acquisition power 立即啟動）**
- 滑鼠點 canvas → place 單一 tangle unit (花 / crescent)
- 點第二下 → define direction
- R 鍵 → 沿 direction repeat 3 次
- ~3-4h
- 比 6z-4 (8h+ pure infra) / 6z-5 (8-10h+ pseudo-3D 沒 target) 先行

### Option B — 6z-3.X auto-fill polish
- hollow/bg 視覺差異 + density UI + 4 個 tangle 完整
- ~2-3h
- 但仍是 swap pattern、不增 user 親手感

### Option C — 6z-4 全 input wiring (per v0.3 順序)
- ACTIONS dispatcher 全 14 個 handler 接齊
- ~5-7h
- 純 infra、無視覺新東西

### Option D — 6z-5a Pseudo-3D MVP
- D-Pad 4 方向 perspective
- ~5-6h
- 但 user 沒 stroke、沒 target

**senior 建議 A** — 6z-3.5 (user-place + repeat) 對 thesis 落實最強、scope 中等、打開後續路徑（pseudo-3D 才有 target stroke）。

---

## 7. 配對 reference

- v0.3 design doc：[`2026-05-06_phase6z_zentangle_design_v0.3.md`](2026-05-06_phase6z_zentangle_design_v0.3.md)
- 各 sub-phase decision logs：
  - [6z-1 outline canvas scaffold](2026-05-07_phase6z-1_outline_canvas_scaffold.md)
  - [6z-1.1 default config](2026-05-07_phase6z-1.1_default_config_acquisition_first.md)
  - [6z-1.2 inline replace modal](2026-05-08_phase6z-1.2_inline_controls_replace_modal.md)
  - [6z-2 rotation tile resize](2026-05-08_phase6z-2_rotation_tile_resize.md)
  - [6z-2.1 frame rotates with outline](2026-05-08_phase6z-2.1_tile_frame_rotates_with_outline.md)
  - [6z-2.2 pan buttons](2026-05-08_phase6z-2.2_pan_buttons_for_rotation_overflow.md)
  - [6z-3 tangle library minimal](2026-05-08_phase6z-3_tangle_library_minimal.md)
- Memory: `feedback_domain_specific_defaults` (5/7 saved)
- Personal-playbook 治理層：§0.4 重新框架、§8.32 失敗 2 次換方法、§8.31 P7 三問自審
- Stroke-order 新加 PRINCIPLES：§6.9 / §6.10 / §6.11 / §6.12
