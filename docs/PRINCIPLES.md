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

## 17. 主體字型為準、語義正確補足缺字（2026-07-15 5dn 新增）

崇羲篆書＝台灣繁體篆書，繁體覆蓋近乎完整（教育部常用字 4808 只真缺
~8 罕見字），缺口約 1500 字**幾乎全是簡體**。使用者要「以崇羲為主體、
補充不足」。

### 17.1 先量清楚「缺什麼」再決定「怎麼補」

比較兩顆篆書時，一開始「崇羲缺 1500 常用字、方正可補 99%」看似崇羲
不足；深挖才發現缺的**全是簡體**、崇羲的繁體其實近乎完整——結論從
「換/加字型」翻轉成「只補簡體那一塊」。缺口的**組成**（簡/繁/罕見）
比缺口的**數量**更決定方案。量測要拆到能翻轉判斷的粒度。

### 17.2 補足選語義正確、授權乾淨的路

三方案：方正小篆（真簡體篆形，但 Founder 商用授權、部署有雷）／
簡轉繁 opencc（繁體篆形，零新字型、授權乾淨）／混合。選 opencc——
**篆書本來就用繁體/古形，「簡體篆書」是現代產物，簡轉繁在篆書語境
反而更正確**；且 opencc 已是專案既有依賴（繁↔簡 fallback），零新增。
授權與語義同時乾淨的方案，勝過「覆蓋最完整但帶授權雷」的方案。

### 17.3 fallback 保留「主體」語義與輸入身份

以崇羲為主體＝**原字先試**（繁體直接命中），只有崇羲缺才簡轉繁；
渲染用繁體字形，但 `Character.char` 記使用者**原本輸入**的簡體
（least surprise）。轉換限「恰一字且有變化」才觸發；opencc 缺套件
即靜默降級（同字型未裝即降級的容錯策略）。實測救回崇羲 99% 缺字。

## 18. 依墨置中、量對旋鈕再實作、轉換鏈補足（2026-07-15 5do 新增）

抄經佛經缺字補足＋鏤空字置中＋噴漆字平順化三修的沉澱。

### 18.1 CJK 字模置中要依「實際墨邊界」，不靠字型 baseline

思源黑體漢字墨在 em 框內落 y 705..2574 / 2048（**溢出下緣**），靠
`oy=margin`＋em 框排版會讓字沉底貼下框、甚至裁切。正解：算所有字形的
**實際墨 y-範圍**、把它置於上下等距的邊界內、畫布高隨墨自適應。字型
的 ascender/baseline metrics 對「視覺置中」會說謊，量墨最實。

### 18.2 平順化：先量哪個旋鈕有效，別造無效機制

要去噴漆字輪廓的階梯微凸/微凹，我第一版寫了個「軸向吸附 _dejag」，
**量測後發現它對單位步階階梯是 no-op**（頂點數 83→83，與純 RDP 相同）
——真正有效的旋鈕是**細化光柵（4→8px/mm）＋放大 RDP 容差**
（1.2→2.0px≈0.25mm）。教訓：加機制前先量它到底有沒有動到指標；
既有工具（RDP）調對參數常勝過另造新機制（§避免過度工程）。刪掉無效
的 _dejag、留 px_per_mm＋eps 兩個真旋鈕。

### 18.3 缺字補足是「轉換鏈」，罕見字誠實維持缺字

5dn 的「簡轉繁」5do 延伸成鏈：崇羲 → s2t（簡體）→ s2tw / t2tw
（異體字正規化）→ 崇羲，救回爲→為、衆→眾、卻、兌 等異體。但核心
佛經崇羲本已覆蓋 97–99%，剩下的是**真正罕見佛字**（閦毘鉢憍耨＝
音譯梵字），**任何轉換都救不回**——依使用者決策**維持缺字並清楚
提示**，不為補幾個字引入商用字型。轉換鏈能補的是「異寫」，補不了
「異字」；後者要嘛換授權有雷的字，要嘛誠實留白。

## 19. 重端點：sync def ＋ per-位置 loader 記憶化（2026-07-15 5dp 新增）

線上抄經「產生預覽」回 HTTP 502。本機量測：一頁心經（260 字位）純字形
載入 ~十幾秒。兩個複合根因，各對一條鐵則：

### 19.1 重活端點一律 sync def，別放 async def（§9/5ck 再驗）

`sutra_post` 是 `async def`、內跑十幾秒的同步字形載入＋SVG 渲染——**凍住
單一 event loop**，Render 單 worker 期間無法回健康檢查/其他請求 → 逾時
502。改 `def`（FastAPI 自動丟 threadpool、不凍 loop；stencil 端點早已此
策略）。判準：**端點內有 CPU 密集/阻塞工作 → sync def**；只有 I/O
await 才用 async def。（改 sync 前先確認 body 內無 `await`；本例 `sutra_
get` 原 `return await sutra_post` 要改成直接呼叫。）

### 19.2 per-位置 callback 要記憶化——同輸入別重算

渲染器對**每個字位**呼叫 `char_loader(ch)`（一頁 260 位、117 唯一），
而 `_load` 不快取——重複字每位重載。加一層 per-request 記憶化（dict
cache）「每唯一字只載一次」，預覽 ~15s→2~3s、PDF 多頁跨頁重複字省更多。
判準：**回呼被同一輸入反覆呼叫、且解析昂貴 → 記憶化**。安全前提＝結果
唯讀（渲染器不改 Character）；已驗記憶化前後**逐位元相同輸出**。教訓：
效能問題先量「呼叫次數 × 單次成本」拆兩軸，本例砍的是「次數」（去重），
不是「單次成本」。

## 20. 昂貴工廠要跨呼叫快取，但可變狀態要能失效（2026-07-15 5dq 新增）

元素週期表改「只留週期表形狀」後暴露一個效能舊帳：一頁 118 罕見字光
字形載入 ~31s → Render 逾時 502。§19.2 砍的是「單次請求內的重複次數」；
這裡的根因在**更上一層**——`_load` 每次呼叫都 `make_source(source)` 建
**全新** `AutoSource`（含全新 `MMHSource` 重解 9500 行 ~20s、全新
`MoeKaishuSource` 重讀 CFF glyphset ~9s），把各字源的 per-instance 快取
整個丟掉重建。

### 20.1 同名昂貴工廠在 process 內只建一次

`make_source` 加 `_SOURCE_CACHE`（同名字源建一次、跨請求重用），呼應既
有 `get_kaishu_source` 等 singleton 的設計意圖。118 字載入 31s→~3s。判準：
**工廠產物「昂貴建置＋語意上無狀態/唯讀」→ 快取重用**；未知名稱走
`_build_source` 拋 `ValueError`（不進快取，錯誤不被記住）。

### 20.2 快取「可變」資源，寫入端一定要主動失效

`AutoSource` 內含 `UserDictSource`——使用者字庫**可在執行期被寫改**。加
了 §20.1 快取後，`user_dict_post/delete/import` 三個寫入端點若不清快取，
已建的 `AutoSource` 就讀不到新寫入/已刪的字（回歸測
`test_api_user_dict_override_visible_in_notebook`：POST 一個 2 畫的字後
GET notebook 竟仍回 1 畫）。修法：寫入成功後呼叫 `reset_source_cache()`。
鐵則：**引入任何快取，同時要盤點「誰會讓底層資料變」並在那裡失效**；
快取與失效是一組、不可只做一半（cache-and-invalidate 成對）。

## 21. 目錄 ready-gating：只列當下真正可用的 preset（2026-07-15 5dr 新增）

麥克阿瑟為子祈禱文因通行中譯本著作權未確認，repo 刻意不打包正文（§5bp/
SOURCES.md）；但 preset metadata 仍在，於是它以 `ready=false` 出現在抄經
目錄，選了卻算不出東西——「列出但報錯」是最糟的 UX。

修法（前端一行）：目錄過濾掉「內建但正文未打包」的 preset
（`p.is_builtin && !p.ready`）。這同時滿足兩個相反需求且自我修復：線上
部署無正文→隱藏；使用者在本機 `~/.stroke-order/sutras/builtin/` 放入正文
→ `ready` 翻真 → 自動出現（已 Playwright 雙向驗證：無正文 54 項不含它、
有正文 55 項含「✓ 麥克阿瑟為子祈禱文」）。

鐵則：**選單只呈現使用者「當下真的能用」的選項**——環境/授權缺件的項目
用「不列出」而非「列出後報錯」處理；且用 `ready` 這類既有狀態旗標一般化，
不硬寫特定 key（macarthur 只是目前唯一命中者，規則本身通用）。著作權排除
與否是資料層決定，UI 只忠實反映當下可用狀態，兩者解耦。

## 22. 描紅表格頁重用米字格語彙；視覺版面先 mockup 再實作（2026-07-15 5ds 新增）

元素週期表原 render_periodic_table_page 走「化學參考卡」風（原子序＋
英文符號＋分類底色＋圖例），與抄經米字格格格不入。使用者要的是「維持
抄經表格樣式、只排週期表文字」。兩條原則：

### 22.1 描紅/表格頁沿用抄經共用的米字格語彙，不各自造格

改繪時直接 import sutra.py 既有常數（GRID_LINE_COLOR/WIDTH、
HELPER_LINE_COLOR/WIDTH/DASH）與 _char_cut_paths/_render_skeleton_glyph
描紅管線，格子外觀與抄經本體逐像素一致。判準：**同一產品的多種頁型該共用
視覺語彙（顏色/線寬/助線/描紅），用共享常數而非各頁重定義**——風格一致
且改一處全改。座標排列（哪格放哪個元素）是資料，樣式（怎麼畫格）是共用元件，
兩者分離。

### 22.2 視覺版面：先出 mockup 圖、由用戶確認，再接正式管線

版面類需求（週期表排列、空格規則、鑭系/錒系抽出、標題/標記取捨）字面
易懂、細節多歧義。作法：先寫獨立 script 產 SVG→PNG 給用戶看，QODA 只問
真正分歧的一兩點（此例：標題與系標記去留），確認後才改正式 exporter＋
翻既有測試。省下「猜錯版面→重做」的來回。順帶修正使用者口誤（砝→鍅，Fr
的臺灣譯名）並明講。

## 23. 互動地基：伺服器發 data-* 標記，前端只掛事件；重用既有存儲（2026-07-15 5dt 新增）

抄經「逐字手寫」需求（點預覽的字→彈窗手寫→存本機→取代描紅→上/下字）
看似大，實作卻小——因為八成後端已存在：罕用字管理的手寫畫布、
`POST /api/user-dict`、匯出/匯入、以及 AutoSource「user_dict 最優先」使手寫
自動覆蓋描紅。新做的只是把這些接起來。三條原則：

### 23.1 讓元素可互動，靠伺服器發 data-* 座標標記，不要前端反推

抄經頁的字格座標（方向/邊界/cell 大小/直書欄序）伺服器最清楚。要讓前端
能點字，做法是伺服器多發一層**透明 click-map**（`<g id="sutra-cellmap">`
內每格一個 `fill="transparent"` 的 rect，帶 `data-char`/`data-pos`），前端
只 querySelectorAll 掛事件即可——不必用 viewBox 反算像素位置（脆弱、隨版面
規則漂移）。字帖模式的 `data-char` 早有先例，這是同一手法延伸到抄經。
（`fill="transparent"` 才收得到點擊；`fill="none"` 不會。）

### 23.2 預覽專用互動層用旗標與下載/PDF 分流

click-map 只對瀏覽器預覽有意義。加 `emit_cellmap` 參數（預設 False），只有
預覽端點傳 True；SVG 下載、PDF 皆維持 False——plotter/PDF 輸出不被無意義的
透明 rect 汙染。原則：**預覽專屬的裝飾/互動，用旗標與「給機器的輸出」分流、
預設關**。

### 23.3 新功能優先重用既有存儲與元件，別另造平行系統

「送出的字存本機、可下載匯入、分段完成」全部落在既有 user-dict（本機檔＋
export/import）上，不另建儲存；連手寫覆蓋描紅都是 user_dict 既有的最優先
語意免費得來。彈窗雖新做（要上/下字導覽與範字），但畫布捕捉、送出格式、
存取端點都沿用。判準：**先問「這需求能不能掛在既有子系統上」，能就別造
第二套**——否則兩套資料要同步、維護加倍。

## 24. 變體版面：把資料塞進原頁型，別複刻格線（2026-07-15 5du 新增）

元素週期表歷經三版：5ds 我**複刻**了一套米字格（只在有元素處畫格）；使用者
回饋「請維持原有抄經模式的表格樣式，用一張空白抄經紙也能寫下週期表，空格
空行也是原味」。5du 改成**直接重用 `render_sutra_page`**：把 118 個元素名
放進標準抄經格的對應格位（`direction="horizontal"` 時 `n = row*cols+col`，
座標由 `_cell_of` 換算），其餘格子留白。結果自動獲得完整米字格＋日期/抄寫者
表頭＋外框，與其他抄經頁**逐像素同源**，且程式碼從一大坨自繪縮成建一個
定位字表＋一次呼叫。

鐵則：**當變體只是「同一頁型、換內容排列」，優先「把資料塞進原渲染器」，
不要複刻它的格線/表頭/外框**。複刻會漂移（§22.1 的共用語彙問題）、且把
「排版」與「內容定位」黏死；重用則讓變體天生跟本體一致，改本體全體受惠。
教訓：5ds 一度往「自繪版面」走，是因為誤把需求當成「畫一張週期表圖」；
其實需求是「在抄經紙上定位文字」——**先辨清是新頁型還是原頁型換內容**。

## 25. 渲染層的視覺參數是為某來源調的；新來源同形不同義要分流（2026-07-15 5dv 新增）

逐字手寫送出後格子看起來空白。根因：使用者手寫是 centerline（raw_track、
無 outline），在 render_sutra_page 落入「隸/篆 骨架層」——那層的 opacity
被刻意調到 0.03（§5cb，因為 隸/篆 centerline trace 不完美、不想干擾使用
者）。手寫套進同一層 → 幾乎不可見。

修法：依 `data_source` 分流。手寫（data_source 以 "user" 開頭）走新的
`sutra-trace-user` 可見層（opacity 0.9），隸/篆保留 0.03。判準：**同一段
渲染程式的視覺參數（opacity/顏色/線寬）常是為「某個特定來源」調的；當新
來源產出相同形狀（皆 centerline）但語意不同（要可見 vs 要淡出）時，用
data_source 分兩條 lane，別硬塞進既有 lane**——否則新來源被套上不屬於它
的視覺假設。教訓：加功能（5dt 逐字手寫）時只驗到「有沒有存進 user-dict」，
沒驗「存了之後在預覽長什麼樣」——**端到端要驗到使用者實際看到的那一格**，
不是只驗資料寫入。

（本輪另含兩個純參數調整：逐字彈窗按鈕重排——復原/清空疊畫布左上、
上/下字/略過移畫布右側、彈窗加寬容納右欄；元素週期表版面下移 3 列、右移
1 欄，左右各留 1 空欄。皆 offset 常數／CSS，無架構變動。）

---

## 26. registry dispatch 用能力偵測、別寫死 preset；重用紅利在第 N 個消費者兌現（2026-07-17 5dw 新增）

把逐字手寫（5dt）從抄經內文頁延伸到元素週期表頁，實作只有兩處、且沒有
任何新機制——這兩件事各自是一條原則。

**① 缺口是「單一未轉發的旗標」，靠端到端追資料契約才抓到。** 前端其實
早就對表格頁送 `emit_cellmap:true` 並無條件呼叫 `swAttachPreviewClicks`
（點擊接線本來就通用）；`render_sutra_page` 也早就會吐 `#sutra-cellmap`
（horizontal 方向照樣發 data-char）。唯一斷點：server.py 的 `page_type
== "table"` 分支呼叫 table renderer 時**沒把 `emit_cellmap` 傳下去**，
而 body 分支有。判準：**功能「幾乎會動但沒動」時，沿著資料契約從產生端
到消費端逐段走，斷點常是某一段沒把既有參數往下傳**——不是缺機制，是缺
一條線。

**② registry 分派要「能力偵測」，不要寫死 preset 名。** `_table_page_
renderer` 是六個簽名互異的 renderer 註冊表（週期表重用 render_sutra_page、
其餘自繪、乘法表/節氣每格還是多字詞）。要把 `emit_cellmap` 只餵給吃得下
的 renderer，寫法用 `inspect.signature(fn).parameters` 偵測——能就傳、
不能就跳過。**好處：未來任何新的單字表 renderer 只要在簽名加上 `emit_
cellmap` 就自動參與，不必回頭改 server；自繪多字表則零影響。** 反例是
`if preset == "periodic_table"`：每加一張表就要回來補一個 if，且把「誰
支援」的知識從 renderer 自身外洩到分派點。判準：**當一個共用分派點要對
異質實作傳選配能力，用簽名/介面偵測讓實作自行 opt-in，別在分派點維護一
份會過期的 preset 白名單。**

**③ 重用決策會複利，紅利在第 N 個消費者兌現。** 這次之所以只花兩行，
正因為 5du（§24）先前把週期表改成「重用 render_sutra_page、別複刻格線」
——所以週期表天生就是一張單字米字格頁，cellmap 機制原封不動就套上了。
**「重用勝於自造」的省力常不在當下、而在後續某個功能免費落地時才結清**；
每次選重用，都是在替未來的自己預存紅利。（承 §23.3／§24；同一機制第三度
兌現：cellmap 收集器 → 抄經內文頁 → 週期表頁。）

驗收照 §25：沙箱起 uvicorn + Playwright 走真 UI（選週期表→到表格頁→真
sutraRender→118 個 cellmap rect→點「氫」→逐字手寫彈窗開、顯示「第 1/118
字・目前：氫」），截圖目視到「使用者實際看到的那一格」，不是只驗 API 回傳。
（沙箱網路擋遠端字形源、118 罕用字載入吃 503，用 null loader 打樁——正好
是罕用字無筆順＝data-missing 的真實手寫場景，cellmap 不依賴字形載入成功。）

---

## 27. 跨層契約要單一真相源：N 個產生端別各持一份會漂移的複本（2026-07-17 5dx 新增）

把逐字手寫再延伸到部首/倉頡/注音三張表時，落地免費——這正是 §26②③ 的
複利兌現：server 的能力偵測讓三個 renderer 簽名長出 emit_cellmap 就自動
被餵旗標、前端契約不變。真正的新教訓在「怎麼讓三個自繪 renderer 吐出同一
個疊層」。

這三個 renderer 各自自繪版面（不重用 render_sutra_page），要吐的
`#sutra-cellmap rect` 格式必須與抄經頁**逐字節一致**——因為前端 parser
（swAttachPreviewClicks）只認 `#sutra-cellmap rect[data-char]` 這個確切
結構（含 data-pos 讀序、data-missing 缺字標記）。**當 N 個產生端要吐同一個
「由別層 parser 消費」的字串契約，把產生那段抽成一個共用 emitter，別讓每個
產生端各持一份複本。** 這裡抽出 `cellmap_rect()`＋`cellmap_group()` 單一
真相源，連 render_sutra_page 原本內嵌那段也改用（零行為變化、既有測試綠
證）——契約要改時一處改、全體生效，parser 端永遠不會突然對不上。反例是
「每個 renderer 各自 f-string 拼 rect」：4 份複本，任一處欄位漂移（少個
data-pos、escape 規則不同）都讓前端悄悄接不到、且很難一眼看出是哪份漂了。

配套一個語意邊界：cellmap 只對**可寫格**發 rect。倉頡/注音左側的分類標籤帶
（哲理類/聲母…）不是可寫字格，要跳過——否則「哲」「聲」等標籤字會變成可點
手寫格。測試明確斷言標籤字不出現在 cellmap。判準：**共用 emitter 解決「格式
統一」，但「哪些格該進 cellmap」是每個頁型自己的語意，要在呼叫端界定清楚。**

---

## 28. 宣告式 registry：先「純重構立 seam」一個 commit、再沿 seam 加功能（2026-07-18 5ef 新增）

要把散落的參數（函式引數、模組常數）收斂成宣告式 registry、且接下來會長出
多個變體時，把「搬家」和「加新演算法」拆成**兩個 commit**：先做純重構、行為
逐位元保存（既有測試全綠即證），再引入第一個真正的新行為。5ef 先立
`CuttingStyle`＋`CUTTING_STYLES` seam（只有 1 entry、全連派、殘腔 0，與重構前
逐位元相同），5eg 才引入 envelope 第二風格；之後 5ei/5ej/5eo 四個功能都沿同
一 seam 乾淨長出、每個都是小 diff。

判準：**registry 只有 1 entry 常被當成 YAGNI 警訊——但當第二消費者「已規劃」
（文件藍圖／使用者點名／已設計），它就從臆測變已規劃，值得先立。關鍵是拆
commit：一旦沿 seam 的新演算法出錯，純重構那個 commit 讓你能一眼排除「是不是
搬家搬壞的」。** 反面：重構與新演算法混一個 diff，鏤空幾何一錯就分不清病灶。

---

## 29. 單一連通 blob 上的局部幾何量測會 leak：巢狀深度用 Jordan 最小穿牆、別用形態學層剝（2026-07-18 5eg／R1 dead-end 新增）

要問「這個孔被幾層墨包住」（巢狀深度），對**單一連通 blob**（漢字墨跡幾乎
總是）要用 Jordan 曲線定理：從孔往外射四條軸向射線，被 d 層 loop 包住的孔
任一射線至少穿 d 次牆，**最小**的那個方向恰等於 d（`_hole_depths`）。**不要**
用形態學層剝（erode 幾次到消失）——層剝量的是「到 blob 邊界的距離」，不是
「包覆層數」，在單一 blob 上會給出完全錯的深度。

同一弧的反面教材：完整 R1（keep_primary=structural）試圖在交接處量筆畫的
垂直 run 長度來判主幹，沙箱實測切掉了長橫主幹——因為 run 會 **blob-leak** 進
相連筆畫，量到的是墨團尺寸不是單根筆畫長度，退化成長寬比。已 revert、未提交。

判準：**在單一連通 blob 上做任何局部幾何量測前，先問「這個量測會不會漏進
相連的結構」。孔巢狀深度有 Jordan 全域解；筆畫級量測（主幹判定）繞不開骨架
切分——若骨架太貴（dense 字形 OOM），就別假裝局部量測能替代它。**

---

## 30. 切割方向↔牆是對偶：「保某方向筆畫」＝「懲罰切它的射線」，可調量放 runtime 旋鈕別放身份欄位（2026-07-18 5ei/5ej/5eo 新增）

鏤空切割的射線方向與它切斷的牆**正交**——水平射線切的是豎筆、垂直射線切的是
橫筆。所以要「直豎筆別從中切」不需要偵測每根筆畫在哪（那要骨架，見 §29），
只需在逃逸評分 `_escape_score` 裡對「切豎筆的方向＝水平射線」加懲罰
（BIAS 1.6）。5eo 把 physical 也統一成此 `vertical_first`。連框方向同理：
5eo 每個 component 連最近框邊＋一根 90° 垂直方向第二 spoke，破解「連框線全同
方向」。

配套：**可調量（連筋深度 envelope_depth）是 runtime 旋鈕、不是 style 欄位。**
CuttingStyle 定義風格身份（envelope vs physical），深度是使用者當下旋鈕值——
塞進身份欄位會逼出 envelope-1／envelope-2… 一堆偽風格。runtime 參數覆蓋風格
預設才是正交分解。

判準：**方向性幾何操作，先找「操作方向 ↔ 受影響對象」的對偶，用加權啟發式
取代顯式偵測；把「風格是誰」與「使用者當下調到多少」分成宣告欄位 vs runtime
參數兩個正交軸。**

---

## 31. 同源演算法有多消費點：改進要一次套齊，帶快取的消費點 tuning 參數必須進 cache key（2026-07-18 5eh/5ek/5el/5em 新增）

一個平滑/簡化演算法（Chaikin、RDP）常有多個等價消費點——骨架描紅（5ed）、
塗鴉中心線、字帖自訂字型 grid。改進要**一次套齊所有消費點**否則體驗分裂；
把強度開成 UI 旋鈕時，塗鴉與字帖要**對稱**（都給平滑＋簡化）。踩到的坑：
`fontCharTracks` 有記憶化快取，**cache key 必須併入 tuning 參數（iters+eps）**，
否則使用者調旋鈕會拿到舊軌跡（快取沒失效）——這是 §15.8「快取破壞要涵蓋整個
依賴圖」在使用者可調參數上的再驗。（純 JS 靜態檔改動記得 bump `?v=` 三處
lockstep，§15.8／收工陷阱；只改 index.html 主頁免 bump。）

判準：**同源演算法改進要枚舉所有消費點一次套齊；任何「輸入→快取→輸出」的
消費點，凡會影響輸出的 tuning 參數都必須是 cache key 的一部分，否則旋鈕失效
於快取。**

---

## 32. 要顯示 styled 字形而瀏覽器無該字型時，reuse 伺服器已渲進預覽的 SVG 字形、別 canvas fillText（2026-07-18 5en 新增）

逐字手寫範字要顯示篆/隸字形，但這些字形是**伺服器渲染的 SVG**、瀏覽器本地
沒有這些字型——`ctx.fillText` 只會落回系統 sans/楷。正解：伺服器早已把正確
字形渲進抄經預覽 SVG 了，前端 reuse 它——`swBuildRefImg` clone 範字圖層
（glyph-reference/trace/trace-skeleton，**排除** user/marks/cellmap）、裁到
該格 cellmap rect bbox、recolor、載成 Image 疊在 canvas。缺字→範字空白（誠實）。

判準：**當前端要呈現一個「只有伺服器有正確字型/渲染能力」的 styled 字形，
第一選擇是 reuse 伺服器已經渲染進頁面某處的那份 SVG（clone＋裁＋recolor），
不要在前端用系統字型硬畫（只會出系統楷/黑）。**

---

## 33. 修「JS 讀哪個 DOM 元素」的 bug，e2e 必須對真實渲染的元素跑；注入 mock 會遷就錯誤假設而假性通過（2026-07-18 5en→5ep 新增）

5en 的 `swBuildRefImg` 讀 `getElementById("st-preview")`，但 `st-`＝印章
stamp、抄經是 `su-`（`su-preview`）——production 抓到印章預覽（抄經模式無
cellmap）→回 null→fallback 楷書，**部署後使用者重報同一 bug**。為什麼 5en
測試沒抓到：它的 e2e 用**注入的 mock st-preview**、pytest 只鎖字串 wiring——
沒有一個測試對真實 sutraRender 產出的 su-preview 跑。mock 遷就了「元素叫
st-preview」這個錯誤假設，於是假性通過。5ep 修一詞（st→su）＋補 `e2e_5ep`
對真實 sutraRender 跑（切抄經→產生預覽→等真 `#su-preview #sutra-cellmap`→
swOpen→驗 `SW.refImg` 為已載入 HTMLImageElement）。

判準：**修「程式讀/寫哪個具名資源（DOM id、檔名、key、端點）」的 bug，端到端
測必須對真實產生那個資源的路徑跑；用注入 mock 只會遷就你對名字的（可能錯的）
假設而假性通過。mock 驗邏輯、真實渲染/整合驗接線，兩者缺一不可。** 記憶點：
本專案抄經＝`su-`（sutra）、印章＝`st-`（stamp），前綴極易混。

---

## 34. reuse 多圖層 SVG 當 styled 範字時，要挑對「代表該風格的那一層」、別全 clone 並拉 opacity=1（2026-07-18 5eq 新增）

承 §32：5en reuse 抄經預覽 SVG 當逐字手寫 styled 範字時，一次 clone 三個範字層
並把 opacity **全設 1**——`sutra-glyph-reference`（填實外框、預覽 opacity 0.55）、
`sutra-trace`、`sutra-trace-skeleton`（中線骨架、stroke-width＝char_size×0.12＝粗、
預覽 opacity **0.03**）。篆書是 skeleton 模式：格子靠 0.55 填實層呈現細灰篆形、
0.03 粗骨架只是幾乎透明的 hint。popup 把 opacity 全拉到 1 → 填實層變重＋12% 粗
骨架全顯、疊在一起＝又粗又重疊的黑團，且骨架 round-cap 端點超出字形 bbox → 比例
偏大（實機三症狀同源）。5eq 修＝只 clone 填實層（有 `sutra-glyph-reference`/
`sutra-trace` 任一即用、否則才 fallback 骨架），篆書拿到細填實篆形＝格子描紅。

判準：**reuse 一份「各層 opacity/stroke 是為原用途（印刷描紅疊合）調好」的多圖層
SVG 到另一用途（螢幕 styled 範字）時，別平權全 clone 再統一拉 opacity=1——那會把
原本的 hint 層（0.03 的粗骨架）放大成主體。先辨識「哪一層代表你要的那個東西」
（篆書＝填實外框、不是那條粗中線），只取那層。** 各層權重帶著原用途的假設，換用途
就要重挑，不能無腦繼承。驗證循 §8.15/§33＝對真實渲染跑（e2e_5eq：注入「填實＋粗
骨架並存」的篆書情境 mock、解碼 swBuildRefImg 回傳 Image 的 data-URL、斷言含填實
path、排除粗骨架）。

---

## 35. 立新鐵則要同輪掃全體＋配機器回歸鎖；審查最大宗技術債往往是「已知鐵則未擴散」（2026-07-19 架構健檢/5er 新增）

全景健檢的核心發現：最嚴重的問題不是新缺陷，而是**已寫下的鐵則只修了案發
現場**——§9.1（async def 內同步 I/O 凍 event loop）在 5dp 修了 sutra/stencil
四條路由後未擴散，其餘 79 條 sync-body async 路由原樣躺了數週；§27 單一真相
源在 SVG header（11 處手寫、格式已漂移）與 ?v=（22 處手動）同樣失守。5er 一次
掃齊並加 `test_async_route_lock.py`：inspect 掃全部 APIRoute，async 端點必須
在 allowlist（附理由）且 allowlist 不得有殭屍項。

判準：**立鐵則的那一輪就要 grep/inspect 掃全體套齊（§13.1），且凡是「掃全體」
型的鐵則都要配一個機器回歸鎖測試——掃描結構、比對 allowlist——讓下一個違反者
在 CI 紅燈，而不是等下一次全景審查。**「人記得」的鐵則半衰期以週計；「機器擋」
的鐵則才會複利。

---

## 36. 功能之外要驗「目標環境的資源天花板」：JSON 解析成物件有 10 倍級記憶體膨脹（2026-07-19 5es 新增）

5er 把 1,830 字 g0v 筆順打包成單一 JSON bundle（gzip 4.9MB、序列化 26MB），
功能測試全綠；部署後首次載入全量 `json.load` 實測膨脹 **305MB RSS**（track/
outline 是海量 `{"x":…,"y":…}` 小 dict，物件開銷 10 倍級）——Render free tier
512MB 直接 OOM、worker 被殺、全站 503。修＝格式改 gzip JSONL（每行
hex<TAB>緊湊 JSON），載入只存原始字串（28MB），用到哪個字才 loads 哪行；
threading.Lock 防併發首載雙倍瞬時峰值；回歸鎖＝「bundle 快取值必須是 str」。

判準：**「能跑」不等於「能在目標環境跑」。引入大資料常駐結構前，量測解析後
RSS 增量並對照部署環境記憶體上限（沙箱一行 resource.getrusage 就有答案）；
序列化大小 ×10 是 JSON→Python 物件的合理預估。懶解析（字串進、用時才 parse）
是通用解；並用回歸鎖把「不可預先解析」鎖成契約。**另記：/api/health 這類
寫死 version 的端點不能當部署指標，部署簽章要用行為特徵（header/新端點）。

---

## 37. 0 是合法值：預設值填充別用 `||`（falsy 短路會吃掉 0），用 Number.isFinite/?? 判定（2026-07-19 5et-R4 新增）

sanitizeFrame 首版 `Number(f?.padMm) || 3`——使用者把外框內距設 0（貼邊，
完全合法）會被 falsy 短路成預設 3，靜默改掉使用者的值。JS 的 `||` 預設值
慣用寫法對「0/空字串是合法值」的欄位都是地雷；`??` 只擋 null/undefined 但
擋不住 NaN。修＝`Number.isFinite(raw) ? clamp(raw) : 預設`，並補「0 不可被
預設蓋掉」的測試。

判準：**寫預設值填充時先問「0（或空字串）是不是合法輸入」——是，就禁用
`||`；要同時擋 NaN 就用 Number.isFinite 顯式判定。數值欄位的 sanitize 測試
必含 0 邊界。**

---

## 38. `from __future__ import annotations` 之下，FastAPI request model 必須定義在模組層（2026-07-19 5et-R4 新增）

CardPdfRequest 首版定義在 create_app() 內——future annotations 讓所有型別
註記變成字串，FastAPI 用函式 globals 解析時找不到區域類別，參數被**靜默誤判
成 query 參數**（POST body 直接 422 Field required in query）。全 repo 既有
15 個 request model 都在模組層，正是同一個原因。

判準：**檔案有 `from __future__ import annotations` 時，任何要被框架
（FastAPI/pydantic/dataclass 反射類）解析型別註記的類別，一律定義在模組層；
在 closure 內定義的 model 會以「參數位置錯亂」而非 ImportError 的形式炸，
極難從錯誤訊息回推根因。**沿用專案慣例（model 集中模組層）本身就是防護。

---

## 39. 外部內容立「單一 sanitize 入口」＋跨層縱深防禦；新增匯入路徑必重跑 sanitize（2026-07-19 5et-R3/R4 新增）

卡片模式吃三種外部向量內容（使用者 SVG 檔、doodle 伺服器回傳、未來可能的
版面 JSON 匯入）。設計：`sanitizeSvgText` 是 art fragment 的**唯一合法來源**
（元素 allowlist 排除 script/foreignObject/image/use/animate/filter＋屬性
過濾 on*/href/style url()＋大小上限），render 層對 frag 原樣嵌入並在註解
標明信任邊界；伺服器 /api/card/pdf 再設第二道 `_CARD_PDF_DENY`（防 SSRF，
公開端點不能假設輸入來自自家前端）。E2E 用惡意樣本驗五威脅全剝除。

判準：**外部內容進系統只許走一個 sanitize 函式，消費端註明「此欄位唯一合法
來源」；跨信任邊界（前端→伺服器）各設各的檢查、不互相假設。新增任何匯入
路徑（如日後的 JSON 版面匯入）時，載入端必須重跑 sanitize——「當初存進去
時是乾淨的」不可依賴，因為存檔可能被分享/手改。**判斷函式做成純函式供
node 直測，DOM 走訪交給真實渲染 E2E（§33）。

---

## 40. 編輯器類功能：畫面與匯出共用同一條（字串）渲染路徑，純函式層與 DOM 層切開（2026-07-19 5et 弧新增）

卡片編輯器的渲染層全部輸出 SVG 字串：編輯畫面 innerHTML 掛載、本面 SVG
下載、展開列印版、印刷 PDF（前端組出血＋裁切標記後送轉檔）**全走同一組
函式**——所見即匯出，不存在「編輯畫面對了、匯出歪了」的雙軌漂移面。編輯
專屬的 chrome（框線/把手/導引/框選 marquee）用 mode 參數附加，匯出模式
天然不含。配套分層：geometry/model/render/判定函式零 DOM（node --test
直測 37 項），互動與 DOM 走訪（DOMParser、pointer、IndexedDB）交給
Playwright 真實渲染 E2E。

判準：**做「編輯＋匯出」類功能時，先立「單一渲染路徑」不變式——畫面是
匯出函式的預覽，不是另一套實作；再把可純函式化的部分全部下沉到零 DOM
模組，讓最大面積的邏輯進快速單元測試，DOM 只留接線薄層給 E2E。**這也是
index.html 巨石拆分（健檢 W4）的目標範式。

---

## 41. 大型重構走兩輪制：機械搬遷輪（行為零變＋機器快照鎖）與去重複輪分離（2026-07-19 W3/W4 新增）

server.py 5,010→269 行、index.html 10,859→3,255 行都用同一方法完成：
R1 純機械搬遷——先立快照鎖（路由 (method,path) 集合／拆檔串接與拆前
逐位元組一致／載入序清單），diff 再大也是零邏輯變更，全量測試＋鎖
可以完全鎖死；R2 才在綠色地基上改邏輯（工廠收斂／module 化）。

判準：**「搬家」和「改邏輯」永遠不同輪、不同 commit。**混在一起出
問題無法定位；分開後每輪可獨立回退，且 R1 的「零變」是可被機器
證明的命題，不是口頭保證。

---

## 42. 搬遷式重構的 by-value 陷阱簇：monkeypatch 目標、import 綁定、模組層副作用、框架 introspection（2026-07-19 W3 新增）

把符號從 A 模組搬到 B 模組時，四件事會沉默失效：①測試
`monkeypatch.setattr(A, "f", ...)` 對 `from A import f` 的既有綁定無效
——被 patch 的符號要嘛執行期屬性存取、要嘛 patch 目標跟著搬且
**不留別名**（patch 別名不影響實際呼叫）；②搬遷區段的相對 import
深度會變；③模組層副作用（`app = create_app()`）在互相 import 下
變循環——PEP 562 `__getattr__` 惰性化；④框架 introspection 的形狀
可能不是你以為的（FastAPI 0.139 include_router 巢狀掛載——iterate
app.routes 只見容器）——introspect 一律過自家攤平走訪器。

判準：**搬符號前先 grep 三件事：誰 monkeypatch 它、誰 from-import
它、誰在模組層執行它。**三張清單處理完才動手。

---

## 43. classic↔ES module 翻轉是語意變更，用 AST 量測決定順序、翻轉狀態入快照鎖（2026-07-19 W4-R2 新增）

`<script>` 轉 `type="module"` 改三件事：嚴格模式（未宣告賦值炸）、
自有作用域（頂層宣告從全域消失——消費者斷炊）、deferred（執行時序
後移）。安全轉換順序不是猜的：AST def/use 矩陣算出「零被依賴」檔
先轉（別檔不用其任何頂層名），供應鏈節點等消費端就緒（import 網）
才轉；轉前跑三道掃描（嚴格模式未宣告賦值／頂層 this／隱性全域
外洩）。翻轉狀態（哪些檔是 module）入快照鎖——改集合必先重跑量測。

判準：**轉 module 的單位是「量測出的相依邊界」，不是檔案清單順序；
UNRESOLVED=0 才動手。**

---

## 44. ES module 跨檔邊三定律：import binding 唯讀、循環靠函式宣告＋事件時呼叫、URL 帶版本佔位符（2026-07-19 W4-R2 新增）

①import binding 唯讀但 live——被多檔「寫」的共享狀態，宣告權必須
歸寫入方（讀方 import live binding）；②循環 import 安全條件＝跨邊
引用是函式宣告（instantiation 期已初始化）且雙方只在事件時呼叫；
跨邊 const/let 必須逐一確認無頂層取用（TDZ）；③import 路徑帶
`?v=__V__` 佔位符走版本注入——跨檔 import 的瀏覽器快取隨版本失效，
與頁面資源同一套快取鍵紀律（§11.4 的 module 版）。

---

## 45. 斷言歸源：registry／資料集長度收斂 src 常數＋機制鎖；演算法輸出期望保留寫死（2026-07-19 W4-R2 新增）

「改預設值→大面積紅」的結構根因是測試自帶字面量。解法分兩類：
**registry／資料集長度**（字集筆數、部首數、樣式數）收斂為 src 內
單一真相源常數（如 COVERSET_SIZES），配一條機制鎖（實載筆數＝常數，
防常數與資料檔漂移），測試一律引用同源；**演算法輸出期望**（「這個
輸入該切 4 段」）是規格、本來就該寫死，不歸源。附帶教訓：歸源時
會順手抓到命名與實況的漂移（moe_elementary_5021 實收 5,018——名稱
取公告字數）。

---

## 46. 單例互動元件服務多來源時，狀態要綁「事件當下」、不綁「掛載當下」（2026-07-19 5ew-R4 新增）

SW overlay 泛化到七模式時的陷阱：若 attach 時直寫模組級狀態
（SW.adapter/SW.positions），最後 render 的模式獲勝——使用者切到
別的模式再點「舊預覽」，開窗拿到的是別人的 adapter 與字集。正確形：
collect 閉包持有自己的 positions，**點擊 handler 內**才寫入單例狀態
再開窗。判準：凡是「一份 UI、多個掛載來源」的元件，問「使用者能不能
在兩次掛載之間互動舊 DOM？」——能，就綁事件當下。

---

## 47. E2E 有伺服器側副作用，用環境變數隔離出獨立資料目錄；「事後清理」不是隔離（2026-07-19 5ew-R3→R4 新增）

R3 教訓：Playwright 畫兩筆「永」寫進沙箱真實 user-dict，蓋掉標準
5 筆 → 8 個 pytest 連鎖紅、驗屍半小時。清理靠「記得清＋清得全」，
失敗模式是靜默汙染下一個 suite。R4 起制度化：被測服務啟動時帶
`STROKE_ORDER_USER_DICT_DIR=/tmp/<run>` 之類的資料目錄環境變數，
副作用天然落在可拋棄目錄，驗收後再確認正式目錄零檔案。適用一切
「測試會寫伺服器持久層」的場景——隔離靠環境，不靠紀律。

---

## 48. 純屬性錨點（data-*）是後端→前端最便宜的互動契約；加在共用放置函式上，一次覆蓋全部消費模式（2026-07-19 5ew-R5 新增）

第三度復用同一招（5cn grid、5ct page 型、5ew-R5 wordart/mandala）：
後端在字形放置點加 `data-char` 等純屬性——視覺零變化、零行為風險、
測試好鎖；前端互動（點字、注入、量測）全部長在錨點上。R5 的放大
效果：屬性加在 **共用** 放置函式 `_place_char_svg` 上，wordart 與
mandala（中心字＋環字）一處生效。要點：錨點函式的「局部座標系」
要一致（本案全部 EM2048），前端命中矩形/範字複製才能通用。

---

## 49. 同語意的 fallback 修過一處要掃兄弟實作；瀏覽器 console error 是「資料默默不顯示」的偵測訊號（2026-07-19 5ew-R4 新增）

page.py 5ai 早就會「outline/track 拆兩群、track-only 折線 fallback」，
grid.py 同目的的 _cell_content 卻對所有筆畫硬轉 outline path——空
outline 產生 `d="Z"` 垃圾 path，且手寫字/標點在 ghost/outline/filled
**完全隱形**。這是 §35（鐵則掃全體）的資料呈現版：語意修正落地時
grep 同類消費點（本案 `_outline_path_d` 的呼叫者），別讓兄弟檔漂移。
偵測面：E2E 把 console error 當一等訊號——「Expected moveto」這類
解析錯誤背後常是整段資料沒畫出來，不是 cosmetic。

---

## 50. 併發測試方法學四則：單迴圈 gather、boot 安定、停用瀏覽器快取、DOM 解析比對（2026-07-19 5ex 新增）

（一）starlette TestClient 每請求各開事件迴圈——跨迴圈搶同一顆
asyncio.Semaphore 會死鎖（正式環境 uvicorn 單迴圈無此事）；併發
行為測試用 httpx.ASGITransport＋單一迴圈 asyncio.gather。（二）E2E
按鈕前先等 boot 安定：非同步填入的欄位（如迴向偈）沒就緒就出手，
快取 key 帶空值漂移＝假陰性。（三）瀏覽器 HTTP 快取會替你回放舊
回應、遮蔽伺服器端觀察（x-render-cache 看不到）——page.route 攔截
即停用。（四）巢狀 SVG 數 children 用 DOM 解析、不用正則（非貪婪
遇巢狀 </g> 必錯）。附加價值實證：併發 E2E 當場揪出 opencc 初始化
race 與 grid.py d="Z" 兩個既有 bug。

---

## 51. 資源受限環境的渲染治理鏈六件套：快取、閘門、中止、分段、回收、縮批重試（2026-07-19 5ex～5fb 新增）

512MB／0.1 vCPU 免費層跑重渲染，單一手段不夠、六件互補成鏈：
**快取**治重複（輸出由參數決定→GET 進回應快取）；**閘門**鎖峰值
（Semaphore 排隊不拒絕、快取命中與輕量互動路徑豁免）；**中止**斷
殭屍（AbortController——世代計數只防誤塞畫面，abort 才停伺服器上
的舊請求）；**分段**攤前期（空白版面秒回＋分批填字＝感知延遲）；
**回收**壓底線（LRU 上限＋gc/malloc_trim＋字型句柄回收）；**縮批
＋重試**抗逾時（同症狀 502 有 OOM 與路由逾時兩因——縮短單請求、
偶發失敗補一針）。新增重端點時對照這張單子逐件問「有沒有」。

---

## 52. 量測歸因要逐層切割＋下了結論再複驗；同症狀常有多重根因（2026-07-19 5fb 新增）

兩次自我糾錯的教訓：①「預覽 POST 化是 R2 引入」——查 git 後發現
5bz 起就是 POST（對使用者陳述歷史因果前先查證）；②「TTFont 記憶體
逐字累積 209MB」——tracemalloc top-stats 逐層切割後改判「首字即付
的固定開銷」（檔案緩衝＋hmtx＋CFF），若照初判開藥（更激進逐字回收）
＝白工。方法：總量量測（RSS/tracemalloc 總數）只能提示規模，開藥前
必須 top-stats／逐層歸因到持有者；同一症狀（502）列出所有候選根因
（OOM／路由逾時）分別驗證，不要治了一個就宣告結案。

---

## 53. 缺字合成走「誠實放棄曲線」：推得出才合成、合成必標示、相容欄位不汙染（2026-07-19 5fa 新增）

以部件重組補缺字（篆體：罣＝网+圭、鋰＝金+里）三原則：**寧缺勿錯**
——方位/部件推不出就走原退化路徑（退楷書），覆蓋率提升零品質風險；
**誠實標示**——合成字帶機器可讀記號（validation_notes → cellmap
data 屬性）＋使用者可見統計「N 字為推測非原典」；**相容不汙染**——
管線分流欄位（data_source）維持原值讓合成字走同一條轉換鏈，「是否
合成」另闢欄位。附帶：部件取件重用本尊 get_character＝變體鏈/巢狀
合成免費復用（鉨 → 聲旁 尔→爾）；防循環用 in-progress 集合。

---

## 54. HTML hidden 屬性會被元件 CSS display 蓋掉；樣式化後必驗 hidden 生效（2026-07-19 5fc 新增）

UA 的 `[hidden] { display: none }` 優先權低於作者樣式——元件一旦
套 `.xxx { display: flex/grid }`，JS 再怎麼正確 toggle hidden 都
不會消失。症狀常偽裝成多個獨立 JS bug（面板全展開、抽屜常開、
條件區常駐），實為一源。修法：全域一行
`[hidden] { display: none !important; }` 歸位——一次修完、未來
新元件自動受保護。教訓：給元件加 display 樣式時，順手驗一下
hidden 還有沒有效。

---

## 55. grid 容器裡動態插入的元素會被 auto-placement 吃進錯格；跨欄項的 max-content 會撐爆欄寬——動態內容插 grid 外（2026-07-19 5fe 新增）

顯式定位的 grid（tools=(1,1)、canvas=(2,1)、side=(2,2)）遇到 JS
動態 insertBefore 的元素：它沒有顯式格位 → auto-placement 塞進
第一個空格（(1,2)）＝出現在完全意外的位置。改成跨欄
（grid-column: 1/-1）也有第二雷：**跨欄項的 max-content 尺寸會
分配進所有被跨的欄**，一段長文字就把 max-content 欄撐爆。終解：
動態、長度不可控的內容插在 grid 容器**之外**；grid 內只放格位
明確、尺寸可控的元素。另收：`display: contents` 可讓包裝層的
子元素直接進格——DOM 結構不動（測試鎖的 class 保留）就能改排版。

---

## 56. 幾何合成用「內容 bbox → 目標槽位」映射，別縮放整個座標系；覆蓋率驗收三態分列（2026-07-19 5fe 新增）

把部件塞進槽位時縮放整個 EM，部件自身的留白（side bearings）
跟著縮放進槽——縫隙＝設計縫＋兩件留白×縮放，怎麼調槽位比例都
治標。正解：先量內容實際 bbox，仿射到槽位矩形——縫隙就是設計值、
整體撐滿目標框。配變形上限（aspect cap）：窄件硬拉滿槽會爆形，
超上限改夾住置中——寧留小縫不毀形（§53 誠實取捨的幾何版）。
附帶（5fa 帳目修正的教訓）：**覆蓋率驗收計數要三態分列
（合成／原典／退化 fallback）**——「總數 118 全滿」看不出 7 字
其實退了楷書；只分「缺/不缺」兩態的計數會把退化算成成功。

---

## 57. 版本顯示一律走注入、不手刻；「疑似回歸」先用 exact-URL 重放驗伺服器現況再動前端（2026-07-19 5fe 新增）

手刻的版本標籤必定卡版（v0.13.0 卡了十幾版），有害於部署狀態
判斷——一切版本顯示走單一事實源注入（?v=__V__ → APP_VERSION），
標籤讀資產 ?v= 自動同步。靜態資產沒帶 ?v= ＝ cache TTL 長度的
「隱形舊版窗口」（CSS 3600s：版面修正上線後最長一小時使用者看
不到，狀態回報就會失真）。同輪方法學：使用者回報「大面積壞掉」
時，先用**前端一模一樣的請求（含參數序）重放伺服器**——快取/
伺服器現況完好即可判定暫時性（部署重啟窗口），不寫推測性防禦碼；
未重現的 bug 寫補丁＝把猜測固化進 codebase。

---

## 58. 驗收要驗到「看得見」：計數對≠畫面對；無頭環境用有效可見度稽核（2026-07-19 5ff 新增）

「格數全滿、旗標全對、md5 等價」仍可能整頁空白——內容存在與
內容可見是兩件事（實例：118 格字全在、整層 opacity 0.03）。
驗收鏈的終點必須落在使用者看得見的那一層：瀏覽器截圖量畫素、
或無頭環境的替代品——**有效可見度稽核**（走訪 SVG 祖先累乘
opacity、繼承 stroke/fill，判每條線是否真畫得出來）。同輪教訓：
「伺服器內容完好」只能證明伺服器沒壞，不能推論「畫面沒壞」——
下「暫時性故障」結論前，先驗渲染層。附帶：沙箱與實機的環境差
（字型組合）會讓 bug 只在一邊現形——實機活體 DOM（瀏覽器擴充
diagnostics）是十輪沙箱推測抵不上的三分鐘。

---

## 59. 借用渲染器要逐一核對「全部」開關；複製貼上的兄弟實作錯得一模一樣（2026-07-19 5ff/5fg 新增，§26＋§49 合流）

§26 的「單一未轉發旗標」在同一個 wrapper 三現：emit_cellmap
（5dw 補）→ show_original_glyph（5ff 補）→ 五個自繪表的等價
缺漏（5fg 補）。兩條合流教訓：**①借用（wrap/delegate）另一個
渲染器時，把它的參數表逐一過一遍——「我沒轉的每一面旗」都是
未來的雷**；能力偵測轉發（inspect.signature 有才給）讓新旗標
自動覆蓋後續 renderer。**②修 bug 時 grep 兄弟實作**（§49）——
五份複製貼上的 _traced 錯得一模一樣；當場歸一成共用函式，
才是「修一次」而不是「修五次的第一次」。

---

## 60. 人工維護的資料表配「覆蓋稽核測試＋白名單」——漏項變紅燈，不靠實機逐格找（2026-07-19 5fh 新增）

特化資料表（元素拆解 111 條）漏收是三批實機回報才找完的
（Ext-B 七字→釓鋱）。根治不是「這次補齊」，是**讓漏項自動變
測試紅燈**：對表的完整目標域（118 元素）逐一驗「查得到」，
查不到者只准出現在明確白名單（原典古字 硫鐵銀金鉛）——白名單
就是「為什麼可以不在表裡」的機器可讀理由。適用一切人工維護的
對照表：缺席必須是決策，不是遺漏。附帶：語意相近的條目要防
混淆（釓⿰金乚 vs 釔⿰金乙——兩個元素必須可區分，圖方便共用
部件＝製造新錯）。

---

## 61. 版面多輪收斂：佈局斷言集中「終局測試」；動版位先掃歷代測試的版位斷言（2026-07-19 5fj～5fl 新增）

同一批 UI 元件三輪遷移（畫布右下→左欄→匯出跟進），前兩輪全綠、
第三輪被更早的 5ez 版位斷言（hw-data-row-inline）咬紅——版面
斷言散在歷代測試裡，每輪搬家都是地雷。作法：①版位/順序斷言
集中一個**終局版面測試**，隨版面演進改名續版（test_5fj →
test_5fj_5fk → test_5fj_5fl）；舊輪測試的版位斷言移交＋留註記，
不讓 N 個測試各鎖一個歷史版面 ②動版位 checklist 固定含「grep
歷代測試中被移元素的 class/id」③行為全綁 id/data-action
（per-element querySelector）＝DOM 大搬家 JS 零改動，搬家成本
只剩 HTML+CSS+測試。附帶：搬空的容器（抽屜）整段移除不留
dead UI；其入口鈕不刪、改語意（捲動到內容新位置）——affordance
保留、語意跟著內容走。

---

## 62. 不可復原操作配二次確認；E2E 要實測「攔得住」，不是驗「有 confirm 字樣」（2026-07-19 5fk 新增）

整庫刪除這類不可復原操作雙 confirm：第一關給退路（建議先匯出
備份）、第二關明示範圍與不可復原（「最後確認：刪除『全部』」）；
兩關都必須在真正動手（clearAllTraces）**之前**。測試兩層：
靜態鎖「處理器內恰 2 個 confirm( 且都在動手前」（防未來重構把
確認移到刪除後或刪掉一關）；E2E 用 dialog handler「第一關接受＋
第二關取消」然後驗資料完好——驗的是**攔截力**，字樣存在不代表
攔得住。

---

## 63. 需求語意不明：先重現、帶證據問；使用者現場證據可折抵自動驗收（2026-07-19 5fk/5fl 新增）

「恢復X按鈕」一句話三種解讀（常駐化／消失 bug／別的頁面的鈕）。
別猜著做：先本機**重現 X 的全部出現路徑**（該鈕僅深連結出現、
實測正常、歷史確認從未常駐），把驗證結果寫進選項再問——使用者
一眼選「維持現狀」，零改動結案；不先驗證就動手，三個解讀猜錯
兩個。姊妹律（驗收經濟）：使用者貼的 production 截圖含版號＋
完整版面＝比 curl 更強的驗收證據，已排的自動驗收 trigger 可撤，
不重複燒資源；無截圖的輪次才走輕量 curl 驗收模板。

---

## 64. 「同一物件的多個呈現面」用同一條墨跡實框正規化契約；改共用下游要巡全部上游消費路徑（2026-07-22 5fm/5fn 新增）

逐字手寫範字在五個入口出現（稿紙/字帖/筆記/信紙彈窗、抄經彈窗、獨立
練習頁），要看起來一樣大就用同一條契約：量該字的**墨跡實框**（ink
bbox）、取正方＋固定邊距（8%→佔 ~86%）、置中；而非隨字浮動的權宜——
「硬放大 1.4×＋任其裁切」讓滿框字（春）溢出米字格、「裁到容器/字格框」
讓有留白的格子偏小，佔比都取決於「這字剛好多滿」。量墨跡才能每字固定
佔比。後半同等重要：改了**共用繪製那一步**（swDrawBase 拿掉 1.4×），要
巡過**所有**餵它的建構器——本案只清點走 swBuildCellRefImg 的四模式，抄經
走另一支 swBuildSutraRefImg 就被漏、暴露成「別人正常、抄經偏小」，隔輪
才補（5fn）。一個病、多個入口：改共用下游＝改動半徑遍及其全部消費者，
漏一支就是「別人好、它獨壞」的分岔 bug。

---

## 65. 已知脆弱的慣例升級成自動閘門，別留 note 靠紀律；自動挑「最新/預設」配 fail-open 新鮮度守門（2026-07-22 收工檢查 新增）

收工檢查.bat 以 `dir /o:n`（檔名字典序）挑 commit 訊息檔當「最新」，沒放
當班檔時**靜默沿用**上一個最大檔名的舊訊息（7/19 訊息套到 7/22 commit）。
此坑 7/19（5er）踩過、當時只在 WORK_LOG 留 note→7/22 復發。**靠紀律的
教訓會復發；把教訓變成自動閘門才治本。**作法：自動挑「最新/預設」配
**新鮮度守門**——挑到的不含今天日期就中止並提示先建當班檔，讓遺漏從
『靜默用錯』變『明確中止』。守門本身要 **fail-open**：取不到日期等異常
就跳過守門、絕不誤擋合法提交（守門是助手不是安全閘，寧放行不誤擋）。
姊妹坑（同輪）：裸 `git push` 因 `main` 追蹤 backup 而誤入備份庫、Render
來源 origin 沒更新——`git push -u origin main` 一次推 origin＋改追蹤根治。

---

## 66. 守門測試鎖「不變式」不鎖「當時的寫法」；改實作同批更新守門並註明「意圖不變」（2026-07-22 5fm/5fn 新增）

本輪三次被守門咬紅——`test_5fb` 鎖 `REF_SCALE = 1.4`、`test_5eq` 鎖
`_filledIds = [...]` 及其否定斷言——全是**鎖字面實作字串**：保留意圖的
重構把字串換掉，守門就誤紅。鎖字面寫法＝把「怎麼寫」當契約，重構必踩。
作法：守門盡量鎖**不變式**（存在性/順序/行為）——如「骨架 index 大於
填實層 index ＋ break 存在」鎖住「填實優先、骨架殿後」，而非某常數值或
某段陣列字面；真要鎖實作字串，就改實作時**同批更新守門**、commit 註明
「意圖不變、僅結構更新」。承 §61（動版位先 grep 歷代版位斷言）：改前先
grep 被改符號在 tests/ 的出現，把守門更新排進本次改動。

---

## 67. 版本破快取的紀律要覆蓋「整條 import 圖」；ES 子模組的相對 import 也要帶 ?v=，不只入口 script（2026-07-22 5et-R5 新增）

卡片模式加 `faceFoldEdge` export 後線上白畫：入口 `card.html` 以
`?v=__V__` 載 `main.js`（每次破快取），但 `main.js` 內部
`import './geometry.js'`（相對、無 `?v=`）——`/static` 未帶 `?v=` 只快取
1 小時，瀏覽器載到快取的舊 `geometry.js`（沒有新 export）→ named import
link 失敗 → 整頁初始化中斷。入口有版本、子 import 沒有＝**「半破快取」**：
一旦動到被 import 模組的 export 面（新增/改名/刪 export）就中招，且只中
「1 小時內回訪」的使用者。作法：**所有** static ES module 的相對 `.js`
import 一律帶 `?v=__V__`（讓 versioning 中介層改寫成版號、與入口同步破
快取）；配掃全 static 的守門測試，任何相對 import 缺 `?v=` 即紅燈。承
§27（單一事實源）／§57（版本注入不手刻）：版本快取鍵要覆蓋整條 import
圖，不是只有 HTML 引的第一層。**驗收盲點**：這類半破快取 bug 全新瀏覽器
／CI 無舊快取、測不出（Playwright 測過≠沒事）——要嘛靠靜態守門，要嘛
實機帶快取回訪重現。

---

## 68. 紙藝／實體機構先折實體原型定案再寫幾何；別把一條摺線複雜化成逐筆 tab；鏤空字材料是字身要實色（2026-07-23 popup 新增）

立體字卡片（pop-up）我一開始照「想像的機構」寫——把「文字頂連接頂面」拆成
每個筆畫各一個小長方形 tab（DAD 立體卡範本式），反覆多輪，使用者連回「差異太大、
根本不理解我的修改」。轉折是使用者給了**實體折好的箱型照片**：正確機構其實最簡——
前立面＝整片鏤空文字、文字頂＝**一條**摺線接頂面 roof、文字底＝**一條**摺線接底座、
字中一條中線谷折，**沒有 per-stroke tab**。我把「一條摺線」誤讀成「每筆一個 tab」＝
把最簡機構複雜化。教訓：**紙藝／實體機構先折一個實體原型定案，再寫幾何**——程式碼
描述的是「摺起來會立起來／收得平」的實體行為，紙上想像最容易疊特例；使用者說「不
理解」是明確 stop-and-replan 訊號，該停手要一張定案圖（實體照片），回到最簡機構
（Occam）而非基於自己的想像繼續疊。

鏤空字的語意（同批）：字即結構、字身是**材料（實心）**、周圍才是透空剪掉——渲染
要畫**實色**，一度畫成白色留空（暗示被剪掉）就與圖不符。可折合是**對稱不變式**、用
測試鎖：中線谷折穿卡片正中、且 |字頂到中線|=|字底到中線|（|a-d|=|b-c|，雙層再加
上下兩排巢狀等高），對稱才折得平（`test_spine_at_card_center_symmetric` 斷言 spine
在 CH//2 且 |top_d−bot_d|≤2）。整卡剪下不可散＝**單一連通**不變式：鏤空後浮件（如
「口」中心塊）補最短縱向連筋橋回主體，測試鎖 `ncomp==1`（承 §66 守門鎖不變式不鎖
寫法）。

姊妹律一（**部署期字型相依→缺則誠實降級**，承 §8/§9）：思源黑體不進版控、由
`scripts/render_fetch_fonts.sh` 部署時抓；本機缺字型時需字型的測試要 **skip 不是
fail**（沿用既有 `needs_hei = skipif(not default_hei_font_path().exists())` 模式）、
端點回 **503 帶安裝指引**，別讓「開發機沒資源」誤判成功能壞；不需字型的測試獨立
不掛守門，確保零字型也有回歸覆蓋。姊妹律二（**選用相依要能降級**，承 §8）：連通
標記優先 `scipy.ndimage.label`、缺了退回純 numpy run-based union-find（`_label_runs`，
比純 numpy BFS 快一量級：雙層 24s→2.8s），同一測試雙驗兩路徑計數一致——選用相依
（scipy）不可硬性 require、擋住整個功能。

---

## 69. 跨會話寫回前先「三步對表」；沙箱有未推 commit 勿盲 reset；多輪堆疊訊息寫累積式（2026-07-23 5fo 新增）

事故（covert clobber）：一個停機多日的舊沙箱恢復後直接寫回裝置，而裝置端 repo
早被另一會話推進——版本退回（0.14.263→0.14.255）、`scipy>=1.10` 被舊檔覆蓋抹掉、
收工檢查.bat 撿到同日**已消費**的訊息檔導致 commit 訊息張冠李戴，**三重傷害全部
靜默成功**。雲端多會話工作型態下，「我沙箱裡的檔案」不等於「repo 現況」。

鐵則——**開工／寫回前三步對表**：① 沙箱 `git fetch origin` 對 log，確認自己不落後
② 裝置端 `grep version pyproject.toml`＋`ls docs/_commit_msg | tail` 對現值，任何
「device 比我新」都是紅燈停 ③ 本輪 phase 代號 grep 近期 log 防撞名。善後選**前進
修復**（版本推高於一切殘影＋下一筆訊息補述錯誤 commit 的真實內容），不 force-push
改史。

姊妹律一：沙箱有未推 commit 時**勿盲 `git reset --hard origin/main`**——先
`git log origin/main..HEAD` 看有沒有會被洗掉的工作（本弧實踩，reflog 撈回）。
姊妹律二：多輪堆疊未收工時，訊息檔要寫**累積式**——收工檢查.bat 依名稱取最新
一檔，一筆 commit 吃多輪時單輪訊息會遺漏前輪內容。

---

## 70. 「手刻／漏 guard」類病修一處不算修完：回歸鎖掃全類、guard 每個獨立檔皆備（2026-07-23 5fo/5fr 新增）

/gallery 版本標籤手刻 `v0.13.0`——§57「版本一律注入」的漏網頁（走獨立 route 沒經
`_versioned_page`）。修這頁的同批要立**掃全類的回歸鎖**：
`test_no_hardcoded_version_labels_on_disk` 掃全部 HTML 的 `>vX.Y.Z<` 字面，未來
任何頁再手刻直接紅燈。同弧同款：`[hidden]` 被元件 display 蓋掉（§54）在
handwriting.css、index.css 修過兩次後，gallery.css **第三現**——結論：這類
「每個獨立作用域都要各自帶一份」的修法（CSS guard、注入紀律、sanitize 入口），
修時就要**盤出全部作用域一次補齊**，並問「哪個機器測試會在下一個新檔漏掉時變紅」。
承 §59（兄弟實作錯得一模一樣）：同類病的單位是「類」，不是「處」。

---

## 71. 全站 UX 稽核工作法：僅稽核不動程式→分級 P0/P1/P2→逐級 sign-off 分輪施工；稽核發現在施工輪要現場再驗證（2026-07-23 稽核弧 新增）

「初次使用者觀點」稽核的正確姿勢：Playwright 模擬新手把**每個模式實走**
「進入→輸入→產生→檢視結果」，全頁截圖＋按鈕盤點留證；**環境限制先聲明**
（沙箱缺字型/CDN 的觀察逐條標註〔環境〕，避免環境問題誤報成產品 bug）；報告
**僅稽核不動程式**，分級 P0（互動缺陷）／P1（一致性）／P2（打磨）並言明
「未經 sign-off 不實作」。施工由使用者逐級放行、一輪一級、一輪一 commit
一部署驗收——稽核發現≠工單。

姊妹律：**稽核是遠觀，施工輪要現場再驗證每條建議**。本弧兩例：「↻ 全部歸零」
稽核建議加二次確認，實測發現它只歸零位移微調（低風險），正確修法是正名
「位移全部歸零」；「三空區」部分容器實已有舊短句，修法從補句改為統一句式。
稽核誤讀照單施工＝把錯誤放大成程式碼。

---

## 72. E2E 錨點與可見性三陷阱：checkVisibility 判收合內容、佈局斷言用 id 錨定、幾何斷言容換行（2026-07-23 5fp/5fr/5fu 新增）

① 閉合 `<details>` 內的元素 `getBoundingClientRect` **仍回非零幾何**（Chromium
content-visibility 行為）——「收進 details 後不可見」要用 `el.checkVisibility()`
判，不能用 rect 判。② 佈局順序斷言別用「字串首現位置」——「基本符號」「推薦
組合」這類字樣常多處出現（按鈕、說明、tooltip），首現位置會誤中別處；改用
**元素 id** 錨定（`indexOf('id="zentangle-combo-buttons"')`）。③ 訊息文字會
**換行**——「與按鈕同一行」的幾何斷言在長訊息下誤紅，改「錨點下方 N px 帶內」。
承 §49（純屬性錨點）、§61（終局測試）：斷言要錨在**唯一且穩定**的記號上。

---

## 73. UI 跨模式統一取三層次：同名→同序→相鄰即可，多數原生一致時不硬搬絕對位置（2026-07-23 5fu 新增）

共用控制項（字型風格／罕用字／資料源）散布 13 模式，統一的目標是「跨模式一致的
心智模型」，三層次即達成：**同名**（同物同名，「資料來源」「字體」「字型」歸一）
→**同序**（全站固定順序）→**相鄰**（散落的聚攏成一列）。第四層「絕對同位」
（全表單搬到同一位置）邊際收益低於代價——各表單語意分組不同，硬搬破壞就近原則，
是為統一而統一。執行紀律：統一前先**全模式盤點現況表**，多數派已一致就以多數為準
只搬少數；id 全保留讓 JS 零改動；搬 DOM 的輪除了幾何斷言（同列、順序、各 id
恰一次防搬移殘留複本），**必實測動過的模式改值後產生成功**——綁定沒斷才算搬完。

---

## 74. 新分類走 registry 派遣制零 API 改動、驗證憑據內嵌檔案自身；深連結參數路是重用複利的預設接口（2026-07-23 5ft/5fs 新增）

分享庫加「立體字」分類只動 registry：`ALLOWED_KINDS` 加常數、
`VALIDATORS[kind]`／`SUMMARIZERS[kind]` 註冊純函式——上傳/列表/下載 route
一行不動。當初（5b r28）立 registry 的投資在此第一次兌現「新增分類＝註冊三件事」。
驗證憑據設計：**檔案自帶**——popup SVG 產出時內嵌
`<metadata><popup-config><![CDATA[{json}]]></popup-config></metadata>`（含 schema
tag），上傳端認 metadata 拒收四型（非 SVG／無 metadata／schema 錯／缺必要欄），
前端偵測同一 schema 字串——不靠猜檔案內容。

姊妹律（承 §26 重用複利）：**深連結參數路設計成寬鬆型別就是預設擴充接口**。
5fd 的 `/handwriting?char=<字串>&from=X` 因為收「字串」不是「單字」，5fs 卡片
文字框「逐字手寫」只加一顆鈕＋一個 from 標籤＋返回分流即接上——零新 API、
零新頁面、資料同庫。設計參數路時多想一步「值域放寬會不會白吃未來需求」。

---

## 75. 大改動估工前先盤 choke point——「逐處改」與「單點改」成本差以倍計（2026-07-23 5fv 新增）

「11 個模式的匯出 SVG 都要內嵌憑據」直覺估法是逐模式改、3 輪起跳。開工先盤
出口：`svg_response` 是 W3 重構收斂出的**全站唯一 image/svg+xml 出口**、
`render_pages_as_single_or_zip` 是文字群五模式共用的多頁出口——在這兩個
choke point 內嵌＋各呼叫點標一個 mode 字串，11 模式一輪接完（唯一前端產
SVG 的禪繞單獨補）。教訓兩面：**估工前先問「這類輸出有沒有單一出口」**，
方案取捨（本案 A/B 案之爭）該建立在盤點後的成本上而非直覺估計；反向看，
當年「散寫收斂單點」的純重構投資（§28、W3），會在日後某個需求「只改一點」
時整筆兌現——choke point 是重構的複利帳戶。

---

## 76. 白名單下沉單一事實源，route/前端不重複持有；E2E 要驗到「回應成功」不只「請求發出」（2026-07-23 5fw/5fx 新增）

live bug 一對：①列表 kind 參數在 route 層硬編 `pattern="^(psd|mandala)$"`——
5ft 加 popup、5fw 加 12 分類時沒人記得這裡還有一份清單，全部 422；同型病在
前端：popup 沒進 hash.mjs 白名單，深連結被靜默丟棄。修法：**白名單只存在
單一事實源**（service 的 ALLOWED_KINDS／hash.mjs 的 EXPORT_KINDS），route
驗證下沉呼叫、不重複持有；再配前後端同表鎖（測試比對兩份清單）。
②這條 422 竟穿過 5fw 的 E2E——因為斷言只到「選分類→發出帶 kind= 的請求」，
沒驗回應 200。**斷言鏈的終點必須是使用者可感知的結果**（回應成功、畫面出
資料），「有動作」不等於「有效果」。承 §58（驗到看得見）在網路層的對應。

---

## 77. 無外部依賴的防機器人三層法：蜜罐＋停留時間＋簽章算術題；匿名去重用加鹽雜湊不存明文（2026-07-23 5fx 新增）

免費層無法外接 CAPTCHA 服務時，三層自製已足擋住批次濫用：①**隱形蜜罐欄位**
（CSS 移出視野、真人不會填，有值即拒）②**伺服器簽章挑戰 token 內含發題時間**
——太快送出（<3s）拒「機器人特徵」、過期（>10min）拒重放；③**算術題免存題**
：簽章把正確答案簽進去，驗證時以「使用者送來的答案」重算 HMAC——答錯簽章
必不合，伺服器零狀態。配套：匿名身分以**加鹽 HMAC 雜湊的 IP** 去重（不存
明文 IP，隱私與去重兼得）；去重交給資料庫**部分唯一索引**守恆，不靠應用層
檢查。E2E 要實測「太快被攔住」（§62 攔得住紀律）。

---

## 78. 防護機制疊加時明定優先序；每個自動機制只回收自己造成的狀態（2026-07-23 5fx/5fy 新增）

同一個 `hidden` 欄位背後有五種來源（管理員下架/多人檢舉/作者黑名單/人工
審閱/首次上傳 24h 窗）時，兩條鐵則：①**優先序明定**——人工（管理員勾選）
＞自動（24h 窗）；作者被勾「人工審閱」時新上傳走 pending-review，不落自動
窗。②**解除語意對稱**——每個機制解除時只復原「自己造成的隱藏」：解除黑名單
只復原 hide_reason=author-blacklisted 的作品（管理員手動下架的不動）；24h
懶釋放只碰 first-upload-review。靠 hide_reason 記「誰藏的」，回收就不會誤放。
附：到期自動化在無排程器的環境用**查詢入口懶釋放**（一發條件 UPDATE、無匹配
近零成本、自癒）勝過引入 cron。

---

## 79. 行為變更的既有測試遷移：用「視角 fixture」批次表達新前提，不逐測試 hack（2026-07-23 5fy 新增）

「首件上傳自動隱藏 24h」改變了「上傳即公開」的隱含前提，8 個既有測試紅。
逐測試 backdate 時間戳或改斷言會把「為什麼這樣改」散進八處；正解是一個
conftest 共用 fixture（`established_authors`＝monkeypatch 關閉首件窗），
讓既有測試以「老帳號」**視角**繼續驗原契約——fixture 名字本身就記錄了測試
前提，新行為由專屬測試檔獨立全覆蓋。原則：行為變更落地時，先分清「哪些
測試在驗舊契約的別的面向」（給視角 fixture）與「哪些該改寫成新契約」，
別讓兩者混在同一批修改裡。附：async 函式的同步測試用 `asyncio.run`（每測試
全新 event loop），別用 get_event_loop——整批共跑時共用 loop 會 closed。

---

## 80. 部署平台的網路限制先查官方文件再懷疑設定；錯誤訊息要把可辨病因帶出來（2026-07-23 5fz 新增）

Gmail SMTP 設定全對仍 `Errno 101 Network is unreachable`——查證（web search
官方 changelog）發現是 **Render 免費層封鎖所有對外 SMTP 埠**：平台政策，
換任何帳號/埠都無效，唯一通道是走 443 的 HTTP 郵件 API。教訓：連線類錯誤
在 PaaS 上**先查平台限制文件**（SMTP、固定 IP、長連線、磁碟持久性都是常見
封鎖面），別在自己的設定裡打轉。選型附註：無自有網域時挑「驗證單一寄件人
即可寄任意收件人」的服務（Brevo）而非要求網域驗證的（Resend）。

姊妹律（**錯誤訊息寫明可辨病因**）：同一條寄信路的第二關（Brevo 401 IP
白名單）之所以一眼定位，是因為新代碼把「HTTP 狀態＋常見原因清單＋對方回應
原文」都帶進錯誤訊息——對照第一關的裸 traceback 要查證半天。包外部服務的
呼叫時，把「你最可能做錯的三件事」寫進錯誤字串，未來的自己（或使用者）會
在事故現場直接收到答案。

---

## 81. 設計真理源三步：成文→立鎖→分輪掃債；文件是執法依據不是快照（2026-07-25 5ga~5gf 新增）

參考庫（awesome-design-md）給的是**格式慣例**，不是風格——既有設計語言
已上線且有測試鎖著時，該做的是把它成文（DESIGN.md 九節＋機器可讀 token
表），不是套模板。成文只是第一步：**同步鎖**（test_design_md 逐列驗
`--token: #hex` 真實存在於宣稱檔案）讓文件與 CSS 綁死、不會腐化；然後
才能拿文件當**執法依據**回掃全站——本弧三波掃債（5gb/5gd/5gf）每一輪的
「違規」定義都直接引用 DESIGN.md 條文。沒有鎖的設計文件三個月後就是
誤導源。掃債輪的範圍用**量測數字**框定（「四種藍」「六處 import」
「31 處 chip-bg」），開工前量測、收工後歸零、每項配回歸鎖。

---

## 82. token 同名反義是最毒的設計債：語意全站唯一，值可分作用域、語意不可（2026-07-25 5gd 新增）

`--accent` 曾三頁三義：主站＝破壞性紅、card＝藍當主色、popup＝綠當主鈕。
這比散寫 hex 更毒——散寫只是亂，**同名反義會誤導照文件動手的人**（在
card 頁按「--accent＝紅」的契約改樣式必出事）。修法是語意歸位不是改名
遷移：凡當主色用的改 `--primary`，`--accent` 全站收斂回單一語意，並上
跨頁鎖（定義值只准 #c33）。兩個配套教訓：①機械替換前逐點判別語意——
sutra-editor 六處 `var(--accent)` 全是錯誤訊息（紅是對的，保留）、popup
圖例綠是輸出品語意色（不動）；②字面回流鎖的**豁免規則要同批設計**
（token 定義行/註解行豁免、3 碼 hex 斷言後不接 hex 字元）——我們自己的
測試 docstring 與 CSS 註解就誤中過兩次。

---

## 83. 「統一」＝合理差異成文為例外＋不合理分岔修平；硬套一致性是反模式（2026-07-25 5ge 新增）

版面盤點看到 960/1400/full-bleed 三種頁寬、640/767/480 三種斷點，直覺是
「統一成一種」——錯。分享庫 1400 是瀏覽工作區的合理選擇（硬壓 960 讓
卡格變少＝負優化）；筆順練習 767 是雙欄工作區的合理值。**成文的例外就是
一致性**：容器三檔、斷點準則寫進 DESIGN.md，之後的「不一樣」是有據可查
的設計，不是漂移。真該修的是**無語意的分岔**：同一檔案並存 760/767 兩個
近同斷點（7px 窗內行為不同、無人能說出為什麼）、「←/↩ 回主頁」混用——
這類修平＋鎖。判準：能為差異說出理由→成文；說不出→修平。

---

## 84. 視覺零變重構的驗收是「證明沒變」：E2E 比對 computed style＝原值（2026-07-25 5gf 新增）

token 化/重構這類「行為不該變」的改動，驗收重點與功能開發相反——不是
證明新行為對，是**證明舊觀感一位元都沒動**。工法：改動前記下代表性元素
的期望色值，改動後 E2E 取 `getComputedStyle` 逐一比對＝原 rgb 值。這同時
證明兩件事：token 解析成功（不是 var() 打錯名回退成透明/繼承色）、值
對映無誤。刻意的例外（同族雜色歸一）要在 commit/註解**點名**——「值不變」
是預設承諾，變的地方逐一列舉，讓 review 者只需盯例外清單。

---

## 85. 啟發式守門升級成狀態機消費制：「用過」是事實、「新鮮」是猜測（2026-07-25 5gc 新增）

收工檢查.bat 的訊息檔守門用「檔名日期＝今天」判新鮮，連三次誤擋合法的
跨夜收工——啟發式在邊界情境必然誤判，且每次誤判都要人工繞過。根治是把
啟發式升級成**狀態機**：訊息檔 pending→used，commit 成功才消費（移入
used\；失敗保留），「這檔用過了沒」從猜測變成可查的事實。兩個設計要點：
①消費時連舊 pending 一起歸檔的前提是 §69 累積式訊息（新檔必涵蓋舊檔）
——兩條慣例互相成立，改其一要檢查另一條；②降級不刪除：日期不符仍
WARNING＋choice 人工確認，保留最後一道人眼。首航自動清 191 個歷史積欠
＝機制正確性的現場證明。

---

## 86. 降級要「供應」不只「報錯」：同格式後備＋誠實標注；長壽會話每輪動工前重新對表（2026-08-11 R1a 新增）

popup 缺思源黑體原本回 503。R1a 做出骨架長肉字模（zh-stroke-data track→
Chaikin→shapely buffer→多輪廓折線）後，端點從「報錯」升級成**降級供應**：
noto_hei → skeleton 後備 → 兩者皆缺才 503。三個工法：①後備供應器的輸出
**同形對齊既有契約**（`_outline_to_polylines` 的多輪廓折線、EM2048、even-odd）
——消費端 drop-in、降級只是換供應器，不發明第二種格式；②**誠實標注不無聲
頂替**（§8 升級版）：回應帶 glyph_source/degraded、UI 顯示「骨架字模（降級）」
——品質不同的後備冒充主供應器是欺騙，標注即誠實；③演算法常數用**實證錨點
測試**鎖（密度補償 w_eff=w·√(10/(10+n))，spike 實證歡 22 筆 180→101 字碗
全開；守門斷言 101±2）——防常數被無聲改掉。

回應層加新欄位的姊妹律：既有測試常以 monkeypatch **替身**餵假結果（無新欄位
屬性），端點取值一律 `getattr(r, field, 保守預設)`——否則加欄位＝逼全部歷史
替身同批擴欄。

§69 再犯變體（事故重放）：**會話跨多日存活＝等同跨會話**。上一輪結束時把
雲端副本對齊過 origin，不等於這一輪還新鮮——本輪即因沿用 17 commit 前的
過期基底動工寫回，倒退四檔功能，靠收工檢查全量測試 6 紅全數攔下（守門網
值回票價）。規則收斂：「每輪動工前」fetch 對表，不是每個會話對一次。

---

## 87. 借鏡外部 AI 作品：能用靜態可查證資料做到的別接生成式；沒有的資料留白給人、不用猜的填滿（2026-08-15 T1 新增）

同好用 Gemini Canvas 做的漢字部件教學（LLM 即時生成部件說明/字義/造詞/插圖）
很吸睛，但作者自己在分享文點名弱點：「資料都是 AI 生成，使用前一定要確認」
——對老師那是**每次備課都要付的查核稅**。借鏡時先問三題：①**它的資料從哪來、
使用者要不要查核**？②我手上有沒有同等內容的**靜態可查證來源**（本專案：g0v
筆順、CHISE IDS、朱邦復部首分類、教育部辭典開放資料）？③接生成式會帶進什麼
（金鑰、額度、斷網失效、查核負擔）？本輪答案是「用現成資產重組」——**功能
對等不是目標，可信度才是**；別人的即時生成，在我們這是可查證的靜態資料。
姊妹判斷：對方的**降級後備**（雲端 TTS 失敗才用瀏覽器語音）往往正是我們該當
**主路徑**的東西（`speechSynthesis`：零服務、零金鑰、離線可用）——代價（音色
依電腦而異）誠實揭露即可。

**沒有的資料留白給人填，不要用猜的填滿**（§8 誠實降級在內容層的延伸）：本輪
注音無逐字資料、字義/造詞尚無來源，就給「請自填／老師填寫」的可編輯欄位，
不用啟發式硬湊——教學場景**教錯比沒有更糟**。附帶好處：可編輯欄位讓日後接
權威資料源變成純升級（欄位不變、只是預先填好，介面零改）；自動判別的結果
（如部首建議）要標「可修改」，不冒充權威。

**新頁三配套同批完成**：入口（§74）、設計鎖清單（§81 的 --primary/--accent/
導覽三鎖）、路由快照——三者都是「當下做只要一行、事後補要考古」，漏了就是
下一輪掃債的來源。

**長壽會話的環境事實每輪重取**（§86 續）：本輪收工檢查警告訊息檔日期非當日
——會話跨多日存活，沿用了上一輪算好的日期。與 §86 的「git 基底過期」同源：
長壽會話裡 **git 基底、當日日期、裝置檔案現值** 都會過期，每輪動工前重取，
別信上一輪的快照。

---

## 88. 禁止改作（ND）授權的資料：劃清「載體轉換／節錄」與「內容改寫」，並把授權義務寫成機器守門（2026-08-16 T2 新增）

教育部辭典資料是 CC BY-ND 3.0 臺灣（可商用、須標示、**不得改作**），但工程上
不轉檔就不能用。劃線：**可以**做載體轉換（xlsx→JSONL.gz）、還原編碼假影
（`_x000D_`→換行，是還原不是改寫）、**節錄**（只取需要的條目——選取不等於
修改）；**不可以**改寫、摘要、截斷任何一條釋義。關鍵動作：**把「不得改作」
寫成可執行的不變式**——守門測試抽驗 N 行斷言無假影、無截斷標記。授權義務
只寫在文件裡，擋不住下一個人做「效能優化：釋義只存前 50 字」；寫成測試才擋得住
（§66 精神）。姊妹律：**允許使用者修改內容與冒稱原文是兩件事**——教學頁讓老師
改字義（教學需要）是對的，但下載檔必須註明「若經教師修改則非原文」。出處標示
（attribution／license／source_url）要**隨資料走進 API 回應與產出檔**，不是只
放在 repo 的授權檔裡。

**留白欄位改自動帶入＝可升級設計的兌現**（§87 的下一步實證）：T1 因為沒有資料
而把字義／注音做成「可編輯欄位＋請自填」，T2 拿到權威資料後只是**預先填好**
——欄位不變、介面零改。當時若用啟發式硬湊或寫死唯讀顯示，這一步就得重做介面。
配套：權威值取代猜測（部首改採官方值、缺才退啟發式），但**不同維度的既有資訊
不該刪**（部件的四大類語意歸類與官方部首不互斥，保留為教學補充）；每個欄位的
提示文字誠實標示來源等級（「教育部，可修改」／「自動判別，可修改」／「請自填」）。

**能力邊界誠實**：官方另有標準讀音錄音（單字 1.52 GB），品質必勝瀏覽器合成
——但體積不可行就是不納入，於授權檔明載「未納入的資料」與原因、頁面標明發音
非官方錄音。不因為「官方有」就假裝我們有。

**環境事實包含時區**（續 §86/§87）：收工檢查的訊息檔新鮮度守門用**使用者本機
（台北 UTC+8）**日期，而雲端容器是 UTC——每天 UTC 16:00 後台北已跨日，命名一律
依**使用者本機日期**。先前兩次 STALE 警告曾被誤判為「我沿用舊日期」，改依台北
日期後不再出現＝根因確認。長壽會話要重取的環境事實清單自此是：git 基底、
當日日期、**時區**、裝置檔案現值。

---

## 89. 外部資產打包前先量「對本用途的覆蓋率」；量測數據留在 ADR 供翻案（2026-08-16 T3 新增）

教育部同一授權下也有官方插圖檔（856 張、13.5 MB、可商用）——「官方有、授權可、
技術可行」三個條件都成立，但**對本用途的覆蓋率**才是決策依據：實測教學頁只有
全字 12.0%／國小常用字 13.7%／常用 808 字 21.5%／最高頻 500 字 22.4% 能配到圖
（示範字「園」還沒圖），而代價是 repo 體積翻倍（`.git` 17 MB→約 31 MB）。約五個
常教的字命中一個，老師另外四個仍得自備——邊際價值撐不起永久成本，故不打包。
**對照組**：同一輪的辭典資料 2 MB 換 100% 字有字義（§88），命中率天差地別。
規則：外部資產（資料／圖庫／字型）打包前先量覆蓋率，不是看它總量多大或授權多
友善；**覆蓋率決定值不值得付永久成本**（repo 體積、部署相依）。承 §75（估工前
先盤 choke point）：這裡盤的是「命中率」而非工時。

配套三條：①**量測數據留在 ADR 供翻案**——列成表（樣本數／命中數／百分比／體積
影響），日後條件改變（覆蓋率提高、改按需抓不落地）可據以推翻，不必重做量測。
②**下結論前覆查自己的數字**——本輪我一度宣稱「索引引用的檔案有缺」，實為只數
了 `.jpg`、漏掉 237 個 `.gif`；錯誤數據會導出錯誤決策，斷言前先自我覆查。
③**產品定位寫成守門測試**——T3 最容易的擴張是「乾脆接影像生成」，那正是 §87
明確否決的方向；否決只寫在文件裡擋不住未來的自己，故加斷言「頁面不得出現任何
影像生成端點字樣」。與 §88 的 ND 授權守門同一手法：**定位與義務都不能只靠文件**。

附帶（自包含產出物）：可下載的離線產出物（教學單檔）內的圖片一律**內嵌
data URL**、不外連——外連＝在沒網路的教室破圖；配長邊上限與 canvas 縮放，
避免單檔膨脹。

---

## 90. 「借鏡落地」五步工作法：別人的作品是**需求證據**，不是實作藍圖（2026-08-16 兩弧歸納）

同一個工作階段用同一套流程落地了四個功能（R1a 骨架長肉引擎、T1/T2/T3 識字教學頁），
來源都是「看到別人做的東西」——一份參數化字型工作室、一份 LLM 生成的教學工具。五步：

1. **評估建議書**（進 `docs/analysis/`）：先盤**組件對照表**——哪些是本專案現成資產、
   哪些是真缺口、哪些不做。對照表往往顯示「對方的獨家賣點是我們的日常」（FANGCUN 的
   per-stroke path、教學工具的部件/筆順），真缺口通常只有一兩項。此文件成為後續每一輪
   的依據，不是寫完就丟。
2. **spike／資料查證**：**不估計，實測**。R1a 用三個字驗長肉品質（實測抓到「密筆畫糊成
   黑塊」，才有密度補償公式）；T2/T3 實際下載資料量體積與覆蓋率（辭典 2MB/100% vs 插圖
   13.5MB/12–22%，兩個相反結論都是量出來的，不是猜的）。
3. **QODA 規格 sign-off**：選項附**真實數據**（不是「A 比較好」而是「A 命中 22%、成本
   +13.5MB」），等明確同意才動工。
4. **實作＋守門同批**：新頁三配套（入口／設計鎖／路由快照，§87）、把**產品定位與授權
   義務寫成測試**（§88/§89）。
5. **收工文件當輪寫完**：WORK_LOG＋ADR＋原則，不積欠——功能 commit 與文件 commit 一比一
   交錯，是這段能連續四輪不亂的原因。

**核心心法：別人的作品是需求證據，不是實作藍圖。** 同好的工具證明了「單字→部件教學單頁」
是老師真正想要的（他提案兩個月、做了幾次才成功）——這個**需求已被驗證**的資訊極有價值；
但照抄它的實作（接 LLM 生成內容）會把它的弱點一併抄來（作者自己點名「資料都是 AI 生成，
使用前一定要確認」）。看到作品先問三題：**它的資料從哪來？使用者要不要查核？我手上有沒有
同等內容的可查證來源？**（承 §87）三題答完，多半會得到「同型需求、不同實作」的結論——
而那個不同，往往就是差異化本身。

**分輪原則**：每輪都要**獨立可用**（T1 就能上課、T2 免查核、T3 才完整），不要「三輪之後
才有東西」。前一輪的誠實留白（「請自填」）會讓後一輪變成純升級（預先填好、介面零改）。

---

## 91. 「看著舒服／怪怪的」先歸因再動旋鈕；比值變小 ≠ 特徵變弱（2026-08-20 S1 新增）

使用者說「這個圓體看著特別舒服，我也不知為何」。這類**感受型需求**最容易被直覺
接管：當下的假設是「舒服＝圓角克制（半圓不到）」，順著做就會去開一個「圓角程度」
旋鈕。實測後假設整個翻掉——那個字型是**全圓頭**（`R/(W/2)` ＝ 1.087 ≥ 1），圓角
一點都不克制；真正的差別是**筆畫比現行預設細三分之一**。

**做法三條**：

1. **先造指標，再量。** 把感受翻成一個可算的數（此例：終端圓角半徑 ÷ 半筆寬，
   0＝方頭、1＝全圓頭）＋一個對照組。指標要能**自驗**：拿已知答案的樣本先跑
   （方頭黑體應得 0、`buffer(cap=round)` 應得 1.0）。首版量到方頭黑體 ＝ 2.652
   就是量法錯了（尖角的轉折集中在單一頂點，卻把後續直線段也算進弧長）——**沒有
   自驗樣本，這個錯會一路帶進決策**。
2. **歸因結果決定要開哪個旋鈕。** 此例省下了一整個「圓角參數」功能（做了也沒用），
   換成「字重滑桿」——而且實測直接給出建議區間，不必再猜。**感受型需求的量測，
   產出的不是數字，是「該做什麼」。**
3. **比值變小 ≠ 特徵變弱。** 同字型的 Bold 版 `R/(W/2)` 從 1.087 掉到 0.615，看起來
   像「變方了」，但那是**分母（筆寬）變大**造成的——圓角**絕對半徑**兩者近乎相同
   （75 vs 69 EM），本來就是同一套圓角化程序。**看到正規化比值變動，先問分子分母
   哪個動了**，否則會把「粗一點」誤讀成「不圓了」而選錯字重。（承 §89 下結論前
   覆查自己的數字。）

**附帶兩條（同輪浮現，成本低價值高）**：

- **上游若把成品資產進版控，就 raw 直取，不要轉存自家 release。** 多數字型/資料
  專案只在 Release 放成品，所以「請使用者上傳到我們的 release」變成慣例；但**先探
  一次上游 repo 樹**（此例 `STATIC_OTF/` 目錄真的在版控裡，raw 200＋md5 與官方 zip
  逐位元組相同）就刪掉了一個人工阻塞步驟。順帶好處：散布的是**上游未經本專案改動
  的原檔**，OFL/ND 這類授權的遵循更單純。探的時候連分支名一起確認（此例是 `master`
  不是 `main`）。
- **沿用姊妹實作的措辭前，逐項查證原文。** 同為 OFL 就複製「Reserved Font Name: X」
  是很自然的手滑——實查上游 `LICENSE.md` 與字型 name table，版權方不是我以為的那個，
  且**根本未宣告保留字型名**。照抄等於**替上游發明一個它沒有主張的限制**。授權欄位
  永遠回原文核對，然後把登錄鎖成測試（承 §88）。

**新字源／新資產接線**：照 §49 兄弟實作掃描列出全部接點後，多加**兩道 parity 鎖**
——(a) UI 選項集合 ≡ registry 鍵集合；(b) 部署三處（抓取落點／env 值／模組內建檔名）
同名。這兩類漂移（只加模組沒加下拉、改檔名導致抓得到卻讀不到）以前只能靠人眼對。

---

## 92. 「該加什麼旋鈕」定了之後，還要盤「接在哪」——落點不是唯一的（2026-08-20 R1b 新增）

§91 量出了「該開的旋鈕是字重」。但那只指出**方向**，沒指出**落點**。本輪一半的
工時花在盤落點，而且盤出來的三個候選裡有兩個不及格——**如果沒盤，會照直覺選到
最廣的那個（真輪廓 ±δ，對七種字型都有效），然後做出一個調了也沒感覺的滑桿。**

**做法**：把每個候選落點的**天花板**量出來，並列一張表。天花板不是「能不能做」，
是「做出來能調多少」：

| 落點 | 覆蓋 | 可調範圍 | 致命限制 |
|---|---|---|---|
| 形態學 ±δ | 全部字源 | 筆寬 **±9%** | 有感的範圍就破字 |
| 現成參數（骨架長肉） | 單一引擎 | 大 | 只有 1,827 字、常用字命中 65% |
| 可變字體 `wght` 軸 | 單一字型 | 筆寬 **2.7 倍** | 只此一顆有；RSS +75 MB |

**「覆蓋最廣」和「調得最動」通常不是同一個落點**，而使用者要的是後者——一個
對七種字型都有效但只能調 ±9% 的滑桿，不如一個只對一種字型有效但能調 2.7 倍的。
**先量天花板再選，不要先選再想辦法。**

**提選項前先掃既有實作。** 本輪我把 ±δ 當成「還沒有的東西」提給使用者選——結果
`/api/stencil` 早就有 `bold_mm`（光柵膨脹）、前端也有控制項。數據是真的，選項
描述失真。落點盤查的第一步是 `grep`，不是量測。（承 §49 兄弟實作掃描——那條講
的是「改東西前掃全部接點」，這裡補的是「**提方案前掃全部既有方案**」。）

**新舊功能語意相近時，把差別寫進 tooltip 與 API description**，不要只寫在 ADR
裡：`bold_mm`＝事後膨脹濾鏡、`weight`＝字型本身的字重。使用者在畫面上看到兩個
都叫「變粗」的東西時，要能當場分辨。

### 92.1 正規化比值只是幾何的一半——方向與巢狀是另一半

本輪修「可變字體重疊輪廓」花了三版，每版都是**量出來才知道錯**，而三次的錯法
剛好構成一組完整的教訓：

1. **只看方向、批次做集合代數**（外環聯集 − 洞環聯集）→ 巢狀結構爆掉。「田」是
   口的洞裡再放十，一次性差集把十整個扣掉（面積 −33%）。
2. **只看巢狀深度、不看方向** → 落在別的筆畫**內部**的重疊筆畫被誤判為洞而扣掉
   （面積 −29%）。
3. **✔ 方向決定運算、依面積遞減逐環套用**（不批次）：父環必先於子環，洞裡的墨
   在洞挖掉之後才聯集回去；同向重疊落進同一次聯集、自然被吸收。

**通則：處理巢狀幾何時，「方向（winding）」與「包含關係」缺一不可，而且順序有
意義——批次集合運算會抹掉順序資訊。** 由外而內逐層套用，是唯一同時滿足兩者的
作法。

**推論：座標慣例不要寫死。** 第 1 版還順帶把方向判反了（Y-down 座標下外環是負
帶號面積，我照教科書寫成正的）。改成「**面積最大的環必為外環，以它的方向定義
外環方向**」——這在任何座標慣例下都成立，日後翻座標系也不會壞。**能從資料推出
的慣例，就不要寫成常數。**

### 92.2 上游同一顆資產的「靜態版」與「參數版」語意可能不同

字型的填充規則是 nonzero；靜態字重檔在建置時做過 overlap removal，所以下游拿
even-odd 畫也對。但**重疊消除的結果無法沿參數軸內插**，可變字體因此保留重疊
輪廓——同一個上游、同一個字重，靜態檔能用、參數檔不能直接用。

**通則：換用同一資產的「可參數化版本」時，不要假設它與靜態版逐位元等價；先拿
一個已知答案的參數點（此例 wght=700 對靜態 700B）做端對端比對。** 這個比對後來
成了守門測試（鎖墨面積 ±2%），也是發現 bug 的那次煙霧測試。

比對時**鎖不變式、不鎖實作巧合**（承 §66）：22 字裡 20 字面積差 <0.5%，剩 2 字
拓撲件數差 1 但面積差同樣 <0.5%——那是靜態檔 overlap removal 把「剛好相切」處
併掉造成的次像素差異。所以測試鎖**面積 ±2%**，不鎖拓撲件數。

### 92.3 新增昂貴能力時走雙軌，並把「預設不付代價」鎖成測試

可變字體首次取字 RSS +75 MB（Render 免費層 512 MB，§35–§38 才因 OOM 付過代價）。
解法是雙軌：**不給參數就完全不載入那個資產**，現有使用者的行為與記憶體足跡零
變動，成本只由主動用新能力的請求承擔。

關鍵是**這件事要有測試，否則「雙軌」只是註解裡的宣稱**。兩條鎖：

1. 不給參數時的輸出**逐點等同**新功能之前（零回歸鐵證）。
2. 把昂貴資產的路徑指到**不存在的檔**，預設路徑仍須完全正常，且內部 handle
   仍為 `None`。哪天有人把它提到 `__init__` 預載，這條立刻紅。

---

## 93. 中間量也要當結論看待：一輪八次量錯的共同結構（2026-08-20 昭源環方弧歸納）

§89 已經寫過「下結論前覆查自己的數字」。這一輪把那條**再收緊一級**：不只最終
結論要覆查，**任何要拿去下決策的中間量都要**——包括自己五分鐘前才算出來的那個。

依據是一個不太好看的統計：這一輪（S1＋R1b＋一份評估建議書）**量錯了八次**，
八次都靠再量一次抓回來（清單見
[`RETROSPECTIVE_2026-08_chiron_arc.md`](RETROSPECTIVE_2026-08_chiron_arc.md)）。
錯法可歸成五個結構，每個都有對應解法：

| 錯的結構 | 實例 | 解法 |
|---|---|---|
| **指標本身沒自驗** | 圓角量測把方頭黑體量成 2.652 | 拿**已知答案的樣本**先跑（方頭應得 0、`buffer(cap=round)` 應得 1.0）；對不上就是量法錯 |
| **指標選錯** | 用「輪廓數變化」判破字——加粗本來就會併輪廓 | 先問「這個數變動代表什麼」，答不出來就換指標（改用墨連通件數＋洞數） |
| **照抄姊妹實作** | OFL 版權方與保留字型名沿用思源黑體措辭，兩處都錯 | 回**原文**逐項核對，然後鎖成測試 |
| **假設兩版本等價** | 以為可變字體 @700 等於靜態 700B | 拿**已知參數點做端對端比對**（就是靠它抓到重疊輪廓的假洞） |
| **把 A 路徑的數據套到 B 路徑** | 從字模路徑的 EM 框偏移推論字帖也沒置中 | 直接量 B 路徑的**實際產出**，不跨路徑外推 |

**代價分佈很不平均，但抓回來的成本都一樣。** 八次裡只有兩次若沒抓到會真的傷人
（替上游發明一個它沒主張的授權限制、把假洞輸出給使用者），其餘多半只是浪費工。
但**復驗的成本都只是「再量一次」**——所以值得無差別地做，不必先判斷這次重不重要。

**寫作紀律的推論**：不要預寫尚未跑出來的數字。本輪 WORK_LOG 先寫了「tests 2103」
（猜的），實際 2070。**文件裡的每個數字都該有一次對應的執行**，沒有就先留空。

**與 §89 的分工**：§89 講「下結論前覆查」，§93 講「**什麼算結論**」——答案是
「任何你要據以做決定的數」。中間量之所以危險，正是因為它不長得像結論。

---

## 94. 新增光柵化／轉檔能力：先量記憶體再定介面，配額模型只准往安全側錯（2026-08-20 W1 新增）

W1 表面上是「把抄經既有的多頁 PDF 管線接到另外四個模式」——**接管線而已，
不是開發新能力**。但動手前的量測把介面設計整個改寫了一次：照抄那條的
`dpi=200` 預設，稿紙滿載（27 頁）峰值 465 MB，Render 免費層 512 MB 直接
OOM。**「複製一段在生產跑得好好的程式碼」不等於安全——原本的呼叫情境有
天然上限（經文長度固定），新情境沒有。**

**做法四條**：

1. **先找便宜的解，並實測它不成立。** 這裡是「Pillow 的 `append_images`
   吃不吃 generator」——若吃，記憶體就與頁數無關，整個配額問題消失。
   實測不吃（generator 466 MB vs list 462 MB，內部全部具現化）。**花五分鐘
   否證一個便宜解，好過花一小時設計不必要的複雜度，也好過假設它成立。**
2. **量到能寫成模型，而不是只量一個點。** 掃 dpi × 頁數的網格，讓模型能
   外推到沒量過的組合。第一版模型只有兩項，在低頁數高 dpi 低估——根因是
   **光柵器的工作緩衝隨單頁像素走、與頁數無關**，那是獨立的第三項。
   *模型不合的地方通常是漏了一個獨立的物理量，不是係數不夠好。*
3. **係數只准往安全側錯。** 低估會撞 OOM（死機），高估只是保守一點。所以
   取「所有量測點都不低估」所需的值再加一成，而不是最小平方擬合。並把
   **實測點直接寫進測試參數**——日後有人「優化」係數就會紅。
4. **超出配額要降級供應、不要只會拒絕**（承 §86）。自動下修解析度並以標頭
   誠實回報；連下限都塞不下才拒絕，且訊息要能行動（「請減少內容分批輸出，
   或改用 SVG／ZIP」）。

**介面設計的推論：先盤「哪些消費端已經有你要的資訊」。** 這裡三個模式走
共用的 page 標頭、已帶 mm 尺寸 → **接 PDF 零新參數**；只有 grid 是 px 座標
無紙張概念 → 只有它需要新的 `paper`／`margin_mm`。**先分類再設計，就不會
為了少數例外把所有人的介面都弄複雜。**

**能讓渲染器算的就別自己算。** grid 貼合紙張是包一層帶 mm 的外層 SVG、內層
用巢狀 `preserveAspectRatio="xMidYMid meet"`，不自己算縮放與置中——少一個
會算錯的地方。但**驗收要驗到畫面**：光看頁面尺寸對不出 `meet` 寫成 `slice`
（會裁切），所以掃輸出的非白像素 bbox 確認四邊都在留白內。

**共用出口的插入位置也是設計。** 三個模式各寫一份分支必然漂移（§76），抽成
一個「非本格式就回 None、呼叫端照原路走」的共用函式；而它**必須插在既有的
早退分支之前**——PNG 也要吃 `?page=N`，被 SVG 的早退攔下就永遠出不來。

### 94.1 擴充值域時，回頭找「拿它當反例」的既有測試

把 `pdf` 加進合法格式後，三個既有測試紅了——它們拿 `format=pdf` 當「顯然
無效的格式」的範例。**正確處置是換一個仍然無效的值（`tiff`）保留原意，
不是刪掉測試。** 擴充任何值域（格式、狀態、列舉）之後，都值得 grep 一次
舊值域的反例用法。

---

## 95. 深連結不是 API 整合；新元件對照參考實作驗，再拿獨立解碼器端到端驗一次（2026-08-20 W3 新增）

W3 要把「紙本掃碼連到線上字典」做出來。對方有 Open API，但**要註冊 api_key**
——執行期外部相依＋密鑰管理，正是 §68／§86 花兩輪根治掉的東西。結果根本用
不到：**它的詞條頁本身就是純網址**，編碼進 QR 不必連網、不必金鑰、離線可產。

**通則：想接外部服務時，先問「我需要的是它的資料，還是只是一個能到它的
入口？」** 若是後者，深連結就夠了，成本是零——而且只連不抓，也沒有轉存
內容帶來的授權義務。會漏掉這條，是因為「有 API」這件事本身會把人推向
「那就接 API」，而沒有先確認需求到底在哪一層。

### 95.1 兩層驗證：對照參考實作 ＋ 獨立解碼器

做一個有既定規格的元件（QR、條碼、校驗碼、序列化格式）時，正確性驗證分兩層，
**兩層問的是不同的問題**：

| 層 | 做法 | 回答的問題 | 進版控？ |
|---|---|---|---|
| 對照參考實作 | 反解自己的輸出，與函式庫的中間表示逐格比對 | **我寫錯了嗎？** | 是——天天跑、零新相依 |
| 獨立解碼器 | 拿真正的讀取器端到端解一次 | **成品真的能用嗎？** | 否——做一次、留紀錄 |

W3 的第一層是「把自組 SVG 反解回暗模組集合 ≡ `segno` 的 matrix」——座標算錯、
靜區位移、合併 rect 的寬度算錯都會紅。第二層是拿 OpenCV 的 QR 讀取器真的解，
四個字全部解回完全正確的網址。

**只做第一層的風險**：它證明的是「我和另一套實作算出一樣的東西」，**不等於
「掃得到」**——若兩邊對同一個規格有相同的誤解，或問題出在渲染層（線寬、
反鋸齒、對比），第一層完全看不到。**只做第二層的風險**：獨立解碼器通常要重
相依（OpenCV 幾十 MB），不適合進 CI，而且它告訴你「壞了」卻不告訴你壞在哪。

### 95.2 借用函式庫時，只借它難的那部分

`segno` 難的部分是編碼與 Reed–Solomon 糾錯（自己寫約 300 行，不該由本專案
維護）；它的 SVG writer 反而不合用（只吃 bytes buffer、配色與尺寸不好控）。
它剛好暴露了中間表示（`q.matrix`），所以**借編碼、不借輸出**，SVG 依既有
風格自己組——順帶還能做該做的優化（同列連續模組併成一個 `<rect>`，實測
573 → 282，內嵌進自包含檔時標記量減半）。

**選相依時多看一眼：它有沒有暴露中間表示？** 有的話，你就能只取難的那段，
輸出層留在自己手上。

### 95.3 守門的字面值掃描連註解都算——重寫措辭，不要放寬守門

本輪被既有守門攔兩次（新端點沒進路由快照、自組 `Response` 硬寫了 media
type）。第二個修完**還是紅的**：那道鎖是純文字掃描，連**註解裡**引用該字串
都算，而我正好在註解裡引用了它。

正確處置是**重寫註解措辭**，不是給守門加例外。純文字掃描型的守門本來就會
有這種誤傷面，但它換來的是「絕不漏抓」——為了一句註解的措辭去鑿一個洞，
是拿長期的可靠性換當下的方便。

---

## 96. 版面問題量測擋不住，要把圖印出來看；「放不下」有兩種，別混成一個參數（2026-08-20 W2 新增）

W2 把教育部辭典的釋義排到字帖頁尾。資料層的功課做得很足——6,028 條的義項
長度分佈、三種分隔樣態、字形路徑成本，全部量過寫進規格。第一版照規格寫完，
測試全綠。**產圖一看，三個地方都是錯的。**

### 96.1 相對於什麼，決定了它在紙上多大

註記字級定成 `EM_SIZE * 0.18`（格高的六分之一，A4 上約 9pt）——推理沒問
題，前提錯了。字帖整張會**等比縮放貼進 A4**，所以「格高的六分之一」在兩個
生字的窄字帖上會被同一個比例放大成半個標題。實測一列只排得下 11 個字。

**凡是會被整體縮放的東西，尺寸只能相對於「最後決定實際大小的那一層」。**
這裡是版面寬度，不是格高：`min(EM_SIZE*0.18, 版面寬/目標字數)`。取 `min`
保留上限，寬版面不會反過來讓字級無限放大。

同型的問題會出現在任何「先組版再貼合紙張」的管線上——W1 的 `fit_svg_to_
paper` 是這條產線的分水嶺，它之前的所有 em 尺寸都變成了相對值。

### 96.2 字形不保證填滿 em 框

「框頂＝y、框高＝字級」是很自然的假設，對**自家骨架字形**成立，對**字型檔
字形**不成立。noto_hei 的字形是基線相對的：實測墨跡落在 y∈[573, 2728]／
EM=2048——上方空 0.28 em、下方**超出框 0.33 em**。照框排版，最後一列被畫布
下緣削掉半個字，而所有斷言都是綠的，因為沒有一條在問「墨跡在不在畫布裡」。

處置不是查表寫死偏移量（換字型就錯），是**渲染時量出實際墨跡上下緣再排**。
這條和 §64「墨跡實框正規化」是同一個道理的兩次現身：**框是宣告，墨跡是事
實；排版要依事實。**

### 96.3 「放不下」有兩種，混成一個參數就會截到不該截的東西

第一版用一個 `capacity`（一列幾個字）同時處理兩件事：釋義太長、版面太窄。
結果 `meta` 欄位被一起截掉——`ㄒㄧㄚˋ` 掉了聲調記號。

這兩件事的性質完全不同：

| | 判準 | 處置 | 授權含意 |
|---|---|---|---|
| 內容太長 | 字數 > 預算 | 整段不放＋告示語 | **會動到內容，受 ND 約束** |
| 版面太窄 | 寬度不足 | **換行** | 不減字，與授權無關 |

分開之後，長度預算與版面寬度脫鉤，而「會不會動到內容」只剩**一個決策點**
（`compose_info_line`）。要違反規則得先改那一個函式——這正是 §88 說的「把
授權的線寫成機器守門」該有的形狀。

### 96.4 所以

- **有版面的功能，收工前一定要產圖用眼睛看。** 資料層量得再細，都量不到
  「印出來多大、有沒有被切到」。這次三個錯全部是產圖那一眼發現的，測試一
  條都沒抓到——因為我寫的斷言問的是「值對不對」，不是「看起來對不對」。
- 補上的鎖也要照這個教訓寫：`test_w2_footer_ink_fits_inside_the_canvas`
  算的是**墨跡下緣 vs viewBox 高**，不是「高度公式有沒有照我想的算」。
  **鎖現象，不鎖算式**（同 §66）。

---

## 97. 評估文件的風險註記是預繳的規格——落地輪把它寫成守門測試（2026-08-20 字帖借鏡弧歸納）

字帖借鏡弧四輪（W1→W3→W2→W4）照著評估建議書的排序做完，收工對帳時發現一個
四之四的型態：**建議書裡每一輪的風險註記，最後全都變成了機器守門**。

| 輪 | 建議書風險註記 | 變成的守門 |
|---|---|---|
| W1 | dpi × 頁數的記憶體 | 配額模型＋`RasterBudgetExceeded`＋誠實標頭 |
| W3 | 網址樣板要做成單一常數 | 單一事實源＋前端字面值掃描鎖 |
| W2 | 長釋義截不截是授權問題，只能整條放或不放 | 單一決策點＋原文子字串抽驗＋刪節號黑名單 |
| W4 | 標示要誠實，不能寫年級 | 「年級」字面值掃描（只許否定句） |

### 97.1 為什麼這條生產線值得固化

寫評估時被迫想清楚「這裡會出什麼事」；到了落地輪，那句話就是**現成的測試
規格**——而且是最便宜的一種，因為思考已經付過錢了。反過來不成立：落地後
才回頭想守門，得重新進入當時的風險脈絡，通常只想得起一半。

操作上是一個固定動作：**每輪開工第一步，回讀建議書該輪的風險註記，逐條問
「這句話的機器化長什麼樣」**。答案通常是三種之一：字面值掃描（W3/W4）、
單一決策點＋抽驗（W2）、量化模型＋安全側係數（W1）。

### 97.2 寫不成守門＝當初想得不夠具體

W1 的風險註記原文是「沿用抄經既有的節流與上限」——這句**寫不成測試**，
因為它是個未經驗證的假設。動手一量才發現既有節流根本擋不住（照抄 465MB
／上限 512MB），介面整個重設計。對照組是 W2 的「只能整條放或不放」——
一句話就能直接變成斷言。

所以這條原則有個反向用法：**評估時就用「這句風險寫得成守門嗎」自我檢查**。
寫得成＝風險已想具體；寫不成＝那裡藏著一個還沒做的量測，要嘛當場補量，
要嘛在建議書裡誠實標注「此處需先量測」。

### 97.3 邊界

風險註記變守門，不代表守門只來自風險註記——W2 的三個版面錯（§96）和 W4
的排序契約三根樁都是落地時才浮現的，該立照立。本條講的是**下限**：評估
文件裡已經寫下的風險，落地輪沒有理由讓它停留在散文。

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
    SVG/G-code/DXF 匯出＋evenodd 真裁切＋雷雕掃描填充；雲端工作階段。
    §十一/§十二另收 5dm→5do 字模字型弧）
  - [`WORK_LOG_2026-07-16.md`](WORK_LOG_2026-07-16.md)（5dp→5dv
    抄經深化弧：502 穩定性×2（sync def/loader 去重、字源工廠快取）＋
    麥克阿瑟著作權治理＋元素週期表三迭代（自繪→標準抄經紙→定位）＋
    逐字手寫互動新功能＋手寫可見修復）
  - [`WORK_LOG_2026-07-17.md`](WORK_LOG_2026-07-17.md)（5dw+5dx
    逐字手寫延伸到表格頁：5dw 週期表（table 分支能力偵測轉發 emit_cellmap）
    ＋5dx 部首/倉頡/注音（抽共用 cellmap emitter、三自繪 renderer 各吐疊層））
  - [`WORK_LOG_2026-07-18.md`](WORK_LOG_2026-07-18.md)（5ea→5eq
    全日大弧：抄經 500 修復＋逐字手寫▶播放/✎示範＋骨架/PDF 手寫層；切割風格
    registry 五弧（5ef 純重構→envelope→keep_primary→深度旋鈕→鏤空方向）＋
    中心線 Chaikin/RDP UI 四弧（塗鴉/字帖對稱）＋styled 逐字手寫範字三發（5en→5ep
    st/su 前綴修復→5eq 篆書範字挑對圖層別全 clone）；含 5ef~5ep 收工總結節）
  - [`WORK_LOG_2026-07-19.md`](WORK_LOG_2026-07-19.md)（跨日大階段：
    架構健檢全景審查＋四波路線圖→Wave 1 止血（5er async 掃全體/gzip/CI
    缺口/g0v bundle）→5es 503 OOM 搶修（JSONL 懶解析）→5et 手寫卡片模式
    弧五輪（/card 編輯器、三源字形、顏文字/塗鴉/SVG、版面自由度、外框/
    印刷 PDF/PNG）；**第二階段**：W2 快取層＋單一事實源（5eu/5ev）→
    W3 後端拆分兩輪（server.py 5,010→269）→ W4 前端拆分兩輪
    （index.html 10,859→3,255、16 ES modules）——健檢四波全數執行完畢；
    **第三～七階段**：5ew 手寫整合＋5ex~5fb 渲染治理鏈＋5fa 部件合成＋
    5fc~5fe 版面/深連結/正方化＋5ff~5fh 表格可見度三部曲＋
    5fi~5fl 版本標籤與資料區終局收斂）
  - [`WORK_LOG_2026-07-22.md`](WORK_LOG_2026-07-22.md)（逐字手寫範字大小線
    三批：5fm 移除 1.4× 硬放大改墨跡實框正規化（彈窗＋獨立頁）＋收工檢查.bat
    當日新鮮度守門＋5fn 抄經彈窗補正規化（不同建構器漏改一輪）；含守門鎖字面／
    裸 push 誤入備份庫／橋接 git 留 index.lock 三事故。**另收 5et-R5**：卡片模式
    加尺規＋卡緣摺邊虛線＋子模組 import 快取缺口白畫回歸根治）
  - [`WORK_LOG_2026-07-23.md`](WORK_LOG_2026-07-23.md)（兩場。第一場：立體字
    卡片鏤空 pop-up 全弧：機構迭代（逐筆 tab 誤讀彎路→實體折紙照片定案箱型）＋
    Phase 3 網頁模式（popup.py／/popup 頁／/api/popup/svg／popup.html）＋
    缺字型測試 skip+503＋run-based 連通標記後備。**第二場**：跨會話 covert
    clobber 事故善後＋5fo（/gallery 版本注入＋手刻掃全站回歸鎖）→全站 UX 稽核
    （13 模式＋3 頁，[`UX_AUDIT_2026-07-23.md`](UX_AUDIT_2026-07-23.md)）→
    5fp P0／5fq P1／5fr P2／5fs 四項規格／5ft 立體字分類／5fu 共用控制列
    三統一——稽核項全數清空上線，v0.14.264→0.14.270。**第三場**：公眾分享庫
    大擴建 5fv~5fz——統一出口信封（choke point 一輪接 11 模式）→15 分類＋
    分類下拉→檢舉（匿名/登入、IP 雜湊去重、三層防機器人）＋管理端（緊急
    下架/作者審閱/黑名單）→文字黑名單詞庫＋首次上傳 24h 審閱期（懶釋放免
    cron）→Brevo HTTP API 寄信（Render 封 SMTP 的根治）；兩 live bug 修＋
    端到端實測打通，v0.14.271→0.14.275）
  - [`WORK_LOG_2026-07-25.md`](WORK_LOG_2026-07-25.md)（設計真理源與全站
    設計一致性弧 5ga~5gf＋5gc：DESIGN.md 成文＋同步鎖→5gb 主頁/分享庫
    一致性（info 雜色歸一/分頁紅高亮修藍/ES ?v= 六處收口）→5gc 收工腳本
    訊息檔消費制（跨日 STALE 根治、首航歸檔 191）→5gd 跨頁配色按鈕統一
    （--accent 三頁三義根治/sutra-editor 紅主鈕/popup GitHub 灰系接軌/
    藍同值鎖六處）→5ge 版面一致性（容器三檔與斷點成文/760+767 分岔修平/
    ←回主頁統一）→5gf 識別色 16 token 化（31 處 chip-bg/回流鎖 21 色/
    視覺零變 E2E），v0.14.276→0.14.280）
  - [`WORK_LOG_2026-08-11.md`](WORK_LOG_2026-08-11.md)（FANGCUN 參數化字型
    評估→R1a 骨架長肉字模引擎全弧：評估建議書（R1~R4 選項）→spike 實證
    （A/B 路線＋密度補償）→R1a 實作（skeleton_glyph.py＋popup 降級階梯
    noto_hei→skeleton→503＋glyph_source 誠實標注）→本機 shapely 離線安裝
    →§69 再犯 clobber 事故（收工檢查 6 紅攔下）＋fetch 對齊重做）
  - [`WORK_LOG_2026-08-15.md`](WORK_LOG_2026-08-15.md)（漢字部件互動教學
    評估→T1 識字教學頁：六組件對照（四項現成/TTS 用瀏覽器/字義造詞待 T2）
    ＋/teach 頁＋/api/radical-info＋主頁入口＋設計鎖三配套；含長壽會話
    日期漂移事故）
  - [`WORK_LOG_2026-08-16.md`](WORK_LOG_2026-08-16.md)（T2 教育部辭典接入：
    資料查證（6.9MB 文字庫/欄位含注音部首/讀音檔 1.5GB 排除）＋兩 QODA
    決策（打包進 repo、官方值優先）＋build 腳本/懶載資料源//api/dict/
    教學頁自動帶入＋ND 授權治理與機器守門；含 STALE 警告時區破案。
    **同日續收 T3**：插圖槽——先量官方插圖覆蓋率（12～22%）決定不打包、
    老師自備圖內嵌 data URL、「不做生成」鎖成守門）
  - [`WORK_LOG_2026-08-20.md`](WORK_LOG_2026-08-20.md)（S1 昭源環方圓體字模：
    前置量測把「看著舒服」歸因（推翻圓角假設，真因是筆畫細三分之一）→上游
    `STATIC_OTF/` 進版控故 raw 直取、刪掉使用者上傳阻塞→用殘腔 0 判準實測選
    700B 而非 400R→七個接點全接＋兩道 parity 鎖→OFL 版權方與保留字型名查證訂正，
    v0.14.286）
  - [`RETROSPECTIVE_2026-08_chiron_arc.md`](RETROSPECTIVE_2026-08_chiron_arc.md)（**昭源環方弧總回顧**：一句「看著特別舒服」→ 量化歸因 → S1 字模來源＋R1b 字重軸；跨弧決策總覽表、八次量錯的共同結構與代價分佈、五道 parity 鎖、字帖弧待辦盤點，對應 §91–§93）
  - [`RETROSPECTIVE_2026-08_teach_arc.md`](RETROSPECTIVE_2026-08_teach_arc.md)（**跨弧總回顧**：FANGCUN→R1a／教學工具→T1-T3 兩條「借鏡落地」弧、8 commit、
    跨弧決策總覽表、三次踩坑的共同根因（環境事實過期）、待辦盤點與產出清單）
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
  - [`2026-07-15_5dm_5do_stencil_font_seal.md`](decisions/2026-07-15_5dm_5do_stencil_font_seal.md)（字模字型與切割精修弧：黑體字模＋切割風格庫＋崇羲繁簡＋佛經缺字，對應 §16–§18）
  - [`2026-07-16_5dp_5dv_sutra_periodic_handwrite.md`](decisions/2026-07-16_5dp_5dv_sutra_periodic_handwrite.md)（抄經深化弧：502 成本模型＋著作權治理＋週期表三迭代＋逐字手寫＋渲染分流，對應 §19–§25）
  - [`2026-07-17_5dw_periodic_handwrite.md`](decisions/2026-07-17_5dw_periodic_handwrite.md)（逐字手寫延伸表格頁：單一未轉發旗標＋registry 能力偵測分派＋重用複利，對應 §26）
  - [`2026-07-17_5dx_table_handwrite.md`](decisions/2026-07-17_5dx_table_handwrite.md)（逐字手寫延伸部首/倉頡/注音：跨層契約單一真相源＋可寫格語意邊界，對應 §27）
  - [`2026-07-18_5ef_5ep_stencil_registry_centerline_styled.md`](decisions/2026-07-18_5ef_5ep_stencil_registry_centerline_styled.md)（切割 registry 純重構先立 seam＋Jordan 巢狀深度/blob-leak＋方向↔牆對偶/runtime 旋鈕＋同源平滑套全消費點/cache key＋styled 字形 reuse 伺服器 SVG＋真實渲染 e2e/su-st 前綴，對應 §28–§33）
  - [`2026-07-18_5eq_handwrite_ref_layer.md`](decisions/2026-07-18_5eq_handwrite_ref_layer.md)（逐字手寫篆書範字太粗——styled 範字 reuse 多圖層 SVG 要挑對代表層、別全 clone 拉 opacity=1，對應 §34）
  - [`2026-07-19_arch_review_wave1_5es.md`](decisions/2026-07-19_arch_review_wave1_5es.md)（架構線：全景健檢＋Wave 1 止血＋503 OOM 修復，對應 §35–§38）
  - [`2026-07-19_5et_card_mode.md`](decisions/2026-07-19_5et_card_mode.md)（5et 手寫卡片弧五輪 QODA 重放，對應 §37–§40）
  - [`2026-07-19_w2_cache_single_source.md`](decisions/2026-07-19_w2_cache_single_source.md)（W2 快取層＋單一事實源 5eu/5ev QODA 重放：純 ASGI vs BaseHTTPMiddleware、cache_bus 分層、pyproject 優先版本源、badge 自動化）
  - [`2026-07-19_w3_w4_decomposition.md`](decisions/2026-07-19_w3_w4_decomposition.md)（W3＋W4 前後端巨石拆分四輪 QODA 重放，對應 §41–§45）
  - [`2026-07-19_5ew_handwriting_integration.md`](decisions/2026-07-19_5ew_handwriting_integration.md)（5ew 手寫整合弧五輪 QODA 重放：分段載入語意/共用儲存層誠實降階/adapter 事件時綁定/E2E 環境隔離/純屬性錨點/兄弟實作掃描，對應 §46–§49）
  - [`2026-07-19_5ex_5fb_render_resource_governance.md`](decisions/2026-07-19_5ex_5fb_render_resource_governance.md)（渲染資源治理鏈六件套 QODA 重放：量測先行/快取-閘門-中止-分段-回收-縮批重試/opencc race/併發測試方法學，對應 §50–§52）
  - [`2026-07-19_5fa_seal_compose.md`](decisions/2026-07-19_5fa_seal_compose.md)（篆體缺字部件合成：誠實放棄曲線/標示/相容分流；週期表缺字 60→0、62 字合成，對應 §53）
  - [`2026-07-19_5fc_5fe_layout_deeplink_seal_square.md`](decisions/2026-07-19_5fc_5fe_layout_deeplink_seal_square.md)（筆順練習版面三輪＋深連結分流＋合成正方化：hidden 全域歸位/grid 動態插入雙陷阱/bbox 正規化/三態驗收/版本注入與 exact-URL 重放，對應 §54–§57）
  - [`2026-07-19_5ff_5fh_table_visibility.md`](decisions/2026-07-19_5ff_5fh_table_visibility.md)（表格隱形字三部曲：可見度契約歸位/traced_run 三態降級/覆蓋稽核白名單/實機活體 DOM 診斷/「暫時性」誤判訂正，對應 §58–§60）
  - [`2026-07-19_5fi_5fl_version_label_data_area.md`](decisions/2026-07-19_5fi_5fl_version_label_data_area.md)（主頁版本標籤注入＋資料區三輪收斂到左欄一條龍：終局測試治理/清空二次確認實測攔截力/先重現帶證據問/截圖折抵驗收，對應 §61–§63）
  - [`2026-07-22_5fm_5fn_ink_bbox_normalization.md`](decisions/2026-07-22_5fm_5fn_ink_bbox_normalization.md)（逐字手寫範字大小：墨跡實框正規化為跨呈現面共用契約／改共用下游巡全消費路徑／守門鎖不變式／收工檢查當日新鮮度守門，對應 §64–§66）
  - [`2026-07-22_5et_r5_card_ruler_fold_cachebust.md`](decisions/2026-07-22_5et_r5_card_ruler_fold_cachebust.md)（手寫卡片模式加尺規＋卡緣摺邊虛線；子模組 import 快取缺口根治整類＋守門，對應 §67）
  - [`2026-07-23_popup_hollow_box.md`](decisions/2026-07-23_popup_hollow_box.md)（立體字卡片鏤空 pop-up 網頁模式：紙藝機構先實體試折定案／別把一條摺線複雜化成逐筆 tab／鏤空字材料實色／可折合對稱＋單一連通不變式／部署期字型相依缺則 skip+503／選用相依 scipy 降級 numpy，對應 §68）
  - [`2026-07-23_5fo_5fu_ux_audit_arc.md`](decisions/2026-07-23_5fo_5fu_ux_audit_arc.md)（covert clobber 前進修復＋開工三步對表／手刻版本掃全類回歸鎖／UX 稽核分級 sign-off 分輪工作法＋稽核發現現場再驗證／色彩語意藍主動作紅破壞性／卡片逐字手寫重用深連結參數路／分享庫新分類 registry 派遣零 API＋metadata 內嵌憑據／共用控制列三層次統一不硬搬絕對位置，對應 §69–§74）
  - [`2026-07-23_5fv_5fz_gallery_kinds_protection_email.md`](decisions/2026-07-23_5fv_5fz_gallery_kinds_protection_email.md)（分享庫大擴建十決策 QODA：B 案 choke point 翻案／統一信封／匿名+登入檢舉 IP 雜湊去重／三層防機器人零外依／管理員環境變數制／XSS 與黑名單拒收不改寫／審閱期懶釋放＋防護優先序／視角 fixture 測試遷移／SMTP 封鎖查證與 Brevo 選型／Brevo IP 白名單取捨；附 live bug 雙教訓，對應 §75–§80）
  - [`2026-07-25_5ga_5gf_design_truth_arc.md`](decisions/2026-07-25_5ga_5gf_design_truth_arc.md)（設計真理源弧八決策 QODA：自寫 DESIGN.md 非套模板＋同步鎖／盤點複選分輪掃債節奏／info-accent 歸 primary 與回流鎖豁免工法／ES ?v= 同模組一批補／收工腳本消費制取代日期啟發式／--accent 同名反義語意歸位逐點判別／版面統一＝例外成文分岔修平／識別色 token 化值不變＋視覺零變驗收；附掃債量測數據表，對應 §81–§85）
  - [`2026-08-11_r1a_skeleton_glyph.md`](decisions/2026-08-11_r1a_skeleton_glyph.md)（R1a 骨架長肉字模四決策 QODA：A 路線骨架 buffer（B 另案）／輸出契約對齊 _outline_to_polylines drop-in／降級供應＋誠實標注不無聲頂替／新欄位 getattr 替身防禦；附 §69 長壽會話再犯事故重放，對應 §86）
  - [`2026-08-15_t1_teach_page.md`](decisions/2026-08-15_t1_teach_page.md)（T1 識字教學頁四決策 QODA：不接 LLM 用靜態可查證資料／瀏覽器 TTS 當主路徑／沒有的資料留白給人不猜／新頁三配套同批；附長壽會話日期漂移事故，對應 §87）
  - [`2026-08-16_t2_moe_dict.md`](decisions/2026-08-16_t2_moe_dict.md)（T2 教育部辭典四決策 QODA：資料打包進 repo 不走部署抓／ND 授權劃清載體轉換與內容改寫並寫成機器守門／官方值優先但不同維度既有資訊保留／1.5GB 讀音檔誠實不納入；附 STALE 時區破案，對應 §88）
  - [`2026-08-16_t3_pic_slot.md`](decisions/2026-08-16_t3_pic_slot.md)（T3 插圖槽三決策 QODA：先量覆蓋率決定不打包官方插圖（附量測表供翻案）／插圖內嵌 data URL 不外連／「不做生成」定位鎖成守門測試；含數據誤判訂正，對應 §89）
  - [`2026-08-20_w3_qr.md`](decisions/2026-08-20_w3_qr.md)（W3 QR code 四決策 QODA：只做深連結不碰要金鑰的 API／放 /teach 零回歸不放 grid／連教育百科不連沒有 ID 的簡編本／加 segno 但只借編碼不借它的 SVG writer；驗證分兩層——對照 segno matrix ＋ OpenCV 獨立解碼；附 segno 授權 MIT→BSD 訂正，對應 §95）
  - [`2026-08-20_w2_info_footer.md`](decisions/2026-08-20_w2_info_footer.md)（W2 字帖頁尾生字資訊區五決策 QODA：取第一個完整義項要嘛整條要嘛不放／長度預算與版面寬度脫鉤（內容太長換告示語、版面太窄換行）／字級相對版面寬不綁格高／註記走 noto_hei 並在渲染時量墨跡上下緣／opt-in 且關著時連字典都不查；附三個產圖才發現的版面錯，對應 §96）
  - [`2026-08-20_w4_freq_pick.md`](decisions/2026-08-20_w4_freq_pick.md)（W4 分級選字三決策 QODA：只接唯一有字頻的表不給假難度軸／純前端切片零新端點（排序即契約，三根樁釘死：連續無跳號＋端點≡檔案序＋已知答案樁）／填入而非鎖定＋誠實標示「字頻不代表年級難度」鎖成守門；本輪未立新原則——踩點皆 §93/§95 再套用）
  - [`RETROSPECTIVE_2026-08-20_worksheet_arc.md`](RETROSPECTIVE_2026-08-20_worksheet_arc.md)（字帖借鏡弧收工：一份建議書四輪照序落地零改序／風險註記四之四變成機器守門（→§97）／守門攔自己三次皆改措辭不放寬／測試全綠但圖是錯的（→§96），對應 §94–§97）
  - [`2026-08-20_w1_page_pdf.md`](decisions/2026-08-20_w1_page_pdf.md)（W1 字帖多頁 PDF/PNG 四決策 QODA：先量記憶體發現照抄會 OOM 並否證 generator 串流／配額模型補上光柵器工作緩衝第三項且係數只准高估／grid 貼合紙張其餘三模式零新參數／三模式共用一份出口且須插在早退分支之前；附兩個自己的錯——鎖到 ZIP 時戳、既有測試拿 pdf 當反例，對應 §94）
  - [`2026-08-20_r1b_weight_axis.md`](decisions/2026-08-20_r1b_weight_axis.md)（R1b 字重滑桿四決策 QODA：三個落點各量天花板後選可變字體軸（±δ 只能調 ±9%、骨架長肉只有 1,827 字）／雙軌記憶體並把「預設不付代價」鎖成測試／夾限以出貨中的靜態檔當基準線／可變字體重疊輪廓補正三版才對（方向×巢狀×順序）；附「提選項前沒掃既有 bold_mm」訂正，對應 §92）
  - [`2026-08-20_s1_chiron_round.md`](decisions/2026-08-20_s1_chiron_round.md)（S1 昭源環方圓體字模四決策 QODA：感受型需求先造指標量測再決定開哪個旋鈕（推翻圓角假設）／上游成品進版控就 raw 直取免轉存自家 release／用殘腔 0 判準與餘裕選 700B 並鎖成筆寬測試／七接點全接＋UI-registry 與部署三處 parity 鎖；附 OFL 版權方訂正，對應 §91）
  - [`2026-07-11_5bt_5ch_doodle_engines_teaching_route.md`](decisions/2026-07-11_5bt_5ch_doodle_engines_teaching_route.md)（**塗鴉引擎體系 × 教學路線，全日 QODA 重放**）
  - 各 phase 詳細：`docs/decisions/2026-05-0[456]_phase*.md`
- Personal-playbook cross-link：
  - `2026-05-06_r29-r29k_principles.md`（在 personal-playbook repo，跨 ref 案例 §B.15-B.23）
- 已存 memory：`/sessions/friendly-dreamy-noether/mnt/.auto-memory/MEMORY.md`

---

**寫這份的目的**：把跨 phase 浮現的「不只此一處適用」工程習慣固化下來。下次新 phase 開動前可快速 scan 一遍 — 「我這次該套用哪幾條？」比每次重發明強。

§1-5 是 **implementation-time** 原則（寫 code 時）；§6 是 **design-time** 原則（把願景轉 spec 時）；§8-§97 是 **runtime/整合** 原則（降級、外部資源、跨環境檔案、實機驗收、資料源選型、根因再挑戰、區段模型與互動編輯、工法規則與互動狀態、引擎正交與匯出管線與雲端工作階段、字型即根因/範本學技法、主體字型為準、依墨置中/量對旋鈕、重端點 sync def/loader 記憶化、昂貴工廠快取與失效、目錄 ready-gating、描紅表格頁重用米字格/mockup 先行、互動地基伺服器發 data-* 標記/重用既有存儲、變體版面塞進原頁型、渲染層依來源分流/驗到畫面、registry 能力偵測分派/重用複利、跨層契約單一真相源/可寫格語意邊界、registry 先純重構立 seam、單一 blob 局部量測 leak/Jordan 巢狀深度、方向↔牆對偶/runtime 旋鈕、同源演算法套全消費點/tuning 進 cache key、styled 字形 reuse 伺服器 SVG、讀 DOM 元素 bug 對真實渲染跑 e2e、styled 範字 reuse 多圖層 SVG 挑對代表層別全 clone、鐵則掃全體配機器回歸鎖、目標環境資源天花板/JSON 物件膨脹、0 合法值禁 || 預設、future annotations 下 model 模組層、外部內容單一 sanitize 入口/縱深防禦、編輯器單一渲染路徑/純函式層下沉、兩輪制重構、by-value 陷阱簇、module 翻轉語意/快照鎖、跨檔邊三定律、斷言歸源、單例互動元件綁事件當下、E2E 環境變數隔離、純屬性錨點契約、兄弟實作掃描/console error 訊號、併發測試單迴圈 gather/boot 安定、渲染治理鏈六件套、量測逐層歸因複驗、缺字合成誠實放棄曲線、hidden 被元件 display 蓋掉全域歸位、grid 動態插入/跨欄 max-content 雙陷阱、內容 bbox 映射槽位/三態覆蓋率驗收、版本注入不手刻/exact-URL 重放判暫時性、驗到看得見/有效可見度稽核、借用渲染器核對全部開關/兄弟實作歸一、資料表覆蓋稽核白名單、版面收斂終局測試/搬家掃歷代版位斷言、不可復原操作二次確認/實測攔截力、需求先重現帶證據問/截圖折抵驗收、墨跡實框正規化跨呈現面共用契約/改共用下游巡全消費路徑、脆弱慣例升級自動閘門/fail-open 新鮮度守門、守門鎖不變式不鎖寫法、版本快取鍵覆蓋整條 import 圖/子模組 import 也帶 ?v=、紙藝機構先實體試折定案不把一條摺線複雜化成逐筆 tab/鏤空字材料實色＋連筋單一連通/可折合對稱不變式/部署期字型相依缺則 skip+503/選用相依降級、跨會話寫回前三步對表/未推 commit 勿盲 reset/多輪堆疊訊息累積式、手刻漏 guard 類病回歸鎖掃全類/guard 每獨立檔皆備、UX 稽核分級 sign-off 分輪/稽核發現現場再驗證、checkVisibility 判收合/佈局斷言 id 錨定/幾何斷言容換行、UI 統一三層次同名同序相鄰不硬搬絕對位置、新分類 registry 派遣零 API/憑據內嵌檔案自身/深連結參數路重用複利、估工前先盤 choke point、白名單下沉單一事實源/E2E 驗回應不只驗請求、防機器人三層法/加鹽雜湊去重、防護疊加優先序/自動機制只回收自因/懶釋放免 cron、行為變更視角 fixture 遷移測試、平台限制先查官方文件/錯誤訊息寫明可辨病因、設計真理源成文→立鎖→分輪掃債、token 同名反義語意歸位/回流鎖豁免同批設計、統一＝例外成文分岔修平、視覺零變重構驗 computed style 原值、啟發式守門升級狀態機消費制、降級供應同格式後備＋誠實標注/替身 getattr 防禦/實證錨點鎖常數/長壽會話每輪對表、借鏡外部 AI 作品優先靜態可查證資料/沒有的資料留白不猜/新頁三配套同批/環境事實每輪重取、ND 授權劃清轉換與改寫並寫成機器守門/出處隨資料進回應與產出檔/留白改自動帶入是可升級設計/環境事實含時區、外部資產先量對本用途覆蓋率再打包/量測數據留 ADR 供翻案/下結論前覆查數字/產品定位寫成守門、借鏡落地五步工作法/別人的作品是需求證據不是實作藍圖/每輪獨立可用、感受型需求先造可自驗指標再歸因決定開哪個旋鈕/比值變小先問分子分母哪個動了/上游成品進版控就 raw 直取/沿用姊妹措辭前查證授權原文/UI-registry 與部署三處 parity 鎖、旋鈕定了還要盤落點並各量天花板/覆蓋最廣≠調得最動/提方案前先掃既有實作/巢狀幾何方向與包含缺一不可且順序有意義/座標慣例能從資料推就不寫死/同資產靜態版與參數版語意未必等價要拿已知參數點端對端比對/新增昂貴能力走雙軌並把預設不付代價鎖成測試、中間量也要當結論看待/指標要拿已知答案自驗/不預寫尚未跑出的數字、新增光柵化能力先量記憶體再定介面/先花五分鐘否證便宜解/量到能寫成模型且係數只准往安全側錯/先盤哪些消費端已有你要的資訊再設計介面/能讓渲染器算的別自己算但要驗到畫面/擴充值域後回頭找拿它當反例的舊測試、深連結不是 API 整合先問要資料還是要入口/有規格的元件對照參考實作驗再拿獨立解碼器端到端驗一次/借函式庫只借它難的那部分看它有沒有暴露中間表示/守門的字面值掃描連註解都算應重寫措辭而非放寬守門、有版面的功能收工前一定要產圖用眼睛看／會被整體縮放的尺寸只能相對於最後決定實際大小的那一層／字型檔字形不保證填滿 em 框要量墨跡／「內容太長」與「版面太窄」是兩件事別混成一個參數、評估文件的風險註記是預繳的規格落地輪寫成守門／風險寫不成守門＝當初想得不夠具體該補量測）。三者互補。
