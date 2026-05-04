# Phase 5b r28–r29k 決策紀錄總覽

**範圍**：兩日內 15 個 phase 的設計決策跨 phase 索引
**索引指向**：`docs/decisions/2026-05-04_*` 跟 `docs/decisions/2026-05-05_*` 各 per-phase 詳細日誌

---

## 1. 跨 phase 主軸決策（5 條策略級）

### S1：「Multi-kind 通用化用 dispatch dict 不用 if/elif」（r28）

```python
VALIDATORS = {KIND_PSD: parse_and_validate_psd,
              KIND_MANDALA: parse_and_validate_mandala}
SUMMARIZERS = {KIND_PSD: summarise_psd,
               KIND_MANDALA: summarise_mandala}
```

加新 kind 改兩個 dict + 寫對應 function，`create_upload` 主邏輯不動。

**詳見**：[r28 decision log](2026-05-04_phase5b_r28_gallery_mandala_upload.md) §3.4

### S2：「Schema dual-write 漸進遷移，舊欄位繼續寫」（r28）

加新通用 `summary_json` 欄位的同時，legacy `trace_count` / `unique_chars` / `styles_used` 繼續寫 — 給後續 phase 慢慢遷移。不 big-bang 切換避免 rollback 困難。

**已存 memory**：`feedback_schema_dual_write_migration.md`

### S3：「並行 fetch 設計集中在 refresh()」（r29d → r29f → r29g）

```javascript
async function refresh() {
  _writeHash();
  const fetches = [fetchMe(), _fetchUploads()];
  if (state.userFilter) fetches.push(_fetchUserProfile(...));
  if (state.deepLinkUploadId && !cached) fetches.push(_fetchUploadDetail(...));
  const results = await Promise.all(fetches);
  // ... render ...
}
```

後續 phase 加新 fetch source 只是 push 進 array — r29f hash deeplink + r29g upload deeplink + 編輯 profile 後 banner re-render 都享受這紅利。

### S4：「Pure helpers 拆 `.mjs` 給 browser + Node 共測」（r29f / r29h / r29j / r29k）

4 個 module 都遵循同 pattern：
- `hash.mjs` — `stateToHash` / `parseHash` (r29f, r29g 擴 upload key)
- `toast.mjs` — `_toastSpec` (r29h)
- `avatar.mjs` — `_initialsSpec` (r29j) + `validateAvatarFile` (r29k)

`.mjs` 強制 ESM，browser + Node 同份原始檔不重複實作。

### S5：「URL = 公開介面，state 進 URL 前先問『分享出去 OK 嗎』」（r29f → r29k 沿用）

| State | 進 hash？ | 理由 |
|---|---|---|
| `userFilter` | ✅ | profile 連結要分享 |
| `sort` (非 newest) | ✅ | 改變看到的內容 |
| `q` | ✅ | search 結果要分享 |
| `kindFilter` | ✅ | filter 過的 view |
| `deepLinkUploadId` | ✅ | 單張作品分享 (r29g) |
| `bookmarkedOnly` | ❌ | 私人 view，不該分享 |
| `page` | ❌ | ephemeral，分享連結帶 page=3 體驗差 |

---

## 2. Tactical 決策（per phase 索引）

| Phase | 關鍵決策 | 文件 |
|---|---|---|
| r28 | dispatch dict + summary_json 通用化 + per-kind validators | [r28 log](2026-05-04_phase5b_r28_gallery_mandala_upload.md) |
| r28b | cairosvg 直接 SVG→PNG，存 `<nonce>.thumb.png` | [r28b log](2026-05-04_phase5b_r28b_svg_thumbnail.md) |
| r28c | char loader DI 方便測 + render 一致性 | [r28c log](2026-05-04_phase5b_r28c_md_thumbnail_char_loader_di.md) |
| r28d | state-aware loader factory（依 state.style 動態構造） | [r28d log](2026-05-04_phase5b_r28d_state_aware_loader_factory.md) |
| r29 | likes table (user_id, upload_id) PK + ON DELETE CASCADE + EXISTS subquery | [r29 log](2026-05-04_phase5b_r29_gallery_likes.md) |
| r29b | bookmarks table mirror likes 結構；sort=likes 切 ORDER BY | [r29b log](2026-05-04_phase5b_r29b_bookmark_sort.md) |
| r29c | hot ranking `log(likes) * 5 + julianday(created_at)` + LIKE search ESCAPE 防 wildcards | [r29c log](2026-05-04_phase5b_r29c_hot_search.md) |
| r29d | user profile + user_id filter + banner / list 拆兩 endpoint（fetch frequency 不同） | [r29d log](2026-05-04_phase5b_r29d_user_profile.md) |
| r29e | top_uploads 同 endpoint forward（fetch frequency 一致 → 併） | [r29e log](2026-05-04_phase5b_r29e_profile_top_uploads.md) |
| r29f | URLSearchParams hash + `_writingHash` flag + `setTimeout(0)` reset | [r29f log](2026-05-05_phase5b_r29f_url_hash_route.md) |
| r29g | hash schema 加 1 key + prepend list[0] + `requestAnimationFrame` scrollIntoView | [r29g log](2026-05-05_phase5b_r29g_upload_deep_link.md) |
| r29h | reusable toast utility + 取代 4 處 alert + textContent over innerHTML | [r29h log](2026-05-05_phase5b_r29h_toast_component.md) |
| r29i | reconnaissance 修正 phase 5c scope + banner ✏️ 快捷 | [r29i log](2026-05-05_phase5b_r29i_profile_edit_shortcut.md) |
| r29j | DB 存 nonce 非 path + Pillow verify+重 open + initials hash palette | [r29j log](2026-05-05_phase5b_r29j_avatar.md) |
| r29k | mirror server validation + multi-source `_handleSelectedFile` shared path | [r29k log](2026-05-05_phase5b_r29k_avatar_drag_drop.md) |

---

## 3. 決策反向：放棄 / 推回的選項

幾條重要的「不做」決策也值得記錄：

### 「不開 modal lightbox 給 deep-link upload」（r29g 評估後 push back）

評估 detail modal 跟 card-expand 後選 card-expand：modal 要 focus trap + scroll lock + back-button 同步，跟 card 90% 重複 — over-engineering。

### 「不做 phase 5c 重做」（r29i reconnaissance 後）

開動前 grep 發現 9/9 元件已 ship，phase 5c scope 縮成 r29i 的 banner 快捷。

### 「不做 toast queue」（r29h MVP 砍）

實作 queue 增加 ~30% 複雜度，連續 5 個 error 一起跳出反而焦慮。MVP 同時最多 1 個。

### 「不做 client-side preview before upload」（r29k 評估後）

current immediate-upload 體驗 OK — 上傳完才 preview server 結果反而是 source of truth。User 不喜歡 re-upload 即可。Preview-before-upload 增加 state 複雜度（selectedFile vs uploadedAvatar）。

### 「不做 r29 的 hot ranking 純 Reddit 公式」（r29c 簡化）

Reddit 原版 score = upvotes - downvotes，gallery 沒 dislike → 簡化掉 sign。常數從 45000s 拉到 1 day 配合慢節奏。**不要為了相容 reference 設計而過度抽象**。

---

## 4. 跨 phase 一致性表

| 主題 | 一致實踐 | 起始 phase |
|---|---|---|
| Decision log 格式 | `2026-MM-DD_phase5b_<phase>_<topic>.md` 8 章節結構 | （pre-existing） |
| Test smoke 範圍 | gallery + mandala + web 統一 set | r28 |
| Version bump cadence | 每 phase +1 patch（patch = pure ship） | （pre-existing） |
| ALTER TABLE migration | `_migrate_<table>_<feature>` idempotent helper + PRAGMA check | r28 |
| Frontend `.mjs` pure helper | 抽 export + Node `node:test` cover | r29f |
| Cross-cutting derivation | 集中 helper（如 `_user_dict_with_avatar`） | r29j |
| Multi-trigger entry | shared execution path（如 `_handleSelectedFile`） | r29k |
| CSS visual feedback | 多重 cue（outline + scale + label） | r29g（首例）/ r29k |

---

## 5. 後續 defer 累積

各 phase 列的 defer 集中於此（**強烈推薦明天再開**）：

### High-value（user 真有需求才推進）
- **Phase 6**：Follow / 跟隨 user → 個人化 feed（social loop）
- **Phase 5c 真版本**：admin role + featured / curated picks
- **Comment / 留言**：per-upload discussion thread

### Polish（dim returns）
- Avatar client-side preview before upload (FileReader → ObjectURL)
- 上傳 progress bar（256x256 PNG ~50KB，不需要）
- Avatar crop / rotate UI
- Profile 編輯 dialog 字數計數 (real-time)
- Toast queue（多 toast 排隊）/ undo button
- `pushState` 取代 hash route（pretty URL `/users/42`）

### Tooling / 觀察
- Hot ranking 公式 tuning（基於實際 user 反饋 A/B）
- FTS5 + 中文分詞 advanced search
- Rate-limit search endpoint
- Avatar WebP（更小檔，但 IE / 老 Safari 不支援）

---

## 6. 引用其他文件

- 工作日誌：[`docs/journal/2026-05-04_05_session_log_r28-r29k.md`](../journal/2026-05-04_05_session_log_r28-r29k.md)
- 共通性原則：[`docs/PRINCIPLES.md`](../PRINCIPLES.md)
- 各 phase 詳細日誌：`docs/decisions/2026-05-0[45]_phase5b_r29*.md`（15 個）
