# 2026-04-29：personal-playbook divergence — 兩台電腦並行演化的踩雷

> 範圍：今晚 push 自己的 morning audit 抽象化更新到 personal-playbook 時，發現 remote 已經被另一台電腦（同樣是 Claude session）大幅推進。stroke-order 端的更新無法直接同步過去——需要明天清醒時做反向比對 + 決定 SoT 走向。
>
> 起點：以為 personal-playbook 還是 yesterday `2b6c13e` 的狀態
> 終點：發現 remote 已演進到 `274d685`（多 7 個 commit + 重構為多檔），暫停 sync，留 follow-up

---

## 一、背景：今天的工作鏈與發現點

今天在 stroke-order 端做的：
1. Morning audit：補 4 個 PROJECT_PLAYBOOK 漏跑的章節（§六.A/B/C 三段檢查、§七 公開前審查、WORK_LOG_2026-04-27 backfill、cjk_common_808 §六 retrospective、§七 retrospective）
2. PROJECT_PLAYBOOK 抽象化：6+ 個子章節（§4.5 Backfill、§5.7 不該立即實作、§6.5 多源 triangulation、§7.5 attribution、§8.5 Morning audit ritual、§六 重寫成 abstract pattern + 「真實案例見各專案決策日誌」交叉引用）
3. 解 GH007 email privacy：rewrite 三個 commit 的 author email 為 noreply、移動 v0.14.0 tag 到 rewrite 後的新 hash、雙 remote push

push 完 stroke-order 後 → 試圖 sync 同樣的 PROJECT_PLAYBOOK 到 personal-playbook → push 被拒「remote contains work that you do not have locally」。

---

## 二、發現：remote 上有 7 個我們不知道的 commit

```
274d685 refactor+log: split into rule-handbook + history-and-cases + day-end work log
fcaf6d9 audit: pre-public last-mile + future website extensions + license compatibility
bb09bb9 docs: dogfood §四§五 with docs/ scaffold + audit decision log
46171a0 test: verify noreply email config
c8007a5 security: redact personal email from setup examples
f013818 chore: self-audit fixes — clean LICENSE pollution, unify SSH alias, add README + .gitignore + §8.5
512e5f3 docs(§3): add 3.5 setup SOP, 3.6 troubleshooting, 3.7 cross-machine setup
```

從 commit message + commit author + 同日時間戳判斷：**用戶今天另一台電腦也跑了一場 Claude session，主題與本場 stroke-order morning audit 高度重疊**——同樣在處理 noreply email、§8.5 子章節、playbook 抽象化、cross-machine setup 等議題。

---

## 三、對照表：兩場 Claude session 各做了什麼

| 維度 | stroke-order 端（本場） | personal-playbook 端（remote） |
|---|---|---|
| morning audit | 4 gaps closure + §六/§七 retrospective | email audit + pre-public last-mile |
| 抽象化 | §六 + 6 個子章節 | 抽象化 6+ 處、HISTORY 拆出去、§十二 升格 §十一 |
| §3.x 多帳號備份深化 | 沒做 | ✅ §3.5 setup SOP / §3.6 troubleshooting / §3.7 cross-machine |
| §7.2 commit metadata 稽核 | 沒做 | ✅ git config / history / 文件 email grep |
| **§8.5 編號** | Morning audit ritual | ⚠️ 為未來預留架構彈性（6 條前瞻心法） |
| §8.6（被擠到） | 無 | 移除功能：保留檔案、只拔載入 |
| 附錄 F-J | 沒做 | ✅ 第三方品牌、COPPA/GDPR-K/PIPL、Privacy Policy、ToS、License 相容性 cheat sheet |
| PROJECT_PLAYBOOK 拆檔 | 沒做（單檔 784 行）| ✅ 拆出 HISTORY.md（§A 修訂 + §B 共用案例 + §C 已知 gap） |
| dogfood scaffolding | 沒做 | ✅ docs/_TEMPLATE.md + WORK_LOG_2026-04-29 + 3 份決策日誌 |
| GH007 email privacy 處理 | 事中救火（rebase rewrite + tag move） | 系統性 email_audit decision log + commit metadata 稽核 |
| Phase A 4-gaps audit | ✅ 做了 | 沒做（這是 stroke-order 專屬議題） |

**關鍵衝突點**：§8.5 編號碰撞——兩場各自加了不同內容到同一個編號。

---

## 四、決定：暫停 sync，留 follow-up（不強推）

**做出的選擇**：
- 把本地 90d7875 commit 內容用 `git format-patch origin/main..HEAD --stdout > backup-90d7875.patch` 備份
- `git reset --hard origin/main` 把本地 personal-playbook 對齊 remote 274d685
- 刪掉 stroke-order/docs/_personal-playbook-README.md 草稿（remote 已有正式 README）
- 寫本份 follow-up

**為什麼不強推 90d7875**：
1. Remote 是「進化版」（拆檔重構 + 附錄 F-J + dogfood scaffolding），硬推會 regress
2. PROJECT_PLAYBOOK 結構已不同（remote 多檔、本場單檔），三方合併衝突會極大
3. §8.5 編號衝突需要設計性決策，不是文字 merge 能解
4. 工作 17 小時後做大規模內容比對風險高

---

## 五、Follow-up TODO（明天清醒時）

### 5.1 PROJECT_PLAYBOOK 反向同步評估

**問題**：stroke-order/docs/PROJECT_PLAYBOOK.md 是否還是 single source of truth？還是要改用 personal-playbook 的 274d685 版作為 SoT？

**判斷依據**：
- Remote 274d685 已做了 abstract 化（6+ 處）+ HISTORY 拆檔——更乾淨
- 本場 stroke-order 抽象化也做了同樣方向，但未拆檔
- 兩邊的內容**主題重疊但具體章節結構不同**

**建議步驟**：
1. 開啟 personal-playbook 的 PROJECT_PLAYBOOK.md（C:\Users\USER\Documents\Cowork\personal-playbook\PROJECT_PLAYBOOK.md）
2. 對照 stroke-order/docs/PROJECT_PLAYBOOK.md，逐章看哪一邊更好
3. 若 remote 更好 → 反向 copy 到 stroke-order，**翻轉 SoT 方向**：以 personal-playbook 為主、stroke-order 同步過來

### 5.2 補上本場特有的子章節

stroke-order 本場加的這些子章節，**確認 remote 是否已涵蓋**：

| 我們的子章節 | 預期在 remote 的位置 | 動作 |
|---|---|---|
| §4.5 Backfill 規則 | 不確定 | 若沒 → 補進 |
| §5.7 何時不該立即實作 | 不確定 | 若沒 → 補進 |
| §6.5 多源 triangulation | 不確定 | 若沒 → 補進 |
| §7.5 第三方資料源 attribution 完整性 | 不確定 | 若沒 → 補進 |
| §8.5 Morning audit ritual | ⚠️ **編號衝突** | 重新編號（如 §8.7 或合併進 §3.x） |
| §六 重寫成 abstract pattern | 大概 remote 也有同向 | 比對細節 |

### 5.3 §8.5 編號衝突解法

**選項**：
- A. 把本場的「Morning audit ritual」改成 §8.7（remote 已用 8.5、8.6）
- B. 把它合併進 §3.x cross-machine setup 章節（因為 morning audit 通常在跨電腦 sync 後執行）
- C. 把它放進 HISTORY.md 的「已知 gap」section 而非 PROJECT_PLAYBOOK

### 5.4 重要檔案位置備忘

| 檔案 | 路徑 | 用途 |
|---|---|---|
| 本場 commit 備份 patch | `C:\Users\USER\Documents\Cowork\backup-90d7875.patch` | 39 KB，含本場做的 README + PROJECT_PLAYBOOK 改動 |
| stroke-order PROJECT_PLAYBOOK | `C:\Users\USER\Documents\Cowork\stroke_order\docs\PROJECT_PLAYBOOK.md` | 本場抽象化後版本（單檔 12 章）|
| personal-playbook PROJECT_PLAYBOOK | `C:\Users\USER\Documents\Cowork\personal-playbook\PROJECT_PLAYBOOK.md` | remote 274d685 版（拆檔 + 附錄 F-J）|
| personal-playbook HISTORY | `C:\Users\USER\Documents\Cowork\personal-playbook\HISTORY.md` | 從 PROJECT_PLAYBOOK 拆出的修訂歷史 + 共用案例索引 |

---

## 六、教訓 / 寫入長期記憶

### 6.1 跨電腦 / 跨 session 工作的 race condition

當 personal-playbook 同時被「stroke-order 內的 Claude session」和「personal-playbook repo 的 Claude session」更新，沒先做 `git pull` 同步就會踩雷。本場僥倖：reset 前已 `format-patch` 備份，沒丟失工作。

**新規則建議寫進 PROJECT_PLAYBOOK §3.x（跨電腦同步）**：

> **每次工作 session 開始前**，對所有要操作的 repo 跑 `git fetch && git status`，確認本地是否落後 remote。**特別是當這個 repo 可能被另一台電腦或另一場 AI session 操作時**。

### 6.2 `git format-patch` 是修正不確定性的安全網

當你想做有風險的操作（rebase、reset、force push）但又不確定該不該做，先用 `git format-patch <base>..HEAD --stdout > backup.patch` 把 commit 內容存成獨立 patch。即使後來 `git reset --hard` 也不會丟失——明天可以 `git apply backup.patch` 還原。

### 6.3 「兩個 AI 並行做相似工作」是新型 conflict pattern

本場揭露：當你在多個工作環境讓 AI 做同一個 repo 的 audit 時，AI 的章節編號（§8.5、§6.5）很容易碰撞。**未來建議**：每場 AI session 開始前先 `git pull` 並讀完最新 PROJECT_PLAYBOOK，再決定要加哪個編號。

---

## 七、結論

stroke-order 端的工作（06ae882 + 三個 rewrite commit）**已成功 push 到 origin/backup**——這部分完整、可信。

personal-playbook 端的同步工作（90d7875）**今天不推**，等明天清醒比對後再決定要不要：
- 反向 sync remote → stroke-order
- 或補上本場特有的子章節到 personal-playbook
- 或兩者各自並存（兩個 SoT）

**stroke-order 的工作沒被影響**——HEAD 還是 06ae882，雙 remote 一致，working tree clean。
