# 個人專案 Playbook

> 許士彥（Hsu Shih-Yen）GitHub 專案的標準化實踐
>
> 這份文件凝結了從 stroke-order 累積出來的個人最佳實踐：智慧財產權保護、雙帳號備份、決策日誌自動化、與 AI 協作時的工作紀錄習慣。
>
> 任何新建 GitHub 專案的第一天，把這份文件 copy 進新 repo 的 `docs/PROJECT_PLAYBOOK.md`，再依新專案實際內容調整即可。
>
> 最後更新：2026-04-28

---

## 目錄

1. [新專案第一天清單](#一新專案第一天清單)
2. [智慧財產權三件套](#二智慧財產權三件套)
3. [多帳號 GitHub 備份](#三多帳號-github-備份)
4. [工作紀錄自動化規則](#四工作紀錄自動化規則)
5. [決策日誌自動化規則](#五決策日誌自動化規則)
6. [公開前審查清單](#六公開前審查清單)
7. [長期維護習慣](#七長期維護習慣)
8. [附錄：可複製模板](#八附錄可複製模板)
9. [與 AI 協作時的 prompt 片段](#九與-ai-協作時的-prompt-片段)

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

**為每個帳號各產一支 ed25519 key**：
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_seyen37
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_seyenbot
```

**`~/.ssh/config` Host alias**：
```
Host github.com-seyen37
  HostName github.com
  IdentityFile ~/.ssh/id_ed25519_seyen37

Host github-backup
  HostName github.com
  IdentityFile ~/.ssh/id_ed25519_seyenbot
```

各帳號 GitHub 設定 → SSH and GPG keys → 加入對應 public key。

### 3.3 雙 remote 設定

```bash
git remote add origin git@github.com-seyen37:seyen37/PROJECT.git
git remote add backup git@github-backup:seyenbot/PROJECT.git
```

### 3.4 一行同步推送 alias

```bash
git config --global alias.pa '!git push origin main && git push backup main'
```

之後 `git pa` 一行同步推兩個 remote。`&&` 鏈意味著 origin 失敗時 backup 不會跑——這是故意的（讓你先處理 origin 問題）。

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

---

## 六、公開前審查清單

repo 從 Private 改 Public 之前，**必跑**：

### 6.1 Secret 稽核

```bash
# 搜尋常見 secret 關鍵字
git grep -i "password\|secret\|api_key\|token\|credentials" -- ":!docs/" ":!*.md"

# 確認 .env 在 .gitignore
grep "^\.env" .gitignore
```

### 6.2 個資稽核

- [ ] commit message 沒有寫到家裡地址 / 私人電話 / 銀行帳號
- [ ] 程式碼註解沒有客戶 / 朋友本名
- [ ] 截圖 / 測試資料沒有真實個人資訊

### 6.3 授權稽核

- [ ] LICENSE 存在且資訊正確
- [ ] 第三方資料 / 字型 / 圖片授權都有 attribution
- [ ] 拷貝來的程式碼有註明來源 + 原 license

### 6.4 文件稽核

- [ ] README 第一段能讓陌生人 30 秒理解專案
- [ ] 安裝 / 啟動指令確認可重現
- [ ] 至少一份 `docs/decisions/` 已寫好

---

## 七、長期維護習慣

### 7.1 每次 push 前

- [ ] 跑 `pytest`（或同等 test runner）確認綠燈
- [ ] `git status` 確認沒夾帶意外檔案
- [ ] commit message 描述「為什麼」而非「做了什麼」

### 7.2 每週一次

- [ ] 看一下 GitHub Actions 是否仍綠
- [ ] 看一下 Render / 部署平台 cold start 健康度
- [ ] 整理當週 `docs/decisions/` 是否有遺漏

### 7.3 每月一次

- [ ] 升級依賴（`pip list --outdated`）
- [ ] Review `docs/HISTORY.md` 是否反映目前狀態
- [ ] 清理 stale branches

### 7.4 每個 release

- [ ] bump version
- [ ] 寫 release notes
- [ ] 更新 README badges 數字（測試數、版本）
- [ ] tag the commit (`git tag v0.x.x`)

---

## 八、附錄：可複製模板

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

---

## 九、與 AI 協作時的 prompt 片段

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

詳見 docs/PROJECT_PLAYBOOK.md。
```

---

## 十、修訂歷史

- 2026-04-28：初版。基於 stroke-order 專案累積的實踐凝結。
- (未來修訂在此記錄)

---

## 十一、給未來自己的話

這份文件不是「規定」，是「我已經試過、確認對自己有用的習慣」。

當你下次新建專案誘惑著想跳過 LICENSE / decision log 時——記得：**這些動作的成本是當下 5 分鐘，省下的是未來 5 小時的回憶 / 解釋 / 防衛工作。**

開源是長期的事，文件是給未來的自己。
