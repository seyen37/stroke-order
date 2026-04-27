# 推到 GitHub 完整步驟

最後更新：2026-04-26 · 對應 v0.13.0 首次公開推送

---

## 前置確認

1. 你的 GitHub repo 已建好且為**空的**（沒有 README、沒有 LICENSE、沒有任何檔案）：
   - URL：`https://github.com/seyen37/stroke-order`
   - 若 repo 不是空的，先到 GitHub Settings → 刪除重建，或 clone 下來再覆蓋

2. 你的本機 Git 已設好 SSH key 或 HTTPS 認證，可 push 到自己的 GitHub
   ```bash
   ssh -T git@github.com
   # 應顯示 "Hi seyen37! You've successfully authenticated, …"
   ```
   若還沒設好認證 → 先看 [`GIT_AUTH_SETUP.md`](GIT_AUTH_SETUP.md)（含 SSH / HTTPS / GitHub CLI 三種方式 + 三作業系統指引）

3. 確認本機 Git 全域設定（commit author 用得上）：
   ```bash
   git config --global user.name        # 應顯示「許士彥」或 seyen37
   git config --global user.email       # 應顯示 seyen37@gmail.com
   ```
   若沒設過，用：
   ```bash
   git config --global user.name "許士彥"
   git config --global user.email "seyen37@gmail.com"
   ```

---

## Step 1：開啟你本機的終端機

cd 到 stroke-order 專案所在的資料夾。例：

```bash
cd ~/path/to/stroke-order
```

確認你在對的資料夾：
```bash
ls
# 應該看到 README.md, pyproject.toml, src/, tests/, docs/, ... 等
```

---

## Step 2：清掉 Cowork sandbox 留下的不完整 .git

Cowork 嘗試初始化但 mount filesystem 不允許寫入 lock 檔，留下一個**空殼 .git/**。先清掉：

```bash
rm -rf .git
ls -a | grep '^.git'    # 確認真的清空（只該看到 .gitignore .github，沒有 .git）
```

---

## Step 3：初始化 git + 設定本 repo 的 author

```bash
git init -b main

# 確認 author 是繁體中文姓名（這對版權有用）
git config user.name  "許士彥"
git config user.email "seyen37@gmail.com"
```

> 若你想讓**這個 repo 的設定**跟全域 git config 不同（譬如全域用英文名字），上面 local config 會 override 全域。否則用全域即可。

---

## Step 4：分批 commit（誠實版 — 4 個 commits，全部今天 timestamp）

> **理由**：見 `docs/decisions/`——我們選擇誠實版而非偽造日期，因為法庭 / 訴訟非常重視時戳的可信度。所有 commit 都是今天的真實時間，配合 GitHub server-side push timestamp 就是強證據。

### Commit 1：開發脈絡資料先行（讓 reviewer 一打開就看到 narrative）

```bash
git add docs/
git status                       # 確認只 add 了 docs/
git commit -m "docs: import development records (decisions/, WORK_LOG, GALLERY_DEPLOYMENT, QUICK_START)

This repository's git history begins on 2026-04-26 with v0.13.0
first-time publication, but the codebase itself was developed locally
across 67 internal phases (Phase 1 → Phase 5g) prior to this commit.

The decision logs in docs/decisions/ retroactively reconstruct the
key design choices, alternatives considered, difficulties encountered,
and final solutions, based on phase tags + design comments + test
docstrings embedded in the source code.

See README.md '開發歷程' section + docs/HISTORY.md (when produced)
for the full timeline."
```

### Commit 2：源碼

```bash
git add src/
git status
git commit -m "feat: import source code at v0.13.0

- 9 web UI modes: 單字 / 字帖 / 筆記 / 信紙 / 稿紙 / 塗鴉 / 文字雲 /
  筆順練習 (5d) / 公眾分享庫 (5g)
- 13 character data sources: g0v / mmh / kanjivg / cns_font /
  punctuation / user_dict / chongxi_seal / moe_lishu / moe_song /
  moe_kaishu / cns_components / cns_strokes
- Independent gallery package with email magic-link auth + SQLite
- ~5000 lines of Python + 6 ES module frontend"
```

### Commit 3：測試套件

```bash
git add tests/
git status
git commit -m "test: import test suite (1057 tests, 41 skipped)

Phase 1 → 5g coverage:
- Character IR + classifier + smoothing + validation
- 13 source adapters
- All 9 web UI modes incl. routing + rendering
- Gallery 19 core + 24 API tests (5g)
- Handwriting page 26 tests (5d)
- Sutra mode evolution 5bv → 5cc"
```

### Commit 4：專案中繼資料 + CI

```bash
git add pyproject.toml LICENSE README.md REF_ANALYSIS_*.md \
        .gitignore .github/
git status
git commit -m "chore: project metadata, MIT LICENSE, GitHub Actions CI

- pyproject.toml: package + 4 optional extras (web/gif/all/dev)
- LICENSE: MIT for code; third-party data sources retain own licenses
- README.md: badges, dev history note, install + run instructions
- .github/workflows/ci.yml: pytest matrix on Python 3.10/3.11/3.12
  for both push and PR. Each CI run leaves a public timestamp."
```

### 確認 4 個 commits 都好了

```bash
git log --oneline
# 應該顯示 4 行（最新在上）：
#   <hash>  chore: project metadata, MIT LICENSE, ...
#   <hash>  test: import test suite (1057 tests, 41 skipped)
#   <hash>  feat: import source code at v0.13.0
#   <hash>  docs: import development records (...)
```

---

## Step 5：加 remote 並 push

```bash
git remote add origin git@github.com:seyen37/stroke-order.git

# 也可改用 HTTPS（若沒設 SSH key）：
# git remote add origin https://github.com/seyen37/stroke-order.git

# 確認 remote 設好
git remote -v

# Push
git push -u origin main
```

push 完成後到 https://github.com/seyen37/stroke-order 看：
- 4 個 commits 都在
- README 顯示 5 個 badges（CI 那個一開始會是「pending」/「unknown」，等 CI 跑完才綠）
- LICENSE 旁邊應有「MIT」標示

---

## Step 6：等 GitHub Actions CI 跑完

Push 後 GitHub 自動觸發 CI（`.github/workflows/ci.yml`）：

1. 開 `https://github.com/seyen37/stroke-order/actions`
2. 應看到一筆「CI」run 在跑（黃色圓圈）
3. 約 3–5 分鐘後變綠（pytest 1057 條全綠的話）
4. 變綠後 README 上的 CI badge 也會自動變「passing」

**這是版權保護上的關鍵步驟**：每次 CI run 都有 GitHub server-side timestamp + 完整 log，是不可偽造的第三方證據，證明你的 code 在 N 月 N 日這個時間點通過 1057 個測試。

> 若 CI 失敗：通常是 cairo 系統依賴或 Python 版本相關問題。打開失敗 log，根據錯誤訊息調整 `.github/workflows/ci.yml`。常見處理：
>
> - **`No module named 'fastapi'`** → `pip install -e ".[dev]"` 沒裝好，檢查 pyproject 的 dev extras
> - **`cairosvg.surface.UnsupportedSVG...`** → 系統 cairo 庫缺，CI yaml 加 `apt-get install libcairo2-dev`
> - **CJK font 缺**：`fonts-noto-cjk` 預設沒裝；CI runs 可能跳過部分需要 CJK 的 raster 測試

---

## Step 7（可選但推薦）：補上 v0.13.0 git tag

```bash
git tag -a v0.13.0 -m "First public release: 9 web UI modes, 1057 tests passing

This is the first public commit of stroke-order, after extensive local
development across 67 internal phases. See docs/decisions/ for the
full design history."

git push origin v0.13.0
```

之後 https://github.com/seyen37/stroke-order/releases 可以基於這個 tag 建立正式的 GitHub Release（含 release notes、可附下載 zip）。

---

## Step 8（強化版權證據，可選）

### 8a. 開啟 branch protection
- GitHub → Settings → Branches → Add rule for `main`
- 勾選「Require pull request before merging」+「Require status checks (CI)」
- 防止未來自己誤直接 push 破壞 history

### 8b. GPG sign commits（若有 GPG key）
```bash
git config --global user.signingkey YOUR_GPG_KEY_ID
git config --global commit.gpgsign true
```
之後每個 commit 都會帶簽章，GitHub 顯示「Verified」徽章。

### 8c. OpenTimestamps（免費 blockchain 時戳）
```bash
# 把當前 commit hash 上鏈
ots stamp .git/refs/heads/main
```
產生的 `.ots` 檔可作為「我在 X 時間擁有這個 git 狀態」的密碼學證據，無法事後偽造。

### 8d. 智慧局著作權登記（公示效果）
台灣作者可向經濟部智慧局申請著作權登記。雖非強制，但訴訟時提供公示證據。
- 表格：[經濟部智慧財產局著作權登記](https://www.tipo.gov.tw/)

---

## Step 9：之後的維護循環

每次本機改完一段功能：

```bash
# 編輯程式碼 / 文件
git status                 # 看改了什麼
git add <files>
git commit -m "feat(...): ..."
git push
```

> 提醒：commit message 寫詳細點對未來自己有幫助；Conventional Commits 格式（`feat:`/`fix:`/`docs:`/`test:`/`chore:`/`refactor:`/`perf:`）方便用 `git log --oneline` 一眼掃。

---

## 常見問題

### Q: push 時 GitHub 拒絕「main 跟 master 衝突」
GitHub 預設新 repo 是 `main` branch，但如果舊版 git 預設 `master`，要改：
```bash
git branch -M main
git push -u origin main
```

### Q: SSH key 沒設好，能用 HTTPS push 嗎？
可以：
```bash
git remote set-url origin https://github.com/seyen37/stroke-order.git
git push
# 會跳出帳號密碼提示。HTTPS 需要 Personal Access Token（不是登入密碼），
# 在 GitHub Settings → Developer settings → Personal access tokens 申請
```

### Q: CI 跑很慢、想取消
- 在 Actions 頁面點該 run → 「Cancel workflow」
- 或在 commit message 加 `[skip ci]` 跳過 CI（但這次不建議跳）

### Q: 我想把 commit author 顯示為英文「Allen Hsu」？
local config 改 user.name 即可：
```bash
git config user.name "Allen Hsu"
# 注意：只影響「之後」的 commit；歷史 commit 要 amend / rebase 才能改
```

對版權影響：英文名 vs 中文名都可，重點是**跟你 pyproject.toml 跟 LICENSE 一致**。我的建議是統一用「許士彥」中文，你 pyproject 已經是這個。

### Q: 我寫的程式碼裡有別人的程式碼怎麼辦？
- 用到 g0v / MMH / KanjiVG 等資料源 = OK，那些是「資料」，授權資訊在 LICENSE 跟 sources/ docstring
- 用到別人的程式碼片段 = 必須在源碼註明出處 + 該段程式碼的授權
- 用到 stack overflow / blog 的範例 = 一般可重寫；若實質照搬 > 10 行，建議註明

---

## 推送完成的檢查清單

- [ ] `https://github.com/seyen37/stroke-order` 顯示 4 個 commits + 你的繁中姓名
- [ ] README 上方 5 個 badges 都顯示
- [ ] LICENSE 顯示 MIT
- [ ] `.github/workflows/ci.yml` 在 Actions tab 跑了
- [ ] CI 變綠（badges 自動更新成 passing）
- [ ] v0.13.0 tag 在 Releases 頁可看到
- [ ] （可選）GPG signed commits 顯示 Verified 徽章
- [ ] 自己 clone 一份到別的資料夾驗證 push 完整：
      ```bash
      cd /tmp
      git clone git@github.com:seyen37/stroke-order.git
      cd stroke-order
      pip install -e ".[dev]"
      pytest tests/             # 應該 1057 passed
      ```

---

## 之後新增決策日誌的工作流

我們講好「每次工作結束自動寫決策日誌」（規則記在 `.auto-memory/`，未來對話會自動套用）。下次工作完成後產出 `docs/decisions/<新檔>.md` 後：

```bash
git add docs/decisions/<新檔>.md
git commit -m "docs: add decision log for <主題>"
git push
```

每次 push 都是另一個第三方時戳 — 漸進累積證據鏈。

---

完成 push 後告訴我，我會繼續做 Batch 2 的考古決策日誌（mode_02 / mode_03 / infra_02）。
