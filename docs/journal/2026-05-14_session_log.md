# 工作日誌 — 2026-05-14（半日，workflow 轉換 day）

**主軸**：5/14 morning audit 看到 personal-playbook §3.10 5/14 升等 default-deny 嚴格化 → user 選 **A 嚴格落實** → 全 day 1 commit (`28c1730`) 完成 PRINCIPLES.md §6.8 補充 + `.gitignore` + commit msg handoff convention 落地 + memory 持久化 → workflow 首跑 retro。**這天沒寫 phase 6z 任何 code、純 workflow 治理 day**。

> 🔗 **前段 5/11 / 5/13**：純讀 audit + PRINCIPLES.md §6.8 cross-ref（小幅 +row, 已整合進 §6.8 mapping table、無另開 journal/decision 檔）。本檔銜接 5/8 收工後第一份正式 journal。

---

## Session 概觀

| 段 | 內容 | Commit |
|---|---|---|
| Morning audit | personal-playbook 5/14 update：§3.10 升等 default-deny / §3.13 strengthen / §8.36 sub-rule 3 / AIQ pptx decisions / git-hooks install 共 7 commits 讀完 | (純讀) |
| QODA 提案 | 3 條 path: A 嚴格落實 / B 實用折衷 / C Hybrid；recommendation 給 B 或 C | (無 commit) |
| User 選 A | 嚴格落實 §3.10 default-deny：sandbox bash **完全不跑** 任何 git 寫入命令 | (無 commit) |
| 落地實作 | PRINCIPLES.md §6.8 加 2026-05-14 補充 +22 行 / `.gitignore` +5 行 / `docs/_commit_msg/2026-05-14_01.txt` 1843 bytes | `28c1730` |
| 首跑 host PowerShell 6-command | user 5 秒 paste 完，push origin + backup 雙 remote 同步 | (28c1730 push) |
| Memory 持久化 | 加 `feedback_strict_default_deny_git.md` + MEMORY.md index +1 line | (auto-memory) |

**狀態**：HEAD `28c1730`、雙 remote 對齊，版號 **0.14.133 不變**（本 commit 0 code 變更、純治理層）。

---

## 1. Morning audit — §3.10 5/14 升等

Personal-playbook 5/14 update 共 7 commits（HEAD 對齊 `40b1130`）。最重磅是兩條 PRINCIPLES.md 修訂：

### 1.1 `f6b5628` (32nd revision) — §3.10 升等

原 §3.10 是「sandbox bash 連續多 `git add` 撞 index corruption → mitigation: 單 batched call + rm + read-tree 重建」。5/14 升等為 **default-deny 嚴格化**：

> Sandbox bash 對該 repo **完全不跑任何 git 寫入命令**，含 `git fetch` / `git status` / `git add` / `git commit` / `git push`（不只先前的 add/commit/push）。

**Rationale**（personal-playbook 紀錄）：sandbox vs host `.git` index 異步、跨 device session 並行 lock race 是隱性風險、即使先前無事故也是倖存者偏差。default-deny 是最安全姿勢、friction 用 commit msg handoff convention 補。

### 1.2 `60b8ff3` (31st revision) — §3.14 strengthen 4

Cowork mount 6 維度補強：UTF-8 / LF / xxd / wc / mojibake 抓法 cross-validate 標準化。本 repo 已 dogfood 5/8 起、不需再動 — 引用即可。

### 1.3 `40b1130` 5/14 worklog（personal-playbook）

記錄 §3.10 升等對 stroke-order 跨 ref 預期：「下次 cross-ref 動作就會把 stroke-order PRINCIPLES.md §6.8 加 row」 — **本 day 就是兌現這條**。

---

## 2. QODA — 3 條 path

我提案 3 條選擇：

| Path | 嚴格度 | Friction | 推薦理由 |
|---|---|---|---|
| A 嚴格落實 | sandbox 0 git-write、全 host PowerShell | 每 commit 6 命令 vs 1 | 安全最大、跨 session 並行 0 風險 |
| B 實用折衷 | sandbox commit OK、push host | 同既有 | 18+ commits 無事故、保留 sandbox velocity |
| C Hybrid | 預設 B、user 提示「另一台在動」就切 A | 條件式 | 平衡彈性 vs 安全 |

**我 recommend B 或 C** — 理由是 18+ commits 跨日節奏實證 sandbox commit + host push 無 lock collision，§3.10 default-deny 是過度保守對應 biped-research 多人協作場景。

**User 選 A** — 嚴格對齊 personal-playbook governance。

### 2.1 User 為何選 A？（推測 + 對話 context）

- Cross-repo governance alignment 偏好（stroke-order 跟著 personal-playbook §3.10 嚴格走、不另立特例）
- 倖存者偏差認知到位（18+ commits 無事故 ≠ 機制安全）
- 願意承擔 friction 換 zero-risk

**Lesson learned**：我下次提 QODA 時、「safer 但 friction ↑」路徑該放第一位、避免我用「實用」當推薦詞 prime user 偏向妥協。User 偏好 governance discipline > Claude velocity。

---

## 3. 落地實作（commit `28c1730`）

### 3.1 PRINCIPLES.md §6.8 加 2026-05-14 補充（+22 行）

插入位置：line 834 空行 → 「**設計意義**：」之間。新區段：

- **5/14 升等表** 3 row：§3.10 5/14 default-deny / §3.13 strengthen 整合 / §8.36 sub-rule 3
- **Workflow 對照表**（5/14 前 vs 5/14 後）7 row 命令類別
- **Commit message handoff convention** 一段：`docs/_commit_msg/YYYY-MM-DD_NN.txt` (gitignore) + `git commit -F`

寫法：Python list-of-strings（§3.14 SOP）。三件套 verify pass：
- `wc -l 891`（前 870 + 22 新 - 1 重疊 = 891 ✓）
- `tail -3` 完整無截斷
- `xxd | tail -c 64` 結尾 `e380 820a` = 「。\n」 UTF-8 + LF

### 3.2 `.gitignore` 加 `/docs/_commit_msg/` 規則（+5 行）

追加在末尾、含註解 line 帶 `(Cowork §3.10 default-deny workflow)`。三件套 verify pass：116 lines / 結尾 `2f0a` = 「/\n」。

### 3.3 `docs/_commit_msg/2026-05-14_01.txt`（1843 bytes）

Commit message 自身存到此檔。內容含：
- Subject line（中文一行）
- Workflow 對照（命令類別）
- 本 commit 3 個檔的角色說明
- 三件套 verify 結果摘要
- Cross-ref personal-playbook commit hash + memory 條目
- `Co-Authored-By:` trailer

33 lines / 結尾 LF / 不入版控（被 `/docs/_commit_msg/` gitignore 過）。

### 3.4 Host PowerShell 6-command 清單

```
cd <repo path>
git status                              # sanity
git add docs/PRINCIPLES.md
git add .gitignore
git status                              # 確認 staged
git commit -F docs/_commit_msg/2026-05-14_01.txt
git push origin main
git push backup main
```

**注意點**：
- `git add` 分行（依 memory `feedback_powershell_commands`）
- `-F` 引用避免中文 escape / heredoc 痛
- 雙 remote (origin + backup) push 維持既有節奏

---

## 4. Workflow 首跑 retro

### 4.1 Round-trip 對照

| 維度 | 5/14 前 (sandbox commit) | 5/14 後 (host commit) | 差 |
|---|---|---|---|
| Claude 端 sandbox 動作 | 寫檔 + git add + git commit (5 cmd) | 寫檔 + 寫 commit msg 檔 (2 cmd) | **-3** |
| User 端 host PowerShell 動作 | 1 cmd (`git push`) | 6 cmd (status×2 + add×2 + commit -F + push×2) | **+5** |
| Commit msg escape 痛 | 0 (sandbox 內聯) | 0 (`-F` 讀檔) | **持平** |
| Git lock race 風險 | 中 (跨 device session 並行隱憂) | 0 | **大降** |
| Sandbox stale index 風險 | 中 (sandbox vs host .git 異步) | 0 | **大降** |

**淨體感**：user 端 friction +5 cmd 但 escape-free（`-F`）抵銷 ~80%；user paste 6 命令 5 秒內完成。**比預期低**。

### 4.2 首跑沒踩到的雷

- 無 `git add` failures（避開 sandbox index）
- 無 push collision（無並行 session）
- 無 commit msg encoding 問題（`-F` 直接讀 UTF-8 LF 檔）
- 無 `.gitignore` 漏配置（`docs/_commit_msg/` 規則正確、未現於 `git status`）

### 4.3 仍待觀察的維度

- 連續多 commit / day 累積 friction 是否 sustainable
- 大型 commit (e.g. 多 phase 共享檔) 是否需要分 commit msg 檔
- 跨 session（多 day 接續）的 `2026-05-14_NN.txt` 編號管理

---

## 5. Memory 持久化

加 `feedback_strict_default_deny_git.md`（31 lines body）+ `MEMORY.md` index +1 line（line 30）。覆蓋：
- Rule + Why + How to apply 三段式（依 memory convention）
- 6-command 清單範本（未來 session 可直接搬）
- Cross-ref personal-playbook commits + stroke-order commit + 3 條相關 memory

**作用**：下次新 Claude session 啟動 auto-load 即可直接套 §3.10 嚴格 workflow、不用 user 再說一次。

---

## 6. 學到的 pattern（適用未來）

### 6.1 「QODA recommendation 排序會 prime user」

我把 B/C 列在 recommendation、A 排在最後，等於暗示妥協是 default。User 選 A 後我反省到：**未來 QODA 提案、safer 路徑應該第一個列、且避免用「實用」「折衷」當 recommend 字眼**。Governance > velocity 是這個 repo 的隱性偏好。

### 6.2 「Commit msg handoff convention 是 friction killer」

原以為「sandbox 不能跑 git commit → user 要 paste 長中文 commit msg」是大 friction。但 `git commit -F <file>` + gitignore 過的 `_commit_msg/` 資料夾、把 escape / heredoc 痛點完全砍掉。**這條 convention 可推廣到所有 sandbox-host workflow split 的場景**（不只 git）。

### 6.3 「Personal-playbook governance 沿用、不另立特例」

Stroke-order PRINCIPLES.md §6.8 mapping 持續展開 row、不在本 repo 另寫 §6.x rule。**單一 source of truth 原則**：governance 在 personal-playbook、工程在 stroke-order PRINCIPLES.md §1-§5+§6.1-§6.7,§6.9-§6.14。§6.8 是 cross-ref bridge。

### 6.4 「Workflow 轉換值得獨立 commit、不混 phase code」

本 commit `28c1730` 0 code 變更、純治理層 + workflow convention。Git history 留下乾淨切片、未來查「default-deny 是何時開始」直接看本 hash。**Don't mix governance with feature code**。

---

## 7. 相關檔案

**Commit `28c1730`**：
- `docs/PRINCIPLES.md` §6.8 +22 行（新 5/14 升等表 + workflow 對照 + handoff convention）
- `.gitignore` +5 行（新 `/docs/_commit_msg/` 規則）
- `docs/_commit_msg/2026-05-14_01.txt`（commit msg 自身、gitignore 過）

**Memory（auto-memory，不入版控）**：
- `feedback_strict_default_deny_git.md`（31 lines）
- `MEMORY.md` index +1 line

**Decision log**：
- 同日 [`2026-05-14_strict_default_deny_workflow.md`](../decisions/2026-05-14_strict_default_deny_workflow.md)

**Cross-ref**：
- personal-playbook commits `60b8ff3` (31st) + `f6b5628` (32nd) + `40b1130` (5/14 worklog)
- 3 條相關 memory：`feedback_cross_session_race` / `feedback_cowork_git_index_single_batched_add` / `feedback_cowork_fs_index_desync`

---

## 8. 未來 path

- **6z-6 切割 mode** 實作（plan + 6 QODA 寫好、未動工、~5-6h）— 首次走完 §3.10 嚴格 workflow 的 feature commit
- **6z-3.5.X polish**（outline 外點警告 / R2 raycast / 4 個 tangle 增補）
- **6z-7 ~ 6z-12**（gamepad / embedded / draft / gallery / final tests / marketing）
- **Workflow sustainability 觀察**：累積 5+ commit 後評估 friction 是否需要 affordance 加強（e.g. `_commit_msg/` 內建編號 helper）

---

**結語**：5/14 是 stroke-order 第一個「純治理 day」 — 0 feature code、全力把 §3.10 嚴格 default-deny 落地。Workflow 首跑無事故、friction 低於預期。下次 phase 6z-6 開動將是首次 feature commit 走完整新流程。
