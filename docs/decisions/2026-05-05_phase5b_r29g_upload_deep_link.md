# Phase 5b r29g：Upload Deep-link（單張作品可分享連結）

**日期**：2026-05-05
**版本**：0.14.116 → 0.14.117
**範圍**：r29f hash route 延伸 — 新增 `#upload=123` deep-link，把該 upload prepend 到 list[0] + accent border + flash 4s
**測試**：`tests/test_hash_route.mjs` +6 (29 累計，3 既有 update + 3 新) → Node 29 / Python 307 不退化

---

## 1. 動機

r29f ship URL hash route 後，user 可分享 profile 連結（`#user=42`）但**單張作品不能分享**。「我覺得這張曼陀羅畫得好，想傳給朋友看」沒有對應 URL。

r29g 補完：`https://.../gallery#upload=123` 進入 → 那張被 prepend 到 list 第一位 + 顯眼 accent border + auto scroll-to-card + 4 秒 flash。是 r29f deep-link 機制的自然延伸。

## 2. 設計核心

### 2.1 不開新 detail page，用 prepend + 強調樣式

**選擇**：fetch `/api/gallery/uploads/{id}` (r29 既有 endpoint) → prepend 到 `state.items[0]` + dedup → render with `.gl-card--deeplink` class。

**避開**：modal lightbox（~300 行 + focus trap + scroll lock + back-button 同步），新 detail page。

**理由**：
- Card 已含 title / kind / author / comment / time / thumbnail / like / bookmark / download — 90% detail view 該有的資訊
- Modal 只多「比較大」這個維度 → 用 CSS scale + accent border + larger thumb 即可達到「強調」訊號
- 零後端 endpoint 變更（r29f 起延續純 frontend feature）

### 2.2 Deep-link 載入時清 sort/q/filter 到 default

**選擇**：`_applyHashPatchToState` 看到 `patch.deepLinkUploadId` → 強制 reset `userFilter / sort / q / kindFilter / bookmarkedOnly` 到 default + page=1。

**理由**：deep-link 訪客通常「**新鮮進來**」沒既有 view 偏好。清 filter 確保 list 乾淨 + prepend 那張在最頂 = deterministic 體驗。User 想瀏覽其他作品自己再切。避開「分享連結 + filter 衝突 → 看不到」的混淆。

### 2.3 Hash schema：`#upload=123` (whitelist 加 1 key)

**選擇**：跟 r29f 同 URLSearchParams pattern，加 `upload` key（positive integer）。State 端對應 `state.deepLinkUploadId`。

```
#user=42&sort=likes&q=曼陀羅&kind=mandala&upload=123
```

順序：user → sort → q → kind → upload（跟 set 順序一致，保 canonical）。

**State naming**：`deepLinkUploadId` 而非 `upload` — `state.upload` 模糊（單張上傳？上傳動作？），加 `deepLink` 前綴清楚是 deep-link 指向。

### 2.4 Highlight 4 秒自動清 + hash 留

**選擇**：deep-link fetch 完成後 `setTimeout(() => { state.deepLinkUpload = null; state.deepLinkUploadId = null; _writeHash(); renderList(); }, 4000)`。

**設計取捨**：
- **4 秒清 state**：highlight 時間夠看清「就是這張」，之後回普通 list
- **不清 hash**：reload 仍能重 trigger（分享連結 reload-safe 是 r29f 的核心承諾）
- 等等，這跟「`_writeHash()` 同步移除 `upload`」是矛盾的——

**修正設計**：4 秒後**只清 state**，**不調 `_writeHash`**，hash 保留。下次 user 操作其他 view 變動觸發 refresh → `_writeHash()` 跑時 `state.deepLinkUploadId` 已是 null → hash 自動清。最終結果：highlight 4 秒消失，hash 在 user 下次主動操作 view 時清。Reload 仍 deep-link work。

實作：

```javascript
setTimeout(() => {
  state.deepLinkUpload = null;
  state.deepLinkUploadId = null;
  _writeHash();    // 主動清 hash（避免 user 不操作時 URL bar 仍有 #upload=N）
  renderList();
}, 4000);
```

**最終決定保留 `_writeHash()`**：4 秒後主動清 hash，URL bar 變乾淨。Reload 失去 deep-link 是合理 trade-off — user 4 秒已看到內容，需要再分享應再點分享連結。

### 2.5 Prepend 而非 splice，dedup 防重複

```javascript
if (state.deepLinkUpload) {
  const dlId = state.deepLinkUpload.id;
  state.items = state.items.filter(it => it.id !== dlId);  // dedup
  state.items.unshift(state.deepLinkUpload);
}
```

如果 deep-link upload 本來就在 page 1（newest sort 下新作品），filter 先把原版移除，再 unshift → 確保只出現一次且在最頂。

### 2.6 並行 fetch：deep-link upload 跟 list 同時打

`refresh()` 把 `_fetchUploadDetail(state.deepLinkUploadId)` push 進 `Promise.all`，跟既有 `fetchMe + _fetchUploads`（+ optional `_fetchUserProfile`）平行。

零額外 round-trip 等待時間。

### 2.7 條件 fetch：避免重複下載

```javascript
const dlFetchIdx = (state.deepLinkUploadId
                    && (!state.deepLinkUpload
                        || state.deepLinkUpload.id !== state.deepLinkUploadId))
  ? fetches.push(_fetchUploadDetail(...)) - 1
  : -1;
```

只在「有 id 但還沒 fetch 過」或「id 換了」時 fetch。中間 user 切 sort/q/filter → refresh 重跑時不會無謂打 detail endpoint。

### 2.8 找不到 silently ignore

**選擇**：`_fetchUploadDetail` 回 null 時 `console.warn` + 不 prepend。Hash 保留方便 dev/分享者 debug。

**避開** toast 元件（gallery 沒既有 toast），404 redirect（overkill — 整 gallery 仍 work）。

實際上 user 看到普通 list 也猜得到「分享的東西沒了」。後續真有 user 反饋再加 toast。

### 2.9 CSS 視覺強化：accent border + scale + flash + 標籤

```css
.gl-card--deeplink {
  outline: 3px solid var(--gl-accent, #46a);
  outline-offset: 3px;
  transform: scale(1.02);
  box-shadow: 0 4px 18px rgba(70, 102, 170, 0.25);
  animation: gl-card-deeplink-flash 4s ease;
}
.gl-card--deeplink::before {
  content: '🔗 分享連結指向';
  /* tag in top-left corner */
}
@keyframes gl-card-deeplink-flash {
  0%   { background-color: #fff3a8; }
  60%  { background-color: #fffae0; }
  100% { background-color: transparent; }
}
```

四種視覺 cue 疊加：
1. Accent outline（藍色框）
2. 1.02x scale + box-shadow（浮起來）
3. 標籤 `🔗 分享連結指向`（明確語意）
4. 4s 黃→淡黃→透明 flash（吸引注意）

跟 r29e `.gl-card--highlight` 不同 family — deep-link 比「strip click scroll」更強訊號。

### 2.10 `requestAnimationFrame` 包 scrollIntoView

```javascript
if (state.deepLinkUpload) {
  const dlCard = root.querySelector('.gl-card--deeplink');
  if (dlCard) {
    requestAnimationFrame(() => {
      dlCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }
}
```

`innerHTML = ...` 完之後 layout 還沒 settle；直接 `scrollIntoView` 偶爾算錯位置。`rAF` 等下一 frame layout 確定後再捲。

## 3. 實作

### 3.1 `hash.mjs`（純擴）

新欄位 `deepLinkUploadId`：
- `stateToHash`: `params.set('upload', String(s.deepLinkUploadId))` (positive integer guard)
- `parseHash`: 同樣 positive-integer-only
- `emptyPatch` 自動跟著（透過 parseHash('')）

向後相容：r29f 既有 4 keys 行為不變。新加 1 key。

### 3.2 `gallery.js` 主要異動

| 區塊 | 變更 |
|---|---|
| `state` | 加 `deepLinkUploadId` (id) + `deepLinkUpload` (full obj) |
| `_applyHashPatchToState` | 看到 `patch.deepLinkUploadId` → 清 sort/q/kind/user/bookmarked 到 default |
| `refresh()` | 並行 push `_fetchUploadDetail` (條件) + 後 prepend + dedup + setTimeout 清 |
| 新 `_fetchUploadDetail(uploadId)` | reuse 既有 `GET /api/gallery/uploads/{id}` |
| `_card()` | `state.deepLinkUpload?.id === item.id` → 加 `gl-card--deeplink` class |
| `renderList()` | render 完用 rAF + scrollIntoView 那張 card |

### 3.3 CSS（`gallery.css`）

加 `.gl-card--deeplink` 系列（outline + scale + shadow + ::before 標籤 + 4s flash keyframe）。

### 3.4 Server 零變動

純 frontend feature，service / API / DB schema 無動。

## 4. 測試

### 4.1 Node `node:test` (29 = 23 r29f + 3 update + 3 r29g)

| Test | 驗證 |
|---|---|
| `stateToHash: deepLinkUploadId=99` | 序列化單欄位 |
| `stateToHash: 跟 user/sort 並存` | canonical 順序 user→sort→q→kind→upload |
| `stateToHash: 0 / 負數 / 字串 不寫` | invalid 走 default |
| `parseHash: #upload=123` | 反序列化單欄位 |
| `parseHash: 惡意 upload=<script>` | whitelist 防注入 |
| `round-trip r29g: 全 5 欄位` | state ↔ hash 雙向 |

3 個既有 round-trip / parseHash 測試 update（shape 從 4-key → 5-key，加 `deepLinkUploadId: null`）。

### 4.2 Python regression：307 不退化

純 frontend feature，server / DB / service 零動。`pytest -q tests/test_gallery_*.py tests/test_mandala*.py tests/test_web_*.py tests/test_wordart.py` → **307 pass**。

### 4.3 Manual E2E checklist（PR 描述）

| # | 場景 | 預期 |
|---|---|---|
| 1 | 直訪 `https://.../gallery#upload=42` | upload 42 prepend 到 list 頂端、accent border、`🔗 分享連結指向` 標籤、auto scroll、4s 後 flash 漸消 |
| 2 | 既有 view 在 sort=likes + q="曼陀羅"，網址列改 `#upload=99` | filter/q 自動清，list reset 到 newest，upload 99 在頂 |
| 3 | 直訪 `#upload=99999` (不存在) | console.warn，list 正常顯示無 prepend、無 highlight |
| 4 | 直訪 `#upload=42` 後 4 秒 → 動 sort dropdown | hash 變成 `#sort=likes`（upload 已清） |
| 5 | reload `#upload=42` 仍 work | 重新 fetch、重新 prepend、重新 highlight 4s |

## 5. 涉及檔案

```
src/stroke_order/web/static/gallery/hash.mjs     (5 keys 從 4 keys 擴；+ deepLinkUploadId)
src/stroke_order/web/static/gallery/gallery.js   (state + _applyHashPatchToState + refresh + _card + renderList)
src/stroke_order/web/static/gallery/gallery.css  (.gl-card--deeplink 系)
tests/test_hash_route.mjs                         (3 既有 update + 6 新 r29g)
docs/decisions/2026-05-05_phase5b_r29g_upload_deep_link.md
pyproject.toml                                    (0.14.116 → 0.14.117)
```

API endpoint / service / DB / Python tests 零動。

## 6. 教訓 / 共通性

- **Reuse > new endpoint**：`_fetchUploadDetail` 直接 reuse `GET /api/gallery/uploads/{id}`（r29 既有），沒新 backend 工作。**通用原則**：deep-link target 通常已有 detail endpoint，直接拿。
- **Prepend + dedup 比「找頁碼」薄一個量級**：不需算 page，list 永遠 reset 到第一頁，prepend 那張一定在最頂。後端 zero work。**設計訊號**：能用 frontend list manipulation 達成的需求，別開後端 endpoint。
- **State naming：加前綴 disambiguate**：`state.upload` 太模糊（單張 upload？上傳動作？），`state.deepLinkUploadId` 即清楚指向 deep-link 用途。**通用原則**：state 欄位名要表達「為什麼存在」不只「是什麼」。
- **rAF 包 scrollIntoView**：`innerHTML = ...` 後 layout 未 settle，直接 scrollIntoView 偶爾錯位。`requestAnimationFrame` 等下 frame 才捲 = 穩定。**通用原則**：DOM mutation 後的 measure / scroll 操作 always 用 rAF 過一道。
- **4s timeout 主動清 hash 是 trade-off**：清 hash 換 URL bar 乾淨；reload 失 deep-link 是 cost。User 4 秒已看到 = 用一次的設計目的達成。重要：highlight 4s 跟 hash 清同步發生 — `_writeHash()` 跟 `state.deepLinkUploadId = null` 在同 setTimeout callback 一致。
- **CSS 訊號疊加**：accent outline + scale + shadow + 標籤 + flash 五重 cue 對 deep-link card，跟 r29e single-flash highlight 不同 family — 清楚分別「點擊跳到」（瞬時）vs「分享連結指向」（持續強調）。**通用原則**：UI 強度跟訊號重要性對齊，不要 single-style 通吃。
- **Deep-link 進入時清 filter 是 deterministic 設計**：避免「分享連結 + 收件人既有 filter 衝突 → 看不到」的隱性 bug。簡化規則 > 智慧推測（C 選項就是過度智慧）。**通用原則**：跨 user view 的 link → 進入時 reset 到 deterministic state。

## 7. r28-r29g 系列累計統計

| Phase | 重點 | Tests | 版本 |
|---|---|---|---|
| r28-r29f（前 10 phase） | 略 | Python +85 / Node +23 | ... → 0.14.116 |
| **r29g** | **upload deep-link** | **Node +6** (29 累計) | **0.14.117** |

**Two-day total: Python 307 + Node 29 = 336 tests, +11 phases, 11 versions, 11 decision logs.**

Gallery deep-link 完整覆蓋 user profile + 單張作品兩種粒度 — 任何 view 都可分享、reload-safe（最後 4s 內）。

## 8. Defer 留給後續

| 待做 | Phase |
|---|---|
| Toast 元件 — upload 不存在時友善提示 | 視 user 反饋 |
| Modal lightbox（fullscreen 大圖 + 留言區） | phase 5c+ 視需求 |
| Profile 編輯 UI（user 改 bio / display_name） | phase 5c |
| Profile avatar 頭像上傳 | phase 5c+ |
| `pushState` 取代 hash（pretty URL `/uploads/123`） | 視 SEO / 美觀 |
| Featured / curated picks（admin role） | phase 5c |
| Follow / 跟隨 user → 個人化 feed | phase 6 |
