# 2026-05-01 — Cold-start wakeup overlay UX 設計決策

<!-- retrofit 2026-05-02：原檔名 2026-05-02_cold_start_ux.md，內部日期 5-02。git commit 5-01 16:27 (+0800)，align commit date 後重命名。 -->

> Render free tier 閒置 15 分鐘後 server 會 sleep，第一個請求要等 ~30 秒喚醒。**選擇：把這個延遲從「無聲缺陷」變成「告知式等待」**——加 wakeup overlay。本決策記錄五個關鍵設計選擇與替代方案。

## 背景

Phase 12 起點。User 在問完網站架構後追問：「所以我每次清空快取後重連，等的不是程式下載而是 server 重啟？」這個問題暴露了 cold start 對使用者的隱形成本——沒有任何反饋、不知道要等多久、不確定是不是壞了。

### 量化

| 三種等待情境 | 時間 | 主因 |
|---|---|---|
| Normal request（server 醒著） | < 1 秒 | HTML 下載 + 網路 latency |
| **Cold start**（閒置 15 分鐘+） | **~30 秒** | **Render 容器 wake up + Python 啟動 + 字型載入** |
| Redeploy（剛 push） | ~3 分鐘 | git pull + pip install + fetch 字型 |

90% 的「等」是 cold start。

### 決策範圍

只解 cold start 的 UX 層告知；不解決底層延遲（解決底層需要付費 plan / cron job 保活，是後續決策）。

## 替代方案

### 治本方案（不採用）

| 方案 | 解什麼 | 為何不採用 |
|---|---|---|
| 升 Render Starter $7/月 | 永不睡 | $84/年成本，個人 demo 不值得；保留升級彈性即可 |
| 外部 cron job 14 分鐘 ping `/api/health` | 心跳保活 | 用滿 free tier 750 hours/月（24×31=744 hours），非常邊緣，可能某月斷線 |
| 換 fly.io / railway | 喚醒從 30s 降到 5s | migrate 工大；fly.io 也是 sleep-on-idle |

### UX 緩解方案（本次採用）

加 wakeup overlay 告訴使用者「正在喚醒」。**effort/value 最划算**——半天工程，使用者體驗大幅改善（從「卡住了？」變成「OK 我知道在等什麼」）。

## 五個設計決策

### 決策 1：「3 秒才顯示」而不是立即顯示

**選項**：

| 選項 | 描述 |
|---|---|
| A | 任何 fetch 都立即顯示 overlay |
| B | fetch 超過 3 秒未回才顯示 ✅ |
| C | 永不顯示，只在 30s timeout 後顯示錯誤 |

**選 B**

**為什麼**：
- A：normal request < 1s，立即顯示會「閃一下」打斷正常流程，比沒有 overlay 還煩
- B：3s 是個 sweet spot——normal request 不會觸發、cold start 會剛好觸發
- C：「30s 都沒回應 = 錯誤」誤判機率高，且使用者前 30s 完全沒回饋

**3 秒怎麼來的**：normal request 中位數 200-500ms，p99 通常 < 2s。設 3s 給 normal request safety margin，同時 cold start 才剛要進入「使用者可能放棄」的時間區。

### 決策 2：包 `window.fetch` wrapper，不改 ~50 處呼叫端

**選項**：

| 選項 | 描述 |
|---|---|
| A | 在每個 `fetch()` callsite 加 timer 邏輯 |
| B | 包 `window.fetch` wrapper，全站任意 fetch 自動受惠 ✅ |
| C | 只包 wrapper 在「進入頁面的第一個 fetch」 |

**選 B**

**為什麼**：
- A：~50 處 callsite，重複代碼 + 維護成本爆炸
- B：寫一次解全部
- C：聽起來合理但實作判斷「哪個是第一個」很 fragile（race condition / 多 fetch 並發）

**陷阱避免**：
- 透傳所有 args（用 `...args`）
- return original Promise，不要包額外層（避免破壞 caller 的 `.then` chain）
- 用 `.finally()` 而不是 `.then().catch()`，避免吞掉錯誤

### 決策 3：sessionStorage 而不是 localStorage

**選項**：

| 選項 | 描述 |
|---|---|
| A | localStorage：跨分頁、跨 session 持久 |
| B | sessionStorage：分頁綁定 ✅ |
| C | 不持久，每次 reload 都重新計時 |

**選 B**

**為什麼**：
- A：localStorage 持久太久——使用者隔天再開，server 又睡了，但 localStorage 說「已喚醒」，使用者第一個 fetch 又卡 30s 卻沒 overlay
- B：sessionStorage 跟分頁綁，關掉分頁再開 = 假設 server 可能又睡了，重新計時
- C：每次 reload 都重新計時 = 使用者重整一次就跳一次 overlay，太煩

**「session」的定義**：分頁活著 = server 認為醒著。這個 heuristic 對 Render free tier 不完全對（15 分鐘無流量就會睡），但「分頁活著一段時間」也通常意味著「使用者有在 fetch」進而保活，所以 sessionStorage 已經夠用。

### 決策 4：3 階段訊息切換而不是單一訊息

**選項**：

| 選項 | 描述 |
|---|---|
| A | 單一訊息「正在喚醒伺服器」 |
| B | 3 階段：3s / 10s / 30s 漸進式補上下文 ✅ |
| C | 進度條顯示具體「還剩 XX 秒」 |

**選 B**

**為什麼**：
- A：使用者過了 15 秒會想「為什麼還沒好？」沒有上下文補充
- B：3s 「正在喚醒，約需 30 秒」設定預期 → 10s 補「Render 免費主機閒置會休眠」解釋為什麼 → 30s 「比預期久，可能正在重新部署」讓使用者知道是極端情況
- C：cold start 時間不可預測（看 Render 當下負載），假進度條會被使用者看穿

**心理學依據**：使用者「等待中的不確定性」是焦慮主因。漸進式上下文 = 「我知道我為什麼在等 + 我知道大概還要多久」。

### 決策 5：只在 index.html 做，不全站

**選項**：

| 選項 | 描述 |
|---|---|
| A | 全站每個 .html (index/handwriting/sutra-editor/gallery) 都加 |
| B | 只在 index.html 做 ✅ |
| C | 抽出 `wakeup.js` shared module 引用 |

**選 B**

**為什麼**：
- 使用者通常從 `index.html` 進站（root URL），這是 cold start 觸發的主場景
- 從 index 進去之後 server 已醒，切到其他頁面 (`/handwriting` `/gallery`) 都是 warm fetch
- A：4 處重複代碼，維護成本變 4 倍，但 90%+ 使用者不會走另外 3 個入口
- C：要破壞 index.html 的 inline SPA 風格（其他頁面已用 `<script src>`，但 index.html 全 inline）

**極端情境（不解）**：使用者直接 bookmark `/handwriting`，server 醒著時可以；server 睡著時會卡 30 秒沒 overlay。**接受這個 trade-off**，因為 root URL bookmark 比 sub-page 常見一個量級以上。

## 教訓 / 共通原則

### 教訓 1：「免費 tier 限制」是設計問題不是隱藏問題

Render free tier cold start 是公開的限制。stroke-order 的 README 沒寫 / UI 沒提示，使用者看到「網站打開要等 30 秒」會懷疑是 stroke-order 壞了。**告知 = 信任**。

→ 這條值得寫進 personal-playbook。**候選新原則 §3.10**：「**PaaS 免費 tier 的固有限制，要在 UX 層主動告知使用者，不是隱藏。隱藏會讓使用者把限制誤認為缺陷。**」

待跟 §3.8（PaaS 部署 fs 模型）+ §3.9（跨 session SOP）形成 §3 chapter 的一個 sub-cluster「PaaS 部署的隱形成本」。下次同步 personal-playbook 時加。

### 教訓 2：「使用者問架構」常常是「使用者在診斷他遇到的問題」

User 一開始問「網站架構在哪、字型放哪、使用者下載什麼」，看起來是學習問題。但接下來追問「所以我等的是 server 重啟？」就直接連到 12a-1 的工作。

**回答架構問題時，要想：「他為什麼問這個？接下來可能想做什麼？」** — 用這個指南針回答比純粹的「正確架構解釋」更有用。

→ 這條也是值得進 personal-playbook 的候選原則，但不夠抽象，先放這份決策日誌就好。

### 教訓 3：3-tier 設計（CSS / HTML / JS 分離）讓 review 容易

本次改動 3 段 inject：CSS overlay / HTML 元素 / JS controller。**每段獨立可測試**：
- CSS：直接 console 加 class 看樣式
- HTML：DOM 元素可 inspect
- JS：fetch wrapper 可被 console 觸發

如果改動把 CSS-in-JS 全塞 controller 裡，本次的「先測樣式再測邏輯」分階段驗收就做不出來。**Inline 不等於糾纏**。

## 後續

**短期（本次 ship 後）**：
- [ ] User 在 production 驗收 3 個 case（Console 強制 / fetch wrapper 不阻擋 / 真實 cold start）
- [ ] 補 v0.14.2 git tag + push

**中期（後續 Phase）**：
- [ ] Phase 12b 候選：抽 wakeup module 加到 handwriting / sutra-editor / gallery（但邊際效益低，**先不動**直到看到實際投訴）
- [ ] Phase 12c 候選：加「server 預熱」hint—使用者點 `index.html` 的時候用 `<link rel="preconnect">` 預熱第一個 API 連線（HTTP layer 緩解 ~100ms，cold start 沒解）

**長期（如果有外部使用者）**：
- 升 Render Starter ($7/月)：永不睡，無需 wakeup overlay
- 或：接 UptimeRobot 免費 monitor 加 14 分鐘 ping / 計算 free tier 750 hours 是否夠用

## 相關 commit

- `2a0f161` feat(web): 加 cold-start wakeup overlay（首次 fetch >3s 才顯示）

## 相關 PROJECT_PLAYBOOK 章節

- §3.8 PaaS 部署 fs 模型（cold start 的姊妹原則 — 同一類「PaaS 隱形成本」）
- §8.8 先 inspect 實際輸出，再下 root cause 結論（本決策的 root cause 是直接看 Render dashboard 跟 server log 確認 cold start 行為，而不是猜）
