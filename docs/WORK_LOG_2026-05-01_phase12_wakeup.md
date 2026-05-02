# Work Log — 2026-05-01 — Phase 12 wakeup overlay
> （retrofit 2026-05-02：原檔名 `WORK_LOG_2026-05-02.md`、內部日期 5-02。git commit 5-01 16:27 (+0800)，align commit date 後重命名 `WORK_LOG_2026-05-01_phase12_wakeup.md`。）

> Phase 12 第一發：cold-start wakeup overlay。**昨天的 §8.7 morning audit 真的抓到價值** — Phase 11 收尾的 4 件 gap（雙 remote sync / v0.14.1 tag / §8.8 同步 / .gitattributes）今早 30 分鐘清完，乾淨進主工作。

**版本**：0.14.1 → 0.14.2
**Commits**：1 個（`2a0f161`）+ 昨晚 audit 收尾（`6011449` + 昨天 §8.8 同步）
**修改檔**：`web/static/index.html`（+116 行 inline CSS/HTML/JS）、`pyproject.toml`（+1/-1）

---

## 一、Morning audit 結果（§8.7 真實案例）

開工後跑昨天既定的 morning audit checklist。原列 4 件 gap（昨晚已預備 PowerShell 步驟給 user 跑），今早全部清完：

| Audit 項目 | 狀態 | 證據 |
|---|---|---|
| 雙 remote sync | ✅ origin/backup 一致 | `git status` 乾淨、`git log origin/main..HEAD` 空 |
| v0.14.1 git tag | ✅ pushed | sandbox 建 tag → user push 雙 remote |
| personal-playbook §8.8 反向同步 | ✅ commit + push 雙 remote | snippet + HISTORY entry 走 §3.9 fetch-first SOP |
| `.gitattributes` 解 CRLF noise | ✅ commit `6011449` | git status 雜訊消失 |
| 全套 pytest 回歸 | ✅ 1140 passed / 0 failed | sandbox 4 batch 跑完 |

**§8.7 morning audit ritual 自證價值**：5 件 gap 在主工作前清完，Phase 12 起跑時 codebase 是整齊狀態，沒有「殘留 todo 在背景累積壓力」的感覺。

---

## 二、與 user 的架構釐清對話

收尾 audit 後，user 主動問：「網站主體架設在哪？字型放 GitHub 哪裡？使用者點選後實際下載什麼？」

我把架構分成三段答（角色分層 / 字型不到瀏覽器 / 流量 trace）。**最關鍵的釐清是「字型 binary 從來不離開 Render server」**——使用者拿到的只有後端 render 完的 SVG path。

接著 user 追問：「所以每次重新連線等的不是程式下載，是 server 重啟？」這就是 12a-1 的觸發點——把 Render free tier 的 cold start 從「無聲缺陷」變成「告知使用者的 UX 設計」。

---

## 三、12a-1 — Cold-start wakeup overlay（commit `2a0f161`）

### 規格

| 維度 | 設計 |
|---|---|
| 觸發 | 第一個 in-flight `fetch()` 超過 3 秒未回應 |
| 解除 | 最後一個 in-flight 結束 → hide + `sessionStorage.wakeupSeen='1'` |
| 同 session 二次喚醒 | 不觸發（已 awake，後續 fetch 直接 passthrough） |
| 訊息 | 3 階段（3s 標準 / 10s 補解釋 / 30s 升級警告） |
| 範圍 | `index.html`（其他頁面不需要——server 醒了大家受惠） |
| 風格 | inline 全部，維持既有 SPA 風格 |

### 改動結構

3 段 inline 注入到 `index.html`：

1. **CSS（L88-130）**：fixed overlay + indeterminate progress bar (`@keyframes wakeupBar`) + 3 階段樣式（`.stage-2 .wakeup-stage-extra` / `.stage-3 .wakeup-stage-late`）+ `backdrop-filter: blur(2px)` 緩解卡住感
2. **HTML（L135-148）**：`role="status" aria-live="polite"` 螢幕閱讀器無障礙
3. **JS controller（L1906-1962）**：包 `window.fetch` wrapper；`inFlight` 計數；3 個 setTimeout 控制階段切換

### 設計決策（細節進 decision log）

詳見 `docs/decisions/2026-05-01_cold_start_ux.md`。摘要：

- **3 秒延遲才顯示**（不立即顯示）：避免 normal request 也閃 overlay
- **包 fetch 而不改呼叫端**：~50 處 fetch 自動受惠，無需動 30+ 個 callsite
- **sessionStorage 不 localStorage**：「醒過」的狀態跟分頁綁，分頁關掉再開假設 server 又睡了
- **3 階段訊息**：避免使用者卡在「不知道要等多久」
- **只做 index.html**：server 一醒，handwriting / sutra-editor / gallery 進入時都不會慢

### 驗收 checklist（user 在 production 跑，等 Render redeploy 完）

- [ ] Console 強制觸發 3 階段都正確顯示
- [ ] 同分頁正常 fetch（轉字 / 印章 / 抄經）不被阻擋
- [ ] 真實 cold start（閒置 20+ 分鐘後重訪）看到完整 30 秒流程

---

## 四、版本 / Tag

- pyproject.toml: 0.14.1 → **0.14.2**
- Render deploy: push 後自動 redeploy（~3 分鐘）
- Production 驗收完後補 `v0.14.2` 注解 git tag + push

---

## 五、Backlog

無新增。Phase 12a 範圍封閉。

---

## 六、給未來自己的話

1. **Cold start UX 是 PaaS 免費 tier 的固有設計問題**，不是 stroke-order 的 bug。但「使用者體驗」維度上它就是缺陷。從 §3.8（PaaS fs 模型）延伸出 §3.10 候選原則：「**免費 tier 的固有限制，要在 UX 層告知使用者，不是隱藏**」——值得思考是否寫進 personal-playbook（決策日誌會展開討論）。

2. **架構問題的回答**：user 主動問架構問題時，我用「分角色 → 流量 trace → 三種等待」三段論回答，後續直接驅動了 12a-1 的工作。**「使用者問架構不是要架構圖，而是要決策依據」**——下次 user 問類似問題，記得用「他下一步可能想做什麼」當作回答的指南針。

3. **Morning audit 收尾再進主工作**：今早 5 件 gap → 30 分鐘清完，比直接跳進 Phase 12 不亂（沒有 commit message 卡住要修 audit / personal-playbook divergence 等問題在背景）。§8.7 ritual 第三次自證價值（前兩次：04-29 morning audit 抓 4 件 gap、05-01 morning audit 抓 4 件 gap）。
