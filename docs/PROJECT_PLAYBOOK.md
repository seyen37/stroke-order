# 個人專案 Playbook

> 許士彥（Hsu Shih-Yen）GitHub 專案的標準化實踐。
>
> 本文件凝結了個人多個開源專案累積出來的最佳實踐：智慧財產權保護、雙帳號備份、決策日誌自動化、與 AI 協作時的工作紀錄習慣。
>
> **本文件設計為「**通用、可被任何新 repo 直接複製套用**」**：所有自身專屬的歷史紀錄、具體案例 metadata 都另外收錄在 source-of-truth repo 的 [`HISTORY.md`](HISTORY.md)。
>
> **位置慣例**：本文件在 source-of-truth repo（`personal-playbook`）放在 root；複製到其他新專案時放 `docs/PROJECT_PLAYBOOK.md`，避免擾亂主結構。複製後**請勿一併抄走** `HISTORY.md`（那是 source-of-truth repo 自身的歷史，新 repo 應有自己的歷史）。

---

## 目錄

1. [新專案第一天清單](#一新專案第一天清單)
2. [智慧財產權三件套](#二智慧財產權三件套)
3. [多帳號 GitHub 備份](#三多帳號-github-備份)
4. [工作紀錄自動化規則](#四工作紀錄自動化規則)
5. [決策日誌自動化規則](#五決策日誌自動化規則)
6. [**資料源稽核（Source-of-Truth Audit）**](#六資料源稽核source-of-truth-audit)
7. [公開前審查清單](#七公開前審查清單)
8. [長期維護習慣](#八長期維護習慣)
9. [附錄：可複製模板](#九附錄可複製模板)
10. [與 AI 協作時的 prompt 片段](#十與-ai-協作時的-prompt-片段)
11. [給未來自己的話](#十一給未來自己的話)

---

## 一、新專案第一天清單

不必一次做完，但這個順序最少摩擦：

### 1.1 本機 repo 初始化
- [ ] `git init`
- [ ] 建立 `README.md`（基本骨架見附錄 A）
- [ ] 建立 `LICENSE`（MIT 或其他，見附錄 B）
- [ ] 建立 `.gitignore`（語言相關，見附錄 C）
- [ ] 建立 `docs/` 資料夾
- [ ] 建立 `docs/decisions/` 資料夾 + `_TEMPLATE.md`（見附錄 D）

### 1.2 第一次 commit
```powershell
git add README.md LICENSE .gitignore docs/
git commit -m "init: project skeleton"
```

### 1.3 推到雙 GitHub 帳號
- [ ] 在 seyen37 建立空 repo
- [ ] 在 seyenbot 建立空 repo（同名）
- [ ] 設定雙 remote（見「三、多帳號 GitHub 備份」）
- [ ] `git push origin main && git push backup main`

### 1.4 開啟基礎建設
- [ ] GitHub Actions CI workflow（見附錄 E）
- [ ] GitHub Pages（如果專案會公開）
- [ ] 確認 LICENSE 在 GitHub repo 首頁可被識別為 MIT

### 1.5 寫第一份決策日誌
即使是「我為什麼選這個技術 stack」也值得寫一份 `docs/decisions/YYYY-MM-DD_init.md`。**這是長期專案最有價值的累積。**

---

## 二、智慧財產權三件套

著作權保護的關鍵是建立**身份鏈**——同一個身份在多處出現、互相印證。三個必設位置：

### 2.1 LICENSE（法律文件）

**標準格式**：
```
Copyright (c) 2026 許士彥 (Hsu Shih-Yen) (https://github.com/seyen37)
```

**要素**（缺一不可）：
- 中文實名（法律文件中可指認的個人）
- 羅馬拼音（國際合作 / 授權詢問友善）
- GitHub profile URL（活的證據鏈，含 commit 時序）
- 年份（採用首次公開年；長期專案不寫範圍）

**避免**：
- 用 handle/暱稱（`(seyen37)` 不夠正式）
- 寫 email（會被爬蟲爬走）
- 寫年份範圍（除非真的需要強調歷史）

> 📌 **email 處理的 layer 區分**：LICENSE / README 內文**不寫實名 email**；但 git config `user.email`（commit metadata 那一層）是另一回事、可使用 **GitHub noreply email**（見 §3.7 step 5）——兼顧實名追溯與隱私保護。

### 2.2 README.md（讀者第一印象）

**開發脈絡段落**範本：
```markdown
本專案由 **許士彥（Hsu Shih-Yen，<https://github.com/seyen37>）獨立設計與開發**，
[簡述開發歷程：phase 數量、測試數、達成 milestone]。

詳細設計脈絡見 [`docs/decisions/`](docs/decisions/) — 每個關鍵設計決策都有
對應的決策日誌，記錄當時遇到的困難、選項評估、與最終解法。
```

### 2.3 docs/index.html footer（GitHub Pages 文件站）

```html
<footer>
  © 2026 許士彥 (Hsu Shih-Yen) ·
  <a href="https://github.com/seyen37">github.com/seyen37</a> ·
  本網站由 GitHub Pages 託管
</footer>
```

### 2.4 為什麼三處同步重要

每處角色不同：
- **LICENSE** = 法律基礎（最權威）
- **README** = 讀者進入點（最常被閱讀）
- **footer** = 文件站每頁可見（曝光度最高）

三處用一致格式，建立**多點互相印證**的身份鏈——任何人質疑著作權歸屬時，三處都導向同一個可驗證身份。

---

## 三、多帳號 GitHub 備份

### 3.1 為什麼要雙帳號

- **冗餘**：主帳號被鎖、ban、無法登入時，備份帳號是保險
- **時序證據**：兩處 commit 時間戳互相印證，比單一來源強
- **可分流**：若以後有商業化，主帳號 public、備份帳號 private 可彈性切換

### 3.2 SSH key per 帳號設定

**為每個帳號各產一支 ed25519 key**（完整 PowerShell 命令見 §3.7 step 1）：
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_seyen37
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_seyenbot
```

**`~/.ssh/config` Host alias**（採對稱命名，host 名稱直接含帳號）：
```
Host github.com-seyen37
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_seyen37
  IdentitiesOnly yes

Host github.com-seyenbot
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_seyenbot
  IdentitiesOnly yes
```

各帳號 GitHub 設定 → SSH and GPG keys → 加入對應 public key。測試命令見 §3.7 step 4。

### 3.3 雙 remote 設定

```bash
git remote add origin git@github.com-seyen37:seyen37/PROJECT.git
git remote add backup git@github.com-seyenbot:seyenbot/PROJECT.git
```

### 3.4 一行同步推送 alias

```bash
git config --global alias.pa '!git push origin main && git push backup main'
```

之後 `git pa` 一行同步推兩個 remote。`&&` 鏈意味著 origin 失敗時 backup 不會跑——這是故意的（讓你先處理 origin 問題）。

> **命名建議**：建議所有 host alias 都用 `github.com-<account>` **對稱命名**（host 名稱與 GitHub URL pattern 對應），避免「主帳號是 `github.com-X`、備份帳號是 `github-backup`」這種不對稱命名 — 跨電腦設定時最不容易出錯、配套 SOP 也較一致。

### 3.5 新 repo 完整 setup 七步

開新 repo（不論開源工具、個人筆記、工作專案）都依此 SOP：

**1. 在兩個 GitHub 帳號各建空 repo**（同名）
- **seyen37**（主）：依專案性質選 Public / Private
- **seyenbot**（備份）：永遠 Private（純備份）
- 兩邊都**不勾** README / .gitignore / LICENSE（本地會建）

**2. 本地初始化 + 第一次 commit**
```powershell
cd C:\path\to\<your-project>
git init
git branch -M main
"# my-project" | Out-File README.md -Encoding utf8
git add .
git commit -m "init: project skeleton"
```

**3. 加 origin + backup 兩個 remote**
```powershell
git remote add origin git@github.com-seyen37:seyen37/<repo>.git
git remote add backup git@github.com-seyenbot:seyenbot/<repo>.git
git remote -v   # 確認 4 行（origin/backup 各 fetch+push）
```

**4. 第一次 push 兩邊**（建立 main tracking）
```powershell
git push -u origin main
git push -u backup main
```

**5. 補必備檔案**（依 §一、§二）
- LICENSE（標真名 `許士彥 (Hsu Shih-Yen)`）
- .gitignore（語言對應 + 大檔排除）
- docs/decisions/_TEMPLATE.md
- 第一份 init 決策日誌

**6. 之後每次工作流**
```powershell
git pull         # 開工
# ... 做事 ...
git add .
git commit -m "..."
git pa           # 收工，自動推 origin + backup
```

**7.（可選）啟用 GitHub Pages**
主帳號 repo Settings → Pages → main / root → Save。等 1-3 分鐘訪問 `https://seyen37.github.io/<repo>/`。

### 3.6 常見錯誤與排查

| 症狀 | 原因 | 解法 |
|---|---|---|
| `git pa` 報 `'backup' does not appear to be a git repository` | 沒設 backup remote | 補做 §3.5 step 3 |
| `git push` 卡在 password | SSH key 沒設或 host alias 不對 | 檢查 `~/.ssh/config` + `ssh -T git@github.com-seyen37` 測試 |
| origin 有兩個 push URL（之前用 `set-url --add --push` 設過）| 與 git pa alias 重疊 → seyenbot 收到 2 次 push（重複但無害）| `git config --unset-all remote.origin.pushurl` 清掉，純靠 alias 推兩邊 |
| repo 在 GitHub 改名後 `git pa` 推到舊 URL | 本地 git remote URL 沒更新 | `git remote set-url origin git@github.com-seyen37:seyen37/<新名>.git`（backup 同樣處理）|
| `fatal: Unable to create '.git/index.lock': File exists` | 之前 git 命令異常中斷 / 編輯器仍開著 | `Remove-Item .git\index.lock -Force` 後重試（PowerShell）|
| PowerShell 把 `::` 當命令報錯 | cmd 註解符號被當成 cmdlet | PowerShell 用 `#` 當註解；複製命令時別連同註解貼進去 |

### 3.7 跨電腦初次設定（公司 / 第二台電腦）

新電腦上做 6 步（私鑰絕不從別台複製，每台各自生）：

**1. 生成兩支 SSH key**

> 💡 `-C` 是 SSH key comment、會出現在 GitHub「Settings → SSH keys」公鑰列表（**他人可見**）。建議用 `<account>+<machine-id>` 風格、**不要塞實名 email**——避免協作者透過 GitHub UI 撈到你的私人聯絡。
>
> ⚠️ **`<電腦識別>` 用通用代號**（如 `desktop1`、`laptop`、`work-pc`、`win11-2024`），**不要填家裡 / 公司的真實機名 / 暱稱**（例：「我家桌機」「公司 NB」「Mary's Mac」），避免透過公鑰列表暴露實體位置或人際關係。

```powershell
mkdir $HOME\.ssh -Force
ssh-keygen -t ed25519 -C "seyen37+desktop1" -f "$HOME\.ssh\id_ed25519_seyen37" -N '""'
ssh-keygen -t ed25519 -C "seyenbot+desktop1" -f "$HOME\.ssh\id_ed25519_seyenbot" -N '""'
```

**2. 公鑰加到對應 GitHub 帳號**
```powershell
type $HOME\.ssh\id_ed25519_seyen37.pub
# → 複製貼到 https://github.com/settings/keys（登入 seyen37）

type $HOME\.ssh\id_ed25519_seyenbot.pub
# → 切到 seyenbot 帳號，貼到 settings/keys
```

**3. 建立 `~/.ssh/config`**

`notepad $HOME\.ssh\config`，貼：
```
Host github.com-seyen37
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_seyen37
    IdentitiesOnly yes

Host github.com-seyenbot
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_seyenbot
    IdentitiesOnly yes
```

⚠️ 確認檔名是 `config` 沒有 `.txt`：
```powershell
dir $HOME\.ssh\config*
# 若顯示 config.txt：ren $HOME\.ssh\config.txt config
```

**4. 測試 SSH 連線**
```powershell
ssh -T git@github.com-seyen37   # 預期：Hi seyen37!
ssh -T git@github.com-seyenbot  # 預期：Hi seyenbot!
```

**5. 設 global git config（每台電腦各設一次）**

> ⚠️ **`user.email` 用 GitHub noreply、不要用實名 email**——commit metadata 是 public、會被 GitHub UI、`git log`、第三方爬蟲完整暴露。
>
> **取得 noreply email 的步驟**：
> 1. 登入 GitHub → 開 <https://github.com/settings/emails>
> 2. 勾選 **「Keep my email addresses private」** + **「Block command line pushes that expose my email」**（雙保險）
> 3. 該頁會顯示你的 noreply email，格式：`<numeric-id>+seyen37@users.noreply.github.com`
> 4. 複製該 email、填入下方取代 `<YOUR_NOREPLY_EMAIL>`

```powershell
git config --global alias.pa '!git push origin main && git push backup main'
git config --global user.name "seyen37"
git config --global user.email "<YOUR_NOREPLY_EMAIL>"   # 例：12345678+seyen37@users.noreply.github.com
```

**6. Clone 既有 repo 開始工作**
```powershell
git clone git@github.com-seyen37:seyen37/<repo>.git
cd <repo>
git remote add backup git@github.com-seyenbot:seyenbot/<repo>.git
git fetch backup
git pa  # 驗證雙推可用
```

### 3.8 PaaS 部署的 build vs runtime fs 模型

> 部署到免費 / 廉價 PaaS（Render free tier、Railway、Fly.io 等）時，**build phase 寫到 `$HOME/` 的檔案不會傳到 runtime container**——只有 git-checkout 路徑（如 Render 的 `/opt/render/project/src/`）才會。

#### 3.8.1 為什麼會踩雷

直觀以為「build 完成後整個 container fs 都變成 runtime fs」——錯。多數 PaaS 設計：
- **Build container**：跑 `buildCommand`，`$HOME/` 是 build user 的 ephemeral workspace，build 結束就丟
- **Runtime container**：fresh 起，**只**承襲 git checkout 路徑內的檔案

任何 build 階段下載 / 生成想 persist 到 runtime 的檔案（字型、預訓練模型、編譯快取等），**必須**寫到 git-checkout 路徑下，不要寫到 `$HOME/` 或其他「臨時」目錄。

#### 3.8.2 正確 pattern

**反例（會踩雷）**：
```yaml
buildCommand: |
  pip install -e ".[web]"
  bash scripts/fetch_assets.sh    # script 內部寫到 $HOME/.myapp/
```

**正確做法**：
```yaml
buildCommand: |
  pip install -e ".[web]"
  MYAPP_DEST=/opt/render/project/src/.assets bash scripts/fetch_assets.sh

envVars:
  - key: MYAPP_ASSETS_DIR
    value: /opt/render/project/src/.assets   # runtime 從這裡讀
```

並在 `.gitignore` 加 `.assets/`，避免本地跑 build 誤 commit 大檔。

#### 3.8.3 fetch script 的 graceful 設計

下載第三方資源時，**單一資源失敗不該 abort 整個 build**：
- 用 try-per-resource，記 `ok/fail/total` 計數
- `exit 0` 即使部分失敗——讓 app 帶著「部分功能 degraded」上線比 build 完全不過好
- 若服務有 fallback path（前端 fallback 到濾鏡 / 伺服器側 fallback 到 default），這個設計尤其有效

> 📜 **真實案例**：見各專案決策日誌（搜尋 `render_fetch` 或 `build runtime fs`）。

### 3.9 跨 AI session / 跨電腦並行工作 SOP

> 同一個 repo 被多台電腦或多場 AI session 並行更新時，會發生 push 拒絕 / 章節編號碰撞 / 工作覆寫等衝突。下面 4 條 SOP 預防。

#### 3.9.1 每場 session 開工前必跑

```powershell
git fetch                # 拉 remote 變動
git status               # 確認本地 vs remote 差距
git log --oneline --decorate -5    # 看 remote 是否多出未知 commit
```

❌ 不要假設 local 是最新——另一台電腦或另一場 AI session 可能在你不知道的時候 push 過 commit。

#### 3.9.2 動筆加新章節編號前先 grep

```powershell
# 之前在編 §8.5，加新章節前確認 §8.x 哪個是空編號
grep "^### 8\." PROJECT_PLAYBOOK.md
```

❌ 不要看到「§8.4 是最後一條」就直接加 §8.5——另一場 session 可能也加了 §8.5（不同內容）。

#### 3.9.3 破壞性 git 操作前用 `format-patch` 備份

`rebase`、`reset --hard`、`force push` 之前：

```powershell
# 把本地 unpushed commits 存成 patch（永不丟失）
git format-patch <base>..HEAD --stdout > C:\path\to\backup.patch
```

萬一操作失敗或發現遠端版本更好，可用 `git apply backup.patch` 還原本地工作。**5 秒備份 = 永不後悔**。

#### 3.9.4 發現 diverge 時的處理順序

1. **先理解** remote 多了什麼：`git log --oneline --graph --all -10` 看 commit 主題
2. **判斷是否重疊**：commit message 提到的章節 / 主題是否與本場工作重疊？
3. **重疊高** → reset to remote + cherry-pick 本場獨特部分（昨夜 stroke-order × personal-playbook 並行整合即此模式）
4. **重疊低** → 標準 `pull --rebase` 即可
5. **完全衝突** → 暫停、做差異分析、寫整合 plan、再動手

> 📜 **真實案例**：見各專案決策日誌（搜尋 `divergence` 或 `cross-session race`）。

---

## 四、工作紀錄自動化規則

### 4.1 核心規則

**每次工作結束時，自動寫工作紀錄**——不需 prompt，AI 助手應主動完成。

存放位置：
- 整段：`docs/WORK_LOG_YYYY-MM-DD.md`（單日總結）
- 細節：`docs/decisions/YYYY-MM-DD_topic.md`（決策流）

### 4.2 工作紀錄結構

```markdown
# YYYY-MM-DD 工作紀錄

> 範圍：今日工作主題（一句話）
> 對應 commits: [hash] [一行 subject]

## 完成項目

- [ ] X-1 任務名稱（測試 N 條 ✅）
- [ ] X-2 任務名稱
- ...

## 數字總結

| 維度 | 數字 |
|---|---|
| 新增模組 | N |
| 新增測試 | N |
| 修改檔案 | N |
| 工作時長 | ~N 小時 |

## 對長期專案的影響

簡短描述今日對 roadmap 的位置與影響。
```

### 4.3 何時寫

- **每個工作 session 結束時**（不論完成度）
- **每個 phase 完成時**（額外寫 `docs/HISTORY.md` 條目）
- **每個 release 時**（加上 release notes）

### 4.4 何時不寫

- 純調查 / 學習（沒有 code 變更）
- 微小 typo 修正（單字換掉）
- 純配置調整（環境變數改動）

### 4.5 Backfill 規則

**未寫的 work log 不是 lost forever**。事後 retrospective 仍可重建——這個彈性消除「沒當天寫就放棄」的拖延陷阱。

backfill 的 source materials（可從中還原時序）：
- 該日相關的 decision logs
- `git log --since=<date> --until=<date>` 的 commit 列表
- commit messages（特別是含 phase/task ID 的）
- chat / email / slack 該日的對話紀錄（若可取得）

backfill 的格式約束：
- 標明 **「補寫日期 + 從何處重建」**（避免日後誤認為當天寫的）
- 內容寬度依然走標準 work log 結構（時段 / 數字 / 影響 / 反思）
- 若某些細節真的消失了（如「當天卡了多久」），誠實寫「無紀錄」優於猜測

> 「Decision log 是 backfill 的 source of truth」這個事實，反過來強化「**decision log 值得即時寫**」的論點——它不只給未來找答案用。

---

## 五、決策日誌自動化規則

> 這是個人專案最有價值的長期累積——遠勝程式碼本身。

### 5.1 核心鐵則

**捕捉「為什麼」，不是「做了什麼」**——「做了什麼」git diff / git log 可以查；「為什麼這樣做、不那樣做」只有當下能寫。

### 5.2 何時寫

凡符合以下任一條件，就寫一份：

- 有 **2 個以上選項**且選了其中一個
- 遭遇 **debug 過程超過 30 分鐘**的 bug
- 做了 **架構決策**（會影響後續多個檔案）
- 與 **使用者偏好** 衝突需要妥協
- 採用了 **看似違反直覺** 的做法

### 5.3 標準結構（每筆決策）

```markdown
## 決策 N：標題（一句話）

**情境**：當時遇到什麼問題？

**選項**：
- A. 選項 A（含技術細節）
- B. 選項 B
- C. 選項 C

**決定**：選 X。

**考量**：
1. 為什麼 A 不行
2. 為什麼 B 不夠好
3. 為什麼 C 是甜蜜點
4. 風險 / 妥協是什麼

**教訓**：
- 通用 lesson 1
- 通用 lesson 2
```

### 5.4 檔案命名規範

兩種命名 schema 並用：

**A. 日期型**（適合單日多項決策的工作紀錄）：
```
docs/decisions/YYYY-MM-DD_topic.md

例：
docs/decisions/2026-04-27_public_deployment.md
docs/decisions/2026-04-27_808_analysis.md
docs/decisions/2026-04-28_phase_a_backend.md
```

**B. 模組型**（適合單一功能的長期演進）：
```
docs/decisions/mode_NN_topic.md
docs/decisions/infra_NN_topic.md

例：
docs/decisions/mode_01_single_char_and_ir.md
docs/decisions/infra_01_data_sources.md
```

### 5.5 整體 layout

```
docs/decisions/
├── _TEMPLATE.md              # 空白模板
├── 2026-04-26_init.md         # 日期型（首日決策）
├── 2026-04-27_phase_X.md
├── mode_01_topic.md           # 模組型
├── mode_02_topic.md
├── infra_01_topic.md
└── infra_02_topic.md
```

### 5.6 為什麼這個習慣值錢

1. **回顧時找得回來**：「半年前那個關於 X 的決定，當時為什麼這樣？」→ 翻日誌找答案
2. **新人接手友善**：未來合作者 / 接手者讀完 `docs/decisions/` 就懂專案脈絡
3. **AI 協作 context**：下次與 AI 協作時，AI 讀決策日誌可以更快理解現有 trade-offs
4. **著作權證據**：「這個設計是我獨立思考的結果」——決策日誌是時序證據鏈
5. **避免重複犯錯**：「教訓」段落會在你下次想做同樣事情時警告自己
6. **Backfill source of truth**：當 work log 來不及當天寫時，事後 retrospective 重建只能靠 decision log + git log（見 §4.5）。決策日誌寫得詳實 = 未來重建 timeline 的可能性

### 5.7 「何時不該立即實作」決策框架

決策不只是「動了什麼」，**「沒動什麼 / 為什麼不動」**同樣值得記錄，是 anti-scope-creep 的關鍵工具。

當你考慮要不要立即實作某個閃過腦海的想法時，跑這 4 題：

1. **主線該做的事都做完了嗎？** 沒做完 → 別分心
2. **有實際使用者拉力嗎？** 沒人問 → 自己用得到嗎？dogfooding 也算
3. **依賴 / 基礎建設都成熟了嗎？** 缺什麼 → 先把那邊補完
4. **新增的維護成本承擔得起嗎？** 已超 N 個 active 工作項時，再加是否合理？

四題全 yes 才動工。否則：
- 寫進 backlog（如 `SPINOFFS.md` 或 `BACKLOG.md`）
- 寫一份精簡決策日誌：**「為何此刻不做」**
- 等下次 review 時重新評估

> **「停下動作收進 backlog」本身是一個有意識的決策**，不是輸給時間。在工程上 knowing when to stop 跟 knowing when to push 同樣重要。

---

## 六、資料源稽核（Source-of-Truth Audit）

> 凡標榜「官方」「政府」「標準」「規範」的資料源，**必須回追到一手公文**。否則內容可能被中介者意外或刻意污染。

**典型風險**：第三方整理品（GitHub Gist、Wikipedia 表格、學術部落格）即使號稱來自官方，仍可能在轉錄過程中夾帶他國規範變體 — 例如以「教育部某字單」為名的整理品中混入 GB18030 變體字、看起來「99.98% 一樣」但已足以污染下游。對 Taiwan-first 專案的影響尤其嚴重。

### 6.1 何時必跑

任何時候加入新資料源——**不只是 public release 之前**。

觸發場合：
- 引用「教育部」「國家標準」「國際協議」「ISO」的字單 / 規範 / 詞典
- 從第三方整理的 GitHub repo / Gist / 學術網站 / 部落格抓資料
- 接 API 取得「政府開放資料」「百科平台資料」
- 抓 Wikipedia / Wikidata 整理表格

### 6.2 三段檢查

**A. 一手公文確認**

- [ ] 找到原始公文 / 公報 / 標準文件（PDF / 紙本掃描 / 政府網站直連）
- [ ] 第三方整理品（Gist、GitHub repo、Wikipedia 表格）只能當「線索」，不能當「資料源」
- [ ] 出版年月、版次、發布單位都明確記錄到 metadata
- [ ] 一手 URL 寫進 `source` / `url` 欄位

**B. 內容比對**

- [ ] 一手 vs 第三方逐字比對（字數、Unicode codepoint 都要對）
- [ ] 任何差異都要追蹤原因（是第三方 OCR 錯？變體污染？版本差？人為刪改？）
- [ ] 差異 ≥ 0 時，**永遠採用一手**，並把差異記錄進決策日誌
- [ ] 一手本身有 metadata bug 時（如 PDF hex/char 不一致），明示「以實際 char 為準」

**C. 區域變體完整性（Taiwan-variant integrity）**

- [ ] 確認所有字元的 Unicode codepoint 屬於目標區域標準
  - **T (Taiwan)**：依 CNS 11643 標準
  - G (PRC)：GB18030 變體（Taiwan-first 專案要避開）
  - J (Japan)：JIS 變體
  - K (Korea)：KSC 變體
  - V (Vietnam)：喃字變體
- [ ] 對近似字（外觀像但 codepoint 不同）特別留意。已知陷阱：
  - **彞 (U+5F5E, T)** vs 彝 (U+5F5D, G)
  - **汨 (U+6C68)** vs 汩 (U+6C69)
  - **過** 在 G/H/T/J/K/V 各有不同變體
- [ ] 工具：Unicode 17.0 CJK chart `https://www.unicode.org/charts/PDF/U4E00.pdf`
      字元下方 G/H/T/J/K/V 標註對應區域變體

### 6.3 抽象案例：政府字單 / 規範類整理品的變體污染

**情境**：第三方整理的「政府某字單」(Gist / GitHub repo / Wikipedia) 與**官方公文 PDF** 比對。

**典型發現**：N 字中常出現 1-2 字差異
- 第三方版：含他國規範變體（例：GB18030 / JIS / KSC 變體）
- 官方版：本國標準字（例：CNS 11643）

**結論**：**永遠採用官方一手 PDF 作為唯一資料源**，每字保留官方 metadata（如字號）追溯到原始公告。

**啟示**：「**字數一樣 ≠ 內容一樣**」、「**99.98% 相同也夠污染**」、「**0.02% 差異就是供應鏈污染的警示燈**」。

> 📜 **真實故事**：本案例的具體經歷（教育部 4808 常用字 + 彝 vs 彞 變體污染）見 [`HISTORY.md` §B.2](HISTORY.md#b2--六-資料源稽核--教育部-4808-變體污染彝-vs-彞)。

### 6.4 自動化建議

如果資料源是會反覆更新的（例如教育部每幾年公告新版字表）：

- 寫 `scripts/build_<source>.py`：從一手公文自動萃取 → 標準 JSON
- script 本身要：
  - 文件開頭 docstring 明確記錄資料源 URL + 出版日 + 版本
  - 預期 char count 在 sanity check 範圍內（避免 PDF parsing 失敗 silent fallback）
  - **Cross-check Unicode codepoint vs 實際字元**（catch PDF metadata bugs）
  - 輸出含 traceability 欄位（如官方字號、流水序號）

**通用 script 雛形**（任何 `build_<source>.py` 都建議含這幾段）：
```python
"""
Source: <一手公文 URL>
Published: <出版日 / 版本>
Authority: <發布單位>
"""
# 從官方 PDF / 一手檔案萃取
# 每筆資料附 traceability id (對應原始公告的字號 / 流水序號)
# 一筆一比對 hex metadata vs 實際內容（catch PDF parsing bugs）
# 預期 char count 在 sanity check 範圍內（避免 silent fallback）
```

### 6.5 多源 triangulation

當有 ≥ 3 份獨立一手源同時對同物件分類時（如：3 份不同的字頻語料 / 3 份不同地名拼寫指南 / 3 份不同的標準分類表），套 **consensus schema**：

```
strict   ← 三源都標 (最 conservative)
majority ← ≥ 2 源標 (平衡)
any      ← ≥ 1 源標 (最 inclusive)
none     ← 無源標 (排除)
```

**為什麼**：每個官方源各自 sampling 偏誤；三源差異本身是資訊不是雜訊。整合 schema 比「挑一個 winner」更有研究價值。

> 📜 **真實案例**：本原則衍生於 stroke-order 專案處理「教育部 4808 + NAER 99-108 字頻 + BIAU 詞典語料」三份獨立字頻一手源時——若硬挑一份當「真理」會丟掉「現代媒體頻次 vs 歷史標準」的關鍵差異，consensus schema 反而保留差異作為下游分類維度。詳見各專案決策日誌。

### 6.6 給 Future Self 的話

「為什麼花這個力氣？只是 1 個字的差異而已。」

因為個人字型 / 寫字機器人 / 教育素材 / Taiwan-first 專案都對「**這字是本國標準嗎？**」這個問題有要求。如果您的 codebase 從一開始就有 audit 習慣，這個 claim 站得住腳；如果省略了，N 年後想補 audit 會發現要回頭比對幾十個資料源——那個 cost 比現在多 100 倍。

> **「資料源頭管理是著作權保護的第一道關卡。」**

從一開始就 audit、就標 source、就比對一手公文 — **這 5 分鐘的習慣是您未來幾年內最划算的投資之一**。

---

## 七、公開前審查清單

repo 從 Private 改 Public 之前，**必跑**：

### 7.1 Secret 稽核

```bash
# 搜尋常見 secret 關鍵字
git grep -i "password\|secret\|api_key\|token\|credentials" -- ":!docs/" ":!*.md"

# 確認 .env 在 .gitignore
grep "^\.env" .gitignore
```

### 7.2 個資稽核

- [ ] commit message 沒有寫到家裡地址 / 私人電話 / 銀行帳號
- [ ] 程式碼註解沒有客戶 / 朋友本名
- [ ] 截圖 / 測試資料沒有真實個人資訊
- [ ] **`git config user.email` 用 GitHub noreply**（避免 commit metadata 暴露實名 email）
  - 取得：<https://github.com/settings/emails> → 勾「Keep my email addresses private」
  - 設定：`git config --global user.email "<numeric-id>+<username>@users.noreply.github.com"`
- [ ] **既有 commit history 是否含實名 email**：
  ```bash
  git log --all --format="%ae" | sort -u
  ```
  若有：通常**接受 trade-off、不 rewrite**（成本高、影響備份獨立性）。重點是「從現在起不再暴露」、不是「過去全清」。
- [ ] **文件內 hardcode email 殘留掃描**：
  ```bash
  grep -rn "@gmail\|@hotmail\|@yahoo\|@outlook\|@example.com\|@your-domain" \
    --include="*.md" --include="LICENSE"
  ```
  範例與文字應該全部用 placeholder 或 noreply 格式、不留實名 email。
- [ ] **更廣的個資 pattern 掃描**（電話、地址、銀行尾號、身分證）：
  ```bash
  # 台灣手機 / 市話
  grep -rEn "09[0-9]{8}|0[2-8]-?[0-9]{6,8}" --include="*.md"
  # 銀行帳號 / 信用卡尾段
  grep -rEn "\b[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{4}\b|\b[0-9]{12,16}\b" --include="*.md"
  # 台灣地址常見字
  grep -rEn "(台北|新北|桃園|台中|台南|高雄)市.*(路|街|大道).*段.*號" --include="*.md"
  # 身分證字號
  grep -rEn "\b[A-Z][12][0-9]{8}\b" --include="*.md"
  ```
  截圖、測試資料、commit message body 都要看（不只 source code）。

> 💡 **重要 Lesson**：**第一次 `git init` 之前**就把 `git config user.email` 設成 noreply，否則所有早期 commit 都會帶實名 email 進 history。事後 rewrite 成本高、且若已雙推 GitHub，backup remote 會跟著要強推（破壞時序證據獨立性）。
>
> 📜 **真實故事**：本 lesson 起源於一次 public 化前的 audit、發現 5 個 commits 已暴露實名 email — 完整經過見 [`HISTORY.md` §B.3](HISTORY.md#b3--七-公開前審查--email-暴露-audit--lesson-learned)。

### 7.3 授權稽核

- [ ] LICENSE 存在且資訊正確
- [ ] 第三方資料 / 字型 / 圖片授權都有 attribution
- [ ] 拷貝來的程式碼有註明來源 + 原 license

### 7.4 文件稽核

- [ ] README 第一段能讓陌生人 30 秒理解專案
- [ ] 安裝 / 啟動指令確認可重現
- [ ] 至少一份 `docs/decisions/` 已寫好

### 7.5 第三方資料源 attribution 完整性

§7.3 授權稽核的細項——**逐一比對：codebase 引用的所有資料源，是否在 LICENSE 末段都有 attribution**。

具體做法：

1. 列出 codebase 內所有「外部資料」的 inventory：
   - 字典 / 字單 / 詞庫 / 字頻表
   - 字型檔（ttf / otf / woff）
   - 圖庫（pixel art / icon set）
   - 翻譯檔 / 對照表
   - 預訓練模型權重
2. 對每筆來源確認：
   - LICENSE 末段是否有 attribution block？
   - 該資料的原始授權條款是否相容於主授權？
   - 衍生使用是否符合條款（特別是 CC BY-SA / GPL 類有「相同方式分享」要求的）？
3. **只要有「使用了但沒 attribution」的，視為 violation**——即使是公共領域資料，attribution 也表達基本尊重

> 檢查觸發點：每次 release 前 + repo 從 Private 改 Public 前 + 新增 dataset / 字型 / 圖庫的 commit。

### 7.6 強制 attribution 資源的主動同意 gate UX 模式

> 公開部署的網站使用 **CC BY-ND**、**CC BY-SA**、嚴格 attribution 要求的字型 / 圖庫 / 資料時，光在 LICENSE 末段標 attribution 不夠——使用者**沒看見** = 沒達成「visible attribution」的精神。本節給設計模式：UI 上紅綠燈 + 主動同意 gate。

#### 7.6.1 何時必用

凡屬下列任一情境：
- 部署的線上 demo / 工具用到 **CC BY-ND**（必須顯示原作者）資源
- 用到 **CC BY-SA**（衍生作品也要 BY-SA、attribution 強制）
- 政府開放資料的「強制標示出處」條款（例如 Taiwan 政府資料開放授權 1.0）
- 任何 license 寫「**must visibly attribute**」的資源

純把 attribution 寫在 LICENSE 末段、頁尾小字，**法律上爭議大**——普通使用者不會看到。

#### 7.6.2 設計模式：紅燈預設 + 主動同意 toggle

```
進入頁面 → 字型/資源預設 紅燈（未授權）
   ↓ 使用者點 [授權] 按鈕
彈出 confirm dialog 顯示：
   - 資源名稱 + 字數 / 規格
   - License 條款摘要
   - Attribution（原作者 + URL）
   - 法律精確說明：「授權 = 同意網站代為下載/使用，著作權仍歸原作者」
   ↓ 使用者按 [確定]
紅燈 → 綠燈，按鈕變 [取消授權]，資源啟用
   ↓ 使用者隨時可點 [取消授權]
直接生效（無二次確認），綠 → 紅
```

#### 7.6.3 三個關鍵法律精確點

**(a) 區分「下載/使用代理」 vs 「授權轉讓」**

最容易誤解的點。「授權」一詞模糊——使用者可能誤以為 = 「字型給我用 forever」。實際是「**我授權網站從來源下載並代為使用，著作權仍歸原作者**」。

UI 必須**顯著標示**這個區別。建議在 modal 頂端放橘色警示框：

```html
⚠️「授權」一詞的精確意義：此處的「授權」指您授權本網站從字型來源網站
下載與使用該字型，並非字型授權的轉讓。字型本身的著作權仍歸原作者所有。
```

**(b) Confirm dialog 包含 license URL**

使用者要有「能跳到 license 全文」的能力。dialog 內必含 `licenseUrl`，不是只有 license 名稱。

**(c) 取消授權直接生效**

CC BY-ND 等 license 內含「使用者可隨時撤回」精神。「取消授權」不該需二次確認——直接清 localStorage、紅燈、disable 該資源。

#### 7.6.4 技術實作架構（純前端 gate）

最簡單實作：
- 後端字型 / 資源**永遠載入**（runtime 不依授權狀態）
- 前端用 `localStorage["app:resource-authorized:" + key] === "1"` 控制 UI 紅綠燈
- 5 個 init function 各自 check `localStorage` → 渲染對應 banner（紅燈 + 授權按鈕 / 綠燈 + 取消授權 + attribution）
- render 時前端可選擇 reject 未授權 style（額外 gate；非必要）

**為什麼純前端足夠**：CC BY-ND 主要要求「**visible attribution + 使用者明確同意**」，不是嚴格 access control。純前端 UI 顯示 + 點按同意已達成這目標。

**何時需要後端 gate**：商業專案、強監管產業（醫療 / 金融）、license 明確要求 server-side enforcement。一般教育 / 工具網站純前端足夠。

#### 7.6.5 跨字型 / 多資源時的粒度

5 套字型 / 多份資料時，**每個獨立 toggle**——粒度精確匹配 license 顆粒度。一次性「授權所有」按鈕雖簡潔，但混淆不同 license 條款。

#### 7.6.6 按鈕視覺位置

按鈕放在 banner **最前面**（左側），不是末尾。原因：
- 中文 UI 慣例「動作詞」在左
- 末尾的按鈕容易被長 attribution 文字擠到視窗外
- 點擊區域明顯、降低使用者尋找成本

> 📜 **真實案例**：見各專案決策日誌（搜尋 `font_authorization_gate` 或 `cc-by-nd consent ui`）。

---

## 八、長期維護習慣

### 8.1 每次 push 前

- [ ] 跑 `pytest`（或同等 test runner）確認綠燈
- [ ] `git status` 確認沒夾帶意外檔案
- [ ] commit message 描述「為什麼」而非「做了什麼」

### 8.2 每週一次

- [ ] 看一下 GitHub Actions 是否仍綠
- [ ] 看一下 Render / 部署平台 cold start 健康度
- [ ] 整理當週 `docs/decisions/` 是否有遺漏

### 8.3 每月一次

- [ ] 升級依賴（`pip list --outdated`）
- [ ] Review `docs/HISTORY.md` 是否反映目前狀態
- [ ] 清理 stale branches

### 8.4 每個 release

- [ ] bump version
- [ ] 寫 release notes
- [ ] 更新 README badges 數字（測試數、版本）
- [ ] tag the commit (`git tag v0.x.x`)

### 8.5 為未來預留架構彈性（前瞻設計原則）

> **核心思想**：寫第一個檔案前，先想 **6 個月 / 1 年後** 可能的用法 — public 化？變網站？變書？變課程？  
> 想清楚了，**license 選擇、檔案結構、引用方式**自然會浮現。日後拆分 / fork / 公開時，多花 5 分鐘的成本換回避免 5 小時痛苦的價值。

具體習慣（寫筆記 / 開專案時就要做）：

1. **保持原創內容與引用內容的清楚分離**
   - 引用大段第三方內容時，**獨立成檔案 / 段落**，加 metadata 標明來源 + license（在 frontmatter 或檔頭註解）
   - 不要讓「您寫的話」和「您引用的話」深度交織 — 拆分時就無從下刀
   - 範例：`01_硬體架構.md`（原創）vs `99_引用_egh0bww1_blog_excerpt.md`（純引用）

2. **預留 license 抉擇空間**
   - 私人筆記**可以**含 CC BY-SA / GPL 等傳染性引用，但**心裡有數**：未來公開時要選擇「整體跟著傳染 license」或「拆出引用部分到獨立 repo」
   - 詳見附錄 J「授權相容性 cheat sheet」

3. **最小化嵌入式引用**
   - 與其貼 5 行第三方原文，不如**用自己的話 paraphrase** + 引用來源連結
   - Paraphrased text 著作權歸您 → license 自由選

4. **檔案命名 / frontmatter 暗示來源**
   ```yaml
   ---
   license: CC BY-SA 4.0 (derived from egh0bww1 blog)
   source: https://egh0bww1.com/posts/2023-10-24-unitree-go1-collection/
   ---
   ```
   未來自動化 audit script 能 grep 出所有「非 MIT」內容、決定怎麼處理

5. **私人筆記也別放 secret**
   - 即使是 private repo，「現在 private、未來 public」的成本巨大
   - secret 永遠放 `.env` / 環境變數 / 1Password、**never** 在 markdown 內文
   - 想像「明天有人意外 push 成 public」場景，現在能不能承受？

6. **公開化前的「逆向設計」演練**
   - 開新 repo 時，問自己「**最終公開版** 會長什麼樣子？」
   - 從那個目標倒推回來：哪些檔案要拆、哪些 license、哪些 attribution 要先寫好
   - 這比「先寫再說、之後再清」省力 10 倍

> 📌 **提醒**：本節是**心法**，附錄 J 是**工具**。心法不確定時翻附錄 J 的決策樹（J.4）。

### 8.6 移除功能時：保留檔案、只拔載入

當決定下線一個功能（模組、模擬器、舊版實作），預設做法是：

1. **HTML / 入口處拔掉載入**（`<script>` / import / require）
2. **被引用處改寫成走新路徑**（不留 fallback 分支，避免技術債堆積）
3. **檔案本身留在原位**（不要 `rm`，加註「v0.X.Y 起不再載入；保留供歷史追溯」即可）
4. **dead CSS selector / metadata 欄位**：清掉明顯的（避免 grep 噪音），但「資料定義」型的（如每個 skill 帶 `anim` 欄位給已下線 simulator 用）可以暫留，標為已知技術債

**為什麼**：刪檔很爽，但日後想復原（例如做「教學前後對照」、寫 retrospective）時要去 git 撈，成本很高。檔案保留 + 拔載入是最低後悔成本的下線方式。

> 📜 **真實故事**：本原則起源於一次下線 2D SVG simulator（被 3D 模擬器取代）的實戰經驗，完整經過見 [`HISTORY.md` §B.4](HISTORY.md#b4--86-移除功能保留檔案--doglab-coding-v051-下線-2d-svg-simulator)。

### 8.7 Morning audit ritual（每日工作 session 起手式）

每個工作日新 session 開始前，跑 SOP 一致性掃描——**通常 30 分鐘內可完成，效益是後續 4-8 小時的工作不在歪掉的基礎上累積**。

掃描清單：

- [ ] **§二 IP 三件套**：LICENSE / README / footer 三處身份鏈是否一致？
- [ ] **§三 雙 remote**：origin + backup 都活著？最新 commit 兩邊都到了？
- [ ] **§4 work logs**：上一個工作日的 work log 有沒有寫？沒寫立刻補（§4.5 backfill）
- [ ] **§5 decision logs**：上一個工作日的關鍵決策有沒有 log？
- [ ] **§六 audit checklist**：新引入的資料源有跑過三段檢查嗎？
- [ ] **§7.5 attribution 完整性**：新增資料源有寫進 LICENSE 末段？
- [ ] **§8.4 release tag**：上一個 version bump 有對應 git tag？

發現 gap：寫進今天的工作項目（前 30-60 分鐘清掉），再進主工作。

> **為什麼這個習慣值錢**：SOP 寫進 playbook 是一回事，**確實執行是另一回事**。Morning audit 是「對自己的 SOP 服從度的誠實度測試」——即使每次都全綠，這個 ritual 本身就是對 SOP 的尊重。

> 📜 **真實案例**：本 ritual 起源於 stroke-order 專案 2026-04-29 的 morning audit——一次例行掃描揭露 4 個 PROJECT_PLAYBOOK 漏跑章節（WORK_LOG_2026-04-27 backfill / cjk_common_808 §六 retrospective / §七 公開前審查 retrospective / v0.14.0 git tag pending），驗證了「即使 SOP 看似已內化，定期 audit 仍會抓到實際 gap」。詳見各專案決策日誌。

### 8.8 先 inspect 實際輸出，再下 root cause 結論

Debug 時的常見陷阱：看到 UI 不對，就直接改 UI；看到報告說某層出問題，就直接信。**真正的 debug 第一步是 dump 真實輸出**，不要用「應該怎樣」當作起點。

#### 規則

1. **直接看資料層**：可 curl 的 endpoint curl，可 dump 的中間態 dump，可 log 的執行路徑 log。看實際出來的東西，不是「應該」出來的東西。
2. **跨層問題從下往上 trace**：UI 層的「不對」可能是 backend 路徑漏參數，可能是資料層本身就壞。從最底層先看，逐層往上。
3. **看夠細才下結論**：「樣子怪怪的」不是 root cause。具體到「outline path 含 142 段直線 + 181 段 Bezier 但 0 段 C 命令」這種顆粒度，才有資格下結論。

#### 反例 vs 正例

**反例（修兩輪才中）**：
> 用戶報「印章切到隸書/篆書預覽空白」。
> Round 1：盯著前端 tintPreviewFill 看，覺得是 stroke="none" 抹掉子元素 → 修前端。**只解一半**（border 出來了，骨架線還是不見）。
> Round 2：curl `/stamp` endpoint 直接看 SVG。發現 backend 根本沒回 outline path → root cause 在 backend loader 漏帶 `outline_mode=skip` 參數。1 行 fix。

**正例（一次中）**：
> 用戶報「篆書邊緣不平滑」。
> 不假設「是渲染端鋸齒」。curl 取實際 SVG，分析 outline path 命令分布：142 段 L + 181 段 Q + 0 段 C → root cause 在 OTF 字型本身（資料層），用大量短直線近似曲線。立刻知道治本要換字型，緩解可加 `shape-rendering="geometricPrecision"`。

#### 工具技巧

- **Web API**：`curl` / `httpie` / browser DevTools Network tab。看真實 response payload，不要只看前端 console。
- **檔案處理**：`hexdump -C | head` / `xxd | head` 看 raw bytes，`file` 看實際格式。
- **資料庫**：query 出 raw rows，不要只看 ORM 抽象。
- **SVG / 結構化 data**：grep / awk 命令分布，不要只看渲染後的視覺。

#### 為什麼這個習慣值錢

- **省一輪修法時間**：每次「先看實際輸出」可能多花 5-10 分鐘，但少修錯一輪可能省 1-3 小時。
- **跨人協作的可信度**：「我 curl 過 endpoint，response 是 X」遠比「我覺得 backend 應該是這樣」可信。
- **Root cause 文化**：寫 decision log 時，「root cause 是 Y」前面可以接「實際輸出證明...」，論證鏈不靠假設。

> 📜 **真實案例**：本原則起源於 stroke-order 專案 2026-05-01 Phase 11 印章模組精修——前後 8 個 bug fix / feature 中至少 3 處的 root cause 必須先 dump 真實 SVG / API response 才找得到，盲改前端的修法都只解一半。詳見 [`docs/decisions/2026-05-01_stamp_phase11.md`](decisions/2026-05-01_stamp_phase11.md)。

### 8.9 底層改動 → 整條 pipeline audit

座標系統 / scale / EM / bbox / 預設值等基礎抽象的改動，視為**高風險改動**。不只看「直接相關功能是否正確」，要主動 audit 周邊：

- 所有用同類座標的 caller 是否仍正確
- 所有 default 值在新 base 下是否仍合理
- 所有 cap / floor / clamp 是否仍合理
- UX 上「user 看到的數字」是否還對應預期意義

#### 為什麼這個習慣值錢

底層改動會把上層舊 bug 從「不顯眼」變「使用者可感知」。如果改完只看直接範圍 → 隱性 bug 等到使用者撞到才被發現，債務變大。

#### 反例

stroke-order 11g 改 bbox-based scale（從 EM-based）—— 字身改成「outline bbox 撐滿 cell」，比 EM-based 更貼合。但這個改動暴露了既有 `inner_w = max(_, char_size_mm)` 的副作用：以前 EM-scale 字身有自然 padding 看不出來，bbox-scale 撐滿後 user 改 char_size_mm 時 inner_w 會被拉大，造成「user 主觀感覺章面內框跟著變」。

11g 當時只 audit 了「字撐滿 cell」這個直接目標，沒看 inner_w 計算的合理性。Bug 在 12b 才暴露。

#### 正例

12c 陽刻支援動主線之前先 prototype 驗證演算法（見 §8.11）。確認效能 / 視覺 / G-code 規模 / 邊角情況都 OK 之後才動 stamp.py。整個 12c 主分支只有 1 commit。

#### Audit checklist（base infra 改動專用）

- [ ] 列出所有 import 此 module 的 file
- [ ] 列出所有用此 default 值的處（grep magic number）
- [ ] 列出所有 cap / clamp 邏輯
- [ ] 跑全套 pytest 看 regression（不只直接 test file）
- [ ] 若有 UI，spot-check 所有相關面板的「user 看到的數字」

> 📜 **真實案例**：起源於 stroke-order 2026-05-01 Phase 12b — 11g bbox-scale 改動之後 5 週才被 user 撞到 inner_w bug。詳見 [`docs/decisions/2026-05-01_stamp_industry_alignment.md`](decisions/2026-05-01_stamp_industry_alignment.md)。

### 8.10 Default 值 single source of truth

超過一處出現的 default 值在 codebase 內，要改 named constant 並 import。grep 看到 3 處以上的 magic number 即觸發重構。

#### 規則

1. **Pydantic Field default + Query() default + 函式參數 default + UI input value** 同一個值散布到 4-7 處是常見反模式
2. 集中到 module-level constant（如 `stamp.py` 頂端 `DEFAULT_BORDER_PADDING_MM = 0.8`）
3. 所有地方 import 用，UI 改用 `<input :value="defaultBorderPadding">` 之類的 binding（如果框架支援）

#### 為什麼這個習慣值錢

更新 default 時，grep 漏改一處就造成 default 不一致。例如 stroke-order 12b 改 `border_padding_mm 2.0 → 0.8` 要同步 7 處（3 server + 4 stamp.py + 1 index.html）。手動 sed + grep 驗證能 work，但累積 debt。

#### Audit checklist

- [ ] grep `= 0\.8\|= 2\.0\|= 25\|...`（任何看起來像 default 的 magic number）
- [ ] 數出現次數 ≥ 3 → 列入 backlog
- [ ] 重構時：建 module constant + 全部 import + 加 test 確認 default 對齊

> 📜 **真實案例**：起源於 stroke-order 2026-05-01 Phase 12b-6 — 改 `border_padding_mm` 預設要同步 7 處。詳見 [`docs/decisions/2026-05-01_stamp_industry_alignment.md`](decisions/2026-05-01_stamp_industry_alignment.md)。

### 8.11 演算法工作 SOP：先 prototype 後主線

對「未驗證可行性的演算法」工作，動主線之前先寫 prototype（在 `scripts/` 或 `notebooks/`，不進主分支）。

#### 規則

prototype 階段必驗證：

1. **演算法正確性**：單元 case 對（最簡 input 跑出預期 output）
2. **效能規模**：最大 use case 不爆（時間 / 記憶體 / 輸出規模）
3. **視覺 / 業務正確性**：render → 看圖 / 跑端對端 case → 確認業務語意對

prototype 通過後才 port 進主線 module。**Prototype 檔案保留** 在 `scripts/`，當未來文件 / 教學 / 重新驗證用。

#### 為什麼這個習慣值錢

直接動主線寫演算法 + 直接接 API → 邊改邊試 → 主分支被 churn 多輪 commit / 測試持續紅 / 多次 force push 修細節。**Prototype 階段**避開所有這些雜訊。

主分支看起來：演算法工作會是 1 個乾淨 commit（含完整 test），而不是 5-10 個 fix-up commits。

#### 反例 vs 正例

**反例**（典型 anti-pattern）：
> 想實作 X 演算法 → 直接動主線 → 寫 module + 改 endpoint + 改 UI 全部一起 → push → CI 紅 → 修 → CI 還紅 → 修細節 → 最後過 → 主分支多了 5 個無意義 commit。

**正例**（stroke-order 12c-3）：
> 寫 `scripts/prototype_engrave_convex.py` → 跑壓力測試（4 分 / 8 分 / 1 寸 各尺寸）→ render PNG 看 ON/OFF 區段 → 確認 even-odd 正確 → 演算法 port 進主線 module → 1 commit 完整 5 子任務 + 5 測試 → CI 一次過。

#### 何時不需要 prototype

- 純 UI 改動（CSS / 既有元件 reorganize）
- 單純參數調整（已驗證的演算法 default 值更新）
- bug fix（修復路徑已知）
- 文件 / 重構（不改演算法行為）

簡單說：**「演算法行為的 first-time 實作」才需要 prototype**。

> 📜 **真實案例**：起源於 stroke-order 2026-05-01 Phase 12c-3 G-code 陽刻光柵掃描——prototype 確認 scanline + even-odd + boustrophedon 演算法可行（4 分章 38 秒、1 寸 4.5 分、演算 < 100ms），主分支 1 commit (74b996d) 完成 5 子任務。詳見 [`docs/decisions/2026-05-01_phase12c_convex_engrave.md`](decisions/2026-05-01_phase12c_convex_engrave.md)。

### 8.12 演算法 module 獨立、不依賴業務 module

演算法（特別是新類型）獨立 module，不污染既有 file，不依賴業務概念。

#### 規則

1. **演算法 module 只依賴抽象資料結構**（polygon / vector / matrix），不知道 stamp / sutra / patch 業務概念
2. **業務 module import 演算法 module**，不反過來
3. **演算法 module 測試獨立**（單元測試只給 module 自己，不依賴業務 fixture）

#### 為什麼這個習慣值錢

- **跨 use case 重用**：同個演算法可能 stamp / patch / sutra / 未來新模式都能用
- **God file 控制**：既有業務 file 不會無限長大（stroke-order 11g 之後 stamp.py 1100+ 行已經很大）
- **測試獨立**：演算法 bug 可在 module 層直接抓，不必 instantiate 完整業務上下文

#### Audit checklist

- [ ] 演算法 module 是否 import 業務 module？（如果有 → 抽象顛倒，要重構）
- [ ] 演算法 module 名稱反映「做什麼」（`engrave.py` / `scanline.py`）而非「給誰用」（`stamp_engrave.py`）
- [ ] 演算法 module 文件含「跨用途複用提示」段落

> 📜 **真實案例**：起源於 stroke-order 2026-05-01 Phase 12c-3 — 光柵掃描演算法獨立成 `exporters/engrave.py`，stamp.py 跟（未來的）patch / sutra 都能 import 用。詳見 [`docs/decisions/2026-05-01_phase12c_convex_engrave.md`](decisions/2026-05-01_phase12c_convex_engrave.md)。

### 8.13 結構化 input fields > separator hack

當功能 input 含多個語意獨立欄位（如橢圓章 5 段：上弧 / 中央 1-3 行 body / 下弧），用結構化 schema（多個獨立 fields）優於 single text + separator hack（如 `text="A|B|C|D"`）。

#### 規則

1. **多語意欄位 ≥ 3 個** → 拆獨立 fields，不用 separator string
2. **list[T] 用 native list type**（Pydantic / JSON），不用 `"a||b||c"` 字串拆分
3. **GET endpoint 才接受 separator**（query string 沒原生 list） — 但 POST body 一律 native list
4. **Backward compat**：保留舊 single-text fallback path，新欄位全空時 fallback 老邏輯

#### 為什麼這個習慣值錢

Single text + separator 的問題：

- **User 心智成本**：要學 separator 是什麼字元（`|` ? `||` ? `,` ?）+ 怎麼 escape（內文有 `|` 怎麼辦）
- **API 不自我文件化**：`text` field 看 type signature 不知有結構，要看 docs / 範例才懂
- **可選欄位處理麻煩**：empty 欄位要寫 `||` 連續分隔符，user 容易忘
- **未來擴充 break schema**：要加 per-line font size 等 metadata 時，被 separator 綁死
- **語意 vs 顯示混淆**：UI 要 5 個 input 對齊 API 5 段，separator 要做 split / join 同步邏輯

結構化 schema 的代價：

- API field 多 3-5 個（surface area 略大）
- Backward compat 處理：fallback 邏輯（all empty → 走老 path）

代價可控，長期收益大。**反例可參考 CSS `font` shorthand**（多欄位塞 single string 已多次造成 bug，後來 modern CSS 全部拆獨立 property）。

#### Audit checklist

- [ ] grep API field 看有沒有 `text.split("...")` / `text.split("|")` 等 hack
- [ ] 數該 field 在 UI 對應幾個 input → ≥ 3 個就觸發重構
- [ ] 重構時：新增獨立 fields + UI 對齊 + backward-compat fallback + tests

> 📜 **真實案例**：起源於 stroke-order 2026-05-02 Phase 12m-1 橢圓章 — 5 段語意獨立欄位（上弧 / 中央 1/2/3 / 下弧），原本只有 single text + 1-2 行 horizontal split layout。重構成結構化 5 欄位後，user UI 一看即懂、API 自我文件化、各欄位 empty 自動 skip。詳見 [`docs/decisions/2026-05-02_phase12m_oval_structured.md`](decisions/2026-05-02_phase12m_oval_structured.md)。

### 8.14 UI 預設套用要 hook init time，不只 change

UI 控件的 default state 由 JS 在 dropdown / preset 變動時填入（如「切到 oval preset → 自動勾雙線外框」），**必須在 init 時也跑一次**。光是 hook `change` event 不夠 — 第一次載入或 user 沒做 change 時不會觸發 → init state 跟 default-after-change 不一致。

#### 規則

```js
// ❌ 反模式
$("preset").addEventListener("change", applyDefaults);

// ✅ 正模式
$("preset").addEventListener("change", applyDefaults);
applyDefaults();   // ← init 時跑一次，覆蓋首次載入路徑
```

延伸：所有「依賴 user 互動觸發 default」的 init 邏輯都同樣處理。

#### 為什麼這個習慣值錢

症狀：

- User 截圖顯示 default 未生效（checkbox 沒勾、size 不對、hint 是別的 preset 數值）
- 開發者 reproduce 困難（自己切 preset 兩下都 OK，因為觸發過 change）
- 容易誤判為「部署沒上去 / 快取問題」白白浪費排查時間

根因：UI 的 default 邏輯散在兩處 — HTML 寫死 default + JS change-time override。如果 JS change 沒觸發，HTML 寫死的就是「真 default」。但 HTML 不知道目前 preset 是哪個 → 任何依賴 preset 的 default 必然錯。

修法簡單（一行 init call），但容易漏。

#### Audit checklist

- [ ] grep `addEventListener("change",` 對應的 handler 有沒有在 init 也 call
- [ ] 列出所有「依 preset/select 切換填 default」的 handler → 每個都該 init time 跑
- [ ] 寫測試：page load 後 dropdown 預設 preset 對應的 default state 對齊（hard）；OR 簡單 grep `function xxx_init` 內呼叫 default-applier（pragma）

#### 反例 vs 正例

**反例**（典型 anti-pattern）：
> User 進站 → preset dropdown 預設 oval → 但 double_border checkbox 維持 HTML 寫死 unchecked → user 看到「該勾沒勾」回報 bug → 開發者 reproduce 不出來（自己切兩下都 OK）→ 浪費 1 小時排查 cache / 部署 / 後端後才發現是 JS init 沒呼叫 default。

**正例**（stroke-order 12m-1 r3）：
> `stampInit()` 結尾加 `stampApplyPresetDefaults();` → 任何 preset 進站都同步 default → 跟 change-time 行為完全一致 → 沒 first-time UX bug。

> 📜 **真實案例**：起源於 stroke-order 2026-05-02 Phase 12m-1 r3 — r1 設了 oval default = double_border ON 但只 hook 在 change event。User 截圖顯示首次進站雙線外框沒勾，初步誤判為部署問題，後 trace 到 init 沒呼叫 `stampApplyPresetDefaults()`。修法 1 行。詳見 [`docs/decisions/2026-05-02_phase12m_oval_structured.md`](decisions/2026-05-02_phase12m_oval_structured.md)。

---

## 九、附錄：可複製模板

### 附錄 A：README.md 骨架

```markdown
# PROJECT_NAME

[![CI](https://github.com/seyen37/PROJECT_NAME/actions/workflows/ci.yml/badge.svg)](https://github.com/seyen37/PROJECT_NAME/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10+-blue)
![license](https://img.shields.io/badge/license-MIT-yellow)

一句話描述專案做什麼。

## 🔗 線上資源

- 📖 **文件中心**：<https://seyen37.github.io/PROJECT_NAME/>
- 📦 **GitHub repo**：<https://github.com/seyen37/PROJECT_NAME>

---

## 為什麼

兩三段描述為什麼這個專案存在、解決什麼問題。

## 開發歷程

本專案由 **許士彥（Hsu Shih-Yen，<https://github.com/seyen37>）獨立設計與開發**。
詳細設計脈絡見 [`docs/decisions/`](docs/decisions/)。

## 安裝

```
[安裝指令]
```

## 授權

MIT License — 詳見 [LICENSE](LICENSE)。
```

### 附錄 B：LICENSE（MIT）

```
MIT License

Copyright (c) 2026 許士彥 (Hsu Shih-Yen) (https://github.com/seyen37)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

### 附錄 C：.gitignore（Python 為主）

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
*.egg
build/
dist/

# Virtual env
venv/
.venv/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Project-specific (調整)
.env
*.log
data/cache/
```

### 附錄 D：決策日誌 _TEMPLATE.md

```markdown
# YYYY-MM-DD：決策主題

> 範圍：本日 / 本任務的工作主題（一句話）
>
> 起點：開始時的狀態
> 終點：結束時的狀態
>
> 對應 commits：
> - `hash1` commit subject
> - `hash2` commit subject

---

## 決策 1：標題

**情境**：當時遇到什麼問題？

**選項**：
- A. 選項 A
- B. 選項 B

**決定**：選 X。

**考量**：
1. 為什麼這樣選
2. 風險 / 妥協

**教訓**：
- 通用 lesson

---

## 決策 2：標題

[同上]

---

## 反思

**做得好的**：
- ...

**可以更好的**：
- ...

**對長期專案的影響**：
- ...
```

### 附錄 E：GitHub Actions CI（Python）

`.github/workflows/ci.yml`：

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[test]"
      - name: Test
        run: pytest
```

### 附錄 F：第三方品牌使用準則 + 商標 disclaimer

> **何時用**：當您的 repo / 文件 / 網站提及任何**他人註冊商標**（廠商名、產品名、品牌 logo）時。
>
> **為什麼必要**：避免被指控「攀附商譽」或「impersonation」。同時保護自己的善意使用。

#### F.1 使用準則（DO / DON'T）

✅ **可以做**：
- 在文件中**事實性提及**他人產品（「本筆記研究 Unitree Go1 機器狗」）
- 在比較表中對照不同產品（"Unitree Go1 vs Petoi Bittle"）
- 引用他人開源 code 並依其 LICENSE 作 attribution

❌ **不要做**：
- 用他人商標當您的 repo / 網站 / 產品名（例：`unitree-blocks.com`、`bittle-toolkit`）
- 直接使用他人 logo / 視覺識別圖案（即使加變形）
- 暗示官方合作 / 認可（`Official Unitree Toolkit`、`Petoi Partner`）
- 在比較中刻意貶低他牌（不實 / 誇大缺點）

#### F.2 標準 disclaimer 模板

放在 README 結尾或網站 footer：

```markdown
## 商標聲明 / Trademark Disclaimer

本專案 / 網站僅作個人學習研究用途。文中提及的所有產品名、品牌名、logo 為其各自擁有者之商標或註冊商標。

This project / site is for personal learning and research only. All product
names, brand names, and logos mentioned are trademarks or registered
trademarks of their respective owners.

- **Unitree®**, **Go1®**, **Go2®** 為 Hangzhou Yushu Technology Co., Ltd. 之商標
- **Petoi®**, **Bittle®**, **Nybble®** 為 Petoi LLC. 之商標
- **Boston Dynamics®**, **Spot®** 為 Boston Dynamics, Inc. 之商標
- 其他未列出商標亦同樣歸其各自擁有者所有

本專案與上述任一公司**無任何附屬、贊助、認可關係**（not affiliated with, endorsed by, or sponsored by）。
```

#### F.3 中國市場的額外考量

若內容會被中國使用者讀到（例如 GitHub 在中國可訪問、或翻譯成簡中發到知乎/CSDN）：
- **「攀附商譽」訴訟風險高於台美**，disclaimer 一定要中文版同時存在
- **避免直接吐槽中國品牌**（特別是 Unitree）— 改用中性「以下為已知技術細節」描述
- **不要 fork 後改名魚目混珠**（例：把 `unitree_legged_sdk` 改名 `unitree_legged_sdk_pro` 上傳，會引廠商注意）

---

### 附錄 G：教育類網站合規清單（COPPA / 個資法 / GDPR-K / 兒少法）

> **何時用**：網站 target user 包含 **18 歲以下**（特別 < 13 歲）時。程式積木 / Scratch-like 編程網站幾乎必中。

#### G.1 法規地圖

| 法規 | 司法管轄 | 適用年齡 | 觸發條件 |
|---|---|---|---|
| **COPPA**（Children's Online Privacy Protection Act） | 美國 | < 13 歲 | 收集兒童個資 / 該網站「主要受眾為兒童」 |
| **GDPR-K**（GDPR 兒童特別保護） | EU | < 16 歲（成員國可降至 13） | 同上，加 EU 用戶 |
| **個資法**（個人資料保護法） | 台灣 | 不分齡（< 7 歲須法定代理人同意） | 收集任何個資 |
| **兒少權益保障法** | 台灣 | < 18 歲 | 內容呈現 / 平台責任 |
| **PIPL**（個人信息保護法） | 中國 | < 14 歲須監護人同意 | 中國用戶 |

#### G.2 合規清單（最小必要）

**A. 設計階段**
- [ ] 明確網站定位：「教育用途，13 歲以上」 vs 「親子共用，需家長監督」 — **影響後續所有政策**
- [ ] 設計時遵循「Privacy by Design」：**預設不收個資**、可選的功能才開啟收集
- [ ] 評估必要性：每個收集欄位都問「真的需要嗎？」（例：暱稱可以、實名不必、地址絕對不要）

**B. 帳號 / 登入**
- [ ] 若有帳號功能：年齡驗證機制（不是嚴格驗證但要有「請輸入生日」並過濾 < 13）
- [ ] < 13 歲：要求家長 email + 同意機制（COPPA verifiable parental consent）
- [ ] 不接受 13 歲以下兒童的姓名 / 地址 / 電話 / 學校名 / 照片 / 影片 / 聲音
- [ ] **建議：教育網站只用「匿名 session」**，不需要登入就能用，避開 COPPA 大部分條文

**C. 上傳 / 分享功能**
- [ ] 用戶創作的積木程式 / 角色 / 動畫，預設**僅本人可見**
- [ ] 「分享」必須是 explicit opt-in，不能 default-public
- [ ] 內容審核機制（至少 keyword filter；社群互動最小化）
- [ ] 不允許 < 13 歲用戶在 public 留言區發文

**D. 數據收集 / Analytics**
- [ ] **不要用 Google Analytics 預設配置**（會收集 cookie、IP）
- [ ] 改用對兒童友善的：**Plausible**、**Umami**、**Fathom**（無 cookie、IP 匿名）
- [ ] 或使用 GA 但開啟「IP anonymization」+ 不啟用「remarketing」
- [ ] Cookie banner（GDPR 必須；台灣個資法建議）

**E. 文件層**
- [ ] **Privacy Policy** 必須 < 13 歲兒童看得懂的版本（白話）+ 完整法律版
- [ ] 明確列出「我們收集 / 我們不收集」
- [ ] 家長聯絡管道（要刪除孩子資料時的窗口）
- [ ] **每年定期 review** Privacy Policy（標日期、變動加 changelog）

**F. 技術層**
- [ ] HTTPS-only（這是 baseline 不是選配）
- [ ] CSP（Content Security Policy）防 XSS
- [ ] 用戶上傳的程式碼**沙箱化執行**（iframe sandbox / Web Worker）
- [ ] 不允許 user code 存取 `window.parent` / `localStorage` 跨來源資料

#### G.3 實務建議：最小化合規負擔

如果您不想處理一堆合規手續，**最強建議**：

> **設計成完全不需要帳號的網站**
>
> - 用 `localStorage` 存使用者作品（瀏覽器本機，不上傳）
> - 「分享」改成「複製連結」（URL 含序列化的程式內容、不存伺服器）
> - 完全不收集個資 → 大部分 COPPA / GDPR / 個資法 條文不適用
> - Privacy Policy 簡單到一句：「本網站不收集任何個人資料；您的作品儲存在您自己的瀏覽器」

**Scratch、Blockly demo、CodePen** 都採類似策略。對個人 / 小型專案是甜蜜點。

---

### 附錄 H：Privacy Policy 骨架（最小版）

> **何時用**：網站涉及任何個資收集（含 cookie、analytics、帳號）時。
>
> **本骨架定位**：個人 / 小型開源網站 baseline 模板。商業專案請找律師。

```markdown
# Privacy Policy / 隱私權政策

> 最後更新：YYYY-MM-DD

## 1. 我們是誰

本網站 [SITE_NAME] 由 許士彥（Hsu Shih-Yen）以個人名義營運。
聯絡：透過 GitHub <https://github.com/seyen37>

## 2. 我們收集什麼資料

我們**不收集**：
- 您的姓名 / 真實身分
- 您的 email / 電話 / 地址
- 您的位置
- 您的瀏覽歷史

我們**會收集**（如有，列出實際情況）：
- [ ] Web Analytics（Plausible / Umami，不用 cookie、IP 匿名化）
- [ ] 錯誤回報（不含個資）
- [ ] 您主動上傳的內容（[說明用途]）

## 3. 我們如何使用資料

[逐項對應上方收集項目，說明用途。沒有的就略過。]

## 4. 我們如何保護資料

- 全站 HTTPS
- 不與第三方分享
- [若有伺服器]：使用業界標準加密儲存

## 5. Cookie 使用

[根據實際情況選擇]
- ☐ 本網站不使用 cookie。
- ☐ 本網站使用以下 cookie：[列出每個 cookie 名稱、用途、保存期限]

## 6. 兒童隱私

本網站[未/有]針對 13 歲以下兒童。如您是家長並擔心孩子的資料：
- 透過 [聯絡方式] 聯繫我們刪除任何相關資料

## 7. 您的權利

依台灣個資法、GDPR、CCPA：
- 查詢您的資料
- 要求刪除您的資料
- 撤回同意

## 8. 政策變更

任何變更會在本頁標示新的「最後更新」日期。重大變更會[網站公告 / email 通知（如有訂閱）]。

## 9. 聯絡

任何問題：透過 GitHub <https://github.com/seyen37>
```

---

### 附錄 I：Terms of Service 骨架（最小版）

```markdown
# Terms of Service / 服務條款

> 最後更新：YYYY-MM-DD

## 1. 服務性質

本網站 [SITE_NAME] 為個人營運之開源教育工具，**免費提供、不保證可用性**。

## 2. 您的責任

使用本服務時您同意：
- 不上傳違法 / 侵權 / 不適合兒童的內容
- 不利用本站從事任何商業營利行為（除非另有書面同意）
- 不嘗試入侵 / 破解 / 反向工程本站
- 自行備份您創作的作品

## 3. 我們的責任

- **本服務按「現狀」提供**，不保證無錯誤、不間斷、無資料遺失
- 本人[ 不負責 / 不承擔 ]因使用本站造成的任何直接或間接損失
- 本服務可能隨時暫停 / 終止（會盡量提前公告）

## 4. 智慧財產權

- 本網站程式碼以 [LICENSE 名稱，例：MIT] 授權
- 您創作的作品**權利歸您所有**；上傳分享即授權本站非專屬展示權
- 若您引用 / fork 本站內容，請依 LICENSE 條款 attribution

## 5. 第三方服務 / 商標

本站使用的第三方服務（[列出，例：GitHub Pages、Plausible Analytics]）有其自己的條款。
本站提及的他人商標（見[商標聲明](#商標聲明)）為其各自擁有者所有。

## 6. 法律適用

本條款依**中華民國（台灣）法律**解釋。任何爭議以**台灣管轄法院**為第一審。

## 7. 條款變更

任何變更會在本頁標示新的「最後更新」日期。繼續使用即視為接受新條款。

## 8. 聯絡

任何問題：透過 GitHub <https://github.com/seyen37>
```

> **注意**：以上是個人小型開源網站的 baseline。若涉及付費功能、用戶資料儲存、商業授權，**請找專業律師**。本模板**不構成法律建議**。

---

### 附錄 J：授權相容性 cheat sheet + 「割開」決策

> **何時用**：要決定 repo / 網站 / 文件**用什麼 license**、或要引用 / fork 他人作品時。  
> **本附錄定位**：個人專案實務指南，不是法律意見。涉及商業 / 訴訟請找律師。

#### J.1 三句話心法

1. **寬鬆 license**（MIT / BSD / Apache / CC BY / CC0）= 衍生作品**可選任何 license**
2. **傳染性 license**（GPL / CC BY-SA / AGPL）= 衍生作品**必須同 license**
3. **「混到一起」前先問一句**：這個來源 license **強制傳染**嗎？是 → 我接受 / 我割開 / 我重寫；否 → 標 attribution 即可

#### J.2 授權相容性矩陣（從「來源」用到「目標」）

| 來源 → 目標 | MIT | Apache 2.0 | GPL v3 | CC BY 4.0 | CC BY-SA 4.0 | CC0 | 商用閉源 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **MIT** | ✓ | ✓ | ✓* | ✓ | ✓* | ✓ | ✓ |
| **Apache 2.0** | ⚠️¹ | ✓ | ✓* | ✓ | ✓* | ⚠️ | ✓ |
| **BSD-3** | ✓ | ✓ | ✓* | ✓ | ✓* | ✓ | ✓ |
| **GPL v3** | ❌ | ❌ | ✓ | ❌ | ⚠️² | ❌ | ❌ |
| **AGPL v3** | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ |
| **CC BY 4.0** | ✓¹ | ✓¹ | ✓ | ✓ | ✓ | ✓ | ✓¹ |
| **CC BY-SA 4.0** | ❌ | ❌ | ⚠️³ | ❌ | ✓ | ❌ | ❌ |
| **CC BY-NC** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **CC0 / Public Domain** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

**符號解讀**：
- ✓ 可以（保留 attribution + LICENSE 通知）
- ✓* 整體目標必須變成傳染 license（不是「相容」是「被吸收」）
- ⚠️¹ 必須保留 NOTICE 檔（Apache 2.0 強制要求）
- ⚠️² CC 4.0 → GPL 3.0 是 CC 官方宣告的單向相容（僅軟體脈絡）
- ⚠️³ 同上反方向，CC BY-SA 內容可被 GPL 軟體吸收
- ❌ 不可以（除非取得來源作者額外授權）

**最常見的個人專案結論**：
- **想最大相容** → 用 MIT 或 Apache 2.0（程式碼）/ CC BY 4.0（文件）
- **想保護「衍生作品也要開源」** → GPL 3.0（程式碼）/ CC BY-SA 4.0（文件）
- **想完全放棄權利** → CC0（文件）/ Unlicense（程式碼）

#### J.3 「割開」決策樹

```
您的內容會成為 GitHub PUBLIC repo 嗎？
│
├── ❌ 否（永遠 private）
│      └── 任何引用都 OK，license 不觸發。但仍應預留未來公開化空間（§8.5）
│
└── ✅ 是
       │
       ├── 內容 100% 原創？
       │   └── ✅ 任選 license（程式碼建議 MIT，文件建議 CC BY 4.0）
       │
       └── 內容含第三方授權內容
              │
              ├── 引用都是「寬鬆」license（MIT/BSD/Apache/CC BY/CC0）
              │   └── ✅ 標 attribution、整 repo 自由選 license
              │
              └── 引用含「傳染性」license（GPL / CC BY-SA / AGPL）
                     │
                     ├── 願意接受傳染
                     │   └── 整 repo 用同 license
                     │      （例：含大量 CC BY-SA 引用 → 整 repo 用 CC BY-SA）
                     │
                     └── 不願意傳染（想用 MIT 等寬鬆 license）
                            │
                            ├── 選項 A：重寫所有引用部分為 paraphrase
                            │   （自己的話 → 您自己的著作權 → 自由選 license）
                            │
                            └── 選項 B：「割開」兩個 repo
                                   ├── repo A：原 repo（含引用、用 CC BY-SA）
                                   ├── repo B：純原創（用 MIT）
                                   └── 兩 repo 互相連結但不複製貼上
```

#### J.4 「割開」實作步驟（具體做法）

當您決定割開時：

```powershell
# 1. 各自的 GitHub repo
#    seyen37/<研究筆記名>      ← LICENSE: CC BY-SA 4.0
#    seyen37/<網站 / 程式碼名>  ← LICENSE: MIT

# 2. 本機可以一個 Cowork 資料夾、兩個子目錄各 git init
mkdir C:\Users\F0012\Documents\CoWork\<新專案>
cd C:\Users\F0012\Documents\CoWork\<新專案>
mkdir notes website

cd notes
git init
# 建 LICENSE 為 CC BY-SA 4.0（見 J.5）

cd ..\website
git init
# 建 LICENSE 為 MIT（見附錄 B）

# 3. 各自雙推 GitHub（用 §3.5 SOP）
#    notes 目錄推到 seyen37/<研究筆記名> + seyenbot 備份
#    website 目錄推到 seyen37/<網站名> + seyenbot 備份
```

**互相引用的合法做法**：

✅ **可以做**：
- README 加超連結 `[研究筆記](https://github.com/seyen37/<研究筆記名>)`
- 致謝段落提及「本網站基於 ... 研究筆記之研究結果（CC BY-SA 4.0）」

❌ **不要做**：
- 把 notes repo 某段含 CC BY-SA 引用的文字**整段複製**到 website repo
  → 整個 website 變成混合授權麻煩

✅ **可以做（取代上一條的方式）**：
- 用**自己的話 paraphrase** 該段內容，貼到 website repo
  → paraphrased text 是您原創 → 自由選 license

#### J.5 LICENSE 檔案範本（CC BY-SA 4.0 + Apache 2.0）

**CC BY-SA 4.0**（用於文件 / 研究筆記 repo）：

於 repo root 建 `LICENSE` 檔案：

```
This work by 許士彥 (Hsu Shih-Yen) (https://github.com/seyen37) is
licensed under the Creative Commons Attribution-ShareAlike 4.0
International License (CC BY-SA 4.0).

To view a copy of this license, visit:
https://creativecommons.org/licenses/by-sa/4.0/

You are free to:
  - Share — copy and redistribute the material in any medium or format
  - Adapt — remix, transform, and build upon the material for any purpose,
    even commercially.

Under the following terms:
  - Attribution — You must give appropriate credit, provide a link to
    the license, and indicate if changes were made.
  - ShareAlike — If you remix, transform, or build upon the material,
    you must distribute your contributions under the same license as
    the original.
  - No additional restrictions — You may not apply legal terms or
    technological measures that legally restrict others from doing
    anything the license permits.

Suggested attribution format:
  "<work title>" by 許士彥 (Hsu Shih-Yen)
  (https://github.com/seyen37/<repo>),
  licensed under CC BY-SA 4.0.
```

**Apache 2.0**（用於需要 patent grant 的程式碼）：

完整文字從 <https://www.apache.org/licenses/LICENSE-2.0.txt> 複製，將 `Copyright [yyyy] [name of copyright owner]` 改為：
```
Copyright 2026 許士彥 (Hsu Shih-Yen) (https://github.com/seyen37)
```

> **不要忘記 NOTICE 檔**：Apache 2.0 strongly 建議 repo root 也放 `NOTICE` 檔，列出所有第三方依賴的 attribution。

#### J.6 場景手冊：常見實際案例

**場景 1：私人筆記引用 CC BY-SA blog 大段內容**  
✅ **OK**（私人沒分發、license 不觸發）。但寫筆記時就把該段獨立成檔（§8.5），未來公開時容易處理。

**場景 2：把上述筆記轉 public**  
選一：
- A. 整個筆記 repo 用 CC BY-SA 4.0（接受傳染、最簡單）
- B. 重寫所有 CC BY-SA 引用為 paraphrase + 引用連結（自己的話 → 自由 license）
- C. 「割開」（J.4）

**場景 3：要做網站（MIT）、想用筆記某些圖表**  
選一：
- A. 重新繪製、配上自己的描述文字（最乾淨）
- B. 引用圖表的 CC BY-SA 來源 → 在網站某個 `/credits` 頁標清楚 + 整體網站變混合授權（不推薦）
- C. 圖表只放在 notes repo（CC BY-SA），website 用連結指過去（割開）

**場景 4：fork 別人 GPL 程式碼做修改**  
- 您 fork 後的版本**也必須是 GPL**
- 不能改成 MIT 重新發布
- 在自己的 README 明確標出「Based on `<原專案>`, GPL v3.0」

**場景 5：用 Apache 2.0 函式庫到您的 MIT 專案**  
✅ **OK**，但：
- 必須保留原作者 NOTICE 檔（如果原 repo 有的話）
- README 中標出使用了 Apache 2.0 函式庫 + attribution
- 您專案整體仍可是 MIT（不會被 Apache 2.0 「污染」）

**場景 6：自己 repo 的某些檔案想用不同 license**  
可以做，但要**清楚標註**：
- repo root 主 LICENSE
- 例外檔案開頭寫 `<!-- LICENSE: CC BY-SA 4.0, see LICENSE-CC-BY-SA -->`
- 或建 `LICENSES/` 目錄放各別 license 文字
- **建議：除非真的必要，否則整 repo 一個 license 比較好維護**

#### J.7 一個簡單口訣

> **「我以後**（會 / 可能會）**怎麼用這份內容？」**
> 
> 寫第一行字之前、開新 repo 之前，先想 6 個月、1 年、3 年後可能的用法：
> - 變成 GitHub public？
> - 變成網站？
> - 變成書 / 課程教材？
> - 想被別人 fork？想被別人商用？
> 
> 想清楚了，license 怎麼選、檔案結構怎麼分、什麼可以引用什麼不行，自然會浮現。  
> 不確定時，預設選 **最寬鬆的選項 + 最清楚的 attribution**——進可攻退可守。

#### J.8 進階閱讀

- [Creative Commons - License Compatibility](https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/)
- [SPDX License List](https://spdx.org/licenses/)
- [GNU License Compatibility](https://www.gnu.org/licenses/license-compatibility.en.html)
- [TLDRLegal - 各 license 白話對照](https://tldrlegal.com/)
- [choosealicense.com - GitHub 官方 license 選擇器](https://choosealicense.com/)

---

## 十、與 AI 協作時的 prompt 片段

如果你用 Claude Code / 其他 AI 助手協作，把下面這段加進使用者偏好或專案 CLAUDE.md，AI 會自動套用本文件的習慣：

```markdown
## 自動工作習慣（必須遵守）

1. **每次工作結束時**，自動寫決策流（不只成果），存到：
   - 日期型：`docs/decisions/YYYY-MM-DD_topic.md`
   - 模組型：`docs/decisions/mode_NN_topic.md` 或 `infra_NN_topic.md`

2. **決策日誌結構**：每筆決策包含「情境 / 選項 / 決定 / 考量 / 教訓」五段式。
   絕對值得寫的決策：（a）有 2+ 選項且選一個 （b）debug > 30 分鐘
   （c）架構決策 （d）違反直覺的做法。

3. **commit message** 描述「為什麼」而非「做了什麼」。git diff 已經
   告訴讀者做了什麼，commit 該負責解釋動機。

4. **任何 push 之前**：跑 test、`git status` 確認沒夾帶、確認檔案
   不含 secret。

5. **公開前**（Private → Public）：跑 secret 稽核、個資稽核、授權
   稽核，全綠才轉。

6. **新模組第一行**：寫 module docstring，明確「做什麼、不做什麼、
   何時用、何時不用」。

7. **回應使用者** 用繁體中文台灣詞彙，避免大陸用語。

8. **資料源 audit**：使用者要求加入「官方」「政府」「標準」「規範」相關
   的 dataset 時，先問是否有一手公文 PDF / 公報可用。如果只有第三方
   整理品（Gist、GitHub、Wikipedia、學術網站）作為來源，主動 flag 風險：
   提示「第三方整理品可能夾帶他國變體」，建議補一手資料再動工。
   詳見 §六「資料源稽核」。

詳見 docs/PROJECT_PLAYBOOK.md。
```

---

## 十一、給未來自己的話

這份文件不是「規定」，是「我已經試過、確認對自己有用的習慣」。

當你下次新建專案誘惑著想跳過 LICENSE / decision log 時——記得：**這些動作的成本是當下 5 分鐘，省下的是未來 5 小時的回憶 / 解釋 / 防衛工作。**

開源是長期的事，文件是給未來的自己。
