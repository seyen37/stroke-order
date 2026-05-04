# PROJECT_PLAYBOOK Pending Addenda — 2026-05-04

> **這份檔案是草稿、不是 SoT**。
>
> 依 4/29 divergence decision log §8.2 約定：**personal-playbook = SoT**。
> 此檔列出 `.auto-memory/` 中 r25–r28 沉澱的 11 條共通性原則，**尚未** codify 到
> `personal-playbook/PROJECT_PLAYBOOK.md`。請 cherry-pick 到 SoT，再 sync 回此 repo。
>
> SoT 路徑：`C:\Users\USER\Documents\Cowork\personal-playbook\PROJECT_PLAYBOOK.md`
>
> Cherry-pick 流程：
> 1. 在 personal-playbook repo 跑 `git fetch && git status` 確認最新狀態
> 2. 動筆前讀完 §3 / §5 / §8 確認編號未被佔用（依 4/29 教訓）
> 3. 把下方草稿章節貼進對應位置 + 調整 cross-ref + 真實案例引用
> 4. Commit 到 personal-playbook + push
> 5. 反向 sync 到 stroke-order/docs/PROJECT_PLAYBOOK.md
> 6. 刪本檔（pending addenda 已落地）

---

## 草稿總覽

| 編號 | 標題 | 來源 memory | 既有交叉引用 |
|---|---|---|---|
| §3.10 (新) | Cowork sandbox git index 操作 SOP | `feedback_cowork_git_index_single_batched_add.md` | 補 §3.6 / §3.9 |
| §3.11 (新) | i18n 檔名：原文 + slug 雙存 | `feedback_i18n_filename_dual_storage.md` | 配 §3.7 跨電腦 |
| §3.6+ | PowerShell 指令給法（補完整） | `feedback_powershell_commands.md` | 既有 §3.6 排查表 |
| §5.8 (新) | 跨 phase 共享檔的 commit 策略 | `feedback_cross_phase_commit_honest_label.md` | 補 §5 / 連 §3.9 |
| §8.16 (新) | Mixed-arity tuple 解構 pattern | `feedback_mixed_arity_tuple.md` | 算 §8.x 演算法系列 |
| §8.17 (新) | 多輪 reference-image 視覺迭代 SOP | `feedback_iterative_visual_loop.md` | 擴展 §8.15 |
| §8.18 (新) | YAML frontmatter + Markdown body 雙層格式 | `feedback_md_frontmatter_body_format.md` | r27 |
| §8.19 (新) | Schema versioning：嚴格 + migration table | `feedback_schema_versioning_with_migration.md` | r27，配 §8.18 |
| §8.20 (新) | By-kind dispatch dict 取代 if/elif | r28 候選（尚未寫 memory） | r28 |
| §8.21 (新) | Schema 通用化時 dual-write 漸進遷移 | r28 候選（尚未寫 memory） | r28，配 §8.19 |

> 「自動寫決策日誌」（`feedback_decision_log.md`）已被既有 §5 整章涵蓋，**不需新章節**。

---

## §3.10（新）Cowork sandbox git index 操作 SOP

> Cowork sandbox 的 git index 在連續寫入時會 corruption，連續 `git add` 多次會撞
> `bad signature 0x00000000`。預先重建 index、用單一 batched add，可穩定避開。

### 何時必跑

- 用 cowork sandbox 終端機操作 git
- 上一場 session 留下未 commit 的檔案，現場準備 stage（高風險區）
- 出現 `bad signature 0x00000000` / `index file corrupt`

### 標準 SOP

**A. 開工前預先重建 index（防禦性）**
```bash
rm -f .git/index && git read-tree HEAD && git status --short
```

**B. 用單一 batched `git add`**（**不**用 `&&` 串多 call）：
```bash
# ✅ Good — 一次到位
git add file1 file2 file3 docs/*.md tests/*.py

# ❌ Bad — 連續多 call 容易撞 corruption
git add file1
git add file2
git add file3
```

**C. 出現 corruption 時的修復**
```bash
rm -f .git/index && git read-tree HEAD
git status --short  # 確認 working tree 改動還在
git add <files batched>
git commit -m "..."
```

**D. Stale lock 處理**
```bash
ls .git/index.lock 2>&1   # 看上場 session 是否留下
# 確認沒有實際 git process 在跑（ps aux | grep git）
rm .git/index.lock
```

**E. 0-byte 垃圾檔 / stale lock 刪除受限**

Cowork sandbox 預設 `rm` 會 `Operation not permitted`。要先 mcp 授權：
```
mcp__cowork__allow_cowork_file_delete(file_path=...)
```
再 `rm`。

### Push / Pull

Sandbox 內**沒有 SSH key**，push / fetch 會撞 `Permission denied (publickey)`。
Push 必須在 user 自己 terminal 跑：
```bash
git fetch origin
git push origin main
git push backup main  # 雙 remote
```

### 真實案例

stroke-order 2026-05-04 整理 5b r1-r26 + 12m-7 r39 累積 commit。第一次連續 `git add ... && git add ... && git add ...` 立刻撞 index corrupt。改成 batched + 重建 SOP 後 4 個 commit 全成功。詳 `docs/journal/2026-05-04_session_log.md`。

### 反例

- 只 `rm .git/index.lock` 但不重建 index → 後續 `git add` 仍可能撞 corrupt
- 用 cowork sandbox 嘗試 `git push` → 永遠失敗，省下這次嘗試

### Cross-ref

- §3.6 git 排查表（已有 `index.lock` 處理一條，可加 `bad signature` 修復）
- §3.9 跨 AI session race（cowork sandbox 是衍生 case）

---

## §3.11（新）i18n 檔名：原文 + slug 雙存

> 中文 / 非 ASCII 標題的下載檔，filename 用 slug（拼音 / transliteration）保跨平台
> 穩定性，但檔內 metadata **同時保留原文** 給系統 / AI 看得懂語意。

### 為什麼雙存

| 場景 | 純中文檔名 | 純拼音檔名 | 雙存 |
|---|---|---|---|
| 現代 Mac / Windows 本機 | ✓ | ✓ | ✓ |
| Email 附件 | ⚠️ 偶爾 mangle | ✓ | ✓ |
| S3 key / CDN URL | ✗ | ✓ | ✓ |
| Git artifact / CI log | ⚠️ 變 `?????` | ✓ | ✓ |
| AI 解讀檔內 title | ✓ | ✗ 拼音失語意 | ✓ |
| User 看了知道是哪個檔 | ✓ | ⚠️ 要對照 | ✓ |

**雙存** = filename 拼音 + 內容原文 + inline 註解對照，全勝。

### Schema pattern

```yaml
metadata:
  # 中文標題 + 拼音對照（拼音用於檔名 slug，import 時系統讀中文 title）
  title: "我的曼陀羅—九字真言"     # 拼音: wo-de-mandala-jiu-zi-zhen-yan
  title_pinyin: "wo-de-mandala-jiu-zi-zhen-yan"
```

兩個欄位 + inline `# 拼音: xxx` 註解（人類可讀）。

### Slug 生成規則

- 全 lowercase
- ASCII alphanumeric + hyphen only（`/[^a-z0-9-]/g` 過濾）
- 多重 hyphen merge（`--+ → -`）
- trim leading/trailing hyphens
- 空時 fallback 到 ID 前 8 字元（`<id-short>`）

### Lib 選擇

- 中文 → `pinyin-pro` (CDN 約 300KB，僅 export 時需要)
- CJK 通用 → `transliteration`
- 西語 / Latin extended → 標準 unicode normalize（`String.prototype.normalize('NFD')`）
- Server-side Python → `pypinyin`

### 真實案例

stroke-order 2026-05-04 Phase 5b r27 — `.mandala.md` 匯出。User 明確要求「檔名用拼音但內容保留中文」。前端 `_mandalaTitleToPinyin()` 生成 slug，frontmatter `title` (中文) + `title_pinyin` (slug) + inline 註解。詳 `docs/decisions/2026-05-04_phase5b_r27_*.md`。

### 反例

- 只存 slug 「`wo-de-mandala.mandala.md`」內容無原文 → 5 個月後 user 看 filename 想不起來是哪張曼陀羅
- 只存中文檔名 → user 在 Linux server 拉 file 變亂碼

### Cross-ref

- §3.7 跨電腦初次設定（語言 / locale 議題的延伸）

---

## §3.6 補充：PowerShell 指令給法完整規則

既有 §3.6 排查表已涵蓋 `index.lock` 跟 `::` 註解誤判。補完整規則：

### 4 個必守規則

1. **禁尖括號 placeholder**：PowerShell `<>` 是 redirection 語法
   ```powershell
   # ❌ Bad — 尖括號被 PowerShell 解析成 redirect
   git checkout <branch-name>
   # ✅ Good — 用 placeholder 提示語、不用尖括號
   git checkout BRANCH_NAME    # 替換成實際 branch 名
   git checkout 'feat/foo'     # 或直接舉例
   ```

2. **禁 `&&`**：PowerShell 的 `&&` 是 PowerShell 7+ 才有，5.x 報錯
   ```powershell
   # ❌ Bad in PowerShell 5.x
   git add . && git commit
   # ✅ Good — 用換行 / 分號 / `;`
   git add .
   git commit -m "..."
   # or
   git add .; git commit -m "..."
   ```

3. **`git add` 分行**：跟 §3.10 cowork sandbox 共通，避免 index race
   ```powershell
   git add file1.py
   git add file2.py
   # 或單一 batched：
   git add file1.py file2.py file3.py
   ```

4. **用 `HEAD~N` / `origin/main` 相對引用，不寫死 commit hash**
   ```powershell
   # ❌ Bad — hash 容易漂
   git diff abc1234..def5678
   # ✅ Good — 相對引用穩
   git diff HEAD~3..HEAD
   git diff origin/main..HEAD
   ```

### 真實案例

stroke-order 2026-05-03 Phase 12m-7 r38b — 給 user PowerShell 指令貼到 Windows terminal 跑時撞尖括號 + `&&` 雙重錯誤。memory 沉澱後，每次給 PS 指令都先審這 4 條。

---

## §5.8（新）跨 phase 共享檔案的 commit：誠實標註 > hunk 強拆

> 累積多 phase 改動沒 commit 時，共享檔（如 `server.py` / `index.html`）會混
> 多個 phase 的 hunk。**強行 hunk-by-hunk staging 風險高**；commit message 誠實
> 註明「同檔含其他 phase 改動」是務實妥協。

### 三選一比較

| 路徑 | 風險 | 工序 | 推薦度 |
|---|---|---|---|
| (A) Hunk-by-hunk staging（`git add -p` 或 patch apply） | 高 | 高（每檔每 hunk 手動判斷） | ✗ |
| (B) 一個大 commit 全塞 | 低 | 最低 | ⚠️ 失去 phase 結構 |
| (C) 按 phase 分 commit，**共享檔誠實標註** | 低 | 中 | ✓ 推薦 |

### How to apply

1. 識別「乾淨可拆」的檔（單 phase 修改）vs「共享檔」（多 phase 並行修改）
2. 乾淨檔按 phase 分 commit
3. 共享檔丟到「主流 phase」commit 內（通常是改動最大那個 phase）
4. **commit message 明確註明**：
   ```
   注：server.py / index.html 同時含 12m-7 r39 rect_title UI/API 改動
   （共享檔案，未拆 hunk）。
   ```
5. 後續 phase 的 commit 也提一句：
   ```
   對應 UI/API 改動已併入前一個 commit。
   ```

### 為什麼不強拆

- Hunk staging 需要 deep understanding 每個 hunk 屬於哪 phase。誤切會產生「不能 build / 不能 import」的部分 commit，造成後續 bisect 困難
- `git log -p` 任何時候都能看到完整 diff，誠實註明就足夠後人理解 commit 邊界
- 真要 phase-precise rollback，可用 `git checkout <commit> -- <file>` 局部回退；不需 commit 階段就 perfect

### 真實案例

stroke-order 2026-05-04 整理 5b r4-r26 (mandala) + 12m-7 r39 (rect_title) 累積工作。`server.py` + `index.html` 同時含兩 phase 改動。Plan A 原本想 hunk 拆，評估風險高（hunks 跨 phase 互依），改成 C2 commit 內含完整 diff、commit message 註明，後續 C3 commit 提「對應 UI/API 改動已併入前一個 commit」。`git log -p` 仍可看完整 diff。

### Cross-ref

- §3.9 跨 AI session race（同問題的另一個面向）
- §5.4 檔案命名規範

---

## §8.16（新）Mixed-arity tuple 解構 pattern 兼容 API 擴充

> 函式簽章用 tuple 回傳時，未來 API 加欄位會撞解構。改用 `[:N]` 截斷 + `*_`
> trailing rest，向後兼容多解構點。

### 痛點

```python
# v1: tuple 3 元素
def get_user_meta(uid):
    return (name, email, role)

# 多處解構
name, email, role = get_user_meta(uid)
```

v2 想加 `created_at` 變 4 元素 → 所有解構點都撞錯。

### Pattern

```python
# v1: function 多回 1 個 trailing 欄位
def get_user_meta(uid):
    return (name, email, role, created_at)

# 解構點 — `[:N]` 或 `*_` 兩種寫法
name, email, role = get_user_meta(uid)[:3]   # 顯式截斷
name, email, role, *_ = get_user_meta(uid)   # rest 吃掉

# 新解構點 — 拿到完整
name, email, role, created_at = get_user_meta(uid)
```

兩種寫法都向後兼容，新欄位加在 trailing 不破壞舊呼叫。

### 對應的 anti-pattern

- 改成 `dict` / `dataclass` 也好（更嚴謹），但對既有 tuple-based API 而言，加 trailing element + `[:N]` 是最小改動量
- **絕不**在 middle 插新欄位（`(name, NEW, email, role)`）— 一定撞解構

### 真實案例

stroke-order Phase 5b r10 — `placed: list[(char, x, y, size, rot)]` 5-tuple 加 `flags` 欄位。所有 `for (c, x, y, sz, r) in placed` 改成 `for (c, x, y, sz, r, *_) in placed`，避免 caller-side 大改。詳 `docs/decisions/...`。

---

## §8.17（新）多輪 reference-image-driven 視覺迭代 SOP（擴展 §8.15）

> User 提供 reference 圖時，每輪迭代必跑：plan → design Q → 視覺驗證 → bump。
> 跳過任一步容易做出「演算法對、視覺錯」的迭代結果。

### 每輪 SOP

1. **Read reference 圖** — 不只看 user 描述，自己看圖（multimodal）
2. **Plan + design Q** — 寫 1-2 段提案 + 1-3 個關鍵抉擇問題給 user 確認，不直接動手
3. **Implement** — 實作（單元測試驗演算法）
4. **PNG render 視覺驗證** — cairosvg / 截圖，並排比對 reference
5. **Bump version** — 即使是 micro 改動也 bump（追蹤每輪變化）
6. **寫 micro decision log**（可選，重大轉折才寫）

### 為什麼每輪都要做

- 跳過 #2（不問 design Q 直接動）→ 做出 user 不要的結果
- 跳過 #4（不視覺驗證）→ unit test 通過但 user 截圖看到「形狀對效果錯」
- 跳過 #5（不 bump）→ 多輪間混淆無法追溯哪輪出了問題

### 真實案例

stroke-order 2026-05-02 Phase 12m-1 r14 → r19，sawtooth 邊飾 6 輪迭代。每輪都跑完整 SOP，r18 出現「inner side 也鋸齒」bug 時能準確定位是 r17→r18 polygon-replace 引入的，r19 改回 smooth ellipse + filled triangle attached outside。詳 `docs/decisions/2026-05-02_phase12m_iterative_polish.md`。

### Cross-ref

- §8.15 Visual rendering 驗證每 round（這節是進階版，含 plan/design Q）

---

## §8.18（新）AI-friendly 設定檔 = YAML frontmatter + Markdown body 雙層

> 給 AI / 人類雙讀的設定檔，純 JSON 不夠 AI-friendly，純散文不夠機器精確。
> **YAML frontmatter（機器） + Markdown body（人類 / AI）** 雙層是黃金標準。

### Pattern

```markdown
---
schema: project-feature-v1
exported_at: <ISO>
metadata:
  id: <UUID>
  title: <user-facing>
  design_note: <user 自由 prose>
  ...
{...其餘 structured 欄位...}
---

# {{title}}

## 視覺/結構概觀（自動生成，下次匯出會被覆蓋）
（從 frontmatter render template）

## 設計意圖
（user 自由寫，AI 看了會更懂作者想表達什麼）
```

### 三方各得其所

| 角色 | 看哪 | 行為 |
|---|---|---|
| 機器（import / parse） | frontmatter | 嚴格 schema validation，body 完全忽略 |
| AI 模型 | frontmatter + body | 結構（schema） + 意圖（prose） 全吃 |
| 人類 | body 為主 | frontmatter 偶爾掃，body prose 是主要閱讀面 |

### 規則

- **frontmatter 是 single source of truth**（機器只信這一邊）
- **body 是 derived view**（每次匯出系統自動 render template）
- 給 user 預留**自由 prose section**（如 `## 設計意圖`）— body 中**唯一** user 可手動編輯保留的部分
- frontmatter 帶 inline comment（`# 拼音: xxx`）提升人類可讀性

### 真實案例

stroke-order Phase 5b r27 — `.mandala.md` 曼陀羅匯出。一開始 user 問「能用 MD 嗎」，純散文 MD 不可逆 round-trip；改用雙層後 frontmatter 嚴格 parse + body 給 AI 解讀意圖。詳 `docs/decisions/2026-05-04_phase5b_r27_*.md`。

### 反例

- 純 JSON：機器精確但 AI 解讀時要 prompt engineering 才知道欄位語意，user 看不懂
- 純散文 MD：AI 讀爽但同樣的圖每人寫不同 prose → round-trip 不可靠
- frontmatter 全英文 + body 全中文：AI 切 context 困擾，建議都用同語系

### Cross-ref

- §8.19 Schema versioning（搭配使用）
- §3.11 i18n 檔名（同樣 export/import 場景）

---

## §8.19（新）Schema versioning：嚴格 + migration table + 友善錯誤

> 可匯出/匯入的設定檔 schema 一定會演進。Schema 字串 baked into file，未知
> schema 嚴格拒絕但訊息列出已知版本，**避免沉默吞錯**。

### 三大原則

1. **Schema 字串 baked into file**：每個檔案 frontmatter 寫
   `schema: <project>-<feature>-v<n>`，不依賴副檔名 / 上下文判斷
2. **Migration table 集中管理**：
   ```javascript
   const MIGRATIONS = {
     "project-feature-v1": (data) => data,            // identity
     "project-feature-v2": (data) => migrateV1to2(data),
   };
   ```
3. **嚴格但帶引導訊息**：未知 schema → reject + 列出已知版本

### 嚴格 vs 寬鬆

| 風格 | user 體驗 |
|---|---|
| ❌ 寬鬆（缺欄位忽略）| 「looks-like-it-imported」但實際缺欄位的狀態，編輯後再 export 變混合版本，**沉默破壞資料完整性** |
| ✅ 嚴格（reject + 訊息）| user 馬上看到錯誤訊息 + 已知版本列表 → 知道該升級工具或找對的 importer |

### Schema 命名約定

- 跨 feature 統一：`<project>-<feature>-v<n>`
- 對齊既有：本 repo `stroke-order-psd-v1` (5d 抄經) → 新增 `stroke-order-mandala-v1`
- 數字版本（不用 semver）— migration 邏輯只關心 major version
- **預留 metadata 欄位給未來** — 如 `author` / `tags` / `license`，v1 不用也定義為 optional reserved，未來 r28+ 上 gallery / r29 評分時不破壞檔案

### 真實案例

stroke-order Phase 5b r27 — `.mandala.md` schema = `stroke-order-mandala-v1`，`MD_MIGRATIONS` 表只一行 identity 但留下擴充模板。`_mandalaMigrateState()` 嚴格 reject 未知 schema 並列出已知版本。

### 反例

純 JSON `{"foo": 1}` 沒帶 schema 字串 → 升版時無法判定來源版本，只能 heuristic 猜（脆弱）。

### Cross-ref

- §8.18 frontmatter + body 雙層（schema 字串放在 frontmatter）
- §8.21 dual-write 漸進遷移（schema 升版時搭配使用）

---

## §8.20（新）By-kind dispatch dict 取代 if/elif 鏈

> Endpoint / 服務通用化給多 kind 時，最常見 anti-pattern 是 `if/elif` 鏈散在
> 多處。用**dict-of-functions** 集中派遣，加新 kind 不動核心邏輯。

### Pattern

```python
KIND_PSD     = "psd"
KIND_MANDALA = "mandala"
ALLOWED_KINDS = (KIND_PSD, KIND_MANDALA)

VALIDATORS = {
    KIND_PSD:     lambda b: (parse_psd(b), "json"),
    KIND_MANDALA: parse_mandala,  # returns (state, "md"|"svg")
}
SUMMARIZERS = {
    KIND_PSD:     summarise_psd,
    KIND_MANDALA: summarise_mandala,
}

def create_upload(*, kind, content_bytes, ...):
    if kind not in ALLOWED_KINDS:
        raise InvalidUpload(...)
    state, ext = VALIDATORS[kind](content_bytes)
    summary = SUMMARIZERS[kind](state)
    # ... 統一 dedup / rate limit / DB insert（kind 無關）
```

加新 kind 只需 5 步：
1. 加 `KIND_X` 常數 + 進 `ALLOWED_KINDS`
2. 寫 `parse_and_validate_x(content_bytes) → (state, ext)`
3. 寫 `summarise_x(state) → dict`
4. 加進 `VALIDATORS` / `SUMMARIZERS` dict
5. 前端 `_detectKindFromText` 加偵測 + analyser

**核心 `create_upload` 邏輯不動**。

### Anti-pattern

```python
# ❌ Bad — if/elif 鏈散在多處
def create_upload(...):
    if kind == "psd":
        state = parse_psd(...)
        summary = summarise_psd(state)
    elif kind == "mandala":
        state = parse_mandala(...)
        summary = summarise_mandala(state)
    # ...

def list_uploads(...):
    if kind == "psd":
        cols = "trace_count, unique_chars"
    elif kind == "mandala":
        cols = "summary_json"
    # ...

def download(...):
    if kind == "psd":
        ext = "json"
    elif kind == "mandala":
        ext = state.get("source_format", "md")
    # ...
```

加 kind 要改 N 處，每處都可能漏。

### 額外好處

- Validator / summarizer 各自獨立 module，便於 unit test
- `ALLOWED_KINDS = tuple(VALIDATORS.keys())` 自動同步
- 加進 dict 即注冊，沒寫 dict entry 就會 KeyError 提早炸（fail loud）

### 真實案例

stroke-order Phase 5b r28 — gallery 從 PSD-only 通用化到接 mandala upload。`VALIDATORS` / `SUMMARIZERS` dict 派遣，`create_upload` / `list_uploads` / download endpoint 核心邏輯零變動，只動 dict 跟前端偵測 + 資料層 schema。詳 `docs/decisions/2026-05-04_phase5b_r28_*.md`。

### Cross-ref

- §8.21 dual-write 漸進遷移（搭配使用）

---

## §8.21（新）Schema 通用化時 dual-write legacy column 漸進遷移

> 既有 schema 加新通用欄位（如 `summary_json`）時，**legacy 專用欄位繼續寫**，
> 給未來 phase 慢慢遷移空間。**不一次性切換**避免破壞既有資料 / 既有讀者。

### 場景

`uploads` table 原本有 PSD 專用 `trace_count` / `unique_chars` / `styles_used`。r28 加 mandala 後新增通用 `summary_json TEXT`。

### Dual-write 策略

```python
# create_upload 內部
if kind == KIND_PSD:
    legacy_trace_count = summary["trace_count"]
    legacy_unique_chars = summary["unique_chars"]
    legacy_styles_used = json.dumps(summary["styles_used"])
else:
    legacy_trace_count = 0
    legacy_unique_chars = 0
    legacy_styles_used = None

INSERT INTO uploads (
    user_id, ...,
    kind, summary_json,                        -- 新欄位（所有 kind）
    trace_count, unique_chars, styles_used,    -- legacy（PSD 寫，其他 kind 0/null）
    ...
)
```

讀取側對應：

```javascript
// 列表 card 渲染
if (kind === 'mandala') {
    return summary.layer_count + ' 裝飾層';
} else {
    // PSD legacy 路徑
    return item.trace_count + ' 筆軌跡';
}
```

### 為什麼 dual-write

| 一次切換到 summary_json | Dual-write |
|---|---|
| 必須跑 backfill migration（risk）| Existing PSD rows 不動 |
| 既有 client 讀 trace_count 會壞 | 既有 client 不受影響 |
| 一次性大改動，rollback 困難 | 漸進可逆 |

### 何時拔掉 legacy column

當以下 3 條件都成立才考慮 drop legacy column：
1. 所有 PSD 寫入路徑都已切到 summary_json（dual-write 持續 N 個月）
2. 所有讀取側都改成優先讀 summary_json，legacy 路徑只剩 fallback
3. Backfill PSD 既有 row：把 `trace_count` 等寫進 `summary_json` 對應欄位

時機通常是 r29+ 或更後，**r28 的 dual-write 是 stable resting state**，不急著拔。

### 真實案例

stroke-order Phase 5b r28 — gallery 通用化。PSD upload 仍寫 `trace_count` / `unique_chars` / `styles_used`，**也**寫 `summary_json`（內含相同資訊副本）；mandala upload 只寫 `summary_json`，legacy 欄位 = 0/null。列表 card 渲染對 PSD 用 legacy 欄位、對 mandala 用 `item.summary`。

### Cross-ref

- §8.20 By-kind dispatch dict（搭配使用）
- §8.19 Schema versioning（schema 升版層級的 migration）

---

## 整合到 personal-playbook 後的清單變化

預期 personal-playbook 章節異動：

| 章節 | 動作 |
|---|---|
| §3.6 | 補完整 4 條 PowerShell 規則（既有 2 條保留） |
| §3.10 | **新增** Cowork sandbox git index 操作 SOP |
| §3.11 | **新增** i18n 檔名雙存 |
| §5.8 | **新增** 跨 phase 共享檔的 commit 策略 |
| §8.16 | **新增** Mixed-arity tuple 解構 |
| §8.17 | **新增** 多輪 reference-image 視覺迭代 SOP |
| §8.18 | **新增** YAML frontmatter + body 雙層 |
| §8.19 | **新增** Schema versioning + migration table |
| §8.20 | **新增** By-kind dispatch dict |
| §8.21 | **新增** Schema dual-write 漸進遷移 |

並更新 personal-playbook/HISTORY.md §A 加同日修訂 entry，§B 加跨 ref 案例。

---

## 草稿狀態

- 寫於 stroke-order sandbox 端，**不是 SoT**
- Cherry-pick 流程見檔頭
- 落地完成後請刪本檔（或 archive 到 `docs/decisions/`）
