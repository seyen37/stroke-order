# Phase 5b r29k：Avatar Drag-Drop + Client-side Validation

**日期**：2026-05-05
**版本**：0.14.120 → 0.14.121
**範圍**：r29j avatar 的 UX polish — drag-drop 拖放上傳 + client-side type/size 驗證避免無效 round-trip
**測試**：Node `test_avatar_validate.mjs` +9（4 計劃 + 5 邊界 case）→ Node 55 / Python 320 不退化

---

## 1. 動機

r29j avatar 上傳走 file input button 流程能 work，但兩個小痛：

1. **拖放更直覺**：modern user 習慣把圖片從 desktop 拖進來，不想點按鈕開檔案選擇器
2. **失敗 round-trip 浪費**：選錯檔（GIF / 3MB JPEG）才送 server → 422 → user 看 toast 才知道。client-side 預檢可即時回饋

r29k 補完：drag-drop on preview area + 跟 server 完全 mirror 的 client validation，**不換功能、純 UX 補丁**。

## 2. 設計核心

### 2.1 共用 `_handleSelectedFile(file)` path — file input + drag-drop 同 entry

```javascript
async function _handleSelectedFile(file) {
  // r29k: client-side validation（mirror server）
  const result = validateAvatarFile(file);
  if (!result.ok) {
    status.textContent = result.error;
    return;
  }
  // ... upload + UI flow ...
}
```

兩個觸發來源：
- `avatarInput.change` → `files[0]` → `_handleSelectedFile`
- `avatarPreview.drop` → `dataTransfer.files[0]` → `_handleSelectedFile`

**避開**：兩套上傳 logic 各自 implement validation + status update + refresh — drift 風險。

**通用原則**：多入口共用 single execution path，validation/error handling 寫一次。

### 2.2 Pure validator `validateAvatarFile(file) → {ok, error?}` mirror server

```javascript
const ALLOWED_AVATAR_TYPES = ['image/png', 'image/jpeg'];
export const AVATAR_MAX_SIZE_BYTES = 2 * 1024 * 1024;

export function validateAvatarFile(file) {
  if (!file) return { ok: false, error: '請選擇要上傳的檔案' };
  const type = String(file.type || '').toLowerCase().split(';')[0].trim();
  if (!ALLOWED_AVATAR_TYPES.includes(type))
    return { ok: false, error: `頭像格式須為 PNG 或 JPEG（收到 ${file.type || '未知'}）` };
  // ... size checks ...
}
```

跟 server `service.py` 的 `ALLOWED_AVATAR_TYPES` / `AVATAR_MAX_SIZE_BYTES` **完全 mirror**。

**為什麼 mirror 不嚴格**：規則一致 → user 不會困惑「client 過了 server 卻 reject」。Single source of truth：先寫 server 再 mirror 到 client，避免兩端規則 drift。

**charset 後綴處理**：`image/png; charset=binary` 偶爾出現（部分 browser），split(';')[0] 拿前段比對。

### 2.3 Drag-drop visual feedback：3 件套（border + scale + label）

```css
.gl-profile-avatar-preview.is-dragover {
  box-shadow: 0 0 0 3px var(--gl-accent, #46a),
              0 0 12px rgba(70, 102, 170, 0.35);
  transform: scale(1.05);
}
.gl-profile-avatar-preview.is-dragover::after {
  content: '✚ 放開上傳';
  /* 浮在底部 */
}
```

三件視覺 cue：
1. accent border highlight
2. 1.05x scale 浮起
3. `::after` label「✚ 放開上傳」

跟 r29g `.gl-card--deeplink` 同 family 多重 cue 訊號設計。

### 2.4 `dragover` 必 `preventDefault` 否則 drop 不觸發

```javascript
avatarPreview.addEventListener('dragover', (ev) => {
  ev.preventDefault();   // ← 必要
  ev.dataTransfer.dropEffect = 'copy';
  avatarPreview.classList.add('is-dragover');
});
```

Browser 預設 dragover behavior 是「不接受 drop」，要 preventDefault 才能讓後續 drop event 觸發。**通用原則**：drop zone 必 preventDefault dragover/dragenter/drop 三 events（這裡只 dragover/drop 即可，dragenter 跟 dragover 任一即可）。

### 2.5 保留 file input button（accessibility）

Touch device（手機 / 平板）沒 drag-drop 概念，screen reader 也不適合 drag。Hidden `<input type="file">` + label-as-button 仍是 primary entry point；drag-drop 只是 desktop power-user shortcut。

**通用原則**：alternative input methods 並存，不互斥。

## 3. 實作

### 3.1 `avatar.mjs` 加 export

```javascript
export const AVATAR_MAX_SIZE_BYTES = 2 * 1024 * 1024;
export function validateAvatarFile(file) { ... }
```

跟 r29j 既有 `avatarHtml` / `_initialsSpec` 並存。

### 3.2 `auth.js` refactor + drag-drop handlers

- 抽 `_handleSelectedFile(file)` 共用 path
- file input change handler 改 call `_handleSelectedFile`
- 新增 dragover / dragleave / drop on preview

### 3.3 CSS

`.gl-profile-avatar-preview` 加 `position: relative` + transition；`.is-dragover` modifier + `::after` label。

### 3.4 零後端改動

純 frontend polish，service / API / DB / Python tests 全沒動。

## 4. 測試

### 4.1 Node `test_avatar_validate.mjs` — 9 unit

| 範疇 | Test |
|---|---|
| Happy path | PNG 1KB / JPEG 500KB / 邊界恰 2MB |
| Reject type | GIF / text/plain |
| Reject size | 3MB / 0 bytes |
| Defensive | null / undefined |
| Edge | charset 後綴（`image/png; charset=binary`） |

執行：`node --test tests/test_avatar_validate.mjs` → **9 pass**。

### 4.2 Node 累計 55（29+9+8+9）

### 4.3 Python regression：320 不退化（純 frontend，server 零動）

### 4.4 Manual E2E 4 條

| # | 場景 | 預期 |
|---|---|---|
| 1 | 拖 PNG 進 preview 圈 | dragover → border + scale + ✚ label / drop → 上傳 → 圈內 preview 換新 |
| 2 | 拖 GIF | error toast「PNG 或 JPEG」即時，0 round-trip |
| 3 | 拖 3MB JPEG | error toast「2 MB」即時 |
| 4 | 點「🖼️ 上傳頭像」按鈕仍 work（手機 fallback） | 既有流程不變 |

## 5. 涉及檔案

```
src/stroke_order/web/static/gallery/avatar.mjs   (+ validateAvatarFile + AVATAR_MAX_SIZE_BYTES export)
src/stroke_order/web/static/gallery/auth.js      (_handleSelectedFile shared path + drag-drop handlers)
src/stroke_order/web/static/gallery/gallery.css  (.is-dragover + ::after label)
tests/test_avatar_validate.mjs                    (新 — 9 Node unit)
docs/decisions/2026-05-05_phase5b_r29k_avatar_drag_drop.md
pyproject.toml                                    (0.14.120 → 0.14.121)
```

零後端 / 零 service / 零 Python tests 改動。

## 6. 教訓 / 共通性

- **多入口共用 single execution path**：file input + drag-drop 兩個 trigger，validation + upload + UI 流程寫一次（`_handleSelectedFile`）。**通用原則**：找到「不論 input source 都該走同一步」的點，往那裡 collapse。
- **Client validation 必須 mirror server，不嚴格不寬鬆**：規則 drift = user 困惑。同 source of truth。**通用原則**：先寫 server 規則，client 走 mirror。
- **Pure validator export 給 Node test**：跟 r29f hash.mjs / r29h toast.mjs / r29j _initialsSpec 同 testability pattern。**通用原則**：side-effect-free logic 全抽 export。
- **`dragover` preventDefault 是 drop 觸發 prerequisite**：少這行 drop 永不觸發，新手最常踩坑。**通用原則**：drop zone preventDefault dragover/drop 兩 events。
- **保留 button fallback 是無障礙基本盤**：touch device 沒 drag-drop，全靠 drop = 排除手機 user。**通用原則**：alternative input methods 並存，不互斥。
- **CSS 三件套 visual feedback**：border + scale + label 多重 cue 對「進入特殊狀態」是強訊號設計（同 r29g `.gl-card--deeplink`）。**通用原則**：UI 強度跟動作重要性對齊。
- **charset 後綴 split(';')[0] 防御**：`image/png; charset=binary` 邊界 case 讀過 spec 才知道 — 是 mirror server 的 `service.py` 處理（`(content_type or "").lower().split(";")[0].strip()`）。**通用原則**：規則 mirror 時連 edge case 也 mirror。

## 7. r28-r29k 系列累計統計

| Phase | 重點 | Tests | 版本 |
|---|---|---|---|
| r28-r29j（前 14 phase） | 略 | Python +98 / Node +46 | ... → 0.14.120 |
| **r29k** | **avatar drag-drop + client validation** | **Node +9** | **0.14.121** |

**Two-day total: Python 320 + Node 55 = 375 tests, +15 phases, 15 versions, 15 decision logs.**

Avatar UX 閉環：上傳（button + drag-drop）+ instant client validation + initials fallback + 跨 view 顯示 + cache-bust。

## 8. Defer 留給後續

| 待做 | Phase |
|---|---|
| Client-side image preview before upload (FileReader → ObjectURL) | nice-to-have，目前 immediate upload 體驗其實 OK |
| 上傳 progress bar | 256x256 PNG ~30-80KB，太快不需要 |
| Multi-file drop（誤拖多檔）→ 用第一張 | 已實際行為（dataTransfer.files[0]）|
| Crop / rotate UI | 視 user 反饋 |
| Phase 6: Follow / 跟隨 user → 個人化 feed | 真社群 loop |
| Featured / curated picks（admin role） | phase 5c 真版本 |
