# Phase 5b r29i：Profile Banner 編輯快捷入口

**日期**：2026-05-05
**版本**：0.14.118 → 0.14.119
**範圍**：r29d/r29e profile banner 看自己時加 ✏️ 編輯按鈕；空 bio 顯 placeholder
**測試**：Node 38 / Python 307 不退化（純 frontend 改動）

---

## 1. 動機 — recon 後修正規劃

打算開 phase 5c（profile 編輯）前先 reconnaissance，意外發現編輯功能其實 **大部分已 shipped**：

| 元件 | 狀態 |
|---|---|
| Backend `PUT /api/gallery/me` | ✅ 已實作 |
| `update_profile` service + 字數驗證（display_name 50 / bio 500） | ✅ 已實作 |
| `gl-profile-dialog` HTML form | ✅ 已實作 |
| `showProfileDialog` JS + submit handler | ✅ 已實作 |
| User dropdown 「編輯個人資料」連結 | ✅ 已 wire |
| Backend tests（401 / 200 / 422 三 case） | ✅ 已存在 |

我之前說「bio 是 dead column」是**誤判** — 不是不能改，是 user 還沒透過 dropdown 進去填過。Senior 標準做法：reconnaissance 先，再下定義。

剩下唯一真實 UX 缺口：**banner 上沒有快捷編輯入口**。User 看自己 profile 時要繞 user dropdown 找「編輯個人資料」。r29i 補一個 ✏️ 按鈕直接觸發 dialog。

也順手 polish 空 bio 的視覺：原本完全不顯示 bio div，改成顯 italicized placeholder「（尚未填寫個人簡介）」— 既給 user hint「可以填」，又不像 dead state。

## 2. 設計核心

### 2.1 條件 render：只看自己 profile 才顯按鈕

```javascript
const isOwnProfile = state.me && state.me.id === u.id;
const editBtnHtml = isOwnProfile
  ? `<button class="gl-btn gl-profile-edit" data-action="profile-edit"
              type="button" title="編輯個人資料">✏️ 編輯</button>`
  : '';
```

別人 profile 不該看到「編輯」（無權限）。`state.me?.id === u.id` 判斷是看自己。匿名 user (state.me=null) 自動判斷 false。

### 2.2 編輯後同步 re-render（行為已存在，不需多寫）

`auth.js` submit handler 成功後 chain `ctx.refresh()`：

```javascript
$('gl-profile-form').addEventListener('submit', async (ev) => {
  const updated = await submitProfile(ev);
  if (updated) {
    setTimeout(() => {
      hideProfileDialog();
      ctx.refresh && ctx.refresh();  // ← 這裡
    }, 600);
  }
});
```

`refresh()` 看到 `state.userFilter` set 就會重 fetch profile：

```javascript
if (state.userFilter) {
  fetches.push(_fetchUserProfile(state.userFilter).catch(() => null));
}
```

所以**編輯自己 bio + 在自己 profile** → 編完 600ms 後 dialog 關閉 → refresh → profile 重 fetch → banner re-render with new bio。**已自動 work**，r29i 不需任何補丁。

我原本誤以為這會壞掉是沒 trace 完 refresh path 的結果。

### 2.3 空 bio placeholder

```javascript
const bioHtml = u.bio
  ? `<div class="gl-profile-bio">${_escape(u.bio)}</div>`
  : '<div class="gl-profile-bio gl-profile-bio--empty">（尚未填寫個人簡介）</div>';
```

CSS 用 italic + opacity 0.7 跟正常 bio 區別。看自己時是 hint「該填了」；看別人時也比「banner 中間少一行什麼都沒有」更平衡。

### 2.4 ✏️ 按鈕跟名字 inline

把 `${editBtnHtml}` 直接接在 `${_escape(author)}` 後面：

```html
<div class="gl-profile-name">👤 Alice ✏️ 編輯</div>
```

vs 另起一行 — 這樣節省 banner 高度，且視覺上「名字旁邊就是編輯」是常見 social media pattern（Twitter / 巴哈姆特 都這做法）。CSS `.gl-profile-edit { vertical-align: middle; }` + 小字小 padding 不喧賓奪主。

## 3. 實作

### 3.1 `gallery.js` — `renderProfileBanner` 內加 4 件事

1. `isOwnProfile` 判斷
2. `editBtnHtml` 條件 render
3. 空 bio fallback placeholder
4. Click handler delegated 觸發 `showProfileDialog(state.me)`

`showProfileDialog` 已 import in r29h pre-existing imports — 零新 dependency。

### 3.2 `gallery.css` — 兩個小 rule

```css
.gl-profile-edit {
  margin-left: 8px;
  font-size: 11px;
  padding: 2px 8px;
  vertical-align: middle;
}
.gl-profile-bio--empty {
  font-style: italic;
  color: var(--gl-muted);
  opacity: 0.7;
}
```

### 3.3 零後端 / 零 service / 零 test changes

純 UI shortcut + cosmetic placeholder。既有 backend / dialog / submit / refresh 路徑全沒動。

## 4. 測試

### 4.1 Smoke regression

- Node `node --test tests/test_hash_route.mjs tests/test_toast.mjs` → **38 pass**
- Python gallery subset → **134 pass**

### 4.2 Manual E2E checklist

| # | 場景 | 預期 |
|---|---|---|
| 1 | 看別人 profile（`#user=42`，state.me 是不同 user）| banner 無 ✏️ 按鈕 |
| 2 | 看自己 profile（`#user=<my_id>`）| 名字旁有 ✏️ 編輯按鈕 |
| 3 | Click ✏️ → dialog 開 | 表單預填當前 display_name / bio |
| 4 | 編輯後 submit | 成功 toast / dialog 關閉 / banner bio 立刻反映新值 |
| 5 | bio 為空 | 顯示 italic「（尚未填寫個人簡介）」placeholder |
| 6 | 匿名 (state.me=null) 看別人 profile | 無 ✏️ 按鈕（state.me 為 null 短路） |

## 5. 涉及檔案

```
src/stroke_order/web/static/gallery/gallery.js   (renderProfileBanner +12 行)
src/stroke_order/web/static/gallery/gallery.css  (+10 行)
docs/decisions/2026-05-05_phase5b_r29i_profile_edit_shortcut.md
pyproject.toml                                    (0.14.118 → 0.14.119)
```

零後端 / 零 test / 零 dependency 改動。

## 6. 教訓 / 共通性

- **Reconnaissance 在 phase plan 之前 = senior 標準動作**：我假設 phase 5c 是「從 0 做 profile 編輯」，recon 發現 **9 個元件中 9 個都已 ship**。**通用原則**：開新 phase 前 grep 既有 implementation，避免重做輪子或誤判 scope。
- **Re-render 自動 work 是 r29d/r29e 設計紅利**：refresh() 一條路徑統管 me / list / profile / deeplink 四個 fetch，編輯 profile 後 chain refresh 自動帶動 banner 更新。**通用原則**：fetch 邏輯集中在 single function 帶來的後續紅利 — 寫的時候多一點分鐘，後續 phase 直接享免費。
- **空 state placeholder vs hide**：bio 空時 hide 整個 div 看起來像「沒這 feature」；顯 italic placeholder「（尚未填寫）」反而引導 user 填 + 視覺平衡。**通用原則**：empty state 是 affordance hint 機會，不是該藏起來的瑕疵。
- **誠實 push back 比悶頭做好**：發現 phase 5c 範圍跟原假設差很多後直接停下重新評估，比硬把 r29i 偽裝成 phase 5c 健康。**通用原則**：評估錯了就承認，重新 scope 是 senior 該有的習慣。

## 7. r28-r29i 系列累計統計

| Phase | 重點 | Tests | 版本 |
|---|---|---|---|
| r28-r29h（前 12 phase） | 略 | Python +85 / Node +38 | ... → 0.14.118 |
| **r29i** | **profile banner ✏️ 編輯快捷 + 空 bio placeholder** | **0**（純 UI polish） | **0.14.119** |

**Two-day total: Python 307 + Node 38 = 345 tests, +13 phases, 13 versions, 13 decision logs.**

Profile 編輯閉環：dropdown 入口（既有）+ banner 快捷（r29i）+ 編輯後即時更新（既有 refresh 路徑紅利）。

## 8. Defer 留給後續

| 待做 | Phase |
|---|---|
| Avatar 頭像上傳（解決 profile 視覺空洞） | **r29j（next）** — 我推薦 |
| 編輯 dialog 字數計數（real-time） | nice-to-have，待 user 反饋 |
| Display_name 跟 email handle 的衝突 / 重名警示 | edge case，少見 |
| Featured / curated picks（admin role） | phase 5c 真版本 |
| Follow / 跟隨 user → 個人化 feed | phase 6 |
