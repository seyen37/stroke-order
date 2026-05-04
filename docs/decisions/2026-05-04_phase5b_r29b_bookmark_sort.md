# Phase 5b r29b：Gallery Bookmark + Sort by Likes

**日期**：2026-05-04
**版本**：0.14.111 → 0.14.112
**範圍**：r29 後續 — 私人收藏 (bookmark) + 按 like 數排序
**測試**：`tests/test_gallery_bookmarks.py` 17 new + 1 既有 test 更新 → 283 累計 pass

---

## 1. 動機

r29 ship 後 gallery 有 like 機制（公開讚賞 + count），但缺：
- **私人收藏**：user 想存「之後再看」的作品（跟「公開讚」語意不同）
- **找熱門**：list 預設 newest first，沒法看「最受歡迎」

r29b 一次補齊兩個 deferred items（r29 decision log §7 承諾）。

## 2. 設計核心

### 2.1 Bookmark 跟 Like 完全獨立

| 比較 | Like | Bookmark |
|---|---|---|
| 語意 | 公開讚賞 | 私人收藏 |
| 計數可見性 | 全公開（card 顯示 count） | 私人（不顯示計數） |
| 互動 | 任何 user 看得到別人 like | 只有自己看得到自己的 bookmarks |
| Schema | likes table | bookmarks table（mirror likes） |

**獨立 table** 比共用更乾淨：兩個 mechanism 演化方向不同（like 可能加 reactions / 排行；bookmark 可能加分類 folder），分開不互相牽動。

### 2.2 Sort 簡單版優先

只支援 `newest` (default) 跟 `likes`。**不**做 Reddit-style hot ranking — 公式工程化 + 需 age decay tuning，過度工程 MVP 不該做。

### 2.3 「我的收藏」用 filter 而非獨立頁面

兩種 UI 路：
- (A) 獨立 `/gallery/bookmarks` 子頁面 — SPA 拆兩個 view，狀態管理複雜
- (B) ★ Filter tab：toolbar 加「📌 我的收藏」tab，`?bookmarked=true` filter — 跟 kind filter 同 pattern

**(B) 簡單**：既有 list infrastructure 重用、跟 sort 可組合、登出/登入切換 graceful（hidden + 自動切回全部）。

### 2.4 `bookmarked` 跟 `kind` filter 互斥

當 user 切「我的收藏」→ 自動清掉 kind filter（顯示「所有種類」的 bookmarked uploads）。雙 filter 同時生效會讓 UX 困惑（「曼陀羅的我的收藏」是 sub-of-sub）。簡化決策。

## 3. 實作

### 3.1 DB schema

```sql
CREATE TABLE bookmarks (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    upload_id  INTEGER NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, upload_id)
);
CREATE INDEX bookmarks_user ON bookmarks(user_id);
```

跟 likes 結構完全 mirror — 兩個 mechanism 同 pattern 易讀易維護。`bookmarks_user` index 給「我的收藏」filter（撈該 user 的 bookmarks）。

### 3.2 Service

```python
def toggle_bookmark(*, user_id, upload_id) -> {"bookmarked": bool}:
    # atomic INSERT or DELETE
    
def is_bookmarked_by(*, upload_id, user_id) -> bool:
    # 給 detail endpoint 用

# list_uploads 加：
SORT_NEWEST = "newest"
SORT_LIKES = "likes"
ALLOWED_SORTS = (SORT_NEWEST, SORT_LIKES)

def list_uploads(
    *, page, size, kind=None, viewer_user_id=None,
    sort=SORT_NEWEST,           # r29b: 'newest' | 'likes'
    bookmarked_by=None,         # r29b: filter to user's bookmarks
):
    ...
    # SQL：
    # - bookmarked_by filter → WHERE EXISTS(... bookmarks)
    # - sort=likes → ORDER BY like_count DESC, created_at DESC, id DESC
    # - 每 row 加 EXISTS(... bookmarks WHERE user_id=viewer) AS bookmarked_by_me
```

`viewer_user_id=None` 用 `-1` placeholder（r29 既有 pattern 延續），bookmarked_by_me 永遠 false。

### 3.3 API

```python
# POST /api/gallery/uploads/{id}/bookmark — 需登入
@app.post("/api/gallery/uploads/{upload_id}/bookmark")
async def gallery_uploads_bookmark(upload_id, psd_session=Cookie(...)):
    user = _require_user(psd_session)
    return gallery_service.toggle_bookmark(...)

# GET /uploads 加 sort + bookmarked params
sort: str = Query("newest", pattern="^(newest|likes)$"),
bookmarked: bool = Query(False),  # True 需登入

# GET /uploads/{id} 也加 bookmarked_by_me（mirror liked_by_me）
```

### 3.4 Frontend

**Toolbar**：
- 加 sort dropdown：`📅 最新` / `❤️ 最多讚`
- kind filter 加「📌 我的收藏」tab（hidden 直到登入）

**Card actions**：
- 加 `_bookmarkButton(item)` 在 like button 旁
- 📌 已收藏 / 📍 未收藏（兩個 icon 視覺對比）

**Click handler**：
- 跟 like 同 pattern (POST → optimistic UI update + state.items 同步)
- 在「我的收藏」filter 內取消收藏 → 自動 refresh（該 card 應從列表消失）

**State**：
- `state.sort` ∈ `{'newest', 'likes'}`
- `state.bookmarkedOnly` boolean
- 登出時自動切回 bookmarkedOnly=false

## 4. 測試 +17 (test_gallery_bookmarks.py 全新)

| 範疇 | Test 數 |
|---|---|
| DB schema | 2 (table 存在 / unique constraint) |
| `toggle_bookmark` | 3 (toggle / nonexistent / is_bookmarked_by) |
| Sort | 3 (sort=likes / default newest / invalid) |
| Bookmarked filter | 3 (filter / bookmarked_by_me column / combo sort+filter) |
| FK cascade | 1 (delete upload cascades bookmarks) |
| API integration | 5 (bookmark 401 / bookmark 200 / bookmarked filter 401 / sort=likes / detail bookmarked_by_me) |

283 累計 pass（含修 1 既有：test_db_schema_creates_all_tables 加 `bookmarks` 到 schema 表單列表）。

## 5. 涉及檔案

```
src/stroke_order/gallery/db.py                  (bookmarks table + bookmarks_user index)
src/stroke_order/gallery/service.py              (toggle_bookmark + is_bookmarked_by + list sort/bookmarked_by)
src/stroke_order/web/server.py                    (POST /bookmark + GET sort/bookmarked + detail bookmarked_by_me)
src/stroke_order/web/static/gallery.html          (toolbar 加 sort + 「我的收藏」tab)
src/stroke_order/web/static/gallery/gallery.js    (state.sort/bookmarkedOnly + handlers + UI sync)
src/stroke_order/web/static/gallery/gallery.css   (.gl-sort + .gl-btn-bookmark + .gl-filter-bookmark)
tests/test_gallery_bookmarks.py                    (新建，17 r29b tests)
tests/test_gallery_core.py                         (1 line：schema table 列表加 bookmarks)
pyproject.toml                                      (0.14.111 → 0.14.112)
```

## 6. 教訓 / 共通性

- **獨立 table 給語意獨立 mechanism**：bookmarks 跟 likes 雖結構相同，但語意不同 → 不共用 table。將來 evolve 方向（reaction / folder / 排行）也不同，分開省未來 refactor。
- **Filter tab > 子頁面**：「我的收藏」在 SPA 內就是個 filter，重用既有 list infrastructure。建獨立 page 純粹增加狀態管理複雜度，UX 也沒比較好。
- **Filter 互斥 > 雙 filter 組合**：bookmarked 跟 kind filter 互斥讓 UX 簡單。雙條件 sub-of-sub 多數使用者會困惑（「曼陀羅的我的收藏」這個 mental model 不直覺）。
- **`-1` placeholder 模式延續**：viewer_user_id=None → SQL 用 -1，EXISTS 永遠 false。r29 模式 r29b 沿用 → list SQL 統一單一版本。
- **Combo 測試確認雙 filter 互動**：`sort=likes + bookmarked=true` 同時生效驗證 SQL 兩個 condition 正交，避免某 filter 被另一個吃掉。

## 7. r29 → r29b 系列收尾

| Phase | 重點 | Tests | 版本 |
|---|---|---|---|
| r29 | Like / unlike toggle | 16 | 0.14.111 |
| r29b | Bookmark + sort by likes | 17 (+1 修) | 0.14.112 |

合計 33 user-interaction tests，gallery 從「PSD-only 純 read 列表」演化到「multi-kind upload + thumbnail + like + bookmark + sort + filter 完整社交分享平台」。

## 8. Defer 留給後續

| 待做 | Phase |
|---|---|
| Reddit-style hot ranking (likes + age decay) | 觀察用戶反饋 |
| Bookmark folders / tags | r29c+ |
| 篩選排序組合（kind + bookmarked + sort）| 看 UX 反饋 |
| 排行榜 / featured selection | r29c |
| Unsubscribe / privacy controls | 看政策需求 |
