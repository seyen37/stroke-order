# 共通性原則（Cross-cutting Engineering Principles）

兩日 r28–r29k 15 個 phase 累積出的 senior-level 工程習慣彙整。每條原則一個段落 + 適用場景 + 反例 + 出處 phase。

---

## 1. 規劃 / 流程

### 1.1 Reconnaissance 在 phase plan 之前

開新 phase 前 **grep 既有 implementation**。`grep -n "function_name\|endpoint\|table" <relevant_dirs>` 一句指令 + 5 分鐘讀，能避免：
- 重做輪子（功能其實已 ship）
- 誤判 scope（你想的「從零做」其實是「補一個 button」）
- 跟既有設計衝突

**反例**：r29i 原本當「phase 5c profile 編輯」開動，recon 才發現 9/9 元件早已實作 → scope 立刻縮成 banner ✏️ 快捷。

**出處**：r29i

---

### 1.2 5-Q 架構 ceremony 對非 trivial 改動

任何 ≥3 步 + 含設計取捨的改動，先列 5–7 個架構 Q & A，每個標 ★ 推薦並寫 reasoning。等 user 確認再動工。

**收益**：
- 明示思考脈絡，user 可挑特定 Q 改方向
- 避免「悶頭做出 user 不要的東西」
- 跟 user 對齊優先順序

**反例**：r29k drag-drop 是 trivial polish (~80 行)，4-Q 即可不需 5-Q。Trivial 還上 ceremony 是浪費時間。

**判斷標準**：「能不能 5 分鐘內口頭講完」？能 → 跳 ceremony；不能 → 5-Q。

**出處**：跨多 phase

---

### 1.3 誠實 push back > 悶頭做

評估錯了就承認，重新 scope。User 一句「OK」會誘惑你 ship anything；senior 該做的是「先停一下講真話」。

**例**：r29g 「upload deep-link」原計劃 modal lightbox，評估後改 card-expand（modal 工程量翻倍但價值只多 10%）。r29i 直接停 phase 5c，重新評估發現 90% 已 ship。

**反例**：硬把 r29i 偽裝成 phase 5c → 用 lipstick on a pig 充版本。

**出處**：r29g, r29i

---

### 1.4 Per-phase 一致節奏 — 規劃 → 確認 → 實作 → 驗證 → bump → log → commit

兩日 15 phases 全走同節奏：

1. **規劃**：5-Q（or skip if trivial）
2. **確認**：「全 ★ OK」or 挑 Q 改向
3. **實作**：批次 edit + smoke test
4. **驗證**：Node + Python 全跑 + manual E2E checklist
5. **Bump version + decision log**：版本 patch +1 + `docs/decisions/<date>_*.md`
6. **Commit**：rebuild git index → batched add → conventional message
7. **User push**（sandbox 沒 SSH）

可重複的節奏 = 工作 cadence，不需每次重新發明流程。

**出處**：跨 15 phases

---

## 2. 設計 / 架構

### 2.1 By-kind dispatch dict 取代 if/elif 鏈

```python
VALIDATORS = {KIND_PSD: parse_and_validate_psd,
              KIND_MANDALA: parse_and_validate_mandala}
```

加新 kind 改一個 dict + 寫對應 function，核心邏輯不動。Fail loud（KeyError）+ per-kind unit test 容易。

**反例**：`if kind == "psd": ... elif kind == "mandala": ...` — 加新 kind 要動每個 if/elif，散點 maintenance。

**已 memory**：`feedback_by_kind_dispatch_dict.md`

**出處**：r28

---

### 2.2 Schema dual-write 漸進遷移

加新通用欄位（如 `summary_json`）時 legacy 欄位（如 `trace_count`）**繼續寫**，給後續 phase 慢慢遷移。新 row 同時填新舊欄位，read 路徑漸進改用新欄位。Big-bang 切換 = rollback 困難 + dual-deploy 不可能。

**已 memory**：`feedback_schema_dual_write_migration.md`

**出處**：r28

---

### 2.3 Fetch frequency 一致 → 同 endpoint；不一致 → 拆

| 場景 | 結果 |
|---|---|
| Profile + top_uploads（user 切 profile 時兩者都要 fetch） | **同 endpoint forward**（r29e） |
| Profile + uploads list（profile 不變，list 隨翻頁/sort 動） | **拆兩 endpoint**（r29d） |

**通用規則**：「**fetch frequency 一致 → 併**；**不一致 → 拆**」是 API 設計訊號的兩面。併在一起每次 high-frequency fetch 都重抓 low-frequency 資料 = 浪費 round-trip。拆開 low-frequency 變化時 client 要 sync 兩 fetch 反而麻煩。

**出處**：r29d, r29e

---

### 2.4 集中 fetch 在 single function 帶來後續 phase 紅利

```javascript
async function refresh() {
  _writeHash();
  const fetches = [fetchMe(), _fetchUploads()];
  if (state.userFilter) fetches.push(...);
  if (state.deepLinkUploadId) fetches.push(...);
  const results = await Promise.all(fetches);
  // 集中 render
}
```

r29d 寫 refresh 時把 fetch 集中起來，r29f 加 hash deeplink、r29g 加 upload deeplink、r29i 編輯 profile 後 banner re-render — **都享免費紅利**，不需各自寫 fetch + render coordination。

**通用原則**：「跟 render 同步的 side-effect 集中到 render 入口」— 寫一次規則，後續 phase 自動受益。

**出處**：r29d, r29f, r29g, r29i

---

### 2.5 Cross-cutting derivation 集中到 helper

5 個 SELECT path 都要派生 `avatar_url` from `avatar_path` nonce → 抽 `_user_dict_with_avatar(row)` 助手，全走同一函式。

**反例**：每個 SELECT path 各自 derive `avatar_url` → 5 個漏改點，加 cache-bust 規則時要找全 5 處。

**通用原則**：跨多個 query / endpoint 的 transformation logic 集中到一個 helper。

**出處**：r29j

---

### 2.6 DB column 應存「unique fact」不存「derivable」

`avatar_path` column 名是歷史，**內容是 8-char hex nonce 不是路徑**。檔案路徑 `avatars/<user_id>.png` 可由 user_id 算出 → DB 不該重複存。

**通用原則**：可 derive 的資訊不該 store；DB column 該存「versioned identity」、「user intent」、「timestamp」這類本質事實。

**出處**：r29j

---

### 2.7 Versioned URL > ETag 對 cache-bust

`/api/users/42/avatar?v=<nonce>` + `Cache-Control: public, max-age=86400, immutable` = client 換頭像時 URL 換 → 新 fetch；舊 URL 永遠 cached 舊內容（immutable 表示不該 revalidate）。**0 round-trip 即 cache-bust**。

**反例**：ETag/Last-Modified 仍要 conditional GET round-trip 確認；URL stable 但 client 不知該 invalidate。

**通用原則**：可變資源用 versioned URL（讓「換內容」= 「換 URL」）。

**出處**：r29j

---

### 2.8 Multi-source single execution path

File input change + drag-drop drop 兩入口都走 `_handleSelectedFile(file)`：validation + upload + UI flow 寫一次。

**反例**：兩套 logic 各自 implement → drift（drag-drop 漏驗證 / file input 漏 status update）。

**通用原則**：找到「不論 input source 都該走同一步」的點，往那裡 collapse。

**出處**：r29k

---

### 2.9 Client validation 必 mirror server，不嚴不寬

```javascript
const ALLOWED_AVATAR_TYPES = ['image/png', 'image/jpeg'];
export const AVATAR_MAX_SIZE_BYTES = 2 * 1024 * 1024;
```

直接 mirror server `service.py` 的常數。Client 嚴於 server → user 困惑「明明合法 file」；client 寬於 server → user 上傳完才看到 422。

**通用原則**：先寫 server 規則，client 走 mirror。Single source of truth = 同一份 spec 兩種 enforce。

**邊界 case**：含 charset 後綴（`image/png; charset=binary`）— `split(';')[0].trim()` 預處理在兩端都做。

**出處**：r29k

---

### 2.10 Whitelist > blacklist 防注入

```javascript
if (Number.isInteger(n) && n > 0) out.userFilter = n;        // user int
if (sort && ['newest','likes','hot'].includes(sort)) out.sort = sort;  // enum
```

惡意 hash `#user=DROP_TABLE&sort=evil` → 全 fallback default。

**反例**：`if (sort !== 'evil') ...` 黑名單 — 永遠少考慮一種攻擊。

**通用原則**：user-controlled 字串進 enum / int 欄位前 **必經 whitelist**，invalid → fallback default。

**出處**：r29f, r29g

---

## 3. UI / UX

### 3.1 Empty state 是 affordance hint，不是該藏的 placeholder

空 bio 不要 hide 整個 div — 顯 italic「（尚未填寫個人簡介）」+ opacity 0.7。看自己 = 引導「該填了」；看別人 = 比 banner 中間少一行平衡。

無 avatar 不要 generic 灰色 icon — 顯 initials circle + hash 顏色。「有 visual identity」勝過「沒 feature」感受。

**通用原則**：empty state 是創造價值機會，不是該藏的瑕疵。

**出處**：r29i, r29j

---

### 3.2 CSS 多重 cue 對重要狀態變更

`.gl-card--deeplink`（r29g）：accent outline + 1.02x scale + box-shadow + ::before 標籤 + 4s flash keyframe = 5 重視覺 cue。
`.gl-profile-avatar-preview.is-dragover`（r29k）：accent box-shadow + 1.05x scale + ::after「✚ 放開上傳」label = 3 重 cue。

**反例**：single-style（只 background 變色）— 訊號太弱 user 看不到。

**通用原則**：UI 強度跟動作重要性對齊；重要 / 短暫狀態用多重 cue 強化。

**出處**：r29g, r29h, r29k

---

### 3.3 Alternative input methods 並存（不互斥）

Drag-drop 加進來但 file input button **保留** — touch device（手機 / 平板）沒 drag 概念，screen reader 也不適合 drag。

**通用原則**：accessibility baseline = 多種 input 方式並存。Power-user shortcut 不該排除 majority。

**出處**：r29k

---

### 3.4 `aria-live="polite"` + role 區分 是 ephemeral notification a11y baseline

Toast container 加 `aria-live="polite"` + `aria-atomic="true"`，error 用 `role="alert"`，info/warning 用 `role="status"`。

**通用原則**：所有 ephemeral notification（toast / snackbar / banner）必標 aria-live；緊急程度用 role 區分。

**出處**：r29h

---

### 3.5 用 `textContent` 賦值，不 `innerHTML`（除非真要 markup）

```javascript
msgSpan.textContent = spec.message;  // 自動 escape
// 不要 msgSpan.innerHTML = spec.message — XSS 風險
```

Toast 訊息 90% 來自 server error，可能含特殊符；textContent 自動轉純文字，spec 不需 manual escape。

**反例**：`innerHTML = "<script>alert(1)</script>"` 會執行。

**通用原則**：display 純文字用 textContent；需要 markup 才 innerHTML + 手動 escape。

**出處**：r29h, r29j

---

### 3.6 `requestAnimationFrame` 包 post-mutation scrollIntoView / measure

```javascript
root.innerHTML = cards;
if (state.deepLinkUpload) {
  requestAnimationFrame(() => {
    dlCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
}
```

`innerHTML = ...` 完之後 layout 還沒 settle，直接 scrollIntoView 偶爾算錯位置。`rAF` 等下一 frame layout 確定後再捲。

**通用原則**：DOM mutation 後的 measure / scroll 操作必經 `requestAnimationFrame` 過一道。

**出處**：r29g

---

### 3.7 4 種關閉方式 + auto timeout 對 ephemeral UI

Toast：click body / click X / press ESC / 5s auto-timeout = 4 種關法覆蓋 keyboard / mouse / passive wait 三類 user。

**通用原則**：ephemeral UI 給 user 主動結束 + 預設 timeout 兜底。

**出處**：r29h

---

## 4. 測試 / 驗證

### 4.1 Pure logic 抽 export 給 Node test

DOM-coupled module 中的 input validation logic 抽 pure function：
- `hash.mjs` `stateToHash` / `parseHash` (r29f) — 23 tests
- `toast.mjs` `_toastSpec` (r29h) — 9 tests
- `avatar.mjs` `_initialsSpec` (r29j) — 8 tests
- `avatar.mjs` `validateAvatarFile` (r29k) — 9 tests

DOM 操作走 manual E2E。**通用原則**：side-effect-free logic 全抽 export 給 unit cover。

**出處**：r29f, r29h, r29j, r29k

---

### 4.2 `.mjs` 強制 ESM 跨 browser/Node

Repo 沒 `package.json` 設 `"type": "module"`，`.js` 在 Node 預設是 CommonJS — `import/export` 不能用。`.mjs` 強制 ESM，browser 也吃（`text/javascript` MIME 沒問題）。

**通用原則**：跨環境共用 pure module 用 `.mjs`，避免依賴 package.json 設定。

**出處**：r29f

---

### 4.3 Smoke regression 跑全 test suite

每 phase 結束跑 Node + Python 全 suite，不只 affected file。漏測點 = 後續 phase 才爆 = debug 成本翻倍。

**反例**：「我只改 service.py 不需要跑 web tests」— `_user_dict_with_avatar` 改了 row shape，list_uploads 也踩到。

**出處**：跨多 phase

---

### 4.4 Manual E2E checklist 補 test 蓋不到的盲點

每個 frontend phase 列 3–6 條 manual E2E 場景：
- DOM mutation timing（scroll-to-card 是否真的滑進 view）
- 視覺 feedback（accent border 是否在 dragover 出現）
- Cross-tab / reload behavior（hash 是否還原 state）

push 給 user 跑，不靠 sandbox 自動化（Playwright 太重）。

**通用原則**：unit + integration test 蓋 logic，manual E2E 蓋「真瀏覽器才會發生的事」。

**出處**：r29f, r29g, r29j, r29k

---

## 5. 實作細節（容易踩坑）

### 5.1 `dragover.preventDefault()` 是 drop trigger prerequisite

```javascript
preview.addEventListener('dragover', (ev) => {
  ev.preventDefault();   // ← 沒這行 drop 永不觸發
  // ...
});
```

Browser 預設 dragover 行為「不接受 drop」，要 preventDefault 才會 fire drop。新手最常踩。

**出處**：r29k

---

### 5.2 `setTimeout(0)` vs Promise.resolve().then 跨事件 timing

`hashchange` 是 macrotask；`Promise.resolve().then` 是 microtask。微任務在 hashchange dispatch **之前**觸發 → flag reset 失效。`setTimeout(0)` 排在 hashchange handler 之後 → flag 在 handler 期間仍 true → 正確 skip。

**通用原則**：跨事件 timing 別猜，read spec 看 target event 排哪一隊。

**出處**：r29f

---

### 5.3 `Pillow.verify() + 重 open` 是 image upload security pattern

```python
Image.open(io.BytesIO(file_bytes)).verify()  # 檢查合法
img = Image.open(io.BytesIO(file_bytes))      # 重 open 才能 decode
```

`verify()` 是 single-pass 檢查會消耗 stream → 之後 `.size` / `.convert()` 會炸。先 verify 防 evil image bombs，再 open 處理。

**出處**：r29j

---

### 5.4 ALTER TABLE migration helper 模板

```python
def _migrate_<table>_<feature>(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(<table>)")}
    if "<col>" not in cols:
        conn.execute("ALTER TABLE <table> ADD COLUMN <col> TEXT")
```

SQLite ALTER TABLE 不支援 IF NOT EXISTS → 必經 PRAGMA 查。一個 table 一個函式，獨立 idempotent。

**已 memory**：`feedback_schema_versioning_with_migration.md`（相關但不完全同）

**出處**：r28（首例）、r29、r29b、r29j

---

### 5.5 CSS animation duration vs JS removeChild 多 20ms 緩衝

```javascript
toast.classList.add('is-leaving');  // 觸發 CSS 0.2s fade-out
setTimeout(() => removeChild(toast), 220);  // 多 20ms 等動畫完
```

CSS keyframe `0.2s` + JS removeChild 同步觸發 = 動畫被切斷的視覺 glitch。多 10–20ms 緩衝 = 安全。

**出處**：r29h

---

### 5.6 Cowork sandbox：git index 用單一 batched add

連續多次 `git add` call 在 sandbox 會累積撞 `bad signature 0x00000000` index corruption。修法：
```bash
rm -f .git/index && git read-tree HEAD && git add <files...> && git status
```
single batched add 一次完。

**已 memory**：`feedback_cowork_git_index_single_batched_add.md` + `feedback_cowork_fs_index_desync.md`

**出處**：跨 15 phases

---

## 6. 索引

- 工作日誌：[`docs/journal/2026-05-04_05_session_log_r28-r29k.md`](journal/2026-05-04_05_session_log_r28-r29k.md)
- 決策紀錄總覽：[`docs/decisions/2026-05-05_phase5b_r28-r29k_summary.md`](decisions/2026-05-05_phase5b_r28-r29k_summary.md)
- 各 phase 詳細 decision log：`docs/decisions/2026-05-0[45]_phase5b_r29*.md`
- 已存 memory：`/sessions/friendly-dreamy-noether/mnt/.auto-memory/MEMORY.md`

---

**寫這份的目的**：把跨 phase 浮現的「不只此一處適用」工程習慣固化下來。下次新 phase 開動前可快速 scan 一遍 — 「我這次該套用哪幾條？」比每次重發明強。
