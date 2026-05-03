# Phase 5b r27：曼陀羅檔案匯出/匯入（純前端，本機儲存）

**日期**：2026-05-04
**版本**：0.14.105 → 0.14.106
**範圍**：純前端 export/import 機制
- Tier 1：`.mandala.md`（YAML frontmatter + auto prose body）
- Tier 2：SVG 內嵌 `<metadata><mandala-config>` JSON

**測試**：14 r27 schema fixture tests + 173 累計測試全 pass

---

## 1. 動機

User 花時間繪製曼陀羅後希望：
- 把所有設定下載成一個 local 檔案，可帶到別台電腦繼續編輯
- 設定資料**完全本機**，**不上傳伺服器**
- 用 MD 格式（人類 + AI 都讀得懂）
- 將來能擴充成「上傳 gallery + 評分 + 分享」（對齊抄經模式 PSD 機制）

## 2. 三大關鍵設計決策

### 2.1 Schema 命名 `stroke-order-mandala-v1`

跟既存的 `stroke-order-psd-v1`（抄經軌跡）對齊。未來 r28 上 gallery 共用 `gallery.html` + `uploader.js` 基礎建設不需改架構。

### 2.2 雙 Tier 並行

**Tier 1 — `.mandala.md`**：YAML frontmatter（機器精確解析）+ Markdown body（人類 / AI 讀）。**單一真相來源在 frontmatter**，body 是 derived view（每次匯出系統自動 render，user 編輯只在「設計意圖」section 內生效）。

**Tier 2 — SVG 內嵌**：既有 SVG 下載路徑後 inject `<metadata><mandala-config><![CDATA[{json}]]></mandala-config></metadata>` 元素。一張 SVG = 視覺 + 完整還原資料 + 可編輯（拖回系統還原）。

兩 tier 並存 — user 偏好哪個用哪個。Import 時自動偵測檔頭（`---` → MD path / `<svg` → SVG path）。

### 2.3 中文標題 + 拼音 slug 雙存

User 希望檔名跨平台穩定（拼音）但檔內保留中文（系統 + AI 看得懂原字）。Schema：

```yaml
metadata:
  # 中文標題 + 拼音對照（拼音用於檔名 slug，import 時系統讀中文 title）
  title: "我的曼陀羅—九字真言"     # 拼音: wo-de-man-tuo-luo-jiu-zi-zhen-yan
  title_pinyin: "wo-de-man-tuo-luo-jiu-zi-zhen-yan"
```

Inline `# 拼音: xxx` 註解提升人類可讀性，`title_pinyin` 欄位給機器精確讀取。下載檔名 = `<title_pinyin>.mandala.md`。

拼音轉換用 `pinyin-pro@3.20.4` CDN 載入（≈300KB minified，僅 export 時用）。fallback：CDN 失敗時退到「ASCII-only 過濾」生成 slug。

## 3. 完整 Schema 規格

```yaml
schema: stroke-order-mandala-v1
exported_at: <ISO 8601>
generator: { app: stroke-order, version: <semver> }

metadata:
  id: <UUID v4 from crypto.randomUUID()>
  title: <中文 / 任意語系>
  title_pinyin: <a-z0-9- only>
  design_note: <user 自由 prose, AI 解讀此檔時看到>
  author: ""        # r28 上 gallery 時填寫
  created_at: <ISO>  # 首次 export 生成的時間，import 後保留
  modified_at: <ISO> # 每次 export 重設

canvas: { size_mm, page_width_mm, page_height_mm }
center: { type, text, size_mm, line_color, icon_style?, icon_n?, icon_size_mm? }
ring: { text, size_mm, spacing, orientation, auto_shrink, shrink_safety_margin,
        protect_chars, protect_radius_factor, line_color }
mandala: { style, composition_scheme, n_fold, show, overlap_ratio, lotus_*,
           rays_length_ratio, inscribed_padding_factor, r_ring_ratio,
           r_band_ratio, stroke_width, line_color }
extra_layers:
  - { ring, style, n_fold, r_mm, color, visible, ...style-specific... }
style: { font, cns_outline_mode, source }
```

**Body sections**（auto-generated from frontmatter）：
- `## 視覺概觀（自動生成，下次匯出會被覆蓋）` — 從 state render template
- `## 設計意圖` — 直接寫 `metadata.design_note`（user `<textarea>` 內容）

## 4. ID + created_at 跨 import/export 持久化

User flow 會這樣：
1. User 開新 mandala → `window._mandalaSessionMeta = null`
2. 第一次 export → 生成 id + created_at，存進 sessionMeta，寫入檔案
3. User 編輯後 export → 沿用同 id，created_at 保留，modified_at 更新
4. User 在另一台電腦 import 同檔案 → applyMandalaState 把 id + created_at 讀回 sessionMeta
5. 該機器後續 export → 仍用同 id（編輯歷史可追蹤）

這個機制給未來 gallery 上傳一個穩定 dedup key（同 id 的多版本可以連結成編輯軌跡）。

## 5. Migration 表

```javascript
const MD_MIGRATIONS = {
  "stroke-order-mandala-v1": (data) => data,  // identity
  // 未來 v2 從此加：v1 → v2 的轉換邏輯
};
```

匯入時 schema 不在表中 → reject + 顯示「不支援的 schema：xxx（已知：...）」。**嚴格但帶錯誤訊息引導**（不寬鬆吞錯讓使用者陷入沉默 bug）。

## 6. 純前端架構

| 元件 | 技術 |
|---|---|
| YAML parse / dump | `js-yaml@4.1.0` (CDN) |
| 拼音轉換 | `pinyin-pro@3.20.4` (CDN) |
| 檔案匯出 | `Blob` + `<a download>` 觸發 |
| 檔案匯入 | `<input type="file">` + `FileReader.readAsText()` |
| ID 生成 | `crypto.randomUUID()` (fallback Math.random) |
| 狀態保留 | `window._mandalaSessionMeta`（in-memory） |

**不經 server**：連 localhost API 都不需要。設定資料完全在使用者 browser memory + local file。

## 7. 主要 JS 模組（index.html 內）

| 函數 | 職責 |
|---|---|
| `mandalaBuildState()` | 從 UI inputs 抓所有設定 → state object |
| `_mandalaCurrentMetadata()` | 生成 metadata（id 沿用、modified_at 更新） |
| `_mandalaTitleToPinyin(title)` | 中文 → 拼音 slug |
| `serializeMandalaMd(state)` | state → frontmatter（manual template 保留註解）+ body |
| `parseMandalaMd(text)` | MD 字串 → state（含 schema validation） |
| `_mandalaInjectSvgMetadata(svg, state)` | Tier 2: SVG 加 `<metadata>` |
| `_mandalaExtractSvgMetadata(svg)` | Tier 2: SVG → state |
| `applyMandalaState(state)` | state → 套回 UI inputs（含 ring 重建） |
| `_mandalaSlugifyFilename(state)` | filename = `<pinyin>.mandala.md` |
| `_mandalaMigrateState(state)` | schema version 檢查 + migration |

## 8. 驗證

| 驗證項 | 結果 |
|---|---|
| `tests/test_mandala_state.py`（14 cases）— PyYAML 驗 fixture schema | **14 passed** |
| 全 mandala/web/wordart 測試（包含 r25/r26）| 173 passed |
| Index page 渲染（`curl /` ）| 200 OK，所有 r27 element + CDN refs 出現 |
| CDN 可達性（js-yaml + pinyin-pro）| 200 OK |
| JS syntax (`node --check`) | OK |

## 9. 為什麼不在 Python 也實作 parser

短答：r27 不需要。

長答：當前流程不需要 server-side parsing。匯出由前端 build；匯入由前端 parse；`/api/mandala` 仍然吃既有的 query params（不是吃 .mandala.md）。

**未來 r28 上 gallery 時**會需要 server-side parser：
- Server 收 .mandala.md → 解析 → render preview thumbnail（cache）
- Validation 防 schema 攻擊
- Indexed search

那時補一個 Python `mandala_state.py` module。設計上 schema 用標準 YAML，PyYAML 跟 js-yaml 互操作零成本。

## 10. 教訓 / 未來

- **MD 格式 = frontmatter（機器）+ body（人類/AI）的雙層架構**：要做給 AI 讀的檔案，純結構化 JSON 不夠 AI-friendly，純散文不夠機器精確。frontmatter + body 雙層是黃金標準。
- **拼音 slug 跟原文並存比單選一邊更穩**：跨平台檔名穩定靠拼音，系統還原靠原文，二者並存解決所有場景。
- **Schema 版本字串包含 `-v1`**：跟 PSD 對齊命名（`stroke-order-{kind}-v{n}`），未來 v2 升版有 migration table 接住，不破壞 v1 檔。
- **session metadata 跨 import/export**：id + created_at 用 `window._mandalaSessionMeta` 全域變數記住，避免 user 編輯一個 import 來的檔案後變成新 id（誤造分支）。
- **CDN dependency**：引入 2 個外部 lib（js-yaml 50KB + pinyin-pro 300KB）讓首次載入慢一點，但不需要 build pipeline。如果未來要 self-host，把 lib 放到 `/static/vendor/` 即可，import path 改成相對路徑。

## 11. 涉及檔案

```
src/stroke_order/web/static/index.html  (UI 加 file section + 大 r27 JS module)
tests/fixtures/sample.mandala.md         (新建 — schema 驗證 fixture)
tests/test_mandala_state.py              (新建 — 14 schema validation tests)
pyproject.toml                            (0.14.105 → 0.14.106)
```
