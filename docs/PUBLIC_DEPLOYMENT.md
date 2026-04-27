---
layout: default
---

# 把 stroke-order 公開架設到網路上

最後更新：2026-04-26

---

## 先回答 github.io 是什麼

**`github.io` = GitHub Pages**：GitHub 提供的免費**靜態網頁**寄存服務。

- 你 push 到特定 branch（通常 `gh-pages` 或 `main` 的 `/docs` 子目錄）
- GitHub 自動把那些檔案發布到 `https://<username>.github.io/<repo>/`
- 完全免費（個人 public repo）
- 自動 HTTPS
- 也可以綁自己買的網域（譬如 `stroke-order.tw`）

**範例**：
- `https://seyen37.github.io/` — 個人首頁（如果有 `seyen37/seyen37.github.io` repo）
- `https://seyen37.github.io/stroke-order/` — 專案頁

---

## ⚠ 但 GitHub Pages **不適合直接跑** stroke-order

關鍵限制：**GitHub Pages 只能跑靜態檔案（HTML / CSS / JS）**。

stroke-order 的問題：

| 功能 | 需要的東西 | GitHub Pages 能跑？ |
|---|---|---|
| 單字 / 字帖 / 筆記 / 信紙 / 文字雲 | Python FastAPI 後端 + cairosvg 渲染 | ❌ |
| 抄經模式 PDF 下載 | Python + cairosvg + Pillow | ❌ |
| `/handwriting` 筆順練習頁 | 前端可、但需要 `/api/handwriting/reference` 後端 | 部分（但缺字形 fetch）|
| `/gallery` 公眾分享庫 | SQLite + SMTP + auth | ❌ |
| `/api/*` 全部 API endpoints | Python 後端 | ❌ |

**結論**：要讓使用者實際使用 stroke-order 全部功能，必須找**支援 Python 後端**的平台。

---

## 部署選項一覽

| 方案 | 月費 | 難度 | 適合場景 |
|---|---|---|---|
| **Render.com 免費** | 免費（有 cold start）| 低 | 試水溫、個人專案 demo |
| **Render.com 付費** | $7+ | 低 | 穩定運作、無 cold start |
| **Fly.io 免費** | 免費（小機器）| 中 | 對 Docker 熟悉的進階使用者 |
| **DigitalOcean / Linode / Vultr / Hetzner VPS** | $5-6 | 高 | 完全控制、長期穩定、用得久 |
| **自架（家中伺服器 + Cloudflare Tunnel）** | 0（電費）| 高 | 已有硬體、要學 Linux |
| **Hugging Face Spaces** | 免費 | 中 | AI demo 風格，需 Docker |
| **GitHub Pages**（**僅靜態頁**）| 免費 | 低 | 文件、landing page、不需後端 |

---

## 推薦路線：分階段部署

### 階段 1：GitHub Pages 放「介紹頁 + 文件」（免費、馬上能用）

把 `docs/` 變成可瀏覽的網站，作為**專案的對外門面**——介紹 stroke-order 是什麼、有哪些功能、怎麼安裝、有截圖、文件齊全，但**實際使用要 clone 下來自己跑**。

這個階段不能讓使用者直接「在你的網站上寫字」，但可以讓 stroke-order 被人發現、有 SEO、有引用價值。

### 階段 2：Render.com 免費部署「完整後端」（免費 + 5 分鐘）

讓使用者可以直接用 `https://stroke-order.onrender.com/` 跑全部功能。免費 tier 限制：

- **Cold start**：15 分鐘無人訪問會睡覺，下次第一個請求要等 30 秒喚醒
- 750 小時/月（一個服務 24h × 31 天 = 744h，剛好用滿）
- SSL 自動

對個人 demo / 朋友圈推薦完全夠用。**有人用得多就會付費升級**，無痛擴展。

### 階段 3（可選）：自架 VPS 或自家伺服器

有實際使用者後（譬如月活 100+）再考慮——預算可控（$5/月）、效能穩定、無 cold start。

---

## 階段 1：GitHub Pages 設定（5 分鐘）

讓 `https://seyen37.github.io/stroke-order/` 顯示你的 README + docs。

### 在 repo 啟用 Pages

1. 開 <https://github.com/seyen37/stroke-order/settings/pages>
2. **Source**: 選「Deploy from a branch」
3. **Branch**: `main` / 資料夾選 `/docs`
4. 點「Save」

等 1-2 分鐘 GitHub 部署完成。

### 處理：GitHub Pages 預設用 Jekyll（會吃掉某些檔）

加一個空 `.nojekyll` 檔避免：

```powershell
cd C:\Users\USER\Documents\Cowork\stroke_order
New-Item docs/.nojekyll -ItemType File
git add docs/.nojekyll
git commit -m "docs: disable Jekyll on GitHub Pages"
git push
```

### 結果

`https://seyen37.github.io/stroke-order/` 自動顯示 `docs/index.md`（如果有）或目錄列表。

> 你的 `docs/` 目前主要是 .md 檔（QUICK_START / GALLERY_DEPLOYMENT / WORK_LOG / PUSH_TO_GITHUB / decisions/）——GitHub Pages 會把它們渲染成漂亮 HTML，自動加上 syntax highlighting。

### 進階：用 MkDocs 美化（可選）

把 docs/ 弄成正式文件網站（像 [docs.python.org](https://docs.python.org/) 風格）：

```bash
pip install mkdocs mkdocs-material
mkdocs new .             # 在專案根目錄
# 編輯 mkdocs.yml + 把 docs/ 結構配進 nav
mkdocs gh-deploy         # 一鍵推到 gh-pages branch
```

GitHub Pages 自動服務 `gh-pages` branch 內容。

---

## 階段 2：Render.com 免費部署完整後端（最推薦）

讓 `https://stroke-order.onrender.com/`（或自選名字）跑你的整個 FastAPI app。

### Step 1：建 Render 帳號

1. <https://render.com/> → Sign up with GitHub（用你的 seyen37 帳號）
2. 授權 Render 讀你的 GitHub repos

### Step 2：在 repo 加部署設定檔

在專案根目錄建 `render.yaml`（PowerShell）：

```powershell
@"
services:
  - type: web
    name: stroke-order
    runtime: python
    plan: free
    buildCommand: pip install -e ".[web]"
    startCommand: uvicorn stroke_order.web.server:app --host 0.0.0.0 --port `$PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.7
      - key: STROKE_ORDER_AUTH_SECRET
        generateValue: true
      - key: STROKE_ORDER_AUTH_DEV_MODE
        value: true
      - key: STROKE_ORDER_BASE_URL
        sync: false
"@ | Out-File -FilePath render.yaml -Encoding ascii
```

> `STROKE_ORDER_AUTH_DEV_MODE=true` 先設 true 讓你可以先測試——5g gallery 不會真的寄信，magic-link 印到 Render log。確認 app 跑起來後再切 false + 設 SMTP。

```powershell
git add render.yaml
git commit -m "deploy: add Render.com configuration"
git push
```

### Step 3：在 Render dashboard 建 service

1. 登入 Render → 點「**New +**」→「**Blueprint**」
2. 連你的 `stroke-order` repo
3. Render 自動讀 `render.yaml` → 點「**Apply**」
4. 等 5–10 分鐘 build + deploy

完成後會給你 URL：`https://stroke-order.onrender.com/`（或類似）。

### Step 4：設 `STROKE_ORDER_BASE_URL` 環境變數

回到 Render 服務 dashboard：

1. 「Environment」tab
2. 找到 `STROKE_ORDER_BASE_URL`（剛剛設 `sync: false` 表示「我之後再填」）
3. 填 `https://stroke-order.onrender.com`（不要結尾的 `/`）
4. 點 Save → Render 自動 redeploy

### Step 5：測試

開 `https://stroke-order.onrender.com/` —— 應該看到 stroke-order 主頁。
- 第一次訪問：15-30 秒（cold start 喚醒）
- 之後快很多（直到 15 分鐘無人訪問又睡覺）

訪問各個模式都試一下：
- `/handwriting` 筆順練習
- `/gallery` 公眾分享庫（dev mode 下登入會印 magic-link 到 Render log）

### Step 6（可選）：開正式 SMTP（讓 /gallery 真的寄信）

當你準備接受真實使用者：

1. 申請 Gmail App Password 或 SendGrid（見 `docs/GALLERY_DEPLOYMENT.md`）
2. Render dashboard → Environment：
   - 取消 `STROKE_ORDER_AUTH_DEV_MODE`（或設 `false`）
   - 加 `STROKE_ORDER_SMTP_HOST` / `_USER` / `_PASS` / `_FROM`
3. Save → 自動 redeploy
4. 試從 `/gallery` 寄登入信，到收件夾驗證

---

## 階段 2 替代：Fly.io 部署

Fly.io 免費 tier 略好（無 cold start，3 個小機器），但要寫 `Dockerfile` + 設定 `fly.toml`，門檻略高。

如果你已經會 Docker：

```dockerfile
# Dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install -e ".[web]"
EXPOSE 8000
CMD ["uvicorn", "stroke_order.web.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# 安裝 flyctl
curl -L https://fly.io/install.sh | sh

# 登入 + 部署
flyctl auth login
flyctl launch         # 互動式問答產生 fly.toml
flyctl deploy
```

---

## 階段 3：自架 VPS（DigitalOcean / Hetzner）

**何時值得**：
- 月活 100+ 使用者
- 需要持續運作（不能 cold start）
- 想完全控制部署環境

**最便宜選擇**（2026 行情）：
- **Hetzner CX11**：€4.51/月，1 vCPU + 2GB RAM + 20GB SSD（在歐洲，台灣 ping ~250ms）
- **Hetzner CCX13**（亞洲區待開）
- **Vultr Tokyo**：$6/月，1 vCPU + 1GB RAM（離台灣近 ~50ms）
- **DigitalOcean SGP1**：$6/月（新加坡 ~80ms）

部署流程概要（之後若你決定要做我可以寫詳細指南）：

```bash
# 在 VPS 上
sudo apt update && sudo apt install -y python3.11 python3.11-venv git nginx certbot python3-certbot-nginx
git clone git@github.com:seyen37/stroke-order.git
cd stroke-order
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[web]"

# Run via systemd
sudo nano /etc/systemd/system/stroke-order.service   # 寫 service unit
sudo systemctl enable --now stroke-order

# Nginx reverse proxy + HTTPS
sudo nano /etc/nginx/sites-available/stroke-order
sudo certbot --nginx -d stroke-order.tw
```

---

## 自定義網域（綁自己的 .com）

不論用哪個平台，都可以綁自己買的網域。

### 1. 買網域

- 國內：[Gandi](https://www.gandi.net/) / [Namecheap](https://www.namecheap.com/) / [台灣中華電信 hinet.net](https://domain.hinet.net/)
- `stroke-order.tw` 一年大約 $15–30（看後綴）

### 2. 設 DNS

| 平台 | DNS 設定 |
|---|---|
| GitHub Pages | CNAME → `seyen37.github.io.` |
| Render | CNAME → `stroke-order.onrender.com.` |
| 自架 VPS | A record → 你的 VPS IP |

### 3. SSL 證書

- GitHub Pages / Render：自動處理（Let's Encrypt）
- 自架 VPS：`sudo certbot --nginx`

---

## 三個方案的決策樹

```
你想先做什麼？
│
├─ 「先讓人看到專案存在」
│    → 階段 1：GitHub Pages（5 分鐘）
│
├─ 「想讓人直接用 /handwriting / /gallery」
│    → 階段 2：Render.com 免費 tier（15 分鐘）
│
└─ 「要長期運作 + 月活破百 + 沒 cold start」
     → 階段 3：自架 VPS（半天起跳）
```

---

## 真實成本概覽（一年下來）

| 方案 | 一年總成本 | 包含 |
|---|---|---|
| GitHub Pages（純文件）| 0 | 文件託管 |
| Render.com 免費 | 0 | + 完整 web app（cold start）|
| Render.com Starter | $84 | + 無 cold start |
| Hetzner VPS + 網域 | $90–110 | + 完全控制 + 無 cold start |
| 自架家中伺服器 | $30 (電費) | + 完全控制 + 一台機器另做別的 |

---

## 我的個人推薦

**現階段**：先做**階段 1 GitHub Pages**，把 `docs/` 公開讓人讀文件——5 分鐘的事，立刻有 SEO 跟對外形象。

**有空的時候**：做**階段 2 Render**，讓人能實際試用 stroke-order——你的核心 demo 才能被體驗。免費 tier 對個人專案夠用。

**等到累積真實使用者**：再考慮**階段 3 VPS**——這是「真的營運」的成本。

---

## 完成 GitHub Pages 後的 README 連結

部署完成後，README 開頭可以加：

```markdown
- 📖 文件網站：https://seyen37.github.io/stroke-order/
- 🚀 線上 demo：https://stroke-order.onrender.com/
- 📦 GitHub repo：https://github.com/seyen37/stroke-order
```

---

## 常見問題

### Q: GitHub Pages 跟 GitHub Actions CI 衝突嗎？
不會。GitHub Actions 是「跑測試」、Pages 是「服務靜態檔」，互不相干。可以同時用。

### Q: Render 的 cold start 真的影響大嗎？
個人 demo 不太影響（朋友看到一次慢點就好）。**重度使用者**會抱怨。一旦你看到流量穩定 → 升 $7/月就無 cold start。

### Q: 我的 SQLite 資料庫在 Render 重啟後會消失嗎？
**會**（免費 tier 沒有持久 disk）。免費 tier 適合「無使用者狀態」的 demo。一旦要保留 gallery 上傳資料：
- 升 Starter plan 加 disk
- 或改用外部 PostgreSQL（Render 也有免費 PostgreSQL）

### Q: 要不要先付費？
不用。Render 免費 tier 部署完，先看真實流量——大部分專案永遠在免費 tier 就夠。
