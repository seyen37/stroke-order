# Phase 5b r29：Gallery Like 機制（rating MVP）

**日期**：2026-05-04
**版本**：0.14.110 → 0.14.111
**範圍**：gallery 加 like / unlike toggle + count 顯示
**測試**：`tests/test_gallery_likes.py` 16 new cases，266 累計 pass

---

## 1. 動機

r28 系列做完 mandala upload + thumbnail 後，gallery 還缺「使用者互動」一塊。User 在 r27 thread 提過「下一步能提供使用者上傳檔案及給分的機制，可藉此分享自己的檔案」— r29 補上 like 機制（rating MVP）。

排除其他選項的理由：

| 機制 | 為何不選 |
|---|---|
| Star rating 1-5 | 偏 review，創作分享領域少用 |
| Like + Bookmark 雙機制 | r29 範圍過大，bookmark 留 r29b |
| 多 emoji reactions | 過度工程，MVP 不該做 |

**Like (二元 ❤️)** 是最通用的創作分享 UX，符合本系統用戶心智模型。

## 2. 設計核心

### 2.1 獨立 `likes` table，不 denormalize

```sql
CREATE TABLE likes (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    upload_id  INTEGER NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, upload_id)
);
CREATE INDEX likes_upload ON likes(upload_id);
```

**Why 獨立 table**：
- (user_id, upload_id) UNIQUE PK 自動 dedup（同 user × upload 一次 like）
- ON DELETE CASCADE 兩邊：user 刪 / upload 刪都自動清 likes
- 不 denormalize `uploads.like_count` column → 省 dual-write 同步邏輯
- Aggregate count 用 `(SELECT count(*) FROM likes WHERE upload_id = u.id)` 雖每 row 多一個 subquery 但 INDEX `likes_upload` 讓 lookup 是 O(log n)，MVP 規模 OK

### 2.2 Toggle semantics

POST `/api/gallery/uploads/{id}/like` toggle：
- 若 user 沒 like 過 → INSERT row + return `{liked: True, like_count: N+1}`
- 若已 like 過 → DELETE row + return `{liked: False, like_count: N-1}`

Single endpoint 處理兩個方向，前端 button 點擊一律 POST。標準 like UI pattern（Twitter / Instagram / GitHub star）。

### 2.3 Self-like 允許

User 能 like 自己的作品。理由：
- 藝術領域 self-appreciation 合理
- 防刷靠登入限制（per-user PK），不需禁 self-like
- 實作簡單（少一條 check）

### 2.4 Anonymous 不能 like

未登入 user 點擊 like button → 前端提示登入。理由：
- 沒 user_id 沒法 dedup
- IP / cookie 防重複容易繞過
- 跟 upload 行為一致（也需登入）

### 2.5 Optimistic UI update

前端不 refresh 整頁，POST 成功後直接更新該 card 的 button 狀態 + count：
```javascript
heart.textContent = data.liked ? '❤️' : '🤍';
cnt.textContent = String(data.like_count);
button.classList.toggle('is-liked', data.liked);
```
也同步 `state.items` 對應 item — 下次 list refresh 拉到相同 state，避免 server / client 不一致。

## 3. 實作

### 3.1 DB schema (`gallery/db.py`)

`likes` table + `likes_upload` index 加進 SCHEMA 常數。`CREATE TABLE IF NOT EXISTS` 自動 idempotent — 新建 DB 跟既有 DB 都 OK，不需 ALTER migration。

### 3.2 Service (`gallery/service.py`)

新增：
```python
def toggle_like(*, user_id, upload_id) -> {"liked": bool, "like_count": int}:
    # verify upload exists (raises NotFound)
    get_upload(upload_id)
    # check existing → INSERT or DELETE atomically
    # return updated count
    
def get_like_info(*, upload_id, user_id=None) -> {"like_count": int, "liked_by_me": bool}:
    # liked_by_me=False if user_id is None (anon)
```

修改：
- `get_upload` SELECT 加 `(SELECT count(*) FROM likes ...) AS like_count`
- `list_uploads` 加 `viewer_user_id` 參數，SQL 加 `EXISTS(...) AS liked_by_me`（viewer_user_id=None 用 -1 placeholder → 永遠 false）
- `_row_to_dict` 確保 `like_count: int`、`liked_by_me: bool`

### 3.3 API (`web/server.py`)

新增：
```python
@app.post("/api/gallery/uploads/{upload_id}/like")
async def gallery_uploads_like(upload_id, psd_session=Cookie(...)):
    user = _require_user(psd_session)  # 401 if not logged in
    return gallery_service.toggle_like(user_id=user["id"], upload_id=upload_id)
```

修改：
- `gallery_uploads_list` 從 cookie 拿 viewer，傳給 list_uploads → items 含 liked_by_me
- `gallery_uploads_get` 從 cookie 拿 viewer，加 liked_by_me 到 return

### 3.4 Frontend (`gallery/gallery.js` + `gallery.css`)

Card actions row 加 like button，handler 在 `renderList` 內 wire（跟 delete 同 pattern）。

CSS：`.gl-btn-like.is-liked .gl-like-count` 加重字粗體；hover heart scale 1.15 微動畫。

## 4. 測試 +16 (test_gallery_likes.py)

| 範疇 | Test 數 |
|---|---|
| DB schema | 2 (table 存在 / unique constraint) |
| `toggle_like` | 5 (create / second-toggle unlike / 多 user aggregate / self-like / NotFound) |
| `get_like_info` | 2 (anon / logged-in) |
| List/get includes count | 2 (get_upload / list_uploads with viewer) |
| FK cascade | 2 (delete upload / delete user → cascades likes) |
| API integration | 3 (401 for anon / login + toggle / detail liked_by_me) |

266 累計 pass（含修一個既有 test：schema 表單列表加 likes）。

## 5. 涉及檔案

```
src/stroke_order/gallery/db.py                 (likes table + likes_upload index)
src/stroke_order/gallery/service.py             (toggle_like + get_like_info + list/get like_count)
src/stroke_order/web/server.py                   (POST /like endpoint + list/get viewer)
src/stroke_order/web/static/gallery/gallery.js   (_likeButton + click handler + optimistic UI)
src/stroke_order/web/static/gallery/gallery.css  (.gl-btn-like 樣式)
tests/test_gallery_likes.py                       (新建，16 r29 tests)
tests/test_gallery_core.py                        (1 test 加 likes 到 schema 表列)
pyproject.toml                                     (0.14.110 → 0.14.111)
```

## 6. 教訓 / 共通性

- **Aggregate via subquery > denormalized counter**：MVP 階段別 over-optimize。`(SELECT count(*) FROM likes ...)` 配合 INDEX 滿足 N < 100k 上傳的需求。Denormalize 風險：dual-write 同步邏輯散在 toggle / delete / 任何 future 涉及 likes 的 endpoint，bug magnet。
- **`-1` placeholder for "no viewer"**：避免 SQL 條件分支（IF viewer THEN add column ELSE skip）。EXISTS subquery 用不存在的 user_id 自動 false，列表 SQL 統一一個版本。
- **CASCADE delete > app-level cleanup**：DB 層 ON DELETE CASCADE 自動清 likes，刪 upload / user 不需 service code 管。Less code = less bugs。
- **Optimistic UI**：toggle 後直接更新 DOM + state.items，不 refresh 整頁。fetch 失敗 → alert + 回滾（本實作 alert 後沒主動回滾，但 user refresh 即同步）。完整 optimistic 行為留 r29b 看 UX 反饋。

## 7. Defer 留給後續

| 待做 | Phase |
|---|---|
| Bookmark 私人收藏（user 自己看的列表） | r29b |
| Sort by likes / hot ranking | r29b |
| Like 數可視化排序 / featured selection | r29c |
| Email notification on like（過於 spammy）| 不做 |

## 8. r28 + r29 系列收尾統計

| Phase | 重點 | 版本 | Tests |
|---|---|---|---|
| r28 | gallery 接 mandala upload | 0.14.107 | 237 |
| r28b | SVG thumbnail | 0.14.108 | 243 |
| r28c | MD thumbnail (loader DI) | 0.14.109 | 247 |
| r28d | State-aware loader factory | 0.14.110 | 250 |
| r29 | Like / unlike + count | 0.14.111 | 266 |

從 r28 起算，gallery 從「PSD-only 列表 + 無互動」→「multi-kind upload + 視覺縮圖 + 用戶互動」完整一條 stack 升級。
