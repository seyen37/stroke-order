#!/usr/bin/env python3
"""
PROJECT_PLAYBOOK SoT cherry-pick — 2026-05-04
=============================================

把 stroke-order 副本累積的 §8.13/§8.14/§8.15（SoT 漂移修復）+ r25–r28
浮現的 9 條共通性原則（§3.10/§3.11/§5.8/§8.16-§8.21）+ §3.6 PowerShell 補強
插入 personal-playbook 的 PROJECT_PLAYBOOK.md。

Idempotent：重跑檢查 marker 已在則 skip，不會重複插入。

執行方法（在 personal-playbook repo 根目錄）：

    python3 playbook_cherry_pick_2026-05-04.py

接著：

    git diff PROJECT_PLAYBOOK.md   # 檢查
    git add PROJECT_PLAYBOOK.md
    git commit -m "feat(playbook): r25-r28 共通性原則 + SoT 漂移修復"
    git push origin main

注意：HISTORY.md 需手動更新（§A 加修訂列表 + §B 加跨 ref 案例索引）。
"""
from pathlib import Path
import sys

PLAYBOOK = Path("PROJECT_PLAYBOOK.md")
if not PLAYBOOK.exists():
    sys.exit("❌ PROJECT_PLAYBOOK.md 不在當前目錄；請 cd 到 personal-playbook 根目錄")


# =====================================================================
# 章節內容 payload
# =====================================================================

# §8.13 + §8.14 + §8.15 — SoT 漂移修復（從 stroke-order 副本搬回）
# 塞在 ## 九、附錄 之前；獨立 skip_if marker
SEC_8_13_TO_15 = """### 8.13 結構化 input fields > separator hack

當功能 input 含多個語意獨立欄位（如橢圓章 5 段：上弧 / 中央 1-3 行 body / 下弧），用結構化 schema（多個獨立 fields）優於 single text + separator hack（如 `text="A|B|C|D"`）。

#### 規則

1. **多語意欄位 ≥ 3 個** → 拆獨立 fields，不用 separator string
2. **list[T] 用 native list type**（Pydantic / JSON），不用 `"a||b||c"` 字串拆分
3. **GET endpoint 才接受 separator**（query string 沒原生 list） — 但 POST body 一律 native list
4. **Backward compat**：保留舊 single-text fallback path，新欄位全空時 fallback 老邏輯

#### 為什麼這個習慣值錢

Single text + separator 的問題：

- **User 心智成本**：要學 separator 是什麼字元（`|` ? `||` ? `,` ?）+ 怎麼 escape（內文有 `|` 怎麼辦）
- **API 不自我文件化**：`text` field 看 type signature 不知有結構，要看 docs / 範例才懂
- **可選欄位處理麻煩**：empty 欄位要寫 `||` 連續分隔符，user 容易忘
- **未來擴充 break schema**：要加 per-line font size 等 metadata 時，被 separator 綁死
- **語意 vs 顯示混淆**：UI 要 5 個 input 對齊 API 5 段，separator 要做 split / join 同步邏輯

結構化 schema 的代價：

- API field 多 3-5 個（surface area 略大）
- Backward compat 處理：fallback 邏輯（all empty → 走老 path）

代價可控，長期收益大。**反例可參考 CSS `font` shorthand**（多欄位塞 single string 已多次造成 bug，後來 modern CSS 全部拆獨立 property）。

#### Audit checklist

- [ ] grep API field 看有沒有 `text.split("...")` / `text.split("|")` 等 hack
- [ ] 數該 field 在 UI 對應幾個 input → ≥ 3 個就觸發重構
- [ ] 重構時：新增獨立 fields + UI 對齊 + backward-compat fallback + tests

> 📜 **真實案例**：起源於 stroke-order 2026-05-02 Phase 12m-1 橢圓章 — 5 段語意獨立欄位（上弧 / 中央 1/2/3 / 下弧），原本只有 single text + 1-2 行 horizontal split layout。重構成結構化 5 欄位後，user UI 一看即懂、API 自我文件化、各欄位 empty 自動 skip。詳見 stroke-order 的 `docs/decisions/2026-05-02_phase12m_oval_structured.md`。

### 8.14 UI 預設套用要 hook init time，不只 change

UI 控件的 default state 由 JS 在 dropdown / preset 變動時填入（如「切到 oval preset → 自動勾雙線外框」），**必須在 init 時也跑一次**。光是 hook `change` event 不夠 — 第一次載入或 user 沒做 change 時不會觸發 → init state 跟 default-after-change 不一致。

#### 規則

```js
// ❌ 反模式
$("preset").addEventListener("change", applyDefaults);

// ✅ 正模式
$("preset").addEventListener("change", applyDefaults);
applyDefaults();   // ← init 時跑一次，覆蓋首次載入路徑
```

延伸：所有「依賴 user 互動觸發 default」的 init 邏輯都同樣處理。

#### 為什麼這個習慣值錢

症狀：

- User 截圖顯示 default 未生效（checkbox 沒勾、size 不對、hint 是別的 preset 數值）
- 開發者 reproduce 困難（自己切 preset 兩下都 OK，因為觸發過 change）
- 容易誤判為「部署沒上去 / 快取問題」白白浪費排查時間

根因：UI 的 default 邏輯散在兩處 — HTML 寫死 default + JS change-time override。如果 JS change 沒觸發，HTML 寫死的就是「真 default」。但 HTML 不知道目前 preset 是哪個 → 任何依賴 preset 的 default 必然錯。

修法簡單（一行 init call），但容易漏。

#### Audit checklist

- [ ] grep `addEventListener("change",` 對應的 handler 有沒有在 init 也 call
- [ ] 列出所有「依 preset/select 切換填 default」的 handler → 每個都該 init time 跑
- [ ] 寫測試：page load 後 dropdown 預設 preset 對應的 default state 對齊（hard）；OR 簡單 grep `function xxx_init` 內呼叫 default-applier（pragma）

#### 反例 vs 正例

**反例**（典型 anti-pattern）：
> User 進站 → preset dropdown 預設 oval → 但 double_border checkbox 維持 HTML 寫死 unchecked → user 看到「該勾沒勾」回報 bug → 開發者 reproduce 不出來（自己切兩下都 OK）→ 浪費 1 小時排查 cache / 部署 / 後端後才發現是 JS init 沒呼叫 default。

**正例**（stroke-order 12m-1 r3）：
> `stampInit()` 結尾加 `stampApplyPresetDefaults();` → 任何 preset 進站都同步 default → 跟 change-time 行為完全一致 → 沒 first-time UX bug。

> 📜 **真實案例**：起源於 stroke-order 2026-05-02 Phase 12m-1 r3 — r1 設了 oval default = double_border ON 但只 hook 在 change event。User 截圖顯示首次進站雙線外框沒勾，初步誤判為部署問題，後 trace 到 init 沒呼叫 `stampApplyPresetDefaults()`。修法 1 行。詳見 stroke-order 的 `docs/decisions/2026-05-02_phase12m_oval_structured.md`。

### 8.15 Visual rendering 驗證每 round — unit tests 不夠

對 layout / 視覺 / SVG / canvas 工作，**unit tests 驗算法輸出符合預期形狀，但渲染後的 stroke / fill / 多 path 互動可能跟預期完全不同**。每 round 必須 PNG render（或螢幕截圖）視覺驗證，不能光靠單元測試 green 就 ship。

#### 規則

對「視覺輸出」改動（任何 SVG/canvas/UI layout），驗證流程：

1. Unit test 驗演算法核心（座標 / 比例 / count）
2. **PNG render 視覺驗證**（cairosvg / Playwright screenshot / 等）
3. 對齊 reference 圖（如有）— 並排視覺對比
4. 檢查邊角情況（最小/最大 input、極端比例）

少了 step 2/3 容易出**「演算法對、渲染錯」**的 bug。

#### 為什麼這個習慣值錢

SVG render 細節容易 surprise:

- **Stroke** 在 polygon centerline 兩側都加半寬 → 預期單邊效果可能變雙邊
- **Fill-rule** (even-odd vs non-zero) 對複雜 path 結果不同
- **Path 順序** (z-index) 影響覆蓋
- **viewBox padding** 不夠時 stroke 外緣被裁
- **不同瀏覽器** stroke join / linecap 渲染微差

Unit test 通常測座標、頂點、count；無法捕捉這些渲染細節。

#### 反例 vs 正例

**反例**（typical anti-pattern）：
> 寫 sawtooth polygon helper，unit test 驗 polygon 有 N 個 vertices alternating outer/inner — 通過。Ship。User 看到「inner side 也鋸齒」回報 bug → 才發現 stroke 雙邊都 zigzag。多 1 round 重設計 + tests 重寫。

**正例**（stroke-order 12m-1 r19）：
> 改設計用 smooth ellipse + filled triangle teeth attached outside → render PNG → 確認 outer zigzag、inner smooth → user 滿意 1 round 過。Round 之間沒省 PNG verify step。

#### Audit checklist

- [ ] 每個 visual / layout PR 跑了 PNG render 比對
- [ ] reference 圖（user 提供 / 業界範例）有並排比對
- [ ] 邊角 input（n=1, n=極大、aspect ratio 極端）視覺檢查
- [ ] Unit tests 跟 PNG verify 都 green 才 commit

> 📜 **真實案例**：起源於 stroke-order 2026-05-02 Phase 12m-1 r18→r19 — sawtooth 邊飾用 polygon 替換 outer ellipse，unit tests 通過。但 SVG stroke 渲染後 polygon 兩側都 zigzag，user 反映「內側也呈鋸齒」。重設計改用「smooth ellipse + filled triangle teeth attached outside」，PNG verify 通過。詳見 stroke-order 的 `docs/decisions/2026-05-02_phase12m_iterative_polish.md`。

"""

# §8.16 + §8.17 + §8.18 + §8.19 + §8.20 + §8.21 — r25-r28 新原則
# 塞在 ## 九、附錄 之前；獨立 skip_if marker
SEC_8_16_TO_21 = """### 8.16 Mixed-arity tuple 解構 pattern 兼容 API 擴充

函式簽章用 tuple 回傳時，未來 API 加欄位會撞解構。改用 `[:N]` 截斷 + `*_` trailing rest，向後兼容多解構點。

#### 痛點

```python
# v1: tuple 3 元素
def get_user_meta(uid):
    return (name, email, role)

# 多處解構
name, email, role = get_user_meta(uid)
```

v2 想加 `created_at` 變 4 元素 → 所有解構點都撞錯。

#### Pattern

```python
# v1+: function 多回 1 個 trailing 欄位
def get_user_meta(uid):
    return (name, email, role, created_at)

# 解構點 — `[:N]` 或 `*_` 兩種寫法
name, email, role = get_user_meta(uid)[:3]   # 顯式截斷
name, email, role, *_ = get_user_meta(uid)   # rest 吃掉

# 新解構點 — 拿到完整
name, email, role, created_at = get_user_meta(uid)
```

兩種寫法都向後兼容，新欄位加在 trailing 不破壞舊呼叫。

#### Anti-pattern

- 改成 `dict` / `dataclass` 也好（更嚴謹），但對既有 tuple-based API 而言，加 trailing element + `[:N]` 是最小改動量
- **絕不**在 middle 插新欄位（`(name, NEW, email, role)`）— 一定撞解構

> 📜 **真實案例**：stroke-order Phase 5b r10 — `placed: list[(char, x, y, size, rot)]` 5-tuple 加 `flags` 欄位。所有 `for (c, x, y, sz, r) in placed` 改成 `for (c, x, y, sz, r, *_) in placed`，避免 caller-side 大改。

### 8.17 多輪 reference-image-driven 視覺迭代 SOP

User 提供 reference 圖時，每輪迭代必跑：plan → design Q → 視覺驗證 → bump。跳過任一步容易做出「演算法對、視覺錯」的迭代結果。本節為 §8.15 的進階版（含 plan/design Q 流程）。

#### 每輪 SOP

1. **Read reference 圖** — 不只看 user 描述，自己看圖（multimodal）
2. **Plan + design Q** — 寫 1-2 段提案 + 1-3 個關鍵抉擇問題給 user 確認，不直接動手
3. **Implement** — 實作（單元測試驗演算法）
4. **PNG render 視覺驗證** — cairosvg / 截圖，並排比對 reference
5. **Bump version** — 即使是 micro 改動也 bump（追蹤每輪變化）
6. **寫 micro decision log**（可選，重大轉折才寫）

#### 為什麼每輪都要做

- 跳過 #2（不問 design Q 直接動）→ 做出 user 不要的結果
- 跳過 #4（不視覺驗證）→ unit test 通過但 user 截圖看到「形狀對效果錯」
- 跳過 #5（不 bump）→ 多輪間混淆無法追溯哪輪出了問題

> 📜 **真實案例**：stroke-order 2026-05-02 Phase 12m-1 r14 → r19，sawtooth 邊飾 6 輪迭代。每輪都跑完整 SOP，r18 出現「inner side 也鋸齒」bug 時能準確定位是 r17→r18 polygon-replace 引入的，r19 改回 smooth ellipse + filled triangle attached outside。詳 stroke-order 的 `docs/decisions/2026-05-02_phase12m_iterative_polish.md`。

### 8.18 AI-friendly 設定檔 = YAML frontmatter + Markdown body 雙層

給 AI / 人類雙讀的設定檔，純 JSON 不夠 AI-friendly，純散文不夠機器精確。**YAML frontmatter（機器） + Markdown body（人類 / AI）** 雙層是黃金標準。

#### Pattern

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

#### 三方各得其所

| 角色 | 看哪 | 行為 |
|---|---|---|
| 機器（import / parse） | frontmatter | 嚴格 schema validation，body 完全忽略 |
| AI 模型 | frontmatter + body | 結構（schema） + 意圖（prose） 全吃 |
| 人類 | body 為主 | frontmatter 偶爾掃，body prose 是主要閱讀面 |

#### 規則

- **frontmatter 是 single source of truth**（機器只信這一邊）
- **body 是 derived view**（每次匯出系統自動 render template）
- 給 user 預留**自由 prose section**（如 `## 設計意圖`）— body 中**唯一** user 可手動編輯保留的部分
- frontmatter 帶 inline comment（如 `# 拼音: xxx`）提升人類可讀性

#### Anti-pattern

- 純 JSON：機器精確但 AI 解讀時要 prompt engineering 才知道欄位語意，user 看不懂
- 純散文 MD：AI 讀爽但同樣的圖每人寫不同 prose → round-trip 不可靠
- frontmatter 全英文 + body 全中文：AI 切 context 困擾，建議都用同語系

> 📜 **真實案例**：stroke-order Phase 5b r27 — `.mandala.md` 曼陀羅匯出。一開始 user 問「能用 MD 嗎」，純散文 MD 不可逆 round-trip；改用雙層後 frontmatter 嚴格 parse + body 給 AI 解讀意圖。詳 stroke-order 的 `docs/decisions/2026-05-04_phase5b_r27_mandala_state_export_import.md`。

### 8.19 Schema versioning：嚴格 + migration table + 友善錯誤

可匯出/匯入的設定檔 schema 一定會演進。Schema 字串 baked into file，未知 schema 嚴格拒絕但訊息列出已知版本，**避免沉默吞錯**。

#### 三大原則

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

#### 嚴格 vs 寬鬆

| 風格 | user 體驗 |
|---|---|
| ❌ 寬鬆（缺欄位忽略）| 「looks-like-it-imported」但實際缺欄位的狀態，編輯後再 export 變混合版本，**沉默破壞資料完整性** |
| ✅ 嚴格（reject + 訊息）| user 馬上看到錯誤訊息 + 已知版本列表 → 知道該升級工具或找對的 importer |

#### Schema 命名約定

- 跨 feature 統一：`<project>-<feature>-v<n>`
- 對齊既有專案：如 stroke-order 用 `stroke-order-psd-v1` (5d 抄經) → 新增 `stroke-order-mandala-v1`
- 數字版本（不用 semver）— migration 邏輯只關心 major version
- **預留 metadata 欄位給未來** — 如 `author` / `tags` / `license`，v1 不用也定義為 optional reserved

#### Anti-pattern

純 JSON `{"foo": 1}` 沒帶 schema 字串 → 升版時無法判定來源版本，只能 heuristic 猜（脆弱）。

> 📜 **真實案例**：stroke-order Phase 5b r27 — `.mandala.md` schema = `stroke-order-mandala-v1`，`MD_MIGRATIONS` 表只一行 identity 但留下擴充模板。`_mandalaMigrateState()` 嚴格 reject 未知 schema 並列出已知版本。詳 stroke-order 的 `docs/decisions/2026-05-04_phase5b_r27_mandala_state_export_import.md`。

### 8.20 By-kind dispatch dict 取代 if/elif 鏈

Endpoint / 服務通用化給多 kind 時，最常見 anti-pattern 是 `if/elif` 鏈散在多處。用 **dict-of-functions** 集中派遣，加新 kind 不動核心邏輯。

#### Pattern

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

**核心 endpoint 邏輯不動**。

#### Why dict 比 if/elif 好

- **集中**：所有 kind-specific 邏輯收在 dict，加新 kind 只動 dict（grep 一搜全找到）
- **fail loud**：沒寫 dict entry 立刻 KeyError，不會沉默 fallback 到 default
- **`ALLOWED_KINDS = tuple(VALIDATORS.keys())` 自動同步**，列舉永遠正確
- **per-kind unit test 容易**：每個 validator/summarizer 是獨立 function

#### Anti-pattern

```python
# ❌ if/elif 散在多處
def create_upload(...):
    if kind == "psd": ...
    elif kind == "mandala": ...

def list_uploads(...):
    if kind == "psd": ...
    elif kind == "mandala": ...

def download(...):
    if kind == "psd": ...
    elif kind == "mandala": ...
```

加 kind 要改 N 處，每處都可能漏。

> 📜 **真實案例**：stroke-order Phase 5b r28 — gallery 從 PSD-only 通用化到接 mandala upload。`VALIDATORS` / `SUMMARIZERS` dict 派遣，`create_upload` / `list_uploads` / download endpoint 核心邏輯零變動，只動 dict 跟前端偵測 + 資料層 schema。詳 stroke-order 的 `docs/decisions/2026-05-04_phase5b_r28_gallery_mandala_upload.md`。

### 8.21 Schema 通用化時 dual-write legacy column 漸進遷移

既有 schema 加新通用欄位（如 `summary_json`）時，**legacy 專用欄位繼續寫**，給未來 phase 慢慢遷移空間。**不一次性切換**避免破壞既有資料 / 既有讀者。

#### Dual-write 策略

```python
# create_upload 內部
if kind == KIND_PSD:
    legacy_trace_count   = summary["trace_count"]
    legacy_unique_chars  = summary["unique_chars"]
    legacy_styles_used   = json.dumps(summary["styles_used"])
else:
    legacy_trace_count   = 0
    legacy_unique_chars  = 0
    legacy_styles_used   = None

INSERT INTO uploads (
    user_id, ...,
    kind, summary_json,                        -- 新欄位（所有 kind）
    trace_count, unique_chars, styles_used,    -- legacy（PSD 寫，其他 kind 0/null）
    ...
)
```

讀取側對應：

```javascript
if (kind === 'mandala') {
    return summary.layer_count + ' 裝飾層';   // 新欄位
} else {
    return item.trace_count + ' 筆軌跡';       // PSD legacy
}
```

#### 為什麼 dual-write

| 一次切換到 summary_json | Dual-write |
|---|---|
| 必須跑 backfill migration（risk）| Existing PSD rows 不動 |
| 既有 client 讀 trace_count 會壞 | 既有 client 不受影響 |
| 一次性大改動，rollback 困難 | 漸進可逆 |
| schema deploy 跟 client 部署要同步 | 解耦 |

#### 何時拔掉 legacy column

3 條件都成立才考慮 drop：

1. 所有 PSD 寫入路徑都已切到 summary_json（dual-write 持續 N 個月）
2. 所有讀取側都改成優先讀 summary_json，legacy 路徑只剩 fallback
3. Backfill PSD 既有 row：把 `trace_count` 等寫進 `summary_json` 對應欄位

時機通常是 N+ phase 後。**dual-write 是 stable resting state**，不急著拔。

#### Anti-pattern

- Big-bang migration：寫好新 schema，drop 舊 column，跑 backfill。風險：backfill 失敗時 mid-state DB 既不能讀舊也不能讀新
- 不寫 legacy column：mandala upload 把 `trace_count = NULL`，但既有列表 SQL `COUNT_BY trace_count > 0` 直接漏掉 mandala rows

> 📜 **真實案例**：stroke-order Phase 5b r28 — gallery `uploads` table 加 `kind` + `summary_json`。PSD upload 仍寫 `trace_count` / `unique_chars` / `styles_used`（**也**寫 `summary_json`，內含相同資訊副本）；mandala upload 只寫 `summary_json`，legacy 欄位 = 0/null。列表 card 渲染對 PSD 用 legacy 欄位、對 mandala 用 `item.summary`。詳 stroke-order 的 `docs/decisions/2026-05-04_phase5b_r28_gallery_mandala_upload.md`。

"""

# §5.8 — 跨 phase 共享檔案的 commit：誠實標註 > hunk 強拆
# 塞在 ## 六、 之前
SEC_5_8 = """### 5.8 跨 phase 共享檔案的 commit：誠實標註 > hunk 強拆

累積多 phase 改動沒 commit 時，共享檔（如 `server.py` / `index.html`）會混多個 phase 的 hunk。**強行 hunk-by-hunk staging 風險高**；commit message 誠實註明「同檔含其他 phase 改動」是務實妥協。

#### 三選一比較

| 路徑 | 風險 | 工序 | 推薦度 |
|---|---|---|---|
| (A) Hunk-by-hunk staging（`git add -p` 或 patch apply） | 高 | 高（每檔每 hunk 手動判斷） | ✗ |
| (B) 一個大 commit 全塞 | 低 | 最低 | ⚠️ 失去 phase 結構 |
| (C) 按 phase 分 commit，**共享檔誠實標註** | 低 | 中 | ✓ 推薦 |

#### How to apply

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

#### 為什麼不強拆

- Hunk staging 需要 deep understanding 每個 hunk 屬於哪 phase。誤切會產生「不能 build / 不能 import」的部分 commit，造成後續 bisect 困難
- `git log -p` 任何時候都能看到完整 diff，誠實註明就足夠後人理解 commit 邊界
- 真要 phase-precise rollback，可用 `git checkout <commit> -- <file>` 局部回退；不需 commit 階段就 perfect

> 📜 **真實案例**：stroke-order 2026-05-04 整理 5b r4-r26 (mandala) + 12m-7 r39 (rect_title) 累積工作。`server.py` + `index.html` 同時含兩 phase 改動。Plan A 原本想 hunk 拆，評估風險高（hunks 跨 phase 互依），改成 C2 commit 內含完整 diff、commit message 註明，後續 C3 commit 提「對應 UI/API 改動已併入前一個 commit」。`git log -p` 仍可看完整 diff。詳 stroke-order 的 `docs/journal/2026-05-04_session_log.md`。

"""

# §3.10 + §3.11 — 塞在 ## 四、 之前
SEC_3_10_3_11 = """### 3.10 Cowork sandbox git index 操作 SOP

Cowork sandbox 的 git index 在連續寫入時會 corruption，連續 `git add` 多次會撞 `bad signature 0x00000000`。預先重建 index、用單一 batched add，可穩定避開。本節為 §3.9 跨 session race 的具體 mitigation。

#### 何時必跑

- 用 cowork sandbox 終端機操作 git
- 上一場 session 留下未 commit 的檔案，現場準備 stage（高風險區）
- 出現 `bad signature 0x00000000` / `index file corrupt`

#### 標準 SOP

**A. 開工前預先重建 index（防禦性）**

```bash
rm -f .git/index
git read-tree HEAD
git status --short
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
rm -f .git/index
git read-tree HEAD
git status --short  # 確認 working tree 改動還在
git add <files batched>
git commit -m "..."
```

**D. Stale lock 處理**

```bash
ls .git/index.lock 2>&1   # 看上場 session 是否留下
# 確認沒有實際 git process 在跑
rm .git/index.lock
```

**E. 0-byte 垃圾檔 / stale lock 刪除受限**

Cowork sandbox 預設 `rm` 會 `Operation not permitted`。要先 mcp 授權：

```
mcp__cowork__allow_cowork_file_delete(file_path=...)
```

再 `rm`。

#### Push / Pull

Sandbox 內**沒有 SSH key**，push / fetch 會撞 `Permission denied (publickey)`。Push 必須在 user 自己 terminal 跑：

```bash
git fetch origin
git push origin main
git push backup main  # 雙 remote
```

> 📜 **真實案例**：stroke-order 2026-05-04 整理 5b r1-r26 + 12m-7 r39 累積 commit。第一次連續 `git add ... && git add ... && git add ...` 立刻撞 index corrupt。改成 batched + 重建 SOP 後 4 個 commit 全成功。詳 stroke-order 的 `docs/journal/2026-05-04_session_log.md`。

### 3.11 i18n 檔名：原文 + slug 雙存

中文 / 非 ASCII 標題的下載檔，filename 用 slug（拼音 / transliteration）保跨平台穩定性，但檔內 metadata **同時保留原文** 給系統 / AI 看得懂語意。

#### 為什麼雙存

| 場景 | 純中文檔名 | 純拼音檔名 | 雙存 |
|---|---|---|---|
| 現代 Mac / Windows 本機 | ✓ | ✓ | ✓ |
| Email 附件 | ⚠️ 偶爾 mangle | ✓ | ✓ |
| S3 key / CDN URL | ✗ | ✓ | ✓ |
| Git artifact / CI log | ⚠️ 變 `?????` | ✓ | ✓ |
| AI 解讀檔內 title | ✓ | ✗ 拼音失語意 | ✓ |
| User 看了知道是哪個檔 | ✓ | ⚠️ 要對照 | ✓ |

**雙存** = filename 拼音 + 內容原文 + inline 註解對照，全勝。

#### Schema pattern

```yaml
metadata:
  # 中文標題 + 拼音對照（拼音用於檔名 slug，import 時系統讀中文 title）
  title: "我的曼陀羅—九字真言"     # 拼音: wo-de-mandala-jiu-zi-zhen-yan
  title_pinyin: "wo-de-mandala-jiu-zi-zhen-yan"
```

兩個欄位 + inline `# 拼音: xxx` 註解（人類可讀）。

#### Slug 生成規則

- 全 lowercase
- ASCII alphanumeric + hyphen only（`/[^a-z0-9-]/g` 過濾）
- 多重 hyphen merge（`--+ → -`）
- trim leading/trailing hyphens
- 空時 fallback 到 ID 前 8 字元（`<id-short>`）

#### Lib 選擇

- 中文 → `pinyin-pro` (CDN ≈300KB，僅 export 時需要)
- CJK 通用 → `transliteration`
- 西語 / Latin extended → 標準 unicode normalize（`String.prototype.normalize('NFD')`）
- Server-side Python → `pypinyin`

#### Anti-pattern

- 只存 slug 「`wo-de-mandala.mandala.md`」內容無原文 → 5 個月後 user 看 filename 想不起來是哪張曼陀羅
- 只存中文檔名 → user 在 Linux server 拉 file 變亂碼

> 📜 **真實案例**：stroke-order 2026-05-04 Phase 5b r27 — `.mandala.md` 匯出。User 明確要求「檔名用拼音但內容保留中文」。前端 `_mandalaTitleToPinyin()` slug 函式 + frontmatter `title` (中文) + `title_pinyin` (slug) + inline 註解。詳 stroke-order 的 `docs/decisions/2026-05-04_phase5b_r27_mandala_state_export_import.md`。

"""

# §3.6 補強 — append 到 §3.6 既有 table 之後
SEC_3_6_APPEND = """
#### 4 個必守規則（補完整 PowerShell 給法）

1. **禁尖括號 placeholder**：PowerShell `<>` 是 redirection 語法

   ```powershell
   # ❌ Bad — 尖括號被 PowerShell 解析成 redirect
   git checkout <branch-name>
   # ✅ Good — 用 placeholder 提示語、不用尖括號
   git checkout BRANCH_NAME    # 替換成實際 branch 名
   git checkout 'feat/foo'     # 或直接舉例
   ```

2. **禁 `&&`**：PowerShell 5.x 不認得 `&&`（PS 7+ 才有）

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

> 📜 **真實案例**：stroke-order 2026-05-03 Phase 12m-7 r38b — 給 user PowerShell 指令貼到 Windows terminal 跑時撞尖括號 + `&&` 雙重錯誤。memory 沉澱後，每次給 PS 指令都先審這 4 條。
"""


# =====================================================================
# Helper functions
# =====================================================================

def insert_before(text, anchor, payload, *, skip_if):
    """Insert `payload` immediately before `anchor`. Skip if `skip_if` already in text."""
    if skip_if in text:
        print(f"  SKIP — {skip_if[:50]}... already present")
        return text
    idx = text.find(anchor)
    if idx == -1:
        sys.exit(f"❌ Anchor not found: {anchor[:60]}")
    print(f"  INSERT — before '{anchor[:40]}...'")
    return text[:idx] + payload + text[idx:]


def append_to_section(text, section_marker, next_section_marker, payload, *, skip_if):
    """Append `payload` at the end of the section between `section_marker` and `next_section_marker`."""
    if skip_if in text:
        print(f"  SKIP — {skip_if[:50]}... already present")
        return text
    idx_start = text.find(section_marker)
    idx_end = text.find(next_section_marker, idx_start + 1)
    if idx_start == -1 or idx_end == -1:
        sys.exit(f"❌ Section bounds not found: {section_marker[:30]} ... {next_section_marker[:30]}")
    print(f"  APPEND — to section '{section_marker[:40]}...'")
    return text[:idx_end] + payload + text[idx_end:]


# =====================================================================
# Main
# =====================================================================

def main():
    text = PLAYBOOK.read_text(encoding="utf-8")
    original_len = len(text)
    print(f"PROJECT_PLAYBOOK.md: {original_len} chars, {text.count(chr(10))} lines\n")
    print("Applying cherry-pick (bottom-up to keep offsets stable)...")

    # 1a. §8.16–8.21 (r25-r28 新原則) → 塞在 ## 九、附錄 之前
    text = insert_before(
        text,
        anchor="## 九、附錄",
        payload=SEC_8_16_TO_21,
        skip_if="### 8.16 Mixed-arity",
    )

    # 1b. §8.13–8.15 (SoT 漂移修復) → 塞在 §8.16 之前（已先插）
    # 用 §8.16 當 anchor 確保 §8.13-15 排在 §8.12 之後 §8.16 之前
    text = insert_before(
        text,
        anchor="### 8.16 Mixed-arity",
        payload=SEC_8_13_TO_15,
        skip_if="### 8.13 結構化 input fields",
    )

    # 2. §5.8 → 塞在 ## 六、 之前
    text = insert_before(
        text,
        anchor="## 六、",
        payload=SEC_5_8,
        skip_if="### 5.8 跨 phase",
    )

    # 3. §3.10 + §3.11 → 塞在 ## 四、 之前
    text = insert_before(
        text,
        anchor="## 四、",
        payload=SEC_3_10_3_11,
        skip_if="### 3.10 Cowork sandbox",
    )

    # 4. §3.6 補 4 條 PowerShell 規則 → append 到 §3.7 之前
    text = append_to_section(
        text,
        section_marker="### 3.6 常見錯誤與排查",
        next_section_marker="### 3.7 ",
        payload=SEC_3_6_APPEND,
        skip_if="#### 4 個必守規則",
    )

    if len(text) != original_len:
        PLAYBOOK.write_text(text, encoding="utf-8")
        print(f"\n✓ Wrote PROJECT_PLAYBOOK.md")
        print(f"  Before: {original_len} chars")
        print(f"  After:  {len(text)} chars (+{len(text) - original_len})")
        print(f"\nNext steps:")
        print(f"  git diff PROJECT_PLAYBOOK.md   # 檢查")
        print(f"  # 手動更新 HISTORY.md：§A 加修訂 entry + §B 加 r25-r28 案例索引")
        print(f"  git add PROJECT_PLAYBOOK.md HISTORY.md")
        print(f"  git commit -m 'feat(playbook): r25-r28 共通性原則 + SoT 漂移修復'")
        print(f"  git push origin main")
    else:
        print("\n→ No changes (all sections already present, idempotent skip)")


if __name__ == "__main__":
    main()
