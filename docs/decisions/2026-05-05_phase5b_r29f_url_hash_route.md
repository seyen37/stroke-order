# Phase 5b r29f：URL Hash Route（profile 可分享 / reload 保留 state）

**日期**：2026-05-05
**版本**：0.14.115 → 0.14.116
**範圍**：URL `#user=42&sort=likes&q=曼陀羅&kind=mandala` 雙向同步 state；解 reload 失憶 + 鋪 deep-link 基礎建設
**測試**：`tests/test_hash_route.mjs` 23 Node 單元 + 5 manual E2E checklist；Python 307 不退化

---

## 1. 動機

r29d/r29e 完成 profile feature 後三條痛：

1. **Reload 失憶**：user 進 Alice profile → 重整頁面 → `state.userFilter` 重置，回全 gallery，且看不出剛才在哪
2. **無法分享**：想把 Alice profile 連結傳給朋友 → 沒網址可貼
3. **無 deep-link 基礎建設**：未來 phase 5c 想做「分享某張 upload」、「分享某 search 結果」、tag pages 都要 hash route 撐底

r29f 一次解三條：state 雙向綁 `location.hash`，reload + 直訪都能還原 view，並開出未來 deep-link 通道。

## 2. 設計核心

### 2.1 Hash 編碼：`URLSearchParams` 風格

**選擇**：`#key=val&key2=val2`，用瀏覽器內建 `URLSearchParams` 解析。

**避開**：path-style（`#/user/42/sort/likes` — 自家 router）、JSON-encoded（醜 + escape 麻煩）。

**收益**：
- 0 自家 parser，瀏覽器 + Node `URLSearchParams` 同 API
- Encoded chars (`%E6...`) 自動處理
- 跟 server query string 同符號 user 直覺
- Round-trip 穩定（特殊字元 `& = #` 跟非 ASCII 都安全 — 已測）

### 2.2 Whitelist：哪些 state 進 hash

| State | 進 hash？ | 理由 |
|---|---|---|
| `userFilter` | ✅ | profile 連結要分享 |
| `sort` | ✅ (非 newest 才寫) | sort=likes / hot 改變看到的內容 |
| `q` | ✅ | search 結果要分享 |
| `kindFilter` | ✅ | filter 過的 view 要分享 |
| `bookmarkedOnly` | ❌ | **私人 view，不該洩漏 / 分享** |
| `page` | ❌ | ephemeral，分享連結帶 page=3 體驗差 |
| `me` / `items` / `total` / `profile` | ❌ | derived data，不是 user intent |

**Canonical form**：`sort='newest'` 跟空 `q` / 空 `kindFilter` 全部不寫進 hash → empty state ↔ empty hash 雙向 deterministic。

### 2.3 Pure helpers 抽到 `hash.mjs`：browser + Node 共用

**選擇**：`stateToHash` / `parseHash` / `emptyPatch` 三個 pure functions 拆到 `gallery/hash.mjs`，無 DOM dependency。

**收益**：
- Browser side：`gallery.js` 用 `import { stateToHash, parseHash } from './hash.mjs'`
- Node side：`tests/test_hash_route.mjs` 用 `node --test` 跑 23 unit 直接 import 同一份原始檔
- **不重複實作 = 不會 drift**

**`.mjs` 不 `.js` 因**：repo 沒 `package.json` → Node 預設 `.js` = CommonJS 不能用 ESM `import/export`。`.mjs` 強制 ESM 同時 browser 也吃（FastAPI MIME 為 `text/javascript`）。

### 2.4 Sync 時機：`refresh()` 入口集中

**選擇**：`_writeHash()` 在 `refresh()` 第一行 call。所有 state-mutation handler 既有路徑都已 chain `refresh()`，零修改其他 handler。

**避開**：每個 handler 各自 `_writeHash()`（容易漏）、Proxy 自動偵測（overengineering）。

**單一規則**：state 變了 + 要重新 render → 同步 hash。漏掉就漏 refresh，行為 deterministic。

### 2.5 防 hashchange 自家觸發 loop

**問題**：`_writeHash()` 改 `location.hash` → 觸發 `hashchange` 事件 → handler 又重 fetch → 無限 loop。

**選擇**：`_writingHash` boolean flag + `setTimeout(0)` reset。

```javascript
function _writeHash() {
  // ...
  _writingHash = true;
  // 改 hash
  setTimeout(() => { _writingHash = false; }, 0);
}

function _onHashChange() {
  if (_writingHash) return;  // 自家觸發 — 略過
  // 處理外部來源
}
```

**為什麼 setTimeout(0) 而非 microtask**：`hashchange` 是 macrotask；microtask 會在 hashchange dispatch 之前 reset flag → 失效。setTimeout(0) 排在 hashchange handler **之後**，flag 在 handler 期間仍是 true → 正確 skip。

### 2.6 清空 hash 用 `replaceState` 留乾淨 URL

**選擇**：`userFilter` 清掉時，target hash = '' → 用 `history.replaceState(null, '', cleanUrl)` 清掉整個 hash 段（包括 trailing `#`）。

**避開** `location.hash = ''`（仍留 trailing `#` 在 URL bar，醜）。

`replaceState` 不觸發 hashchange，跟 flag 雙保險。

### 2.7 Init 流程：parse hash → sync UI → first refresh

```javascript
(async function boot() {
  attachAuthHandlers({ refresh });
  attachUploaderHandlers({ refresh });
  _wireToolbar();
  // r29f: 讀 hash → 套進 state（在 first refresh 之前）
  _applyHashPatchToState(parseHash(window.location.hash));
  _syncUiFromState();   // sort dropdown / search input / filter tabs
  window.addEventListener('hashchange', _onHashChange);
  await refresh();       // 用 patched state 並行 fetch profile + list
})();
```

**並行 fetch**：r29d `refresh()` 已支援 `state.userFilter` set 時自動 push `_fetchUserProfile` 進 `Promise.all`。所以 deep-link 進入 `#user=42` 時，profile 跟 list 同時開始 fetch — 0 額外工程，零 round-trip 浪費。

### 2.8 防注入：parseHash 嚴格 whitelist

```javascript
// user → positive integer only
if (Number.isInteger(n) && n > 0) out.userFilter = n;
// sort → ['newest','likes','hot'] whitelist
// kind → ['psd','mandala'] whitelist
// q → 截到 100 chars（server `MAX_SEARCH_QUERY_LEN` 對齊）
```

惡意 hash 如 `#user=DROP_TABLE&sort=evil&kind=javascript` → 全 fallback default → 安全。已測 `parseHash` 對非法輸入皆走 fallback。

## 3. 實作

### 3.1 新檔：`hash.mjs`（45 lines pure helpers）

`stateToHash(s)` / `parseHash(hash)` / `emptyPatch()` — 上面 §2.2-§2.8 細節。Whitelist + canonical form + 防注入全在 pure function 層級確保。

### 3.2 `gallery.js` 異動

| 區塊 | 變更 |
|---|---|
| imports | 加 `import { stateToHash, parseHash } from './hash.mjs'` |
| 新 section `hash route` | 加 `_writingHash` flag + `_writeHash` + `_applyHashPatchToState` + `_syncUiFromState` + `_onHashChange` |
| `refresh()` 第一行 | 加 `_writeHash()`（state→hash 同步） |
| `boot()` | 加 parse hash → apply → sync UI → addListener — 順序在 first refresh 之前 |

零修改：所有 mutation handlers（filter-user link、sort dropdown、search input、bookmark/kind tabs、profile-back）— 全已 chain `refresh()`，自動受益。

### 3.3 Server 零變動

純 frontend feature，FastAPI / SQLite schema / API endpoint 無動。

## 4. 測試

### 4.1 Node `node:test` 23 unit（tests/test_hash_route.mjs）

| 範疇 | Test 數 |
|---|---|
| `stateToHash` | 10（empty / 各欄位單一 / 中文 encode / 多欄位 / `bookmarkedOnly + page` 排除 / invalid sort/kind/userFilter fallback） |
| `parseHash` | 10（empty / 中文 decode / leading-# / 多欄位 / 防注入 user/sort/kind / q 過長截斷 / 未知 key ignore） |
| Round-trip | 3（一般 / empty / 特殊字元 `& = #`） |

執行：`node --test tests/test_hash_route.mjs` → **23 pass**（Node v22.22.0）。

### 4.2 Manual E2E checklist（PR 描述列）

| # | 場景 | 預期 |
|---|---|---|
| 1 | 全 gallery → 點 Alice 名 | URL 變 `#user=42`；banner / strip 出現 |
| 2 | 在 profile view 切 sort=likes | URL 變 `#user=42&sort=likes` |
| 3 | 在 profile view 搜 "曼陀羅" | URL 變 `#user=42&sort=likes&q=%E6%9B%BC...` |
| 4 | 直接打 `https://.../gallery#user=42&sort=likes` 進入 | banner 顯 Alice、list 走 sort=likes、sort dropdown UI 反映 |
| 5 | 點「← 返回全部」 | URL 清成 `https://.../gallery`（無 #） |

### 4.3 Python regression：307 不退化

所有 r28-r29e 測試：`pytest -q tests/test_gallery_*.py tests/test_mandala*.py tests/test_web_*.py tests/test_wordart.py` → **307 pass**。

## 5. 涉及檔案

```
src/stroke_order/web/static/gallery/hash.mjs         (新 — 45 行 pure helpers)
src/stroke_order/web/static/gallery/gallery.js       (import + hash section + boot init)
tests/test_hash_route.mjs                             (新 — 23 Node unit)
docs/decisions/2026-05-05_phase5b_r29f_url_hash_route.md
pyproject.toml                                        (0.14.115 → 0.14.116)
```

API endpoint 跟 service 層零動。

## 6. 教訓 / 共通性

- **Pure helpers 拆檔 = browser + Node 共測**：`hash.mjs` 兩邊吃同份原始碼，避免重複實作 drift。`.mjs` 強制 ESM 跨環境一致。**設計訊號**：純 logic 無 DOM/IO 依賴 → 拆檔換來零成本可測性。
- **Sync 時機集中在 mutation 入口**：`_writeHash()` 在 `refresh()` 第一行，跟「state 變 → render」綁同節奏。每個 handler 各自寫 hash = 漏點源頭。**規則**：跟 render 同步的 side-effect → 集中到 render 入口。
- **`setTimeout(0)` vs `Promise.resolve().then`**：差在 macrotask vs microtask。`hashchange` 是 macrotask → microtask 在它**之前**觸發 reset → 失效。挑時序工具要看「target event 排哪一隊」。**通用原則**：跨事件 timing 要 setTimeout / queueMicrotask 別猜，read spec。
- **`replaceState` 留乾淨 URL**：`location.hash = ''` 留 trailing `#`，視覺髒。`history.replaceState(null, '', cleanUrl)` 完整清掉 hash 段又不觸發 hashchange — 雙保險。
- **Whitelist > blacklist 防注入**：`parseHash` 對 `sort` / `kind` 用 `if (whitelist.includes(v))`，對 `userFilter` 用 `Number.isInteger(n) && n > 0`，惡意值全走 fallback default。**通用原則**：user-controlled 字串進 enum 欄位前必經 whitelist。
- **`bookmarkedOnly` 不進 hash 是隱私決定**：書籤是個人私密 view，分享連結帶 `bookmarked=1` 會暴露行為。**通用原則**：URL 是公開介面，state 進 URL 前先問「分享出去 OK 嗎」。
- **Refresh 重 fetch 邏輯零改**：r29d 的並行 fetch 設計（has userFilter → 同時 push profile request 進 `Promise.all`）讓 deep-link 進入時 0 額外工程就達 minimal latency。**設計訊號**：「parallel fetch 結構提前準備」帶來後續 phase 免費紅利。

## 7. r28-r29f 系列累計統計

| Phase | 重點 | Tests | 版本 |
|---|---|---|---|
| r28 | gallery 接 mandala upload | +20 | 0.14.107 |
| r28b | SVG thumbnail | +6 | 0.14.108 |
| r28c | MD thumbnail (loader DI) | +4 | 0.14.109 |
| r28d | state-aware loader factory | +3 | 0.14.110 |
| r29 | like 機制 | +16 | 0.14.111 |
| r29b | bookmark + sort by likes | +17 | 0.14.112 |
| r29c | hot ranking + search | +12 | 0.14.113 |
| r29d | user profile + user_id filter | +7 | 0.14.114 |
| r29e | profile top uploads strip | +5 | 0.14.115 |
| **r29f** | **URL hash route** | **+23 Node** | **0.14.116** |

**Two-day total: +113 tests (Python 307 + Node 23 = 330 total), +10 phases, 10 versions, 10 decision logs.**

Gallery 完整社群 + deep-link 雙跨：multi-kind upload + thumbnail + like + bookmark + sort × 3 + search + filter × 4 + user profile + 代表作 showcase + 可分享 / reload-safe URL。

## 8. Defer 留給後續

| 待做 | Phase |
|---|---|
| 單張 upload deep-link（`#upload=123`） | phase 5c — hash route 已撐底，加一個 key 即可 |
| Profile 編輯 UI（user 改 bio / display_name） | phase 5c |
| Profile avatar 頭像上傳 | phase 5c+ |
| Featured / curated picks（admin role） | phase 5c |
| Follow / 跟隨 user → 個人化 feed | phase 6 |
| FTS5 + 中文分詞 advanced search | 待 user 反饋 |
| `pushState` 取代 `location.hash`（pretty URL `/users/42` 而非 `#user=42`） | 視 SEO / 分享美觀需求 |
