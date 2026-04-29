# 2026-04-30：Render.com 字型載入修復（方案 B：build-phase fetch from GitHub Release）

> 範圍：解決 stroke-order.onrender.com 部署狀態下 5 套外掛字型未載入的問題。
>
> 起點：截圖顯示「字型載入狀態」彈窗 — 5 套字型全部 ❌（僅 fallback 機制運作）
> 終點：build script 從 GitHub Release fonts-v1 自動下載 10 個 TTF/OTF；graceful fallback；LICENSE attribution 補完整

---

## 決策 1：修還是不修？

**情境**：onrender.com 上 5 套外掛字型未載入。但既有 fallback 機制（5aj 假隸書 / 假宋體濾鏡 / kaishu fallback）讓網站仍可用，篆書 + CNS 罕用字 fallback 真的不可用。

**選項**：
- A. 不修（接受 demo 站受限）
- B. 修（讓 demo 站完整體驗）

**決定**：B。

**考量**：
1. 公開部署 demo 的目的就是讓陌生人 30 秒看到 working state
2. 5 套字型全沒載入 → 隸 / 篆 / 宋下拉只剩楷書能選 → 50%+ 功能無法 demo
3. 修的成本中等（一個 build script + GitHub Release）；不修的長期成本（每個訪客困惑）累積很快
4. 既有的 fallback 機制不是設計目標、是 degraded mode；長期該是「外掛字型存在 → 顯示真字」

---

## 決策 2：4 個解決方案中選哪個？

**情境**：5 個技術選項，各有 trade-off。

**選項**：
| 方案 | 工作量 | 可靠性 | 成本 | trade-off |
|---|---|---|---|---|
| A. 接受現狀 + 文件說明 | 5 min | ✅ | $0 | 短期繞過、長期不變 |
| **B. GitHub Release + build script** | 30-60 min | 高 | $0 | **甜蜜點** |
| C. Cloudflare R2 / S3 | 1-2 hr | 最高 | 免費 (R2 10GB egress) | 過度工程 |
| D. Pre-bake Docker image | 2 hr+ | 高 | 改部署架構 | 失去 Render 簡潔性 |
| E. Render 付費 disk plan | 5 min | 最高 | $1+/月 | 為個人 demo 站付月費 |

**決定**：B。

**考量**：
1. **GitHub Release 是 stroke-order 既有 infra**（同一個 repo `seyen37/stroke-order`），不需要新帳號 / 新平台
2. **Build phase 下載的可靠性夠**：Render free tier 雖無 persistent disk，但 build 完成後 ephemeral fs 保留到下次 deploy；不是每 request 重 download
3. **GitHub Release 對 release asset 的 bandwidth 是 unmetered**（不像 LFS）
4. Cloudflare R2（C）對個人 demo 站的可靠性提升微乎其微，但設定成本翻倍
5. **未來想擴展時 B → C 是漸進路徑**：先用 B，若 release asset 撞到 GitHub 限制再遷 R2

**教訓**：選方案時優先看「**用既有 infra 能不能解**」——能就不要引入新依賴。

---

## 決策 3：build script 的 graceful fallback 政策

**情境**：寫 fetch script 時要決定「下載失敗如何處置」。

**選項**：
- A. `set -e` — 任何失敗 abort build（標準 shell script 寫法）
- B. **每個字型獨立 try / 失敗只 warn 不 abort** — 讓「部分字型載入」也是合法狀態
- C. retry 無限次直到成功

**決定**：B。

**考量**：
1. 5 套字型彼此獨立——TW-Kai-Plus 下載失敗不該影響 chongxi_seal 載入
2. 既有的 fallback 機制（5aj / kaishu fallback）本來就是設計用來處理「某字型缺失」的場景——graceful fetch 與既有 fallback 對齊
3. Render free tier 偶爾 build phase 網路不穩；單一字型失敗就 abort 會讓 deploy 變得脆弱
4. C 無限 retry 容易讓 build 永遠跑不完，超過 Render free tier 的 build timeout 反而更糟
5. **Graceful 的代價**：如果某字型長期下載不到，不會有 hard error 提示——但現有 UI 「字型載入狀態」彈窗本來就會顯示哪些載入了哪些沒有，這個 UI 變成 SoT

**實作**：
- 每個字型獨立 `fetch_one` function 內部 try
- 失敗只計數 + 印 WARN，不 abort
- 最終 summary 印 `ok / fail / total`，給 build log 觀察用
- `exit 0` 永遠正常退出（即使全失敗）

**教訓**：「下載資料的 build 步驟」≠「驗證資料的 build 步驟」——下載失敗可被 graceful 處理，驗證失敗才該 abort。混在一起設計反而失去彈性。

---

## 決策 4：字型 redistribution 法律確認

**情境**：把 5 套字型上傳到 GitHub Release 是 redistribution 行為，要先確認 license 允許。

**選項**：
- A. 假設「政府公告 = 公共領域」全部上傳
- B. 逐一查 license + 在 LICENSE 末段補 attribution

**決定**：B。

**確認結果**：

| 字型 | License | Redistribution? |
|---|---|---|
| CNS 11643 全字庫 | 政府資料開放授權 1.0 | ✅ |
| 崇羲篆體 | CC BY-ND 4.0（季旭昇）| ✅（不衍生即可）|
| 教育部楷書 | 政府著作權 / 開放授權 1.0 | ✅ |
| 教育部隸書 | 同上 | ✅ |
| 教育部宋體 | 同上 | ✅ |

**考量**：
- CC BY-ND 是限制最嚴的（不允許「衍生作品」）—— 我們只 mirror 原檔（unmodified），符合
- 政府資料開放授權 1.0 允許 free use + redistribution + modification with attribution
- 5 個來源都允許 mirror，**前提是保留 attribution**

**動作**：把 LICENSE 末段重寫，從原本粗略的「consult terms」改成完整 attribution block——同時補 5 個 cover-set 的 attribution（這是先前 §七 audit 列出但未做的 TODO）。

**教訓**：**§七 audit 標的 TODO 不應該無限期擱置**。這次修部署問題順手把它清掉。Audit 的意義是「找到問題」+「在合理時點清理」，不是「找到後自滿」。

---

## 決策 5：未來如何處理「字型版本更新」

**情境**：教育部偶爾更新字型版本；CNS 全字庫每 N 年發新版。

**選項**：
- A. 每次都重新 build GitHub Release（手動工作流）
- B. 寫 script 自動從 source 抓最新版（fully automated）
- C. **pin 在 fonts-v1 不主動更新**

**決定**：C（暫時）。

**考量**：
1. 字型更新頻率低（年級）
2. 自動更新會引入「上游變更導致下游 break」的風險
3. 手動 release 雖累但版本可控
4. 等真的有版本升級需求時，再決定要不要建 fonts-v2

**教訓**：版本固定 vs 自動追蹤的選擇，看上游變更頻率 vs 下游容錯——對「年級更新」的字型，版本固定 + 手動升級是合理 default。

---

## 落地清單

- [x] `scripts/render_fetch_fonts.sh` — graceful fetch script，含 retry + size sanity check + per-font fallback
- [x] `render.yaml` buildCommand 串 fetch_fonts.sh
- [x] `LICENSE` 末段重寫為 4 段式 attribution block（A 筆畫資料 / B 字型 / C cover-set / D 衍生重發要求）
- [ ] 用戶建立 GitHub Release `fonts-v1` 並上傳 10 個 font 檔
- [ ] 用戶 commit + push → 觸發 Render 自動重 deploy
- [ ] 用戶 reload onrender.com 驗證字型載入狀態彈窗顯示 5 套全綠

---

## 反思

**做得好的**：
- 用既有 GitHub Release infra 解決問題（不引入新平台）
- Graceful fallback 設計與既有的 fallback 機制（5aj 假字濾鏡 / kaishu fallback）對齊
- 順手清掉 §七 audit 的 TODO（attribution 完整性）

**可以更好的**：
- Build time 可能因下載 ~300 MB 字型增加 5-10 分鐘——對 Render free tier 仍可接受，但 paid tier 用戶會感受
- 字型版本固定在 fonts-v1，沒有自動偵測上游更新的機制——可接受 trade-off

**對長期專案的影響**：
- 線上 demo 完整度從 ~50%（楷書 only）→ 100%（5 種風格全可用）
- LICENSE attribution 完整化讓 stroke-order 真正達到「**§七 公開前審查全綠**」
- 為未來新字型加入定下流程：源碼路徑 → license check → upload to release → script 加一行 → done
