# 多 GitHub 帳號同步備份指南

最後更新：2026-04-26

把同一個專案同步推到兩個（或更多）GitHub 帳號的 repo，用途：

- **異地備份**：主帳號 repo 萬一被刪 / 帳號被 ban，備援 repo 還在
- **版權證據加成**：兩個帳號的 push timestamp 都是不可偽造的第三方時戳
- **公開 / 私密分流**：主帳公開、備份帳設 private

---

## 你的兩個帳號

| 角色 | 帳號 | repo URL |
|---|---|---|
| 主帳號 | `seyen37` | `git@github.com:seyen37/stroke-order.git`（已 push 完成 ✅）|
| 備份帳 | `seyenbot` | `git@github.com:seyenbot/stroke-order.git`（待設定）|

---

## 整體流程概覽

```
本機 stroke_order/
   ├── .git/
   └── 一條 main branch
            │
            ├── push → seyen37 帳號（用 ssh key #1）
            └── push → seyenbot 帳號（用 ssh key #2）
```

**關鍵概念**：
- 一個本機 git repo 可以有多個 remote / 多個 push URL
- SSH key 跟 GitHub 帳號是 1:1（一支 key 只能掛一個帳號）
- 用 `~/.ssh/config` 為兩個 GitHub host 配不同 key

---

## Step 1：產第二支 SSH key 給 seyenbot 用

**在 PowerShell**（一般權限）：

```powershell
ssh-keygen -t ed25519 -C "seyenbot@github" -f $HOME\.ssh\id_ed25519_seyenbot
```

過程：
- **「Enter passphrase」**：直接按 Enter（跟第一支 key 一致）

完成後 `~/.ssh/` 應有兩組 key：
```
id_ed25519              ← seyen37 用
id_ed25519.pub
id_ed25519_seyenbot     ← seyenbot 用（新的）
id_ed25519_seyenbot.pub
```

驗證：
```powershell
ls $HOME\.ssh\
```

---

## Step 2：把第二支公鑰貼到 seyenbot 帳號

複製公鑰到剪貼簿：

```powershell
Get-Content $HOME\.ssh\id_ed25519_seyenbot.pub | Set-Clipboard
```

然後：

1. **登出**目前的 GitHub 帳號（seyen37）
2. **登入 seyenbot 帳號**
3. 開 <https://github.com/settings/keys>
4. 點「**New SSH key**」
5. **Title**: `Windows PC (backup)` 或類似
6. **Key**: 點輸入框 → **Ctrl+V** 貼上
7. 點「**Add SSH key**」

> 確認頁面右上角頭像/名字是 **seyenbot** 而不是 seyen37 — 加錯帳號後面會卡住！

---

## Step 3：建立 seyenbot 帳號的 stroke-order repo（如果還沒）

1. 仍在 seyenbot 帳號下
2. <https://github.com/new>
3. **Repository name**: `stroke-order`（跟 seyen37 那個名稱可以一樣）
4. **Public** / **Private**: 看你決定（私人備份建議 Private）
5. **不要**勾「Initialize with README」（要保持空的，等下我們 push 上去）
6. 「Create repository」

---

## Step 4：設定 `~/.ssh/config` 區分兩個 GitHub host

PowerShell 建檔：

```powershell
# 確保 ~/.ssh 目錄存在
if (-not (Test-Path $HOME\.ssh)) { New-Item -ItemType Directory -Path $HOME\.ssh }

# 寫 config 檔
@"
# 主帳號 — seyen37
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes

# 備份帳號 — seyenbot
# 用法：把 git URL 的 github.com 改成 github-backup
# 例：git@github-backup:seyenbot/stroke-order.git
Host github-backup
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_seyenbot
  IdentitiesOnly yes
"@ | Out-File -FilePath $HOME\.ssh\config -Encoding ascii
```

驗證內容：
```powershell
Get-Content $HOME\.ssh\config
```

> `IdentitiesOnly yes` 很重要——強制 SSH 只用指定的 key，不去試其他的（避免 GitHub 收到「錯帳號的 key」直接 reject）

---

## Step 5：驗證兩個 host 都能連

```powershell
# 主帳號（用 key #1）
ssh -T git@github.com
# 預期：Hi seyen37! You've successfully authenticated...

# 備份帳（用 key #2）
ssh -T git@github-backup
# 預期：Hi seyenbot! You've successfully authenticated...
```

兩個都打對名字才算成功。如果某個顯示錯帳號，回 Step 4 檢查 config 對不對。

---

## Step 6：加 backup remote 並 push

兩種模式選一個：

### 模式 A：兩個獨立 remote（手動推兩次）

優：清楚分開、可以選擇只推某一個
缺：每次 push 要打兩個指令

```powershell
cd C:\Users\USER\Documents\Cowork\stroke_order

# 加 backup remote
git remote add backup git@github-backup:seyenbot/stroke-order.git

# 確認兩個 remote 都在
git remote -v
# 應顯示：
#   backup  git@github-backup:seyenbot/stroke-order.git (fetch)
#   backup  git@github-backup:seyenbot/stroke-order.git (push)
#   origin  git@github.com:seyen37/stroke-order.git     (fetch)
#   origin  git@github.com:seyen37/stroke-order.git     (push)

# 推到 backup
git push -u backup main
git push backup v0.13.0       # tag 也要推

# 之後每次更新：
git push origin main
git push backup main
```

### 模式 B：一個 origin、兩個 push URL（一次同步推兩處）

優：一行 `git push` 推兩處
缺：fetch 還是只從第一個（origin）拉

```powershell
cd C:\Users\USER\Documents\Cowork\stroke_order

# 把 backup URL 加進 origin 的 push targets
git remote set-url --add --push origin git@github.com:seyen37/stroke-order.git
git remote set-url --add --push origin git@github-backup:seyenbot/stroke-order.git

# 確認 push 變兩個 URL
git remote -v
# 應顯示：
#   origin  git@github.com:seyen37/stroke-order.git     (fetch)
#   origin  git@github.com:seyen37/stroke-order.git     (push)
#   origin  git@github-backup:seyenbot/stroke-order.git (push)

# 一次推兩處
git push origin main
git push origin v0.13.0       # tag
```

> ⚠ 模式 B 的奇怪行為：第一次 `set-url --add --push` 其實是「替換」原本的單一 push URL；第二次才是真的「加」。這是 git 的設計怪癖。所以**第一行**雖然看起來是「重複加一樣的 URL」，其實是讓 git 進入「多 push URL」模式。**一定要兩行都跑才正確**。

### 我的建議

**先用模式 A**（保險、清楚）。日後想簡化再切模式 B。

---

## Step 7：驗證兩個 GitHub 帳號 repo 都收到

開兩個瀏覽器視窗（或同一個瀏覽器分頁）：

1. <https://github.com/seyen37/stroke-order> — 4 個 commits
2. <https://github.com/seyenbot/stroke-order> — 同 4 個 commits

兩處 commit hash 應該完全一樣（因為是同一個本機 repo push 的）。

GitHub Actions CI 會在**兩個 repo 都跑**（如果兩邊都啟用 Actions）——等於每次 push 多一倍 server-side timestamp。

---

## 之後的維護循環

### 模式 A 的日常工作流

```powershell
# 改完程式碼 commit
git add ...
git commit -m "..."

# 同時推到兩個帳號
git push origin main
git push backup main
```

或寫個 alias 簡化：

```powershell
git config alias.pushall '!git push origin main && git push backup main'

# 之後一行解決
git pushall
```

### 模式 B 的日常工作流

```powershell
git push origin main         # 自動同時推兩處
```

---

## 安全提醒

### ⚠ seyenbot 帳號的權限管理

如果 seyenbot 是 bot 帳號（自動化用），考慮：

- **限制 SSH key scope**：那支第二 key 只給這台機器用，別在多處重複裝
- **開啟 2FA**：即使是 bot 帳號也別忘了
- **定期 audit**：到 <https://github.com/settings/keys> 看 key 列表，確認沒有意外多出的 key

### 不要把私鑰 commit 進 git

`.gitignore` 已經排除 `*.pem` `*.key`，但 SSH key 預設不在這個 pattern。**`~/.ssh/id_ed25519*` 永遠在你的 home 目錄，絕不在專案內，所以不會誤 commit**。但如果你習慣手動移動檔案，記得確認。

### 兩個帳號的 commit author 統一

兩個 repo 的所有 commits 應該都是 `許士彥 <seyen37@gmail.com>` —— **不需要**改成 `seyenbot`。原因：

- commit author = 「誰寫的」（你本人）
- GitHub 帳號 = 「push 到哪個帳號」（路由）
- 這兩件事是分開的，不要混淆
- 統一 author 對版權保護**有利**——兩個 repo 都顯示同一個原作者

驗證：
```powershell
git log --pretty=format:'%h %an <%ae> %s'
# 所有行都應該是 許士彥 <seyen37@gmail.com>
```

---

## 故障排除

### 「Permission denied (publickey)」push 到 backup 時

檢查順序：
1. `ssh -T git@github-backup` — 是否回 `Hi seyenbot!`？沒回就是 SSH config 設錯
2. `git remote -v` — backup URL 是 `git@github-backup:seyenbot/...` 而**不是** `git@github.com:...`
3. seyenbot 帳號的 Settings → Keys 真的有第二支公鑰嗎

### 「remote: Repository not found」

seyenbot 帳號下還沒建 stroke-order repo。回 Step 3。

### push 到 backup 慢 / 卡住

兩個 remote 各自網路請求，加總要兩倍時間是正常的。如果單個 remote 慢，可能網路不穩定。

### CI 在兩邊都跑變很吵

有兩種策略：
- **只在 seyen37 主帳號開 Actions**：seyenbot 是 cold backup，不跑 CI
  - 到 seyenbot 的 repo Settings → Actions → General → Disable
- **兩邊都跑**（預設）：每次 push 都有兩份 CI 紀錄，當作雙重時戳證據

---

## 額外做法：多向 mirror

如果你之後想加第三、第四個 backup（譬如 GitLab、Codeberg），同樣模式：

```powershell
# 加 GitLab
git remote add gitlab git@gitlab.com:seyen37/stroke-order.git

# 一次推三處（模式 A 的 alias）
git config alias.pushall '!git push origin main && git push backup main && git push gitlab main'
git pushall
```

GitLab 跟 GitHub 一樣需要設 SSH key + 新增 repo。

---

## 總結

| Step | 做什麼 |
|---|---|
| 1 | `ssh-keygen -f $HOME\.ssh\id_ed25519_seyenbot` |
| 2 | 公鑰貼到 seyenbot 帳號 GitHub Settings → Keys |
| 3 | seyenbot 帳號建 `stroke-order` 空 repo |
| 4 | 寫 `~/.ssh/config` 區分 `github.com` 跟 `github-backup` |
| 5 | `ssh -T git@github.com` + `ssh -T git@github-backup` 雙驗證 |
| 6 | 模式 A：`git remote add backup git@github-backup:seyenbot/stroke-order.git` |
| 7 | `git push backup main` + `git push backup v0.13.0` |
| 之後 | 每次 push 都記得推兩個 remote（或設 alias）|
