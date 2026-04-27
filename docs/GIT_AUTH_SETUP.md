---
layout: default
---

# ?祆? Git ??GitHub 隤?閮剖?

?敺?堆?2026-04-26

GitHub 銝??亙?撖Ⅳ?餃嚗?021 韏瘀?嚗??隞乩??嗡葉銝蝔殷?

| ?孵? | ?刻摨?| ?拍 |
|---|---|---|
| **SSH key** | 潃?潃?潃?| ?犖?璈?蝙?具身摰?甈⊥偶銋???|
| **HTTPS + Personal Access Token (PAT)** | 潃?潃?| ?砍蝬脰楝??SSH port???I ?啣? |
| GitHub CLI (`gh auth login`) | 潃?潃? | ?蝪∪嚗?閬? `gh` |

銝**銝餅??SSH**嚗??嫣???HTTPS PAT 頝?GitHub CLI ???
---

## ?孵? 1嚗?佗?嚗SH key

### Step 1嚗炎?交?血歇??SSH key

```bash
ls -la ~/.ssh/
```

??瘝? `id_ed25519` ??`id_rsa` 銋???獢?

| 瑼???| 閫 |
|---|---|
| `id_ed25519` | 雿????啜?銝?澈嚗
| `id_ed25519.pub` | 雿???啜??航票??GitHub嚗
| `known_hosts` | 撌脰??舐? host 蝝??|

**????頝喳 Step 3**??*瘝? ??Step 2**??
### Step 2嚗???SSH key嚗?甈⊥改?銝?璆剔頂蝯梢嚗?
```bash
ssh-keygen -t ed25519 -C "seyen37@gmail.com"
```

????嚗?- **?nter file in which to save the key??*嚗?交? Enter ?券?閮?`~/.ssh/id_ed25519`
- **?nter passphrase??*嚗?征嚗?嫣噶嚗?閮剖?蝣潘??游??剁?macOS Keychain / Windows Credential Manager ?鼠雿?雿?銝瘥活頛詨嚗?
摰?敺??Ｙ??拙?獢?
- `~/.ssh/id_ed25519`嚗??堆???**蝯??澈??銝?commit**
- `~/.ssh/id_ed25519.pub`嚗?堆???蝑?閬票??GitHub

### Step 3嚗?鋆賢??
#### macOS
```bash
pbcopy < ~/.ssh/id_ed25519.pub
# ?祇撌脰?鋆賢?芾票蝪?```

#### Linux
```bash
cat ~/.ssh/id_ed25519.pub
# ?冽?曌?銵?敺?ssh-ed25519 ???email 蝯偏嚗?鋆?```

?? `xclip`嚗?```bash
xclip -sel clip < ~/.ssh/id_ed25519.pub
```

#### Windows嚗owerShell / Git Bash嚗?```powershell
Get-Content ~/.ssh/id_ed25519.pub | Set-Clipboard
# ??cat ~/.ssh/id_ed25519.pub | clip
```

### Step 4嚗??祇鞎澆 GitHub

1. ?汗?典 <https://github.com/settings/keys>
2. 暺銝?*New SSH key**??3. 銵典憛恬?
   - **Title**: ?其噶??敺?芸璈??摮?靘?`MacBook 2024` / `Home Desktop`嚗?   - **Key type**: Authentication Key嚗?閮哨?
   - **Key**: 鞎潔???銴ˊ???4. ??*Add SSH key**??5. ?航??瘙??啗撓??GitHub 撖Ⅳ蝣箄?

### Step 5嚗???ssh-agent + ? key嚗acOS / Linux嚗?
#### macOS
```bash
# macOS Sequoia / Ventura / Monterey ?批遣 ssh-agent
eval "$(ssh-agent -s)"

# ??key ??agent + Apple Keychain嚗?雿?passphrase嚗?ssh-add --apple-use-keychain ~/.ssh/id_ed25519

# 霈?~/.ssh/config ?芸?雿輻 keychain
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

#### Windows嚗it Bash嚗?```bash
# ?? OpenSSH agent
eval `ssh-agent`
ssh-add ~/.ssh/id_ed25519
```

? PowerShell嚗恣?嚗?
```powershell
# 銝甈⊥折??????Set-Service ssh-agent -StartupType Automatic
Start-Service ssh-agent
ssh-add ~/.ssh/id_ed25519
```

### Step 6嚗?霅??

```bash
ssh -T git@github.com
```

???嚗?```
Hi seyen37! You've successfully authenticated, but GitHub does not provide shell access.
```

蝚砌?甈⊥??re you sure you want to continue connecting?? 頛詨 `yes`??
**?圈?甇交??停摰?鈭?*?敺?`git clone git@github.com:...` / `git push` ?賣??芸???SSH key嚗?????蝣潦?
---

## ?孵? 2嚗隞??嚗TTPS + Personal Access Token (PAT)

?拍??嚗?貊雯頝舀? SSH嚗?2/443 port嚗I ?啣????唾身 SSH key??
### Step 1嚗??PAT

1. ??<https://github.com/settings/tokens>
2. 暺?*Generate new token**?? ?詻?*Generate new token (classic)**??   - 瘜冽??蝔殷?classic 頝?fine-grained??*?犖撠???classic 頛蝝?*
3. 銵典憛恬?
   - **Note**: ??嚗?嚗stroke-order push from MBP`嚗?   - **Expiration**: ?芸楛?賂?**No expiration** = 瘞訾?嚗? 90 憭拙???堆?
   - **Scopes**: ??*?喳??嗾??*嚗?     - ??`repo`嚗蝯???push / pull嚗?     - ??`workflow`嚗?雿??GitHub Actions workflow嚗?4. ??*Generate token**??5. **擐砌?銴ˊ**??葡 `ghp_xxxx...`嚗?*?ａ??撠勗?銋?銝**嚗?
### Step 2嚗? token ?策 git嚗蝔格瘜?銝嚗?
#### ?寞? A嚗 git credential helper嚗?佗?閮?銝甈∴?

```bash
# macOS ????keychain
git config --global credential.helper osxkeychain

# Linux ????libsecret嚗NOME / KDE嚗?git config --global credential.helper /usr/share/doc/git/contrib/credential/libsecret/git-credential-libsecret

# Windows ??Git for Windows ?身撌脤? Credential Manager
git config --global credential.helper manager
```

蝚砌?甈?push ??頝喳撣唾?撖Ⅳ?內嚗?- **Username**: `seyen37`
- **Password**: 鞎?*??銴ˊ??PAT 摮葡**嚗???GitHub ?餃撖Ⅳ嚗?
銋? keychain / credential manager ?鼠雿?雿?
#### ?寞? B嚗?亙 remote URL 撋嚗陛?桐?頛?摰嚗?
```bash
git remote set-url origin https://seyen37:ghp_xxxxxxxxxxxxxx@github.com/seyen37/stroke-order.git
```

??蝻粹?嚗AT ??曉 `git remote -v` 頝?shell history??*銝?阡?蝙??*??
### Step 3嚗?霅?
```bash
git ls-remote https://github.com/seyen37/stroke-order.git
# ??垢 branches ??隤???
```

---

## ?孵? 3嚗?蝪∴?嚗itHub CLI

憒?雿??? `gh` ?賭誘嚗?
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

# ??伐?
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/etc/apt/trusted.gpg.d/githubcli.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/trusted.gpg.d/githubcli.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list
sudo apt update && sudo apt install gh
```

### ?餃
```bash
gh auth login
# 鈭?撘?
#   ? Where do you use GitHub? ??GitHub.com
#   ? What is your preferred protocol for Git operations? ??SSH嚗?佗?
#   ? Generate a new SSH key to add to your GitHub account? ??Yes
#   ? How would you like to authenticate? ??Login with a web browser
# (頝??8 摮?隞?Ⅳ嚗雿??汗?刻票銝)
```

摰?敺?`gh` + `git` ?賢隞亦??
---

## 閮剖? Git ?典? author嚗?閬?頝?甈?霅瑞??

銝??典蝔株?霅撘?**commit author 頝?GitHub 撣唾??臬隞嗡???**????甇伐?

```bash
git config --global user.name  "閮勗ㄚ敶?
git config --global user.email "seyen37@gmail.com"
```

撽?嚗?```bash
git config --global --list | grep user
# user.name=閮勗ㄚ敶?# user.email=seyen37@gmail.com
```

> ???乩???GitHub 撣唾???primary email 銝 `seyen37@gmail.com`嚗ommit ??GitHub 銝???雿??剖??嚗＊蝷箇?啗?剖?嚗? 
> ?乩?**銝?祇?雿? email**嚗itHub ?? noreply ?蹂誨嚗 <https://github.com/settings/emails> ??eep my email addresses private???策雿???`12345678+seyen37@users.noreply.github.com`嚗????`git config user.email`??
---

## ???

### Q: ssh -T ?∩?瘝???/ Connection refused

?砍蝬脰楝??22 port???SSH over HTTPS嚗?43 port嚗?

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

?航??嚗?1. ?祇??鞎澆 GitHub ???? Step 4
2. ssh-agent 瘝???key ???? Step 5
3. SSH ?券 key 瑼???`ssh -vT git@github.com` ??debug log

### Q: HTTPS 銝?渲?瘙?蝣?
credential.helper 瘝身憟賬炎?伐?
```bash
git config --global --get credential.helper
```
?亦征?賢停????閬撘?2 Step 2嚗?
### Q: ???圈?虫?
SSH key ?舐??券?虫???餉?? Step 1??嚗票銝???啣 GitHub Settings ??Keys嚗?*??衣? key ??瘝?靽??臭誑?勗?**嚗?日?臭誑敺?銝??歹???
### Q: ?獐蝣箄??嗅? push ?典蝔株?霅?
```bash
git remote get-url origin

# ??URL ?嚗?# git@github.com:...    ??SSH
# https://github.com/... ??HTTPS嚗? credential.helper ??暻潘?
```

??嚗?```bash
# HTTPS ??SSH
git remote set-url origin git@github.com:seyen37/stroke-order.git

# SSH ??HTTPS
git remote set-url origin https://github.com/seyen37/stroke-order.git
```

---

## 摰撱箄降

| ??蝯??賢??? | 撱箄降?? |
|---|---|
| ???堆?id_ed25519嚗???.pub嚗?鈭怎策?乩犖 | 瘞賊?靽??刻撌梢??|
| ??PAT commit ??git | ??git credential helper |
| ?祇??澈 .ssh/ ?游??冗 | 蝘?刻ㄐ?ｇ??芾?遢?啣?撖?擃?|
| ?典?券?西身摰?SSH key | ??HTTPS PAT嚗摰??|

---

## 摰?閮剖?敺???push 瘚?

摰??祆??身摰?嚗???[`PUSH_TO_GITHUB.md`](PUSH_TO_GITHUB.md) Step 3 ???瑁?嚗git init -b main` ??4 ????commit ??push??
撽?銝銵?隞歹?
```bash
ssh -T git@github.com
# 憿舐內 "Hi seyen37! You've successfully authenticated..." 撠?OK
```

