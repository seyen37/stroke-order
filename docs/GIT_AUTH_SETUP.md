# 本機 Git 連 GitHub 認證設定

最後更新：2026-04-26

GitHub 不再接受密碼登入（2021 起），必須用以下其中一種：

| 方式 | 推薦度 | 適用 |
|---|---|---|
| **SSH key** | ⭐⭐⭐⭐⭐ | 個人開發機長期使用、設定一次永久有效 |
| **HTTPS + Personal Access Token (PAT)** | ⭐⭐⭐ | 公司網路擋 SSH port、暫時用、CI 環境 |
| GitHub CLI (`gh auth login`) | ⭐⭐⭐⭐ | 最簡單，但要裝 `gh` |

下面**主推薦 SSH**，下方也附 HTTPS PAT 跟 GitHub CLI 備用。

---

## 方式 1（推薦）：SSH key

### Step 1：檢查是否已有 SSH key

```bash
ls -la ~/.ssh/
```

看有沒有 `id_ed25519` 或 `id_rsa` 之類的檔案：

| 檔案名 | 角色 |
|---|---|
| `id_ed25519` | 你的「私鑰」（不可分享）|
| `id_ed25519.pub` | 你的「公鑰」（可貼到 GitHub）|
| `known_hosts` | 已認可的 host 紀錄 |

**有 → 跳到 Step 3**。**沒有 → Step 2**。

### Step 2：產生新的 SSH key（一次性，三作業系統通用）

```bash
ssh-keygen -t ed25519 -C "seyen37@gmail.com"
```

過程會問：
- **「Enter file in which to save the key」**：直接按 Enter 用預設 `~/.ssh/id_ed25519`
- **「Enter passphrase」**：可留空（更方便）或設個密碼（更安全；macOS Keychain / Windows Credential Manager 會幫你記住，不用每次輸入）

完成後會產生兩個檔案：
- `~/.ssh/id_ed25519`（私鑰）— **絕不分享、絕不 commit**
- `~/.ssh/id_ed25519.pub`（公鑰）— 等下要貼到 GitHub

### Step 3：複製公鑰

#### macOS
```bash
pbcopy < ~/.ssh/id_ed25519.pub
# 公鑰已複製到剪貼簿
```

#### Linux
```bash
cat ~/.ssh/id_ed25519.pub
# 用滑鼠選取整行（從 ssh-ed25519 開頭到 email 結尾）複製
```

或裝 `xclip`：
```bash
xclip -sel clip < ~/.ssh/id_ed25519.pub
```

#### Windows（PowerShell / Git Bash）
```powershell
Get-Content ~/.ssh/id_ed25519.pub | Set-Clipboard
# 或
cat ~/.ssh/id_ed25519.pub | clip
```

### Step 4：把公鑰貼到 GitHub

1. 開瀏覽器到 <https://github.com/settings/keys>
2. 點右上「**New SSH key**」
3. 表單填：
   - **Title**: 隨便取個記得是哪台機器的名字（例：`MacBook 2024` / `Home Desktop`）
   - **Key type**: Authentication Key（預設）
   - **Key**: 貼上剛剛複製的公鑰
4. 按「**Add SSH key**」
5. 可能會要求重新輸入 GitHub 密碼確認

### Step 5：啟動 ssh-agent + 加入 key（macOS / Linux）

#### macOS
```bash
# macOS Sequoia / Ventura / Monterey 內建 ssh-agent
eval "$(ssh-agent -s)"

# 加 key 到 agent + Apple Keychain（記住 passphrase）
ssh-add --apple-use-keychain ~/.ssh/id_ed25519

# 讓 ~/.ssh/config 自動使用 keychain
cat >> ~/.ssh/config <<'EOF'
Host github.com
  AddKeysToAgent yes
  UseKeychain yes
  IdentityFile ~/.ssh/id_ed25519
EOF
```

#### Linux
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

#### Windows（Git Bash）
```bash
# 啟動 OpenSSH agent
eval `ssh-agent`
ssh-add ~/.ssh/id_ed25519
```

或在 PowerShell（管理員）：
```powershell
# 一次性開啟自動啟動
Set-Service ssh-agent -StartupType Automatic
Start-Service ssh-agent
ssh-add ~/.ssh/id_ed25519
```

### Step 6：驗證連線

```bash
ssh -T git@github.com
```

預期看到：
```
Hi seyen37! You've successfully authenticated, but GitHub does not provide shell access.
```

第一次會問「Are you sure you want to continue connecting」→ 輸入 `yes`。

**到這一步成功就完成了**。日後 `git clone git@github.com:...` / `git push` 都會自動用 SSH key，不會再問密碼。

---

## 方式 2（替代）：HTTPS + Personal Access Token (PAT)

適用情境：公司網路擋 SSH（22/443 port）、CI 環境、不想設 SSH key。

### Step 1：產生 PAT

1. 開 <https://github.com/settings/tokens>
2. 點「**Generate new token**」→ 選「**Generate new token (classic)**」
   - 注意有兩種：classic 跟 fine-grained。**個人專案用 classic 較單純**
3. 表單填：
   - **Note**: 取個名（例：`stroke-order push from MBP`）
   - **Expiration**: 自己選（**No expiration** = 永久；或 90 天定期更新）
   - **Scopes**: 勾**至少這幾個**：
     - ☑ `repo`（整組，含 push / pull）
     - ☑ `workflow`（讓你能改 GitHub Actions workflow）
4. 按「**Generate token**」
5. **馬上複製**那串 `ghp_xxxx...`（**離開頁面就再也看不到**）

### Step 2：把 token 配給 git（兩種方法擇一）

#### 方法 A：用 git credential helper（推薦，記住一次）

```bash
# macOS — 用 keychain
git config --global credential.helper osxkeychain

# Linux — 用 libsecret（GNOME / KDE）
git config --global credential.helper /usr/share/doc/git/contrib/credential/libsecret/git-credential-libsecret

# Windows — Git for Windows 預設已配 Credential Manager
git config --global credential.helper manager
```

第一次 push 時會跳出帳號密碼提示：
- **Username**: `seyen37`
- **Password**: 貼**剛剛複製的 PAT 字串**（不是 GitHub 登入密碼）

之後 keychain / credential manager 會幫你記住。

#### 方法 B：直接在 remote URL 嵌入（簡單但較不安全）

```bash
git remote set-url origin https://seyen37:ghp_xxxxxxxxxxxxxx@github.com/seyen37/stroke-order.git
```

⚠ 缺點：PAT 會出現在 `git remote -v` 跟 shell history。**不推薦長期使用**。

### Step 3：驗證

```bash
git ls-remote https://github.com/seyen37/stroke-order.git
# 列出遠端 branches → 認證成功
```

---

## 方式 3（最簡）：GitHub CLI

如果你習慣用 `gh` 命令：

### macOS
```bash
brew install gh
```

### Windows
```powershell
winget install --id GitHub.cli
```

### Linux
```bash
# Ubuntu / Debian
sudo apt install gh

# 或直接：
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/etc/apt/trusted.gpg.d/githubcli.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/trusted.gpg.d/githubcli.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list
sudo apt update && sudo apt install gh
```

### 登入
```bash
gh auth login
# 互動式：
#   ? Where do you use GitHub? → GitHub.com
#   ? What is your preferred protocol for Git operations? → SSH（推薦）
#   ? Generate a new SSH key to add to your GitHub account? → Yes
#   ? How would you like to authenticate? → Login with a web browser
# (跑出個 8 字元代碼，叫你開瀏覽器貼上去)
```

完成後 `gh` + `git` 都可以用。

---

## 設定 Git 全域 author（重要：跟版權保護相關）

不論用哪種認證方式，**commit author 跟 GitHub 帳號是兩件不同事**——必須同步：

```bash
git config --global user.name  "許士彥"
git config --global user.email "seyen37@gmail.com"
```

驗證：
```bash
git config --global --list | grep user
# user.name=許士彥
# user.email=seyen37@gmail.com
```

> ⚠ 若你的 GitHub 帳號的 primary email 不是 `seyen37@gmail.com`，commit 在 GitHub 上不會跟你的頭像關聯（顯示為灰色頭像）。  
> 若你**不想公開你的 email**，GitHub 提供 noreply 替代：到 <https://github.com/settings/emails> 啟用「Keep my email addresses private」，會給你一個 `12345678+seyen37@users.noreply.github.com`，把這個用在 `git config user.email`。

---

## 故障排除

### Q: ssh -T 卡住沒回應 / Connection refused

公司網路擋 22 port。改用 SSH over HTTPS（443 port）：

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  Hostname ssh.github.com
  Port 443
  User git
EOF

ssh -T git@github.com
```

### Q: Permission denied (publickey)

可能原因：
1. 公鑰還沒貼到 GitHub → 重做 Step 4
2. ssh-agent 沒載入 key → 重做 Step 5
3. SSH 用錯 key 檔 → `ssh -vT git@github.com` 看 debug log

### Q: HTTPS 一直要求密碼

credential.helper 沒設好。檢查：
```bash
git config --global --get credential.helper
```
若空白就配一個（見方式 2 Step 2）。

### Q: 我換新電腦了
SSH key 是綁在電腦上的。新電腦重做 Step 1–6，貼一個新的公鑰到 GitHub Settings → Keys（**舊電腦的 key 留著沒關係，可以共存**；想撤銷可以從同一頁刪除）。

### Q: 怎麼確認當前 push 用哪種認證？
```bash
git remote get-url origin

# 看 URL 開頭：
# git@github.com:...    → SSH
# https://github.com/... → HTTPS（看 credential.helper 配什麼）
```

切換：
```bash
# HTTPS → SSH
git remote set-url origin git@github.com:seyen37/stroke-order.git

# SSH → HTTPS
git remote set-url origin https://github.com/seyen37/stroke-order.git
```

---

## 安全建議

| ⚠ 絕不能做的事 | 建議做法 |
|---|---|
| 把私鑰（id_ed25519，沒有 .pub）分享給別人 | 永遠保留在自己電腦 |
| 把 PAT commit 進 git | 用 git credential helper |
| 公開分享 .ssh/ 整個資料夾 | 私鑰在裡面，只能備份到加密媒體 |
| 在公用電腦設定 SSH key | 用 HTTPS PAT，用完撤銷 |

---

## 完成設定後回到 push 流程

完成本檔的設定後，回到 [`PUSH_TO_GITHUB.md`](PUSH_TO_GITHUB.md) Step 3 開始執行：`git init -b main` → 4 個分批 commit → push。

驗證一行指令：
```bash
ssh -T git@github.com
# 顯示 "Hi seyen37! You've successfully authenticated..." 就 OK
```
