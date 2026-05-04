# Phase 5b r29d：User Profile Pages（社群最後一哩）

**日期**：2026-05-04
**版本**：0.14.113 → 0.14.114
**範圍**：r29c 後續 — 加 user profile（`/gallery/users/{id}`）+ 從 card 點擊 uploader 進入 profile filter view
**測試**：`tests/test_gallery_profile.py` 7 new → 302 累計 pass

---

## 1. 動機

r29 / r29b / r29c 完成 like / bookmark / sort / search 後，gallery 已是完整 discovery 平台，但仍缺**社群維度的最後一塊**：

- **看到一張喜歡的作品 → 想看作者其他作品**：目前只能在 list 用文字搜「Alice」，無法直接跳。
- **作者 = 黑盒子**：display_name 只是字串，無 bio / 累積總 likes / 加入時間，無法建立信任跟跟隨意願。
- **單張 upload 是孤點，缺累積上下文**：累積 60 likes 的老作者跟 0 累積的新人，目前 UI 沒區分。

r29d 把 uploader 從「字串標籤」升格為「entity with profile + stats」，補完 gallery 的社群骨架。

## 2. 設計核心

### 2.1 Profile = 既有資料聚合，不加新欄位

**選擇**：profile = `users` row + 對 `uploads` / `likes` 做 aggregate。**不加新 schema**。

**理由**：
- `users` 既有 email / display_name / bio / created_at 全用得上
- stats（total_uploads / total_likes_received / member_since）= 對既有 table COUNT，無 denormalize 必要
- < 10k rows 規模 + index 已建，aggregate query O(N) 毫秒級

**避開**：cached `user_stats` table（trigger / cron 維護）。Premature optimization。

### 2.2 Profile = 「banner + filtered list」，不開新 page

**選擇**：profile 不開新 SPA route / page，而是 gallery 同頁 + banner overlay + 自動套 `user_id` filter。

**UI flow**：
```
[user 在 gallery 看到 card]
    ↓ click 'Alice' uploader name
[banner 顯示 Alice 資料 + stats]
[grid 自動 filter 成 Alice 所有 uploads]
[原 search / sort / kind filter 仍可用 → 在 Alice 範圍內 search]
```

**理由**：
- 維持 SPA 簡潔（gallery.html 是唯一 page）
- 用 既有 list_uploads + `user_id` 參數即可，service 層只加 1 個 column 的 WHERE
- 「在某 user 作品中再 search/sort」→ 自然 composable

### 2.3 list_uploads 加 `user_id` filter，跟 sort/q/bookmarked 全 composable

**Service 訊號**：
```python
def list_uploads(*, user_id=None, viewer_user_id=None,
                 kind=None, q=None, sort=SORT_NEWEST,
                 bookmarked_by=None, ...) -> dict:
    if user_id is not None:
        WHERE += "u.user_id = ?"
        params.append(user_id)
```

不開新 endpoint `/users/{id}/uploads`，因為要支援「Alice 作品中搜『曼陀羅』sort by hot」這種組合 — 開新 endpoint 等於把 list 邏輯複製一份。

### 2.4 新 endpoint `GET /api/gallery/users/{id}` 純 profile

只 return user info + stats（不含 uploads list — list 走原 `/uploads?user_id=`）。

**理由**：banner 跟 list 是兩個獨立 fetch 點，banner 在 user 切換 profile filter 時更新一次即可，list 隨 sort/page/q 動。如果合在一起 endpoint，每次翻頁都重 fetch profile = 浪費。

### 2.5 Frontend：clickable uploader + URL state（hash route lite）

**Card 上 author name → `<a data-action="filter-user">`**：

```javascript
const authorHtml =
  `<a href="#" data-action="filter-user" data-user-id="${item.user_id}"
      class="gl-card-author-link">${_escape(author)}</a>`;
```

State 新增 `state.userFilter` (number | null)：
- `null` = 全 gallery 模式
- 數字 = profile filter 模式 → fetch profile + 帶 user_id 進 list_uploads

「離開 profile」按鈕 = 把 `state.userFilter = null` + clear banner + refresh。

URL hash route 留給 phase 5c（目前 reload 會 reset）— MVP 不引入 router 複雜度。

## 3. 實作

### 3.1 Service (`gallery/service.py`)

```python
def get_user_profile(user_id: int) -> dict:
    """Return user info + aggregated stats."""
    with db_connection() as conn:
        u = conn.execute(
            "SELECT id, email, display_name, bio, created_at "
            "FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if u is None:
            raise NotFound(f"user {user_id} 不存在")
        # COUNT uploads + SUM likes received via LEFT JOIN
        stats = conn.execute(
            "SELECT COUNT(DISTINCT u.id) AS upload_count, "
            "       COUNT(l.user_id)    AS like_count "
            "FROM uploads u "
            "LEFT JOIN likes l ON l.upload_id = u.id "
            "WHERE u.user_id = ? AND u.hidden = 0",
            (user_id,)
        ).fetchone()
    return {
        "user": {
            "id": u["id"], "email": u["email"],
            "display_name": u["display_name"], "bio": u["bio"],
            "created_at": u["created_at"],
        },
        "stats": {
            "total_uploads": stats["upload_count"] or 0,
            "total_likes_received": stats["like_count"] or 0,
            "member_since": u["created_at"],
        },
    }
```

`list_uploads(user_id=...)` 加 1 個 WHERE clause + param 即可。

### 3.2 API (`web/server.py`)

```python
@app.get("/api/gallery/users/{user_id}")
async def gallery_user_profile(user_id: int):
    try:
        return gallery_service.get_user_profile(user_id)
    except gallery_service.GalleryError as e:
        _gallery_error_to_http(e)

# list endpoint 加 user_id query param
user_id: Optional[int] = Query(None, ge=1),
```

NotFound → 404 經 `_gallery_error_to_http` 統一映射。

### 3.3 Frontend

**`gallery.js`** 新增：

```javascript
state.userFilter = null;
state.profile = null;

async function _fetchUserProfile(uid) {
    const r = await fetch(`/api/gallery/users/${uid}`);
    if (!r.ok) throw new Error('profile fetch failed');
    return await r.json();
}

function renderProfileBanner() {
    if (!state.profile) {
        $banner.innerHTML = ''; $banner.hidden = true;
        return;
    }
    const p = state.profile;
    $banner.hidden = false;
    $banner.innerHTML = `
      <div class="gl-profile-info">
        <h2>${_escape(p.user.display_name || p.user.email)}</h2>
        ${p.user.bio ? `<p class="gl-profile-bio">${_escape(p.user.bio)}</p>` : ''}
        <div class="gl-profile-stats">
          <span>📤 ${p.stats.total_uploads} uploads</span>
          <span>❤️ ${p.stats.total_likes_received} likes</span>
          <span>📅 since ${p.stats.member_since.slice(0, 10)}</span>
        </div>
      </div>
      <button class="gl-profile-clear" data-action="clear-profile">× 全部</button>
    `;
}

// click delegate
gridEl.addEventListener('click', async (ev) => {
    const link = ev.target.closest('[data-action="filter-user"]');
    if (link) {
        ev.preventDefault();
        const uid = Number(link.dataset.userId);
        state.userFilter = uid;
        state.profile = await _fetchUserProfile(uid);
        state.page = 1;
        renderProfileBanner();
        refresh();
        return;
    }
});
```

**Banner 動態 inject**：避免改 `gallery.html`，JS 在 `renderProfileBanner` 第一次呼叫時 `document.createElement('section')` 注入到 `.gl-main` 之上。Pure JS 控制，HTML 維持乾淨。

**`gallery.css`**：`.gl-profile-banner` flex layout + `.gl-card-author-link` underline-on-hover。

## 4. 測試 +7（test_gallery_profile.py 全新）

| 範疇 | Test 數 |
|---|---|
| `get_user_profile` | 3（含 uploads/likes 統計 / 0-state / unknown user→NotFound） |
| `list_uploads(user_id=)` | 2（基本 filter / 跟 q+sort 組合） |
| API | 2（`GET /api/gallery/users/{id}` 200 / 404） |

302 累計 pass（295 → 302）。

## 5. 涉及檔案

```
src/stroke_order/gallery/service.py              (get_user_profile + list_uploads user_id filter)
src/stroke_order/web/server.py                   (GET /api/gallery/users/{id} + user_id Query)
src/stroke_order/web/static/gallery/gallery.js   (state.userFilter/profile + fetch + banner dynamic inject + click delegate)
src/stroke_order/web/static/gallery/gallery.css  (.gl-profile-banner / .gl-card-author-link)
tests/test_gallery_profile.py                     (新建，7 r29d tests)
pyproject.toml                                     (0.14.113 → 0.14.114)
```

## 6. 教訓 / 共通性

- **Aggregate stats 不 denormalize 是合理 default**：`total_uploads` / `total_likes_received` 直接 COUNT，每次 profile fetch < 1ms。Cached column 要維護 trigger，bug 面更大。除非 profile 變高頻 page，否則不該預先 cache。
- **Profile = 「filter view + banner」比「獨立 page」乾淨**：list_uploads 加 1 個 user_id WHERE 即可跟 sort/q/bookmarked 全 composable。獨立 page 等於複製 list 邏輯，未來改 sort 算法兩處同步是慢性技術債。
- **Profile 跟 list 拆兩 endpoint**：banner 換 profile 才 fetch，list 隨 page/sort 動。合在一起 = 翻頁也重抓 profile。「fetch frequency 不一樣 → endpoint 拆」是通用 API 設計訊號。
- **LEFT JOIN 對 0-state 必要**：`get_user_profile` 對新註冊 user（無 uploads）做 stats 必須 LEFT JOIN，否則 INNER JOIN 會把整 row drop 掉，user 無 stats 顯示。寫測試 `test_profile_zero_uploads_zero_likes` 防回歸。
- **Click delegation 比 inline `onclick` 乾淨**：grid 上每個 card 都 dynamic render，掛 individual listener 等於 leak。`gridEl.addEventListener('click', e => closest(...))` 是 SPA 模式 standard。

## 7. r28-r29d 系列累計統計

| Phase | 重點 | Tests | 版本 |
|---|---|---|---|
| r28 | gallery 接 mandala upload | +20 | 0.14.107 |
| r28b | SVG thumbnail | +6 | 0.14.108 |
| r28c | MD thumbnail (loader DI) | +4 | 0.14.109 |
| r28d | state-aware loader factory | +3 | 0.14.110 |
| r29 | like 機制 | +16 | 0.14.111 |
| r29b | bookmark + sort by likes | +17 | 0.14.112 |
| r29c | hot ranking + search | +12 | 0.14.113 |
| **r29d** | **user profile + user_id filter** | **+7** | **0.14.114** |

**Today total: +85 tests (207 → 302), +8 phases, 8 versions, 8 decision logs.**

Gallery 完整骨架：「**multi-kind upload + thumbnail + like + bookmark + sort (newest/likes/hot) + search + kind/bookmark filter + user profile + user filter view**」 — 一日內從零搭起完整社群分享平台。

## 8. Defer 留給後續

| 待做 | Phase |
|---|---|
| URL hash route（`#user=42` deep-link / refresh 保留 state） | phase 5c |
| Profile 編輯（user 改自己 bio / display_name） | phase 5c |
| Profile avatar / 頭像上傳 | phase 5c+ |
| Follow / 跟隨 user → feed | phase 6 |
| Profile 內顯示 received-likes 排行（user 最受歡迎前 3 作品） | r29e |
| Featured / curated picks（admin role） | phase 5c |
| FTS5 + 中文分詞 advanced search | 待 user 反饋驅動 |
