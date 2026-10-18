# ADR — 計數器跨重啟累計（Gist）＋暫時性磁碟誠實標示

- 日期：2026-10-18
- 版本：0.14.295 → **0.14.296**
- 狀態：已實作（待使用者設定 Gist 金鑰後線上生效）
- 相關：`docs/BLUEPRINT.md` v1.2（Phase 0 超時轉向→個人化線，gate＝
  「手寫字型下載數 >0（儀器 D2）」）、ADR `2026-08-27_phase0_verification_kit.md`
  （D2 原設計）、PRINCIPLES §80／§99／**§100**（本輪新立）

## 脈絡

Blueprint v1.2 轉攻個人化線，其 gate 直接讀 D2 儀器。10-18 第一次讀
正式環境 `GET /api/metrics`：

```json
{"since":"2026-10-18T08:24:41+00:00","mode":{},"missing_char":{},"missing_char_overflow":0}
```

`since`＝本次請求把主機叫醒的時刻，計數全空。查 Render 官方文件
（https://render.com/docs/free ，10-18）：免費 web service 閒置 **15 分鐘**
休眠；本機檔案在「redeploys, restarts, or spins down」時全數遺失；免費層
**不能**掛永久硬碟；免費 Postgres 30 天到期；免費 Key Value 純記憶體。

D2 原設計假設重置觸發＝重新部署（偶發），補償是 log 留歷史＋gate 用相對
訊號。實際重置頻率高兩個數量級，補償失效。同一事實也意味著**分享庫
SQLite（帳號／上傳／收藏）與上傳檔同樣會消失**——線上查詢 `total: 0`。

## 決策

### 1. 方案 C：只救計數器，分享庫設觸發條件後根治（QODA，使用者 sign-off「C」）

| 方案 | 內容 | 不選理由 |
|---|---|---|
| A 付費＋永久硬碟 | US$7/月＋US$0.25/GB/月，改 render.yaml | 零使用者時月費過早；**列為分享庫根治方案**，觸發條件見下 |
| B Turso 等外部 DB | 分享庫遷移、上傳改存 blob | 兩三輪工＋新相依＋新帳號，過早建設 |
| **C（採用）** | 計數器同步私密 Gist＋誠實標示 | 半輪工、免費、只多一個金鑰 |

理由：眼前卡路線圖的只有計數器（個人化線的手寫字型在使用者本機產生，
不需要分享庫）。Blueprint 原則 1「證據先於建設」＋原則 5「永久成本過需求
門檻」。**分享庫根治觸發條件**（寫進 Blueprint §8 G3）：D4 教材範本庫
動工，或分享庫出現第一筆真實（非自測）上傳 → 走方案 A。

### 2. Gist 同步的兩條不變式（鎖成測試，`tests/test_metrics_gist.py`）

- **開機讀回是合併不是覆蓋**：遠端總數加進記憶體計數；讀回完成前進來的
  請求不會被吃掉；`since` 取較早者；合併仍守 500 缺字 key 上限（擠不進的
  計入 overflow）。Gist 模式下**不讀本機檔**——Gist 是唯一事實源，避免
  本機開發時同一份次數算兩次。冪等：重複讀回不重複加。
- **未讀回成功不推送**：推送前先重試讀回，仍失敗就放棄本輪——寧可少存
  一輪，也不拿較小計數覆蓋遠端歷史。

推送時機：flush 尾端節流（最多每 600 秒一次）丟背景 daemon 執行緒，網路
不在請求路徑上；另掛 `router.on_shutdown` 同步推一次（休眠前 uvicorn 會
跑 shutdown）。開機讀回掛 `router.on_startup` 背景執行緒。TestClient 不進
context manager 不觸發——測試零網路。

**零回歸**：`STROKE_ORDER_METRICS_GIST_ID`＋`_TOKEN` 任一缺＝與 0.14.295
行為相同、零網路呼叫（測試以「呼叫即 AssertionError」的替身鎖住）。

隱私：Gist 內容就是原本的四鍵快照。Gist 修訂歷史會形成 ≥10 分鐘粒度的
**總數**時間序列——這是總量層級、無任何請求脈絡，與 D2「不記人」的約束
相容；在此明記以免日後誤讀為違反「無時間序列」（原約束指的是逐請求紀錄）。

### 3. 暫時性磁碟由環境宣告，兩處誠實標示

- `STROKE_ORDER_EPHEMERAL_STORAGE=true`（render.yaml 固定值）。
- `/api/metrics` 多一個 `persistence` 欄位：`gist`／`gist-pending`／
  `ephemeral`／`local`。隱私守門測試的鍵集合同步更新（新鍵是儲存位置，
  非請求脈絡；禁字掃描照舊）。
- 分享庫頁：伺服器把 `<!--EPHEMERAL_NOTICE-->` 換成警示橫幅（沿用既有
  `--gl-warn-*` token，新增 `.gl-banner-warn`），ETag 加 `-eph` 後綴；
  未宣告時頁面逐位元組不變。截圖目視確認。

## 驗證

- 新測試 13 項＋既有 D2 測試 13 項全綠；沙箱全套 2,201 passed，4 failed
  與未改動版本逐項相同（`test_grid_info_footer` 頁尾字型，沙箱缺字型；
  本機上次全綠）；node 323/323。
- 真 uvicorn 端到端：Gist 接本機假檔，打 /guide＋/teach→SIGTERM→Gist 寫入
  `{guide_page:1, teach_page:1}`；**換一個全新空的 METRICS_DIR**（模擬醒來
  磁碟全空）重啟再打一輪→`/api/metrics` 回 2/2、`since` 保留首輪時刻、
  `persistence: gist`，關機再寫回 2/2。
- 分享庫頁 Playwright 截圖：警示橫幅在說明橫幅上方，配色正確。

## 使用者待辦

依 `docs/PUBLIC_DEPLOYMENT.md`「計數器跨重啟累計」建私密 Gist＋只勾 `gist`
權限的 token，填進 Render Environment。驗收：`/api/metrics` 的
`persistence` 為 `gist`。若 Render 未自動同步 render.yaml 新增的
`STROKE_ORDER_EPHEMERAL_STORAGE`，需在 Dashboard 手動加。
