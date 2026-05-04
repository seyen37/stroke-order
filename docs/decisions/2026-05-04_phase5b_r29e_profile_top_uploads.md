# Phase 5b r29e：Profile Top Uploads（最受歡迎前 N 件）

**日期**：2026-05-04
**版本**：0.14.114 → 0.14.115
**範圍**：r29d 後續 — profile banner 內嵌「🏆 最受歡迎 top 3」thumbnail strip
**測試**：`tests/test_gallery_profile.py` +5 r29e → 307 累計 pass

---

## 1. 動機

r29d profile banner 已顯示 user 累積 like 數，但「Alice **哪幾張**最受歡迎」要 user 自己切 sort=likes 才能看到 — 兩步動作 + 視野要從 banner 跳到 list。

r29e 把這資訊直接做進 profile：進 profile 即看到 top 3 thumbnail，每張帶 🥇🥈🥉 + like 數，click 即 scroll 到該 card 高亮。社群「**作者代表作**」秒識別。

## 2. 設計核心

### 2.1 Top N 嵌進 banner，不開新 section

**選擇**：banner 內嵌 horizontal strip（label 「🏆 最受歡迎」+ 3 個 60×60 thumbnail）。

**理由**：
- Banner 已是 user-focused 區塊，跟 user info / stats 同視覺單元自然
- 獨立 section 視覺破碎；hero 模式（替代 list）壓垮主 list 又脫離 user 期待
- Strip 高度 ~70px，banner 整體只長一點

### 2.2 同 endpoint 一次 fetch（不拆）

**選擇**：`get_user_profile` 加 `top_uploads` key，**不開新** `/users/{id}/top-uploads` endpoint。

**理由**：banner / top_uploads **fetch frequency 一致** — user 切 profile filter 時兩者都需要重抓，平時 (翻頁 / sort / search) 都不變動。一次 fetch 比兩次省 round-trip。

跟 r29d「banner / list 拆兩 endpoint」原則不衝突 — list 隨 page/sort/q 動所以拆，top_uploads 不動所以併。**「fetch frequency 一致 → 同 endpoint，不一致 → 拆」是通用 API 設計訊號。**

### 2.3 排序：like_count DESC, created_at DESC, id DESC

**理由**：「最受歡迎」最直覺 = 純 like 數比；同分時新作品優先（鼓勵活躍作者）；最後 id 防 deterministic tie。

**避開** hot ranking 公式（log + julianday recency）— 那會混進「最近」語意，跟「全時段最受歡迎」對不上。

### 2.4 N = 3（top 3 直覺）

🥇🥈🥉 = top tier 全球認知。3 個 thumbnail strip 高度 + 寬度都可控。動態 N（≥10 上 5 個）會把畫面複雜度提一級，CSS responsive 麻煩，捨棄。

### 2.5 精簡 4 欄：id, title, kind, like_count

**Banner strip 顯示需求**：
- thumbnail（從 id 拼 `/api/gallery/uploads/{id}/thumbnail`）
- title（hover tooltip）
- like_count（角落 badge）
- kind（決定要不要 render `<img>` — psd 沒 thumbnail 改顯文字 placeholder）

不帶 created_at / comment / file_size — 沒人在 60×60 縮圖看。最小帶寬。

### 2.6 0-state = 空陣列

新註冊 user `top_uploads = []`，frontend `_renderProfileTopStrip` 看到 empty 直接 return `''` — banner 不 render strip。比塞「尚無作品」placeholder 乾淨（banner 仍顯 0 stats，已表達清楚）。

### 2.7 PSD 沒 thumbnail → 文字 placeholder（前 2 字）

```javascript
const thumbHtml = (kind === 'mandala')
  ? `<img src="/api/gallery/uploads/${it.id}/thumbnail" ...>`
  : `<span class="gl-profile-top-noimg">${title.slice(0, 2)}</span>`;
```

PSD 在 r28b 設計就 skip thumbnail（return False），URL 會 404。直接從 kind 分支避開無效 request + onerror flash。文字 fallback 顯前 2 字（中文足以辨識）。

### 2.8 Click → scroll-to-card + 2 秒高亮

**選擇**：thumbnail click 不 navigate，而是 `card.scrollIntoView({block:'center'})` + 加 `.gl-card--highlight` class 2 秒（CSS 黃底動畫 + accent outline）。

**理由**：
- Gallery 本身是 grid SPA，沒 detail page → click navigate 沒去處
- 「在 list 裡找 highlight 那張」= 最接近「展示這件代表作」語意
- Profile filter view 那 user 全 uploads 都在 list 裡，scroll 一定 hit

避開：lightbox 彈窗（多寫一個 modal 元件 + ESC handler），動畫 4 秒（太慢 / 干擾下一動作）。

## 3. 實作

### 3.1 Service (`gallery/service.py`)

```python
PROFILE_TOP_UPLOADS_LIMIT = 3

def get_user_profile(user_id: int) -> dict:
    # ... 既有 user / stats query ...
    top_rows = conn.execute(
        "SELECT u.id, u.title, u.kind, "
        "  (SELECT count(*) FROM likes l WHERE l.upload_id = u.id) "
        "    AS like_count "
        "FROM uploads u "
        "WHERE u.user_id = ? AND u.hidden = 0 "
        "ORDER BY like_count DESC, u.created_at DESC, u.id DESC "
        "LIMIT ?",
        (user_id, PROFILE_TOP_UPLOADS_LIMIT),
    ).fetchall()
    return {
        "user": {...},
        "stats": {...},
        "top_uploads": [
            {"id": int(r["id"]), "title": r["title"],
             "kind": r["kind"], "like_count": int(r["like_count"] or 0)}
            for r in top_rows
        ],
    }
```

關鍵：`WHERE u.hidden = 0` 排除隱藏作品（即使 like 多也不該秀），`LIMIT ?` 讓常數從常量集中改可不動 query string。

### 3.2 API（無變動）

`GET /api/gallery/users/{id}` return shape 自動包含 `top_uploads`（service 已包，FastAPI 直接 forward dict）。

### 3.3 Frontend (`gallery/gallery.js`)

新 helper `_renderProfileTopStrip(top)`：
- 空陣列 → return `''`
- 每筆 render `<a>` thumbnail with 🥇/🥈/🥉 + like badge

整合到 `renderProfileBanner`：strip 嵌在 `.gl-profile-info` 底，跟 stats 同一視覺塊。

Click handler：

```javascript
banner.querySelectorAll('[data-action="goto-upload"]').forEach(link => {
    link.addEventListener('click', (ev) => {
      ev.preventDefault();
      const uid = Number(link.dataset.uploadId);
      const card = document.querySelector(`.gl-card[data-id="${uid}"]`);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('gl-card--highlight');
        setTimeout(() => card.classList.remove('gl-card--highlight'), 2000);
      }
    });
});
```

不重 fetch，不切 state — 純 DOM 跳轉。

### 3.4 CSS

```css
.gl-profile-top-thumb {
  position: relative;
  width: 60px; height: 60px;
  border: 1px solid var(--gl-line, #ddd);
  border-radius: 4px;
  overflow: hidden;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}
.gl-profile-top-thumb:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
}
.gl-profile-top-medal { /* top-left 角 */ ... }
.gl-profile-top-likes { /* bottom-right 角 */ ... }

@keyframes gl-card-flash {
  0%   { background-color: #fff8c4; }
  100% { background-color: transparent; }
}
```

## 4. 測試 +5（test_gallery_profile.py 追加）

| Test | 驗證 |
|---|---|
| `test_top_uploads_returns_top_3_by_likes` | 4 件 uploads 取 top 3，order 跟 4-key shape 都檢 |
| `test_top_uploads_tie_break_created_at_then_id` | 同 0 likes 走 created_at DESC tie-break |
| `test_top_uploads_empty_for_zero_uploads` | 新 user → `[]` |
| `test_top_uploads_excludes_hidden` | hidden=1 即使 20 likes 也不進 top |
| `test_api_profile_includes_top_uploads` | API endpoint return 含 top_uploads + 完整 4 欄 |

307 累計 pass（302 → 307）。

## 5. 涉及檔案

```
src/stroke_order/gallery/service.py              (PROFILE_TOP_UPLOADS_LIMIT + top_uploads query)
src/stroke_order/web/static/gallery/gallery.js   (_renderProfileTopStrip + scroll-to-card click)
src/stroke_order/web/static/gallery/gallery.css  (.gl-profile-top* 系 + .gl-card--highlight)
tests/test_gallery_profile.py                     (+5 r29e tests)
pyproject.toml                                    (0.14.114 → 0.14.115)
```

API endpoint 無變動（service forward）。

## 6. 教訓 / 共通性

- **「Fetch frequency 一致 → 同 endpoint」是 API 設計訊號**：跟 r29d「fetch frequency 不一致 → 拆 endpoint」是同一條規則的兩面。Profile / top_uploads 都隨 user 切換而變、其他時候不動 → 同 endpoint 省 round-trip。Profile / list 一個隨 page 動一個不 → 拆 endpoint 省重抓。
- **「最受歡迎」≠「Hot」**：兩者語意不同。Hot 含 recency boost（log likes + julianday），全時段「最受歡迎」純 like 排序。Profile top 是後者，主 list 的 sort=hot 才是前者。**同字面下挖意圖差異** = 設計決定點。
- **Click → scroll-to-card 比 lightbox 簡單一級**：SPA 沒 detail page 時，「展示這個」最自然語意是「在現有 list 裡 highlight」而非「彈窗」。少寫一整個 modal 元件 + ESC / outside-click handler。
- **PSD 缺 thumbnail 的 fallback 用 kind 分支，不靠 onerror**：onerror 雖能隱藏壞圖，但仍打了 1 個 404 request（network tab 噪音）。從 kind 早判分支直接 render 文字 placeholder，零 wasted request。
- **動畫高亮用 outline + animation 雙保險**：`animation` flash 完後背景回原色，但 `outline` 留到 class 移除瞬間消失。雙重視覺強化「就是這張」訊號。
- **常數 `PROFILE_TOP_UPLOADS_LIMIT = 3` 集中**：未來想換 5 / 10 改一處。`LIMIT ?` 而非 `LIMIT 3` 寫在 SQL 字串裡 → 常量跟 query 解耦。

## 7. r28-r29e 系列累計統計

| Phase | 重點 | Tests | 版本 |
|---|---|---|---|
| r28 | gallery 接 mandala upload | +20 | 0.14.107 |
| r28b | SVG thumbnail | +6 | 0.14.108 |
| r28c | MD thumbnail (loader DI) | +4 | 0.14.109 |
| r28d | state-aware loader factory | +3 | 0.14.110 |
| r29 | like 機制 | +16 | 0.14.111 |
| r29b | bookmark + sort by likes | +17 | 0.14.112 |
| r29c | hot ranking + search | +12 | 0.14.113 |
| r29d | user profile + user_id filter | +7 | 0.14.114 |
| **r29e** | **profile top uploads strip** | **+5** | **0.14.115** |

**Today total: +90 tests (207 → 307), +9 phases, 9 versions, 9 decision logs.**

Profile 從「user info + stats」進化成「**user info + stats + 代表作 showcase**」 — 進別人 profile 一眼識別「這個人擅長畫什麼」。社群信任建立的最後關鍵組件。

## 8. Defer 留給後續

| 待做 | Phase |
|---|---|
| URL hash route（`#user=42` deep-link） | phase 5c |
| Profile 編輯 UI（user 改 bio / display_name） | phase 5c |
| Profile avatar 頭像上傳 | phase 5c+ |
| Top uploads 改 N=5 + 切換 tab（最受歡迎 / 最新 / 最多 bookmark） | r29f 視 user 反饋 |
| Featured / curated picks（admin role） | phase 5c |
| Follow / 跟隨 user → 個人化 feed | phase 6 |
| FTS5 + 中文分詞 advanced search | 待 user 反饋驅動 |
