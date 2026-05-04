# Phase 5b r29h：Toast 元件（取代散點 alert + 補完 r29g 提示）

**日期**：2026-05-05
**版本**：0.14.117 → 0.14.118
**範圍**：reusable toast notification + 替換 4 處散點 `alert()` / `console.warn`
**測試**：`tests/test_toast.mjs` 9 Node unit + Node 累計 38 / Python 307 不退化

---

## 1. 動機

r29g defer 表寫了「toast 元件 — upload 不存在友善提示」。再深挖一層 — gallery 至少 4 處散點 `alert()` / `console.warn`：

| 既有 | 問題 |
|---|---|
| r29g `console.warn`（upload 不存在） | user 看不到，分享連結失效時靜默 |
| r29 delete 失敗 `alert()` | 醜，blocking 體驗差 |
| r29 like 失敗 `alert()` | 醜 |
| r29b bookmark 失敗 `alert()` | 醜 |

r29h 一次做齊：reusable toast utility + 換掉 4 處 alert/warn → foundation 投資而非 single-purpose。

## 2. 設計核心

### 2.1 Scope：reusable utility（不單修 r29g）

**選擇**：`gallery/toast.mjs` exports `showToast` + `_toastSpec`，replace 4 處 alert/warn。

**避開**：
- 單一 `alert()` patch（醜，1 行 fix）
- 完整 toast 系統（queue / multi-position / theme / a11y aria-live polite/assertive 切換 / undo button 等）— overkill

**理由**：4 處同模式散點 = 標準 utility 投資訊號。同時最多 1 個（無 queue），3 個 type，5s auto-dismiss — 足夠 cover 90% 場景。

### 2.2 Pure helper 抽出 `_toastSpec`

```javascript
export function _toastSpec(message, type='info', duration=5000) {
  const validType = ALLOWED_TYPES.includes(type) ? type : 'info';
  const validDuration = (Number.isFinite(duration) && duration > 0)
    ? duration : DEFAULT_DURATION;
  return { type: validType, duration: validDuration,
           classNames: `gl-toast gl-toast--${validType}`,
           message: String(message ?? '') };
}
```

**理由**：DOM 操作沒法 Node 純測（沒 `document`）— 把 input validation logic 抽出 pure function 即可 9 個 unit test 涵蓋 type fallback / duration fallback / message 強制 string 等。`showToast` 的 DOM 部分走 manual E2E。

跟 r29f hash.mjs 同 pattern：**pure helper exported for testability**。

### 2.3 Type 三軸：info / warning / error

| Type | 用途 | 顏色 |
|---|---|---|
| `info` | 一般通知 | 淡藍 #e8f0ff |
| `warning` | 預期外但非錯（如 r29g upload 不存在） | 淡黃 #fff7d9 |
| `error` | 操作失敗（delete / like / bookmark fail） | 淡紅 #ffe5e5 |

**避開** success type — user 看 view 變動就知（like count 增加、card 消失）。多餘 toast 干擾節奏。

### 2.4 同時最多 1 個 toast，無 queue

**選擇**：`showToast` 內部 `_dismissCurrent()` 先清舊 toast，再顯新。`_currentToast` / `_currentTimer` / `_escListener` 三個 module-level state。

**避開**：queue 系統（多 toast 排隊顯示）— 增加複雜度，user 體驗未必更好（連 5 個 error 一起跳出反而焦慮）。

**Trade-off**：快速連續操作失敗時只看到最後一個 toast → 對 MVP 可接受。後續真有需求再加 queue。

### 2.5 三種關閉方式：click / X / ESC

```javascript
toast.addEventListener('click', (ev) => {
  if (ev.target !== closeBtn) _dismissCurrent();
});
closeBtn.addEventListener('click', _dismissCurrent);
document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape') _dismissCurrent();
});
```

加自動 timeout = 4 種關法。覆蓋 keyboard / mouse / passive wait 三類 user。

### 2.6 容器動態 inject 不改 HTML

```javascript
function _ensureContainer() {
  let c = document.getElementById(CONTAINER_ID);
  if (!c) {
    c = document.createElement('div');
    c.id = CONTAINER_ID;
    c.setAttribute('aria-live', 'polite');
    c.setAttribute('aria-atomic', 'true');
    document.body.appendChild(c);
  }
  return c;
}
```

跟 r29d profile banner 同手法 — JS 在 first call 時 inject，HTML 維持乾淨。

`aria-live="polite"` + `aria-atomic="true"` = 螢幕閱讀器會讀 toast 內容（無障礙基本盤）。

### 2.7 textContent 不 innerHTML

```javascript
const msgSpan = document.createElement('span');
msgSpan.textContent = spec.message;  // ← 不 innerHTML
```

**理由**：`textContent` 自動 escape — `<script>alert(1)</script>` 變成純文字顯示，不執行。Toast 訊息 90% 來自 server error message（可能含特殊符），用 textContent 就 XSS-safe，spec 也不需做 escape。

### 2.8 動畫：CSS keyframes，220ms 滑入 / 200ms 淡出

```css
@keyframes gl-toast-slide-in {
  from { transform: translateY(-12px); opacity: 0; }
  to   { transform: translateY(0);     opacity: 1; }
}
@keyframes gl-toast-fade-out {
  from { transform: translateY(0); opacity: 1; }
  to   { transform: translateY(-8px); opacity: 0; }
}
```

`is-leaving` class 觸發 fade-out，220ms 後 element removeChild。比 200ms keyframe 多 20ms 緩衝避免動畫被中斷的 visual glitch。

### 2.9 r29g console.warn 替換策略

```javascript
// 替換前
console.warn('[r29g] deep-link upload not found:', state.deepLinkUploadId);
state.deepLinkUpload = null;

// 替換後
showToast(
  `分享的作品 #${state.deepLinkUploadId} 已不存在或已被隱藏`,
  'warning',
);
state.deepLinkUpload = null;
state.deepLinkUploadId = null;
_writeHash();  // 清掉 hash upload key — 避免 reload 又看到同 toast
```

**新增**：清 hash 中 `upload` key。User 不會 reload 又看到同一個錯誤 toast，URL bar 也乾淨。

## 3. 實作

### 3.1 新檔：`gallery/toast.mjs`（~95 lines）

- `_toastSpec(message, type, duration)` pure helper
- `showToast(message, type, duration)` DOM-coupled 主要 API
- 內部 state `_currentToast` / `_currentTimer` / `_escListener` 跟 `_dismissCurrent` / `_ensureContainer` helpers

### 3.2 CSS（`gallery.css` +60 行）

`.gl-toast-container` 固定 top-center / `.gl-toast` flex base / `.gl-toast--info|warning|error` 顏色變體 / `.gl-toast-close` × 按鈕 / `.gl-toast.is-leaving` fade-out / 2 個 keyframes。

### 3.3 `gallery.js` 異動

- imports 加 `import { showToast } from './toast.mjs'`
- 4 處替換：
  - r29g console.warn upload 不存在 → `showToast(... , 'warning')` + 清 hash
  - r29 delete fail alert → `showToast(... , 'error')`
  - r29 like fail alert → `showToast(... , 'error')`
  - r29b bookmark fail alert → `showToast(... , 'error')`

### 3.4 Server 零變動

純 frontend feature。

## 4. 測試

### 4.1 Node `node:test` (`tests/test_toast.mjs` — 9 unit)

| 範疇 | Test 數 |
|---|---|
| Type validation | 3（default info / 3 valid preserved / invalid → fallback） |
| Duration validation | 3（default 5000 / custom preserved / invalid → fallback） |
| Message coercion | 2（string / null/undefined → '' / 不 escape — DOM 端 textContent 處理） |
| Shape | 1（4-key 結構） |

執行：`node --test tests/test_toast.mjs` → **9 pass**。

### 4.2 Node 累計：38（29 hash + 9 toast）

`node --test tests/test_hash_route.mjs tests/test_toast.mjs` → **38 pass**。

### 4.3 Python regression：307 不退化

純 frontend，server / DB / service 零動 → **307 pass**。

### 4.4 MIME 確認

`/static/gallery/toast.mjs` → `text/javascript`，瀏覽器接受。

### 4.5 Manual E2E checklist

| # | 場景 | 預期 toast |
|---|---|---|
| 1 | 直訪 `#upload=99999` (不存在) | warning 黃色 toast「分享的作品 #99999 已不存在...」5s 後消，URL upload key 清掉 |
| 2 | Click 自己 upload 的刪除按鈕 → 後端故意打 500 | error 紅色 toast「刪除失敗：HTTP 500」 |
| 3 | 未登入 click ❤️ | error toast「讚操作失敗：HTTP 401」（authentication required） |
| 4 | Click toast 任意處 / X / ESC 鍵 | 立刻關閉動畫 |
| 5 | 連續觸發 2 個 toast | 第二個取代第一個（無 queue） |

## 5. 涉及檔案

```
src/stroke_order/web/static/gallery/toast.mjs    (新 — ~95 行 pure + DOM)
src/stroke_order/web/static/gallery/gallery.css  (+60 行 toast styles)
src/stroke_order/web/static/gallery/gallery.js   (import + 4 處 alert/warn 替換)
tests/test_toast.mjs                              (新 — 9 Node unit)
docs/decisions/2026-05-05_phase5b_r29h_toast_component.md
pyproject.toml                                    (0.14.117 → 0.14.118)
```

API endpoint / service / DB 零動。

## 6. 教訓 / 共通性

- **散點 4 處同模式 = utility 投資訊號**：見到 `alert()` / `console.warn` 反覆出現相同 shape，是時候抽 utility。**通用原則**：3 個 + 同模式 → 抽出；2 個內 → 還可忍。
- **DOM-coupled module 仍可 unit test**：把 input validation 抽 pure helper（`_toastSpec`），DOM 操作部分走 manual E2E。同 r29f hash.mjs pattern — pure helper for testability。**通用原則**：side-effect 跟 logic 分層，logic 走 unit、effect 走 E2E。
- **`textContent` 自動 escape，spec 不需 escape**：toast 訊息來源 90% 是 server error，可能含 `<` `>`。`textContent` 賦值天然 XSS-safe — spec 層保留原文，DOM 層自動轉純文字。**通用原則**：display 用 `textContent`，需要 markup 才用 `innerHTML` + 手動 escape。
- **無 queue 是 MVP 合理 trade-off**：實作 queue 增加 ~30% 複雜度，但實際 user 體驗（連續 5 個 error 一起跳）未必更好。**通用原則**：MVP 砍 queue，需求出現再加。
- **替換時順帶清 hash key**：r29g console.warn → toast warning 同時清 `state.deepLinkUploadId` 跟 `_writeHash()`，避免 reload 又看到同 toast。**通用原則**：error 處理該 cleanup 的 state 一起 cleanup，不只通知 user。
- **動畫時長 220ms 比 200ms keyframe 多 20ms 緩衝**：避免動畫被 element removeChild 切斷的 visual glitch。**通用原則**：CSS animation duration 跟 JS removeChild timeout 不同步時，後者多 10-20ms 安全。
- **`aria-live="polite"` 是無障礙基本盤**：螢幕閱讀器會自動讀 toast 內容，user 不需 focus toast。`role="alert"` for error vs `role="status"` for info/warning — 區分緊急程度。**通用原則**：所有 ephemeral notification 都該標 aria-live。

## 7. r28-r29h 系列累計統計

| Phase | 重點 | Tests | 版本 |
|---|---|---|---|
| r28-r29g（前 11 phase） | 略 | Python +85 / Node +29 | ... → 0.14.117 |
| **r29h** | **toast 元件 + 替換 4 處 alert** | **Node +9** (38 累計) | **0.14.118** |

**Two-day total: Python 307 + Node 38 = 345 tests, +12 phases, 12 versions, 12 decision logs.**

Gallery UI 補完 user feedback 通道 — error / warning 不再 silent 或 alert blocking。

## 8. Defer 留給後續

| 待做 | Phase |
|---|---|
| Toast queue（多 toast 排隊）| 真有 user 反饋再做 |
| Toast action button（如「重試」/「復原」） | 視需求 |
| Success type | 真需要再加（目前 view 變動已隱含） |
| Profile 編輯 UI（user 改 bio / display_name） | phase 5c — 下個 high-value |
| Profile avatar 頭像上傳 | phase 5c+ |
| Featured / curated picks（admin role） | phase 5c |
| Follow / 跟隨 user → 個人化 feed | phase 6 |
| `pushState` 取代 hash（pretty URL） | 視 SEO / 美觀需求 |
