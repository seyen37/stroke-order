# 決策日誌：§3.10 default-deny 嚴格 workflow 採用（2026-05-14）

**日期**：2026-05-14
**版號變化**：0.14.133 → 0.14.133（純治理層、不改 code、不 bump）
**對話 / 工作期間**：早上 morning audit 看到 personal-playbook 5/14 升等 §3.10 default-deny → 提 QODA → user 選 A 嚴格落實 → 全 day 1 commit `28c1730` 落地

---

## 整體脈絡

> Personal-playbook 第三十一/三十二次修訂（`60b8ff3` / `f6b5628`）5/14 升等 §3.10 Cowork sandbox bash git index corruption SOP — 從原本「sandbox 多 `git add` 撞 index → 用 batched call mitigate」 進化為 **default-deny 嚴格化**：sandbox bash **完全不跑** 任何 git 寫入命令（含 `git fetch` / `git status` / `git add` / `git commit` / `git push`）。
>
> Stroke-order repo 過去 18+ commits 採 sandbox commit + host push 模式雖無事故，但屬倖存者偏差。本決策確認 stroke-order 是否要嚴格對齊 personal-playbook governance、以及如何降低 friction。

---

## 決策 1：§3.10 default-deny 嚴格度

**觸發**：Personal-playbook 5/14 升等後，stroke-order 是否要嚴格採用。

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 嚴格落實 — sandbox 0 git-write、全 host PowerShell | 安全最大、跨 device session 並行 0 風險、與 personal-playbook governance 對齊 | User 端 friction +5 命令 / commit |
| B | 實用折衷 — sandbox commit OK、push host | 保留既有 velocity、18+ commits 實測無事故 | 殘留 sandbox stale index 風險、governance drift |
| C | Hybrid — 預設 B、user 提示「另一台在動」就切 A | 條件式彈性 | 認知負擔 ↑、context-switch overhead |

**考慮的因素**：
- Governance alignment（stroke-order 是否要 mirror personal-playbook 規則）
- 倖存者偏差（18+ commits 無事故 ≠ 機制安全）
- Friction 可控性（user 端命令數 vs 安全度）
- Commit msg handoff 解法可行性（決定 friction 是否實際很高）

**選擇**：☑ **A 嚴格落實**

**理由**：
> User 偏好 cross-repo governance alignment（stroke-order 跟 personal-playbook §3.10 嚴格走、不另立特例）。倖存者偏差認知到位 — 18+ commits 無事故只是運氣未踩到觸發條件。Friction +5 命令看似多，但用 `git commit -F docs/_commit_msg/...txt` convention 可砍掉 PowerShell 中文 escape / heredoc 痛、淨痛點 ~80% 抵銷。

**後續驗證 / 結果**：
- ✅ Commit `28c1730` 首跑成功、雙 remote (origin + backup) 同步
- ✅ User 端 6 命令 5 秒內 paste 完
- ✅ 0 git error / 0 escape issue / 0 push collision
- ⏳ 需累積 5+ commits 後評估長期 sustainability

---

## 決策 2：Commit message handoff convention

**觸發**：選 A 後最大 friction 是「user 要 paste 長中文 commit message」。如何降痛？

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | Claude 把 msg 內嵌 Markdown、user 複製貼到 PowerShell `git commit -m "..."` | 無新檔 | 中文 + 引號 + `§` 符號 escape 痛、PowerShell 多行字串 syntax 限制 |
| B | Claude 寫 msg 到 `docs/_commit_msg/YYYY-MM-DD_NN.txt`、user 跑 `git commit -F <檔>` | escape-free、檔保留供 paste-history 參考 | 多一個 gitignore 規則 + 多一個檔 |
| C | Claude 用 here-string syntax 寫成 PowerShell 命令 | 看似一條命令 | here-string 在 PowerShell 中文支援差、easy 踩雷 |

**選擇**：☑ **B `-F` 引用檔**

**理由**：
> `git commit -F <file>` 是 git 內建、跨平台、UTF-8 + LF 直讀、完全繞過 shell escape。多一個 gitignore 規則 + 多一個 1843-byte 檔的成本 vs PowerShell 中文 escape 痛、CP 值極高。額外好處：commit msg 檔保留在本機、未來查 commit hash 對應的詳細 msg 不用 git show、直接看檔。

**Convention 規範**：
- 路徑：`docs/_commit_msg/YYYY-MM-DD_NN.txt`
- NN 從 01 起、跨 day 不續編（每 day 從 01 起）
- 寫法：Python list-of-strings + `\n.join` + `newline='\n'`（§3.14 SOP）
- gitignore 整個資料夾：`/docs/_commit_msg/`
- User PowerShell：`git commit -F docs/_commit_msg/YYYY-MM-DD_NN.txt`

**後續驗證 / 結果**：
- ✅ 5/14_01.txt 1843 bytes / 33 lines / 結尾 LF
- ✅ `git commit -F` 一次 paste 成功、commit message 完整保留
- ✅ git status 確認檔不入版控（gitignore 生效）

---

## 決策 3：不另開 stroke-order §6.x rule、用 §6.8 mapping row

**觸發**：§3.10 default-deny + commit msg handoff convention 是否要在 stroke-order PRINCIPLES.md 開新 §6.x rule？

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 開 §6.15「Cowork §3.10 default-deny workflow」新 rule | 在 stroke-order 自成體系 | Source-of-truth drift 風險、未來 personal-playbook §3.10 再升等 stroke-order 沒同步 |
| B | 在 §6.8 mapping table 加 row + workflow 對照表 | 單一 SoT（personal-playbook 為主）、cross-ref 一次到位 | §6.8 mapping table 變長 |
| C | 兩處都寫（§6.15 規則 + §6.8 mapping row） | 規則與 mapping 都查得到 | DRY 違反、修改成本 ×2 |

**選擇**：☑ **B 只在 §6.8 mapping table 補**

**理由**：
> Stroke-order PRINCIPLES.md §6.8 從 5/7 起的設計就是「mapping bridge — governance 在 personal-playbook、工程在 §1-§5 + §6.1-§6.7 + §6.9-§6.14」。§3.10 是 AI workflow 治理層 SOP、非 stroke-order 工程 rule、應該維持單一 SoT。§6.8 加 row + workflow 對照表 + commit msg handoff convention 三段足夠未來查詢；真正權威來源永遠是 personal-playbook §3.10。

**Pattern**：
- ✅ Cross-cutting governance / AI workflow SOP → personal-playbook 主、stroke-order §6.8 row 引用
- ✅ Stroke-order 純工程 implementation 經驗 → §6.1-§6.7 / §6.9-§6.14 直接寫
- ❌ 不要雙寫（DRY 違反、drift 風險）

**後續驗證 / 結果**：
- ✅ §6.8 加 3 row 5/14 升等表 + workflow 對照表 + handoff convention
- ✅ §6 子節順序註保持原樣（6.1-§6.7 + §6.9-§6.14 + §6.8 mapping 最末）
- ✅ 未來 §3.10 再升等只動 §6.8 一處

---

## 沒做的決策（明確擱置）

> 這次討論到但**刻意不做**：

- **不寫 sandbox-side `git status` 替代命令** — 想過 `ls -la` + Python `wc -l` 結合提供 sandbox 端 sanity check。決定不做：與 §3.10 嚴格 spirit 衝突（任何 git 知識都該來自 host 端權威）。
- **不寫 PowerShell helper script** — 想過寫 `.ps1` 把 6 命令收成 1 命令。決定不做：first commit 不過度工程化、累積 5+ commits 看 friction 真實程度再決定。
- **不補 5/11 / 5/13 journal** — 那兩天的工作（PRINCIPLES.md §6.8 cross-ref + 6z 後續討論）已整合進 §6.8 mapping 表，無另寫 journal 必要。本 5/14 journal 銜接 5/8 收工後即可。

---

## 學到的規則 / pattern（適用未來）

### 規則 1：QODA recommendation 排序會 prime user — safer 路徑該第一

我把 B/C 列在 recommendation、A 排最後、用「實用」「折衷」當推薦詞，等於暗示妥協是 default。User 選 A 後我認知到 — **這個 repo user 偏好 governance > velocity**。未來提 QODA：
- ✅ Safer 路徑第一個列、提名為「保守」而非「實用」
- ✅ 推薦詞避免「實用」「折衷」「velocity」（會偏向 user 妥協）
- ✅ 列出 friction 但說清「friction killer convention 可砍 ~X%」

### 規則 2：Commit msg handoff convention 是 friction killer 模板

Sandbox-host workflow split 場景，「user 要 paste 長中文 / 多行內容到 PowerShell」是普遍 friction。`-F <file>` + gitignore 過的中介資料夾這個模式可推廣到：
- ✅ 多檔 commit message
- ✅ 長指令參數（用 file-based input）
- ✅ 中文 / 特殊字元密集的指令 payload

### 規則 3：Workflow 轉換值得獨立 commit、不混 feature code

Commit `28c1730` 0 code 變更、純治理層。Git history 留下乾淨切片、未來查「default-deny 何時開始」直接看本 hash + 本 decision log。**Pattern**：
- ✅ Convention 採用 / governance 變更 → 獨立 commit
- ✅ Feature implementation → 另開 commit、不混治理改動
- ❌ 避免「順手把 governance 改動塞 feature commit」(混 commit 難 revert)

### 規則 4：Source of Truth 對齊 — 不要為了「stroke-order 自成體系」雙寫

§6.8 mapping 從 5/7 起就是 cross-ref bridge。新治理規則該寫 personal-playbook、stroke-order 補 mapping row。DRY 不只是 code、governance docs 更要。

---

## 相關檔案

- **工作日誌**：[`docs/journal/2026-05-14_session_log.md`](../journal/2026-05-14_session_log.md)
- **Commit `28c1730`** 3 files：
  - `docs/PRINCIPLES.md` §6.8 +22 行
  - `.gitignore` +5 行（`/docs/_commit_msg/`）
  - `docs/_commit_msg/2026-05-14_01.txt` 1843 bytes（commit msg 自身、不入版控）
- **Memory**：`/sessions/friendly-dreamy-noether/mnt/.auto-memory/feedback_strict_default_deny_git.md`（31 lines）+ `MEMORY.md` index +1 line
- **Cross-ref**：
  - Personal-playbook commits `60b8ff3` (31st revision §3.14) + `f6b5628` (32nd revision §3.10 升等) + `40b1130` (5/14 worklog)
  - 既有相關 memory：`feedback_cross_session_race` / `feedback_cowork_git_index_single_batched_add` / `feedback_cowork_fs_index_desync`
