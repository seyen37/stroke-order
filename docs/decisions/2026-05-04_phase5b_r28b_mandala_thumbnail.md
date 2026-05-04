# Phase 5b r28b：Mandala SVG Thumbnail（Gallery Card 視覺預覽）

**日期**：2026-05-04
**版本**：0.14.107 → 0.14.108
**範圍**：r28a 補充 — gallery list 加 mandala 縮圖預覽
**測試**：`tests/test_gallery_mandala.py` +6 → 26（原 20 + r28b 6）

---

## 1. 動機

r28a ship 後 gallery list 對 mandala upload 顯示 placeholder 沒有視覺。User 視覺辨識弱、找作品慢。加 thumbnail 直接呈現作品輪廓 + 配色，gallery 體驗大幅改善。

## 2. 設計核心：SVG-only thumbnail，搭配 mandala 模式上傳改 SVG path

### 2.1 SVG vs MD 的 thumbnail 路徑

| Source | Thumbnail 路徑 | 複雜度 |
|---|---|---|
| `.svg`（Tier 2，含 metadata） | cairosvg svg2png 直接轉 | 簡單 |
| `.mandala.md`（Tier 1） | parse state → 重 render → cairosvg。需 char loader DI | 複雜 |

**r28b 只做 SVG path**，MD upload 跳過 thumbnail（gallery card 沒 thumbnail，`<img onerror>` 自動隱藏）。MD 渲染需 server-side char loader（API endpoint 已有，但跨模組依賴）— 留給 r28c。

### 2.2 Mandala 模式上傳改成 SVG path

但若不改 mandala 模式上傳，從 mandala 模式上傳的全是 MD（無 thumbnail）— gallery 看不到圖。

→ 改 mandala 模式上傳：fetch `/api/mandala?format=svg` 拿 SVG → JS 注入 metadata → upload 為 `.svg`。多一個 SVG render request（100-300ms latency）但換來完整 thumbnail。

CDN 失敗時 fallback 到 MD path（保 r28a 行為）。

### 2.3 Storage 不動 schema

不加 `thumbnail_path` column — 從 `file_path` 推算：
```python
def thumbnail_path_of(upload: dict) -> Path:
    fp = uploads_dir() / upload["file_path"]
    return fp.with_suffix(".thumb.png")
```

省一次 DB schema migration。

## 3. 實作

### Backend `gallery/service.py`

新增：
- `THUMBNAIL_SIZE_PX = 256` / `THUMBNAIL_SUFFIX = ".thumb.png"`
- `thumbnail_path_of(upload) → Path`
- `_generate_svg_thumbnail(svg_bytes, *, size_px=256) → bytes`：cairosvg svg2png
- `_maybe_generate_thumbnail(content_bytes, *, kind, source_format, abs_path) → bool`：
  - `kind != "mandala"` → False
  - `source_format != "svg"` → False
  - 失敗時 log warning + return False（不擋 upload）

修改：
- `create_upload` 在主 file 寫盤後 call `_maybe_generate_thumbnail`
- `delete_upload` 順手清 thumbnail（`thumbnail_path_of(upload).unlink()`）

### API `web/server.py`

新增：
```python
@app.get("/api/gallery/uploads/{upload_id}/thumbnail")
async def gallery_uploads_thumbnail(upload_id: int):
    upload = gallery_service.get_upload(upload_id)
    if upload.get("hidden"): raise HTTPException(403, ...)
    thumb = gallery_service.thumbnail_path_of(upload)
    if not thumb.is_file(): raise HTTPException(404, ...)
    return FileResponse(thumb, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})
```

24h cache 因為 thumbnail 永不變（upload-time 一次性生成）。

### Frontend `gallery/gallery.js` + `gallery.css`

Card render 加 `_kindThumbnail(item)` 在 mandala 卡片頂端：
```javascript
return `<div class="gl-card-thumb">
  <img src="/api/gallery/uploads/${item.id}/thumbnail"
       alt="..." loading="lazy"
       onerror="this.parentElement.style.display='none'">
</div>`;
```

`onerror` 自動隱藏 — MD upload / 缺 thumbnail / 後端 fail 都 graceful degrade。

CSS：1:1 aspect-ratio + object-fit:contain 保比例不變形。

### Frontend `index.html` mandala 模式上傳

從 r28a MD path 改 SVG path：

```javascript
// 1. fetch SVG
const params = mandalaBuildParams();
params.set("format", "svg");
const r = await fetch(`/api/mandala?` + params);
const svgText = await r.text();

// 2. 注入 metadata
const enrichedSvg = _mandalaInjectSvgMetadata(svgText, state);
const blob = new Blob([enrichedSvg], { type: "image/svg+xml;charset=utf-8" });

// 3. upload as .svg
fd.append("file", blob, `${slug}.svg`);
fd.append("kind", "mandala");
```

SVG render 失敗 → fallback MD path（保 r28a 上傳能力，無 thumbnail 但能上傳）。

## 4. 測試 +6

| Test | 驗證 |
|---|---|
| `test_thumbnail_generated_for_mandala_svg` | SVG upload 生成 PNG，magic bytes 正確 |
| `test_thumbnail_skipped_for_mandala_md` | MD upload 跳過 thumbnail（檔案不存在） |
| `test_thumbnail_skipped_for_psd` | PSD upload 跳過 thumbnail |
| `test_thumbnail_endpoint_serves_png` | API endpoint 回 200 + PNG bytes |
| `test_thumbnail_endpoint_404_for_md_upload` | MD upload thumbnail endpoint 回 404 |
| `test_thumbnail_deleted_on_upload_delete` | delete_upload 連 thumbnail 一起清 |

204 累計 pass（含 r25-r28 全套）。

## 5. 用 cache header

`Cache-Control: public, max-age=86400` — thumbnail 是 upload-time immutable，24h cache 安全。Mandala upload 多了不會撞 cache（每個 upload id 獨立）。

## 6. 關鍵 trade-offs

| 取捨 | 選擇 | 為什麼 |
|---|---|---|
| Upload-time vs lazy generation | upload-time | 簡單；50-200ms 上傳 latency 可接受換取首次瀏覽不卡 |
| SVG only vs SVG+MD | SVG only | MD path 需 char loader DI 跨層；r28c 再加 |
| 改 mandala 模式上傳 vs 不改 | 改 SVG path | 否則從 mandala 模式上傳 = MD = 無 thumbnail，UX 不一致 |
| Schema 加 thumbnail_path column vs 推算 | 推算 | 省一次 DB migration |
| `<img onerror>` 隱藏 vs API check | onerror | 客戶端輕量，不需多 1 個 API call |

## 7. 涉及檔案

```
src/stroke_order/gallery/service.py          (thumbnail constants + generator + create/delete 整合)
src/stroke_order/web/server.py                (GET /uploads/{id}/thumbnail endpoint)
src/stroke_order/web/static/gallery/gallery.js  (_kindThumbnail card render)
src/stroke_order/web/static/gallery/gallery.css (.gl-card-thumb 樣式)
src/stroke_order/web/static/index.html        (mandala 模式上傳改 SVG path + fallback MD)
tests/test_gallery_mandala.py                 (+6 r28b tests，總 26)
pyproject.toml                                 (0.14.107 → 0.14.108)
```

## 8. 教訓 / 共通性

- **Graceful degrade UI 比 server-side perfect 重要**：`<img onerror>` 自動隱藏 — 後端 thumbnail 缺 / 失敗 / 永遠不會生成的 PSD card，前端統一 graceful。比寫 API check + conditional render 簡單。
- **Storage path 推算 > schema column**：當新欄位是 derivable from existing data，推算函式（`thumbnail_path_of`）省一次 schema migration + 永遠跟主 file 同步。
- **fallback path 保 backward compat**：r28a → r28b 切換 SVG path 時保留 MD fallback，CDN / API 失敗仍能上傳（無 thumbnail 但能用）。漸進改善 vs 強硬 break。
- **24h Cache-Control 對 immutable assets**：thumbnail upload-time 生成後永不變 → 強 cache 給瀏覽器，省後續 request。

## 9. Defer 留給後續

| 待做 | Phase |
|---|---|
| MD upload thumbnail（含 char loader DI） | r28c |
| Thumbnail 失效 / 重新生成 endpoint | r28c+ |
| 多尺寸 thumbnail（list / detail / preview） | r28d+ |
| Lazy generation（首次請求才 render） | 觀察必要性 |
