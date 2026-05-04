# Phase 5b r28：Gallery 接 mandala upload（multi-kind generalization）

**日期**：2026-05-04
**版本**：0.14.106 → 0.14.107
**範圍**：把現有 5g 公眾分享庫從「PSD only」擴成「多 kind 支援」（先收 mandala）
**測試**：`tests/test_gallery_mandala.py` +20 tests，198 累計 pass

---

## 1. 動機

User 在 r27 完成 `.mandala.md` 純前端 export/import 後，要求「下一步能提供使用者上傳檔案及給分機制，可藉此分享自己的檔案」。

Repo 已有 5g 公眾分享庫（`gallery.html` + `gallery.js` + `uploader.js` + `gallery/service.py`），但寫死 `stroke-order-psd-v1`。Phase 5b r28 把它通用化，接受 mandala 作為第二個 kind。

評分（rating / like）功能評估後**獨立到 r29**，避免 r28 過大。

## 2. 三大關鍵設計決策

### 2.1 DB schema：加 `kind` + `summary_json`，向後相容

既有 `uploads` table 有 PSD 專用欄位 `trace_count` / `unique_chars` / `styles_used`。直接加更多 mandala 專用 column 會污染 schema。

**改用通用 `summary_json TEXT`**：
- 新 row 寫 `kind` (`psd` / `mandala`) + `summary_json`（dict 序列化）
- legacy PSD rows 仍寫 `trace_count` 等（雙寫，過渡期向後相容）
- mandala rows 不寫 legacy 欄位（`trace_count = 0` / `styles_used = NULL`）
- 既有 DB 透過 ALTER TABLE 自動 migrate（`kind` default 'psd' 自動 backfill）

### 2.2 從內容偵測 kind，不靠副檔名

Frontend `_detectKindFromText(text)` 純看內容開頭：
- `<svg` 或 `<?xml` → mandala-svg
- `---` → mandala-md
- `{` → psd-json

用副檔名判斷會被使用者改檔名打破，**內容偵測**是 single source of truth。後端 `parse_and_validate_mandala()` 同樣用內容偵測（不信 multipart filename）。

### 2.3 雙入口 + 統一上傳路徑

**入口 A**：mandala 模式按鈕「⬆️ 上傳到 Gallery」直接觸發 POST，不用切到 gallery 頁面。

**入口 B**：gallery 頁面 file picker 接受 `.json` / `.md` / `.svg`。

兩個入口同一條 backend 路徑（`POST /api/gallery/uploads` with `kind` form field），差別只在前端 UI；schema validation / dedup / rate limit 都是同一個 `create_upload(kind=...)` dispatch。

## 3. 架構：dispatch by kind

```python
# service.py
KIND_PSD     = "psd"
KIND_MANDALA = "mandala"
ALLOWED_KINDS = (KIND_PSD, KIND_MANDALA)

VALIDATORS = {
    KIND_PSD:     lambda b: (parse_and_validate_psd(b), "json"),
    KIND_MANDALA: parse_and_validate_mandala,  # returns (state, "md"|"svg")
}
SUMMARIZERS = {
    KIND_PSD:     summarise_traces,
    KIND_MANDALA: summarise_mandala,
}

def create_upload(*, user_id, content_bytes, filename,
                  title, comment, kind=KIND_PSD):
    if kind not in ALLOWED_KINDS:
        raise InvalidUpload(...)
    state, ext = VALIDATORS[kind](content_bytes)
    summary = SUMMARIZERS[kind](state)
    # ... 統一 dedup / rate limit / disk write / DB insert
```

新增 kind 只需：
1. 加 `KIND_X` 常數
2. 寫 `parse_and_validate_x(content_bytes) → (state, ext)`
3. 寫 `summarise_x(state) → dict`
4. 加進 `VALIDATORS` / `SUMMARIZERS` dict
5. 前端 `_detectKindFromText` 加偵測 + analyser

## 4. Mandala validator 設計

```python
def parse_and_validate_mandala(content_bytes: bytes) -> tuple[dict, str]:
    """Returns (state, source_format)."""
    text = _common_size_decode(content_bytes)
    text_stripped = text.lstrip()
    if text_stripped.startswith("<svg") or text_stripped.startswith("<?xml"):
        # SVG path: extract <mandala-config><![CDATA[json]]></mandala-config>
        ...
        source_format = "svg"
    else:
        # MD path: split frontmatter + yaml.safe_load
        ...
        source_format = "md"
    
    if state.get("schema") != MANDALA_SCHEMA_TAG:
        raise InvalidUpload(f"不支援的 schema：{state.get('schema')!r}；需 {MANDALA_SCHEMA_TAG}")
    
    missing = [k for k in MANDALA_REQUIRED_TOP if k not in state]
    if missing:
        raise InvalidUpload(f"frontmatter 缺少必要欄位：{', '.join(missing)}")
    
    return state, source_format
```

required top-level: `schema, canvas, center, ring, mandala`（給 server 一個快速 sanity check，完整 schema 檢查靠 r27 client-side migration table）

## 5. 前端 UI

### Gallery 頁面新增
- `<script>` 載入 js-yaml CDN（前端能 parse mandala MD frontmatter 做 preview）
- File input accept extended：`.json,.md,.mandala.md,.svg,...`
- Upload dialog 提示文案改成兩 kind 都支援
- Toolbar 加 kind filter tabs（全部 / 抄經軌跡 / 曼陀羅）
- Card 加 kind badge + kind-specific summary line + kind-aware download label

### Mandala 模式新增
- `⬆️ 上傳到 Gallery` 按鈕，緊鄰既有 `📥 匯出` / `📤 匯入`
- click → 確認 title + 設計意圖 → 序列化 state for blob → POST 到 `/api/gallery/uploads`
- 401 / 403 → 提示開新分頁去 `/gallery` 登入
- 200 → 提示成功 + 開新分頁看作品

## 6. API 變動

| Endpoint | 變動 |
|---|---|
| `POST /api/gallery/uploads` | 新增 `kind: str = Form('psd')`，default psd 向後相容 |
| `GET /api/gallery/uploads?kind=psd|mandala` | 新增 optional kind filter |
| `GET /api/gallery/uploads/{id}/download` | 依 kind + file_path 推 content-type（json / md / svg） |

## 7. 驗證

| 驗證項 | 結果 |
|---|---|
| `tests/test_gallery_mandala.py`（20 cases）| **20 passed** |
| 全 gallery + mandala 測試（含 r25-r28）| 198 passed |
| E2E flow（建 user → 上傳 .mandala.md → 列表 filter → 下載 → reject bogus kind）| ✓ PASS |
| JS syntax (`node --check` ×3) | OK |
| API 422 反應 bogus kind | 確認 reject |

## 8. 棄用 / 行為變化

無 breaking changes。

PSD 既有 endpoint / record 結構保留：
- `trace_count` / `unique_chars` / `styles_used` 仍然寫入 PSD upload
- 新增的 `summary` field（從 `summary_json` parse）對 PSD 也有（內含 trace_count / unique_chars / styles_used 副本）
- 列表 card 渲染對 PSD 自動降級到舊欄位（`item.trace_count`），對 mandala 用 `item.summary.layer_count`

## 9. Defer / 留給後續

| Feature | 後續 phase |
|---|---|
| Mandala SVG thumbnail（cairosvg server-side render） | r28b |
| Rating / like / score 機制 | r29 |
| Tags / search | r29 或更後 |
| 客戶端 magic-link 登入流程整合 mandala 頁面 | TBD |

## 10. 教訓 / 共通性

- **By-kind dispatch dict 比 if/elif 鏈乾淨**：`VALIDATORS[kind](bytes)` 跟 `SUMMARIZERS[kind](state)` — 加新 kind 不用改 `create_upload` 的核心邏輯，只動 dict。
- **內容偵測 > 副檔名信任**：filename 可被 user 改，content prefix 不會。Frontend + backend 都用 content sniff。
- **Generic summary_json 比 typed columns 擴充友善**：列 4 個 mandala 欄位進 schema 會無止盡擴下去；JSON dict 一次解決所有 kind 的「summary 顯示」需求。Trade-off 是不能直接 SQL filter 「找 layer_count > 5 的 mandala」— 但這需求不存在 / 可後加 `layer_count` index。
- **既存 SCHEMA `IF NOT EXISTS` 不會幫忙加 column**：升 schema 必須額外 migration helper（`ALTER TABLE` + `PRAGMA table_info` 偵測）— 為 idempotent 安全。
- **Backward-compat dual-write**：PSD upload 既寫 legacy column 也寫 summary_json。下個 phase 可考慮純粹遷移到 summary_json 後 drop legacy column。

## 11. 涉及檔案

```
src/stroke_order/gallery/db.py              (schema + ALTER TABLE migration)
src/stroke_order/gallery/service.py          (mandala validator + summarizer + kind dispatch)
src/stroke_order/web/server.py               (POST /uploads kind form, GET kind filter, download mime)
src/stroke_order/web/static/gallery.html     (file input accept + filter tabs + dialog hint)
src/stroke_order/web/static/gallery/uploader.js  (kind detection + dual analyser + kind form field)
src/stroke_order/web/static/gallery/gallery.js   (kind filter state + tabs wire + kind-aware card)
src/stroke_order/web/static/gallery/gallery.css  (filter tab + kind badge styles)
src/stroke_order/web/static/index.html       (mandala mode 上傳到 Gallery 按鈕 + handler)
tests/test_gallery_mandala.py                (新建，20 r28 tests)
pyproject.toml                                (0.14.106 → 0.14.107)
```
