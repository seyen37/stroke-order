# Phase 6z 禪繞字 Design Doc — v0.3 (Gamepad-inspired UX + Pseudo-3D)

**日期**：2026-05-07（v0.2 → v0.3 senior review path A reframe）
**版本**：design-v0.3（取代 v0.2，待 user Approval 後動工 6z-1 implementation）
**範圍**：禪繞字模式 — 漢字 outline + 內部禪繞畫填充 + 紙磚旋轉 + ICSO 元素重複疊加 + **鍵盤+滑鼠 core control + 通用 gamepad enhancement (Web Gamepad API)** + **pseudo-3D 變形** + 草稿系統 + gallery 整合
**前一版**：v0.2 (commit `fff3014`，5/6 深夜) + v0.1 [`2026-05-06_phase6z_zentangle_design.md`](2026-05-06_phase6z_zentangle_design.md)（commit `0043cfc`）

> 🔗 **上層 thesis**：personal-playbook §0.4「重新框架問題 > 答問題（plan-first 升級）」 + §0.1「AI 不是能力不夠、是紀律不夠」 — v0.3 是針對 v0.2 senior review path A 的 elegant simplification（PS2 hardware niche → generic gamepad via Web Gamepad API）。

---

## 0. v0.2 → v0.3 Change Log

**v0.2 senior review 結果（2026-05-07）**：5 notes，其中 strong caveat #1 = PS2 controller hardware niche 風險。User 選 path A（PS2 → generic gamepad reframe）。

### v0.3 主要變更

| # | v0.2 | v0.3 |
|---|---|---|
| 1 | PS2 controller 為主 + 三 input method 等效 hard requirement | **鍵盤+滑鼠 core (universal)** + **Web Gamepad API auto-detect 任何標準 gamepad** (PS2 / PS5 / Xbox / 通用) |
| 2 | 6z-7「3-input-method 等效」 8-10h | **6z-7「Web Gamepad API integration」** 3-4h（gamepad detection + button mapping wrapper） |
| 3 | 6z-11 testing「3-input matrix」5-6h | 6z-11 testing「鍵盤+滑鼠 manual E2E + gamepad smoke」3-4h |
| 4 | PS2 圖示 = mandatory hardware target | PS2 圖示 = **通用 gamepad layout 範例** (教學用，不綁定 hardware) |
| 5 | Risk R4「PS2 hardware niche」Medium | **R4 改「Web Gamepad API 跨 browser 行為差異」Medium** (Chrome primary) |
| 6 | 估時 58-79h | **48-67h**（節省 10-12h） |

### Reframing 理由

- **Acquisition target user 大部分沒 PS2 controller**（家裡有 / 配 USB adapter / 願意連電腦的人是 niche）
- **三 input matrix testing = dead weight**（target user 用不到 PS2 path，但 dev cost 真實）
- **More elegant**: Web Gamepad API 自動偵測**任何標準 gamepad**，PS2 layout 圖示作為 mapping 範例保留
- 鍵盤+滑鼠是 web universal core，gamepad 是 progressive enhancement（auto-detect on connect）

### v0.3 不變項目（v0.2 →v0.3 保留）

- Pseudo-3D 變形系統（depth_dir + curve_mode）
- 切割 mode 狀態機（□ cycle I → . → O，I 模式 D-Pad bend C/S）
- Tile-local coords 核心 mechanism
- 6 個 tangle 庫
- 3 modes（純禪繞 / 空心填充 / 背景鑲嵌）
- 草稿 vs 定稿 boundary
- 30 步 undo + 5 分鐘 auto-save
- File schema (含 pseudo_3d field)
- Acquisition-first thesis（「快速產出禪繞效果」）

### Senior review 其他 4 notes 處理

| Note | 處理方式 |
|---|---|
| #2 Pseudo-3D 4×4 over-engineered | 6z-5 內部切階段 (5a depth_dir 4 dir / 5b curve_mode 軸 1 / 5c 評估砍軸)，不動 design doc |
| #3 估時偏樂觀 | §9 Risk R7 補警告「實際 burn 預期 1.2-1.5x」 |
| #4 「禪繞」品牌 vs Pseudo-3D 矛盾 | 列入 §12 defer (6z-12 marketing copy phase) |
| #5 D-C 強紀律弱預設 | 6z-1 主選單 force-modal + schema null 加 comment，6z-1 動手時注意 |

---

## 0a. v0.1 → v0.2 Change Log（歷史紀錄保留）

User 對 v0.1 的反饋：

> 「會用電腦操作來取代手繪的人，本來就已經設想要快速做出禪繞效果，不想慢慢來，所以，這是贏得新用戶的重大變化，吸引不想慢慢手繪的人」

→ **Product positioning 升級**：

| 階段 | Product thesis |
|---|---|
| Phase 6z spike (5/6 早) | 「禪繞字 = 漢字邊框 + 內部禪繞」(user 字面) |
| **v0.1** (5/6 晚) | 「禪繞重複疊加減負工具」 |
| **v0.2** (5/6 深夜) ⭐ | **「快速產出禪繞效果的數位工具」** acquisition-first |

### Major Changes

| # | v0.1 | v0.2 |
|---|---|---|
| 1 | 9 cell 重複疊加 panel 是核心 UX | **PS2-inspired controller scheme** 取代 9-cell |
| 2 | 純 2D ICSO 元素 | **Pseudo-3D 變形系統** 加進 schema（變形 4 軸 + 連續 degree） |
| 3 | 單一輸入（滑鼠）| **3 種輸入裝置等效**：PS2 controller / 鍵盤 / 滑鼠 sidebar |
| 4 | 切割 = 9-cell 重複疊加 mechanism | **切割 mode + base shape cycle**（□ 鍵 cycle I→.→O，D-Pad bend → C/S） |
| 5 | Density slider (low/med/high) | **L3 toggle cycle** |
| 6 | Element size 5 buttons + slider | **PSB_SELECT cycle** |
| 7 | Sub-phase 估時 30-40h | **50-75h** (1.5-2x scope，user 接受 trade-off) |

### v0.2 對應 user 13 個 missing decisions（全 confirmed）

| # | Decision | 落點 |
|---|---|---|
| 1 | Char 選擇 | PSB_START → 主選單 → Char picker |
| 2 | Mode 切換 (純禪繞/空心/背景) | 主選單子項（首次開磚決定，繪製中不改） |
| 3 | Density 設定 | **L3** (左 stick 按下) → cycle low/medium/high |
| 4 | Element size | **PSB_SELECT** → cycle XS/S/M/L/XL |
| 5 | Tile size | 主選單子項（首次開磚） |
| 6 | △ Triangle 切換 | **切 tangle 庫**（6 個 tangles）；□ 切 base shape (I/./O) |
| 7 | String vs 切割工具 | 整合：「切割」 mode 即包含 String，stroke layer=guide → 確認後 final |
| 8 | Save / Snapshot / Download | START 主選單 + 30 步 undo + 5 分鐘 auto-save (localStorage) |
| 9 | Layer 顯示 toggle | **R3** (右 stick 按下) → cycle border/string/final |
| 10 | Character outline 顯示 toggle | START 主選單子項 |
| 11 | D-Pad 上/下 在 I 模式 | **上 = 增加長度** / **下 = 縮短長度** |
| 12 | L-stick 在切割 mode | 跟 D-Pad 同事，連續控制 deformation 強度 |
| 13 | 疊加起點 | **= tile 底部中央（固定）**；想換起點靠旋轉紙磚（呼應「轉動紙磚配合手部」哲學） |

---

## 1. Executive Summary

**Phase 6z 是「快速產出禪繞效果的數位工具」**，鎖定「想要禪繞風格但不想慢慢手繪」的 acquisition target。

| Aspect | v0.1（減負） | v0.2（acquisition-first） | **v0.3（gamepad reframe）** ★ |
|---|---|---|---|
| 核心 user | 想做完整禪繞但減重複勞動的人 | 想要禪繞效果但不想慢慢手繪的人 | **同 v0.2** |
| 主要 UI | 9 cell panel | PS2-inspired + 三 input 等效 | **鍵盤+滑鼠 core + Web Gamepad API auto-detect** |
| 視覺 power | 重複疊加減負 | 重複疊加減負 + Pseudo-3D | **同 v0.2** |
| Product moat | 重複機制 + 紙磚旋轉 + ICSO | 手感豐富 input + Pseudo-3D + 速度產出 | **同 v0.2** |
| Gamepad 支援 | 無 | PS2 only (hard requirement) | **任何標準 USB/Bluetooth gamepad** (PS2/PS5/Xbox/通用，auto-detect) |
| vs 紙筆禪繞 | 不直接競爭（仍偏冥想練習）| 明確 differentiate（電腦 power, 不是紙筆替代） | **同 v0.2** |

**MVP 主流程（鍵盤滑鼠 + 可選 gamepad）**：

```
1. 開磚 (PSB_START 主選單) → 選 char "心" / mode 空心填充 / tile 9cm
2. 紙磚 canvas 顯示，4 角 dot + 細邊框 + char outline 自動 render
3. R-stick 旋轉紙磚到順手角度
4. □ Square 進入「切割」 mode：
   - 從 tile 底部中央向前畫一條 I（直線）切割
   - L-stick / D-Pad 連續變形（彎/S/曲度）
   - □ 再按 cycle 到 . (Dot move pointer) → 再按 cycle 到 O (Orb scale)
5. ✕ Cross 確認切割 → 留 layer=final
6. △ Triangle 切換 tangle 庫（6 個）
7. 從基底元素開始畫疊加：
   - L-stick 連續控制變形 degree
   - D-Pad 4 方向 pseudo-3D 變形（朝前/後/左/右 perspective）
   - R1 = 疊加 3 次 / R2 = 疊加到底
   - L1 = 角度復原 / L2 = 上次角度
8. 草稿系統：30 步 undo (○) + 5 分鐘 auto-save
9. 「發布到 gallery」（START 主選單） → 上傳 kind='zentangle'，**immutable**
```

**MVP 不做（defer）**：
- Multi-character (`chars` array > 1)
- 彩色禪繞（黑白為主）
- 陰影 + Tortillion 推色
- Image → config 反向解析（CV）
- 跨 mode snapshot system（phase 7）

**估時**：6z-0 design doc 已寫（本檔）+ 6z-1 ~ 6z-11 sub-phases 約 **48-67 hours / 1.5-2 週工作日**（v0.3 reframe 從 58-79h 節省 10-12h）。

> **預期實際 burn rate 1.2-1.5x**（greenfield + 4 高 risk sub-phase），realistic 估時 **58-100h**。User 心理預期校正後不會在 6z-5 卡關時恐慌（senior review note #3 應用）。

---

## 2. Gamepad Scheme (以 PS2 layout 圖示，通用 gamepad mapping)

> 🆕 **v0.3 reframe**：本節 PS2 layout 為**示意圖**（教學友善 + 復古辨識度高）；實作上**支援任何標準 USB/Bluetooth gamepad**（PS5 / Xbox / 通用），透過 [Web Gamepad API](https://developer.mozilla.org/en-US/docs/Web/API/Gamepad_API) 自動偵測連接 → 動態 mapping 到下圖 button 角色。Gamepad 是 **optional enhancement**，鍵盤+滑鼠是 **universal core**（§3）。

### 2.1 完整 button mapping

```
                           PSS_RX/RY (R-stick): 紙磚旋轉 (連續 360°)
                                  ┃
                                  ▼
   PSB_PINK □ ──────┐         ┌─── (R3 按下): Layer 顯示 cycle
   PSB_BLUE ✕ ─────┤         │       (border/string/final)
   PSB_RED ○ ──────┤         │
   PSB_GREEN △ ────┤         │
                   │         │
   ┌──────────────┴─────────┴──────────┐
   │                                     │
   │  右側 4 動作鍵                       │
   │  ──────────                         │
   │  □ Square: 切割/切換 base shape    │
   │           (cycle I → . → O → I)     │
   │  △ Triangle: 切換 tangle 庫        │
   │            (cycle 6 個 tangles)     │
   │  ○ Circle: 後悔 (undo 30 步)       │
   │  ✕ Cross: 確認                      │
   │                                     │
   │  R1: 疊加 3 次                      │
   │  R2: 疊加到底 (raycast 邊界)         │
   │                                     │
   ├─────────────────────────────────────┤
   │                                     │
   │  PSB_START: 主選單                  │
   │    ├─ Char picker (預設「心」)      │
   │    ├─ Mode (純禪繞/空心填充/背景) │
   │    ├─ Tile size (Bijou/標準/學徒磚)│
   │    ├─ Char outline 顯示 toggle      │
   │    ├─ Save / Snapshot / Download    │
   │    └─ Settings                      │
   │                                     │
   │  PSB_SELECT: Element size cycle     │
   │              (XS/S/M/L/XL)           │
   │                                     │
   ├─────────────────────────────────────┤
   │                                     │
   │  L-stick (PSS_LX/LY): 元素變形連續  │
   │     (4 軸：中高邊低/邊高中低/        │
   │      左高右低/右高左低)              │
   │  L3 (按下): Density cycle            │
   │             (low/medium/high)        │
   │                                     │
   │  D-Pad: 元素 pseudo-3D 變形 (4 方向)│
   │     ↑: 朝前 (foreshortening)        │
   │     ↓: 朝自己 (左右增厚)            │
   │     ←: 朝左 (右側增厚)               │
   │     →: 朝右 (左側增厚)               │
   │                                     │
   │  L1: 角度立即回正 (rotation = 0)     │
   │  L2: 角度回到上次 (history pop)      │
   │                                     │
   └─────────────────────────────────────┘
```

### 2.2 切割 mode 狀態機

```
┌─ 疊加 mode (default) ──────────────────────┐
│  D-Pad: pseudo-3D 4 方向                  │
│  L-stick: 變形 degree                     │
│  R-stick: tile rotation                   │
│  R1/R2: 疊加 3次/到底                      │
└──────────────┬─────────────────────────────┘
               │ □ Square 按下
               ▼
┌─ 切割 mode + base shape: I ────────────────┐
│  從 tile 底部中央向前畫直線切割            │
│  D-Pad 左/右: 向左/右 bend (curve degree)  │
│    重複按: 加深 bend → 變 C (curve)        │
│  D-Pad 上/下: 增加/縮短長度                 │
│  D-Pad 左後右: S 形 (S-shape)              │
│  D-Pad 右後左: 反向 S 形                   │
│  L-stick: 連續控制 deformation 強度        │
│  ○ Circle: 取消上次按鍵的變形                │
│  ✕ Cross: 確認切割                          │
└──────────────┬─────────────────────────────┘
               │ □ Square 再按
               ▼
┌─ 切割 mode + base shape: . (Dot) ──────────┐
│  從 tile 底部中央朝前虛擬指向點             │
│  D-Pad: 上下左右移動指向點                  │
│  ○ Circle: 取消上次移動                     │
│  ✕ Cross: 確認指向點當作切割中心            │
└──────────────┬─────────────────────────────┘
               │ □ Square 再按
               ▼
┌─ 切割 mode + base shape: O (Orb) ──────────┐
│  從 tile 底部中央向前一個圓                 │
│  D-Pad ↑: 放大圓                           │
│  D-Pad ↓: 縮小圓                           │
│  D-Pad ←: 放大圓                           │
│  D-Pad →: 縮小圓                           │
│  L-stick: 連續放/縮                         │
│  ✕ Cross: 確認切割圓                        │
└──────────────┬─────────────────────────────┘
               │ □ Square 再按
               ▼
回到 切割 mode + base shape: I（cycle 完整）
```

→ ✕ 確認後切割線寫入 `layer: final`，回到疊加 mode；○ 取消最後一筆變形。

### 2.3 預覽畫面 status 顯示

紙磚 canvas 上方 status bar：

```
┌─────────────────────────────────────────────────┐
│ 模式: 切割 / 疊加  │ 元素: I/C/S/./O/<tangle>   │
│ 旋轉: 45°          │ Layer: final               │
│ Density: medium    │ Size: M (40px)             │
└─────────────────────────────────────────────────┘
```

---

## 3. Input methods（鍵盤+滑鼠 core, gamepad optional enhancement）

> 🆕 **v0.3 reframe**：v0.2 將「PS2 + 鍵盤 + 滑鼠三 input method 等效」列為 hard requirement；v0.3 重新定位為：
>
> - **鍵盤 + 滑鼠是 universal core**（web 標準，所有 user 都能用、不需額外硬體）
> - **Gamepad 是 progressive enhancement**（透過 [Web Gamepad API](https://developer.mozilla.org/en-US/docs/Web/API/Gamepad_API) auto-detect 連接，**任何標準 USB/Bluetooth gamepad** 都能 mapping）
> - PS2 layout 圖示作為 mapping 教學範例保留（§2），不限制 hardware

### 3.1 鍵盤 mapping（universal core）

| Gamepad 角色（以 PS2 layout 為例） | 鍵盤 |
|---|---|
| D-Pad ↑↓←→ | **方向鍵** (右手) |
| L-stick (連續 4 軸) | **WASD** (左手, 持續按 = 連續) |
| R-stick | **IJKL** (右手第 2 區) |
| □ Square (切割/切換 base) | **F** (左手食指) |
| △ Triangle (切換 tangle) | **R** |
| ○ Circle (後悔) | **Z** |
| ✕ Cross (確認) | **Space** |
| R1 (疊加 3 次) | **E** |
| R2 (疊加到底) | **Shift + E** |
| L1 (角度回正) | **Q** |
| L2 (角度回上次) | **Shift + Q** |
| PSB_START (主選單) | **Esc** 或 **M** |
| PSB_SELECT (size cycle) | **Tab** |
| L3 (density cycle) | **C** |
| R3 (layer cycle) | **V** |

### 3.2 滑鼠 mapping + 紙磚右側 sidebar（universal core）

```
┌────────────────────────┬─────────────────────────┐
│                         │  📋 模式                 │
│                         │  ⚪ 切割  ⚪ 疊加         │
│                         │                          │
│                         │  🎯 元素 (□ cycle)       │
│                         │  ┌─┬─┬─┐                 │
│                         │  │I│.│O│                 │
│      紙磚 canvas         │  └─┴─┴─┘                 │
│                         │                          │
│  滑鼠拖拉 = 變形         │  🌀 Tangle (△ cycle)     │
│  滾輪 = size 調整        │  ┌─┬─┬─┐                 │
│  右鍵 = ✕ 確認          │  │CM│Hb│Tp│ ← 6 個      │
│  中鍵 = ○ 後悔          │  └─┴─┴─┘                 │
│                         │                          │
│                         │  ↻↺ 旋轉 (R-stick)       │
│                         │  ▼▲ 立即回正 / 上次      │
│                         │                          │
│                         │  🔁 疊加 3 次 / 到底     │
│                         │                          │
│                         │  ⚙️ Density / Layer     │
│                         │                          │
│                         │  💾 主選單 (PSB_START)    │
└────────────────────────┴─────────────────────────┘
```

滑鼠特殊操作：
- **拖拉軌跡** = 連續變形（替代 D-Pad / L-stick）
- **右鍵** = ✕ 確認
- **中鍵** = ○ 後悔
- **滾輪** = element size 調整（XS↔XL）
- **Shift + 滾輪** = density 切換
- **Ctrl + 滾輪** = tile rotation

### 3.3 Web Gamepad API integration（progressive enhancement）

🆕 v0.3 新加。

**偵測流程**：

```js
// 監聽 gamepad 連接事件
window.addEventListener('gamepadconnected', (e) => {
  // e.gamepad.id: 例 "Sony PLAYSTATION(R)3 Controller"
  //                "Xbox 360 Controller"
  //                "Standard Gamepad" (W3C standard mapping)
  showToast(`Gamepad 已連接：${e.gamepad.id}（可選用）`);
  enableGamepadInput(e.gamepad.index);
});

// Game loop 內 poll gamepad state
function pollGamepad(index) {
  const gp = navigator.getGamepads()[index];
  if (!gp) return;
  // gp.buttons[0..16] / gp.axes[0..3]
  // 對應 W3C "Standard Gamepad" mapping
}
```

**Mapping 策略**：
- 使用 W3C **「[Standard Gamepad](https://w3c.github.io/gamepad/#dfn-standard-gamepad)」** mapping (gp.mapping === 'standard')
- Standard mapping 已涵蓋 PS3/PS4/PS5 + Xbox 360/One/Series + 大部分 USB gamepad
- Button index 對應 §2 PS2 layout 的角色（square=button[2], triangle=button[3] 等）
- 非 standard mapping 的 gamepad → fallback 到 generic numeric mapping + UI 顯示「請用鍵盤滑鼠」

**Browser 支援**：
- Chrome / Edge: 完整支援（primary target）
- Firefox: 支援但 button mapping 偶有差異 → 6z-7 manual 驗一次
- Safari: 支援但需 user gesture 啟動
- 對應 §9 Risk R4「Web Gamepad API 跨 browser 行為差異」

**降級策略**：gamepad 不可用 / 沒接 → 鍵盤+滑鼠 sidebar 完整 cover 所有功能（universal core 已是 hard requirement）。

---

## 4. Pseudo-3D 變形機制 ⭐ v0.2 新加

### 4.1 概念

紙磚是 2D，但透過 stroke 變形產生 3D perspective 視覺效果：

| D-Pad 方向 | 視覺效果 | 實作 |
|---|---|---|
| ↑ 朝前 | foreshortening — element 往畫面深處延伸（大→小） | stroke points 朝畫面中心點 scale down |
| ↓ 朝自己 | element 往畫面前方延伸（大→更大），左右兩側變厚 | stroke points 往觀者方向 scale up + side thickening |
| ← 朝左 | left-tilt perspective — 右側看起來比左側厚 | stroke points 朝左方位 skew + right-side thickening |
| → 朝右 | right-tilt perspective — 左側看起來比右側厚 | stroke points 朝右方位 skew + left-side thickening |

**L-stick 4 軸 deformation curvature**：
- 中高邊低 (^_^): 中央凸起，兩側下沉
- 邊高中低 (V_V): 兩側凸起，中央下沉
- 左高右低 (\\\\): 左高斜下到右低
- 右高左底 (////): 右高斜下到左低

L-stick **連續** 控制 degree (0-1)，D-Pad **離散** 4 方向選 perspective。

### 4.2 Schema

```yaml
strokes:
  - id: "stroke_001"
    type: line | curve | s_shape | orb | dot
    layer: final
    points: [...]                          # tile-local 2D points
    size: 40                                # px
    rotation: 45                            # tile-local angle
    pseudo_3d:                              # NEW v0.2
      depth_dir: 'forward' | 'backward' | 'left' | 'right' | null
      depth_degree: 0.5                      # 0-1
      curve_mode: 'high-mid' | 'high-sides' | 'left-high' | 'right-high' | null
      curve_degree: 0.3                      # 0-1, 從 L-stick 強度
    repeat_meta:
      direction: 'E' | 'NE' | ...
      count: 3 | -1                          # -1 = 到底 (raycast)
      spacing: 2                             # mm
```

### 4.3 Render pipeline

```
1. Stroke source: tile-local 2D points
2. Apply pseudo_3d transform:
   - if depth_dir == 'forward': scale toward center
   - if depth_dir == 'backward': scale away from center + side thickening
   - if depth_dir == 'left'|'right': skew + opposite-side thickening
   - apply curve_mode 4-axis displacement based on curve_degree
3. Apply repeat_meta:
   - generate count copies along direction at spacing intervals
   - or raycast to edge if count == -1
4. Apply tile.rotation:
   - rotate all final stroke points by tile.rotation degrees
5. Render to canvas (HTML5 + SVG hybrid)
```

---

## 5. 8+1+3 條架構軸 — 全 QODA 決定

延續 v0.1 軸 1-12，加 v0.2 新軸 13-15：

### 已 confirmed v0.1 軸（簡述）

| # | 軸 | v0.2 狀態 |
|---|---|---|
| 1 | 字框 outline 來源 | 不變 — freetype + 思源黑體 Bold |
| 2 | MVP 3 modes | 不變 — 純禪繞 + 空心填充 + 背景鑲嵌 |
| 3 | MVP tangle 庫 6 個 | 不變 |
| 4a | 紙磚旋轉 hybrid | **更新** — R-stick 連續 + R3 cycle 8 preset + L1 回正 + L2 回上次 |
| 4b | tile-local coords | 不變（核心 mechanism） |
| 5 | Density 控制 | **更新** — L3 cycle 3 檔（原 slider 改 button cycle） |
| 6 | UI 引導 | **更新** — toolbar 順序 + 主選單；具體 input 走 PS2 / 鍵盤 / 滑鼠 |
| 7 | Element size | **更新** — PSB_SELECT cycle 5 size（原 5 button + slider 改 cycle） |
| 8 | File format schema | **大幅更新** — 加 pseudo_3d field |
| 9 | 9 cell panel | **REMOVED** — 由 PS2 D-Pad + L-stick 取代 |
| 10 | 草稿 vs 定稿 | 不變（is_draft boundary） |
| 11 | 下載檔名 timestamp | 不變 |
| 12 | Gallery dispatch | 不變（kind='zentangle'） |

### v0.2 新加軸（v0.3 微調）

### 5.13 軸 13：Input scheme — 鍵盤+滑鼠 core，gamepad enhancement

**Q**：用什麼 input scheme？
**v0.2 D**：PS2 + 鍵盤 + 滑鼠三種等效（hard requirement）。
**v0.3 D ★（reframe）**：**鍵盤 + 滑鼠是 universal core**（所有 user 都能用）；**Gamepad 是 progressive enhancement**（透過 Web Gamepad API auto-detect 任何標準 gamepad，PS2/PS5/Xbox/通用都支援）。PS2 layout 圖示作為 mapping 範例（教學友善），**不限制 hardware**。
**Schema 影響**：input method 不存 schema（只記錄結果 stroke）。
**A**：✅ v0.3 confirmed (senior review path A)

### 5.14 軸 14：Pseudo-3D 變形系統

**Q**：怎麼實現 pseudo-3D 視覺效果？
**D ★** D-Pad 4 方向 (perspective) + L-stick 4 軸 (curvature) + 連續 degree。Schema 加 `pseudo_3d` field。
**A**：✅ 已 confirmed

### 5.15 軸 15：切割 mode 狀態機

**Q**：切割線怎麼設計？
**D ★** □ Square cycle base shape: I → . → O → I（3 個）；I 模式內 D-Pad bend 衍生 C / S（不入 cycle 但變 stroke type）。
**A**：✅ 已 confirmed

### 軸 16-18: 13 missing decisions 對應結果

每條已在 §0 v0.2 change log 列出，不重複。

---

## 6. Sub-phase 拆解 (v0.3 重 plan)

| Sub-phase | 範圍 | v0.1 | v0.2 | **v0.3** | Notes |
|---|---|---|---|---|---|
| **6z-0** | Design doc（v0.2 → v0.3） | — | 4-5h | **5-6h** | ✅ 完成（含 v0.3 reframe） |
| **6z-1** | Outline 抽取 + 純禪繞 mode + 紙磚 canvas | 4-5h | 5-6h | **5-6h** | 加鍵盤+滑鼠 input layer scaffolding（含主選單 force-modal） |
| **6z-2a** | 紙磚 rotation logic + math (pure, no input wiring) | — | — | **3-4h** | NEW v0.3 — 切自 v0.2 6z-2 (senior note #5) |
| **6z-2b** | 紙磚 rotation input wiring (鍵盤+滑鼠 sidebar 鈕 + R-stick 預留) | — | — | **2-3h** | NEW v0.3 — 切自 v0.2 6z-2 |
| **6z-3** | ICSO 工具 + 6 tangles 庫 + tangle cycle | 5-6h | 6-8h | **6-8h** | 鍵盤 R 鍵 + sidebar tangle 區 |
| **6z-4** | 鍵盤+滑鼠 input layer 完整 wiring（D-Pad/L-stick 等 abstraction）| — | 6-8h | **5-7h** | input abstraction layer (gamepad-agnostic) |
| **6z-5a** | Pseudo-3D `depth_dir` 4 方向 (perspective only) | — | — | **5-6h** | NEW v0.3 — 切自 v0.2 6z-5 (senior note #2) |
| **6z-5b** | Pseudo-3D `curve_mode` 軸 1 (中高邊低) + visual verify gate | — | — | **2-3h** | NEW v0.3 — 加軸前 visual verify |
| **6z-5c** | Pseudo-3D `curve_mode` 軸 2 (邊高中低) — 視 5b 結果決定軸 3-4 | — | — | **1-2h or skip** | 評估點：若 5b 視覺夠豐富，軸 3-4 砍 |
| **6z-6** | 切割 mode 狀態機（□ cycle I/./O + D-Pad bend C/S）| — | 5-7h | **5-7h** | 核心 mechanism (pure logic 抽 .mjs，可 Node test) |
| **6z-7** | **Web Gamepad API integration**（auto-detect + button mapping wrapper）| — | 8-10h | **3-4h** ⭐ | 🆕 v0.3 reframe — gamepad-agnostic enhancement (節省 ~6h) |
| **6z-8** | Embedded mode（漢字 outline + fill_mode）| 4-5h | 4-5h | **4-5h** | unchanged |
| **6z-9** | Draft 系統（30 步 undo + 5 分鐘 auto-save + download timestamp）| 3-4h | 4-5h | **4-5h** | 加 layer toggle |
| **6z-10** | Gallery 整合（kind='zentangle' + thumbnail + dispatch dict）| 2-3h | 2-3h | **2-3h** | unchanged |
| **6z-11** | Tests + decision logs + bump（鍵鼠 manual E2E + gamepad smoke）| 3-4h | 5-6h | **3-4h** ⭐ | 🆕 v0.3 — testing matrix 縮減 (節省 ~2h) |

**Phase 6z v0.3 總估**：**48-67 hours / 1.5-2 週工作日**（vs v0.2 58-79h，**節省 10-12h** 透過 gamepad reframe + sub-phase 切細）。

> **v0.3 vs v0.2 估時節省來源**：
> - 6z-7 Web Gamepad API wrapper (3-4h) vs v0.2 三 input matrix 等效 (8-10h) → **-6h**
> - 6z-11 testing 縮減 (3-4h) vs v0.2 三 input matrix testing (5-6h) → **-2h**
> - 6z-2 切 a/b + 6z-5 切 a/b/c：**估時不變但 sub-phase boundary 清楚**（senior review note #2 + #5 應用）
>
> **預期實際 burn 1.2-1.5x**（greenfield + 4 高 risk），realistic **58-100h**（§9 R7）。

---

## 7. Anti-pattern 清單 (v0.2 更新)

> 🔗 **應用 personal-playbook §8.35 strict negative constraints**。

### 7.1 工程層 anti-patterns

- ❌ **stroke smoothing 算法** — user 拖拉軌跡保留原貌
- ❌ **打斷性 notification / progress bar** — 違反 Flow 狀態
- ❌ **強制 hard clip stroke 在 outline 內** — 越界 OK
- ✅ **Pseudo-3D 變形 OK**（v0.2 新接受 — acquisition-first thesis 認可創新藝術風格，不限於正統禪繞）

### 7.2 Schema 層 anti-patterns

- ❌ **stroke 存 world coords** — 違反 tile-local 核心 mechanism
- ❌ **DB 存 outline path 而非 polygon** — runtime 字型依賴讓檔案 portable 性壞
- ❌ **draft 跟 published 混用同一檔案無 boundary** — `is_draft` 必填
- ❌ **multi-char 強推進 MVP** — chars array 預留但 MVP 長度 ≤ 1

### 7.3 UX 層 anti-patterns

- ❌ **強迫使用 gamepad**（user 沒 gamepad 就用不了）— **鍵盤+滑鼠是 universal core**，gamepad 是 optional enhancement
- ❌ **gamepad button 以外的功能塞進無關按鈕** — 每按鈕 single-purpose（鍵盤 mapping 同精神）
- ❌ **published 後可後製改動** — 違反軸 10 immutable
- ❌ **強制 wizard 流程** — 自由為主 + 主選單組織
- ❌ **silent default**（特別 `pseudo_3d.depth_dir` / tile size / mode）— 主選單第一次開磚 force-modal、schema null 加 comment（v0.3 senior review note #5）

### 7.4 Implementation 層 anti-patterns

- ❌ **失敗 2 次仍重試同方法** — §8.32 失敗 2 次換方法
- ❌ **無 P7 completion format 直接 mark 完成** — §8.31
- ❌ **跳過 reviewer / 自己 review 自己** — §8.33 self-defense bias

---

## 8. P7 Completion Format（每 sub-phase 結束強制）

> 🔗 **應用 personal-playbook §8.31**。

```
[P7-COMPLETION] phase 6z-N

任務：<一句話 task summary>
方案：<採用 approach>
改動：<檔案 + 行範圍 list>
影響分析：<grep 結果 + 影響 caller / module>
三問自審：
  - 方案正確：是 / 否（理由）
  - 影響全面：是 / 否（grep 過哪些）
  - 回歸風險：低 / 中 / 高（驗證手段）
剩餘風險：<必填，什麼情境下可能不對 / 待補完處>
```

「剩餘風險」必填。違反此規則的 sub-phase commit 該被 rebase 重做。

---

## 9. Risk Register (v0.3 更新)

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| **R1** | 字框 outline 抽取技術未驗證 | High | 6z-1 spike 先驗證 freetype + Pillow path 抽取；fallback hard-coded outline 庫 |
| **R2** | 紙磚旋轉 + tile-local coords 算錯 | High | 6z-2a 完成後 manual E2E 驗證旋轉一致性（pure logic 抽 .mjs，Node test 易） |
| **R3** | **Pseudo-3D render pipeline 複雜** | **High** | 6z-5 切 a/b/c 三階段：5a depth_dir 4 dir → visual verify → 5b curve 軸 1 → verify → 5c 評估砍軸 |
| **R4** | 🆕 v0.3 改 — **Web Gamepad API 跨 browser 行為差異** | **Medium** | Chrome 為 primary target；Firefox/Safari/Edge 6z-7 manual smoke 各 1 次；非 standard mapping 的 gamepad fallback 顯示「請用鍵盤滑鼠」 |
| **R5** | 🆕 v0.3 縮減 — **Input testing 鍵鼠 + gamepad smoke** | **Medium** | 6z-11 預留 3-4h：鍵盤+滑鼠 完整 manual E2E（universal core），gamepad 各 1 個 smoke 測 |
| R6 | Tangle library 內容深度不足 | Medium | 6 個帶詳細 step tutorial；user 反饋驅動加 tangle |
| R7 | 🆕 v0.3 更新 — **Phase 6z 實際 burn 1.2-1.5x design 估時** | **High** | 估時 48-67h，realistic 預期 58-100h；嚴守 sub-phase 邊界，每 sub-phase 結束 commit + bump（仿 r29 節奏） |
| R8 | Draft 跟 published schema 不對齊 | Medium | `draft_meta.is_draft` 必填 + 兩 phase 明確 boundary |
| R9 | **切割 mode 狀態機 bug** | Medium | 6z-6 寫狀態機 unit test（pure logic，可 Node `node:test`） |
| R10 | 🆕 v0.3 更新 — **「禪繞」品牌 vs Pseudo-3D 創新風格矛盾** | Medium | 列入 §12 defer (6z-12 marketing copy phase)；UI 第一次開磚加「本工具是禪繞**啟發**的數位化創作」disclaimer |

---

## 10. 啟用條件 + 進入準則

✅ **已滿足條件**：

1. ✅ Phase 5b r28-r29k gallery 完整 ship（375 tests / 0.14.121）
2. ✅ Personal-playbook §3.13 / §8.22-§8.30 升格完成（41056b0）
3. ✅ User 願景明確（21 批資料 + v0.1 反饋 + 13 missing decisions confirmed）
4. ✅ Schema 設計收斂（軸 1-15 全 confirmed）
5. ✅ Anti-pattern 清單 + P7 strict completion 套用
6. ✅ Input method spec 明確（鍵盤+滑鼠 universal core + Web Gamepad API enhancement）
7. ✅ Pseudo-3D mechanism 明確（含 6z-5 a/b/c 切階段策略）
8. ✅ v0.2 senior review 5 notes 全處理（path A reframe 已落實 v0.3）

🚦 **未滿足條件（如有）**：無 — 可進 6z-1 implementation。

---

## 11. 跟現有 stroke-order 系統的相容性

| 區塊 | 衝突風險 | Mitigation |
|---|---|---|
| Gallery dispatch dict (r28) | low | 加 KIND_ZENTANGLE 第三 kind，仿 mandala pattern |
| Thumbnail 生成 (r28b) | low | cairosvg 直接複用 |
| User profile / avatar (r29j) | low | 不衝突 |
| Like / bookmark / sort (r29 系列) | low | 不衝突，自動 cover zentangle uploads |
| URL hash route (r29f-g) | low | 不衝突，可選加 `#zentangle=<id>` deep-link |
| Cross-mode snapshot (phase 7) | n/a | 6z 用單 slot localStorage |

---

## 12. Defer 留給後續

| 待做 | Phase |
|---|---|
| Multi-character (`chars` array > 1) | phase 6z+1 |
| 彩色禪繞（11 色 preset） | phase 6z+1 |
| 陰影 + Tortillion 推色 | phase 6z+2 |
| Aura 工具（自動派生平行 stroke） | phase 6z+1 |
| Tangle library 擴大 | user 反饋驅動 |
| Tangle step tutorial 模式 | phase 6z+1 (V1.5) |
| 智慧 size suggest（dim 過大但可選） | phase 6z+1 |
| Image → config 反向解析（CV） | phase 6z+2 / 7+ |
| Cross-mode snapshot system | **phase 7** (獨立) |
| Mobile / tablet responsive | phase 6z+1 |
| `pushState` 取代 hash route | 視 SEO 需求 |
| 🆕 v0.3 — **Marketing copy + 品牌 disclaimer**（「禪繞**啟發**的數位化創作」UI 文案） | **phase 6z-12**（gallery 整合後） |
| 🆕 v0.3 — **Tangle 庫線上更新機制** (server-driven library) | phase 6z+2 |

---

## 13. Approval gate

**Design doc v0.3 寫完 ✅**（v0.2 senior review path A reframe 已落實）。下一步：

| | 動作 |
|---|---|
| **A ★** | **User Approve design doc v0.3 → 進 6z-1 implementation** |
| B | User 想修改某條軸 → re-loop QODA |
| C | 暫存 design doc → 收工 |

每 sub-phase 結束按 P7 completion format 提交 + commit + bump version + 各自 sub-phase decision log。

---

## 14. Cross-link 參考

- Design v0.2（前一版，5/6 深夜）：commit `fff3014`（git history snapshot）
- Design v0.1（5/6 深夜）：[`2026-05-06_phase6z_zentangle_design.md`](2026-05-06_phase6z_zentangle_design.md)
- 設計 spike：[`2026-05-06_phase6z_design_spike.md`](2026-05-06_phase6z_design_spike.md)
- 工作日誌：[`../journal/2026-05-06_session_log.md`](../journal/2026-05-06_session_log.md)
- 共通性原則：[`../PRINCIPLES.md`](../PRINCIPLES.md) §6 設計流程原則 + §6.8 thesis ↔ rule mapping
- Personal-playbook 治理層：
  - §0.1 「AI 不是能力不夠、是紀律不夠」
  - §0.2 Enforcement-based vs Hope-based governance
  - §0.4 重新框架問題 > 答問題
  - §8.31 P7 三問自審
  - §8.32 失敗 2 次換方法
  - §8.35 Strict negative constraints
- r28 by-kind dispatch dict pattern：[`2026-05-04_phase5b_r28_gallery_mandala_upload.md`](2026-05-04_phase5b_r28_gallery_mandala_upload.md)
- r27 .mandala.md schema（仿 frontmatter pattern）：[`2026-05-04_phase5b_r27_mandala_state_export_import.md`](2026-05-04_phase5b_r27_mandala_state_export_import.md)

---

## 15. 結尾

Phase 6z v0.3 是 stroke-order 至今最大單一 phase（**48-67h** 設計估，realistic 58-100h）。Design doc 完成代表「**動筆前該想清楚的事都想清楚了**」 — 對應 personal-playbook §0.4 重新框架問題 thesis 的具體實踐。

**Thesis 升級** (v0.1→v0.2 內容 thesis 不變)：v0.1「禪繞重複疊加減負工具」 → v0.2「**快速產出禪繞效果的數位工具**」 acquisition-first，鎖定「想要禪繞風格但不想慢慢手繪」的 user。

**v0.3 reframe** (input architecture)：v0.2 PS2 hard requirement → v0.3「鍵盤+滑鼠 universal core + Web Gamepad API auto-detect 任何標準 gamepad」。Senior review path A 的 elegant simplification — acquisition power 不下降，dev cost 節省 10-12h，hardware niche risk 消除。

Implementation 等 user Approval design doc v0.3 後正式啟動。每 sub-phase 帶 P7 completion format + anti-pattern 自審 + commit + bump，仿 r29 系列節奏推進。

> 「方法論的本質 = 把『應該做但會偷懶的事』變成『不做就無法交付』」 — personal-playbook §0.1
