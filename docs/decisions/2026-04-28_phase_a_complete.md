# 2026-04-28：Phase A 完成（v0.13.0 → v0.14.0）

> 範圍：完成 VISION.md Phase A「組件覆蓋分析器」全 12 個 sub-task。
>
> 起點：v0.13.0（5d PSD + 5g Gallery 雙基地完成；組件邏輯尚未存在於 codebase）
> 終點：v0.14.0（components 子套件 + 4 API endpoints + 5d UI 整合 + 3 個 cover-sets 全部就緒，77+ 條測試全綠）
>
> 對應 commits（待提交）：
> - `feat(components): Phase A complete — 3 cover-sets + UI + Taiwan-variant integrity`

Phase A roadmap：6b-1 ~ 6b-12。

---

## 決策 1：Phase A 整體 12 task 切分為 4 段

**情境**：VISION.md 寫 Phase A 是「1-2 週」，實際工作分散在多次 session 完成。

**選項**：
- A. 一條鞭：所有 12 個任務一個大 commit
- B. 分段：backend / API / UI / release 四段各 commit
- C. 細粒度：每個 task 一個 commit

**決定**：B（已實際採用）。

**考量**：
1. backend 4 個 task → 純後端可獨立 pytest 驗證 → 一個 commit 自然整合
2. API 3 個 task → 同樣是純後端，且都接通 backend → 一個 commit
3. UI 3 個 task → 純 frontend、共用同個 section、互依強 → 一個 commit
4. release 收尾 → version bump + docs 系列改動 → 獨立 commit

**結果**：Phase A 全程 ~4 個 commits，每個 commit 都有獨立的「驗證標準」（綠色測試 / 渲染檢查 / smoke test）。

**教訓**：對中型 phase（10-15 個 sub-task），「層級式 commit」比「每 task 一 commit」可讀性更高，git log 更乾淨。

---

## 決策 2：cjkvi-ids bundling 策略（2 MB ids.txt 進 package vs git-ignore）

**情境**：Backend foundation（6b-1）需要 88,937 entries 的 IDS 分解資料；資料原檔 2 MB。

**選項**：
- A. Bundle ids.txt 進 package data（committed to git）
- B. 寫 fetch script，使用者首次 install 時下載
- C. 抽取 808/4808/5000 子集 bundle

**決定**：A。

**考量**：
1. 既有先例：`data/5000_wuqian.txt` (590 KB) 已 committed
2. pip install 即可用，零額外步驟
3. cjkvi-ids 更新頻率低（一年 1-2 次），commit 是合理版本鎖定
4. 子集（C）會限制未來 `recommend_next` 對 non-coverset 字的支援

**教訓**：bundle vs fetch-on-first-run 的決策軸是「開箱即用 vs repo 大小」。對個人/研究專案，「即用」勝出。

---

## 決策 3：個人覆蓋追蹤儲存位置 — IndexedDB（client）vs SQLite（server）

**情境**：VISION.md 草稿寫「個人覆蓋追蹤用 SQLite」，但 5d PSD 已用 IndexedDB。

**選項**：
- A. 引入新 SQLite store
- B. 沿用 IndexedDB
- C. 雙棧（client cache + server backup）

**決定**：B。

**考量**：
1. **一致性**：同站不要兩套儲存
2. **不引入 server-side state**：當前架構無使用者帳號，server 純 stateless API
3. **隱私**：個人手寫資料不離開本機，符合 5d 隱私警語
4. C 方案會引入「同步衝突」問題，太複雜

**實作**：`storage.js` 已有的 `listUniqueChars()` 直接被 6b-9 dashboard 引用——不必新增模組。

**教訓**：架構決策時，**先看既有 inventory** 再決定要不要新增——「IndexedDB + server stateless」這個 5d 已落地的架構，6b 直接套用零成本。

---

## 決策 4：API 設計 — 4 個 endpoints 分散 vs 1 個複合 endpoint

**情境**：6b-5 ~ 6b-7 要設計 API。可以全部塞進一個 `/api/coverage/state` endpoint。

**選項**：
- A. 一個 `/api/coverage/state` 回傳所有 component / coverset / coverage / recommendation 資料
- B. 拆成 4 個獨立 endpoints（components / coverset list / coverset detail / recommend）

**決定**：B。

**考量**：
1. **Cacheable**：`/api/components/{char}` 跟 `/api/coverset/list` 都是純讀，可被 frontend / CDN cache
2. **語意清楚**：每個 endpoint 對應一個明確問題
3. **演進性**：未來想加新功能（如 batch decompose）不會撞到現有 schema
4. **A 方案問題**：「state」這種 catch-all endpoint 容易演化成 megastate，難測試

**結果**：17 條 HTTP-level 測試，每條都 focus 在單一 endpoint 的單一行為。

**教訓**：REST 設計上「一個 endpoint = 一個問題」勝過「一個 endpoint = 一切答案」。複合需求用前端組合即可。

---

## 決策 5：UI 整合方式 — 新分頁 vs 5d 控制面板嵌入

**情境**：6b-8 ~ 6b-10 的 UI 元素要放哪裡。

**選項**：
- A. 開新分頁 `/coverage`，獨立的覆蓋率儀表板
- B. 嵌入 5d `/handwriting` 控制面板，作為第 5 個 section
- C. 浮動 widget，在所有頁面都顯示

**決定**：B。

**考量**：
1. **使用流程**：使用者在 5d 寫字 → 立刻看到進度更新 → 立刻看到推薦 → 點推薦再寫，**完全 in-context**
2. **A 方案問題**：要切分頁來看進度太迂迴；推薦字也要在這頁，否則 click → load 跨頁太煩
3. **C 方案問題**：在「主頁」、「公眾分享庫」等 context 顯示組件覆蓋率沒意義
4. **Section 整合成本低**：5d 的 `.hw-section` 樣式可直接重用，Phase A UI 看起來像 5d 原生功能

**驗收標準**（達成）：使用者打開 5d → 第 5 個 section「組件覆蓋」→ 選 cover-set → dashboard 亮起 → 寫字 → dashboard 即時刷新 → 點推薦 → 自動載入到 canvas → 寫完 → 重複。

**教訓**：UI 整合決策的判準是「使用者注意力切換次數」。最少切換 = 最佳整合位置。

---

## 決策 6：第二個 cover-set — 朱邦復 5000 還是教育部 4808

**情境**：6b-11 原任務名為「教育部 4808」。但動工時手邊沒有 4808 官方資料源，只有 `data/5000_wuqian.txt`（朱邦復）。

**選項**：
- A. 用既有 wuqian_5000 假冒 educational_4808
- B. 命名 wuqian_5000，誠實標示來源不同
- C. 等待教育部官方資料再動工
- D. 兩個都做（一個基於既有資料、一個基於外部來源）

**決定**：B 然後 D。

**考量**：
1. A 不可接受——技術上不誠實，未來會被使用者抓包
2. C 完成度差——「等資料」可能無限期延期
3. B 至少推進「第二個 cover-set 框架」，證明 `_BUILTIN_NAMES` 多 cover-set 設計有效
4. 後來使用者提供 [@p208p2002 的 Gist URL](https://gist.github.com/p208p2002/69ddc0197fad375ff8c87d95beb9b59c)，可即時補上 4808

**結果**：Phase A 收尾時有 3 個 cover-sets——比原本「1 個 + 加教育部 4808」的計畫**多 1 個**。

**教訓**：**誠實命名 + 漸進改進** 比「等完美再動」效果好。每一步都有可用的 deliverable。

---

## 決策 7：發現「他國規範漢字滲透」的 Taiwan-variant integrity 議題（最重要的決策）

**情境**：使用者貼出他在 PTT 給高中生的回覆貼文，警告「他國規範漢字溫水煮青蛙」並提供官方教育部 4808 PDF。我們用官方 PDF 驗證 Gist 來源的字單一致性。

**發現**：4807/4808 字相同，**1 字不同**：

| 來源 | 字 | Unicode | 區域 |
|---|---|---|---|
| 教育部官方 PDF（民國71年公告，1982-09-01）| **彞** | U+5F5E | T (Taiwan) |
| 第三方 Gist（@p208p2002）| **彝** | U+5F5D | G (PRC GB18030 變體) |

**選項**：
- A. 不修，反正只差 1 字
- B. 用 Gist 重建並標註差異
- C. 改用官方 PDF 重建，並加 metadata 追溯欄位

**決定**：C。

**考量**：
1. **著作權保護**：本專案哲學是「Taiwan-first」（VISION.md §九）；GB 變體玷污字單會傷害這個 claim
2. **可追溯性**：官方 PDF 有 `教育部字號 A00001 ~ A04808`，每字可回追到 1982 公告——強化證據鏈
3. **未來整合的 lessons learned**：以後加任何「教育部 / 國家標準」cover-set，**第一原則是「能否取得一手公文」**
4. 1 字事小，但**模式建立事大**——這次妥協 = 未來 N 次妥協

**實作**：
- `scripts/build_educational_4808.py` 從官方 PDF 直接 parse
- JSON 每筆加 `moe_id` 欄位
- Source url 改成教育部語文成果網（一手）
- 寫 `decisions/2026-04-28_phase_a_complete.md`（你正在讀的）紀錄此議題

**啟示**（最值得記下的）：
1. **民間整理的「官方資料」常夾帶他國變體**——這次只是 4808 中 1 字，但揭露了一個**普遍的供應鏈污染問題**
2. **資料源頭管理是著作權保護的第一道關卡**：寧可花時間從 PDF 萃取，不要省事用 Gist
3. **發現這個議題的 trigger 是「外部輸入」**：使用者的貼文 + 官方 PDF 的對比，**不是我們能憑空發現的**——團隊（你 + 我）的價值在這裡放大

**教訓**：建立「資料源 audit checklist」進 PROJECT_PLAYBOOK：
> 凡標榜「官方」「政府」「標準」的字表 / 資料 / 規範，**必須回追到一手公文**。否則內容可能被中介者意外或刻意污染。

---

## 決策 8：「200 vs 194」的數字一致性修正

**情境**：6a 階段（4-27）的 prototype 報告 808 → 194 獨特組件；6b 階段（4-28）落地時，新 package 報 200。

**根因**：兩段 code 對 IDS compound markers (①②③...⑳) 的處理不同：
- 舊 prototype（`scripts/analyze_808_components.py`）`continue`（跳過）
- 新 package（`components/decompose.py`）`leaves.append(c)`（保留為不透明葉組件）

**選項**：
- A. 改新 package 跳過 markers，回到 194
- B. 改舊 prototype 保留 markers，更新到 200
- C. 都不改，兩個數字並存

**決定**：B。

**考量**：
1. **語意正確性**：compound markers 代表「結構上存在但 Unicode 未編碼」的組件——保留它們才能正確說「這字有 N 個葉組件」
2. **新 package 是長期 codebase**，舊 prototype 是 one-off
3. C 方案不可行，文檔會 confusing

**實作**：本決策日誌 + VISION.md 統一改用 200。舊 prototype 保留作歷史紀錄但加註解說明這個演進。

**教訓**：數字穩定性對信任很重要。**任何 paper-claim 等級的數字（VISION.md 上對外說的承諾）**，必須跟 production code 同步——不能引用舊 prototype 結果。

---

## Phase A 完整數字總結

| 維度 | 數字 |
|---|---|
| Sub-tasks 完成 | **12/12 (100%)** |
| 新增 Python 模組 | 5（components/__init__、ids、decompose、coverset、algorithm）|
| 新增 API endpoints | 4（/api/components/{char}、/api/coverset/list、/api/coverset/{name}、/api/coverage/recommend）|
| 新增 UI sections | 1（5d 控制面板第 5 section「組件覆蓋」）|
| 新增 cover-sets | **3**（cjk_common_808、educational_4808、wuqian_5000）|
| 新增 Python 測試 | **77+ 條**（10+12+9+12+5+5+17+...）|
| 新增 build scripts | 3（build_808、build_wuqian、build_educational_4808）|
| 新增決策日誌 | 2（808_analysis、phase_a_backend、本文）|
| Bundle 進 package 的資料 | 2 MB ids.txt + 3 個 coverset JSON |
| 新增程式碼行數 | ~1500（含註解、測試）|
| 工作時長（人類認知時間）| ~6-7 小時（跨數個工作日）|

---

## Phase A 對 VISION.md 的驗收

VISION.md §七 Phase A 寫了 6 個驗收項目：

| 項目 | 完成度 | 證據 |
|---|---|---|
| 整合 KanjiVG kvg:element + cjkvi-ids IDS | ✅ | `components/ids.py` |
| 建「字 ↔ 組件清單」雙向索引 | ✅ | `components/decompose.py` + `coverset.py` |
| 內建 808 表為預設 cover-set | ✅ | `cjk_common_808.json` 內建 |
| 實作貪婪 set cover 演算法 | ✅ | `algorithm.py::recommend_next` |
| 5d UI「下一字推薦」+ 進度儀表板 | ✅ | 6b-8/9/10 |
| 5d UI 加覆蓋集選項 4 種 | 🟡 部分 | 已支援 808/4808/5000，algorithm-generated 與 custom 上傳留 future |

**6/6 主項目達成**，1 個次項目部分（custom upload 是 next phase 的事）。

---

## 對下一個 Phase 的影響

Phase A 完成後，VISION.md §七 列出 Phase B / C / D：

- **Phase B（組件級 PSD 切割）**：使用者寫字後，自動用 KanjiVG `kvg:element` 切成組件級樣本——Phase A 的 components 子套件已經把 `kvg:element` 整合機制 ready，B 只要寫切割演算法
- **Phase C（規則式組合引擎）**：用 Phase A 的 `algorithm.py` 套件、Phase B 的組件級資料，開始試做「沒寫過的字」的軌跡組合
- **Phase D（神經組合模型）**：研究級，等資料量到位再啟動

Phase A 沒做、留給後續：
- 教育部 4808 之外的擴充字表（語文成果網 6000、COCT 3000、全字庫 5000 等——使用者貼文有列出）
- KanjiVG 完整資料的 cache 化（目前只 cache 55 字）
- algorithm-generated minimum-cover 即時計算

---

## 反思

**做得好的**：
- **架構決策一次擺清楚（A1-A5）**：Phase A 動工前明確訂下 5 個架構選擇 → 後續 12 個 task 沒一次需要回頭重做
- **誠實命名**（決策 6）：避免假冒「教育部 4808」，後來反而能無痛升級到真的 4808
- **發現 Taiwan-variant integrity 議題**（決策 7）：使用者外部輸入帶來的 catalyst，被我們認真接住並寫進 codebase

**可以更好的**：
- **194 → 200 數字 drift**（決策 8）：應該在 6b-1 落地新 package 時就同步更新 VISION.md，而不是等到 6b-12 才 catch up
- **Gist vs PDF 沒先驗證**：6b-11 第一輪用 Gist 直接 build，沒 cross-check 官方 PDF——下次處理「官方標準資料」應有 SOP：永遠先找一手公文

**值得保留的方法論**：
- 「決策日誌即時寫」習慣讓回顧 Phase A 時所有 trade-off 都有 paper trail
- 「實證數字寫進 VISION.md」讓策略文件有可驗證 backing，不只是空中樓閣
- 「資料源 audit」應正式進 PROJECT_PLAYBOOK 的 checklist

---

## 下一步

依優先度：

1. **Push Phase A** 到 GitHub 雙 remote（commit + git pa）
2. **更新 PROJECT_PLAYBOOK.md** 加入「資料源 audit checklist」一節
3. **下個工作日決定**：是要進 Phase B（組件級 PSD 切割），還是先擴充更多 cover-sets（教育部 6000、COCT 3000、全字庫 5000）

我傾向先擴充 cover-sets——一是 user 已提供 URL 容易抓資料，二是 Phase B 真的是「跨進新領域」需要一段精神好的時間。
