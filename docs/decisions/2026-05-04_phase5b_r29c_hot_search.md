# Phase 5b r29c：Hot Ranking + Text Search（discovery 補完）

**日期**：2026-05-04
**版本**：0.14.112 → 0.14.113
**範圍**：r29b 後續 — 補 discovery 兩工具（hot 排序 + 文字 search）
**測試**：`tests/test_gallery_search_hot.py` 12 new → 295 累計 pass

---

## 1. 動機

r29 / r29b 完成 like / bookmark / sort by likes 後，gallery 仍缺：
- **找熱門**：sort=likes 純看 like 數，所有時代擠在一起；user 想看「最近受歡迎」
- **找特定作品**：toolbar 有 hidden 的 `gl-search` input，但沒 wire（lukewarm 狀態）

r29c 補完 discovery 一條 stack：sort=hot + text search。

## 2. 設計核心

### 2.1 Hot ranking 公式選擇

**目標**：surface「最近 + 受歡迎」內容，平衡 recency 跟 popularity。

**Reddit 原版**：
```
hot = log10(max(score, 1)) + (epoch_seconds / 45000)
```
每 12.5 小時 +1 score，每 10x likes +1 score。

**r29c 簡化版**（適合慢節奏 gallery）：
```sql
hot_score = log(max(like_count, 1)) * 5 + julianday(created_at)
```

- SQLite `log()` = log10
- 每 1 day +1 base
- 每 10x likes +5 days boost（log 縮放 + 5x 倍率）

校準範例（today = J）：
| Upload | likes | age | log10(likes) × 5 | + julianday | 排名 |
|---|---|---|---|---|---|
| 法輪 | 5 | 1d ago | 3.5 | J + 2.5 | 1 |
| 古寺 | 0 | today | 0 | J | 2 |
| 九字 | 20 | 9d ago | 6.5 | J − 2.5 | 3 |
| 漢字 | 50 | 19d ago | 8.5 | J − 10.5 | 4 |

「最近受歡迎」直覺：法輪贏古寺（recency + small boost），但 19-day-old 50-likes 仍被 1-day-old 5-likes 壓過 — 平衡得不錯。

### 2.2 為什麼不做 Reddit-exact

Reddit 算的是 score = upvotes - downvotes，且 negative score 用 sign 處理。我們只有 like (positive)，無 dislike → 簡化掉 sign。常數從 45000s（12.5h）拉長到 1 day，符合 gallery 慢節奏。

### 2.3 Search 用 SQLite `LIKE %q%`，不上 FTS5

**選擇**：MVP 用 LIKE，不上 SQLite FTS5（full-text search）。

**理由**：
- LIKE 對 < 10k uploads 規模 query 速度足夠
- FTS5 需 separate virtual table + tokenizer（中文分詞要 ICU / unicode61），工程量大
- 中文 LIKE 是 byte-level match，「曼陀羅」當作 9 bytes 整體 substring 找，行為符合 user 直覺

**Search 範圍**：title + comment + uploader email + uploader display_name 四欄（所有可能識別 upload 的 text 欄位）。

### 2.4 LIKE 特殊字元 escape

User 搜尋「50%」不該 match all rows。`%` 跟 `_` 是 LIKE wildcard，要 escape：

```python
q_escaped = q.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")
# SQL: LIKE ? ESCAPE '\'
```

避免 user 輸入 `_` 變 single-char wildcard 或 `%` 變 match-all。

### 2.5 Frontend 300ms debounce

Search input 每打一個字觸發 fetch 太頻繁（5 字 = 5 個 request）。300ms debounce：user 停打 300ms 才送 → 平衡即時感跟 server load。

300ms 是 search-input 業界標準（Google / GitHub 都用此區間）。

## 3. 實作

### 3.1 Service (`gallery/service.py`)

```python
SORT_HOT = "hot"
ALLOWED_SORTS = (SORT_NEWEST, SORT_LIKES, SORT_HOT)
MAX_SEARCH_QUERY_LEN = 100

def list_uploads(*, ..., sort=SORT_NEWEST, q=None):
    # q escape + LIKE pattern
    if q.strip():
        q_escaped = q.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")
        like_pat = f"%{q_escaped}%"
        WHERE += "(u.title LIKE ? ESCAPE '\\' OR ... 4 columns)"
        params.extend([like_pat] * 4)
    
    # sort=hot ORDER BY
    if sort == SORT_HOT:
        order_by = (
            "ORDER BY ("
            "CASE WHEN COALESCE(like_count, 0) > 0 "
            "  THEN log(like_count) * 5.0 ELSE 0 END "
            "+ julianday(u.created_at)"
            ") DESC, u.id DESC"
        )
```

關鍵 fix：count query 也要 `JOIN users`（因為 search WHERE 用 `usr.email`）。

### 3.2 API

```python
sort: str = Query("newest", pattern="^(newest|likes|hot)$"),
q: Optional[str] = Query(None, max_length=100),
```

FastAPI 自動 422 if `q` 超過 100 字 / `sort` 不是允許值。

### 3.3 Frontend

`gallery.html`：
- sort dropdown 加 `<option value="hot">🔥 熱門</option>`
- `gl-search` 取消 `hidden`

`gallery.js`：
```javascript
state.q = '';

// debounced 300ms
let searchTimer = null;
searchInput.addEventListener('input', (ev) => {
    const q = ev.target.value.trim();
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        if (state.q === q) return;  // 沒變化不打 API
        state.q = q;
        state.page = 1;
        refresh();
    }, 300);
});
```

`_fetchUploads` 把 `state.q` 加進 URL params。

`gallery.css`：search input 樣式（border + focus 狀態）。

## 4. 測試 +12（test_gallery_search_hot.py 全新）

| 範疇 | Test 數 |
|---|---|
| sort=hot | 2（recent+likes 排序公式 + invalid sort） |
| Search | 7（title / comment / display_name / no match / combo / too long / empty=no filter） |
| API | 3（sort=hot HTTP / search HTTP / too long 422） |

295 累計 pass。

## 5. 涉及檔案

```
src/stroke_order/gallery/service.py             (SORT_HOT + q + count JOIN users + ORDER BY hot)
src/stroke_order/web/server.py                   (sort regex 加 hot + q Query param)
src/stroke_order/web/static/gallery.html         (sort 加 hot option + 取消 search hidden)
src/stroke_order/web/static/gallery/gallery.js   (state.q + debounced search handler + fetch q param)
src/stroke_order/web/static/gallery/gallery.css  (#gl-search 樣式)
tests/test_gallery_search_hot.py                  (新建，12 r29c tests)
pyproject.toml                                     (0.14.112 → 0.14.113)
```

## 6. 教訓 / 共通性

- **Search WHERE 用到 JOIN 欄位 → count query 也要 JOIN**：r29c 第一次跑撞到 `no such column: usr.email` — 我加了 `JOIN users` 到主 list query 但忘了 count query 也用同 WHERE，所以 count query 沒 JOIN 就爆。Fix：count + list 都同樣 FROM clause。
- **Hot ranking 直接 inline SQL > 預計算 column**：dynamic computation in ORDER BY 是 SQLite 強項，不需 denormalize 到 column。每 sort=hot query O(N log N) 排序，N < 10k 規模毫秒級。
- **Search MVP 用 LIKE 即可**：FTS5 對中文要 ICU tokenizer + 大量 setup。MVP 階段 < 10k rows 用 LIKE 速度可接受，工程量小一個量級。
- **Debounce 300ms 是業界 sweet spot**：keystroke 觸發 → 太多 request；keystroke 完才觸發 → 慢；300ms 平衡。
- **特殊字元 escape**：User 輸入 `%` `_` 在 LIKE 是 wildcard，必須 escape。沒做的話 user 搜尋 "50%" 會 match all rows（恐怖默默 bug）。

## 7. r28-r29c 系列收尾統計

| Phase | 重點 | Tests | 版本 |
|---|---|---|---|
| r28 | gallery 接 mandala upload | +20 | 0.14.107 |
| r28b | SVG thumbnail | +6 | 0.14.108 |
| r28c | MD thumbnail (loader DI) | +4 | 0.14.109 |
| r28d | state-aware loader factory | +3 | 0.14.110 |
| r29 | like 機制 | +16 | 0.14.111 |
| r29b | bookmark + sort by likes | +17 | 0.14.112 |
| r29c | hot ranking + search | +12 | 0.14.113 |

**Today total: +78 tests (207 → 295), +7 phases, 7 versions, 7 decision logs.**

Gallery 從「PSD-only 純 read 列表」→「**multi-kind upload + thumbnail + like + bookmark + sort (newest/likes/hot) + search + filter 完整社交分享平台**」。

## 8. Defer 留給後續

| 待做 | Phase |
|---|---|
| FTS5 / advanced search (含中文分詞、欄位權重) | r29d 視 user 反饋 |
| Featured / curated picks (admin role) | phase 5c |
| User profile pages (`/gallery/users/{id}`) | r29d |
| Rate-limit search endpoint | 觀察濫用情況再加 |
| Hot ranking 公式 tuning（基於實際 user 反饋）| 上線後 A/B test |
