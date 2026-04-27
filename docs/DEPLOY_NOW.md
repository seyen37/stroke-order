---
layout: default
---

# 立即部署：GitHub Pages + Render.com

最後更新：2026-04-26 · 對應 v0.13.0

依序做完這份文件，你的專案會：

1. ✅ `https://seyen37.github.io/stroke-order/` — 文件網站
2. ✅ `https://stroke-order.onrender.com/` — 完整可用的 stroke-order app

預估時間：**20 分鐘**（含等待 Render build）

---

## 前置：把新檔案 push 到 GitHub

打開 PowerShell，cd 到專案資料夾：

```powershell
cd C:\Users\USER\Documents\Cowork\stroke_order

# 確認新檔已存在
Test-Path docs/.nojekyll
Test-Path docs/index.md
Test-Path render.yaml
Test-Path apt.txt
# 全部應顯示 True
```

Commit + push：

```powershell
git add docs/.nojekyll docs/index.md docs/PUBLIC_DEPLOYMENT.md docs/MULTI_GITHUB_BACKUP.md docs/GIT_AUTH_SETUP.md docs/DEPLOY_NOW.md render.yaml apt.txt
git commit -m "deploy: GitHub Pages config + Render.com blueprint" -m "- docs/.nojekyll: disable Jekyll on GitHub Pages so all our .md files render directly. - docs/index.md: landing page for the docs site. - render.yaml: Render.com Blueprint for one-click deploy of the FastAPI backend. - apt.txt: cairo + pango system libs needed by cairosvg + Pillow."
git push origin main
```

> 如果你已經設好雙 backup remote，記得也推：`git push backup main`

---

# 階段 1：GitHub Pages（5 分鐘）

## Step 1.1：在 GitHub repo 啟用 Pages

1. 開瀏覽器 → <https://github.com/seyen37/stroke-order/settings/pages>
2. 「**Source**」區塊：
   - 選「**Deploy from a branch**」
   - **Branch**: `main`
   - **Folder**: `/docs`
3. 點「**Save**」

GitHub 開始部署，畫面上會顯示「Your site is being built」。等 1-2 分鐘。

## Step 1.2：等部署完成 + 確認

回到 <https://github.com/seyen37/stroke-order/settings/pages>，重新整理。看到：

> Your site is live at **https://seyen37.github.io/stroke-order/**

點那個連結 → 應該看到 docs/index.md 渲染出來的網頁。

## Step 1.3：把 GitHub Pages URL 加到 README（之後做）

到時候 README 第一段可以改成：

```markdown
- 📖 文件：<https://seyen37.github.io/stroke-order/>
- 📦 GitHub repo：<https://github.com/seyen37/stroke-order>
```

但這不急，可以之後跟其他更新一起 push。

---

# 階段 2：Render.com 完整部署（15 分鐘 + 5–10 分鐘 build）

## Step 2.1：建 Render 帳號

1. 開 <https://render.com/>
2. 點「**Get Started**」→「**GitHub**」（用 seyen37 帳號登入）
3. 授權 Render 讀你的 repos（建議只授權 `stroke-order` 這一個）

## Step 2.2：建立 Blueprint service

1. Dashboard 右上「**New +**」→「**Blueprint**」
2. 「**Connect Repository**」→ 選 `seyen37/stroke-order`
3. Render 自動讀 `render.yaml`，顯示「將建立 service: stroke-order (Web Service, Free)」
4. 點「**Apply**」

開始 build。畫面會跳到 service 頁面，可以看到 build log 即時更新。

> ⏱ 第一次 build 比較久（~5-10 分鐘）：要 apt-get install 系統套件 + pip install 整個專案。
> 之後每次 push 觸發 redeploy 大約 2-3 分鐘。

## Step 2.3：等到「Live」

build 完成後，service 狀態會從「Deploying...」變成「**Live**」（綠色點）。

頁面右上角會顯示 service URL，類似：
```
https://stroke-order.onrender.com
```
（也可能是 `stroke-order-xxxx.onrender.com`，xxxx 是隨機字串——可以日後在 Settings 改）

## Step 2.4：填 STROKE_ORDER_BASE_URL

Render 不會自動知道部署完的 URL，需要手動填一次。

1. Service 頁面 → 左邊導覽列「**Environment**」
2. 找到 `STROKE_ORDER_BASE_URL`
3. 點旁邊的「**Edit**」
4. 值：複製剛才的 service URL（**不含結尾的 `/`**）
   例：`https://stroke-order.onrender.com`
5. 「**Save changes**」
6. Render 自動觸發 redeploy（約 2 分鐘）

## Step 2.5：測試

開 service URL（譬如 `https://stroke-order.onrender.com/`）：

| 測試項 | 預期結果 |
|---|---|
| 主頁 `/` | 顯示主頁面（前 7 個模式 tab）|
| `/handwriting` | 筆順練習頁 |
| `/gallery` | 公眾分享庫主頁 |
| `/api/health` | `{"ok":true,"version":"0.2.0"}` |
| `/api/character/永` | hanzi-writer 格式 JSON |

> 第一次點頁面會慢 30 秒左右（cold start 喚醒）。這是免費 tier 限制——如果 15 分鐘無人訪問會睡覺。

## Step 2.6（可選）：測 gallery 登入流程

1. 開 `https://stroke-order.onrender.com/gallery`
2. 點「登入」→ 輸入 email
3. 因為是 dev mode，**不會真的寄信**——magic-link 印到 Render log
4. 開 service 的「**Logs**」tab 找：
   ```
   ============================================================
   [stroke-order DEV MODE] Magic-link login
     to:  你的 email
     url: https://stroke-order.onrender.com/api/gallery/auth/consume?token=...
   ============================================================
   ```
5. 複製那 url 貼瀏覽器 → 自動登入

驗證完整 e2e 流程沒問題後，要開放給真實使用者前：
- 設 SMTP 環境變數（見下節）
- 把 `STROKE_ORDER_AUTH_DEV_MODE` 改成 `false`

## Step 2.7（之後）：開正式 SMTP

當你準備接受真實使用者，到 Render Dashboard：

1. Service → Environment
2. **新增** 環境變數：
   - `STROKE_ORDER_SMTP_HOST` = `smtp.gmail.com`
   - `STROKE_ORDER_SMTP_PORT` = `587`
   - `STROKE_ORDER_SMTP_USER` = 你的 gmail
   - `STROKE_ORDER_SMTP_PASS` = Gmail App Password（見 `docs/GALLERY_DEPLOYMENT.md` 教學）
   - `STROKE_ORDER_SMTP_FROM` = `stroke-order <你的 gmail>`
3. **修改** `STROKE_ORDER_AUTH_DEV_MODE` → `false`
4. Save → 自動 redeploy
5. 試從 /gallery 寄真信驗證

---

# 完成檢查清單

兩個都做完後，你的成果：

- [ ] `https://seyen37.github.io/stroke-order/` 顯示文件首頁
- [ ] `https://stroke-order.onrender.com/` 顯示主頁面
- [ ] `https://stroke-order.onrender.com/handwriting` 可以畫字
- [ ] `https://stroke-order.onrender.com/gallery` 可以登入（dev mode）
- [ ] GitHub repo README 上的 CI badge 顯示綠色「passing」
- [ ] 兩個 URL 都 HTTPS（自動 cert）

---

# 下一步建議

1. **更新 README 加上線上連結**
2. **告訴朋友 / 社群**——可以發個 g0v 貼文、推特、IG 短文
3. **持續用 docs/decisions/ 累積設計脈絡**——每次新功能都產生決策日誌
4. **觀察 Render 流量**——若 cold start 影響太大，升 Starter $7/月

---

# 故障排除

## GitHub Pages 顯示 404

- 等 1-2 分鐘讓 deployment 完成
- 確認 Settings → Pages 的 Source 是 `main` + `/docs`
- 確認 `docs/index.md` 確實存在（GitHub Pages 預設會找這個檔當首頁）

## Render build 失敗

點 build log 看錯誤。常見原因：

- **`No module named 'fastapi'`**：pyproject 的 `[project.optional-dependencies] web` 沒 web 額外標
- **`libcairo.so.2: cannot open shared object`**：apt.txt 沒讀到 → 確認檔案名是 `apt.txt` 在專案根目錄
- **`pip wheel ... failed`**：pip cache 問題，到 Render Settings → Manual Deploy → Clear build cache

## Render service 跑起來但首頁 500 / 502

- 開 Logs tab 看伺服器錯誤
- 通常是 import 失敗 / port 設錯
- 確認 startCommand 用 `--port $PORT`（Render 動態指派 port）

## /gallery 登入沒反應 / 看不到 magic link

- 確認 `STROKE_ORDER_AUTH_DEV_MODE` 環境變數是 `true`
- 確認 `STROKE_ORDER_BASE_URL` 設好（不然 magic-link 連結會用 localhost）
- 開 Logs tab 重新整理，找 `DEV MODE` 區塊

## 「太多 cold start」抱怨

升 Starter plan ($7/月)：
- Render Dashboard → Service → Settings → Plan → Upgrade
- 立即生效，無 cold start

---

# 結束後告訴我

完成兩個階段後，回我「**部署完成**」+ 兩個 URL，我會：
1. 把 README 更新加上線上連結
2. 繼續寫 Batch 2 考古決策日誌（mode_02 字帖 + mode_03 筆記 + infra_02 字型風格）
