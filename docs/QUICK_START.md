# stroke-order 啟動指南

最後更新：2026-04-26 · v0.13.0

---

## 目錄

1. [基本啟動（前 8 個模式）](#基本啟動前-8-個模式)
2. [包含公眾分享庫（5g）的啟動](#包含公眾分享庫5g的啟動)
3. [環境變數一覽](#環境變數一覽)
4. [.env 檔做法](#env-檔做法)
5. [瀏覽路徑](#瀏覽路徑)
6. [啟動後快速驗證](#啟動後快速驗證)
7. [停止 / 重啟 / 資料位置](#停止--重啟--資料位置)
8. [常見問題排除](#常見問題排除)

---

## 基本啟動（前 8 個模式）

如果只用主頁面的功能（單字 / 字帖 / 筆記 / 信紙 / 稿紙 / 塗鴉 / 文字雲 / 抄經 / 筆順練習）——
**不需要任何環境變數**。

### 第一次安裝

```bash
cd <stroke-order 專案根目錄>
pip install -e ".[web]"
```

附加可選依賴：

| 套件群 | 用途 |
|---|---|
| `[web]` | FastAPI + uvicorn + cairosvg + Pillow（必要）|
| `[gif]` | GIF 輸出（cairosvg + Pillow，與 web 重疊）|
| `[all]` | 上面全部 |
| `[dev]` | 上面全部 + pytest |

### 啟動

```bash
stroke-order serve
```

預設 `http://127.0.0.1:8000/`。

### 進階參數

```bash
stroke-order serve --host 0.0.0.0 --port 8080    # 指定 host / port
stroke-order serve --reload                       # 開發模式（檔案改動自動重啟）
stroke-order serve --help                         # 看完整參數
```

### 不裝 console script，直接 uvicorn 啟

```bash
pip install fastapi 'uvicorn[standard]' cairosvg Pillow
uvicorn stroke_order.web.server:app --reload
```

---

## 包含公眾分享庫（5g）的啟動

`/gallery` 公眾分享庫需要 SMTP 寄 magic-link 登入信，必須設環境變數。

### A. 最快速試用：dev mode（不寄信）

**適用情境**：本機測試 / 你還沒申請 SMTP / sandbox / CI

```bash
export STROKE_ORDER_AUTH_SECRET="$(openssl rand -hex 32)"
export STROKE_ORDER_AUTH_DEV_MODE=true

stroke-order serve
```

開 `/gallery` → 點「登入」→ 輸入 email →
**看伺服器 console** 會印：

```
============================================================
[stroke-order DEV MODE] Magic-link login
  to:  alice@example.com
  url: http://127.0.0.1:8000/api/gallery/auth/consume?token=eyJl...
============================================================
```

複製那個 url 貼瀏覽器 → 自動登入。零 SMTP 設定。

> ⚠ **千萬不要在生產開 dev mode**——所有人的 magic link 都會印到
> server log，誰看 log 就能登入誰的帳號。

### B. 正式部署：Gmail App Password

**前置作業**（一次性）：

1. 前往 <https://myaccount.google.com/security> → 啟用「兩步驟驗證」
2. 前往 <https://myaccount.google.com/apppasswords>
3. 「應用程式名稱」隨便填（例：`stroke-order`）→ 建立
4. 複製 16 字元的 App Password（**不是**你的 Google 登入密碼）

**啟動命令**：

```bash
export STROKE_ORDER_AUTH_SECRET="$(openssl rand -hex 32)"
export STROKE_ORDER_BASE_URL="https://your-domain.example.com"

export STROKE_ORDER_SMTP_HOST="smtp.gmail.com"
export STROKE_ORDER_SMTP_PORT=587
export STROKE_ORDER_SMTP_USER="your-account@gmail.com"
export STROKE_ORDER_SMTP_PASS="abcd efgh ijkl mnop"
export STROKE_ORDER_SMTP_FROM="stroke-order <your-account@gmail.com>"

stroke-order serve --host 0.0.0.0 --port 8000
```

### C. 替代 SMTP：SendGrid free tier

每天 100 封免費，個人練字社群很夠用。

1. <https://signup.sendgrid.com/> 註冊
2. Settings → API Keys → Create API Key（Full Access）→ 複製
3. Sender Authentication → Single Sender Verification → 驗證 from 地址

```bash
export STROKE_ORDER_SMTP_HOST="smtp.sendgrid.net"
export STROKE_ORDER_SMTP_PORT=587
export STROKE_ORDER_SMTP_USER="apikey"             # 字面上就是 'apikey'
export STROKE_ORDER_SMTP_PASS="SG.xxxxxxxxxxxx"    # 你剛剛複製的 API key
export STROKE_ORDER_SMTP_FROM="stroke-order <noreply@your-domain.example.com>"
```

詳細部署 / 安全建議見 `docs/GALLERY_DEPLOYMENT.md`。

---

## 環境變數一覽

| 變數 | 必填 | 預設 | 用途 |
|---|---|---|---|
| `STROKE_ORDER_AUTH_SECRET` | 5g 必填 | 內建警告 fallback | HMAC 簽 token 金鑰，**生產**請設 ≥32 byte 隨機值 |
| `STROKE_ORDER_GALLERY_DIR` | ❌ | `~/.stroke-order/gallery` | SQLite + 上傳檔根目錄 |
| `STROKE_ORDER_BASE_URL` | 生產建議 | `http://127.0.0.1:8000` | magic-link 連結用 |
| `STROKE_ORDER_AUTH_DEV_MODE` | ❌ | `false` | `true` = magic link 印 console 不寄信 |
| `STROKE_ORDER_SMTP_HOST` | 5g 非 dev 必填 | — | SMTP 主機 |
| `STROKE_ORDER_SMTP_PORT` | ❌ | `587` | 587=STARTTLS / 465=SSL |
| `STROKE_ORDER_SMTP_USER` | 5g 非 dev 必填 | — | SMTP 帳號 |
| `STROKE_ORDER_SMTP_PASS` | 5g 非 dev 必填 | — | SMTP 密碼 / App Password |
| `STROKE_ORDER_SMTP_FROM` | ❌ | 預設值（建議覆寫）| email From 標頭 |
| `STROKE_ORDER_SUTRA_DIR` | ❌ | `~/.stroke-order/sutras` | 抄經模式自訂經文目錄 |

---

## .env 檔做法

避免每次 export 麻煩，把設定寫進 `.env`（**加進 `.gitignore`，絕不 commit**）：

```bash
# 建立 .env
cat > .env <<'EOF'
# === Auth ===
STROKE_ORDER_AUTH_SECRET=__把這裡換成_64_hex_字元___
STROKE_ORDER_AUTH_DEV_MODE=true
STROKE_ORDER_BASE_URL=http://127.0.0.1:8000

# === SMTP（dev mode 時可不填） ===
# STROKE_ORDER_SMTP_HOST=smtp.gmail.com
# STROKE_ORDER_SMTP_PORT=587
# STROKE_ORDER_SMTP_USER=your-account@gmail.com
# STROKE_ORDER_SMTP_PASS=your-app-password
# STROKE_ORDER_SMTP_FROM=stroke-order <your-account@gmail.com>
EOF

# 啟動前載入
set -a
source .env
set +a

stroke-order serve
```

## 瀏覽路徑

| URL | 模式 | 加入版本 |
|---|---|---|
| `http://127.0.0.1:8000/` | 主頁（單字 / 字帖 / 筆記 / 信紙 / 稿紙 / 塗鴉 / 文字雲 / 抄經）| 1.x |
| `/sutra-editor` | 抄經模式編輯器子頁 | 5bd |
| `/handwriting` | **筆順練習頁（PSD）** | **5d / v0.12.0** |
| `/gallery` | **公眾分享庫** | **5g / v0.13.0** |

---

## 啟動後快速驗證

開另一個終端：

```bash
# 健康檢查
curl http://127.0.0.1:8000/api/health
# → {"ok":true,"version":"0.2.0"}

# 抓字符資料（hanzi-writer 格式）
curl http://127.0.0.1:8000/api/character/永
# → {"strokes":[...], "medians":[...]}

# 筆順練習頁的 reference outline（5d）
curl 'http://127.0.0.1:8000/api/handwriting/reference/永?style=lishu'
# → {"char":"永","style":"lishu","em_size":2048,"strokes":[...]}

# 公眾分享庫列表（匿名可讀；5g）
curl http://127.0.0.1:8000/api/gallery/uploads
# → {"items":[],"total":0,"page":1,"size":20}
```

也可以開瀏覽器直接走以下流程：

1. `/handwriting` 寫一個字 → 點「✓ 完成本字」→ 「我的資料」 → 「↓ JSON（全部）」 下載
2. `/gallery` → 「登入」→ email → console 取連結 → 點擊 → 自動登入
3. 「↑ 上傳 PSD」→ 選剛剛下載的 JSON → 標題 + 評論 → 上傳
4. 卡片出現在列表 → 「↓ 下載 JSON」 確認可下載

---

## 停止 / 重啟 / 資料位置

### 停止
按 `Ctrl+C` 即可。

### 重啟後資料還在嗎？

| 資料 | 位置 | 重啟後留存？ |
|---|---|---|
| 抄經自訂經文 | `~/.stroke-order/sutras/` | ✅ |
| **5g 使用者帳號 + 上傳檔** | `~/.stroke-order/gallery/` | ✅ |
| **5d 筆順練習軌跡** | 瀏覽器 IndexedDB | ✅（綁瀏覽器） |
| 5g sessions（30 天）| `gallery.db` 內 | ✅ |
| 5g magic-link tokens | `gallery.db` 內，15 分鐘到期 | ✅ |

### 5g 重要注意事項

- **`STROKE_ORDER_AUTH_SECRET` 換了**：所有現有 sessions + 未消費的 magic links **立即失效**——使用者要重新登入。**這是 feature 不是 bug**。
- **`gallery_dir()` 路徑變更**：等於開新資料庫，之前的帳號跟上傳全都看不到。請把整個 `gallery/` 子目錄一起搬。

---

## 常見問題排除

### 「點登入後沒收到 email」

1. 檢查垃圾信件夾
2. 檢查伺服器 log 有沒有錯誤訊息
3. 暫時開 `STROKE_ORDER_AUTH_DEV_MODE=true` 確認流程沒壞，再排查 SMTP
4. Gmail 拒絕：確認用的是 App Password 不是登入密碼，且兩階段驗證已啟用
5. SendGrid 拒絕：確認 from 地址做過 sender 驗證

### 「點登入後 server 回 500」

回應 detail 會明確說：
```
SMTP is not configured. Set STROKE_ORDER_SMTP_HOST + STROKE_ORDER_SMTP_USER + STROKE_ORDER_SMTP_PASS,
OR set STROKE_ORDER_AUTH_DEV_MODE=true ...
```
依提示補環境變數即可。

### 「點 magic-link 顯示『連結無效或已過期』」

- 連結 15 分鐘內有效
- 一個連結只能用一次（防 email 前轉重放）
- 過期 → 回登入頁重新申請

### 「`/gallery` 看到 404」

- 確認啟動了 v0.13.0 之後的版本（`pip show stroke-order` 看版號）
- 確認 `static/gallery.html` 跟 `static/gallery/` 子目錄都存在
- 重新 `pip install -e ".[web]"` 確保 package_data 重新打包

### 「連 `/handwriting` 都不顯示」

- 確認啟動了 v0.12.0 之後的版本
- 同上，確認 `static/handwriting.html` 跟 `static/handwriting/` 都存在

### 「Canvas 不能畫 / 觸控失靈」

- iOS Safari：確認 `touch-action: none` 套用了（用 devtools 看 `.hw-canvas` style）
- LINE / FB / IG 內建瀏覽器有問題：應該會看到頂部黃色警告 banner，照提示用系統 Safari / Chrome 開
- 強制重新整理頁面：Ctrl+Shift+R / Cmd+Shift+R 確保 .js 不走快取

### 「跑測試怎麼跑？」

```bash
pip install -e ".[dev]"
pytest tests/
```

預期看到 `1057 passed, 41 skipped`（v0.13.0）。

---

## 推薦工作流

### 本機開發

```bash
# Terminal 1: 啟動伺服器（自動 reload）
export STROKE_ORDER_AUTH_SECRET="$(openssl rand -hex 32)"
export STROKE_ORDER_AUTH_DEV_MODE=true
stroke-order serve --reload

# Terminal 2: 跑測試
pytest tests/ -v
```

### 部署到自己的 VPS

```bash
# 一次性
ssh user@your-server
git clone <repo> stroke-order
cd stroke-order
pip install -e ".[web]"

# 環境變數設好（.env 或 systemd EnvironmentFile）
# 起 systemd service / supervisor / docker compose

# 反向代理（Caddy 範例）
# Caddyfile:
# your-domain.example.com {
#   reverse_proxy localhost:8000
# }
```

### 跨機備份 5g 資料

```bash
# 備份
rsync -avz ~/.stroke-order/gallery/ backup-host:/backups/stroke-order-gallery/

# 還原（連 secret 一起搬，不然 sessions 都失效）
rsync -avz backup-host:/backups/stroke-order-gallery/ ~/.stroke-order/gallery/
# .env 裡的 STROKE_ORDER_AUTH_SECRET 也要保持一致
```

---

## 相關文件

- 工作紀錄：`docs/WORK_LOG_2026-04-26.md`
- 完整部署指南（含安全建議）：`docs/GALLERY_DEPLOYMENT.md`
- 主 README：`README.md`
