# 個人專案 Playbook

> 許士彥（Hsu Shih-Yen）GitHub 專案的標準化實踐
>
> 這份文件凝結了從 stroke-order 累積出來的個人最佳實踐：智慧財產權保護、雙帳號備份、決策日誌自動化、與 AI 協作時的工作紀錄習慣。
>
> 任何新建 GitHub 專案的第一天，把這份文件 copy 進新 repo 的 `docs/PROJECT_PLAYBOOK.md`，再依新專案實際內容調整即可。
>
> 最後更新：2026-04-29

---

## 目錄

1. [新專案第一天清單](#一新專案第一天清單)
2. [智慧財產權三件套](#二智慧財產權三件套)
3. [多帳號 GitHub 備份](#三多帳號-github-備份)
4. [工作紀錄自動化規則](#四工作紀錄自動化規則)（含 §4.5 Backfill 規則）
5. [決策日誌自動化規則](#五決策日誌自動化規則)（含 §5.7 何時不該立即實作）
6. [**資料源稽核（Source-of-Truth Audit）**](#六資料源稽核source-of-truth-audit)（含 §6.5 多源 triangulation）
7. [公開前審查清單](#七公開前審查清單)（含 §7.5 第三方資料源 attribution 完整性）
8. [長期維護習慣](#八長期維護習慣)（含 §8.5 Morning audit ritual）
9. [附錄：可複製模板](#九附錄可複製模板)
10. [與 AI 協作時的 prompt 片段](#十與-ai-協作時的-prompt-片段)
11. [修訂歷史](#十一修訂歷史)
12. [給未來自己的話](#十二給未來自己的話)

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
6. **Backfill source of truth**：當 work log 來不及當天寫時，事後 retrospective 重建只能靠 decision log + git log（見 §四.5）。決策日誌寫得詳實 = 未來重建 timeline 的可能性

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

這個習慣源於一個典型 pattern：第三方整理品 vs 一手官方源比對，發現「字數一樣 / 但內容有 0.02% 變體字污染」。**真實案例請見各專案的 `docs/decisions/` 紀錄**。

### 6.1 何時必跑

任何時候加入新資料源——**不只是 public release 之前**。

觸發場合：
- 引用「政府」「國家標準」「國際協議」「ISO」的清單 / 規範 / 詞典
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

- [ ] 一手 vs 第三方逐字比對（數量、項目 ID、codepoint 都要對）
- [ ] 任何差異都要追蹤原因（是第三方 OCR 錯？變體污染？版本差？人為刪改？）
- [ ] 差異 ≥ 0 時，**永遠採用一手**，並把差異記錄進決策日誌
- [ ] 一手本身有 metadata bug 時（如 PDF metadata 與實際內容不一致），明示「以實際內容為準」
- [ ] **多個一手官方源同時可得時，做 cross-verification**——兩個獨立官方源逐項比對，比單源高一級品質。共有的 metadata bug 反而是「兩個源都來自同一原始檔」的證據

**C. 區域變體完整性（Locale-variant integrity）**

> 概念框架以 CJK 漢字為例，但原則適用任何有區域變體的資料（拼音 vs Pinyin / Wade-Giles、地名拼寫、計量單位...）。

- [ ] 確認所有資料項屬於目標區域標準
  - 對 CJK 漢字：T (Taiwan/CNS 11643) / G (PRC/GB18030) / H (HK) / J (Japan/JIS) / K (Korea/KSC) / V (Vietnam) 各有不同 codepoint
  - 對其他資料：依該領域的區域標準對齊
- [ ] 對近似項（外觀像但底層編碼不同）特別留意。CJK 已知陷阱：
  - 彞 (U+5F5E, T) vs 彝 (U+5F5D, G)
  - 汨 (U+6C68) vs 汩 (U+6C69)
  - 「過」在 G/H/T/J/K/V 各有不同變體
- [ ] 工具：Unicode 17.0 CJK chart `https://www.unicode.org/charts/PDF/U4E00.pdf` 字元下方 G/H/T/J/K/V 標註對應區域變體
- [ ] **Locale-specific 罕字（PUA、Ext G+ 等本地語言特有字）要保持寬容**——這正是 locale-first 哲學的 niche value，不能盲目過濾。Locale 內的「冷僻字」往往是該 locale 文化獨有資產

### 6.3 範例 pattern：第三方變體字污染

**情境（通用化）**：第三方整理者把標榜為某地區官方標準的清單放上 GitHub 或網站。內容 99%+ 與官方一致，但其中 1-2 項夾帶了「外觀近似但 codepoint 屬於他國規範」的變體。

**發現方式**：取得一手官方源後逐項對比。

**結論**：改用一手源作為唯一資料源；保留 traceability 欄位（官方編號 / 公告日 / 發布單位）。

**啟示**：「數量一樣 = 內容一樣」是錯誤直覺。**99.98% 相同也夠污染**——這是「供應鏈污染」的警示燈。

> 真實案例見各專案的 `docs/decisions/`，含 codepoint 細節、修法、追溯文號。

### 6.4 自動化建議

如果資料源是會反覆更新的（例如某類官方標準每幾年發布新版）：

- 寫 `scripts/build_<source>.py`：從一手公文自動萃取 → 標準 JSON / DB
- script 本身要：
  - 文件開頭 docstring 明確記錄資料源 URL + 出版日 + 版本
  - 預期項目 count 在 sanity check 範圍內（避免 PDF parsing 失敗 silent fallback）
  - **Cross-check 內容 vs metadata**（catch source-side bugs）
  - 輸出含 traceability 欄位（官方編號、流水序號、發布日期）

通用 pseudocode：

```python
# 從官方 PDF / XLSX / API 萃取
# 一項一比對 metadata vs 實際內容
# 主資料 + variant mapping + traceability 三合一輸出
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

### 6.6 給 Future Self 的話

「為什麼花這個力氣？只是 1 個變體的差異而已。」

因為「locale-first」是個 claim，不是 default——如果你的 codebase 從一開始就有 audit 習慣，這個 claim 站得住腳；如果省略了，10 年後想補 audit 會發現要回頭比對幾十個資料源——那個 cost 比現在多 100 倍。

> 「資料源頭管理是著作權保護的第一道關卡。」
> — 摘自某專案決策日誌

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

### 7.3 授權稽核

- [ ] LICENSE 存在且資訊正確
- [ ] 第三方資料 / 字型 / 圖片授權都有 attribution
- [ ] 拷貝來的程式碼有註明來源 + 原 license

### 7.4 文件稽核

- [ ] README 第一段能讓陌生人 30 秒理解專案
- [ ] 安裝 / 啟動指令確認可重現
- [ ] 至少一份 `docs/decisions/` 已寫好

### 7.5 第三方資料源 attribution 完整性

7.3 授權稽核的細項——**逐一比對：codebase 引用的所有資料源，是否在 LICENSE 末段都有 attribution**。

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

> 檢查觸發點：每次 release 前 + repo 從 Private 改 Public 前 + 新增 cover-set / dataset / 字型 / 圖庫的 commit。

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

### 8.5 Morning audit ritual

每個工作日新 session 開始前，跑 SOP 一致性掃描——**通常 30 分鐘內可完成，效益是後續 4-8 小時的工作不在歪掉的基礎上累積**。

掃描清單：

- [ ] **§二 IP 三件套**：LICENSE / README / footer 三處身份鏈是否一致？
- [ ] **§三 雙 remote**：origin + backup 都活著？最新 commit 兩邊都到了？
- [ ] **§四 work logs**：上一個工作日的 work log 有沒有寫？沒寫立刻補（§四.5 backfill）
- [ ] **§五 decision logs**：上一個工作日的關鍵決策有沒有 log？
- [ ] **§六 audit checklist**：新引入的資料源有跑過三段檢查嗎？
- [ ] **§七 attribution 完整性**：新增資料源有寫進 LICENSE 末段？
- [ ] **§八.4 release tag**：上一個 version bump 有對應 git tag？

發現 gap：寫進今天的工作項目（前 30-60 分鐘清掉），再進主工作。

> **為什麼這個習慣值錢**：SOP 寫進 playbook 是一回事，**確實執行是另一回事**。Morning audit 是「對自己的 SOP 服從度的誠實度測試」——即使每次都全綠，這個 ritual 本身就是對 SOP 的尊重。

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

## 十一、修訂歷史

> 原則：本表只記錄「**跨專案抽象原則**」的演進。觸發某條原則的真實案例（誰、何時、哪份檔案、什麼 bug）一律寫在**各專案的決策日誌**，不重複出現在 playbook。

- **2026-04-28**：初版。凝結個人新建 GitHub 專案的標準化實踐——IP 三件套、雙帳號備份、決策日誌自動化、AI 協作工作紀錄習慣。
- **2026-04-28（同日修訂）**：新增 §六「資料源稽核 Source-of-Truth Audit」。
  抽象原則：當「官方 / 政府 / 標準 / 規範」名義的 dataset 進專案時，必跑 A/B/C 三段檢查（一手公文 → 內容比對 → 區域變體完整性）。背景動機是「民間整理的官方資料常被他國規範變體污染」這個跨領域普遍議題。
  其他章節 §六~§十一 統一往後挪一號。§十 AI prompt 補第 8 條 audit 規則。
- **2026-04-29（morning audit 後修訂）**：將 playbook 從「敘事＋特定專案案例」抽象化為「純跨專案原則」。
  - 起因：morning audit 時發現 §六、§七 等章節夾帶過多單一專案的具體案例（檔名、codepoint、特定 bug）。違反 playbook「**跨專案共通性原則**」的定位——專案實況屬於專案的 work log / decision log，playbook 只放可被多個專案重用的抽象。
  - **新增章節 / 子章節**：
    - **§四.5 Backfill 規則**：work log / decision log 漏寫時的補寫流程（git log + 決策日誌 反向重建，標註「Backfill 補寫」誠實標籤）。
    - **§五.6 補一條 backfill source-of-truth**：work log 缺漏時用決策日誌 + git log 重建。
    - **§五.7 何時不該立即實作 決策框架**：4 問 gate（必要性 / 替代品 / 機會成本 / 可逆性），預防 scope creep。
    - **§六.5 多源 triangulation**：當同一資料有多個一手官方來源時，用 strict / majority / any 三層 consensus schema 區分。
    - **§七.5 第三方資料源 attribution 完整性**：LICENSE 末段 attribution block 必須涵蓋所有 ingest 的第三方資料，作為 §七 的第 5 個必跑項。
    - **§八.5 Morning audit ritual**：每日開工前花 5–15 分鐘對照 playbook 自我檢查 SOP 服從度，補上昨天漏掉的 work log / 漏跑的 §六 audit 等。
  - **§六 重寫**：移除單一專案 case study（教育部 4808、彝 / 彞 codepoint、build_*.py 檔名），改為「典型 pattern」描述 + 指向「真實案例見各專案決策日誌」。
  - **§六.2.C 命名修正**：「Taiwan-variant integrity」→ 「Locale-variant integrity」，並補 PUA / Ext G+ 罕字容忍度說明（罕字保留為 locale-first niche 價值，不能因 G/H/J/K 缺對應就刪）。
  - **§六.2.B 補一條 cross-verification**：多個一手源同時可得時做交叉驗證，差異追因。
  - 抽象化後 playbook 仍保留「為什麼這條原則存在」的動機描述，但不再 hardcode 哪個專案、哪份檔案觸發這個原則——保證 playbook 可被任何新專案 copy + 立即適用。

---

## 十二、給未來自己的話

這份文件不是「規定」，是「我已經試過、確認對自己有用的習慣」。

當你下次新建專案誘惑著想跳過 LICENSE / decision log 時——記得：**這些動作的成本是當下 5 分鐘，省下的是未來 5 小時的回憶 / 解釋 / 防衛工作。**

開源是長期的事，文件是給未來的自己。
