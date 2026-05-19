# 決策日誌：2026-05-19 morning audit + d2ea545 + 13bbcc7 cross-ref

**日期**：2026-05-19
**版號變化**：0.14.133 → 0.14.133（純治理、不改 code、不 bump）
**對話 / 工作期間**：跨 5 天再開工 → SOP-0 fetch-first catch 7 commits → 評估 + 落地 + 收工

---

## 整體脈絡

> 5/14 收工後相隔 5 天再開工。依新 SOP-0「fetch-first opening」紀律抓 personal-playbook origin/main、catch 7 個新 commit。直接影響本 repo workflow 的 2 條（`d2ea545` / `13bbcc7`）做 cross-ref + 部署 1 條 contingency memory；其餘 5 條（pptx / U5M60 / U6P40 / 5/19 worklog）為其他專案、本 repo 0 牽涉。
>
> 本 day 0 code 變更、純治理 day 3。決策核心是「對 d2ea545 9 維度框架的 cross-ref 策略」+「對 13bbcc7 5 候選原則的應對策略」+「day 3 收工方式」。

---

## 決策 1：是否新加 `feedback_sandbox_unavailable_fallback` memory？

**觸發**：d2ea545 引入「worst case sandbox 完全失能跨 round」+ §3.13 2nd strengthen「host-side fallback SOP」。本 repo workflow 0 命中、但這是 binary risk（要嘛沒事、要嘛全停）、應對時間短。是否預部署 contingency？

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 加 memory `feedback_sandbox_unavailable_fallback` 預部署 SOP | 真發生時零延遲 switchover、marginal cost 低（~30 min） | 0 命中 risk 寫 memory 違反「不寫 ephemeral」原則 |
| B | 不加 memory、記在 §6.8 即可、真踩到才寫 | 避免 memory noise、保持精簡 | 真發生時臨時想 SOP 來不及 |
| C | 寫進 PRINCIPLES.md §6.x 而非 memory | 入版控、未來查得到 | 違反「不另開 §6.x rule」決策 3（5/14 day 1）、SoT drift |

**考慮的因素**：
- Risk profile（低頻 / 高 impact / 反應時間短）
- Marginal cost vs option value
- Memory noise threshold
- 與既有「不另開 §6.x rule」決策的一致性

**選擇**：☑ **A 加 memory**

**理由**：
> Sandbox 失能是「binary risk + 高 impact + 反應時間短」三條件齊備、預部署 marginal cost ~30 min 但若發生省 1+ hour（臨時 debug + 想 SOP + 切 PowerShell 流程）。Option value > marginal cost、值得寫。
>
> 不違反「不寫 ephemeral」— ephemeral 指的是 conversation-local state、不是 workflow contingency。Worst case fallback SOP 是 workflow-level knowledge、跨 session 都適用。

**後續驗證 / 結果**：
- ✅ Memory 寫成 `feedback_sandbox_unavailable_fallback.md`、含 5 招降層 + 判斷時機 + cross-ref
- ✅ MEMORY.md index 從 33 → 34 條
- ⏳ 真發生 sandbox 失能時驗證 SOP 是否完整（目前 0 命中）

---

## 決策 2：13bbcc7 5 條「候選原則」如何應對？

**觸發**：13bbcc7 user 萃取 5 條共通性原則候選（plan-first ADR / plan v1→v2 / hardcode 掃描 / user-side gate / ssh fallback）、標「待累積 supporting case 升等」。其中 #4「動工延後 user-side gate」本 repo 已實踐 6+ 次。是否在本 repo 主動升等為 §3.x / §5.x rule？

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 不超前升等、只在 §6.8 mapping 記 awareness | SoT 對齊、source 在 personal-playbook、本 repo 跟著 governance 走 | 候選 #4 已實踐多次、不文件化會看不到 pattern |
| B | 升等 #4 為本 repo §6.15 新 rule | 自成體系、查得到 | 違反 5/14 day 1 決策 3「不另開 §6.x rule」、SoT drift |
| C | 待 user 在 personal-playbook 升等後、再 cross-ref 進 §6.8 | 對齊上游時序 | 等很久（user 標「待累積」、不知何時升等）|

**選擇**：☑ **A 不超前升等**

**理由**：
> Governance 層級分工：source of truth 在 personal-playbook、stroke-order §6.8 是 cross-ref bridge。本 repo 做「supporting case 提供方」、不做「governance 決定方」。
>
> 候選 #4 已實踐多次是 supporting case 來源、但提早升等等於越權做 governance 決定。等 user 在 personal-playbook 升等後、§6.8 自然 cross-ref 即可。
>
> 與 5/14 day 1 決策 3「不另開 §6.x rule、用 §6.8 mapping」一致。

**後續驗證 / 結果**：
- ✅ §6.8 9-row 表加入「候選 #1/#2/#4 啟發 + 已實踐」row、不另開 §6.x
- ⏳ 若 user 在 personal-playbook 升等 #4 為正式 §3.x、再回 §6.8 mapping 加 row

---

## 決策 3：5/19 day 3 收工方式（單 commit vs 雙 commit）

**觸發**：5/14 day 1 兩 commit（治理 + journal/decision）vs 5/14 day 2 單 commit（只 §6.8 補充、無另寫 journal）。今日 5/19 工作量介於兩者中間（治理 + memory contingency 部署）、user 明說「請寫工作日誌、決策紀錄、共通性原則」。

**選項**：

| 編號 | 方案 | 優點 | 缺點 |
|---|---|---|---|
| A | 雙 commit（治理 01 + journal/decision 02）= 5/14 day 1 節奏 | Git history 乾淨切片、治理變更獨立 | 多 1 個 commit handoff cycle（PowerShell 6 命令 × 2）|
| B | 單 commit 全打包 = 5/14 day 2 節奏 | 少 1 個 handoff cycle | Journal + decision 跟治理變更混 commit、違反 `feedback_governance_commit_isolation` |
| C | 不寫 journal/decision、只治理 commit + memory | 最少 friction | 跟 user「請寫」要求衝突 |

**選擇**：☑ **A 雙 commit**

**理由**：
> 與 memory `feedback_governance_commit_isolation` 對齊 — 治理 / convention 變更（§6.8 補充）獨立 commit、journal + decision（documentation）另一 commit。Git history 留乾淨切片、未來查「§6.8 何時補 2026-05-19 補充」直接看 commit hash。
>
> 多 1 個 handoff cycle 的 friction 已被 `-F` convention 抵銷 ~80%、user 端 5 秒 paste 完。Cost 可接受。
>
> 5/14 day 2 沒寫 journal 是因為當時工作量較小、且 user 沒明確要求。今日 user 明說「請寫」、應 honor。

**後續驗證 / 結果**：
- ✅ `2026-05-19_01.txt` 治理 commit（PRINCIPLES.md §6.8）pending push
- ✅ `2026-05-19_02.txt` journal/decision commit（本 commit）pending push
- ✅ Memory contingency 部署不入版控（auto-memory）

---

## 沒做的決策（明確擱置）

> 這次討論到但**刻意不做**：

- **不寫 `feedback_windows_python_runtime_check` memory** — d2ea545 維度 9「Microsoft Store python stub」對本 repo 0 命中（host PS 不跑 Python）、低 value 不寫；若未來 6z deployment 流程引入 host PS Python 才寫。
- **不升等 13bbcc7 任何候選為本 repo §3.x / §5.x rule** — 等 user 在 personal-playbook 升等。
- **不補做 5/14 day 2 缺寫的 journal/decision** — 5/14 day 2 工作量小、§6.8 day 2 補充已涵蓋、不為了「完整 journal 系列」回補（避免歷史改寫）。
- **不立即進 6z-6 切割 mode** — 與「治理 day 不混 feature」一致；6z-6 留下次 session 首跑 feature commit。

---

## 學到的規則 / pattern（適用未來）

### 規則 1：Workflow 設計避坑 > 規則記憶

d2ea545 升 9 維度但本 repo workflow 0 命中。**不是因為我們記得多、是因為當初路徑選對**（mounted folder / `path.write_text` / host PS 純 git 命令 / sandbox-host 不交叉編輯）。新 feature 設計時、優先選**不需要記規則**的路徑。

### 規則 2：Contingency 預部署的判斷標準

「低頻 + 高 impact + 反應時間短」三條件齊備才預部署 SOP。Sandbox 失能符合三條件 → 寫 memory。Microsoft Store python stub 不符合（host PS 不跑 Python = 0 頻率）→ 不寫。**標準明確、避免 memory noise**。

### 規則 3：候選原則不超前升等

Source of truth 分層：personal-playbook 是 governance backbone、stroke-order §6.8 是 cross-ref bridge。Stroke-order 做「supporting case 提供方」、不做「governance 決定方」。等上游升等後、§6.8 自然 cross-ref。

### 規則 4：Audit day 的 ROI

5+ 天累積的 governance 更新、值得 1 個 audit day 消化。若不 audit、會繼續用舊紀律集 + contingency 缺位 + 未來踩坑時 debug 跑錯方向。**比硬推 feature 更高 ROI 的 day**。

### 規則 5：Decision log 三分類值得未來考慮（候選）

13bbcc7 候選 #1「plan-first ADR + decision log 三分類 (inspection / plan / close)」目前本 repo decision log 是單一分類。未來若 6z-6 等大 phase 需要、可考慮三分類（inspection log = audit / plan log = 動工前 design / close log = 收尾 retro）。**等 user 升等後跟進、不超前**。

---

## 相關檔案

- **工作日誌**：[`docs/journal/2026-05-19_session_log.md`](../journal/2026-05-19_session_log.md)
- **Commit `2026-05-19_01`**（治理、pending push）：`docs/PRINCIPLES.md` §6.8 +24 行
- **Commit `2026-05-19_02`**（本 commit、pending push）：本檔 + journal
- **Auto-memory（不入版控）**：
  - 新加 `feedback_sandbox_unavailable_fallback.md`
  - `MEMORY.md` index +1 line（33 → 34 條）
- **Cross-ref**：
  - Personal-playbook `d2ea545` (34th revision, 5/14 day 3 R59 biped) + `13bbcc7` (5/19 evening 共通性原則候選 5 條)
  - 本 repo `28c1730` (5/14 day 1 §3.10 落地) + `4698fc8` (5/14 day 1 journal+decision) + `87e92fe` (5/14 day 2 §6.8 補充)
  - Memory `feedback_strict_default_deny_git` SOP-0 第 2 supporting case 落地 + `feedback_governance_commit_isolation`（決策 3 對應）+ `feedback_sandbox_unavailable_fallback`（決策 1 產物）
