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

## 6. 設計流程原則（2026-05-06 phase 6z spike 新增）

前 5 章累積的多是「**implementation-time**」原則（寫 code 時該怎麼做）。Phase 6z 禪繞字 design spike 過程浮現另一層 — 「**design-time**」原則（如何把 user 願景轉成可實作的 spec）。

### 6.1 大 phase 必先寫 design doc，不寫 = 不該動 code

8+ 條架構軸全未決狀態下動工 = 高機率重做 — 「不確認需求清楚」+「不確認技術可行」雙判準（personal-playbook §5.7）齊踩。

**判準**：
- Phase 涉及新 schema / 跨工具鏈 / 跨 mode infrastructure → **必經 design doc**
- 改既有 implementation 內部細節 → 5-Q ceremony 即可，不需 design doc
- Trivial polish / 1-2 行 fix → 跳 ceremony

**Design doc 的 cost vs ROI**：
- Cost：2-3 hours 寫
- ROI：避免 30%+ 的 implementation 重做時間
- ROI 不對 trivial phase 划算（小於 5h 工作別寫 design doc）

**反例**：r29 系列 11 phases 都沒寫 design doc，因為每 phase 1-3h 工作量 + 對既有 schema 局部增量 + 5-Q ceremony 已 cover。Phase 6z 不一樣 — 全新 mode + 3 新 schema concept + 9+ 架構軸。

**出處**：phase 6z spike 評估

---

### 6.2 草稿 vs 定稿 — 哲學張力的調和模式

當 user 期待 (workflow practical) vs philosophy (purity) 衝突時，**用「兩 phase 模型」** 調和：

| Phase | 行為 | 適用 |
|---|---|---|
| **Draft** | 全功能 undo / snapshot / 隨時可改 | 工作中、user 可休息回來 |
| **Final / Published** | Immutable，發布即 frozen | 發布後不再修改 |

**對應實例**：
- **寫作**：草稿（自由改）vs 定稿（出版即定型）
- **攝影**：RAW（後製空間）vs 沖洗成相片（定型）
- **程式**：未 commit（git stash 可改）vs 已 commit（amend 算新 commit）
- **Phase 6z 禪繞字**：draft 全 undo / snapshot vs published 上 gallery 後 immutable 不可後製

**判準**：
- User 既要「自由」又要「結構」 → 用兩 phase 模型
- 不要在同一階段強迫融合衝突需求 → 一定有一邊不爽

**Schema 含義**：`is_draft: bool` 必填 + 兩階段 boundary 明確（**「發布」按鈕**是 boundary 觸發點）。

**出處**：phase 6z 禪繞「沒有錯誤」 vs user 「回上一步」 衝突調和

---

### 6.3 資料分批收集驅動設計，不急著動工

Senior 該耐住「想動手」的衝動，等 user 提供完資料再 commit final spec。

**5 個訊號表示「該等資料」**：
1. User 用「請等我提供資料」 / 「我再想想」 / 「我有更多想法」
2. Architecture decision 還有 ≥ 3 條未決
3. 技術可行性 spike 沒做
4. Multi-mode / cross-system 的 boundary 還沒定
5. 「我覺得 X 應該怎樣 ...」 是個人 hunch，沒實際資料 backing

**反例（不該等）**：
- 既有 mode 內部 polish — 直接 5-Q + ship
- Bug fix — 直接 fix
- User 已給完整 spec — 可動工

**對應 §5.7 personal-playbook 「何時不該立即實作」 的 4 判準** — 但加碼一條：「**user 自己說等等」是壓倒性 stop signal**。

**出處**：phase 6z 接收 21 批資料後才達設計收斂

---

### 6.4 Product positioning 升級：thesis 進化於設計過程

Design discussion 中 product 的核心定位有時會**進化**（不是原始 user request 字面）。Senior 該發現+articulate 這個進化，讓 user 確認新 thesis。

**Phase 6z 案例**：

| 階段 | Product thesis |
|---|---|
| 起點（user 字面）| 「禪繞字 = 漢字邊框 + 內部禪繞」 |
| 中段（21 批資料消化中）| 「禪繞數位畫板 with character mode」 |
| 末段（user 提 9 cell panel 後）| **「禪繞重複疊加減負工具」** |

→ 末段才是真 thesis。「**重複疊加減負**」決定 product moat（vs Krita / Procreate 競品）+ 主 UI（9 cell panel 而非 toolbar of brushes）+ user 期待（享受重複節奏 vs 「畫得像不像」）。

**規則**：
- Design discussion 中發現 thesis 進化 → 主動講出來給 user 確認
- Thesis 確定後 design doc 該明確 product positioning section
- 避免「字面實作」陷阱：user 說 X，但 X 隱含的真 thesis 是 Y → ship Y 才滿足 user

**出處**：phase 6z 21 批資料消化過程

---

### 6.5 QODA 4 步是「對話前置」 不是「事後紀錄」

QODA（Question / Options / Decision / Approval）是 personal-playbook §5.9 的協作協定。今天 morning audit + phase 6z spike 全程套用，發現 4 步**不是事後紀錄結構**，而是**對話前置框架**。

**正確使用**：
- 每個非小事決定**動工前**就走 QODA 4 步
- 文字明確標出當前在哪步（Q / O / D / A）
- 等 user **明示** Approval 才動手
- 動完才寫 decision log（QODA 4 步是 log 的 skeleton）

**反例（事後紀錄誤用）**：
- 動完才補寫 QODA — 是 rationalization 不是 decision-making
- 自己腦補 user OK 了就動 — 跳過 Approval 是違反 QODA 精神

**規則**：
- 對話 / 釐清 / 微小修正 → 跳 QODA
- 加新依賴 / 改架構 / 選 stack / 設計 API / 命名 / 動 license / 跨檔重構 → **必走 4 步**
- 不確定該不該 QODA 時 → 走（cost < 1 分鐘，誤動 cost > 1 小時）

**今日完整套用案例**：
- 上午 morning audit：A/B/C 三 steps 各走 QODA Q-O-D-A 等 user 簽收才動
- 下午 phase 6z spike：15 個決定方向逐個 Q-O-D-A，最終 user 「OK ★」 才算 spike 結束

**出處**：今日全程套用驗證

---

### 6.6 21-batch acknowledge pattern — 資料批次收集 SOP

當 user 要分批給資料（`「請等我提供資料」`），AI 該怎麼處理每批？

**規則**：
- **每批 acknowledge** — 標出「收到第 N 批」
- **抽 3-5 個 architecture-relevant 訊號** — 不要 paraphrase 全文
- **記下 schema / scope / philosophy 等對 design doc 重要的影響**
- **不主動整合 design doc** — 等 user 說「就這些」 / 「OK ★」 才開始整合
- **若該批 user data 跟之前批衝突或補強，標出這個 reconciliation**

**Why**：
- 立即整合每批 = 高機率覆蓋自己 / 跑得快但偏方向
- 等 user 「就這些」 = 收斂 signal，user 自己判斷該停
- 每批小 acknowledge = 給 user 即時反饋「我有理解」 + 可被糾正

**反例**：每批 user 給完都立刻寫 design doc 草稿 → user 想多給但已感覺被「鎖死」 → 提供資料慾下降。

**今日案例**：21 批 zentangle 資料逐批處理，每批 acknowledge + 抽 3-5 訊號 + 等 user signal 才 commit final design。

**出處**：phase 6z 設計過程

---

### 6.7 「資料 + 觀察 = 待驗證」 的設計暫停模式

User 提具體 UI mechanism（如「9 cell 重複疊加 panel」）並說「**先規劃設計，待實際操作驗證後修改**」 — 這是明確的 deferred validation signal。

**規則**：
- AI **直接記下 user proposed design** 進 design doc
- 標 `status: pending UX validation` 或「MVP 採此規劃，待真實使用後 iterate」
- **不過度優化** — user 自己知道現在不確定，AI 別「自作聰明」改設計
- AI 提幾個延伸建議（如預設值該幾個）但不取代 user proposal

**今日案例**：user 說「次數/間距是否要出現預設值，自動因應空白區域大小而自動調整，請先規劃設計，待實際操作驗證後修改」 → 我提了 A 預設快選 + B 簡化版「填滿空白」 + C 智慧 adaptive defer，user 「OK ★」確認 — 採 A+B，C 等驗證。

**對應 §8.5 啟用條件結構性煞車** — 但本條更聚焦「**user 主動標 待驗證**」的場景。

**出處**：phase 6z 9 cell panel + 元素尺寸

---

## 7. 索引

- 工作日誌：
  - [`2026-05-04_05_session_log_r28-r29k.md`](journal/2026-05-04_05_session_log_r28-r29k.md)
  - [`2026-05-06_session_log.md`](journal/2026-05-06_session_log.md)（本日）
- 決策紀錄：
  - [`2026-05-05_phase5b_r28-r29k_summary.md`](decisions/2026-05-05_phase5b_r28-r29k_summary.md)（5/4-5/5 跨 phase 總覽）
  - [`2026-05-06_phase6z_design_spike.md`](decisions/2026-05-06_phase6z_design_spike.md)（**本日 phase 6z spike**）
  - 各 phase 詳細：`docs/decisions/2026-05-0[456]_phase*.md`
- Personal-playbook cross-link：
  - `2026-05-06_r29-r29k_principles.md`（在 personal-playbook repo，跨 ref 案例 §B.15-B.23）
- 已存 memory：`/sessions/friendly-dreamy-noether/mnt/.auto-memory/MEMORY.md`

---

**寫這份的目的**：把跨 phase 浮現的「不只此一處適用」工程習慣固化下來。下次新 phase 開動前可快速 scan 一遍 — 「我這次該套用哪幾條？」比每次重發明強。

§1-5 是 **implementation-time** 原則（寫 code 時）；§6 是 **design-time** 原則（把願景轉 spec 時）。兩者互補。
