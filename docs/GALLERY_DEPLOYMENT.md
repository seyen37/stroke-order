# 公眾分享庫（`/gallery`）部署指南

Phase 5g 加入的公眾分享庫需要少量伺服器端設定才能使用——主要是
SMTP（用於 email magic-link 登入）跟一個 HMAC 簽章 secret。本文整理
各環境變數的意義 + 三種常見部署情境的設定方式。

---

## TL;DR — 我只是想本機試一下

```bash
export STROKE_ORDER_AUTH_SECRET="$(openssl rand -hex 32)"
export STROKE_ORDER_AUTH_DEV_MODE=true
python -m stroke_order.web        # 或你慣用的啟動方式
```

**Dev mode** 不會真的寄信——magic link 會直接印到 console，使用者
複製連結貼到瀏覽器即可登入。零 SMTP 設定。**僅供開發/測試使用**。

---

## 環境變數一覽

| 環境變數 | 必填 | 預設值 | 說明 |
|---|---|---|---|
| `STROKE_ORDER_AUTH_SECRET` | ✅ 生產必填 | 內建警告用 fallback | HMAC-SHA256 簽 magic-link token 的金鑰，建議 ≥ 32 byte 隨機值 |
| `STROKE_ORDER_GALLERY_DIR` | ❌ | `~/.stroke-order/gallery` | SQLite + 上傳檔的根目錄 |
| `STROKE_ORDER_BASE_URL` | ❌ | `http://127.0.0.1:8000` | magic-link 連結的 base URL；**生產必須設**否則 email 連結會指向 localhost |
| `STROKE_ORDER_AUTH_DEV_MODE` | ❌ | `false` | `true` 時 magic link 印 console 不寄信 |
| `STROKE_ORDER_SMTP_HOST` | dev mode off 時必填 | — | SMTP 伺服器主機 |
| `STROKE_ORDER_SMTP_PORT` | ❌ | `587` | 587 = STARTTLS、465 = 隱式 TLS |
| `STROKE_ORDER_SMTP_USER` | dev mode off 時必填 | — | SMTP 帳號 |
| `STROKE_ORDER_SMTP_PASS` | dev mode off 時必填 | — | SMTP 密碼（Gmail 必須是 App Password，不是登入密碼） |
| `STROKE_ORDER_SMTP_FROM` | ❌ | `stroke-order PSD <noreply@example.com>` | From 標頭 |

---

## 情境 1：用 Gmail 寄信（個人部署最常見）

Gmail 不允許「應用程式直接用您的 Google 密碼」登入 SMTP；你需要
申請一個 **App Password**：

### 1. 開兩階段驗證
1. 前往 <https://myaccount.google.com/security>
2. 「Google 帳戶 → 安全性 → 兩步驟驗證」→ 啟用

> 沒有兩步驟驗證的帳戶**無法**申請 App Password，且 Google 一般不
> 允許從 IMAP/SMTP 登入。

### 2. 申請 App Password
1. 前往 <https://myaccount.google.com/apppasswords>
2. 「應用程式名稱」隨便填（例：`stroke-order`）→ 建立
3. 複製 16 字元的密碼（**這個值就是 SMTP_PASS**，不是您的 Google
   登入密碼）

### 3. 設定環境變數

```bash
export STROKE_ORDER_AUTH_SECRET="$(openssl rand -hex 32)"
export STROKE_ORDER_BASE_URL="https://your-domain.example.com"

export STROKE_ORDER_SMTP_HOST="smtp.gmail.com"
export STROKE_ORDER_SMTP_PORT=587
export STROKE_ORDER_SMTP_USER="your-account@gmail.com"
export STROKE_ORDER_SMTP_PASS="abcd efgh ijkl mnop"      # 16-字元 app pw
export STROKE_ORDER_SMTP_FROM="stroke-order <your-account@gmail.com>"
```

### 4. 用 systemd / Docker / 其他方式啟動
記得**不要把 secret commit 進 git**——用 `.env` 檔（加進 `.gitignore`）
或環境管理工具（systemd EnvironmentFile / Docker secret / 1Password）。

---

## 情境 2：用 SendGrid Free Tier（不想用個人 Gmail）

SendGrid 免費額度：**每天 100 封**——個人練字社群足夠用。

1. <https://signup.sendgrid.com/> 註冊
2. 帳戶 → API Keys → Create API Key（權限選 "Full Access"）→ 複製
3. 設定：

```bash
export STROKE_ORDER_AUTH_SECRET="$(openssl rand -hex 32)"
export STROKE_ORDER_BASE_URL="https://your-domain.example.com"

export STROKE_ORDER_SMTP_HOST="smtp.sendgrid.net"
export STROKE_ORDER_SMTP_PORT=587
export STROKE_ORDER_SMTP_USER="apikey"            # 字面就叫 'apikey'
export STROKE_ORDER_SMTP_PASS="SG.xxxxxxxxxxxx"   # 你剛剛複製的 API key
export STROKE_ORDER_SMTP_FROM="stroke-order <noreply@your-domain.example.com>"
```

> **注意**：SendGrid 要求 From 地址做 sender 驗證（Single Sender 或
> 整域驗證）。設好之前 SMTP 會回 550 錯誤。

其他常見替代：
- **Mailgun**：5,000 封/月 free tier
- **Resend** (resend.com)：3,000 封/月 free tier
- 自有 mail server（postfix）：完全無依賴但要自己處理 SPF/DKIM

---

## 情境 3：本機開發 / CI / 沒網路

```bash
export STROKE_ORDER_AUTH_SECRET="$(openssl rand -hex 32)"
export STROKE_ORDER_AUTH_DEV_MODE=true
```

啟動後 SMTP 完全不會被 touch。當使用者在 `/gallery` 點「登入」輸入
email，伺服器 console 會印：

```
============================================================
[stroke-order DEV MODE] Magic-link login
  to:  alice@example.com
  url: http://127.0.0.1:8000/api/gallery/auth/consume?token=eyJl…
============================================================
```

複製 url 貼到瀏覽器 → 自動登入。

> ⚠ **千萬不要在生產開 dev mode**。它會把所有人的 magic link 印到
> 你的 server log，等於誰看 log 就能登入誰的帳號。

---

## 安全建議

### `AUTH_SECRET` 的選擇

```bash
# Linux / macOS
openssl rand -hex 32         # 64 個 hex 字元 = 32 byte 金鑰

# 或 Python:
python -c "import secrets; print(secrets.token_hex(32))"
```

- 最少 32 byte (64 hex chars)
- **絕不能 commit 進 git**
- 換了 secret 後，所有現有 magic-link 跟 session **會立即失效**——
  這是 feature 不是 bug。

### 反向代理 / HTTPS

伺服器目前 cookie 設 `secure=False`（開發友善）。生產環境：

- 在反向代理（Caddy / nginx / Cloudflare）上 enforce HTTPS
- 反向代理層加 `X-Forwarded-Proto: https` header
- 若改用 starlette 的 `ProxyHeadersMiddleware`，cookie 可自動切 secure

### 檔案儲存配額

`uploads_dir()` 預設 `~/.stroke-order/gallery/uploads/`。隨著使用者
上傳累積，硬碟會增長。建議：

- 系統層加 quota 監控
- 定期備份（rsync 到別的機器或物件儲存）
- 5h 階段預計加管理頁可手動 LRU 清理舊檔

### 反濫用

5g MVP 的限制：
- 單檔 ≤ 10 MB（`MAX_FILE_SIZE_BYTES` in service.py）
- 同帳號每日 ≤ 20 次上傳（`DAILY_UPLOAD_LIMIT`）
- 同帳號 + 同 SHA-256 hash 自動拒絕（DB UNIQUE INDEX）

5h 階段預計加：檢舉達 3 次自動隱藏 + 管理員審查介面。

---

## 部署 checklist

開站前確認：

- [ ] `STROKE_ORDER_AUTH_SECRET` 已設且 ≥ 32 byte
- [ ] `STROKE_ORDER_BASE_URL` 指向正確的對外網址（HTTPS）
- [ ] `STROKE_ORDER_AUTH_DEV_MODE` **未設或為 false**
- [ ] SMTP 設定正確（host/port/user/pass/from）
- [ ] 寄一封測試信，確認到達且不在垃圾信件夾
- [ ] `gallery_dir()` 路徑可寫入、有足夠空間（建議 > 10 GB）
- [ ] 反向代理層 HTTPS + `X-Forwarded-*` header 傳遞
- [ ] 自動備份 `gallery_dir()` 內 SQLite + uploads/ 子目錄

---

## 故障排除

### 「magic link 沒收到」
- 檢查垃圾信件夾
- 確認 `SMTP_FROM` 的網域有 SPF/DKIM 記錄
- 改用 Gmail / SendGrid 等已設好寄信信譽的服務
- 暫時開 `AUTH_DEV_MODE=true` 確認流程沒壞，再排查 SMTP

### 「寄信時 server 回 500」
回應 detail 會明確說「`STROKE_ORDER_SMTP_HOST/USER/PASS` 未設」或
SMTP 伺服器拒絕——按提示補環境變數。

### 「登入連結點了顯示『連結無效或已過期』」
- 連結預設 15 分鐘內有效（`LOGIN_TOKEN_TTL_SEC` in auth.py）
- 一個連結只能用一次（防止 email 被前轉導致重放）
- 若這兩個條件都過了，回登入頁重新申請

### 「我換機器 / 重新部署，所有人都登出了」
- 換 `AUTH_SECRET` 會讓所有 token 失效——這是預期行為
- 若是同一個 secret 但 SQLite 檔案沒搬過去（在 `gallery_dir()` 裡），
  使用者帳號跟 session 都沒了；備份時記得連同這個目錄一起。
