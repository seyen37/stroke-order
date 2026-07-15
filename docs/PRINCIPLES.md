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

> **§6 子節順序註**：§6.1-§6.7 是 5/6 spike 累積、§6.9-§6.12 是 5/8 implementation 過程萃取。§6.8 是 meta-mapping section（§6 ↔ personal-playbook 治理層對照），刻意放本章最末。文件順序是 6.1 → 6.7 → 6.9 → 6.10 → 6.11 → 6.12 → 6.8，跟編號順序不同 — by design。

### 6.1 大 phase 必先寫 design doc，不寫 = 不該動 code

> 🔗 **Thesis 層**：personal-playbook **§0.4「重新框架問題 > 答問題（plan-first 升級）」** — 「Senior 紀律的核心不是會用更多工具、是問對問題」。本條是該 thesis 在工程實作層的 rule 化。

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

> 🔗 **Thesis 層**：personal-playbook **§0.2「Enforcement-based vs Hope-based governance」** — 「能用代碼鎖的就不寫 prompt 期待」。QODA 4 步是 plan-approve 層的 enforcement instantiation；本條再強化「**動工前必走 4 步並等 Approval**」是 enforcement，不是 hope。

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

> 🔗 **Thesis 層**：personal-playbook **§8.32「失敗 2 次換方法 反偷懶協議」** 同精神 — 兩者都是「沒對齊就 stop signal」。差別：§8.32 處理「實作中」的失敗 stop，§6.7 處理「設計前」user 主動標記的 deferred validation。

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

### 6.9 預設策略 domain-specific — Ops 強紀律弱預設 vs UX 預設要 senior

**Trigger**：規劃任何 default value / form field / config 流程時。

**規則**：問三維後再決：
1. **錯預設代價**？（Ops 斷網/資料壞 vs UX 視覺不符預期）
2. **修正代價**？（半夜跑機房 vs 按一下換）
3. **First-paint 友善**對 acquisition target 是否致命？

**對映**：
- **Ops / Infra** (e.g. NIC name / schema version) → **強紀律弱預設** (D-C)：force user verify、無預設、ESC 不可 dismiss
- **UX / Acquisition target** (e.g. zentangle char / mode / tile size) → **預設要 senior 不要 absent**：合理初始值即時開磚、modal 改 settings 入口、ESC 可關

**Anti-pattern**：把 ops 通則套進 UX → first-paint friction = lost user。

**今日案例**：
- 6z-1F 套 D-C 寫 force-modal 必填 → user 反饋「要預設值先讓使用者開磚」
- 6z-1.1 加 `DEFAULT_CONFIG = {char:"心", mode:"hollow", tileSize:"standard"}` fallback
- 6z-1.2 完全刪 modal → inline 控件 + change auto-apply

**對應 memory**：[`feedback_domain_specific_defaults`](../../.auto-memory/feedback_domain_specific_defaults.md) — 詳細三維問題清單。

**對應 personal-playbook**：§0.4 重新框架（「**這個 domain 的錯預設代價是什麼**」 才是 senior 問題、「**該不該有預設**」 是表象 binary）。

**出處**：phase 6z-1F → 6z-1.1 → 6z-1.2 三次連續修補

---

### 6.10 Modal vs Inline — Creative tool config 用 inline + auto-apply

**Trigger**：設計任何 settings / config UI 時。

**規則**：
- **Modal** 只用於 **transactional / destructive / irreversible** 動作（轉帳、刪除、發布、上傳）
- **Inline + auto-apply** 用於 **可逆 settings / continuous adjustment**（mode、color、size、density、filter 等 creative tool config）

**Why**：Creative tool 的本質是**直接操作 + 立即反饋**。Modal 在 settings 場景＝多一道 friction（open → confirm → close → 想再調 → 再 open）。對連續微調（slider drag、radio cycle）尤其反 pattern。

**今日案例**：6z-1F 把 char + mode + tile size 包成 modal，連續 3 次 user 反饋（必填 → 改 fallback → 改 inline radio），第 3 次徹底刪 modal、改 inline radio + change 即 apply。

**Strip-and-rebuild signal**：第 2 次同類 modal-vs-inline 修補後，root cause = modal 當 settings 入口的錯誤前提；第 3 次該 strip 而非 patch。

**對應 personal-playbook §8.32 失敗 2 次換方法** — 本條是該原則在 UI 層的 instance。

**出處**：phase 6z-1F → 6z-1.2 三輪修補

---

### 6.11 Canvas 整體變換用 ctx transform，不對 primitive 個別 pre-rotate

**Trigger**：Canvas / SVG 上需要「**多個 primitive 視覺上群組變換**」（旋轉、縮放、平移、透視）時。

**規則**：
- **群組變換**（如「**整個紙磚**旋轉」 含邊框 + dot + 字 + tangle 同步轉）→ **ctx.save / translate / rotate / restore 包住整個 draw block**
- **個別 primitive 變換**（如某條 stroke 的 pseudo-3D 透視 stored 進 schema）→ pure helper 對 polyline coords 預變換

**Anti-pattern**：用 polyline pre-rotation (e.g. `rotateContours()`) 來實現「**整體旋轉**」 — frame 不在 polyline 集合裡，會落在 axis-aligned 空間，造成「字轉、磚不轉」 視覺 bug。

**今日案例**：
- 6z-2 用 `rotateContours(mappedRaw, _rotationDegrees, [ts/2, ts/2])` 對 outline polylines pre-rotate → drawTileBackground 仍 axis-aligned → user 反饋「**外框連同字一起旋轉**才對」
- 6z-2.1 改 `withTileRotation(fn)` ctx transform 包整個 redrawAll → frame + outline + tangle 全在同一 transform 下

**驗法**：當 visual element 群組旋轉時，問「**這群是不是該作為 unit 一起變**」？是 → ctx transform 包住；否 → primitive pre-transform。

**Bonus 觀察**：Pure helper（如 `rotateContours`）仍值得保留 + Node test，給 state-aware 場景用：SVG export、`.zentangle.md` serialization、Pseudo-3D pre-render（content 變換需要存進 schema）。

**對應 6z-2.2 補充 — Viewport 控制 vs 內容變換是不同層**：
- **Viewport** (pan / zoom / scroll) — 只影響顯示、不改 content data → ctx transform 即可
- **內容變換** (rotation / scale / pseudo-3D / fill) — 影響 content 視覺 representation → 該存進 schema
- 兩者正交、state 應分開存（如 `_rotationDegrees` 是內容變換 + `_panState` 是 viewport — 互不重疊）

**出處**：phase 6z-2 → 6z-2.1 修 frame 旋轉 → 6z-2.2 加 pan buttons

---

## 6.12 失敗 2 次同類修補 → 第 3 次 strip and rebuild（§8.32 工程 instance）

**Trigger**：對同一塊 code / UX / spec 連續第 2 次以上同方向修補時。

**規則**：第 2 次同類修補後，停下問「**root cause 是什麼**」 — 通常是某個架構性前提錯了。第 3 次該 **strip and rebuild**，不該再 patch。

**辨識訊號**：
- 同一檔案連續 commit 訊息都是「fix: X 修補 N 次」
- 修法越來越「繞」（補 if、加 hack、case-by-case）
- User 反饋持續同一方向（「再讓 X 更...」 / 「這個還是有問題...」）
- 自我感覺「**怎麼又改這塊**」

**對應 personal-playbook §8.32** — 思維層原則的工程 instance。

**今日案例**：
- **6z-1 force-modal**：6z-1F (必填) → 6z-1.1 (DEFAULT_CONFIG fallback、modal 改非阻擋) → 6z-1.2 (完全刪 modal + inline radio)
  - 三次都修 modal、第 3 次該 strip 才看清「**modal 當 settings 入口」 是錯的前提**
- **6z-2 rotation 視覺**：6z-2 (rotation pre-rotate) → 6z-2.1 (改 ctx transform) → 6z-2.2 (加 pan) → 6z-2.3 (修箭頭方向)
  - 4 次 visual fix 揭示「**unit test 抓不到 visual**」 真實 (對應 memory `feedback_visual_render_verify`) — 但 root cause 不同（架構 vs 視覺細節），所以不是 strip signal、是「visual verify 該每次都做」signal

**區辨**：
- 同 root cause 反覆修補 → strip
- 不同 root cause 只是同檔位/同視覺區 → 持續 visual verify

**出處**：phase 6z-1 三輪 modal 修補（明確 strip signal）+ 6z-2 四輪 visual fix（visual verify 累積）

---

### 6.13 Sticky default + new-element inherit — 連續創作的低 friction 預設

**Trigger**：creative tool 有 per-element 設定（每筆 stroke / 每個 unit / 每張 layer 各自的 perspective、color、density 等）時。

**規則**：
- **Set once → all NEW 元素 inherit**（user 不需逐個重設）
- **修改 sticky state ALSO updates LATEST 元素**（即時 preview，user 看得到效果）
- **Old 元素保留自己的設定**（non-destructive；若想修改舊元素需 selection mechanism — 6z-5a/b 沒做、defer）
- **Reset / clear button** 斷 sticky chain

**對位**：
- §6.9 預設策略 = **product launch** 預設（first-paint 友善）
- §6.13 sticky default = **continuous creation** 預設（per-action 友善）
- 兩者都在減 friction，但發生在 user journey 不同點

**Anti-pattern**：每個新元素 modal 彈出問「要 forward 還是 backward？」 — 違反 6z-1.2 modal-as-settings 反 pattern + 違反 acquisition-first creative tool 直覺。

**今日案例**（5/8）：
- 6z-5a `_stickyDepthDir / _stickyDepthDegree` — 4 方向 + 強度
- 6z-5b `_stickyCurveMode / _stickyCurveDegree` — 4 軸 + 強度
- 6z-1.2 `_config` (char + mode + tile_size) 也是 sticky 但更早期 instance
- 「無透視」 / 「無曲度」 button 是斷 chain 入口

**對應 personal-playbook §0.4 重新框架** — 「應該每次選嗎」 是表象 binary、「**這個 setting 變化頻率 / 用 sticky 還是 per-action**」 才是 senior 問題。

**出處**：6z-5a / 6z-5b sticky state 設計

---

### 6.14 Multi-axis enum + class-based wirable selector — 預埋 + 漸進解鎖 pattern

**Trigger**：feature 有多個 discrete options（4 方向 / 4 軸 / 8 preset / N 個 tangle / N 個 mode）+ 想要漸進 ship 時。

**規則 3 層**：

1. **Pure module 預埋全 enum**：`VALID_X_MODES = [...]` + `isValidX(mode)` 驗證 + `applyXTo*` 實作 ALL options（即使 UI 暫不全暴露）。Node test cover 全 enum。

2. **HTML 用 class + data-attr selector**：
   ```html
   <button class="zt-curve-btn" data-curve="high-mid">中高</button>
   <button class="zt-curve-btn" data-curve="high-sides">邊高</button>
   ```

3. **JS class-based addEventListener**：
   ```js
   document.querySelectorAll(".zt-curve-btn").forEach(btn =>
     btn.addEventListener("click", () => setCurveMode(btn.dataset.curve))
   );
   ```

**結果**：解鎖剩餘 enum option = **加 1 行 HTML + 0 行 JS**（pure module 已 cover、selector 自動 wire）。

**今日案例**（5/8）：
- 6z-5b 寫 pure module 全 4 軸 + UI 暴露 1 軸（high-mid）
- 6z-5c 解鎖剩 3 軸：純 HTML +3 button、JS 0 改動。10 min 完工。
- Pattern 在 6z-2 旋轉 (data-deg) / 6z-2.2 pan (data-pan) / 6z-3 tangle (name="zentangle-tangle") / 6z-5a depth (data-dir) 都重複出現

**對位 personal-playbook §8.32 失敗 2 次換方法** — 反向：**成功 2 次同 pattern 該升格為 reusable mechanism**。

**對位 §6.10 inline + auto-apply** — class-based selector + auto-wire 是 inline pattern 的工程實作底層。

**Anti-pattern**：
- 每 button 寫 `getElementById + addEventListener`（量大時 boilerplate 爆）
- Pure module 只實作 UI 當下需要的 option（解鎖時要重寫邏輯）

**出處**：6z-5b → 6z-5c 解鎖驗證（10 min ship 3 軸）

---

## 6.8 §6 vs personal-playbook 治理層 mapping（thesis ↔ rule 對照）

2026-05-06 personal-playbook 第十三次修訂從 139 ref pool cherry-pick 12 條原則，新加 §零 治理哲學（thesis 層）。本表把 stroke-order §6 工程 rule 對應到 personal-playbook 的 thesis 層：

> **2026-05-07 補充**：personal-playbook commit `0917c60` / `3ad1cab` / `0d66f28` 從另一台電腦 ESXi/VM ops 工作中萃取 4 共通性原則（#13-#16）+ 5 個 U5M60 setup decisions（D-A 至 D-E）。本表已擴充，新增 row 標 🆕。詳見 personal-playbook `docs/WORK_LOG_2026-05-07.md` §G + `docs/decisions/2026-05-07_u5m60_first_setup.md`。

> **2026-05-08 補充**：personal-playbook 第十三次修訂 commit `5ca1ab4` 新加 **§3.14 Cowork 寫檔工具對 mounted Windows UTF-8 中文 markdown 的 corruption SOP** + **§B.24 案例**（biped-research round 12 PRINCIPLES.md 連續踩 Edit / Write / bash heredoc 三種失效模式）。**§3.14 是 AI agent 工作流層級 SOP、非 stroke-order 工程 rule**，本 PRINCIPLES.md 不另寫副本，引用對應即可。**5/7-5/8 stroke-order 13 commits 寫的 10 個中文 .md 已用三件套（`wc -l` / `tail -3` / `xxd | tail -2`）回溯驗證、全 pass（0 mojibake / 結尾全 LF / 行數無截斷）— 是倖存者偏差，從 `5ca1ab4` 起所有新檔寫入採 §3.14 唯一可靠寫法（Python list-of-strings + 三件套 verify）**。

| Stroke-order §6 (rule layer) | Personal-playbook §零 (thesis layer) | 關係 |
|---|---|---|
| §6.1 大 phase 必先寫 design doc | **§0.4** 重新框架問題 > 答問題（plan-first 升級） | thesis 層命名 |
| §6.5 QODA 是對話前置 | **§0.2** Enforcement-based governance | thesis 層命名 |
| §6.7 設計暫停模式 | **§8.32** 失敗 2 次換方法 反偷懶協議 | 同 stop-signal 精神 |
| §6.4 Product positioning 升級 | **§0.4** 重新框架問題 部分 | 「重新框架」精神延伸 |
| §6.2 草稿 vs 定稿 | (待 cherry-pick 進 personal-playbook) | stroke-order 獨有 |
| §6.3 資料分批收集 | (待 cherry-pick) | stroke-order 獨有 |
| §6.6 21-batch acknowledge | (待 cherry-pick) | stroke-order 獨有 |
| 🆕 §8.22 Reconnaissance + §6.4 不擴大 scope | **#13 Prerequisite Confirm** + **#15 IT Debt 區分紀律** | thesis 層強化「假設 vs reality 落差」+ scope hygiene（不是所有 debt 都該動） |
| 🆕 §6.4 Product positioning「真正能用」維度 | **D-D 完成度 = capability not installation**（U5M60 verify gate）| thesis 層深化既有 visual_render_verify culture — 「裝起來」≠「能跑」 |
| 🆕 (memory: schema_versioning + i18n_filename dual-storage) | **D-C 強紀律弱預設**（force verify + 列舉常見值，不 pin specific value）| 跨 domain 同精神 — stroke-order 既有 memory pattern 在 ops domain 重現 |

**反向映射 — personal-playbook 第十三次修訂中 stroke-order 該套用的 rule**：

| Personal-playbook (新加) | Stroke-order 應用點 |
|---|---|
| §8.31 P7 三問自審 + strict completion format | **phase 6z 每 sub-phase 完成寫 P7 completion format**（剩餘風險必填） |
| §8.32 失敗 2 次換方法 | §3.13 sandbox/host lock 是這個的 instance（嘗試 sandbox `rm` 失敗後改 host）|
| §8.33 Self-defense bias / reviewer 拿純 diff | phase 6z review 該套用 |
| §8.34 「會花真錢 API」enforcement | phase 6z+ image-to-config 階段適用 |
| §8.35 Strict negative constraints | **phase 6z design doc 該有 anti-pattern 清單** |
| 🆕 #13 + #16 Prerequisite / Reality Confirm | **phase 6z-1 啟動前**：grep 既有 outline-extract / SVG path ops、verify zentangle library deps、確認 SVG `<path>` API 限制（避免 sandbox 假設 vs 瀏覽器 reality 落差）|
| 🆕 #14 政策對位紀律 | phase 6z 尊重 SVG / Canvas API 既有約束、不 over-engineer rendering（如：不為偽 3D 自寫 perspective transform，先確認 SVG 既有 transform 可達）|
| 🆕 D-C 強紀律弱預設 | phase 6z **API defaults 應 force user 確認**（如 `pseudo_3d.depth_dir` / `tile_size` 不該 silent default、應 require explicit choice 或在 UI 提供 5 預設按鈕並標明）|
| 🆕 D-D 真正能用 verify gate | phase 6z 每 sub-phase 完成 gate = **visual render test pass**（PNG 截圖比對），不是 unit test 過就標 done — 對應 stroke-order memory `feedback_visual_render_verify` |

> **2026-05-11 補充**：personal-playbook 第十五次修訂 commit `19534e9` 從另一專案（biped-research）sync 4 條原則 **§3.15 / §3.16 / §8.36 / §8.37** + §B.25-B.27 案例索引。本表新增 4 row 標 🆕（5/11）：

| Personal-playbook (5/11 新加) | Stroke-order 應用點 |
|---|---|
| 🆕 §3.15 Cowork sandbox cross-mount 大檔 IO 限制（5-6 MB/s, 45s timeout）| AI workflow SOP — stroke-order 純 text 寫入不踩；但若將來加 LFS / 大 PNG fixture 需走 user PowerShell。同 §3.14 是 workflow 層、非 engineering rule、引用即可 |
| 🆕 §3.16 巨型 binary 政策（>50 MB 個別 pathspec gitignore + metadata）| 同上 — stroke-order 目前無 >50 MB binary；若 phase 6z+ 加 high-res tangle texture 或 gallery thumbnail 大檔，套政策（_raw/ 留檔 + .gitignore 個別 pathspec + NOTICE 紀錄）|
| 🆕 §8.36 Self-audit 抓錯立刻修 + 順帶解決相關結構問題 | **stroke-order 4-strike pattern 是 §8.36 的 instance** — 6z-1.2 / 6z-2.1 / 6z-2.2 / 6z-2.3 連續修補時都「順帶清相關小問題」（如 6z-2.1 加 _cachedContours 順手解 slider fetch race）。對應既有 §6.12 strip-and-rebuild 是子集 |
| 🆕 §8.37 一手 metadata > 推測（cross-source 一致 = 強證據）| **stroke-order「visual render verify」 是 §8.37 在前端的 instance** — 不推測渲染結果、跑實際 PNG 比對；不推測 outline 形狀、用 fonttools 一手 outline_cmds。對應 memory `feedback_visual_render_verify`（unit test 不夠、要看真實 render）|

> **2026-05-13 補充**：personal-playbook 第十六/十七次修訂 commits `784dfce` / `f6f0685` 再加 **§3.17 paste prompt audit** + **§3.18 Cowork uploads sync silent failure SOP** + §3.14 R37 dogfood 2nd validation。Cowork sandbox 系列 SOPs 累積成 7 節：§3.10 / §3.13 / §3.14 / §3.15 / §3.16 / §3.17 / §3.18 — 涵蓋 git-index-corruption / git-lock-race / write-tool-corruption / cross-mount-IO-limit / giant-binary-policy / paste-prompt-audit / upload-sync-silent-failure 共「sandbox-視角 ≠ host-視角」 多維邊界。Stroke-order 採取 single reference policy（不逐節 row, 引用全系列即可）：

| Personal-playbook (5/13 新加) | Stroke-order 應用點 |
|---|---|
| 🆕 §3.17 paste prompt audit | AI workflow SOP — Claude 給命令時必標 `【host 端 PowerShell】` / `【sandbox bash】` / `【VM 內 bash】`；user paste 前 5 秒讀 prompt 對位 |
| 🆕 §3.18 uploads sync silent failure | AI workflow SOP — round 啟動前必 `ls /sessions/.../mnt/uploads/` 實證、不可基於 `<uploaded_files>` tag 假設檔案在 sandbox |
| 🆕 Cowork sandbox 系列 (§3.10/13/14/15/16/17/18) 整合引用 | 全列為 AI workflow 紀律、stroke-order 引用即可。若未來 §3.19+ 增加 → 在此 row 加 entry、不另開新 row |

> **2026-05-14 補充**：personal-playbook 第三十一/三十二次修訂 commits `60b8ff3` / `f6b5628` 升等 **§3.10 Cowork sandbox bash git index corruption SOP**：5/14 起 **default-deny 嚴格化** — sandbox bash 對 stroke-order repo **完全不跑任何 git 寫入命令**（含 `git fetch / status / add / commit / push`、不只先前的 `git add`/`commit`/`push`）。同時 §3.13 strengthen 補強、§8.36 加 sub-rule 3 ("順手解結構問題不擴張原 task scope")。

| Personal-playbook (5/14 升等) | Stroke-order 應用點 |
|---|---|
| 🆕 §3.10 5/14 default-deny 升等（sandbox 0 git-write）| **本 repo workflow 從此調整**：Claude 在 sandbox 只能 `Read` / `Bash` 純讀 + `Write`/`Edit`/Python 寫 .md/.py/.mjs 等非 git-index 檔；**所有 `git add` / `git commit` / `git push` / `git fetch` / `git status` 一律由 user 在 host PowerShell 執行**。Claude 負責寫好完整 commit message + 列出該 stage 的檔案清單，user 一次 paste 跑完。Friction ↑ 但 git index corruption / lock race 0 風險、跨 device session 並行最安全。先前 18+ commits 採 sandbox commit + host push 模式雖無事故 (倖存者偏差) — 從本 commit 起轉嚴格 |
| 🆕 §3.13 5/14 strengthen | 同上整合於 §3.10 default-deny；本 repo 無額外 row |
| 🆕 §8.36 sub-rule 3「順手解結構問題、不擴張原 task scope」| **stroke-order 4-strike pattern 已是 §8.36 instance**（5/11 補充已記）；5/14 sub-rule 3 加強約束 — 順手清的「結構問題」不可演變成新 phase 級重構。本 repo 持續以「decision log 標『順手清』 + commit message 分行列舉」收斂 scope drift |

**Workflow 對照表**（5/14 起生效）：

| 命令類別 | 5/14 前 | 5/14 後（A 嚴格）|
|---|---|---|
| `git add` / `git commit` | sandbox bash 跑 | **host PowerShell** 跑（Claude 提供完整命令）|
| `git push` / `git push backup` | sandbox bash 跑 | **host PowerShell** 跑 |
| `git fetch` / `git pull` | sandbox bash 跑 | **host PowerShell** 跑 |
| `git status` / `git log` / `git diff` | sandbox bash 跑（讀） | **host PowerShell** 跑（避免 sandbox 看到 stale index）|
| 檔案寫入 (.md / .py / .mjs / .json) | sandbox `Write`/`Edit`/Python | sandbox `Write`/`Edit`/Python（**§3.14 SOP**：中文 .md 走 Python list-of-strings + 三件套 verify）|
| `grep` / `find` / `cat` / `ls` | sandbox bash | sandbox bash（純讀不受影響）|
| `pytest` / `node --test` | sandbox bash | sandbox bash（純執行測試、不寫 git index）|

**Commit message handoff convention**：Claude 寫 message 時用 Python list-of-strings 存到 `docs/_commit_msg/YYYY-MM-DD_NN.txt`（gitignore），user paste 後 `git commit -F` 引用，避免 PowerShell heredoc / escape 痛點。

> **2026-05-14 day 2 補充**：personal-playbook 第三十三次修訂 commit `551929c` 為「**5/14 day 1 #2 升級 §3.10 default-deny 後的同日 dogfooding**」— user 在另一個 session (biped-research R48) 沒先 fetch / log 就動工、整 round 用 sandbox bash 跑 `git show HEAD:PROJECT_PLAYBOOK.md` 違反剛升級的 §3.10 紀律、修訂編號用 28th 但 remote 已到 32nd（差 4）。R48 6 case 全部對位既有 §3.10/§3.14/§3.18 — user 自寫 SOP 已涵蓋情境、但仍踩 → 強力支持本 repo 嚴格 default-deny + fetch-first opening SOP。

| Personal-playbook (5/14 day 2 補充) | Stroke-order 應用點 |
|---|---|
| 🆕 §3.10 strengthen 候選 / §8.36 sub-rule 4 候選：**開工 SOP 第 1 步 = `git fetch origin + git log HEAD..origin/main`** | **本 repo 今早已實踐** ✓ — 5/14 morning audit 第一動作是請 user host PS 跑這兩條，catch 到 `551929c` 否則會延後一天看到。落地為「開工 routine 第 1 動作」、不另寫 §6.x、merge 進既有 morning audit SOP |
| 🆕 §3.14 / §3.18 strengthen 候選（R48 case 5）：**跨邊界 git 操作後 sandbox bash mount cache stale** — host git 後、sandbox Read 看到 stale 版本、若 sandbox write 回去 = 直接覆蓋 host 最新版（資料損失） | **本 repo workflow 0 風險命中** — sandbox 寫新檔（journal/decision/_commit_msg）→ host commit + push、sandbox 不會 host 改檔後再讀寫該檔。但記錄為已知風險、若未來 host 端被另一 session edit + 本 sandbox 接手 read/write → 必須走 host。Memory 新增 `feedback_host_git_then_sandbox_cache_stale` |
| 🆕 AI 給 user SOP 三段式分離紀律（R48 case 6） | **本 repo 5/14_01 / 5/14_02 commit handoff 已遵守** ✓ — PowerShell 命令獨立 fenced block、commit msg 走 `docs/_commit_msg/...txt` 不混 markdown content。Convention 文件化於 §6.8 5/14 day 1 補充「**Commit message handoff convention**」段 |
| 🆕 修訂編號 race（R48 case 4）→ commit hash > 順序編號 | 本 repo 已 default 用 commit hash (`28c1730` / `4698fc8` 等) cross-ref、無「Nth commit」style 順序編號 — 0 風險 |

**R48 dogfooding 對我們的 4 個 reinforcement**：

1. **§3.10 嚴格 default-deny 是對的** — case 3 證實「user 自己升級紀律後、自己在另一 session 就踩」。我們昨天選 A 嚴格落實受實證支持。
2. **fetch-first opening SOP 是必須** — case 3+4 提煉。本 repo 已實踐、不需新文件、merge 進開工 routine。
3. **Sandbox mount cache stale 是真實 risk** — case 5 嚴重性高（資料損失）；本 repo workflow 0 風險命中但記錄為已知。
4. **Commit msg handoff `-F` convention 預先防 case 6** — 5/14 day 1 採用的 friction killer 同時也是 R48 case 6「SOP 三段式分離」的具體實踐。我們提前一個 commit 就走對了。

**Cross-ref**: personal-playbook commit `551929c` (33rd revision) HISTORY.md §A 第三十三次修訂；本 repo memory `feedback_host_git_then_sandbox_cache_stale`（新加）+ `feedback_strict_default_deny_git`（更新加 fetch-first 條目）。

> **2026-05-19 morning audit 補充**：personal-playbook 5/14 → 5/19 共 7 個新 commit（fetch-first SOP catch）。**直接影響本 repo workflow 的 2 條**：`d2ea545` (5/14 day 3 第 34 修 R59 biped session)「§3.14 升 6→9 維度 + worst case sandbox 失能 + §3.13 2nd strengthen + 3 候選紀律」+ `13bbcc7` (5/19 evening Round 2)「共通性原則候選 5 條（plan-first ADR / plan v1→v2 / hardcode 掃描 / 動工延後 user-side gate / ssh fallback）」。其餘 4 commit（pptx / U5M60 / U6P40 / 5/19 worklog）為另專案無關。

| Personal-playbook (5/14 day 3 + 5/19 補充) | Stroke-order 命中度 / 應用點 |
|---|---|
| 🆕 §3.14 維度 7：Cowork outputs/ 不 host-visible | **0 命中** — 本 repo 寫檔全到 mounted folder (`/sessions/.../mnt/stroke_order/...`)、從未用 `outputs/`、不踩 |
| 🆕 §3.14 維度 8：Python 中文 print silent crash (cp950) | **0 命中** — 本 repo 寫檔 SOP 用 `path.write_text(..., encoding='utf-8', newline='\n')` 不用 print；sandbox bash 三件套 verify 用 `wc/tail/xxd` 不在 host PowerShell 跑 Python；不踩 |
| 🆕 §3.14 維度 9：Windows `python` = Microsoft Store stub | **0 命中** — 本 repo host PowerShell 工作流純 git 命令 (`git add/commit -F/push`)、不跑 Python；不踩 |
| 🆕 §3.13 2nd strengthen：sandbox 完全失能 worst case host-side fallback SOP | **0 命中**（sandbox 持續可用）— 但記錄為 **已知 contingency**；新加 memory `feedback_sandbox_unavailable_fallback` 提前部署應對 |
| 🆕 §8.36 sub-rule 5 候選：Windows Python runtime 邊界檢查 | 不適用（host 不跑 Python）|
| 🆕 13bbcc7 候選 #1 plan-first ADR + decision log 三分類 (inspection/plan/close) | **啟發** — 本 repo decision log 目前單一分類（如 `2026-05-14_strict_default_deny_workflow.md`）；待 user 升等正式紀律後評估是否套用三分類 |
| 🆕 13bbcc7 候選 #2 plan v1 通用 → v2 具體兩段式 | **啟發** — 本 repo phase 6z plan 是 v0.3 一次性、未做兩段式；6z-6 切割 mode 開動時可考慮 |
| 🆕 13bbcc7 候選 #4 動工延後 user-side gate 紀律 | **已實踐** ✓ — 本 repo 多次 plan-first + QODA confirm 後才動工（5/14 day 1 A 嚴格落實 / day 2 R48 補充 / 今日 5/19 audit 都先 confirm 才寫 code）|
| 🆕 13bbcc7 候選 #3 / #5（hardcode 掃描 / ssh fallback） | 不適用（無 production / 無 ssh 場景）|

**✅ Close 第 33 修 follow-up #3**（§3.14/§3.18 跨邊界 mount stale 補強）— d2ea545 9 維度 + worst case 已涵蓋。本 repo 5/14 day 2 提的「sandbox mount cache stale」記錄為 known risk、d2ea545 將其形式化為 6 維度 → 9 維度的維度升級。

**5/19 morning audit 3 個 reinforcement**：

1. **§3.14 9 維度框架對本 repo 0 命中** — 我們 workflow 路徑（mounted folder + Python list-of-strings + sandbox bash 三件套 + `git commit -F`）天然繞過維度 7/8/9 全部三條陷阱。**Reinforce「workflow 設計避坑 > 規則記憶」**。
2. **Worst case sandbox 失能是真實 risk 但 contingency 已部署** — 新 memory `feedback_sandbox_unavailable_fallback` 紀錄若 sandbox 失能時的 host-side fallback SOP（PS 命令直接 paste / commit msg 手寫 / 降層 verify）。
3. **候選原則 #4「user-side gate」是我們 default 紀律** — 本 repo 從 5/14 day 1 起每個 commit 都先 QODA 等 user confirm 才動工。User 在 personal-playbook 才剛標為「候選」、我們已實踐 6+ 次、是 supporting case 來源。

**Cross-ref**: personal-playbook commits `d2ea545` (34th revision, 5/14 day 3 R59 biped session) + `13bbcc7` (5/19 evening Round 2 共通性原則候選 5 條)；本 repo memory `feedback_sandbox_unavailable_fallback`（新加）+ `feedback_strict_default_deny_git` SOP-0 已實踐第 2 supporting case（today fetch-first catch 7 commits）。

> **2026-05-24 morning audit 補充**：personal-playbook 5/19 → 5/24 跨 5 天累積 **17 個新 commit**（fetch-first SOP catch；本機 host 已 pull 至 `d67d483`、sandbox refs invalidate ✓）。**5/24 升等 3 條正式紀律**直接相關：`d67d483` §8.40 default-deny 二維紀律整合升等 + `00193ad` §3.20 PS 5.1 中文編碼三件套 + §8.36 sub-rule 4「Debug ground truth first」。其餘 14 commits（U5/U6 / 知識庫 / PS toolkit 等他專案）無關。

| Personal-playbook (5/24 升等正式紀律) | Stroke-order 命中度 / 應用點 |
|---|---|
| 🆕 **§8.40 Default-deny 二維紀律整合升等**：跨「技術維」(權限域共寫資源) + 「業務維」(交付邊界) 的 4Q 決策框架 (代價 / 成本 / ratio / 跨邊界) | **本 repo 是 §8.40 技術維 source case** ✓ — 5/14 day 1 採用 §3.10 sandbox bash 不跑 git 寫入命令 = `f6b5628` (32nd revision) 升 default-deny 的 instantiation。§8.40 5/14 case study 直接引本 repo 落地經驗。Personal-playbook §3.10 已加 cross-ref note 指向 §8.40 |
| 🆕 **§3.20 PS 5.1 中文 Windows host 編碼地雷三件套 SOP**：Layer 1 (BOM 必加) / Layer 2 (Set-Content `-Encoding UTF8`) / Layer 3 (netsh tempfile + UTF-8 嚴格 heuristic) | **目前 0 命中**（commit msg `-F` 走 UTF-8+LF、不放 emoji、host PS 不跑 netsh）；但記錄為 **已知 contingency**、新加 memory `feedback_ps5_chinese_encoding_three_layers` 預部署、若未來 stroke-order 給 user 跑 `.ps1` 工具或 deploy script 須遵守 |
| 🆕 **§8.36 Sub-rule 4 Debug ground truth first**：第 1 輪猜失敗就停下加 diagnostic、不連續猜超過 2 輪 | **通用 debug 原則、高頻適用**；新加 memory `feedback_debug_ground_truth_first`。未來 phase 6z+ 任何 debug 都套：第 1 個修正版立即加 diagnostic、留 production、第 3 輪絕對停、自己拿 ground truth 不問用戶 |
| §1.6 寫第一份使用手冊 / §3.6 第 5 條 Unix 工具（5/24 升等 4 條中其餘 2 條）| 不適用（無使用手冊交付 / PS toolkit context）|

**§8.40 對位本 repo workflow 的二維 mapping**：

| 動作 | 技術維 | 業務維 | §8.40 紀律 |
|---|---|---|---|
| Sandbox bash 跑 `git add/commit/push` | 跨權限域共寫 `.git/index` | （無業務邊界）| **default-deny** ✓ (5/14 day 1 採用) |
| Sandbox bash 跑 `git log` / `git show` (純讀) | 同域純讀 | （無）| **no rule** ✓ (允許) |
| Sandbox Python `path.write_text(...)` 寫 .md/.py | 同域寫 mounted folder | （無）| **careful-operation** ✓ (§3.14 SOP) |
| Host PowerShell 跑 `git commit -F` | 同域寫 host `.git` | （無）| **careful-operation** ✓ (host 是 git 權限域 owner) |

本 repo 5 個 commits（5/14 → 5/19）workflow 自然滿足 §8.40 二維決策、無 retrofit 需求。

**5/24 audit 3 個 reinforcement**：

1. **§8.40 升等是「supporting case 提供 → source case 升為 thesis」的閉環** — 5/14 day 1 我們選 A 嚴格落實 §3.10 default-deny、6 天後（5/14 day 2 R48 + 5/14 day 3 R59 + 5/24 業務維 Network_Validator）累積 supporting case、5/24 升為 §8.40 二維 thesis。**證實「user-side gate 紀律」+「不超前升等」原則** — 上游時序對齊、本 repo 收成 source case 引用、不越權升等。
2. **§3.20 三件套是 §3.14 9 維度的補維度** — §3.14 涵蓋 Cowork sandbox + Python runtime + 跨邊界、§3.20 補「PS 5.1 host 本身編碼坑」。兩節合用 = 跨工具 / 跨語言 / 跨主機的編碼紀律完整覆蓋。本 repo 兩節 0 命中、但 contingency 預部署。
3. **§8.36 Sub-rule 4 是 phase 6z+ debug 必備工具** — 未來 6z-6 / 6z-7+ 開動時、debug 任何 visual rendering / state transition / canvas transform 等問題、第 1 輪猜失敗就停下加 console.log diagnostic（前綴 `[Diagnostic]`、留 production）、避免「再猜下一個」浪費 user 時間。對位本 repo memory `feedback_visual_render_verify`（visual 驗證每 round）+ 新 memory 二維互補。

**Cross-ref**: personal-playbook commits `d67d483` (§8.40 二維紀律升等) + `00193ad` (5/24 升等 4 條：§1.6/§3.6/§3.20/§8.36 sub-rule 4) + 14 個其他專案 commits（無關）；本 repo 5/14-5/19 5 commits（`28c1730` / `4698fc8` / `87e92fe` / `2b9dd6d` / `1c1d585`）= §8.40 技術維 case study source；新加 memory `feedback_ps5_chinese_encoding_three_layers` + `feedback_debug_ground_truth_first`。

> **2026-05-29 morning audit 補充**：personal-playbook 5/24 → 5/29 跨 5 天累積 **14 個新 commit**（SOP-0 fetch-first 第 4 supporting case、user 今早 02:22 host fetch+pull 完成）。**核心發現：5/14 followup #2「協作電腦類 round 開工 SOP fetch-first」已在 5/25 R36 commit `db52ac1` formal close** — 第 2 個我們 source case 被 cite 收尾的閉環（第 1 個是 5/24 §8.40 close 5/14 candidate 2）。**§3.19 跨機並行 push divergence handling SOP** 升 **3rd practice production-grade**（R59 + R34 + R35/R36 = N+ supporting cases）。

| Personal-playbook (5/29 audit) | Stroke-order 命中度 / 應用點 |
|---|---|
| 🆕 **§3.19 跨機並行 push divergence handling SOP 升 3rd practice production-grade**（stash → pull --ff-only → pop dance 7 步 + 3 反例）| **0 命中** — 本 repo 7 commits single push direction、無跨機 race；但 **contingency 預部署**、新加 memory `feedback_cross_machine_push_divergence_dance`、若未來在另一台改 stroke-order 觸發 fast-forward 衝突立即可套 7 步 dance |
| 🆕 **5/14 followup #2 close**（commit `db52ac1` 5/25 R36）：「協作電腦類 round 開工 SOP 第 1 步 = `git fetch + git log HEAD..origin/main`」**正式 formalize 為 §3.19 SOP 3rd practice** | **本 repo SOP-0 是 source case 之一** ✓（與 R59 / R34 / R35/R36 並列 N+ supporting cases）；5/14 day 2 R48 case 3+4 提煉、5/19/5/24/5/29 4 次連續 catch（1→7→17→14 commits、累計 catch 39 commits）— 我們 sustained discipline 是 close 紀律的 evidence |
| §3.21 已設定電腦稽核 SOP (5/26、6-step monthly checklist) | 不適用 — 本 repo 為 active dev 環境、非「已設定電腦」、無 monthly routine 需求 |
| §3.22 LLM / RAG 黑盒症狀 debug (5/28 升等、先 grep log 後調 model 參數) | 無關 — 本 repo 不做 LLM / RAG |
| §3.23 跨層 cache invalidation 4 步紀律 (5/28、host nginx + docker + browser HSTS + DNS) | 無關 — 本 repo 無 nginx / docker / DNS |
| 其他 9 commits（46th gap fill、47th OpenClaw、48th cleanup、5/24 docx v4.12.1、jitsi、B.36-38）| 無關（governance 內部 sync / 其他專案）|

**5/29 audit 3 個 reinforcement**：

1. **第 2 個 source case 閉環浮現** — 5/24 §8.40 close 我們 5/14 day 1 §3.10 採用（第 1 閉環）；今日 5/25 R36 close 我們 5/14 day 2 SOP-0 提煉（第 2 閉環）。**長期紀律累積的回報 = 被 cite 為 source case** — 5/14 我們提的兩條紀律都在 11 天內被 personal-playbook 正式 formalize、屬「sustained discipline pays」實證。
2. **Contingency memory 第 3 條同類、標準持續形成** — 5/19 `feedback_sandbox_unavailable_fallback`（sandbox 失能 worst case）+ 5/24 `feedback_ps5_chinese_encoding_three_layers`（PS 三件套）+ 5/29 `feedback_cross_machine_push_divergence_dance`（divergence dance）三條同類 contingency。共同特徵：0 命中 + 高 impact + 短反應時間 + marginal cost ~30 min + option value 高。**標準明確化**：未來遇到「跨邊界 + 0 命中 + 高 impact」紀律候選直接套模板。
3. **Fetch-first SOP-0 catch 量分布**：1 (5/14 day 2) → 7 (5/19) → 17 (5/24) → **14 (5/29)** = 累計 39 commits 4 次連續 catch。5/29 量 14 略低於預測 (預期 ≥17、實測 -3) — 推測因為 5/24-5/26 user 在 personal-playbook 集中工作 (12 commits gap fill)、5/27-5/29 較分散 (2 commits OpenClaw + 1 cleanup)。**catch 量隨 user 工作密度波動、不需嚴格 exp growth、但 5-7 天 cycle 仍需維持**。

**Cross-ref**: personal-playbook commits `db52ac1` (46th, 5/25 R36 §3.19 SOP 3rd practice + close 5/14 followup #2) + `f9b15de` (5/25 35-45th gap fill + close 33rd §3.20 + 5/14 candidate 2) + `72a77b6` (§3.21) + `073f903` (§3.22+§3.23) + `10868cb`/`fc7639a` (47-48th OpenClaw + cleanup)；本 repo 5/14-5/24 7 commits（`28c1730` / `4698fc8` / `87e92fe` / `2b9dd6d` / `1c1d585` / `816faaa` / `0f15f13`）= **2 個 source case 閉環的 evidence**（§3.10 / SOP-0 fetch-first）；新加 memory `feedback_cross_machine_push_divergence_dance`。

> **2026-06-08 morning audit 補充**：personal-playbook 5/29 → 6/8 跨 **10 天累積 24 個新 commit**（**catch 量首次爆炸**、超過 5-7 天 sustainable cycle、user 已 host fetch+pull 至 `417e5f7`）。**核心發現：第 3 個 source-case-like 閉環浮現** — 我們 5/19 day 3 候選 #1 awareness「plan-first ADR + decision log 三分類」已在 6/2 commit `17ffefe` 升為 **§5.12 + §5.13** 兩條正式紀律（與 5/14 day 1 §3.10 / 5/14 day 2 SOP-0 / 5/19 候選 #1 三條源頭紀律全部 close）。

| Personal-playbook (6/8 audit) | Stroke-order 命中度 / 應用點 |
|---|---|
| 🆕 **§5.13 decision log 三分類升等**（inspection / plan / close 三類、來源 5/19 候選 #1）| **awareness only、不 retrofit** — 本 repo decision log 是「audit-driven 混合」非 production-deploy 場景（W-N + rollback + downtime）；§5.13 設計目的不對應、不適用嚴格三分類。本 repo decision log 既有單一分類保留、不 churn。**第 3 個閉環**：5/19 候選 #1 awareness → 6/2 升等 |
| 🆕 **§5.12 plan-first ADR 必跑 actual state inspect**（不假設「未做」）| **已天然遵循** ✓ — 每 morning audit 第 1 動作 `cat .git/refs/heads/main` + `git log` 純讀本機 state、絕不假設、跟 §5.12 同 spirit |
| 🆕 **§3.14 / §3.20 R60 補強 + R65 / R65.1 / R65.2**（commits `d2a2521` / `c23e1af` / `35bb022` / `17ffefe`）| **R65.1 ssh -t quoting**：不適用（host PS 不跑 ssh）；**R65.2 foreach Get-Item 中文檔名 0-byte quirk**：不適用（`-F` 走 git commit 不過 Get-Item）；**Memory 更新** `feedback_ps5_chinese_encoding_three_layers` 加 R65 補強 awareness 段 |
| 🆕 **§8.41 Service URL / SOP 必寫文件、不靠 conversation memory** | **已天然遵循** ✓ — commit message + journal + decision log + auto-memory 全文件化、不靠 conversation memory |
| 🆕 **§8.42 跨 session 量化 baseline 必驗、不可信 conversation memory** | **已天然遵循** ✓ — cross-validate mount cache、三件套 verify（wc/tail/xxd）每次重驗、不信 conversation memory |
| 🆕 **§8.43 LLM A/B 評分二維分離** | 無關（不做 LLM）|
| 🆕 §3.24 production VM boot system / §3.26 Docker / §3.27 SDK z-order | 無關（無 VM / Docker / SDK）|
| 🆕 **§3.25 SOP 寫作紀律：rollback / abort 命令必須 explicit ⛔ marker** | **目前不適用**（我們 host PS 命令清單無 rollback 命令）；若未來 6z deploy 流程加 rollback 須遵守 |
| 🆕 **§5.14 跨機 silent work 必補 close ADR** | 不適用（本 repo 是 single-machine repo、無跨機 silent work）|
| 🆕 候選 `2d9a84e` 5/31 候選 3「sandbox 不碰 mounted repo .git」（§3.13 同源）| **本 repo §3.10 default-deny 同源 case、是 supporting case 之一** — 若未來升等可能引用本 repo evidence |
| 其他 19 commits（Cyber 3D 地圖 9 / U5M60 U6 ESXi 4 / Yang+Chiu tta 6）| 無關（其他專案）|

**6/8 audit 4 個 reinforcement**：

1. **第 3 個 source-case-like 閉環浮現** — 5/14 day 1 §3.10 → 5/24 §8.40（10 天）+ 5/14 day 2 SOP-0 → 5/25 §3.19（11 天）+ **5/19 候選 #1 awareness → 6/2 §5.12+§5.13（14 天）**。**5/14-5/19 我們提的三條源頭紀律全部 close**、sustained discipline pays 持續實證。
2. **§5.13 三分類不適用本 repo decision log** — §5.13 是 production-deploy 場景（W-N + rollback + downtime + actual state inspect）、本 repo decision log 是 audit-driven 混合（inspection + plan + close 同一檔內共存）。**不超前升等 + 不為「對齊新紀律」churn 既有 decision log** — 與 5/14 day 1 決策 3「不另開 §6.x rule」+ 5/19 day 3 規則 3「不超前升等」一致。
3. **§8.41 / §8.42 已天然遵循、§8.43 無關** — 我們 workflow 自然滿足「文件化」+「baseline 必驗」兩條 senior 紀律、是其 source case 之一。**workflow 設計避坑 > 規則記憶** 規律再次實證（5/19 規則 1）。
4. **跨 10 天 catch 量首次爆炸 24 commits** — 速率 2.4/day（vs 5-7 天 cycle 速率 1.4-3.4）。雖速率仍 manageable、但 catch 總量翻倍推處理時間。**未來 audit cycle 嚴守 5-7 天**、不要拉長到 10+ 天。

**Catch 量分布**：1 (5/14 day 2) → 7 (5/19) → 17 (5/24) → 14 (5/29) → **24 (6/8、跨 10 天)** = 累計 83 commits、6 次連續 catch、SOP-0 fetch-first 6 supporting cases 累積。

**Cross-ref**: personal-playbook commits `17ffefe` (49th, 6/2 大批升 §3.24-3.27 + §5.12-5.13 + §3.20 R65) + `d2a2521` (R60 升等 §3.14/§3.20 + §8.41-43) + `35bb022` (52nd §5.14 + §3.20 R65.1 v3) + `c23e1af` (50th §3.20 R65.1 dogfood) + `2d9a84e` (5/31 候選 3 §3.13 同源) + 其他 19 commits 無關；本 repo 5/14-5/29 9 commits = **3 個 source case 閉環的 evidence**；memory 更新 `feedback_ps5_chinese_encoding_three_layers` 加 R65 補強段。

**設計意義**：

```
Thesis 層（personal-playbook §零 / §8.31-35）
    ↑ rule 為什麼存在
Rule 層（stroke-order PRINCIPLES.md §1-§6 / personal-playbook §一-§八）
    ↑ 怎麼做
Implementation 層（phase decision logs）
```

兩 SoT 互補：personal-playbook 是 **governance backbone**（thesis + meta-rules），stroke-order 是 **engineering rule book**（具體可動的工程規範）。**下次新原則該存哪**：

- 跨專案、含 thesis / meta-pattern / governance discipline → personal-playbook
- 純工程 implementation 經驗 → stroke-order PRINCIPLES.md，必要時 cherry-pick 進 personal-playbook

---

## 8. 跨引擎／降級／前端化原則（2026-07-11 5bt→5ch 新增）

> 單日十輪（塗鴉三引擎前端化＋部首教學路線＋三個實體製造修復）
> 沉澱。詳細脈絡見
> `decisions/2026-07-11_5bt_5ch_doodle_engines_teaching_route.md`。

### 8.1 降級階梯必須配可觀察性

三層降級（Worker → 主執行緒 → 伺服器）讓 OpenCV 引擎 CDN 死連結
潛伏兩輪——主引擎全滅，體驗上「還能用」。fallback 觸發時必須在
UI 可見（狀態列標注引擎與失敗原因）、console 留 warn；「優雅降級」
若無人看見，等於故障被制度化。

### 8.2 外部資源 pin 完必須實測，修好後寫成清單重試

pin CDN 版號是憑記憶寫的（4.10.0 → 實測 404）。規則：任何外部
URL 寫進 code 前先實測 200；單點 pin 一律升級成有序清單重試
（pinned 優先、latest 備援），錯誤訊息帶上實際嘗試的 URL。

### 8.3 改任何預設值，第一動作是 grep 全部測試

5bp 學過（packaged sutras 改變 fixture 前提）、5ch 再犯（contour
成預設 → 兩個舊斷言紅）。機械規則：`grep -r 舊行為關鍵字 tests/`
在動手前做，不是紅燈後做。

### 8.4 瀏覽器可見 ≠ 光柵管線可見

布章字形在瀏覽器「看得到」是反鋸齒的假象——0.003mm 髮絲線進
cairosvg/雷切軟體直接消失。凡描邊元素進 scale transform，必問
「有效 mm 線寬是多少」；驗證用像素級光柵測試（暗像素計數），
不用肉眼看瀏覽器。

### 8.5 幾何演算法：合成形狀測試先行（本日三度救場）

橫條/L 形/圓環/方形這類「答案可手算」的合成案例，在寫演算法
「之前」就寫成測試。實績：骨架追蹤對角冗餘邊（L 形碎 4 段）、
閉環 RDP 退化基線（方形塌縮成空）、centerline 重複段——三個
肉眼幾乎不可見、雷射會多切一刀的 bug 全在第一次執行就被抓。

### 8.6 閉環 RDP 的退化基線陷阱（具體技法）

閉環首尾同點 → RDP 基線長度 0 → 所有點距離 0 → 全環塌縮。
正解：取距起點最遠的點為錨，拆成兩條開放折線分別簡化再接回。
（骨架/輪廓/任何 loop 簡化皆適用。）

### 8.7 像素圖形的對角鄰接要修剪

8-連通骨架/邊界在轉角與階梯處，對角連接與正交路徑並存 → 假交叉
點、重複段。規則：對角邊若存在正交「墊腳石」即為冗餘，建圖時
修剪；配合「邊訪問」而非「點訪問」去重。

### 8.8 沙箱與 Windows 檔案的單向紀律（事故級教訓）

沙箱 bash 寫 mount 會截斷 Windows 權威檔（server.py 事故：斷點
`tr` 恰為合法名稱表達式 → import 不報錯、create_app 靜默回
None → 406 測試同因齊死）。紀律：**改 Windows 檔一律 Edit/Write
檔案工具；沙箱 bash 只讀**；且剛寫完的檔沙箱視圖可能是舊快照，
驗證一律走檔案工具（Grep/Read），沙箱功能驗證用 heredoc 重建
副本。

### 8.9 可插拔註冊表 > 分支 if——一張表吃五輪演進

5ca 的 `DoodleEngines` 註冊表（id/label/available()/render()
統一介面）讓後續 opencv（5cb）、Worker 卸載（5cf）、centerline
（5cg）全是「掛進來」而非「改架構」。與 5bo 的 table-page
renderer registry 同款哲學：**新能力＝新註冊項，零重構**。

### 8.10 使用者的雙盲實測是最高價值測試

1616 個綠燈攔不到「CDN 網址打錯」——只在真實瀏覽器發生。
使用者拿同一張照片跑兩個工具的對照截圖，一次逼出兩個根因
（5ch）。每輪收工訊息應主動給「實機驗收動線」（去哪裡、按
什麼、應該看到什麼），把使用者變成最後一道測試防線。

## 9. 環境層除錯與資源交付原則（2026-07-11 5ck→5cq 新增）

> OpenCV 交付鏈五層根因（死 CDN → 校網靜默丟包 → docs 官網 403
> 擋資料中心 → async def 凍 event loop → 受管理電腦環境層卡大型
> 腳本執行）單日連環揭露的沉澱。詳細脈絡見
> `decisions/2026-07-11_5ck_5cq_opencv_delivery_userfont.md`。

### 9.1 async 框架裡的同步 I/O 是全站級災難

async def 端點內呼叫同步 requests.get，下載 11MB 期間凍的不是
這條請求、是整個 event loop（全站無回應，5ck）。長 I/O 一律
同步 def（框架自動走 threadpool）或背景執行緒；並用
`inspect.iscoroutinefunction` 斷言把「必須同步 def」釘成回歸鎖。

### 9.2 伺服器端與瀏覽器端是兩套 CDN 可用性

docs.opencv.org 在瀏覽器 200、對 Render 資料中心出站卻 403
（bot/UA 防護，5cl）。代理下載的來源要選 hotlink 友善的基礎
設施（jsDelivr/unpkg）；帶版本轉跳的 URL（如 /4.x/）不可入
pin 清單——轉跳目標會漂移到未驗證版本。

### 9.3 worker 的同步 importScripts 是三重黑箱

不可逾時、不可中斷、錯誤不可見——遇到防火牆「靜默丟包」就是
永久懸掛，還會把整條降級階梯凍住（5cm）。凡載入路徑可能經過
防火牆：fetch 先行當「看門狗＋進度回報＋快取暖身」（15s chunk
間隔逾時、MB 進度），importScripts 只在 fetch 成功後讀暖快取
執行，永不裸碰網路（5co 定型）。

### 9.4 10MB 級大字串 eval 行為不穩定，不可依賴

同一字串：inline eval 216ms、引擎內同一行無限 CPU 懸掛、攔截
self.eval 包一層再轉呼叫又恢復——V8 對大字串 eval 的行為依呼叫
情境而異（5co 實測）。大型第三方腳本在 worker 一律
importScripts（見 9.3 的 fetch 前置），eval 只留給小段程式。

### 9.5 降級階梯每一層都要有看門狗

「失敗會往下走」只對「會回報失敗」的層成立；任一層「懸掛」
（而非失敗）就凍住整條階梯（5cm）。renderVia 的進度看門狗
（每則訊息重計時、逾時 terminate → 降級）是階梯的心跳監測；
逾時值以「正常階段間隔 × 10」估（實測 <3s → 30s，5cp 收緊）。

### 9.6 同 bytes、不同執行管道、結果迥異＝環境層嫌疑

opencv.js 在 blob worker 4/4 成功（最快 420ms），同一台機器的
URL worker importScripts／主執行緒 script tag／worker eval 一律
懸掛（5cp 定案）。嫌疑清單：端點防護掃描大型腳本執行、code
cache 寫入、漫遊設定檔配額。**blob worker 是快速對照組**——
十分鐘分辨「程式錯」還是「環境病」。

### 9.7 環境層病灶的正解是換路徑＋失敗記憶，不是繞

每繞一層它換個地方卡（importScripts 卡 → 換 eval 也卡 → 換回
importScripts 還是卡）。正解：把預設路徑換到不受影響的引擎
（伺服器端渲染），失敗記憶（sessionStorage）避免使用者重複
等待，受影響引擎降「實驗性」並在 UI 講明（5cp）。

### 9.8 驗收必須含「無儀器的人工原生測試」

CDP 偵錯器本身是會改變行為的變因（附掛 worker、影響編譯路徑
與時序）。自動化實機驗證（Chrome MCP）之後，永遠補一輪使用者
親手、無偵錯器的原生操作才算驗收完成（5cp 教訓）。

### 9.9 執行期零外網依賴：build-time 燒入

執行期才抓外部資源＝把可用性押在「當下網路」上。vendor 檔於
build 時下載進 git checkout 路徑（非 ephemeral home）、runtime
以同一環境變數指路（5cq，與字型 render_fetch_fonts.sh 同慣例）；
惰性補抓保留當保險。抓檔邏輯復用同一函式（單一事實來源），
不寫平行實作。

### 9.10 badge／統計數字一律抄實跑輸出

「+3 測試」心算成「+4」讓 badge 錯一輪（5cn 事故）。規則：
README badges、commit 訊息的測試數，一律抄全量 pytest 的
實際輸出，不用預期值。

## 10. 架構紅利與功能線原則（2026-07-12 5cr→5cu 新增）

> 自訂字型能力線收束（描紅→機器軌跡→擴模式）＋注音欄開張的
> 單日沉澱。詳細脈絡見
> `decisions/2026-07-12_5cr_5cu_userfont_zhuyin.md`。

### 10.1 分層的價值在第二個消費者出現時兌現

「伺服器管版面、前端管字形」設計時只有字帖一個消費者；擴到
筆記/信紙時發現共用 page.py 渲染器——一處加錨點、多模式生效、
注入器零修改（5ct）。評估分層是否正確，看第二個消費者接上時
要改多少：接近零＝分對了。

### 10.2 語言知識在前端、排版渲染在伺服器

自訂字型（5cn：字型檔不出本機）與注音欄（5cu：zhuyin_map
由前端 pinyin-pro＋規則表算好傳入）同構——伺服器不認識
「字型」「讀音」這些領域概念，只吃排版參數。好處：零新依賴、
零版權/資料風險、破音字修正這類互動留在有 UI 的那端。

### 10.3 fallback 目的地不可與失敗層共享病灶

worker 懸掛的機器，主執行緒直跑同樣懸掛——而主執行緒一凍
timer 全停、看門狗徹底失效＝整頁凍死（5cr，使用者本機伺服器
實測）。降級要跳過「與失敗層同病因」的層，直達確定安全的層
（伺服器端）。§9.5 的補遺正式成條：看門狗只保護還有事件迴圈
的層。

### 10.4 前端幾何出貨前用 node 假 DOM 做座標級驗證

G-code 組裝（5cs）與版面數學（5cu）都在 node 用 stub DOM＋
已知輸入斷言到小數點（flip_y、格位移、ghost 跳過、pair 寬）。
瀏覽器手測看得出「有沒有東西」，看不出「座標對不對」；幾何
錯誤到了雷切/寫字機才爆炸，成本最高。

### 10.5 語言資料用規則生成、不用窮舉；留意標準分岔

拼音→注音是確定性規則（聲母/韻母/整音節表＋jqx+ü 特例，
33 樣本驗證），不需要 400 音節窮舉表。但**讀音標準有兩套**：
pinyin-pro＝大陸體系，台灣以教育部「一字多音審定表」為準
（垃圾/液類字不同）——凡引語言函式庫，先問它的標準是哪套、
與目標受眾的落差在哪，落差表列成行動項。

### 10.6 生態參考的最高價值是「組合技」

IVS 注音字型（開源免商用）餵進自訂字型＋注音欄同紙＝
「看印刷注音、練筆順注音」，零開發成本的新能力（REF 增補）。
讀參考資料時主動找「他們的產出能不能當我們的輸入」——
互補位比競爭位值錢。

---

## 11. 資料源選型與根因再挑戰原則（2026-07-13 5cv→5da 新增）

> 注音 v2 全線收官＋OpenCV「環境層」懸案破案的單日沉澱。
> 詳細脈絡見 `decisions/2026-07-13_5cv_5da_zhuyin_v2_opencv_case.md`。

### 11.1 治本方案的成本假設要用「資料源品質」重新估

推薦 80/20 補丁（衝突字覆寫表）的前提是「換資料源成本高」；
但 McBopomofo 一個高品質開源資料源同時解掉台灣音＋破音字預設
＋v2 UI 資料三個問題，總成本反而低於補丁（5cw）。凡漸進 vs
治本的取捨，先花十分鐘調查治本路上有沒有現成的開源資產——
成本假設過期，推薦就過期。

### 11.2 舊結論要用「新變因 A/B」定期再挑戰

「受管理電腦環境層懸掛」是當時證據下的合理結論，但它有個
未驗的隱含假設：對照組（blob worker「成功」）驗的層級與受測組
相同。5da 用版本 A/B（4.9 vs 4.11 同機同管道）一發擊穿——
真根因是 build 與新版瀏覽器不相容。**結論越「玄」（環境層、
平台特性、不可修），越要保留一個廉價的再挑戰路徑**：換版本、
換機器、換瀏覽器，任何一軸的 A/B 都比接受玄結論便宜。

### 11.3 對照實驗要驗到「與受測組相同的完成層級」

blob worker 當年的「4/4 成功」只驗了 importScripts 返回；真正
的卡點在下一層（WASM runtime init / cv ready）。對照組與受測
組的「成功判準」必須落在同一層級，否則對照只證明了無關緊要
的上游層。同理，5da 實驗鏈每一步都先排除一個變因（校網→
背景節流→腳本執行→WASM 本身）再前進，卡點才會精準。

### 11.4 版本進快取檔名——pin 升級自動失效

無版本檔名（opencv.js）讓 pin 升級後舊快取永遠命中：Render
build 燒入檔、本機 ~/.stroke-order/vendor、瀏覽器 HTTP 快取
三層全中。檔名即版本（opencv-4.11.0.js）＝升級零遷移邏輯、
舊檔閒置無害。所有「pin 版本的落地快取」都適用。

### 11.5 一參數總開關優先於教引擎新概念

page 型注音欄不教 flow 引擎認識 pair cell，而是把 pair 映射成
既有的 `char_width_mm`（×1.5）——換行/分頁/容量全自動正確、
版面引擎零改動（5cz）。改動抽象層之前先找「現有參數的哪個
賦值等價於我要的新概念」；找得到就是零風險路徑。

### 11.6 收集器輸出要自帶語意標籤

`_zhuyin_layout` 的 placements 起初只帶 Character 物件，G-code
註解從物件反推符號名——測試 stand-in 立刻曝露兩者可以不同。
幾何收集器（或任何中間表示）的輸出欄位要把「來源語意」
（原符號字）顯式帶上，不倚賴消費端反推。

### 11.7 對外驗收實驗先固定「分頁可見性」變因

Chrome 對背景分頁有節流/暫停策略，長時間運算（WASM 編譯）的
實驗在 hidden 分頁跑會得到假懸掛。實機實驗第一步：
`document.visibilityState` 檢查＋請使用者把測試分頁切前景；
必要時改標題（🔴 標記）讓使用者認得該切哪個分頁。

---

## 12. 光柵幾何與互動地基原則（2026-07-13 5db→5df-1 新增）

> 雷切線（鏤空字/布章適配）與禪繞互動編輯弧地基的單日沉澱。
> 詳細脈絡見 `decisions/2026-07-13_5db_5df1_laser_zentangle.md`。

### 12.1 快取版本化要涵蓋所有快取層

伺服器落地檔、部署燒入檔、**瀏覽器 HTTP 快取**三層都會押住舊
資源；URL 即瀏覽器快取的鍵，query 就是它的版本欄位。驗證：
裸 URL vs no-store vs 帶 query 三發 fetch 比 bytes。

### 12.2 對偶問題共用管線、只換方向相反的核心步驟

噴漆字（鑿白橋救孤島）與鏤空字（補黑橋連斷件）共用光柵→
拓撲→向量化→三發射器，只差橋接方向；「邊框」建模成一個黑
元件後連筋演算法自動接管，零特例碼。找出對偶結構＝省一半
工程與一半測試。

### 12.3 大畫布光柵拓撲用 run 填色，不用單像素 frontier

frontier flood 迭代數＝區域直徑；「列/行 run 整段填色交替至
不動點」數個 pass 收斂、正確性等價 4-連通。

### 12.4 幾何適配在「消費點」取值，不信 bounding box

bbox 只對滿弦造型成立；在文字列實際高度取造型水平弦（多線
交集＝凸精確/凹保守），大小、間距、位置全跟弦走。新公式做成
舊公式的一般化，退化情境與舊版全等＝金標零回歸。

### 12.5 「方向/朝向」做成資料變換，不做圖樣變體

orientSpecs 單一純函式讓全部圖樣自動獲得四向；朝向存在區段
資料、渲染時疊加容器旋轉角——旋轉相容在資料層解決，UI 只改
一個欄位。N 個圖樣 × 4 向不是 4N 份碼，是 N＋1。

### 12.6 界內測試先行＋掃描死角補遺

「所有輸出座標落區域內」一條測試在 5df-1 三殺（兩隻越界蟲＋
一條釘常數舊斷言）。鐵則：網格迴圈邊界含元素最大外伸半徑、
新圖樣先過界內測試再入 registry；§8.3 的 grep 範圍必須含
tests/*.mjs（node 測試不在沙箱 pytest 預跑範圍＝死角）。

---

## 13. 區段模型與互動編輯原則（2026-07-13 5df-2→5df-4 新增）

> 禪繞互動編輯弧收官（區段模型/隨機填充/點選編輯/自訂切分）
> 的三輪沉澱。詳細脈絡見
> `decisions/2026-07-13_5df2_5df4_zentangle_regions.md`。

### 13.1 新鐵則要追溯掃全體——消費情境變窄，舊蟲現形

鐵則入庫時只約束「新增碼」是半條鐵則：5df-1「邊界含最大外伸」
只掃了六個新圖樣，5df-2 區段窄帶一來，全磚時代藏得住的**五個
舊 builder 全數越界**。新守則入庫＝立刻回掃既有全體；等價地，
既有碼進入更嚴苛的消費情境（大區域→窄帶、寬鬆→精確）前，
先用該情境重跑守則測試。

### 13.2 不規則形狀支援＝「生成吃 bbox、裁剪吃真形」

內容生成器天然吃矩形時，別為不規則形狀改寫生成器：形狀存真形
（poly）、band 同步為其 bbox、生成照舊、渲染 clip 換真形。
成本封在渲染與命中兩個消費點，N 個生成器零改動。

### 13.3 命中判斷與渲染裁剪要同一套語意——用純幾何重刻換可測

「點在形內嗎」別依賴執行環境 API（ctx.isPointInPath）：用與
渲染 clip 同語意的純函式（evenodd 計數）重刻，渲染與 hit-test
成為同一語意的兩個消費者——行為天然一致、node 全測得到。
依賴 DOM API 省下的碼，會在可測性上加倍還回去。

### 13.4 同一輸入多語意＝明確模式狀態＋入口互清

一鍵多義（方向鍵歸朝向還是透視、點擊選取還是切分）用明確狀態
分流，且每個模式入口清掉另一模式的中間狀態——兩套語意永不
同時活著。決策上：撞鍵位這類使用者體驗取捨，前一輪收工時預先
標出、下輪開工一句話定案，零返工。

### 13.5 UI 清單從 registry 動態生成

靜態 HTML 抄 registry 清單＝§8.3 型漂移的 UI 版（radio 只列
3 個、新六圖樣缺席）。改為執行期從 registry 生成、HTML 只留
容器：新項目入 registry 即現身，「registry 改了、UI 忘了」
整類蟲消失。

### 13.6 分裂物件 id＝父後綴族譜

分裂/衍生物件的 id 用父 id＋後綴（r2 → r2a/r2b，可巢狀）：
父移出清單＋後綴巢狀＝天然唯一、免全域計數器、id 即族譜
（除錯一眼看出衍生史）。

---

## 14. 工法規則與互動狀態原則（2026-07-13 5dg→5dh 新增）

> 鏤空字實測修正（轉角截斷/雙連筋）＋禪繞互動大改版（曲線切割/
> 模式保留/縮圖鈕）的沉澱。詳細脈絡見
> `decisions/2026-07-13_5dg_5dh_stencil_zentangle_ux.md`。

### 14.1 約束編進候選集結構，不靠後驗檢查

「直筆中段不截斷」的實作不是切完檢查，而是讓截斷候選＝孔洞
邊界轉角（直線段從不入候選集）——約束由結構保證＝零誤判。
退化情境走明確降級，不是讓主演算法變複雜。領域工法的依據
（實物樣本/教學文）與提煉出的規則一起入 REF，日後可回查。

### 14.2 幾何演算法的隱含假設要跟資料共同演化

資料形狀升級（凸→凹、直線→曲線）時，盤點所有對舊形狀有隱含
假設的演算法——半平面裁剪對凹形**靜默給錯**，不會報錯。
換成適用域更廣的核心（圍籬剖分）、舊 API 降為包裝＝測試全保。
配套：不確定情況顯式拒絕（恰 2 交點守門）＋不變量自檢
（面積守恆），寧可失敗不出怪形。

### 14.3 邊做邊改拓撲的演算法，統計帳記在初始快照上

「這元件有幾條筋」在橋畫上去之後就數不出來（元件融合了）。
進迴圈前拍快照（labels0），歸屬帳記在原生元件上——凡演算法
一邊執行一邊改變連通性/分組，計數與歸屬都要以初始快照為準。

### 14.4 多階段互動＝顯式狀態機，疊發事件在狀態機裡吸收

點-點-調-雙擊這類流程用 phase 欄位顯式建模；dblclick 自帶兩次
click 的疊發，用「該 phase 單擊＝no-op」吸收，不用計時器猜。
高頻 mousemove 重繪一律 rAF 節流。

### 14.5 狀態保留＝失效條件表，不是一律清空

「切換要保留」逼出的正解：每情境各存暫存，逐事件問「這份狀態
的前提還成立嗎」（字形重載→只失效依字形者；座標系變更→全部
失效；使用者顯式清除→清）。圖省事全清的代價是使用者的編輯
成果。

### 14.6 檔位參數連續化；UI 圖示復用生產碼

離散檔位（密度 2 檔）換成連續函數 f(載體尺寸)＝內容自動適配。
參數開口放寬（enum 兼容數值）後立刻養出第二消費者：縮圖直接
跑生產 builder——圖示與實際輸出同源、永不漂移。

---

## 15. 引擎正交、匯出管線與雲端工作階段原則（2026-07-15 5di→5dk 新增）

> 禪繞引擎重構弧的沉澱：把使用者「理念」翻成正交分層、同一 spec
> 管線同時餵渲染與三格式匯出、近似先落地精確後升級、雲端工作
> 階段的跨檔案系統紀律。詳細脈絡見
> `decisions/2026-07-15_5di_5dk_zentangle_export.md`。

### 15.1 理念的結構就是架構的維度

使用者給的常是理念不是規格（禪繞「五基本符號 × 七延伸技法」）。
把理念的乘法結構直接落成程式的正交維度：基本層（registry
category）× 延伸層（吃 spec 回 spec 的純函式）× 資料（per-region
集合）。延伸層與 builder 完全解耦＝既有圖樣一行不改就歸位、新舊
共用同一朝向/渲染。理念裡的「維度」比「清單」更值得保留。

### 15.2 同一管線同時餵渲染與匯出，不另寫幾何

畫面與匯出共用 `build → orient → enhance` 一條管線——看到什麼、
匯出就是什麼（含全部延伸/朝向/參數）。若為匯出在另一語言/層重寫
幾何＝雙軌維護、必然漂移。單一真相源不只省事，是「所見即所得」
正確性的保證。

### 15.3 近似先落地、精確有觸發才升級

先用可測、夠用的近似當輪交付價值（取樣裁切），保留升級路徑；
精確版（evenodd 真裁切）等到有明確觸發（使用者要更精準）才做。
每輪都有可驗收的成果，不為一次到位拖延交付；升級時 API 不變、
測試全保。

### 15.4 能力邊界誠實，不適用就略過或降級

後處理技法對不適用的輸入不硬套：Coffering 只認完整 orb、Sparkle
對 s_shape 首版 no-op（後輪補）、Rounding 端點近似→真三角但直角
不填。每個「做不到／暫不做」在註解誠實標注、留升級路徑，不假裝
全能、不硬塞怪幾何。降級要有可觀察性（狀態列/註記）。

### 15.5 固定管線的順序是規格，要用組合驗證

多個後處理疊成固定管線時，順序本身就是規格——「不炸」不夠，
要防**靜默失效**（Coffering 排在 Sparkle 後會找不到完整 orb、
無聲失效）。用實際多勾組合（不只單技法）跑 E2E，把「先誰後誰」
的依賴寫進回歸鎖。

### 15.6 雲端工作階段＝兩個檔案系統的跨越紀律

雲端沙箱與本機權威檔是兩套 fs，跨越時：①開工 `git reset --hard`
前確認前輪已 push，否則清掉磁碟上未 commit 的工作（留 `/root/out`
副本可還原）②寫回一律 `device_commit_files` ＋ stage 回讀驗證；
uploads 二次 stage 同路徑讀到舊 md5（快取殘影）＝以 stage 回傳
bytes 或新檔名/clone 對照，不信 `device_bash` 讀值 ③`device_bash`
跑 `git status` 會留刪不掉的 `.git/index.lock`；④外部資源以
「使用者網路環境」為準（release 字型資料中心 403＝系統字型代打）；
⑤`收工檢查.bat` 取最高編號 msg——要兩筆分開就分兩輪交付、之間
讓使用者收工一次。

### 15.7 registry／宣告式清單長出多消費者（§14.6 擴大版）

同一份清單餵多個 UI 與邏輯：`TANGLES`→縮圖鈕（跑生產 builder）／
`ENHANCERS`→toggle／`COMBOS`→快捷鈕／`ENHANCER_PARAM_DEFS`→滑桿／
`DXF_LAYER_COLORS`→DXF 層。新增一項＝改一處清單、UI 自動長出、
永不漂移。前端復刻後端格式時（DXF）以既有實作（`dxf.py`）為規格，
逐項對齊勝過各寫各的。

### 15.8 快取破壞要涵蓋整個 ES module graph，不只入口（§11.4 應驗）

`?v=` 只加在入口 `zentangle.js?v=186`、它 `import` 的 `.mjs` 卻是
裸 URL——瀏覽器抓新入口、卻從 HTTP 快取給舊 `.mjs`。版本一旦跨檔
不一致（新入口 import 舊 `enhancers.mjs`、缺 `export flattenSShape`）
→ import 拋錯 → **整個 module graph 死掉**（線上禪繞頁全空白、
canvas 不 render、工具列不長鈕），且沙箱乾淨載入測不出來。修法＝
所有 `.mjs` 之間的 import URL 一律帶同一版本 query（`from
"./x.mjs?v=187"`），版本一動全 graph 一起破快取。§11.4 的「URL 即
快取鍵」要延伸到 import graph 的每一條邊，不只 `<script>` 那一行。
（node ESM 容許 import specifier 帶 query、以路徑解析檔案，測試不受
影響。）教訓：跨檔快取偏移只在「線上舊快取＋新部署」交會時現形，
純沙箱／硬重整都測不到——版本化要一次涵蓋整個相依圖。

## 16. 字型即根因、範本學技法、軸向近牆橋接（2026-07-15 5dm 新增）

> 使用者拿競品（竹米 STENCIL＝Google Noto 黑體）與範本字（方正大黑
> 連筋）要求「參考修正」字模。三個沉澱：字模品質的根因在字型不在
> 演算法、參考商用範本＝學切割技法非照搬（授權判斷交還使用者）、
> 連筋橋接要軸向對齊且只穿近牆。

### 16.1 字模品質的根因是字型，不是演算法（先挑對要修的層）

橋接/連筋演算法已在 5dg~5dl 反覆打磨，但字模仍破字——根因其實在
**字型**：楷書筆畫收筆帶尖、粗細對比大（沙箱實測「明圖界」筆寬
中位數 ≈6px、第 5 百分位 ≈6px＝滿是易斷細筆），黑體筆畫均勻粗
（中位數 ≈20–24px、最細 ≈14–22px），橋接落在厚壁上就不破。**先量
測再改**：把楷書 vs 黑體光柵化量筆寬，用數據確認「換字型」是根因
修正、勝過在錯的層（演算法）繼續打磨。辨析近義層也要用數據——
宋體/明體不是黑體（橫細直粗＋襯線，最細處一樣脆），別因名字接近
就當同一解。授權面外加紅利：Noto/思源黑體 OFL 1.1 是全專案最寬鬆
（可商用/可打包/可改作），比既有 CC BY-ND 字型更適合打包進部署。

### 16.2 參考商用範本＝學切割技法，不照搬字型（授權判斷交還使用者）

使用者上傳方正大黑連筋當範本要「保留字體特徵」——但它是方正商用
字型（FZDaHei-B02，Founder 版權），打包進公開部署＋開源專案有實際
訴訟風險。「參考」的正解是**學它的切割技法**（交接角內縮橫筆、留
逃逸缺口、保主幹豎筆），套在已核准的 OFL 黑體上：零授權風險、且
通用於範本沒連好的複雜字（實測方正大黑自己在圖/圓/國 也留 3~5 個
未連 counter）。授權是使用者權責，Claude 誠實標出風險、以 QODA 給
「模仿技法／直接用字／混合」三選項，等使用者拍板才動手，不替他
決定用不用商用字。範本的價值是「怎麼切」的美學，不是那個檔案本身。

### 16.3 連筋橋接：純軸向對齊、且只穿「近牆」

複製方正連筋的兩條幾何鐵則：①**純軸向**——逃逸方向限上/下/左/右
四方，缺口成乾淨矩形（像被內縮的筆畫端），取代 ±70° 斜向扇形
（斜橋在複雜字如「圖」會糊成一團蜘蛛網）。②**只穿近牆**——放射
逃逸會穿越孔洞空腔、把對側遠牆當穿牆點，於是對邊兩轉角撞同一面
牆併成一橋（大孔只剩單橋、不穩）；判定「往內 2px 仍是墨」才算
近牆方向，逼橋接鑿在轉角旁的近牆＝方正「筆畫在交接處內縮」的
本質。驗證用**拓撲不變量**（鑿橋後 `~mask & ~outside` 殘孔＝0＝
每個 counter 都連回板、無孤島掉落）＋合成環的截口數（大孔恰 2、
小孔 1），比目視穩。cutout 模式在黑體上本已乾淨（連框確實），此
輪只動 stencil 橋接——**改最小範圍、已好的不碰**。

---

## 7. 索引

- 工作日誌：
  - [`2026-05-04_05_session_log_r28-r29k.md`](journal/2026-05-04_05_session_log_r28-r29k.md)
  - [`2026-05-06_session_log.md`](journal/2026-05-06_session_log.md)
  - [`WORK_LOG_2026-07-11.md`](WORK_LOG_2026-07-11.md)（5bt→5cq
    全日兩弧十七輪＋救援全記錄，含雙收官總結）
  - [`WORK_LOG_2026-07-12.md`](WORK_LOG_2026-07-12.md)（5cr→5cu
    自訂字型全能力線＋注音欄＋REF IVS 增補）
  - [`WORK_LOG_2026-07-13.md`](WORK_LOG_2026-07-13.md)（5cv→5dh
    全日五弧：注音 v2 全收官＋OpenCV 4.11 破案＋雷切線＋禪繞
    互動編輯弧＋鏤空字實測修正＋互動大改版）
  - [`WORK_LOG_2026-07-15.md`](WORK_LOG_2026-07-15.md)（5di→5dk
    禪繞引擎重構弧：iCSO 五基本符號＋七延伸技法＋參數/組合＋
    SVG/G-code/DXF 匯出＋evenodd 真裁切＋雷雕掃描填充；雲端工作階段）
- 決策紀錄：
  - [`2026-05-05_phase5b_r28-r29k_summary.md`](decisions/2026-05-05_phase5b_r28-r29k_summary.md)（5/4-5/5 跨 phase 總覽）
  - [`2026-05-06_phase6z_design_spike.md`](decisions/2026-05-06_phase6z_design_spike.md)（phase 6z spike）
  - [`2026-07-11_5bo_educational_category.md`](decisions/2026-07-11_5bo_educational_category.md)（科普教育分類）
  - [`2026-07-11_5ck_5cq_opencv_delivery_userfont.md`](decisions/2026-07-11_5ck_5cq_opencv_delivery_userfont.md)（OpenCV 交付鏈五層根因＋自訂字型，對應 §9）
  - [`2026-07-12_5cr_5cu_userfont_zhuyin.md`](decisions/2026-07-12_5cr_5cu_userfont_zhuyin.md)（自訂字型全能力線＋注音欄，對應 §10）
  - [`2026-07-13_5cv_5da_zhuyin_v2_opencv_case.md`](decisions/2026-07-13_5cv_5da_zhuyin_v2_opencv_case.md)（注音 v2 全線＋OpenCV 懸案破案，對應 §11）
  - [`2026-07-13_5db_5df1_laser_zentangle.md`](decisions/2026-07-13_5db_5df1_laser_zentangle.md)（第二弧：雷切線＋禪繞地基，對應 §12）
  - [`2026-07-13_5df2_5df4_zentangle_regions.md`](decisions/2026-07-13_5df2_5df4_zentangle_regions.md)（第三弧：禪繞區段模型/互動編輯/切分線，對應 §13）
  - [`2026-07-13_5dg_5dh_stencil_zentangle_ux.md`](decisions/2026-07-13_5dg_5dh_stencil_zentangle_ux.md)（第四弧：鏤空字實測修正＋禪繞互動大改版，對應 §14）
  - [`2026-07-15_5di_5dk_zentangle_export.md`](decisions/2026-07-15_5di_5dk_zentangle_export.md)（禪繞引擎重構弧：互動修正＋iCSO 引擎＋SVG/G-code/DXF 匯出，對應 §15）
  - [`2026-07-11_5bt_5ch_doodle_engines_teaching_route.md`](decisions/2026-07-11_5bt_5ch_doodle_engines_teaching_route.md)（**塗鴉引擎體系 × 教學路線，全日 QODA 重放**）
  - 各 phase 詳細：`docs/decisions/2026-05-0[456]_phase*.md`
- Personal-playbook cross-link：
  - `2026-05-06_r29-r29k_principles.md`（在 personal-playbook repo，跨 ref 案例 §B.15-B.23）
- 已存 memory：`/sessions/friendly-dreamy-noether/mnt/.auto-memory/MEMORY.md`

---

**寫這份的目的**：把跨 phase 浮現的「不只此一處適用」工程習慣固化下來。下次新 phase 開動前可快速 scan 一遍 — 「我這次該套用哪幾條？」比每次重發明強。

§1-5 是 **implementation-time** 原則（寫 code 時）；§6 是 **design-time** 原則（把願景轉 spec 時）；§8-§15 是 **runtime/整合** 原則（降級、外部資源、跨環境檔案、實機驗收、資料源選型、根因再挑戰、區段模型與互動編輯、工法規則與互動狀態、引擎正交與匯出管線與雲端工作階段）。三者互補。
