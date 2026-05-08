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
