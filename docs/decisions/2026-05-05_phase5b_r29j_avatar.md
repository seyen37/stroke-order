# Phase 5b r29j：User Avatar（頭像上傳 + initials fallback）

**日期**：2026-05-05
**版本**：0.14.119 → 0.14.120
**範圍**：user 頭像 — 上傳 / Pillow resize / cache-bust nonce / banner+card+dropdown 三處顯示 / initials fallback
**測試**：Python +13（test_gallery_avatar.py 全新）+ Node +8（test_avatar_initials.mjs）→ Python 320 / Node 46

---

## 1. 動機

r29i 的 reconnaissance 發現 phase 5c 「profile 編輯」九成已 ship，唯一還沒做的就是 avatar — profile banner 仍是純 emoji 👤，cards 上 author 也只是字。avatar 是「**讓 user 變成有臉的人**」最直接的視覺投資，r29j 補完。

不上 avatar 等於 profile 永遠半成品。今日連跑 13 phases，最後一塊應該是它。

## 2. 設計核心

### 2.1 儲存策略：file 在 disk，DB 存 cache-bust nonce

**Disk**：`gallery_dir/avatars/<user_id>.png`（固定路徑覆寫）
**DB `users.avatar_path`**：8-char hex nonce（NULL = 無 avatar）

**為什麼分離**：file 路徑可預測（user_id），DB 欄位專責**版本標識**。`avatar_url = /api/gallery/users/{id}/avatar?v=<nonce>` — 換頭像 → nonce 換 → URL 換 → 瀏覽器強制重 fetch。同時 server 可設 `Cache-Control: max-age=86400, immutable`（URL 變了等於新檔，舊 URL 永遠舊內容）。

**避開**：
- 路徑含 nonce（`avatars/<id>_<nonce>.png`）→ 換頭像要刪舊檔 + 寫新檔，filesystem 操作複雜化
- 純 timestamp → 同秒兩次更新會 collision
- ETag/Last-Modified → revalidate 仍打 server 一回合，nonce 直接換 URL 0 round-trip

### 2.2 上傳格式：PNG / JPEG，server resize 到 256×256 PNG

**接受 input**：PNG / JPEG，max 2MB raw
**輸出 disk**：256×256 PNG（統一格式，optimize=True 壓縮）

**Pillow pipeline**：
1. `Image.open(...).verify()` — 確認合法 image（防 evil bytes）
2. 重 open（verify 消耗 stream，不 reusable）
3. `RGBA` 帶 alpha → composite onto white background → RGB（avoid 黑底）
4. Square crop center — 取短邊正方形
5. `resize(256, 256, LANCZOS)` — 高品質縮放
6. `save(target, format="PNG", optimize=True)`

**256×256 為什麼這個 size**：
- Banner 最大顯示 64×64 → 4x retina 仍有餘
- Card 24×24 / dropdown 24×24 → 縮太多反而模糊
- 256×256 PNG ~30-80KB optimized → server 帶寬 acceptable

### 2.3 Initials fallback — palette 8 色，stable hash by user_id

**沒 avatar 時** frontend render circular div with：
- 1 字 initial（display_name 第一字 / email handle 第一字 / `?`）
- 背景色 from 8-color palette，by `hash(user_id) % 8`

**為什麼 stable hash**：同 user 永遠同色（user 認得「Alice 是綠色」），但不同 user 通常異色（distribution 散）。簡單 FNV-ish hash 就夠：

```javascript
let h = 0;
for (let i = 0; i < seed.length; i++) {
  h = (h * 31 + seed.charCodeAt(i)) | 0;
}
const color = PALETTE[Math.abs(h) % PALETTE.length];
```

**Palette 選色考量**：8 色覆蓋暖冷光譜，全部達 4.5+ 對比度（白字 on 任一色都讀得到）— 無障礙基本盤。

避免「所有 user 都灰色」（generic icon）— 跟 Gmail / GitHub / Slack 同手法。

### 2.4 三處顯示尺寸統一 helper

| 位置 | size | 用途 |
|---|---|---|
| Profile banner | 64×64 | 主 visual identity |
| Card author link | 24×24 | inline 名字旁 |
| User dropdown header | 24×24 | 同 card |
| Profile dialog preview | 80×80 | 編輯時預覽 |

`avatarHtml(user, size)` 單一 helper，size 影響 width/height/font-size（initials 字級 = 0.45 × size）。**通用 helper > inline render** 是 r29j 跨 4 處整合的關鍵。

### 2.5 Cache-bust 透過 URL nonce

**Frontend 拿到 user.avatar_url** = `"/api/gallery/users/42/avatar?v=a3f7c12b"`
**直接放 `<img src="...">`**

換頭像 → POST 後 user.avatar_url 變 `?v=<新 nonce>` → frontend 重 render → `<img>` 新 URL → 瀏覽器新 fetch。

**Server 端 GET endpoint** 設 `Cache-Control: public, max-age=86400, immutable` — URL 換新就等於新檔，舊 URL 永遠 cached 舊版本（`immutable` 表示 client 不該 revalidate）。

### 2.6 防 XSS：avatar_url 不直接拼，frontend 用 textContent / `_escape`

`avatar.mjs` `avatarHtml` 內部用 `_escape(user.avatar_url)` 處理 attribute，雖然 server 端 nonce 是 `secrets.token_hex(8)` 安全字串，但攻擊路徑可能來自 future schema bug — defense in depth。

display_name 在 alt / aria-label 也走 `_escape`。

### 2.7 後端 Pillow verify + 重 open

```python
Image.open(io.BytesIO(file_bytes)).verify()  # 檢查合法
img = Image.open(io.BytesIO(file_bytes))      # 重 open 才能 decode
```

**為什麼兩次 open**：Pillow 的 `verify()` 是 single-pass 檢查，會消耗 stream — 之後 `img.size` / `.convert()` 等操作會炸。**通用模式**：先 verify 防 evil image bombs，再重新 open 處理。

### 2.8 ALTER TABLE migration（pre-r29j DB 升版）

```python
def _migrate_users_avatar(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    if "avatar_path" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_path TEXT")
```

新建 DB 透過 SCHEMA 已含；existing DB 自動補。SQLite ALTER TABLE 不支援 IF NOT EXISTS，故先 PRAGMA 查。同 r28 / r29 既有 migration pattern。

### 2.9 `_user_dict_with_avatar` helper 集中 avatar_url 派生

```python
def _user_dict_with_avatar(row) -> dict:
    d = dict(row)
    nonce = d.get("avatar_path")
    if nonce:
        d["avatar_url"] = f"/api/gallery/users/{d['id']}/avatar?v={nonce}"
    else:
        d["avatar_url"] = None
    d.pop("avatar_path", None)  # 不外洩 internal nonce
    return d
```

3 處用到：`get_session_user`（auth.py）/ `get_user_profile`（service.py）/ `update_profile` / `update_avatar` / `clear_avatar`。**避免 4-5 個 SELECT query 各自 derive URL** = bug 漏改點。

### 2.10 `_row_to_dict` 給 list_uploads / get_upload 自動帶 uploader_avatar_url

```python
nonce = d.pop("uploader_avatar_path", None)
uploader_id = d.get("user_id")
if nonce and uploader_id is not None:
    d["uploader_avatar_url"] = f"/api/gallery/users/{uploader_id}/avatar?v={nonce}"
else:
    d["uploader_avatar_url"] = None
```

每 list_uploads row 自動帶。`uploader_avatar_path` SELECT 出來但 pop 掉不外洩。

## 3. 實作

### 3.1 Files changed (8)

| 檔 | 變更摘要 |
|---|---|
| `gallery/db.py` | SCHEMA users 加 avatar_path TEXT；migration helper；avatars/ subdirectory creation |
| `gallery/config.py` | `avatars_dir()` helper |
| `gallery/service.py` | `update_avatar` / `clear_avatar` / `_avatar_path_on_disk` / `_user_dict_with_avatar`；update SELECT in get_user_profile / update_profile / list_uploads / get_upload；`_row_to_dict` derive uploader_avatar_url |
| `gallery/auth.py` | `get_session_user` SELECT include avatar_path → return via `_user_dict_with_avatar` |
| `web/server.py` | POST /me/avatar / DELETE /me/avatar / GET /users/{id}/avatar |
| `web/static/gallery/avatar.mjs` | 新 — avatarHtml + _initialsSpec |
| `web/static/gallery/auth.js` | profile dialog avatar 上傳 / 移除 handlers |
| `web/static/gallery/gallery.js` | header / card / banner 整合 avatarHtml |
| `web/static/gallery/gallery.css` | `.gl-avatar` 系 + .gl-profile-avatar-row + 各位置 layout |
| `web/static/gallery.html` | profile dialog 加 avatar upload row |
| `tests/test_gallery_avatar.py` | 新 — 13 tests |
| `tests/test_avatar_initials.mjs` | 新 — 8 Node tests |

### 3.2 Routes added

```
POST   /api/gallery/me/avatar          - upload (multipart, 2MB max)
DELETE /api/gallery/me/avatar          - remove
GET    /api/gallery/users/{id}/avatar  - serve PNG (404 if no avatar)
```

## 4. 測試

### 4.1 Python `test_gallery_avatar.py` — 13 tests

| 範疇 | 測 | 數 |
|---|---|---|
| Auth | 401 anon, 200 logged-in | 1 |
| Format | PNG OK / JPEG OK / 非 image 422 / 非 image bytes 422 / 太大 422 | 5 |
| Serve | GET PNG content / 404 no upload | 2 |
| Delete | clear url / idempotent | 2 |
| Plumbing | /me 帶 avatar_url / profile 帶 avatar_url / nonce 變動 | 3 |

### 4.2 Node `test_avatar_initials.mjs` — 8 tests

display_name 取首字 / 中文 / 英文大寫 / 空 fallback / `?`、stable hash by id、distribution（≥4 色 from 50 ids）、palette 限定、surrogate pair 安全切。

### 4.3 Full smoke

- Node 46 (29 hash + 9 toast + 8 avatar)
- Python 320 (307 + 13 avatar)
- 全 pass

## 5. 教訓 / 共通性

- **DB 存 nonce 比存 file path 純粹**：`avatar_path` column 名是歷史，但內容是 nonce token，不是真路徑。檔案路徑可由 user_id 算出 → DB 不該重複存。**通用原則**：可 derive 的資訊不該 store；DB column 該存「unique fact」（這裡是「版本標識」）。
- **Cache-bust 用 URL nonce 比 ETag 簡單一級**：immutable URL + 版本變更時換 URL = client 0 round-trip。ETag/Last-Modified 仍要 conditional GET。**通用原則**：可變資源用 versioned URL。
- **Pillow verify + 重 open 是 image upload security pattern**：`verify()` 檢查合法 image structure，但消耗 stream → 重新 open。沒做的話 PIL bombs / malformed image 可能炸 server。
- **Initials fallback 比 generic icon 友善 + 更便宜**：8 色 palette + hash → 永遠有「visual identity」，不需後端生 default avatar。**通用原則**：empty state 該創造價值，不該只是 placeholder。
- **單一 helper 跨 4 處 = consistency 紅利**：`avatarHtml(user, size)` 統一所有 avatar render，size scaling 規則統一。Inline render 4 處 = 4 個 drift 風險。
- **Pure logic 抽 `_initialsSpec` 給 Node test**：跟 r29f hash.mjs / r29h toast.mjs 同 pattern — DOM-coupled module 中的 pure logic 抽出來測。
- **`_user_dict_with_avatar` 集中派生**：5 個 SELECT path 全走同一 helper，避免每個 query 各自 derive avatar_url 的多點 bug 風險。**通用原則**：cross-cutting derivation 集中到一個 helper。
- **migration helper idempotent + per-table 命名**：`_migrate_users_avatar` 跟 r28 `_migrate_uploads_kind_columns` 同 pattern。**通用原則**：migration helper 一個 table 一個函式，方便獨立測 + 後續 phase 加新欄位不互相 step on。
- **`Cache-Control: immutable`** 是 modern browser optimization：告知 client URL 內容絕不變，免任何 revalidate request。配合 versioned URL 使用。

## 6. 涉及檔案

```
src/stroke_order/gallery/db.py                    (SCHEMA + migration + avatars/ dir)
src/stroke_order/gallery/config.py                (avatars_dir helper)
src/stroke_order/gallery/service.py               (avatar service functions + 5 SELECT path 加 avatar_path)
src/stroke_order/gallery/auth.py                  (get_session_user 帶 avatar_url)
src/stroke_order/web/server.py                    (3 endpoints)
src/stroke_order/web/static/gallery/avatar.mjs    (新 — avatarHtml + _initialsSpec)
src/stroke_order/web/static/gallery/auth.js       (profile dialog avatar upload/clear handlers)
src/stroke_order/web/static/gallery/gallery.js    (banner / card / header 整合 avatarHtml)
src/stroke_order/web/static/gallery/gallery.css   (.gl-avatar 系 + 各位置 layout)
src/stroke_order/web/static/gallery.html          (profile dialog avatar row)
tests/test_gallery_avatar.py                       (新 — 13 tests)
tests/test_avatar_initials.mjs                     (新 — 8 Node tests)
docs/decisions/2026-05-05_phase5b_r29j_avatar.md
pyproject.toml                                     (0.14.119 → 0.14.120)
```

## 7. r28-r29j 系列累計統計

| Phase | 重點 | Tests | 版本 |
|---|---|---|---|
| r28-r29i（前 13 phase） | 略 | Python +85 / Node +38 | ... → 0.14.119 |
| **r29j** | **avatar 上傳 + initials fallback** | **Py +13 / Node +8** | **0.14.120** |

**Two-day total: Python 320 + Node 46 = 366 tests, +14 phases, 14 versions, 14 decision logs.**

Profile 完整性閉環：bio + display_name 編輯（pre-existing）+ banner ✏️ 快捷（r29i）+ avatar 上傳（r29j）+ 跨 view 顯示（banner / card / dropdown）+ initials fallback。User 終於有臉了 🎉

## 8. Defer 留給後續

| 待做 | Phase |
|---|---|
| Avatar 編輯時 client-side preview 在 dialog 內（讀 file 直接 render base64） | nice-to-have |
| 拖放上傳 (drag-drop) | 視 user 反饋 |
| WebP 儲存（更小檔，但 IE/老 Safari 不支援）| 視瀏覽器支援度 |
| Initials fallback 換 SVG 線條（更美但複雜）| 不做 |
| Featured / curated picks（admin role） | phase 5c 真版本 |
| Follow / 跟隨 user → 個人化 feed | phase 6 |
