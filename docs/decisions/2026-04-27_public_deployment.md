# 2026-04-27：公開部署（GitHub Pages + Render.com）

> 範圍：把 stroke-order 從本機開發狀態正式公開到網路，建立著作權數位足跡。
>
> 起點：私有 repo 已 push（昨日 5d+5g 完成 + GitHub 化）。
> 終點：`https://seyen37.github.io/stroke-order/`（文件站）+ `https://stroke-order.onrender.com/`（線上 demo）兩條 URL 全活。
>
> 對應 commits：
> - `f27e276` fix(pages): switch to pure HTML landing page (bypass Jekyll)
> - `e67e137` docs: add live demo URLs to README and docs landing page

---

## 決策 1：repo 由 Private 改為 Public

**情境**：GitHub Pages 在 free tier 要求 repo 必須是 Public。原本為了「先安全 push 上去再決定要不要公開」，repo 是 Private。

**選項**：
- A. 升級 GitHub Pro $4/月 → Private repo 也能用 Pages
- B. 改 Public

**決定**：B。

**考量**：
1. 反正最終目的就是公開——專案的存在意義就是給寫字機器人社群用
2. 升級訂閱解決一個一次性問題不划算
3. 公開前做了 secret 稽核：grep `STROKE_ORDER_SMTP_PASS`、`AUTH_SECRET`、`API_KEY` 全乾淨——所有敏感值都靠環境變數，repo 裡沒洩漏
4. MIT License + 第三方 attribution 已就緒

**教訓**：Public 之前一定要做完整 secret scan。`.env` 應在 `.gitignore`，所有 token / password 不應寫死在程式碼。我們昨天 `.gitignore` 寫得早，今天才能直接 Public。

---

## 決策 2：Jekyll vs 純 HTML — GitHub Pages 怎麼放

**情境**：第一次推上去後，`https://seyen37.github.io/stroke-order/` 顯示 404。

**問題追蹤過程**（這是今天最痛的一段）：
1. 一開始用 `docs/.nojekyll` + `docs/index.md` —— 沒處理 frontmatter，Jekyll 把它當 raw markdown 不渲染
2. 加 frontmatter `--- layout: default ---` —— 仍 404
3. 改 `_config.yml` theme 為 `cayman` —— 仍 404
4. 移除 `.nojekyll`、保留 frontmatter —— Actions 顯示綠 ✓ 但首頁還是 404

**選項**：
- A. 繼續 debug Jekyll（猜測是 BOM / line ending / `_config.yml` YAML 問題）
- B. 完全跳過 Jekyll，restored `.nojekyll`，自己手寫 `docs/index.html`
- C. 把文件放專案根目錄而非 `/docs`

**決定**：B（純 HTML）。

**考量**：
1. Jekyll 的失敗訊號太弱——CI 顯示綠勾但不渲染，失敗模式不可預測
2. 內容是給看的人，不是給 Jekyll 的——靜態 HTML 完全夠用
3. 我們只有一頁首頁要客製，其他 .md 檔可以直接連到 GitHub blob URL（GitHub 自帶 markdown 渲染，不需 Pages 處理）
4. 純 HTML 可在本機用瀏覽器預覽，不依賴雲端 build——debug cycle 從「commit + 等 CI」縮短到「F5」

**教訓**：
- Jekyll 為部落格設計，把多檔靜態文件 mapping 上去本來就不是甜蜜路徑
- 「失敗 silent」比「失敗大聲」更糟。Jekyll 的 build 報綠但內容空，這比直接報錯更難 debug
- 寫 50 行純 HTML 比起 debug 別人的 build pipeline，前者快 10 倍

---

## 決策 3：PowerShell 5.1 cp950 編碼陷阱

**情境**：第一輪修中文 .md 檔之後，網頁顯示「stroke-order ?辣銝剖?」（亂碼）。

**根因**：Windows 繁中版的 PowerShell 5.1 預設 console codepage 是 cp950（Big5）。指令如：
```powershell
Get-Content -Raw docs/index.md
```
會把 UTF-8 bytes 當成 Big5 解碼，所有中文亂碼。寫回去再 commit，repo 裡就被污染了。

**解法**（被迫採用）：
1. `git checkout 7857b21 -- docs/` 從 commit 還原乾淨 UTF-8 檔
2. 用 .NET API 讀寫，繞過 PowerShell 預設：
   ```powershell
   $bytes = [System.IO.File]::ReadAllBytes($path)
   $text  = [System.Text.Encoding]::UTF8.GetString($bytes)
   # 寫入時用 no-BOM 編碼
   $enc = [System.Text.UTF8Encoding]::new($false)
   [System.IO.File]::WriteAllText($path, $text, $enc)
   ```

**選項**：
- A. 把 PowerShell 改 codepage `chcp 65001`
- B. 升級 PowerShell 7（預設 UTF-8）
- C. 用 .NET API 強制 UTF-8（一次性 workaround）

**決定**：C，但記下 A/B 是長期解（沒做）。

**考量**：當下要快速止血，學系統設定花的時間夠重寫整個檔案三次。但這個陷阱會反覆出現，下次處理 .md 檔前要記得用 .NET API 或 git checkout，不要 `Get-Content -Raw`。

**教訓**：
- 繁中 Windows + PowerShell 5.1 是中文編碼的雷區
- 任何 UTF-8 檔處理流程，要先確認讀入端用什麼 codec，不要假設
- BOM 也是個變因——GitHub Pages 對檔案開頭 BOM byte 不寬容（疑似 Jekyll 失敗的真正原因之一）

---

## 決策 4：Render Blueprint vs 手動 Web Service

**情境**：Render 部署有兩條路：（A）手動 Web Service（每個欄位手填）（B）Blueprint（讀 `render.yaml` 自動建）。

**決定**：B（Blueprint）。

**考量**：
1. 環境變數有 4 個（PYTHON_VERSION、AUTH_SECRET、AUTH_DEV_MODE、BASE_URL），手填易漏
2. system packages（cairo / pango）需 `apt.txt`——只有 Blueprint 模式 Render 會去讀
3. `AUTH_SECRET` 用 `generateValue: true` 讓 Render 自動產隨機 32-byte，比自己想安全
4. 整個部署設定 **能 commit 到 repo**——下次部署到別的 Render 帳號，clone repo + Blueprint 就重現

**教訓**：基礎設施即程式碼（Infrastructure as Code）的好處在這裡放大。`render.yaml` 是 12 KB 文字檔，但它替我們省下 N 次填表 + 確保配置可重現。

---

## 決策 5：STROKE_ORDER_BASE_URL 的雞蛋問題

**情境**：`STROKE_ORDER_BASE_URL` 是 magic-link email 用的網址前綴。但這個值要等部署完才知道（Render 自動分配 subdomain）。

**選項**：
- A. 第一次部署填 placeholder（例如 `https://placeholder.onrender.com`），部署成功後改正
- B. 設定為 `sync: false` 讓 Render 必填，使用者部署時手動輸入

**決定**：兩者結合——`render.yaml` 設 `sync: false`（強制使用者填），第一次填 placeholder，部署 Live 後再回來改。

**考量**：dev mode 下 BASE_URL 不正確不會讓 app 壞——只是 magic-link 會指錯地方。可以先讓 service 起來再回填。

**教訓**：知道哪些設定值「先起步再修」OK，哪些「不對 app 就 crash」很重要。前者可用 placeholder，後者必須一次到位。

---

## 決策 6：先做最小可玩 demo，SMTP 等之後

**情境**：5g gallery 的完整流程需要 SMTP 寄真信。但 Render 上跑真 SMTP 要 Gmail App Password 或 SMTP provider 帳號，至少多 30 分鐘設定 + 測試。

**選項**：
- A. 一次到位，今天就開正式 SMTP
- B. 先用 dev mode（magic-link 印 console），驗證 e2e 流程，SMTP 之後再開

**決定**：B。

**考量**：
1. 今天目標是「全公開、有可玩 demo」，不是「對外服務」——dev mode 已足夠展示功能完整性
2. 真 SMTP 開了之後，理論上會有人嘗試註冊。先確認核心流程沒問題，再開水龍頭較安全
3. dev mode → 正式 SMTP 是「改 4 個環境變數」，零 code 改動。隨時可開。

**教訓**：MVP 化思維——把今天的 win 限制在「部署成功 + 可玩」，不擴張到「上線運營」。後者可以是下個工作日。

---

## 決策 7：多帳號 GitHub 備份策略

**情境**：使用者要求同時推到兩個 GitHub 帳號（seyen37 + seyenbot）做異地備份。

**選項**：
- A. 兩台機器各 clone 一份，手動同步
- B. 同個本機 repo 設兩個 remote（origin + backup），每次都推兩次
- C. 用 GitHub Actions 自動 mirror

**決定**：B。

**實作**：每帳號各一支 SSH key（`~/.ssh/id_ed25519_seyen37`、`~/.ssh/id_ed25519_seyenbot`），透過 `~/.ssh/config` 用 Host alias 區分：
```
Host github.com-seyen37
  HostName github.com
  IdentityFile ~/.ssh/id_ed25519_seyen37

Host github-backup
  HostName github.com
  IdentityFile ~/.ssh/id_ed25519_seyenbot
```
remote URL 用 alias：`git@github-backup:seyenbot/stroke-order.git`。

**考量**：
1. Git 沒有「multi-remote 同時 push」原生指令——`git push origin main && git push backup main` 兩行解
2. SSH config 的 Host alias 比每次手填 `-i` flag 乾淨
3. ed25519 key 比 RSA 短、安全性同等

**教訓**：每個 GitHub 帳號用自己的 SSH key，避免「seyen37 帳號 push 用 seyenbot key」的情境（GitHub 會以 key 對應的帳號身分接受 push）。

---

## 今日成果（2026-04-27）

```
✅ Public repo:        https://github.com/seyen37/stroke-order
✅ Mirror backup:      https://github.com/seyenbot/stroke-order
✅ 文件站:             https://seyen37.github.io/stroke-order/
✅ 線上 app:           https://stroke-order.onrender.com/
✅ /handwriting (5d):  線上可用
✅ /gallery (5g):      線上可用（dev mode auth）
✅ CI 綠勾:            1057 條 pytest 全過
```

從昨天的「私有 repo」到今天的「全網可訪問」，著作權數位足跡完整建立。

---

## 對後續工作的影響

1. **任何 push 到 main 都會觸發三件事**：CI、Pages rebuild、Render redeploy。要意識到改個 typo 也會 redeploy。
2. **Render free tier cold start ~30 秒**：示範時要事先預熱（先點一下首頁）。
3. **dev mode 邊界**：5g 真實使用前要切 SMTP——但目前展示功能 OK。
4. **Render auto-deploy on push**：若擔心半成品 commit 觸發部署，可改 manual。但個人專案 over-engineering，保留 auto。

---

## 下次部署前要記得的事

- `chcp 65001` 或用 PowerShell 7，避免 cp950 再次坑中文 .md
- Jekyll 不要碰，純 HTML > Jekyll for 此類專案
- Public 之前 grep 一次 secret 關鍵字
- `render.yaml` 用 `generateValue: true` 給安全敏感值
- BASE_URL 類「部署完才知道」的值，用 `sync: false` 標明
